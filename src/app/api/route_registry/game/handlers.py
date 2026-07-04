"""Import game route callables for registration."""

from app.api.routes.game import (
    handle_arcade_game2_index,
    handle_arcade_game_index,
    handle_arcade_hall_of_fame,
    handle_arcade_race,
    handle_arcade_round_start,
    handle_arcade_status,
    handle_arcade_submit,
    handle_index,
    handle_leaderboard,
    handle_save_display_name,
    handle_submit,
    handle_toggle_leaderboard,
)

__all__ = [
    "handle_arcade_game2_index",
    "handle_arcade_game_index",
    "handle_arcade_hall_of_fame",
    "handle_arcade_race",
    "handle_arcade_round_start",
    "handle_arcade_status",
    "handle_arcade_submit",
    "handle_index",
    "handle_leaderboard",
    "handle_save_display_name",
    "handle_submit",
    "handle_toggle_leaderboard",
]
