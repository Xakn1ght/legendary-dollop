"""Public webapp URLs and arcade reward tables."""

import os

# -----------------------------
# Game Settings
# -----------------------------
GAME_WEBAPP_HOST = os.environ.get("GAME_WEBAPP_HOST", "0.0.0.0")
try:
    GAME_WEBAPP_PORT = int(os.environ.get("GAME_WEBAPP_PORT", "8080"))
except Exception:
    GAME_WEBAPP_PORT = 8080
GAME_WEBAPP_BASE_PATH = "/webapp/arcade"
GAME_SUBMIT_API_PATH = "/api/game/submit"
GAME_PUBLIC_BASE_URL = os.environ.get("GAME_PUBLIC_BASE_URL", "https://game1.astrobytech.com")

DASHBOARD_WEBAPP_BASE_PATH = "/webapp/dashboard"
DASHBOARD_API_BASE_PATH = "/api/dashboard"
DASHBOARD_PUBLIC_BASE_URL = os.environ.get("DASHBOARD_PUBLIC_BASE_URL", "https://game1.astrobytech.com")

# Reward Settings (Percentages) - Default values for referral rewards
REFERRAL_REWARDS = {
    "traffic_percent": 5,
    "days_percent": 1,
    "credit_percent": 10,
}

# ===========================================
# ARCADE GAME REWARD SETTINGS
# ===========================================
# Balanced reward system with anti-farming measures
GAME_REWARDS = {
    # Score thresholds and rewards (credits, XP, star pieces)
    "thresholds": [
        # Star pieces are intentionally conservative to avoid farming stars via a free game.
        # Ranges (approx):
        # - <5000 => 0 pieces
        # - 5000-7999 => 1 piece
        # - 8000-10999 => 2 pieces
        # - 11000-13999 => 3 pieces
        # - 14000-16999 => 4 pieces
        # - >=17000 => 5 pieces (very hard)
        {"min_score": 17000, "credits": 4000, "xp": 200, "star_pieces": 5},
        {"min_score": 15000, "credits": 4000, "xp": 200, "star_pieces": 4},
        {"min_score": 13000, "credits": 3000, "xp": 150, "star_pieces": 3},
        {"min_score": 10000, "credits": 2000, "xp": 120, "star_pieces": 2},
        {"min_score": 7000, "credits": 1500, "xp": 100, "star_pieces": 1},
        {"min_score": 5000, "credits": 1000, "xp": 80, "star_pieces": 1},
        {"min_score": 3000, "credits": 500, "xp": 50, "star_pieces": 0},
        {"min_score": 1000, "credits": 200, "xp": 30, "star_pieces": 0},
        {"min_score": 0, "credits": 100, "xp": 10, "star_pieces": 0},
    ],
    # Star pieces system
    "pieces_per_star": 10,  # 10 pieces = 1 full star
    "monthly_star_cap": 6,  # Max 6 stars from arcade per month
    # Daily limits
    "daily_rewarded_games": 1,  # Only 1 rewarded game per day
    # Streak bonuses
    "streak_bonus_percent_per_day": 5,  # +5% per consecutive day
    "streak_bonus_max_percent": 25,  # Max +25% bonus
    # Session validation
    "min_session_seconds": 20,  # Minimum game duration to get rewards
    # Loyalty points from arcade
    "loyalty_points_per_1000_credits": 0,  # Disabled: no loyalty points from credits
}
