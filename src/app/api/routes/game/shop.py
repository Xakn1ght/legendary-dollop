"""Arcade coin shop (2026-07-07).

GET  /api/arcade/shop         catalog (public) + wallet/inventory (with auth)
POST /api/arcade/shop/buy     {"item": "skin:crimson" | "power:shield_start" | "extra_life"}
POST /api/arcade/shop/equip   {"skin": "crimson"}
POST /api/arcade/retry        spend coins → reset TODAY's ranked run and play again

Economy rules (keep these true):
- Coins are minted ONLY by the validated daily run (capped in the submit
  handler) — nothing here creates coins.
- Nothing in the shop converts coins to credit/stars/GB/days. Items are
  in-game only (skins, run modifiers, a retry of the daily run).
- All spending goes through the repo (repos/reward/_game.py), which locks
  the wallet row so a double-tap can't double-spend or double-grant.
- Retry: the reset zeroes today's best_score first — if the new run scores
  lower, the monthly total drops. That's the player's gamble; the client
  warns before buying.
"""
from aiohttp import web

from app.api.deps import _extract_user_id_from_init, _verify_webapp_auth
from app.core.settings import ARCADE_SHOP, BOT_TOKEN
from app.database import crud
from app.database.models import AsyncSessionLocal
from app.utils.webapp_verify import verify_init_data

_ERROR_STATUS = {
    "unknown_item": 400,
    "unknown_skin": 400,
    "not_enough_coins": 402,
    "not_owned": 403,
    "already_owned": 409,
    "nothing_to_retry": 409,
}


def _auth_chat_id(request: web.Request):
    user_chat_id, _ = _verify_webapp_auth(request)
    if not user_chat_id:
        init_data = request.query.get("init_data", "")
        if init_data and verify_init_data(init_data, BOT_TOKEN):
            user_chat_id = _extract_user_id_from_init(init_data)
    return user_chat_id


def _catalog() -> dict:
    return {
        "skins": [
            {"key": k, "price": v["price"], "color": v["color"]}
            for k, v in ARCADE_SHOP["skins"].items()
        ],
        "powers": [
            {"key": k, "price": v["price"]}
            for k, v in ARCADE_SHOP["powers"].items()
        ],
        "extra_life": {"price": ARCADE_SHOP["extra_life"]["price"]},
        "retry": {"price": ARCADE_SHOP["retry"]["price"]},
    }


def build_loadout(wallet_pub: dict) -> dict:
    """What the game applies at run start — derived purely from the wallet."""
    skin_key = wallet_pub["equipped_skin"]
    skin = ARCADE_SHOP["skins"].get(skin_key) or ARCADE_SHOP["skins"]["default"]
    return {
        "skin": skin_key,
        "skin_color": skin["color"],
        "shield_start": "shield_start" in wallet_pub["owned_powers"],
        "spread_start": "spread_start" in wallet_pub["owned_powers"],
        "extra_lives": wallet_pub["extra_lives"],
    }


async def _resolve_user(request: web.Request, session):
    user_chat_id = _auth_chat_id(request)
    if not user_chat_id:
        return None, web.json_response({"ok": False, "error": "unauthorized"}, status=403)
    user = await crud.get_user(session, user_chat_id)
    if not user:
        return None, web.json_response({"ok": False, "error": "not_registered"}, status=403)
    return user, None


async def handle_arcade_shop(request: web.Request):
    """Catalog is public; wallet/inventory included when authenticated."""
    user_chat_id = _auth_chat_id(request)
    out = {"ok": True, "catalog": _catalog(), "wallet": None}
    if user_chat_id:
        async with AsyncSessionLocal() as session:
            user = await crud.get_user(session, user_chat_id)
            if user:
                wallet = await crud.get_or_create_arcade_wallet(session, user.id)
                out["wallet"] = crud.arcade_wallet_public(wallet)
    return web.json_response(out)


async def handle_arcade_buy(request: web.Request):
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)
    item = str(data.get("item") or "")[:48]

    async with AsyncSessionLocal() as session:
        user, err = await _resolve_user(request, session)
        if err:
            return err
        error, wallet = await crud.arcade_buy(session, user.id, item)
        if error:
            body = {"ok": False, "error": error}
            if wallet is not None:
                body["coins"] = wallet.coins or 0
            return web.json_response(body, status=_ERROR_STATUS.get(error, 400))
        return web.json_response({"ok": True, "wallet": crud.arcade_wallet_public(wallet)})


async def handle_arcade_equip(request: web.Request):
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)
    skin = str(data.get("skin") or "")[:24]

    async with AsyncSessionLocal() as session:
        user, err = await _resolve_user(request, session)
        if err:
            return err
        error, wallet = await crud.arcade_equip(session, user.id, skin)
        if error:
            return web.json_response({"ok": False, "error": error},
                                     status=_ERROR_STATUS.get(error, 400))
        return web.json_response({"ok": True, "wallet": crud.arcade_wallet_public(wallet)})


async def handle_arcade_retry(request: web.Request):
    """Spend coins to reset TODAY's ranked run. XP already granted stays —
    it's status-only and the coin price bounds how often this can happen."""
    async with AsyncSessionLocal() as session:
        user, err = await _resolve_user(request, session)
        if err:
            return err
        error, coins = await crud.arcade_retry(session, user.id)
        if error:
            return web.json_response({"ok": False, "error": error, "coins": coins},
                                     status=_ERROR_STATUS.get(error, 400))
        return web.json_response({"ok": True, "coins": coins,
                                  "message": "Daily run reset — fly again!"})
