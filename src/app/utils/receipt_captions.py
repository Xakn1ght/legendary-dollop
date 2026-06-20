"""Shared admin-notification captions for purchase/charge receipts.

Both the bot flow and the webapp flow must send the SAME structured caption
to the admin so approvals read identically regardless of surface.
"""


def purchase_receipt_caption(sub, user, *, source: str, plans: dict) -> str:
    """Structured admin caption for a purchase receipt.

    source: 'webapp' | 'bot'
    """
    from app.services.flows.pricing import get_plan_info, plan_display_name

    plan_info = get_plan_info(sub.plan_name) or (plans or {}).get(sub.plan_name, {}) or {}
    total = plan_info.get("price", 0) or 0
    if getattr(sub, "renewal_paid", False) and getattr(sub, "renewal_price", 0):
        total += sub.renewal_price

    header = "📱 رسید جدید از وب‌اپ" if source == "webapp" else "🤖 رسید جدید از ربات"
    lines = [
        header,
        "",
        f"👤 کاربر: {user.full_name} ({user.chat_id})",
        f"📦 پلن: {plan_display_name(sub.plan_name)} ({plan_info.get('gb', 0)} گیگابایت)",
        f"🔖 نام سرویس: {sub.marzban_username}",
        f"💵 مبلغ کل: {total:,} تومان",
    ]
    if getattr(sub, "applied_discount_ids", None):
        lines.append("🎟️ تخفیف اعمال شده")
    if getattr(sub, "credit_used", 0):
        lines.append(f"💰 اعتبار استفاده شده: {sub.credit_used:,} تومان")
    if getattr(sub, "renewal_paid", False) and getattr(sub, "renewal_template", None):
        lines.append(f"🔄 تمدید خودکار: {sub.renewal_template}")
    lines += ["", f"🆔 شماره سفارش: #{sub.id}"]
    return "\n".join(lines)


_GB = 1024 ** 3

_CHARGE_TYPE_LABELS = {
    "normal": "",
    "normal_5gb_limit": "\n⚠️ شارژ با حد انتقال 5GB",
    "booking": "\n📅 رزرو پلن (تمدید خودکار)",
}


def charge_receipt_caption(charge_req, user, sub_username: str, *, source: str) -> str:
    """Structured admin caption for a charge/top-up receipt."""
    header = "📱 درخواست شارژ از وب‌اپ" if source == "webapp" else "🤖 درخواست شارژ از ربات"
    header += _CHARGE_TYPE_LABELS.get(getattr(charge_req, "charge_type", "normal") or "normal", "")

    pkg = []
    if getattr(charge_req, "traffic_bytes", 0):
        pkg.append(f"{charge_req.traffic_bytes / _GB:.0f} گیگابایت")
    if getattr(charge_req, "extra_days", None):
        pkg.append(f"+ {charge_req.extra_days} روز")
    if getattr(charge_req, "charge_type", "") == "booking" and getattr(charge_req, "renewal_template", None):
        pkg.append(f"رزرو {charge_req.renewal_template}")

    lines = [
        header,
        "",
        f"👤 کاربر: {user.full_name} ({user.chat_id})",
        f"🔖 اشتراک: {sub_username or 'N/A'}",
        f"📦 بسته: {' '.join(pkg) or '-'}",
        f"💵 مبلغ کل: {charge_req.price:,} تومان",
    ]
    credit_used = getattr(charge_req, "credit_used", 0) or 0
    if credit_used > 0:
        lines.append(f"💰 اعتبار استفاده شده: {credit_used:,} تومان")
        lines.append(f"💵 پرداختی رسید: {charge_req.price - credit_used:,} تومان")
    lines += ["", f"🆔 شماره درخواست: #{charge_req.id}"]
    return "\n".join(lines)
