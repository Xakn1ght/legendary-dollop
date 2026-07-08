"""Admin arcade tools: cheat log + per-user wallet adjustments.

GET  /api/admin/arcade/flags?limit=100        rejected-submit cheat log
GET  /api/admin/users/{user_id}/arcade        wallet view (coins/difficulty/…)
POST /api/admin/users/{user_id}/arcade        {"coins_delta": int, "difficulty": str}
Auth: handled by the global /api/admin middleware (admin session token).

Coin grants stay inside the sealed arcade economy — they buy skins/powers/
retries and nothing else, so this is QA/goodwill sugar, not money.
"""

from aiohttp import web
from sqlalchemy import desc, func
from sqlalchemy.future import select

from app.core.settings import ARCADE_DIFFICULTIES
from app.database import crud
from app.database.models import ArcadeFlag, AsyncSessionLocal, User


async def handle_admin_arcade_flags(request: web.Request):
    try:
        limit = min(500, max(1, int(request.query.get("limit", "100"))))
    except ValueError:
        limit = 100

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(ArcadeFlag, User)
            .join(User, User.id == ArcadeFlag.user_id)
            .order_by(desc(ArcadeFlag.created_at))
            .limit(limit)
        )).all()

        # repeat offenders summary
        counts = (await session.execute(
            select(ArcadeFlag.user_id, func.count(ArcadeFlag.id))
            .group_by(ArcadeFlag.user_id)
        )).all()
        count_by_user = {uid: n for uid, n in counts}

        flags = []
        for flag, user in rows:
            flags.append({
                "id": flag.id,
                "user_id": flag.user_id,
                "chat_id": user.chat_id,
                "name": user.custom_username or user.username or user.full_name or str(user.chat_id),
                "score": flag.score,
                "claimed_duration": flag.claimed_duration,
                "server_elapsed": flag.server_elapsed,
                "reason": flag.reason,
                "total_flags": count_by_user.get(flag.user_id, 1),
                "created_at": flag.created_at.isoformat() if flag.created_at else None,
            })

    return web.json_response({"ok": True, "flags": flags})


async def handle_admin_arcade_user_get(request: web.Request):
    """Current wallet state for the Users-page arcade panel."""
    try:
        user_id = int(request.match_info["user_id"])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_user_id"}, status=400)

    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        if not user:
            return web.json_response({"ok": False, "error": "not_found"}, status=404)
        wallet = await crud.get_or_create_arcade_wallet(session, user_id)
        return web.json_response({
            "ok": True,
            "wallet": crud.arcade_wallet_public(wallet),
            "difficulties": list(ARCADE_DIFFICULTIES),
        })


async def handle_admin_arcade_user_adjust(request: web.Request):
    """Grant/remove coins and/or set per-user difficulty. Audited."""
    try:
        user_id = int(request.match_info["user_id"])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_user_id"}, status=400)
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

    coins_delta = data.get("coins_delta")
    difficulty = data.get("difficulty")
    if coins_delta is not None:
        try:
            coins_delta = max(-10_000, min(10_000, int(coins_delta)))
        except (TypeError, ValueError):
            return web.json_response({"ok": False, "error": "invalid_coins_delta"}, status=400)
    if difficulty is not None and difficulty not in ARCADE_DIFFICULTIES:
        return web.json_response({"ok": False, "error": "unknown_difficulty"}, status=400)
    if not coins_delta and difficulty is None:
        return web.json_response({"ok": False, "error": "nothing_to_do"}, status=400)

    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        if not user:
            return web.json_response({"ok": False, "error": "not_found"}, status=404)
        old_wallet = await crud.get_or_create_arcade_wallet(session, user_id)
        old_coins = old_wallet.coins or 0
        old_diff = old_wallet.difficulty or "normal"

        error, wallet = await crud.admin_arcade_adjust(
            session, user_id, coins_delta=coins_delta, difficulty=difficulty,
        )
        if error:
            return web.json_response({"ok": False, "error": error}, status=400)

        from app.services.audit import record_audit

        bits = []
        if coins_delta:
            bits.append(f"coins {old_coins}→{wallet.coins} ({coins_delta:+d})")
        if difficulty is not None and difficulty != old_diff:
            bits.append(f"difficulty {old_diff}→{difficulty}")
        if bits:
            await record_audit(
                request, "arcade.adjust", target_type="user", target_id=user_id,
                summary=", ".join(bits),
            )
        return web.json_response({"ok": True, "wallet": crud.arcade_wallet_public(wallet)})
