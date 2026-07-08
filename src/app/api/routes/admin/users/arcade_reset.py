from app.utils.tehran_time import tehran_today

from ..common import *  # noqa: F403


async def handle_admin_reset_arcade(request: web.Request):
    """Reset the user's TODAY ranked run so they can play again.

    Same semantics as the paid retry (repos/reward/_game.py::arcade_retry),
    minus the coin charge: zero best_score + reopen the daily gate. The row
    is kept (analytics) — zeroing also removes today's points from the
    monthly race until they replay, exactly like the retry.

    ARCADE DAYS ROLL AT IRAN MIDNIGHT — this used server-UTC date.today()
    until 2026-07-08, which made the reset a silent no-op every night
    between 00:00 and 03:30 Tehran (the two clocks disagree on "today").
    """
    try:
        user_id = int(request.match_info['user_id'])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_user_id"}, status=400)

    from app.database.models import DailyGamePlay

    async with AsyncSessionLocal() as session:
        today = tehran_today()
        play = (await session.execute(
            select(DailyGamePlay).filter(
                DailyGamePlay.user_id == user_id,
                DailyGamePlay.play_date == today,
            )
        )).scalars().first()

        if not play or (not play.rewarded and not play.best_score):
            # nothing to clear — the gate is already open
            return web.json_response({"ok": True, "reset": False})

        old_best = play.best_score
        play.best_score = 0
        play.rewarded = False
        play.duration_seconds = 0
        await session.commit()

        from app.services.audit import record_audit

        await record_audit(
            request, "arcade.reset_daily", target_type="user", target_id=user_id,
            summary=f"today's run cleared (best was {old_best:,})",
        )
        return web.json_response({"ok": True, "reset": True, "cleared_best": old_best})
