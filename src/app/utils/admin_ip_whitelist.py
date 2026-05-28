import json
import os

from aiohttp import web

from app.core.settings import ADMIN_IP_WHITELIST_PATH, TRUST_PROXY_HEADERS


def _default_state() -> dict:
    return {"enabled": False, "ips": []}


def load_whitelist() -> dict:
    try:
        if not os.path.exists(ADMIN_IP_WHITELIST_PATH):
            return _default_state()
        with open(ADMIN_IP_WHITELIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        enabled = bool(data.get("enabled", False))
        ips = data.get("ips", [])
        if not isinstance(ips, list):
            ips = []
        ips = [str(ip).strip() for ip in ips if str(ip).strip()]
        return {"enabled": enabled, "ips": ips}
    except Exception:
        return _default_state()


def save_whitelist(enabled: bool, ips: list[str]) -> None:
    try:
        os.makedirs(os.path.dirname(ADMIN_IP_WHITELIST_PATH), exist_ok=True)
        data = {"enabled": bool(enabled), "ips": ips}
        with open(ADMIN_IP_WHITELIST_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        return


def get_client_ip(request: web.Request) -> str:
    if TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
    peername = request.transport.get_extra_info("peername")
    if peername:
        return peername[0]
    return "unknown"


def is_ip_allowed(ip: str) -> bool:
    state = load_whitelist()
    if not state.get("enabled"):
        return True
    return ip in (state.get("ips") or [])


def update_whitelist(enabled: bool | None, ips: list[str] | None) -> dict:
    state = load_whitelist()
    if enabled is not None:
        state["enabled"] = bool(enabled)
    if ips is not None:
        state["ips"] = [str(ip).strip() for ip in ips if str(ip).strip()]
    save_whitelist(bool(state.get("enabled")), list(state.get("ips") or []))
    return state
