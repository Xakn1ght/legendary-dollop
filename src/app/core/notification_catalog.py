"""Typed notification catalog — the single source of truth for user notifications.

Every user-facing notification type is declared here with its category, frontend
icon token (SVG name, never an emoji), dashboard deeplink, bot-DM policy and
fa/en title+body templates. `services/notify.py` is the only intended consumer
for writes; API payload shaping reads it via `to_payload` there.

Design spec: docs/design-specs/specs/2026-07-20-notification-center-rework-design.md
(section 2, "Typed catalog"). No DB schema change: `notifications.type` stores the
enum value; category/icon/deeplink are computed server-side at payload time, so
legacy rows with unknown types keep working (category=system, no deeplink).

Copy rules (Pasha): Persian-first, both languages, zero emojis anywhere.
Persian copy below is derived from the pre-rework call-site strings with the
same meaning and tone, emojis stripped, and the English-only charge titles
replaced by proper fa+en pairs.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from string import Formatter

logger = logging.getLogger(__name__)

CATEGORIES = ("money", "service", "rewards", "support", "system")

# Icon token shown for legacy/unknown types (and the safe default in general).
DEFAULT_ICON = "bell"
DEFAULT_CATEGORY = "system"


class NotificationType(str, Enum):
    """All notification types written by the app.

    The first 16 are the values that exist in production rows today; the last
    four are the scheduler alerts (jobs/notifications.py) that become rows in
    phase 3 of the rework.
    """

    PURCHASE_APPROVED = "purchase_approved"
    PURCHASE_DENIED = "purchase_denied"
    CHARGE_APPROVED = "charge_approved"
    CHARGE_DENIED = "charge_denied"
    CASHOUT_PAID = "cashout_paid"
    CASHOUT_DENIED = "cashout_denied"
    VIP_GRANTED = "vip_granted"
    VIP_DENIED = "vip_denied"
    VIP_REMOVED = "vip_removed"
    TICKET_NEW_MESSAGE = "ticket_new_message"
    TICKET_CLOSED = "ticket_closed"
    SUBSCRIPTION_DELETED = "subscription_deleted"
    SUBSCRIPTION_EXTENDED = "subscription_extended"
    CREDIT_CHANGE = "credit_change"
    ACCOUNT_STATUS = "account_status"
    GENERAL = "general"
    # Job alerts becoming rows (phase 3):
    LOW_DATA = "low_data"
    DATA_FINISHED = "data_finished"
    EXPIRY_SOON = "expiry_soon"
    EXPIRED = "expired"


@dataclass(frozen=True)
class CatalogEntry:
    """Static definition of one notification type.

    - category: money | service | rewards | support | system (UI grouping/tint).
    - icon: SVG token name the dashboard maps to an inline icon. Never an emoji.
    - deeplink: dashboard route the row navigates to on tap, or None.
      May contain `{ticket_id}` which is filled from the row's ticket_id at
      payload time (row without a ticket_id renders no deeplink).
    - dm: whether notify() sends a plain-text bot DM in addition to the row.
      Policy: money events, VIP outcomes, ticket events, account status,
      subscription deleted/extended, data_finished/expired -> DM.
      `general` (admin broadcast / informational) -> dashboard-only.
      Exception kept from current behavior: low_data and expiry_soon DM users
      from the scheduler today, so they stay dm=True; phase 3 merely migrates
      their transport to notify().
    - title_*/body_*: str.format templates. All placeholders MUST be listed in
      ctx_doc; tests enforce this and render every template emoji-free.
    - ctx_doc: placeholder name -> human description of what the caller passes.
      Numbers are passed pre-formatted by the caller (thousand separators,
      Persian digits where appropriate); language-matched fragments are noted
      explicitly in the description.
    """

    category: str
    icon: str
    deeplink: str | None
    dm: bool
    title_fa: str
    title_en: str
    body_fa: str
    body_en: str
    ctx_doc: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if self.category not in CATEGORIES:
            raise ValueError(f"invalid category {self.category!r}")


CATALOG: dict[NotificationType, CatalogEntry] = {
    # ---------------------------------------------------------------- money
    NotificationType.PURCHASE_APPROVED: CatalogEntry(
        category="money",
        icon="check-circle",
        deeplink="services",
        dm=True,
        title_fa="سرویس فعال شد",
        title_en="Service activated",
        body_fa=(
            "سرویس «{service_name}» ({plan_name}) با موفقیت فعال شد. "
            "از داشبورد می‌توانید اطلاعات اتصال را مشاهده کنید."
        ),
        body_en=(
            "Your service \"{service_name}\" ({plan_name}) is now active. "
            "Open the dashboard to view the connection details."
        ),
        ctx_doc={
            "service_name": "PasarGuard service username (marzban_username)",
            "plan_name": "purchased plan display name",
        },
    ),
    NotificationType.PURCHASE_DENIED: CatalogEntry(
        category="money",
        icon="x-circle",
        deeplink=None,
        dm=True,
        title_fa="درخواست رد شد",
        title_en="Request denied",
        body_fa="درخواست خرید سرویس{service_ref} رد شد.{details}",
        body_en="Your service purchase request{service_ref} was denied.{details}",
        ctx_doc={
            "service_ref": (
                "language-matched service identifier fragment starting with a space "
                "(fa ' «svc» (پلن ۵۰ گیگ)' / en ' for \"svc\" (plan)'); when the "
                "service is unknown fa callers pass ' شما', en callers pass ''"
            ),
            "details": (
                "optional refund/restore lines composed by the caller in the render "
                "language, starting with a space (e.g. ' اعتبار ۵۰,۰۰۰ تومان به حساب "
                "شما برگشت.'); pass '' when there is nothing to add"
            ),
        },
    ),
    NotificationType.CHARGE_APPROVED: CatalogEntry(
        category="money",
        icon="check-circle",
        deeplink="services",
        dm=True,
        title_fa="شارژ تایید شد",
        title_en="Charge approved",
        body_fa="شارژ سرویس «{service_name}» تایید و اعمال شد.{details}",
        body_en="Your top-up for \"{service_name}\" was approved and applied.{details}",
        ctx_doc={
            "service_name": "PasarGuard service username",
            "details": (
                "optional added-volume/days/carry lines composed by the caller in the "
                "render language, starting with a space; pass '' when empty"
            ),
        },
    ),
    NotificationType.CHARGE_DENIED: CatalogEntry(
        category="money",
        icon="x-circle",
        deeplink="charge",
        dm=True,
        title_fa="شارژ رد شد",
        title_en="Charge denied",
        body_fa=(
            "درخواست شارژ سرویس «{service_name}» رد شد.{details} "
            "در صورت نیاز با پشتیبانی در تماس باشید."
        ),
        body_en=(
            "Your top-up request for \"{service_name}\" was denied.{details} "
            "Contact support if you need help."
        ),
        ctx_doc={
            "service_name": "PasarGuard service username",
            "details": (
                "optional refund line composed by the caller in the render language, "
                "starting with a space; pass '' when nothing was refunded"
            ),
        },
    ),
    NotificationType.CASHOUT_PAID: CatalogEntry(
        category="money",
        icon="banknote",
        deeplink=None,
        dm=True,
        title_fa="برداشت پرداخت شد",
        title_en="Withdrawal paid",
        body_fa="درخواست برداشت #{request_id} به مبلغ {amount} تومان پرداخت شد.",
        body_en="Withdrawal request #{request_id} for {amount} toman has been paid.",
        ctx_doc={
            "request_id": "cashout request id",
            "amount": "toman amount, pre-formatted with thousand separators",
        },
    ),
    NotificationType.CASHOUT_DENIED: CatalogEntry(
        category="money",
        icon="x-circle",
        deeplink=None,
        dm=True,
        title_fa="برداشت رد شد",
        title_en="Withdrawal denied",
        body_fa=(
            "درخواست برداشت #{request_id} رد شد و مبلغ {amount} تومان "
            "به کیف پول شما بازگشت."
        ),
        body_en=(
            "Withdrawal request #{request_id} was denied and {amount} toman "
            "was returned to your wallet."
        ),
        ctx_doc={
            "request_id": "cashout request id",
            "amount": "toman amount, pre-formatted with thousand separators",
        },
    ),
    NotificationType.VIP_GRANTED: CatalogEntry(
        category="money",
        icon="crown",
        deeplink=None,
        dm=True,
        title_fa="تبریک! VIP فعال شد",
        title_en="VIP activated",
        body_fa="اشتراک VIP شما فعال شد ({duration}). از مزایای ویژه لذت ببرید!",
        body_en="Your VIP membership is now active ({duration}). Enjoy the perks!",
        ctx_doc={
            "duration": (
                "duration text in the render language (e.g. '۳۰ روز' / 'دائمی', "
                "'30 days' / 'permanent')"
            ),
        },
    ),
    NotificationType.VIP_DENIED: CatalogEntry(
        category="money",
        icon="x-circle",
        deeplink=None,
        dm=True,
        title_fa="درخواست VIP رد شد",
        title_en="VIP request denied",
        body_fa="درخواست خرید VIP شما رد شد. برای اطلاعات بیشتر با پشتیبانی تماس بگیرید.",
        body_en="Your VIP purchase request was denied. Contact support for more information.",
        ctx_doc={},
    ),
    # --------------------------------------------------------------- system
    NotificationType.VIP_REMOVED: CatalogEntry(
        category="system",
        icon="crown",
        deeplink=None,
        dm=True,
        title_fa="اشتراک VIP پایان یافت",
        title_en="VIP ended",
        body_fa="اشتراک VIP شما به پایان رسید. برای تمدید با پشتیبانی تماس بگیرید.",
        body_en="Your VIP membership has ended. Contact support to renew.",
        ctx_doc={},
    ),
    NotificationType.ACCOUNT_STATUS: CatalogEntry(
        category="system",
        icon="shield",
        deeplink=None,
        dm=True,
        title_fa="وضعیت حساب تغییر کرد",
        title_en="Account status changed",
        body_fa="حساب کاربری شما {status} شد. برای اطلاعات بیشتر با پشتیبانی تماس بگیرید.",
        body_en="Your account has been {status}. Contact support for more information.",
        ctx_doc={
            "status": (
                "language-matched state word: fa 'مسدود' | 'فعال', "
                "en 'suspended' | 'reactivated'"
            ),
        },
    ),
    NotificationType.GENERAL: CatalogEntry(
        category="system",
        icon="bell",
        deeplink=None,
        dm=False,
        title_fa="{title}",
        title_en="{title}",
        body_fa="{body}",
        body_en="{body}",
        ctx_doc={
            "title": "free-form title composed by the caller (admin broadcast, challenge info, ...)",
            "body": "free-form body composed by the caller",
        },
    ),
    # -------------------------------------------------------------- support
    NotificationType.TICKET_NEW_MESSAGE: CatalogEntry(
        category="support",
        icon="message-circle",
        deeplink="support?ticket_id={ticket_id}",
        dm=True,
        title_fa="پاسخ جدید به تیکت #{ticket_no}",
        title_en="New reply on ticket #{ticket_no}",
        body_fa="پشتیبانی به تیکت شما پاسخ داده است. برای مشاهده و پاسخ وارد گفتگو شوید.",
        body_en="Support replied to your ticket. Open the chat to view and respond.",
        ctx_doc={
            "ticket_no": "user-visible ticket number (user_ticket_number, falls back to ticket id)",
        },
    ),
    NotificationType.TICKET_CLOSED: CatalogEntry(
        category="support",
        icon="message-square",
        deeplink="support?ticket_id={ticket_id}",
        dm=True,
        title_fa="تیکت #{ticket_no} بسته شد",
        title_en="Ticket #{ticket_no} closed",
        body_fa="تیکت پشتیبانی شما بسته شد. در صورت نیاز می‌توانید تیکت جدیدی ثبت کنید.",
        body_en="Your support ticket was closed. You can open a new one whenever you need help.",
        ctx_doc={
            "ticket_no": "user-visible ticket number (user_ticket_number, falls back to ticket id)",
        },
    ),
    # -------------------------------------------------------------- service
    NotificationType.SUBSCRIPTION_DELETED: CatalogEntry(
        category="service",
        icon="trash",
        deeplink=None,
        dm=True,
        title_fa="اشتراک حذف شد",
        title_en="Subscription removed",
        body_fa="اشتراک «{service_name}» توسط ادمین حذف شد.",
        body_en="Your subscription \"{service_name}\" was removed by an admin.",
        ctx_doc={"service_name": "PasarGuard service username"},
    ),
    NotificationType.SUBSCRIPTION_EXTENDED: CatalogEntry(
        category="service",
        icon="calendar-plus",
        deeplink="services",
        dm=True,
        title_fa="اشتراک تمدید شد",
        title_en="Subscription extended",
        body_fa="اشتراک «{service_name}» تمدید شد: {changes}",
        body_en="Your subscription \"{service_name}\" was extended: {changes}",
        ctx_doc={
            "service_name": "PasarGuard service username",
            "changes": (
                "language-matched summary of what was added "
                "(e.g. '+۳۰ روز و +۱۰ GB ترافیک' / '+30 days and +10 GB')"
            ),
        },
    ),
    NotificationType.CREDIT_CHANGE: CatalogEntry(
        category="money",
        icon="wallet",
        deeplink=None,
        dm=True,
        title_fa="تغییر اعتبار",
        title_en="Credit updated",
        body_fa="اعتبار حساب شما {delta} تومان تغییر کرد. موجودی جدید: {balance} تومان",
        body_en="Your account credit changed by {delta} toman. New balance: {balance} toman.",
        ctx_doc={
            "delta": "signed change, pre-formatted (e.g. '+۵۰,۰۰۰' or '-۵۰,۰۰۰')",
            "balance": "new balance in toman, pre-formatted with thousand separators",
        },
    ),
    NotificationType.LOW_DATA: CatalogEntry(
        category="service",
        icon="gauge",
        deeplink="charge",
        dm=True,  # exception: the scheduler DMs this today; behavior preserved
        title_fa="هشدار حجم کم",
        title_en="Low data warning",
        body_fa=(
            "حجم اشتراک «{service_name}» رو به اتمام است. "
            "باقی‌مانده: {remaining_gb} گیگابایت (حدود {percent}٪). "
            "برای شارژ یا تمدید اقدام کنید."
        ),
        body_en=(
            "Your service \"{service_name}\" is running low on data. "
            "Remaining: {remaining_gb} GB (about {percent}%). "
            "Top up or renew to stay connected."
        ),
        ctx_doc={
            "service_name": "PasarGuard service username",
            "remaining_gb": "remaining volume in GB, pre-formatted",
            "percent": "remaining percentage, pre-formatted",
        },
    ),
    NotificationType.DATA_FINISHED: CatalogEntry(
        category="service",
        icon="gauge-empty",
        deeplink="charge",
        dm=True,
        title_fa="حجم اشتراک تمام شد",
        title_en="Data used up",
        body_fa=(
            "حجم اشتراک «{service_name}» به اتمام رسید. "
            "برای تمدید و جلوگیری از حذف اشتراک اقدام کنید."
        ),
        body_en=(
            "Your service \"{service_name}\" has used all of its data. "
            "Renew now to avoid removal."
        ),
        ctx_doc={"service_name": "PasarGuard service username"},
    ),
    NotificationType.EXPIRY_SOON: CatalogEntry(
        category="service",
        icon="clock",
        deeplink="charge",
        dm=True,  # exception: the scheduler DMs this today; behavior preserved
        title_fa="اشتراک رو به پایان است",
        title_en="Subscription expiring soon",
        body_fa=(
            "از زمان اشتراک «{service_name}» کمتر از {days_left} روز باقی مانده است. "
            "در صورت تمدید، بسته خریداری‌شده رزرو شده و پس از پایان سرویس فعلی "
            "به‌طور خودکار فعال می‌شود."
        ),
        body_en=(
            "Your service \"{service_name}\" expires in less than {days_left} days. "
            "If you renew now, the new package is reserved and activates automatically "
            "when the current one ends."
        ),
        ctx_doc={
            "service_name": "PasarGuard service username",
            "days_left": "days remaining, pre-formatted (Persian digits for fa)",
        },
    ),
    NotificationType.EXPIRED: CatalogEntry(
        category="service",
        icon="clock-off",
        deeplink="charge",
        dm=True,
        title_fa="اشتراک منقضی شد",
        title_en="Subscription expired",
        body_fa=(
            "اشتراک «{service_name}» منقضی شد. "
            "برای تمدید و جلوگیری از حذف اشتراک اقدام کنید."
        ),
        body_en=(
            "Your service \"{service_name}\" has expired. "
            "Renew now to avoid removal."
        ),
        ctx_doc={"service_name": "PasarGuard service username"},
    ),
}


def template_placeholders(template: str) -> set[str]:
    """Names of the `{placeholder}` fields used in a str.format template."""
    return {name for _, name, _, _ in Formatter().parse(template) if name}


# ---------------------------------------------------------------------------
# Shared ctx builders — language-matched fragments used by more than one call
# site live here, next to the templates they feed, so the copy stays in one
# place. `lang` is the recipient's stored language (same normalization as the
# render path: en* -> en, everything else -> fa).
# ---------------------------------------------------------------------------

def purchase_denied_ctx(lang: str | None, *, service_name: str | None, plan_name: str | None,
                        credit_refunded: int = 0, discounts_restored: bool = False,
                        coupon_restored: bool = False) -> dict:
    """ctx for PURCHASE_DENIED: service reference + refund/restore details."""
    if _pick_lang(lang) == "en":
        service_ref = f' for "{service_name}" ({plan_name})' if service_name else ""
        details = ""
        if credit_refunded > 0:
            details += f" {credit_refunded:,} toman was returned to your account credit."
        if discounts_restored:
            details += " Your used discounts were restored."
        if coupon_restored:
            details += " Your used coupon was restored."
    else:
        service_ref = f" «{service_name}» ({plan_name})" if service_name else " شما"
        details = ""
        if credit_refunded > 0:
            details += f" اعتبار {credit_refunded:,} تومان به حساب شما برگشت."
        if discounts_restored:
            details += " تخفیف‌های استفاده‌شده بازگردانده شد."
        if coupon_restored:
            details += " کوپن استفاده‌شده به حساب شما بازگردانده شد."
    return {"service_ref": service_ref, "details": details}


def charge_denied_ctx(lang: str | None, *, service_name: str | None, credit_refunded: int = 0) -> dict:
    """ctx for CHARGE_DENIED: refund detail line when reserved credit came back."""
    if credit_refunded > 0:
        if _pick_lang(lang) == "en":
            details = f" {credit_refunded:,} toman was returned to your account credit."
        else:
            details = f" اعتبار {credit_refunded:,} تومان به حساب شما برگشت."
    else:
        details = ""
    return {"service_name": service_name or "-", "details": details}


def _pick_lang(lang: str | None) -> str:
    """Normalize a stored/user language to 'fa' or 'en'; unknown falls back to fa."""
    if lang and lang.strip().lower().startswith("en"):
        return "en"
    return "fa"


def render(type_: NotificationType | str, lang: str | None, ctx: dict | None = None,
           *, strict: bool = False) -> tuple[str, str]:
    """Render (title, body) for a notification type in the given language.

    - Unknown/None lang falls back to Persian.
    - Missing ctx keys: with strict=True (tests) the KeyError propagates; on the
      production path (strict=False, used by notify()) the raw template is
      returned instead so a copy bug can never block a money notification —
      guarded by a warning log.
    """
    nt = NotificationType(type_)  # raises ValueError for unknown types
    entry = CATALOG[nt]
    ctx = ctx or {}
    if _pick_lang(lang) == "en":
        title_t, body_t = entry.title_en, entry.body_en
    else:
        title_t, body_t = entry.title_fa, entry.body_fa
    try:
        return title_t.format(**ctx), body_t.format(**ctx)
    except (KeyError, IndexError) as e:
        if strict:
            raise
        logger.warning("notification_catalog: missing ctx %s rendering %s; falling back to raw template", e, nt.value)
        return title_t, body_t
