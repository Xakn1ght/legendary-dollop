"""Shared subscription-management flow: add-by-link / remove-local / revoke.

Replaces the duplicated implementations in ``handlers/user/add_subscription.py`` +
``my_services/handlers/charge_revoke.py`` (bot) and
``api/routes/dashboard_subs/subscriptions`` (webapp).

Canonical rules (stricter of the two old surfaces):
- subscription links must come from an allowed domain when
  ``DASHBOARD_SUBSCRIPTION_DOMAIN_ENFORCE`` is on (previously webapp-only);
- the account must actually exist on Marzban before a row is created
  (previously bot-only — the webapp would create an active row from a bare name);
- revoke / remove require ownership (the bot's revoke button previously accepted
  ANY subscription id with no ownership check).
"""
from __future__ import annotations

import base64
import logging
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import (
    DASHBOARD_SUBSCRIPTION_ALLOWED_DOMAINS,
    DASHBOARD_SUBSCRIPTION_DOMAIN_ENFORCE,
)
from app.database import crud
from app.database.models import Subscription
from app.services.flows.errors import FlowError
from app.services.marzban import marzban_api

logger = logging.getLogger(__name__)

_SUB_TOKEN_RE = re.compile(r"/sub/([^/]+)/?")


@dataclass
class AddSubResult:
    subscription: Subscription
    created: bool   # new row was created
    linked: bool    # existing row was shared to this user via the link table


@dataclass
class RevokeResult:
    new_link: str | None
    new_token: str | None
    user_info: dict | None


# ── link parsing ─────────────────────────────────────────────────────────────────

def _decode_b64_safe(s: str) -> str:
    v = (s or "").strip().replace(" ", "").replace("\n", "").replace("\r", "").replace("\t", "")
    v = v.replace("-", "+").replace("_", "/")
    v += "=" * ((-len(v)) % 4)
    try:
        return base64.b64decode(v).decode("utf-8", "ignore")
    except Exception:
        return ""


def _host_allowed(host: str | None) -> bool:
    if not host:
        return False
    h = host.lower().strip(".")
    for allowed in DASHBOARD_SUBSCRIPTION_ALLOWED_DOMAINS or []:
        a = (allowed or "").lower().strip(".")
        if a and (h == a or h.endswith("." + a)):
            return True
    return False


def extract_token_from_link(raw: str) -> str:
    """Token from a subscription URL (raw or base64-encoded). Raises FlowError
    with code ``disallowed_domain`` / ``invalid_subscription_url``."""
    candidate = (raw or "").strip()
    if not candidate:
        raise FlowError("invalid_subscription_url", "Invalid subscription link")

    decoded = _decode_b64_safe(candidate)
    if decoded and ("/sub/" in decoded or decoded.startswith("http")):
        candidate = decoded.strip()
    if not candidate.startswith(("http://", "https://")):
        candidate = "https://" + candidate.lstrip("/")

    parsed = urlparse(candidate)
    if DASHBOARD_SUBSCRIPTION_DOMAIN_ENFORCE and not _host_allowed(parsed.hostname):
        allowed = ", ".join(DASHBOARD_SUBSCRIPTION_ALLOWED_DOMAINS or [])
        raise FlowError("disallowed_domain", f"Subscription link domain is not allowed. Allowed domains: {allowed}")

    m = _SUB_TOKEN_RE.search(parsed.path or "")
    if not m:
        raise FlowError("invalid_subscription_url", "Invalid subscription link")
    return m.group(1)


# ── flows ────────────────────────────────────────────────────────────────────────

async def add_subscription_by_link(
    session: AsyncSession,
    user,
    *,
    url: str | None = None,
    token: str | None = None,
    username: str | None = None,
) -> AddSubResult:
    """Attach an existing Marzban account to this user's panel.

    Accepts a subscription URL (preferred), a bare token, or a username. In every
    case the account must resolve on Marzban before anything is persisted.
    """
    if url:
        token = extract_token_from_link(url)
    elif DASHBOARD_SUBSCRIPTION_DOMAIN_ENFORCE and not token:
        # With enforcement on, a bare username is not enough — the link proves the
        # user actually holds the subscription URL for an allowed panel.
        raise FlowError("subscription_url_required", "Subscription link is required")

    username_val = (username or "").strip() or None
    if token:
        try:
            info = await marzban_api.get_subscription_info(token)
        except Exception:
            info = None
        if info and not username_val:
            username_val = info.get("username")

    if not username_val:
        raise FlowError("cannot_resolve_username")

    # The account must exist on Marzban (bot behavior; the webapp used to skip this).
    user_info = await marzban_api.get_user_info(username_val)
    if user_info is None:
        raise FlowError("marzban_account_not_found", "No such account on the VPN server")

    existing = await crud.get_subscription_by_username(session, username_val)
    if existing:
        if existing.user_id == user.id:
            return AddSubResult(subscription=existing, created=False, linked=False)
        if existing.user_id is None:
            # Previously detached row — re-attach to this user.
            existing.user_id = user.id
            if token and not existing.sub_token:
                existing.sub_token = token
            await session.commit()
            return AddSubResult(subscription=existing, created=False, linked=False)
        # Shared-account scenario: link without changing ownership.
        await crud.add_subscription_link(session, user.id, existing.id)
        return AddSubResult(subscription=existing, created=False, linked=True)

    sub = await crud.create_subscription(
        db=session,
        user_id=user.id,
        marzban_username=username_val,
        plan="custom",
        receipt_message_id=None,
        referrer_id=None,
        renewal_paid=False,
        price=0,  # externally-added subscriptions have no price
        status="active",
    )
    if token:
        sub.sub_token = token
        await session.commit()
        await session.refresh(sub)
    return AddSubResult(subscription=sub, created=True, linked=False)


async def _get_owned_subscription(session: AsyncSession, user, sub_id: int) -> Subscription:
    sub = await session.get(Subscription, sub_id)
    if not sub:
        raise FlowError("not_found")
    if sub.user_id != user.id:
        raise FlowError("unauthorized")
    return sub


async def remove_local_subscription(session: AsyncSession, user, sub_id: int) -> None:
    """Detach a subscription from this user's panel (no Marzban change).

    Owners are detached from the row; link-table (shared) users get their link row
    removed instead."""
    sub = await session.get(Subscription, sub_id)
    if not sub:
        raise FlowError("not_found")
    if sub.user_id == user.id:
        sub.user_id = None
        await session.commit()
        return
    res = await session.execute(
        text("DELETE FROM subscription_links WHERE user_id = :uid AND subscription_id = :sid"),
        {"uid": user.id, "sid": sub_id},
    )
    await session.commit()
    if getattr(res, "rowcount", 0) == 0:
        raise FlowError("not_found")


async def revoke_subscription(session: AsyncSession, user, sub_id: int) -> RevokeResult:
    """Rotate the subscription link on Marzban. Ownership required — the old bot
    button revoked any subscription id without checking."""
    sub = await _get_owned_subscription(session, user, sub_id)

    ok = await marzban_api.revoke_user_subscription(sub.marzban_username)
    if not ok:
        raise FlowError("revoke_failed")

    info = None
    new_link = None
    new_token = None
    try:
        info = await marzban_api.get_user_info(sub.marzban_username)
        new_link = (info or {}).get("subscription_url")
        if new_link:
            m = _SUB_TOKEN_RE.search(new_link)
            if m:
                new_token = m.group(1)
                sub.sub_token = new_token
                await session.commit()
    except Exception as e:
        logger.error(f"Failed to persist new token after revoke of sub {sub_id}: {e}")

    return RevokeResult(new_link=new_link, new_token=new_token, user_info=info)
