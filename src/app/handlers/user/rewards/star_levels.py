from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.utils.text_format import to_persian_digits

router = Router()

@router.callback_query(F.data == "show_star_levels")
async def show_star_levels(callback: CallbackQuery, session: AsyncSession):
    """Displays the star tier progression screen."""
    user = await crud.get_user(session, callback.from_user.id)
    if not user:
        await callback.answer("کاربر یافت نشد!", show_alert=True)
        return

    all_tiers = await crud.get_all_star_reward_tiers(session)
    unclaimed_rewards = await crud.get_user_unclaimed_rewards(session, user.id)
    claimed_reward_tiers_this_cycle = [] # In a real scenario, you'd check history

    header_text = "⭐️ <b>سطوح ستاره‌ها</b> ⭐️\n\n"
    
    # Show current stars and progress to next tier
    next_tier = next((t for t in sorted(all_tiers, key=lambda x: x.star_threshold) if t.star_threshold > user.stars), None)
    if next_tier:
        stars_needed = next_tier.star_threshold - user.stars
        header_text += f"شما <b>{to_persian_digits(user.stars)}</b> ستاره دارید. <b>{to_persian_digits(stars_needed)}</b> ستاره دیگر تا جایزه بعدی!\n"
    else:
        header_text += f"شما با <b>{to_persian_digits(user.stars)}</b> ستاره به بالاترین سطح رسیده‌اید!\n"

    tiers_text = ""
    for tier in sorted(all_tiers, key=lambda x: x.star_threshold):
        # Determine status icon
        status_icon = "⚪️" # Not yet reached
        if user.stars >= tier.star_threshold:
            status_icon = "🟢" # Achieved
        
        # Check if there is an available claim for this tier
        is_claimable = any(claim.tier_id == tier.id for claim in unclaimed_rewards)
        if is_claimable:
            status_icon = "🎁" # Ready to claim

        tiers_text += f"\n{status_icon} <b>{tier.title}</b> ({to_persian_digits(tier.star_threshold)} ستاره)\n"
        tiers_text += f"    - <i>{tier.description}</i>\n"

    # Build keyboard
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    # Add claim buttons for any available rewards
    if unclaimed_rewards:
        for claim in unclaimed_rewards:
             if claim.status == 'offered':
                keyboard.inline_keyboard.append([
                    InlineKeyboardButton(
                        text=f"🎁 دریافت جایزه {claim.tier.title}",
                        callback_data=f"claim_star_reward_{claim.id}"
                    )
                ])

    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="enhanced_rewards_menu")])

    full_text = header_text + tiers_text
    
    try:
        await callback.message.edit_text(full_text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await callback.answer("بدون تغییر", show_alert=False)
        else:
            raise # Re-raise other errors
    
    await callback.answer()
