from app.utils.admin_bot_helper import resolve_user_bot

from ..common import *  # noqa: F403


async def handle_admin_user_update(request: web.Request):
    try:
        user_id = int(request.match_info['user_id'])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_user_id"}, status=400)
    
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)
    
    # Validate input using Pydantic schema
    validated, error = validate_request(AdminUserUpdateRequest, data)
    if error:
        return web.json_response(error, status=400)
    
    try:
        async with AsyncSessionLocal() as session:
            user = await session.get(User, user_id)
            if not user:
                return web.json_response({"ok": False, "error": "not_found"}, status=404)
            
            old_credit = user.credit
            old_banned = user.banned
            
            if validated.credit is not None:
                user.credit = validated.credit
            if validated.stars is not None:
                user.stars = validated.stars
            if validated.banned is not None:
                user.banned = validated.banned
            
            # Send notifications for significant changes
            bot = resolve_user_bot(request.app.get('bot'))
            
            # Credit change notification
            if validated.credit is not None and validated.credit != old_credit:
                credit_diff = validated.credit - old_credit
                if credit_diff > 0:
                    notif_title = "💰 اعتبار اضافه شد"
                    notif_message = f"{credit_diff:,} تومان به حساب شما اضافه شد. موجودی جدید: {validated.credit:,} تومان"
                    tg_msg = f"💰 *اعتبار اضافه شد*\n\n+{credit_diff:,} تومان\nموجودی جدید: {validated.credit:,} تومان"
                else:
                    notif_title = "💸 کسر اعتبار"
                    notif_message = f"{abs(credit_diff):,} تومان از حساب شما کسر شد. موجودی جدید: {validated.credit:,} تومان"
                    tg_msg = f"💸 *کسر اعتبار*\n\n-{abs(credit_diff):,} تومان\nموجودی جدید: {validated.credit:,} تومان"
                
                await notifications_crud.create_notification(
                    db=session,
                    user_id=user.id,
                    type='credit_change',
                    title=notif_title,
                    message=notif_message,
                    sent_to_webapp=True,
                    sent_to_bot=True
                )
                
                if bot and user.chat_id:
                    try:
                        await bot.send_message(chat_id=user.chat_id, text=tg_msg, parse_mode='Markdown')
                    except Exception:
                        pass
            
            # Ban/unban notification
            if validated.banned is not None and validated.banned != old_banned:
                if validated.banned:
                    notif_title = "حساب مسدود شد"
                    notif_message = "حساب کاربری شما مسدود شده است. برای اطلاعات بیشتر با پشتیبانی تماس بگیرید."
                    tg_msg = "*حساب مسدود شد*\n\nحساب کاربری شما مسدود شده است.\nبرای اطلاعات بیشتر با پشتیبانی تماس بگیرید."
                else:
                    notif_title = "رفع مسدودیت"
                    notif_message = "حساب کاربری شما فعال شد. می‌توانید از خدمات استفاده کنید."
                    tg_msg = "*رفع مسدودیت*\n\nحساب کاربری شما فعال شد.\nمی‌توانید از خدمات استفاده کنید."
                
                await notifications_crud.create_notification(
                    db=session,
                    user_id=user.id,
                    type='account_status',
                    title=notif_title,
                    message=notif_message,
                    sent_to_webapp=True,
                    sent_to_bot=True
                )
                
                if bot and user.chat_id:
                    try:
                        await bot.send_message(chat_id=user.chat_id, text=tg_msg, parse_mode='Markdown')
                    except Exception:
                        pass
            
            await session.commit()

            from app.services.audit import record_audit

            bits = []
            if validated.credit is not None and validated.credit != old_credit:
                bits.append(f"credit {old_credit:,}→{validated.credit:,}")
            if validated.banned is not None and validated.banned != old_banned:
                bits.append("BANNED" if validated.banned else "unbanned")
            if validated.stars is not None:
                bits.append(f"stars={validated.stars}")
            if bits:
                await record_audit(
                    request, "user.update", target_type="user", target_id=user_id,
                    summary=", ".join(bits),
                )
            return web.json_response({"ok": True})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)
