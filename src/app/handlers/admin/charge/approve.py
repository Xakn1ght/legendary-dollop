import logging

from aiogram import Bot, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.handlers.admin.common import _send_pending_requests
from app.services.flows.charge import approve_charge as approve_charge_flow
from app.services.flows.errors import FlowError
from app.utils.admin_bot_helper import get_user_bot
from app.utils.bot_i18n import t

from .common import _admin_lang, router

# FlowError code → admin-facing i18n key
_ERROR_KEYS = {
    "not_found_or_handled": "admin_charge_not_found_or_handled",
    "sub_invalid": "admin_charge_sub_invalid",
    "user_missing": "admin_charge_user_missing",
    "sub_inactive": "admin_charge_sub_inactive",
    "panel_fetch_failed": "admin_charge_fetch_panel_failed",
    "panel_reset_failed": "admin_charge_panel_reset_failed",
    "panel_update_failed": "admin_charge_panel_update_failed",
}


@router.callback_query(F.data.startswith("approve_charge_"))
async def approve_charge(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    lang = await _admin_lang(session, callback.from_user)
    charge_id = int(callback.data.split("_")[2])

    user_bot = get_user_bot()
    if not user_bot:
        await callback.answer("User bot unavailable (BOT_TOKEN).", show_alert=True)
        return

    try:
        await approve_charge_flow(session, charge_id, user_bot=user_bot)
    except FlowError as e:
        key = _ERROR_KEYS.get(e.code, "admin_charge_not_found_or_handled")
        await callback.answer(t(lang, key), show_alert=True)
        return

    await callback.answer(t(lang, "admin_charge_approved"))
    try:
        await callback.message.delete()
    except Exception:
        pass
    await _send_pending_requests(bot, session, callback.from_user.id, None)

    try:
        from app.api.routes.admin_ws import broadcast_admin_event

        await broadcast_admin_event("receipts_updated", {"charge_id": charge_id})
    except Exception as e:
        logging.warning(f"Failed to broadcast charge approval to admin panel: {e}")
