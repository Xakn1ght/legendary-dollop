import csv
import datetime
import io

from aiohttp import web
from sqlalchemy.future import select

from app.database.models import (
    AsyncSessionLocal,
    CashoutRequest,
    ChargeRequest,
    Subscription,
    User,
    VipOrder,
)


def _csv_safe(value):
    """Neutralise CSV/formula injection. Excel/Sheets treat a cell starting with
    = + - @ (or tab/CR) as a formula, so a user named =HYPERLINK(...) or
    =cmd|'…' would execute when the admin opens the export. Prefix such cells
    with a single quote so they're read as literal text. Numbers pass through."""
    if not isinstance(value, str):
        return value
    if value and value[0] in ("=", "+", "-", "@", "\t", "\r", "\n"):
        return "'" + value
    return value


def _parse_date(raw: str | None, fallback: datetime.datetime) -> datetime.datetime:
    try:
        return datetime.datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return fallback


async def handle_admin_export_transactions(request: web.Request):
    """GET /api/admin/export/transactions?from=YYYY-MM-DD&to=YYYY-MM-DD —
    all money movements (purchases, charges, VIP, cash-outs) as a CSV download."""
    try:
        now = datetime.datetime.utcnow()
        dt_from = _parse_date(request.query.get("from"), now - datetime.timedelta(days=30))
        dt_to = _parse_date(request.query.get("to"), now) + datetime.timedelta(days=1)  # inclusive end

        rows: list[list] = []
        async with AsyncSessionLocal() as session:
            users: dict[int, User] = {}

            async def user_label(uid):
                if uid is None:
                    return ""
                if uid not in users:
                    users[uid] = await session.get(User, uid)
                u = users.get(uid)
                return f"{u.first_name or u.username or ''} ({u.chat_id})" if u else str(uid)

            subs = (await session.execute(
                select(Subscription).filter(
                    Subscription.created_at >= dt_from, Subscription.created_at < dt_to
                )
            )).scalars().all()
            for s in subs:
                rows.append([
                    s.created_at.isoformat() if s.created_at else "", "purchase", s.id,
                    await user_label(s.user_id), s.plan_name or "", s.status or "",
                    int(s.price or 0), int(s.credit_used or 0),
                    int(s.paid_amount if s.paid_amount is not None else max(int(s.price or 0) - int(s.credit_used or 0), 0)),
                    s.marzban_username or "",
                ])

            charges = (await session.execute(
                select(ChargeRequest).filter(
                    ChargeRequest.created_at >= dt_from, ChargeRequest.created_at < dt_to
                )
            )).scalars().all()
            for c in charges:
                rows.append([
                    c.created_at.isoformat() if c.created_at else "", "charge", c.id,
                    await user_label(c.user_id), c.charge_type or "normal", c.status or "",
                    int(c.price or 0), int(c.credit_used or 0),
                    int(c.paid_amount if c.paid_amount is not None else max(int(c.price or 0) - int(c.credit_used or 0), 0)),
                    "",
                ])

            vips = (await session.execute(
                select(VipOrder).filter(VipOrder.created_at >= dt_from, VipOrder.created_at < dt_to)
            )).scalars().all()
            for v in vips:
                rows.append([
                    v.created_at.isoformat() if v.created_at else "", "vip", v.id,
                    await user_label(v.user_id), v.plan_id or "", v.status or "",
                    int(v.price or 0), 0, int(v.price or 0), "",
                ])

            cashouts = (await session.execute(
                select(CashoutRequest).filter(
                    CashoutRequest.requested_at >= dt_from, CashoutRequest.requested_at < dt_to
                )
            )).scalars().all()
            for co in cashouts:
                rows.append([
                    co.requested_at.isoformat() if co.requested_at else "", "cashout", co.id,
                    await user_label(co.user_id), co.destination or "", co.status or "",
                    -int(co.amount or 0), 0, -int(co.amount or 0), "",
                ])

        rows.sort(key=lambda r: r[0])
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "date", "type", "id", "user", "item", "status",
            "price_toman", "credit_used_toman", "cash_received_toman", "service",
        ])
        writer.writerows([_csv_safe(c) for c in row] for row in rows)

        fname = f"astrobyte_transactions_{dt_from.date()}_{(dt_to - datetime.timedelta(days=1)).date()}.csv"
        return web.Response(
            body=("\ufeff" + buf.getvalue()).encode("utf-8"),  # BOM so Excel opens UTF-8 fine
            headers={
                "Content-Type": "text/csv; charset=utf-8",
                "Content-Disposition": f'attachment; filename="{fname}"',
            },
        )
    except Exception:
        import traceback

        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)
