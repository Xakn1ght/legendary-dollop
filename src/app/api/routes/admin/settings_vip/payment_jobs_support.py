from ..common import *  # noqa: F403


async def handle_admin_get_payment_settings(request: web.Request):
    """Get payment card settings"""
    try:
        from app.core.settings import PAYMENT_CARD_HOLDER, PAYMENT_CARD_NUMBER
        return web.json_response({
            "ok": True,
            "card_number": PAYMENT_CARD_NUMBER,
            "card_holder": PAYMENT_CARD_HOLDER
        })
    except Exception as e:
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_admin_update_payment_settings(request: web.Request):
    """Update payment card settings"""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)
    
    # Validate input using Pydantic schema
    validated, error = validate_request(AdminUpdatePaymentSettingsRequest, data)
    if error:
        return web.json_response(error, status=400)
    
    try:
        from app.core.settings import save_payment_settings
        save_payment_settings(validated.card_number, validated.card_holder)
        
        return web.json_response({"ok": True, "message": "Payment settings updated"})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_admin_get_job_schedules(request: web.Request):
    """Get job schedules"""
    try:
        from app.core.settings import JOB_SCHEDULES
        return web.json_response({"ok": True, "schedules": JOB_SCHEDULES})
    except Exception as e:
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_admin_update_job_schedules(request: web.Request):
    """Update job schedules"""
    try:
        from app.core.settings import JOB_SCHEDULES, save_job_schedules
        data = await request.json()
        schedules = data.get("schedules")
        if schedules and isinstance(schedules, dict):
            JOB_SCHEDULES.update(schedules)
            save_job_schedules()
        return web.json_response({"ok": True, "schedules": JOB_SCHEDULES})
    except Exception as e:
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_admin_get_support_settings(request: web.Request):
    """Get support settings"""
    try:
        from app.core.settings import ISPS, SUPPORT_CATEGORIES, TROUBLESHOOTER_STEPS
        return web.json_response({
            "ok": True,
            "categories": SUPPORT_CATEGORIES,
            "isps": ISPS,
            "troubleshooter_steps": TROUBLESHOOTER_STEPS
        })
    except Exception as e:
        return web.json_response({"ok": False, "error": "server_error"}, status=500)
