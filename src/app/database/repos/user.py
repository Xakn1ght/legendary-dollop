import json
import secrets
import string
import time

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database.models import Referral, User
from app.utils.logger import DatabaseError, log_database_operation, log_error

# Character set for referral codes
_CODE_CHARS = string.ascii_uppercase + string.digits

class UserRepository:
    _DASHBOARD_PREFS_ALLOWED_KEYS = {"theme", "lang", "current_sub_id", "default_sub_id", "auto_claim", "voucher_auto_sub_id", "accent", "welcome_shown"}

    @staticmethod
    def _parse_dashboard_prefs(raw: str | None) -> dict:
        if not raw:
            return {}
        try:
            val = json.loads(raw)
            return val if isinstance(val, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _serialize_dashboard_prefs(prefs: dict) -> str:
        try:
            return json.dumps(prefs or {}, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            return "{}"

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
        result = await db.execute(select(User).filter(User.id == user_id))
        return result.scalars().first()

    @staticmethod
    async def get_user(db: AsyncSession, chat_id: int) -> User | None:
        start_time = time.time()
        try:
            result = await db.execute(select(User).filter(User.chat_id == chat_id))
            user = result.scalars().first()
            duration = time.time() - start_time
            log_database_operation("select", "users", True, duration, user_id=user.id if user else None)
            return user
        except SQLAlchemyError as e:
            duration = time.time() - start_time
            log_database_operation("select", "users", False, duration, error=str(e))
            log_error(e, {"operation": "get_user", "chat_id": chat_id})
            raise DatabaseError(f"Failed to get user: {str(e)}")

    @staticmethod
    def generate_referral_code(name_parts):
        prefix = "".join([p[:1].upper() for p in name_parts if p][:2])
        while len(prefix) < 2:
            prefix += secrets.choice(string.ascii_uppercase)
        suffix = "".join(secrets.choice(_CODE_CHARS) for _ in range(4))
        return (prefix + suffix)

    @staticmethod
    async def create_user(db: AsyncSession, chat_id: int, username: str, full_name: str, language: str | None = None) -> User:
        start_time = time.time()
        try:
            db_user = await UserRepository.get_user(db, chat_id)
            if db_user:
                duration = time.time() - start_time
                log_database_operation("select", "users", True, duration, user_id=db_user.id)
                return db_user
            
            name_parts = full_name.split() if full_name else (username.split('_') if username else [])
            referral_code = UserRepository.generate_referral_code(name_parts)
            
            new_user = User(
                chat_id=chat_id, 
                username=username, 
                full_name=full_name,
                referral_code=referral_code,
                language=(language or "fa"),
            )
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)
            
            duration = time.time() - start_time
            log_database_operation("insert", "users", True, duration, user_id=new_user.id)
            return new_user
            
        except IntegrityError as e:
            await db.rollback()
            duration = time.time() - start_time
            log_database_operation("insert", "users", False, duration, error="IntegrityError")
            log_error(e, {"operation": "create_user", "chat_id": chat_id, "username": username})
            raise DatabaseError(f"User already exists or invalid data: {str(e)}")
        except SQLAlchemyError as e:
            await db.rollback()
            duration = time.time() - start_time
            log_database_operation("insert", "users", False, duration, error=str(e))
            log_error(e, {"operation": "create_user", "chat_id": chat_id, "username": username})
            raise DatabaseError(f"Failed to create user: {str(e)}")

    @staticmethod
    async def set_user_language(db: AsyncSession, chat_id: int, language: str) -> bool:
        """Persist user language preference (e.g., 'fa', 'en')."""
        try:
            result = await db.execute(select(User).filter(User.chat_id == chat_id))
            user = result.scalars().first()
            if not user:
                return False
            user.language = (language or "fa")
            await db.commit()
            return True
        except Exception:
            await db.rollback()
            return False

    @staticmethod
    async def get_dashboard_prefs(db: AsyncSession, chat_id: int) -> dict:
        """Get per-user dashboard prefs used to sync UI settings across devices."""
        result = await db.execute(select(User).filter(User.chat_id == chat_id))
        user = result.scalars().first()
        if not user:
            return {}
        prefs = UserRepository._parse_dashboard_prefs(getattr(user, "dashboard_prefs", None))
        # Keep language in sync with the existing user.language field.
        try:
            if user.language and "lang" not in prefs:
                prefs["lang"] = user.language
        except Exception:
            pass
        return prefs

    @staticmethod
    async def update_dashboard_prefs(db: AsyncSession, chat_id: int, patch: dict) -> dict:
        """Merge `patch` into stored prefs and return the updated prefs."""
        result = await db.execute(select(User).filter(User.chat_id == chat_id))
        user = result.scalars().first()
        if not user:
            return {}

        existing = UserRepository._parse_dashboard_prefs(getattr(user, "dashboard_prefs", None))
        sanitized: dict = {}
        for k, v in (patch or {}).items():
            if k not in UserRepository._DASHBOARD_PREFS_ALLOWED_KEYS:
                continue
            if v is None:
                sanitized[k] = None
            elif isinstance(v, (str, int, bool)):
                sanitized[k] = v

        merged = dict(existing)
        for k, v in sanitized.items():
            if v is None:
                merged.pop(k, None)
            else:
                merged[k] = v

        # Sync the dedicated language column too.
        if "lang" in merged:
            try:
                user.language = str(merged["lang"])[:8]
            except Exception:
                pass

        user.dashboard_prefs = UserRepository._serialize_dashboard_prefs(merged)
        await db.commit()
        return merged

    @staticmethod
    async def get_user_by_referral_code(db: AsyncSession, code: str) -> User | None:
        result = await db.execute(select(User).filter(User.referral_code == code))
        return result.scalars().first()

    @staticmethod
    async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
        result = await db.execute(select(User).filter(User.username == username))
        return result.scalars().first()

    @staticmethod
    async def get_all_users(db: AsyncSession):
        result = await db.execute(select(User))
        return result.scalars().all()

    @staticmethod
    async def add_credit(db: AsyncSession, user_id: int, amount: int) -> User | None:
        if amount < 0:
            raise ValueError("amount must be positive for add_credit")
        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalars().first()
        if user:
            user.credit += amount
            await db.commit()
            await db.refresh(user)
        return user

    @staticmethod
    async def deduct_credit(db: AsyncSession, user_id: int, amount: int) -> User | None:
        if amount < 0:
            raise ValueError("amount must be positive for deduct_credit")
        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalars().first()
        if user:
            if user.credit < amount:
                return None
            user.credit -= amount
            await db.commit()
            await db.refresh(user)
        return user

    @staticmethod
    async def create_referral(db: AsyncSession, referrer_id: int, referee_id: int) -> Referral:
        result = await db.execute(
            select(Referral).filter(Referral.referee_id == referee_id)
        )
        existing = result.scalars().first()
        if existing:
            return existing

        new_referral = Referral(referrer_id=referrer_id, referee_id=referee_id)
        db.add(new_referral)
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            result = await db.execute(select(Referral).filter(Referral.referee_id == referee_id))
            return result.scalars().first()
        await db.refresh(new_referral)
        return new_referral

    @staticmethod
    async def get_referees_by_referrer(db: AsyncSession, referrer_id: int):
        result = await db.execute(
            select(User)
            .join(Referral, User.id == Referral.referee_id)
            .filter(Referral.referrer_id == referrer_id)
        )
        return result.scalars().all()

    @staticmethod
    async def set_custom_username(db: AsyncSession, user_id: int, custom_username: str) -> User | None:
        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalars().first()
        if not user:
            return None
        
        user.custom_username = custom_username
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def set_vip_status(db: AsyncSession, user_id: int, is_vip: bool, vip_until=None) -> User | None:
        """Set VIP status for a user. vip_until=None means lifetime VIP."""
        from datetime import datetime, timedelta
        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalars().first()
        if not user:
            return None
        
        user.is_vip = is_vip
        if is_vip and vip_until is None:
            user.vip_until = None  # Lifetime VIP
        elif is_vip and isinstance(vip_until, int):
            # vip_until is number of days
            user.vip_until = datetime.utcnow() + timedelta(days=vip_until)
        else:
            user.vip_until = vip_until
        
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def is_user_vip(db: AsyncSession, user_id: int) -> bool:
        """Check if user is currently VIP (active)."""
        from datetime import datetime
        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalars().first()
        if not user or not user.is_vip:
            return False
        # Lifetime VIP
        if user.vip_until is None:
            return True
        # Check if VIP hasn't expired
        return user.vip_until > datetime.utcnow()
