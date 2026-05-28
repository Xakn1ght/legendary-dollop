from ..common import *  # noqa: F403


async def handle_admin_ip_whitelist_get(request: web.Request):
    """Get admin IP whitelist settings"""
    try:
        state = load_whitelist()
        return web.json_response({"ok": True, "whitelist": state})
    except Exception:
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_admin_ip_whitelist_update(request: web.Request):
    """Update admin IP whitelist settings"""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)
    
    validated, error = validate_request(AdminIPWhitelistRequest, data)
    if error:
        return web.json_response(error, status=400)
    
    ips = validated.ips
    if ips is not None:
        # Validate IPs
        cleaned = []
        for ip in ips:
            try:
                ipaddress.ip_address(ip)
                cleaned.append(ip)
            except ValueError:
                return web.json_response({"ok": False, "error": "invalid_ip", "ip": ip}, status=400)
        ips = cleaned
    
    state = update_whitelist(validated.enabled, ips)
    return web.json_response({"ok": True, "whitelist": state})
