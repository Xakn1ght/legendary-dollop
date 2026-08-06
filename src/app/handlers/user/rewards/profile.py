from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.database.crud import get_all_star_reward_tiers, get_user
from app.utils.text_format import to_jalali_date, to_persian_digits

router = Router()

@router.callback_query(F.data == "enhanced_profile")
async def show_user_profile(callback: CallbackQuery, session: AsyncSession):
    """Simple user profile (stars + vouchers only)."""
    user = await get_user(session, callback.from_user.id)
    if not user:
        await callback.answer("کاربر یافت نشد!")
        return

    # Add unclaimed star rewards check
    unclaimed_rewards = await crud.get_user_unclaimed_rewards(session, user.id)

    # Dynamically determine the next star tier for progress display
    tiers = await get_all_star_reward_tiers(session)
    next_tier = next((t for t in sorted(tiers, key=lambda x: x.star_threshold) if t.star_threshold > user.stars), None)

    if next_tier:
        stars_line = f"<b>ستاره‌ها:</b> {to_persian_digits(user.stars)} / {to_persian_digits(next_tier.star_threshold)}\n"
    else:
        stars_line = f"<b>ستاره‌ها:</b> {to_persian_digits(user.stars)}\n"


    profile_text = (
        f"<b>پروفایل کاربری</b>\n\n"
        f"<b>نام:</b> {user.full_name or user.username or 'نامشخص'}\n"
        f"<b>آی‌دی عددی:</b> <code>{user.chat_id}</code>\n"
        f"<b>تاریخ عضویت:</b> {to_jalali_date(user.created_at)}\n\n"
        f"<b>اعتبار:</b> {to_persian_digits(f'{user.credit:,}')} تومان\n"
        + stars_line
    )
    if unclaimed_rewards:
        profile_text += f"<b>هدایای ستاره‌ای استفاده‌نشده:</b> {to_persian_digits(len(unclaimed_rewards))} عدد\n"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="بروزرسانی", callback_data="enhanced_profile"),
                InlineKeyboardButton(text="بازگشت", callback_data="enhanced_rewards_menu"),
            ]
        ]
    )
    if unclaimed_rewards:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="دریافت جوایز", callback_data="open_wallet_menu")
        ])

    try:
        await callback.message.edit_text(profile_text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await callback.answer("قبلاً بروزرسانی شده است!", show_alert=False)
        else:
            raise 
