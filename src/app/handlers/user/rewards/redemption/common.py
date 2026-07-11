"""Shared router and low-level helpers for reward redemption."""

from aiogram import Router

from app.services.pasarguard import pasarguard_api

router = Router()


async def _patch_panel_user(username: str, patch_data: dict) -> bool:
    """Low-level helper to PATCH a PasarGuard user; retries once on 401.
    Invalidates the short-TTL panel-info cache so reward GB/days show up
    immediately in the dashboard/bot views."""
    await pasarguard_api.invalidate_user_info(username)
    session_http = await pasarguard_api._get_session()
    url = f"{pasarguard_api.base_url}/api/user/{username}"
    headers = await pasarguard_api._get_headers()
    ok = False
    async with session_http.put(url, headers=headers, json=patch_data) as response:
        if response.status in (200, 204):
            ok = True
        elif response.status == 401:
            await pasarguard_api._login()
            headers = await pasarguard_api._get_headers()
            async with session_http.put(url, headers=headers, json=patch_data) as retry_resp:
                ok = retry_resp.status in (200, 204)
    if ok:
        await pasarguard_api.invalidate_user_info(username)
    return ok


def _parse_reward_callback(data: str):
    """Return tuple (rtype, reward_id, star_cnt|None) or (None, None, None)"""
    parts = data.split("_")
    if len(parts) < 3:
        return None, None, None

    if len(parts) >= 4 and parts[1] == "enhanced" and parts[2] == "star":
        try:
            star_cnt = int(parts[3])
            rid = int(parts[4])
            return "star", rid, star_cnt
        except (ValueError, IndexError):
            return None, None, None

    rtype = parts[1]
    if rtype == "star":
        if len(parts) != 4:
            return None, None, None
        try:
            star_cnt = int(parts[2])
            rid = int(parts[3])
            return rtype, rid, star_cnt
        except (ValueError, IndexError):
            return None, None, None
    try:
        rid = int(parts[2])
        return rtype, rid, None
    except (ValueError, IndexError):
        return None, None, None
