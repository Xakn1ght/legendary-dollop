from .common import *  # noqa: F403


async def handle_submit(request: web.Request):
    """Legacy game submit handler - redirects to handle_arcade_submit logic"""
    from urllib.parse import parse_qsl
    
    try:
        data = await request.json()
    except Exception:
        try:
            body = await request.text()
            data = json.loads(body or "{}")
        except Exception:
            return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

    init_data = data.get("init_data", "")
    score = int(data.get("score", 0))
    duration = int(data.get("duration", 0))
    practice = bool(data.get("practice", False))
    display_name = (data.get("display_name") or "").strip()[:40]

    if not verify_init_data(init_data, BOT_TOKEN):
        return web.json_response({"ok": False, "error": "bad_signature"}, status=403)

    # Extract user_id from init_data
    payload = dict(parse_qsl(init_data, keep_blank_values=True))
    from_user = json.loads(payload.get("user", "{}")) if payload.get("user") else {}
    user_id = int(from_user.get("id", 0))
    if not user_id:
        return web.json_response({"ok": False, "error": "no_user"}, status=400)

    async with AsyncSessionLocal() as session:
        # Get user by chat_id (user_id from Telegram is chat_id)
        user = await crud.get_user(session, user_id)
        if not user:
            return web.json_response({"ok": False, "error": "not_registered"}, status=403)
        
        # Update preferred display name
        if display_name:
            user.custom_username = display_name
        
        # Use the repository method for consistent reward logic
        result = await crud.submit_daily_game_score(session, user.id, score, duration, is_practice=practice)

    return web.json_response({
        "ok": True,
        "awarded": result["awarded"],
        "best_score": result["best_score"],
        "rewards": result["rewards"],
        "already_rewarded": result["already_rewarded"],
        "star_pieces_total": result.get("star_pieces_total", 0),
        "monthly_stars": result.get("monthly_stars", 0)
    })

