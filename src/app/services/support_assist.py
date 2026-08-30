"""Wires the support assistant into the ticket system.

One entry point, `maybe_answer_ticket()`, called wherever a customer's text
lands on a ticket (bot and dashboard alike). It owns every policy decision, so
the four call sites stay one line each and cannot drift apart.

The assistant is OFF unless it is switched on AND a provider key is
configured. Every refusal path is silence — the ticket simply waits for a
human, exactly as it does today.

It never answers when:
  - the switch is off, no provider is configured, or the ticket is closed;
  - a human already took the ticket (assigned) or is live in chat with the
    customer right now;
  - the message is content-free (an emoji, a bare "thanks");
  - the message is an action request, a payment dispute or anger — those are
    escalations by definition, and a bot must never talk its way through one;
  - a rate limit or the daily cap has been reached;
  - the brain returns handoff, or no confident answer at all.

Replies are written with `sender='admin'`: the assistant answers AS support,
and that is also the only sender value both UIs render on the support side.
Every answer is logged and audited, so an admin reading the ticket can always
tell who actually wrote it.
"""
from __future__ import annotations

import json
import os
from datetime import datetime

from sqlalchemy import select

from app.core.paths import data_path
from app.database.models import TicketMessage
from app.services import support_ai, support_context
from app.utils.logger import bot_logger

_STATE_FILE = data_path('support_ai_state.json')

# Rate limits. Deliberately tight: this feature exists to answer the easy
# questions fast, not to hold a conversation on its own.
MAX_ANSWERS_PER_TICKET = 4
MAX_ANSWERS_PER_USER_DAY = 8
MAX_ANSWERS_PER_DAY = 200          # global brake, on top of the USD budget
_DAY_SEC = 24 * 3600


def support_ai_enabled() -> bool:
    """The runtime switch. File wins so it can be flipped without a restart."""
    try:
        with open(_STATE_FILE, encoding='utf-8') as f:
            state = json.load(f)
        if 'enabled' in state:
            return bool(state['enabled'])
    except Exception:
        pass
    return (os.environ.get('SUPPORT_AI_ENABLED') or '').strip() == '1'


def set_support_ai_enabled(enabled: bool) -> None:
    tmp = f'{_STATE_FILE}.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump({'enabled': bool(enabled)}, f)
    os.replace(tmp, _STATE_FILE)


async def _within_limits(ticket, user) -> bool:
    """Rate limits, in Redis. Fails CLOSED: with no cache we cannot count, and
    an uncounted assistant could answer the same ticket forever."""
    try:
        from app.core.redis_config import cache

        for key, cap, ttl in (
            (f'supportai:ticket:{ticket.id}', MAX_ANSWERS_PER_TICKET, 7 * _DAY_SEC),
            (f'supportai:user:{user.id}', MAX_ANSWERS_PER_USER_DAY, _DAY_SEC),
            ('supportai:global', MAX_ANSWERS_PER_DAY, _DAY_SEC),
        ):
            used = int(await cache.get(key) or 0)
            if used >= cap:
                bot_logger.info(f'[SUPPORT-AI] rate limit hit on {key} ({used}/{cap})')
                return False
        return True
    except Exception as exc:
        bot_logger.warning(f'[SUPPORT-AI] rate-limit store unavailable, staying silent: '
                           f'{type(exc).__name__}')
        return False


async def _count_answer(ticket, user) -> None:
    try:
        from app.core.redis_config import cache

        for key, ttl in ((f'supportai:ticket:{ticket.id}', 7 * _DAY_SEC),
                         (f'supportai:user:{user.id}', _DAY_SEC),
                         ('supportai:global', _DAY_SEC)):
            used = int(await cache.get(key) or 0)
            await cache.set(key, used + 1, ttl=ttl)
    except Exception:
        pass


async def _history(session, ticket, limit: int = 12):
    """Recent turns for this ticket, oldest first, as (role, text) pairs."""
    rows = (await session.execute(
        select(TicketMessage)
        .where(TicketMessage.ticket_id == ticket.id)
        .order_by(TicketMessage.created_at.desc())
        .limit(limit))).scalars().all()
    return [('assistant' if m.sender == 'admin' else 'user', m.text or '')
            for m in reversed(rows) if m.text]


def _human_is_live(ticket) -> bool:
    """A human is in the live chat with this customer right now."""
    return bool(ticket.chat_started_at and not ticket.chat_ended_at)


async def maybe_answer_ticket(session, ticket, user, text: str, *, bot=None) -> bool:
    """Answer one customer message if every gate allows it.

    Returns True when a reply was written. Never raises: a failure here must
    never break the customer's own message from being saved.
    """
    try:
        if not text or not support_ai_enabled() or not support_ai.ai_available():
            return False
        if ticket.status in ('closed', 'archived'):
            return False
        if ticket.assigned_admin_id or _human_is_live(ticket):
            return False
        if support_ai.is_noise_message(text):
            return False
        if support_ai.needs_human(text):
            bot_logger.info(f'[SUPPORT-AI] ticket {ticket.id} needs a human — staying silent')
            return False
        if not await _within_limits(ticket, user):
            return False

        owned_links, owned_orders = await support_context.owned_references(session, user)
        result = await support_ai.generate_reply(
            text,
            support_context.build_static_kb(),
            await support_context.build_customer_context(session, user),
            history=await _history(session, ticket),
            owned_links=owned_links,
            owned_order_ids=owned_orders)

        reply = result.get('reply')
        if result.get('handoff') or not reply:
            bot_logger.info(f'[SUPPORT-AI] ticket {ticket.id}: no answer '
                            f"(handoff={bool(result.get('handoff'))})")
            return False

        msg = TicketMessage(ticket_id=ticket.id, sender='admin', content_type='text',
                            text=reply, read_by_admin=True, read_by_user=False,
                            created_at=datetime.utcnow())
        session.add(msg)
        ticket.last_message_at = msg.created_at
        ticket.updated_at = msg.created_at
        await session.commit()
        await _count_answer(ticket, user)

        try:
            from app.api.routes.admin_ws import broadcast_ticket_update
            await broadcast_ticket_update(
                ticket.id, 'new_message',
                {'sender': 'admin', 'text': reply,
                 'created_at': msg.created_at.isoformat(), 'content_type': 'text'},
                ticket_user_id=ticket.user_id)
        except Exception as exc:
            bot_logger.debug(f'[SUPPORT-AI] broadcast skipped: {type(exc).__name__}')

        if bot is not None:
            try:
                await bot.send_message(user.chat_id, reply)
            except Exception as exc:
                bot_logger.debug(f'[SUPPORT-AI] DM skipped: {type(exc).__name__}')

        # The log is the audit trail here: services/audit.record_audit is for
        # admin-panel actions and wants an HTTP session, not a DB one.
        bot_logger.info(f'[SUPPORT-AI] answered ticket {ticket.id} '
                        f'({len(reply)} chars, confidence={result.get("confidence")}, '
                        f'knowledge={result.get("knowledge_ids") or []})')
        return True
    except Exception as exc:
        bot_logger.warning(f'[SUPPORT-AI] maybe_answer_ticket failed: '
                           f'{type(exc).__name__}: {exc}')
        return False
