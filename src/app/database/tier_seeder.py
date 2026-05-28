import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud


async def seed_star_reward_tiers(db: AsyncSession):
    """
    Checks for and creates the default star reward tiers if they don't exist.
    This ensures the core reward system is always available.
    """
    # Defensive: ensure required columns exist (for older SQLite DBs upgraded in place)
    try:
        from sqlalchemy import inspect, text

        from app.database.models import engine
        
        # Detect database type
        db_type = engine.url.get_backend_name()
        
        if db_type == "sqlite":
            # SQLite: use PRAGMA
            result = await db.execute(text("PRAGMA table_info(star_reward_tiers)"))
            cols = {row[1] for row in result.fetchall()}  # row[1] is the column name
        else:
            # PostgreSQL: use information_schema
            result = await db.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'star_reward_tiers'
            """))
            cols = {row[0] for row in result.fetchall()}
        
        alter_stmts: list[str] = []
        if 'reward_type' not in cols:
            alter_stmts.append("ALTER TABLE star_reward_tiers ADD COLUMN reward_type VARCHAR(50) NOT NULL DEFAULT 'credit';")
        if 'reward_value' not in cols:
            alter_stmts.append("ALTER TABLE star_reward_tiers ADD COLUMN reward_value VARCHAR(100) NOT NULL DEFAULT '0';")
        for stmt in alter_stmts:
            try:
                await db.execute(text(stmt))
            except Exception:
                # Best-effort: ignore if already applied by another process
                pass
        if alter_stmts:
            await db.commit()
    except Exception:
        # Non-SQLite or unexpected error; continue — init_db() also migrates these columns
        pass
    tiers_to_add = [
        {
            "star_threshold": 3, "title": "۳ ستاره - نوآموز", "description": "۱۵٪ تخفیف برای خرید بعدی (۶۰ روز)",
            "reward_type": "discount_percent", "reward_value": "15", "is_active": True
        },
        {
            "star_threshold": 5, "title": "۵ ستاره - مسافر فضایی", "description": "انتخاب کنید: ۴۰,۰۰۰ تومان یا ۲۵٪ تخفیف",
            "reward_type": "choice", "reward_value": "credit:40000|discount:25", "is_active": True
        },
        {
            "star_threshold": 7, "title": "۷ ستاره - ناوبر", "description": "انتخاب کنید: ۱۵ روز اضافه یا ۲۰,۰۰۰ تومان",
            "reward_type": "choice", "reward_value": "days:15|credit:20000", "is_active": True
        },
        {
            "star_threshold": 10, "title": "۱۰ ستاره - قهرمان کهکشانی", "description": "پلن ۱۰GB رایگان + ۱۵,۰۰۰ تومان",
            "reward_type": "bundle", "reward_value": "plan:10|credit:15000", "is_active": True
        },
        {
            "star_threshold": 15, "title": "۱۵ ستاره - اسطوره", "description": "انتخاب کنید: پلن ۲۰GB رایگان یا ۷۵,۰۰۰ تومان",
            "reward_type": "choice", "reward_value": "plan:20|credit:75000", "is_active": True
        },
        {
            "star_threshold": 20, "title": "۲۰ ستاره - فرمانده کیهانی", "description": "انتخاب کنید: پلن ۴۰GB رایگان یا ۱۵۰,۰۰۰ تومان",
            "reward_type": "choice", "reward_value": "plan:40|credit:150000", "is_active": True
        },
        {
            "star_threshold": 30, "title": "۳۰ ستاره - امپراتور فضایی", "description": "پلن ۶۰GB رایگان + VIP (۳۰ روز) + ۳۰,۰۰۰ تومان",
            "reward_type": "bundle", "reward_value": "plan:60|vip:30|credit:30000", "is_active": True
        },
        {
            "star_threshold": 50, "title": "۵۰ ستاره - افسانه نهایی", "description": "پلن ۱۰۰GB رایگان + نام سفارشی + VIP مادام‌العمر + ۱۰۰,۰۰۰ تومان",
            "reward_type": "bundle", "reward_value": "plan:100|custom_name|vip:lifetime|credit:100000", "is_active": True
        }
    ]

    existing_tiers = await crud.get_all_star_reward_tiers(db, active_only=False)
    existing_thresholds = {t.star_threshold for t in existing_tiers}

    for tier_data in tiers_to_add:
        if tier_data['star_threshold'] not in existing_thresholds:
            await crud.create_star_reward_tier(db, tier_data)
            print(f"Harcoded tier '{tier_data['title']}' created.")