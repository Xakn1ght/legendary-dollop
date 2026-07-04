import base64
import os
import random
import string

from aiogram.types import BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.api.routes.dashboard_purchase.common import MAX_RECEIPT_BYTES, logger
from app.api.schemas import SubmitReceiptRequest, validate_request
from app.core.paths import webapp_path
from app.core.settings import ADMIN_ID, PLANS
from app.database import crud
from app.database.models import AsyncSessionLocal
from app.services.flows.errors import FlowError
from app.services.flows.purchase import submit_purchase_receipt
from app.utils.admin_bot_helper import get_admin_bot
from app.utils.image_security import ImageRejected, sanitize_image


async def handle_submit_receipt(request: web.Request):
    """
    Submit receipt for a purchase order.
    Body: {
        order_id: int,
        receipt_image: string (base64 encoded image)
    }

    Sends notification to admin via Telegram bot and stores for web panel.
    """
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        data = await request.json()
    except web.HTTPRequestEntityTooLarge:
        return web.json_response(
            {"ok": False, "error": "payload_too_large", "message": "Receipt image is too large"},
            status=413,
        )
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

    validated, error = validate_request(SubmitReceiptRequest, data)
    if error:
        return web.json_response(error, status=400)

    order_id = validated.order_id
    receipt_image_b64 = validated.receipt_image

    async with AsyncSessionLocal() as session:
        user = await crud.get_user(session, user_chat_id)
        if not user:
            return web.json_response({"ok": False, "error": "not_registered"}, status=403)

        try:
            if "," in receipt_image_b64:
                receipt_image_b64 = receipt_image_b64.split(",", 1)[1]
            image_data = base64.b64decode(receipt_image_b64)
        except Exception as e:
            logger.error(f"Failed to decode receipt image: {e}")
            return web.json_response({"ok": False, "error": "invalid_image"}, status=400)

        try:
            image_data, receipt_ext, _mime = sanitize_image(image_data, MAX_RECEIPT_BYTES)
        except ImageRejected as e:
            return web.json_response({"ok": False, "error": "invalid_image", "detail": e.code}, status=400)

        receipt_image_url = None
        try:
            uploads_dir = os.path.abspath(webapp_path("admin", "uploads", "receipts"))
            os.makedirs(uploads_dir, exist_ok=True)
            fname = f"receipt_{order_id}_{''.join(random.choices(string.ascii_lowercase + string.digits, k=10))}.{receipt_ext}"
            fpath = os.path.join(uploads_dir, fname)
            with open(fpath, "wb") as f:
                f.write(image_data)
            receipt_image_url = f"/admin/uploads/receipts/{fname}"
        except Exception as e:
            logger.error(f"Failed to save receipt image for order {order_id}: {e}")

        try:
            sub = await submit_purchase_receipt(
                session, user, order_id, receipt_message_id=-1, receipt_image_url=receipt_image_url
            )
        except FlowError as e:
            status = {"order_not_found": 404, "unauthorized": 403}.get(e.code, 400)
            return web.json_response({"ok": False, "error": e.code}, status=status)

        try:
            photo_file = BufferedInputFile(image_data, filename="receipt.jpg")

            builder = InlineKeyboardBuilder()
            builder.button(text="✅ تایید", callback_data=f"approve_sub_{sub.id}")
            builder.button(text="❌ رد", callback_data=f"deny_sub_{sub.id}")
            builder.button(text="💬 Chat", callback_data=f"chat_sub_{sub.id}_{user_chat_id}")
            builder.adjust(2)

            from app.utils.receipt_captions import purchase_receipt_caption

            admin_text = purchase_receipt_caption(sub, user, source="webapp", plans=PLANS)

            admin_bot = get_admin_bot()
            if admin_bot:
                try:
                    await admin_bot.send_photo(
                        ADMIN_ID,
                        photo=photo_file,
                        caption=admin_text,
                        reply_markup=builder.as_markup(),
                    )
                except Exception as e:
                    logger.error(f"Failed to send receipt to admin bot: {e}")
            else:
                logger.error(
                    "ADMIN_BOT_TOKEN not set; web purchase receipt not sent to Telegram (saved in panel/DB)"
                )

            logger.info(f"Web receipt admin Telegram step done for order {sub.id}")

        except Exception as e:
            logger.error(f"Failed to send receipt to admin: {e}")

        try:
            from app.api.routes.admin_ws import broadcast_admin_event

            await broadcast_admin_event("receipts_updated", {"order_id": sub.id})
        except Exception:
            pass

        resp = web.json_response({"ok": True, "message": "receipt_submitted", "order_id": sub.id})
        if new_session_token:
            set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
        return resp
