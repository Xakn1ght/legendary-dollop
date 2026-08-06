from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.database.repos.reward._challenges import challenge_xp_value
from app.utils.text_format import to_persian_digits

router = Router()


@router.callback_query(F.data == "active_challenges")
async def show_active_challenges(callback: CallbackQuery, session: AsyncSession):
    """Detailed list of active daily and weekly challenges for the user.

    Creation is ensure-on-access (no scheduler): opening this screen
    guarantees today's daily and this week's weekly challenges exist.
    Rewards display as the XP actually paid on completion (legacy monetary
    definitions are mapped to XP at grant time — see repos/reward/_challenges).
    """
    user = await crud.get_user(session, callback.from_user.id)
    if not user:
        await callback.answer("کاربر یافت نشد!", show_alert=True)
        return

    await crud.ensure_today_daily_challenge(session)
    await crud.ensure_current_weekly_challenges(session)

    active_challenges = await crud.get_active_challenges(session)
    user_challenges_progress = await crud.get_user_challenge_progress(session, user.id)

    progress_map = {uc.challenge_id: uc for uc in user_challenges_progress}
    type_names = {"daily": "روزانه", "weekly": "هفتگی", "seasonal": "فصلی"}

    if not active_challenges:
        challenge_text = "در حال حاضر چالش فعالی وجود ندارد."
    else:
        challenge_text = "<b>چالش‌های فعال</b>\n"
        for i, challenge in enumerate(active_challenges):
            user_progress = progress_map.get(challenge.id)

            current_progress = user_progress.progress if user_progress else 0
            is_completed = user_progress.completed if user_progress else False

            status = "انجام شد" if is_completed else "در جریان"

            percentage = (current_progress / challenge.requirement_value) * 100 if challenge.requirement_value > 0 else 100
            percentage = min(percentage, 100.0)
            bar_len = 15
            filled = int((percentage / 100) * bar_len)
            progress_bar = "█" * filled + "░" * (bar_len - filled)

            xp = challenge_xp_value(challenge.reward_type, challenge.reward_value)
            challenge_text += (
                f"\n{i+1}. <b>{challenge.title}</b> ({status})\n"
                f"   {challenge.description}\n"
                f"   پیشرفت: {to_persian_digits(min(current_progress, challenge.requirement_value))}/{to_persian_digits(challenge.requirement_value)}\n"
                f"   <code>{progress_bar}</code> {to_persian_digits(f'{percentage:.0f}')}٪\n"
                f"   پاداش: {to_persian_digits(xp)} امتیاز تجربه\n"
                f"   نوع: {type_names.get(challenge.challenge_type, challenge.challenge_type)}\n"
            )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="بازگشت", callback_data="enhanced_rewards_menu")]
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
