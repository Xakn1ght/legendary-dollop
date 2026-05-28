"""Telegram admin handlers for on-bot settings (plans, charges, renewal, jobs, support)."""

from aiogram import Router

from app.shared.plan_ordering import get_ordered_charge_plans, get_ordered_plans

from . import charges, menu, plans, renewal, scheduling

router = Router()
router.include_router(menu.router)
router.include_router(plans.router)
router.include_router(charges.router)
router.include_router(renewal.router)
router.include_router(scheduling.router)

__all__ = ["router", "get_ordered_plans", "get_ordered_charge_plans"]
