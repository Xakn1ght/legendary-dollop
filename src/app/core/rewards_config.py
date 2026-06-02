"""Central reward configuration — edit values here, not in logic.

Final reward map: docs/design-specs/specs/2026-05-31-final-reward-system-map.md
Star season spec:  docs/design-specs/specs/asstroo_star_season_coupon_spec_v2.md

Iron rule: play/levels mint no VPN value. Stars are referral-only & seasonal.
"""

# ── Star Season ────────────────────────────────────────────────────────────
STAR_SEASON_LENGTH_DAYS = 90      # season window; season stars reset between seasons
COUPON_EXPIRY_DAYS = 45           # unlocked coupons expire this many days after unlock

# ── Referral star earning (one of the 4 referral reward choices) ────────────
MIN_REFERRAL_STAR_PLAN_GB = 20            # referred purchase must be ≥ this to qualify
NORMAL_REFERRAL_STARS = 1                 # normal qualifying purchase
RESERVED_AUTORENEW_REFERRAL_STARS = 2     # purchase with a reserved auto-renewal
MAX_STARS_PER_REFERRED_PURCHASE = 2
REFERRAL_BONUS_XP = 50                    # granted per referral regardless of choice

# ── Coupon usage rules ──────────────────────────────────────────────────────
ONLY_ONE_COUPON_PER_PURCHASE = True
COUPONS_CAN_STACK = False
DISCOUNT_COUPON_MAX_PLAN_GB = 100         # cap discount value on very large custom plans

# ── Star milestone ladder (auto-unlocks a coupon once per season) ───────────
# coupon_type ∈ discount_percent | free_gb | free_plan | free_autorenew | vip_pack | legend_pack
STAR_SEASON_MILESTONES = {
    3:  {"name": "Starter Discount",  "coupon_type": "discount_percent", "payload": {"discount_percent": 10}},
    5:  {"name": "Better Discount",   "coupon_type": "discount_percent", "payload": {"discount_percent": 20}},
    10: {"name": "Free Traffic Boost","coupon_type": "free_gb",          "payload": {"gb": 10}},
    15: {"name": "Half Price",        "coupon_type": "discount_percent", "payload": {"discount_percent": 50}},
    20: {"name": "Free 20GB Plan",    "coupon_type": "free_plan",        "payload": {"plan_gb": 20, "duration_days": 35}},
    25: {"name": "Free 40GB Plan",    "coupon_type": "free_plan",        "payload": {"plan_gb": 40, "duration_days": 35}},
    30: {"name": "Free Auto-Renewal", "coupon_type": "free_autorenew",   "payload": {"max_plan_gb": 100, "duration_days": 35}},
    40: {"name": "Season Champion",   "coupon_type": "vip_pack",         "payload": {
        "free_autorenew": {"max_plan_gb": 100, "duration_days": 35},
        "priority_support_days": 30, "badge": "Champion", "theme": "champion"}},
    50: {"name": "Season Legend",     "coupon_type": "legend_pack",      "payload": {
        "free_autorenew": {"max_plan_gb": 100, "duration_days": 35},
        "bonus_gb": 100, "priority_support_days": 60, "badge": "Legend", "theme": "legend"}},
}

# ── VIP Promoter cashout (Phase D) ──────────────────────────────────────────
CASHOUT_MIN_ACTIVE_REFERRALS = 20
CASHOUT_RATE = 0.05               # 5% cash (vs 10% store credit)
PROMOTER_REFERRAL_CUT = {0: 0.10, 20: 0.12, 50: 0.15}  # store-credit % by active-referral tier
