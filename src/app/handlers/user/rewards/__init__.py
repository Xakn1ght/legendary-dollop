"""Initializes the rewards package, aggregates sub-routers, and re-exports symbols."""
from aiogram import Router

from .achievements import router as achievements_router
from .analytics import router as analytics_router
from .leaderboard import router as leaderboard_router
from .loyalty_shop import router as loyalty_shop_router

# 1. Import sub-routers explicitly
from .menu import router as menu_router
from .profile import router as profile_router

# Gifts disabled due to phishing concerns
from .redemption import router as redemption_router
from .wallet import router as wallet_router

# 2. Aggregate all sub-routers into a single main router for the package.
router = Router()
router.include_routers(
    menu_router,
    profile_router,
    wallet_router,
    redemption_router,
    achievements_router,
    leaderboard_router,
    analytics_router,
    loyalty_shop_router,
)

# 3. Explicitly re-export symbols needed for backward-compatibility.
# This avoids namespace collisions from the previous wildcard import approach.
# from .gifts import GiftStates
from .menu import show_enhanced_rewards_menu

# __all__ controls what `from app.handlers.user.rewards import *` imports.
__all__ = [
    "router",
    "show_enhanced_rewards_menu",
] 