"""Shared admin-notification captions for purchase/charge receipts.

Both the bot flow and the webapp flow must send the SAME structured caption
to the admin so approvals read identically regardless of surface.

v2 (2026-07-13, Pasha): no emojis, Persian digits for money, scannable
label:value lines, and a shared "verified by" stamp appended when a receipt
is approved (approved cards are now edited in place, never deleted).
"""

_TO_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _toman(amount) -> str:
    """1250000 -> «۱,۲۵۰,۰۰۰ تومان» (FA digits, latin separators for scanning)."""
    try:
        return f"{int(amount):,}".translate(_TO_FA) + " تومان"
    except Exception:
        return f"{amount} تومان"


def _fa(n) -> str:
    return str(n).translate(_TO_FA)


def verified_stamp(approved_by: str | None = None) -> str:
    """The line(s) appended to a receipt caption once it is approved."""
    import datetime

    try:
        from app.utils.tehran_time import tehran_now
        now = tehran_now()
    except Exception:
        now = datetime.datetime.now()
    when = _fa(now.strftime("%Y-%m-%d %H:%M"))
    who = (approved_by or "").strip() or "ادمین"
    return f"تایید شد — {who}\n{when}"


def purchase_receipt_caption(sub, user, *, source: str, plans: dict) -> str:
    """Structured admin caption for a purchase receipt.

    source: 'webapp' | 'bot'
    """
    from app.services.flows.pricing import get_plan_info, plan_display_name

    plan_info = get_plan_info(sub.plan_name) or (plans or {}).get(sub.plan_name, {}) or {}
    total = plan_info.get("price", 0) or 0
    if getattr(sub, "renewal_paid", False) and getattr(sub, "renewal_price", 0):
        total += sub.renewal_price

    src = "وب‌اپ" if source == "webapp" else "ربات"
    lines = [
        f"رسید خرید — {src}",
        "",
        f"کاربر: {user.full_name} ({user.chat_id})",
        f"پلن: {plan_display_name(sub.plan_name)} ({_fa(plan_info.get('gb', 0))} گیگابایت)",
        f"نام سرویس: {sub.marzban_username}",
        f"مبلغ کل: {_toman(total)}",
    ]
    if getattr(sub, "applied_discount_ids", None):
        lines.append("تخفیف: اعمال شده")
    if getattr(sub, "credit_used", 0):
        lines.append(f"اعتبار استفاده‌شده: {_toman(sub.credit_used)}")
        lines.append(f"پرداختی رسید: {_toman(max(total - (sub.credit_used or 0), 0))}")
    if getattr(sub, "renewal_paid", False) and getattr(sub, "renewal_template", None):
        lines.append(f"تمدید خودکار: {plan_display_name(sub.renewal_template)}")
    lines += ["", f"سفارش #{sub.id}"]
    return "\n".join(lines)


_GB = 1024 ** 3

_CHARGE_TYPE_LABELS = {
    "normal": "",
    "normal_5gb_limit": "\nنوع: شارژ با حد انتقال ۵ گیگ",
    "booking": "\nنوع: رزرو پلن بعدی (اعمال خودکار پس از اتمام پلن فعلی)",
}


def charge_receipt_caption(charge_req, user, sub_username: str, *, source: str) -> str:
    """Structured admin caption for a charge/top-up receipt."""
    src = "وب‌اپ" if source == "webapp" else "ربات"
    kind = "رزرو پلن" if getattr(charge_req, "charge_type", "") == "booking" else "شارژ"
    header = f"رسید {kind} — {src}"
    header += _CHARGE_TYPE_LABELS.get(getattr(charge_req, "charge_type", "normal") or "normal", "")

    pkg = []
    if getattr(charge_req, "traffic_bytes", 0):
        pkg.append(f"{_fa(f'{charge_req.traffic_bytes / _GB:.0f}')} گیگابایت")
    if getattr(charge_req, "extra_days", None):
        pkg.append(f"+ {_fa(charge_req.extra_days)} روز")
    if getattr(charge_req, "charge_type", "") == "booking" and getattr(charge_req, "renewal_template", None):
        try:
            from app.services.flows.pricing import plan_display_name
            pkg.append(plan_display_name(charge_req.renewal_template))
        except Exception:
            pkg.append(str(charge_req.renewal_template))

    lines = [
        header,
        "",
        f"کاربر: {user.full_name} ({user.chat_id})",
        f"اشتراک: {sub_username or '-'}",
        f"بسته: {' '.join(pkg) or '-'}",
        f"مبلغ کل: {_toman(charge_req.price)}",
    ]
    credit_used = getattr(charge_req, "credit_used", 0) or 0
    if credit_used > 0:
        lines.append(f"اعتبار استفاده‌شده: {_toman(credit_used)}")
        lines.append(f"پرداختی رسید: {_toman(charge_req.price - credit_used)}")
    lines += ["", f"درخواست #{charge_req.id}"]
    return "\n".join(lines)
