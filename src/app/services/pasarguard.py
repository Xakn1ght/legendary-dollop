import asyncio
import base64
import re
import time as _time
from datetime import datetime, timedelta
from typing import Optional

import aiohttp

from app.core.redis_config import cache
from app.core.settings import (
    PASARGUARD_API_KEY,
    PASARGUARD_BASE_URL,
    PASARGUARD_GROUP_IDS,
    PASARGUARD_PASSWORD,
    PASARGUARD_USERNAME,
)
from app.utils.logger import log_api_call, log_error

# Panel-load shield. Every read surface (dashboard list/overview, bot menus, the
# notify + renewal jobs) funnels through get_fast_user_info, so one short-TTL Redis
# cache here caps panel traffic at ~1 request per user per TTL no matter how many
# places poll. Mutations invalidate their user's entry immediately, so post-payment
# screens still show fresh numbers. Redis down → cache no-ops and we fall through
# to the panel exactly as before.
USER_INFO_CACHE_TTL = 90       # seconds; live usage % may lag at most this much
USAGE_CHART_CACHE_TTL = 600    # 7-day usage chart changes slowly

# Any single panel HTTP call slower than this logs a warning with the duration
# and (token-redacted) endpoint, so panel degradation is visible in the logs
# before users complain. Timeouts count too — they are the truest slow signal.
SLOW_PANEL_WARN_SECONDS = 4.0

# In-process cache of the panel's user-template list (template-based creation).
TEMPLATE_LIST_TTL = 600  # re-list at most every 10 min; admin edits show up then

# ---- PasarGuard (2026-07 panel migration) compatibility layer -------------
# The panel is now PasarGuard, a Marzban fork with a few breaking API changes.
# Everything below normalizes responses back to the classic Marzban shapes the
# rest of the codebase (and its tests) were written against:
#   * expire:      ISO-8601 string  -> epoch int (classic)
#   * create user: group_ids based  -> replaces per-user inbounds/proxies
#   * /api/nodes:  {"nodes": [...]} -> bare list
#   * /api/system: renamed counters -> classic total_user/users_active aliases
#   * usage:       {"stats": {...}} -> classic [{node_name, used_traffic}] list
#   * 201/204 now legitimate success codes on create/delete


def _expire_to_epoch(value):
    """PasarGuard returns expire as ISO-8601 ('2026-07-08T13:22:26Z'); the whole
    codebase does epoch-seconds math on it. None/0 (never expires) pass through."""
    if value is None or isinstance(value, (int, float)):
        return value
    try:
        s = str(value).strip()
        if s.isdigit():
            return int(s)
        return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
    except Exception:
        return None


def _norm_user_payload(data):
    """Normalize a PasarGuard user/sub-info dict to classic Marzban keys in place."""
    if isinstance(data, dict) and "expire" in data:
        data["expire"] = _expire_to_epoch(data.get("expire"))
    return data


def _info_key(username: str) -> str:
    return f"mz:info:{username}"


def _usage_key(username: str, days: int) -> str:
    return f"mz:usage:{days}d:{username}"


_V3_TOKEN_RE = re.compile(r"v3,(\d+),(\d+)")


def extract_v3_user_id(token: str) -> Optional[int]:
    """PasarGuard v3 share tokens are base64("v3,<panel_user_id>,<ts>") plus a
    hex signature tail. Return the embedded panel user id, or None for classic
    tokens. Pure parse — never a substitute for validating the token."""
    tok = (token or "").strip()
    if not tok.startswith("djM"):  # base64 of "v3" — cheap pre-filter
        return None
    for cut in range(min(len(tok), 40), 7, -1):
        seg = tok[:cut] + "=" * (-cut % 4)
        try:
            decoded = base64.b64decode(seg, validate=True).decode("utf-8", "strict")
        except Exception:
            continue
        m = _V3_TOKEN_RE.fullmatch(decoded)
        if m:
            return int(m.group(1))
    return None


def _redact_panel_path(path: str) -> str:
    """Share-link tokens must not land in logs: /sub/<token>/info → /sub/***/info."""
    return re.sub(r"/sub/[^/]+", "/sub/***", path or "")


def _make_slow_call_tracer() -> aiohttp.TraceConfig:
    """TraceConfig hooked into the panel HTTP session: one warning per call that
    exceeds SLOW_PANEL_WARN_SECONDS (finished or failed), with method, redacted
    path and duration. Instruments every panel call, including the raw
    session.put/post usages in renewal/charge/redemption code."""
    tc = aiohttp.TraceConfig()

    async def _on_start(session, ctx, params):
        ctx.start = _time.monotonic()

    async def _on_end(session, ctx, params):
        dur = _time.monotonic() - getattr(ctx, "start", _time.monotonic())
        if dur >= SLOW_PANEL_WARN_SECONDS:
            from app.utils.logger import bot_logger
            bot_logger.warning(
                f"[PANEL] slow call: {params.method} {_redact_panel_path(params.url.path)} took {dur:.1f}s"
            )

    async def _on_exception(session, ctx, params):
        dur = _time.monotonic() - getattr(ctx, "start", _time.monotonic())
        if dur >= SLOW_PANEL_WARN_SECONDS:
            from app.utils.logger import bot_logger
            bot_logger.warning(
                f"[PANEL] slow call FAILED ({type(params.exception).__name__}): "
                f"{params.method} {_redact_panel_path(params.url.path)} after {dur:.1f}s"
            )

    tc.on_request_start.append(_on_start)
    tc.on_request_end.append(_on_end)
    tc.on_request_exception.append(_on_exception)
    return tc


class PasarGuardAPI:
    # Auth modes (2026-07-20, Pasha-approved API-key switch):
    #   * api_key set   -> every request carries X-Api-Key (PasarGuard 5.1+,
    #     key "astrobyte-app", scoped: users CRUD/reset/revoke, templates read,
    #     nodes read/stats, system read). Static — no login, no expiry, so the
    #     per-method 401 retries become harmless no-ops and the raw session.put/
    #     session.post call sites in renewal/charge/redemption code can no
    #     longer fail on a stale token.
    #   * api_key empty -> classic username/password bearer flow with the
    #     _login()/401-retry dance, unchanged (the rollback path: unset
    #     PASARGUARD_API_KEY and restart).
    def __init__(self):
        self.base_url = PASARGUARD_BASE_URL
        self.username = PASARGUARD_USERNAME
        self.password = PASARGUARD_PASSWORD
        self.api_key = PASARGUARD_API_KEY
        self._access_token: Optional[str] = None
        self._session: Optional[aiohttp.ClientSession] = None
        # Prevent concurrent logins when multiple jobs request headers at once
        self._login_lock: asyncio.Lock = asyncio.Lock()
        # (data_limit_bytes, expire_seconds) → template dict; None = never audited
        self._template_map: Optional[dict] = None
        self._template_fetched_at: float = 0.0
        self._template_lock: asyncio.Lock = asyncio.Lock()

    async def _get_session(self) -> aiohttp.ClientSession:
        # aiohttp can end up with a closed connector even if the session object still exists
        if (
            self._session is None
            or self._session.closed
            or getattr(self._session, "connector", None) is None
            or getattr(self._session.connector, "closed", False)
        ):
            # Apply conservative timeouts so scheduled jobs don't hang and get cancelled
            timeout = aiohttp.ClientTimeout(total=12, connect=5, sock_connect=5, sock_read=10)
            self._session = aiohttp.ClientSession(timeout=timeout, trace_configs=[_make_slow_call_tracer()])
        return self._session

    async def _reset_http(self):
        """Reset the underlying HTTP session/token (best-effort)."""
        try:
            if self._session and not self._session.closed:
                await self._session.close()
        except Exception:
            pass
        self._session = None
        self._access_token = None

    async def _login(self):
        # API-key mode: nothing to log in to. Returning True keeps every
        # existing "401 -> _login() -> retry once" branch (here and in the raw
        # call sites) valid: the retry just re-sends the same static header.
        if self.api_key:
            return True
        import time
        start_time = time.time()
        try:
            async with self._login_lock:
                # If another waiter already logged in, reuse the token
                if self._access_token:
                    return True

                session = await self._get_session()
                login_url = f"{self.base_url}/api/admin/token"
                credentials = {"username": self.username, "password": self.password}

                async with session.post(login_url, data=credentials) as response:
                    duration = time.time() - start_time

                    if response.status == 200:
                        data = await response.json()
                        self._access_token = data.get("access_token")
                        log_api_call("pasarguard", "login", True, duration)
                        return True
                    else:
                        error_text = await response.text()
                        log_api_call("pasarguard", "login", False, duration, status_code=response.status, error=error_text)
                        log_error(Exception(f"PasarGuard login failed: {response.status} - {error_text}"),
                                 {"operation": "pasarguard_login", "status_code": response.status})
                        return False

        except Exception as e:
            duration = time.time() - start_time
            log_api_call("pasarguard", "login", False, duration, error=str(e))
            log_error(e, {"operation": "pasarguard_login"})
            return False

    async def _get_headers(self):
        if self.api_key:
            return {"X-Api-Key": self.api_key}
        if not self._access_token:
            await self._login()
        return {"Authorization": f"Bearer {self._access_token}"}

    # NOTE (2026-07-20): _inbounds_for_new_user() removed — dead since the
    # group_ids-based creation migration (inbounds come from group membership;
    # nothing read config/inbounds.json anymore).

    # ---- PasarGuard user templates (2026-07-10 speed work) -----------------
    # Fixed plans whose (data_limit, duration) exactly matches a panel template
    # are created via POST /api/user/from_template — one lightweight call, no
    # inbound filtering, and plan shape managed on the panel. Everything else
    # (custom GB, multi-month scaling, coupon bonus GB, on_hold gifts, missing
    # template) transparently keeps the manual path.

    async def audit_templates(self, force: bool = False) -> dict:
        """Fetch + cache the panel's user templates as {(data_limit_bytes,
        expire_seconds): template}. Only templates that create users equivalent
        to our manual creation qualify: enabled, active, and group_ids exactly
        our PASARGUARD_GROUP_IDS (the panel also holds legacy templates with NO
        groups — those would create config-less dud users). Never hard-fails:
        on any error the map stays as-is (or empty) and creation falls back to
        the manual path."""
        now = _time.monotonic()
        if not force and self._template_map is not None and (now - self._template_fetched_at) < TEMPLATE_LIST_TTL:
            return self._template_map
        async with self._template_lock:
            now = _time.monotonic()
            if not force and self._template_map is not None and (now - self._template_fetched_at) < TEMPLATE_LIST_TTL:
                return self._template_map
            first_audit = self._template_map is None
            new_map: dict = {}
            try:
                session = await self._get_session()
                headers = await self._get_headers()
                url = f"{self.base_url}/api/user_templates"
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 401:
                        await self._login()
                        headers = await self._get_headers()
                        async with session.get(url, headers=headers) as retry:
                            templates = (await retry.json()) if retry.status == 200 else None
                    elif resp.status == 200:
                        templates = await resp.json()
                    else:
                        templates = None
                if not isinstance(templates, list):
                    raise RuntimeError(f"unexpected template list response: {type(templates)}")

                our_groups = set(PASARGUARD_GROUP_IDS)
                for t in templates:
                    if not isinstance(t, dict):
                        continue
                    if t.get("is_disabled") or (t.get("status") or "active") != "active":
                        continue
                    if set(t.get("group_ids") or []) != our_groups:
                        continue
                    if t.get("username_prefix") or t.get("username_suffix"):
                        continue  # would mangle our service names
                    limit = int(t.get("data_limit") or 0)
                    duration = int(t.get("expire_duration") or 0)
                    if limit <= 0 or duration <= 0:
                        continue
                    key = (limit, duration)
                    # Prefer the AstroByte-named template on shape collisions.
                    if key in new_map and not str(t.get("name") or "").startswith("AstroByte"):
                        continue
                    new_map[key] = t

                self._template_map = new_map
                self._template_fetched_at = _time.monotonic()
                if first_audit:
                    from app.utils.logger import bot_logger
                    backed = sorted(
                        f"{limit // (1024 ** 3)}GB/{dur // 86400}d({t.get('name')})"
                        for (limit, dur), t in new_map.items()
                    )
                    bot_logger.info(
                        f"[PANEL] template audit: {len(new_map)} usable template(s): "
                        + (", ".join(backed) if backed else "none — all creations use the manual path")
                    )
            except Exception as e:
                if self._template_map is None:
                    self._template_map = {}
                self._template_fetched_at = _time.monotonic()  # don't re-hammer a sick panel
                log_error(e, {"operation": "pasarguard_template_audit"})
            return self._template_map

    async def _add_user_from_template(self, username: str, template_id: int):
        """POST /api/user/from_template. Returns the normalized user dict, or
        None on any failure (caller falls back to manual creation). 409
        already-exists is treated as idempotent success, same as add_user."""
        session = await self._get_session()
        headers = await self._get_headers()
        url = f"{self.base_url}/api/user/from_template"
        payload = {"user_template_id": int(template_id), "username": username, "note": ""}
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status in (200, 201):
                return _norm_user_payload(await resp.json())
            if resp.status == 409 and "already exists" in (await resp.text()).lower():
                try:
                    return await self.get_user_info(username)
                except Exception:
                    return None
            if resp.status == 401:
                await self._login()
                headers = await self._get_headers()
                async with session.post(url, headers=headers, json=payload) as retry:
                    if retry.status in (200, 201):
                        return _norm_user_payload(await retry.json())
            return None

    async def add_user(self, username: str, data_limit_gb: int, expire_days: int,
                       on_hold_days: int | None = None):
        import time
        start_time = time.time()
        await self.invalidate_user_info(username)

        # Template fast path — only for plain active plans whose exact shape is
        # template-backed on the panel. on_hold gifts can't ride a template.
        if not on_hold_days and data_limit_gb > 0 and expire_days > 0 and float(data_limit_gb).is_integer():
            try:
                tmap = await self.audit_templates()
                template = tmap.get((int(data_limit_gb) * 1024 ** 3, int(expire_days) * 86400))
                if template:
                    result = await self._add_user_from_template(username, template["id"])
                    if result:
                        await self.invalidate_user_info(username)
                        log_api_call("pasarguard", "add_user", True, time.time() - start_time,
                                     username=username, template=template.get("name"))
                        return result
                    # fall through to manual creation on any template failure
                    from app.utils.logger import bot_logger
                    bot_logger.warning(
                        f"[PANEL] from_template failed for {username} "
                        f"(template {template.get('name')}); using manual creation"
                    )
            except Exception as e:
                log_error(e, {"operation": "pasarguard_add_user_template", "username": username})
        try:
            session = await self._get_session()
            url = f"{self.base_url}/api/user"
            headers = await self._get_headers()
            
            # Convert GB to bytes
            data_limit_bytes = data_limit_gb * 1024 * 1024 * 1024
            # Convert days to timestamp
            expire_timestamp = int((datetime.now() + timedelta(days=expire_days)).timestamp()) if expire_days > 0 else 0

            # PasarGuard: inbounds come from group membership. The classic
            # inbounds/proxies payload is still ACCEPTED but creates a user in
            # no group => empty subscription (zero configs) — a silent dud.
            user_data = {
                "data_limit": data_limit_bytes,
                "expire": expire_timestamp,
                "group_ids": list(PASARGUARD_GROUP_IDS),
                "note": "",
                "status": "active",
                "username": username
            }
            # "Days start at first connect": PasarGuard on_hold users sit idle
            # until their client connects once, then the countdown begins.
            # Used for reward free-plans so a gift never burns while unused.
            if on_hold_days and on_hold_days > 0:
                user_data["status"] = "on_hold"
                user_data["expire"] = 0
                user_data["on_hold_expire_duration"] = int(on_hold_days) * 86400
            
            try:
                async with session.post(url, headers=headers, json=user_data) as response:
                    duration = time.time() - start_time
                    
                    if response.status in (200, 201):
                        result = _norm_user_payload(await response.json())
                        await self.invalidate_user_info(username)
                        log_api_call("pasarguard", "add_user", True, duration, username=username)
                        return result
                    else:
                        # Treat "already exists" as a safe idempotent success
                        if response.status == 409:
                            error_details = await response.text()
                            if "already exists" in error_details.lower():
                                # Fetch existing user and proceed without logging as error
                                log_api_call("pasarguard", "add_user", True, duration, username=username, already_exists=True)
                                try:
                                    existing = await self.get_user_info(username)
                                    return existing
                                except Exception:
                                    return None
    
                        # Handle token expiration and retry once
                        if response.status == 401:
                            await self._login()
                            headers = await self._get_headers()
                            async with session.post(url, headers=headers, json=user_data) as retry_response:
                                retry_duration = time.time() - start_time
                                if retry_response.status in (200, 201):
                                    result = _norm_user_payload(await retry_response.json())
                                    log_api_call("pasarguard", "add_user", True, retry_duration, username=username, retry=True)
                                    return result
                        
                        error_details = await response.text()
                        log_api_call("pasarguard", "add_user", False, duration, username=username, 
                                   status_code=response.status, error=error_details)
                        log_error(Exception(f"Failed to add user {username}: {response.status} - {error_details}"), 
                                 {"operation": "pasarguard_add_user", "username": username, "status_code": response.status})
                        return None
            except (aiohttp.ClientConnectionError, RuntimeError) as e:
                # Auto-recover from "Connector is closed"/"Session is closed" once
                if "connector is closed" in str(e).lower() or "session is closed" in str(e).lower():
                    await self._reset_http()
                    session = await self._get_session()
                    headers = await self._get_headers()
                    async with session.post(url, headers=headers, json=user_data) as response:
                        duration = time.time() - start_time
                        if response.status in (200, 201):
                            result = _norm_user_payload(await response.json())
                            log_api_call("pasarguard", "add_user", True, duration, username=username, recovered=True)
                            return result
                        # If it still fails, fall through to generic error handling below
                        error_details = await response.text()
                        log_api_call("pasarguard", "add_user", False, duration, username=username, 
                                   status_code=response.status, error=error_details, recovered=True)
                        return None
                raise
                    
        except Exception as e:
            duration = time.time() - start_time
            log_api_call("pasarguard", "add_user", False, duration, username=username, error=str(e))
            log_error(e, {"operation": "pasarguard_add_user", "username": username})
            return None

    async def get_user_info(self, username: str):
        url = f"{self.base_url}/api/user/{username}"
        try:
            session = await self._get_session()
            headers = await self._get_headers()
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return _norm_user_payload(await response.json())
                if response.status == 401:
                    await self._login()
                    headers = await self._get_headers()
                    async with session.get(url, headers=headers) as retry_response:
                        if retry_response.status == 200:
                            return _norm_user_payload(await retry_response.json())
                return None
        except (aiohttp.ClientConnectionError, RuntimeError) as e:
            if "connector is closed" in str(e).lower() or "session is closed" in str(e).lower():
                await self._reset_http()
                try:
                    session = await self._get_session()
                    headers = await self._get_headers()
                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            return _norm_user_payload(await response.json())
                        return None
                except Exception:
                    return None
            return None

    async def get_user_info_by_id(self, panel_user_id: int):
        """PasarGuard: GET /api/user/by-id/{id}. One call resolves username +
        full user object when the caller only holds a v3 share token (see
        extract_v3_user_id). Returns None on 404/any failure."""
        url = f"{self.base_url}/api/user/by-id/{int(panel_user_id)}"
        try:
            session = await self._get_session()
            headers = await self._get_headers()
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return _norm_user_payload(await response.json())
                if response.status == 401:
                    await self._login()
                    headers = await self._get_headers()
                    async with session.get(url, headers=headers) as retry_response:
                        if retry_response.status == 200:
                            return _norm_user_payload(await retry_response.json())
                return None
        except Exception:
            return None

    async def delete_user(self, username: str):
        await self.invalidate_user_info(username)
        session = await self._get_session()
        url = f"{self.base_url}/api/user/{username}"
        headers = await self._get_headers()
        
        # PasarGuard answers 204 No Content; classic Marzban answered 200.
        async with session.delete(url, headers=headers) as response:
            if response.status in (200, 204):
                await self.invalidate_user_info(username)
                return True
            else:
                if response.status == 401:
                    await self._login()
                    headers = await self._get_headers()
                    async with session.delete(url, headers=headers) as retry_response:
                        if retry_response.status in (200, 204):
                            await self.invalidate_user_info(username)
                            return True
                return False

    # ------------- Subscription info via share link token --------------

    async def get_subscription_info(self, token: str):
        """Return json of /sub/{token}/info."""
        url = f"{self.base_url}/sub/{token}/info"
        try:
            session = await self._get_session()
            async with session.get(url) as response:
                if response.status == 200:
                    return _norm_user_payload(await response.json())
                return None
        except asyncio.CancelledError:
            # Scheduler/job shutdown or timeout cancellation – treat as transient and return None
            return None
        except (aiohttp.ClientConnectionError, RuntimeError) as e:
            if "connector is closed" in str(e).lower() or "session is closed" in str(e).lower():
                await self._reset_http()
                try:
                    session = await self._get_session()
                    async with session.get(url) as response:
                        if response.status == 200:
                            return _norm_user_payload(await response.json())
                        return None
                except Exception:
                    return None
            return None
        except Exception as e:
            log_error(e, {"operation": "pasarguard_get_subscription_info", "url": url})
            return None

    async def get_subscription_links(self, token: str) -> list:
        """PasarGuard: per-config links moved off the user object to
        /sub/{token}/links (newline-separated). Classic Marzban embedded them
        as user_info['links']."""
        url = f"{self.base_url}/sub/{token}/links"
        try:
            session = await self._get_session()
            async with session.get(url) as response:
                if response.status != 200:
                    return []
                text = await response.text()
                return [ln.strip() for ln in text.splitlines() if ln.strip()]
        except Exception:
            return []

    async def get_subscription_info_from_url(self, sub_url: str):
        """Extract token from a full subscription URL and fetch /sub/{token}/info."""
        try:
            from urllib.parse import urlparse
            path = urlparse(sub_url).path
            # Expecting /sub/{token} or /sub/{token}/info
            parts = [p for p in path.split('/') if p]
            if len(parts) >= 2 and parts[0] == 'sub':
                token = parts[1]
                return await self.get_subscription_info(token)
        except Exception:
            return None
        return None

    async def invalidate_user_info(self, username: str):
        """Drop the cached info/usage for a user around any panel mutation.

        Mutators call this BEFORE the panel write (stop serving stale data now)
        and again AFTER success — a concurrent reader can re-cache the old panel
        state mid-write, and without the second delete that zombie entry would
        survive for the full TTL right after a payment."""
        try:
            await cache.delete(_info_key(username))
            await cache.delete(_usage_key(username, 7))
        except Exception:
            pass

    async def get_fast_user_info(self, username: str, sub_token: Optional[str] = None):
        """Prefer share-link /sub/{token}/info when token present; fallback to admin API.

        Returns a dict compatible with get_user_info keys: used_traffic, data_limit, expire, status, links, subscription_url.
        Results are served from a short-TTL Redis cache (USER_INFO_CACHE_TTL) to
        protect the panel; mutations call invalidate_user_info().
        """
        try:
            cached = await cache.get(_info_key(username))
            if isinstance(cached, dict) and cached:
                return cached
        except Exception:
            pass

        result = None
        if sub_token:
            try:
                data = await self.get_subscription_info(sub_token)
                if data:
                    # Normalize to admin API-like keys. PasarGuard's sub-info
                    # carries neither links nor subscription_url — links come
                    # from /sub/{token}/links, the url we can rebuild locally.
                    from app.utils.logger import bot_logger
                    bot_logger.debug("[USER_INFO] source=share_link", username=username)
                    links = data.get('links') or await self.get_subscription_links(sub_token)
                    result = {
                        'used_traffic': data.get('used_traffic'),
                        'data_limit': data.get('data_limit'),
                        'expire': data.get('expire'),
                        'status': data.get('status'),
                        'links': links,
                        'subscription_url': data.get('subscription_url') or f"/sub/{sub_token}",
                        'online_at': data.get('online_at'),
                    }
            except asyncio.CancelledError:
                return None
        if result is None:
            # Fallback
            from app.utils.logger import bot_logger
            bot_logger.debug("[USER_INFO] source=admin", username=username)
            result = await self.get_user_info(username)
            # Admin user object also lost embedded links on PasarGuard.
            if isinstance(result, dict) and not result.get('links'):
                tok = None
                try:
                    sub_url = result.get('subscription_url') or ''
                    parts = [p for p in sub_url.split('/') if p]
                    if 'sub' in parts:
                        tok = parts[parts.index('sub') + 1]
                except Exception:
                    tok = None
                if tok:
                    result['links'] = await self.get_subscription_links(tok)

        if isinstance(result, dict) and result:
            try:
                await cache.set(_info_key(username), result, ttl=USER_INFO_CACHE_TTL)
            except Exception:
                pass
        return result

    async def _node_name_map(self) -> dict:
        """id -> name for PasarGuard usage stats (keyed by node id there)."""
        try:
            cached = await cache.get("mz:nodenames")
            if isinstance(cached, dict) and cached:
                return cached
        except Exception:
            pass
        out: dict = {}
        try:
            for n in await self.get_nodes():
                if isinstance(n, dict) and n.get("id") is not None:
                    out[str(n["id"])] = str(n.get("name") or f"node-{n['id']}")
        except Exception:
            return out
        try:
            await cache.set("mz:nodenames", out, ttl=USAGE_CHART_CACHE_TTL)
        except Exception:
            pass
        return out

    def _flatten_pg_usage(self, data: dict, node_names: dict) -> list:
        """PasarGuard usage: {"stats": {node_id: [{total_traffic, period_start}...]}}
        → classic [{node_id, node_name, used_traffic}] (window totals per node)."""
        usages = []
        for node_id, points in (data.get("stats") or {}).items():
            total = 0
            for p in points or []:
                try:
                    total += int(p.get("total_traffic") or 0)
                except Exception:
                    continue
            name = node_names.get(str(node_id)) or ("Master" if str(node_id) == "-1" else f"node-{node_id}")
            usages.append({"node_id": node_id, "node_name": name, "used_traffic": total})
        return usages

    async def get_user_usage(self, username: str, days: int = 7):
        """Return usage stats for the last `days` days as a list of dicts with
        node_name & used_traffic (classic Marzban `usages` shape).

        NOTE: this class used to define get_user_usage TWICE — the later
        uncached definition silently shadowed this one. Merged here."""
        try:
            cached = await cache.get(_usage_key(username, days))
            if isinstance(cached, list):
                return cached
        except Exception:
            pass
        from datetime import datetime, timedelta
        end = datetime.utcnow()
        start = end - timedelta(days=days)
        params = {
            "start": start.isoformat(timespec="seconds"),
            "end": end.isoformat(timespec="seconds")
        }
        session = await self._get_session()
        headers = await self._get_headers()
        url = f"{self.base_url}/api/user/{username}/usage"
        async with session.get(url, headers=headers, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                if isinstance(data, dict) and "stats" in data:  # PasarGuard
                    usages = self._flatten_pg_usage(data, await self._node_name_map())
                else:  # classic Marzban
                    usages = data.get("usages", [])
                try:
                    await cache.set(_usage_key(username, days), usages, ttl=USAGE_CHART_CACHE_TTL)
                except Exception:
                    pass
                return usages
            return None

    async def with_next_plan_preserved(self, username: str, payload: dict) -> dict:
        """PasarGuard quirk (live-verified 2026-07-12): a PUT /api/user/{username}
        whose body OMITS ``next_plan`` silently deletes any armed next-plan on
        the panel. Every modify payload must therefore echo the armed plan
        back. Call this right before any PUT to /api/user/{username}.

        - The armed object is echoed verbatim (``next_plan.expire`` stays a raw
          seconds-duration int on read, so the round-trip is loss-free).
        - An explicit ``next_plan`` key in the payload wins — pass ``None`` to
          deliberately clear an armed plan.
        - Fail-open: if the pre-read fails, the payload is returned unchanged
          (identical to pre-guard behavior; nothing arms next_plan yet).
        """
        if "next_plan" in payload:
            return payload
        try:
            info = await self.get_user_info(username)
            armed = (info or {}).get("next_plan")
            if isinstance(armed, dict):
                payload = dict(payload)
                payload["next_plan"] = armed
        except Exception:
            pass
        return payload

    async def reset_user_traffic_bytes(self, username: str, new_data_limit_bytes: int, new_expire_ts: int):
        """
        Reset user traffic via PasarGuard and then set new limits.

        PasarGuard does not reliably accept `used_traffic` updates via `PUT /api/user/{username}`.
        The canonical way to reset usage is `POST /api/user/{username}/reset`.
        """
        await self.invalidate_user_info(username)
        session = await self._get_session()
        headers = await self._get_headers()

        # Reset user traffic
        reset_url = f"{self.base_url}/api/user/{username}/reset"
        async with session.post(reset_url, headers=headers) as resp:
            if resp.status not in (200, 204):
                # Attempt to handle token expiration and retry once for the reset
                if resp.status == 401:
                    await self._login()
                    headers = await self._get_headers()
                    async with session.post(reset_url, headers=headers) as retry_resp:
                        if retry_resp.status not in (200, 204):
                            log_error(
                                Exception(
                                    f"Failed to reset traffic for {username} after retry: {retry_resp.status} - {await retry_resp.text()}"
                                ),
                                {"operation": "pasarguard_reset_traffic", "username": username, "status_code": retry_resp.status},
                            )
                            return False
                else:
                    log_error(
                        Exception(f"Failed to reset traffic for {username}: {resp.status} - {await resp.text()}"),
                        {"operation": "pasarguard_reset_traffic", "username": username, "status_code": resp.status},
                    )
                    return False

        # Extend data limit and expiration
        modify_url = f"{self.base_url}/api/user/{username}"
        payload = await self.with_next_plan_preserved(username, {
            "data_limit": max(int(new_data_limit_bytes or 0), 0),
            "expire": max(int(new_expire_ts or 0), 0),
            "status": "active",
            "data_limit_reset_strategy": "no_reset",
        })

        async with session.put(modify_url, headers=headers, json=payload) as resp:
            if resp.status in (200, 204):
                await self.invalidate_user_info(username)
                return True
            # Attempt to handle token expiration and retry once for the modification
            if resp.status == 401:
                await self._login()
                headers = await self._get_headers()
                async with session.put(modify_url, headers=headers, json=payload) as retry_resp:
                    if retry_resp.status in (200, 204):
                        await self.invalidate_user_info(username)
                        return True
                    log_error(
                        Exception(
                            f"Failed to modify user after reset for {username} after retry: {retry_resp.status} - {await retry_resp.text()}"
                        ),
                        {"operation": "pasarguard_modify_after_reset", "username": username, "status_code": retry_resp.status},
                    )
                    return False

            log_error(
                Exception(f"Failed to modify user after reset for {username}: {resp.status} - {await resp.text()}"),
                {"operation": "pasarguard_modify_after_reset", "username": username, "status_code": resp.status},
            )
            return False

    async def reset_user_traffic(self, username: str, new_data_limit_gb: int, new_expire_days: int):
        """Reset user traffic, set new data limit, and new expiration date."""
        data_limit_bytes = int(new_data_limit_gb) * (1024**3)
        expire_timestamp = int((datetime.now() + timedelta(days=new_expire_days)).timestamp()) if new_expire_days > 0 else 0
        return await self.reset_user_traffic_bytes(username, data_limit_bytes, expire_timestamp)

    async def toggle_user_status(self, username: str, status: str):
        """Set user status (active|disabled). Returns bool."""
        await self.invalidate_user_info(username)
        session = await self._get_session()
        headers = await self._get_headers()
        url = f"{self.base_url}/api/user/{username}"
        payload = await self.with_next_plan_preserved(username, {"status": status})
        async with session.put(url, headers=headers, json=payload) as resp:
            ok = resp.status in (200, 204)
        if ok:
            await self.invalidate_user_info(username)
        return ok

    async def revoke_user_subscription(self, username: str):
        """Rotate the user's share link. PasarGuard answers with the full updated
        user object — return it (truthy) so callers get the NEW subscription_url
        without a follow-up get_user_info round-trip. Falsy return = failure;
        a bare ``True`` remains possible when the panel sends no body."""
        await self.invalidate_user_info(username)
        session = await self._get_session()
        headers = await self._get_headers()
        url = f"{self.base_url}/api/user/{username}/revoke_sub"

        async def _handle(resp):
            if resp.status not in (200, 204):
                return None
            await self.invalidate_user_info(username)
            try:
                data = await resp.json()
                if isinstance(data, dict) and data:
                    return _norm_user_payload(data)
            except Exception:
                pass
            return True

        async with session.post(url, headers=headers) as resp:
            result = await _handle(resp)
            if result is not None:
                return result
            if resp.status == 401:
                await self._login()
                headers = await self._get_headers()
                async with session.post(url, headers=headers) as retry_resp:
                    result = await _handle(retry_resp)
                    return result if result is not None else False
            return False

    async def get_user_hwid_devices(self, panel_user_id: int):
        """GET /api/user/{user_id}/hwids — the user's registered devices
        (PasarGuard 5.1.0, keyed by panel user ID, not username). Returns the
        raw {"hwids": [...], "count": N} dict, or None on any failure so the
        caller can distinguish "no devices" from "panel unreachable"."""
        session = await self._get_session()
        url = f"{self.base_url}/api/user/{int(panel_user_id)}/hwids"
        headers = await self._get_headers()
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data if isinstance(data, dict) else None
                if resp.status == 401:
                    await self._login()
                    headers = await self._get_headers()
                    async with session.get(url, headers=headers) as retry:
                        if retry.status == 200:
                            data = await retry.json()
                            return data if isinstance(data, dict) else None
                return None
        except Exception as e:
            log_error(e, {"operation": "pasarguard_get_hwids", "panel_user_id": panel_user_id})
            return None

    async def get_user_sub_updates(self, username: str, limit: int = 10):
        """GET /api/user/{username}/sub_update — recent subscription/config
        fetches ({"updates": [{created_at, user_agent, ip, hwid}], "count": N}).
        Support triage: which client app the user runs and when it last pulled
        the config. None on any failure."""
        session = await self._get_session()
        url = f"{self.base_url}/api/user/{username}/sub_update"
        headers = await self._get_headers()
        params = {"limit": max(1, min(int(limit), 50))}
        try:
            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data if isinstance(data, dict) else None
                if resp.status == 401:
                    await self._login()
                    headers = await self._get_headers()
                    async with session.get(url, headers=headers, params=params) as retry:
                        if retry.status == 200:
                            data = await retry.json()
                            return data if isinstance(data, dict) else None
                return None
        except Exception as e:
            log_error(e, {"operation": "pasarguard_get_sub_updates", "username": username})
            return None

    async def reconnect_node(self, node_id: int) -> bool:
        """POST /api/node/{node_id}/reconnect — ask the panel to re-establish
        the node connection. CAUTION (probed live 2026-07-21): the panel
        answers 200 {} even for nonexistent node ids, so callers must validate
        the id against get_nodes() first if they need a real existence check."""
        session = await self._get_session()
        url = f"{self.base_url}/api/node/{int(node_id)}/reconnect"
        headers = await self._get_headers()
        try:
            async with session.post(url, headers=headers) as resp:
                if resp.status == 200:
                    return True
                if resp.status == 401:
                    await self._login()
                    headers = await self._get_headers()
                    async with session.post(url, headers=headers) as retry:
                        return retry.status == 200
                log_error(
                    Exception(f"node reconnect failed: {resp.status} - {(await resp.text())[:200]}"),
                    {"operation": "pasarguard_reconnect_node", "node_id": node_id, "status_code": resp.status},
                )
                return False
        except Exception as e:
            log_error(e, {"operation": "pasarguard_reconnect_node", "node_id": node_id})
            return False

    async def get_online_users_series(self, period: str = "hour", start_iso: str | None = None,
                                      end_iso: str | None = None):
        """GET /api/users/counts/online — online-user counts bucketed by
        period. Returns the raw UserCountMetricStatsList dict ({"stats":
        {node_id: [{count, period_start}...]}, "count_during_period": N}) or
        None. SLOW on the panel (~13s for a 24h hourly window, probed live
        2026-07-21) — callers must cache; a per-request 35s timeout overrides
        the session's 12s default."""
        session = await self._get_session()
        url = f"{self.base_url}/api/users/counts/online"
        headers = await self._get_headers()
        params: dict = {"period": period if period in ("minute", "hour", "day", "month") else "hour"}
        if start_iso:
            params["start"] = start_iso
        if end_iso:
            params["end"] = end_iso
        timeout = aiohttp.ClientTimeout(total=35)
        try:
            async with session.get(url, headers=headers, params=params, timeout=timeout) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data if isinstance(data, dict) else None
                if resp.status == 401:
                    await self._login()
                    headers = await self._get_headers()
                    async with session.get(url, headers=headers, params=params, timeout=timeout) as retry:
                        if retry.status == 200:
                            data = await retry.json()
                            return data if isinstance(data, dict) else None
                return None
        except Exception as e:
            log_error(e, {"operation": "pasarguard_online_series", "period": period})
            return None

    async def get_nodes_realtime_stats(self) -> dict:
        """PasarGuard live per-node stats keyed by node id (as str):
        cpu_usage, cpu_cores, mem_used/total, incoming/outgoing_bandwidth_speed,
        uptime. Only connected nodes appear. Empty dict on any failure."""
        session = await self._get_session()
        url = f"{self.base_url}/api/nodes/realtime_stats"
        headers = await self._get_headers()
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data if isinstance(data, dict) else {}
                return {}
        except Exception:
            return {}

    async def get_nodes(self):
        """Get all nodes/servers from the panel as a bare list.
        PasarGuard wraps them: {"nodes": [...], "total": N}."""
        session = await self._get_session()
        url = f"{self.base_url}/api/nodes"
        headers = await self._get_headers()
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, dict):
                        return data.get("nodes", []) or []
                    return data if isinstance(data, list) else []
                return []
        except Exception as e:
            print(f"Error fetching nodes: {e}")
            return []
    
    async def get_system_stats(self):
        """Get system stats. PasarGuard renamed the user counters — alias the
        classic keys the health/ops surfaces read (total_user, users_active)."""
        session = await self._get_session()
        url = f"{self.base_url}/api/system"
        headers = await self._get_headers()
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    stats = await resp.json()
                    if isinstance(stats, dict):
                        # 5.1.0 ships total_user natively again but still never
                        # the classic users_active; older builds shipped neither.
                        # Alias each key independently — the old combined guard
                        # skipped users_active as soon as total_user reappeared
                        # (health card showed "?").
                        if "users_active" not in stats and "active_users" in stats:
                            stats["users_active"] = stats.get("active_users")
                        if "total_user" not in stats and "active_users" in stats:
                            parts = ("active_users", "disabled_users", "expired_users", "limited_users", "on_hold_users")
                            stats["total_user"] = sum(int(stats.get(k) or 0) for k in parts)
                    return stats
                return None
        except Exception as e:
            print(f"Error fetching system stats: {e}")
            return None
    
    async def get_all_users(self, offset: int = 0, limit: int = 100, search: str = None,
                            sort: str = None, status: str = None, extra_params: dict = None):
        """Get all users from PasarGuard with pagination.

        `sort` takes a panel UserSortOption string (e.g. '-created_at', 'expire',
        '-used_traffic', 'username'); `status` a UserStatus value. Both verified
        live 2026-07-20 — invalid sort values 400, so callers map from a fixed
        table rather than passing UI input through. `extra_params` passes other
        documented /api/users filters (expire_after, online, ...) verbatim.
        """
        session = await self._get_session()
        url = f"{self.base_url}/api/users"
        headers = await self._get_headers()
        
        params = {
            'offset': offset,
            'limit': limit
        }
        if search:
            params['search'] = search
        if sort:
            params['sort'] = sort
        if status:
            params['status'] = status
        if extra_params:
            params.update(extra_params)
        
        try:
            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()  # {"users": [...], "total": N}
                    for u in (data.get("users") or []):
                        _norm_user_payload(u)
                    return data
                return {"users": [], "total": 0}
        except Exception as e:
            print(f"Error fetching users: {e}")
            return {"users": [], "total": 0}

    async def get_all_users_paged(self, search: str = None, page_size: int = 500, max_users: int = 50000):
        """Fetch EVERY user by walking the paginated endpoint — replaces the old
        'limit=2000 and hope' pattern that silently truncated large panels."""
        users: list = []
        offset = 0
        while offset < max_users:
            data = await self.get_all_users(offset=offset, limit=page_size, search=search)
            batch = data.get("users", []) or []
            users.extend(batch)
            total = int(data.get("total") or 0)
            offset += page_size
            if len(batch) < page_size or (total and len(users) >= total):
                break
        return users

    async def update_user(self, username: str, update_data: dict) -> bool:
        """Update a user in PasarGuard"""
        await self.invalidate_user_info(username)
        session = await self._get_session()
        url = f"{self.base_url}/api/user/{username}"
        headers = await self._get_headers()
        headers['Content-Type'] = 'application/json'
        update_data = await self.with_next_plan_preserved(username, update_data)

        try:
            async with session.put(url, headers=headers, json=update_data) as resp:
                if resp.status in (200, 204):
                    await self.invalidate_user_info(username)
                    return True
                print(f"Error updating user {username}: status {resp.status}")
                return False
        except Exception as e:
            print(f"Error updating user {username}: {e}")
            return False

    async def close(self):
        # Ensure we fully reset state so next call can recreate cleanly
        await self._reset_http()

pasarguard_api = PasarGuardAPI()
