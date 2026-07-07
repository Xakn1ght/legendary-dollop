"""Admin panel login: password step."""

from datetime import datetime, timedelta

from aiogram import Bot
from aiohttp import web

from app.api.schemas import AdminLoginRequest, validate_request
from app.core.settings import (
    ADMIN_2FA_ENABLED,
    ADMIN_BOT_TOKEN,
    ADMIN_ID,
    ADMIN_PANEL_PASSWORD_HASH,
    ADMIN_SESSION_EXPIRY_HOURS,
    ADMIN_USERNAME,
    needs_password_migration,
    verify_admin_password,
)

from ... import state as st

import logging

logger = logging.getLogger(__name__)


async def handle_admin_login(request: web.Request):
    """
    Admin login endpoint with security measures

    POST /api/admin/login
    Body: { "chat_id": "123456", "password": "secret" }

    Returns:
    - Success: { "ok": true, "requires_2fa": true/false, "user": {...} }
    - Failure: { "ok": false, "error": "...", "lockout_seconds": N }
    """
    ip = st._get_client_ip(request)
    ua = request.headers.get("User-Agent", "")

    is_limited, remaining = st._is_rate_limited(ip)
    if is_limited:
        return web.json_response(
            {
                "ok": False,
                "error": "too_many_attempts",
                "message": f"Too many login attempts. Try again in {remaining} seconds.",
                "lockout_seconds": remaining,
            },
            status=429,
        )

    try:
        data = await request.json()
    except Exception:
        st._record_login_attempt(ip)
        return web.json_response({"ok": False, "error": "invalid_json", "message": "Invalid request body"}, status=400)

    validated, error = validate_request(AdminLoginRequest, data)
    if error:
        st._record_login_attempt(ip)
        return web.json_response(error, status=400)

    chat_id_str = validated.chat_id
    password = validated.password

    try:
        chat_id = None

        try:
            chat_id = int(chat_id_str)
        except ValueError:
            if ADMIN_USERNAME and chat_id_str.lower() == ADMIN_USERNAME.lower():
                chat_id = ADMIN_ID
            else:
                st._record_login_attempt(ip)
                logger.warning(f"[ADMIN AUTH] Failed login - invalid username: {chat_id_str}")
                return web.json_response(
                    {"ok": False, "error": "invalid_credentials", "message": "Invalid credentials"}, status=401
                )

        if chat_id != ADMIN_ID:
            st._record_login_attempt(ip)
            logger.warning(f"[ADMIN AUTH] Failed login attempt from IP {ip} - wrong chat_id: {chat_id}")
            return web.json_response({"ok": False, "error": "invalid_credentials", "message": "Invalid credentials"}, status=401)

        if not ADMIN_PANEL_PASSWORD_HASH:
            logger.critical("[ADMIN AUTH] CRITICAL: No ADMIN_PANEL_PASSWORD_HASH set. Login blocked until configured.")
            return web.json_response(
                {"ok": False, "error": "not_configured", "message": "Admin panel is not configured. Set ADMIN_PANEL_PASSWORD_HASH in .env"},
                status=503,
            )

        if not verify_admin_password(password, ADMIN_PANEL_PASSWORD_HASH):
            st._record_login_attempt(ip)
            logger.warning(f"[ADMIN AUTH] Failed login attempt from IP {ip} - wrong password")
            return web.json_response(
                {"ok": False, "error": "invalid_credentials", "message": "Invalid credentials"}, status=401
            )

        if needs_password_migration(ADMIN_PANEL_PASSWORD_HASH):
            st._migrate_password_hash(password)

        if ADMIN_2FA_ENABLED:
            code = st._generate_2fa_code()
            expires = datetime.utcnow() + timedelta(minutes=5)

            st._pending_2fa[chat_id] = {"code": code, "expires": expires, "ip": ip, "attempts": 0}

            if not ADMIN_BOT_TOKEN:
                return web.json_response(
                    {"ok": False, "error": "2fa_config_error", "message": "Admin bot not configured"}, status=500
                )

            try:
                admin_bot = Bot(token=ADMIN_BOT_TOKEN)
                await admin_bot.send_message(
                    chat_id,
                    f"🔐 **کد ورود پنل ادمین**\n\n"
                    f"کد: `{code}`\n\n"
                    f"⏱ این کد تا ۵ دقیقه معتبر است.\n"
                    f"🌐 IP: `{ip}`\n\n"
                    f"⚠️ اگر شما درخواست ورود نکردید، این پیام را نادیده بگیرید.",
                    parse_mode="Markdown",
                )
                await admin_bot.session.close()
            except Exception as e:
                logger.warning(f"[ADMIN AUTH] Failed to send 2FA code: {e}")
                return web.json_response(
                    {"ok": False, "error": "2fa_send_failed", "message": "Failed to send 2FA code. Check Telegram."},
                    status=500,
                )

            logger.info(f"[ADMIN AUTH] 2FA code sent to admin {chat_id} from IP {ip}")

            return web.json_response({"ok": True, "requires_2fa": True, "message": "2FA code sent to your Telegram"})

        session = st._create_session(chat_id, ip, ua)
        logger.info(f"[ADMIN AUTH] Successful login from IP {ip}")
        try:
            from app.services.audit import record_audit

            await record_audit(request, "auth.login", target_type="session",
                               summary=f"login from {ip}")
        except Exception:
            pass

        response = web.json_response(
            {
                "ok": True,
                "requires_2fa": False,
                "expires_at": session["expires_at"],
                "token": session["token"],
                "csrf_token": session.get("csrf_token"),
                "user": {"chat_id": chat_id, "name": "Admin", "role": "super_admin"},
            }
        )
        is_https, samesite = st._admin_cookie_attrs(request)
        response.set_cookie(
            st._ADMIN_SESSION_COOKIE,
            session["token"],
            httponly=True,
            secure=is_https,
            samesite=samesite,
            max_age=ADMIN_SESSION_EXPIRY_HOURS * 60 * 60,
            path="/",
        )
        try:
            response.set_cookie(
                st._ADMIN_CSRF_COOKIE,
                str(session.get("csrf_token") or ""),
                httponly=False,
                secure=is_https,
                samesite=samesite,
                max_age=ADMIN_SESSION_EXPIRY_HOURS * 60 * 60,
                path="/",
            )
        except Exception:
            pass
        return response

    except Exception:
        import traceback

        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error", "message": "An error occurred"}, status=500)
