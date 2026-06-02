"""Import dashboard route callables once for registration."""

from app.api.routes.admin_ws import handle_user_support_ws
from app.api.routes.dashboard import (
    handle_dashboard_challenges,
    handle_dashboard_challenges_claim,
    handle_dashboard_enter_referral,
    handle_dashboard_login,
    handle_dashboard_notification_clear_history,
    handle_dashboard_notification_mark_read,
    handle_dashboard_notification_unread_count,
    handle_dashboard_notifications,
    handle_dashboard_preferences_get,
    handle_dashboard_preferences_patch,
    handle_dashboard_redeem_referral_reward,
    handle_dashboard_referral_rewards,
    handle_dashboard_referrals,
    handle_dashboard_rewards_summary,
    handle_dashboard_season,
    handle_dashboard_star_claim_apply,
    handle_dashboard_star_claims,
    handle_dashboard_star_tiers,
    handle_dashboard_stats,
    handle_dashboard_submit_referral,
    handle_dashboard_wallet_cashout,
    handle_dashboard_wallet_convert_loyalty,
    handle_vip_plans,
    handle_vip_purchase,
    handle_vip_upload_receipt,
)
from app.api.routes.dashboard_charge import (
    handle_cancel_charge,
    handle_get_charge_packages,
    handle_start_charge,
    handle_submit_charge_receipt,
)
from app.api.routes.dashboard_purchase import (
    handle_cancel_order,
    handle_check_service_name,
    handle_get_pending_orders,
    handle_get_plans,
    handle_get_user_purchase_info,
    handle_start_purchase,
    handle_submit_receipt,
    handle_validate_referral,
)
from app.api.routes.dashboard_subs import (
    handle_dashboard_add_sub,
    handle_dashboard_detect_country,
    handle_dashboard_flag,
    handle_dashboard_links,
    handle_dashboard_list_subs,
    handle_dashboard_overview,
    handle_dashboard_ping,
    handle_dashboard_remove_local,
    handle_dashboard_revoke,
    handle_dashboard_speed_dl,
    handle_dashboard_speed_ul,
)
from app.api.routes.dashboard_tickets import (
    handle_dashboard_tickets_create,
    handle_dashboard_tickets_delete,
    handle_dashboard_tickets_detail,
    handle_dashboard_tickets_list,
    handle_dashboard_tickets_reply,
)
