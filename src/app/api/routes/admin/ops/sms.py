from aiohttp import web

from app.services.audit import record_audit


async def handle_admin_sms_control_get(request: web.Request):
    """GET /api/admin/sms-control — arm state, config sanity, pooled deposits,
    and recent [SMS] log lines so the whole system is visible from the panel."""
    try:
        from app.services.sms_ingest import (
            SMS_SOURCE_CHAT_ID,
            _load_deposits,
            sms_enabled,
        )

        deposits = []
        try:
            for d in sorted(_load_deposits(), key=lambda x: -int(x.get("ts", 0)))[:50]:
                deposits.append({
                    "ts": d.get("ts"),
                    "amount_rial": d.get("amount"),
                    "tracking": d.get("tracking"),
                    "card_last4": d.get("card_last4") or d.get("last4"),
                    "matched": d.get("matched"),
                })
        except Exception:
            deposits = []

        log_lines = []
        try:
            from app.core.paths import repo_root

            log_file = repo_root() / "logs" / "bot.log"
            if log_file.exists():
                with open(log_file, encoding="utf-8", errors="replace") as f:
                    tail = f.readlines()[-4000:]
                log_lines = [ln.rstrip() for ln in tail if "[SMS]" in ln][-80:]
        except Exception:
            log_lines = []

        return web.json_response({
            "ok": True,
            "enabled": bool(sms_enabled()),
            "source_chat_configured": bool(SMS_SOURCE_CHAT_ID),
            "deposits": deposits,
            "log": log_lines,
        })
    except Exception:
        import traceback

        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_admin_sms_control_set(request: web.Request):
    """POST /api/admin/sms-control {enabled: bool} — arm/disarm the auto-approver.
    Money-critical toggle: always audited."""
    try:
        data = await request.json()
        enabled = bool(data.get("enabled"))

        from app.services.sms_ingest import SMS_SOURCE_CHAT_ID, set_sms_enabled, sms_enabled

        if enabled and not SMS_SOURCE_CHAT_ID:
            return web.json_response(
                {"ok": False, "error": "source_chat_not_configured"}, status=400
            )

        set_sms_enabled(enabled)
        await record_audit(
            request, "sms.arm" if enabled else "sms.disarm",
            target_type="sms", summary=f"SMS auto-approve {'ARMED' if enabled else 'disarmed'}",
        )
        return web.json_response({"ok": True, "enabled": bool(sms_enabled())})
    except Exception:
        import traceback

        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)
