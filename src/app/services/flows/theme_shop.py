"""Purchasable dashboard themes (2026-07-15, Pasha's bubblegum mock).

Unlike the tier worlds (earned: VIP membership / season stars), shop themes
are bought once with WALLET CREDIT and land in the same permanent storage the
season cosmetics use: ``dashboard_prefs.unlocked_themes`` — so the profile
picker, prefs sync and the accent allow-lists need no new plumbing.

Money rules (thin but real money — everything money stays in the flows layer):
- price is charged from ``User.credit`` atomically via ``crud.deduct_credit``
  (balance-checked; never negative);
- buying an already-owned theme is a no-op success (idempotent — double taps
  must not double-charge);
- every purchase writes a RewardHistory row (audit trail).
"""
from __future__ import annotations

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.services.flows.errors import FlowError

logger = logging.getLogger(__name__)

# key -> {price (toman, wallet credit)}. Extend here for future shop themes.
THEME_SHOP: dict[str, dict] = {
    "bubblegum": {"price": 40_000},
}


def theme_shop_items(prefs_json: str | None) -> list[dict]:
    """Shop items annotated with ownership for one user's prefs JSON."""
    try:
        owned = set((json.loads(prefs_json or "{}").get("unlocked_themes")) or [])
    except Exception:
        owned = set()
    return [
        {"key": key, "price": int(info["price"]), "owned": key in owned}
        for key, info in THEME_SHOP.items()
    ]


async def buy_theme(session: AsyncSession, user, theme_key: str) -> dict:
    """Charge the wallet and permanently unlock ``theme_key`` for ``user``.

    Returns {theme, price, credit, unlocked_themes, already_owned}.
    Raises FlowError codes: unknown_theme, insufficient_credit.
    """
    info = THEME_SHOP.get(theme_key)
    if not info:
        raise FlowError("unknown_theme", "This theme is not for sale")
    price = int(info["price"])

    try:
        prefs = json.loads(user.dashboard_prefs or "{}")
    except Exception:
        prefs = {}
    themes = set(prefs.get("unlocked_themes") or [])

    if theme_key in themes:
        return {
            "theme": theme_key, "price": price, "credit": int(user.credit or 0),
            "unlocked_themes": sorted(themes), "already_owned": True,
        }

    if int(user.credit or 0) < price:
        err = FlowError("insufficient_credit", "Not enough wallet credit")
        err.price = price
        err.credit = int(user.credit or 0)
        raise err

    charged = await crud.deduct_credit(session, user.id, price)
    if charged is None:  # balance changed under us — same error, fresh numbers
        err = FlowError("insufficient_credit", "Not enough wallet credit")
        err.price = price
        err.credit = int(user.credit or 0)
        raise err

    themes.add(theme_key)
    prefs["unlocked_themes"] = sorted(themes)
    user.dashboard_prefs = json.dumps(prefs)
    await session.commit()
    await session.refresh(user)

    try:
        await crud.add_reward_history(
            session, user.id, "theme", price, "theme_shop", notes=theme_key,
        )
    except Exception:
        logger.exception("theme_shop: reward history write failed (purchase itself is fine)")

    logger.info(f"[THEME-SHOP] user {user.id} bought '{theme_key}' for {price:,} toman credit")
    return {
        "theme": theme_key, "price": price, "credit": int(charged.credit or 0),
        "unlocked_themes": sorted(themes), "already_owned": False,
    }
