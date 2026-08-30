"""Knowledge blocks for the support assistant, built from THIS app's data.

The sales bot built these inside `support_ai.py` by reaching into its own
module globals. Here they live apart so the brain stays pure and testable:
this is the only file that touches the database, the catalog or the panel.

Two blocks:
  * `build_static_kb()` — business facts that change rarely (plans, prices,
    payment, renewal rules, apps, troubleshooting playbook). Cached per
    process for KB_TTL_SEC.
  * `build_customer_context()` — this one customer's live situation. Panel
    stats come from the cached user info only, so a support answer never
    waits on the panel.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

from sqlalchemy import select

from app.core import products
from app.core.pricing import CUSTOM_MAX_GB_NONVIP, CUSTOM_MIN_GB
from app.core.settings import PLANS
from app.database import crud
from app.database.models import Subscription
from app.services.flows.charge import TRAFFIC_GATE_GB
from app.utils.logger import bot_logger

KB_TTL_SEC = 600
GB = 1024 ** 3

_kb_cache: tuple[float, str] | None = None


def _toman(value) -> str:
    try:
        return f'{int(value):,} تومان'
    except (TypeError, ValueError):
        return '؟'


def _fmt_gb(value) -> str:
    try:
        return f'{float(value):.1f}'.rstrip('0').rstrip('.')
    except (TypeError, ValueError):
        return '?'


def build_static_kb(force: bool = False) -> str:
    """The business-facts block. Prose ported from the live sales bot, with
    every number read from THIS project's catalog and settings."""
    global _kb_cache
    now = time.time()
    if not force and _kb_cache and now - _kb_cache[0] < KB_TTL_SEC:
        return _kb_cache[1]

    lines = ['# دانش کسب‌وکار AstroByte VPN', '', '## پلن‌ها و قیمت‌ها (تومان)']
    for name, meta in PLANS.items():
        days = meta.get('days', 35)
        tail = ' — فقط برای اعضای VIP' if meta.get('vip_only') else ''
        months = meta.get('min_months')
        if months and months > 1:
            tail += f' — حداقل {months} ماهه'
        lines.append(f"- {name} — {days} روزه — {_toman(meta.get('price'))}{tail}")
    lines += [
        f'- حجم دلخواه (سفارشی): از {CUSTOM_MIN_GB} تا {CUSTOM_MAX_GB_NONVIP} گیگ، '
        'یک‌ماهه. قیمت دقیق هر عدد را ربات هنگام سفارش نشان می‌دهد. '
        'حجم‌های بالاتر فقط برای اعضای VIP است.',
        f'- پلن تست رایگان: {_fmt_gb(products.FREE_TEST_GB)} گیگ، '
        f'{products.FREE_TEST_DAYS} روزه — هر '
        f'{products.TEST_COOLDOWN_DAYS} روز یک بار برای هر حساب '
        '(محدودیت خودکار؛ زمان باقی‌مانده در <customer_data> آمده).',
        '- پلن‌های چندماهه فقط برای اعضای VIP فعال است.',
        '',
        '## پرداخت',
        # The card number is deliberately NOT in the prompt: cards rotate, and
        # a model quoting a stale one sends a customer's money nowhere. The
        # bot shows the current card at the payment step. (Same rule as the
        # live sales bot, which tests for exactly this.)
        '- پرداخت کارت‌به‌کارت است. شماره کارت را هرگز خودت اعلام نکن — ربات '
        'شماره کارت روز را در مرحله پرداخت نشان می‌دهد.',
        '- برای تأیید خودکار و فوری: مبلغ باید «دقیق» و در «یک تراکنش» واریز شود، '
        'اسکرین‌شات واقعی رسید «انتقال موفق» خود اپ بانک ارسال شود، و بین واریز و '
        'ارسال رسید بیشتر از ۴۵ دقیقه فاصله نیفتد.',
        '- عکس رسید باید در مرحله «ارسال رسید» همان سفارش در ربات یا داشبورد '
        'فرستاده شود، نه در این گفتگو. در این صورت معمولاً ظرف چند دقیقه خودکار '
        'تأیید و اشتراک ارسال می‌شود؛ در غیر این صورت ادمین دستی بررسی می‌کند.',
        '',
        '## تمدید / شارژ',
        f'- شارژ وقتی مجاز است که کمتر از {TRAFFIC_GATE_GB} گیگ باقی مانده باشد '
        'یا اشتراک به انقضا نزدیک باشد.',
        f'- حداکثر {TRAFFIC_GATE_GB} گیگ از حجم باقی‌مانده به پلن جدید منتقل می‌شود.',
        '- اگر اشتراک منقضی شود، حجم باقی‌مانده از بین می‌رود و قابل انتقال نیست.',
        '- بعد از تمدید نیازی به وارد کردن لینک جدید نیست — همان لینک قبلی کار می‌کند.',
        '- تمدید را می‌شود از قبل رزرو کرد؛ در این حالت پنل خودش دقیقاً وقتی حجم '
        'تمام شود پلن بعدی را اعمال می‌کند.',
        '',
        '## استفاده از ربات و داشبورد',
        '- «اشتراک‌های من»: دیدن وضعیت مصرف، لینک و QR هر اشتراک، در ربات و داشبورد.',
        '- «افزودن لینک»: اگر اشتراکی از قبل دارید که در ربات نیست، لینک sub آن را '
        'اضافه کنید تا قابل مدیریت و تمدید شود.',
        '- برنامه‌های اتصال: اندروید → v2rayNG؛ آیفون به ترتیب اولویت → '
        'Karing، بعد NPV Tunnel، بعد Streisand (V2Box توصیه نمی‌شود)؛ '
        'ویندوز/مک → v2rayN یا Hiddify. لینک اشتراک را در بخش Subscription '
        'برنامه وارد و به‌روزرسانی کنید.',
        '',
        '## نام‌گذاری کانفیگ‌ها در برنامه',
        '- الگو: «کشور | پرچم | کاربرد».',
        '- کاربردها: Irancell = مخصوص اینترنت ایرانسل؛ MCI = مخصوص همراه اول؛ '
        'TG = تلگرام؛ ALL = همه اینترنت‌ها و همه‌کاره؛ Streaming = بهینه برای '
        'سرویس‌های استریم (YouTube، Twitch و…).',
        '- انتخاب: کانفیگ هم‌نام اپراتور مشتری (ایرانسل → Irancell، همراه اول → '
        'MCI)؛ فیلم/استریم → Streaming؛ جواب نداد → چند کانفیگ و لوکیشن دیگر '
        'امتحان شود. پسوندی خارج از این موارد را حدس نزن — بگو همکار پشتیبانی '
        'دقیق توضیح می‌دهد.',
        '',
        '## راهنمای حل مشکل (به همین ترتیب پیش برو)',
        '- وصل نمی‌شود: اگر اپراتور معلوم نیست بپرس؛ کانفیگ هم‌نام اپراتور؛ '
        'یک‌بار به‌روزرسانی اشتراک تا کانفیگ‌های جدید بیاید؛ چند کانفیگ و لوکیشن '
        'مختلف؛ اگر با V2Box است حتماً به Karing منتقلش کن. باز هم وصل نشد → '
        'handoff و در note بنویس: اپراتور، برنامه، چه چیزهایی امتحان شد.',
        '- کندی یا فیلم/استریم/یوتیوب: کانفیگ Streaming را پیشنهاد بده.',
        '- حجم یا زمان تمام شده: قوانین تمدید و انتقال حجم را صادقانه توضیح بده '
        'و show_renew را true کن.',
        '- لیست کانفیگ‌ها قدیمی است: آموزش Update در بخش Subscription برنامه.',
        '- سفارش/پرداخت معلق: وضعیت آخرین سفارش را از <customer_data> بخوان و '
        'همان را توضیح بده — «در انتظار بررسی» یعنی رسیدش در صف بررسی است؛ '
        'اگر خیلی قدیمی به نظر می‌رسد → handoff؛ «تحویل‌شده» و لینک می‌خواهد → '
        'show_links را true کن.',
        '- برنامهٔ نامناسب دارد: راهنمای اپ درست همان سیستم‌عامل را بده.',
    ]
    text = '\n'.join(lines)
    _kb_cache = (now, text)
    return text


def _tehran_now_line() -> str:
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo('Asia/Tehran'))
        return f"- زمان حال تهران: {now.strftime('%Y-%m-%d %H:%M')}"
    except Exception:
        return ''


# At most this many panel lookups per answer, each with its own short
# deadline: a support reply must never sit waiting on the panel. Subs beyond
# the budget still appear, just without usage numbers.
STATS_FETCH_BUDGET = 2
STATS_TIMEOUT_SEC = 4


async def _sub_line(sub: Subscription, budget: list) -> str:
    """One subscription as a context line, usage numbers included when the
    panel answers inside the budget."""
    label = sub.plan_name or '—'
    parts = [f'- اشتراک #{sub.id} | {label} | وضعیت: {sub.status}']
    info = None
    if budget and budget[0] > 0 and sub.marzban_username:
        budget[0] -= 1
        try:
            from app.services.pasarguard import pasarguard_api
            info = await asyncio.wait_for(
                pasarguard_api.get_user_info(sub.marzban_username), STATS_TIMEOUT_SEC)
        except Exception as exc:
            bot_logger.debug(f'[SUPPORT-AI] panel stats skipped for {sub.id}: '
                             f'{type(exc).__name__}')
            info = None
    if info:
        limit = int(info.get('data_limit') or 0)
        used = int(info.get('used_traffic') or 0)
        if limit:
            parts.append(f'باقی‌مانده: {_fmt_gb(max(0, limit - used) / GB)} از '
                         f'{_fmt_gb(limit / GB)} گیگ')
        expire = info.get('expire')
        if expire:
            days = int((int(expire) - time.time()) // 86400)
            parts.append(f'{max(0, days)} روز تا انقضا')
    if sub.renewal_paid and not sub.renewal_applied:
        parts.append(f'تمدید رزرو شده: {sub.renewal_template or "—"}')
    return ' | '.join(parts)


async def build_customer_context(session, user) -> str:
    """This customer's live situation, as the <customer_data> block."""
    lines = [f'- نام: {user.full_name or user.username or "—"}',
             f'- شناسه عددی: {user.chat_id}']
    try:
        if int(user.credit or 0) > 0:
            lines.append(f'- اعتبار حساب: {_toman(user.credit)}')
        if await crud.is_user_vip(session, user.id):
            lines.append('- عضو VIP است (تخفیف و پلن‌های چندماهه برایش فعال است).')
    except Exception as exc:
        bot_logger.debug(f'[SUPPORT-AI] customer extras skipped: {type(exc).__name__}: {exc}')

    now_line = _tehran_now_line()
    if now_line:
        lines.append(now_line)

    try:
        rows = (await session.execute(
            select(Subscription)
            .where(Subscription.user_id == user.id)
            .order_by(Subscription.created_at.desc())
            .limit(6))).scalars().all()
    except Exception as exc:
        bot_logger.warning(f'[SUPPORT-AI] subscription lookup failed: {type(exc).__name__}')
        rows = []

    active = [s for s in rows if s.status == 'active']
    pending = [s for s in rows if s.status == 'pending']
    if active:
        lines.append('')
        lines.append('## اشتراک‌های فعال')
        budget = [STATS_FETCH_BUDGET]
        for sub in active:
            lines.append(await _sub_line(sub, budget))
    else:
        lines.append('- هیچ اشتراک فعالی ندارد.')
    if pending:
        lines.append('')
        lines.append('## سفارش‌های در انتظار بررسی')
        for sub in pending:
            created = sub.created_at.replace(tzinfo=timezone.utc) if sub.created_at else None
            age = f", {int((datetime.now(timezone.utc) - created).total_seconds() // 60)} دقیقه پیش" \
                if created else ''
            lines.append(f'- سفارش #{sub.id} | {sub.plan_name or "—"} | '
                         f'{_toman(sub.price)} | در انتظار بررسی{age}')
    return '\n'.join(lines)


async def owned_references(session, user) -> tuple[set[str], set[str]]:
    """This user's own subscription links and order ids, for the ownership
    gate. Never consult a global index — that would leak other customers."""
    links: set[str] = set()
    order_ids: set[str] = set()
    try:
        rows = (await session.execute(
            select(Subscription).where(Subscription.user_id == user.id))).scalars().all()
    except Exception:
        return links, order_ids
    for sub in rows:
        order_ids.add(str(sub.id))
        if sub.sub_token:
            links.add(str(sub.sub_token))
    return links, order_ids
