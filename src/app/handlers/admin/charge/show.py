import logging

from aiogram import Bot, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.handlers.admin.common import ADMIN_IDS
from app.utils.bot_i18n import t

from .common import GB, _admin_lang, router


@router.callback_query(F.data.startswith("show_charge_"))
async def show_charge_request(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    lang = await _admin_lang(session, callback.from_user)
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(lang, "not_authorized"), show_alert=True)
        return

    req_id = int(callback.data.split("_")[2])

    charge_req = await crud.get_charge_request(session, req_id)
    if not charge_req:
        await callback.answer(t(lang, "admin_charge_not_found"), show_alert=True)
        return

    await session.refresh(charge_req, attribute_names=["user", "subscription"])

    if charge_req.receipt_message_id and charge_req.user:
        try:
            await bot.copy_message(
                chat_id=callback.from_user.id,
                from_chat_id=charge_req.user.chat_id,
                message_id=charge_req.receipt_message_id,
            )
        except Exception as e:
            logging.warning(f"Failed to copy receipt #{req_id}: {e}")

    kb = InlineKeyboardBuilder()
    kb.button(text="تایید", callback_data=f"approve_charge_{req_id}")
    kb.button(text="رد", callback_data=f"deny_charge_{req_id}")
    kb.adjust(2)

    pkg_parts: list[str] = []
    if charge_req.traffic_bytes:
        gb_amount = charge_req.traffic_bytes / GB
        pkg_parts.append(f"{gb_amount:g}GB")
    if charge_req.extra_days:
        pkg_parts.append(f"+{charge_req.extra_days}days")
    pkg_desc = " ".join(pkg_parts) if pkg_parts else "-"

    await callback.message.edit_text(
        t(lang, "admin_charge_request_details").format(
            id=req_id,
            user=(charge_req.user.full_name if charge_req.user else charge_req.user_id),
            user_id=charge_req.user_id,
            subscription_id=charge_req.subscription_id,
            package=pkg_desc,
            price=charge_req.price,
        ),
        reply_markup=kb.as_markup(),
    )

    await callback.answer()
