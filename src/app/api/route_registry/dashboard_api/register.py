"""Register dashboard JSON API and WebSocket routes."""

from aiohttp import web

from .constants import DASHBOARD_API_BASE_PATH
from .handlers import (
    handle_cancel_charge,
    handle_cancel_order,
    handle_check_service_name,
    handle_custom_plan_quote,
    handle_dashboard_add_sub,
    handle_dashboard_challenges,
    handle_dashboard_challenges_claim,
    handle_dashboard_detect_country,
    handle_dashboard_enter_referral,
    handle_dashboard_flag,
    handle_dashboard_links,
    handle_dashboard_list_subs,
    handle_dashboard_login,
    handle_dashboard_notification_clear_history,
    handle_dashboard_notification_mark_read,
    handle_dashboard_notification_unread_count,
    handle_dashboard_notifications,
    handle_dashboard_overview,
    handle_dashboard_ping,
    handle_dashboard_preferences_get,
    handle_dashboard_preferences_patch,
    handle_dashboard_orbit_add_link,
    handle_profile_photo,
    handle_dashboard_redeem_referral_reward,
    handle_dashboard_referral_rewards,
    handle_dashboard_referrals,
    handle_dashboard_remove_local,
    handle_dashboard_revoke,
    handle_dashboard_rewards_summary,
    handle_dashboard_redeem_vip_days,
    handle_dashboard_season,
    handle_dashboard_speed_dl,
    handle_dashboard_speed_ul,
    handle_dashboard_star_claim_apply,
    handle_dashboard_star_claims,
    handle_dashboard_star_tiers,
    handle_dashboard_stats,
    handle_dashboard_submit_referral,
    handle_dashboard_tickets_create,
    handle_dashboard_tickets_delete,
    handle_dashboard_tickets_detail,
    handle_dashboard_tickets_list,
    handle_dashboard_ticket_photo_get,
    handle_dashboard_ticket_photo_upload,
    handle_dashboard_tickets_reply,
    handle_dashboard_wallet_cashout,
    handle_dashboard_wallet_convert_loyalty,
    handle_get_charge_packages,
    handle_get_pending_orders,
    handle_get_plans,
    handle_get_user_purchase_info,
    handle_start_charge,
    handle_start_purchase,
    handle_submit_charge_receipt,
    handle_submit_receipt,
    handle_user_support_ws,
    handle_validate_referral,
    handle_vip_plans,
    handle_vip_purchase,
    handle_vip_upload_receipt,
)


def register_dashboard_api_routes(app: web.Application) -> None:
    app.router.add_post(DASHBOARD_API_BASE_PATH + "/login", handle_dashboard_login)
    app.router.add_post(DASHBOARD_API_BASE_PATH + "/submit-referral", handle_dashboard_submit_referral)
    app.router.add_get(DASHBOARD_API_BASE_PATH + "/stats", handle_dashboard_stats)

    app.router.add_get(DASHBOARD_API_BASE_PATH + "/subscriptions", handle_dashboard_list_subs)
    app.router.add_post(DASHBOARD_API_BASE_PATH + "/subscriptions/add", handle_dashboard_add_sub)
    app.router.add_get(DASHBOARD_API_BASE_PATH + "/subscriptions/{sub_id}/links", handle_dashboard_links)
    app.router.add_post(DASHBOARD_API_BASE_PATH + "/subscriptions/{sub_id}/revoke", handle_dashboard_revoke)
    app.router.add_delete(DASHBOARD_API_BASE_PATH + "/subscriptions/{sub_id}", handle_dashboard_remove_local)
    app.router.add_get(DASHBOARD_API_BASE_PATH + "/overview", handle_dashboard_overview)
    app.router.add_get(DASHBOARD_API_BASE_PATH + "/profile-photo", handle_profile_photo)
    app.router.add_post(DASHBOARD_API_BASE_PATH + "/orbit/add-link", handle_dashboard_orbit_add_link)

    app.router.add_get(DASHBOARD_API_BASE_PATH + "/ping", handle_dashboard_ping)
    app.router.add_get(DASHBOARD_API_BASE_PATH + "/speed-dl", handle_dashboard_speed_dl)
    app.router.add_post(DASHBOARD_API_BASE_PATH + "/speed-ul", handle_dashboard_speed_ul)
    app.router.add_get(DASHBOARD_API_BASE_PATH + "/detect-country", handle_dashboard_detect_country)
    app.router.add_get(DASHBOARD_API_BASE_PATH + "/flags/{code}.png", handle_dashboard_flag)

    app.router.add_get(DASHBOARD_API_BASE_PATH + "/notifications", handle_dashboard_notifications)
    app.router.add_get(
        DASHBOARD_API_BASE_PATH + "/notifications/unread-count",
        handle_dashboard_notification_unread_count,
    )
    app.router.add_post(
        DASHBOARD_API_BASE_PATH + "/notifications/mark-read",
        handle_dashboard_notification_mark_read,
    )
    app.router.add_post(
        DASHBOARD_API_BASE_PATH + "/notifications/clear-history",
        handle_dashboard_notification_clear_history,
    )

    app.router.add_get(DASHBOARD_API_BASE_PATH + "/challenges", handle_dashboard_challenges)
    app.router.add_post(DASHBOARD_API_BASE_PATH + "/challenges/claim", handle_dashboard_challenges_claim)

    app.router.add_get(DASHBOARD_API_BASE_PATH + "/preferences", handle_dashboard_preferences_get)
    app.router.add_post(DASHBOARD_API_BASE_PATH + "/preferences", handle_dashboard_preferences_patch)

    app.router.add_get(DASHBOARD_API_BASE_PATH + "/referrals", handle_dashboard_referrals)
    app.router.add_post(DASHBOARD_API_BASE_PATH + "/referrals/enter", handle_dashboard_enter_referral)
    app.router.add_get(DASHBOARD_API_BASE_PATH + "/referral-rewards", handle_dashboard_referral_rewards)
    app.router.add_post(
        DASHBOARD_API_BASE_PATH + "/referral-rewards/{reward_id}/redeem",
        handle_dashboard_redeem_referral_reward,
    )
    app.router.add_get(DASHBOARD_API_BASE_PATH + "/rewards/summary", handle_dashboard_rewards_summary)
    app.router.add_post(DASHBOARD_API_BASE_PATH + "/wallet/convert-loyalty", handle_dashboard_wallet_convert_loyalty)
    app.router.add_post(DASHBOARD_API_BASE_PATH + "/wallet/cashout", handle_dashboard_wallet_cashout)
    app.router.add_get(DASHBOARD_API_BASE_PATH + "/season", handle_dashboard_season)
    app.router.add_post(DASHBOARD_API_BASE_PATH + "/coupons/{coupon_id}/redeem-vip", handle_dashboard_redeem_vip_days)
    app.router.add_get(DASHBOARD_API_BASE_PATH + "/star-tiers", handle_dashboard_star_tiers)
    app.router.add_get(DASHBOARD_API_BASE_PATH + "/star-claims", handle_dashboard_star_claims)
    app.router.add_post(
        DASHBOARD_API_BASE_PATH + "/star-claims/{claim_id}/claim",
        handle_dashboard_star_claim_apply,
    )

    app.router.add_get(DASHBOARD_API_BASE_PATH + "/vip/plans", handle_vip_plans)
    app.router.add_post(DASHBOARD_API_BASE_PATH + "/vip/purchase", handle_vip_purchase)
    app.router.add_post(DASHBOARD_API_BASE_PATH + "/vip/receipt", handle_vip_upload_receipt)

    app.router.add_get(DASHBOARD_API_BASE_PATH + "/tickets", handle_dashboard_tickets_list)
    app.router.add_post(DASHBOARD_API_BASE_PATH + "/tickets", handle_dashboard_tickets_create)
    app.router.add_get(DASHBOARD_API_BASE_PATH + "/tickets/{ticket_id}", handle_dashboard_tickets_detail)
    app.router.add_post(DASHBOARD_API_BASE_PATH + "/tickets/{ticket_id}/reply", handle_dashboard_tickets_reply)
    app.router.add_post(DASHBOARD_API_BASE_PATH + "/tickets/{ticket_id}/photo", handle_dashboard_ticket_photo_upload)
    app.router.add_get(
        DASHBOARD_API_BASE_PATH + "/tickets/{ticket_id}/photo/{file_name}", handle_dashboard_ticket_photo_get
    )
    app.router.add_delete(DASHBOARD_API_BASE_PATH + "/tickets/{ticket_id}", handle_dashboard_tickets_delete)

    app.router.add_get(DASHBOARD_API_BASE_PATH + "/ws/support", handle_user_support_ws)

    app.router.add_get(DASHBOARD_API_BASE_PATH + "/purchase/plans", handle_get_plans)
    app.router.add_get(DASHBOARD_API_BASE_PATH + "/purchase/user-info", handle_get_user_purchase_info)
    app.router.add_post(DASHBOARD_API_BASE_PATH + "/purchase/start", handle_start_purchase)
    app.router.add_post(DASHBOARD_API_BASE_PATH + "/purchase/receipt", handle_submit_receipt)
    app.router.add_post(DASHBOARD_API_BASE_PATH + "/purchase/cancel", handle_cancel_order)
    app.router.add_get(DASHBOARD_API_BASE_PATH + "/purchase/check-name", handle_check_service_name)
    app.router.add_get(DASHBOARD_API_BASE_PATH + "/purchase/custom-quote", handle_custom_plan_quote)
    app.router.add_get(DASHBOARD_API_BASE_PATH + "/purchase/validate-referral", handle_validate_referral)
    app.router.add_get(DASHBOARD_API_BASE_PATH + "/purchase/pending-orders", handle_get_pending_orders)

    app.router.add_get(DASHBOARD_API_BASE_PATH + "/charge/packages", handle_get_charge_packages)
    app.router.add_post(DASHBOARD_API_BASE_PATH + "/charge/start", handle_start_charge)
    app.router.add_post(DASHBOARD_API_BASE_PATH + "/charge/receipt", handle_submit_charge_receipt)
    app.router.add_post(DASHBOARD_API_BASE_PATH + "/charge/cancel", handle_cancel_charge)
