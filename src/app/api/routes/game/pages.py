from .common import *  # noqa: F403

# NOTE: names starting with "_" are NOT pulled in by `from .common import *`
# (Python excludes underscore-prefixed names from wildcard imports), so import
# the auth helpers explicitly or every handler here 500s with a NameError.
from app.api.deps import _extract_user_id_from_init, _verify_webapp_auth  # noqa: E402


async def handle_index(request: web.Request):
    """
    Arcade lobby entrypoint.
    Only accessible via Telegram WebApp (verified auth or init_data).
    """
    user_chat_id, _ = _verify_webapp_auth(request)
    
    # Fallback: allow direct init_data verification from query (e.g. web.telegram.org)
    if not user_chat_id:
        init_data = request.query.get("init_data", "")
        if init_data and verify_init_data(init_data, BOT_TOKEN):
            user_chat_id = _extract_user_id_from_init(init_data)
    
    if not user_chat_id:
        # Show a friendly page telling user to open from Telegram
        return web.FileResponse(path=webapp_path("arcade", "blocked.html"))
    
    return web.FileResponse(path=webapp_path("arcade", "index.html"))


async def handle_arcade_game_index(request: web.Request):
    """
    Game wrapper entrypoint (astrobugz).
    Also locked to Telegram WebApp auth.
    """
    user_chat_id, _ = _verify_webapp_auth(request)
    
    if not user_chat_id:
        init_data = request.query.get("init_data", "")
        if init_data and verify_init_data(init_data, BOT_TOKEN):
            user_chat_id = _extract_user_id_from_init(init_data)
    
    if not user_chat_id:
        return web.FileResponse(path=webapp_path("arcade", "blocked.html"))

    return web.FileResponse(path=webapp_path("arcade", "astrobugz", "index.html"))


async def handle_arcade_game2_index(request: web.Request):
    """
    New (config-driven) AstroBugz game wrapper entrypoint (astrobugz2).
    Gated identically to the original astrobugz game.
    """
    user_chat_id, _ = _verify_webapp_auth(request)

    if not user_chat_id:
        init_data = request.query.get("init_data", "")
        if init_data and verify_init_data(init_data, BOT_TOKEN):
            user_chat_id = _extract_user_id_from_init(init_data)

    if not user_chat_id:
        return web.FileResponse(path=webapp_path("arcade", "blocked.html"))

    return web.FileResponse(path=webapp_path("arcade", "astrobugz2", "index.html"))

