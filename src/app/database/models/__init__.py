import sqlalchemy

from ._audit import AdminAuditLog
from ._base import AsyncSessionLocal, Base, engine
from ._referral import Referral, ReferralReward
from ._reward import (
    Achievement,
    AchievementClaim,
    ArcadeFlag,
    ArcadeWallet,
    Challenge,
    DailyGamePlay,
    DailyStarCap,
    Leaderboard,
    RewardConfig,
    RewardEffectiveness,
    RewardHistory,
    SeasonalEvent,
    StarHistory,
    StarRewardTier,
    UserAchievement,
    UserAnalytics,
    UserChallenge,
    UserDiscount,
    UserGift,
    UserStarRewardClaim,
)
from ._season import (
    RewardCoupon,
    StarMilestoneClaim,
    StarSeason,
    UserStarProgress,
)
from ._subscription import (
    CashoutRequest,
    ChargeRequest,
    PendingDeletionRequest,
    Receipt,
    RenewalHistory,
    Subscription,
    VipOrder,
)
from ._ticket import Notification, Ticket, TicketMessage
from ._user import User

__all__ = [
    "Base",
    "engine",
    "AsyncSessionLocal",
    "init_db",
    "AdminAuditLog",
    "User",
    "Subscription",
    "Receipt",
    "VipOrder",
    "Referral",
    "ReferralReward",
    "RenewalHistory",
    "CashoutRequest",
    "ChargeRequest",
    "PendingDeletionRequest",
    "RewardConfig",
    "Achievement",
    "UserAchievement",
    "Challenge",
    "UserChallenge",
    "RewardHistory",
    "ArcadeFlag",
    "ArcadeWallet",
    "AchievementClaim",
    "DailyGamePlay",
    "UserAnalytics",
    "RewardEffectiveness",
    "Leaderboard",
    "SeasonalEvent",
    "UserGift",
    "StarRewardTier",
    "UserStarRewardClaim",
    "UserDiscount",
    "StarHistory",
    "DailyStarCap",
    "StarSeason",
    "UserStarProgress",
    "StarMilestoneClaim",
    "RewardCoupon",
    "Ticket",
    "TicketMessage",
    "Notification",
]


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate)
        await conn.run_sync(_ensure_link_table)

        from sqlalchemy import select

        result = await conn.execute(select(RewardConfig).limit(1))
        if result.scalar_one_or_none() is None:
            await conn.execute(
                sqlalchemy.insert(RewardConfig).values(
                    id=1, traffic_percent=10.0, days_percent=10.0, credit_percent=10.0
                )
            )

        await _initialize_default_achievements(conn)
        await _initialize_default_challenges(conn)
        await _create_database_indexes(conn)


def _migrate(connection):
    db_type = connection.dialect.name
    datetime_type = "DATETIME" if db_type == "sqlite" else "TIMESTAMP"
    inspector = sqlalchemy.inspect(connection)

    if "users" in inspector.get_table_names():
        existing_cols = {col["name"] for col in inspector.get_columns("users")}
        _add_col_if_missing = lambda col, sql: (  # noqa: E731
            connection.exec_driver_sql(sql) if col not in existing_cols else None
        )
        _add_col_if_missing("language", "ALTER TABLE users ADD COLUMN language VARCHAR(8) NOT NULL DEFAULT 'fa';")
        _add_col_if_missing("dashboard_prefs", "ALTER TABLE users ADD COLUMN dashboard_prefs TEXT NOT NULL DEFAULT '{}';")
        _add_col_if_missing("credit", "ALTER TABLE users ADD COLUMN credit INTEGER NOT NULL DEFAULT 0;")
        _add_col_if_missing("stars", "ALTER TABLE users ADD COLUMN stars INTEGER NOT NULL DEFAULT 0;")
        _add_col_if_missing("level", "ALTER TABLE users ADD COLUMN level INTEGER NOT NULL DEFAULT 1;")
        _add_col_if_missing("experience_points", "ALTER TABLE users ADD COLUMN experience_points INTEGER NOT NULL DEFAULT 0;")
        _add_col_if_missing("last_daily_login", f"ALTER TABLE users ADD COLUMN last_daily_login {datetime_type};")
        _add_col_if_missing("login_streak", "ALTER TABLE users ADD COLUMN login_streak INTEGER NOT NULL DEFAULT 0;")
        _add_col_if_missing("loyalty_points", "ALTER TABLE users ADD COLUMN loyalty_points INTEGER NOT NULL DEFAULT 0;")
        _add_col_if_missing("custom_username", "ALTER TABLE users ADD COLUMN custom_username VARCHAR;")
        _add_col_if_missing("star_pieces", "ALTER TABLE users ADD COLUMN star_pieces INTEGER NOT NULL DEFAULT 0;")
        _add_col_if_missing("arcade_stars_this_month", "ALTER TABLE users ADD COLUMN arcade_stars_this_month INTEGER NOT NULL DEFAULT 0;")
        _add_col_if_missing("arcade_stars_month_reset", "ALTER TABLE users ADD COLUMN arcade_stars_month_reset DATE;")
        _add_col_if_missing("banned", "ALTER TABLE users ADD COLUMN banned BOOLEAN NOT NULL DEFAULT FALSE;")
        _add_col_if_missing("username", "ALTER TABLE users ADD COLUMN username VARCHAR;")
        _add_col_if_missing("phone_number", "ALTER TABLE users ADD COLUMN phone_number VARCHAR;")
        _add_col_if_missing("discount_percent", "ALTER TABLE users ADD COLUMN discount_percent INTEGER NOT NULL DEFAULT 0;")
        _add_col_if_missing("discount_expiration", f"ALTER TABLE users ADD COLUMN discount_expiration {datetime_type};")
        _add_col_if_missing("category", "ALTER TABLE users ADD COLUMN category VARCHAR(32) NOT NULL DEFAULT 'normal';")
        _add_col_if_missing("is_vip", "ALTER TABLE users ADD COLUMN is_vip BOOLEAN NOT NULL DEFAULT FALSE;")
        _add_col_if_missing("vip_until", f"ALTER TABLE users ADD COLUMN vip_until {datetime_type};")

    if "user_gifts" in inspector.get_table_names():
        gift_cols = {col["name"] for col in inspector.get_columns("user_gifts")}
        if "plan_name" not in gift_cols:
            connection.exec_driver_sql("ALTER TABLE user_gifts ADD COLUMN plan_name VARCHAR(100);")
        if "payment_status" not in gift_cols:
            connection.exec_driver_sql("ALTER TABLE user_gifts ADD COLUMN payment_status VARCHAR(20) NOT NULL DEFAULT 'none';")
        if "payment_receipt_message_id" not in gift_cols:
            connection.exec_driver_sql("ALTER TABLE user_gifts ADD COLUMN payment_receipt_message_id BIGINT;")

    if "subscriptions" in inspector.get_table_names():
        sub_cols = {col["name"] for col in inspector.get_columns("subscriptions")}
        for col, sql in [
            ("sub_token", "ALTER TABLE subscriptions ADD COLUMN sub_token VARCHAR;"),
            ("carry_over_bytes", "ALTER TABLE subscriptions ADD COLUMN carry_over_bytes BIGINT;"),
            ("carry_over_reset_at", f"ALTER TABLE subscriptions ADD COLUMN carry_over_reset_at {datetime_type};"),
            ("price", "ALTER TABLE subscriptions ADD COLUMN price INTEGER;"),
            ("paid_amount", "ALTER TABLE subscriptions ADD COLUMN paid_amount INTEGER;"),
            ("plan_name", "ALTER TABLE subscriptions ADD COLUMN plan_name VARCHAR;"),
            ("credit_used", "ALTER TABLE subscriptions ADD COLUMN credit_used INTEGER NOT NULL DEFAULT 0;"),
            ("applied_discount_ids", "ALTER TABLE subscriptions ADD COLUMN applied_discount_ids VARCHAR;"),
            ("applied_coupon_id", "ALTER TABLE subscriptions ADD COLUMN applied_coupon_id INTEGER;"),
            ("admin_receipt_forward_message_id", "ALTER TABLE subscriptions ADD COLUMN admin_receipt_forward_message_id BIGINT;"),
            ("admin_request_message_id", "ALTER TABLE subscriptions ADD COLUMN admin_request_message_id BIGINT;"),
            ("receipt_image_url", "ALTER TABLE subscriptions ADD COLUMN receipt_image_url VARCHAR;"),
            ("user_link_sent", "ALTER TABLE subscriptions ADD COLUMN user_link_sent BOOLEAN NOT NULL DEFAULT FALSE;"),
        ]:
            if col not in sub_cols:
                connection.exec_driver_sql(sql)
        if "referral_rewards" in inspector.get_table_names():
            reward_cols = {col["name"] for col in inspector.get_columns("referral_rewards")}
            if "reward_value" not in reward_cols:
                connection.exec_driver_sql("ALTER TABLE referral_rewards ADD COLUMN reward_value INTEGER;")
            if "stars" not in reward_cols:
                connection.exec_driver_sql("ALTER TABLE referral_rewards ADD COLUMN stars INTEGER;")

    if "tickets" in inspector.get_table_names():
        ticket_cols = {col["name"] for col in inspector.get_columns("tickets")}
        for col, sql in [
            ("subscription_id", "ALTER TABLE tickets ADD COLUMN subscription_id INTEGER;"),
            ("last_reminder_at", f"ALTER TABLE tickets ADD COLUMN last_reminder_at {datetime_type};"),
            ("notify_on_reply", "ALTER TABLE tickets ADD COLUMN notify_on_reply BOOLEAN NOT NULL DEFAULT TRUE;"),
            ("closed_at", f"ALTER TABLE tickets ADD COLUMN closed_at {datetime_type};"),
            ("resolved", "ALTER TABLE tickets ADD COLUMN resolved BOOLEAN NOT NULL DEFAULT FALSE;"),
            ("feedback_score", "ALTER TABLE tickets ADD COLUMN feedback_score INTEGER;"),
            ("feedback_text", "ALTER TABLE tickets ADD COLUMN feedback_text TEXT;"),
            ("hidden_from_user", "ALTER TABLE tickets ADD COLUMN hidden_from_user BOOLEAN NOT NULL DEFAULT FALSE;"),
            ("hidden_at", f"ALTER TABLE tickets ADD COLUMN hidden_at {datetime_type};"),
        ]:
            if col not in ticket_cols:
                connection.exec_driver_sql(sql)

    if "ticket_messages" in inspector.get_table_names():
        msg_cols = {col["name"] for col in inspector.get_columns("ticket_messages")}
        if "read_by_user" not in msg_cols:
            connection.exec_driver_sql("ALTER TABLE ticket_messages ADD COLUMN read_by_user BOOLEAN NOT NULL DEFAULT TRUE;")

    if "star_reward_tiers" in inspector.get_table_names():
        tier_cols = {col["name"] for col in inspector.get_columns("star_reward_tiers")}
        if "reward_type" not in tier_cols:
            connection.exec_driver_sql("ALTER TABLE star_reward_tiers ADD COLUMN reward_type VARCHAR(50) NOT NULL DEFAULT 'credit';")
        if "reward_value" not in tier_cols:
            connection.exec_driver_sql("ALTER TABLE star_reward_tiers ADD COLUMN reward_value VARCHAR(100) NOT NULL DEFAULT '0';")

    if "charge_requests" in inspector.get_table_names():
        charge_cols = {col["name"] for col in inspector.get_columns("charge_requests")}
        if "receipt_image_url" not in charge_cols:
            connection.exec_driver_sql("ALTER TABLE charge_requests ADD COLUMN receipt_image_url VARCHAR;")
        if "charge_type" not in charge_cols:
            connection.exec_driver_sql("ALTER TABLE charge_requests ADD COLUMN charge_type VARCHAR(32) DEFAULT 'normal';")
        if "paid_amount" not in charge_cols:
            connection.exec_driver_sql("ALTER TABLE charge_requests ADD COLUMN paid_amount INTEGER;")


def _ensure_link_table(connection):
    db_type = connection.dialect.name
    datetime_type = "DATETIME" if db_type == "sqlite" else "TIMESTAMP"
    inspector = sqlalchemy.inspect(connection)
    if "subscription_links" not in inspector.get_table_names():
        connection.exec_driver_sql(
            f"""
            CREATE TABLE subscription_links (
                user_id INTEGER NOT NULL,
                subscription_id INTEGER NOT NULL,
                added_at {datetime_type},
                PRIMARY KEY (user_id, subscription_id),
                FOREIGN KEY(user_id) REFERENCES users (id),
                FOREIGN KEY(subscription_id) REFERENCES subscriptions (id)
            );
            """
        )


async def _initialize_default_achievements(conn):
    from sqlalchemy import select

    result = await conn.execute(select(Achievement).limit(1))
    if result.scalar_one_or_none():
        return

    default_achievements = [
        {"name": "بلند پرواز", "description": "اولین بازی خود را انجام دهید", "icon": "🚀", "requirement_type": "game_plays", "requirement_value": 1, "reward_type": "bundle", "reward_value": "credit:500|xp:100"},
        {"name": "اولین تماس", "description": "اولین دوست خود را معرفی کنید", "icon": "🎯", "requirement_type": "referrals", "requirement_value": 1, "reward_type": "bundle", "reward_value": "credit:2000|xp:200"},
        {"name": "رهبر گروه", "description": "۵ نفر را معرفی کنید", "icon": "👥", "requirement_type": "referrals", "requirement_value": 5, "reward_type": "bundle", "reward_value": "credit:10000|xp:500|stars:1"},
        {"name": "امپراتوری کهکشانی", "description": "۲۰ معرفی فعال (خرید پلن ۲۰GB+)", "icon": "🌌", "requirement_type": "active_referrals", "requirement_value": 20, "reward_type": "bundle", "reward_value": "credit:50000|xp:1200|stars:3"},
        {"name": "مسافر داده", "description": "۵۰ گیگابایت داده مصرف کنید", "icon": "📡", "requirement_type": "usage", "requirement_value": 50, "reward_type": "bundle", "reward_value": "credit:5000|xp:300"},
        {"name": "فرمانده داده", "description": "۲۰۰ گیگابایت داده مصرف کنید", "icon": "📊", "requirement_type": "usage", "requirement_value": 200, "reward_type": "bundle", "reward_value": "credit:20000|xp:800"},
        {"name": "جنگجوی نوار", "description": "۷ روز متوالی بازی کنید", "icon": "🔥", "requirement_type": "play_streak", "requirement_value": 7, "reward_type": "bundle", "reward_value": "credit:5000|xp:400"},
        {"name": "مسافر زمان", "description": "۳۰ روز متوالی بازی کنید", "icon": "⏰", "requirement_type": "play_streak", "requirement_value": 30, "reward_type": "bundle", "reward_value": "credit:25000|xp:1200|stars:2"},
        {"name": "خریدار بزرگ", "description": "۵ اشتراک خریداری کنید", "icon": "💎", "requirement_type": "purchases", "requirement_value": 5, "reward_type": "bundle", "reward_value": "xp:800|stars:1|cashback:5"},
        {"name": "حامی", "description": "۱۰ اشتراک خریداری کنید", "icon": "👑", "requirement_type": "purchases", "requirement_value": 10, "reward_type": "bundle", "reward_value": "xp:2000|stars:2|cashback:10"},
        {"name": "امتیاز کامل", "description": "در بازی به ۱۵۰۰۰+ امتیاز برسید", "icon": "🏆", "requirement_type": "high_score", "requirement_value": 15000, "reward_type": "bundle", "reward_value": "credit:5000|xp:500|stars:1"},
    ]
    for data in default_achievements:
        await conn.execute(sqlalchemy.insert(Achievement).values(**data))


async def _initialize_default_challenges(conn):
    from datetime import datetime, timedelta

    from sqlalchemy import select

    result = await conn.execute(select(Challenge).limit(1))
    if result.scalar_one_or_none():
        return

    now = datetime.utcnow()
    week_start = now - timedelta(days=now.weekday())
    week_end = week_start + timedelta(days=7)

    default_challenges = [
        {"title": "ورود روزانه", "description": "امروز وارد شوید", "challenge_type": "daily", "requirement_type": "logins", "requirement_value": 1, "reward_type": "xp", "reward_value": 10, "start_date": now.replace(hour=0, minute=0, second=0, microsecond=0), "end_date": now.replace(hour=23, minute=59, second=59, microsecond=999999)},
        {"title": "معرفی هفتگی", "description": "۳ نفر را این هفته معرفی کنید", "challenge_type": "weekly", "requirement_type": "referrals", "requirement_value": 3, "reward_type": "loyalty_points", "reward_value": 100, "start_date": week_start, "end_date": week_end},
        {"title": "بازی روزانه", "description": "یک بار بازی روزانه انجام دهید", "challenge_type": "daily", "requirement_type": "daily_game", "requirement_value": 1, "reward_type": "xp", "reward_value": 20, "start_date": now.replace(hour=0, minute=0, second=0, microsecond=0), "end_date": now.replace(hour=23, minute=59, second=59, microsecond=999999)},
        {"title": "امتیاز بازی هفتگی", "description": "این هفته به امتیاز مشخصی در بازی برسید", "challenge_type": "weekly", "requirement_type": "weekly_game_score", "requirement_value": 3000, "reward_type": "loyalty_points", "reward_value": 150, "start_date": week_start, "end_date": week_end},
    ]
    for data in default_challenges:
        await conn.execute(sqlalchemy.insert(Challenge).values(**data))


async def _create_database_indexes(conn):
    from app.database.indexes import (
        create_analytics_indexes,
        create_notification_indexes,
        create_reward_indexes,
        create_subscription_indexes,
        create_ticket_indexes,
        create_user_indexes,
    )

    try:
        await create_user_indexes(conn)
        await create_subscription_indexes(conn)
        await create_reward_indexes(conn)
        await create_analytics_indexes(conn)
        await create_ticket_indexes(conn)
        await create_notification_indexes(conn)
        await conn.execute(sqlalchemy.text("CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals (referrer_id)"))
        await conn.execute(sqlalchemy.text("CREATE INDEX IF NOT EXISTS idx_referrals_created_at ON referrals (created_at)"))
        await conn.execute(sqlalchemy.text("CREATE INDEX IF NOT EXISTS idx_charge_requests_status ON charge_requests (status)"))
        await conn.execute(sqlalchemy.text("CREATE INDEX IF NOT EXISTS idx_charge_requests_user ON charge_requests (user_id)"))
        await conn.execute(sqlalchemy.text("CREATE INDEX IF NOT EXISTS idx_renewal_history_subscription ON renewal_history (subscription_id)"))
        await conn.execute(sqlalchemy.text("CREATE INDEX IF NOT EXISTS idx_achievements_requirement_type ON achievements (requirement_type)"))
        await conn.execute(sqlalchemy.text("CREATE INDEX IF NOT EXISTS idx_challenges_type_active ON challenges (challenge_type, active)"))
        await conn.execute(sqlalchemy.text("CREATE INDEX IF NOT EXISTS idx_user_gifts_sender ON user_gifts (sender_id)"))
        await conn.execute(sqlalchemy.text("CREATE INDEX IF NOT EXISTS idx_user_gifts_receiver ON user_gifts (receiver_id)"))
        print("Database indexes created successfully")
    except Exception as e:
        print(f"Warning: some indexes may already exist or failed to create: {e}")
