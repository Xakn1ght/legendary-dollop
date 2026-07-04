from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import DASHBOARD_PUBLIC_BASE_URL
from app.database.crud import (
    add_credit,
    get_unspent_rewards_by_referrer,
    get_user,
    get_user_active_subscriptions,
    get_user_unclaimed_rewards,
)
from app.keyboards.inline import get_reward_voucher_keyboard
from app.utils.text_format import to_jalali_date, to_persian_digits

router = Router()

def _build_rewards_webapp_url(user_chat_id: int) -> str:
    # WebAppInfo button → Telegram injects signed initData; no URL token
    # (raw links with tokens must never grant access — Telegram-only policy).
    return f"{DASHBOARD_PUBLIC_BASE_URL}/webapp/dashboard/#page=tasks"

# -----------------------------
#  Integrated Wallet
# -----------------------------

@router.callback_query(F.data.in_({"enhanced_wallet", "open_wallet_menu"}))
async def show_wallet(callback: CallbackQuery, session: AsyncSession):
    """Show detailed wallet information with all financial assets."""
    user = await get_user(session, callback.from_user.id)
    if not user:
        await callback.answer("کاربر یافت نشد!")
        return

    # Get wallet data
    credit = user.credit or 0
    stars = user.stars or 0
    vouchers = await get_unspent_rewards_by_referrer(session, user.id)

    wallet_text = (
        "💰 <b>کیف پول شما</b>\n\n"
        f"💵 <b>اعتبار:</b> {to_persian_digits(f'{credit:,}')} تومان\n"
        f"⭐ <b>ستاره‌ها:</b> {to_persian_digits(stars)}\n"
        f"🎟️ <b>بن‌های استفاده‌نشده:</b> {to_persian_digits(len(vouchers))} عدد\n"
    )

    # Display active discount(s)
    from app.database.crud import get_active_user_discounts
    discounts = await get_active_user_discounts(session, user.id)
    if discounts:
        for d in discounts:
            wallet_text += f"🏷️ <b>تخفیف فعال:</b> {to_persian_digits(d.percent)}٪ (تا {to_jalali_date(d.expiration)})\n"

    # No need to show claimed rewards again, they are part of credit/discounts
    # wallet_text += f"📊 <b>ارزش کل:</b> {to_persian_digits(f'{total_value:,}')} تومان\n\n"
    
    wallet_text += f"\n<b>سطوح ستاره‌ها:</b>\n"


    # Show progress towards next reward tier
    from app.database.crud import get_all_star_reward_tiers
    tiers = await get_all_star_reward_tiers(session)
    next_tier = next((t for t in tiers if t.star_threshold > stars), None)
    if next_tier:
        remaining_stars = next_tier.star_threshold - stars
        wallet_text += f"📈 {to_persian_digits(remaining_stars)} ستاره دیگر تا جایزهٔ بعدی ({next_tier.title} - {next_tier.description}).\n"
    else:
        wallet_text += "🏆 همهٔ جوایز ستاره‌ای را گرفته‌اید!\n"

    wallet_text += "\n<b>نکته:</b>\n"
    wallet_text += "• سیستم امتیاز وفاداری و XP غیرفعال است.\n"

    # Check for unclaimed star rewards
    unclaimed_rewards = await get_user_unclaimed_rewards(session, user.id)
    if unclaimed_rewards:
        wallet_text += "\n<b>🎁 جوایز ستاره‌ای در انتظار:</b>\n"
        for claim in unclaimed_rewards:
            if claim.status == 'pending_subscription':
                wallet_text += f"• <b>{claim.tier.title}</b>: {claim.tier.description} (در انتظار خرید اشتراک)\n"
            else:
                wallet_text += f"• <b>{claim.tier.title}</b>: {claim.tier.description}\n"

    # Create wallet action keyboard
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    # Add claim buttons for 'offered' rewards
    for claim in unclaimed_rewards:
        if claim.status == 'offered':
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"🎁 دریافت {claim.tier.title}",
                    callback_data=f"claim_star_reward_{claim.id}"
                )
            ])

    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="🎟️ بن‌های من", callback_data="enhanced_wallet_rewards"),
    ])


    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="enhanced_rewards_menu")
    ])

    # WebApp-first: prepend a link to the Rewards page so users can manage everything there.
    try:
        web_kb = InlineKeyboardBuilder()
        web_kb.button(text="⭐ پاداش‌ها (وب‌اپ)", web_app=WebAppInfo(url=_build_rewards_webapp_url(callback.from_user.id)))
        web_kb.adjust(1)
        keyboard.inline_keyboard = web_kb.as_markup().inline_keyboard + (keyboard.inline_keyboard or [])
    except Exception:
        pass

    try:
        await callback.message.edit_text(wallet_text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await callback.answer("قبلاً بروزرسانی شده است!", show_alert=False)
        else:
            raise


@router.callback_query(F.data == "enhanced_wallet_rewards")
async def show_wallet_rewards(callback: CallbackQuery, session: AsyncSession):
    """Show detailed list of unclaimed rewards."""
    user = await get_user(session, callback.from_user.id)
    if not user:
        await callback.answer("کاربر یافت نشد!")
        return

    rewards = await get_unspent_rewards_by_referrer(session, user.id)
    if not rewards:
        await callback.answer("هیچ بنی ندارید.", show_alert=True)
        return

    # Show each reward with its own redeem keyboard
    for rw in rewards:
        parts = []
        extra_gb = None
        if rw.traffic_bytes and rw.traffic_bytes > 0:
            extra_gb = rw.traffic_bytes / (1024 ** 3)
            parts.append(f"+{to_persian_digits(f'{extra_gb:.0f}')}GB")
        if rw.extra_days and rw.extra_days > 0:
            parts.append(f"+{to_persian_digits(rw.extra_days)}D")
        if rw.credit_amount and rw.credit_amount > 0:
            parts.append(f"{to_persian_digits(f'{rw.credit_amount:,}')}T")

        desc = " / ".join(parts) if parts else "—"

        # Build redeem keyboard
        kb = get_reward_voucher_keyboard(
            reward_id=rw.id,
            extra_gb=extra_gb,
            extra_days=rw.extra_days,
            credit_amount=rw.credit_amount,
            stars_progress=user.stars,
            star_increment=1,
            show_star=True,
        )

        await callback.message.answer(
            text=f"🎟️ بن #{rw.id}: {desc}",
            reply_markup=kb,
        )

    await callback.answer("بن‌های شما نمایش داده شدند.")


@router.callback_query(F.data == "enhanced_convert_loyalty")
async def convert_loyalty_points_confirm(callback: CallbackQuery, session: AsyncSession):
    """Loyalty points are disabled."""
    await callback.answer("امتیاز وفاداری غیرفعال است.", show_alert=True)


@router.callback_query(F.data == "enhanced_convert_loyalty_confirm")
async def convert_loyalty_points_do(callback: CallbackQuery, session: AsyncSession):
    """Loyalty points are disabled."""
    await callback.answer("امتیاز وفاداری غیرفعال است.", show_alert=True)
    await show_wallet(callback, session)


@router.callback_query(F.data == "enhanced_wallet_cashout")
async def wallet_cashout(callback: CallbackQuery, session: AsyncSession):
    """Handle cashout request."""
    await callback.answer("لطفاً برای برداشت اعتبار با پشتیبانی تماس بگیرید.", show_alert=True)


@router.callback_query(F.data == "enhanced_wallet_spend")
async def wallet_spend(callback: CallbackQuery, session: AsyncSession):
    """Handle wallet spend in next purchase."""
    await callback.answer("در خرید بعدی به‌صورت خودکار از اعتبار استفاده خواهد شد.", show_alert=True)


@router.callback_query(F.data == "enhanced_free_renewal")
async def show_free_renewal_options(callback: CallbackQuery, session: AsyncSession):
    """Show free renewal options for eligible users."""
    user = await get_user(session, callback.from_user.id)
    if not user or user.stars < 5:
        await callback.answer("شما واجد شرایط تمدید رایگان نیستید.", show_alert=True)
        return

    subs = await get_user_active_subscriptions(session, user.id)
    if not subs:
        await callback.answer("شما سرویس فعالی ندارید.", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for sub in subs:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"⭐ تمدید {sub.marzban_username}",
                callback_data=f"enhanced_free_renew_{sub.id}"
            )
        ])

    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="enhanced_wallet")
    ])

    await callback.message.edit_text(
        "⭐ <b>تمدید رایگان با ستاره‌ها</b>\n\n"
        "سرویس مورد نظر برای تمدید رایگان را انتخاب کنید:",
        reply_markup=keyboard,
        parse_mode="HTML"
    ) 
