from app.api.deps import _verify_webapp_auth
from app.utils.admin_bot_helper import resolve_user_bot

from ..common import *  # noqa: F403


async def handle_dashboard_enter_referral(request: web.Request):
    """
    POST /api/dashboard/referrals/enter
    Authenticated user submits a referral code to link themselves to a referrer.
    Returns: {ok, referral_code, referrer_name} or error.
    """
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

    import re
    code = str(data.get("referral_code", "")).strip().upper()
    if not re.match(r'^[A-Z0-9]{6}$', code):
        return web.json_response({"ok": False, "error": "invalid_format"}, status=400)

    try:
        async with AsyncSessionLocal() as session:
            user = await crud.get_user(session, user_chat_id)
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)

            # Already used a referral code?
            existing = await session.execute(
                select(Referral).filter(Referral.referee_id == user.id)
            )
            if existing.scalars().first():
                return web.json_response({"ok": False, "error": "already_used"}, status=400)

            referrer = await crud.get_user_by_referral_code(session, code)
            if not referrer:
                return web.json_response({"ok": False, "error": "invalid_code"}, status=400)
            if referrer.chat_id == user_chat_id:
                return web.json_response({"ok": False, "error": "own_code"}, status=400)

            await crud.create_referral(session, referrer_id=referrer.id, referee_id=user.id)

            # Notify referrer
            try:
                bot = resolve_user_bot(request.app.get('bot'))
                if bot:
                    lang = getattr(referrer, 'language', 'fa') or 'fa'
                    name = user.full_name or user.username or str(user.chat_id)
                    msg = (
                        f"🎉 <b>{name}</b> با کد دعوت شما به AstroByte پیوست!\n"
                        "🎁 اگر خرید انجام دهند، پاداش دریافت می‌کنید."
                        if lang == 'fa' else
                        f"🎉 <b>{name}</b> joined AstroByte using your referral code!\n"
                        "🎁 You'll earn a reward when they make a purchase."
                    )
                    await bot.send_message(referrer.chat_id, msg, parse_mode="HTML")
            except Exception:
                pass

            resp = web.json_response({
                "ok": True,
                "referral_code": user.referral_code,
                "referrer_name": referrer.full_name or referrer.username or "a friend",
            })
            if new_session_token:
                set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
            return resp

    except Exception:
        import traceback; traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)
