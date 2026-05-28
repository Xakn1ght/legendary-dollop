from ..common import *  # noqa: F403


async def handle_admin_stats(request: web.Request):
    try:
        async with AsyncSessionLocal() as session:
            total_users = await session.scalar(select(func.count(User.id)))
            total_subs = await session.scalar(select(func.count(Subscription.id)))
            active_subs = await session.scalar(select(func.count(Subscription.id)).where(Subscription.status == 'active'))
            
            pending_tickets = await session.scalar(select(func.count(Ticket.id)).where(Ticket.status == 'pending'))
            
            return web.json_response({
                "ok": True,
                "stats": {
                    "total_users": total_users,
                    "total_subscriptions": total_subs,
                    "active_subscriptions": active_subs,
                    "pending_tickets": pending_tickets
                }
            })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)
