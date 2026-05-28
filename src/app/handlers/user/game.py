from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import GAME_PUBLIC_BASE_URL, GAME_WEBAPP_BASE_PATH
from app.database.crud import can_play_daily_game, get_game_leaderboard, get_user
from app.utils.text_format import to_persian_digits

router = Router()

def _game_menu_kb(play_url: str) -> InlineKeyboardMarkup:
    # Telegram requires HTTPS for web_app URLs. If not HTTPS, show a practice link via a normal URL button.
    if play_url.startswith("https://"):
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🎮 شروع بازی روزانه", web_app={"url": play_url})],
                [InlineKeyboardButton(text="🌐 باز کردن در مرورگر (تمرینی)", url=f"{GAME_PUBLIC_BASE_URL}{GAME_WEBAPP_BASE_PATH}?practice=1")],
                [InlineKeyboardButton(text="🏅 جدول روزانه", callback_data="game_lb_daily"),
                 InlineKeyboardButton(text="🏆 جدول هفتگی", callback_data="game_lb_weekly")],
                [InlineKeyboardButton(text="🔙 بازگشت", callback_data="enhanced_rewards_menu")],
            ]
        )
    else:
        practice_url = f"{GAME_PUBLIC_BASE_URL}{GAME_WEBAPP_BASE_PATH}?practice=1"
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔗 لینک تمرینی (بدون پاداش)", url=practice_url)],
                [InlineKeyboardButton(text="🏅 جدول روزانه", callback_data="game_lb_daily"),
                 InlineKeyboardButton(text="🏆 جدول هفتگی", callback_data="game_lb_weekly")],
                [InlineKeyboardButton(text="🔙 بازگشت", callback_data="enhanced_rewards_menu")],
            ]
        )

@router.callback_query(F.data == "open_daily_game")
async def open_daily_game(callback: CallbackQuery, session: AsyncSession):
    user = await get_user(session, callback.from_user.id)
    if not user:
        await callback.answer("کاربر یافت نشد", show_alert=True)
        return

    status = await can_play_daily_game(session, user.id)
    allowed = status.get("allowed", True)
    play_url = f"{GAME_PUBLIC_BASE_URL}{GAME_WEBAPP_BASE_PATH}?practice={'0' if allowed else '1'}"
    https_note = "" if play_url.startswith("https://") else "\n\n⚠️ برای باز شدن داخل تلگرام باید لینک HTTPS باشد. فعلاً می‌توانید حالت تمرینی را با لینک معمولی باز کنید."
    text = (
        "🚀 <b>بازی روزانه AstroByte Blaster</b>\n\n"
        + ("✅ امروز می‌توانید بازی کنید و پاداش بگیرید!\n" if allowed else "⏳ امروز پاداش گرفته‌اید؛ حالت تمرینی فعال است.\n")
        + f"✨ بهترین امتیاز امروز: {to_persian_digits(status.get('best_score', 0))}" + https_note + "\n\n"
        "- با فلش‌ها حرکت کنید و شلیک کنید.\n- هر روز یک بار پاداش می‌گیرید."
    )

    try:
        await callback.message.edit_text(text, reply_markup=_game_menu_kb(play_url), parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=_game_menu_kb(play_url), parse_mode="HTML")
    await callback.answer()

async def _render_leaderboard(callback: CallbackQuery, session: AsyncSession, period: str):
    data = await get_game_leaderboard(session, period=period, limit=10)
    title = "🏅 جدول روزانه" if period == "daily" else "🏆 جدول هفتگی"
    if not data:
        text = f"{title}\n\nرکوردی یافت نشد."
    else:
        lines = [title, ""]
        for row in data:
            name = row["name"]
            score = to_persian_digits(row["score"]) 
            lines.append(f"{row['rank']}. {name} — {score}")
        text = "\n".join(lines)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 بازگشت", callback_data="open_daily_game")]])
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data == "game_lb_daily")
async def game_lb_daily(callback: CallbackQuery, session: AsyncSession):
    await _render_leaderboard(callback, session, period="daily")

@router.callback_query(F.data == "game_lb_weekly")
async def game_lb_weekly(callback: CallbackQuery, session: AsyncSession):
    await _render_leaderboard(callback, session, period="weekly")


