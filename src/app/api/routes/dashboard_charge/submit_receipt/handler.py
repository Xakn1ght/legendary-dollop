import base64
import os
import random
import string

from aiogram.types import BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.api.routes.dashboard_charge.common import GB, MAX_RECEIPT_BYTES, logger
from app.core.paths import webapp_path
from app.core.settings import ADMIN_ID
from app.database import crud
from app.database.models import AsyncSessionLocal, Subscription
from app.services.flows.charge import submit_charge_receipt
from app.services.flows.errors import FlowError
from app.utils.admin_bot_helper import get_admin_bot
from app.utils.validation import detect_image_type, validate_image_bytes


async def handle_submit_charge_receipt(request: web.Request):
    """
    Submit receipt for a charge order.
    Body: {
        order_id: int,
        receipt_image: string (base64 encoded image)
    }
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

    order_id = data.get("order_id")
    receipt_image_b64 = data.get("receipt_image", "")

    if not order_id:
        return web.json_response({"ok": False, "error": "missing_order_id"}, status=400)
    if not receipt_image_b64 or len(receipt_image_b64) < 100:
        return web.json_response({"ok": False, "error": "missing_receipt_image"}, status=400)

    receipt_ext = "jpg"
    try:
        if isinstance(receipt_image_b64, str) and receipt_image_b64.startswith("data:image/"):
            mime = receipt_image_b64.split(";")[0].split(":")[1].strip().lower()
            if "png" in mime:
                receipt_ext = "png"
            elif "jpeg" in mime or "jpg" in mime:
                receipt_ext = "jpg"
            else:
                return web.json_response(
                    {"ok": False, "error": "invalid_format", "message": "Only JPG and PNG allowed"},
                    status=400,
                )
    except Exception:
        pass

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

        ok, err = validate_image_bytes(image_data, MAX_RECEIPT_BYTES)
        if not ok:
            return web.json_response({"ok": False, "error": "invalid_image", "detail": err}, status=400)

        detected = detect_image_type(image_data)
        if receipt_ext and detected and receipt_ext != detected:
            return web.json_response({"ok": False, "error": "invalid_image", "detail": "type_mismatch"}, status=400)

        receipt_image_url = None
        try:
            uploads_dir = os.path.abspath(webapp_path("admin", "uploads", "receipts"))
            os.makedirs(uploads_dir, exist_ok=True)
            fname = f"charge_receipt_{order_id}_{''.join(random.choices(string.ascii_lowercase + string.digits, k=10))}.{receipt_ext}"
            fpath = os.path.join(uploads_dir, fname)
            with open(fpath, "wb") as f:
                f.write(image_data)
            receipt_image_url = f"/admin/uploads/receipts/{fname}"
        except Exception as e:
            logger.error(f"Failed to save charge receipt image for order {order_id}: {e}")

        try:
            charge_req = await submit_charge_receipt(
                session, user, order_id, receipt_message_id=-1, receipt_image_url=receipt_image_url
            )
        except FlowError as e:
            status = {"order_not_found": 404, "unauthorized": 403}.get(e.code, 400)
            return web.json_response({"ok": False, "error": e.code}, status=status)

        sub = await session.get(Subscription, charge_req.subscription_id)

        try:
            photo_file = BufferedInputFile(image_data, filename="charge_receipt.jpg")

            builder = InlineKeyboardBuilder()
            builder.button(text="✅ تایید شارژ", callback_data=f"approve_charge_{charge_req.id}")
            builder.button(text="❌ رد", callback_data=f"deny_charge_{charge_req.id}")
            builder.button(text="💬 Chat", callback_data=f"chat_with_user_{user_chat_id}")
            builder.adjust(2)

            gb_amount = charge_req.traffic_bytes / GB

            charge_type_label = ""
            if getattr(charge_req, "charge_type", "normal") == "normal_5gb_limit":
                charge_type_label = "\n⚠️ شارژ (حد 5GB)"

            admin_text = (
                f"📱 درخواست شارژ از وب‌اپ{charge_type_label}\n\n"
                f"👤 کاربر: {user.full_name} ({user_chat_id})\n"
                f"🔖 اشتراک: {sub.marzban_username if sub else 'N/A'}\n"
                f"📦 بسته: {gb_amount:.0f} گیگابایت"
            )

            if charge_req.extra_days:
                admin_text += f" + {charge_req.extra_days} روز"

            admin_text += f"\n💵 مبلغ: {charge_req.price:,} تومان"
            admin_text += f"\n\n🆔 شماره درخواست: #{charge_req.id}"

            admin_bot = get_admin_bot()
            if admin_bot:
                try:
                    await admin_bot.send_photo(
                        ADMIN_ID,
                        photo=photo_file,
                        caption=admin_text,
                        reply_markup=builder.as_markup(),
                    )
                    logger.info(f"Web charge receipt sent to admin bot for order {charge_req.id}")
                except Exception as e:
                    logger.error(f"Failed to send charge receipt to admin bot: {e}")
            else:
                logger.error(
                    "ADMIN_BOT_TOKEN not set; web charge receipt not delivered to Telegram (DB/panel updated)"
                )

        except Exception as e:
            logger.error(f"Failed to prepare/send charge receipt to admin: {e}")

        try:
            from app.api.routes.admin_ws import broadcast_admin_event

            await broadcast_admin_event("receipts_updated", {"order_id": charge_req.id, "type": "charge"})
        except Exception:
            pass

        resp = web.json_response({"ok": True, "message": "receipt_submitted", "order_id": charge_req.id})
        if new_session_token:
            set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
        return resp
