import datetime

from aiohttp import web
from sqlalchemy import func
from sqlalchemy.future import select

from app.database.models import AsyncSessionLocal, ChargeRequest, Subscription, User, VipOrder

# Statuses that mean the money was NOT kept (pending review, denied, rolled back…)
_NON_REVENUE = ("pending", "denied", "deny", "canceled", "cancelled", "draft", "failed", "rejected")


def _paid_expr(model):
    """Cash actually received for a row: paid_amount when recorded (net figure
    the buyer transferred), else price minus reserved wallet credit."""
    credit = getattr(model, "credit_used", None)
    fallback = model.price - func.coalesce(credit, 0) if credit is not None else model.price
    return func.coalesce(model.paid_amount, fallback) if hasattr(model, "paid_amount") else fallback


async def _daily_series(session, model, date_col, *, days: int):
    since = datetime.datetime.utcnow() - datetime.timedelta(days=days - 1)
    day = func.date(date_col)
    rows = (await session.execute(
        select(day.label("d"), func.count(model.id), func.sum(_paid_expr(model)))
        .filter(model.status.notin_(_NON_REVENUE), date_col >= since)
        .group_by(day).order_by(day)
    )).all()
    return {str(r[0]): {"count": int(r[1] or 0), "amount": int(r[2] or 0)} for r in rows}


async def _window_total(session, model, date_col, *, days: int | None):
    stmt = select(func.count(model.id), func.sum(_paid_expr(model))).filter(
        model.status.notin_(_NON_REVENUE)
    )
    if days is not None:
        stmt = stmt.filter(date_col >= datetime.datetime.utcnow() - datetime.timedelta(days=days))
    row = (await session.execute(stmt)).first()
    return {"count": int(row[0] or 0), "amount": int(row[1] or 0)}


async def handle_admin_analytics_revenue(request: web.Request):
    """GET /api/admin/analytics/revenue?days=30 — daily cash series (purchases +
    charges + VIP), window totals, plan popularity, new-user series."""
    try:
        try:
            days = min(180, max(7, int(request.query.get("days", 30))))
        except (TypeError, ValueError):
            days = 30

        async with AsyncSessionLocal() as session:
            subs = await _daily_series(session, Subscription, Subscription.created_at, days=days)
            charges = await _daily_series(session, ChargeRequest, ChargeRequest.created_at, days=days)
            vip_date = func.coalesce(VipOrder.approved_at, VipOrder.created_at)
            vips = await _daily_series(session, VipOrder, vip_date, days=days)

            today = datetime.date.today()
            series = []
            for i in range(days - 1, -1, -1):
                d = str(today - datetime.timedelta(days=i))
                s, c, v = subs.get(d, {}), charges.get(d, {}), vips.get(d, {})
                series.append({
                    "date": d,
                    "subs": s.get("amount", 0), "charges": c.get("amount", 0), "vip": v.get("amount", 0),
                    "total": s.get("amount", 0) + c.get("amount", 0) + v.get("amount", 0),
                    "orders": s.get("count", 0) + c.get("count", 0) + v.get("count", 0),
                })

            async def window(days_):
                parts = [
                    await _window_total(session, Subscription, Subscription.created_at, days=days_),
                    await _window_total(session, ChargeRequest, ChargeRequest.created_at, days=days_),
                    await _window_total(session, VipOrder, vip_date, days=days_),
                ]
                return {
                    "amount": sum(p["amount"] for p in parts),
                    "count": sum(p["count"] for p in parts),
                }

            totals = {
                "today": await window(1),
                "week": await window(7),
                "month": await window(30),
                "all_time": await window(None),
            }

            plan_rows = (await session.execute(
                select(Subscription.plan_name, func.count(Subscription.id), func.sum(_paid_expr(Subscription)))
                .filter(
                    Subscription.status.notin_(_NON_REVENUE),
                    Subscription.created_at >= datetime.datetime.utcnow() - datetime.timedelta(days=days),
                )
                .group_by(Subscription.plan_name)
                .order_by(func.sum(_paid_expr(Subscription)).desc())
                .limit(8)
            )).all()
            plans = [
                {"plan": r[0] or "?", "count": int(r[1] or 0), "amount": int(r[2] or 0)}
                for r in plan_rows
            ]

            new_users = {}
            try:
                since = datetime.datetime.utcnow() - datetime.timedelta(days=days - 1)
                day = func.date(User.created_at)
                for r in (await session.execute(
                    select(day, func.count(User.id)).filter(User.created_at >= since).group_by(day)
                )).all():
                    new_users[str(r[0])] = int(r[1] or 0)
            except Exception:
                new_users = {}
            for point in series:
                point["new_users"] = new_users.get(point["date"], 0)

            return web.json_response({"ok": True, "days": days, "series": series, "totals": totals, "plans": plans})
    except Exception:
        import traceback

        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_admin_analytics_expiring(request: web.Request):
    """GET /api/admin/analytics/expiring?window=7 — subs expiring within N days
    (and ones that expired in the last N), enriched with the owning user, so the
    admin can fire renewal reminders at exactly this cohort."""
    from app.services.pasarguard import pasarguard_api

    try:
        try:
            window = min(30, max(1, int(request.query.get("window", 7))))
        except (TypeError, ValueError):
            window = 7

        marz_users = await pasarguard_api.get_all_users_paged()
        now = datetime.datetime.now(datetime.timezone.utc).timestamp()
        horizon = now + window * 86400
        floor = now - window * 86400

        interesting = {}
        for u in marz_users:
            exp = u.get("expire")
            if not exp:
                continue
            if floor <= exp <= horizon:
                interesting[u.get("username") or ""] = u

        expiring, expired = [], []
        if interesting:
            async with AsyncSessionLocal() as session:
                rows = (await session.execute(
                    select(Subscription, User)
                    .join(User, User.id == Subscription.user_id)
                    .filter(Subscription.marzban_username.in_(list(interesting.keys())))
                )).all()
                by_name = {s.marzban_username: (s, u) for s, u in rows}
                for name, mu in interesting.items():
                    exp = mu.get("expire") or 0
                    days_left = (exp - now) / 86400
                    sub, user = by_name.get(name, (None, None))
                    used = mu.get("used_traffic") or 0
                    limit_b = mu.get("data_limit") or 0
                    # Churn radar: how long since this client last connected.
                    # A sub that expires soon AND hasn't connected for days is
                    # a likely-churned user — remind them first (or don't).
                    inactive_days = None
                    online_at = mu.get("online_at")
                    if online_at:
                        try:
                            dt = datetime.datetime.fromisoformat(str(online_at).replace("Z", "+00:00"))
                            inactive_days = round(max(0.0, (now - dt.timestamp()) / 86400), 1)
                        except Exception:
                            inactive_days = None
                    item = {
                        "username": name,
                        "days_left": round(days_left, 1),
                        "expire_at": datetime.datetime.fromtimestamp(exp, tz=datetime.timezone.utc).isoformat(),
                        "used_gb": round(used / (1024 ** 3), 1),
                        "limit_gb": round(limit_b / (1024 ** 3), 1) if limit_b else None,
                        "plan_name": sub.plan_name if sub else None,
                        "renewal_paid": bool(sub.renewal_paid) if sub else False,
                        "user_id": user.id if user else None,
                        "chat_id": user.chat_id if user else None,
                        "user_name": (user.first_name or user.username) if user else None,
                        "inactive_days": inactive_days,
                        "likely_churned": bool(inactive_days is not None and inactive_days >= 5),
                    }
                    (expiring if days_left >= 0 else expired).append(item)

        expiring.sort(key=lambda x: x["days_left"])
        expired.sort(key=lambda x: x["days_left"], reverse=True)
        return web.json_response({
            "ok": True, "window": window,
            "expiring": expiring[:100], "expired": expired[:100],
            "counts": {"expiring": len(expiring), "expired": len(expired)},
        })
    except Exception:
        import traceback

        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_admin_expiring_remind(request: web.Request):
    """POST /api/admin/analytics/expiring/remind {chat_ids:[..]} — DM a renewal
    reminder (user bot) to at most 100 users; returns per-user delivery result."""
    from app.services.audit import record_audit
    from app.utils.admin_bot_helper import resolve_user_bot

    try:
        data = await request.json()
        chat_ids = [int(c) for c in (data.get("chat_ids") or []) if str(c).strip()][:100]
        if not chat_ids:
            return web.json_response({"ok": False, "error": "no_targets"}, status=400)
        custom = str(data.get("message") or "").strip()
        text = custom or (
            "⏳ اشتراک شما به‌زودی منقضی می‌شود.\n"
            "برای تمدید، از منوی ربات یا داشبورد اقدام کنید تا اتصال‌تان قطع نشود."
        )

        user_bot = resolve_user_bot(request.app.get("bot"))
        if user_bot is None:
            return web.json_response({"ok": False, "error": "bot_not_available"}, status=500)

        sent, failed = 0, 0
        for cid in chat_ids:
            try:
                await user_bot.send_message(cid, text)
                sent += 1
            except Exception:
                failed += 1

        await record_audit(
            request, "expiry.remind", target_type="broadcast",
            summary=f"renewal reminder to {sent}/{len(chat_ids)} users",
            detail={"sent": sent, "failed": failed},
        )
        return web.json_response({"ok": True, "sent": sent, "failed": failed})
    except Exception:
        import traceback

        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)
