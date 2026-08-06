"""Legacy star-tier ladder screen — RETIRED (2026-07-19).

The tier ladder was deactivated on 2026-06-02 in favor of the Star Season
coupon system. This screen is only reachable from stale buttons in old chat
messages; it now shows a graceful notice and points at the live coupon
wallet instead of rendering an empty ladder.
"""

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

router = Router()

RETIRED_TEXT = (
    "<b>سطوح ستاره‌ها</b>\n\n"
    "این بخش جمع شده و جای آن «ستاره‌های فصل» فعال است.\n"
    "با معرفی دوستان ستاره فصلی جمع کنید؛ با هر نقطه عطف، کوپن تخفیف یا "
    "ترافیک رایگان به صورت خودکار در کیف کوپن شما باز می‌شود."
)


@router.callback_query(F.data == "show_star_levels")
async def show_star_levels(callback: CallbackQuery, session: AsyncSession):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="کیف کوپن من", callback_data="show_season_coupons")],
        [InlineKeyboardButton(text="بازگشت", callback_data="enhanced_rewards_menu")],
    ])
    try:
        await callback.message.edit_text(RETIRED_TEXT, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await callback.answer()
