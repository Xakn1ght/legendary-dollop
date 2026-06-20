"""Admin panel login: Telegram 2FA verification."""

from datetime import datetime, timedelta

from aiogram import Bot
from aiohttp import web

from app.api.schemas import AdminLoginRequest, AdminVerify2FARequest, validate_request
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

from .. import state as st

import logging

logger = logging.getLogger(__name__)


async def handle_admin_verify_2fa(request: web.Request):
    """
    Verify 2FA code and complete login
    
    POST /api/admin/verify-2fa
    Body: { "chat_id": "123456", "code": "123456" }
    """
    ip = st._get_client_ip(request)
    ua = request.headers.get("User-Agent", "")
    
    try:
        data = await request.json()
    except Exception:
        return web.json_response({
            "ok": False,
            "error": "invalid_json",
            "message": "Invalid request body"
        }, status=400)
    
    # Validate input using Pydantic schema
    validated, error = validate_request(AdminVerify2FARequest, data)
    if error:
        return web.json_response(error, status=400)
    
    chat_id_str = validated.chat_id
    code = validated.code
    
    try:
        # Convert username to chat_id if needed (@ prefix already stripped by schema)
        try:
            chat_id = int(chat_id_str)
        except ValueError:
            # Username provided - convert to ADMIN_ID
            if ADMIN_USERNAME and chat_id_str.lower() == ADMIN_USERNAME.lower():
                chat_id = ADMIN_ID
            else:
                return web.json_response({
                    "ok": False,
                    "error": "invalid_chat_id",
                    "message": "Invalid credentials"
                }, status=400)
        
        pending = st._pending_2fa.get(chat_id)
        if not pending:
            return web.json_response({
                "ok": False,
                "error": "nost._pending_2fa",
                "message": "No pending 2FA verification. Please login again."
            }, status=400)
        
        # Check expiration
        if datetime.utcnow() > pending['expires']:
            del st._pending_2fa[chat_id]
            return web.json_response({
                "ok": False,
                "error": "code_expired",
                "message": "2FA code has expired. Please login again."
            }, status=400)
        
        # Check attempts
        if pending['attempts'] >= 3:
            del st._pending_2fa[chat_id]
            st._record_login_attempt(ip)
            return web.json_response({
                "ok": False,
                "error": "too_many_attempts",
                "message": "Too many failed attempts. Please login again."
            }, status=400)
        
        # Verify code
        if code != pending['code']:
            pending['attempts'] += 1
            return web.json_response({
                "ok": False,
                "error": "invalid_code",
                "message": f"Invalid code. {3 - pending['attempts']} attempts remaining."
            }, status=400)
        
        # Success - create session
        del st._pending_2fa[chat_id]
        session = st._create_session(chat_id, ip, ua)
        
        logger.info(f"[ADMIN AUTH] 2FA verified, session created for admin {chat_id} from IP {ip}")
        
        response = web.json_response({
            "ok": True,
            "expires_at": session['expires_at'],
            # Fallback for clients where third-party cookies are blocked (Telegram Web).
            # Frontend may keep this IN MEMORY and send it via Authorization header.
            "token": session['token'],
            # CSRF token: frontend must send it in X-CSRF-Token on state-changing requests.
            "csrf_token": session.get("csrf_token"),
            "user": {
                "chat_id": chat_id,
                "name": "Admin",
                "role": "super_admin"
            }
        })
        # Set HttpOnly cookie for XSS protection.
        # IMPORTANT: Telegram Web (web.telegram.org) is a cross-site embed. Use SameSite=None
        # on HTTPS so cookies are sent on fetch/XHR and survive tab/iframe reloads.
        is_https, samesite = st._admin_cookie_attrs(request)
        response.set_cookie(
            st._ADMIN_SESSION_COOKIE,
            session['token'],
            httponly=True,
            secure=is_https,
            samesite=samesite,
            max_age=ADMIN_SESSION_EXPIRY_HOURS * 60 * 60,
            path='/'
        )
        # CSRF cookie (readable by JS; paired with X-CSRF-Token header)
        try:
            response.set_cookie(
                st._ADMIN_CSRF_COOKIE,
                str(session.get("csrf_token") or ""),
                httponly=False,
                secure=is_https,
                samesite=samesite,
                max_age=ADMIN_SESSION_EXPIRY_HOURS * 60 * 60,
                path='/',
            )
        except Exception:
            pass
        return response
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({
            "ok": False,
            "error": "server_error"
        }, status=500)
