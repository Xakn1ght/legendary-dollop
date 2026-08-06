from aiogram import F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.handlers.admin.common import ADMIN_IDS
from app.utils.admin_bot_helper import get_user_bot
from app.utils.bot_i18n import t

from .common import _lang_for_tg_user, router


async def _pending_cashouts_view(session: AsyncSession):
    """Text + keyboard for the pending cash-out list (command and legacy callback share it)."""
    pending = await crud.list_cashout_requests(session, status="pending", limit=10)
    if not pending:
        return "هیچ درخواست برداشت در انتظار وجود ندارد.", None
    text_lines = ["**درخواست‌های برداشت (در انتظار)**\n"]
    kb = InlineKeyboardBuilder()
    for r in pending:
        text_lines.append(
            f"- `#{r.id}` | user_id=`{r.user_id}` | مبلغ=`{r.amount:,}`"
        )
        kb.button(text=f"پرداخت #{r.id}", callback_data=f"cashout_pay_{r.id}")
        kb.button(text=f"رد #{r.id}", callback_data=f"cashout_deny_{r.id}")
    kb.adjust(2)
    return "\n".join(text_lines), kb.as_markup()


@router.message(Command("cashouts"))
async def cashouts_command(message: Message, session: AsyncSession):
    """Command entry — the financial menu that used to link here is retired."""
    if message.from_user.id not in ADMIN_IDS:
        return
    text, markup = await _pending_cashouts_view(session)
    await message.answer(text, reply_markup=markup, parse_mode="Markdown")


@router.callback_query(F.data == "cashout_requests")
async def cashout_requests(callback: CallbackQuery, session: AsyncSession):
    """List pending cashout requests."""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return

    text, markup = await _pending_cashouts_view(session)
    await callback.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("cashout_pay_"))
async def cashout_pay_prompt(callback: CallbackQuery, session: AsyncSession):
    """Ask admin to send receipt photo for payout."""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return

    try:
        req_id = int(callback.data.split("_")[-1])
    except Exception:
        await callback.answer("نامعتبر.", show_alert=True)
        return

    req = await crud.get_cashout_request(session, req_id)
    if not req or req.status != "pending":
        await callback.answer(
            "این درخواست موجود نیست یا دیگر در انتظار نیست.", show_alert=True
        )
        return

    await callback.message.answer(
        "لطفاً رسید پرداخت را به صورت عکس ارسال کنید و در کپشن بنویسید:\n"
        f"`cashout_receipt_{req.id}`\n\n"
        f"مبلغ: `{req.amount:,}` | مقصد: `{(req.destination or '—')}`",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cashout_deny_"))
async def cashout_deny(callback: CallbackQuery, session: AsyncSession):
    """Deny a cashout request and refund reserved credit."""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return

    try:
        req_id = int(callback.data.split("_")[-1])
    except Exception:
        await callback.answer("نامعتبر.", show_alert=True)
        return

    req = await crud.deny_cashout_request(
        session, req_id, admin_user_id=callback.from_user.id, admin_note="Denied by admin"
    )
    if not req:
        await callback.answer("درخواست یافت نشد یا قابل رد نیست.", show_alert=True)
        return

    try:
        user_db = await crud.get_user_by_id(session, req.user_id)
        user_bot = get_user_bot()
        if user_db and user_bot:
            await user_bot.send_message(
                user_db.chat_id,
                f"درخواست برداشت شما با کد #{req.id} رد شد.\n"
                f"مبلغ {req.amount:,} تومان به کیف پول شما بازگردانده شد.",
            )
    except Exception:
        pass

    await callback.answer("رد شد.", show_alert=False)
    await cashout_requests(callback, session)


@router.message(F.photo, F.caption.startswith("cashout_receipt_"))
async def cashout_receipt_photo(message: Message, session: AsyncSession):
    """Admin sends payout receipt photo with caption cashout_receipt_<id>."""
    if message.from_user.id not in ADMIN_IDS:
        return

    try:
        req_id = int((message.caption or "").split("_")[-1])
    except Exception:
        await message.answer("کپشن نامعتبر است.")
        return

    req = await crud.get_cashout_request(session, req_id)
    if not req or req.status != "pending":
        await message.answer("این درخواست موجود نیست یا دیگر در انتظار نیست.")
        return

    file_id = message.photo[-1].file_id if message.photo else None
    paid = await crud.mark_cashout_paid(
        session,
        req_id,
        admin_user_id=message.from_user.id,
        receipt_file_id=file_id,
        receipt_message_id=message.message_id,
        admin_note="Paid by admin",
    )
    if not paid:
        await message.answer("خطا در ثبت پرداخت.")
        return

    try:
        user_db = await crud.get_user_by_id(session, paid.user_id)
        user_bot = get_user_bot()
        if user_db and user_bot:
            caption = (
                f"درخواست برداشت شما پرداخت شد.\n\nکد: #{paid.id}\n"
                f"مبلغ: {paid.amount:,} تومان"
            )
            sent = False
            if message.photo:
                # file_ids are bot-scoped: the photo arrived on the ADMIN bot, so
                # the user bot must re-upload the bytes, not reuse the file_id.
                try:
                    from io import BytesIO

                    from aiogram.types import BufferedInputFile

                    buf = BytesIO()
                    await message.bot.download(message.photo[-1], destination=buf)
                    buf.seek(0)
                    await user_bot.send_photo(
                        user_db.chat_id,
                        photo=BufferedInputFile(buf.getvalue(), filename="payout.jpg"),
                        caption=caption,
                    )
                    sent = True
                except Exception:
                    sent = False
            if not sent:
                await user_bot.send_message(user_db.chat_id, caption)
    except Exception:
        pass

    await message.answer(f"ثبت شد: پرداخت #{paid.id}")
