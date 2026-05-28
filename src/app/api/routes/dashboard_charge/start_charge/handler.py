from datetime import datetime

from aiohttp import web

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.api.routes.dashboard_charge.common import GB
from app.core.settings import CHARGE_PRESET_PACKAGES
from app.database import crud
from app.database.models import AsyncSessionLocal, ChargeRequest, Subscription
from app.services.marzban import marzban_api


async def handle_start_charge(request: web.Request):
    """
    Start a charge order for an existing subscription.
    Body: {
        subscription_id: int,
        package: string (package name),
        use_credit: boolean,
        charge_type: string ('normal', 'normal_5gb_limit', 'booking') - optional, defaults to 'normal'
    }
    """
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

    subscription_id = data.get("subscription_id")
    package_name = data.get("package", "")
    use_credit = data.get("use_credit", False)
    charge_type = data.get("charge_type", "normal")
    auto_renewal = data.get("auto_renewal", False)
    renewal_template = data.get("renewal_template", None)

    if not subscription_id:
        return web.json_response({"ok": False, "error": "missing_subscription_id"}, status=400)

    if package_name not in CHARGE_PRESET_PACKAGES:
        return web.json_response(
            {"ok": False, "error": "invalid_package", "message": "Selected package does not exist"}, status=400
        )

    async with AsyncSessionLocal() as session:
        user = await crud.get_user(session, user_chat_id)
        if not user:
            return web.json_response({"ok": False, "error": "not_registered"}, status=403)

        sub = await session.get(Subscription, subscription_id)
        if not sub:
            return web.json_response({"ok": False, "error": "subscription_not_found"}, status=404)
        if sub.user_id != user.id:
            return web.json_response({"ok": False, "error": "unauthorized"}, status=403)
        if sub.status != "active":
            return web.json_response({"ok": False, "error": "subscription_not_active"}, status=400)

        user_info = await marzban_api.get_user_info(sub.marzban_username)
        if not user_info:
            return web.json_response(
                {
                    "ok": False,
                    "error": "failed_to_fetch_traffic",
                    "message": "Could not fetch subscription status from server",
                },
                status=500,
            )

        data_limit = user_info.get("data_limit", 0) or 0
        used_traffic = user_info.get("used_traffic", 0) or 0
        remaining_bytes = max(data_limit - used_traffic, 0)
        remaining_gb = remaining_bytes / GB

        if remaining_gb > 5 and charge_type == "normal":
            return web.json_response(
                {
                    "ok": False,
                    "error": "traffic_above_5gb",
                    "message": "You have more than 5GB remaining. Please choose an option.",
                    "remaining_gb": remaining_gb,
                },
                status=400,
            )

        pkg_info = CHARGE_PRESET_PACKAGES[package_name]
        total_price = pkg_info.get("price", 0)
        traffic_bytes = pkg_info.get("gb", 0) * GB
        extra_days = pkg_info.get("days", 0)

        credit_used = 0
        if use_credit and user.credit > 0:
            credit_used = min(user.credit, total_price)

        final_price = total_price - credit_used

        charge_req = ChargeRequest(
            subscription_id=subscription_id,
            user_id=user.id,
            traffic_bytes=traffic_bytes,
            extra_days=extra_days,
            price=total_price,
            charge_type=charge_type,
            status="draft",
            created_at=datetime.utcnow(),
        )
        session.add(charge_req)
        await session.flush()

        if credit_used > 0:
            await crud.deduct_credit(session, user.id, credit_used)

        if auto_renewal and renewal_template:
            from app.core.settings import PLANS

            renewal_plan_info = PLANS.get(renewal_template, {})
            await crud.update_subscription_renewal(
                session,
                subscription_id,
                renewal_paid=True,
                renewal_template=renewal_template,
                renewal_price=renewal_plan_info.get("price"),
                renewal_requested_at=datetime.utcnow(),
            )

        await session.commit()
        await session.refresh(charge_req)

        resp_data = {
            "ok": True,
            "order": {
                "id": charge_req.id,
                "subscription_id": subscription_id,
                "package": package_name,
                "package_gb": pkg_info.get("gb", 0),
                "package_days": extra_days,
                "total_price": total_price,
                "credit_used": credit_used,
                "final_price": final_price,
                "charge_type": charge_type,
                "remaining_gb": remaining_gb,
            },
        }

        resp = web.json_response(resp_data)
        if new_session_token:
            set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
        return resp
