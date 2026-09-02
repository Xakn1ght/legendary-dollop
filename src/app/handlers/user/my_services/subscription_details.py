import time

from aiogram.types import CopyTextButton, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.utils.sub_links import public_sub_url

from .constants import STATUS_MAP_NO_EMOJI
from .utils import convert_to_gb, to_persian_digits


def _fa_mb(value_gb: float) -> str:
    """Megabytes in Persian digits, for plans below 1 GB."""
    return to_persian_digits(int(round(float(value_gb or 0) * 1024)))


def _fa_gb(value: float) -> str:
    """GB figure in Persian digits: integer when whole, else one decimal
    with the Persian decimal mark (matches the card image)."""
    g = round(float(value or 0), 1)
    if g == int(g):
        return to_persian_digits(int(g))
    return to_persian_digits(str(g).replace('.', '٫'))


def build_subscription_detail(sub, user_info, generate_image=True):
    """Return (text, InlineKeyboardBuilder, media_bytes) for subscription detail screen.

    When generate_image=True, media_bytes is the static status PHOTO (PNG).
    Handlers render it off-thread via render_subscription_photo_async instead.
    """
    used = user_info.get('used_traffic', 0)
    limit = user_info.get('data_limit', 0)

    expire_ts = user_info.get('expire') or 0
    if expire_ts == 0:
        days_remaining = "نامحدود"
        days_remaining_chart = "نامحدود"
    else:
        secs_left = expire_ts - int(time.time())
        if secs_left > 0:
            days_count = secs_left // (60 * 60 * 24)
            days_remaining = days_count
            days_remaining_chart = days_count
        else:
            days_remaining = "پایان یافته"
            days_remaining_chart = "پایان یافته"

    status_str_chart = STATUS_MAP_NO_EMOJI.get(user_info.get('status', 'unknown'), 'نامشخص')

    used_gb = convert_to_gb(used)
    limit_gb = convert_to_gb(limit)
    carry_gb = convert_to_gb(sub.carry_over_bytes or 0)

    # Generate the chart image only if requested
    img_bytes = None
    if generate_image:
        from .chart_generator import generate_subscription_photo
        img_bytes = generate_subscription_photo(
            used_gb, limit_gb, days_remaining_chart, carry_gb, status_str_chart,
            sub.marzban_username, expire_ts=int(expire_ts or 0))

    # Public share link on the SUBLINK domain (bakbot parity). The panel's
    # subscription_url is a RELATIVE "/sub/<token>" — shown raw it is a dead
    # string (Pasha screenshot 2026-07-13), and the panel host must never
    # leak to users anyway.
    sub_url = None
    try:
        raw = user_info.get('subscription_url') if isinstance(user_info, dict) else None
        sub_url = public_sub_url(raw, token=getattr(sub, 'sub_token', None))
    except Exception:
        sub_url = None

    # Caption v3 (2026-07-12, Pasha: "a normal user with average age of 40
    # wouldnt understand shit"): ONE plain fact per line — RTL text mixed
    # with digits around separators turns into soup, so no dot-joins, no
    # quote blocks, no jargon. Remaining-first (the number users act on),
    # percent/used live in the card image. The link is a plain tap-to-copy
    # line with the instruction spelled out.
    lines = [f"<b>{sub.marzban_username}</b>", ""]
    lines.append(f"وضعیت: {status_str_chart}")
    if limit_gb:
        # A plan smaller than 1 GB reads in MB. The free trial is sold as
        # "۲۵۰ مگابایت"; rounded to GB it became "۰٫۲ گیگ", which understates
        # what was bought and is the first screen a new customer lands on.
        if 0 < limit_gb < 1:
            lines.append(f"حجم باقی‌مانده: {_fa_mb(max(limit_gb - used_gb, 0))} از "
                         f"{_fa_mb(limit_gb)} مگابایت")
        else:
            lines.append(f"حجم باقی‌مانده: {_fa_gb(max(limit_gb - used_gb, 0))} از {_fa_gb(limit_gb)} گیگ")
    else:
        lines.append("حجم: نامحدود")
    if isinstance(days_remaining, str):
        lines.append(f"زمان باقی‌مانده: {days_remaining}")
    else:
        lines.append(f"زمان باقی‌مانده: {to_persian_digits(int(days_remaining))} روز")
    if carry_gb:
        lines.append(f"ترافیک انتقالی: {_fa_gb(carry_gb)} گیگ")
    if sub_url:
        lines.append("")
        lines.append("لینک اتصال شما — با یک لمس کپی می‌شود:")
        lines.append(f"<code>{sub_url}</code>")
    text = "\n".join(lines)

    kb = InlineKeyboardBuilder()
    if str(sub.status) == 'pending' or user_info.get('status') in {'pending', 'on_hold'}:
        # Read-only pending card
        kb.button(text="ویرایش نام کاربری", callback_data=f"edituname_{sub.id}")
        kb.button(text="لغو و بازگشت مبلغ", callback_data=f"cancel_pending_{sub.id}")
        kb.button(text="پیام به ادمین", callback_data=f"support_for_sub_{sub.id}")
        kb.button(text="بازگشت", callback_data="my_services_list")
        kb.adjust(1)
    else:
        # v2 layout (2026-07-13, bakbot-informed): money actions first, then
        # the link (native clipboard button — one tap, no extra message),
        # then link tools, then info, then a way back. Explicit rows.
        kb.row(
            InlineKeyboardButton(text="شارژ سرویس", callback_data=f"charge_{sub.id}"),
            InlineKeyboardButton(text="رزرو پلن بعدی", callback_data=f"renew_{sub.marzban_username}"),
        )
        kb.row(InlineKeyboardButton(text="خرید روز بیشتر", callback_data=f"buydays_{sub.marzban_username}"))
        if sub_url and len(sub_url) <= 256:
            # Bot API caps copy_text at 256 chars; token links are ~60.
            kb.row(InlineKeyboardButton(text="کپی لینک اتصال", copy_text=CopyTextButton(text=sub_url)))
        kb.row(
            InlineKeyboardButton(text="همه لینک‌ها", callback_data=f"link_{sub.id}"),
            InlineKeyboardButton(text="لینک جدید", callback_data=f"revoke_{sub.id}"),
        )
        kb.row(
            InlineKeyboardButton(text="نمودار مصرف", callback_data=f"usage_{sub.id}"),
            InlineKeyboardButton(text="بروزرسانی", callback_data=f"refresh_{sub.id}"),
        )
        kb.row(
            InlineKeyboardButton(text="گزارش مشکل", callback_data=f"support_for_sub_{sub.id}"),
            InlineKeyboardButton(text="بازگشت به سرویس‌ها", callback_data="my_services_list"),
        )

    return text, kb, img_bytes
