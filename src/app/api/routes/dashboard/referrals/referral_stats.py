from app.api.deps import _verify_webapp_auth
from app.utils.admin_bot_helper import resolve_user_bot

from ..common import *  # noqa: F403


async def handle_dashboard_referrals(request: web.Request):
    """Get user referral stats and list"""
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)
    
    try:
        async with AsyncSessionLocal() as session:
            user = await crud.get_user(session, user_chat_id)
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)
            
            # Get all referrals made by this user
            referrals_result = await session.execute(
                select(Referral, User)
                .join(User, Referral.referee_id == User.id)
                .filter(Referral.referrer_id == user.id)
                .order_by(desc(Referral.created_at))
            )
            referrals = referrals_result.all()
            
            # Count active referrals (users who have active subscriptions)
            active_count = 0
            referral_list = []
            for ref, referee in referrals:
                # Check if referee has any active subscription
                subs = await crud.get_user_subscriptions(session, referee.id)
                has_active = any(s.status == 'active' for s in subs)
                if has_active:
                    active_count += 1
                
                referral_list.append({
                    "id": ref.id,
                    "username": referee.username or "Anonymous",
                    "full_name": referee.full_name or "User",
                    "joined_at": ref.created_at.isoformat() if ref.created_at else None,
                    "is_active": has_active
                })
            
            # Get total credits earned from referrals
            rewards_result = await session.execute(
                select(func.sum(ReferralReward.credit_amount))
                .filter(ReferralReward.referrer_id == user.id)
            )
            total_earned = rewards_result.scalar() or 0
            
            # Get referral link - try to get bot username from app state
            try:
                bot = resolve_user_bot(request.app.get('bot'))
                if bot and hasattr(bot, 'username'):
                    bot_username = bot.username
                elif bot and hasattr(bot, '_me') and bot._me:
                    bot_username = bot._me.username
                else:
                    bot_username = "AstroByteBot"  # Default fallback
            except Exception:
                bot_username = "AstroByteBot"
            
            referral_link = f"https://t.me/{bot_username}?start={user.referral_code}" if user.referral_code else None

            # Whether the user has already been attributed to a referrer — the
            # Rewards page uses this to show/hide the "enter a friend's code" box.
            existing_ref = await session.execute(
                select(Referral).filter(Referral.referee_id == user.id)
            )
            has_referrer = existing_ref.scalars().first() is not None

            resp = web.json_response(
                {
                    "ok": True,
                    "total": len(referrals),
                    "active": active_count,
                    "earned": total_earned,
                    "referral_code": user.referral_code,
                    "referral_link": referral_link,
                    "has_referrer": has_referrer,
                    "referrals": referral_list[:20],  # Limit to 20 most recent
                }
            )
            if new_session_token:
                set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
            return resp
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"Error fetching referrals: {e}")
        return web.json_response({"ok": False, "error": "server_error"}, status=500)
