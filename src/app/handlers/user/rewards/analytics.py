
from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.handlers.admin.common import ADMIN_IDS
from app.utils.logger import bot_logger

router = Router()


@router.callback_query(F.data == "star_analytics")
async def show_star_analytics_menu(callback: CallbackQuery, session: AsyncSession):
    """Display main star analytics menu for admins."""
    try:
        if callback.from_user.id not in ADMIN_IDS:
            await callback.answer("شما دسترسی ادمین ندارید!", show_alert=True)
            return

        analytics_data = await crud.get_star_analytics_overview(session)

        text = "<b>آمار ستاره‌ها</b>\n\n"
        text += f"<b>کل ستاره‌های توزیع شده:</b> {analytics_data['total_stars_earned']:,}\n"
        text += f"<b>کل جوایز دریافت شده:</b> {analytics_data['total_rewards_claimed']:,}\n"
        text += f"<b>کاربران فعال با ستاره:</b> {analytics_data['active_users_with_stars']:,}\n"
        text += f"<b>متوسط ستاره به ازای هر کاربر:</b> {analytics_data['avg_stars_per_user']:.1f}\n\n"
        text += "<b>آمار امروز:</b>\n"
        text += f"   └─ ستاره‌های امروز: {analytics_data['stars_today']}\n"
        text += f"   └─ جوایز امروز: {analytics_data['rewards_today']}\n"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="توزیع ستاره‌ها", callback_data="star_distribution")],
            [InlineKeyboardButton(text="محبوب‌ترین جوایز", callback_data="popular_rewards")],
            [InlineKeyboardButton(text="آمار زمانی", callback_data="star_time_analytics")],
            [InlineKeyboardButton(text="آمار کاربران", callback_data="user_star_analytics")],
            [InlineKeyboardButton(text="بازگشت", callback_data="admin_menu")]
        ])

        await callback.message.edit_text(text, reply_markup=keyboard)

    except Exception as e:
        bot_logger.error(f"Error in show_star_analytics_menu: {e}")
        await callback.answer("خطا در نمایش آمار!", show_alert=True)


@router.callback_query(F.data == "star_distribution")
async def show_star_distribution(callback: CallbackQuery, session: AsyncSession):
    """Show star distribution by earning sources."""
    try:
        if callback.from_user.id not in ADMIN_IDS:
            await callback.answer("شما دسترسی ادمین ندارید!", show_alert=True)
            return

        distribution = await crud.get_star_distribution_by_reason(session)

        text = "<b>توزیع ستاره‌ها بر اساس منبع</b>\n\n"

        for reason_data in distribution:
            reason = reason_data['reason']
            count = reason_data['count']
            total_stars = reason_data['total_stars']

            # Translate reason to Persian
            reason_persian = {
                'referral': 'معرفی کاربر',
                'achievement': 'دستاورد',
                'voucher_redemption': 'استفاده بن',
                'challenge_completion': 'تکمیل چالش',
                'admin_grant': 'اعطای ادمین',
                'tier_claim': 'دریافت جایزه تایر',
                'general': 'عمومی'
            }.get(reason, reason)

            text += f"• <b>{reason_persian}:</b> {total_stars:,} ستاره ({count:,} بار)\n"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="بازگشت به آمار", callback_data="star_analytics")]
        ])

        await callback.message.edit_text(text, reply_markup=keyboard)

    except Exception as e:
        bot_logger.error(f"Error in show_star_distribution: {e}")
        await callback.answer("خطا در نمایش توزیع!", show_alert=True)


@router.callback_query(F.data == "popular_rewards")
async def show_popular_rewards(callback: CallbackQuery, session: AsyncSession):
    """Show most popular star reward tiers."""
    try:
        if callback.from_user.id not in ADMIN_IDS:
            await callback.answer("شما دسترسی ادمین ندارید!", show_alert=True)
            return

        popular_rewards = await crud.get_popular_star_rewards(session)

        text = "<b>محبوب‌ترین جوایز ستاره‌ای</b>\n\n"

        for i, reward in enumerate(popular_rewards, 1):
            tier_title = reward['tier_title']
            tier_threshold = reward['tier_threshold']
            claim_count = reward['claim_count']
            reward_type = reward['reward_type']
            reward_value = reward['reward_value']

            # Format reward description
            reward_desc = f"{reward_value}"
            if reward_type == 'credit':
                reward_desc += " تومان اعتبار"
            elif reward_type == 'data_gb':
                reward_desc += " گیگابایت"
            elif reward_type == 'stars':
                reward_desc += " ستاره"

            text += f"{i}. <b>{tier_title}</b> (ستاره {tier_threshold})\n"
            text += f"   └─ {reward_desc} • {claim_count:,} دریافت\n\n"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="بازگشت به آمار", callback_data="star_analytics")]
        ])

        await callback.message.edit_text(text, reply_markup=keyboard)

    except Exception as e:
        bot_logger.error(f"Error in show_popular_rewards: {e}")
        await callback.answer("خطا در نمایش جوایز محبوب!", show_alert=True)


@router.callback_query(F.data == "star_time_analytics")
async def show_star_time_analytics(callback: CallbackQuery, session: AsyncSession):
    """Show star analytics over time periods."""
    try:
        if callback.from_user.id not in ADMIN_IDS:
            await callback.answer("شما دسترسی ادمین ندارید!", show_alert=True)
            return

        # Get analytics for different time periods
        today_stats = await crud.get_star_analytics_by_period(session, 'today')
        week_stats = await crud.get_star_analytics_by_period(session, 'week')
        month_stats = await crud.get_star_analytics_by_period(session, 'month')

        text = "<b>آمار زمانی ستاره‌ها</b>\n\n"

        text += "<b>امروز:</b>\n"
        text += f"   └─ ستاره: {today_stats['stars']:,} • جوایز: {today_stats['rewards']:,}\n\n"

        text += "<b>هفته جاری:</b>\n"
        text += f"   └─ ستاره: {week_stats['stars']:,} • جوایز: {week_stats['rewards']:,}\n\n"

        text += "<b>ماه جاری:</b>\n"
        text += f"   └─ ستاره: {month_stats['stars']:,} • جوایز: {month_stats['rewards']:,}\n"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="بازگشت به آمار", callback_data="star_analytics")]
        ])

        await callback.message.edit_text(text, reply_markup=keyboard)

    except Exception as e:
        bot_logger.error(f"Error in show_star_time_analytics: {e}")
        await callback.answer("خطا در نمایش آمار زمانی!", show_alert=True)


@router.callback_query(F.data == "user_star_analytics")
async def show_user_star_analytics(callback: CallbackQuery, session: AsyncSession):
    """Show user star analytics."""
    try:
        if callback.from_user.id not in ADMIN_IDS:
            await callback.answer("شما دسترسی ادمین ندارید!", show_alert=True)
            return

        user_stats = await crud.get_user_star_statistics(session)

        text = "<b>آمار کاربران ستاره‌دار</b>\n\n"
        text += f"<b>کل کاربران:</b> {user_stats['total_users']:,}\n"
        text += f"<b>کاربران با ستاره:</b> {user_stats['users_with_stars']:,}\n"
        text += f"<b>کاربران بدون ستاره:</b> {user_stats['users_without_stars']:,}\n\n"

        text += "<b>آمار توزیع:</b>\n"
        text += f"   └─ میانگین ستاره: {user_stats['avg_stars']:.1f}\n"
        text += f"   └─ حداکثر ستاره: {user_stats['max_stars']:,}\n"
        text += f"   └─ حداقل ستاره: {user_stats['min_stars']}\n\n"

        # Show top users
        text += "<b>کاربران برتر:</b>\n"
        for i, top_user in enumerate(user_stats['top_users'][:5], 1):
            username = top_user['username'] or top_user['full_name'] or f"کاربر {top_user['user_id']}"
            stars = top_user['stars']
            text += f"   {i}. {username}: {stars:,} ستاره\n"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="بازگشت به آمار", callback_data="star_analytics")]
        ])

        await callback.message.edit_text(text, reply_markup=keyboard)

    except Exception as e:
        bot_logger.error(f"Error in show_user_star_analytics: {e}")
        await callback.answer("خطا در نمایش آمار کاربران!", show_alert=True)
