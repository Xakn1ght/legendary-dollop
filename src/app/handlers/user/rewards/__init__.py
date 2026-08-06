"""Initializes the rewards package, aggregates sub-routers, and re-exports symbols."""
from aiogram import Router

from .achievements import router as achievements_router
from .leaderboard import router as leaderboard_router
from .loyalty_shop import router as loyalty_shop_router

# 1. Import sub-routers explicitly
from .menu import router as menu_router
from .profile import router as profile_router
from .redemption import router as redemption_router
from .wallet import router as wallet_router

# 2. Aggregate all sub-routers into a single main router for the package.
# NOTE: analytics_router (star_analytics/star_distribution/… callbacks) is
# deliberately NOT included: it was admin-only surface living inside the USER
# bot (no user-facing button ever emitted those callbacks). Admin analytics
# belong to the admin panel/bot only.
router = Router()
router.include_routers(
    menu_router,
    profile_router,
    wallet_router,
    redemption_router,
    achievements_router,
    leaderboard_router,
    loyalty_shop_router,
)

# 3. Explicitly re-export symbols needed for backward-compatibility.
# This avoids namespace collisions from the previous wildcard import approach.
from .menu import show_enhanced_rewards_menu

# __all__ controls what `from app.handlers.user.rewards import *` imports.
__all__ = [
    "router",
    "show_enhanced_rewards_menu",
] 