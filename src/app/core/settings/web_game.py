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
    # Score thresholds and rewards.
    # XP-ONLY as of 2026-06-02 (final reward map "iron rule"): the arcade gives XP
    # (→ levels → status) and leaderboard glory, but NO credit and NO stars. Credit
    # of 100–4,000/play (~150k/mo) was a farming hole; season stars are referral-only
    # now. Money is minted only by referrals + cashback. credits/star_pieces kept as
    # 0 keys so the score-tier shape stays editable if we ever add capped payouts.
    "thresholds": [
        {"min_score": 17000, "credits": 0, "xp": 200, "star_pieces": 0},
        {"min_score": 15000, "credits": 0, "xp": 200, "star_pieces": 0},
        {"min_score": 13000, "credits": 0, "xp": 150, "star_pieces": 0},
        {"min_score": 10000, "credits": 0, "xp": 120, "star_pieces": 0},
        {"min_score": 7000, "credits": 0, "xp": 100, "star_pieces": 0},
        {"min_score": 5000, "credits": 0, "xp": 80, "star_pieces": 0},
        {"min_score": 3000, "credits": 0, "xp": 50, "star_pieces": 0},
        {"min_score": 1000, "credits": 0, "xp": 30, "star_pieces": 0},
        {"min_score": 0, "credits": 0, "xp": 10, "star_pieces": 0},
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
    # ── Anti-cheat (2026-07-03) ────────────────────────────────────────────
    # The rewarded run requires a single-use round token issued by
    # /api/arcade/round-start when the round actually begins. The server
    # measures elapsed time itself (token age) — the client-claimed duration
    # is only a sanity cross-check. Score is capped by a points-per-second
    # ceiling derived from the game's actual scoring math (megaboss burst
    # ~260/s is the hottest legit source; 500/s leaves generous headroom).
    "round_token_ttl_seconds": 2 * 60 * 60,   # token lifetime (max round length)
    "max_points_per_second": 500,             # score ≤ this × server-elapsed seconds
    "max_score_absolute": 500_000,            # hard per-run ceiling
    "duration_slack_seconds": 30,             # client duration may exceed server elapsed by this
}

# ===========================================
# MONTHLY ARCADE LEADERBOARD PRIZES
# ===========================================
# Awarded once per calendar month for the PREVIOUS month, based on each
# user's single validated daily-run score (best of the month). Prizes are
# coupons (existing wallet/checkout flow); traffic is the cheapest asset we
# have, so the pool costs ~nothing while feeling substantial.
ARCADE_MONTHLY_PRIZES = [
    {"min_rank": 1, "max_rank": 1, "coupon_type": "free_gb",
     "payload": {"gb": 50}, "name": "Arcade Champion — 50GB Free"},
    {"min_rank": 2, "max_rank": 2, "coupon_type": "free_gb",
     "payload": {"gb": 25}, "name": "Arcade Runner-up — 25GB Free"},
    {"min_rank": 3, "max_rank": 3, "coupon_type": "free_gb",
     "payload": {"gb": 10}, "name": "Arcade 3rd Place — 10GB Free"},
    {"min_rank": 4, "max_rank": 4, "coupon_type": "discount_percent",
     "payload": {"discount_percent": 10}, "name": "Arcade 4th Place — 10% Off"},
]
ARCADE_PRIZE_COUPON_EXPIRY_DAYS = 45   # same shelf life as season coupons
