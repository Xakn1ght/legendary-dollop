from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.shared.admin_access import ADMIN_IDS


def get_admin_broadcast_ids() -> list[int]:
    # Expandable later (could load from settings.json). For now single ADMIN_ID
    return ADMIN_IDS

async def _send_pending_requests(
    bot: Bot,
    session: AsyncSession,
    admin_chat_id: int,
    message_id: int | None = None,
):
    """Send or refresh the pending-requests list for *admin_chat_id*.

    If *message_id* is provided, an attempt is made to **edit** that message; otherwise a
    new message is sent. The function collates pending subscription, toggle and charge
    requests and shows them as inline-keyboard buttons so the admin can inspect them.
    """
    pending = await crud.get_pending_charge_requests(session)
    subs_pending = await crud.get_pending_subscriptions(session)
    toggles_pending = await crud.get_pending_toggle_subscriptions(session)

    # Nothing to show → simply notify and return
    if not pending and not subs_pending and not toggles_pending:
        text = "No pending requests."
        if message_id:
            try:
                await bot.edit_message_text(text, chat_id=admin_chat_id, message_id=message_id)
            except Exception:
                pass  # message might have been deleted – ignore
        else:
            await bot.send_message(admin_chat_id, text)
        return

    # Build keyboard – one button per pending item
    kb = InlineKeyboardBuilder()

    for sub in subs_pending:
        kb.button(
            text=f"🆕 Sub #{sub.id} – {sub.user.full_name[:10]}",
            callback_data=f"show_sub_{sub.id}"
        )

    for sub in toggles_pending:
        label = "🚫 Disable" if sub.status == "pending_disable" else "✅ Enable"
        kb.button(
            text=f"{label} #{sub.id} – {sub.user.full_name[:10]}",
            callback_data=f"show_toggle_{sub.id}"
        )

    for req in pending:
        kb.button(
            text=(
                f"Charge #{req.id} – "
                f"{(req.user.username if req.user and req.user.username else req.user.chat_id if req.user else req.user_id)}"
            ),
            callback_data=f"show_charge_{req.id}"
        )

    kb.adjust(1)

    text = "Pending requests:"
    if message_id:
        try:
            await bot.edit_message_text(
                text,
                chat_id=admin_chat_id,
                message_id=message_id,
                reply_markup=kb.as_markup(),
            )
        except Exception:
            # Fallback – maybe original msg removed
            await bot.send_message(admin_chat_id, text, reply_markup=kb.as_markup())
    else:
        await bot.send_message(admin_chat_id, text, reply_markup=kb.as_markup()) 