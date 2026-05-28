"""
Database Indexes for ASSTRO Bot
Critical indexes for optimal performance based on query patterns
"""

import time

from sqlalchemy import Index, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.logger import DatabaseError, log_database_operation, log_error

# Critical indexes for optimal performance
CRITICAL_INDEXES = [
    # ========================================
    # USERS TABLE INDEXES
    # ========================================
    
    # Primary lookup by chat_id (most frequent query)
    Index('idx_users_chat_id', 'users', 'chat_id'),
    
    # Referral code lookup (frequent in purchase flow)
    Index('idx_users_referral_code', 'users', 'referral_code'),
    
    # Username lookup (for admin operations)
    Index('idx_users_username', 'users', 'username'),
    
    # Created date for analytics and reporting
    Index('idx_users_created_at', 'users', 'created_at'),
    
    # Level and XP for leaderboards and gamification
    Index('idx_users_level_xp', 'users', 'level', 'experience_points'),
    
    # Loyalty points for rewards system
    Index('idx_users_loyalty_points', 'users', 'loyalty_points'),
    
    # Login streak for daily rewards
    Index('idx_users_login_streak', 'users', 'login_streak'),
    
    # Last daily login for streak calculations
    Index('idx_users_last_daily_login', 'users', 'last_daily_login'),
    
    # ========================================
    # SUBSCRIPTIONS TABLE INDEXES
    # ========================================
    
    # User's active subscriptions (most frequent query)
    Index('idx_subscriptions_user_status', 'subscriptions', 'user_id', 'status'),
    
    # Pending subscriptions for admin approval
    Index('idx_subscriptions_status_pending', 'subscriptions', 'status'),
    
    # Marzban username lookup (frequent in API calls)
    Index('idx_subscriptions_marzban_username', 'subscriptions', 'marzban_username'),
    
    # Referrer lookup for reward calculations
    Index('idx_subscriptions_referrer', 'subscriptions', 'referrer_id'),
    
    # Created date for analytics
    Index('idx_subscriptions_created_at', 'subscriptions', 'created_at'),
    
    # Renewal-related indexes
    Index('idx_subscriptions_renewal_paid', 'subscriptions', 'renewal_paid'),
    Index('idx_subscriptions_renewal_applied', 'subscriptions', 'renewal_applied'),
    
    # Notification status indexes
    Index('idx_subscriptions_low_data_notified', 'subscriptions', 'low_data_notified'),
    Index('idx_subscriptions_imminent_expiry_notified', 'subscriptions', 'imminent_expiry_notified'),
    Index('idx_subscriptions_expired_notified', 'subscriptions', 'expired_notified'),
    
    # ========================================
    # REFERRALS TABLE INDEXES
    # ========================================
    
    # Referrer's referrals (frequent query)
    Index('idx_referrals_referrer', 'referrals', 'referrer_id'),
    
    # Referee lookup (unique constraint already exists)
    Index('idx_referrals_referee', 'referrals', 'referee_id'),
    
    # Created date for analytics
    Index('idx_referrals_created_at', 'referrals', 'created_at'),
    
    # ========================================
    # REFERRAL_REWARDS TABLE INDEXES
    # ========================================
    
    # Unspent rewards by referrer (frequent query)
    Index('idx_referral_rewards_referrer_spent', 'referral_rewards', 'referrer_id', 'spent'),
    
    # Subscription rewards
    Index('idx_referral_rewards_subscription', 'referral_rewards', 'subscription_id'),
    
    # Created date for analytics
    Index('idx_referral_rewards_created_at', 'referral_rewards', 'created_at'),
    
    # ========================================
    # CHARGE_REQUESTS TABLE INDEXES
    # ========================================
    
    # Pending charge requests for admin
    Index('idx_charge_requests_status', 'charge_requests', 'status'),
    
    # User's charge requests
    Index('idx_charge_requests_user', 'charge_requests', 'user_id'),
    
    # Subscription charge requests
    Index('idx_charge_requests_subscription', 'charge_requests', 'subscription_id'),
    
    # Created date for analytics
    Index('idx_charge_requests_created_at', 'charge_requests', 'created_at'),
    
    # ========================================
    # RENEWAL_HISTORY TABLE INDEXES
    # ========================================
    
    # Subscription renewal history
    Index('idx_renewal_history_subscription', 'renewal_history', 'subscription_id'),
    
    # Renewal date for analytics
    Index('idx_renewal_history_renewed_at', 'renewal_history', 'renewed_at'),
    
    # ========================================
    # ACHIEVEMENTS TABLE INDEXES
    # ========================================
    
    # Achievement type lookup
    Index('idx_achievements_requirement_type', 'achievements', 'requirement_type'),
    
    # Active achievements
    Index('idx_achievements_created_at', 'achievements', 'created_at'),
    
    # ========================================
    # USER_ACHIEVEMENTS TABLE INDEXES
    # ========================================
    
    # User's achievements (frequent query)
    Index('idx_user_achievements_user', 'user_achievements', 'user_id'),
    
    # Achievement lookup
    Index('idx_user_achievements_achievement', 'user_achievements', 'achievement_id'),
    
    # Earned date for analytics
    Index('idx_user_achievements_earned_at', 'user_achievements', 'earned_at'),
    
    # ========================================
    # CHALLENGES TABLE INDEXES
    # ========================================
    
    # Active challenges by type
    Index('idx_challenges_type_active', 'challenges', 'challenge_type', 'active'),
    
    # Challenge date range
    Index('idx_challenges_start_end', 'challenges', 'start_date', 'end_date'),
    
    # Requirement type for challenge matching
    Index('idx_challenges_requirement_type', 'challenges', 'requirement_type'),
    
    # ========================================
    # USER_CHALLENGES TABLE INDEXES
    # ========================================
    
    # User's challenge progress (frequent query)
    Index('idx_user_challenges_user', 'user_challenges', 'user_id'),
    
    # Challenge progress lookup
    Index('idx_user_challenges_challenge', 'user_challenges', 'challenge_id'),
    
    # Completed challenges
    Index('idx_user_challenges_completed', 'user_challenges', 'completed'),
    
    # Progress tracking
    Index('idx_user_challenges_progress', 'user_challenges', 'progress'),
    
    # ========================================
    # REWARD_HISTORY TABLE INDEXES
    # ========================================
    
    # User's reward history (frequent query)
    Index('idx_reward_history_user', 'reward_history', 'user_id'),
    
    # Reward type analytics
    Index('idx_reward_history_type', 'reward_history', 'reward_type'),
    
    # Source analytics
    Index('idx_reward_history_source', 'reward_history', 'source'),
    
    # Earned date for analytics
    Index('idx_reward_history_earned_at', 'reward_history', 'earned_at'),
    
    # Spent date for analytics
    Index('idx_reward_history_spent_at', 'reward_history', 'spent_at'),
    
    # ========================================
    # USER_ANALYTICS TABLE INDEXES
    # ========================================
    
    # User's analytics by date (frequent query)
    Index('idx_user_analytics_user_date', 'user_analytics', 'user_id', 'date'),
    
    # Date-based analytics
    Index('idx_user_analytics_date', 'user_analytics', 'date'),
    
    # ========================================
    # REWARD_EFFECTIVENESS TABLE INDEXES
    # ========================================
    
    # Reward type effectiveness
    Index('idx_reward_effectiveness_type', 'reward_effectiveness', 'reward_type'),
    
    # Date-based effectiveness
    Index('idx_reward_effectiveness_date', 'reward_effectiveness', 'date'),
    
    # ========================================
    # LEADERBOARDS TABLE INDEXES
    # ========================================
    
    # Leaderboard by category and period (frequent query)
    Index('idx_leaderboards_category_period', 'leaderboards', 'category', 'period'),
    
    # User's leaderboard entries
    Index('idx_leaderboards_user', 'leaderboards', 'user_id'),
    
    # Score ranking
    Index('idx_leaderboards_score', 'leaderboards', 'score'),
    
    # Date-based leaderboards
    Index('idx_leaderboards_date', 'leaderboards', 'date'),
    
    # ========================================
    # SEASONAL_EVENTS TABLE INDEXES
    # ========================================
    
    # Active events
    Index('idx_seasonal_events_active', 'seasonal_events', 'active'),
    
    # Event date range
    Index('idx_seasonal_events_start_end', 'seasonal_events', 'start_date', 'end_date'),
    
    # Event type
    Index('idx_seasonal_events_type', 'seasonal_events', 'event_type'),
    
    # ========================================
    # USER_GIFTS TABLE INDEXES
    # ========================================
    
    # User's sent gifts
    Index('idx_user_gifts_sender', 'user_gifts', 'sender_id'),
    
    # User's received gifts
    Index('idx_user_gifts_receiver', 'user_gifts', 'receiver_id'),
    
    # Gift acceptance status
    Index('idx_user_gifts_accepted', 'user_gifts', 'accepted'),
    
    # Gift type
    Index('idx_user_gifts_type', 'user_gifts', 'gift_type'),
    
    # Created date for analytics
    Index('idx_user_gifts_created_at', 'user_gifts', 'created_at'),
    
    # ========================================
    # TICKETS TABLE INDEXES
    # ========================================
    
    # User's tickets (most frequent query)
    Index('idx_tickets_user_id', 'tickets', 'user_id'),
    
    # Ticket status filtering (for admin dashboard)
    Index('idx_tickets_status', 'tickets', 'status'),
    
    # Created date for sorting and analytics
    Index('idx_tickets_created_at', 'tickets', 'created_at'),
    
    # Category filtering
    Index('idx_tickets_category', 'tickets', 'category'),
    
    # Admin assignment lookup
    Index('idx_tickets_assigned_admin_id', 'tickets', 'assigned_admin_id'),
    
    # ========================================
    # TICKET_MESSAGES TABLE INDEXES
    # ========================================
    
    # Messages by ticket (most frequent query)
    Index('idx_ticket_messages_ticket_id', 'ticket_messages', 'ticket_id'),
    
    # Created date for sorting messages chronologically
    Index('idx_ticket_messages_created_at', 'ticket_messages', 'created_at'),
    
    # ========================================
    # NOTIFICATIONS TABLE INDEXES
    # ========================================
    
    # User's notifications (most frequent query)
    Index('idx_notifications_user_id', 'notifications', 'user_id'),
    
    # Created date for sorting notifications
    Index('idx_notifications_created_at', 'notifications', 'created_at'),
]

# Composite indexes for complex queries
COMPOSITE_INDEXES = [
    # User lookup by chat_id and status
    Index('idx_users_chat_id_status', 'users', 'chat_id', 'level'),
    
    # Subscription lookup by user and status
    Index('idx_subscriptions_user_status_created', 'subscriptions', 'user_id', 'status', 'created_at'),
    
    # Referral rewards by referrer and spent status
    Index('idx_referral_rewards_referrer_spent_created', 'referral_rewards', 'referrer_id', 'spent', 'created_at'),
    
    # User achievements by user and achievement
    Index('idx_user_achievements_user_achievement', 'user_achievements', 'user_id', 'achievement_id'),
    
    # User challenges by user and challenge
    Index('idx_user_challenges_user_challenge', 'user_challenges', 'user_id', 'challenge_id'),
    
    # Reward history by user and type
    Index('idx_reward_history_user_type', 'reward_history', 'user_id', 'reward_type'),
    
    # Leaderboards by category, period, and score
    Index('idx_leaderboards_category_period_score', 'leaderboards', 'category', 'period', 'score'),
    
    # User analytics by user and date
    Index('idx_user_analytics_user_date_type', 'user_analytics', 'user_id', 'date', 'login_count'),
    
    # Notifications by user and read status (composite for efficient filtering)
    Index('idx_notifications_user_read', 'notifications', 'user_id', 'read'),
]

# Performance optimization indexes
PERFORMANCE_INDEXES = [
    # Partial indexes for active records only
    Index('idx_subscriptions_active_only', 'subscriptions', 'user_id', 
          postgresql_where=text("status = 'active'")),
    
    # Partial indexes for unspent rewards
    Index('idx_referral_rewards_unspent_only', 'referral_rewards', 'referrer_id', 
          postgresql_where=text("spent = false")),
    
    # Partial indexes for pending requests
    Index('idx_charge_requests_pending_only', 'charge_requests', 'user_id', 
          postgresql_where=text("status = 'pending'")),
    
    # Partial indexes for completed challenges
    Index('idx_user_challenges_completed_only', 'user_challenges', 'user_id', 
          postgresql_where=text("completed = true")),
]

def _parse_index(index_obj):
    """Extract table name and columns from SQLAlchemy Index object.
    
    Index objects are created as: Index('name', 'table', 'col1', 'col2', ...)
    We need to extract the table (2nd arg) and columns (3rd+ args).
    """
    # Get the expressions (columns) from the index
    # Index stores columns in .expressions or we can get from .columns
    try:
        # Try to get table name from the index's table attribute
        if hasattr(index_obj, 'table') and index_obj.table is not None:
            table_name = index_obj.table.name if hasattr(index_obj.table, 'name') else str(index_obj.table)
        else:
            # Fallback: parse from expressions or use a default
            # For Index('name', 'table', 'col1'), we need to extract manually
            # Since Index doesn't store table as separate attr, we'll need to track it differently
            return None, []
        
        # Get column names
        columns = []
        if hasattr(index_obj, 'expressions'):
            for expr in index_obj.expressions:
                if hasattr(expr, 'name'):
                    columns.append(expr.name)
                elif hasattr(expr, 'key'):
                    columns.append(expr.key)
                else:
                    columns.append(str(expr))
        elif hasattr(index_obj, 'columns'):
            for col in index_obj.columns:
                if hasattr(col, 'name'):
                    columns.append(col.name)
                elif hasattr(col, 'key'):
                    columns.append(col.key)
                else:
                    columns.append(str(col))
        
        return table_name, columns
    except Exception:
        return None, []


async def create_all_indexes(session: AsyncSession):
    """Create all critical database indexes for optimal performance"""
    start_time = time.time()
    
    # Helper to create index from definition tuple
    async def create_index_from_def(index_def):
        """index_def is a tuple: (name, table, col1, col2, ...) or Index object"""
        try:
            if isinstance(index_def, Index):
                # Try to parse Index object
                table_name, columns = _parse_index(index_def)
                if not table_name or not columns:
                    # Fallback: Index was created with strings, parse manually
                    # This is tricky - we'd need to store metadata differently
                    return False
                index_name = index_def.name
            else:
                # Assume tuple format: (name, table, col1, col2, ...)
                index_name = index_def[0]
                table_name = index_def[1]
                columns = list(index_def[2:])
            
            if not table_name or not columns:
                return False
            
            cols_str = ', '.join(columns)
            # Use autocommit for index creation to avoid transaction abort issues
            await session.execute(text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({cols_str})"))
            await session.commit()  # Commit after each index to avoid transaction abort cascade
            log_database_operation("create_index", table_name, True, 0, index_name=index_name)
            return True
        except Exception as e:
            # Rollback on error and continue
            await session.rollback()
            table_name = index_def[1] if isinstance(index_def, (tuple, list)) else getattr(index_def, 'name', 'unknown')
            index_name = index_def[0] if isinstance(index_def, (tuple, list)) else getattr(index_def, 'name', 'unknown')
            log_error(e, {"operation": "create_index", "index_name": index_name, "table": table_name})
            return False
    
    try:
        # Create critical indexes - parse Index objects manually
        # Since Index('name', 'table', 'col') doesn't expose table/columns easily,
        # we'll recreate them as tuples for easier parsing
        critical_index_defs = [
            ('idx_users_chat_id', 'users', 'chat_id'),
            ('idx_users_referral_code', 'users', 'referral_code'),
            ('idx_users_username', 'users', 'username'),
            ('idx_users_created_at', 'users', 'created_at'),
            ('idx_users_level_xp', 'users', 'level', 'experience_points'),
            ('idx_users_loyalty_points', 'users', 'loyalty_points'),
            ('idx_users_login_streak', 'users', 'login_streak'),
            ('idx_users_last_daily_login', 'users', 'last_daily_login'),
            ('idx_subscriptions_user_status', 'subscriptions', 'user_id', 'status'),
            ('idx_subscriptions_status_pending', 'subscriptions', 'status'),
            ('idx_subscriptions_marzban_username', 'subscriptions', 'marzban_username'),
            ('idx_subscriptions_referrer', 'subscriptions', 'referrer_id'),
            ('idx_subscriptions_created_at', 'subscriptions', 'created_at'),
            ('idx_subscriptions_renewal_paid', 'subscriptions', 'renewal_paid'),
            ('idx_subscriptions_renewal_applied', 'subscriptions', 'renewal_applied'),
            ('idx_subscriptions_low_data_notified', 'subscriptions', 'low_data_notified'),
            ('idx_subscriptions_imminent_expiry_notified', 'subscriptions', 'imminent_expiry_notified'),
            ('idx_subscriptions_expired_notified', 'subscriptions', 'expired_notified'),
            ('idx_referrals_referrer', 'referrals', 'referrer_id'),
            ('idx_referrals_referee', 'referrals', 'referee_id'),
            ('idx_referrals_created_at', 'referrals', 'created_at'),
            ('idx_referral_rewards_referrer_spent', 'referral_rewards', 'referrer_id', 'spent'),
            ('idx_referral_rewards_subscription', 'referral_rewards', 'subscription_id'),
            ('idx_referral_rewards_created_at', 'referral_rewards', 'created_at'),
            ('idx_charge_requests_status', 'charge_requests', 'status'),
            ('idx_charge_requests_user', 'charge_requests', 'user_id'),
            ('idx_charge_requests_subscription', 'charge_requests', 'subscription_id'),
            ('idx_charge_requests_created_at', 'charge_requests', 'created_at'),
            ('idx_renewal_history_subscription', 'renewal_history', 'subscription_id'),
            ('idx_renewal_history_renewed_at', 'renewal_history', 'renewed_at'),
            ('idx_achievements_requirement_type', 'achievements', 'requirement_type'),
            ('idx_achievements_created_at', 'achievements', 'created_at'),
            ('idx_user_achievements_user', 'user_achievements', 'user_id'),
            ('idx_user_achievements_achievement', 'user_achievements', 'achievement_id'),
            ('idx_user_achievements_earned_at', 'user_achievements', 'earned_at'),
            ('idx_challenges_type_active', 'challenges', 'challenge_type', 'active'),
            ('idx_challenges_start_end', 'challenges', 'start_date', 'end_date'),
            ('idx_challenges_requirement_type', 'challenges', 'requirement_type'),
            ('idx_user_challenges_user', 'user_challenges', 'user_id'),
            ('idx_user_challenges_challenge', 'user_challenges', 'challenge_id'),
            ('idx_user_challenges_completed', 'user_challenges', 'completed'),
            ('idx_user_challenges_progress', 'user_challenges', 'progress'),
            ('idx_reward_history_user', 'reward_history', 'user_id'),
            ('idx_reward_history_type', 'reward_history', 'reward_type'),
            ('idx_reward_history_source', 'reward_history', 'source'),
            ('idx_reward_history_earned_at', 'reward_history', 'earned_at'),
            ('idx_reward_history_spent_at', 'reward_history', 'spent_at'),
            ('idx_user_analytics_user_date', 'user_analytics', 'user_id', 'date'),
            ('idx_user_analytics_date', 'user_analytics', 'date'),
            ('idx_reward_effectiveness_type', 'reward_effectiveness', 'reward_type'),
            ('idx_reward_effectiveness_date', 'reward_effectiveness', 'date'),
            ('idx_leaderboards_category_period', 'leaderboards', 'category', 'period'),
            ('idx_leaderboards_user', 'leaderboards', 'user_id'),
            ('idx_leaderboards_score', 'leaderboards', 'score'),
            ('idx_leaderboards_date', 'leaderboards', 'date'),
            ('idx_seasonal_events_active', 'seasonal_events', 'active'),
            ('idx_seasonal_events_start_end', 'seasonal_events', 'start_date', 'end_date'),
            ('idx_seasonal_events_type', 'seasonal_events', 'event_type'),
            ('idx_user_gifts_sender', 'user_gifts', 'sender_id'),
            ('idx_user_gifts_receiver', 'user_gifts', 'receiver_id'),
            ('idx_user_gifts_accepted', 'user_gifts', 'accepted'),
            ('idx_user_gifts_type', 'user_gifts', 'gift_type'),
            ('idx_user_gifts_created_at', 'user_gifts', 'created_at'),
            ('idx_tickets_user_id', 'tickets', 'user_id'),
            ('idx_tickets_status', 'tickets', 'status'),
            ('idx_tickets_created_at', 'tickets', 'created_at'),
            ('idx_tickets_category', 'tickets', 'category'),
            ('idx_tickets_assigned_admin_id', 'tickets', 'assigned_admin_id'),
            ('idx_ticket_messages_ticket_id', 'ticket_messages', 'ticket_id'),
            ('idx_ticket_messages_created_at', 'ticket_messages', 'created_at'),
            ('idx_notifications_user_id', 'notifications', 'user_id'),
            ('idx_notifications_created_at', 'notifications', 'created_at'),
        ]
        
        for index_def in critical_index_defs:
            await create_index_from_def(index_def)
        
        # Create composite indexes
        composite_index_defs = [
            ('idx_users_chat_id_status', 'users', 'chat_id', 'level'),
            ('idx_subscriptions_user_status_created', 'subscriptions', 'user_id', 'status', 'created_at'),
            ('idx_referral_rewards_referrer_spent_created', 'referral_rewards', 'referrer_id', 'spent', 'created_at'),
            ('idx_user_achievements_user_achievement', 'user_achievements', 'user_id', 'achievement_id'),
            ('idx_user_challenges_user_challenge', 'user_challenges', 'user_id', 'challenge_id'),
            ('idx_reward_history_user_type', 'reward_history', 'user_id', 'reward_type'),
            ('idx_leaderboards_category_period_score', 'leaderboards', 'category', 'period', 'score'),
            ('idx_user_analytics_user_date_type', 'user_analytics', 'user_id', 'date', 'login_count'),
            ('idx_notifications_user_read', 'notifications', 'user_id', 'read'),
        ]
        
        for index_def in composite_index_defs:
            await create_index_from_def(index_def)
        
        # Create performance indexes (with WHERE clauses)
        performance_index_defs = [
            ('idx_subscriptions_active_only', 'subscriptions', 'user_id', "status = 'active'"),
            ('idx_referral_rewards_unspent_only', 'referral_rewards', 'referrer_id', "spent = false"),
            ('idx_charge_requests_pending_only', 'charge_requests', 'user_id', "status = 'pending'"),
            ('idx_user_challenges_completed_only', 'user_challenges', 'user_id', "completed = true"),
        ]
        
        for index_def in performance_index_defs:
            try:
                index_name = index_def[0]
                table_name = index_def[1]
                columns = [index_def[2]]  # First column
                where_clause = index_def[3]  # WHERE condition
                
                cols_str = ', '.join(columns)
                await session.execute(text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({cols_str}) WHERE {where_clause}"))
                await session.commit()  # Commit after each index
                log_database_operation("create_index", table_name, True, 0, index_name=index_name)
            except Exception as e:
                await session.rollback()  # Rollback on error and continue
                log_error(e, {"operation": "create_index", "index_name": index_def[0], "table": index_def[1]})
        duration = time.time() - start_time
        log_database_operation("create_all_indexes", "all_tables", True, duration)
        
        return True
        
    except Exception as e:
        await session.rollback()
        duration = time.time() - start_time
        log_database_operation("create_all_indexes", "all_tables", False, duration, error=str(e))
        log_error(e, {"operation": "create_all_indexes"})
        raise DatabaseError(f"Failed to create indexes: {str(e)}")

async def analyze_table_performance(session: AsyncSession):
    """Analyze table performance and suggest additional indexes"""
    try:
        # Get table statistics
        result = await session.execute(text("""
            SELECT 
                schemaname,
                tablename,
                attname,
                n_distinct,
                correlation
            FROM pg_stats 
            WHERE schemaname = 'public'
            ORDER BY tablename, n_distinct DESC
        """))
        
        stats = result.fetchall()
        
        # Analyze query patterns and suggest indexes
        suggestions = []
        
        for stat in stats:
            table_name = stat[1]
            column_name = stat[2]
            n_distinct = stat[3]
            correlation = stat[4]
            
            # Suggest indexes for high-cardinality columns
            if n_distinct and n_distinct > 100:
                suggestions.append(f"Consider index on {table_name}.{column_name} (distinct values: {n_distinct})")
            
            # Suggest indexes for low-correlation columns (good for range queries)
            if correlation and correlation < 0.1:
                suggestions.append(f"Consider index on {table_name}.{column_name} (correlation: {correlation:.3f})")
        
        return suggestions
        
    except Exception as e:
        log_error(e, {"operation": "analyze_table_performance"})
        return []

async def get_index_usage_stats(session: AsyncSession):
    """Get index usage statistics"""
    try:
        result = await session.execute(text("""
            SELECT 
                schemaname,
                tablename,
                indexname,
                idx_scan,
                idx_tup_read,
                idx_tup_fetch
            FROM pg_stat_user_indexes 
            ORDER BY idx_scan DESC
        """))
        
        return result.fetchall()
        
    except Exception as e:
        log_error(e, {"operation": "get_index_usage_stats"})
        return []

# Index creation functions for specific tables
async def create_user_indexes(session: AsyncSession):
    """Create indexes for users table"""
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_users_chat_id ON users (chat_id)",
        "CREATE INDEX IF NOT EXISTS idx_users_referral_code ON users (referral_code)",
        "CREATE INDEX IF NOT EXISTS idx_users_username ON users (username)",
        "CREATE INDEX IF NOT EXISTS idx_users_created_at ON users (created_at)",
        "CREATE INDEX IF NOT EXISTS idx_users_level_xp ON users (level, experience_points)",
        "CREATE INDEX IF NOT EXISTS idx_users_loyalty_points ON users (loyalty_points)",
        "CREATE INDEX IF NOT EXISTS idx_users_login_streak ON users (login_streak)",
        "CREATE INDEX IF NOT EXISTS idx_users_last_daily_login ON users (last_daily_login)"
    ]
    
    for index_sql in indexes:
        try:
            await session.execute(text(index_sql))
        except Exception as e:
            log_error(e, {"operation": "create_user_indexes", "sql": index_sql})

async def create_subscription_indexes(session: AsyncSession):
    """Create indexes for subscriptions table"""
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_user_status ON subscriptions (user_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_status_pending ON subscriptions (status)",
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_marzban_username ON subscriptions (marzban_username)",
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_referrer ON subscriptions (referrer_id)",
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_created_at ON subscriptions (created_at)",
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_renewal_paid ON subscriptions (renewal_paid)",
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_renewal_applied ON subscriptions (renewal_applied)"
    ]
    
    for index_sql in indexes:
        try:
            await session.execute(text(index_sql))
        except Exception as e:
            log_error(e, {"operation": "create_subscription_indexes", "sql": index_sql})

async def create_reward_indexes(session: AsyncSession):
    """Create indexes for reward-related tables"""
    indexes = [
        # Referral rewards
        "CREATE INDEX IF NOT EXISTS idx_referral_rewards_referrer_spent ON referral_rewards (referrer_id, spent)",
        "CREATE INDEX IF NOT EXISTS idx_referral_rewards_subscription ON referral_rewards (subscription_id)",
        "CREATE INDEX IF NOT EXISTS idx_referral_rewards_created_at ON referral_rewards (created_at)",
        
        # User achievements
        "CREATE INDEX IF NOT EXISTS idx_user_achievements_user ON user_achievements (user_id)",
        "CREATE INDEX IF NOT EXISTS idx_user_achievements_achievement ON user_achievements (achievement_id)",
        "CREATE INDEX IF NOT EXISTS idx_user_achievements_earned_at ON user_achievements (earned_at)",
        
        # User challenges
        "CREATE INDEX IF NOT EXISTS idx_user_challenges_user ON user_challenges (user_id)",
        "CREATE INDEX IF NOT EXISTS idx_user_challenges_challenge ON user_challenges (challenge_id)",
        "CREATE INDEX IF NOT EXISTS idx_user_challenges_completed ON user_challenges (completed)",
        
        # Reward history
        "CREATE INDEX IF NOT EXISTS idx_reward_history_user ON reward_history (user_id)",
        "CREATE INDEX IF NOT EXISTS idx_reward_history_type ON reward_history (reward_type)",
        "CREATE INDEX IF NOT EXISTS idx_reward_history_source ON reward_history (source)",
        "CREATE INDEX IF NOT EXISTS idx_reward_history_earned_at ON reward_history (earned_at)"
    ]
    
    for index_sql in indexes:
        try:
            await session.execute(text(index_sql))
        except Exception as e:
            log_error(e, {"operation": "create_reward_indexes", "sql": index_sql})

async def create_analytics_indexes(session: AsyncSession):
    """Create indexes for analytics tables"""
    indexes = [
        # User analytics
        "CREATE INDEX IF NOT EXISTS idx_user_analytics_user_date ON user_analytics (user_id, date)",
        "CREATE INDEX IF NOT EXISTS idx_user_analytics_date ON user_analytics (date)",
        
        # Leaderboards
        "CREATE INDEX IF NOT EXISTS idx_leaderboards_category_period ON leaderboards (category, period)",
        "CREATE INDEX IF NOT EXISTS idx_leaderboards_user ON leaderboards (user_id)",
        "CREATE INDEX IF NOT EXISTS idx_leaderboards_score ON leaderboards (score)",
        "CREATE INDEX IF NOT EXISTS idx_leaderboards_date ON leaderboards (date)",
        
        # Reward effectiveness
        "CREATE INDEX IF NOT EXISTS idx_reward_effectiveness_type ON reward_effectiveness (reward_type)",
        "CREATE INDEX IF NOT EXISTS idx_reward_effectiveness_date ON reward_effectiveness (date)"
    ]
    
    for index_sql in indexes:
        try:
            await session.execute(text(index_sql))
        except Exception as e:
            log_error(e, {"operation": "create_analytics_indexes", "sql": index_sql})

async def create_ticket_indexes(session: AsyncSession):
    """Create indexes for tickets and ticket_messages tables"""
    indexes = [
        # Tickets table indexes
        "CREATE INDEX IF NOT EXISTS idx_tickets_user_id ON tickets (user_id)",
        "CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets (status)",
        "CREATE INDEX IF NOT EXISTS idx_tickets_created_at ON tickets (created_at)",
        "CREATE INDEX IF NOT EXISTS idx_tickets_category ON tickets (category)",
        "CREATE INDEX IF NOT EXISTS idx_tickets_assigned_admin_id ON tickets (assigned_admin_id)",
        
        # Ticket messages table indexes
        "CREATE INDEX IF NOT EXISTS idx_ticket_messages_ticket_id ON ticket_messages (ticket_id)",
        "CREATE INDEX IF NOT EXISTS idx_ticket_messages_created_at ON ticket_messages (created_at)",
    ]
    
    for index_sql in indexes:
        try:
            await session.execute(text(index_sql))
        except Exception as e:
            log_error(e, {"operation": "create_ticket_indexes", "sql": index_sql})

async def create_notification_indexes(session: AsyncSession):
    """Create indexes for notifications table"""
    indexes = [
        # Notifications table indexes
        "CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications (user_id)",
        "CREATE INDEX IF NOT EXISTS idx_notifications_created_at ON notifications (created_at)",
        "CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON notifications (user_id, read)",
    ]
    
    for index_sql in indexes:
        try:
            await session.execute(text(index_sql))
        except Exception as e:
            log_error(e, {"operation": "create_notification_indexes", "sql": index_sql}) 