import logging

from aiogram import Bot, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud, notifications_crud
from app.handlers.admin.common import _send_pending_requests
from app.utils.admin_bot_helper import get_user_bot
from app.utils.bot_i18n import t

from .common import _admin_lang, router


@router.callback_query(F.data.startswith("deny_charge_"))
async def deny_charge(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    lang = await _admin_lang(session, callback.from_user)
    charge_id = int(callback.data.split("_")[2])
    charge_req = await crud.get_charge_request(session, charge_id)
    if not charge_req or charge_req.status != "pending":
        await callback.answer(t(lang, "admin_charge_not_found_or_handled"), show_alert=True)
        return

    await session.refresh(charge_req, attribute_names=["subscription", "user"])

    await crud.update_charge_request_status(session, charge_id, "denied")

    user_bot = get_user_bot()
    if user_bot:
        await user_bot.send_message(
            charge_req.user.chat_id,
            "❌ درخواست شارژ شما توسط ادمین رد شد. در صورت نیاز دوباره تلاش کنید.",
        )

    try:
        service_name = charge_req.subscription.marzban_username if charge_req.subscription else "your service"
        await notifications_crud.create_notification(
            session,
            user_id=charge_req.user_id,
            type="charge_denied",
            title="Charge denied",
            message=f"❌ Your charge request for {service_name} was denied.",
            sent_to_webapp=True,
            sent_to_bot=False,
        )
    except Exception:
        pass

    await callback.answer(t(lang, "admin_charge_denied"))
    try:
        await callback.message.delete()
    except Exception:
        pass
    await _send_pending_requests(bot, session, callback.from_user.id, None)

    try:
        from app.api.routes.admin_ws import broadcast_admin_event

        await broadcast_admin_event("receipts_updated", {"charge_id": charge_id})
    except Exception as e:
        logging.warning(f"Failed to broadcast charge denial to admin panel: {e}")
