from datetime import datetime, timedelta

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.services.pasarguard import pasarguard_api
from app.utils.logger import bot_logger
from app.utils.text_format import to_persian_digits

from .common import _patch_panel_user, router


@router.callback_query(F.data.startswith("starchoice_"))
async def handle_star_choice(callback: CallbackQuery, session: AsyncSession):
    """Handle user's choice for star tier rewards"""
    try:
        parts = callback.data.split("_")
        claim_id = int(parts[1])
        choice_type = parts[2]
        choice_val = parts[3]
    except (IndexError, ValueError):
        await callback.answer("درخواست نامعتبر", show_alert=True)
        return

    user = await crud.get_user(session, callback.from_user.id)
    claim = await crud.get_user_star_reward_claim_by_id(session, claim_id)

    if not claim or not user or claim.user_id != user.id or claim.status != "offered":
        await callback.answer("این جایزه در دسترس نیست", show_alert=True)
        return

    success = False
    message = ""

    if choice_type == "credit":
        credit_amt = int(choice_val)
        await crud.add_credit(session, user.id, credit_amt)
        await crud.add_reward_history(
            session,
            user.id,
            "credit",
            credit_amt,
            "star_tier",
            claim.tier_id,
            notes="Choice reward",
        )
        message = f"✅ {credit_amt:,} تومان به کیف پول شما افزوده شد!"
        success = True

    elif choice_type == "discount":
        discount_pct = int(choice_val)
        expiration = datetime.utcnow() + timedelta(days=60)
        await crud.add_user_discount(
            session, user.id, discount_pct, expiration, source=claim.tier.title
        )
        await crud.add_reward_history(
            session,
            user.id,
            "discount_percent",
            discount_pct,
            "star_tier",
            claim.tier_id,
            notes="Choice reward, 60 days",
        )
        message = f"✅ تخفیف {discount_pct}% برای ۶۰ روز آینده فعال شد!"
        success = True

    elif choice_type == "days":
        days = int(choice_val)
        active_subs = await crud.get_user_active_subscriptions(session, user.id)
        if not active_subs:
            await callback.answer(
                "شما سرویس فعالی ندارید. ابتدا یک سرویس خریداری کنید.",
                show_alert=True,
            )
            return

        sub = active_subs[0]
        user_info = await pasarguard_api.get_user_info(sub.marzban_username)
        if user_info:
            current_expire = user_info.get("expire") or 0
            new_expire = current_expire + (days * 24 * 60 * 60)
            if await _patch_panel_user(sub.marzban_username, {"expire": new_expire}):
                await crud.add_reward_history(
                    session,
                    user.id,
                    "extra_days",
                    days,
                    "star_tier",
                    claim.tier_id,
                    notes=f"Choice reward, applied to {sub.marzban_username}",
                )
                message = f"✅ {days} روز به سرویس شما افزوده شد!"
                success = True

    elif choice_type == "plan":
        gb = int(choice_val)
        credit_value = gb * 3250
        await crud.add_credit(session, user.id, credit_value)
        await crud.add_reward_history(
            session,
            user.id,
            "credit",
            credit_value,
            "star_tier",
            claim.tier_id,
            notes=f"Free {gb}GB plan converted to credits",
        )
        message = (
            f"✅ معادل پلن {gb}GB ({credit_value:,} تومان) به کیف پول شما افزوده شد!"
        )
        success = True

    if success:
        claim.status = "claimed"
        claim.claimed_at = datetime.utcnow()
        claim.chosen_reward_type = choice_type
        await session.commit()

        await callback.message.edit_text(message)
        await callback.answer("✅ جایزه دریافت شد!", show_alert=False)
    else:
        await callback.answer("خطا در دریافت جایزه", show_alert=True)


@router.callback_query(F.data.startswith("claim_star_reward_"))
async def claim_star_reward(callback: CallbackQuery, session: AsyncSession):
    claim_id = int(callback.data.split("_")[-1])
    claim = await crud.get_user_star_reward_claim_by_id(session, claim_id)
    user = await crud.get_user(session, callback.from_user.id)
    if (
        (not claim)
        or (not user)
        or (claim.user_id != user.id)
        or claim.status != "offered"
        or claim.expires_at < datetime.utcnow()
    ):
        await callback.answer(
            "این جایزه در دسترس نیست یا منقضی شده است.", show_alert=True
        )
        return

    success = await _apply_star_reward(callback, session, claim, user)
    if success:
        await callback.answer("جایزه با موفقیت دریافت شد!", show_alert=True)
        from ..wallet import show_wallet

        await show_wallet(callback, session)
    else:
        await callback.answer("خطا در دریافت جایزه.", show_alert=True)


async def _apply_star_reward(callback: CallbackQuery, session: AsyncSession, claim, user) -> bool:
    tier = claim.tier
    reward_type = tier.reward_type
    reward_value = tier.reward_value

    if reward_type == "credit":
        try:
            credit_amount = int(reward_value)
            await crud.add_credit(session, claim.user_id, credit_amount)
            await crud.add_reward_history(
                session,
                claim.user_id,
                "credit",
                credit_amount,
                "star_tier",
                claim.tier_id,
            )
            bot_logger.info(f"Added {credit_amount} credit to user {claim.user_id}")

            claim.status = "claimed"
            claim.claimed_at = datetime.utcnow()
            await session.commit()

        except ValueError:
            bot_logger.error(
                f"Invalid credit amount '{reward_value}' for tier {claim.tier_id}"
            )
            return False

    elif reward_type == "discount_percent":
        try:
            discount_percent = int(reward_value)
            expiration_days = 30
            expiration = datetime.utcnow() + timedelta(days=expiration_days)
            await crud.add_user_discount(
                session,
                claim.user_id,
                discount_percent,
                expiration,
                source=claim.tier.title,
            )
            await crud.add_reward_history(
                session,
                claim.user_id,
                "discount_percent",
                discount_percent,
                "star_tier",
                claim.tier_id,
                notes=f"Expires in {expiration_days} days",
            )
            bot_logger.info(
                f"Granted {discount_percent}% discount for {expiration_days} days to user {claim.user_id}"
            )

            claim.status = "claimed"
            claim.claimed_at = datetime.utcnow()
            await session.commit()

        except ValueError:
            bot_logger.error(
                f"Invalid discount percentage '{reward_value}' for tier {claim.tier_id}"
            )
            return False

    elif reward_type == "extra_days":
        try:
            days_to_add = int(reward_value)
            active_subs = await crud.get_user_active_subscriptions(session, user.id)

            if not active_subs:
                claim.status = "pending_subscription"
                claim.expires_at = datetime.utcnow() + timedelta(days=7)
                await session.commit()
                await callback.message.edit_text(
                    "🎉 جایزه ۱۰ روز اعتبار هدیه برای شما رزرو شد!\n\n"
                    "شما در حال حاضر اشتراک فعالی ندارید. این جایزه تا ۷ روز آینده معتبر است و به محض خرید یا افزودن اشتراک جدید، به صورت خودکار به آن اضافه خواهد شد."
                )
                return True

            if len(active_subs) == 1:
                sub = active_subs[0]
                user_info = await pasarguard_api.get_user_info(sub.marzban_username)
                if not user_info:
                    await callback.answer("خطا در دریافت اطلاعات سرویس.", show_alert=True)
                    return False

                current_expire_ts = user_info.get("expire") or 0
                new_expire = current_expire_ts + days_to_add * 24 * 60 * 60

                if not await _patch_panel_user(
                    sub.marzban_username, {"expire": new_expire}
                ):
                    await callback.answer("خطا در افزایش زمان اعتبار.", show_alert=True)
                    return False

                claim.status = "claimed"
                claim.claimed_at = datetime.utcnow()
                await session.commit()

                await crud.add_reward_history(
                    session,
                    claim.user_id,
                    "extra_days",
                    days_to_add,
                    "star_tier",
                    claim.tier_id,
                    notes=f"Applied to {sub.marzban_username}",
                )
                await callback.message.edit_text(
                    f"✅ تبریک! {to_persian_digits(days_to_add)} روز به اعتبار سرویس {sub.marzban_username} شما اضافه شد."
                )
                return True

            buttons = []
            for sub in active_subs:
                buttons.append(
                    [
                        InlineKeyboardButton(
                            text=f"🚀 {sub.marzban_username}",
                            callback_data=f"apply_days_{claim.id}_{sub.id}",
                        )
                    ]
                )

            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            await callback.message.edit_text(
                "شما چند اشتراک فعال دارید. لطفاً انتخاب کنید که ۱۰ روز اعتبار هدیه به کدام یک اضافه شود:",
                reply_markup=keyboard,
            )
            return True

        except ValueError:
            bot_logger.error(
                f"Invalid extra_days value '{reward_value}' for tier {claim.tier_id}"
            )
            return False

    elif reward_type == "choice":
        try:
            options = reward_value.split("|")
            keyboard = []
            for option in options:
                option_type, option_val = option.split(":")
                if option_type == "credit":
                    text = f"💰 {int(option_val):,} تومان"
                elif option_type == "discount":
                    text = f"🎫 {option_val}% تخفیف"
                elif option_type == "days":
                    text = f"📅 {option_val} روز اضافه"
                elif option_type == "plan":
                    text = f"📦 پلن {option_val}GB رایگان"
                else:
                    text = option

                keyboard.append(
                    [
                        InlineKeyboardButton(
                            text=text,
                            callback_data=f"starchoice_{claim.id}_{option_type}_{option_val}",
                        )
                    ]
                )

            keyboard.append(
                [InlineKeyboardButton(text="🔙 بازگشت", callback_data="show_star_levels")]
            )
            kb = InlineKeyboardMarkup(inline_keyboard=keyboard)

            await callback.message.edit_text(
                f"🎉 تبریک! شما به {tier.title} رسیدید!\n\n"
                f"{tier.description}\n\n"
                "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
                reply_markup=kb,
            )
            return True
        except Exception as e:
            bot_logger.error(f"Error parsing choice reward: {e}")
            return False

    elif reward_type == "bundle":
        try:
            options = reward_value.split("|")
            rewards_given = []

            for option in options:
                if ":" in option:
                    option_type, option_val = option.split(":")
                else:
                    option_type = option
                    option_val = None

                if option_type == "credit":
                    credit_amt = int(option_val)
                    await crud.add_credit(session, claim.user_id, credit_amt)
                    await crud.add_reward_history(
                        session,
                        claim.user_id,
                        "credit",
                        credit_amt,
                        "star_tier",
                        claim.tier_id,
                    )
                    rewards_given.append(f"💰 {credit_amt:,} تومان")

                elif option_type == "plan":
                    gb = int(option_val)
                    credit_value = gb * 3250
                    await crud.add_credit(session, claim.user_id, credit_value)
                    await crud.add_reward_history(
                        session,
                        claim.user_id,
                        "credit",
                        credit_value,
                        "star_tier",
                        claim.tier_id,
                        notes=f"Free {gb}GB plan as credits",
                    )
                    rewards_given.append(f"📦 پلن {option_val}GB رایگان ({credit_value:,} تومان)")

                elif option_type == "vip":
                    if option_val == "lifetime":
                        await crud.set_vip_status(session, claim.user_id, True, None)
                        await crud.add_reward_history(
                            session,
                            claim.user_id,
                            "vip",
                            0,
                            "star_tier",
                            claim.tier_id,
                            notes="Lifetime VIP",
                        )
                        rewards_given.append("👑 VIP مادام‌العمر")
                    else:
                        days = int(option_val)
                        await crud.set_vip_status(session, claim.user_id, True, days)
                        await crud.add_reward_history(
                            session,
                            claim.user_id,
                            "vip",
                            days,
                            "star_tier",
                            claim.tier_id,
                            notes=f"VIP for {days} days",
                        )
                        rewards_given.append(f"👑 VIP ({option_val} روز)")

                elif option_type == "custom_name":
                    await crud.set_custom_username(
                        session,
                        claim.user_id,
                        f"⭐ {user.full_name or user.username or 'VIP'}",
                    )
                    await crud.add_reward_history(
                        session,
                        claim.user_id,
                        "custom_name",
                        1,
                        "star_tier",
                        claim.tier_id,
                        notes="Custom name unlocked",
                    )
                    rewards_given.append("🎨 نام کاربری سفارشی")

            claim.status = "claimed"
            claim.claimed_at = datetime.utcnow()
            await session.commit()

            rewards_text = "\n".join(rewards_given)
            await callback.message.edit_text(
                f"✅ تبریک! شما جوایز زیر را دریافت کردید:\n\n{rewards_text}"
            )
            return True
        except Exception as e:
            bot_logger.error(f"Error applying bundle reward: {e}")
            return False

    await callback.message.edit_text(
        f"✅ تبریک! شما جایزه زیر را دریافت کردید: {tier.description}"
    )
    return True


@router.callback_query(F.data.startswith("apply_days_"))
async def apply_days_to_subscription(callback: CallbackQuery, session: AsyncSession):
    """Handles the user's choice of subscription to apply extra days to."""
    try:
        parts = callback.data.split("_")
        # apply_days_<claim_id>_<sub_id>
        claim_id = int(parts[2])
        sub_id = int(parts[3])
    except (ValueError, IndexError):
        await callback.answer("درخواست نامعتبر.", show_alert=True)
        return

    user = await crud.get_user(session, callback.from_user.id)
    claim = await crud.get_user_star_reward_claim_by_id(session, claim_id)
    sub = await crud.get_subscription_by_id(session, sub_id)

    if not all([user, claim, sub]):
        await callback.answer("اطلاعات یافت نشد.", show_alert=True)
        return
    if claim.user_id != user.id or sub.user_id != user.id:
        await callback.answer("این درخواست متعلق به شما نیست.", show_alert=True)
        return
    if claim.status != "offered":
        await callback.answer(
            "این جایزه قبلاً استفاده شده یا در دسترس نیست.", show_alert=True
        )
        return

    tier = claim.tier
    if tier.reward_type != "extra_days":
        await callback.answer("نوع جایزه نامعتبر است.", show_alert=True)
        return

    try:
        days_to_add = int(tier.reward_value)
        user_info = await pasarguard_api.get_user_info(sub.marzban_username)
        if not user_info:
            await callback.answer("خطا در دریافت اطلاعات سرویس.", show_alert=True)
            return

        current_expire_ts = user_info.get("expire") or 0
        new_expire = current_expire_ts + days_to_add * 24 * 60 * 60

        if not await _patch_panel_user(
            sub.marzban_username, {"expire": new_expire}
        ):
            await callback.answer("خطا در افزایش زمان اعتبار.", show_alert=True)
            return

        claim.status = "claimed"
        claim.claimed_at = datetime.utcnow()
        await session.commit()

        await crud.add_reward_history(
            session,
            claim.user_id,
            "extra_days",
            days_to_add,
            "star_tier",
            claim.tier_id,
            notes=f"Applied to {sub.marzban_username}",
        )
        await callback.message.edit_text(
            f"✅ تبریک! {to_persian_digits(days_to_add)} روز به اعتبار سرویس {sub.marzban_username} شما اضافه شد."
        )

    except ValueError:
        bot_logger.error(
            f"Invalid extra_days value '{tier.reward_value}' for tier {claim.tier_id}"
        )
        await callback.answer("خطا در پردازش جایزه.", show_alert=True)
    except Exception as e:
        bot_logger.error(
            f"Error applying extra days to sub {sub_id} for claim {claim_id}: {e}"
        )
        await callback.answer("یک خطای پیش‌بینی‌نشده رخ داد.", show_alert=True)
