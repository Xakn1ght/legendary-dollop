from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import PLANS, PLANS_BUTTON_COLUMNS
from app.database import crud
from app.handlers.user.flow_inline import ikb
from app.shared.plan_ordering import get_ordered_plans
from app.utils.bot_i18n import normalize_lang, set_cached_lang, t

router = Router()


class PurchaseState(StatesGroup):
    referral_code = State()
    # Level 1 of the purchase menu: Normal or Pro. The two never share a
    # screen - a rule Pasha approved on the live sales bot, so a customer
    # cannot buy a Pro plan thinking it is a normal one.
    plan_category = State()
    plan = State()
    custom_gb = State()
    auto_renew_choice = State()
    renewal_template = State()
    name = State()
    ask_discount = State()
    ask_coupon = State()
    ask_credit = State()
    confirmation = State()
    receipt = State()
    edit_choice = State()


CUSTOM_PLAN_BTN_FA = "پلن دلخواه"
CUSTOM_PLAN_BTN_EN = "Custom Plan"

# Level-1 categories.
CAT_NORMAL_BTN_FA = "اشتراک معمولی"
CAT_NORMAL_BTN_EN = "Normal subscription"
CAT_PRO_BTN_FA = "اشتراک پرو (همه اپراتورها)"
CAT_PRO_BTN_EN = "Pro subscription (all operators)"

# Free trials. Labels are STATIC: the button is hidden entirely while a user
# is on cooldown (Pasha's call) rather than relabelled with the remaining
# time, which also keeps the ikb() bridge's exact-text matching intact.
FREE_TEST_BTN_FA = "تست رایگان - ۲۵۰ مگابایت / ۱۰ روز"
FREE_TEST_BTN_EN = "Free test - 250 MB / 10 days"
PRO_TEST_BTN_FA = "تست پرو رایگان - ۲۵۰ مگابایت / ۱۰ روز"
PRO_TEST_BTN_EN = "Free Pro test - 250 MB / 10 days"

# Pro is sold by GB, so its "plan" button opens a GB prompt.
PRO_BUY_BTN_FA = "خرید اشتراک پرو"
PRO_BUY_BTN_EN = "Buy a Pro subscription"


def category_labels(lang: str) -> tuple[str, str]:
    if lang == "fa":
        return CAT_NORMAL_BTN_FA, CAT_PRO_BTN_FA
    return CAT_NORMAL_BTN_EN, CAT_PRO_BTN_EN


def free_test_label(tier: str, lang: str) -> str:
    from app.core.products import PRO_TEST_PLAN

    if tier == PRO_TEST_PLAN:
        return PRO_TEST_BTN_FA if lang == "fa" else PRO_TEST_BTN_EN
    return FREE_TEST_BTN_FA if lang == "fa" else FREE_TEST_BTN_EN


def pro_route_available() -> bool:
    """Pro is offered only when its panel group is configured - mirrors the
    live bot's plan_available('ir_tun') gate."""
    try:
        from app.core.settings import PASARGUARD_IR_TUN_GROUP_ID

        return bool(PASARGUARD_IR_TUN_GROUP_ID)
    except Exception:
        return False


async def _category_keyboard(state: FSMContext, lang: str = "fa") -> InlineKeyboardMarkup:
    normal, pro = category_labels(lang)
    rows = [[normal]]
    if pro_route_available():
        rows.append([pro])
    rows.append([t(lang, "btn_back")])
    return await ikb(state, rows)


async def _pro_plan_keyboard(
    state: FSMContext, lang: str = "fa", show_free_test: bool = False
) -> InlineKeyboardMarkup:
    from app.core.products import PRO_TEST_PLAN

    rows = []
    if show_free_test:
        rows.append([free_test_label(PRO_TEST_PLAN, lang)])
    rows.append([PRO_BUY_BTN_FA if lang == "fa" else PRO_BUY_BTN_EN])
    rows.append([t(lang, "btn_back")])
    return await ikb(state, rows)


async def _normal_plan_keyboard(
    state: FSMContext, lang: str = "fa", is_vip: bool = False, show_free_test: bool = False
) -> InlineKeyboardMarkup:
    from app.core.products import TEST_PLAN

    rows = []
    if show_free_test:
        rows.append([free_test_label(TEST_PLAN, lang)])
    keys = get_ordered_plans()
    # Filter VIP-only plans based on user's VIP status
    available_keys = []
    for k in keys:
        plan = PLANS.get(k, {})
        if plan.get('vip_only', False) and not is_vip:
            continue  # Skip VIP-only plans for non-VIP users
        available_keys.append(k)

    for i in range(0, len(available_keys), PLANS_BUTTON_COLUMNS):
        rows.append(available_keys[i:i + PLANS_BUTTON_COLUMNS])
    rows.append([CUSTOM_PLAN_BTN_FA if lang == "fa" else CUSTOM_PLAN_BTN_EN])
    rows.append([t(lang, "btn_back")])
    return await ikb(state, rows)


# Kept as an alias: re-exported from purchase/__init__ and used by tests.
_build_plan_keyboard = _normal_plan_keyboard


async def _get_plan_keyboard_for_user(
    session, chat_id: int, state: FSMContext, lang: str = "fa", route: str = "normal"
) -> InlineKeyboardMarkup:
    """Plan keyboard for one route, with VIP filtering and trial availability."""
    from app.core.products import PRO_TEST_PLAN, ROUTE_PRO, TEST_PLAN
    from app.services.flows.free_tests import is_free_test_available

    user = await crud.get_user(session, chat_id)
    is_vip = await crud.is_user_vip(session, user.id) if user else False

    tier = PRO_TEST_PLAN if route == ROUTE_PRO else TEST_PLAN
    show_free_test = False
    if user is not None:
        try:
            show_free_test = await is_free_test_available(session, user, tier)
        except Exception:
            # Never let an eligibility hiccup take the whole menu down; the
            # money path re-checks before anything is provisioned anyway.
            show_free_test = False

    if route == ROUTE_PRO:
        return await _pro_plan_keyboard(state, lang, show_free_test=show_free_test)
    return await _normal_plan_keyboard(state, lang, is_vip, show_free_test=show_free_test)


async def _category_keyboard_for_user(session, chat_id: int, state: FSMContext, lang: str = "fa"):
    return await _category_keyboard(state, lang)


async def _lang_for(message: Message, session: AsyncSession) -> str:
    """Best-effort language resolution for this user."""
    try:
        user = await crud.get_user(session, message.chat.id)
        lang = normalize_lang(getattr(user, "language", None)) if user else normalize_lang(getattr(message.from_user, "language_code", None))
        set_cached_lang(message.chat.id, lang)
        return lang
    except Exception:
        return normalize_lang(getattr(message.from_user, "language_code", None))


async def _auto_renew_keyboard(state: FSMContext, lang: str) -> InlineKeyboardMarkup:
    return await ikb(state, [
        [("فعال‌سازی تمدید خودکار" if lang == "fa" else "Enable auto-renew")],
        [("بدون تمدید خودکار" if lang == "fa" else "No auto-renew")],
        [t(lang, "btn_back")],
    ])


async def _name_keyboard(state: FSMContext, lang: str) -> InlineKeyboardMarkup:
    return await ikb(state, [
        [("اتفاقی" if lang == "fa" else "Random")],
        [t(lang, "btn_back")],
    ])


async def _back_keyboard(state: FSMContext, lang: str) -> InlineKeyboardMarkup:
    return await ikb(state, [[t(lang, "btn_back")]])


async def _confirm_keyboard(state: FSMContext, lang: str) -> InlineKeyboardMarkup:
    return await ikb(state, [
        [("تایید و پرداخت ✅" if lang == "fa" else "Confirm & Pay ✅")],
        [("ویرایش ✏️" if lang == "fa" else "Edit ✏️"), t(lang, "btn_back")],
    ])


# NOTE: orders are now created only at Confirm & Pay via
# app.services.flows.purchase.start_purchase_order; cancellation/refunds go through
# cancel_purchase_order. The old _cleanup_pending_subscription helper is gone.
