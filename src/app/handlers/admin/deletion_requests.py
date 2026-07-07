from datetime import datetime

from aiogram import F, Router
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.database.models import PendingDeletionRequest, Subscription, User
from app.handlers.admin.common import ADMIN_IDS
from app.services.marzban import marzban_api
from app.utils.admin_bot_helper import get_user_bot
from app.utils.logger import bot_logger, log_error

router = Router()


@router.callback_query(F.data == "admin_deletion_requests")
async def show_deletion_requests(callback: CallbackQuery, session: AsyncSession):
    """Show list of pending deletion requests."""
    # Check if user is admin
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("دسترسی غیرمجاز", show_alert=True)
        return
    
    # Get pending deletion requests
    pending_requests = await session.execute(
        select(PendingDeletionRequest)
        .where(PendingDeletionRequest.status == 'pending')
        .order_by(PendingDeletionRequest.created_at.desc())
    )
    pending_requests = pending_requests.scalars().all()
    
    if not pending_requests:
        await callback.message.edit_text(
            "📋 <b>درخواست‌های حذف</b>\n\n"
            "هیچ درخواست حذفی در انتظار تایید وجود ندارد.",
            parse_mode="HTML"
        )
        return
    
    text = "📋 <b>درخواست‌های حذف در انتظار تایید</b>\n\n"
    kb = InlineKeyboardBuilder()
    
    for req in pending_requests:
        # Get user info
        user_info = await session.get(User, req.user_id)
        if not user_info:
            continue
            
        text += (
            f"🆔 <b>درخواست #{req.id}</b>\n"
            f"👤 کاربر: {user_info.full_name} (@{user_info.username or 'بدون یوزرنیم'})\n"
            f"📱 سرویس: {req.subscription_username}\n"
            f"📅 تاریخ: {req.created_at.strftime('%Y-%m-%d %H:%M')}\n"
            f"📝 دلیل: {req.reason or 'درخواست کاربر'}\n\n"
        )
        
        kb.button(
            text=f"✅ تایید #{req.id}",
            callback_data=f"approve_deletion_{req.id}"
        )
        kb.button(
            text=f"❌ رد #{req.id}",
            callback_data=f"deny_deletion_{req.id}"
        )
    
    kb.button(text="🔙 بازگشت", callback_data="admin_main")
    kb.adjust(2, 1)
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("approve_deletion_"))
async def approve_deletion_request(callback: CallbackQuery, session: AsyncSession):
    """Approve a deletion request."""
    # Check if user is admin
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("دسترسی غیرمجاز", show_alert=True)
        return
    
    req_id = int(callback.data.split("_")[2])
    
    # Get the deletion request
    deletion_request = await session.get(PendingDeletionRequest, req_id)
    if not deletion_request or deletion_request.status != 'pending':
        await callback.answer("درخواست یافت نشد یا قبلاً پردازش شده", show_alert=True)
        return
    
    # Get subscription
    subscription = await session.get(Subscription, deletion_request.subscription_id)
    if not subscription:
        await callback.answer("سرویس یافت نشد", show_alert=True)
        return
    
    try:
        # Delete from Marzban
        success = await marzban_api.delete_user(subscription.marzban_username)
        if not success:
            await callback.answer("خطا در حذف سرویس از پنل", show_alert=True)
            return
        
        # Update deletion request status
        deletion_request.status = 'approved'
        deletion_request.processed_at = datetime.utcnow()
        # processed_by is FK → users.id (int32): resolve the admin's DB row —
        # a raw Telegram id overflows AND violates the FK
        admin_row = await crud.get_user(session, callback.from_user.id)
        deletion_request.processed_by = admin_row.id if admin_row else None
        
        # Delete subscription from local database
        await session.delete(subscription)
        await session.commit()
        
        # Notify the user
        user_info = await session.get(User, deletion_request.user_id)
        if user_info and user_info.chat_id:
            try:
                await (get_user_bot() or callback.bot).send_message(
                    user_info.chat_id,
                    f"✅ درخواست حذف سرویس {subscription.marzban_username} تایید و حذف شد."
                )
            except Exception as e:
                log_error(e, {"operation": "notify_user_deletion_approved", "user_id": user_info.id})
        
        await callback.answer("درخواست حذف تایید و سرویس حذف شد ✅")
        
        # Refresh the deletion requests list
        await show_deletion_requests(callback, session)
        
    except Exception as e:
        log_error(e, {"operation": "approve_deletion_request", "request_id": req_id})
        await callback.answer("خطا در پردازش درخواست", show_alert=True)


@router.callback_query(F.data.startswith("deny_deletion_"))
async def deny_deletion_request(callback: CallbackQuery, session: AsyncSession):
    """Deny a deletion request."""
    # Check if user is admin
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("دسترسی غیرمجاز", show_alert=True)
        return
    
    req_id = int(callback.data.split("_")[2])
    
    # Get the deletion request
    deletion_request = await session.get(PendingDeletionRequest, req_id)
    if not deletion_request or deletion_request.status != 'pending':
        await callback.answer("درخواست یافت نشد یا قبلاً پردازش شده", show_alert=True)
        return
    
    try:
        # Update deletion request status
        deletion_request.status = 'denied'
        deletion_request.processed_at = datetime.utcnow()
        admin_row = await crud.get_user(session, callback.from_user.id)
        deletion_request.processed_by = admin_row.id if admin_row else None
        await session.commit()
        
        # Notify the user
        user_info = await session.get(User, deletion_request.user_id)
        if user_info and user_info.chat_id:
            try:
                await (get_user_bot() or callback.bot).send_message(
                    user_info.chat_id,
                    f"❌ درخواست حذف سرویس {deletion_request.subscription_username} رد شد."
                )
            except Exception as e:
                log_error(e, {"operation": "notify_user_deletion_denied", "user_id": user_info.id})
        
        await callback.answer("درخواست حذف رد شد ❌")
        
        # Refresh the deletion requests list
        await show_deletion_requests(callback, session)
        
    except Exception as e:
        log_error(e, {"operation": "deny_deletion_request", "request_id": req_id})
        await callback.answer("خطا در پردازش درخواست", show_alert=True) 