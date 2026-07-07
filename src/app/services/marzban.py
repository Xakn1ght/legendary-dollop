import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional

import aiohttp

from app.core.paths import core_path
from app.core.redis_config import cache
from app.core.settings import MARZBAN_BASE_URL, MARZBAN_PASSWORD, MARZBAN_USERNAME, PASARGUARD_GROUP_IDS
from app.utils.logger import log_api_call, log_error

# Panel-load shield. Every read surface (dashboard list/overview, bot menus, the
# notify + renewal jobs) funnels through get_fast_user_info, so one short-TTL Redis
# cache here caps panel traffic at ~1 request per user per TTL no matter how many
# places poll. Mutations invalidate their user's entry immediately, so post-payment
# screens still show fresh numbers. Redis down → cache no-ops and we fall through
# to the panel exactly as before.
USER_INFO_CACHE_TTL = 90       # seconds; live usage % may lag at most this much
USAGE_CHART_CACHE_TTL = 600    # 7-day usage chart changes slowly

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


class MarzbanAPI:
    def __init__(self):
        self.base_url = MARZBAN_BASE_URL
        self.username = MARZBAN_USERNAME
        self.password = MARZBAN_PASSWORD
        self._access_token: Optional[str] = None
        self._session: Optional[aiohttp.ClientSession] = None
        # Prevent concurrent logins when multiple jobs request headers at once
        self._login_lock: asyncio.Lock = asyncio.Lock()

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
            self._session = aiohttp.ClientSession(timeout=timeout)
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
                        log_api_call("marzban", "login", True, duration)
                        return True
                    else:
                        error_text = await response.text()
                        log_api_call("marzban", "login", False, duration, status_code=response.status, error=error_text)
                        log_error(Exception(f"Marzban login failed: {response.status} - {error_text}"),
                                 {"operation": "marzban_login", "status_code": response.status})
                        return False

        except Exception as e:
            duration = time.time() - start_time
            log_api_call("marzban", "login", False, duration, error=str(e))
            log_error(e, {"operation": "marzban_login"})
            return False

    async def _get_headers(self):
        if not self._access_token:
            await self._login()
        return {"Authorization": f"Bearer {self._access_token}"}

    async def _inbounds_for_new_user(self) -> dict:
        """Load configured inbounds and drop any tag missing on the Marzban panel."""
        with open(core_path("inbounds.json"), "r", encoding="utf-8") as f:
            configured = json.load(f)
        try:
            session = await self._get_session()
            headers = await self._get_headers()
            url = f"{self.base_url}/api/inbounds"
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    return configured
                live = await response.json()
            live_tags: set[str] = set()
            for proto, entries in (live or {}).items():
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    if isinstance(entry, dict) and entry.get("tag"):
                        live_tags.add(str(entry["tag"]))
            filtered: dict[str, list[str]] = {}
            for proto, tags in (configured or {}).items():
                if not isinstance(tags, list):
                    continue
                kept = [t for t in tags if t in live_tags]
                if kept:
                    filtered[proto] = kept
            return filtered or configured
        except Exception:
            return configured

    async def add_user(self, username: str, data_limit_gb: int, expire_days: int,
                       on_hold_days: int | None = None):
        import time
        start_time = time.time()
        await self.invalidate_user_info(username)
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
                        log_api_call("marzban", "add_user", True, duration, username=username)
                        return result
                    else:
                        # Treat "already exists" as a safe idempotent success
                        if response.status == 409:
                            error_details = await response.text()
                            if "already exists" in error_details.lower():
                                # Fetch existing user and proceed without logging as error
                                log_api_call("marzban", "add_user", True, duration, username=username, already_exists=True)
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
                                    log_api_call("marzban", "add_user", True, retry_duration, username=username, retry=True)
                                    return result
                        
                        error_details = await response.text()
                        log_api_call("marzban", "add_user", False, duration, username=username, 
                                   status_code=response.status, error=error_details)
                        log_error(Exception(f"Failed to add user {username}: {response.status} - {error_details}"), 
                                 {"operation": "marzban_add_user", "username": username, "status_code": response.status})
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
                            log_api_call("marzban", "add_user", True, duration, username=username, recovered=True)
                            return result
                        # If it still fails, fall through to generic error handling below
                        error_details = await response.text()
                        log_api_call("marzban", "add_user", False, duration, username=username, 
                                   status_code=response.status, error=error_details, recovered=True)
                        return None
                raise
                    
        except Exception as e:
            duration = time.time() - start_time
            log_api_call("marzban", "add_user", False, duration, username=username, error=str(e))
            log_error(e, {"operation": "marzban_add_user", "username": username})
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

    async def get_subscription_url(self, username: str):
        user_info = await self.get_user_info(username)
        if user_info:
            return user_info.get("subscription_url")
        return None

    async def delete_user(self, username: str):
        await self.invalidate_user_info(username)
        session = await self._get_session()
        url = f"{self.base_url}/api/user/{username}"
        headers = await self._get_headers()
        
        # PasarGuard answers 204 No Content; classic Marzban answered 200.
        async with session.delete(url, headers=headers) as response:
            if response.status in (200, 204):
                return True
            else:
                if response.status == 401:
                    await self._login()
                    headers = await self._get_headers()
                    async with session.delete(url, headers=headers) as retry_response:
                        if retry_response.status in (200, 204):
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
            log_error(e, {"operation": "marzban_get_subscription_info", "url": url})
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
        """Drop the cached info/usage for a user after any panel mutation."""
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

    async def reset_user_traffic_bytes(self, username: str, new_data_limit_bytes: int, new_expire_ts: int):
        """
        Reset user traffic via Marzban and then set new limits.

        Marzban does not reliably accept `used_traffic` updates via `PUT /api/user/{username}`.
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
                                {"operation": "marzban_reset_traffic", "username": username, "status_code": retry_resp.status},
                            )
                            return False
                else:
                    log_error(
                        Exception(f"Failed to reset traffic for {username}: {resp.status} - {await resp.text()}"),
                        {"operation": "marzban_reset_traffic", "username": username, "status_code": resp.status},
                    )
                    return False

        # Extend data limit and expiration
        modify_url = f"{self.base_url}/api/user/{username}"
        payload = {
            "data_limit": max(int(new_data_limit_bytes or 0), 0),
            "expire": max(int(new_expire_ts or 0), 0),
            "status": "active",
            "data_limit_reset_strategy": "no_reset",
        }

        async with session.put(modify_url, headers=headers, json=payload) as resp:
            if resp.status in (200, 204):
                return True
            # Attempt to handle token expiration and retry once for the modification
            if resp.status == 401:
                await self._login()
                headers = await self._get_headers()
                async with session.put(modify_url, headers=headers, json=payload) as retry_resp:
                    if retry_resp.status in (200, 204):
                        return True
                    log_error(
                        Exception(
                            f"Failed to modify user after reset for {username} after retry: {retry_resp.status} - {await retry_resp.text()}"
                        ),
                        {"operation": "marzban_modify_after_reset", "username": username, "status_code": retry_resp.status},
                    )
                    return False

            log_error(
                Exception(f"Failed to modify user after reset for {username}: {resp.status} - {await resp.text()}"),
                {"operation": "marzban_modify_after_reset", "username": username, "status_code": resp.status},
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
        async with session.put(url, headers=headers, json={"status": status}) as resp:
            return resp.status in (200, 204)

    async def revoke_user_subscription(self, username: str) -> bool:
        await self.invalidate_user_info(username)
        session = await self._get_session()
        headers = await self._get_headers()
        url = f"{self.base_url}/api/user/{username}/revoke_sub"
        async with session.post(url, headers=headers) as resp:
            if resp.status in (200, 204):
                return True
            if resp.status == 401:
                await self._login()
                headers = await self._get_headers()
                async with session.post(url, headers=headers) as retry_resp:
                    return retry_resp.status in (200, 204)
            return False

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
                    if isinstance(stats, dict) and "total_user" not in stats and "active_users" in stats:
                        parts = ("active_users", "disabled_users", "expired_users", "limited_users", "on_hold_users")
                        stats["total_user"] = sum(int(stats.get(k) or 0) for k in parts)
                        stats["users_active"] = stats.get("active_users")
                    return stats
                return None
        except Exception as e:
            print(f"Error fetching system stats: {e}")
            return None
    
    async def get_all_users(self, offset: int = 0, limit: int = 100, search: str = None):
        """Get all users from Marzban with pagination"""
        session = await self._get_session()
        url = f"{self.base_url}/api/users"
        headers = await self._get_headers()
        
        params = {
            'offset': offset,
            'limit': limit
        }
        if search:
            params['search'] = search
        
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
        """Update a user in Marzban"""
        session = await self._get_session()
        url = f"{self.base_url}/api/user/{username}"
        headers = await self._get_headers()
        headers['Content-Type'] = 'application/json'
        
        try:
            async with session.put(url, headers=headers, json=update_data) as resp:
                if resp.status == 200:
                    return True
                print(f"Error updating user {username}: status {resp.status}")
                return False
        except Exception as e:
            print(f"Error updating user {username}: {e}")
            return False

    async def close(self):
        # Ensure we fully reset state so next call can recreate cleanly
        await self._reset_http()

marzban_api = MarzbanAPI()
