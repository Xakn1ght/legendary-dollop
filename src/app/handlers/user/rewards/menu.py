from datetime import datetime

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud import (
    get_active_user_discounts,
    get_all_star_reward_tiers,
    get_unspent_rewards_by_referrer,
    get_user,
    get_user_unclaimed_rewards,
)
from app.utils.bot_i18n import get_cached_lang, normalize_lang, set_cached_lang, t, text_matches
from app.utils.text_format import to_persian_digits

router = Router()

# Optional Jalali date support
try:
    import jdatetime  # type: ignore
except Exception:
    jdatetime = None

def _to_persian_digits(s):
    digits = "۰۱۲۳۴۵۶۷۸۹"
    return ''.join(digits[int(ch)] if ch.isdigit() else ch for ch in str(s))

def _format_jalali(dt):
    if not dt:
        return "-"
    try:
        if jdatetime:
            return _to_persian_digits(jdatetime.datetime.fromgregorian(datetime=dt).strftime('%Y/%m/%d %H:%M'))
    except Exception:
        pass
    return dt.strftime('%Y-%m-%d %H:%M')

async def show_enhanced_rewards_menu(target, session: AsyncSession):
    """Display the root rewards menu (stars + referral vouchers only)."""
    user_id = target.from_user.id if hasattr(target, "from_user") else target.chat.id
    user = await get_user(session, user_id)
    if not user:
        return
    lang = normalize_lang(getattr(user, "language", None))
    set_cached_lang(user.chat_id, lang)

    # Wallet snapshot
    credit = user.credit or 0
    stars = user.stars or 0
    vouchers = await get_unspent_rewards_by_referrer(session, user.id)
    discounts = await get_active_user_discounts(session, user.id)

    # Dynamically determine the next star tier for progress display
    tiers = await get_all_star_reward_tiers(session)
    next_tier = next((t for t in sorted(tiers, key=lambda x: x.star_threshold) if t.star_threshold > stars), None)

    def fmt_num(n):
        return to_persian_digits(n) if lang == "fa" else str(n)

    if next_tier:
        stars_line = (
            f"⭐ <b>ستاره‌ها:</b> {fmt_num(stars)} / {fmt_num(next_tier.star_threshold)}\n"
            if lang == "fa"
            else f"⭐ <b>Stars:</b> {fmt_num(stars)} / {fmt_num(next_tier.star_threshold)}\n"
        )
    else:
        stars_line = (
            f"⭐ <b>ستاره‌ها:</b> {fmt_num(stars)} (حداکثر سطح)\n"
            if lang == "fa"
            else f"⭐ <b>Stars:</b> {fmt_num(stars)} (max)\n"
        )

    discount_line = "🏷️ <b>تخفیف‌های فعال:</b> ندارد" if lang == "fa" else "🏷️ <b>Active discounts:</b> none"
    if discounts:
        try:
            # Sort by nearest expiry, then by percent desc
            sorted_discounts = sorted(
                discounts,
                key=lambda d: (
                    (d.expiration or None) or datetime.max,
                    -(d.percent or 0)
                )
            )
            preview_items = []
            for d in sorted_discounts[:3]:
                perc = _to_persian_digits(d.percent or 0) if lang == "fa" else str(d.percent or 0)
                exp = _format_jalali(getattr(d, 'expiration', None)) if lang == "fa" else (getattr(d, 'expiration', None).strftime('%Y-%m-%d %H:%M') if getattr(d, 'expiration', None) else "-")
                preview_items.append((f"{perc}% تا {exp}") if lang == "fa" else f"{perc}% until {exp}")
            suffix = "، …" if len(sorted_discounts) > 3 else ""
            discount_line = (f"🏷️ <b>تخفیف‌های فعال:</b> " if lang == "fa" else "🏷️ <b>Active discounts:</b> ") + "، ".join(preview_items) + suffix
        except Exception:
            discount_line = f"🏷️ <b>تخفیف‌های فعال:</b> {len(discounts)} عدد" if lang == "fa" else f"🏷️ <b>Active discounts:</b> {len(discounts)}"

    # Check unclaimed star rewards
    unclaimed = await get_user_unclaimed_rewards(session, user.id)

    menu_text = (
        t(lang, "rewards_title")
        + "\n\n"
        + (
        f"💰 <b>اعتبار:</b> {to_persian_digits(f'{credit:,}')} تومان\n"
            if lang == "fa"
            else f"💰 <b>Credit:</b> {credit:,} Toman\n"
        )
        + stars_line
        + (
        f"🎟️ <b>بن‌های استفاده‌نشده:</b> {to_persian_digits(len(vouchers))} عدد\n"
            if lang == "fa"
            else f"🎟️ <b>Unused vouchers:</b> {len(vouchers)}\n"
        )
        + f"{discount_line}\n"
    )
    if unclaimed:
        menu_text += (
            f"🟢 جوایز ستاره‌ایِ قابل دریافت: {to_persian_digits(len(unclaimed))} — برای دریافت دکمه زیر را بزنید.\n"
            if lang == "fa"
            else f"🟢 Unclaimed star rewards: {len(unclaimed)} — tap the button below to claim.\n"
        )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=("🎟️ بن‌های من" if lang == "fa" else "🎟️ My vouchers"),
                    callback_data="enhanced_wallet_rewards",
                ),
                InlineKeyboardButton(
                    text=t(lang, "rewards_star_levels"),
                    callback_data="show_star_levels",
                ),
            ],
            [
                InlineKeyboardButton(text=("🔄 بروزرسانی" if lang == "fa" else "🔄 Refresh"), callback_data="enhanced_rewards_menu"),
                InlineKeyboardButton(text=t(lang, "rewards_close"), callback_data="enhanced_close"),
            ],
        ]
    )

    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(menu_text, reply_markup=keyboard, parse_mode="HTML")
        except TelegramBadRequest:
            await target.message.answer(menu_text, reply_markup=keyboard, parse_mode="HTML")
        await target.answer()
    else:
        await target.answer(menu_text, reply_markup=keyboard, parse_mode="HTML")


# Entry points -------------------------------------------------

@router.message(text_matches("btn_rewards"))
async def enhanced_rewards_menu_cmd(message: Message, session: AsyncSession):
    await show_enhanced_rewards_menu(message, session)


@router.callback_query(F.data == "enhanced_rewards_menu")
async def enhanced_rewards_menu_cb(callback: CallbackQuery, session: AsyncSession):
    await show_enhanced_rewards_menu(callback, session)


@router.callback_query(F.data == "enhanced_close")
async def enhanced_close(callback: CallbackQuery):
    # Safely delete the rewards menu message; fall back to simple answer
    try:
        await callback.message.delete()
    except Exception:
        lang = get_cached_lang(callback.from_user.id)
        await callback.answer(t(lang, "closed"))
