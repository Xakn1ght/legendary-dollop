from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_links_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="دریافت لینک ها 🔗", callback_data="get_links")
    return builder.as_markup()

def get_renewal_keyboard(username):
    builder = InlineKeyboardBuilder()
    builder.button(text="تمدید سرویس 🔄", callback_data=f"renew_{username}")
    return builder.as_markup()

def get_low_resource_keyboard(username: str):
    """Inline actions for low traffic/time: quick charge and add 10 days."""
    builder = InlineKeyboardBuilder()
    builder.button(text="شارژ سرویس⚡️", callback_data=f"charge_{username}")
    builder.button(text="خرید روز بیشتر 📅", callback_data=f"buydays_{username}")
    builder.adjust(2)
    return builder.as_markup()

def get_low_traffic_keyboard(username: str):
    """Inline action for low traffic only: quick charge button."""
    builder = InlineKeyboardBuilder()
    builder.button(text="شارژ سرویس⚡️", callback_data=f"charge_{username}")
    builder.adjust(1)
    return builder.as_markup()

def get_purchase_confirmation_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="آپلود رسید 🧾", callback_data="upload_receipt")
    return builder.as_markup()

def get_reward_voucher_keyboard(
    reward_id: int,
    extra_gb: float | None = None,
    extra_days: int | None = None,
    credit_amount: int | None = None,
    stars_progress: int = 0,
    star_increment: int = 1,
    show_star: bool = True,
) -> "InlineKeyboardMarkup":
    """Build the inline keyboard that lets a referrer pick **one** reward.

    Only the buttons whose corresponding values are provided will be included.
    - `extra_gb`  – show traffic button if a positive float is given.
    - `extra_days` – show days button if a positive int is given.
    - `credit_amount` – show credit-wallet button if a positive int is given.
    - `show_star` – whether to offer the ⭐ button. Star increment defaults to 1.
    """

    builder = InlineKeyboardBuilder()

    if extra_gb and extra_gb > 0:
        builder.button(
            text=f"1️⃣ +{extra_gb:.0f} GB",
            callback_data=f"redeem_traffic_{reward_id}",
        )

    if extra_days and extra_days > 0:
        builder.button(
            text=f"2️⃣ +{extra_days} days",
            callback_data=f"redeem_days_{reward_id}",
        )

    if credit_amount and credit_amount > 0:
        builder.button(
            text=f"3️⃣ +{credit_amount:,} T",
            callback_data=f"redeem_credit_{reward_id}",
        )

    if show_star:
        builder.button(
            text=f"⭐ +{star_increment} (⭐ {stars_progress})",
            callback_data=f"redeem_star_{star_increment}_{reward_id}",
        )

    # Lay out max 2 buttons per row for readability
    builder.adjust(2)
    return builder.as_markup()

def get_wallet_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="درخواست برداشت", callback_data="wallet_cashout")
    builder.button(text="استفاده در خرید بعدی", callback_data="wallet_spend")
    builder.button(text="🎟️ بن های من", callback_data="wallet_rewards")
    builder.adjust(2)
    return builder.as_markup()

def get_free_renewal_keyboard(subscriptions):
    """subscriptions: list of Subscription objects"""
    builder = InlineKeyboardBuilder()
    for sub in subscriptions:
        builder.button(text=f"تمدید {sub.marzban_username}", callback_data=f"free_renew_{sub.id}")
    builder.adjust(1)
    return builder.as_markup()


def get_enhanced_reward_voucher_keyboard(
    reward_id: int,
    extra_gb: float | None = None,
    extra_days: int | None = None,
    credit_amount: int | None = None,
    stars_progress: int = 0,
    star_increment: int = 1,
    show_star: bool = True,
    show_enhanced_stars: bool = False,
) -> "InlineKeyboardMarkup":
    """
    Build the inline keyboard for enhanced reward voucher actions.
    Includes buttons for traffic, days, credit, and optionally enhanced stars.
    """
    builder = InlineKeyboardBuilder()

    if extra_gb and extra_gb > 0:
        builder.button(
            text=f"1️⃣ +{extra_gb:.0f} GB",
            callback_data=f"redeem_traffic_{reward_id}",
        )

    if extra_days and extra_days > 0:
        builder.button(
            text=f"2️⃣ +{extra_days} days",
            callback_data=f"redeem_days_{reward_id}",
        )

    if credit_amount and credit_amount > 0:
        builder.button(
            text=f"3️⃣ +{credit_amount:,} T",
            callback_data=f"redeem_credit_{reward_id}",
        )

    if show_enhanced_stars:
        builder.button(
            text=f"⭐ +{star_increment} (⭐ {stars_progress})",
            callback_data=f"redeem_enhanced_star_{star_increment}_{reward_id}",
        )
    elif show_star:
        builder.button(
            text=f"⭐ +{star_increment} (⭐ {stars_progress})",
            callback_data=f"redeem_star_{star_increment}_{reward_id}",
        )

    builder.adjust(2)
    return builder.as_markup() 