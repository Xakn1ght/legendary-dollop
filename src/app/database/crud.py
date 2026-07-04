from app.database.repos.analytics import AnalyticsRepository
from app.database.repos.cashout import CashoutRepository
from app.database.repos.reward import RewardRepository
from app.database.repos.subscription import SubscriptionRepository
from app.database.repos.ticket import TicketRepository
from app.database.repos.user import UserRepository

# --- Cashout ---
has_active_paid_subscription = CashoutRepository.has_active_paid_subscription
create_cashout_request = CashoutRepository.create_cashout_request
get_cashout_request = CashoutRepository.get_cashout_request
list_cashout_requests = CashoutRepository.list_cashout_requests
deny_cashout_request = CashoutRepository.deny_cashout_request
mark_cashout_paid = CashoutRepository.mark_cashout_paid

# --- User ---
get_user_by_id = UserRepository.get_user_by_id
get_user = UserRepository.get_user
create_user = UserRepository.create_user
set_user_language = UserRepository.set_user_language
get_dashboard_prefs = UserRepository.get_dashboard_prefs
update_dashboard_prefs = UserRepository.update_dashboard_prefs
generate_referral_code = UserRepository.generate_referral_code
get_user_by_referral_code = UserRepository.get_user_by_referral_code
get_user_by_username = UserRepository.get_user_by_username
add_credit = UserRepository.add_credit
deduct_credit = UserRepository.deduct_credit
create_referral = UserRepository.create_referral
get_referees_by_referrer = UserRepository.get_referees_by_referrer
set_custom_username = UserRepository.set_custom_username
set_vip_status = UserRepository.set_vip_status
is_user_vip = UserRepository.is_user_vip
get_all_users = UserRepository.get_all_users

# --- Subscription ---
create_subscription = SubscriptionRepository.create_subscription
get_user_subscriptions = SubscriptionRepository.get_user_subscriptions
add_subscription_link = SubscriptionRepository.add_subscription_link
get_user_active_subscriptions = SubscriptionRepository.get_user_active_subscriptions
get_pending_subscriptions = SubscriptionRepository.get_pending_subscriptions
get_pending_toggle_subscriptions = SubscriptionRepository.get_pending_toggle_subscriptions
activate_subscription = SubscriptionRepository.activate_subscription
deactivate_subscription_on_failure = SubscriptionRepository.deactivate_subscription_on_failure
get_all_active_subscriptions_for_notification = SubscriptionRepository.get_all_active_subscriptions_for_notification
set_low_data_notified = SubscriptionRepository.set_low_data_notified
delete_subscription = SubscriptionRepository.delete_subscription
update_subscription_renewal = SubscriptionRepository.update_subscription_renewal
get_subscriptions_for_renewal = SubscriptionRepository.get_subscriptions_for_renewal
get_subscription_by_username = SubscriptionRepository.get_subscription_by_username
create_renewal_history = SubscriptionRepository.create_renewal_history
get_renewal_history = SubscriptionRepository.get_renewal_history
set_imminent_expiry_notified = SubscriptionRepository.set_imminent_expiry_notified
set_expired_notified = SubscriptionRepository.set_expired_notified
create_referral_reward = SubscriptionRepository.create_referral_reward
get_unspent_rewards_by_referrer = SubscriptionRepository.get_unspent_rewards_by_referrer
spend_reward = SubscriptionRepository.spend_reward
create_charge_request = SubscriptionRepository.create_charge_request
get_pending_charge_requests = SubscriptionRepository.get_pending_charge_requests
get_charge_request = SubscriptionRepository.get_charge_request
update_charge_request_status = SubscriptionRepository.update_charge_request_status
set_subscription_carry_over = SubscriptionRepository.set_subscription_carry_over
create_subscription_on_marzban = SubscriptionRepository.create_subscription_on_marzban

# --- Ticket ---
create_ticket = TicketRepository.create_ticket
add_ticket_message = TicketRepository.add_ticket_message
get_ticket_by_id = TicketRepository.get_ticket_by_id
list_tickets_by_user = TicketRepository.list_tickets_by_user
get_ticket_messages = TicketRepository.get_ticket_messages
update_ticket_status = TicketRepository.update_ticket_status
set_ticket_notify_on_reply = TicketRepository.set_ticket_notify_on_reply
save_ticket_feedback = TicketRepository.save_ticket_feedback
assign_ticket = TicketRepository.assign_ticket
change_ticket_category = TicketRepository.change_ticket_category
change_ticket_priority = TicketRepository.change_ticket_priority
set_ticket_allow_more = TicketRepository.set_ticket_allow_more
get_category_queue_position = TicketRepository.get_category_queue_position
list_tickets_by_category = TicketRepository.list_tickets_by_category
list_all_tickets = TicketRepository.list_all_tickets
start_private_chat = TicketRepository.start_private_chat
accept_chat_invitation = TicketRepository.accept_chat_invitation
expire_chat_invitation = TicketRepository.expire_chat_invitation
end_private_chat = TicketRepository.end_private_chat
add_ticket_message_with_reply = TicketRepository.add_ticket_message_with_reply
get_ticket_message_by_telegram_id = TicketRepository.get_ticket_message_by_telegram_id
update_ticket_message_text_by_telegram_id = TicketRepository.update_ticket_message_text_by_telegram_id
get_active_chat_tickets = TicketRepository.get_active_chat_tickets

# --- Reward ---
# StarManager class replacement (mapping static methods)
class StarManager:
    add_stars = RewardRepository.add_stars
    reset_stars = RewardRepository.reset_stars
    get_star_balance = RewardRepository.get_star_balance
    transfer_stars = RewardRepository.transfer_stars
    get_daily_cap_status = RewardRepository.get_daily_cap_status

add_stars = RewardRepository.add_stars
# Star Season (Phase B): referral stars feed seasonal milestone progress, not the
# permanent star/tier balance.
add_season_stars = RewardRepository.add_season_stars
get_or_create_active_season = RewardRepository.get_or_create_active_season
get_season_progress = RewardRepository.get_season_progress
get_active_coupons = RewardRepository.get_active_coupons
get_coupon_by_id = RewardRepository.get_coupon_by_id
mark_coupon_used = RewardRepository.mark_coupon_used
restore_coupon = RewardRepository.restore_coupon
free_gb_bonus_for_coupon = RewardRepository.free_gb_bonus_for_coupon
end_active_season = RewardRepository.end_active_season
reset_stars = RewardRepository.reset_stars
log_star_change = RewardRepository.log_star_change
get_star_history = RewardRepository.get_star_history
create_star_reward_tier = RewardRepository.create_star_reward_tier
get_star_reward_tier = RewardRepository.get_star_reward_tier
get_star_reward_tier_by_threshold = None  # overwritten below by real implementation
get_all_star_reward_tiers = RewardRepository.get_all_star_reward_tiers
update_star_reward_tier = RewardRepository.update_star_reward_tier
delete_star_reward_tier = RewardRepository.delete_star_reward_tier
create_user_star_reward_claim = RewardRepository.create_user_star_reward_claim
get_user_unclaimed_rewards = RewardRepository.get_user_unclaimed_rewards
claim_user_star_reward = RewardRepository.claim_user_star_reward
get_user_star_reward_claim_by_id = RewardRepository.get_user_star_reward_claim_by_id
get_pending_extradays_claim = RewardRepository.get_pending_extradays_claim
get_or_create_daily_game_play = RewardRepository.get_or_create_daily_game_play
can_play_daily_game = RewardRepository.can_play_daily_game
submit_daily_game_score = RewardRepository.submit_daily_game_score
check_daily_game_play = RewardRepository.check_daily_game_play
save_game_play = RewardRepository.save_game_play
get_monthly_arcade_ranking = RewardRepository.get_monthly_arcade_ranking
add_arcade_flag = RewardRepository.add_arcade_flag
get_active_challenges = RewardRepository.get_active_challenges
get_user_challenge_progress = RewardRepository.get_user_challenge_progress
update_challenge_progress = RewardRepository.update_challenge_progress
ensure_current_weekly_challenge = RewardRepository.ensure_current_weekly_challenge
ensure_today_daily_challenge = RewardRepository.ensure_today_daily_challenge
record_daily_login = RewardRepository.record_daily_login
calculate_and_award_cashback = RewardRepository.calculate_and_award_cashback
get_user_achievements = RewardRepository.get_user_achievements
check_and_award_achievements = RewardRepository.check_and_award_achievements
add_reward_history = RewardRepository.add_reward_history
get_user_reward_history = RewardRepository.get_user_reward_history
add_experience_points = RewardRepository.add_experience_points
check_level_up = RewardRepository.check_level_up
add_loyalty_points = RewardRepository.add_loyalty_points
deduct_loyalty_points = RewardRepository.deduct_loyalty_points
get_reward_config = RewardRepository.get_reward_config
update_reward_config = RewardRepository.update_reward_config
create_user_gift = RewardRepository.create_user_gift
set_gift_payment_status = RewardRepository.set_gift_payment_status
accept_user_gift = RewardRepository.accept_user_gift
get_user_gifts = RewardRepository.get_user_gifts
add_user_discount = RewardRepository.add_user_discount
get_active_user_discounts = RewardRepository.get_active_user_discounts
mark_user_discounts_used = RewardRepository.mark_user_discounts_used
get_or_create_daily_cap = RewardRepository.get_or_create_daily_cap
get_daily_cap_status = RewardRepository.get_daily_cap_status

# --- Analytics ---
get_user_analytics = AnalyticsRepository.get_user_analytics
update_user_analytics = AnalyticsRepository.update_user_analytics
update_leaderboard = AnalyticsRepository.update_leaderboard
get_leaderboard = AnalyticsRepository.get_leaderboard
get_star_analytics_overview = AnalyticsRepository.get_star_analytics_overview
get_star_distribution_by_reason = AnalyticsRepository.get_star_distribution_by_reason
get_popular_star_rewards = AnalyticsRepository.get_popular_star_rewards
get_star_analytics_by_period = AnalyticsRepository.get_star_analytics_by_period
get_user_star_statistics = AnalyticsRepository.get_user_star_statistics
get_game_leaderboard = AnalyticsRepository.get_leaderboard # Mapping to generic leaderboard if specific logic isn't needed, otherwise need implementation

# Helper to fix missing lambda
async def _get_star_reward_tier_by_threshold(db, threshold):
    from sqlalchemy.future import select

    from app.database.models import StarRewardTier
    result = await db.execute(select(StarRewardTier).filter(StarRewardTier.star_threshold == threshold))
    return result.scalars().first()

get_star_reward_tier_by_threshold = _get_star_reward_tier_by_threshold

# Helper for game leaderboard if it differs
async def _get_game_leaderboard(db, period="daily", limit=10):
    # This was specific to DailyGamePlay in original crud
    # Re-implementing briefly here or in AnalyticsRepository
    from datetime import datetime, timedelta

    from sqlalchemy import select

    from app.database.models import DailyGamePlay, User
    
    now = datetime.utcnow()
    start_play_date = None

    if period == "daily":
        start_play_date = now.date()
    elif period == "weekly":
        start_play_date = (now - timedelta(days=now.weekday())).date()

    query = (
        select(DailyGamePlay, User.username, User.full_name, User.custom_username)
        .join(User, User.id == DailyGamePlay.user_id)
        .filter(User.show_on_leaderboard == True)  # Only show users who opted in
        .order_by(DailyGamePlay.best_score.desc())
        .limit(limit)
    )

    if start_play_date is not None:
        query = query.filter(DailyGamePlay.play_date >= start_play_date)

    result = await db.execute(query)
    rows = result.all()
    leaderboard = []
    rank = 1
    for play, username, full_name, custom_username in rows:
        leaderboard.append({
            "rank": rank,
            "user_id": play.user_id,
            "name": (custom_username or username or full_name or str(play.user_id)),
            "score": play.best_score,
        })
        rank += 1
    return leaderboard

get_game_leaderboard = _get_game_leaderboard
