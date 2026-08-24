"""Free-trial buttons: tap and the subscription arrives.

No name prompt, no receipt step - the flow Pasha approved on the live sales
bot. All the work happens in services/flows/free_tests.start_free_test; this
module is only the button wiring and the error wording.
"""
from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.products import PRO_TEST_PLAN, TEST_PLAN
from app.database import crud
from app.keyboards.reply import get_main_keyboard
from app.services.flows.errors import FlowError
from app.services.flows.free_tests import format_cooldown, start_free_test

from .common import (
    FREE_TEST_BTN_EN,
    FREE_TEST_BTN_FA,
    PRO_TEST_BTN_EN,
    PRO_TEST_BTN_FA,
    PurchaseState,
    _lang_for,
    router,
)

_TIER_BY_LABEL = {
    FREE_TEST_BTN_FA: TEST_PLAN,
    FREE_TEST_BTN_EN: TEST_PLAN,
    PRO_TEST_BTN_FA: PRO_TEST_PLAN,
    PRO_TEST_BTN_EN: PRO_TEST_PLAN,
}


def _error_text(err: FlowError, lang: str) -> str:
    code = getattr(err, "code", "")
    if code == "test_cooldown":
        wait = format_cooldown(int(getattr(err, "remaining_seconds", 0) or 0), lang)
        if lang == "fa":
            return f"شما به تازگی از این تست استفاده کرده‌اید. {wait} دیگر می‌توانید دوباره تست بگیرید."
        return f"You have used this trial recently. You can take another in {wait}."
    if code == "test_in_progress":
        return ("تست شما در حال ساخت است. چند لحظه صبر کنید." if lang == "fa"
                else "Your trial is being created. Please wait a moment.")
    return ("ساخت تست ناموفق بود. لطفا دوباره تلاش کنید." if lang == "fa"
            else "Could not create the trial. Please try again.")


@router.message(PurchaseState.plan, F.text.in_(set(_TIER_BY_LABEL)))
async def take_free_test(message: Message, state: FSMContext, session: AsyncSession):
    tier = _TIER_BY_LABEL[(message.text or "").strip()]
    lang = await _lang_for(message, session)

    user = await crud.get_user(session, message.chat.id)
    if user is None:
        return

    # Leave the flow before provisioning: the trial needs neither a name nor a
    # receipt, so there is no purchase state left to be in, and the delivery
    # message should not arrive on top of a live keyboard.
    await state.clear()

    await message.answer(
        ("در حال ساخت اشتراک تست..." if lang == "fa" else "Creating your trial subscription..."),
        reply_markup=get_main_keyboard(message.chat.id, lang=lang),
    )

    try:
        await start_free_test(session, user, tier, bot=message.bot)
    except FlowError as e:
        await message.answer(_error_text(e, lang))
        return
    except Exception:
        await message.answer(_error_text(FlowError("unknown"), lang))
        return
