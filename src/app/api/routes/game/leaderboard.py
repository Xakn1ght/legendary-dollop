from .common import *  # noqa: F403


async def handle_leaderboard(request: web.Request):
    # Validate query parameters
    params_data = {
        'period': request.query.get("period", "daily").lower(),
        'limit': request.query.get("limit", "10")
    }
    try:
        params_data['limit'] = int(params_data['limit'])
    except ValueError:
        params_data['limit'] = 10
    
    validated, error = validate_request(LeaderboardRequest, params_data)
    if error:
        return web.json_response(error, status=400)
    
    async with AsyncSessionLocal() as session:
        lb = await crud.get_game_leaderboard(session, period=validated.period, limit=validated.limit)
    return web.json_response({"ok": True, "period": validated.period, "leaderboard": lb})

