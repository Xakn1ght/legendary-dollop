from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud import get_user, get_user_reward_history

router = Router()

@router.callback_query(F.data == "enhanced_reward_history")
async def show_reward_history(callback: CallbackQuery, session: AsyncSession):
    user = await get_user(session, callback.from_user.id)
    if not user:
        await callback.answer("کاربر یافت نشد!")
        return

    history = await get_user_reward_history(session, user.id, limit=20)
    if not history:
        text = "📊 **تاریخچه پاداش‌ها**\n\nهنوز هیچ پاداشی دریافت نکرده‌اید!"
    else:
        text = "📊 **تاریخچه پاداش‌ها**\n\n"
        src_names = {
            "referral": "معرفی",
            "achievement": "دستاورد",
            "challenge": "چالش",
            "streak": "رکورد ورود",
            "level_up": "ارتقاء سطح",
            "daily_login": "ورود روزانه",
            "gift": "هدیه",
        }
        for entry in history:
            date_str = entry.earned_at.strftime('%Y/%m/%d %H:%M')
            source = src_names.get(entry.source, entry.source)
            text += (
                f"🎁 {entry.reward_value:,} {entry.reward_type}\n"
                f"   📝 منبع: {source}\n"
                f"   📅 {date_str}\n\n"
            )

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔄 بروزرسانی", callback_data="enhanced_reward_history"),
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="enhanced_rewards_menu"),
    ]])

    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await callback.answer("قبلاً بروزرسانی شده است!", show_alert=False)
        else:
            raise 