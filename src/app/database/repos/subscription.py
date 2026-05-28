from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.database.models import ChargeRequest, ReferralReward, RenewalHistory, Subscription
from app.services.marzban import marzban_api


class SubscriptionRepository:
    @staticmethod
    async def create_subscription(
        db: AsyncSession, 
        user_id: int, 
        marzban_username: str, 
        plan: str, 
        receipt_message_id: int, 
        referrer_id: int = None, 
        renewal_paid: bool = False, 
        renewal_template: str = None, 
        renewal_price: int = None, 
        renewal_requested_at = None, 
        renewal_applied: bool = False, 
        price: int = 0,
        status: str = "pending",
    ) -> Subscription:
        new_subscription = Subscription(
            user_id=user_id,
            referrer_id=referrer_id,
            marzban_username=marzban_username,
            plan_name=plan,
            price=price,
            receipt_message_id=receipt_message_id,
            status=status or "pending",
            renewal_paid=renewal_paid,
            renewal_template=renewal_template,
            renewal_price=renewal_price,
            renewal_requested_at=renewal_requested_at,
            renewal_applied=renewal_applied
        )
        db.add(new_subscription)
        await db.commit()
        await db.refresh(new_subscription)
        return new_subscription

    @staticmethod
    async def get_user_subscriptions(db: AsyncSession, user_id: int):
        # Subscriptions owned by user
        owned = await db.execute(select(Subscription).filter(Subscription.user_id == user_id))
        owned_list = owned.scalars().all()

        # Subscriptions shared with user via link table
        link_rows = await db.execute(
            text("SELECT subscription_id FROM subscription_links WHERE user_id = :uid"),
            {"uid": user_id},
        )
        link_ids = [row[0] for row in link_rows.fetchall()]

        linked_list = []
        if link_ids:
            result_link = await db.execute(select(Subscription).filter(Subscription.id.in_(link_ids)))
            linked_list = result_link.scalars().all()

        # Merge while keeping uniqueness
        ids = {s.id for s in owned_list}
        for s in linked_list:
            if s.id not in ids:
                owned_list.append(s)
        return owned_list

    @staticmethod
    async def add_subscription_link(db: AsyncSession, user_id: int, subscription_id: int):
        # Detect database type for proper SQL syntax
        # PostgreSQL uses ON CONFLICT, SQLite uses INSERT OR IGNORE
        try:
            db_type = db.bind.dialect.name if db.bind else 'postgresql'
        except (AttributeError, Exception):
            db_type = 'postgresql'
        
        if db_type == 'sqlite':
            # SQLite syntax
            sql = "INSERT OR IGNORE INTO subscription_links (user_id, subscription_id, added_at) VALUES (:u, :s, :t)"
        else:
            # PostgreSQL syntax (ON CONFLICT DO NOTHING)
            # The PRIMARY KEY constraint on (user_id, subscription_id) handles the conflict
            sql = "INSERT INTO subscription_links (user_id, subscription_id, added_at) VALUES (:u, :s, :t) ON CONFLICT (user_id, subscription_id) DO NOTHING"
        
        await db.execute(
            text(sql),
            {"u": user_id, "s": subscription_id, "t": datetime.utcnow()},
        )
        await db.commit()

    @staticmethod
    async def get_user_active_subscriptions(db: AsyncSession, user_id: int):
        result = await db.execute(
            select(Subscription)
            .filter(Subscription.user_id == user_id, Subscription.status == 'active')
        )
        return result.scalars().all()

    @staticmethod
    async def get_pending_subscriptions(db: AsyncSession):
        result = await db.execute(
            select(Subscription)
            .options(selectinload(Subscription.user))
            .filter(Subscription.status == 'pending', Subscription.receipt_message_id != None)
        )
        return result.scalars().all()

    @staticmethod
    async def get_pending_toggle_subscriptions(db: AsyncSession):
        result = await db.execute(
            select(Subscription)
            .options(selectinload(Subscription.user))
            .filter(Subscription.status.in_(("pending_disable", "pending_enable")))
        )
        return result.scalars().all()

    @staticmethod
    async def activate_subscription(db: AsyncSession, subscription_id: int) -> Subscription | None:
        result = await db.execute(
            select(Subscription)
            .options(selectinload(Subscription.user))
            .filter(Subscription.id == subscription_id)
        )
        subscription = result.scalars().first()
        if subscription:
            subscription.status = 'active'
            await db.commit()
            await db.refresh(subscription)
        return subscription

    @staticmethod
    async def deactivate_subscription_on_failure(db: AsyncSession, subscription_id: int) -> Subscription | None:
        result = await db.execute(
            select(Subscription).filter(Subscription.id == subscription_id)
        )
        subscription = result.scalars().first()
        if not subscription:
            return None

        subscription.status = "pending"
        await db.commit()
        await db.refresh(subscription)
        return subscription

    @staticmethod
    async def get_all_active_subscriptions_for_notification(db: AsyncSession):
        result = await db.execute(
            select(Subscription)
            .options(selectinload(Subscription.user))
            .filter(Subscription.status == 'active')
        )
        return result.scalars().all()

    @staticmethod
    async def set_low_data_notified(db: AsyncSession, subscription_id: int, status: bool = True):
        result = await db.execute(select(Subscription).filter(Subscription.id == subscription_id))
        subscription = result.scalars().first()
        if subscription:
            subscription.low_data_notified = status
            await db.commit()
            await db.refresh(subscription)
        return subscription

    @staticmethod
    async def delete_subscription(db: AsyncSession, subscription_id: int):
        result = await db.execute(select(Subscription).filter(Subscription.id == subscription_id))
        subscription = result.scalars().first()
        if subscription:
            await db.delete(subscription)
            await db.commit()
        return subscription

    @staticmethod
    async def update_subscription_renewal(
        db: AsyncSession, 
        subscription_id: int, 
        renewal_paid: bool = None, 
        renewal_template: str = None, 
        renewal_price: int = None, 
        renewal_requested_at = None, 
        renewal_applied: bool = None
    ):
        result = await db.execute(select(Subscription).filter(Subscription.id == subscription_id))
        subscription = result.scalars().first()
        if subscription:
            if renewal_paid is not None:
                subscription.renewal_paid = renewal_paid
            if renewal_template is not None:
                subscription.renewal_template = renewal_template
            if renewal_price is not None:
                subscription.renewal_price = renewal_price
            if renewal_requested_at is not None:
                subscription.renewal_requested_at = renewal_requested_at
            if renewal_applied is not None:
                subscription.renewal_applied = renewal_applied
            await db.commit()
            await db.refresh(subscription)
        return subscription

    @staticmethod
    async def get_subscriptions_for_renewal(db: AsyncSession):
        result = await db.execute(
            select(Subscription).filter(
                Subscription.status == 'active', 
                Subscription.renewal_paid == True, 
                Subscription.renewal_applied == False
            )
        )
        return result.scalars().all()

    @staticmethod
    async def get_subscription_by_username(db: AsyncSession, marzban_username: str) -> Subscription | None:
        result = await db.execute(select(Subscription).filter(Subscription.marzban_username == marzban_username))
        return result.scalars().first()

    @staticmethod
    async def create_renewal_history(db: AsyncSession, subscription_id: int, result: str, details: str = None):
        history = RenewalHistory(
            subscription_id=subscription_id,
            result=result,
            details=details
        )
        db.add(history)
        await db.commit()
        await db.refresh(history)
        return history

    @staticmethod
    async def get_renewal_history(db: AsyncSession, subscription_id: int):
        result = await db.execute(
            select(RenewalHistory).filter(RenewalHistory.subscription_id == subscription_id)
        )
        return result.scalars().all()

    @staticmethod
    async def set_imminent_expiry_notified(db: AsyncSession, subscription_id: int, status: bool = True):
        result = await db.execute(select(Subscription).filter(Subscription.id == subscription_id))
        subscription = result.scalars().first()
        if subscription:
            subscription.imminent_expiry_notified = status
            await db.commit()
            await db.refresh(subscription)
        return subscription

    @staticmethod
    async def set_expired_notified(db: AsyncSession, subscription_id: int, status: bool = True):
        result = await db.execute(select(Subscription).filter(Subscription.id == subscription_id))
        subscription = result.scalars().first()
        if subscription:
            subscription.expired_notified = status
            await db.commit()
            await db.refresh(subscription)
        return subscription

    @staticmethod
    async def create_referral_reward(
        db: AsyncSession,
        subscription_id: int,
        referrer_id: int,
        traffic_bytes: int = None,
        extra_days: int = None,
        credit_amount: int = None,
        reward_value: int | None = None,
    ):
        reward = ReferralReward(
            subscription_id=subscription_id,
            referrer_id=referrer_id,
            traffic_bytes=traffic_bytes,
            extra_days=extra_days,
            credit_amount=credit_amount,
            reward_value=reward_value,
            spent=False
        )
        db.add(reward)
        await db.commit()
        await db.refresh(reward)
        return reward

    @staticmethod
    async def get_unspent_rewards_by_referrer(db: AsyncSession, referrer_id: int):
        result = await db.execute(
            select(ReferralReward).filter(ReferralReward.referrer_id == referrer_id, ReferralReward.spent == False)
        )
        return result.scalars().all()

    @staticmethod
    async def spend_reward(db: AsyncSession, reward_id: int):
        result = await db.execute(select(ReferralReward).filter(ReferralReward.id == reward_id))
        reward = result.scalars().first()
        if reward and not reward.spent:
            reward.spent = True
            await db.commit()
            await db.refresh(reward)
        return reward

    @staticmethod
    async def create_charge_request(
        db: AsyncSession,
        subscription_id: int,
        user_id: int,
        traffic_bytes: int,
        extra_days: int | None,
        price: int,
        receipt_message_id: int | None = None,
        original_price: int | None = None,
        discount_percent: int | None = None,
        discount_amount: int | None = None,
        credit_used: int | None = None,
    ):
        req = ChargeRequest(
            subscription_id=subscription_id,
            user_id=user_id,
            traffic_bytes=traffic_bytes,
            extra_days=extra_days,
            price=price,
            original_price=original_price,
            discount_percent=discount_percent,
            discount_amount=discount_amount,
            credit_used=credit_used,
            receipt_message_id=receipt_message_id,
            status='pending'
        )
        db.add(req)
        await db.commit()
        await db.refresh(req)
        return req

    @staticmethod
    async def get_pending_charge_requests(db: AsyncSession):
        result = await db.execute(
            select(ChargeRequest)
            .options(selectinload(ChargeRequest.user))
            .filter(ChargeRequest.status == 'pending')
        )
        return result.scalars().all()

    @staticmethod
    async def get_charge_request(db: AsyncSession, request_id: int):
        result = await db.execute(
            select(ChargeRequest)
            .options(selectinload(ChargeRequest.user))
            .filter(ChargeRequest.id == request_id)
        )
        return result.scalars().first()

    @staticmethod
    async def update_charge_request_status(db: AsyncSession, request_id: int, status: str):
        req = await SubscriptionRepository.get_charge_request(db, request_id)
        if req:
            req.status = status
            await db.commit()
            await db.refresh(req)
        return req

    @staticmethod
    async def set_subscription_carry_over(db: AsyncSession, subscription_id: int, carry_bytes: int | None, reset_at):
        result = await db.execute(select(Subscription).filter(Subscription.id == subscription_id))
        sub = result.scalars().first()
        if sub:
            sub.carry_over_bytes = carry_bytes
            sub.carry_over_reset_at = reset_at
            await db.commit()
            await db.refresh(sub)
        return sub

    @staticmethod
    async def create_subscription_on_marzban(subscription: Subscription, plan_info: Dict[str, Any]) -> Optional[dict]:
        gb = plan_info.get("gb", 0)
        if gb <= 0:
            return None

        try:
            plan_days = int(plan_info.get("days", 35) or 35)
            marzban_user = await marzban_api.add_user(subscription.marzban_username, gb, plan_days)
            
            # If add_user failed (returns None), check if user already exists (from partial approval)
            if marzban_user is None:
                existing_user = await marzban_api.get_user_info(subscription.marzban_username)
                if existing_user and existing_user.get("subscription_url"):
                    # User already exists, return their info for the approval to proceed
                    return existing_user
            
            return marzban_user
        except Exception:
            # Also try to get existing user on exception
            try:
                existing_user = await marzban_api.get_user_info(subscription.marzban_username)
                if existing_user and existing_user.get("subscription_url"):
                    return existing_user
            except Exception:
                pass
            return None
