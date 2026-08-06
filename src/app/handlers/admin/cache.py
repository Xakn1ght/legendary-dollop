"""
Admin commands for Redis cache management
"""

import time

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_config import cache, close_redis, get_redis_client, init_redis
from app.handlers.admin.common import ADMIN_IDS
from app.utils.bot_i18n import get_cached_lang, guess_lang_from_telegram, t
from app.utils.logger import log_database_operation, log_error

router = Router()

def _lang_for_tg_user(tg_user) -> str:
    return get_cached_lang(tg_user.id) or guess_lang_from_telegram(getattr(tg_user, "language_code", None))

@router.message(F.text == '/cache_stats')
async def cache_stats_command(message: Message):
    """Show Redis cache statistics"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    lang = _lang_for_tg_user(message.from_user)
    try:
        stats = await cache.get_stats()
        
        if not stats:
            await message.answer(t(lang, "admin_cache_unavailable"))
            return
        
        if lang == "fa":
            response = "**آمار کش Redis**\n\n"
            response += f"کلاینت‌های متصل: {stats.get('connected_clients', 0)}\n"
            response += f"مصرف حافظه: {stats.get('used_memory_human', '0B')}\n"
            response += f"تعداد دستورات: {stats.get('total_commands_processed', 0):,}\n"
            response += f"هیت کش: {stats.get('keyspace_hits', 0):,}\n"
            response += f"میس کش: {stats.get('keyspace_misses', 0):,}\n"
            response += f"زمان کارکرد: {stats.get('uptime_in_seconds', 0):,} ثانیه\n"
        else:
            response = "**Redis Cache Statistics**\n\n"
            response += f"Connected Clients: {stats.get('connected_clients', 0)}\n"
            response += f"Memory Usage: {stats.get('used_memory_human', '0B')}\n"
            response += f"Total Commands: {stats.get('total_commands_processed', 0):,}\n"
            response += f"Cache Hits: {stats.get('keyspace_hits', 0):,}\n"
            response += f"Cache Misses: {stats.get('keyspace_misses', 0):,}\n"
            response += f"Uptime: {stats.get('uptime_in_seconds', 0):,} seconds\n"
        
        # Calculate hit rate
        hits = stats.get('keyspace_hits', 0)
        misses = stats.get('keyspace_misses', 0)
        total_requests = hits + misses
        
        if total_requests > 0:
            hit_rate = (hits / total_requests) * 100
            response += (f"نرخ هیت: {hit_rate:.1f}%\n" if lang == "fa" else f"Hit Rate: {hit_rate:.1f}%\n")
        
        await message.answer(response, parse_mode='Markdown')
        
    except Exception as e:
        error_msg = (f"خطا در دریافت آمار کش: {str(e)}" if lang == "fa" else f"Failed to get cache stats: {str(e)}")
        await message.answer(error_msg)
        log_error(e, {"operation": "cache_stats_command"})

@router.message(F.text == '/cache_clear')
async def cache_clear_command(message: Message):
    """Clear all cache data"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    lang = _lang_for_tg_user(message.from_user)
    await message.answer(t(lang, "admin_cache_clearing"))
    
    start_time = time.time()
    try:
        client = await get_redis_client()
        if client is None:
            await message.answer(t(lang, "admin_cache_unavailable"))
            return
        
        # Get all keys
        keys = await client.keys("*")
        
        if not keys:
            await message.answer(t(lang, "admin_cache_empty"))
            return
        
        # Delete all keys
        deleted_count = await client.delete(*keys)
        duration = time.time() - start_time
        
        await message.answer(t(lang, "admin_cache_cleared").format(count=deleted_count, sec=duration))
        
        log_database_operation("cache_clear", "redis", True, duration, keys_deleted=deleted_count)
        
    except Exception as e:
        duration = time.time() - start_time
        error_msg = (f"خطا در پاک‌سازی کش: {str(e)}" if lang == "fa" else f"Failed to clear cache: {str(e)}")
        await message.answer(error_msg)
        
        log_database_operation("cache_clear", "redis", False, duration, error=str(e))
        log_error(e, {"operation": "cache_clear_command"})

@router.message(F.text == '/cache_keys')
async def cache_keys_command(message: Message):
    """Show cache keys by pattern"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    lang = _lang_for_tg_user(message.from_user)
    try:
        client = await get_redis_client()
        if client is None:
            await message.answer(t(lang, "admin_cache_unavailable"))
            return
        
        # Get keys by pattern
        patterns = ["user:*", "subscription:*", "reward:*", "leaderboard:*", "analytics:*"]
        
        response = ("**کلیدهای کش بر اساس الگو**\n\n" if lang == "fa" else "**Cache Keys by Pattern**\n\n")
        
        for pattern in patterns:
            keys = await client.keys(pattern)
            count = len(keys)
            response += f"{pattern}: {count} keys\n"
        
        # Get total keys
        all_keys = await client.keys("*")
        total_count = len(all_keys)
        response += (f"\n**مجموع کلیدها: {total_count}**" if lang == "fa" else f"\n**Total Keys: {total_count}**")
        
        await message.answer(response, parse_mode='Markdown')
        
    except Exception as e:
        error_msg = (f"خطا در دریافت کلیدهای کش: {str(e)}" if lang == "fa" else f"Failed to get cache keys: {str(e)}")
        await message.answer(error_msg)
        log_error(e, {"operation": "cache_keys_command"})

@router.message(F.text == '/cache_info')
async def cache_info_command(message: Message):
    """Show detailed cache information"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    lang = _lang_for_tg_user(message.from_user)
    try:
        client = await get_redis_client()
        if client is None:
            await message.answer(t(lang, "admin_cache_unavailable"))
            return
        
        info = await client.info()
        
        if lang == "fa":
            response = "**اطلاعات Redis**\n\n"
            response += f"نسخه Redis: {info.get('redis_version', 'نامشخص')}\n"
            response += f"معماری: {info.get('arch_bits', 'نامشخص')} بیت\n"
            response += f"مصرف حافظه: {info.get('used_memory_human', '0B')}\n"
            response += f"بیشترین مصرف حافظه: {info.get('used_memory_peak_human', '0B')}\n"
            response += f"کلاینت‌های متصل: {info.get('connected_clients', 0)}\n"
            response += f"کلاینت‌های بلاک‌شده: {info.get('blocked_clients', 0)}\n"
            response += f"تعداد دستورات: {info.get('total_commands_processed', 0):,}\n"
            response += f"هیت کش: {info.get('keyspace_hits', 0):,}\n"
            response += f"میس کش: {info.get('keyspace_misses', 0):,}\n"
            response += f"زمان کارکرد: {info.get('uptime_in_seconds', 0):,} ثانیه\n"
            response += f"فضای کلیدها: {info.get('db0', 'بدون داده')}\n"
        else:
            response = "**Redis Cache Information**\n\n"
            response += f"Redis Version: {info.get('redis_version', 'Unknown')}\n"
            response += f"Architecture: {info.get('arch_bits', 'Unknown')} bits\n"
            response += f"Memory Usage: {info.get('used_memory_human', '0B')}\n"
            response += f"Peak Memory: {info.get('used_memory_peak_human', '0B')}\n"
            response += f"Connected Clients: {info.get('connected_clients', 0)}\n"
            response += f"Blocked Clients: {info.get('blocked_clients', 0)}\n"
            response += f"Total Commands: {info.get('total_commands_processed', 0):,}\n"
            response += f"Cache Hits: {info.get('keyspace_hits', 0):,}\n"
            response += f"Cache Misses: {info.get('keyspace_misses', 0):,}\n"
            response += f"Uptime: {info.get('uptime_in_seconds', 0):,} seconds\n"
            response += f"Keyspace: {info.get('db0', 'No data')}\n"
        
        await message.answer(response, parse_mode='Markdown')
        
    except Exception as e:
        error_msg = (f"خطا در دریافت اطلاعات کش: {str(e)}" if lang == "fa" else f"Failed to get cache info: {str(e)}")
        await message.answer(error_msg)
        log_error(e, {"operation": "cache_info_command"})

@router.message(F.text == '/cache_test')
async def cache_test_command(message: Message):
    """Test cache functionality"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    lang = _lang_for_tg_user(message.from_user)
    await message.answer(t(lang, "admin_cache_test_start"))
    
    start_time = time.time()
    try:
        # Test basic operations
        test_key = "cache_test:admin_test"
        test_value = {"test": "data", "timestamp": time.time()}
        
        # Set value
        set_result = await cache.set(test_key, test_value, ttl=60)
        if not set_result:
            raise Exception(t(lang, "admin_cache_test_err_set"))
        
        # Get value
        get_result = await cache.get(test_key)
        if get_result != test_value:
            raise Exception(t(lang, "admin_cache_test_err_mismatch"))
        
        # Check TTL
        ttl_result = await cache.ttl(test_key)
        if ttl_result <= 0:
            raise Exception(t(lang, "admin_cache_test_err_ttl"))
        
        # Delete value
        delete_result = await cache.delete(test_key)
        if not delete_result:
            raise Exception(t(lang, "admin_cache_test_err_delete"))
        
        duration = time.time() - start_time
        
        await message.answer(t(lang, "admin_cache_test_ok").format(sec=duration, ttl=ttl_result))
        
    except Exception as e:
        duration = time.time() - start_time
        await message.answer(t(lang, "admin_cache_test_failed").format(err=str(e), sec=duration))
        log_error(e, {"operation": "cache_test_command"})

@router.message(F.text == '/cache_invalidate_user')
async def cache_invalidate_user_command(message: Message, session: AsyncSession):
    """Invalidate cache for a specific user"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    lang = _lang_for_tg_user(message.from_user)
    # Check if message has reply
    if not message.reply_to_message:
        await message.answer(t(lang, "admin_cache_invalidate_user_usage"))
        return
    
    user_id = message.reply_to_message.from_user.id
    
    await message.answer(t(lang, "admin_cache_invalidating_user").format(user_id=user_id))
    
    start_time = time.time()
    try:
        from app.database.cached_crud import invalidate_user_cache
        result = await invalidate_user_cache(user_id)
        
        duration = time.time() - start_time
        
        if result:
            await message.answer(t(lang, "admin_cache_invalidate_user_ok").format(user_id=user_id, sec=duration))
        else:
            await message.answer(t(lang, "admin_cache_invalidate_user_none").format(user_id=user_id, sec=duration))
        
    except Exception as e:
        duration = time.time() - start_time
        await message.answer(t(lang, "admin_cache_invalidate_user_failed").format(err=str(e)))
        log_error(e, {"operation": "cache_invalidate_user_command", "user_id": user_id})

@router.message(F.text == '/cache_invalidate_pattern')
async def cache_invalidate_pattern_command(message: Message):
    """Invalidate cache by pattern"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    lang = _lang_for_tg_user(message.from_user)
    # Parse pattern from message
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(t(lang, "admin_cache_invalidate_pattern_usage"))
        return
    
    pattern = args[1]
    
    await message.answer(t(lang, "admin_cache_invalidating_pattern").format(pattern=pattern))
    
    start_time = time.time()
    try:
        deleted_count = await cache.invalidate_pattern(pattern)
        duration = time.time() - start_time
        
        await message.answer(
            t(lang, "admin_cache_invalidate_pattern_ok").format(pattern=pattern, count=deleted_count, sec=duration)
        )
        
    except Exception as e:
        duration = time.time() - start_time
        await message.answer(t(lang, "admin_cache_invalidate_pattern_failed").format(err=str(e)))
        log_error(e, {"operation": "cache_invalidate_pattern_command", "pattern": pattern})

@router.message(F.text == '/cache_restart')
async def cache_restart_command(message: Message):
    """Restart Redis cache connection"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    lang = _lang_for_tg_user(message.from_user)
    await message.answer(t(lang, "admin_cache_restarting"))
    
    start_time = time.time()
    try:
        # Close existing connection
        await close_redis()
        
        # Reinitialize connection
        redis_connected = await init_redis()
        duration = time.time() - start_time
        
        if redis_connected:
            await message.answer(t(lang, "admin_cache_restart_ok").format(sec=duration))
        else:
            await message.answer(t(lang, "admin_cache_restart_failed").format(sec=duration))
        
    except Exception as e:
        duration = time.time() - start_time
        await message.answer(t(lang, "admin_cache_restart_error").format(err=str(e)))
        log_error(e, {"operation": "cache_restart_command"})

@router.message(F.text == '/cache_health')
async def cache_health_command(message: Message):
    """Check cache health and performance"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    lang = _lang_for_tg_user(message.from_user)
    try:
        stats = await cache.get_stats()
        
        if not stats:
            await message.answer(t(lang, "admin_cache_health_unavailable"), parse_mode='Markdown')
            return
        
        # Calculate health metrics
        hits = stats.get('keyspace_hits', 0)
        misses = stats.get('keyspace_misses', 0)
        total_requests = hits + misses
        
        # Health score calculation
        health_score = 100
        
        # Hit rate penalty
        if total_requests > 0:
            hit_rate = (hits / total_requests) * 100
            if hit_rate < 50:
                health_score -= 30
            elif hit_rate < 80:
                health_score -= 10
        else:
            health_score -= 20  # No requests yet
        
        # Memory usage check
        memory_str = stats.get('used_memory_human', '0B')
        if 'MB' in memory_str or 'GB' in memory_str:
            # Extract numeric value
            import re
            memory_value = float(re.findall(r'[\d.]+', memory_str)[0])
            if 'GB' in memory_str and memory_value > 1:
                health_score -= 20
            elif 'MB' in memory_str and memory_value > 500:
                health_score -= 10
        
        # Uptime check
        uptime = stats.get('uptime_in_seconds', 0)
        if uptime < 3600:  # Less than 1 hour
            health_score -= 10
        
        health_score = max(0, health_score)
        
        hit_rate = (hits / total_requests * 100) if total_requests > 0 else 0.0

        if lang == "fa":
            response = "**گزارش سلامت کش**\n\n"
            if health_score >= 90:
                response += "**وضعیت: عالی**\n"
            elif health_score >= 70:
                response += "**وضعیت: خوب**\n"
            elif health_score >= 50:
                response += "**وضعیت: متوسط**\n"
            else:
                response += "**وضعیت: ضعیف**\n"

            response += f"**امتیاز سلامت: {health_score}/100**\n\n"
            response += "**شاخص‌های عملکرد:**\n"
            response += f"• نرخ هیت: {hit_rate:.1f}% ({hits:,} هیت، {misses:,} میس)\n"
            response += f"• مصرف حافظه: {stats.get('used_memory_human', '0B')}\n"
            response += f"• کلاینت‌های متصل: {stats.get('connected_clients', 0)}\n"
            response += f"• زمان کارکرد: {uptime:,} ثانیه\n"

            response += "\n**پیشنهادها:**\n"
            if health_score < 70:
                response += "• TTL کش را بیشتر کنید\n"
                response += "• الگوهای پاک‌سازی کش را بررسی کنید\n"
                response += "• مصرف حافظه را مانیتور کنید\n"
            else:
                response += "• کش عملکرد خوبی دارد\n"
                response += "• مانیتورینگ را ادامه دهید\n"
        else:
            response = "**Cache Health Report**\n\n"
            if health_score >= 90:
                response += "**Status: Excellent**\n"
            elif health_score >= 70:
                response += "**Status: Good**\n"
            elif health_score >= 50:
                response += "**Status: Fair**\n"
            else:
                response += "**Status: Poor**\n"

            response += f"**Health Score: {health_score}/100**\n\n"
            response += "**Performance Metrics:**\n"
            response += f"• Hit Rate: {hit_rate:.1f}% ({hits:,} hits, {misses:,} misses)\n"
            response += f"• Memory Usage: {stats.get('used_memory_human', '0B')}\n"
            response += f"• Connected Clients: {stats.get('connected_clients', 0)}\n"
            response += f"• Uptime: {uptime:,} seconds\n"

            response += "\n**Recommendations:**\n"
            if health_score < 70:
                response += "• Consider increasing cache TTL\n"
                response += "• Review cache invalidation patterns\n"
                response += "• Monitor memory usage\n"
            else:
                response += "• Cache is performing well\n"
                response += "• Continue monitoring\n"

        await message.answer(response, parse_mode='Markdown')
        
    except Exception as e:
        await message.answer(t(lang, "admin_cache_health_failed").format(err=str(e)))
        log_error(e, {"operation": "cache_health_command"}) 
