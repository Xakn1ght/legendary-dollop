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
    # ── Round checkpoints (2026-07-19) ─────────────────────────────────────
    # v28+ clients POST /api/arcade/checkpoint every ~10s during active play.
    # The rolling state lets the server (a) finalize interrupted runs with the
    # score the player actually earned, (b) kill abandon-grinding (closing
    # mid-run no longer resets the daily attempt once >= min_session_seconds
    # were played), and (c) judge score curves per window instead of the blunt
    # session average — bomb wipes / boss bursts fit in the burst allowance
    # (megaboss max single dump is 8000).
    "checkpoint_burst_allowance": 8000,       # extra points allowed on top of rate x window
    "checkpoint_max_anomalies": 1,            # tolerated over-rate windows before the run is flagged
    "round_stale_finalize_seconds": 30 * 60,  # sweep finalizes rounds idle this long (pauses stop checkpoints)
}

# ===========================================
# MONTHLY ARCADE LEADERBOARD PRIZES
# ===========================================
# Awarded once per calendar month for the PREVIOUS month, based on each
# user's single validated daily-run score (best of the month). Prizes are
# coupons (existing wallet/checkout flow); traffic is the cheapest asset we
# have, so the pool costs ~nothing while feeling substantial.
ARCADE_MONTHLY_PRIZES = [
    # coins (2026-07-08): arcade-only hangar currency on top of the coupon —
    # the main faucet for the premium ability ships (daily cap stays 3/run).
    {"min_rank": 1, "max_rank": 1, "coupon_type": "free_gb",
     "payload": {"gb": 50}, "name": "Arcade Champion — 50GB Free", "coins": 40},
    {"min_rank": 2, "max_rank": 2, "coupon_type": "free_gb",
     "payload": {"gb": 25}, "name": "Arcade Runner-up — 25GB Free", "coins": 25},
    {"min_rank": 3, "max_rank": 3, "coupon_type": "free_gb",
     "payload": {"gb": 10}, "name": "Arcade 3rd Place — 10GB Free", "coins": 15},
    # 2026-07-08: was max_rank 4 — drifted from the documented "#4-10 10% off";
    # restored to 10 (also carries the rank 4-10 coin prize).
    {"min_rank": 4, "max_rank": 10, "coupon_type": "discount_percent",
     "payload": {"discount_percent": 10}, "name": "Arcade Top 10 — 10% Off", "coins": 8},
]
ARCADE_PRIZE_COUPON_EXPIRY_DAYS = 45   # same shelf life as season coupons

# ===========================================
# ARCADE COINS + SHOP (2026-07-07)
# ===========================================
# Coins are an ARCADE-ONLY currency: minted exclusively by the single
# validated daily run (server-capped per run, so ≤ max_per_run per day) and
# spent on in-game cosmetics/upgrades or a daily-run retry. They can NEVER
# convert to credit, stars, GB, days or anything money-adjacent — that keeps
# the "arcade mints nothing" economy invariant intact.
ARCADE_COINS = {
    "max_per_run": 3,          # server cap on coins credited per validated run
}

# The catalog is server truth: prices, item keys and skin tints live here.
# skins: permanent, one equipped at a time ("default" is free and always owned).
#   color  = overlay tint composited onto the base ship sprite (source-atop).
#   sprite = a WHOLE different ship drawing (astrobugz2-relative path) —
#            same 52x32 canvas as the original, so hitbox/feel are identical.
# powers: permanent unlocks applied at the start of every run.
# extra_life: permanent +1 starting life (single purchase).
# retry: consumable — resets today's ranked run so it can be played again.
ARCADE_SHOP = {
    # SHIP CLASSES (2026-07-08): every skin carries a power now.
    #   perk    = passive, applied silently at run start (tuning lives in
    #             astrobugz2/config.js SHIPS.perks — client-side numbers,
    #             bounded by the same score-plausibility caps as everything)
    #   ability = ACTIVE, kill-charged, fired from the on-screen button
    #             (tuning in config.js SHIPS.abilities)
    # The server only says WHICH power a user has (via the loadout); prices
    # and ownership stay server-truth here.
    "skins": {
        "default": {"price": 0,  "color": None},
        "crimson": {"price": 18, "color": "#ff4d4d", "perk": "speed"},
        "ice":     {"price": 18, "color": "#7be0ff", "perk": "iframes"},
        "void":    {"price": 24, "color": "#c04dff", "perk": "slow_tokens"},
        "gold":    {"price": 30, "color": "#ffd23f", "perk": "coin_luck"},
        # full ship redesigns (2026-07-07) — not tints
        "falcon":  {"price": 40, "color": None, "sprite": "sprites/ship_falcon.png",
                    "perk": "fire_rate"},
        "comet":   {"price": 40, "color": None, "sprite": "sprites/ship_comet.png",
                    "perk": "bullet_speed"},
        "titan":   {"price": 50, "color": None, "sprite": "sprites/ship_titan.png",
                    "perk": "shield_cap"},
        "phantom": {"price": 60, "color": None, "sprite": "sprites/ship_phantom.png",
                    "perk": "cheat_death"},
        # premium ability ships (2026-07-08) — the long-term coin goals
        "reaper":  {"price": 80,  "color": None, "sprite": "sprites/ship_reaper.png",
                    "ability": "scythe"},
        "vulcan":  {"price": 110, "color": None, "sprite": "sprites/ship_vulcan.png",
                    "ability": "overdrive"},
        "aegis":   {"price": 150, "color": None, "sprite": "sprites/ship_aegis.png",
                    "ability": "bastion"},
    },
    "powers": {
        "shield_start": {"price": 40},   # start every run with 1 shield
        "spread_start": {"price": 35},   # start every run with the 3-WAY timer
    },
    "extra_life": {"price": 60},
    "retry": {"price": 12},
}

# Per-user difficulty (2026-07-08): admin-set on the wallet, delivered to the
# game via the loadout. The game maps it to an enemy time-scale; boss_rush is
# a QA mode that pulls every boss gate down to level 2 and unlocks all boss
# variants (for testing late-game content without a 10-level grind).
ARCADE_DIFFICULTIES = ("easy", "normal", "hard", "boss_rush")
