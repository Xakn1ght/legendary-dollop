"""Single write path for user notifications (phase 1 of the notification rework).

`notify()` owns the full lifecycle of one user notification:

    row insert (notifications table) -> optional bot DM -> stamp -> WS publish seam

Callers (bot handlers, API routes, jobs) pass an AsyncSession, the internal
user id, a `NotificationType` and the template ctx; wording, DM policy,
category/icon/deeplink all come from `core/notification_catalog.py`. Nothing
is migrated onto this path yet — call sites move over in later phases.

Design spec: docs/design-specs/specs/2026-07-20-notification-center-rework-design.md
(section 1, "Single write path").
"""
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.notification_catalog import (
    CATALOG,
    DEFAULT_CATEGORY,
    DEFAULT_ICON,
    NotificationType,
    render,
    template_placeholders,
)
from app.database import notifications_crud
from app.database.models import Notification, User
from app.utils.admin_bot_helper import resolve_user_bot

logger = logging.getLogger(__name__)


def _resolve_bot():
    """Resolve the bot used for user DMs.

    Same resolution as the existing call sites: prefer the aiohttp-embedded
    user bot, else a lazily-created client from BOT_TOKEN. Kept as a module
    attribute so tests can stub it (no network in tests).
    """
    return resolve_user_bot(None)


async def _publish(user_id: int, payload: dict) -> None:
    """WS publish seam — phase 4 wires the dashboard WebSocket here.

    Contract: called after the notification row is committed with
    ``{"notification": <to_payload dict>, "unread_count": <int>}``; failures
    must never propagate into notify().
    """
    return None


async def notify(
    session: AsyncSession,
    user_id: int,
    type_: NotificationType | str,
    ctx: dict | None = None,
    *,
    ticket_id: int | None = None,
    dm_override: bool | None = None,
    dm_reply_markup=None,
) -> Notification:
    """Create a notification for a user and deliver it per catalog policy.

    - Renders title/body in the user's language (User.language, default fa).
    - Writes the row through the existing crud create (sent_to_webapp=True,
      sent_to_bot per the effective DM decision) in the caller's session.
    - Sends the plain-text bot DM when the catalog says so and stamps
      bot_message_sent/bot_message_id. A DM failure never blocks the row.
    - dm_override: None (default) follows the catalog DM policy; False
      suppresses the DM (call site delivers its own rich transactional DM,
      or the user is live on the page); True forces it (admin broadcast
      with "also send to bot").
    - dm_reply_markup: optional inline keyboard attached to the DM
      (e.g. the ticket WebApp deep-link button). Ignored when no DM is sent.
    - Publishes to the WS seam after the commit-safe point.

    Raises ValueError for an unknown notification type.
    """
    nt = NotificationType(type_)  # ValueError for unknown types
    entry = CATALOG[nt]
    send_dm = entry.dm if dm_override is None else bool(dm_override)

    user = await session.get(User, user_id)
    lang = (user.language if user is not None else None) or "fa"
    title, body = render(nt, lang, ctx)

    notification = await notifications_crud.create_notification(
        db=session,
        user_id=user_id,
        type=nt.value,
        title=title,
        message=body,
        ticket_id=ticket_id,
        sent_to_webapp=True,
        sent_to_bot=send_dm,
    )

    if send_dm:
        await _send_dm(session, notification, user, title, body, reply_markup=dm_reply_markup)

    # Commit-safe point: the row (and any DM stamps) are persisted; push to
    # open dashboard sessions. Failures here must never undo the notification.
    try:
        unread_count = await notifications_crud.get_unread_count(session, user_id)
        await _publish(user_id, {"notification": to_payload(notification), "unread_count": unread_count})
    except Exception:
        logger.warning("notify: WS publish failed for notification %s", notification.id, exc_info=True)

    return notification


async def _send_dm(session: AsyncSession, notification: Notification, user: User | None,
                   title: str, body: str, *, reply_markup=None) -> None:
    """Send the bot DM for a dm=True notification and stamp the row.

    On any failure (no bot, no chat_id, Telegram error) the row survives with
    bot_message_sent=False AND sent_to_bot flipped back to False: a row that
    never got its DM must not look "pending" to any later sweep (the old
    process_pending_bot_notifications-style replay bug, where flipping a
    broadcast to bot-enabled re-sent stale rows, is fixed by construction).
    """
    bot = _resolve_bot()
    try:
        if bot is None or user is None or not user.chat_id:
            raise RuntimeError("user bot or recipient chat_id unavailable")
        sent = await bot.send_message(chat_id=user.chat_id, text=f"{title}\n\n{body}",
                                      reply_markup=reply_markup)
        notification.bot_message_sent = True
        notification.bot_message_id = getattr(sent, "message_id", None)
    except Exception as e:
        logger.warning(
            "notify: DM failed for notification %s (user %s): %s",
            notification.id, notification.user_id, e,
        )
        notification.sent_to_bot = False
    await session.commit()


def to_payload(n: Notification) -> dict:
    """Shape one notification row for the API/WS payload.

    Adds the computed category/icon/deeplink from the catalog. Legacy rows
    with unknown types stay valid: category=system, default icon, no deeplink.
    """
    try:
        entry = CATALOG[NotificationType(n.type)]
        category, icon = entry.category, entry.icon
        deeplink = entry.deeplink
        if deeplink and "ticket_id" in template_placeholders(deeplink):
            deeplink = deeplink.format(ticket_id=n.ticket_id) if n.ticket_id else None
    except ValueError:
        category, icon, deeplink = DEFAULT_CATEGORY, DEFAULT_ICON, None

    return {
        "id": n.id,
        "type": n.type,
        "title": n.title,
        "message": n.message,
        "ticket_id": n.ticket_id,
        "read": n.read,
        "created_at": n.created_at.isoformat() if n.created_at else None,
        "category": category,
        "icon": icon,
        "deeplink": deeplink,
    }
