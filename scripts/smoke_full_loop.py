#!/usr/bin/env python3
"""Full money-loop smoke test against the REAL stack (DB + Marzban + Telegram).

Exercises, in order, printing PASS/FAIL per step:
  1. quote          — price a 20GB plan for the buyer
  2. order          — create a draft purchase order (with referrer attribution)
  3. receipt        — attach a receipt, order goes pending
  4. approve        — admin approval path: provisions in Marzban, DMs the buyer,
                      creates the referrer's 4-choice voucher (+50 XP)
  5. redeem-star    — referrer redeems the voucher as a season star via the
                      dashboard HTTP API (forged initData, same as smoke_dashboard)
  6. coupon         — quote with the freshly unlocked coupon, place an order,
                      cancel it, verify the coupon is restored (spend safety)
  7. charge         — top-up preset on the new sub: receipt → admin approve →
                      Marzban data_limit/expire updated; charge voucher created
  8. cashout-gate   — cashout via HTTP correctly refuses (< 20 active referrals)

Leaves the provisioned test subscription in place so it can be inspected from
the phone; clean up afterwards with:
  PYTHONPATH=src .venv/bin/python scripts/smoke_full_loop.py --cleanup <marzban_username>

Run: PYTHONPATH=src .venv/bin/python scripts/smoke_full_loop.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / "config" / ".env")

REFERRER_CHAT = 8148909121  # Paşanim (has referral link to buyer from earlier test rounds)
BUYER_CHAT = 8120318706     # Rakai
PLAN_20GB_FA = "۲۰ گیگ | یکماه"
CHARGE_PRESET_FA = "۲۰ گیگ | یکماه"

_results: list[tuple[str, bool, str]] = []


def report(step: str, ok: bool, detail: str = ""):
    _results.append((step, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {step}  {detail}")


def http_call(chat_id: int, path: str, method: str = "GET", body=None):
    """Dashboard API call with forged initData (same helper as smoke_dashboard)."""
    from scripts.smoke_dashboard import call  # type: ignore
    return call(chat_id, path, method=method, body=body)


async def main():
    from aiogram import Bot
    from app.core.settings import BOT_TOKEN
    from app.database import crud
    from app.database.models import AsyncSessionLocal
    from app.services.flows import charge as charge_flow
    from app.services.flows import purchase as purchase_flow
    from app.services.flows.pricing import quote_purchase
    from app.services.pasarguard import pasarguard_api
    from app.services.subscription_processing import process_approved_subscription

    bot = Bot(BOT_TOKEN)
    marz_username = None
    try:
        async with AsyncSessionLocal() as session:
            referrer = await crud.get_user(session, REFERRER_CHAT)
            buyer = await crud.get_user(session, BUYER_CHAT)
            if not referrer or not buyer:
                report("setup", False, "test users missing — adjust REFERRER_CHAT/BUYER_CHAT")
                return

            # 1. quote
            quote = await quote_purchase(session, buyer, plan_name=PLAN_20GB_FA)
            report("quote", quote.final_price > 0, f"plan={PLAN_20GB_FA!r} final={quote.final_price:,}")

            # 2. order (draft) with referrer attribution
            order = await purchase_flow.start_purchase_order(
                session, buyer, quote=quote, referrer_id=referrer.id, bot=bot,
            )
            sub = order.subscription
            marz_username = sub.marzban_username
            report("order", sub.status == "draft", f"sub_id={sub.id} service={marz_username}")

            # 3. receipt → pending
            sub = await purchase_flow.submit_purchase_receipt(
                session, buyer, sub.id, receipt_message_id=-1,
            )
            report("receipt", sub.status == "pending", f"status={sub.status}")

            # 4. admin approve → provision + referral voucher
            stars_before = (await crud.get_season_progress(session, referrer.id))[1]
            vouchers_before = len(await crud.get_unspent_rewards_by_referrer(session, referrer.id))
            ok = await process_approved_subscription(sub.id, session, bot)
            await session.refresh(sub)
            minfo = await pasarguard_api.get_user_info(marz_username)
            provisioned = bool(ok and minfo and (minfo.get("status") == "active"))
            report("approve+provision", provisioned,
                   f"marzban={marz_username} limit_gb={round(((minfo or {}).get('data_limit') or 0)/2**30, 1)}")

            vouchers_after = await crud.get_unspent_rewards_by_referrer(session, referrer.id)
            new_vouchers = [v for v in vouchers_after if v.stars]
            report("referral-voucher", len(vouchers_after) == vouchers_before + 1,
                   f"open_vouchers={len(vouchers_after)} (star option on newest: "
                   f"{vouchers_after[-1].stars if vouchers_after else '-'})")

        # 5. redeem the newest voucher as a season star over HTTP (owner = referrer)
        if new_vouchers:
            reward_id = new_vouchers[-1].id
            status, data = http_call(
                REFERRER_CHAT, f"/api/dashboard/referral-rewards/{reward_id}/redeem",
                method="POST", body={"reward_type": "star"},
            )
            async with AsyncSessionLocal() as session:
                referrer = await crud.get_user(session, REFERRER_CHAT)
                stars_now = (await crud.get_season_progress(session, referrer.id))[1]
            report("redeem-star", status == 200 and stars_now == stars_before + 1,
                   f"http={status} season_stars={stars_before}->{stars_now}")

            # 1-star milestone should have auto-unlocked a coupon
            status, season = http_call(REFERRER_CHAT, "/api/dashboard/season")
            coupons = (season or {}).get("coupons", [])
            first_spark = [c for c in coupons if c.get("milestone_stars") == 1 and c.get("coupon_type") == "discount_percent"]
            report("milestone-coupon", status == 200 and bool(first_spark),
                   f"coupons={[(c.get('milestone_stars'), c.get('coupon_type')) for c in coupons]}")
        else:
            first_spark = []
            report("redeem-star", False, "no star voucher to redeem")

        # 6. coupon spend safety: quote+order with the coupon, cancel, expect restore
        if first_spark:
            coupon_id = first_spark[0]["id"]
            async with AsyncSessionLocal() as session:
                referrer = await crud.get_user(session, REFERRER_CHAT)
                q2 = await quote_purchase(session, referrer, plan_name=PLAN_20GB_FA, coupon_id=coupon_id)
                expected_cut = q2.coupon.discount_amount if q2.coupon else 0
                o2 = await purchase_flow.start_purchase_order(session, referrer, quote=q2, bot=bot)
                c = await crud.get_coupon_by_id(session, coupon_id)
                consumed = c.status == "used"
                await purchase_flow.cancel_purchase_order(session, referrer, o2.subscription.id)
                c = await crud.get_coupon_by_id(session, coupon_id)
                restored = c.status == "active"
            report("coupon-spend+restore", consumed and restored and expected_cut > 0,
                   f"discount={expected_cut:,} used-on-order={consumed} restored-on-cancel={restored}")

        # 7. charge top-up on the new sub → receipt → approve → Marzban updated
        async with AsyncSessionLocal() as session:
            buyer = await crud.get_user(session, BUYER_CHAT)
            subs = await crud.get_user_active_subscriptions(session, buyer.id)
            target = next((s for s in subs if s.marzban_username == marz_username), None)
            if not target:
                report("charge", False, "provisioned sub not found active")
            else:
                res = await charge_flow.start_charge_order(
                    session, buyer,
                    subscription_id=target.id,
                    package_name=CHARGE_PRESET_FA,
                    charge_type="normal_5gb_limit",
                )
                req = await charge_flow.submit_charge_receipt(
                    session, buyer, res.charge_request.id, receipt_message_id=-1,
                )
                before = await pasarguard_api.get_user_info(marz_username)
                approved = await charge_flow.approve_charge(session, req.id, user_bot=bot)
                after = await pasarguard_api.get_user_info(marz_username)
                grew = (after or {}).get("expire") and (before or {}).get("expire") and after["expire"] > before["expire"]
                report("charge-approve", bool(approved and grew),
                       f"limit_gb={round(((after or {}).get('data_limit') or 0)/2**30, 1)} expire+={bool(grew)}")

        # 8. cashout gate over HTTP (referrer has 1 active referral < 20)
        status, data = http_call(
            REFERRER_CHAT, "/api/dashboard/wallet/cashout",
            method="POST", body={"amount": 250000, "destination": "IR000000000000000000000000"},
        )
        gate_ok = status == 403 and (data or {}).get("error") == "requires_vip_promoter"
        report("cashout-gate", gate_ok, f"http={status} error={(data or {}).get('error')}")

    finally:
        await bot.session.close()

    print("\n──────── summary ────────")
    fails = [r for r in _results if not r[1]]
    for step, ok, detail in _results:
        print(f"  {'✅' if ok else '❌'} {step}")
    print(f"\n{len(_results) - len(fails)}/{len(_results)} passed."
          + (f"  Marzban test user left in place: {marz_username}" if marz_username else ""))
    sys.exit(1 if fails else 0)


async def cleanup(username: str):
    from app.database.models import AsyncSessionLocal, Subscription
    from app.services.pasarguard import pasarguard_api
    from sqlalchemy import select

    deleted = await pasarguard_api.delete_user(username)
    async with AsyncSessionLocal() as session:
        sub = (await session.execute(
            select(Subscription).filter(Subscription.marzban_username == username)
        )).scalars().first()
        if sub:
            sub.status = "removed"
            await session.commit()
    print(f"cleanup: pasarguard_deleted={bool(deleted)} sub_marked_removed={bool(sub)}")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--cleanup":
        asyncio.run(cleanup(sys.argv[2]))
    else:
        asyncio.run(main())
