"""Monthly arcade race: prize ladder, live top-10, your rank, hall of fame.

GET /api/arcade/race
    Public: prize ladder, current month's top 10, days left.
    With auth: adds `me` = { rank, score, gap_to_next } for the caller.

GET /api/arcade/hall-of-fame
    Last month's prize winners (read from the reward_history rows the payout
    job writes, so it always matches what was actually awarded).
"""

import calendar
import re

from aiohttp import web
from sqlalchemy import select

from app.api.deps import _extract_user_id_from_init, _verify_webapp_auth
from app.core.settings import ARCADE_MONTHLY_PRIZES, BOT_TOKEN
from app.database import crud
from app.database.models import AsyncSessionLocal, RewardHistory, User
from app.jobs.arcade_prizes import GUARD_SOURCE, _previous_month_bounds
from app.utils.tehran_time import tehran_today
from app.utils.webapp_verify import verify_init_data

# "2026-07 rank 3 (score 4210) → Arcade 3rd Place — 10GB Free"
_HOF_NOTE = re.compile(r"^(\d{4}-\d{2}) rank (\d+) \(score (\d+)\) → (.+)$")


def _auth_chat_id(request: web.Request):
    user_chat_id, _ = _verify_webapp_auth(request)
    if not user_chat_id:
        init_data = request.query.get("init_data", "")
        if init_data and verify_init_data(init_data, BOT_TOKEN):
            user_chat_id = _extract_user_id_from_init(init_data)
    return user_chat_id


def _prize_ladder():
    return [
        {"min_rank": p["min_rank"], "max_rank": p["max_rank"],
         "coupon_type": p["coupon_type"], "payload": p["payload"], "name": p["name"]}
        for p in ARCADE_MONTHLY_PRIZES
    ]


async def handle_arcade_race(request: web.Request):
    today = tehran_today()  # race month flips at IRAN midnight
    month_start = today.replace(day=1)
    month_end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    days_left = (month_end - today).days

    user_chat_id = _auth_chat_id(request)

    async with AsyncSessionLocal() as session:
        ranking = await crud.get_monthly_arcade_ranking(session, month_start, month_end)

        top = [
            {"rank": i + 1, "name": row.display_name or "Player", "score": int(row.top_score)}
            for i, row in enumerate(ranking[:10])
        ]

        me = None
        if user_chat_id:
            user = await crud.get_user(session, user_chat_id)
            if user:
                for i, row in enumerate(ranking):
                    if row.user_id == user.id:
                        gap = (int(ranking[i - 1].top_score) - int(row.top_score)) if i > 0 else 0
                        me = {"rank": i + 1, "score": int(row.top_score), "gap_to_next": gap}
                        break

    return web.json_response({
        "ok": True,
        "month": f"{today.year:04d}-{today.month:02d}",
        "days_left": days_left,
        "prizes": _prize_ladder(),
        "top": top,
        "me": me,
    })


async def handle_arcade_hall_of_fame(request: web.Request):
    today = tehran_today()
    _, _, prev_key = _previous_month_bounds(today)

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(RewardHistory, User)
            .join(User, User.id == RewardHistory.user_id)
            .filter(
                RewardHistory.source == GUARD_SOURCE,
                RewardHistory.notes.like(f"{prev_key} rank %"),
            )
            .order_by(RewardHistory.reward_value.asc())
        )).all()

        winners = []
        for hist, user in rows:
            m = _HOF_NOTE.match(hist.notes or "")
            if not m:
                continue
            winners.append({
                "rank": int(m.group(2)),
                "score": int(m.group(3)),
                "prize": m.group(4),
                "name": user.custom_username or user.username or user.full_name or "Player",
            })

    return web.json_response({"ok": True, "month": prev_key, "winners": winners})
