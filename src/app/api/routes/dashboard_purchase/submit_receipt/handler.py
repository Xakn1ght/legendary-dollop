import base64
import logging
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
from app.database.models import AsyncSessionLocal, Subscription
from app.utils.admin_bot_helper import get_admin_bot
from app.utils.validation import detect_image_type, validate_image_bytes


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
        receipt_ext = "jpg"

    async with AsyncSessionLocal() as session:
        user = await crud.get_user(session, user_chat_id)
        if not user:
            return web.json_response({"ok": False, "error": "not_registered"}, status=403)

        sub = await session.get(Subscription, order_id)
        if not sub:
            return web.json_response({"ok": False, "error": "order_not_found"}, status=404)
        if sub.user_id != user.id:
            return web.json_response({"ok": False, "error": "unauthorized"}, status=403)
        if (sub.status or "") not in ("draft", "pending") or sub.receipt_message_id is not None:
            return web.json_response({"ok": False, "error": "order_already_processed"}, status=400)

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

        sub.receipt_message_id = -1
        sub.status = "pending"
        try:
            uploads_dir = os.path.abspath(webapp_path("admin", "uploads", "receipts"))
            os.makedirs(uploads_dir, exist_ok=True)
            fname = f"receipt_{sub.id}_{''.join(random.choices(string.ascii_lowercase + string.digits, k=10))}.{receipt_ext}"
            fpath = os.path.join(uploads_dir, fname)
            with open(fpath, "wb") as f:
                f.write(image_data)
            sub.receipt_image_url = f"/admin/uploads/receipts/{fname}"
        except Exception as e:
            logger.error(f"Failed to save receipt image for order {sub.id}: {e}")

        await session.commit()

        try:
            photo_file = BufferedInputFile(image_data, filename="receipt.jpg")

            builder = InlineKeyboardBuilder()
            builder.button(text="✅ تایید", callback_data=f"approve_sub_{sub.id}")
            builder.button(text="❌ رد", callback_data=f"deny_sub_{sub.id}")
            builder.button(text="💬 Chat", callback_data=f"chat_sub_{sub.id}_{user_chat_id}")
            builder.adjust(2)

            plan_info = PLANS.get(sub.plan_name, {})
            total = plan_info.get("price", 0)
            if sub.renewal_paid and sub.renewal_price:
                total += sub.renewal_price

            discount_info = ""
            if sub.applied_discount_ids:
                discount_info = "\n🎟️ تخفیف اعمال شده"

            credit_info = ""
            if sub.credit_used and sub.credit_used > 0:
                credit_info = f"\n💰 اعتبار استفاده شده: {sub.credit_used:,} تومان"

            admin_text = (
                f"📱 رسید جدید از وب‌اپ\n\n"
                f"👤 کاربر: {user.full_name} ({user_chat_id})\n"
                f"📦 پلن: {sub.plan_name} ({plan_info.get('gb', 0)} گیگابایت)\n"
                f"🔖 نام سرویس: {sub.marzban_username}\n"
                f"💵 مبلغ کل: {total:,} تومان"
                f"{discount_info}"
                f"{credit_info}"
            )

            if sub.renewal_paid and sub.renewal_template:
                admin_text += f"\n🔄 تمدید خودکار: {sub.renewal_template}"

            admin_text += f"\n\n🆔 شماره سفارش: #{sub.id}"

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
