from aiogram import Bot, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.handlers.user.purchase import PLANS
from app.services.marzban import marzban_api

from .common import _patch_marzban_user, router


def _parse_free_renew_callback(data: str):
    try:
        _, _, sid = data.split("_", 2)
        return int(sid)
    except ValueError:
        return None


@router.callback_query(F.data.startswith("free_renew_"))
async def free_renew_legacy(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    """Legacy free renewal handler (kept for existing keyboards)."""
    sub_id = _parse_free_renew_callback(callback.data)
    if sub_id is None:
        await callback.answer("نامعتبر.", show_alert=True)
        return
    await _apply_free_renew(callback, session, bot, sub_id)


@router.callback_query(F.data.startswith("enhanced_free_renew_"))
async def enhanced_free_renewal(callback: CallbackQuery, session: AsyncSession):
    sub_id = int(callback.data.split("_")[3])
    await _apply_free_renew(callback, session, callback.message.bot, sub_id)


async def _apply_free_renew(
    callback: CallbackQuery, session: AsyncSession, bot: Bot, sub_id: int
):
    """Shared helper implementing the renewal itself."""
    from app.database.models import Subscription

    user = await crud.get_user(session, callback.from_user.id)
    subscription = await session.get(Subscription, sub_id) if sub_id else None
    if not subscription or subscription.user_id != user.id:
        await callback.answer("اجازه ندارید.", show_alert=True)
        return
    if user.stars < 99999:
        await callback.answer("این قابلیت دیگر پشتیبانی نمی‌شود.", show_alert=True)
        return

    plan_info = PLANS.get(subscription.plan_name)
    if not plan_info:
        await callback.answer("پلن ناشناخته.", show_alert=True)
        return

    user_info = await marzban_api.get_user_info(subscription.marzban_username)
    if not user_info:
        await callback.answer("خطای اطلاعات سرویس.", show_alert=True)
        return

    add_bytes = int(plan_info["gb"] * 1024**3)
    new_limit = (user_info.get("data_limit") or 0) + add_bytes
    new_expire = (user_info.get("expire") or 0) + 30 * 24 * 60 * 60

    success = await _patch_marzban_user(
        subscription.marzban_username,
        {"data_limit": new_limit, "expire": new_expire, "status": "active"},
    )
    if not success:
        await callback.answer("تمدید انجام نشد.", show_alert=True)
        return

    await crud.StarManager.reset_stars(session, user.id, reason="free_renewal", source_id=sub_id)
    await callback.answer("✅ تمدید رایگان انجام شد!", show_alert=True)
    await bot.send_message(
        user.chat_id,
        f"سرویس {subscription.marzban_username} برای ۳۰ روز دیگر تمدید و {plan_info['gb']}GB ترافیک افزوده شد. ستاره‌های شما ریست شد.",
    )

    from ..wallet import show_wallet

    await show_wallet(callback, session)
