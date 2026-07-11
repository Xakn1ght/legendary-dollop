from app.utils.admin_bot_helper import resolve_user_bot

from ..common import *  # noqa: F403


async def handle_admin_subscription_delete(request: web.Request):
    """Delete a user from PasarGuard"""
    username = request.match_info.get('username', '').strip()
    if not username or len(username) > 100:
        return web.json_response({"ok": False, "error": "invalid_username"}, status=400)
    
    try:
        # First find the user to notify before deleting
        user_to_notify = None
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Subscription).where(Subscription.marzban_username == username)
            )
            sub = result.scalar_one_or_none()
            if sub and sub.user_id:
                user_to_notify = await session.get(User, sub.user_id)
        
        success = await pasarguard_api.delete_user(username)
        if success:
            # Send notification to user
            if user_to_notify:
                async with AsyncSessionLocal() as session:
                    await notifications_crud.create_notification(
                        db=session,
                        user_id=user_to_notify.id,
                        type='subscription_deleted',
                        title='اشتراک حذف شد',
                        message=f'اشتراک {username} توسط ادمین حذف شد.',
                        sent_to_webapp=True,
                        sent_to_bot=True
                    )
                    await session.commit()
                
                bot = resolve_user_bot(request.app.get('bot'))
                if bot and user_to_notify.chat_id:
                    try:
                        tg_msg = f"❌ *اشتراک حذف شد*\n\nسرویس `{username}` توسط مدیریت حذف شد.\nبرای اطلاعات بیشتر با پشتیبانی تماس بگیرید."
                        await bot.send_message(chat_id=user_to_notify.chat_id, text=tg_msg, parse_mode='Markdown')
                    except Exception:
                        pass
            
            from app.services.audit import record_audit

            await record_audit(
                request, "subscription.delete", target_type="subscription", target_id=username,
                summary=f"deleted panel user {username}",
            )
            return web.json_response({"ok": True, "message": "deleted"})
        else:
            return web.json_response({"ok": False, "error": "delete_failed"}, status=500)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)
