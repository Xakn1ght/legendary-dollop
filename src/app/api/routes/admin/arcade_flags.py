"""Admin cheat log: arcade submits rejected by the anti-cheat gate.

GET /api/admin/arcade/flags?limit=100
Auth: handled by the global /api/admin middleware (admin session token).
"""

from aiohttp import web
from sqlalchemy import desc, func
from sqlalchemy.future import select

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
