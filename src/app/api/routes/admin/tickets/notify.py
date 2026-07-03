"""Shared side effects after an admin posts into a ticket (text or photo):
Telegram deep-link DM (skipped while the user is live on the support page),
dashboard notification row, and WebSocket broadcasts."""

from app.utils.admin_bot_helper import resolve_user_bot

from ..common import *  # noqa: F403


async def notify_user_after_admin_message(request, session, ticket, ws_payload: dict, status_changed: bool):
    """Call after the TicketMessage row is committed. Commits the notification row."""
    ticket_id = ticket.id
    user = await session.get(User, ticket.user_id)

    bot = resolve_user_bot(request.app.get("bot"))
    ticket_owner_chat_id = user.chat_id if user else None
    if bot and user and user.chat_id:
        try:
            from app.api.routes.admin_ws import is_user_connected_to_support, is_user_watching_ticket
            from app.core.settings import DASHBOARD_PUBLIC_BASE_URL

            url = f"{DASHBOARD_PUBLIC_BASE_URL}/webapp/dashboard/support.html?ticket_id={ticket_id}"
            kb = InlineKeyboardBuilder()
            kb.button(text="🎫 باز کردن پشتیبانی", web_app=WebAppInfo(url=url))
            kb.adjust(1)

            # If the user currently has the support page open, don't spam Telegram.
            if not (
                ticket_owner_chat_id
                and (
                    is_user_watching_ticket(ticket_owner_chat_id, ticket_id)
                    or is_user_connected_to_support(ticket_owner_chat_id)
                )
            ):
                visible_no = ticket.user_ticket_number or ticket_id
                await bot.send_message(
                    user.chat_id,
                    f"📩 پیام جدید پشتیبانی برای تیکت #{visible_no}\n"
                    "برای مشاهده و پاسخ، دکمه زیر را بزنید:",
                    reply_markup=kb.as_markup(),
                )
        except Exception:
            pass

    await notifications_crud.create_notification(
        db=session,
        user_id=ticket.user_id,
        type="ticket_new_message",
        title=f"پاسخ جدید به تیکت #{ticket_id}",
        message="پشتیبانی به تیکت شما پاسخ داده است",
        ticket_id=ticket.id,
        sent_to_webapp=True,
    )
    await session.commit()

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
