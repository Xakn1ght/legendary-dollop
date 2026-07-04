"""Periodic sweep so a bank SMS that arrived before its receipt still matches.

Inert unless SMS auto-approval is armed (``sms_ingest.sms_enabled()``). Cheap:
returns immediately when disabled or when there are no unmatched deposits.
"""
from app.services import sms_ingest
from app.utils.logger import bot_logger


async def sms_sweep_job(bot=None):
    try:
        await sms_ingest.sweep_pooled(bot)
    except Exception as e:
        bot_logger.warning(f"[SMS] sweep job error: {e}")
