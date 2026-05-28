from datetime import datetime

from aiogram import Bot, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import PLANS
from app.database import crud
from app.handlers.admin.common import ADMIN_IDS, _send_pending_requests
from app.utils.admin_bot_helper import get_user_bot
from app.utils.bot_i18n import t

from .common import _admin_lang, router


@router.callback_query(F.data.startswith("approve_booking_"))
async def approve_booking(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    lang = await _admin_lang(session, callback.from_user)
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(lang, "not_authorized"), show_alert=True)
        return

    try:
        payload = callback.data.split("_", 2)[2]
        charge_id_str, plan_name = payload.split(":", 1)
        charge_id = int(charge_id_str)
    except Exception:
        await callback.answer(t(lang, "admin_booking_invalid_payload"), show_alert=True)
        return

    charge_req = await crud.get_charge_request(session, charge_id)
    if not charge_req or charge_req.status != "pending":
        await callback.answer(t(lang, "admin_booking_not_found_or_handled"), show_alert=True)
        return

    await session.refresh(charge_req, attribute_names=["subscription", "user"])
    sub = charge_req.subscription
    user = charge_req.user
    if not sub or not user:
        await callback.answer(t(lang, "admin_booking_related_missing"), show_alert=True)
        return

    user_bot = get_user_bot()
    if not user_bot:
        await callback.answer("User bot unavailable (BOT_TOKEN).", show_alert=True)
        return

    await crud.update_charge_request_status(session, charge_id, "approved")

    plan_info = PLANS.get(plan_name, {})
    await crud.update_subscription_renewal(
        session,
        sub.id,
        renewal_paid=True,
        renewal_template=plan_name,
        renewal_price=plan_info.get("price"),
        renewal_requested_at=datetime.utcnow(),
    )

    await user_bot.send_message(
        user.chat_id,
        (
            "✅ رزرو پلن شما تایید شد.\n\n"
            f"📦 پلن: {plan_name} ({plan_info.get('gb', '—')} GB)\n"
            f"💵 مبلغ: {charge_req.price:,} تومان\n\n"
            "🔄 در زمان مناسب به صورت خودکار اعمال می‌شود."
        ),
    )

    await callback.answer(t(lang, "admin_booking_approved"))
    try:
        await callback.message.delete()
    except Exception:
        pass
    await _send_pending_requests(bot, session, callback.from_user.id, None)
