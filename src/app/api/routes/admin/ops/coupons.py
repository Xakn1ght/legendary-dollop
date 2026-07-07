import datetime
import json

from aiohttp import web
from sqlalchemy import desc, func, or_
from sqlalchemy.future import select

from app.database.models import AsyncSessionLocal, RewardCoupon, Subscription, User
from app.services.audit import record_audit
from app.utils.admin_bot_helper import resolve_user_bot

# Types the checkout flow can actually redeem today (see flows/pricing._validate_coupon)
_ISSUABLE_TYPES = {"discount_percent", "free_gb", "free_plan"}

_TYPE_LABEL_FA = {
    "discount_percent": "کد تخفیف",
    "free_gb": "حجم هدیه",
    "free_plan": "پلن هدیه",
}


def _coupon_json(c: RewardCoupon, user: User | None = None) -> dict:
    try:
        payload = json.loads(c.payload or "{}")
    except Exception:
        payload = {}
    return {
        "id": c.id,
        "user_id": c.user_id,
        "user_name": (user.first_name or user.username) if user else None,
        "chat_id": user.chat_id if user else None,
        "source": c.source,
        "coupon_type": c.coupon_type,
        "payload": payload,
        "campaign": payload.get("campaign"),
        "status": c.status,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "expires_at": c.expires_at.isoformat() if c.expires_at else None,
        "used_at": c.used_at.isoformat() if c.used_at else None,
    }


async def handle_admin_coupons_list(request: web.Request):
    """GET /api/admin/coupons?status=&q=&campaign=&page=&limit= + summary counts."""
    try:
        try:
            page = max(1, int(request.query.get("page", 1)))
            limit = min(200, max(1, int(request.query.get("limit", 50))))
        except (TypeError, ValueError):
            page, limit = 1, 50
        status = (request.query.get("status") or "").strip()
        q = (request.query.get("q") or "").strip()
        campaign = (request.query.get("campaign") or "").strip()

        async with AsyncSessionLocal() as session:
            stmt = select(RewardCoupon, User).join(User, User.id == RewardCoupon.user_id, isouter=True)
            if status:
                stmt = stmt.filter(RewardCoupon.status == status)
            if campaign:
                stmt = stmt.filter(RewardCoupon.payload.ilike(f'%"campaign": "{campaign}%'))
            if q:
                like = f"%{q}%"
                stmt = stmt.filter(or_(
                    User.username.ilike(like),
                    User.first_name.ilike(like),
                    RewardCoupon.payload.ilike(like),
                ))

            total = (await session.execute(
                select(func.count()).select_from(stmt.subquery())
            )).scalar() or 0
            rows = (await session.execute(
                stmt.order_by(desc(RewardCoupon.id)).offset((page - 1) * limit).limit(limit)
            )).all()

            counts = {}
            for st, cnt in (await session.execute(
                select(RewardCoupon.status, func.count(RewardCoupon.id)).group_by(RewardCoupon.status)
            )).all():
                counts[st or "?"] = int(cnt or 0)

            return web.json_response({
                "ok": True, "total": int(total), "page": page, "limit": limit,
                "counts": counts,
                "coupons": [_coupon_json(c, u) for c, u in rows],
            })
    except Exception:
        import traceback

        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


def _validate_payload(coupon_type: str, raw: dict) -> dict | None:
    """Whitelist + sanity-check the payload for each issuable type."""
    try:
        if coupon_type == "discount_percent":
            pct = int(raw.get("discount_percent") or 0)
            if not 1 <= pct <= 100:
                return None
            return {"discount_percent": pct}
        if coupon_type == "free_gb":
            gb = int(raw.get("gb") or 0)
            if not 1 <= gb <= 1000:
                return None
            return {"gb": gb}
        if coupon_type == "free_plan":
            gb = int(raw.get("plan_gb") or 0)
            days = int(raw.get("duration_days") or 30)
            if not (1 <= gb <= 1000 and 1 <= days <= 365):
                return None
            return {"plan_gb": gb, "duration_days": days}
    except (TypeError, ValueError):
        return None
    return None


async def handle_admin_coupon_create(request: web.Request):
    """POST /api/admin/coupons — issue coupons to a user / all users / active subs.

    Body: {coupon_type, payload{...}, expires_days, campaign?, notify?,
           target: {mode: 'user'|'all'|'active_subs', chat_id?}}
    """
    try:
        data = await request.json()
        coupon_type = str(data.get("coupon_type") or "").strip()
        if coupon_type not in _ISSUABLE_TYPES:
            return web.json_response({"ok": False, "error": "invalid_type"}, status=400)

        payload = _validate_payload(coupon_type, data.get("payload") or {})
        if payload is None:
            return web.json_response({"ok": False, "error": "invalid_payload"}, status=400)

        try:
            expires_days = min(365, max(1, int(data.get("expires_days") or 30)))
        except (TypeError, ValueError):
            expires_days = 30
        campaign = str(data.get("campaign") or "").strip()[:60]
        if campaign:
            payload["campaign"] = campaign
        notify = bool(data.get("notify", True))

        target = data.get("target") or {}
        mode = str(target.get("mode") or "user")

        async with AsyncSessionLocal() as session:
            if mode == "user":
                raw_cid = str(target.get("chat_id") or "").strip()
                if not raw_cid:
                    return web.json_response({"ok": False, "error": "missing_chat_id"}, status=400)
                conds = [User.username == raw_cid.lstrip("@")]
                if raw_cid.lstrip("-").isdigit():
                    conds.append(User.chat_id == int(raw_cid))
                targets = (await session.execute(select(User).filter(or_(*conds)))).scalars().all()
                if not targets:
                    return web.json_response({"ok": False, "error": "user_not_found"}, status=404)
            elif mode == "active_subs":
                targets = (await session.execute(
                    select(User).join(Subscription, Subscription.user_id == User.id)
                    .filter(Subscription.status == "active").distinct()
                )).scalars().all()
            elif mode == "all":
                targets = (await session.execute(select(User))).scalars().all()
            else:
                return web.json_response({"ok": False, "error": "invalid_target"}, status=400)

            if len(targets) > 20000:
                return web.json_response({"ok": False, "error": "too_many_targets"}, status=400)

            expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=expires_days)
            payload_str = json.dumps(payload, ensure_ascii=False)
            for u in targets:
                session.add(RewardCoupon(
                    user_id=u.id,
                    source="marketing",
                    coupon_type=coupon_type,
                    payload=payload_str,
                    expires_at=expires_at,
                    status="active",
                ))
            await session.commit()

        sent = 0
        if notify:
            user_bot = resolve_user_bot(request.app.get("bot"))
            if user_bot is not None:
                label = _TYPE_LABEL_FA.get(coupon_type, "کوپن")
                if coupon_type == "discount_percent":
                    what = f"{payload['discount_percent']}٪ تخفیف"
                elif coupon_type == "free_gb":
                    what = f"{payload['gb']} گیگ حجم هدیه"
                else:
                    what = f"پلن هدیه {payload['plan_gb']} گیگ"
                text = (
                    f"🎁 یک {label} برای شما فعال شد: <b>{what}</b>\n"
                    f"تا {expires_days} روز در سبد خرید قابل استفاده است."
                )
                for u in targets[:2000]:
                    try:
                        await user_bot.send_message(u.chat_id, text, parse_mode="HTML")
                        sent += 1
                    except Exception:
                        pass

        await record_audit(
            request, "coupon.create", target_type="coupon",
            summary=f"{coupon_type} → {len(targets)} user(s), campaign={campaign or '-'}",
            detail={"payload": payload, "targets": len(targets), "notified": sent, "expires_days": expires_days},
        )
        return web.json_response({"ok": True, "issued": len(targets), "notified": sent})
    except Exception:
        import traceback

        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_admin_coupon_revoke(request: web.Request):
    """POST /api/admin/coupons/revoke — {coupon_id} or {campaign} (bulk).
    Only active, unused coupons are touched."""
    try:
        data = await request.json()
        coupon_id = data.get("coupon_id")
        campaign = str(data.get("campaign") or "").strip()
        if not coupon_id and not campaign:
            return web.json_response({"ok": False, "error": "missing_target"}, status=400)

        async with AsyncSessionLocal() as session:
            stmt = select(RewardCoupon).filter(RewardCoupon.status == "active")
            if coupon_id:
                stmt = stmt.filter(RewardCoupon.id == int(coupon_id))
            else:
                stmt = stmt.filter(RewardCoupon.payload.ilike(f'%"campaign": "{campaign}"%'))
            rows = (await session.execute(stmt)).scalars().all()
            for c in rows:
                c.status = "revoked"
            await session.commit()

        await record_audit(
            request, "coupon.revoke", target_type="coupon",
            target_id=coupon_id or campaign,
            summary=f"revoked {len(rows)} coupon(s)",
        )
        return web.json_response({"ok": True, "revoked": len(rows)})
    except (TypeError, ValueError):
        return web.json_response({"ok": False, "error": "invalid_id"}, status=400)
    except Exception:
        import traceback

        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)
