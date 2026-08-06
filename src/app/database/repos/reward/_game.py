import json
from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database.models import ArcadeFlag, ArcadeWallet, DailyGamePlay, User
from app.utils.tehran_time import tehran_now, tehran_today


class _GameMixin:
    @staticmethod
    async def get_monthly_arcade_ranking(
        db: AsyncSession, month_start: date, month_end: date, limit: int | None = None
    ):
        """The canonical monthly race ranking (also used for prize payouts):
        per-user SUM of validated daily-run scores in the window (each day's
        ranked run adds to the month total, so daily play climbs the board),
        visible users only, ties broken by whoever started playing earlier in
        the month. Returns rows of (user_id, top_score, first_play,
        display_name) — top_score is the month total."""
        name = func.coalesce(
            func.nullif(User.custom_username, ""),
            func.nullif(User.username, ""),
            func.nullif(User.full_name, ""),
        )
        q = (
            select(
                DailyGamePlay.user_id,
                func.sum(DailyGamePlay.best_score).label("top_score"),
                func.min(DailyGamePlay.play_date).label("first_play"),
                func.max(name).label("display_name"),
            )
            .join(User, User.id == DailyGamePlay.user_id)
            .filter(
                DailyGamePlay.play_date >= month_start,
                DailyGamePlay.play_date <= month_end,
                DailyGamePlay.rewarded == True,  # noqa: E712
                DailyGamePlay.best_score > 0,
                User.show_on_leaderboard == True,  # noqa: E712
            )
            .group_by(DailyGamePlay.user_id)
            .order_by(
                func.sum(DailyGamePlay.best_score).desc(),
                func.min(DailyGamePlay.play_date).asc(),
                DailyGamePlay.user_id.asc(),
            )
        )
        if limit:
            q = q.limit(limit)
        return (await db.execute(q)).all()

    # ------------------------------------------------------------------
    # Arcade coin wallet (2026-07-07). Coins are an arcade-only currency:
    # minted exclusively by the validated daily run (capped per run in the
    # submit handler) and spent on skins/powers/lives/retry. They can never
    # convert to credit, stars or traffic.
    # ------------------------------------------------------------------
    @staticmethod
    async def get_or_create_arcade_wallet(db: AsyncSession, user_id: int, for_update: bool = False) -> ArcadeWallet:
        q = select(ArcadeWallet).filter(ArcadeWallet.user_id == user_id)
        if for_update:
            q = q.with_for_update()
        wallet = (await db.execute(q)).scalars().first()
        if wallet:
            return wallet
        wallet = ArcadeWallet(user_id=user_id)
        db.add(wallet)
        await db.commit()
        if for_update:
            # re-read under the lock so the caller holds it
            wallet = (await db.execute(
                select(ArcadeWallet).filter(ArcadeWallet.user_id == user_id).with_for_update()
            )).scalars().first()
        return wallet

    @staticmethod
    async def award_arcade_coins(db: AsyncSession, user_id: int, count: int) -> int:
        """Credit validated-run coins. Caller commits (alongside the play
        save). Returns the new balance."""
        from app.database.repos.reward import RewardRepository as _RR

        if count <= 0:
            wallet = await _RR.get_or_create_arcade_wallet(db, user_id)
            return wallet.coins
        wallet = await _RR.get_or_create_arcade_wallet(db, user_id, for_update=True)
        wallet.coins += count
        wallet.coins_earned_total += count
        return wallet.coins

    @staticmethod
    async def arcade_buy(db: AsyncSession, user_id: int, item: str):
        """Buy a shop item ("skin:<key>" | "power:<key>" | "extra_life").
        Wallet row is locked for the whole operation so concurrent taps can't
        double-spend or double-grant. Commits on success.
        Returns (error_code | None, wallet | None)."""
        from app.core.settings import ARCADE_SHOP
        from app.database.repos.reward import RewardRepository as _RR

        if item.startswith("skin:"):
            kind, key = "skin", item[5:]
            entry = ARCADE_SHOP["skins"].get(key)
        elif item.startswith("power:"):
            kind, key = "power", item[6:]
            entry = ARCADE_SHOP["powers"].get(key)
        elif item == "extra_life":
            kind, key, entry = "extra_life", "extra_life", ARCADE_SHOP["extra_life"]
        else:
            return "unknown_item", None
        if not entry:
            return "unknown_item", None
        price = int(entry["price"])

        wallet = await _RR.get_or_create_arcade_wallet(db, user_id, for_update=True)
        owned_skins = set(json.loads(wallet.owned_skins or "[]"))
        owned_powers = set(json.loads(wallet.owned_powers or "[]"))

        if kind == "skin" and (key in owned_skins or key == "default"):
            return "already_owned", wallet
        if kind == "power" and key in owned_powers:
            return "already_owned", wallet
        if kind == "extra_life" and (wallet.extra_lives or 0) >= 1:
            return "already_owned", wallet
        if (wallet.coins or 0) < price:
            return "not_enough_coins", wallet

        wallet.coins -= price
        if kind == "skin":
            owned_skins.add(key)
            wallet.owned_skins = json.dumps(sorted(owned_skins))
            wallet.equipped_skin = key          # equip what you just bought
        elif kind == "power":
            owned_powers.add(key)
            wallet.owned_powers = json.dumps(sorted(owned_powers))
        else:
            wallet.extra_lives = (wallet.extra_lives or 0) + 1
        await db.commit()
        return None, wallet

    @staticmethod
    async def arcade_equip(db: AsyncSession, user_id: int, skin: str):
        """Equip an owned skin. Returns (error_code | None, wallet | None)."""
        from app.core.settings import ARCADE_SHOP
        from app.database.repos.reward import RewardRepository as _RR

        if skin not in ARCADE_SHOP["skins"]:
            return "unknown_skin", None
        wallet = await _RR.get_or_create_arcade_wallet(db, user_id, for_update=True)
        owned = set(json.loads(wallet.owned_skins or "[]")) | {"default"}
        if skin not in owned:
            return "not_owned", wallet
        wallet.equipped_skin = skin
        await db.commit()
        return None, wallet

    @staticmethod
    async def arcade_retry(db: AsyncSession, user_id: int):
        """Spend coins to reset TODAY's ranked run (Iran day). Today's
        best_score is zeroed — the next run replaces it, higher or lower.
        Returns (error_code | None, new_coin_balance)."""
        from app.core.settings import ARCADE_SHOP
        from app.database.repos.reward import RewardRepository as _RR

        price = int(ARCADE_SHOP["retry"]["price"])

        # Lock the wallet FIRST: a concurrent double-tap serializes here, and
        # the play row is then read fresh (populate_existing) so the second
        # request sees the already-reset run and bails instead of re-charging.
        wallet = await _RR.get_or_create_arcade_wallet(db, user_id, for_update=True)

        today = tehran_today()
        play = (await db.execute(
            select(DailyGamePlay)
            .filter(DailyGamePlay.user_id == user_id, DailyGamePlay.play_date == today)
            .execution_options(populate_existing=True)
        )).scalar_one_or_none()
        if not play or not play.rewarded:
            return "nothing_to_retry", wallet.coins or 0

        if (wallet.coins or 0) < price:
            return "not_enough_coins", wallet.coins or 0

        wallet.coins -= price
        play.best_score = 0
        play.rewarded = False
        play.duration_seconds = 0
        await db.commit()
        return None, wallet.coins

    @staticmethod
    async def admin_arcade_adjust(
        db: AsyncSession, user_id: int,
        coins_delta: int | None = None, difficulty: str | None = None,
    ):
        """ADMIN-ONLY wallet adjustment (2026-07-08): grant/remove coins and/or
        set the per-user difficulty. Coins stay arcade-only (the seal holds —
        this touches nothing but the wallet); the balance never goes below 0
        and grants don't inflate the lifetime-earned analytics counter.
        Returns (error_code | None, wallet | None)."""
        from app.core.settings import ARCADE_DIFFICULTIES
        from app.database.repos.reward import RewardRepository as _RR

        if difficulty is not None and difficulty not in ARCADE_DIFFICULTIES:
            return "unknown_difficulty", None
        wallet = await _RR.get_or_create_arcade_wallet(db, user_id, for_update=True)
        if coins_delta:
            wallet.coins = max(0, (wallet.coins or 0) + int(coins_delta))
        if difficulty is not None:
            wallet.difficulty = difficulty
        await db.commit()
        return None, wallet

    @staticmethod
    def wallet_public(wallet: ArcadeWallet) -> dict:
        """JSON-safe wallet view shared by status/shop/loadout responses."""
        try:
            skins = json.loads(wallet.owned_skins or "[]")
        except Exception:
            skins = []
        try:
            powers = json.loads(wallet.owned_powers or "[]")
        except Exception:
            powers = []
        if "default" not in skins:
            skins = ["default"] + skins
        return {
            "coins": wallet.coins or 0,
            "equipped_skin": wallet.equipped_skin or "default",
            "owned_skins": skins,
            "owned_powers": powers,
            "extra_lives": wallet.extra_lives or 0,
            "difficulty": wallet.difficulty or "normal",
        }

    @staticmethod
    async def add_arcade_flag(
        db: AsyncSession, user_id: int, score: int, claimed_duration: int,
        server_elapsed: int | None, reason: str,
    ):
        """Persist a rejected arcade submit for the admin cheat log."""
        db.add(ArcadeFlag(
            user_id=user_id, score=score, claimed_duration=claimed_duration,
            server_elapsed=server_elapsed, reason=reason,
        ))
        await db.commit()
    @staticmethod
    async def get_or_create_daily_game_play(
        db: AsyncSession, user_id: int, date: datetime | None = None
    ) -> DailyGamePlay:
        if date is None:
            date = tehran_now()  # arcade days roll over at IRAN midnight
        play_date = date.date()
        result = await db.execute(
            select(DailyGamePlay).filter(
                DailyGamePlay.user_id == user_id,
                DailyGamePlay.play_date == play_date,
            )
        )
        row = result.scalars().first()
        if row:
            return row
        row = DailyGamePlay(user_id=user_id, play_date=play_date)
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row

    @staticmethod
    async def can_play_daily_game(db: AsyncSession, user_id: int) -> dict:
        from app.database.repos.reward import RewardRepository as _RR

        play = await _RR.get_or_create_daily_game_play(db, user_id)
        return {"allowed": not play.rewarded, "best_score": play.best_score}

    # submit_daily_game_score was DELETED (2026-07-19): it was a dead
    # duplicate of the live HTTP submit path (api/routes/game/reward_core.py)
    # that still minted credit/stars per play — never called, but one import
    # away from re-arming the farming hole the 2026-06-02 audit closed.

    @staticmethod
    async def check_daily_game_play(db: AsyncSession, user_id: int, play_date: date):
        result = await db.execute(
            select(DailyGamePlay)
            .filter(DailyGamePlay.user_id == user_id)
            .filter(DailyGamePlay.play_date == play_date)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def save_game_play(
        db: AsyncSession,
        user_id: int,
        score: int,
        duration: int,
        display_name: str,
        rewarded: bool = False,
        reward_credit: int = 0,
        reward_stars: int = 0,
        reward_xp: int = 0,
        count_for_leaderboard: bool = False,
    ):
        """Record a play. best_score is ONLY updated when count_for_leaderboard
        is True — i.e. by the single validated rewarded run per day. Practice,
        already-played and rejected runs are stored for analytics but can never
        reach a leaderboard or the monthly prize ranking (anti-cheat 2026-07-03)."""
        from app.database.repos.reward import RewardRepository as _RR

        today = tehran_today()
        existing = await _RR.check_daily_game_play(db, user_id, today)

        if existing:
            if count_for_leaderboard and score > existing.best_score:
                existing.best_score = score
            existing.duration_seconds = duration
            existing.display_name = display_name or existing.display_name
            if rewarded and not existing.rewarded:
                existing.rewarded = True
                existing.reward_credit = reward_credit
                existing.reward_stars = reward_stars
                existing.reward_xp = reward_xp
            await db.commit()
            return existing

        play = DailyGamePlay(
            user_id=user_id,
            play_date=today,
            best_score=score if count_for_leaderboard else 0,
            duration_seconds=duration,
            display_name=display_name,
            rewarded=rewarded,
            reward_credit=reward_credit if rewarded else 0,
            reward_stars=reward_stars if rewarded else 0,
            reward_xp=reward_xp if rewarded else 0,
        )
        db.add(play)
        await db.commit()
        await db.refresh(play)
        return play
