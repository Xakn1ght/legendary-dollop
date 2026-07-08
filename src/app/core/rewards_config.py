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
# coupon_type ∈ discount_percent | free_gb | free_plan | vip_days
# (free_autorenew coupons are no longer minted but stay honored until expiry;
#  vip_pack/legend_pack are retired — see specs/2026-07-06-star-ladder-simplification-design.md)
# Optional milestone keys "badge"/"theme" grant profile cosmetics at unlock time.
# Economics @175k toman/$: every prize is VPN value (~70 toman/GB real cost) or
# VIP time (zero infra cost). The ladder never mints cash/credit.
STAR_SEASON_MILESTONES = {
    1:  {"name": "First Spark",       "coupon_type": "discount_percent", "payload": {"discount_percent": 5}},
    3:  {"name": "Starter Discount",  "coupon_type": "discount_percent", "payload": {"discount_percent": 10}},
    5:  {"name": "Better Discount",   "coupon_type": "discount_percent", "payload": {"discount_percent": 20}},
    10: {"name": "Free Traffic Boost","coupon_type": "free_gb",          "payload": {"gb": 10}},
    15: {"name": "Half Price",        "coupon_type": "discount_percent", "payload": {"discount_percent": 50}},
    20: {"name": "Free 20GB Plan",    "coupon_type": "free_plan",        "payload": {"plan_gb": 20, "duration_days": 35}},
    25: {"name": "Free 40GB Plan",    "coupon_type": "free_plan",        "payload": {"plan_gb": 40, "duration_days": 35}},
    40: {"name": "Season Champion",   "coupon_type": "free_plan",
         "payload": {"plan_gb": 60, "duration_days": 35},
         "badge": "Champion", "theme": "champion"},
    50: {"name": "Season Legend",     "coupon_type": "vip_days",
         "payload": {"days": 30},
         # Legend also gets 100GB as a normal checkout coupon (~7k toman real cost).
         "extra_coupons": [{"coupon_type": "free_gb", "payload": {"gb": 100}}],
         "badge": "Legend", "theme": "legend"},
}

# ── VIP Promoter cashout (Phase D) ──────────────────────────────────────────
CASHOUT_MIN_ACTIVE_REFERRALS = 20
CASHOUT_MIN_AMOUNT_TOMAN = 200_000   # below this, credit stays spendable in-app
# Cash-out is 1:1 by decision — credit is referral-only, so no haircut. (Was 5%.)
PROMOTER_REFERRAL_CUT = {0: 0.10, 20: 0.12, 50: 0.15}  # store-credit % by active-referral tier
# Two-stage earnings (Pasha, 2026-07-08): BEFORE the 20-active gate the cut
# pays STORE CREDIT, capped at this lifetime total; crossing the gate flips
# the account permanently (promoter_unlocked_at) and from then on the cut
# pays the withdrawable cashback balance instead. Pre-gate credit never
# converts to cash.
REFERRAL_STORE_CREDIT_CAP_TOMAN = 1_000_000
