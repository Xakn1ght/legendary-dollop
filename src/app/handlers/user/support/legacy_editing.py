from __future__ import annotations

from typing import List

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .common import SupportStates, router, safe_edit_message


@router.callback_query(F.data.startswith("support_text_ok_"))
async def text_ok(callback: CallbackQuery):
    await callback.answer("تایید شد.")


@router.callback_query(F.data.startswith("support_text_del_"))
async def text_delete(callback: CallbackQuery, state: FSMContext):
    idx = int(callback.data.removeprefix("support_text_del_"))
    data = await state.get_data()
    texts: List[str] = data.get('texts', [])
    if 0 <= idx < len(texts):
        texts.pop(idx)
        await state.update_data(texts=texts)
        await safe_edit_message(callback, "پیام حذف شد.")
    await callback.answer()


@router.callback_query(F.data.startswith("support_text_edit_"))
async def text_edit_start(callback: CallbackQuery, state: FSMContext):
    idx = int(callback.data.removeprefix("support_text_edit_"))
    await state.set_state(SupportStates.editing_text)
    await state.update_data(edit_index=idx)
    await callback.message.answer("متن جدید را ارسال کنید.")
    await callback.answer()


@router.message(SupportStates.editing_text, F.text)
async def text_edit_save(message: Message, state: FSMContext):
    data = await state.get_data()
    idx = data.get('edit_index', -1)
    texts: List[str] = data.get('texts', [])
    if 0 <= idx < len(texts):
        texts[idx] = message.text.strip()
        await state.update_data(texts=texts)
        await state.clear()
        await message.answer("ویرایش شد ✅")
    else:
        await state.clear()
        await message.answer("موردی برای ویرایش یافت نشد.")


# ------- Image delete callback -------

@router.callback_query(F.data.startswith("support_img_del_"))
async def image_delete(callback: CallbackQuery, state: FSMContext):
    idx = int(callback.data.removeprefix("support_img_del_"))
    data = await state.get_data()
    images: List[str] = data.get('images', [])
    if 0 <= idx < len(images):
        images.pop(idx)
        await state.update_data(images=images)
        await safe_edit_message(callback, "تصویر حذف شد.")
    await callback.answer()

