"""Dashboard HTTP handlers (split from former routes/dashboard.py)."""

from app.api.routes.dashboard.challenges_prefs import (
    handle_dashboard_challenges,
    handle_dashboard_challenges_claim,
    handle_dashboard_notification_clear_history,
    handle_dashboard_preferences_get,
    handle_dashboard_preferences_patch,
)
from app.api.routes.dashboard.index_auth import (
    handle_dashboard_index,
    handle_dashboard_login,
    handle_dashboard_submit_referral,
)
from app.api.routes.dashboard.orbit import handle_dashboard_orbit_add_link
from app.api.routes.dashboard.profile_photo import handle_profile_photo
from app.api.routes.dashboard.referrals import (
    handle_dashboard_enter_referral,
    handle_dashboard_redeem_referral_reward,
    handle_dashboard_referral_rewards,
    handle_dashboard_referrals,
)
from app.api.routes.dashboard.star_rewards import (
    handle_dashboard_coupon_apply_gb,
    handle_dashboard_season,
    handle_dashboard_redeem_vip_days,
    handle_dashboard_star_claim_apply,
    handle_dashboard_star_claims,
    handle_dashboard_star_tiers,
)
from app.api.routes.dashboard.stats_notifications import (
    handle_dashboard_notification_mark_read,
    handle_dashboard_notification_unread_count,
    handle_dashboard_notifications,
    handle_dashboard_stats,
)
from app.api.routes.dashboard.vip import (
    handle_vip_plans,
    handle_vip_purchase,
    handle_vip_upload_receipt,
)
from app.api.routes.dashboard.achievements import (
    handle_dashboard_achievements,
    handle_dashboard_achievements_claim,
)
from app.api.routes.dashboard.wallet import (
    handle_dashboard_earnings,
    handle_dashboard_earnings_card,
    handle_dashboard_rewards_summary,
    handle_dashboard_wallet_cashout,
    handle_dashboard_wallet_convert_loyalty,
)

__all__ = [
    "handle_dashboard_achievements",
    "handle_dashboard_achievements_claim",
    "handle_dashboard_challenges",
    "handle_dashboard_challenges_claim",
    "handle_dashboard_earnings",
    "handle_dashboard_earnings_card",
    "handle_dashboard_index",
    "handle_dashboard_login",
    "handle_dashboard_notification_clear_history",
    "handle_dashboard_notification_mark_read",
    "handle_dashboard_notification_unread_count",
    "handle_dashboard_notifications",
    "handle_dashboard_preferences_get",
    "handle_dashboard_preferences_patch",
    "handle_dashboard_enter_referral",
    "handle_dashboard_redeem_referral_reward",
    "handle_dashboard_referral_rewards",
    "handle_dashboard_referrals",
    "handle_dashboard_rewards_summary",
    "handle_dashboard_coupon_apply_gb",
    "handle_dashboard_redeem_vip_days",
    "handle_dashboard_season",
    "handle_dashboard_star_claim_apply",
    "handle_dashboard_star_claims",
    "handle_dashboard_star_tiers",
    "handle_dashboard_stats",
    "handle_dashboard_submit_referral",
    "handle_dashboard_wallet_cashout",
    "handle_dashboard_wallet_convert_loyalty",
    "handle_dashboard_orbit_add_link",
    "handle_profile_photo",
    "handle_vip_plans",
    "handle_vip_purchase",
    "handle_vip_upload_receipt",
]
