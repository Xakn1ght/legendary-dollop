from ..common import *  # noqa: F403


async def handle_admin_reset_arcade(request: web.Request):
    try:
        user_id = int(request.match_info['user_id'])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_user_id"}, status=400)
    try:
        async with AsyncSessionLocal() as session:
            # Logic to reset arcade stats for user
            # e.g. clear daily play limits
            from datetime import date
            today = date.today()
            from app.database.models import DailyGamePlay
            stmt = delete(DailyGamePlay).where(
                and_(DailyGamePlay.user_id == user_id, DailyGamePlay.play_date == today)
            )
            await session.execute(stmt)
            await session.commit()
            return web.json_response({"ok": True})
    except Exception as e:
        return web.json_response({"ok": False, "error": "server_error"}, status=500)
