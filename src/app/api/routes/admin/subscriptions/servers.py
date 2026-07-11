from ..common import *  # noqa: F403


async def handle_admin_servers(request: web.Request):
    """Get servers/nodes from PasarGuard"""
    try:
        # Get nodes from PasarGuard
        nodes = await pasarguard_api.get_nodes()
        
        # Get system stats for traffic
        system_stats = await pasarguard_api.get_system_stats()
        
        servers = []
        
        # If we got nodes, format them
        if nodes:
            for node in nodes:
                servers.append({
                    "id": node.get("id", 0),
                    "name": node.get("name", "Unknown"),
                    "location": node.get("address", "Unknown"),
                    "ip": node.get("address", "N/A"),
                    "traffic": format_bytes(node.get("usage", {}).get("uplink", 0) + node.get("usage", {}).get("downlink", 0)) if node.get("usage") else "N/A",
                    "active": node.get("status") == "connected" or node.get("status") is None,
                    "status": node.get("status", "unknown")
                })
        else:
            # Fallback: show main server status from system stats
            if system_stats:
                total_traffic = system_stats.get("total_user", 0)
                servers.append({
                    "id": 1,
                    "name": "Main Server",
                    "location": "Primary",
                    "ip": pasarguard_api.base_url.replace("https://", "").replace("http://", "").split(":")[0] if pasarguard_api.base_url else "N/A",
                    "traffic": format_bytes(total_traffic) if total_traffic else "N/A",
                    "active": True,
                    "status": "connected"
                })
            else:
                # No connection to PasarGuard
                servers.append({
                    "id": 1,
                    "name": "Main Server",
                    "location": "Unknown",
                    "ip": "N/A",
                    "traffic": "N/A",
                    "active": False,
                    "status": "offline"
                })
        
        return web.json_response({
            "ok": True,
            "servers": servers,
            "system_stats": system_stats
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({
            "ok": True,
            "servers": [{
                "id": 1,
                "name": "Main Server",
                "location": "Unknown",
                "ip": "N/A",
                "traffic": "N/A",
                "active": False,
                "status": "error"
            }],
            "error": str(e)
        })

def format_bytes(bytes_value):
    """Format bytes to human readable string"""
    if bytes_value is None or bytes_value == 0:
        return "0 B"
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    unit_index = 0
    value = float(bytes_value)
    while value >= 1024 and unit_index < len(units) - 1:
        value /= 1024
        unit_index += 1
    return f"{value:.1f} {units[unit_index]}"
