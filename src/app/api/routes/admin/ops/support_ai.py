"""Admin control for the support assistant: switch, budget, knowledge records.

Mirrors `ops/sms.py` — same shape, same auditing. Nothing here can make the
assistant say something new by itself: a knowledge record is created as a
DRAFT and only becomes customer-visible after an explicit approve.
"""
from aiohttp import web

from app.services.audit import record_audit


async def handle_admin_support_ai_get(request: web.Request):
    """GET /api/admin/support-ai — switch state, provider/budget status,
    knowledge records and the recent [SUPPORT-AI] log lines."""
    try:
        from app.services import support_ai, support_knowledge, support_provider
        from app.services.support_assist import support_ai_enabled

        try:
            records = support_knowledge.store().list_records()
        except Exception:
            records = []

        log_lines = []
        try:
            from app.core.paths import repo_root

            log_file = repo_root() / "logs" / "bot.log"
            if log_file.exists():
                with open(log_file, encoding="utf-8", errors="replace") as f:
                    tail = f.readlines()[-4000:]
                log_lines = [ln.rstrip() for ln in tail
                             if "[SUPPORT-AI]" in ln or "[SUPPORT-KB]" in ln][-80:]
        except Exception:
            log_lines = []

        return web.json_response({
            "ok": True,
            "enabled": bool(support_ai_enabled()),
            "provider_configured": bool(support_provider.available()),
            "providers": support_provider.configured_providers(),
            "budget": support_provider.budget_status(),
            "corpus": support_ai.corpus_summary(),
            "knowledge_summary": support_ai.knowledge_summary(),
            "records": records,
            "log": log_lines,
        })
    except Exception:
        import traceback

        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_admin_support_ai_set(request: web.Request):
    """POST /api/admin/support-ai {enabled: bool} — turn the assistant on/off.

    Refuses to switch on with no provider configured: it would look armed and
    answer nothing.
    """
    try:
        data = await request.json()
        enabled = bool(data.get("enabled"))

        from app.services import support_provider
        from app.services.support_assist import set_support_ai_enabled, support_ai_enabled

        if enabled and not support_provider.available():
            return web.json_response(
                {"ok": False, "error": "no_provider_configured"}, status=400)

        set_support_ai_enabled(enabled)
        await record_audit(
            request, "support_ai.enable" if enabled else "support_ai.disable",
            target_type="support_ai",
            summary=f"Support assistant {'ENABLED' if enabled else 'disabled'}")
        return web.json_response({"ok": True, "enabled": bool(support_ai_enabled())})
    except Exception:
        import traceback

        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_admin_support_ai_knowledge(request: web.Request):
    """POST /api/admin/support-ai/knowledge — create, approve, reject, resolve
    or delete one knowledge record.

    Body: {action, id?, kind?, title?, body?, expires_ts?, priority?}.
    A created record is always a DRAFT; only `approve` makes it visible to
    customers, and that is audited separately from the draft.
    """
    try:
        data = await request.json()
        action = str(data.get("action") or "").strip()

        from app.services import support_knowledge

        store = support_knowledge.store()
        if store.write_blocked:
            return web.json_response(
                {"ok": False, "error": "knowledge_store_read_only",
                 "detail": store.error}, status=409)

        actor = str(data.get("actor") or "admin")
        if action == "create":
            record = store.create_draft(
                kind=str(data.get("kind") or "faq"),
                title=str(data.get("title") or ""),
                body=str(data.get("body") or ""),
                scope=data.get("scope") or None,
                start_ts=data.get("start_ts"),
                expires_ts=data.get("expires_ts"),
                priority=int(data.get("priority") or 50),
                creator=actor,
                meta=data.get("meta") or None)
        elif action in ("approve", "reject", "resolve", "delete"):
            record_id = str(data.get("id") or "")
            if not record_id:
                return web.json_response({"ok": False, "error": "id_required"}, status=400)
            if action == "approve":
                record = store.approve(record_id, actor=actor,
                                       expected_version=data.get("expected_version"))
            elif action == "reject":
                record = store.reject(record_id, actor=actor)
            elif action == "resolve":
                record = store.resolve(record_id, actor=actor)
            else:
                record = {"id": record_id, "deleted": store.delete(record_id, actor=actor)}
        else:
            return web.json_response({"ok": False, "error": "unknown_action"}, status=400)

        await record_audit(
            request, f"support_ai.knowledge.{action}",
            target_type="support_knowledge", target_id=record.get("id"),
            summary=str(data.get("title") or record.get("title") or "")[:120])
        return web.json_response({"ok": True, "record": record})
    except ValueError as exc:
        return web.json_response({"ok": False, "error": "invalid", "detail": str(exc)},
                                 status=400)
    except Exception:
        import traceback

        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)
