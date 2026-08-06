"""Game and arcade HTTP handlers (split from former routes/game.py)."""

from app.api.routes.game.arcade_submit import handle_arcade_submit
from app.api.routes.game.leaderboard import handle_leaderboard
from app.api.routes.game.legacy_submit import handle_submit
from app.api.routes.game.pages import (
    handle_arcade_game2_index,
    handle_arcade_game_index,
    handle_index,
)
from app.api.routes.game.profile import (
    handle_arcade_status,
    handle_save_display_name,
    handle_toggle_leaderboard,
)
from app.api.routes.game.race import handle_arcade_hall_of_fame, handle_arcade_race
from app.api.routes.game.round_lifecycle import handle_arcade_checkpoint
from app.api.routes.game.round_start import handle_arcade_round_start
from app.api.routes.game.shop import (
    handle_arcade_buy,
    handle_arcade_equip,
    handle_arcade_retry,
    handle_arcade_shop,
)

__all__ = [
    "handle_arcade_buy",
    "handle_arcade_checkpoint",
    "handle_arcade_equip",
    "handle_arcade_game2_index",
    "handle_arcade_game_index",
    "handle_arcade_hall_of_fame",
    "handle_arcade_race",
    "handle_arcade_retry",
    "handle_arcade_round_start",
    "handle_arcade_shop",
    "handle_arcade_status",
    "handle_arcade_submit",
    "handle_index",
    "handle_leaderboard",
    "handle_save_display_name",
    "handle_submit",
    "handle_toggle_leaderboard",
]
