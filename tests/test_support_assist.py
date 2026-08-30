#!/usr/bin/env python3
"""Ticket wiring for the support assistant: every gate that keeps it quiet.

Silence is the safe outcome here — the ticket just waits for a human, which
is what happens today. So each gate gets its own case.

    PYTHONPATH=src .venv/bin/python tests/test_support_assist.py
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from app.services import support_assist as sa  # noqa: E402

PASS = []


def check(name, cond, detail=''):
    assert cond, f'{name}: {detail}'
    PASS.append(name)


class Ticket:
    def __init__(self, **kw):
        self.id = 1
        self.user_id = 7
        self.status = 'pending'
        self.assigned_admin_id = None
        self.chat_started_at = None
        self.chat_ended_at = None
        self.last_message_at = None
        self.updated_at = None
        self.__dict__.update(kw)


class User:
    id = 7
    chat_id = 12345
    full_name = 'تست'
    username = 'test'
    credit = 0


class Sub:
    def __init__(self, sub_id, plan='۲۰ گیگ'):
        self.id = sub_id
        self.plan_name = plan
        self.marzban_username = f'user{sub_id}'


class Session:
    """Minimal async session: records what would have been written."""

    def __init__(self, rows=()):
        self.added = []
        self.commits = 0
        self.rows = list(rows)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def execute(self, *_a, **_kw):
        rows = self.rows

        class _R:
            def scalars(self_inner):
                class _S:
                    def all(self_s):
                        return rows
                return _S()
        return _R()


class Bot:
    """Captures the DM the assistant would send."""

    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, reply_markup=None):
        self.sent.append((chat_id, text, reply_markup))


def _install(reply='پاسخ تست', handoff=False, allow=True):
    """Point the service at a fake brain and open all the outer gates."""
    sa.support_ai_enabled = lambda: True
    sa.support_ai.ai_available = lambda: True

    async def _gen(*_a, **_kw):
        out = {'reply': reply, 'handoff': handoff, 'knowledge_ids': [],
               'confidence': 0.9}
        return out

    sa.support_ai.generate_reply = _gen

    async def _refs(_s, _u):
        return set(), set()

    sa.support_context.owned_references = _refs
    sa.support_context.build_static_kb = lambda *a, **kw: 'KB'

    async def _ctx(_s, _u):
        return 'CTX'

    sa.support_context.build_customer_context = _ctx

    async def _limits(_t, _u):
        return allow

    sa._within_limits = _limits

    async def _count(_t, _u):
        return None

    sa._count_answer = _count

    async def _hist(_s, _t, limit=12):
        return []

    sa._history = _hist


def _run(ticket, text, user=None):
    return asyncio.run(sa.maybe_answer_ticket(Session(), ticket, user or User(), text))


def test_answers_when_every_gate_passes():
    _install()
    session = Session()
    ticket = Ticket()
    answered = asyncio.run(sa.maybe_answer_ticket(session, ticket, User(), 'چطور وصل بشم؟'))
    check('answers a plain question', answered is True)
    check('one message written', len(session.added) == 1)
    written = session.added[0]
    check("written as 'admin' so both UIs render it on the support side",
          written.sender == 'admin')
    check('reply text stored', written.text == 'پاسخ تست')
    check('unread for the customer', written.read_by_user is False)
    check('ticket timestamps bumped', isinstance(ticket.last_message_at, datetime))
    check('committed', session.commits == 1)


def test_switch_off_is_silent():
    _install()
    sa.support_ai_enabled = lambda: False
    check('off switch silences', _run(Ticket(), 'چطور وصل بشم؟') is False)


def test_no_provider_is_silent():
    _install()
    sa.support_ai.ai_available = lambda: False
    check('no configured provider silences', _run(Ticket(), 'چطور وصل بشم؟') is False)


def test_human_presence_is_silent():
    _install()
    check('assigned ticket silences',
          _run(Ticket(assigned_admin_id=3), 'چطور وصل بشم؟') is False)
    check('live chat silences',
          _run(Ticket(chat_started_at=datetime.utcnow()), 'چطور وصل بشم؟') is False)
    check('ended chat does NOT silence',
          _run(Ticket(chat_started_at=datetime.utcnow(),
                      chat_ended_at=datetime.utcnow()), 'چطور وصل بشم؟') is True)
    check('closed ticket silences', _run(Ticket(status='closed'), 'چطور وصل بشم؟') is False)


def test_noise_and_escalation_never_reach_the_model():
    called = []
    _install()
    real = sa.support_ai.generate_reply

    async def _spy(*a, **kw):
        called.append(1)
        return await real(*a, **kw)

    sa.support_ai.generate_reply = _spy
    check('emoji-only is silent', _run(Ticket(), '😂😂😂') is False)
    check('bare thanks is silent', _run(Ticket(), 'ممنون') is False)
    check('refund demand is silent', _run(Ticket(), 'پولمو پس بده') is False)
    check('act-for-me demand is silent', _run(Ticket(), 'خودت تایید کن') is False)
    check('none of those cost a model call', called == [], called)


def test_handoff_and_empty_reply_are_silent():
    _install(handoff=True)
    check('model handoff silences', _run(Ticket(), 'چطور وصل بشم؟') is False)
    _install(reply=None)
    check('no reply silences', _run(Ticket(), 'چطور وصل بشم؟') is False)


def test_rate_limit_is_silent():
    _install(allow=False)
    check('rate limit silences', _run(Ticket(), 'چطور وصل بشم؟') is False)


def test_failure_never_breaks_the_customers_message():
    _install()

    async def _boom(*_a, **_kw):
        raise RuntimeError('provider exploded')

    sa.support_ai.generate_reply = _boom
    check('an exception degrades to silence, not an error',
          _run(Ticket(), 'چطور وصل بشم؟') is False)


def test_buttons_only_when_the_brain_asks():
    _install()
    bot = Bot()
    asyncio.run(sa.maybe_answer_ticket(Session([Sub(4)]), Ticket(), User(),
                                       'چطور وصل بشم؟', bot=bot))
    check('a plain answer carries no buttons', bot.sent[0][2] is None)


def test_button_flags_pick_the_right_action():
    for flag, prefix in (('show_links', 'link_'), ('show_renew', 'charge_'),
                         ('show_subs', 'usage_')):
        _install()
        real = sa.support_ai.generate_reply

        async def _gen(*a, _flag=flag, **kw):
            out = await real(*a, **kw)
            out[_flag] = True
            return out

        sa.support_ai.generate_reply = _gen
        bot = Bot()
        asyncio.run(sa.maybe_answer_ticket(Session([Sub(4), Sub(9)]), Ticket(), User(),
                                           'سوال', bot=bot))
        markup = bot.sent[0][2]
        check(f'{flag} attaches buttons', markup is not None)
        data = [b.callback_data for row in markup.inline_keyboard for b in row]
        check(f'{flag} uses {prefix} callbacks', data == [f'{prefix}4', f'{prefix}9'], data)


def test_no_subscriptions_means_no_buttons():
    _install()
    real = sa.support_ai.generate_reply

    async def _gen(*a, **kw):
        out = await real(*a, **kw)
        out['show_links'] = True
        return out

    sa.support_ai.generate_reply = _gen
    bot = Bot()
    asyncio.run(sa.maybe_answer_ticket(Session([]), Ticket(), User(), 'سوال', bot=bot))
    check('no active subscription means no buttons', bot.sent[0][2] is None)


def main():
    for fn in [v for k, v in sorted(globals().items()) if k.startswith('test_')]:
        fn()
        print('PASS', fn.__name__)
    print(f'\n{len(PASS)} support-wiring checks passed.')


if __name__ == '__main__':
    main()
