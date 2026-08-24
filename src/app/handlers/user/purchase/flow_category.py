"""Level 1 of the purchase menu: Normal or Pro.

The two never share a screen. That is the rule Pasha approved on the live
sales bot, and a test there locks it in - a customer must not be able to buy a
Pro plan believing it is a normal one, or the reverse.
"""
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.products import ROUTE_NORMAL, ROUTE_PRO
from app.keyboards.reply import get_main_keyboard

from .common import (
    PurchaseState,
    _category_keyboard,
    _get_plan_keyboard_for_user,
    _lang_for,
    category_labels,
    pro_route_available,
    router,
)

_BACK_TEXTS = {"بازگشت🔙", "Back 🔙"}


async def show_category_menu(message: Message, state: FSMContext, session: AsyncSession, lang: str):
    await state.set_state(PurchaseState.plan_category)
    await message.answer(
        ("نوع اشتراک را انتخاب کنید:" if lang == "fa" else "Choose a subscription type:"),
        reply_markup=await _category_keyboard(state, lang),
    )


async def show_plan_menu(message: Message, state: FSMContext, session: AsyncSession, lang: str, route: str):
    await state.update_data(route=route)
    await state.set_state(PurchaseState.plan)
    if route == ROUTE_PRO:
        prompt = "پلن پرو را انتخاب کنید:" if lang == "fa" else "Choose a Pro plan:"
    else:
        prompt = "لطفا یکی از پلن های زیر را انتخاب کنید:" if lang == "fa" else "Please choose a plan:"
    await message.answer(
        prompt,
        reply_markup=await _get_plan_keyboard_for_user(session, message.chat.id, state, lang, route=route),
    )


@router.message(PurchaseState.plan_category)
async def process_plan_category(message: Message, state: FSMContext, session: AsyncSession):
    """Catch-all for level 1, in the same shape as invalid_plan.py.

    Registered as the only handler for this state so nothing can shadow it.
    """
    text = (message.text or "").strip()

    if text.startswith("/start"):
        await state.clear()
        return

    lang = await _lang_for(message, session)
    normal_label, pro_label = category_labels(lang)

    if text == normal_label:
        await show_plan_menu(message, state, session, lang, ROUTE_NORMAL)
        return

    if text == pro_label:
        if not pro_route_available():
            await message.answer(
                ("اشتراک پرو در حال حاضر در دسترس نیست." if lang == "fa"
                 else "Pro subscriptions are not available right now."),
                reply_markup=await _category_keyboard(state, lang),
            )
            return
        await show_plan_menu(message, state, session, lang, ROUTE_PRO)
        return

    # Back at level 1 means leaving the purchase entirely - there is no level
    # above it, and no order row exists yet.
    if text in _BACK_TEXTS:
        await state.clear()
        await message.answer(
            ("خرید لغو شد. به منوی اصلی بازگشتید." if lang == "fa"
             else "Purchase cancelled. Back to main menu."),
            reply_markup=get_main_keyboard(message.chat.id, lang=lang),
        )
        return

    # A main-menu button tapped while stuck here must escape the flow rather
    # than be eaten - same fix as invalid_plan.py (2026-07-14).
    from .invalid_plan import _menu_texts

    if text in _menu_texts():
        await state.clear()
        raise SkipHandler()

    await message.answer(
        ("لطفا از دکمه های زیر استفاده کنید." if lang == "fa" else "Please use the buttons below."),
        reply_markup=await _category_keyboard(state, lang),
    )
