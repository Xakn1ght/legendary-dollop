from .common import *  # noqa: F403


async def handle_arcade_status(request: web.Request):
    """Return user's arcade game status - can they play today, best score, etc."""
    from datetime import date

    from app.core.settings import GAME_REWARDS
    
    # Verify authentication
    user_chat_id, _ = _verify_webapp_auth(request)
    if not user_chat_id:
        # Also try init_data from query
        init_data = request.query.get("init_data", "")
        if init_data and verify_init_data(init_data, BOT_TOKEN):
            user_chat_id = _extract_user_id_from_init(init_data)
    
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)
    
    async with AsyncSessionLocal() as session:
        user = await crud.get_user(session, user_chat_id)
        if not user:
            return web.json_response({"ok": False, "error": "not_registered"}, status=403)
        
        # Check daily play status
        today = date.today()
        existing_play = await crud.check_daily_game_play(session, user.id, today)
        
        can_play_for_rewards = not (existing_play and existing_play.rewarded)
        best_score_today = existing_play.best_score if existing_play else 0
        
        # Get monthly star cap info
        monthly_cap = GAME_REWARDS.get("monthly_star_cap", 6)
        stars_this_month = user.arcade_stars_this_month or 0
        
        return web.json_response({
            "ok": True,
            "can_play_for_rewards": can_play_for_rewards,
            "played_today": not can_play_for_rewards,  # Frontend expects this name
            "already_played_today": not can_play_for_rewards,
            "best_score_today": best_score_today,
            "star_pieces": user.star_pieces or 0,
            "show_on_leaderboard": user.show_on_leaderboard if hasattr(user, 'show_on_leaderboard') else True,
            "display_name": user.custom_username or user.username or user.full_name or "",
            "monthly_stars": {
                "earned": stars_this_month,
                "cap": monthly_cap,
                "remaining": max(0, monthly_cap - stars_this_month)
            },
            "streak": user.login_streak or 0,
            "user": {
                "credits": user.credit or 0,
                "stars": user.stars or 0,
                "level": user.level or 1,
                "xp": user.experience_points or 0
            }
        })


async def handle_toggle_leaderboard(request: web.Request):
    """Toggle user's leaderboard visibility preference"""
    # Verify authentication
    user_chat_id, _ = _verify_webapp_auth(request)
    if not user_chat_id:
        init_data = request.query.get("init_data", "")
        if init_data and verify_init_data(init_data, BOT_TOKEN):
            user_chat_id = _extract_user_id_from_init(init_data)
    
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)
    
    try:
        data = await request.json()
    except Exception:
        data = {}
    
    # Get the new value (optional - if not provided, toggle)
    new_value = data.get("show_on_leaderboard")
    
    async with AsyncSessionLocal() as session:
        user = await crud.get_user(session, user_chat_id)
        if not user:
            return web.json_response({"ok": False, "error": "not_registered"}, status=403)
        
        # Toggle or set the value
        if new_value is None:
            # Toggle the current value
            current = getattr(user, 'show_on_leaderboard', True)
            user.show_on_leaderboard = not current
        else:
            user.show_on_leaderboard = bool(new_value)
        
        await session.commit()
        
        return web.json_response({
            "ok": True,
            "show_on_leaderboard": user.show_on_leaderboard
        })


async def handle_save_display_name(request: web.Request):
    """Save user's display name for leaderboard (synced across all devices)"""
    # Verify authentication
    user_chat_id, _ = _verify_webapp_auth(request)
    if not user_chat_id:
        init_data = request.query.get("init_data", "")
        if init_data and verify_init_data(init_data, BOT_TOKEN):
            user_chat_id = _extract_user_id_from_init(init_data)
    
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)
    
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)
    
    display_name = (data.get("display_name") or "").strip()[:40]
    
    if not display_name:
        return web.json_response({"ok": False, "error": "name_required"}, status=400)
    
    async with AsyncSessionLocal() as session:
        user = await crud.get_user(session, user_chat_id)
        if not user:
            return web.json_response({"ok": False, "error": "not_registered"}, status=403)
        
        user.custom_username = display_name
        await session.commit()
        
        return web.json_response({
            "ok": True,
            "display_name": user.custom_username
        })

