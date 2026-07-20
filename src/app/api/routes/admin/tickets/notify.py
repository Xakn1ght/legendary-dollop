"""Shared side effects after an admin posts into a ticket (text or photo):
notification row + Telegram deep-link DM through the notify() single write
path (DM skipped while the user is live on the support page), and WebSocket
broadcasts."""

from app.core.notification_catalog import NotificationType
from app.services.notify import notify
from app.utils.bot_i18n import normalize_lang

from ..common import *  # noqa: F403


async def notify_user_after_admin_message(request, session, ticket, ws_payload: dict, status_changed: bool):
    """Call after the TicketMessage row is committed. Commits the notification row."""
    ticket_id = ticket.id
    user = await session.get(User, ticket.user_id)
    ticket_owner_chat_id = user.chat_id if user else None

    # If the user currently has the support page open, don't spam Telegram.
    user_is_live = False
    try:
        from app.api.routes.admin_ws import is_user_connected_to_support, is_user_watching_ticket

        user_is_live = bool(
            ticket_owner_chat_id
            and (
                is_user_watching_ticket(ticket_owner_chat_id, ticket_id)
                or is_user_connected_to_support(ticket_owner_chat_id)
            )
        )
    except Exception:
        user_is_live = False

    from app.core.settings import DASHBOARD_PUBLIC_BASE_URL

    url = f"{DASHBOARD_PUBLIC_BASE_URL}/webapp/dashboard/support.html?ticket_id={ticket_id}"
    kb = InlineKeyboardBuilder()
    label = "Open support" if normalize_lang(getattr(user, "language", None)) == "en" else "باز کردن پشتیبانی"
    kb.button(text=label, web_app=WebAppInfo(url=url))
    kb.adjust(1)

    await notify(
        session,
        ticket.user_id,
        NotificationType.TICKET_NEW_MESSAGE,
        {"ticket_no": ticket.user_ticket_number or ticket_id},
        ticket_id=ticket_id,
        dm_override=False if user_is_live else None,
        dm_reply_markup=kb.as_markup(),
    )

    try:
        await broadcast_ticket_update(ticket_id, "new_message", ws_payload, ticket_user_id=ticket_owner_chat_id)
    except Exception:
        pass

    if status_changed:
        try:
            await broadcast_ticket_update(
                ticket_id,
                "status_change",
                {
                    "status": ticket.status,
                    "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
                },
                ticket_user_id=ticket_owner_chat_id,
            )
        except Exception:
            pass
