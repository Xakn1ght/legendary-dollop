from datetime import datetime

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import PLANS
from app.database.models import Receipt, Subscription, User
from app.services.marzban import marzban_api
from app.utils.bot_i18n import t
from app.utils.logger import bot_logger, log_error

from .common import UserManagementStates, _lang_for_tg_user, router


async def _build_subscription_details_view(
    sub_id: int, session: AsyncSession
) -> tuple[str, InlineKeyboardMarkup | None]:
    """Build the text and keyboard for the subscription details view."""
    # Get subscription details
    sub_query = select(Subscription).filter(Subscription.id == sub_id)
    sub_result = await session.execute(sub_query)
    subscription = sub_result.scalar_one_or_none()

    if not subscription:
        return ("❌ اشتراک یافت نشد.", None)

    # Get user details
    user_query = select(User).filter(User.id == subscription.user_id)
    user_result = await session.execute(user_query)
    user = user_result.scalar_one_or_none()

    # Format subscription details
    status_emoji = {
        "active": "✅ فعال",
        "pending": "⏳ در انتظار",
        "disabled": "🚫 غیرفعال",
        "expired": "❌ منقضی",
        "cancelled": "🚫 لغو شده",
    }.get(subscription.status, "❓ نامشخص")

    created_date = (
        subscription.created_at.strftime("%Y-%m-%d %H:%M")
        if subscription.created_at
        else "نامشخص"
    )

    # Escape special characters for HTML
    def escape_html(text):
        if not text:
            return "نامشخص"
        return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Get Marzban user details if possible
    marzban_info = ""
    try:
        if subscription.marzban_username:
            marzban_user = await marzban_api.get_user_info(subscription.marzban_username)
            if marzban_user:
                # Format data usage
                used_traffic = marzban_user.get("used_traffic", 0)
                data_limit = marzban_user.get("data_limit", 0)

                # Convert bytes to GB
                used_gb = used_traffic / (1024**3) if used_traffic else 0
                limit_gb = data_limit / (1024**3) if data_limit else 0

                expire_timestamp = marzban_user.get("expire")
                if expire_timestamp:
                    expire_date = datetime.fromtimestamp(expire_timestamp).strftime(
                        "%Y-%m-%d %H:%M"
                    )
                else:
                    expire_date = "نامحدود"

                marzban_status = marzban_user.get("status", "unknown")
                marzban_status_map = {
                    "active": "🟢 فعال",
                    "disabled": "🔴 غیرفعال",
                    "limited": "🟡 محدود",
                    "expired": "⚫️ منقضی",
                }
                marzban_status_emoji = marzban_status_map.get(marzban_status, "❓")

                marzban_info = (
                    f"\n📈 <b>اطلاعات مرزبان:</b>\n"
                    f"🌐 مصرف: <code>{used_gb:.2f} GB</code> از <code>{limit_gb:.2f} GB</code>\n"
                    f"⏰ انقضا: {expire_date}\n"
                    f"🔄 وضعیت مرزبان: {marzban_status_emoji}\n"
                )
    except Exception as e:
        bot_logger.error(
            f"Could not fetch marzban info for {subscription.marzban_username}: {e}"
        )
        marzban_info = "\n⚠️ unable to fetch marzban info"

    text = (
        f"<b>جزئیات اشتراک</b>\n\n"
        f"👤 کاربر: {escape_html(user.full_name if user else 'Unknown')}\n"
        f"🆔 شناسه: <code>{subscription.id}</code>\n"
        f"🏷 نام کاربری مرزبان: <code>{escape_html(subscription.marzban_username)}</code>\n"
        f"📦 پلن: {escape_html(subscription.plan_name)}\n"
        f"💰 قیمت: <code>{subscription.price:,}</code> تومان\n"
        f"🔄 وضعیت: {status_emoji}\n"
        f"📅 تاریخ ایجاد: {created_date}\n"
        f"💳 شناسه رسید: {subscription.receipt_message_id or 'ندارد'}\n"
        f"{marzban_info}"
    )

    kb = InlineKeyboardBuilder()

    # Action buttons based on subscription status
    if subscription.status == "pending":
        kb.button(text="✅ تایید", callback_data=f"approve_sub_{subscription.id}")
        kb.button(text="❌ رد", callback_data=f"reject_sub_{subscription.id}")
    elif subscription.status == "active":
        kb.button(text="⏸ غیرفعال کردن", callback_data=f"disable_sub_{subscription.id}")
        kb.button(text="🔄 تمدید", callback_data=f"renew_sub_{subscription.id}")
    elif subscription.status in ["disabled", "cancelled"]:
        kb.button(text="✅ فعال کردن", callback_data=f"enable_sub_{subscription.id}")
        kb.button(text="🔄 تمدید", callback_data=f"renew_sub_{subscription.id}")
    elif subscription.status == "expired":
        kb.button(text="🔄 تمدید", callback_data=f"renew_sub_{subscription.id}")
        kb.button(text="🗑 حذف", callback_data=f"delete_sub_{subscription.id}")

    # Common buttons
    kb.button(text="📈 تغییر حجم", callback_data=f"edit_traffic_{subscription.id}")
    kb.button(text="🔙 بازگشت", callback_data=f"user_subs_{user.chat_id}")
    kb.adjust(2)

    return text, kb.as_markup()


@router.callback_query(F.data.startswith("sub_details_"))
async def show_subscription_details(callback: CallbackQuery, session: AsyncSession):
    """Show detailed information about a specific subscription"""
    try:
        sub_id = int(callback.data.split("_")[2])
        await callback.answer("⏳ در حال دریافت جزئیات اشتراک...")

        text, reply_markup = await _build_subscription_details_view(sub_id, session)

        if reply_markup:
            await callback.message.edit_text(
                text, reply_markup=reply_markup, parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(text)

    except Exception as e:
        error_msg = f"Error in show_subscription_details handler: {str(e)}"
        bot_logger.error(error_msg)
        await callback.answer("❌ خطای داخلی رخ داد.", show_alert=True)


@router.callback_query(F.data.startswith("disable_sub_"))
async def disable_subscription(callback: CallbackQuery, session: AsyncSession):
    """Disable an active subscription"""
    try:
        sub_id = int(callback.data.split("_")[2])
        await callback.answer("⏳ در حال غیرفعال کردن اشتراک...")

        # Get subscription
        sub_query = select(Subscription).filter(Subscription.id == sub_id)
        sub_result = await session.execute(sub_query)
        subscription = sub_result.scalar_one_or_none()

        if not subscription:
            await callback.answer("❌ اشتراک یافت نشد.", show_alert=True)
            return

        # Disable in Marzban
        try:
            if subscription.marzban_username:
                await marzban_api.toggle_user_status(subscription.marzban_username, "disabled")
        except Exception as e:
            await callback.answer(
                f"⚠️ خطا در غیرفعال کردن در مرزبان: {str(e)}", show_alert=True
            )
            return

        # Update status in database
        subscription.status = "disabled"
        await session.commit()

        await callback.answer("✅ اشتراک غیرفعال شد.", show_alert=True)

        # Notify the user
        try:
            user = await session.get(User, subscription.user_id)
            if user:
                await callback.bot.send_message(
                    user.chat_id,
                    f"⏸ اشتراک شما ({subscription.marzban_username}) توسط ادمین غیرفعال شد.",
                )
        except Exception as e:
            bot_logger.error(
                f"Failed to send disable notification to user {subscription.user_id}: {e}"
            )

        # Refresh the details view
        await show_subscription_details(callback, session)

    except Exception as e:
        error_msg = f"Error in disable_subscription handler: {str(e)}"
        bot_logger.error(error_msg)
        await callback.answer("❌ خطای داخلی رخ داد.", show_alert=True)


@router.callback_query(F.data.startswith("enable_sub_"))
async def enable_subscription(callback: CallbackQuery, session: AsyncSession):
    """Enable a disabled subscription"""
    try:
        sub_id = int(callback.data.split("_")[2])
        await callback.answer("⏳ در حال فعال کردن اشتراک...")

        # Get subscription
        sub_query = select(Subscription).filter(Subscription.id == sub_id)
        sub_result = await session.execute(sub_query)
        subscription = sub_result.scalar_one_or_none()

        if not subscription:
            await callback.answer("❌ اشتراک یافت نشد.", show_alert=True)
            return

        # Enable in Marzban
        if subscription.marzban_username:
            try:
                success = await marzban_api.toggle_user_status(
                    subscription.marzban_username, "active"
                )
                if not success:
                    await callback.answer("⚠️ خطا در فعال کردن در مرزبان", show_alert=True)
                    return
            except Exception as e:
                bot_logger.error(f"Error enabling user in Marzban: {str(e)}")
                await callback.answer("⚠️ خطا در فعال کردن در مرزبان", show_alert=True)
                return

        # Update status in database
        subscription.status = "active"
        await session.commit()

        await callback.answer("✅ اشتراک فعال شد.", show_alert=True)

        # Notify the user
        try:
            user = await session.get(User, subscription.user_id)
            if user:
                await callback.bot.send_message(
                    user.chat_id,
                    f"✅ اشتراک شما ({subscription.marzban_username}) توسط ادمین فعال شد.",
                )
        except Exception as e:
            bot_logger.error(
                f"Failed to send enable notification to user {subscription.user_id}: {e}"
            )

        # Refresh the details view
        await show_subscription_details(callback, session)

    except Exception as e:
        error_msg = f"Error in enable_subscription handler: {str(e)}"
        bot_logger.error(error_msg)
        await callback.answer("❌ خطای داخلی رخ داد.", show_alert=True)


@router.callback_query(F.data.startswith("renew_sub_"))
async def renew_subscription_admin(callback: CallbackQuery, session: AsyncSession):
    """Admin-initiated renewal of a subscription."""
    try:
        sub_id = int(callback.data.split("_")[2])
        await callback.answer("⏳ در حال تمدید اشتراک...")

        subscription = await session.get(Subscription, sub_id)
        if not subscription:
            await callback.answer("❌ اشتراک یافت نشد.", show_alert=True)
            return

        plan_details = PLANS.get(subscription.plan_name)
        if not plan_details:
            await callback.answer("❌ پلن اشتراک یافت نشد.", show_alert=True)
            return

        # Renew user in Marzban
        success = await marzban_api.reset_user_traffic(
            username=subscription.marzban_username,
            new_data_limit_gb=plan_details["gb"],
            new_expire_days=30,  # Assuming a default of 30 days
        )

        if not success:
            await callback.answer("❌ خطا در تمدید در مرزبان.", show_alert=True)
            return

        # Create a new receipt
        receipt = Receipt(
            user_id=subscription.user_id,
            plan_name=subscription.plan_name,
            price=subscription.price,
            paid_amount=subscription.price,
            status="completed",
            subscription_id=sub_id,
        )
        session.add(receipt)
        await session.flush()

        subscription.receipt_message_id = receipt.id
        await session.commit()

        await callback.answer("✅ اشتراک با موفقیت تمدید شد.", show_alert=True)

        # Refresh the details view
        text, reply_markup = await _build_subscription_details_view(sub_id, session)
        if reply_markup:
            await callback.message.edit_text(
                text, reply_markup=reply_markup, parse_mode="HTML"
            )

        # Notify the user
        try:
            user = await session.get(User, subscription.user_id)
            if user:
                await callback.bot.send_message(
                    user.chat_id,
                    f"✅ اشتراک شما با موفقیت تمدید شد!\\n"
                    f"پلن: {subscription.plan_name}\\n"
                    f"حجم: {plan_details['gb']} گیگابایت\\n"
                    f"مدت: 30 روز",
                )
        except Exception as e:
            bot_logger.error(
                f"Failed to send renewal notification to user {subscription.user_id}: {e}"
            )

    except Exception as e:
        bot_logger.error(f"Error in renew_subscription_admin: {e}")
        await callback.answer("❌ خطای داخلی رخ داد.", show_alert=True)


@router.callback_query(F.data.startswith("edit_traffic_"))
async def edit_traffic_prompt(
    callback: CallbackQuery, state: FSMContext, _session: AsyncSession
):
    """Prompt admin to enter new traffic amount"""
    try:
        sub_id = int(callback.data.split("_")[2])
        await state.update_data(sub_id=sub_id)

        await callback.message.edit_text(
            "📈 لطفاً مقدار حجم جدید را وارد کنید (به گیگابایت).",
            reply_markup=InlineKeyboardBuilder()
            .button(text="🔙 لغو", callback_data=f"sub_details_{sub_id}")
            .as_markup(),
        )
        await state.set_state(UserManagementStates.waiting_traffic_amount)

    except Exception as e:
        bot_logger.error(f"Error in edit_traffic_prompt: {e}")
        await callback.answer("❌ خطای داخلی رخ داد.", show_alert=True)


@router.message(UserManagementStates.waiting_traffic_amount)
async def process_traffic_amount(
    message: Message, state: FSMContext, session: AsyncSession
):
    """Process the new traffic amount and update the subscription"""
    try:
        new_traffic_gb = float(message.text)
        data = await state.get_data()
        sub_id = data.get("sub_id")

        # Get subscription
        subscription = await session.get(Subscription, sub_id)
        if not subscription or not subscription.marzban_username:
            await message.answer("❌ اشتراک یافت نشد یا نام کاربری مرزبان ندارد.")
            await state.clear()
            return

        # Convert GB to bytes
        new_traffic_bytes = new_traffic_gb * (1024**3)

        # Update user in Marzban
        api_session = await marzban_api._get_session()
        headers = await marzban_api._get_headers()
        url = f"{marzban_api.base_url}/api/user/{subscription.marzban_username}"

        async with api_session.put(
            url, headers=headers, json={"data_limit": new_traffic_bytes}
        ) as resp:
            if resp.status in (200, 204):
                admin_lang = _lang_for_tg_user(message.from_user)
                await message.answer(
                    t(admin_lang, "admin_um_traffic_updated").format(
                        username=subscription.marzban_username,
                        gb=new_traffic_gb,
                    )
                )

                # Notify the user
                try:
                    user = await session.get(User, subscription.user_id)
                    if user:
                        user_lang = getattr(user, "language", None)
                        await message.bot.send_message(
                            user.chat_id,
                            t(user_lang, "user_traffic_updated_by_admin").format(
                                username=subscription.marzban_username,
                                gb=new_traffic_gb,
                            ),
                        )
                except Exception as e:
                    bot_logger.error(
                        f"Failed to send traffic change notification to user {subscription.user_id}: {e}"
                    )

                # Show the updated details view
                text, reply_markup = await _build_subscription_details_view(sub_id, session)
                if reply_markup:
                    await message.answer(
                        text, reply_markup=reply_markup, parse_mode="HTML"
                    )

            else:
                error_details = await resp.text()
                log_error(
                    Exception(
                        f"Failed to update traffic for {subscription.marzban_username}: {resp.status} - {error_details}"
                    ),
                    {
                        "operation": "marzban_update_traffic",
                        "username": subscription.marzban_username,
                        "status_code": resp.status,
                    },
                )
                await message.answer("❌ خطا در به‌روزرسانی حجم در مرزبان.")

    except ValueError:
        await message.answer("❌ لطفاً یک عدد معتبر وارد کنید.")
    except Exception as e:
        bot_logger.error(f"Error in process_traffic_amount: {e}")
        await message.answer("❌ خطای داخلی رخ داد.")
    finally:
        await state.clear()


@router.callback_query(F.data.startswith("approve_sub_"))
async def approve_subscription(callback: CallbackQuery, session: AsyncSession):
    """Approve a pending subscription"""
    try:
        sub_id = int(callback.data.split("_")[2])
        await callback.answer("⏳ در حال تایید اشتراک...")

        # Get subscription
        sub_query = select(Subscription).filter(Subscription.id == sub_id)
        sub_result = await session.execute(sub_query)
        subscription = sub_result.scalar_one_or_none()

        if not subscription:
            await callback.answer("❌ اشتراک یافت نشد.", show_alert=True)
            return

        # Activate in Marzban
        try:
            if subscription.marzban_username:
                await marzban_api.toggle_user_status(subscription.marzban_username, "active")
        except Exception as e:
            await callback.answer(
                f"⚠️ خطا در فعال کردن در مرزبان: {str(e)}", show_alert=True
            )
            return

        # Update status in database
        subscription.status = "active"
        await session.commit()

        await callback.answer("✅ اشتراک با موفقیت تایید شد.", show_alert=True)

        # Refresh the details view
        await show_subscription_details(callback, session)

    except Exception as e:
        error_msg = f"Error in approve_subscription handler: {str(e)}"
        bot_logger.error(error_msg)
        await callback.answer("❌ خطای داخلی رخ داد.", show_alert=True)


@router.callback_query(F.data.startswith("reject_sub_"))
async def reject_subscription(callback: CallbackQuery, session: AsyncSession):
    """Reject a pending subscription"""
    try:
        sub_id = int(callback.data.split("_")[2])
        await callback.answer("⏳ در حال رد اشتراک...")

        # Get subscription
        sub_query = select(Subscription).filter(Subscription.id == sub_id)
        sub_result = await session.execute(sub_query)
        subscription = sub_result.scalar_one_or_none()

        if not subscription:
            await callback.answer("❌ اشتراک یافت نشد.", show_alert=True)
            return

        # Delete from Marzban
        try:
            if subscription.marzban_username:
                await marzban_api.delete_user(subscription.marzban_username)
        except Exception as e:
            bot_logger.error(f"Error deleting user from Marzban: {str(e)}")

        # Update status in database
        subscription.status = "cancelled"
        await session.commit()

        await callback.answer("✅ اشتراک رد شد.", show_alert=True)

        # Refresh the details view
        await show_subscription_details(callback, session)

    except Exception as e:
        error_msg = f"Error in reject_subscription handler: {str(e)}"
        bot_logger.error(error_msg)
        await callback.answer("❌ خطای داخلی رخ داد.", show_alert=True)
