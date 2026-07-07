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
        
        # Convert to list format for easier UI handling
        plans_list = [
            {"name": name, "price": data.get("price", 0), "gb": data.get("gb", 0), "days": data.get("days", 30)}
            for name, data in plans.items()
        ]
        
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
        # Convert validated list to dict format
        plans_dict = {}
        for plan in validated.plans:
            plans_dict[plan.name] = {
                "price": plan.price,
                "gb": plan.gb,
                "days": plan.days
            }
        
        plans_path = str(CORE_DIR / "plans.json")
        with open(plans_path, 'w', encoding='utf-8') as f:
            json.dump(plans_dict, f, ensure_ascii=False, indent=2)

        # Mutate the in-memory catalog in place so checkout/pricing use the new
        # prices immediately — the file alone doesn't take effect until restart,
        # so GET showed new prices while purchases still charged the old ones.
        from app.core.settings import PLANS
        PLANS.clear()
        PLANS.update(plans_dict)

        return web.json_response({"ok": True, "message": "Plans updated successfully"})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_admin_get_charge_packages(request: web.Request):
    """Get all charge packages"""
    try:
        packages_path = str(CORE_DIR / "charge_packages.json")

        if os.path.exists(packages_path):
            with open(packages_path, 'r', encoding='utf-8') as f:
                packages = json.load(f)
        else:
            from app.core.settings import CHARGE_PRESET_PACKAGES
            packages = CHARGE_PRESET_PACKAGES
        
        # Convert to list format
        packages_list = [
            {"name": name, "price": data.get("price", 0), "gb": data.get("gb", 0), "days": data.get("days", 0)}
            for name, data in packages.items()
        ]
        
        return web.json_response({"ok": True, "packages": packages_list})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_admin_update_charge_packages(request: web.Request):
    """Update charge packages"""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)
    
    # Validate input using Pydantic schema
    validated, error = validate_request(AdminUpdateChargePackagesRequest, data)
    if error:
        return web.json_response(error, status=400)
    
    try:
        # Convert validated list to dict format
        packages_dict = {}
        for pkg in validated.packages:
            packages_dict[pkg.name] = {
                "price": pkg.price,
                "gb": pkg.gb,
                "days": pkg.days
            }
        
        packages_path = str(CORE_DIR / "charge_packages.json")
        with open(packages_path, 'w', encoding='utf-8') as f:
            json.dump(packages_dict, f, ensure_ascii=False, indent=2)

        # In-memory update so the charge flow prices new top-ups correctly
        # without a restart (same staleness bug as plans).
        from app.core.settings import CHARGE_PRESET_PACKAGES
        CHARGE_PRESET_PACKAGES.clear()
        CHARGE_PRESET_PACKAGES.update(packages_dict)

        return web.json_response({"ok": True, "message": "Charge packages updated successfully"})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)
