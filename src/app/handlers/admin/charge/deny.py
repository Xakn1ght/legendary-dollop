import logging

from aiogram import Bot, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.notification_catalog import NotificationType, charge_denied_ctx
from app.database import crud
from app.handlers.admin.common import _send_pending_requests
from app.services.flows.charge import deny_charge as deny_charge_flow
from app.services.flows.errors import FlowError
from app.services.notify import notify
from app.utils.bot_i18n import normalize_lang, t

from .common import _admin_lang, router


@router.callback_query(F.data.startswith("deny_charge_"))
async def deny_charge(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    lang = await _admin_lang(session, callback.from_user)
    charge_id = int(callback.data.split("_")[2])

    try:
        result = await deny_charge_flow(session, charge_id)
    except FlowError:
        await callback.answer(t(lang, "admin_charge_not_found_or_handled"), show_alert=True)
        return

    user = await crud.get_user_by_id(session, result.user_id)

    # Notification row + policy DM through the single write path (the old
    # ad-hoc plain DM duplicated the row content and is gone).
    try:
        ctx = charge_denied_ctx(
            normalize_lang(getattr(user, "language", None)),
            service_name=result.service_name,
            credit_refunded=result.credit_refunded,
        )
        await notify(session, result.user_id, NotificationType.CHARGE_DENIED, ctx)
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
