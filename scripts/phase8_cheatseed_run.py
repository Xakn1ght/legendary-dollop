"""FINAL_TEST_CHECKLIST Phase 8 driver (cheat-seeds) — one shot, self-cleaning.

8.1 grant 40 season stars to the test admin account -> champion unlocks +
    free_plan coupon must zero a 20GB checkout quote.
8.2 seed 20 active referrals + 500k credit -> cash-out gate:
    100k (below min) / 250k -> deny -> refund / 250k -> approve -> paid.
8.3 wipe the seeds; the account's credit is restored to its pre-run value.

Money logic is exercised through the real code paths: flows/pricing.quote_purchase,
flows/cashout.create_cashout, CashoutRepository deny/paid. No Telegram DMs are
sent by these paths. Stars/coupons/badge stay granted (checklist: final DB reset
happens before launch anyway; Pasha can eyeball the Champion look on his phone).

    PYTHONPATH=src .venv/bin/python scripts/phase8_cheatseed_run.py
"""
import asyncio
import sys

from dotenv import load_dotenv

load_dotenv('config/.env')

from sqlalchemy import text  # noqa: E402

from app.database import crud  # noqa: E402
from app.database.models import AsyncSessionLocal, Referral, Subscription, User  # noqa: E402
from app.database.repos.cashout import CashoutRepository  # noqa: E402
from app.database.repos.reward import RewardRepository as RR  # noqa: E402
from app.services.flows import cashout as cashout_flow  # noqa: E402
from app.services.flows.errors import FlowError  # noqa: E402
from app.services.flows.pricing import quote_purchase  # noqa: E402

CHAT_ID = 8148909121  # Paşanim (test admin account)
SEED_BASE = 990000
RESULTS: list[tuple[bool, str]] = []


def check(ok: bool, label: str, detail: str = ''):
    RESULTS.append((ok, label))
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ''))


async def main():
    async with AsyncSessionLocal() as db:
        user = await crud.get_user(db, CHAT_ID)
        if not user:
            print('test account not found — abort')
            sys.exit(1)
        orig_credit = int(user.credit or 0)
        _, orig_stars = await crud.get_season_progress(db, user.id)
        print(f'snapshot: credit={orig_credit} season_stars={orig_stars}')

        # ── 8.1 grant 40★ ─────────────────────────────────────────
        print('\n── 8.1 grant 40★')
        total, unlocked = await RR.add_season_stars(db, user.id, 40)
        names = [x.get('milestone') for x in unlocked]
        print(f'  stars now {total}, newly unlocked: {names}')
        check(total == orig_stars + 40, 'stars incremented by 40', f'{orig_stars}→{total}')
        check(40 in names, 'Champion (40★) milestone unlocked')

        coupons = await crud.get_active_coupons(db, user.id)
        by_type = {}
        for c in coupons:
            by_type.setdefault(c.coupon_type, []).append(c)
        print('  wallet coupon types:', {k: len(v) for k, v in by_type.items()})
        check(bool(by_type.get('free_plan')), 'free_plan coupon(s) in wallet')

        # free_plan(20GB) must zero a 20GB checkout quote
        import json as _json
        plan20_coupon = None
        for c in by_type.get('free_plan', []):
            payload = c.payload if isinstance(c.payload, dict) else _json.loads(c.payload or '{}')
            if int(payload.get('plan_gb') or 0) == 20:
                plan20_coupon = c
                break
        from app.core.settings import PLANS
        plan20_name = None
        for name, info in PLANS.items():
            gb = int((info.get('data_limit') or 0) / (1024 ** 3)) if info.get('data_limit') else int(info.get('gb') or 0)
            if gb == 20:
                plan20_name = name
                break
        print(f'  20GB plan={plan20_name!r} coupon_id={getattr(plan20_coupon, "id", None)}')
        if plan20_name and plan20_coupon:
            q = await quote_purchase(db, user, plan_name=plan20_name, coupon_id=plan20_coupon.id)
            check(q.final_price == 0, 'free_plan coupon zeroes 20GB checkout',
                  f'plan={q.plan_price} final={q.final_price}')
        else:
            check(False, 'free_plan(20GB) coupon + plan lookup', 'missing plan or coupon')

        # ── 8.2 seed 20 active referrals + 500k credit ────────────
        print('\n── 8.2 cash-out gate')
        for i in range(20):
            u = User(chat_id=SEED_BASE + i, referral_code=f'seedref{i}')
            db.add(u)
            await db.flush()
            db.add(Referral(referrer_id=user.id, referee_id=u.id))
            db.add(Subscription(user_id=u.id, marzban_username=f'seedref{i}',
                                status='active', price=90000))
        # cash-out also demands the REQUESTER has an active paid sub
        had_own_sub = await CashoutRepository.has_active_paid_subscription(db, user.id)
        if not had_own_sub:
            db.add(Subscription(user_id=user.id, marzban_username='seedself',
                                status='active', price=90000))
        user.credit = 500_000
        await db.commit()
        active = await cashout_flow.count_active_referrals(db, user.id)
        check(active >= 20, '20 active referrals counted', str(active))

        # a) below minimum
        try:
            await cashout_flow.create_cashout(db, user, amount=100_000)
            check(False, '100k rejected (min 200k)')
        except FlowError as e:
            check(e.code == 'amount_below_minimum', '100k rejected (min 200k)', e.code)

        # b) 250k -> reserved
        req = await cashout_flow.create_cashout(db, user, amount=250_000, destination='6037-9911-1111-1111')
        await db.refresh(user)
        check(req is not None and req.status == 'pending', '250k request created', f'id={req.id}')
        check(int(user.credit) == 250_000, 'credit reserved on request', f'credit={user.credit}')

        # c) deny -> refund
        denied = await CashoutRepository.deny_cashout_request(db, req.id, admin_user_id=user.id, admin_note='phase8 test deny')
        await db.refresh(user)
        check(denied is not None and denied.status == 'denied', 'deny processed')
        check(int(user.credit) == 500_000, 'credit refunded after deny', f'credit={user.credit}')

        # d) again 250k -> approve/paid
        req2 = await cashout_flow.create_cashout(db, user, amount=250_000, destination='6037-9911-1111-1111')
        paid = await CashoutRepository.mark_cashout_paid(db, req2.id, admin_user_id=user.id, admin_note='phase8 test approve')
        await db.refresh(user)
        check(paid is not None and paid.status == 'paid', 'approve -> paid')
        check(int(user.credit) == 250_000, 'credit stays deducted after payout', f'credit={user.credit}')

        # double-deny guard: processed request can't flip
        again = await CashoutRepository.deny_cashout_request(db, req2.id)
        check(again is None, 'paid request cannot be denied afterwards')

        # ── 8.3 wipe seeds + restore credit ───────────────────────
        print('\n── 8.3 wipe')
        await db.execute(text("DELETE FROM subscriptions WHERE marzban_username LIKE 'seedref%' OR marzban_username = 'seedself'"))
        await db.execute(text(
            'DELETE FROM referrals WHERE referee_id IN '
            f'(SELECT id FROM users WHERE chat_id BETWEEN {SEED_BASE} AND {SEED_BASE + 19})'
        ))
        await db.execute(text(f'DELETE FROM users WHERE chat_id BETWEEN {SEED_BASE} AND {SEED_BASE + 19}'))
        user.credit = orig_credit
        await db.commit()
        left = await db.scalar(text(f'SELECT count(*) FROM users WHERE chat_id BETWEEN {SEED_BASE} AND {SEED_BASE + 19}'))
        active_after = await cashout_flow.count_active_referrals(db, user.id)
        await db.refresh(user)
        check(int(left or 0) == 0, 'seed users wiped')
        check(active_after < 20, 'referral count back to real', str(active_after))
        check(int(user.credit) == orig_credit, 'credit restored to snapshot', f'credit={user.credit}')
        print('\nNOTE: the two cashout_requests rows (denied+paid) and the 40★/coupons/'
              'badge stay for Pasha to eyeball; the final pre-launch DB reset clears them.')

    failed = [label for ok, label in RESULTS if not ok]
    print(f"\n{'='*56}\nPhase 8: {len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    if failed:
        print('FAILED:', failed)
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
