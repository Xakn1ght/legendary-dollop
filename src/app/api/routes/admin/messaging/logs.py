from ..common import *  # noqa: F403


async def handle_admin_logs(request: web.Request):
    # Return last N lines of log file
    try:
        log_file = "logs/bot.log"
        lines = []
        try:
            with open(log_file, 'r') as f:
                # Read last 100 lines efficiently-ish
                lines = f.readlines()[-100:]
        except FileNotFoundError:
            lines = ["Log file not found"]
            
        return web.json_response({"ok": True, "logs": lines})
    except Exception:
        return web.json_response({"ok": False, "error": "server_error"}, status=500)
