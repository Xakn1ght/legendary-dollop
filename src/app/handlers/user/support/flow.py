from __future__ import annotations

from typing import List, Optional

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import SUPPORT_AVG_HANDLE_MINUTES, TROUBLESHOOTER_STEPS
from app.database import crud
from app.utils.bot_i18n import guess_lang_from_telegram, t
from app.utils.logger import log_user_action

from .common import (
    SupportStates,
    _controls_markup_simple,
    _image_confirmation_kb,
    _images_step_kb,
    _mask_sensitive,
    _two_column_builder,
    router,
    safe_edit_message,
)


@router.callback_query(F.data == "support_troubleshoot")
async def support_troubleshoot(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    os_name = data.get('os') or 'Android'
    steps = TROUBLESHOOTER_STEPS.get(os_name, TROUBLESHOOTER_STEPS['Android'])
    await state.update_data(ts_index=0)
    kb = InlineKeyboardBuilder()
    kb.button(text="حل شد ✅", callback_data="support_ts_resolved")
    kb.button(text="ادامه مشکل ⛔️", callback_data="support_ts_next")
    kb.adjust(2)
    await callback.message.answer(f"راهنمای {os_name} – مرحله 1:\n{steps[0]}", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "support_ts_next")
async def support_ts_next(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    os_name = data.get('os') or 'Android'
    steps = TROUBLESHOOTER_STEPS.get(os_name, TROUBLESHOOTER_STEPS['Android'])
    idx = int(data.get('ts_index', 0)) + 1
    if idx >= len(steps):
        await callback.message.answer("تمام گزینه‌ها بررسی شد. لطفاً اطلاعات بیشتری ارسال کنید یا منتظر پاسخ پشتیبانی بمانید.")
        await callback.answer()
        return
    await state.update_data(ts_index=idx)
    kb = InlineKeyboardBuilder()
    kb.button(text="حل شد ✅", callback_data="support_ts_resolved")
    kb.button(text="ادامه مشکل ⛔️", callback_data="support_ts_next")
    kb.adjust(2)
    await callback.message.answer(f"راهنمای {os_name} – مرحله {idx+1}:\n{steps[idx]}", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "support_ts_resolved")
async def support_ts_resolved(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("خوشحالیم مشکل حل شد ✅")
    await callback.answer()


@router.message(SupportStates.description_one, F.text)
async def simple_description(message: Message, state: FSMContext):
    data = await state.get_data()
    safe_text = _mask_sensitive(message.text.strip())
    await state.update_data(texts=[safe_text], text_msg_ids=[message.message_id])
    # After text, go to confirmation directly
    await state.set_state(SupportStates.confirm_simple)
    await message.answer("متن ثبت شد. برای ارسال، دکمه ‘ارسال’ را بزنید.", reply_markup=_controls_markup_simple())


# Allow the user to edit their Telegram message before submitting; keep state in sync
@router.edited_message(SupportStates.description_one, F.text)
async def description_one_edited(message: Message, state: FSMContext):
    data = await state.get_data()
    text_msg_ids: List[int] = data.get('text_msg_ids', []) or []
    if text_msg_ids and text_msg_ids[0] == message.message_id:
        safe_text = _mask_sensitive(message.text.strip())
        await state.update_data(texts=[safe_text])
        await message.answer("✅ متن شما بروزرسانی شد.")


@router.edited_message(SupportStates.confirm_simple, F.text)
async def confirm_simple_edited(message: Message, state: FSMContext):
    data = await state.get_data()
    text_msg_ids: List[int] = data.get('text_msg_ids', []) or []
    if text_msg_ids and text_msg_ids[0] == message.message_id:
        safe_text = _mask_sensitive(message.text.strip())
        await state.update_data(texts=[safe_text])
        await message.answer("✅ متن شما بروزرسانی شد.")


@router.callback_query(F.data == "support_yes_images")
async def simple_yes_images(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SupportStates.images_two)
    await safe_edit_message(
        callback,
        "تا ۲ تصویر مرتبط ارسال کنید. سپس ‘ادامه و نوشتن متن’ را بزنید.",
        _images_step_kb(0)
    )
    await callback.answer()

@router.callback_query(F.data == "support_no_images")
async def simple_no_images(callback: CallbackQuery, state: FSMContext):
    # Deprecated button removed from UI; keep as defensive handler
    await state.set_state(SupportStates.description_one)
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="بازگشت🔙", callback_data="support_back_main")
    kb.adjust(1)
    await safe_edit_message(callback, "حالا لطفاً مشکل را در یک پیام توضیح دهید (یک پیام متنی).", kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "support_continue_to_text")
async def continue_to_text(callback: CallbackQuery, state: FSMContext):
    # Move from images step to text entry
    await state.set_state(SupportStates.description_one)
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="بازگشت🔙", callback_data="support_back_main")
    kb.adjust(1)
    await safe_edit_message(callback, "حالا لطفاً مشکل را در یک پیام توضیح دهید (یک پیام متنی).", kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "support_img_remove_last")
async def remove_last_image(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    images: List[str] = data.get('images', [])
    image_msg_ids: List[int] = data.get('image_msg_ids', [])
    if images:
        images.pop()
        if image_msg_ids:
            image_msg_ids.pop()
        await state.update_data(images=images, image_msg_ids=image_msg_ids)
        await callback.message.answer(f"آخرین تصویر حذف شد. ({len(images)}/2)", reply_markup=_images_step_kb(len(images)))
    else:
        await callback.message.answer("تصویری برای حذف وجود ندارد.", reply_markup=_images_step_kb(0))
    await callback.answer()


@router.callback_query(F.data == "support_edit_desc")
async def start_edit_description(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SupportStates.edit_description)
    await callback.message.answer("متن جدید را ارسال کنید (یک پیام).")
    await callback.answer()


@router.message(SupportStates.edit_description, F.text)
async def save_edit_description(message: Message, state: FSMContext):
    await state.update_data(texts=[message.text.strip()], text_msg_ids=[message.message_id])
    # Return to confirmation view with controls
    await state.set_state(SupportStates.confirm_simple)
    await message.answer("متن بروزرسانی شد. آماده ارسال.", reply_markup=_controls_markup_simple())


# Note: Users can send images directly; no need to switch state via buttons.

@router.message(SupportStates.images_two, F.photo)
async def collect_image(message: Message, state: FSMContext):
    data = await state.get_data()
    images: List[str] = data.get('images', [])
    image_msg_ids: List[int] = data.get('image_msg_ids', [])
    if len(images) >= 2:
        await message.answer("حداکثر ۲ تصویر. برای تایید، ‘ارسال’ را بزنید.")
        return
    # Largest size photo
    file_id = message.photo[-1].file_id
    images.append(file_id)
    image_msg_ids.append(message.message_id)
    await state.update_data(images=images, image_msg_ids=image_msg_ids)
    lang = guess_lang_from_telegram(getattr(message.from_user, "language_code", None))
    await message.answer(
        t(lang, "support_image_saved").format(current=len(images), total=2),
        reply_markup=_images_step_kb(len(images)),
    )
    if len(images) == 2:
        await message.answer("۲ تصویر ذخیره شد. برای تایید، ‘ارسال’ را بزنید.", reply_markup=_images_step_kb(len(images)))


# Allow texts while in image-collection state (no need to switch)
@router.message(SupportStates.images_two, F.text)
async def collect_text_from_image_state(message: Message, state: FSMContext):
    # Record the single allowed description text when user types after (optional) images
    data = await state.get_data()
    if not data.get('texts'):
        from_text = _mask_sensitive(message.text.strip())
        await state.update_data(texts=[from_text], text_msg_ids=[message.message_id])
        await message.answer("متن ثبت شد. اگر لازم است تصویر دیگری بفرستید؛ سپس ‘ارسال’ را بزنید.", reply_markup=_controls_markup_simple())
    else:
        await message.answer("فقط یک متن لازم است. برای تایید، ‘ارسال’ را بزنید.", reply_markup=_controls_markup_simple())


@router.message(SupportStates.images_two)
async def ignore_non_photo(message: Message):
    # Accept text separately in collect_text_from_image_state; other types ignored
    await message.answer("فقط متن یا عکس ارسال کنید.")


@router.callback_query(F.data == "support_add_text")
async def back_to_texts(callback: CallbackQuery, state: FSMContext):
    # Kept for backward compatibility; no explicit switching required
    await state.set_state(SupportStates.collecting_texts)
    await callback.message.answer("متن یا تصویر خود را ارسال کنید.")
    await callback.answer()


@router.callback_query(F.data == "support_clear_last")
async def clear_last(callback: CallbackQuery, state: FSMContext):
    # Deprecated: per-item delete now available; keep as no-op or backward compatibility
    await callback.answer()


@router.callback_query(F.data == "support_clear_all")
async def clear_all(callback: CallbackQuery, state: FSMContext):
    # Deprecated; keep for backward compatibility
    await callback.answer()


@router.callback_query(F.data == "support_send")
async def submit_ticket(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    category = data.get('category') or 'other'
    texts: List[str] = data.get('texts', [])
    images: List[str] = data.get('images', [])
    os_name: Optional[str] = data.get('os')
    isp: Optional[str] = data.get('isp')

    # New simplified limits: 1 text (already enforced) and up to 2 images
    texts = texts[:1]
    images = images[:2]

    # Find user_id by chat_id
    from app.database.crud import get_user, is_user_vip
    user = await get_user(session, callback.from_user.id)
    if not user:
        await callback.answer("ابتدا /start را ارسال کنید.", show_alert=True)
        return

    # VIP users get high priority tickets
    is_vip = await is_user_vip(session, user.id)
    priority = 'high' if is_vip else 'normal'

    # Selected subscription if provided earlier
    subscr_id = data.get('subscription_id')
    ticket = await crud.create_ticket(
        session, user_id=user.id, category=category, os=os_name, isp=isp, subscription_id=subscr_id, priority=priority
    )

    # Store messages
    text_msg_ids: List[int] = data.get('text_msg_ids', [])
    image_msg_ids: List[int] = data.get('image_msg_ids', [])
    for i, t in enumerate(texts):
        tm_id = text_msg_ids[i] if i < len(text_msg_ids) else None
        await crud.add_ticket_message(session, ticket.id, sender='user', content_type='text', text=t, telegram_message_id=tm_id)
    for i, file_id in enumerate(images):
        mm_id = image_msg_ids[i] if i < len(image_msg_ids) else None
        await crud.add_ticket_message(session, ticket.id, sender='user', content_type='photo', file_id=file_id, telegram_message_id=mm_id)

    # The assistant may answer the first message straight away; every gate
    # (switch, human present, escalation words, rate limit) lives in the
    # service, and it stays silent unless all of them pass.
    if texts:
        from app.services.support_assist import maybe_answer_ticket
        await maybe_answer_ticket(session, ticket, user, texts[0], bot=callback.message.bot)

    # Compute queue position
    pos = await crud.get_category_queue_position(session, category, ticket.id)

    await state.clear()
    # ETA calculation (rough): (pos-1) * avg minutes
    eta_min = max(pos - 1, 0) * int(SUPPORT_AVG_HANDLE_MINUTES)
    if eta_min >= 60:
        eta_str = f"~{eta_min // 60} ساعت"
    else:
        eta_str = f"~{eta_min} دقیقه"
    
    # VIP priority message
    vip_msg = "\n👑 اولویت VIP: تیکت شما در اولویت بالا قرار دارد!" if is_vip else ""
    
    await safe_edit_message(callback, 
        f"درخواست شما ثبت شد.\n📍 جایگاه در صف: {pos}\n⏳ زمان تقریبی پاسخ: {eta_str}\n🧾 شناسه تیکت: {ticket.id}{vip_msg}",
        _two_column_builder([
            ("🎟 تیکت‌های من", f"support_my_tickets"),
            ("🔔 اطلاع‌رسانی پاسخ: روشن", f"support_toggle_notify_{ticket.id}")
        ])
    )
    await callback.answer()

    # Optional: notify admins via separate mechanism later
    log_user_action("support_ticket_submitted", user_id=user.id, category=category, ticket_id=ticket.id, position=pos)

    # Enhanced admin notification with open button
    try:
        from app.database import crud as _crud
        from app.handlers.admin.common import get_admin_broadcast_ids
        from app.services.pasarguard import pasarguard_api as _api
        # Build short summary
        first_text = (texts[0] if texts else "").strip()
        summary = "\n".join(first_text.splitlines()[:2])[:300]
        # Take primary subscription if any
        subs = await _crud.get_user_active_subscriptions(session, user.id)
        svc_line = "-"
        if subs:
            sub = subs[0]
            ui = await _api.get_fast_user_info(sub.marzban_username, getattr(sub, 'sub_token', None))
            if ui:
                dl = ui.get('data_limit') or 0
                ut = ui.get('used_traffic') or 0
                pct = (max(dl - ut, 0) / dl * 100) if dl > 0 else 0
                days = 0
                if ui.get('expire'):
                    from datetime import datetime as _dt
                    days = int(((_dt.utcfromtimestamp(ui['expire']) - _dt.utcnow()).total_seconds()) // 86400)
                svc_line = f"{sub.marzban_username} | {ui.get('status','-')} | {pct:.0f}% | {days}d"
            else:
                svc_line = f"{sub.marzban_username} | active"
        kb = InlineKeyboardBuilder()
        kb.button(text="🔎 باز کردن تیکت", callback_data=f"admin_sup_open_{ticket.id}")
        kb.button(text="📌 اختصاص به من", callback_data=f"admin_sup_claim_{ticket.id}")
        kb.adjust(2)
        for admin_chat_id in get_admin_broadcast_ids():
            try:
                await callback.bot.send_message(
                    admin_chat_id,
                    (
                        f"🆕 تیکت #{ticket.id}\n"
                        f"👤 {user.full_name or user.username or user.chat_id} (ID:{user.chat_id})\n"
                        f"🏷 دسته: {category}\n"
                        f"🧾 خلاصه:\n{summary or '—'}\n"
                        f"🛍 سرویس: {svc_line}\n"
                        f"📍 صف: {pos}"
                    ),
                    reply_markup=kb.as_markup()
                )
            except Exception:
                pass
    except Exception:
        pass

