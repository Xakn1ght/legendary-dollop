from .common import *  # noqa: F403


async def handle_get_charge_packages(request: web.Request):
    """Get available charge packages and payment info"""
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)
    
    packages_list = []
    for name, info in CHARGE_PRESET_PACKAGES.items():
        packages_list.append({
            "name": name,
            "price": info.get("price", 0),
            "gb": info.get("gb", 0),
            "days": info.get("days", 0),
            "discount_percent": info.get("discount_percent", 0),
            "badge_label": info.get("badge_label", None),
            "badge_type": info.get("badge_type", "event")  # event, vip, or custom
        })
    
    # Sort by price
    packages_list.sort(key=lambda x: x["price"])
    
    resp = web.json_response({
        "ok": True,
        "packages": packages_list,
        "payment": {
            "card_number": PAYMENT_CARD_NUMBER,
            "card_holder": PAYMENT_CARD_HOLDER
        }
    })
    if new_session_token:
        set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
    return resp


