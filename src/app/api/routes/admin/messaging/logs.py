from ..common import *  # noqa: F403


async def handle_admin_logs(request: web.Request):
    # Return last N lines of the log file. Anchor to the repo root — the old
    # relative "logs/bot.log" resolved against CWD (src/ per run instructions),
    # so it always returned "Log file not found" (audit fix).
    try:
        from app.core.paths import repo_root
        log_path = repo_root() / "logs" / "bot.log"
        lines = []
        try:
            with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = [ln.rstrip('\n') for ln in f.readlines()[-100:]]
        except FileNotFoundError:
            lines = ["Log file not found"]

        return web.json_response({"ok": True, "logs": lines})
    except Exception:
        return web.json_response({"ok": False, "error": "server_error"}, status=500)
