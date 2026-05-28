from aiogram import F, Router
from aiogram.types import Message, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import BOT_TOKEN, DASHBOARD_PUBLIC_BASE_URL, WEBAPP_SESSION_SECRET
from app.database import crud
from app.utils.bot_i18n import normalize_lang, set_cached_lang, t, text_matches
from app.utils.webapp_verify import create_one_time_token

router = Router()

def _build_rewards_webapp_url(user_chat_id: int) -> str:
    session_secret = WEBAPP_SESSION_SECRET or BOT_TOKEN
    auth_token = create_one_time_token(user_chat_id, session_secret, ttl_seconds=15 * 60)
    return f"{DASHBOARD_PUBLIC_BASE_URL}/webapp/dashboard/tasks.html?auth={auth_token}"

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
    stars = user.stars or 0
    
    referee_list = "\n".join([f" - {ref.full_name or ref.username}" for ref in referees]) if referees else ("هنوز کسی از کد شما استفاده نکرده است." if lang == "fa" else "No one has used your code yet.")

    referral_message = (
        (
        "💌 کد دعوت شما:\n"
        f"<code>{user.referral_code}</code>\n\n"
        "دعوت دوستان = هدیه برای شما!\n"
        f"🎟️ بن‌های باز: {len(vouchers)} | ⭐ ستاره: {stars}/5 | 💰 اعتبار: {credit:,} تومان\n\n"
        "لیست افرادی که با کد شما عضو شده اند:\n"
        f"{referee_list}"
        )
        if lang == "fa"
        else (
            "💌 Your invite code:\n"
            f"<code>{user.referral_code}</code>\n\n"
            "Invite friends = get rewards!\n"
            f"🎟️ Open vouchers: {len(vouchers)} | ⭐ Stars: {stars}/5 | 💰 Credit: {credit:,} Toman\n\n"
            "People who joined with your code:\n"
            f"{referee_list}"
        )
    )
    
    kb = InlineKeyboardBuilder()
    try:
        kb.button(text=("⭐ Rewards (WebApp)" if lang != "fa" else "⭐ پاداش‌ها (وب‌اپ)"), web_app=WebAppInfo(url=_build_rewards_webapp_url(message.chat.id)))
        kb.adjust(1)
        await message.answer(referral_message, parse_mode='HTML', reply_markup=kb.as_markup())
    except Exception:
        await message.answer(referral_message, parse_mode='HTML')
