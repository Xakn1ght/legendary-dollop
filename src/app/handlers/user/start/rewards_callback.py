from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.cached_crud import get_user_with_cache
from app.utils.logger import bot_logger, handle_errors

from .common import router


@router.callback_query(lambda c: c.data == "open_enhanced_rewards")
@handle_errors
async def open_enhanced_rewards_callback(callback: CallbackQuery, session: AsyncSession, notification_queue):
	user_chat_id = callback.from_user.id
	bot_logger.info(f"[CHALLENGE_DEBUG] Handling daily challenge for user chat_id:{user_chat_id} in open_enhanced_rewards_callback.")
	user = await get_user_with_cache(session, user_chat_id)
	if not user:
		from app.utils.bot_i18n import guess_lang_from_telegram, t
		lang = guess_lang_from_telegram(getattr(callback.from_user, "language_code", None))
		await callback.answer(t(lang, "user_not_found"), show_alert=True)
		return

	# Record daily login
	from app.database.crud import (
		check_and_award_achievements,
		ensure_today_daily_challenge,
		record_daily_login,
		update_challenge_progress,
	)
	from app.handlers.user.rewards.menu import show_enhanced_rewards_menu

	# Record login (returns user, is_new) - MUST use user.id (PK), not user_chat_id
	_user_obj, _is_new_login = await record_daily_login(session, user.id)

	# Only apply daily-login challenge progress and related achievements once per UTC day.
	if _is_new_login:
		# Re-evaluate today's daily challenge progress and send notification if just completed
		daily_challenge = await ensure_today_daily_challenge(session)
		if daily_challenge:
			bot_logger.info(f"[CHALLENGE_DEBUG] Daily challenge found: {daily_challenge.id}. Updating progress for user:{user.id}.")
			_uc, _just_completed = await update_challenge_progress(
				session, user.id, daily_challenge.id, 1
			)
			bot_logger.info(f"[CHALLENGE_DEBUG] Daily challenge for user:{user.id} - just_completed: {_just_completed}")
		else:
			bot_logger.warning("[CHALLENGE_DEBUG] No active daily challenge found.")

		# Achievement checks (XP, streak etc.) - MUST use user.id (PK)
		await check_and_award_achievements(session, user.id, "logins", _user_obj.login_streak)

	await show_enhanced_rewards_menu(callback, session)

	await callback.answer()
