from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.utils.text_format import to_persian_digits

router = Router()

# Loyalty Shop Items (rebalanced: 1 loyalty point = 1 Toman)
# Credits from shop are subscription_credit (only for subscriptions, not cashable)
# Iron rule (2026-06-02): loyalty points are earned by play, so they must not buy VPN
# value. These item types are retired — hidden from the shop and blocked at redemption.
# Status/cosmetic perks (vip, priority_support, custom_username, star*) remain.
RETIRED_LOYALTY_TYPES = {"sub_credit", "plan"}

LOYALTY_SHOP = {
    "sub_credit_small": {
        "cost": 5000,
        "reward": 5000,
        "name": "💳 ۵,۰۰۰ تومان اعتبار اشتراک",
        "type": "sub_credit"
    },
    "sub_credit_medium": {
        "cost": 12000,
        "reward": 12000,
        "name": "💳 ۱۲,۰۰۰ تومان اعتبار اشتراک",
        "type": "sub_credit"
    },
    "sub_credit_large": {
        "cost": 50000,
        "reward": 50000,
        "name": "💳 ۵۰,۰۰۰ تومان اعتبار اشتراک",
        "type": "sub_credit"
    },
    "star_piece": {
        "cost": 2500,
        "reward": 1,
        "name": "⭐ ۱ تکه ستاره",
        "type": "star_piece"
    },
    "star_full": {
        "cost": 40000,
        "reward": 1,
        "name": "🌟 ۱ ستاره کامل",
        "type": "star"
    },
    "plan_10gb": {
        "cost": 32500,
        "reward": "10",
        "name": "📦 پلن ۱۰GB رایگان",
        "type": "plan"
    },
    "plan_20gb": {
        "cost": 65000,
        "reward": "20",
        "name": "📦 پلن ۲۰GB رایگان",
        "type": "plan"
    },
    "priority_support": {
        "cost": 30000,
        "reward": 30,
        "name": "🎧 پشتیبانی ویژه (۳۰ روز)",
        "type": "priority_support"
    },
    "custom_username": {
        "cost": 70000,
        "reward": "permanent",
        "name": "🎨 نام کاربری سفارشی",
        "type": "custom_username"
    },
    "vip_90days": {
        "cost": 180000,
        "reward": 90,
        "name": "👑 VIP (۹۰ روز)",
        "type": "vip"
    },
    "vip_lifetime": {
        "cost": 600000,
        "reward": "lifetime",
        "name": "👑 VIP مادام‌العمر",
        "type": "vip"
    }
}

@router.callback_query(F.data == "loyalty_shop")
async def show_loyalty_shop(callback: CallbackQuery, session: AsyncSession):
    """Display the loyalty shop menu."""
    user = await crud.get_user(session, callback.from_user.id)
    if not user:
        await callback.answer("کاربر یافت نشد!", show_alert=True)
        return
    
    loyalty_points = user.loyalty_points or 0
    
    text = (
        f"💎 <b>فروشگاه امتیاز وفاداری</b>\n\n"
        f"امتیاز شما: <b>{to_persian_digits(f'{loyalty_points:,}')}</b> امتیاز\n"
        f"<i>(هر ۱۰۰۰ امتیاز = ۱,۰۰۰ تومان)</i>\n\n"
        f"با امتیازهای وفاداری خود می‌توانید جوایز زیر را خریداری کنید:\n"
        f"<i>⚠️ اعتبار اشتراک فقط برای خرید سرویس قابل استفاده است.</i>\n"
    )
    
    keyboard = []

    def _render_section(header, item_ids):
        nonlocal text
        rows = [iid for iid in item_ids if LOYALTY_SHOP[iid]["type"] not in RETIRED_LOYALTY_TYPES]
        if not rows:
            return
        text += header
        for item_id in rows:
            item = LOYALTY_SHOP[item_id]
            affordable = "✅" if loyalty_points >= item["cost"] else "🔒"
            cost_str = f"{item['cost']:,}"
            text += f"{affordable} {item['name']} - {to_persian_digits(cost_str)} امتیاز\n"
            if loyalty_points >= item["cost"]:
                keyboard.append([InlineKeyboardButton(text=item['name'], callback_data=f"loyaltyby_{item_id}")])

    # sub_credit / plan items are retired (play must not mint VPN value) → not shown.
    _render_section("\n<b>⭐ ستاره:</b>\n", ["star_piece", "star_full"])
    _render_section("\n<b>🎁 ویژه:</b>\n", ["plan_10gb", "plan_20gb", "priority_support", "custom_username", "vip_90days", "vip_lifetime"])

    keyboard.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="enhanced_rewards_menu")])
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    
    await callback.answer()

@router.callback_query(F.data.startswith("loyaltyby_"))
async def purchase_loyalty_item(callback: CallbackQuery, session: AsyncSession):
    """Handle loyalty shop purchases."""
    item_id = callback.data.replace("loyaltyby_", "")
    
    if item_id not in LOYALTY_SHOP:
        await callback.answer("آیتم نامعتبر!", show_alert=True)
        return
    
    item = LOYALTY_SHOP[item_id]

    # Retired (sub_credit/plan): never grant VPN value for play-earned loyalty points.
    if item["type"] in RETIRED_LOYALTY_TYPES:
        await callback.answer("این جایزه دیگر در دسترس نیست.", show_alert=True)
        return

    user = await crud.get_user(session, callback.from_user.id)

    if not user:
        await callback.answer("کاربر یافت نشد!", show_alert=True)
        return

    # Check if user has enough loyalty points
    if user.loyalty_points < item["cost"]:
        await callback.answer(
            f"امتیاز کافی ندارید! نیاز: {item['cost']:,} - دارید: {user.loyalty_points:,}",
            show_alert=True
        )
        return
    
    # Deduct loyalty points
    user.loyalty_points -= item["cost"]
    
    # Award the item
    message = ""
    if item["type"] == "sub_credit":
        # Give subscription_credit (non-cashable, only for subscriptions)
        await crud.add_subscription_credit(session, user.id, item["reward"], "loyalty_shop", notes=f"Bought {item_id}")
        message = f"✅ {item['reward']:,} تومان اعتبار اشتراک افزوده شد!\n(فقط برای خرید سرویس قابل استفاده است)"
    
    elif item["type"] == "star_piece":
        user.star_pieces = (user.star_pieces or 0) + item["reward"]
        # Check if pieces convert to full star
        if user.star_pieces >= 10:
            user.star_pieces -= 10
            await crud.StarManager.add_stars(session, user.id, 1, "loyalty_shop")
            message = f"✅ تکه ستاره به کیف شما افزوده شد و به یک ستاره کامل تبدیل شد!"
        else:
            message = f"✅ {item['reward']} تکه ستاره افزوده شد! ({user.star_pieces}/10)"
    
    elif item["type"] == "star":
        await crud.StarManager.add_stars(session, user.id, item["reward"], "loyalty_shop")
        message = f"✅ {item['reward']} ستاره به کیف شما افزوده شد!"
    
    elif item["type"] == "plan":
        # Convert to subscription_credit (plan value as non-cashable credit)
        gb = int(item["reward"])
        sub_credits = gb * 3250
        await crud.add_subscription_credit(session, user.id, sub_credits, "loyalty_shop", notes=f"Free {gb}GB plan converted")
        message = f"✅ معادل پلن {gb}GB ({sub_credits:,} تومان اعتبار اشتراک) افزوده شد!\n(فقط برای خرید سرویس قابل استفاده است)"
    
    elif item["type"] in ["priority_support", "vip", "custom_username"]:
        if item["type"] in ["priority_support", "vip"]:
            # VIP is the system-wide "priority support" flag (used by support ticket priority).
            if item["reward"] == "lifetime":
                await crud.set_vip_status(session, user.id, True, None)
                await crud.add_reward_history(
                    session, user.id, "vip", 0, "loyalty_shop", notes=f"Bought {item_id} (lifetime)"
                )
                message = "✅ VIP مادام‌العمر برای شما فعال شد!"
            else:
                days = int(item["reward"])
                now = datetime.utcnow()
                # Extend if already VIP and has an expiry in the future (lifetime stays lifetime).
                if getattr(user, "is_vip", False) and getattr(user, "vip_until", None) is None:
                    message = "✅ شما VIP مادام‌العمر دارید."
                elif getattr(user, "is_vip", False) and getattr(user, "vip_until", None):
                    if user.vip_until > now:
                        user.vip_until = user.vip_until + timedelta(days=days)
                    else:
                        user.vip_until = now + timedelta(days=days)
                    user.is_vip = True
                    await session.commit()
                    await crud.add_reward_history(
                        session, user.id, "vip", days, "loyalty_shop", notes=f"Bought {item_id} (extended)"
                    )
                    message = f"✅ VIP/اولویت پشتیبانی به مدت {to_persian_digits(days)} روز تمدید شد!"
                else:
                    await crud.set_vip_status(session, user.id, True, days)
                    await crud.add_reward_history(
                        session, user.id, "vip", days, "loyalty_shop", notes=f"Bought {item_id}"
                    )
                    message = f"✅ VIP/اولویت پشتیبانی به مدت {to_persian_digits(days)} روز فعال شد!"
        else:
            # Enable a custom display name (used in arcade leaderboard + profile).
            base_name = (user.custom_username or user.username or user.full_name or "").strip()
            if not base_name:
                base_name = str(user.chat_id)
            base_name = base_name[:40]
            await crud.set_custom_username(session, user.id, base_name)
            await crud.add_reward_history(
                session, user.id, "custom_name", 1, "loyalty_shop", notes=f"Bought {item_id}"
            )
            message = (
                "✅ نام نمایشی شما فعال شد!\n\n"
                f"نام فعلی: {base_name}\n"
                "برای تغییر نام نمایشی، از بخش Arcade/Leaderboard در وب‌اپ استفاده کنید."
            )

    await session.commit()
    
    await callback.answer(message, show_alert=True)
    
    # Refresh shop display
    await show_loyalty_shop(callback, session)
