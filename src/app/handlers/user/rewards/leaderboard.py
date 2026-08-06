from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud import get_leaderboard

router = Router()

@router.callback_query(F.data == "enhanced_leaderboard")
async def show_leaderboard_menu(callback: CallbackQuery, session: AsyncSession):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="معرفی", callback_data="leaderboard_referrals"),
            InlineKeyboardButton(text="مصرف", callback_data="leaderboard_usage"),
        ],
        [
            InlineKeyboardButton(text="فعالیت", callback_data="leaderboard_activity"),
            InlineKeyboardButton(text="خرید", callback_data="leaderboard_spending"),
        ],
        [InlineKeyboardButton(text="بازگشت", callback_data="enhanced_rewards_menu")],
    ])
    await callback.message.edit_text(
        "**جدول امتیازات**\n\nانتخاب کنید که کدام جدول امتیازات را مشاهده کنید:",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("leaderboard_"))
async def show_leaderboard(callback: CallbackQuery, session: AsyncSession):
    category = callback.data.replace("leaderboard_", "")
    names = {
        "referrals": "معرفی",
        "usage": "مصرف",
        "activity": "فعالیت",
        "spending": "خرید",
    }
    board = await get_leaderboard(session, category, limit=10)

    if not board:
        text = f"**جدول امتیازات {names.get(category, category)}**\n\nهنوز هیچ امتیازی ثبت نشده است!"
    else:
        text = f"**جدول امتیازات {names.get(category, category)}**\n\n"
        for i, entry in enumerate(board, 1):
            username = entry.user.username or entry.user.full_name or f"کاربر {entry.user.chat_id}"
            text += f"{i}. {username} - {entry.score:,} امتیاز\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="بروزرسانی", callback_data=callback.data),
        InlineKeyboardButton(text="بازگشت", callback_data="enhanced_rewards_menu"),
    ]])

    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await callback.answer("قبلاً بروزرسانی شده است!", show_alert=False)
        else:
            raise 