from aiogram import Bot, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.database.models import ReferralReward
from app.utils.validation import BusinessLogicValidator, InputValidator

from .common import _parse_reward_callback, router
from .redeem_helpers import (
    _redeem_credit,
    _redeem_days,
    _redeem_star,
    _redeem_traffic,
)


@router.callback_query(F.data.startswith("redeem_"))
async def redeem_voucher(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    """Universal voucher redemption path for all redeem_* callbacks."""
    if not InputValidator.validate_callback_data(callback.data):
        await callback.answer("درخواست نامعتبر.", show_alert=True)
        return

    rtype, reward_id, star_cnt = _parse_reward_callback(callback.data)
    if rtype is None:
        await callback.answer("درخواست نامعتبر.", show_alert=True)
        return

    validation_result = BusinessLogicValidator.validate_reward_redemption(
        callback.from_user.id, rtype, star_cnt or 1
    )
    if not validation_result["is_valid"]:
        await callback.answer("پارامترهای درخواست نامعتبر است.", show_alert=True)
        return

    user = await crud.get_user(session, callback.from_user.id)
    if not user:
        await callback.answer("ابتدا باید با /start ثبت‌نام کنید.", show_alert=True)
        return

    reward: ReferralReward | None = await session.get(ReferralReward, reward_id)
    if not reward or reward.spent:
        await callback.answer("این بن قبلا استفاده شده است.", show_alert=True)
        return
    if reward.referrer_id != user.id:
        await callback.answer("این بن متعلق به شما نیست.", show_alert=True)
        return

    if rtype == "traffic":
        await _redeem_traffic(callback, session, bot, reward)
    elif rtype == "days":
        await _redeem_days(callback, session, bot, reward)
    elif rtype == "credit":
        await _redeem_credit(callback, session, bot, reward)
    elif rtype == "star":
        await _redeem_star(callback, session, bot, reward, star_cnt or 1)
    else:
        await callback.answer("نوع بن ناشناخته.", show_alert=True)
