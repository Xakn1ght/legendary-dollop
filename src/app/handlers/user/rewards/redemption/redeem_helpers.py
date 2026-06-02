from aiogram import Bot
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.database.models import ReferralReward, UserStarRewardClaim
from app.services.marzban import marzban_api
from app.utils.logger import bot_logger
from app.utils.text_format import to_persian_digits

from .common import _patch_marzban_user


async def _redeem_traffic(
    callback: CallbackQuery, session: AsyncSession, bot: Bot, reward: ReferralReward
):
    user = await crud.get_user(session, callback.from_user.id)
    subs = await crud.get_user_active_subscriptions(session, user.id)
    if not subs:
        await callback.answer("شما سرویس فعالی ندارید.", show_alert=True)
        return
    sub = subs[0]
    user_info = await marzban_api.get_user_info(sub.marzban_username)
    if not user_info:
        await callback.answer("نشد! اطلاعات سرویس یافت نشد.", show_alert=True)
        return
    new_limit = (user_info.get("data_limit") or 0) + (reward.traffic_bytes or 0)
    if not await _patch_marzban_user(sub.marzban_username, {"data_limit": new_limit}):
        await callback.answer("خطا در افزایش ترافیک.", show_alert=True)
        return

    await crud.spend_reward(session, reward.id)

    await callback.answer("✅ ترافیک شما افزایش یافت!", show_alert=True)
    try:
        await callback.message.edit_text(
            f"🎁 بن استفاده شد: +{to_persian_digits(f'{reward.traffic_bytes/(1024**3):.0f}')} گیگابایت افزوده شد."
        )
    except Exception:
        pass
    await bot.send_message(
        user.chat_id,
        f"🎉 +{to_persian_digits(f'{reward.traffic_bytes/(1024**3):.0f}')} گیگابایت به سرویس {sub.marzban_username} افزوده شد.",
    )


async def _redeem_days(
    callback: CallbackQuery, session: AsyncSession, bot: Bot, reward: ReferralReward
):
    user = await crud.get_user(session, callback.from_user.id)
    subs = await crud.get_user_active_subscriptions(session, user.id)
    if not subs:
        await callback.answer("شما سرویس فعالی ندارید.", show_alert=True)
        return
    sub = subs[0]
    user_info = await marzban_api.get_user_info(sub.marzban_username)
    if not user_info:
        await callback.answer("خطا در دریافت اطلاعات سرویس.", show_alert=True)
        return
    current_expire_ts = user_info.get("expire") or 0
    new_expire = current_expire_ts + (reward.extra_days or 0) * 24 * 60 * 60
    if not await _patch_marzban_user(sub.marzban_username, {"expire": new_expire}):
        await callback.answer("خطا در افزایش زمان اعتبار.", show_alert=True)
        return
    await crud.spend_reward(session, reward.id)
    await callback.answer("✅ مدت اعتبار سرویس افزایش یافت!", show_alert=True)
    try:
        await callback.message.edit_text(
            f"🎁 بن استفاده شد: +{to_persian_digits(reward.extra_days)} روز افزوده شد."
        )
    except Exception:
        pass
    await bot.send_message(
        user.chat_id,
        f"🎉 {to_persian_digits(reward.extra_days)} روز به اعتبار سرویس {sub.marzban_username} افزوده شد.",
    )


async def _redeem_credit(
    callback: CallbackQuery, session: AsyncSession, bot: Bot, reward: ReferralReward
):
    user = await crud.get_user(session, callback.from_user.id)
    if reward.credit_amount is None:
        await callback.answer("مقدار اعتبار نامعتبر است.", show_alert=True)
        return
    await crud.add_credit(session, user.id, reward.credit_amount)
    await crud.spend_reward(session, reward.id)
    await callback.answer("✅ اعتبار به کیف پول شما افزوده شد!", show_alert=True)
    try:
        await callback.message.edit_text(
            f"🎁 بن استفاده شد: {to_persian_digits(f'{reward.credit_amount:,}')} تومان به کیف پول افزوده شد."
        )
    except Exception:
        pass
    await bot.send_message(
        user.chat_id,
        f"💰 {to_persian_digits(f'{reward.credit_amount:,}')} تومان به کیف پول شما افزوده شد.",
    )


async def _redeem_star(
    callback: CallbackQuery,
    session: AsyncSession,
    bot: Bot,
    reward: ReferralReward,
    increment: int,
):
    user = await crud.get_user(session, callback.from_user.id)
    # Season stars (Phase B): feed seasonal milestone progress; coupons auto-unlock
    # into the wallet. Uses the stored star option, falling back to the callback value.
    amount = int(reward.stars or increment or 1)
    new_total, unlocked = await crud.add_season_stars(session, user.id, amount)
    await crud.spend_reward(session, reward.id)
    await callback.answer(
        f"⭐ +{to_persian_digits(amount)} ستاره فصلی (مجموع: {to_persian_digits(new_total)})",
        show_alert=True,
    )
    try:
        await callback.message.edit_text(
            f"🎁 بن استفاده شد: +{to_persian_digits(amount)} ستاره فصلی. "
            f"مجموع امتیاز فصل شما: {to_persian_digits(new_total)}."
        )
    except Exception:
        pass
    for coupon in unlocked:
        try:
            await bot.send_message(
                user.chat_id,
                f"🎉 به {to_persian_digits(coupon['milestone'])} ستاره رسیدید! "
                f"«{coupon['name']}» در کیف کوپن شما ذخیره شد.",
            )
        except Exception:
            pass
