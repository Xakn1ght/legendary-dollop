import random

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.settings import PLANS
from app.database.crud import (
    accept_user_gift,
    create_user_gift,
    get_all_users,
    get_user,
    get_user_by_id,
    get_user_gifts,
    set_gift_payment_status,
)
from app.database.models import UserGift
from app.handlers.user.purchase import generate_unique_username
from app.shared.plan_ordering import get_ordered_plans
from app.utils.bot_i18n import guess_lang_from_telegram, t

router = Router()

def _lang_for_tg_user(tg_user) -> str:
    return guess_lang_from_telegram(getattr(tg_user, "language_code", None))

# -----------------------------
#  Gift System
# -----------------------------

class GiftStates(StatesGroup):
    waiting_for_receiver = State()
    waiting_for_gift_type = State()
    waiting_for_gift_value = State()
    waiting_for_message = State()
    waiting_for_plan = State()
    waiting_for_payment_receipt = State()


@router.callback_query(F.data == "enhanced_send_gift")
async def start_gift_process(callback: CallbackQuery, state: FSMContext):
    """Start the gift sending process: choose manual vs random recipient."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎲 انتخاب تصادفی گیرنده", callback_data="gift_random_pick"),
            InlineKeyboardButton(text="🆔 وارد کردن گیرنده", callback_data="gift_choose_manual"),
        ],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="enhanced_rewards_menu")]
    ])

    await callback.message.edit_text(
        "💝 **ارسال هدیه**\n\n"
        "لطفاً روش انتخاب گیرنده را انتخاب کنید:",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "gift_choose_manual")
async def choose_manual_receiver(callback: CallbackQuery, state: FSMContext):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="enhanced_rewards_menu")]
    ])
    await callback.message.edit_text(
        "💝 **ارسال هدیه**\n\n"
        "لطفاً گیرنده را وارد کنید: @username یا شناسه عددی Telegram",
        reply_markup=keyboard
    )
    await state.set_state(GiftStates.waiting_for_receiver)


@router.callback_query(F.data == "gift_random_pick")
async def pick_random_receiver(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Pick a random eligible user as receiver (not the sender, not banned)."""
    all_users = await get_all_users(session)
    sender_chat_id = callback.from_user.id
    candidates = [u for u in all_users if getattr(u, "banned", False) is False and u.chat_id and u.chat_id != sender_chat_id]
    if not candidates:
        await callback.answer("❌ کاربر مناسبی برای انتخاب تصادفی یافت نشد.", show_alert=True)
        return
    receiver = random.choice(candidates)
    await state.update_data(receiver_id=receiver.id)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰 اعتبار", callback_data="gift_type_credit"),
            InlineKeyboardButton(text="💎 امتیازات وفاداری", callback_data="gift_type_loyalty_points")
        ],
        [InlineKeyboardButton(text="📦 اشتراک", callback_data="gift_type_subscription")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="enhanced_rewards_menu")]
    ])

    await callback.message.edit_text(
        f"✅ گیرنده تصادفی انتخاب شد: {receiver.full_name or receiver.username or f'کاربر {receiver.chat_id}'}\n\n"
        "حالا نوع هدیه را انتخاب کنید:",
        reply_markup=keyboard
    )
    await state.set_state(GiftStates.waiting_for_gift_type)


@router.message(GiftStates.waiting_for_receiver)
async def process_gift_receiver(message: Message, state: FSMContext, session: AsyncSession):
    """Process the gift receiver input."""
    lang = _lang_for_tg_user(message.from_user)
    raw = (message.text or "").strip()
    receiver = None
    # Try numeric chat_id
    try:
        receiver_chat_id = int(raw)
        receiver = await get_user(session, receiver_chat_id)
    except ValueError:
        receiver = None
    # Try @username
    if receiver is None:
        from app.database.crud import get_user_by_username
        username = raw.lstrip('@')
        if username:
            receiver = await get_user_by_username(session, username)
    if not receiver:
        await message.answer(t(lang, "gift_user_not_found_hint"))
        return
    if receiver.chat_id == message.from_user.id:
        await message.answer(t(lang, "gift_cannot_gift_self"))
        return

    await state.update_data(receiver_id=receiver.id)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰 اعتبار", callback_data="gift_type_credit"),
            InlineKeyboardButton(text="💎 امتیازات وفاداری", callback_data="gift_type_loyalty_points")
        ],
        [InlineKeyboardButton(text="📦 اشتراک", callback_data="gift_type_subscription")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="enhanced_rewards_menu")]
    ])

    await message.answer(
        f"✅ کاربر یافت شد: {receiver.full_name or receiver.username}\n\n"
        "حالا نوع هدیه را انتخاب کنید:",
        reply_markup=keyboard
    )
    await state.set_state(GiftStates.waiting_for_gift_type)


@router.callback_query(F.data.startswith("gift_type_"))
async def process_gift_type(callback: CallbackQuery, state: FSMContext):
    """Process gift type selection."""
    gift_type = callback.data.replace("gift_type_", "")
    await state.update_data(gift_type=gift_type)
    if gift_type == "subscription":
        # Ask for plan selection
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        kb = InlineKeyboardBuilder()
        for plan_name in get_ordered_plans():
            kb.button(text=plan_name, callback_data=f"gift_plan_{plan_name}")
        kb.button(text="🔙 بازگشت", callback_data="enhanced_rewards_menu")
        kb.adjust(2)
        await callback.message.edit_text(
            "📦 لطفاً پلن اشتراک مورد نظر را انتخاب کنید:",
            reply_markup=kb.as_markup()
        )
        # Reuse waiting_for_message after plan chosen
        # We'll set plan via gift_plan_ handler
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="enhanced_rewards_menu")]
    ])

    await callback.message.edit_text(
        f"💝 **ارسال هدیه**\n\n"
        f"نوع هدیه: {gift_type}\n\n"
        f"لطفاً مقدار هدیه را وارد کنید:",
        reply_markup=keyboard
    )
    await state.set_state(GiftStates.waiting_for_gift_value)


@router.callback_query(F.data.startswith("gift_plan_"))
async def process_gift_plan(callback: CallbackQuery, state: FSMContext):
    plan_name = callback.data.replace("gift_plan_", "")
    if plan_name not in PLANS:
        await callback.answer("❌ پلن نامعتبر است.", show_alert=True)
        return
    await state.update_data(gift_plan=plan_name, gift_value=PLANS[plan_name]['price'])
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 بازگشت", callback_data="enhanced_rewards_menu")]])
    await callback.message.edit_text(
        f"💝 **ارسال هدیه**\n\n"
        f"پلن: {plan_name} – قیمت: {PLANS[plan_name]['price']:,}\n\n"
        f"آیا پیام خاصی همراه هدیه ارسال کنید؟ (اختیاری)\nاگر پیام ندارید، 'نه' را تایپ کنید:",
        reply_markup=keyboard
    )
    await state.set_state(GiftStates.waiting_for_message)


@router.message(GiftStates.waiting_for_gift_value)
async def process_gift_value(message: Message, state: FSMContext, session: AsyncSession):
    """Process gift value input."""
    try:
        gift_value = int(message.text)
        if gift_value <= 0:
            await message.answer("❌ مقدار هدیه باید مثبت باشد!")
            return

        await state.update_data(gift_value=gift_value)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data="enhanced_rewards_menu")]
        ])

        await message.answer(
            f"💝 **ارسال هدیه**\n\n"
            f"مقدار هدیه: {gift_value:,}\n\n"
            f"آیا پیام خاصی همراه هدیه ارسال کنید؟ (اختیاری)\n"
            f"اگر پیام ندارید، 'نه' را تایپ کنید:",
            reply_markup=keyboard
        )
        await state.set_state(GiftStates.waiting_for_message)

    except ValueError:
        await message.answer("❌ لطفاً یک عدد صحیح وارد کنید!")


@router.message(GiftStates.waiting_for_message)
async def process_gift_message(message: Message, state: FSMContext, session: AsyncSession):
    """Process gift message and send the gift."""
    data = await state.get_data()
    receiver_id = data.get("receiver_id")
    gift_type = data.get("gift_type")
    gift_value = data.get("gift_value")
    gift_plan = data.get("gift_plan")
    gift_message = None if message.text.lower() in ["نه", "no", "n"] else message.text

    sender = await get_user(session, message.from_user.id)
    if not sender:
        await message.answer("❌ خطا در یافتن اطلاعات شما!")
        await state.clear()
        return

    # Handle insufficient funds by allowing pay-by-receipt (credit and subscription)
    if gift_type == "credit" and sender.credit < gift_value:
        gift = await create_user_gift(session, sender.id, receiver_id, gift_type, gift_value, gift_message)
        await set_gift_payment_status(session, gift.id, 'pending')
        await state.update_data(pending_gift_id=gift.id)
        # Offer immediate pay action
        pay_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📤 ارسال رسید الان", callback_data=f"gift_paynow:{gift.id}")],
                [InlineKeyboardButton(text="❌ لغو", callback_data=f"gift_cancel:{gift.id}")],
            ]
        )
        await message.answer(
            "❌ اعتبار کافی ندارید!",
            reply_markup=pay_kb
        )
        return
    elif gift_type == "loyalty_points" and sender.loyalty_points < gift_value:
        await message.answer("❌ امتیازات وفاداری کافی ندارید!")
        await state.clear()
        return
    elif gift_type == "subscription":
        from app.core.settings import PLANS
        if not gift_plan or gift_plan not in PLANS:
            await message.answer("❌ پلن نامعتبر است.")
            await state.clear()
            return
        plan_price = PLANS[gift_plan]['price']
        if sender.credit < plan_price:
            gift = await create_user_gift(session, sender.id, receiver_id, gift_type, plan_price, gift_message, plan_name=gift_plan)
            await set_gift_payment_status(session, gift.id, 'pending')
            await state.update_data(pending_gift_id=gift.id)
            pay_kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="📤 ارسال رسید الان", callback_data=f"gift_paynow:{gift.id}")],
                    [InlineKeyboardButton(text="❌ لغو", callback_data=f"gift_cancel:{gift.id}")],
                ]
            )
            await message.answer(
                f"❌ اعتبار کافی ندارید!\n\nبرای هدیه پلن {gift_plan} به مبلغ {plan_price:,} تومان، می‌توانید همین حالا رسید پرداخت را ارسال کنید.",
                reply_markup=pay_kb
            )
            return
        gift_value = plan_price
        gift = await create_user_gift(session, sender.id, receiver_id, gift_type, gift_value, gift_message, plan_name=gift_plan)
    else:
        # Normal create
        gift = await create_user_gift(
            session, sender.id, receiver_id, gift_type, gift_value, gift_message
        )

    if gift:
        # Deduct from sender (raw SQL for brevity)
        if gift_type == "credit":
            await session.execute(
                "UPDATE users SET credit = credit - :amount WHERE id = :user_id",
                {"amount": gift_value, "user_id": sender.id}
            )
        elif gift_type == "loyalty_points":
            await session.execute(
                "UPDATE users SET loyalty_points = loyalty_points - :amount WHERE id = :user_id",
                {"amount": gift_value, "user_id": sender.id}
            )
        elif gift_type == "subscription":
            await session.execute(
                "UPDATE users SET credit = credit - :amount WHERE id = :user_id",
                {"amount": gift_value, "user_id": sender.id}
            )
        await session.commit()

        # Notify sender
        await message.answer(
            f"✅ هدیه با موفقیت ارسال شد!\n\n"
            f"🎁 نوع: {gift_type}\n"
            f"💰 مقدار: {gift_value:,}\n"
            f"📝 پیام: {gift_message or 'بدون پیام'}"
        )
        # Notify receiver with accept button
        try:
            receiver = await get_user_by_id(session, receiver_id)
            if receiver and receiver.chat_id:
                accept_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="✅ پذیرش هدیه", callback_data=f"gift_accept:{gift.id}")]]
                )
                await message.bot.send_message(
                    receiver.chat_id,
                    (
                        "🎁 شما یک هدیه جدید دارید!\n\n"
                        f"👤 فرستنده: {sender.full_name or sender.username or sender.chat_id}\n"
                        f"نوع: {gift_type}{(' – ' + gift_plan) if gift_type == 'subscription' else ''}\n"
                        f"مقدار: {gift_value:,}\n"
                        f"پیام: {gift_message or 'بدون پیام'}\n\n"
                        "برای افزودن به حساب خود، دکمه زیر را لمس کنید."
                    ),
                    reply_markup=accept_keyboard
                )
        except Exception:
            pass
    else:
        await message.answer("❌ خطا در ارسال هدیه!")

    await state.clear()


@router.message(GiftStates.waiting_for_payment_receipt, F.content_type == 'photo')
async def process_gift_payment_receipt(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    gift_id = data.get('pending_gift_id')
    if not gift_id:
        await message.answer("❌ خطا: شناسه هدیه یافت نشد.")
        await state.clear()
        return
    await set_gift_payment_status(session, gift_id, 'pending', receipt_message_id=message.message_id)
    # Notify admin — on the ADMIN bot (admin traffic never flows through the
    # user bot). The photo can't be copy_message'd by a bot that isn't in the
    # user's chat, so it's relayed download→re-upload with the caption inline.
    from app.handlers.admin.common import ADMIN_IDS
    from app.utils.admin_bot_helper import get_admin_bot, relay_user_receipt_photo_to_admin
    try:
        admin_bot = get_admin_bot()
        if admin_bot:
            caption = f"🧾 رسید پرداخت برای هدیه #{gift_id} ارسال شد. برای تایید/رد از منوی مدیریت هدایا استفاده کنید."
            for admin_id in ADMIN_IDS:
                try:
                    sent = await relay_user_receipt_photo_to_admin(
                        message.bot, admin_bot, admin_id, message, caption=caption
                    )
                    if not sent:
                        await admin_bot.send_message(admin_id, caption)
                except Exception:
                    pass
    except Exception:
        pass
    await message.answer("✅ رسید دریافت شد. پس از تایید ادمین، هدیه برای گیرنده فعال/قابل پذیرش می‌شود.")
    await state.clear()


@router.callback_query(F.data.startswith("gift_paynow:"))
async def gift_paynow(callback: CallbackQuery, state: FSMContext):
    # Instruct user to upload receipt photo now
    gift_id = callback.data.split(":", 1)[1]
    await state.update_data(pending_gift_id=int(gift_id))
    await callback.message.answer("لطفاً تصویر رسید پرداخت را ارسال کنید.")
    await state.set_state(GiftStates.waiting_for_payment_receipt)
    await callback.answer()


@router.callback_query(F.data.startswith("gift_cancel:"))
async def gift_cancel(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    try:
        gid = int(callback.data.split(":", 1)[1])
    except Exception:
        gid = None
    await state.clear()
    await callback.answer("لغو شد")


@router.callback_query(F.data.startswith("gift_accept:"))
async def accept_gift_callback(callback: CallbackQuery, session: AsyncSession):
    """Accept a pending gift and transfer rewards to receiver."""
    try:
        gift_id = int(callback.data.split(":", 1)[1])
    except Exception:
        await callback.answer("❌ شناسه هدیه نامعتبر است.", show_alert=True)
        return

    # Verify ownership before accepting
    result = await session.execute(select(UserGift).filter(UserGift.id == gift_id))
    gift_row = result.scalars().first()
    if not gift_row:
        await callback.answer("❌ هدیه یافت نشد.", show_alert=True)
        return
    # Ensure the clicker is the intended receiver
    receiver = await get_user_by_id(session, gift_row.receiver_id)
    if not receiver or receiver.chat_id != callback.from_user.id:
        await callback.answer("❌ شما مجاز به پذیرش این هدیه نیستید.", show_alert=True)
        return
    if gift_row.accepted:
        await callback.answer("ℹ️ این هدیه قبلاً پذیرفته شده است.", show_alert=True)
        return

    # Handle subscription gifts specially
    if gift_row.gift_type == "subscription":
        from app.core.settings import PLANS
        from app.handlers.admin.subscription import process_approved_subscription
        plan_name = gift_row.plan_name
        if not plan_name or plan_name not in PLANS:
            await callback.answer("❌ پلن هدیه نامعتبر است.", show_alert=True)
            return
        # Generate marzban username
        base_username = (receiver.username or receiver.full_name or "gift").replace(" ", "")[:12]
        if not base_username:
            base_username = "gift"
        marzban_username = await generate_unique_username(session, base_username)
        # Create subscription and auto-activate
        from app.database.crud import create_subscription
        sub = await create_subscription(
            db=session,
            user_id=receiver.id,
            marzban_username=marzban_username,
            plan=plan_name,
            receipt_message_id=None,
            referrer_id=None,
            renewal_paid=False,
            renewal_template=None,
            renewal_price=None,
            renewal_requested_at=None,
            renewal_applied=False,
            price=PLANS[plan_name]['price']
        )
        ok = await process_approved_subscription(sub.id, session, callback.bot)
        if not ok:
            await callback.answer("❌ خطا در فعال‌سازی اشتراک هدیه.", show_alert=True)
            return
        # Mark gift accepted
        from datetime import datetime
        gift_row.accepted = True
        gift_row.accepted_at = datetime.utcnow()
        await session.commit()
        # Notify both parties
        try:
            if receiver and receiver.chat_id:
                await callback.bot.send_message(
                    receiver.chat_id,
                    f"✅ هدیه اشتراک را پذیرفتید! پلن: {plan_name}"
                )
            sender = await get_user_by_id(session, gift_row.sender_id)
            if sender and sender.chat_id:
                await callback.bot.send_message(
                    sender.chat_id,
                    f"🎉 هدیه اشتراک شما توسط گیرنده پذیرفته و فعال شد: {plan_name}"
                )
        except Exception:
            pass
        await callback.answer("✅ اشتراک هدیه با موفقیت فعال شد.")
        return

    # Default: credit/loyalty gifts
    gift = await accept_user_gift(session, gift_id)
    if not gift:
        await callback.answer("❌ هدیه یافت نشد یا قبلاً پذیرفته شده است.", show_alert=True)
        return
    try:
        receiver = await get_user_by_id(session, gift.receiver_id)
        sender = await get_user_by_id(session, gift.sender_id)
        if receiver and receiver.chat_id:
            await callback.bot.send_message(
                receiver.chat_id,
                f"✅ هدیه را پذیرفتید!\n\n🎁 نوع: {gift.gift_type}\n💰 مقدار: {gift.gift_value:,}"
            )
        if sender and sender.chat_id:
            await callback.bot.send_message(
                sender.chat_id,
                f"🎉 هدیه شما پذیرفته شد!\n\n👤 گیرنده: {receiver.full_name if receiver else ''}\n🎁 نوع: {gift.gift_type}\n💰 مقدار: {gift.gift_value:,}"
            )
    except Exception:
        pass
    await callback.answer("✅ هدیه با موفقیت پذیرفته شد.")


@router.callback_query(F.data == "enhanced_received_gifts")
async def show_received_gifts(callback: CallbackQuery, session: AsyncSession):
    """Show gifts received by the user."""
    user = await get_user(session, callback.from_user.id)
    if not user:
        await callback.answer("کاربر یافت نشد!")
        return

    gifts = await get_user_gifts(session, user.id, "received")

    if not gifts:
        text = "📋 **هدایای دریافتی**\n\nهنوز هیچ هدیه‌ای دریافت نکرده‌اید!"
        rows = []
    else:
        text = "📋 **هدایای دریافتی**\n\n"
        rows = []
        pending_buttons = []
        for i, gift in enumerate(gifts, 1):
            sender_name = gift.sender.full_name or gift.sender.username or f"کاربر {gift.sender.chat_id}"
            status = "✅ پذیرفته شده" if gift.accepted else "⏳ در انتظار"
            date_str = gift.created_at.strftime('%Y/%m/%d %H:%M')

            text += (
                f"{i}. 🎁 از: {sender_name}\n"
                f"   💰 {gift.gift_value:,} {gift.gift_type}\n"
                f"   📝 {gift.message or 'بدون پیام'}\n"
                f"   📅 {date_str}\n"
                f"   {status}\n\n"
            )
            if not gift.accepted and len(pending_buttons) < 8:
                pending_buttons.append([
                    InlineKeyboardButton(text=f"✅ پذیرش هدیه #{i}", callback_data=f"gift_accept:{gift.id}")
                ])

        rows = pending_buttons

    # Footer controls
    rows.append([
        InlineKeyboardButton(text="🔄 بروزرسانی", callback_data="enhanced_received_gifts"),
        InlineKeyboardButton(text="🔙 بازگشت", callback_data="enhanced_rewards_menu")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=rows)

    await callback.message.edit_text(text, reply_markup=keyboard) 
