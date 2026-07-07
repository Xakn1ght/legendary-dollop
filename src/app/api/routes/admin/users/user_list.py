from sqlalchemy import String, cast

from ..common import *  # noqa: F403


async def handle_admin_users(request: web.Request):
    try:
        # Validate pagination parameters
        params_data = {
            'page': request.query.get('page', '1'),
            'limit': request.query.get('limit', '20'),
            'search': request.query.get('search', '')
        }
        try:
            params_data['page'] = int(params_data['page'])
            params_data['limit'] = int(params_data['limit'])
        except ValueError:
            return web.json_response({"ok": False, "error": "invalid_pagination_params"}, status=400)
        
        validated, error = validate_request(PaginationParams, params_data)
        if error:
            return web.json_response(error, status=400)
        
        page = validated.page
        limit = validated.limit
        search = validated.search or ''
        
        offset = (page - 1) * limit
        
        async with AsyncSessionLocal() as session:
            stmt = select(User)
            if search:
                stmt = stmt.where(
                    (User.username.ilike(f"%{search}%")) |
                    (User.full_name.ilike(f"%{search}%")) |
                    (cast(User.chat_id, String).ilike(f"%{search}%"))
                )
            
            total_count = await session.scalar(select(func.count()).select_from(stmt.subquery()))
            
            stmt = stmt.order_by(User.created_at.desc()).offset(offset).limit(limit)
            result = await session.execute(stmt)
            users = result.scalars().all()
            
            users_data = [{
                "id": u.id,
                "chat_id": u.chat_id,
                "username": u.username,
                "full_name": u.full_name,
                "credit": u.credit,
                "stars": u.stars,
                "level": getattr(u, 'level', 1) or 1,
                "banned": u.banned,
                "created_at": u.created_at.isoformat() if u.created_at else None
            } for u in users]
            
            return web.json_response({
                "ok": True,
                "users": users_data,
                "total": total_count,
                "page": page,
                "limit": limit
            })
    except Exception as e:
        return web.json_response({"ok": False, "error": "server_error"}, status=500)
