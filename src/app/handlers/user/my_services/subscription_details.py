import time

from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core.settings import PASARGUARD_BASE_URL

from .constants import STATUS_MAP, STATUS_MAP_NO_EMOJI
from .utils import convert_to_gb, to_persian_digits


def build_subscription_detail(sub, user_info, generate_image=True):
    """Return (text, InlineKeyboardBuilder, media_bytes) for subscription detail screen.

    When generate_image=True, returns GIF bytes for backward compatibility.
    MP4 generation will be handled by the async renderer in handlers.
    """
    used = user_info.get('used_traffic', 0)
    limit = user_info.get('data_limit', 0)
    percent = (used / limit) if limit else 0

    expire_ts = user_info.get('expire') or 0
    if expire_ts == 0:
        days_remaining = "نامحدود ♾️"
        days_remaining_chart = "نامحدود"
    else:
        secs_left = expire_ts - int(time.time())
        if secs_left > 0:
            days_count = secs_left // (60 * 60 * 24)
            # Keep numeric count for chart, but display English in caption
            days_remaining = days_count
            days_remaining_chart = days_count
        else:
            days_remaining = "پایان یافته 🔚"
            days_remaining_chart = "پایان یافته"

    status_str = STATUS_MAP.get(user_info.get('status', 'unknown'), 'نامشخص')

    # Status string for chart (no emoji)
    status_str_chart = STATUS_MAP_NO_EMOJI.get(user_info.get('status', 'unknown'), 'نامشخص')

    used_gb = convert_to_gb(used)
    limit_gb = convert_to_gb(limit)
    carry_gb = convert_to_gb(sub.carry_over_bytes or 0)

    # Generate the chart image only if requested
    img_bytes = None
    if generate_image:
        from .chart_generator import generate_subscription_chart
        img_bytes = generate_subscription_chart(used_gb, limit_gb, days_remaining_chart, carry_gb, status_str_chart, sub.marzban_username)

    # Localized numbers
    def _fmt_num(val):
        try:
            return to_persian_digits(val)
        except Exception:
            return str(val)

    percent_str = _fmt_num(f"{percent*100:.1f}")
    used_str = _fmt_num(used_gb)
    limit_str = _fmt_num(limit_gb if limit_gb else '∞')
    # Show remaining time in English like "73 days" (avoid Persian numerals here)
    if isinstance(days_remaining, str):
        days_str = days_remaining
    else:
        try:
            # Force LTR so it doesn't flip inside Persian text
            days_str = f"\u2066{int(days_remaining)} days\u2069"
        except Exception:
            days_str = f"\u2066{days_remaining} days\u2069"
    carry_str = _fmt_num(f"{carry_gb:.1f} GB") if carry_gb else "-"

    # Compose subscription URL: prefer user_info, fallback to stored token
    sub_url = None
    try:
        if isinstance(user_info, dict):
            sub_url = user_info.get('subscription_url')
        if not sub_url and getattr(sub, 'sub_token', None):
            sub_url = f"{PASARGUARD_BASE_URL}/sub/{sub.sub_token}"
    except Exception:
        sub_url = None

    # Build detail text with link directly under username
    text = f"👤 <b>{sub.marzban_username}</b>\n"
    if sub_url:
        text += f"<code>{sub_url}</code>\n"
    text += (
        f"📊 وضعیت: {status_str}\n"
        f"📈 مصرف: {used_str}/{limit_str} GB  ({percent_str}%)\n"
        f"⏳ زمان باقی مانده: {days_str}\n"
        f"📦 ترافیک انتقالی: {carry_str}"
    )

    kb = InlineKeyboardBuilder()
    if str(sub.status) == 'pending' or user_info.get('status') in {'pending', 'on_hold'}:
        # Read-only pending card
        kb.button(text="✏️ ویرایش نام کاربری", callback_data=f"edituname_{sub.id}")
        kb.button(text="❌ لغو و بازگشت مبلغ", callback_data=f"cancel_pending_{sub.id}")
        kb.button(text="📨 پیام به ادمین", callback_data=f"support_for_sub_{sub.id}")
        kb.button(text="⬅️ بازگشت", callback_data="my_services_list")
        kb.adjust(1)
    else:
        # Row 1: Charge + Buy more days
        kb.button(text="🔋 شارژ", callback_data=f"charge_{sub.id}")
        kb.button(text="📅 خرید روز بیشتر", callback_data=f"buydays_{sub.marzban_username}")
        # Row 2: Usage + Subscription links
        kb.button(text="📈 مصرف", callback_data=f"usage_{sub.id}")
        kb.button(text="🌐 لینک اشتراک", callback_data=f"link_{sub.id}")
        # Single refresh button: text every 30s; GIF auto if 1h passed
        kb.button(text="↻ بروزرسانی", callback_data=f"refresh_{sub.id}")
        kb.button(text="🆘 گزارش مشکل", callback_data=f"support_for_sub_{sub.id}")
        # Deletion options removed by product decision
        kb.button(text="🔁 لینک جدید", callback_data=f"revoke_{sub.id}")
        kb.adjust(2)

    return text, kb, img_bytes
