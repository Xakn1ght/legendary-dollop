"""
Admin commands for managing database indexes
"""

import time

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.indexes import analyze_table_performance, create_all_indexes, get_index_usage_stats
from app.handlers.admin.common import ADMIN_IDS
from app.utils.bot_i18n import get_cached_lang, guess_lang_from_telegram, t
from app.utils.logger import log_database_operation, log_error

router = Router()

def _lang_for_tg_user(tg_user) -> str:
    return get_cached_lang(tg_user.id) or guess_lang_from_telegram(getattr(tg_user, "language_code", None))

@router.message(F.text == '/create_indexes')
async def create_indexes_command(message: Message, session: AsyncSession):
    """Create all critical database indexes"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    lang = _lang_for_tg_user(message.from_user)
    await message.answer(t(lang, "admin_db_indexes_creating"))
    
    start_time = time.time()
    try:
        await create_all_indexes(session)
        duration = time.time() - start_time
        
        await message.answer(t(lang, "admin_db_indexes_created").format(sec=duration))
        
        log_database_operation("create_indexes", "all_tables", True, duration)
        
    except Exception as e:
        duration = time.time() - start_time
        await message.answer(t(lang, "admin_db_failed_create_indexes").format(err=str(e)))
        
        log_database_operation("create_indexes", "all_tables", False, duration, error=str(e))
        log_error(e, {"operation": "create_indexes_command"})

@router.message(F.text == '/analyze_indexes')
async def analyze_indexes_command(message: Message, session: AsyncSession):
    """Analyze database performance and suggest indexes"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    lang = _lang_for_tg_user(message.from_user)
    await message.answer(t(lang, "admin_db_analyzing"))
    
    try:
        # Skip Postgres-only queries on SQLite
        dialect_name = session.bind.dialect.name if session.bind else "unknown"
        if dialect_name != 'postgresql':
            await message.answer(t(lang, "admin_db_postgres_only_analysis"))
            return
        # Get performance suggestions
        suggestions = await analyze_table_performance(session)
        
        # Get index usage stats
        usage_stats = await get_index_usage_stats(session)
        
        # Build response message
        response = t(lang, "admin_db_analysis_title") + "\n\n"
        
        if suggestions:
            response += t(lang, "admin_db_suggested_indexes") + "\n"
            for i, suggestion in enumerate(suggestions[:10], 1):  # Limit to top 10
                response += f"{i}. {suggestion}\n"
            if len(suggestions) > 10:
                response += t(lang, "admin_db_more_suggestions").format(count=len(suggestions) - 10) + "\n"
        else:
            response += t(lang, "admin_db_no_suggestions") + "\n"
        
        response += "\n" + t(lang, "admin_db_index_usage_stats_heading") + "\n"
        if usage_stats:
            for stat in usage_stats[:5]:  # Top 5 most used indexes
                table_name = stat[1]
                index_name = stat[2]
                scans = stat[3]
                response += t(lang, "admin_db_usage_line").format(table=table_name, index=index_name, scans=f"{scans:,}") + "\n"
        else:
            response += t(lang, "admin_db_no_index_usage") + "\n"
        
        await message.answer(response, parse_mode='Markdown')
        
    except Exception as e:
        await message.answer(t(lang, "admin_db_failed_analyze_indexes").format(err=str(e)))
        log_error(e, {"operation": "analyze_indexes_command"})

@router.message(F.text == '/index_stats')
async def index_stats_command(message: Message, session: AsyncSession):
    """Show detailed index usage statistics"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    lang = _lang_for_tg_user(message.from_user)
    try:
        dialect_name = session.bind.dialect.name if session.bind else "unknown"
        if dialect_name != 'postgresql':
            await message.answer(t(lang, "admin_db_postgres_only_index_stats"))
            return
        # Get index usage stats
        usage_stats = await get_index_usage_stats(session)
        
        if not usage_stats:
            await message.answer(t(lang, "admin_db_no_index_usage"))
            return
        
        # Build detailed response
        response = t(lang, "admin_db_index_stats_title") + "\n\n"
        
        total_scans = 0
        for stat in usage_stats:
            table_name = stat[1]
            index_name = stat[2]
            scans = stat[3]
            tuples_read = stat[4]
            tuples_fetched = stat[5]
            total_scans += scans
            
            response += f"**{table_name}.{index_name}**\n"
            response += f"• {t(lang, 'admin_db_label_scans')}: {scans:,}\n"
            response += f"• {t(lang, 'admin_db_label_tuples_read')}: {tuples_read:,}\n"
            response += f"• {t(lang, 'admin_db_label_tuples_fetched')}: {tuples_fetched:,}\n"
            efficiency = (tuples_fetched / tuples_read * 100) if tuples_read else None
            efficiency_str = (f"{efficiency:.1f}%" if efficiency is not None else t(lang, "admin_db_na"))
            response += f"• {t(lang, 'admin_db_label_efficiency')}: {efficiency_str}\n\n"
        
        response += t(lang, "admin_db_index_stats_total_scans").format(total=f"{total_scans:,}")
        
        # Split long messages
        if len(response) > 4096:
            parts = [response[i:i+4096] for i in range(0, len(response), 4096)]
            for i, part in enumerate(parts):
                await message.answer(
                    f"{part}\n\n" + t(lang, "admin_db_part").format(i=i + 1, n=len(parts)),
                    parse_mode='Markdown',
                )
        else:
            await message.answer(response, parse_mode='Markdown')
        
    except Exception as e:
        await message.answer(t(lang, "admin_db_failed_index_stats").format(err=str(e)))
        log_error(e, {"operation": "index_stats_command"})

@router.message(F.text == '/vacuum_analyze')
async def vacuum_analyze_command(message: Message, session: AsyncSession):
    """Run VACUUM ANALYZE to update table statistics"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    lang = _lang_for_tg_user(message.from_user)
    await message.answer(t(lang, "admin_db_vacuum_running"))
    
    start_time = time.time()
    try:
        dialect_name = session.bind.dialect.name if session.bind else "unknown"
        if dialect_name != 'postgresql':
            await message.answer(t(lang, "admin_db_postgres_only_vacuum"))
            return
        # Run VACUUM ANALYZE on all tables
        await session.execute(text("VACUUM ANALYZE"))
        await session.commit()
        
        duration = time.time() - start_time
        
        await message.answer(t(lang, "admin_db_vacuum_done").format(sec=duration))
        
        log_database_operation("vacuum_analyze", "all_tables", True, duration)
        
    except Exception as e:
        duration = time.time() - start_time
        await message.answer(t(lang, "admin_db_failed_vacuum").format(err=str(e)))
        
        log_database_operation("vacuum_analyze", "all_tables", False, duration, error=str(e))
        log_error(e, {"operation": "vacuum_analyze_command"})

@router.message(F.text == '/slow_queries')
async def slow_queries_command(message: Message, session: AsyncSession):
    """Show slow queries from PostgreSQL statistics"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    lang = _lang_for_tg_user(message.from_user)
    try:
        dialect_name = session.bind.dialect.name if session.bind else "unknown"
        if dialect_name != 'postgresql':
            await message.answer(t(lang, "admin_db_postgres_only_slow"))
            return
        # Get slow queries from pg_stat_statements
        result = await session.execute(text("""
            SELECT 
                query,
                calls,
                total_time,
                mean_time,
                rows
            FROM pg_stat_statements 
            ORDER BY mean_time DESC 
            LIMIT 10
        """))
        
        slow_queries = result.fetchall()
        
        if not slow_queries:
            await message.answer(t(lang, "admin_db_no_slow_queries"))
            return
        
        response = t(lang, "admin_db_slow_title") + "\n\n"
        
        for i, query in enumerate(slow_queries, 1):
            query_text = query[0][:100] + "..." if len(query[0]) > 100 else query[0]
            calls = query[1]
            total_time = query[2]
            mean_time = query[3]
            rows = query[4]
            
            response += t(lang, "admin_db_slow_query_heading").format(i=i) + "\n"
            response += f"• {t(lang, 'admin_db_label_calls')}: {calls:,}\n"
            response += f"• {t(lang, 'admin_db_label_total_time')}: {total_time:.2f}ms\n"
            response += f"• {t(lang, 'admin_db_label_avg_time')}: {mean_time:.2f}ms\n"
            response += f"• {t(lang, 'admin_db_label_rows')}: {rows:,}\n"
            response += f"• {t(lang, 'admin_db_label_query')}: `{query_text}`\n\n"
        
        await message.answer(response, parse_mode='Markdown')
        
    except Exception as e:
        await message.answer(t(lang, "admin_db_failed_slow_queries").format(err=str(e)))
        log_error(e, {"operation": "slow_queries_command"})

@router.message(F.text == '/table_sizes')
async def table_sizes_command(message: Message, session: AsyncSession):
    """Show table sizes and row counts"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    lang = _lang_for_tg_user(message.from_user)
    try:
        dialect_name = session.bind.dialect.name if session.bind else "unknown"
        if dialect_name != 'postgresql':
            await message.answer(t(lang, "admin_db_postgres_only_table_stats"))
            return
        # Get table sizes and row counts
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
        
        if not stats:
            await message.answer(t(lang, "admin_db_no_table_stats"))
            return
        
        # Group by table
        table_stats = {}
        for stat in stats:
            table_name = stat[1]
            column_name = stat[2]
            n_distinct = stat[3]
            correlation = stat[4]
            
            if table_name not in table_stats:
                table_stats[table_name] = []
            
            table_stats[table_name].append({
                'column': column_name,
                'distinct': n_distinct,
                'correlation': correlation
            })
        
        response = t(lang, "admin_db_table_stats_title") + "\n\n"
        
        for table_name, columns in table_stats.items():
            response += f"**{table_name}**\n"
            for col in columns[:3]:  # Top 3 columns per table
                response += t(lang, "admin_db_table_stats_distinct_line").format(col=col["column"], val=col["distinct"]) + "\n"
            response += "\n"
        
        await message.answer(response, parse_mode='Markdown')
        
    except Exception as e:
        await message.answer(t(lang, "admin_db_failed_table_stats").format(err=str(e)))
        log_error(e, {"operation": "table_sizes_command"})

@router.message(F.text == '/db_health')
async def db_health_command(message: Message, session: AsyncSession):
    """Show overall database health metrics"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    lang = _lang_for_tg_user(message.from_user)
    try:
        dialect_name = session.bind.dialect.name if session.bind else "unknown"
        if dialect_name != 'postgresql':
            await message.answer(t(lang, "admin_db_postgres_only_health"))
            return
        
        # Table counts
        result = await session.execute(text("""
            SELECT 
                schemaname,
                tablename,
                n_tup_ins,
                n_tup_upd,
                n_tup_del,
                n_live_tup,
                n_dead_tup
            FROM pg_stat_user_tables
            ORDER BY n_live_tup DESC
        """))
        
        table_stats = result.fetchall()
        
        # Index usage
        result = await session.execute(text("""
            SELECT 
                COUNT(*) as total_indexes,
                SUM(idx_scan) as total_scans,
                AVG(idx_scan) as avg_scans
            FROM pg_stat_user_indexes
        """))
        
        index_stats = result.fetchone()
        
        # Build health report
        response = t(lang, "admin_db_health_title") + "\n\n"
        
        response += t(lang, "admin_db_health_table_stats_heading") + "\n"
        total_rows = 0
        for stat in table_stats[:5]:  # Top 5 tables
            table_name = stat[1]
            live_tuples = stat[5]
            dead_tuples = stat[6]
            total_rows += live_tuples
            
            response += t(lang, "admin_db_health_rows_line").format(table=table_name, rows=f"{live_tuples:,}")
            if dead_tuples > 0:
                response += t(lang, "admin_db_health_dead_suffix").format(dead=f"{dead_tuples:,}")
            response += "\n"
        
        response += "\n" + t(lang, "admin_db_health_total_rows").format(total=f"{total_rows:,}") + "\n"
        
        if index_stats:
            response += t(lang, "admin_db_health_index_usage_heading") + "\n"
            response += f"• {t(lang, 'admin_db_health_total_indexes')}: {index_stats[0]:,}\n"
            response += f"• {t(lang, 'admin_db_health_total_scans')}: {index_stats[1]:,}\n"
            response += f"• {t(lang, 'admin_db_health_avg_scans')}: {index_stats[2]:.1f}\n"
        
        # Health score
        health_score = 100
        if index_stats and index_stats[1] > 0:
            health_score = min(100, (index_stats[1] / 1000) * 100)  # Normalize to 100
        
        response += "\n" + t(lang, "admin_db_health_score").format(score=f"{health_score:.0f}") + "\n"
        
        if health_score >= 80:
            response += t(lang, "admin_db_health_status_ok")
        elif health_score >= 60:
            response += t(lang, "admin_db_health_status_attention")
        else:
            response += t(lang, "admin_db_health_status_bad")
        
        await message.answer(response, parse_mode='Markdown')
        
    except Exception as e:
        await message.answer(t(lang, "admin_db_failed_db_health").format(err=str(e)))
        log_error(e, {"operation": "db_health_command"}) 
