from ..common import *  # noqa: F403


async def handle_admin_subscriptions(request: web.Request):
    """Get subscriptions with real-time PasarGuard data"""
    try:
        page = int(request.query.get('page', 1))
        limit = int(request.query.get('limit', 100))
        search = request.query.get('search', '').strip()
        sort_by = request.query.get('sort', 'created')  # created, expire, used, username
        sort_order = request.query.get('order', 'desc')  # asc, desc
        
        # Fetch ALL users from PasarGuard (paged walk — no silent truncation at 2000)
        offset = (page - 1) * limit
        pasarguard_users = await pasarguard_api.get_all_users_paged(search=search if search else None)
        total_count = len(pasarguard_users)
        
        # Transform PasarGuard user data
        subs_data = []
        for u in pasarguard_users:
            username = u.get('username', '')
            status = u.get('status', 'unknown')
            
            # Traffic data (bytes to GB)
            used_traffic = u.get('used_traffic', 0) or 0
            data_limit = u.get('data_limit', 0) or 0
            used_gb = used_traffic / (1024**3) if used_traffic else 0
            limit_gb = data_limit / (1024**3) if data_limit else 0
            
            # Expiry timestamp
            expire_ts = u.get('expire')
            expire_date = None
            days_left = None
            if expire_ts:
                from datetime import datetime, timezone
                expire_dt = datetime.fromtimestamp(expire_ts, tz=timezone.utc)
                expire_date = expire_dt.isoformat()
                days_left = (expire_dt - datetime.now(timezone.utc)).days
            
            # Created timestamp
            created_ts = u.get('created_at')
            created_date = None
            if created_ts:
                try:
                    # PasarGuard returns ISO format string
                    created_date = created_ts if isinstance(created_ts, str) else datetime.fromtimestamp(created_ts, tz=timezone.utc).isoformat()
                except:
                    created_date = None
            
            # Online status
            online_at = u.get('online_at')
            is_online = False
            last_online = None
            if online_at:
                try:
                    from datetime import datetime, timedelta, timezone
                    if isinstance(online_at, str):
                        online_dt = datetime.fromisoformat(online_at.replace('Z', '+00:00'))
                    else:
                        online_dt = datetime.fromtimestamp(online_at, tz=timezone.utc)
                    is_online = (datetime.now(timezone.utc) - online_dt) < timedelta(minutes=2)
                    last_online = online_at if isinstance(online_at, str) else online_dt.isoformat()
                except:
                    pass
            
            subs_data.append({
                "id": u.get('id', 0),
                "username": username,
                "status": status,
                "used_traffic_gb": round(used_gb, 2),
                "data_limit_gb": round(limit_gb, 2) if limit_gb > 0 else None,
                "expire": expire_ts,
                "expire_date": expire_date,
                "days_left": days_left,
                "created_at": created_date,
                "is_online": is_online,
                "last_online": last_online,
                "note": u.get('note', ''),
                "data_limit_reset_strategy": u.get('data_limit_reset_strategy', ''),
                "inbounds": u.get('inbounds', {}),
                # PasarGuard device cap (0/None = unlimited) — editable from the panel UI
                "hwid_limit": u.get('hwid_limit'),
            })
        
        # Sort the data
        def sort_key(item):
            if sort_by == 'expire':
                val = item.get('expire') or (999999999999 if sort_order == 'asc' else 0)
                return val
            elif sort_by == 'used':
                return item.get('used_traffic_gb', 0)
            elif sort_by == 'username':
                return (item.get('username') or '').lower()
            else:  # created - parse ISO date to timestamp
                created = item.get('created_at')
                if not created:
                    return 0
                try:
                    from datetime import datetime
                    if isinstance(created, str):
                        # Parse ISO format
                        dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                        return dt.timestamp()
                    return float(created) if created else 0
                except:
                    return 0
        
        reverse = sort_order == 'desc'
        subs_data.sort(key=sort_key, reverse=reverse)
        
        # Apply pagination after sorting
        paginated = subs_data[offset:offset + limit]
        
        return web.json_response({
            "ok": True,
            "users": paginated,
            "subscriptions": paginated,  # Alias for compatibility
            "total": total_count,
            "page": page,
            "limit": limit
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error", "detail": str(e)}, status=500)
