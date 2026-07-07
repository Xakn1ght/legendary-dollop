from datetime import datetime

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rewards_config import STAR_SEASON_MILESTONES
from app.database.crud import (
    get_active_coupons,
    get_active_user_discounts,
    get_season_progress,
    get_unspent_rewards_by_referrer,
    get_user,
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
    vouchers = await get_unspent_rewards_by_referrer(session, user.id)
    discounts = await get_active_user_discounts(session, user.id)

    def fmt_num(n):
        return to_persian_digits(n) if lang == "fa" else str(n)

    # Season stars + next milestone (referral-only, resets each season).
    _season, season_stars = await get_season_progress(session, user.id)
    coupons = await get_active_coupons(session, user.id)
    next_ms = next((m for m in sorted(STAR_SEASON_MILESTONES) if m > season_stars), None)
    if next_ms:
        stars_line = (
            f"⭐ <b>ستاره‌های فصل:</b> {fmt_num(season_stars)} / {fmt_num(next_ms)}\n"
            if lang == "fa"
            else f"⭐ <b>Season stars:</b> {fmt_num(season_stars)} / {fmt_num(next_ms)}\n"
        )
    else:
        stars_line = (
            f"⭐ <b>ستاره‌های فصل:</b> {fmt_num(season_stars)} (همه باز شد)\n"
            if lang == "fa"
            else f"⭐ <b>Season stars:</b> {fmt_num(season_stars)} (all unlocked)\n"
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
        f"🎁 <b>کوپن‌های فعال:</b> {to_persian_digits(len(coupons))} عدد\n"
            if lang == "fa"
            else f"🎁 <b>Active coupons:</b> {len(coupons)}\n"
        )
        + (
        f"🎟️ <b>بن‌های استفاده‌نشده:</b> {to_persian_digits(len(vouchers))} عدد\n"
            if lang == "fa"
            else f"🎟️ <b>Unused vouchers:</b> {len(vouchers)}\n"
        )
        + f"{discount_line}\n"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=("🎟️ بن‌های من" if lang == "fa" else "🎟️ My vouchers"),
                    callback_data="enhanced_wallet_rewards",
                ),
                InlineKeyboardButton(
                    text=("🎁 کوپن‌های من" if lang == "fa" else "🎁 My coupons"),
                    callback_data="show_season_coupons",
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


def _coupon_label(coupon, lang):
    """Human-readable one-line label for a season coupon."""
    import json
    try:
        p = json.loads(coupon.payload or "{}")
    except Exception:
        p = {}
    ct = coupon.coupon_type
    if ct == "discount_percent":
        return (f"٪{_to_persian_digits(p.get('discount_percent', 0))} تخفیف" if lang == "fa"
                else f"{p.get('discount_percent', 0)}% discount")
    if ct == "free_gb":
        return (f"{_to_persian_digits(p.get('gb', 0))}GB رایگان" if lang == "fa"
                else f"{p.get('gb', 0)}GB free")
    if ct == "free_plan":
        return (f"پلن {_to_persian_digits(p.get('plan_gb', 0))}GB رایگان" if lang == "fa"
                else f"Free {p.get('plan_gb', 0)}GB plan")
    if ct == "free_autorenew":
        return ("تمدید خودکار رایگان" if lang == "fa" else "Free auto-renewal")
    if ct == "vip_days":
        return (f"🎖 {_to_persian_digits(p.get('days', 30))} روز VIP رایگان" if lang == "fa"
                else f"🎖 {p.get('days', 30)} days of free VIP")
    return ct


@router.callback_query(F.data == "show_season_coupons")
async def show_season_coupons(callback: CallbackQuery, session: AsyncSession):
    """Coupon wallet: list the user's active (unlocked, unexpired) season coupons."""
    user = await get_user(session, callback.from_user.id)
    if not user:
        await callback.answer()
        return
    lang = normalize_lang(getattr(user, "language", None))
    coupons = await get_active_coupons(session, user.id)

    title = "🎁 <b>کیف کوپن شما</b>" if lang == "fa" else "🎁 <b>Your coupon wallet</b>"
    vip_rows = []
    if not coupons:
        body = ("\n\nهنوز کوپنی ندارید. با دعوت دوستان ستاره جمع کنید تا کوپن باز شود."
                if lang == "fa" else "\n\nNo coupons yet. Earn season stars by referring friends to unlock them.")
    else:
        lines = []
        for c in coupons:
            exp = _format_jalali(c.expires_at) if lang == "fa" else (c.expires_at.strftime('%Y-%m-%d') if c.expires_at else "-")
            star = _to_persian_digits(c.milestone_stars or 0) if lang == "fa" else (c.milestone_stars or 0)
            if lang == "fa":
                lines.append(f"• {_coupon_label(c, lang)} — ⭐{star} — تا {exp}")
            else:
                lines.append(f"• {_coupon_label(c, lang)} — ⭐{star} — exp {exp}")
            if c.coupon_type == "vip_days":
                vip_rows.append([InlineKeyboardButton(
                    text=("🎖 فعال‌سازی VIP رایگان" if lang == "fa" else "🎖 Activate free VIP"),
                    callback_data=f"redeem_vip_days:{c.id}",
                )])
        body = "\n\n" + "\n".join(lines)
        body += ("\n\nℹ️ هر کوپن فقط یک‌بار قابل استفاده است. کوپن VIP از همین‌جا فعال می‌شود؛ بقیه هنگام خرید." if lang == "fa"
                 else "\n\nℹ️ Each coupon is one-time. The VIP coupon activates right here; the rest apply at checkout.")

    kb = InlineKeyboardMarkup(inline_keyboard=vip_rows + [[
        InlineKeyboardButton(text=("⬅️ بازگشت" if lang == "fa" else "⬅️ Back"), callback_data="enhanced_rewards_menu"),
    ]])
    try:
        await callback.message.edit_text(title + body, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(title + body, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("redeem_vip_days:"))
async def redeem_vip_days_cb(callback: CallbackQuery, session: AsyncSession):
    """Activate a vip_days coupon from the bot wallet (same rules as the webapp)."""
    user = await get_user(session, callback.from_user.id)
    if not user:
        await callback.answer()
        return
    lang = normalize_lang(getattr(user, "language", None))
    try:
        coupon_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer()
        return

    import json as _json

    from app.database.crud import get_coupon_by_id, mark_coupon_used, restore_coupon
    from app.services.subscription_processing import extend_vip_window

    coupon = await get_coupon_by_id(session, coupon_id)
    if not coupon or coupon.user_id != user.id or coupon.coupon_type != "vip_days":
        await callback.answer("کوپن معتبر نیست" if lang == "fa" else "Invalid coupon", show_alert=True)
        return
    try:
        days = int(_json.loads(coupon.payload or "{}").get("days") or 0)
    except Exception:
        days = 0
    if days <= 0 or not await mark_coupon_used(session, coupon.id):
        await callback.answer("این کوپن قبلاً استفاده شده" if lang == "fa" else "Coupon already used", show_alert=True)
        return
    try:
        await extend_vip_window(session, user, days)
    except Exception:
        await restore_coupon(session, coupon.id)
        await callback.answer("خطا — دوباره تلاش کنید" if lang == "fa" else "Error — try again", show_alert=True)
        return
    await callback.answer(
        (f"🎖 VIP شما {_to_persian_digits(days)} روز فعال شد!" if lang == "fa"
         else f"🎖 VIP activated for {days} days!"),
        show_alert=True,
    )
    await show_season_coupons(callback, session)


@router.callback_query(F.data == "enhanced_close")
async def enhanced_close(callback: CallbackQuery):
    # Safely delete the rewards menu message; fall back to simple answer
    try:
        await callback.message.delete()
    except Exception:
        lang = get_cached_lang(callback.from_user.id)
        await callback.answer(t(lang, "closed"))
