"""Earnings ("درآمد من") — the referral cash-out story on the Tasks page.

Read model + saved payout card. The withdraw action itself stays on the
existing /wallet/cashout endpoint (flow service owns all eligibility rules);
this module only *shows* the state and stores the destination card.
Spec: docs/design-specs/specs/2026-07-08-earnings-cashback-card-design.md
"""
import logging
import re
import traceback

from aiohttp import web
from sqlalchemy import desc
from sqlalchemy.future import select

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.core.rewards_config import CASHOUT_MIN_AMOUNT_TOMAN, REFERRAL_STORE_CREDIT_CAP_TOMAN
from app.database import crud
from app.database.models import AsyncSessionLocal, CashoutRequest
from app.services.flows.cashout import CASHOUT_MIN_ACTIVE_REFERRALS, count_active_referrals
from app.services.flows.earnings import ensure_promoter_unlock, referral_store_credit_earned

logger = logging.getLogger(__name__)

_CARD_RE = re.compile(r"^\d{16}$")


def mask_card(card: str | None) -> str | None:
    if not card or len(card) < 4:
        return None
    return "•••• •••• •••• " + card[-4:]


async def handle_dashboard_earnings(request: web.Request):
    """GET — everything the earnings card renders, one payload."""
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        async with AsyncSessionLocal() as session:
            user = await crud.get_user(session, user_chat_id)
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)

            # Stamps promoter_unlocked_at the first time the gate is met —
            # opening the earnings card is enough to flip cash-back mode on.
            unlocked = await ensure_promoter_unlock(session, user)
            active = await count_active_referrals(session, user.id)
            credit_earned = await referral_store_credit_earned(session, user.id)
            payouts = (
                await session.execute(
                    select(CashoutRequest)
                    .where(CashoutRequest.user_id == user.id)
                    .order_by(desc(CashoutRequest.requested_at))
                    .limit(3)
                )
            ).scalars().all()

            resp = web.json_response(
                {
                    "ok": True,
                    "active_referrals": active,
                    "gate": CASHOUT_MIN_ACTIVE_REFERRALS,
                    "unlocked": unlocked,
                    # Two-stage model: store credit (in-app, capped) vs cash.
                    "credit_earned_toman": credit_earned,
                    "credit_cap_toman": REFERRAL_STORE_CREDIT_CAP_TOMAN,
                    "credit_toman": int(getattr(user, "credit", 0) or 0),
                    "cash_balance_toman": int(getattr(user, "cashback_balance", 0) or 0),
                    "min_cashout_toman": CASHOUT_MIN_AMOUNT_TOMAN,
                    "card_masked": mask_card(getattr(user, "payout_card", None)),
                    "recent_payouts": [
                        {
                            "id": p.id,
                            "amount_toman": int(p.amount),
                            "status": p.status,
                            "created_at": p.requested_at.isoformat() if p.requested_at else None,
                        }
                        for p in payouts
                    ],
                }
            )
            if new_session_token:
                set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
            return resp
    except Exception as e:
        traceback.print_exc()
        logger.error(f"Error fetching earnings: {e}")
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_dashboard_earnings_card(request: web.Request):
    """POST {card} — save/replace the payout destination card (16 digits)."""
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

    card = re.sub(r"[\s-]", "", str(data.get("card") or ""))
    # Persian/Arabic-Indic digits arrive from fa keyboards — normalize first.
    card = card.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    if not _CARD_RE.match(card):
        return web.json_response({"ok": False, "error": "invalid_card"}, status=400)

    try:
        async with AsyncSessionLocal() as session:
            user = await crud.get_user(session, user_chat_id)
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)
            user.payout_card = card
            await session.commit()

            resp = web.json_response({"ok": True, "card_masked": mask_card(card)})
            if new_session_token:
                set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
            return resp
    except Exception as e:
        traceback.print_exc()
        logger.error(f"Error saving payout card: {e}")
        return web.json_response({"ok": False, "error": "server_error"}, status=500)
