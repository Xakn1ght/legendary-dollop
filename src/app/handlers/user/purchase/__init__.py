"""User purchase flow; submodules register handlers on the shared `router`."""

from app.core.settings import PLANS

# Order matters: preserve the same handler registration sequence as the legacy monolith.
from . import (
    common,  # noqa: F401
    confirmation,  # noqa: F401
    coupon,  # noqa: F401
    credit,  # noqa: F401
    edit_flow,  # noqa: F401
    flow_category,  # noqa: F401
    flow_referral_plan,  # noqa: F401
    free_test,  # noqa: F401
    invalid_plan,  # noqa: F401
    name_discount,  # noqa: F401
    plan_exits,  # noqa: F401
    receipt,  # noqa: F401
    summary,  # noqa: F401
    username,  # noqa: F401
)
from .common import PurchaseState, _build_plan_keyboard, _normal_plan_keyboard, router
from .edit_flow import go_back_from_confirmation
from .plan_exits import back_from_auto_renew_choice, back_from_renewal_template, cancel_from_plan
from .receipt import cancel_purchase_receipt
from .username import generate_unique_username

__all__ = (
    "PLANS",
    "PurchaseState",
    "_build_plan_keyboard",
    "_normal_plan_keyboard",
    "back_from_auto_renew_choice",
    "back_from_renewal_template",
    "cancel_from_plan",
    "cancel_purchase_receipt",
    "generate_unique_username",
    "go_back_from_confirmation",
    "router",
)
