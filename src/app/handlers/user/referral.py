from aiogram import Router
from aiogram.types import Message, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import DASHBOARD_PUBLIC_BASE_URL
from app.database import crud
from app.handlers.user.start.common import _create_share_button
from app.utils.bot_i18n import normalize_lang, set_cached_lang, t, text_matches
from app.utils.premium_emoji import answer_premium

router = Router()

def _build_rewards_webapp_url(user_chat_id: int) -> str:
    # WebAppInfo button → Telegram injects signed initData; no URL token
    # (raw links with tokens must never grant access — Telegram-only policy).
    return f"{DASHBOARD_PUBLIC_BASE_URL}/webapp/dashboard/#page=tasks"

@router.message(text_matches("btn_invite"))
async def referral_handler(message: Message, session: AsyncSession):
    user = await crud.get_user(session, message.chat.id)
    if not user or not user.referral_code:
        # This should ideally not happen if user is created on /start
        lang = normalize_lang(getattr(user, "language", None))
        await message.answer(t(lang, "start_bot_first"))
        return
    lang = normalize_lang(getattr(user, "language", None))
    set_cached_lang(message.chat.id, lang)
    
    referees = await crud.get_referees_by_referrer(session, user.id)
    # Additional info
    vouchers = await crud.get_unspent_rewards_by_referrer(session, user.id)
    credit = user.credit or 0
    _season, season_stars = await crud.get_season_progress(session, user.id)

    from app.core.rewards_config import CASHOUT_MIN_ACTIVE_REFERRALS
    from app.services.flows.cashout import count_active_referrals, promoter_credit_percent

    active_refs = await count_active_referrals(session, user.id)
    credit_pct = int(promoter_credit_percent(active_refs))

    referee_list = "\n".join([f" - {ref.full_name or ref.username}" for ref in referees]) if referees else ("هنوز کسی از کد شما استفاده نکرده است." if lang == "fa" else "No one has used your code yet.")

    referral_message = (
        (
        "💌 کد دعوت شما:\n"
        f"<code>{user.referral_code}</code>\n\n"
        "با هر خرید دوستِ شما، یکی را انتخاب می‌کنید:\n"
        f"💰 {credit_pct}٪ اعتبار نقدی · 📶 ۱۰٪ حجم · 📅 ۱۰٪ زمان · ⭐ ستاره فصل\n"
        f"سطح شما: {credit_pct}٪ (با ۲۰ دعوت فعال → ۱۲٪، با ۵۰ → ۱۵٪)\n"
        f"از {CASHOUT_MIN_ACTIVE_REFERRALS} دعوت فعال به بعد، اعتبار قابل برداشت نقدی است 💳\n\n"
        f"🎟️ بن‌های باز: {len(vouchers)} | ⭐ ستاره فصل: {season_stars} | 💰 اعتبار: {credit:,} تومان\n"
        f"👥 دعوت فعال: {active_refs}\n\n"
        "لیست افرادی که با کد شما عضو شده اند:\n"
        f"{referee_list}"
        )
        if lang == "fa"
        else (
            "💌 Your invite code:\n"
            f"<code>{user.referral_code}</code>\n\n"
            "Every time a friend buys, you pick one:\n"
            f"💰 {credit_pct}% cash credit · 📶 10% data · 📅 10% days · ⭐ season star\n"
            f"Your tier: {credit_pct}% (20 active invites → 12%, 50 → 15%)\n"
            f"From {CASHOUT_MIN_ACTIVE_REFERRALS} active invites, credit becomes cash-out-able 💳\n\n"
            f"🎟️ Open vouchers: {len(vouchers)} | ⭐ Season stars: {season_stars} | 💰 Credit: {credit:,} Toman\n"
            f"👥 Active invites: {active_refs}\n\n"
            "People who joined with your code:\n"
            f"{referee_list}"
        )
    )
    
    kb = InlineKeyboardBuilder()
    try:
        kb.row(_create_share_button(message.bot, user.referral_code, lang))
        kb.button(text=("⭐ Rewards (WebApp)" if lang != "fa" else "⭐ پاداش‌ها (وب‌اپ)"), web_app=WebAppInfo(url=_build_rewards_webapp_url(message.chat.id)))
        kb.adjust(1)
        await answer_premium(message, referral_message, reply_markup=kb.as_markup())
    except Exception:
        await answer_premium(message, referral_message)
