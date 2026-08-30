"""Register /api/admin JSON routes."""

from aiohttp import web

from .constants import ADMIN_API_BASE
from .handlers import (
    handle_admin_analytics_expiring,
    handle_admin_analytics_online,
    handle_admin_analytics_revenue,
    handle_admin_approve_cashout,
    handle_admin_approve_charge,
    handle_admin_approve_receipt,
    handle_admin_approve_vip_order,
    handle_admin_arcade_flags,
    handle_admin_arcade_user_adjust,
    handle_admin_arcade_user_get,
    handle_admin_audit_list,
    handle_admin_broadcast,
    handle_admin_coupon_create,
    handle_admin_coupon_revoke,
    handle_admin_coupons_list,
    handle_admin_db_capabilities,
    handle_admin_db_exec,
    handle_admin_db_query,
    handle_admin_db_table_rows,
    handle_admin_db_table_schema,
    handle_admin_db_tables,
    handle_admin_deny_cashout,
    handle_admin_deny_charge,
    handle_admin_deny_receipt,
    handle_admin_deny_vip_order,
    handle_admin_expiring_remind,
    handle_admin_export_transactions,
    handle_admin_get_job_schedules,
    handle_admin_get_payment_settings,
    handle_admin_get_plans,
    handle_admin_get_support_settings,
    handle_admin_ip_whitelist_get,
    handle_admin_ip_whitelist_update,
    handle_admin_login,
    handle_admin_logout,
    handle_admin_logs,
    handle_admin_node_reconnect,
    handle_admin_nodes,
    handle_admin_pending_receipts,
    handle_admin_receipt_detail,
    handle_admin_recent_broadcasts,
    handle_admin_remove_vip,
    handle_admin_reset_arcade,
    handle_admin_search_user_for_vip,
    handle_admin_send_notification,
    handle_admin_servers,
    handle_admin_session_revoke,
    handle_admin_sessions_list,
    handle_admin_sessions_revoke_others,
    handle_admin_set_hwid_limit,
    handle_admin_set_vip,
    handle_admin_sms_control_get,
    handle_admin_sms_control_set,
    handle_admin_stats,
    handle_admin_subscription_delete,
    handle_admin_subscription_devices,
    handle_admin_subscription_extend,
    handle_admin_subscription_usage,
    handle_admin_subscriptions,
    handle_admin_support_ai_get,
    handle_admin_support_ai_knowledge,
    handle_admin_support_ai_set,
    handle_admin_support_ws,
    handle_admin_system_health,
    handle_admin_ticket_archive,
    handle_admin_ticket_close,
    handle_admin_ticket_delete,
    handle_admin_ticket_detail,
    handle_admin_ticket_photo_get,
    handle_admin_ticket_photo_upload,
    handle_admin_ticket_reopen,
    handle_admin_ticket_reply,
    handle_admin_ticket_user_photo,
    handle_admin_tickets,
    handle_admin_toggle_user,
    handle_admin_ui_get_settings,
    handle_admin_ui_set_settings,
    handle_admin_ui_upload_background,
    handle_admin_update_job_schedules,
    handle_admin_update_payment_settings,
    handle_admin_update_plans,
    handle_admin_user_delete,
    handle_admin_user_detail,
    handle_admin_user_update,
    handle_admin_users,
    handle_admin_verify_2fa,
    handle_admin_verify_session,
    handle_admin_vip_users,
)


def register_admin_api_routes(app: web.Application) -> None:
    app.router.add_get(ADMIN_API_BASE + "/stats", handle_admin_stats)
    app.router.add_get(ADMIN_API_BASE + "/users", handle_admin_users)
    app.router.add_get(ADMIN_API_BASE + "/users/{user_id}", handle_admin_user_detail)
    app.router.add_post(ADMIN_API_BASE + "/users/{user_id}", handle_admin_user_update)
    app.router.add_delete(ADMIN_API_BASE + "/users/{user_id}", handle_admin_user_delete)
    app.router.add_post(ADMIN_API_BASE + "/users/{user_id}/reset-arcade", handle_admin_reset_arcade)
    app.router.add_get(ADMIN_API_BASE + "/users/{user_id}/arcade", handle_admin_arcade_user_get)
    app.router.add_post(ADMIN_API_BASE + "/users/{user_id}/arcade", handle_admin_arcade_user_adjust)
    app.router.add_get(ADMIN_API_BASE + "/arcade/flags", handle_admin_arcade_flags)
    app.router.add_post(ADMIN_API_BASE + "/users/{username}/toggle-status", handle_admin_toggle_user)

    app.router.add_get(ADMIN_API_BASE + "/subscriptions", handle_admin_subscriptions)
    app.router.add_post(ADMIN_API_BASE + "/subscriptions/{username}/extend", handle_admin_subscription_extend)
    app.router.add_post(ADMIN_API_BASE + "/subscriptions/{username}/hwid", handle_admin_set_hwid_limit)
    app.router.add_get(ADMIN_API_BASE + "/subscriptions/{username}/devices", handle_admin_subscription_devices)
    app.router.add_delete(ADMIN_API_BASE + "/subscriptions/{username}", handle_admin_subscription_delete)
    app.router.add_get(ADMIN_API_BASE + "/subscriptions/{username}/usage", handle_admin_subscription_usage)
    app.router.add_get(ADMIN_API_BASE + "/servers", handle_admin_servers)
    app.router.add_post(ADMIN_API_BASE + "/broadcast", handle_admin_broadcast)
    app.router.add_get(ADMIN_API_BASE + "/logs", handle_admin_logs)

    app.router.add_get(ADMIN_API_BASE + "/tickets", handle_admin_tickets)
    app.router.add_get(ADMIN_API_BASE + "/tickets/{ticket_id}", handle_admin_ticket_detail)
    app.router.add_post(ADMIN_API_BASE + "/tickets/{ticket_id}/reply", handle_admin_ticket_reply)
    app.router.add_post(ADMIN_API_BASE + "/tickets/{ticket_id}/photo", handle_admin_ticket_photo_upload)
    app.router.add_get(ADMIN_API_BASE + "/tickets/{ticket_id}/photo/{file_name}", handle_admin_ticket_photo_get)
    app.router.add_get(ADMIN_API_BASE + "/tickets/{ticket_id}/user-photo", handle_admin_ticket_user_photo)
    app.router.add_post(ADMIN_API_BASE + "/tickets/{ticket_id}/close", handle_admin_ticket_close)
    app.router.add_post(ADMIN_API_BASE + "/tickets/{ticket_id}/archive", handle_admin_ticket_archive)
    app.router.add_post(ADMIN_API_BASE + "/tickets/{ticket_id}/reopen", handle_admin_ticket_reopen)
    app.router.add_delete(ADMIN_API_BASE + "/tickets/{ticket_id}", handle_admin_ticket_delete)

    app.router.add_post(ADMIN_API_BASE + "/notifications/send", handle_admin_send_notification)
    app.router.add_get(ADMIN_API_BASE + "/notifications/broadcasts/recent", handle_admin_recent_broadcasts)

    app.router.add_get(ADMIN_API_BASE + "/receipts/pending", handle_admin_pending_receipts)
    app.router.add_get(ADMIN_API_BASE + "/receipts/{sub_id}", handle_admin_receipt_detail)
    app.router.add_post(ADMIN_API_BASE + "/receipts/{sub_id}/approve", handle_admin_approve_receipt)
    app.router.add_post(ADMIN_API_BASE + "/receipts/{sub_id}/deny", handle_admin_deny_receipt)

    app.router.add_get(ADMIN_API_BASE + "/settings/plans", handle_admin_get_plans)
    app.router.add_post(ADMIN_API_BASE + "/settings/plans", handle_admin_update_plans)
    app.router.add_get(ADMIN_API_BASE + "/settings/payment", handle_admin_get_payment_settings)
    app.router.add_post(ADMIN_API_BASE + "/settings/payment", handle_admin_update_payment_settings)
    app.router.add_get(ADMIN_API_BASE + "/settings/job-schedules", handle_admin_get_job_schedules)
    app.router.add_post(ADMIN_API_BASE + "/settings/job-schedules", handle_admin_update_job_schedules)
    app.router.add_get(ADMIN_API_BASE + "/settings/support", handle_admin_get_support_settings)
    app.router.add_get(ADMIN_API_BASE + "/settings/ip-whitelist", handle_admin_ip_whitelist_get)
    app.router.add_post(ADMIN_API_BASE + "/settings/ip-whitelist", handle_admin_ip_whitelist_update)

    app.router.add_get(ADMIN_API_BASE + "/vip", handle_admin_vip_users)
    app.router.add_get(ADMIN_API_BASE + "/vip/search", handle_admin_search_user_for_vip)
    app.router.add_post(ADMIN_API_BASE + "/users/{user_id}/vip", handle_admin_set_vip)
    app.router.add_delete(ADMIN_API_BASE + "/users/{user_id}/vip", handle_admin_remove_vip)

    app.router.add_post(ADMIN_API_BASE + "/vip-orders/{order_id}/approve", handle_admin_approve_vip_order)
    app.router.add_post(ADMIN_API_BASE + "/vip-orders/{order_id}/deny", handle_admin_deny_vip_order)

    app.router.add_post(ADMIN_API_BASE + "/charges/{charge_id}/approve", handle_admin_approve_charge)
    app.router.add_post(ADMIN_API_BASE + "/charges/{charge_id}/deny", handle_admin_deny_charge)

    app.router.add_post(ADMIN_API_BASE + "/cashouts/{cashout_id}/approve", handle_admin_approve_cashout)
    app.router.add_post(ADMIN_API_BASE + "/cashouts/{cashout_id}/deny", handle_admin_deny_cashout)

    # Ops: analytics / audit / health / nodes / export / coupons / SMS control
    app.router.add_get(ADMIN_API_BASE + "/analytics/revenue", handle_admin_analytics_revenue)
    app.router.add_get(ADMIN_API_BASE + "/analytics/expiring", handle_admin_analytics_expiring)
    app.router.add_post(ADMIN_API_BASE + "/analytics/expiring/remind", handle_admin_expiring_remind)
    app.router.add_get(ADMIN_API_BASE + "/analytics/online", handle_admin_analytics_online)
    app.router.add_get(ADMIN_API_BASE + "/audit", handle_admin_audit_list)
    app.router.add_get(ADMIN_API_BASE + "/system-health", handle_admin_system_health)
    app.router.add_get(ADMIN_API_BASE + "/nodes", handle_admin_nodes)
    app.router.add_post(ADMIN_API_BASE + "/nodes/{node_id}/reconnect", handle_admin_node_reconnect)
    app.router.add_get(ADMIN_API_BASE + "/export/transactions", handle_admin_export_transactions)
    app.router.add_get(ADMIN_API_BASE + "/coupons", handle_admin_coupons_list)
    app.router.add_post(ADMIN_API_BASE + "/coupons", handle_admin_coupon_create)
    app.router.add_post(ADMIN_API_BASE + "/coupons/revoke", handle_admin_coupon_revoke)
    app.router.add_get(ADMIN_API_BASE + "/sms-control", handle_admin_sms_control_get)
    app.router.add_post(ADMIN_API_BASE + "/sms-control", handle_admin_sms_control_set)
    app.router.add_get(ADMIN_API_BASE + "/support-ai", handle_admin_support_ai_get)
    app.router.add_post(ADMIN_API_BASE + "/support-ai", handle_admin_support_ai_set)
    app.router.add_post(ADMIN_API_BASE + "/support-ai/knowledge",
                        handle_admin_support_ai_knowledge)

    app.router.add_post(ADMIN_API_BASE + "/login", handle_admin_login)
    app.router.add_post(ADMIN_API_BASE + "/verify-2fa", handle_admin_verify_2fa)
    app.router.add_post(ADMIN_API_BASE + "/logout", handle_admin_logout)
    app.router.add_get(ADMIN_API_BASE + "/verify-session", handle_admin_verify_session)
    app.router.add_get(ADMIN_API_BASE + "/sessions", handle_admin_sessions_list)
    app.router.add_post(ADMIN_API_BASE + "/sessions/revoke", handle_admin_session_revoke)
    app.router.add_post(ADMIN_API_BASE + "/sessions/revoke-others", handle_admin_sessions_revoke_others)

    app.router.add_get(ADMIN_API_BASE + "/ui/settings", handle_admin_ui_get_settings)
    app.router.add_post(ADMIN_API_BASE + "/ui/settings", handle_admin_ui_set_settings)
    app.router.add_post(ADMIN_API_BASE + "/ui/background", handle_admin_ui_upload_background)

    app.router.add_get(ADMIN_API_BASE + "/db/capabilities", handle_admin_db_capabilities)
    app.router.add_get(ADMIN_API_BASE + "/db/tables", handle_admin_db_tables)
    app.router.add_get(ADMIN_API_BASE + "/db/table/{table}/schema", handle_admin_db_table_schema)
    app.router.add_get(ADMIN_API_BASE + "/db/table/{table}/rows", handle_admin_db_table_rows)
    app.router.add_post(ADMIN_API_BASE + "/db/query", handle_admin_db_query)
    app.router.add_post(ADMIN_API_BASE + "/db/exec", handle_admin_db_exec)

    app.router.add_get(ADMIN_API_BASE + "/ws/support", handle_admin_support_ws)
