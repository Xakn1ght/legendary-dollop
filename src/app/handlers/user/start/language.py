from html import escape

from aiogram import F
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.database.cached_crud import create_user_cached, get_user_by_referral_code_cached, get_user_with_cache
from app.keyboards.reply import get_main_keyboard
from app.utils.bot_i18n import normalize_lang, set_cached_lang, t
from app.utils.logger import handle_errors
from app.utils.premium_emoji import edit_premium, send_premium

from .common import ReferralStates, _create_share_button, _is_og_user, router


@router.callback_query(F.data.in_(["lang_fa", "lang_en"]))
@handle_errors
async def process_language_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession, notification_queue):
	"""Process language selection and proceed with user creation flow"""
	selected_lang = "fa" if callback.data == "lang_fa" else "en"
	
	# Get stored user info from state
	data = await state.get_data()
	chat_id = data.get("chat_id")
	username = data.get("username")
	full_name = data.get("full_name")
	
	if not chat_id:
		await callback.answer("❌ خطا در دریافت اطلاعات", show_alert=True)
		return
	
	# Update cached language
	set_cached_lang(chat_id, selected_lang)
	
	# Check if user already exists (race condition)
	user = await get_user_with_cache(session, chat_id)
	if user:
		await state.clear()
		# Show a nicer welcome message with stats for returning users
		full_name = user.full_name or user.username or "کاربر"
		
		# Get account stats
		stats_line = ""
		try:

			subs = await crud.get_user_subscriptions(session, user.id)
			active_subs = [s for s in subs if (getattr(s, 'status', None) or '').lower() == 'active']
			active_count = len(active_subs)
			credit_amount = getattr(user, 'credit', 0) or 0
			sub_credit_amount = getattr(user, 'subscription_credit', 0) or 0
			
			if selected_lang == "fa":
				parts = []
				parts.append(f"{active_count} سرویس فعال" if active_count > 0 else "بدون سرویس فعال")
				if credit_amount > 0 or sub_credit_amount > 0:
					parts.append(f"کیف‌پول: {credit_amount:,}T")
				stats_line = "\n📊 " + " | ".join(parts)
			else:
				parts = []
				parts.append(f"{active_count} active" if active_count > 0 else "No active services")
				if credit_amount > 0 or sub_credit_amount > 0:
					parts.append(f"Wallet: {credit_amount:,}T")
				stats_line = "\n📊 " + " | ".join(parts)
		except Exception:
			pass
		
		welcome_msg = (
			f"👋 خوش برگشتی {full_name}!\n"
			f"{stats_line}\n\n"
			f"🎫 کد دعوت شما: <code>{user.referral_code}</code>\n\n"
			"از منوی زیر استفاده کنید."
			if selected_lang == "fa" else
			f"👋 Welcome back {full_name}!\n"
			f"{stats_line}\n\n"
			f"🎫 Your referral code: <code>{user.referral_code}</code>\n\n"
			"Use the menu below."
		)
		
		await edit_premium(callback.message, welcome_msg)
		await callback.message.answer(
			("از منوی زیر استفاده کنید:" if selected_lang == "fa" else "Use the menu below:"),
			reply_markup=get_main_keyboard(chat_id, is_admin=user.is_admin, lang=selected_lang),
			parse_mode=ParseMode.HTML,
		)
		await callback.answer()
		return
	
	# Check if user is OG (existing customer) - skip referral requirement
	is_og = _is_og_user(chat_id, username)
	if is_og:
		# Create OG user without referral requirement
		user = await create_user_cached(session, chat_id, username, full_name, language=selected_lang)
		
		# Special welcome message for OG users
		welcome_msg = (
			f"🚀 خوش آمدی {full_name}! 👋\n\n"
			"✨ شما یکی از کاربران قدیمی ما هستید!\n"
			"🎁 از تمام امکانات ربات به صورت رایگان استفاده کنید.\n\n"
			f"🎫 کد دعوت شما: <code>{user.referral_code}</code>\n"
			"👆 این کد را با دوستان خود به اشتراک بگذارید!\n\n"
			"🚀 از منوی زیر استفاده کنید."
			if selected_lang == "fa"
			else (
				f"🚀 Welcome back {full_name}! 👋\n\n"
				"✨ You're one of our OG users!\n"
				"🎁 Enjoy all bot features for free.\n\n"
				f"🎫 Your referral code: <code>{user.referral_code}</code>\n"
				"👆 Share this with your friends!\n\n"
				"🚀 Use the menu below to get started."
			)
		)
		
		keyboard = InlineKeyboardMarkup(
			inline_keyboard=[
				[
					InlineKeyboardButton(
						text=("🛒 خرید سرویس" if selected_lang == "fa" else "🛒 Buy a Plan"),
						callback_data="welcome_buy"
					),
					InlineKeyboardButton(
						text=("➕ افزودن اشتراک" if selected_lang == "fa" else "➕ Add Subscription"),
						callback_data="welcome_addsub"
					),
				],
				[_create_share_button(callback.message.bot, user.referral_code, selected_lang)]
			]
		)
		
		await edit_premium(callback.message, welcome_msg, reply_markup=keyboard)
		await state.clear()
		await callback.answer()
		return
	
	# Not OG - need referral code
	# Check if /start had a referral code
	start_text = data.get("start_text", "")
	parts = start_text.split(maxsplit=1) if start_text else []
	referral_code = parts[1].strip() if len(parts) > 1 else None
	
	# Handle special deep links
	if referral_code and referral_code.lower() == 'vip':
		await callback.message.edit_text(
			(
				"👑 برای خرید VIP، ابتدا باید در ربات ثبت‌نام کنید.\n\n"
				"🔐 لطفاً کد دعوت خود را ارسال کنید تا بتوانید از ربات استفاده کنید.\n"
				"💡 کد دعوت را از دوستان خود بگیرید."
				if selected_lang == "fa" else
				"👑 To purchase VIP, you need to register first.\n\n"
				"🔐 Please send your referral code to use this bot.\n"
				"💡 Get a referral code from your friends."
			),
			parse_mode=ParseMode.HTML
		)
		await state.set_state(ReferralStates.awaiting_code)
		await state.update_data(lang=selected_lang)
		await callback.answer()
		return
	
	if referral_code:
		referrer = await get_user_by_referral_code_cached(session, referral_code)
		if referrer:
			user = await create_user_cached(session, chat_id, username, full_name, language=selected_lang)
			await crud.create_referral(session, referrer_id=referrer.id, referee_id=user.id)

			try:
				referrer_lang = normalize_lang(getattr(referrer, "language", None))
				await send_premium(
					callback.message.bot,
					referrer.chat_id,
					t(referrer_lang, "referral_new_user_dm").format(
						name=escape(str(full_name or username or chat_id))
					),
				)
			except Exception:
				pass

			if selected_lang == "fa":
				welcome_message = (
					f"سلام {full_name}! 🥳\n\n"
					f"شما با کد دعوت {referral_code} عضو شدید.\n"
					f"کد دعوت شما: <code>{user.referral_code}</code>\n\n"
					"از منوی زیر استفاده کنید."
				)
			else:
				welcome_message = (
					f"Hi {full_name}! 🥳\n\n"
					f"You joined with invite code {referral_code}.\n"
					f"Your invite code: <code>{user.referral_code}</code>\n\n"
					"Use the menu below."
				)

			share_keyboard = InlineKeyboardMarkup(
				inline_keyboard=[
					[
						InlineKeyboardButton(
							text=("🛒 خرید سرویس" if selected_lang == "fa" else "🛒 Buy a Plan"),
							callback_data="welcome_buy"
						),
						InlineKeyboardButton(
							text=("➕ افزودن اشتراک" if selected_lang == "fa" else "➕ Add Subscription"),
							callback_data="welcome_addsub"
						),
					],
					[_create_share_button(callback.message.bot, user.referral_code, selected_lang)]
				]
			)

			await edit_premium(callback.message, welcome_message, reply_markup=share_keyboard)
			await callback.message.answer(
				("از منوی زیر استفاده کنید:" if selected_lang == "fa" else "Use the menu below:"),
				reply_markup=get_main_keyboard(chat_id, is_admin=user.is_admin, lang=selected_lang),
				parse_mode=ParseMode.HTML,
			)
			await state.clear()
			await callback.answer()
			return
	
	# No referral code - ask for it
	await callback.message.edit_text(
		(
			f"👋 سلام {full_name}!\n\n"
			"🔐 برای استفاده از این ربات، نیاز به کد دعوت دارید.\n\n"
			"📝 لطفاً کد دعوت خود را ارسال کنید:\n\n"
			"💡 <i>کد دعوت را از دوستان خود بگیرید یا در گروه‌های ما بپرسید.</i>"
			if selected_lang == "fa" else
			f"👋 Hi {full_name}!\n\n"
			"🔐 This bot requires a referral code to use.\n\n"
			"📝 Please send your referral code:\n\n"
			"💡 <i>Get a referral code from friends or ask in our community.</i>"
		),
		parse_mode=ParseMode.HTML
	)
	await state.set_state(ReferralStates.awaiting_code)
	await state.update_data(lang=selected_lang)
	await callback.answer()
