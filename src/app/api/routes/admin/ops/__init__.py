"""Operational admin endpoints: audit trail, revenue analytics, expiry cohorts,
system health, PasarGuard nodes, CSV export, coupon campaigns, SMS auto-approve
control."""

from .analytics import (
    handle_admin_analytics_expiring,
    handle_admin_analytics_online,
    handle_admin_analytics_revenue,
    handle_admin_expiring_remind,
)
from .audit import handle_admin_audit_list
from .coupons import (
    handle_admin_coupon_create,
    handle_admin_coupon_revoke,
    handle_admin_coupons_list,
)
from .export import handle_admin_export_transactions
from .health import handle_admin_system_health
from .nodes import handle_admin_node_reconnect, handle_admin_nodes
from .sms import handle_admin_sms_control_get, handle_admin_sms_control_set
from .support_ai import (
    handle_admin_support_ai_get,
    handle_admin_support_ai_knowledge,
    handle_admin_support_ai_set,
)

__all__ = [
    "handle_admin_analytics_expiring",
    "handle_admin_analytics_online",
    "handle_admin_analytics_revenue",
    "handle_admin_audit_list",
    "handle_admin_expiring_remind",
    "handle_admin_coupon_create",
    "handle_admin_coupon_revoke",
    "handle_admin_coupons_list",
    "handle_admin_export_transactions",
    "handle_admin_system_health",
    "handle_admin_node_reconnect",
    "handle_admin_nodes",
    "handle_admin_sms_control_get",
    "handle_admin_support_ai_get",
    "handle_admin_support_ai_knowledge",
    "handle_admin_support_ai_set",
    "handle_admin_sms_control_set",
]
