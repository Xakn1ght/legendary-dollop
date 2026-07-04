from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ChargeRequest, Subscription, User
from app.handlers.admin.common import ADMIN_IDS

router = Router()

@router.message(F.text == 'آمار📊')
async def show_stats(message: Message, session: AsyncSession):
    """Send aggregated bot statistics to admin when the "آمار📊" button is pressed."""
    if message.from_user.id not in ADMIN_IDS:
        return

    # Redirect to the web dashboard
    await message.answer("📊 آمار سیستم منتقل شد به داشبورد جدید. لطفاً از دکمه '📊 داشبورد' استفاده کنید.")
    
    # Call the new dashboard function
    from app.handlers.admin.dashboard import admin_dashboard
    await admin_dashboard(message, session) 