"""Register game and arcade HTTP routes."""

from pathlib import Path

from aiohttp import web

from app.core.settings import GAME_SUBMIT_API_PATH, GAME_WEBAPP_BASE_PATH

from .handlers import (
    handle_arcade_game2_index,
    handle_arcade_game_index,
    handle_arcade_status,
    handle_arcade_submit,
    handle_index,
    handle_leaderboard,
    handle_save_display_name,
    handle_submit,
    handle_toggle_leaderboard,
)


def register_game_routes(app: web.Application, wd: Path) -> None:
    app.router.add_get(GAME_WEBAPP_BASE_PATH, handle_index)
    app.router.add_get(GAME_WEBAPP_BASE_PATH + "/astrobugz/index.html", handle_arcade_game_index)
    app.router.add_get(GAME_WEBAPP_BASE_PATH + "/astrobugz2/index.html", handle_arcade_game2_index)
    app.router.add_static(GAME_WEBAPP_BASE_PATH + "/", path=str(wd / "arcade"), name="arcade_static")
    app.router.add_post(GAME_SUBMIT_API_PATH, handle_submit)
    app.router.add_post("/api/arcade/submit", handle_arcade_submit)
    app.router.add_get("/api/arcade/leaderboard", handle_leaderboard)
    app.router.add_get("/api/arcade/status", handle_arcade_status)
    app.router.add_post("/api/arcade/toggle-leaderboard", handle_toggle_leaderboard)
    app.router.add_post("/api/arcade/save-name", handle_save_display_name)
