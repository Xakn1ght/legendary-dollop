from aiohttp import web

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.api.schemas import StartChargeRequest, validate_request
from app.core.settings import CHARGE_PRESET_PACKAGES
from app.database import crud
from app.database.models import AsyncSessionLocal
from app.services.flows.charge import start_charge_order
from app.services.flows.errors import FlowError

_ERROR_STATUS = {
    "subscription_not_found": 404,
    "unauthorized": 403,
    "failed_to_fetch_traffic": 500,
}


async def handle_start_charge(request: web.Request):
    """
    Start a charge order for an existing subscription.
    Body: {
        subscription_id: int,
        package: string (package name),
        use_credit: boolean,
        charge_type: string ('normal', 'normal_5gb_limit', 'booking') - optional, defaults to 'normal',
        auto_renewal: boolean,
        renewal_template: string (optional)
    }
    """
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

    validated, error = validate_request(StartChargeRequest, data)
    if error:
        return web.json_response(error, status=400)

    async with AsyncSessionLocal() as session:
        user = await crud.get_user(session, user_chat_id)
        if not user:
            return web.json_response({"ok": False, "error": "not_registered"}, status=403)

        try:
            result = await start_charge_order(
                session,
                user,
                subscription_id=validated.subscription_id,
                package_name=validated.package,
                charge_type=validated.charge_type,
                use_credit=validated.use_credit,
                renewal_template=validated.renewal_template if validated.auto_renewal else None,
                status="draft",
            )
        except FlowError as e:
            body = {"ok": False, "error": e.code, "message": str(e)}
            if e.code == "traffic_above_5gb":
                body["remaining_gb"] = getattr(e, "remaining_gb", None)
            return web.json_response(body, status=_ERROR_STATUS.get(e.code, 400))

        pkg_info = CHARGE_PRESET_PACKAGES[validated.package]
        resp_data = {
            "ok": True,
            "order": {
                "id": result.charge_request.id,
                "subscription_id": validated.subscription_id,
                "package": validated.package,
                "package_gb": pkg_info.get("gb", 0),
                "package_days": pkg_info.get("days", 0),
                "total_price": result.charge_request.price,
                "credit_used": result.credit_used,
                "final_price": result.final_price,
                "charge_type": validated.charge_type,
                "remaining_gb": result.remaining_gb,
            },
        }

        resp = web.json_response(resp_data)
        if new_session_token:
            set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
        return resp
