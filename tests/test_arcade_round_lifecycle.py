"""Arcade round lifecycle tests (checkpoints + finalization, 2026-07-19).

Uses an in-memory FakeRedis (same monkeypatch style as test_arcade_prizes.py
uses for the round-token memory path) and in-memory SQLite. Covers:
- checkpoint monotonicity + per-window burst allowance
- finalize-on-new-round consumes the daily attempt at the last checkpoint
- a sub-20s abandoned round costs nothing (silent invalidate)
- finalized round then a real submit -> friendly "already recorded",
  no cheat flag, no double reward
- legacy no-checkpoint client passes through the exact old gates

Run: PYTHONPATH=src python tests/test_arcade_round_lifecycle.py
"""
import asyncio
import fnmatch
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import app.database.models as models_mod  # noqa: E402
from app.database import crud  # noqa: E402
from app.database.models import ArcadeFlag, Base, RewardHistory, User  # noqa: E402
from app.utils.tehran_time import tehran_today  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        FAIL += 1
        print(f"FAIL  {name}")


# ---------------------------------------------------------------------------
# Fake infra
# ---------------------------------------------------------------------------

class FakeRedis:
    """Just enough async redis for round_start + round_lifecycle."""

    def __init__(self):
        self.store: dict[str, str] = {}

    async def set(self, key, value, ex=None):
        self.store[key] = str(value)
        return True

    async def get(self, key):
        return self.store.get(key)

    async def getdel(self, key):
        return self.store.pop(key, None)

    async def getset(self, key, value):
        old = self.store.get(key)
        self.store[key] = str(value)
        return old

    async def delete(self, key):
        return 1 if self.store.pop(key, None) is not None else 0

    async def exists(self, key):
        return 1 if key in self.store else 0

    async def expire(self, key, ttl):
        return True

    async def scan(self, cursor=0, match="*", count=100):
        return 0, [k for k in list(self.store.keys()) if fnmatch.fnmatch(k, match)]


class FakeRequest:
    def __init__(self, payload=None, query=None):
        self._payload = payload or {}
        self.query = query or {}
        self.headers = {}
        self.cookies = {}

    async def json(self):
        return self._payload


async def make_session():
    engine = create_async_engine("sqlite+aiosqlite://", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)


async def seed_user(db, chat_id, name):
    u = User(chat_id=chat_id, full_name=name, show_on_leaderboard=True)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


def wire_fakes(fake_redis, maker):
    """Point every module involved at the fakes."""
    from app.api.routes.game import round_lifecycle as rl
    from app.api.routes.game import round_start as rs
    from app.api.routes.game.arcade_submit import handler as submit_mod

    async def _fake_client():
        return fake_redis

    rs.get_redis_client = _fake_client
    rl.get_redis_client = _fake_client
    models_mod.AsyncSessionLocal = maker            # finalize_round sessions
    submit_mod.AsyncSessionLocal = maker            # real-submit sessions
    submit_mod._verify_webapp_auth = lambda req: (None, None)  # per-test override
    return rs, rl, submit_mod


def backdate_token(fake_redis, token, seconds):
    """Shift a round token's issued_ts into the past (simulates elapsed play)."""
    key = "arcade:round:" + token
    uid, issued = fake_redis.store[key].split(":")
    fake_redis.store[key] = f"{uid}:{int(issued) - seconds}"


def backdate_meta(fake_redis, token, *, issued_shift=0, last_shift=0):
    key = "arcade:round:meta:" + token
    meta = json.loads(fake_redis.store[key])
    meta["issued_ts"] -= issued_shift
    meta["first_ts"] -= issued_shift
    meta["last_ts"] -= last_shift
    fake_redis.store[key] = json.dumps(meta)
    return meta


async def checkpoint(rl, uid, token, score, coins=0):
    req = FakeRequest({"round_token": token, "score": score, "coins": coins})
    rl._auth_user = lambda request: uid
    resp = await rl.handle_arcade_checkpoint(req)
    return json.loads(resp.body.decode())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_checkpoint_monotonic_and_burst():
    print("-- checkpoint monotonicity + burst allowance --")
    fake = FakeRedis()
    maker = await make_session()
    rs, rl, _ = wire_fakes(fake, maker)

    tok = await rs.issue_round_token(42)
    d = await checkpoint(rl, 42, tok, 1000)
    check("first checkpoint stored", d.get("stored") is True)

    meta = json.loads(fake.store["arcade:round:meta:" + tok])
    check("no anomaly on a sane first window", meta["anomalies"] == 0)

    # same second, +8000 burst on top of the rate budget -> allowed
    d = await checkpoint(rl, 42, tok, 1000 + 500 * 1 + 8000)
    meta = json.loads(fake.store["arcade:round:meta:" + tok])
    check("burst allowance absorbs a bomb-wipe dump", meta["anomalies"] == 0)

    # way over budget in ~0-1s -> anomaly recorded, but request still ok
    d = await checkpoint(rl, 42, tok, meta["last_score"] + 60_000)
    check("over-rate checkpoint still returns ok", d.get("ok") is True)
    meta = json.loads(fake.store["arcade:round:meta:" + tok])
    check("over-rate window recorded as anomaly", meta["anomalies"] == 1)

    # decreasing score: anomaly + max kept
    high = meta["last_score"]
    await checkpoint(rl, 42, tok, high - 5000)
    meta = json.loads(fake.store["arcade:round:meta:" + tok])
    check("decreasing score keeps the max", meta["last_score"] == high)
    check("decreasing score counts as anomaly", meta["anomalies"] == 2)

    # foreign user cannot write checkpoints
    d = await checkpoint(rl, 43, tok, high + 100)
    check("foreign user checkpoint not stored", d.get("stored") is False)
    meta = json.loads(fake.store["arcade:round:meta:" + tok])
    check("meta untouched by foreign user", meta["last_score"] == high)


async def test_finalize_on_new_round():
    print("-- abandoned round with checkpoints is finalized on next round-start --")
    fake = FakeRedis()
    maker = await make_session()
    rs, rl, _ = wire_fakes(fake, maker)

    async with maker() as db:
        await seed_user(db, 4242, "abandoner")

    tok1 = await rs.issue_round_token(4242)
    await rl.set_open_round(4242, tok1)
    await checkpoint(rl, 4242, tok1, 9000, coins=2)
    # simulate 90s of play recorded in the meta
    backdate_meta(fake, tok1, issued_shift=90)
    backdate_token(fake, tok1, 90)

    # player closed the app, later starts a new round
    tok2 = await rs.issue_round_token(4242)
    await rl.finalize_previous_round_of(4242, tok2)

    async with maker() as db:
        play = await crud.check_daily_game_play(
            db, (await db.execute(select(User).filter(User.chat_id == 4242))).scalars().first().id,
            tehran_today(),
        )
        check("daily attempt consumed", play is not None and play.rewarded is True)
        check("finalized at the last checkpoint score", play.best_score == 9000)
        check("coins from the checkpoint were paid (capped)", True)  # asserted below via wallet
        user = (await db.execute(select(User).filter(User.chat_id == 4242))).scalars().first()
        wallet = await crud.get_or_create_arcade_wallet(db, user.id)
        check("checkpoint coins credited within cap", wallet.coins == 2)
        check("XP granted for the finalized run", (user.experience_points or 0) > 0)
        check("no credit minted", (user.credit or 0) == 0)

    check("old token consumed", "arcade:round:" + tok1 not in fake.store)
    check("tombstone written", "arcade:round:done:" + tok1 in fake.store)
    check("new round token still alive", "arcade:round:" + tok2 in fake.store)


async def test_short_abandon_costs_nothing():
    print("-- sub-20s abandoned round dies silently --")
    fake = FakeRedis()
    maker = await make_session()
    rs, rl, _ = wire_fakes(fake, maker)

    async with maker() as db:
        u = await seed_user(db, 5555, "quick-quitter")
        uid_db = u.id

    tok1 = await rs.issue_round_token(5555)
    await rl.set_open_round(5555, tok1)
    await checkpoint(rl, 5555, tok1, 300)  # ~0s of timeline

    tok2 = await rs.issue_round_token(5555)
    await rl.finalize_previous_round_of(5555, tok2)

    async with maker() as db:
        play = await crud.check_daily_game_play(db, uid_db, tehran_today())
        check("no daily attempt consumed", play is None or play.rewarded is False)
        flags = (await db.execute(select(ArcadeFlag))).scalars().all()
        check("no cheat flag", len(flags) == 0)
    check("short round token still consumed", "arcade:round:" + tok1 not in fake.store)

    # a round with NO checkpoints at all is also free
    tok3 = await rs.issue_round_token(5555)
    await rl.finalize_previous_round_of(5555, tok3)
    async with maker() as db:
        play = await crud.check_daily_game_play(db, uid_db, tehran_today())
        check("checkpoint-less round also free", play is None or play.rewarded is False)


async def test_finalized_then_real_submit_is_friendly():
    print("-- finalized round + late real submit -> friendly, no flag, no double pay --")
    fake = FakeRedis()
    maker = await make_session()
    rs, rl, submit_mod = wire_fakes(fake, maker)

    async with maker() as db:
        u = await seed_user(db, 7777, "interrupted")
        uid_db = u.id

    tok = await rs.issue_round_token(7777)
    await rl.set_open_round(7777, tok)
    await checkpoint(rl, 7777, tok, 15000, coins=1)
    backdate_meta(fake, tok, issued_shift=120)
    backdate_token(fake, tok, 120)

    # sweep-style finalization (e.g. 30 min stale)
    settled = await rl.finalize_round(tok, reason="stale")
    check("stale round finalized", settled is True)

    async with maker() as db:
        user = (await db.execute(select(User).filter(User.id == uid_db))).scalars().first()
        xp_after_finalize = user.experience_points or 0
        play = await crud.check_daily_game_play(db, uid_db, tehran_today())
        check("finalized at checkpoint score", play.best_score == 15000)

    # ...the client actually comes back and its queued submit lands late.
    # (For a user whose daily is already settled, the daily-limit branch
    # answers first — equally friendly. Both outcomes are "no flag, no pay".)
    submit_mod._verify_webapp_auth = lambda req: (7777, None)
    req = FakeRequest({
        "score": 15400, "duration": 130, "practice": False,
        "round_token": tok, "coins": 1, "display_name": "interrupted",
    })
    resp = await submit_mod.handle_arcade_submit(req)
    data = json.loads(resp.body.decode())
    check("late submit answered ok", data.get("ok") is True)
    check("late submit answered friendly",
          bool(data.get("already_recorded") or data.get("already_played")))
    check("late submit not treated as cheating", not data.get("rejected"))

    async with maker() as db:
        flags = (await db.execute(select(ArcadeFlag))).scalars().all()
        check("no no_token flag for the late submit", len(flags) == 0)
        user = (await db.execute(select(User).filter(User.id == uid_db))).scalars().first()
        check("no double XP", (user.experience_points or 0) == xp_after_finalize)
        arcade_rows = (await db.execute(
            select(RewardHistory).filter(RewardHistory.user_id == uid_db,
                                         RewardHistory.source == "arcade")
        )).scalars().all()
        check("exactly one arcade grant", len(arcade_rows) == 1)

    # Direct tombstone path: daily NOT settled (finalize rejected the run or
    # invalidated it) but the token is consumed + tombstoned -> the duplicate
    # submit must get "already recorded", NOT a no_token cheat flag.
    async with maker() as db:
        w = await seed_user(db, 7878, "tombstoned")
        w_db = w.id
    tok_t = await rs.issue_round_token(7878)
    consumed = await rs.consume_round_token_any(tok_t)
    check("tombstone setup consumed the token", consumed is not None)
    await rl.mark_round_done(tok_t)
    submit_mod._verify_webapp_auth = lambda req: (7878, None)
    req = FakeRequest({
        "score": 4000, "duration": 60, "practice": False,
        "round_token": tok_t, "coins": 0,
    })
    resp = await submit_mod.handle_arcade_submit(req)
    data = json.loads(resp.body.decode())
    check("tombstoned submit marked already_recorded", data.get("already_recorded") is True)
    async with maker() as db:
        flags = (await db.execute(
            select(ArcadeFlag).filter(ArcadeFlag.user_id == w_db)
        )).scalars().all()
        check("tombstoned submit not flagged", len(flags) == 0)


async def test_legacy_client_unchanged():
    print("-- legacy v27 client (no checkpoints) keeps the exact old gates --")
    fake = FakeRedis()
    maker = await make_session()
    rs, rl, submit_mod = wire_fakes(fake, maker)

    async with maker() as db:
        u = await seed_user(db, 9999, "legacy-player")
        uid_db = u.id

    # happy path: 60s round, plausible score
    tok = await rs.issue_round_token(9999)
    backdate_token(fake, tok, 60)
    submit_mod._verify_webapp_auth = lambda req: (9999, None)
    req = FakeRequest({
        "score": 20000, "duration": 65, "practice": False,
        "round_token": tok, "coins": 0, "display_name": "legacy-player",
    })
    resp = await submit_mod.handle_arcade_submit(req)
    data = json.loads(resp.body.decode())
    check("legacy submit rewarded", data.get("rewarded") is True)

    async with maker() as db:
        play = await crud.check_daily_game_play(db, uid_db, tehran_today())
        check("legacy best_score written", play.best_score == 20000)

    # cheat path: score above 500 pts/s session average -> implausible_score
    async with maker() as db:
        c = await seed_user(db, 10000, "legacy-cheat")
        cheat_db = c.id
    tok2 = await rs.issue_round_token(10000)
    backdate_token(fake, tok2, 60)
    submit_mod._verify_webapp_auth = lambda req: (10000, None)
    req = FakeRequest({
        "score": 60 * 500 + 1, "duration": 65, "practice": False,
        "round_token": tok2, "coins": 0, "display_name": "legacy-cheat",
    })
    resp = await submit_mod.handle_arcade_submit(req)
    data = json.loads(resp.body.decode())
    check("legacy implausible score rejected", data.get("rejected") is True)
    async with maker() as db:
        flags = (await db.execute(
            select(ArcadeFlag).filter(ArcadeFlag.user_id == cheat_db)
        )).scalars().all()
        check("legacy flag reason unchanged", len(flags) == 1 and flags[0].reason == "implausible_score")

    # no-token path still flags exactly as before (fresh user — the daily
    # limit of already-played users answers before the token gate)
    async with maker() as db:
        n = await seed_user(db, 10001, "legacy-notoken")
        n_db = n.id
    submit_mod._verify_webapp_auth = lambda req: (10001, None)
    req = FakeRequest({
        "score": 5000, "duration": 65, "practice": False,
        "round_token": "definitely-not-a-token", "coins": 0,
    })
    resp = await submit_mod.handle_arcade_submit(req)
    data = json.loads(resp.body.decode())
    check("unknown token still rejected", data.get("rejected") is True)
    async with maker() as db:
        flags = (await db.execute(
            select(ArcadeFlag).filter(ArcadeFlag.user_id == n_db)
        )).scalars().all()
        check("no_token flag recorded", any(f.reason == "no_token" for f in flags))


async def test_checkpoint_curve_rejection_on_submit():
    print("-- checkpoint-aware submit: dirty window history is flagged --")
    fake = FakeRedis()
    maker = await make_session()
    rs, rl, submit_mod = wire_fakes(fake, maker)

    async with maker() as db:
        u = await seed_user(db, 11111, "curver")
        uid_db = u.id

    tok = await rs.issue_round_token(11111)
    # two over-rate windows -> anomalies = 2 > allowed 1
    await checkpoint(rl, 11111, tok, 100_000)
    await checkpoint(rl, 11111, tok, 260_000)
    backdate_meta(fake, tok, issued_shift=60)
    backdate_token(fake, tok, 60)

    submit_mod._verify_webapp_auth = lambda req: (11111, None)
    req = FakeRequest({
        "score": 260_000, "duration": 65, "practice": False,
        "round_token": tok, "coins": 0,
    })
    resp = await submit_mod.handle_arcade_submit(req)
    data = json.loads(resp.body.decode())
    check("anomalous curve rejected", data.get("rejected") is True)
    async with maker() as db:
        flags = (await db.execute(
            select(ArcadeFlag).filter(ArcadeFlag.user_id == uid_db)
        )).scalars().all()
        check("flag reason is checkpoint_curve",
              len(flags) == 1 and flags[0].reason == "checkpoint_curve")

    # clean checkpoints + a final jump inside the tail allowance -> rewarded,
    # even though the SESSION AVERAGE would have failed the old blunt gate
    async with maker() as db:
        await seed_user(db, 12121, "burst-legit")
    tok2 = await rs.issue_round_token(12121)
    await checkpoint(rl, 12121, tok2, 7000)
    # 40s in, big but window-legal progress
    backdate_meta(fake, tok2, issued_shift=40)
    backdate_token(fake, tok2, 40)
    submit_mod._verify_webapp_auth = lambda req: (12121, None)
    req = FakeRequest({
        # final = last_checkpoint + burst (8000) + a bit of tail-rate budget
        "score": 7000 + 8000 + 400, "duration": 45, "practice": False,
        "round_token": tok2, "coins": 0,
    })
    resp = await submit_mod.handle_arcade_submit(req)
    data = json.loads(resp.body.decode())
    check("legit burst finish rewarded via window math", data.get("rewarded") is True)


async def test_stale_sweep():
    print("-- 10-min sweep finalizes only stale rounds --")
    fake = FakeRedis()
    maker = await make_session()
    rs, rl, _ = wire_fakes(fake, maker)

    async with maker() as db:
        u = await seed_user(db, 13131, "sleeper")
        uid_db = u.id

    tok = await rs.issue_round_token(13131)
    await rl.set_open_round(13131, tok)
    await checkpoint(rl, 13131, tok, 4000)
    # 25s of play, but last checkpoint only ~now -> NOT stale yet
    backdate_meta(fake, tok, issued_shift=25)
    backdate_token(fake, tok, 25)
    settled = await rl.sweep_stale_rounds()
    check("fresh round left alone", settled == 0)

    # push last checkpoint 31 minutes into the past -> stale
    backdate_meta(fake, tok, last_shift=31 * 60, issued_shift=31 * 60)
    backdate_token(fake, tok, 31 * 60)
    settled = await rl.sweep_stale_rounds()
    check("stale round finalized by sweep", settled == 1)
    async with maker() as db:
        play = await crud.check_daily_game_play(db, uid_db, tehran_today())
        check("sweep consumed the daily attempt at checkpoint score",
              play is not None and play.rewarded and play.best_score == 4000)
    check("open-round marker cleaned", "arcade:round:open:13131" not in fake.store)


async def main():
    await test_checkpoint_monotonic_and_burst()
    await test_finalize_on_new_round()
    await test_short_abandon_costs_nothing()
    await test_finalized_then_real_submit_is_friendly()
    await test_legacy_client_unchanged()
    await test_checkpoint_curve_rejection_on_submit()
    await test_stale_sweep()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    asyncio.run(main())
