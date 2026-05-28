from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud import get_active_challenges, get_user, get_user_achievements, get_user_challenge_progress

router = Router()

# -----------------------------
#  Achievements
# -----------------------------

@router.callback_query(F.data == "enhanced_achievements")
async def show_achievements(callback: CallbackQuery, session: AsyncSession):
    user = await get_user(session, callback.from_user.id)
    if not user:
        await callback.answer("کاربر یافت نشد!")
        return

    achievements = await get_user_achievements(session, user.id)
    if not achievements:
        text = (
            "🏆 **دستاوردها**\n\n"
            "هنوز هیچ دستاوردی کسب نکرده‌اید!\n\n"
            "برای کسب دستاورد:\n"
            "• دوستان خود را معرفی کنید\n"
            "• اشتراک خریداری کنید\n"
            "• روزانه وارد شوید\n"
            "• از VPN استفاده کنید"
        )
    else:
        text = "🏆 **دستاوردهای کسب شده**\n\n"
        for i, user_achievement in enumerate(achievements, 1):
            ach = user_achievement.achievement
            earned = user_achievement.earned_at.strftime('%Y/%m/%d')
            text += (
                f"{i}. {ach.icon} **{ach.name}**\n"
                f"   📝 {ach.description}\n"
                f"   🎁 پاداش: {ach.reward_value} {ach.reward_type}\n"
                f"   📅 {earned}\n\n"
            )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="🔄 بروزرسانی", callback_data="enhanced_achievements"),
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="enhanced_rewards_menu"),
        ]]
    )
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await callback.answer("قبلاً بروزرسانی شده است!", show_alert=False)
        else:
            raise

# -----------------------------
#  Challenges
# -----------------------------

@router.callback_query(F.data == "enhanced_challenges")
async def show_challenges(callback: CallbackQuery, session: AsyncSession):
    user = await get_user(session, callback.from_user.id)
    if not user:
        await callback.answer("کاربر یافت نشد!")
        return

    active_chals = await get_active_challenges(session)
    user_chals = await get_user_challenge_progress(session, user.id)
    progress_map = {uc.challenge_id: uc for uc in user_chals}

    if not active_chals:
        text = (
            "🎯 **چالش‌ها**\n\n"
            "در حال حاضر هیچ چالش فعالی وجود ندارد.\n"
            "به زودی چالش‌های جدید اضافه خواهند شد!"
        )
    else:
        text = "🎯 **چالش‌های فعال**\n\n"
        for i, chal in enumerate(active_chals, 1):
            uc = progress_map.get(chal.id)
            prog = uc.progress if uc else 0
            completed = uc.completed if uc else False

            percent = min(1.0, prog / chal.requirement_value)
            bar_len = 15
            filled = int(percent * bar_len)
            bar = "█" * filled + "░" * (bar_len - filled)
            status = "✅" if completed else "🔄" if prog > 0 else "⏳"

            text += (
                f"{i}. {status} **{chal.title}**\n"
                f"   📝 {chal.description}\n"
                f"   📊 پیشرفت: {prog}/{chal.requirement_value}\n"
                f"   `{bar}` {percent:.1%}\n"
                f"   🎁 پاداش: {chal.reward_value} {chal.reward_type}\n"
                f"   ⏰ نوع: {chal.challenge_type}\n\n"
            )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="🔄 بروزرسانی", callback_data="enhanced_challenges"),
            InlineKeyboardButton(text="🔙 بازگشت", callback_data="enhanced_rewards_menu"),
        ]]
    )

    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await callback.answer("قبلاً بروزرسانی شده است!", show_alert=False)
        else:
            raise 