import base64
import logging
import os
import random
import string
import traceback

from aiogram.types import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web
from sqlalchemy.future import select

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.api.routes.dashboard.common import MAX_RECEIPT_BYTES
from app.core.paths import webapp_path
from app.core.settings import ADMIN_ID, VIP_PLANS
from app.database import crud
from app.database.models import AsyncSessionLocal, VipOrder
from app.utils.admin_bot_helper import get_admin_bot
from app.utils.image_security import ImageRejected, sanitize_image

logger = logging.getLogger(__name__)


async def handle_vip_upload_receipt(request: web.Request):
    """Upload receipt for VIP purchase."""
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

    order_id = data.get("order_id")
    receipt_image_b64 = data.get("receipt_image")

    if not order_id or not receipt_image_b64:
        return web.json_response({"ok": False, "error": "missing_data"}, status=400)

    try:
        async with AsyncSessionLocal() as session:
            user = await crud.get_user(session, user_chat_id)
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)

            result = await session.execute(
                select(VipOrder).filter(VipOrder.id == order_id, VipOrder.user_id == user.id)
            )
            order = result.scalars().first()

            if not order:
                return web.json_response({"ok": False, "error": "order_not_found"}, status=404)

            if order.status not in ("draft", "pending"):
                return web.json_response({"ok": False, "error": "order_already_processed"}, status=400)

            # Idempotent re-submit: the receipt already landed and the admin was
            # notified — spam-tapping Confirm must not DM the admin again.
            if order.status == "pending" and order.receipt_image_url:
                return web.json_response(
                    {"ok": True, "message": "already_submitted", "order_id": order.id, "status": "pending"}
                )

            try:
                if "," in receipt_image_b64:
                    receipt_image_b64 = receipt_image_b64.split(",")[1]
                image_data = base64.b64decode(receipt_image_b64)
            except Exception as e:
                logger.error(f"Failed to decode receipt image: {e}")
                return web.json_response({"ok": False, "error": "invalid_image"}, status=400)

            try:
                image_data, receipt_ext, _mime = sanitize_image(image_data, MAX_RECEIPT_BYTES)
            except ImageRejected as e:
                return web.json_response({"ok": False, "error": "invalid_image", "detail": e.code}, status=400)

            uploads_dir = os.path.abspath(webapp_path("admin", "uploads", "receipts"))
            os.makedirs(uploads_dir, exist_ok=True)
            fname = f"vip_receipt_{order.id}_{''.join(random.choices(string.ascii_lowercase + string.digits, k=10))}.{receipt_ext}"
            fpath = os.path.join(uploads_dir, fname)

            with open(fpath, "wb") as f:
                f.write(image_data)

            order.receipt_image_url = f"/admin/uploads/receipts/{fname}"
            order.status = "pending"
            await session.commit()

            # Live-update the admin panel receipts list/badge (same-process WS).
            try:
                import asyncio

                from app.api.routes.admin_ws import broadcast_admin_event

                asyncio.create_task(broadcast_admin_event("receipts_updated", {"order_id": order.id, "type": "vip"}))
            except Exception:
                pass

            try:
                admin_bot = get_admin_bot()
                if admin_bot and ADMIN_ID:
                    plan_info = VIP_PLANS.get(order.plan_id, {})

                    caption = (
                        f"<b>درخواست خرید VIP جدید</b>\n\n"
                        f"کاربر: {user.full_name or user.username or user.chat_id}\n"
                        f"پلن: {plan_info.get('label_fa', order.plan_id)}\n"
                        f"مبلغ: {order.price:,} تومان\n"
                        f"شماره سفارش: #VIP{order.id}"
                    )
                    kb = InlineKeyboardBuilder()
                    kb.button(text="تایید", callback_data=f"approve_vip_{order.id}")
                    kb.button(text="رد", callback_data=f"deny_vip_{order.id}")
                    kb.adjust(2)
                    # ONE message: photo + details + approve/deny buttons
                    await admin_bot.send_photo(
                        ADMIN_ID,
                        FSInputFile(fpath),
                        caption=caption,
                        parse_mode="HTML",
                        reply_markup=kb.as_markup(),
                    )
                elif not admin_bot:
                    logger.warning("ADMIN_BOT_TOKEN not set; VIP receipt not sent to Telegram (saved in panel)")
            except Exception as e:
                logger.warning(f"Could not notify admin about VIP purchase: {e}")

            resp = web.json_response(
                {
                    "ok": True,
                    "message": "Receipt uploaded successfully",
                    "order_id": order.id,
                    "status": "pending",
                }
            )
            if new_session_token:
                set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
            return resp
    except Exception as e:
        traceback.print_exc()
        logger.error(f"Error uploading VIP receipt: {e}")
        return web.json_response({"ok": False, "error": "server_error"}, status=500)
