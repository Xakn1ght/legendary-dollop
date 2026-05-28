from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.utils.text_format import to_persian_digits

router = Router()

def translate_challenge_terms(term: str) -> str:
    """Translates challenge-related terms to Persian."""
    translations = {
        'xp': 'تجربه',
        'loyalty_points': 'امتیاز وفاداری',
        'credit': 'اعتبار',
        'daily': 'روزانه',
        'weekly': 'هفتگی'
    }
    return translations.get(term.lower(), term)

@router.callback_query(F.data == "active_challenges")
async def show_active_challenges(callback: CallbackQuery, session: AsyncSession):
    """Displays a detailed list of active daily and weekly challenges for the user."""
    user = await crud.get_user(session, callback.from_user.id)
    if not user:
        await callback.answer("کاربر یافت نشد!", show_alert=True)
        return

    active_challenges = await crud.get_active_challenges(session)
    user_challenges_progress = await crud.get_user_challenge_progress(session, user.id)
    
    progress_map = {uc.challenge_id: uc for uc in user_challenges_progress}

    if not active_challenges:
        challenge_text = "در حال حاضر چالش فعالی وجود ندارد."
    else:
        challenge_text = "🎯 <b>چالش‌های فعال</b>\n"
        for i, challenge in enumerate(active_challenges):
            user_progress = progress_map.get(challenge.id)
            
            current_progress = user_progress.progress if user_progress else 0
            is_completed = user_progress.completed if user_progress else False
            
            icon = "✅" if is_completed else "🔄"
            
            # Progress bar calculation
            percentage = (current_progress / challenge.requirement_value) * 100 if challenge.requirement_value > 0 else 100
            bar_len = 15
            filled = int((percentage / 100) * bar_len)
            progress_bar = "█" * filled + "░" * (bar_len - filled)
            
            challenge_text += (
                f"\n{i+1}. {icon} <b>{challenge.title}</b>\n"
                f"   📝 {challenge.description}\n"
                f"   📊 پیشرفت: {to_persian_digits(current_progress)}/{to_persian_digits(challenge.requirement_value)}\n"
                f"   `{progress_bar}` {to_persian_digits(f'{percentage:.1f}')}%\n"
                f"   🎁 پاداش: {to_persian_digits(challenge.reward_value)} {translate_challenge_terms(challenge.reward_type)}\n"
                f"   ⏰ نوع: {translate_challenge_terms(challenge.challenge_type)}\n"
            )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data="enhanced_rewards_menu")]
        ]
    )

    try:
        await callback.message.edit_text(challenge_text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await callback.answer("بدون تغییر", show_alert=False)
        else:
            raise
    await callback.answer()
