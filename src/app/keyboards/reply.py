from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from app.core.settings import BOT_TOKEN, DASHBOARD_PUBLIC_BASE_URL, DASHBOARD_WEBAPP_BASE_PATH, WEBAPP_SESSION_SECRET
from app.utils.bot_i18n import get_cached_lang, t
from app.utils.webapp_verify import create_one_time_token


def get_main_keyboard(user_id: int, is_admin: bool = False, lang: str | None = None) -> ReplyKeyboardMarkup:
    """Generate main keyboard (localized)."""
    # IMPORTANT:
    # Some Telegram clients intermittently provide empty initData. In those cases the WebApp
    # cannot authenticate unless we include a short-lived URL token.
    # Keep TTL short to reduce exposure if the URL leaks.
    session_secret = WEBAPP_SESSION_SECRET or BOT_TOKEN
    auth_token = create_one_time_token(user_id, session_secret, ttl_seconds=15 * 60)  # 15 minutes
    dashboard_url = f"{DASHBOARD_PUBLIC_BASE_URL}{DASHBOARD_WEBAPP_BASE_PATH}?auth={auth_token}"
    lang = lang or get_cached_lang(user_id)
    
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_buy")), KeyboardButton(text=t(lang, "btn_my_services"))],
            [KeyboardButton(text=t(lang, "btn_recharge")), KeyboardButton(text=t(lang, "btn_support"))],
            [KeyboardButton(text=t(lang, "btn_rewards")), KeyboardButton(text=t(lang, "btn_invite"))],
            [KeyboardButton(text=t(lang, "btn_add_service")), KeyboardButton(text=t(lang, "btn_guide"))],
            [KeyboardButton(text=t(lang, "btn_language")), KeyboardButton(text=t(lang, "btn_dashboard"), web_app=WebAppInfo(url=dashboard_url))],
        ],
        resize_keyboard=True
    )


# Legacy static keyboard for backward compatibility (no dashboard button)
KEYBOARD_MARKUP_MAIN = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='💳 خرید سرویس'), KeyboardButton(text='🛍 سرویس‌های من')],
        [KeyboardButton(text='⚡️ شارژ سرویس'), KeyboardButton(text='💬 پشتیبانی')],
        [KeyboardButton(text='🎁 پاداش‌ها'), KeyboardButton(text='💌 کد دعوت')],
        [KeyboardButton(text='➕ افزودن سرویس'), KeyboardButton(text='📚 راهنمای اتصال')],
    ],
    resize_keyboard=True
)

KEYBOARD_MARKUP_BACK = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='بازگشت🔙')]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

KEYBOARD_MARKUP_TUTORIAL = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='اندروید📱'), KeyboardButton(text='آیفون📱'), KeyboardButton(text='ویندوز💻')],
        [KeyboardButton(text='بازگشت🔙')]
    ],
    resize_keyboard=True
)

KEYBOARD_MARKUP_PURCHASE = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="۲۰ گیگابایت"), KeyboardButton(text="۴۰ گیگابایت")],
        [KeyboardButton(text="۶۰ گیگابایت"), KeyboardButton(text="۱۰۰ گیگابایت")],
        [KeyboardButton(text='بازگشت🔙')]
    ],
    resize_keyboard=True
)

KEYBOARD_MARKUP_CONFIRM_PURCHASE = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="تایید و پرداخت ✅")],
        [KeyboardButton(text="ویرایش ✏️"), KeyboardButton(text='بازگشت🔙')]
    ],
    resize_keyboard=True
)

# -------- Admin keyboard ----------

def get_admin_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    """Generate admin keyboard (WebApp-only admin)."""
    # Admin is WebApp-only; keep only a single WebApp entry point.
    admin_panel_url = f"{DASHBOARD_PUBLIC_BASE_URL}/admin/"
    
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='👑 Admin Panel', web_app=WebAppInfo(url=admin_panel_url))],
            [KeyboardButton(text='Close menu 🔙')]
        ],
        resize_keyboard=True
    )

# Legacy static admin keyboard (without WebApp)
KEYBOARD_MARKUP_ADMIN = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='تنظیمات⚙️'), KeyboardButton(text='🔙 بستن منو')]
    ],
    resize_keyboard=True
) 
