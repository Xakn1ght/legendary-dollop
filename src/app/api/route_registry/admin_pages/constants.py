"""Paths and route lists for the admin SPA shell and legacy redirects."""

LEGACY_ADMIN_PREFIXES: tuple[str, ...] = ("/admin/v1/", "/admin/v2/", "/admin/v3/")

ADMIN_SPA_GET_PATHS: tuple[str, ...] = (
    "/admin/dashboard",
    "/admin/users",
    "/admin/subscriptions",
    "/admin/servers",
    "/admin/receipts",
    "/admin/notifications",
    "/admin/settings",
    "/admin/logs",
)

ADMIN_LEGACY_SUBPAGES: tuple[str, ...] = (
    "dashboard",
    "users",
    "subscriptions",
    "servers",
    "receipts",
    "notifications",
    "settings",
    "logs",
)

LEGACY_VERSIONS: tuple[str, ...] = ("v1", "v2", "v3")
