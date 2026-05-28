from app.utils.admin_bot_helper import resolve_user_bot

from ..common import *  # noqa: F403


async def handle_admin_vip_users(request: web.Request):
    """Get all VIP users"""
    try:
        async with AsyncSessionLocal() as session:
            # Get all VIP users
            result = await session.execute(
                select(User).where(User.is_vip == True).order_by(desc(User.vip_until))
            )
            vip_users = result.scalars().all()
            
            users_data = []
            for user in vip_users:
                users_data.append({
                    "id": user.id,
                    "chat_id": user.chat_id,
                    "username": user.username,
                    "full_name": user.full_name,
                    "is_vip": user.is_vip,
                    "vip_until": user.vip_until.isoformat() if user.vip_until else None,
                    "credit": user.credit,
                    "stars": user.stars,
                    "level": user.level,
                    "created_at": user.created_at.isoformat() if user.created_at else None
                })
            
            # Get VIP stats
            total_vip = len(users_data)
            lifetime_vip = sum(1 for u in users_data if u["vip_until"] is None)
            expiring_soon = sum(1 for u in users_data if u["vip_until"] and datetime.fromisoformat(u["vip_until"]) < datetime.utcnow().replace(hour=0, minute=0, second=0) + __import__('datetime').timedelta(days=7))
            
            return web.json_response({
                "ok": True,
                "users": users_data,
                "stats": {
                    "total_vip": total_vip,
                    "lifetime_vip": lifetime_vip,
                    "expiring_soon": expiring_soon
                }
            })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_admin_set_vip(request: web.Request):
    """Set or update VIP status for a user"""
    try:
        user_id = int(request.match_info['user_id'])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_user_id"}, status=400)
    
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)
    
    # Get VIP duration (days) - None or 0 means lifetime
    days = data.get('days')
    if days is not None:
        try:
            days = int(days)
            if days < 0:
                return web.json_response({"ok": False, "error": "invalid_days"}, status=400)
        except (ValueError, TypeError):
            return web.json_response({"ok": False, "error": "invalid_days"}, status=400)
    
    try:
        async with AsyncSessionLocal() as session:
            user = await session.get(User, user_id)
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)
            
            was_vip = user.is_vip
            old_expiry = user.vip_until
            user.is_vip = True
            
            from datetime import timedelta
            if days and days > 0:
                # If user already has VIP with future expiry, extend from that date
                # Otherwise start from now
                if old_expiry and old_expiry > datetime.utcnow():
                    user.vip_until = old_expiry + timedelta(days=days)
                    duration_text = f"+{days} روز (تا {user.vip_until.strftime('%Y-%m-%d')})"
                else:
                    user.vip_until = datetime.utcnow() + timedelta(days=days)
                    duration_text = f"{days} روز"
            else:
                # Lifetime VIP
                user.vip_until = None
                duration_text = "دائمی"
            
            # Create notification for user dashboard
            notif_title = "⭐ تبریک! شما VIP شدید" if not was_vip else "⭐ اشتراک VIP تمدید شد"
            notif_message = f"اشتراک VIP شما فعال شد ({duration_text}). از مزایای ویژه لذت ببرید!"
            
            await notifications_crud.create_notification(
                db=session,
                user_id=user.id,
                type='vip_granted',
                title=notif_title,
                message=notif_message,
                sent_to_webapp=True,
                sent_to_bot=True
            )
            
            await session.commit()
            
            # Send Telegram notification
            bot = resolve_user_bot(request.app.get('bot'))
            if bot and user.chat_id:
                try:
                    vip_msg = (
                        f"🌟 *تبریک! شما VIP شدید* 🌟\n\n"
                        f"✨ اشتراک VIP شما با موفقیت فعال شد.\n"
                        f"⏱ مدت: {duration_text}\n\n"
                        f"🎁 از مزایای ویژه VIP لذت ببرید!"
                    )
                    await bot.send_message(
                        chat_id=user.chat_id,
                        text=vip_msg,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    print(f"[VIP] Failed to send VIP notification to {user.chat_id}: {e}")
            
            return web.json_response({
                "ok": True,
                "message": "VIP status updated",
                "user": {
                    "id": user.id,
                    "chat_id": user.chat_id,
                    "username": user.username,
                    "full_name": user.full_name,
                    "is_vip": user.is_vip,
                    "vip_until": user.vip_until.isoformat() if user.vip_until else None
                }
            })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_admin_remove_vip(request: web.Request):
    """Remove VIP status from a user"""
    try:
        user_id = int(request.match_info['user_id'])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_user_id"}, status=400)
    
    try:
        async with AsyncSessionLocal() as session:
            user = await session.get(User, user_id)
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)
            
            was_vip = user.is_vip
            user.is_vip = False
            user.vip_until = None
            
            # Only notify if user was actually VIP
            if was_vip:
                # Create notification for user dashboard
                await notifications_crud.create_notification(
                    db=session,
                    user_id=user.id,
                    type='vip_removed',
                    title='اشتراک VIP پایان یافت',
                    message='اشتراک VIP شما به پایان رسید. برای تمدید با پشتیبانی تماس بگیرید.',
                    sent_to_webapp=True,
                    sent_to_bot=True
                )
            
            await session.commit()
            
            # Send Telegram notification if was VIP
            if was_vip:
                bot = resolve_user_bot(request.app.get('bot'))
                if bot and user.chat_id:
                    try:
                        vip_msg = (
                            "📢 *اشتراک VIP پایان یافت*\n\n"
                            "اشتراک VIP شما به پایان رسیده است.\n"
                            "برای تمدید با پشتیبانی تماس بگیرید."
                        )
                        await bot.send_message(
                            chat_id=user.chat_id,
                            text=vip_msg,
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        print(f"[VIP] Failed to send VIP removal notification to {user.chat_id}: {e}")
            
            return web.json_response({
                "ok": True,
                "message": "VIP status removed"
            })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_admin_search_user_for_vip(request: web.Request):
    """Search users to add as VIP"""
    search = request.query.get('q', '').strip()
    if not search or len(search) < 2:
        return web.json_response({"ok": True, "users": []})
    
    try:
        async with AsyncSessionLocal() as session:
            # Search by username, full_name, or chat_id
            query = select(User).where(
                (User.username.ilike(f"%{search}%")) |
                (User.full_name.ilike(f"%{search}%")) |
                (User.chat_id == int(search) if search.isdigit() else False)
            ).limit(20)
            
            result = await session.execute(query)
            users = result.scalars().all()
            
            users_data = [{
                "id": u.id,
                "chat_id": u.chat_id,
                "username": u.username,
                "full_name": u.full_name,
                "is_vip": u.is_vip,
                "vip_until": u.vip_until.isoformat() if u.vip_until else None
            } for u in users]
            
            return web.json_response({"ok": True, "users": users_data})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)
