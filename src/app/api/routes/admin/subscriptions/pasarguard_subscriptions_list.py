from datetime import datetime, timedelta, timezone

from ..common import *  # noqa: F403

# Frontend sort keys → panel UserSortOption strings. The panel 400s on unknown
# sort values, so UI input never passes through raw (probed live 2026-07-20).
_SORT_MAP = {
    "created": "-created_at",
    "created_asc": "created_at",
    "expire": "expire",
    "expire_desc": "-expire",
    "used": "-used_traffic",
    "used_asc": "used_traffic",
    "username": "username",
    "username_desc": "-username",
    "online": "-online_at",
}

_STATUS_VALUES = {"active", "disabled", "limited", "expired", "on_hold"}


def _transform_panel_user(u: dict) -> dict:
    """Panel user object → the flat card shape the admin UIs render."""
    used_traffic = u.get('used_traffic', 0) or 0
    data_limit = u.get('data_limit', 0) or 0
    used_gb = used_traffic / (1024**3) if used_traffic else 0
    limit_gb = data_limit / (1024**3) if data_limit else 0

    expire_ts = u.get('expire')
    expire_date = None
    days_left = None
    if expire_ts:
        expire_dt = datetime.fromtimestamp(expire_ts, tz=timezone.utc)
        expire_date = expire_dt.isoformat()
        days_left = (expire_dt - datetime.now(timezone.utc)).days

    created_ts = u.get('created_at')
    created_date = None
    if created_ts:
        try:
            created_date = created_ts if isinstance(created_ts, str) else datetime.fromtimestamp(created_ts, tz=timezone.utc).isoformat()
        except Exception:
            created_date = None

    online_at = u.get('online_at')
    is_online = False
    last_online = None
    if online_at:
        try:
            if isinstance(online_at, str):
                online_dt = datetime.fromisoformat(online_at.replace('Z', '+00:00'))
            else:
                online_dt = datetime.fromtimestamp(online_at, tz=timezone.utc)
            if online_dt.tzinfo is None:
                online_dt = online_dt.replace(tzinfo=timezone.utc)
            is_online = (datetime.now(timezone.utc) - online_dt) < timedelta(minutes=2)
            last_online = online_at if isinstance(online_at, str) else online_dt.isoformat()
        except Exception:
            pass

    return {
        "id": u.get('id', 0),
        "username": u.get('username', ''),
        "status": u.get('status', 'unknown'),
        "used_traffic_gb": round(used_gb, 2),
        "data_limit_gb": round(limit_gb, 2) if limit_gb > 0 else None,
        "expire": expire_ts,
        "expire_date": expire_date,
        "days_left": days_left,
        "created_at": created_date,
        "is_online": is_online,
        "last_online": last_online,
        "note": u.get('note', ''),
        "data_limit_reset_strategy": u.get('data_limit_reset_strategy', ''),
        "inbounds": u.get('inbounds', {}),
        # PasarGuard device cap (0/None = unlimited) — editable from the panel UI
        "hwid_limit": u.get('hwid_limit'),
    }


async def handle_admin_subscriptions(request: web.Request):
    """Subscriptions list, server-driven: ONE panel call per page.

    Pagination, search, sort, and status filtering all proxy to the PasarGuard
    /api/users endpoint natively (2026-07-20 — replaces the full 3k-user walk
    that took 3s+ per request and re-sorted everything in Python).
    """
    try:
        try:
            page = max(1, int(request.query.get('page', 1)))
        except ValueError:
            page = 1
        try:
            limit = min(2000, max(1, int(request.query.get('limit', 100))))
        except ValueError:
            limit = 100
        search = request.query.get('search', '').strip()
        sort_key = request.query.get('sort', 'created')
        sort_order = request.query.get('order', '')  # legacy asc/desc modifier
        status = request.query.get('status', '').strip()

        # Legacy callers sent sort=created&order=asc style; fold into one key.
        if sort_order == 'asc' and sort_key in ("created", "expire", "used", "username"):
            asc_alias = {"created": "created_asc", "expire": "expire", "used": "used_asc", "username": "username"}
            sort_key = asc_alias[sort_key]
        elif sort_order == 'desc' and sort_key == 'expire':
            sort_key = 'expire_desc'
        panel_sort = _SORT_MAP.get(sort_key, "-created_at")

        # 'Expiry (soon)' quirk: the panel sorts NULL expire first on ascending,
        # so the 55 never-expiring users would bury page 1 (old client-side sort
        # put them last). Excluding them from just this sort keeps the workflow
        # — finding who expires next — intact; they appear in every other sort.
        extra = {"expire_after": "1970-01-01T00:00:01+00:00"} if panel_sort == "expire" else None

        offset = (page - 1) * limit
        data = await pasarguard_api.get_all_users(
            offset=offset,
            limit=limit,
            search=search or None,
            sort=panel_sort,
            status=status if status in _STATUS_VALUES else None,
            extra_params=extra,
        )
        users = data.get("users", []) or []
        total_count = int(data.get("total") or 0)

        subs_data = [_transform_panel_user(u) for u in users]

        # Panel-wide counters for the stats strip — one cheap /api/system call
        # instead of walking every user to count actives/onlines client-side.
        stats = None
        try:
            sysstats = await pasarguard_api.get_system_stats()
            if isinstance(sysstats, dict):
                stats = {
                    "total": sysstats.get("total_user"),
                    "active": sysstats.get("active_users", sysstats.get("users_active")),
                    "online": sysstats.get("online_users"),
                }
        except Exception:
            stats = None

        return web.json_response({
            "ok": True,
            "users": subs_data,
            "subscriptions": subs_data,  # Alias for compatibility
            "total": total_count,
            "page": page,
            "limit": limit,
            "stats": stats,
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error", "detail": str(e)}, status=500)
