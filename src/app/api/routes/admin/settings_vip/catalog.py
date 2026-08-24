from __future__ import annotations

import json
import os

from app.core.settings.bootstrap import CORE_DIR

from ..common import *  # noqa: F403


async def handle_admin_get_plans(request: web.Request):
    """Get all subscription plans"""
    try:
        plans_path = str(CORE_DIR / "plans.json")

        if os.path.exists(plans_path):
            with open(plans_path, 'r', encoding='utf-8') as f:
                plans = json.load(f)
        else:
            from app.core.settings import PLANS
            plans = PLANS
        
        # Convert to list format for easier UI handling. The editor only edits
        # price/gb/days, but the extra catalog flags are echoed back so the UI
        # can show them and so nothing looks like it silently vanished.
        plans_list = []
        for name, data in plans.items():
            row = {
                "name": name,
                "price": data.get("price", 0),
                "gb": data.get("gb", 0),
                "days": data.get("days", 30),
            }
            for extra in ("vip_only", "min_months", "name_en", "badge_label", "badge_type", "route", "free"):
                if extra in data:
                    row[extra] = data[extra]
            plans_list.append(row)
        
        return web.json_response({"ok": True, "plans": plans_list})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_admin_update_plans(request: web.Request):
    """Update subscription plans"""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)
    
    # Validate input using Pydantic schema
    validated, error = validate_request(AdminUpdatePlansRequest, data)
    if error:
        return web.json_response(error, status=400)
    
    try:
        # MERGE, never replace. The editor only owns price/gb/days; every other
        # catalog flag (vip_only, min_months, name_en, badges, route...) must
        # survive a save. Rebuilding the entry from scratch here used to strip
        # vip_only + min_months off the three VIP plans on the first admin save,
        # which silently un-gated them and dropped their 2-month minimum.
        from app.core.settings import PLANS

        plans_dict = {}
        for plan in validated.plans:
            merged = dict(PLANS.get(plan.name) or {})
            merged.update({"price": plan.price, "gb": plan.gb, "days": plan.days})
            plans_dict[plan.name] = merged
        
        plans_path = str(CORE_DIR / "plans.json")
        with open(plans_path, 'w', encoding='utf-8') as f:
            json.dump(plans_dict, f, ensure_ascii=False, indent=2)

        # Mutate the in-memory catalog in place so checkout/pricing use the new
        # prices immediately — the file alone doesn't take effect until restart,
        # so GET showed new prices while purchases still charged the old ones.
        PLANS.clear()
        PLANS.update(plans_dict)

        return web.json_response({"ok": True, "message": "Plans updated successfully"})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


# The separate charge-package catalog is RETIRED (2026-07-18 ONE-catalog law):
# a top-up IS a purchase plan applied to an existing sub, so the charge-package
# editor endpoints were removed — edit PLANS instead.
