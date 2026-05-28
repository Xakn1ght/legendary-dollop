from aiogram import F
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.database.cached_crud import get_user_by_referral_code_cached, get_user_with_cache
from app.keyboards.reply import get_main_keyboard
from app.utils.bot_i18n import guess_lang_from_telegram, normalize_lang
from app.utils.logger import handle_errors

from .common import ReferralStates, _create_share_button, router


@router.message(ReferralStates.awaiting_code)
@handle_errors
async def process_invitation_code(message: Message, state: FSMContext, session: AsyncSession, notification_queue):
	# Get saved language or detect it
	state_data = await state.get_data()
	lang = state_data.get("lang") or guess_lang_from_telegram(getattr(message.from_user, "language_code", None))

	# Check if user sent /start again
	if message.text and message.text.startswith("/start"):
		parts = message.text.split(maxsplit=1)
		if len(parts) > 1:
			# They sent /start CODE, extract the code
			referral_code = parts[1].strip()
		else:
			# Just /start without code, remind them
			await message.answer(
				("⚠️ لطفاً کد دعوت خود را ارسال کنید:" if lang == "fa" else "⚠️ Please send your referral code:"),
				parse_mode=ParseMode.HTML
			)
			return
	else:
		referral_code = message.text.strip() if message.text else ""

	# Validate referral code
	if not referral_code:
		await message.answer(
			("⚠️ لطفاً کد دعوت خود را ارسال کنید:" if lang == "fa" else "⚠️ Please send your referral code:"),
			parse_mode=ParseMode.HTML
		)
		return

	referrer = await get_user_by_referral_code_cached(session, referral_code)
	if not referrer:
		error_msg = (
			"❌ کد دعوت نامعتبر است!\n\n"
			"🔄 لطفاً یک کد دعوت معتبر ارسال کنید.\n"
			"💡 <i>از دوستان خود کد دعوت بگیرید.</i>"
			if lang == "fa" else
			"❌ Invalid referral code!\n\n"
			"🔄 Please send a valid referral code.\n"
			"💡 <i>Get a code from your friends.</i>"
		)
		await message.answer(error_msg, parse_mode=ParseMode.HTML)
		return

	chat_id = message.chat.id
	username = message.from_user.username
	full_name = message.from_user.full_name

	# Double-check if user already exists (race condition)
	user = await get_user_with_cache(session, chat_id)
	if user:
		await state.clear()
		already_msg = (
			"✅ شما قبلاً ثبت‌نام کرده‌اید!" if lang == "fa" else "✅ You're already registered!"
		)
		await message.answer(already_msg, reply_markup=get_main_keyboard(message.chat.id, is_admin=user.is_admin, lang=lang), parse_mode=ParseMode.HTML)
		return

	# Create user with language (must run when user did not exist — was wrongly nested under `if user:`)
	user = await crud.create_user(session, chat_id, username, full_name, language=lang)
	await crud.create_referral(session, referrer_id=referrer.id, referee_id=user.id)

	# Notify referrer FIRST to ensure correct message order
	referrer_lang = normalize_lang(getattr(referrer, "language", None))
	try:
		notify_msg = (
			"🎉 یک کاربر جدید با کد دعوت شما عضو شد!\n\n"
			f"👤 نام کاربر: {full_name or username or chat_id}\n"
			"🎁 اگر این کاربر خرید انجام دهد، بن پاداش برای شما فعال می‌شود."
			if referrer_lang == "fa" else
			"🎉 A new user joined with your referral code!\n\n"
			f"👤 User: {full_name or username or chat_id}\n"
			"🎁 If they make a purchase, you’ll get a reward voucher."
		)
		await message.bot.send_message(referrer.chat_id, notify_msg, parse_mode=ParseMode.HTML)
	except Exception:
		pass

	# Check if user was trying to do something specific (like add subscription)
	return_to = state_data.get("return_to")
	if return_to == "add_subscription":
		# Redirect back to add subscription flow
		from app.handlers.user.add_subscription import AddSubState

		await state.set_state(AddSubState.link)
		await message.answer(
			(
				"✅ ثبت‌نام موفقیت‌آمیز بود!\n\n"
				+ ("لطفاً لینک اشتراک خود را ارسال کنید:" if lang == "fa" else "Please send your subscription link:")
			)
			if lang == "fa"
			else "✅ Registration successful!\n\nPlease send your subscription link:",
			reply_markup=get_main_keyboard(message.chat.id, is_admin=user.is_admin, lang=lang),
		)
		return

	await state.clear()

	# Welcome message for new user
	referrer_name = referrer.username or referrer.full_name or "someone"
	welcome_text = (
		f"🎉 خوش آمدی {full_name}!\n\n"
		f"✅ با موفقیت با دعوت @{referrer_name} عضو شدید.\n\n"
		f"🎫 کد دعوت شما: <code>{user.referral_code}</code>\n"
		"👆 این کد را با دوستان خود به اشتراک بگذارید!\n\n"
		"🚀 از منوی زیر استفاده کنید."
		if lang == "fa" else
		f"🎉 Welcome {full_name}!\n\n"
		f"✅ You successfully joined via @{referrer_name}'s invite.\n\n"
		f"🎫 Your referral code: <code>{user.referral_code}</code>\n"
		"👆 Share this with your friends!\n\n"
		"🚀 Use the menu below to get started."
	)
	keyboard = InlineKeyboardMarkup(
		inline_keyboard=[
			[InlineKeyboardButton(
				text=("🎁 باز کردن منوی پاداش" if lang == "fa" else "🎁 Open Rewards Menu"),
				callback_data="open_enhanced_rewards"
			)],
			[_create_share_button(message.bot, user.referral_code, lang)]
		]
	)
	await message.answer(welcome_text, reply_markup=keyboard, parse_mode=ParseMode.HTML) 
