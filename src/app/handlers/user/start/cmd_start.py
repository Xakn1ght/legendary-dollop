from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import ADMIN_ID
from app.database import crud
from app.database.cached_crud import create_user_cached, get_user_with_cache
from app.keyboards.reply import get_main_keyboard
from app.utils.bot_i18n import guess_lang_from_telegram, normalize_lang, set_cached_lang
from app.utils.logger import handle_errors
from app.utils.premium_emoji import answer_premium

from .common import ReferralStates, router


@router.message(CommandStart())
@handle_errors
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession, notification_queue):
	# Always reset any ongoing conversations or wizards
	try:
		await state.clear()
	except Exception:
		pass

	chat_id = message.chat.id
	username = message.from_user.username
	full_name = message.from_user.full_name
	lang = guess_lang_from_telegram(getattr(message.from_user, "language_code", None))
	set_cached_lang(chat_id, lang)

	user = await get_user_with_cache(session, chat_id)
	if not user:
		# 1) Always allow the admin (defined in settings) to join without any referral requirements.
		if chat_id == ADMIN_ID:
			user = await create_user_cached(session, chat_id, username, full_name, language=lang)
			await message.answer(
				(f"سلام ادمین {full_name}! 👑\nاز منوی زیر استفاده کنید." if lang == "fa" else f"Hi admin {full_name}! 👑\nUse the menu below."),
				reply_markup=get_main_keyboard(message.chat.id, is_admin=True, lang=lang),
				parse_mode=ParseMode.HTML,
			)
			return

		# 2) For new users, ask for language selection first
		# Store user info in state for later use (including start text for referral code)
		await state.update_data(
			chat_id=chat_id,
			username=username,
			full_name=full_name,
			detected_lang=lang,
			start_text=message.text  # Store original /start text to check for referral code
		)
		await state.set_state(ReferralStates.awaiting_language)
		
		# Language selection keyboard
		lang_keyboard = InlineKeyboardMarkup(
			inline_keyboard=[
				[
					InlineKeyboardButton(text="🇮🇷 فارسی", callback_data="lang_fa"),
					InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")
				]
			]
		)
		
		lang_msg = (
			"👋 سلام! خوش آمدید!\n\n"
			"🌐 لطفاً زبان خود را انتخاب کنید:\n\n"
			"👋 Hello! Welcome!\n\n"
			"🌐 Please select your language:"
		)
		
		await answer_premium(message, lang_msg, reply_markup=lang_keyboard)
		return

	else:
		# Cache persisted language (for keyboards)
		try:
			lang = normalize_lang(getattr(user, "language", None) or lang)
			set_cached_lang(chat_id, lang)
		except Exception:
			pass
		
		# Check for VIP purchase deep link
		parts = message.text.split(maxsplit=1)
		payload = parts[1].strip().lower() if len(parts) > 1 else None
		
		if payload == 'vip':
			# Show VIP purchase options
			is_vip = await crud.is_user_vip(session, user.id)
			if is_vip:
				# Already VIP - show status
				vip_msg = (
					"👑 شما در حال حاضر عضو VIP هستید!\n\n"
					"✅ مزایای VIP شما:\n"
					"• ۲۰٪ تخفیف روی همه خریدها\n"
					"• دسترسی به پلن‌های اختصاصی\n"
					"• پشتیبانی VIP با اولویت بالا"
					if lang == "fa" else
					"👑 You are already a VIP member!\n\n"
					"✅ Your VIP benefits:\n"
					"• 20% discount on all purchases\n"
					"• Access to exclusive plans\n"
					"• Priority VIP support"
				)
			else:
				# Not VIP - show purchase options
				vip_msg = (
					"👑 <b>ارتقا به VIP</b>\n\n"
					"مزایای عضویت VIP:\n"
					"• ۲۰٪ تخفیف روی همه خریدها\n"
					"• دسترسی به پلن‌های اختصاصی\n"
					"• پشتیبانی VIP با اولویت بالا\n\n"
					"برای خرید VIP از داخل داشبورد اقدام کنید."
					if lang == "fa" else
					"👑 <b>Upgrade to VIP</b>\n\n"
					"VIP membership benefits:\n"
					"• 20% discount on all purchases\n"
					"• Access to exclusive plans\n"
					"• Priority VIP support\n\n"
					"Open the dashboard to purchase VIP."
				)
			
			kb = InlineKeyboardMarkup(inline_keyboard=[
				[InlineKeyboardButton(
					text="🔙 بازگشت" if lang == "fa" else "🔙 Back",
					callback_data="close_menu"
				)]
			])
			await message.answer(vip_msg, reply_markup=kb, parse_mode=ParseMode.HTML)
			return
		
		# Enhanced, user-friendly summary: active accounts, nearest expiry, remaining data, wallet
		stats_line = ""
		try:
			import time

			from app.services.pasarguard import pasarguard_api
			user_obj = await crud.get_user(session, chat_id)
			subs = await crud.get_user_subscriptions(session, user_obj.id)
			active_subs = [s for s in subs if (getattr(s, 'status', None) or '').lower() == 'active']
			active_count = len(active_subs)
			credit_amount = getattr(user_obj, 'credit', 0) or 0
			nearest_days = None
			total_remaining_bytes = 0
			has_unlimited = False
			now_ts = int(time.time())
			for s in active_subs:
				if not getattr(s, 'marzban_username', None):
					continue
				# Read-only summary — the short-TTL cached path spares the panel
				# a full admin fetch per subscription on every /start.
				info = await pasarguard_api.get_fast_user_info(s.marzban_username, getattr(s, 'sub_token', None))
				if not info:
					continue
				# Expiry (seconds since epoch)
				expire_ts = info.get('expire')
				if expire_ts:
					days_left = max(0, int((expire_ts - now_ts) / 86400))
					nearest_days = days_left if nearest_days is None else min(nearest_days, days_left)
				# Remaining traffic
				data_limit = info.get('data_limit')
				used = info.get('used_traffic') or 0
				if data_limit is None:
					has_unlimited = True
				else:
					remaining = max(0, int(data_limit) - int(used))
					total_remaining_bytes += remaining
			
			# Build parts based on language
			if lang == "fa":
				parts = []
				parts.append(f"{active_count} اکانت فعال" if active_count > 0 else "بدون اکانت فعال")
				if nearest_days is not None:
					parts.append(f"نزدیک‌ترین انقضا: {nearest_days} روز")
				if has_unlimited:
					parts.append("حجم: نامحدود")
				elif total_remaining_bytes > 0:
					remaining_gb = total_remaining_bytes / (1024 ** 3)
					# Under 1 GB reads in MB: the free trial is 250 MB and
					# "0.2GB" both understates it and disagrees with the
					# subscription screen.
					if remaining_gb < 1:
						parts.append(f"حجم باقیمانده: {round(remaining_gb * 1024)}MB")
					else:
						parts.append(f"حجم باقیمانده: {remaining_gb:.1f}GB")
				parts.append(f"کیف‌پول: {credit_amount:,} تومان")
				stats_line = "\n📊 وضعیت حساب: " + " | ".join(parts)
			else:
				parts = []
				parts.append(f"{active_count} active" if active_count > 0 else "No active services")
				if nearest_days is not None:
					parts.append(f"Expires in: {nearest_days} days")
				if has_unlimited:
					parts.append("Data: Unlimited")
				elif total_remaining_bytes > 0:
					remaining_gb = total_remaining_bytes / (1024 ** 3)
					parts.append(f"Remaining: {remaining_gb:.1f}GB")
				parts.append(f"Wallet: {credit_amount:,} T")
				stats_line = "\n📊 Account: " + " | ".join(parts)
		except Exception:
			stats_line = ""

		# Check VIP status for badge
		is_vip = await crud.is_user_vip(session, user.id) if user else False
		vip_badge = "👑 " if is_vip else ""
		vip_line = "\n👑 <b>VIP</b> - تخفیف ۲۰٪ روی خرید" if is_vip and lang == "fa" else ("\n👑 <b>VIP</b> - 20% discount on purchases" if is_vip else "")

		welcome_message = (
			f"{vip_badge}خوش آمدی {full_name}! 🤩\n"
			f"{stats_line}{vip_line}\n\n"
			"از منوی زیر برای مدیریت سرویس‌ها یا خرید اشتراک جدید استفاده کنید."
			if lang == "fa" else
			f"{vip_badge}Welcome back {full_name}! 🤩\n"
			f"{stats_line}{vip_line}\n\n"
			"Use the menu below to manage your services or purchase new subscriptions."
		)
	
	# Check if user is admin for keyboard
	is_admin = user.is_admin if user else False
	
	await answer_premium(
		message,
		welcome_message,
		reply_markup=get_main_keyboard(message.chat.id, is_admin=is_admin, lang=lang),
	)
