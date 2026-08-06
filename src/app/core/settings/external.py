"""PasarGuard panel, subscription links, and dashboard purchase/discount env configuration."""

import os

# Backend panel/API details
# IMPORTANT: Set these in your .env file for security.
# Legacy MARZBAN_* env keys are still honored as fallbacks (pre-2026-07 deploys).
PASARGUARD_USERNAME = os.environ.get("PASARGUARD_USERNAME") or os.environ.get("MARZBAN_USERNAME", "mykp")
PASARGUARD_PASSWORD = os.environ.get("PASARGUARD_PASSWORD") or os.environ.get("MARZBAN_PASSWORD", "")
PASARGUARD_BASE_URL = (
    os.environ.get("PASARGUARD_BASE_URL")
    or os.environ.get("MARZBAN_BASE_URL", "https://home.afffb.com:9443")
)

# Static panel API key (PasarGuard 5.1+ "API Keys"). When set, every panel
# request authenticates via the X-Api-Key header and the admin-token
# login/refresh dance is skipped entirely (keys never expire unless created
# with an expire_date). Empty -> classic username/password bearer flow.
PASARGUARD_API_KEY = (os.environ.get("PASARGUARD_API_KEY") or "").strip()

# PasarGuard groups: users get their inbounds via group membership (the old
# per-user inbounds dict is gone). New users are created in these groups —
# must match where the migrated users live (group 1 as of the 2026-07 move).
PASARGUARD_GROUP_IDS = [
    int(g) for g in os.environ.get("PASARGUARD_GROUP_IDS", "1").split(",") if g.strip().isdigit()
] or [1]

# Shared secret the PasarGuard panel sends with webhook events (x-webhook-secret
# header). Empty → the webhook receiver rejects everything (fail closed).
PASARGUARD_WEBHOOK_SECRET = os.environ.get("PASARGUARD_WEBHOOK_SECRET", "")

# Shared secret for the PasarGuard → app webhook receiver
# (POST /api/webhook/pasarguard). Empty = receiver disabled (403s everything).
PASARGUARD_WEBHOOK_SECRET = os.environ.get("PASARGUARD_WEBHOOK_SECRET", "").strip()

# --- Test mode -----------------------------------------------------------------
# When set, every panel username created by a purchase/charge gets this prefix,
# so test accounts are distinguishable from the thousands of real ones sharing
# the panel. `scripts/cleanup_test_panel_users.py` deletes ONLY names carrying
# it, and refuses to run at all when this is empty. Leave EMPTY in production.
TEST_PANEL_PREFIX = os.environ.get("TEST_PANEL_PREFIX", "").strip()

# Subscription link details
SUBLINK = os.environ.get("SUBLINK", "astrobyte.org/sub")
# Optional: base64 of the public subscription link base (used by some legacy clients/tools)
SUBLINK_BASE64 = os.environ.get("SUBLINK_BASE64", "")

# Dashboard: subscription link restrictions
# When enabled, the dashboard will only accept subscription links that come from
# specific domains (e.g., astrobyte.org). Configure as a comma-separated list.
DASHBOARD_SUBSCRIPTION_ALLOWED_DOMAINS = [
    d.strip().lower()
    for d in os.environ.get("DASHBOARD_SUBSCRIPTION_ALLOWED_DOMAINS", "astrobyte.org").split(",")
    if d.strip()
]
DASHBOARD_SUBSCRIPTION_DOMAIN_ENFORCE = (
    os.environ.get("DASHBOARD_SUBSCRIPTION_DOMAIN_ENFORCE", "true").lower() == "true"
)

# Purchase: automatic discounts (VIP / global events)
# 15% since 2026-07-13 (Pasha: "change the vip discount to 15 percent only").
VIP_PURCHASE_DISCOUNT_ENABLED = os.environ.get("VIP_PURCHASE_DISCOUNT_ENABLED", "true").lower() == "true"
try:
    VIP_PURCHASE_DISCOUNT_PERCENT = int(os.environ.get("VIP_PURCHASE_DISCOUNT_PERCENT", "15"))
except Exception:
    VIP_PURCHASE_DISCOUNT_PERCENT = 15
VIP_PURCHASE_DISCOUNT_PERCENT = max(0, min(VIP_PURCHASE_DISCOUNT_PERCENT, 90))

# JSON list of global discounts applied to everyone, e.g.:
#   [{"percent":10,"label_en":"New Year","label_fa":"تخفیف نوروز"}]
GLOBAL_PURCHASE_DISCOUNTS: list = []
try:
    import json as _json

    raw = (os.environ.get("GLOBAL_PURCHASE_DISCOUNTS_JSON", "") or "").strip()
    if raw:
        parsed = _json.loads(raw)
        if isinstance(parsed, list):
            for item in parsed:
                if not isinstance(item, dict):
                    continue
                pct = item.get("percent", 0)
                try:
                    pct = int(pct)
                except Exception:
                    pct = 0
                pct = max(0, min(pct, 90))
                if pct <= 0:
                    continue
                GLOBAL_PURCHASE_DISCOUNTS.append(
                    {
                        "percent": pct,
                        "label_en": str(item.get("label_en") or item.get("label") or "Discount"),
                        "label_fa": str(item.get("label_fa") or item.get("label") or "تخفیف"),
                    }
                )
except Exception:
    GLOBAL_PURCHASE_DISCOUNTS = []
