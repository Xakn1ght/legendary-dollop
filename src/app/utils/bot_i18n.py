from __future__ import annotations

from typing import Callable

# In-memory cache (best-effort) so we can localize keyboards without extra DB lookups.
_LANG_CACHE: dict[int, str] = {}


def normalize_lang(lang: str | None) -> str:
    if not lang:
        return "fa"
    l = str(lang).strip().lower()
    if l.startswith("fa"):
        return "fa"
    if l.startswith("en"):
        return "en"
    # Default fallback (safe)
    return "fa"


def guess_lang_from_telegram(language_code: str | None) -> str:
    return normalize_lang(language_code)


def set_cached_lang(chat_id: int, lang: str) -> None:
    try:
        _LANG_CACHE[int(chat_id)] = normalize_lang(lang)
    except Exception:
        return


def get_cached_lang(chat_id: int) -> str:
    try:
        return normalize_lang(_LANG_CACHE.get(int(chat_id)) or "fa")
    except Exception:
        return "fa"


STRINGS: dict[str, dict[str, str]] = {
    # Main menu buttons
    "btn_buy": {"fa": "خرید سرویس💳", "en": "Buy Service 💳"},
    "btn_my_services": {"fa": "سرویس های من🛍", "en": "My Services 🛍"},
    "btn_recharge": {"fa": "شارژ سرویس⚡️", "en": "Recharge ⚡️"},
    "btn_support": {"fa": "پشتیبانی💬", "en": "Support 💬"},
    "btn_rewards": {"fa": "🎁 سیستم پاداش پیشرفته", "en": "🎁 Rewards"},
    "btn_invite": {"fa": "کد دعوت💌", "en": "Invite Code 💌"},
    "btn_add_service": {"fa": "افزودن سرویس➕", "en": "Add Service ➕"},
    "btn_guide": {"fa": "راهنمای اتصال📚", "en": "Connection Guide 📚"},
    "btn_dashboard": {"fa": "مدیریت اشتراک 🌐", "en": "Dashboard 🌐"},
    "btn_language": {"fa": "زبان🌐", "en": "Language 🌐"},
    "btn_back": {"fa": "بازگشت🔙", "en": "Back 🔙"},
    "btn_android": {"fa": "اندروید📱", "en": "Android 📱"},
    "btn_ios": {"fa": "آیفون📱", "en": "iPhone 📱"},
    "btn_windows": {"fa": "ویندوز💻", "en": "Windows 💻"},

    # Common texts
    "support_webapp_only": {
        "fa": "پشتیبانی فقط از طریق پنل وب انجام می‌شود.\nبرای باز کردن صفحه پشتیبانی، روی دکمه زیر بزنید:",
        "en": "Support is available only in the web dashboard.\nTap the button below to open support:",
    },
    "open_support_btn": {"fa": "🎫 باز کردن پشتیبانی", "en": "🎫 Open Support"},
    "choose_language": {"fa": "زبان را انتخاب کنید:", "en": "Choose a language:"},
    "lang_set_ok": {"fa": "✅ زبان شما بروزرسانی شد.", "en": "✅ Your language has been updated."},

    # Tutorials
    "tutorial_choose_device": {"fa": "لطفا نوع دستگاه خود را انتخاب کنید 👇", "en": "Please choose your device 👇"},
    "tutorial_send_error": {"fa": "خطا در ارسال آموزش. لطفا با پشتیبانی تماس بگیرید.", "en": "Failed to send the tutorial. Please contact support."},
    "tutorial_invalid": {"fa": "لطفا یکی از گزینه‌های موجود را انتخاب کنید.", "en": "Please choose one of the available options."},

    # Rewards
    "rewards_title": {"fa": "🎁 <b>سیستم پاداش پیشرفته و کیف پول</b>", "en": "🎁 <b>Rewards & Wallet</b>"},
    "rewards_completed": {"fa": "🎉 چالش تکمیل شد: {title}! پاداش شما اضافه شد.", "en": "🎉 Challenge completed: {title}! Your reward has been added."},
    "rewards_close": {"fa": "❌ بستن", "en": "❌ Close"},
    "rewards_profile": {"fa": "👤 پروفایل", "en": "👤 Profile"},
    "rewards_wallet": {"fa": "💰 کیف پول", "en": "💰 Wallet"},
    "rewards_challenges": {"fa": "🎯 چالش‌ها", "en": "🎯 Challenges"},
    "rewards_achievements": {"fa": "🏆 دستاوردها", "en": "🏆 Achievements"},
    "rewards_star_levels": {"fa": "⭐️ سطح ستاره‌ها", "en": "⭐️ Star Levels"},
    "rewards_stats": {"fa": "📊 آمار", "en": "📊 Stats"},
    "rewards_daily_game": {"fa": "🎮 بازی روزانه", "en": "🎮 Daily Game"},

    # Charge flow
    "charge_now": {"fa": "شارژ فوری", "en": "Charge Now"},
    "book_plan": {"fa": "رزرو پلن", "en": "Book Plan"},
    "charge_confirm": {"fa": "تایید ✅", "en": "Confirm ✅"},
    "charge_which_service": {"fa": "کدام سرویس را می‌خواهید شارژ کنید؟", "en": "Which service do you want to recharge?"},
    "charge_no_services": {"fa": "شما هیچ سرویس فعالی ندارید.", "en": "You have no active services."},
    "charge_choose_package": {"fa": "لطفا یکی از بسته‌های شارژ را انتخاب کنید:", "en": "Please choose a charge package:"},
    "charge_invalid_service": {"fa": "سرویس نامعتبر است، لطفا از دکمه‌ها استفاده کنید.", "en": "Invalid service. Please use the buttons."},
    "charge_service_not_found": {"fa": "سرویس یافت نشد", "en": "Service not found"},
    "charge_error_fetch": {"fa": "❌ خطا در دریافت اطلاعات سرویس. لطفا دوباره تلاش کنید.", "en": "❌ Error fetching service info. Please try again."},
    "charge_remaining": {"fa": "📊 ترافیک باقیمانده: {gb}GB", "en": "📊 Remaining traffic: {gb}GB"},
    "charge_immediate_title": {"fa": "✅ شارژ فوری (5GB انتقال)\n\nلطفا یکی از بسته‌های شارژ را انتخاب کنید:", "en": "✅ Charge Now (5GB transfer)\n\nPlease choose a charge package:"},
    "charge_booking_title": {"fa": "📅 رزرو پلن\n\nپلن انتخابی زمانی اعمال می‌شود که ترافیک شما کمتر از 5% یا کمتر از 3 روز تا انقضا باشد.\n\nلطفاً پلن تمدید را انتخاب کنید:", "en": "📅 Book Plan\n\nYour selected plan will be applied when traffic drops below 5% or less than 3 days remain.\n\nPlease choose a renewal plan:"},
    "charge_back_step": {"fa": "به مرحله قبل بازگشتید. یک گزینه را انتخاب کنید:", "en": "Returned to previous step. Choose an option:"},
    "charge_cancelled": {"fa": "عملیات لغو شد.", "en": "Operation cancelled."},
    "charge_choose_from_buttons": {"fa": "لطفا از میان گزینه‌های موجود انتخاب کنید.", "en": "Please choose from available options."},
    "charge_choose_plan": {"fa": "لطفاً یکی از پلن‌های موجود را انتخاب کنید.", "en": "Please choose one of the available plans."},
    "charge_error_no_sub": {"fa": "خطا: سرویس انتخاب نشده است. دوباره تلاش کنید.", "en": "Error: No service selected. Please try again."},
    "charge_booking_success": {"fa": "✅ رزرو پلن تمدید با موفقیت ثبت شد!\n\n📦 پلن: {plan} ({gb} گیگابایت)\n💵 مبلغ تمدید: {price} تومان\n\n🔄 در زمان مناسب (کمبود ترافیک یا نزدیک انقضا)، تمدید به‌صورت خودکار انجام می‌شود.", "en": "✅ Renewal plan booked successfully!\n\n📦 Plan: {plan} ({gb}GB)\n💵 Renewal price: {price} Toman\n\n🔄 The renewal will be applied automatically when traffic is low or expiry is near."},
    "charge_request_registered": {"fa": "✅ درخواست شارژ ثبت شد.\n\nلطفا مبلغ را به شماره کارت زیر واریز کرده و سپس تصویر رسید را ارسال کنید:\n<code>{card}</code>", "en": "✅ Charge request registered.\n\nPlease transfer the amount to the card number below and then send the receipt image:\n<code>{card}</code>"},
    "charge_back_to_packages": {"fa": "به مرحله انتخاب بسته بازگشتید. لطفا یک بسته را انتخاب کنید:", "en": "Returned to package selection. Please choose a package:"},
    "charge_back_to_services": {"fa": "به مرحله انتخاب سرویس بازگشتید. سرویس را انتخاب کنید:", "en": "Returned to service selection. Choose a service:"},
    "charge_receipt_sent": {"fa": "رسید ارسال شد. لطفا منتظر تایید ادمین بمانید.", "en": "Receipt sent. Please wait for admin approval."},
    "charge_booking_receipt_success": {"fa": "✅ رزرو پلن با موفقیت ثبت شد!\n\n📋 پلن: {plan}\n💵 مبلغ: {price} تومان\n\n🔄 این پلن زمانی اعمال می‌شود که ترافیک شما کمتر از 5% یا کمتر از 3 روز تا انقضا باشد.", "en": "✅ Plan booked successfully!\n\n📋 Plan: {plan}\n💵 Price: {price} Toman\n\n🔄 This plan will be applied when your traffic drops below 5% or less than 3 days remain."},
    "charge_buy_days_title": {"fa": "📅 خرید روز بیشتر:\nلطفاً یکی از پلن‌های زمانی را انتخاب کنید:", "en": "📅 Buy More Days:\nPlease choose a time plan:"},
    "charge_buy_days_choose": {"fa": "لطفاً یکی از پلن‌های زمانی را انتخاب کنید.", "en": "Please choose a time plan."},
    "charge_buy_days_summary": {"fa": "📅 افزودن روز به سرویس\n\nروزهای اضافه: {days}\nمبلغ: {price} تومان\n\nلطفاً مبلغ را واریز کرده و سپس تصویر رسید را ارسال کنید.", "en": "📅 Add Days to Service\n\nExtra days: {days}\nPrice: {price} Toman\n\nPlease transfer the amount and send the receipt image."},
    "charge_renew_title": {"fa": "📅 رزرو پلن (تمدید خودکار)\n\nپس از انتخاب پلن، در زمان مناسب تمدید به‌صورت خودکار انجام می‌شود.\n\nلطفاً پلن تمدید را انتخاب کنید:", "en": "📅 Book Plan (Auto-renewal)\n\nAfter selecting a plan, the renewal will be applied automatically at the right time.\n\nPlease choose a renewal plan:"},
    "start_bot_first": {"fa": "ابتدا باید ربات را با دستور /start شروع کنید.", "en": "Please start the bot with /start first."},
    "send_start_first": {"fa": "ابتدا /start را ارسال کنید", "en": "Please send /start first"},
    "invalid_request": {"fa": "درخواست نامعتبر است", "en": "Invalid request"},
    "add_subscription_prompt": {"fa": "لطفاً لینک اشتراک خود را ارسال کنید:", "en": "Please send your subscription link:"},
    "add_subscription_invalid_link": {"fa": "لطفاً لینک اشتراک معتبر ارسال کنید.", "en": "Please send a valid subscription link."},
    "add_subscription_invalid_format": {"fa": "لینک اشتراک نامعتبر است. لطفاً دوباره امتحان کنید یا از پشتیبانی کمک بگیرید.", "en": "Invalid subscription link. Please try again or contact support."},
    "add_subscription_fetch_failed": {"fa": "نتوانستم اطلاعات اشتراک را از لینک دریافت کنم. لینک را بررسی کنید.", "en": "Could not fetch subscription info from the link. Please check the link."},
    "add_subscription_no_username": {"fa": "لینک معتبر نیست یا نام کاربری در پاسخ وجود ندارد.", "en": "The link is not valid (username not found)."},
    "add_subscription_marzban_not_found": {"fa": "❌ کاربری با این نام در مارزبان یافت نشد. لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.", "en": "❌ No user found on Marzban for this username. Please try again or contact support."},
    "add_subscription_success": {"fa": "✅ سرویس شما با موفقیت اضافه شد و اکنون در بخش مدیریت سرویس قابل مشاهده است.", "en": "✅ Your service was added successfully and is now available in My Services."},
    "add_subscription_existing_added": {"fa": "✅ سرویس موجود به لیست شما اضافه شد.", "en": "✅ Existing service added to your list."},

    # My Services
    "service_not_found": {"fa": "سرویس یافت نشد.", "en": "Service not found."},
    "error_fetch_service": {"fa": "خطا در دریافت اطلاعات سرویس.", "en": "Failed to fetch service info."},
    "wait_seconds": {"fa": "{sec} ثانیه دیگر صبر کنید.", "en": "Please wait {sec} more seconds."},
    "updating": {"fa": "در حال بروزرسانی...", "en": "Updating..."},
    "deletion_disabled": {"fa": "حذف سرویس از طریق ربات غیرفعال است.", "en": "Service deletion via bot is disabled."},
    "pending_approval": {"fa": "در انتظار تایید", "en": "Pending approval"},
    "waiting_admin": {"fa": "⏳ در انتظار تایید ادمین", "en": "⏳ Waiting for admin confirmation"},
    "links_sent": {"fa": "لینک‌های اشتراک ارسال شد!", "en": "Subscription links sent!"},
    "wait_before_links": {"fa": "لطفاً کمی صبر کنید قبل از درخواست دوباره لینک‌ها.", "en": "Please wait a bit before requesting links again."},
    "failed_fetch_links": {"fa": "خطا در دریافت لینک‌ها.", "en": "Failed to fetch links."},
    "no_links_returned": {"fa": "لینکی توسط سرور بازگردانده نشد.", "en": "No links returned by server."},
    "close_btn": {"fa": "❌ بستن", "en": "❌ Close"},
    "weekly_usage": {"fa": "مصرف هفته اخیر (به تفکیک کشور):", "en": "Weekly usage (by country):"},
    "failed_fetch_usage": {"fa": "خطا در دریافت مصرف.", "en": "Failed to fetch usage."},
    "new_link_issued": {"fa": "لینک جدید صادر شد.", "en": "New link issued."},
    "error_revoke_link": {"fa": "خطا در لغو لینک اشتراک. لطفاً بعداً تلاش کنید.", "en": "Failed to revoke subscription link. Please try again later."},
    "removal_disabled": {"fa": "حذف از لیست غیرفعال است.", "en": "Removal from list is disabled."},
    "support_choose_category": {"fa": "پشتیبانی | دسته مشکل را انتخاب کنید:", "en": "Support | Choose a category:"},
    "support_image_saved": {"fa": "تصویر ذخیره شد 🖼 ({current}/{total})", "en": "Image saved 🖼 ({current}/{total})"},
    "support_admin_reply": {"fa": "پاسخ ادمین به تیکت #{ticket_id}:\n{text}", "en": "Admin reply to ticket #{ticket_id}:\n{text}"},
    "use_main_menu_charge": {"fa": "برای شارژ سرویس، لطفاً از منوی اصلی استفاده کنید.", "en": "To charge the service, please use the main menu."},

    # Admin / common alerts
    "not_authorized": {"fa": "دسترسی غیرمجاز", "en": "Not authorized"},
    "invalid_number_try_again": {"fa": "❌ عدد نامعتبر است. دوباره تلاش کنید یا /cancel را بزنید.", "en": "❌ Invalid number. Try again or /cancel."},

    # User - Gifts (rewards)
    "gift_user_not_found_hint": {"fa": "❌ کاربر یافت نشد! لطفاً @username یا شناسه عددی صحیح وارد کنید.", "en": "❌ User not found. Please enter a valid @username or numeric ID."},
    "gift_cannot_gift_self": {"fa": "❌ نمی‌توانید به خودتان هدیه بفرستید.", "en": "❌ You can't send a gift to yourself."},

    # Admin - Support tickets
    "admin_support_ticket_id_missing": {"fa": "خطا: شناسه تیکت یافت نشد. لطفا دوباره از منوی تیکت استفاده کنید.", "en": "Error: ticket id not found. Please open the ticket menu again."},
    "admin_support_ticket_not_found": {"fa": "خطا: تیکت موردنظر یافت نشد. لطفا دوباره از منوی تیکت استفاده کنید.", "en": "Error: ticket not found. Please open the ticket menu again."},
    "admin_support_ticket_user_not_found": {"fa": "خطا: کاربر مرتبط با تیکت یافت نشد.", "en": "Error: user linked to this ticket was not found."},
    "admin_support_send_user_failed": {"fa": "خطا در ارسال پیام به کاربر: {err}", "en": "Failed to send message to user: {err}"},
    "admin_support_sent": {"fa": "ارسال شد.", "en": "Sent."},
    "admin_support_mode_saved": {"fa": "حالت ثبت شد", "en": "Mode saved"},

    # Admin - System tools
    "admin_system_health_failed": {"fa": "❌ خطا در بررسی سلامت سیستم: {err}", "en": "❌ Failed to check system health: {err}"},

    # Admin - User management
    "admin_um_traffic_updated": {"fa": "✅ حجم اشتراک {username} با موفقیت به {gb} گیگابایت تغییر یافت.", "en": "✅ Traffic limit for {username} updated to {gb} GB."},
    "user_traffic_updated_by_admin": {"fa": "📈 حجم اشتراک شما ({username}) توسط ادمین به {gb} گیگابایت تغییر یافت.", "en": "📈 Your subscription traffic ({username}) was updated to {gb} GB by an admin."},

    # Admin - Charge approvals
    "admin_charge_request_details": {
        "fa": (
            "🔋 درخواست شارژ #{id}\n"
            "کاربر: {user} (id={user_id})\n"
            "شناسه اشتراک: {subscription_id}\n"
            "پکیج: {package}\n"
            "مبلغ: {price:,} تومان\n\n"
            "لطفا یکی از گزینه‌های زیر را انتخاب کنید:"
        ),
        "en": (
            "🔋 Charge request #{id}\n"
            "User: {user} (id={user_id})\n"
            "Subscription ID: {subscription_id}\n"
            "Package: {package}\n"
            "Price: {price:,} T\n\n"
            "Please choose an option:"
        ),
    },
    "admin_charge_not_found": {"fa": "درخواست شارژ یافت نشد.", "en": "Charge request not found."},
    "admin_charge_not_found_or_handled": {"fa": "درخواست شارژ یافت نشد یا قبلاً پردازش شده است.", "en": "Charge request not found or already handled."},
    "admin_charge_sub_invalid": {"fa": "اطلاعات اشتراک نامعتبر است یا نام کاربری Marzban موجود نیست.", "en": "Subscription record is invalid or missing Marzban username."},
    "admin_charge_user_missing": {"fa": "کاربر مربوط به این درخواست یافت نشد.", "en": "User record linked to this request was not found."},
    "admin_charge_sub_inactive": {"fa": "اشتراک فعال نیست و امکان شارژ وجود ندارد.", "en": "Subscription is not active – cannot add charge."},
    "admin_charge_fetch_marzban_failed": {"fa": "خطا در دریافت اطلاعات از Marzban.", "en": "Failed to fetch user info from Marzban."},
    "admin_charge_marzban_reset_failed": {"fa": "خطا در ریست/آپدیت Marzban.", "en": "Marzban reset/update failed."},
    "admin_charge_marzban_update_failed": {"fa": "خطا در آپدیت Marzban.", "en": "Marzban update failed."},
    "admin_charge_approved": {"fa": "شارژ تایید شد ✅", "en": "Charge approved!"},
    "admin_charge_denied": {"fa": "درخواست رد شد.", "en": "Request denied."},
    "admin_booking_invalid_payload": {"fa": "اطلاعات رزرو نامعتبر است.", "en": "Invalid booking payload."},
    "admin_booking_not_found_or_handled": {"fa": "درخواست رزرو یافت نشد یا قبلاً پردازش شده است.", "en": "Booking request not found or already handled."},
    "admin_booking_related_missing": {"fa": "اطلاعات مرتبط یافت نشد.", "en": "Related records missing."},
    "admin_booking_approved": {"fa": "رزرو تایید شد ✅", "en": "Booking approved!"},

    # Admin - Subscription approvals
    "admin_sub_request_details": {
        "fa": (
            "🆕 درخواست اشتراک #{id}\n"
            "کاربر: {user}\n"
            "پلن: {plan}\n"
            "نام کاربری Marzban: {username}\n\n"
            "لطفاً تایید یا رد کنید:"
        ),
        "en": (
            "🆕 Subscription request #{id}\n"
            "User: {user}\n"
            "Plan: {plan}\n"
            "Marzban username: {username}\n\n"
            "Approve or deny:"
        ),
    },
    "admin_sub_not_found": {"fa": "اشتراک یافت نشد.", "en": "Subscription not found."},
    "admin_sub_already_handled": {"fa": "این درخواست قبلاً پردازش شده است.", "en": "This request has already been handled."},
    "admin_sub_no_longer_available": {"fa": "❌ این درخواست دیگر در دسترس نیست.", "en": "❌ This request is no longer available."},
    "admin_sub_already_processed": {"fa": "قبلاً پردازش شده است.", "en": "Already processed."},
    "admin_sub_approved": {"fa": "اشتراک تایید شد ✅", "en": "Subscription approved!"},
    "admin_sub_denied": {"fa": "اشتراک رد شد.", "en": "Subscription denied!"},
    "admin_sub_process_failed": {"fa": "خطا در پردازش اشتراک.", "en": "Failed to process subscription."},

    # Admin - Reward settings
    "admin_rewards_current": {
        "fa": "🔧 درصدهای پاداش (فعلی):\n• ترافیک: {traffic}%\n• روزها: {days}%\n• اعتبار: {credit}% از مبلغ",
        "en": "🔧 Reward percentages (current):\n• Traffic: {traffic}%\n• Days   : {days}%\n• Credit : {credit}% of price",
    },
    "admin_rewards_set_traf_btn": {"fa": "تنظیم % ترافیک", "en": "Set Traffic %"},
    "admin_rewards_set_days_btn": {"fa": "تنظیم % روزها", "en": "Set Days %"},
    "admin_rewards_set_credit_btn": {"fa": "تنظیم % اعتبار", "en": "Set Credit %"},
    "admin_rewards_prompt_traf": {"fa": "🔸 درصد جدید ترافیک را ارسال کنید (مثلاً 5 یعنی 5%)", "en": "🔸 Send new traffic percentage (e.g. 5 for 5%)"},
    "admin_rewards_prompt_days": {"fa": "🔸 درصد جدید روزها را ارسال کنید (مثلاً 1 یعنی 1%)", "en": "🔸 Send new days percentage (e.g. 1 for 1%)"},
    "admin_rewards_prompt_credit": {"fa": "🔸 درصد جدید اعتبار را ارسال کنید (مثلاً 10 یعنی 10%)", "en": "🔸 Send new credit percentage (e.g. 10 for 10%)"},
    "admin_rewards_set_traf_ok": {"fa": "✅ پاداش ترافیک روی {val}% تنظیم شد", "en": "✅ Traffic reward set to {val}%"},
    "admin_rewards_set_days_ok": {"fa": "✅ پاداش روزها روی {val}% تنظیم شد", "en": "✅ Days reward set to {val}%"},
    "admin_rewards_set_credit_ok": {"fa": "✅ پاداش اعتبار روی {val}% تنظیم شد", "en": "✅ Credit reward set to {val}%"},

    # Admin dashboard
    "admin_dashboard_refreshed": {"fa": "داشبورد بروزرسانی شد ✅", "en": "Dashboard refreshed ✅"},

    # Generic
    "user_not_found": {"fa": "کاربر یافت نشد.", "en": "User not found."},
    "closed": {"fa": "بسته شد.", "en": "Closed."},

    # Purchase flow (misc)
    "purchase_text_name_only": {
        "fa": "لطفاً فقط یک نام متنی وارد کنید یا دکمه «اتفاقی» را بزنید.",
        "en": "Please enter a text name or tap “Random”.",
    },
    "purchase_choose_new_name": {
        "fa": "لطفا یک نام جدید برای سرویس خود انتخاب کنید یا دکمه «اتفاقی» را بزنید.",
        "en": "Please choose a new service name or tap “Random”.",
    },
    "purchase_choose_plan": {"fa": "لطفا یکی از پلن‌های زیر را انتخاب کنید:", "en": "Please choose a plan:"},
    "purchase_back_to_confirmation": {"fa": "به مرحله تایید سفارش بازگشتید.", "en": "Back to confirmation."},

    # Admin - Gifts (paid receipts)
    "admin_gift_not_found": {"fa": "هدیه یافت نشد.", "en": "Gift not found."},
    "admin_gift_approved": {"fa": "هدیه تایید شد ✅", "en": "Gift approved!"},
    "admin_gift_denied": {"fa": "هدیه رد شد.", "en": "Gift denied!"},
    "admin_gift_details": {
        "fa": (
            "🎁 هدیه #{id}\n"
            "از: {sender}\n"
            "به: {receiver}\n"
            "نوع: {type}\n"
            "مبلغ/مقدار: {value}\n"
            "پلن: {plan}\n"
            "وضعیت: {status} | پذیرفته‌شده: {accepted}\n"
        ),
        "en": (
            "🎁 Gift #{id}\n"
            "From: {sender}\n"
            "To: {receiver}\n"
            "Type: {type}\n"
            "Value: {value}\n"
            "Plan: {plan}\n"
            "Status: {status} | Accepted: {accepted}\n"
        ),
    },

    # Admin - Toggle approve/deny
    "admin_toggle_sub_not_found": {"fa": "اشتراک یافت نشد.", "en": "Subscription not found."},
    "admin_toggle_already_disabled": {"fa": "این سرویس قبلاً غیرفعال شده است.", "en": "Already disabled."},
    "admin_toggle_invalid_disable": {"fa": "وضعیت اشتراک برای تایید غیرفعال‌سازی معتبر نیست.", "en": "Invalid status for disable approval."},
    "admin_toggle_marzban_failed": {"fa": "خطا در ارتباط با Marzban.", "en": "Marzban API failed."},
    "admin_toggle_disabled": {"fa": "غیرفعال شد.", "en": "Disabled."},
    "admin_toggle_request_denied": {"fa": "درخواست رد شد.", "en": "Request denied."},
    "admin_toggle_already_active": {"fa": "این سرویس قبلاً فعال است.", "en": "Already active."},
    "admin_toggle_invalid_enable": {"fa": "وضعیت اشتراک برای تایید فعال‌سازی معتبر نیست.", "en": "Invalid status for enable approval."},
    "admin_toggle_enabled": {"fa": "فعال شد.", "en": "Enabled."},
    "admin_toggle_request_details": {
        "fa": (
            "🔧 درخواست تغییر وضعیت برای {username} (id={id})\n"
            "کاربر: {user}\n"
            "عملیات در انتظار: {action}\n\n"
            "لطفاً تایید یا رد کنید:"
        ),
        "en": (
            "🔧 Toggle request for {username} (id={id})\n"
            "User: {user}\n"
            "Pending action: {action}\n\n"
            "Approve or deny:"
        ),
    },
    "admin_toggle_action_disable": {"fa": "غیرفعال‌سازی", "en": "Disable"},
    "admin_toggle_action_enable": {"fa": "فعال‌سازی", "en": "Enable"},

    # Admin - User management (category edit)
    "admin_user_category_prompt": {
        "fa": "دسته‌بندی فعلی: `{category}`\nدسته‌بندی جدید را ارسال کنید (مثلاً normal, super, hyper):",
        "en": "Current category: `{category}`\nSend new category (e.g., normal, super, hyper):",
    },
    "admin_user_category_updated": {
        "fa": "دسته‌بندی کاربر به `{category}` بروزرسانی شد.",
        "en": "User category updated to `{category}`.",
    },

    # Admin - Settings (plans / charge packages)
    "admin_settings_layout_set": {"fa": "چیدمان دکمه‌ها روی {cols} ستون تنظیم شد.", "en": "Button layout set to {cols} column(s)."},
    "admin_settings_select_plan_swap": {"fa": "🔢 یک پلن را برای جابجایی انتخاب کنید:{preview}", "en": "🔢 Select a plan to swap positions:{preview}"},
    "admin_settings_select_plan_swap_with": {"fa": "🔢 حالا پلن دوم را برای جابجایی انتخاب کنید:{preview}", "en": "🔢 Now select another plan to swap with:{preview}"},
    "admin_settings_swapped_new_order": {"fa": "✅ جابجا شد! ترتیب جدید:{preview}", "en": "✅ Swapped! New order:{preview}"},
    "admin_settings_plan_not_found": {"fa": "پلن یافت نشد.", "en": "Plan not found."},
    "admin_settings_package_not_found": {"fa": "پکیج یافت نشد.", "en": "Package not found."},
    "admin_settings_edit_plan_title": {"fa": "✏️ ویرایش پلن:", "en": "✏️ Edit Plan:"},
    "admin_settings_edit_package_title": {"fa": "✏️ ویرایش پکیج:", "en": "✏️ Edit Package:"},
    "admin_settings_edit_plan_details": {"fa": "نام: {name}\nقیمت: {price}\nحجم: {gb} GB\nروزها: {days}", "en": "Name: {name}\nPrice: {price}\nGB: {gb}\nDays: {days}"},
    "admin_settings_edit_package_details": {"fa": "قیمت: {price}\nحجم: {gb} GB\nروزها: {days}", "en": "Price: {price}\nGB: {gb}\nDays: {days}"},
    "admin_settings_enter_new_value": {"fa": "مقدار جدید برای «{field}» از «{name}» را وارد کنید:", "en": "Enter new value for {field} of {name}:"},
    "admin_settings_invalid_price": {"fa": "قیمت نامعتبر است.", "en": "Invalid price."},
    "admin_settings_invalid_gb": {"fa": "حجم نامعتبر است.", "en": "Invalid GB."},
    "admin_settings_invalid_days": {"fa": "روزهای نامعتبر است.", "en": "Invalid days."},
    "admin_settings_updated_ok": {"fa": "بروزرسانی شد ✅", "en": "Updated ✅"},
    "admin_settings_enter_name_new_plan": {"fa": "نام پلن جدید را وارد کنید:", "en": "Enter name for new plan:"},
    "admin_settings_enter_price_new_plan": {"fa": "قیمت پلن جدید را وارد کنید:", "en": "Enter price for new plan:"},
    "admin_settings_invalid_price_number": {"fa": "قیمت نامعتبر است. یک عدد وارد کنید:", "en": "Invalid price. Enter a number:"},
    "admin_settings_enter_gb_new_plan": {"fa": "حجم (GB) پلن جدید را وارد کنید:", "en": "Enter GB for new plan:"},
    "admin_settings_invalid_gb_number": {"fa": "حجم نامعتبر است. یک عدد وارد کنید:", "en": "Invalid GB. Enter a number:"},
    "admin_settings_enter_days_new_plan": {"fa": "روزهای پلن جدید را وارد کنید:", "en": "Enter days for new plan:"},
    "admin_settings_invalid_days_number": {"fa": "روزهای نامعتبر است. یک عدد وارد کنید:", "en": "Invalid days. Enter a number:"},
    "admin_settings_plan_added": {"fa": "✅ پلن «{name}» اضافه شد.", "en": "✅ Plan \"{name}\" added."},
    "admin_settings_plan_deleted": {"fa": "پلن «{name}» حذف شد.", "en": "Plan \"{name}\" deleted."},
    "admin_settings_enter_name_new_package": {"fa": "نام پکیج جدید را وارد کنید:", "en": "Enter name for new package:"},
    "admin_settings_enter_price_new_package": {"fa": "قیمت پکیج جدید را وارد کنید:", "en": "Enter price for new package:"},
    "admin_settings_enter_gb_new_package": {"fa": "حجم (GB) پکیج جدید را وارد کنید (اگر ندارد 0):", "en": "Enter GB for new package (send 0 if none):"},
    "admin_settings_enter_days_new_package": {"fa": "روزهای پکیج جدید را وارد کنید (اگر ندارد 0):", "en": "Enter days for new package (send 0 if none):"},
    "admin_settings_package_added": {"fa": "✅ پکیج «{name}» اضافه شد.", "en": "✅ Package \"{name}\" added."},
    "admin_settings_package_deleted": {"fa": "پکیج «{name}» حذف شد.", "en": "Package \"{name}\" deleted."},
    "admin_settings_btn_edit_name": {"fa": "ویرایش نام", "en": "Edit Name"},
    "admin_settings_btn_edit_price": {"fa": "ویرایش قیمت", "en": "Edit Price"},
    "admin_settings_btn_edit_gb": {"fa": "ویرایش حجم", "en": "Edit GB"},
    "admin_settings_btn_edit_days": {"fa": "ویرایش روزها", "en": "Edit Days"},
    "admin_settings_btn_save": {"fa": "💾 ذخیره", "en": "💾 Save"},
    "admin_settings_btn_cancel": {"fa": "❌ لغو", "en": "❌ Cancel"},
    "admin_settings_menu_title": {"fa": "⚙️ منوی تنظیمات:", "en": "⚙️ Settings menu:"},
    "admin_settings_btn_manage_plans": {"fa": "📦 مدیریت پلن‌ها", "en": "📦 Manage Plans"},
    "admin_settings_btn_manage_charges": {"fa": "🔋 مدیریت شارژها", "en": "🔋 Manage Charges"},
    "admin_settings_btn_renewal_settings": {"fa": "🔄 تنظیمات تمدید خودکار", "en": "🔄 Auto-renewal Settings"},
    "admin_settings_btn_day_plans": {"fa": "📅 پلن‌های زمانی", "en": "📅 Day Plans"},
    "admin_settings_btn_support_settings": {"fa": "🆘 پشتیبانی: یادآور/بستن", "en": "🆘 Support: reminders/close"},
    "admin_settings_btn_jobs_manage": {"fa": "⏰ زمان‌بندی وظایف", "en": "⏰ Job schedules"},
    "admin_settings_btn_close": {"fa": "❌ بستن", "en": "❌ Close"},
    "admin_settings_plans_title": {"fa": "📦 پلن‌ها:", "en": "📦 Plans:"},
    "admin_settings_charge_packages_title": {"fa": "🔋 پکیج‌های شارژ:", "en": "🔋 Charge Packages:"},
    "admin_settings_btn_button_layout": {"fa": "🔲 چیدمان دکمه‌ها: {cols} ستون", "en": "🔲 Button layout: {cols} column(s)"},
    "admin_settings_btn_positions": {"fa": "🔢 جایگاه‌ها", "en": "🔢 Positions"},
    "admin_settings_btn_edit_item": {"fa": "✏️ ویرایش {name}", "en": "✏️ Edit {name}"},
    "admin_settings_btn_delete_item": {"fa": "🗑️ حذف {name}", "en": "🗑️ Delete {name}"},
    "admin_settings_btn_add_new_plan": {"fa": "➕ افزودن پلن جدید", "en": "➕ Add New Plan"},
    "admin_settings_btn_add_new_package": {"fa": "➕ افزودن پکیج جدید", "en": "➕ Add New Package"},
    "admin_settings_btn_back": {"fa": "⬅️ بازگشت", "en": "⬅️ Back"},

    # Admin - Cache tools
    "admin_cache_unavailable": {"fa": "📊 کش Redis در دسترس نیست.", "en": "📊 Redis cache is not available"},
    "admin_cache_clearing": {"fa": "🧹 در حال پاک‌سازی کش...", "en": "🧹 Clearing all cache data..."},
    "admin_cache_empty": {"fa": "✅ کش خالی است.", "en": "✅ Cache is already empty"},
    "admin_cache_cleared": {"fa": "✅ کش پاک شد!\n🗑️ تعداد کلیدهای حذف‌شده: {count}\n⏱️ زمان: {sec:.2f} ثانیه", "en": "✅ Cache cleared successfully!\n🗑️ Deleted {count} keys\n⏱️ Time taken: {sec:.2f} seconds"},
    "admin_cache_test_start": {"fa": "🧪 در حال تست کش...", "en": "🧪 Testing cache functionality..."},
    "admin_cache_test_err_set": {"fa": "خطا در عملیات Set", "en": "Failed to set cache value"},
    "admin_cache_test_err_mismatch": {"fa": "عدم تطابق مقدار ذخیره‌شده و خوانده‌شده", "en": "Cache get/set mismatch"},
    "admin_cache_test_err_ttl": {"fa": "TTL درست تنظیم نشد", "en": "TTL not set correctly"},
    "admin_cache_test_err_delete": {"fa": "خطا در عملیات Delete", "en": "Failed to delete cache value"},
    "admin_cache_test_ok": {
        "fa": "✅ تست کش موفق بود!\n⏱️ زمان: {sec:.3f} ثانیه\n✅ Set: OK\n✅ Get: OK\n✅ TTL: OK ({ttl}s)\n✅ Delete: OK",
        "en": "✅ Cache test completed successfully!\n⏱️ Time taken: {sec:.3f} seconds\n✅ Set operation: Working\n✅ Get operation: Working\n✅ TTL operation: Working ({ttl}s)\n✅ Delete operation: Working",
    },
    "admin_cache_test_failed": {"fa": "❌ تست کش ناموفق بود: {err}\n⏱️ زمان: {sec:.3f} ثانیه", "en": "❌ Cache test failed: {err}\n⏱️ Time taken: {sec:.3f} seconds"},
    "admin_cache_invalidate_user_usage": {"fa": "روش استفاده: روی پیام کاربر ریپلای کنید و دستور /cache_invalidate_user را بفرستید.", "en": "Usage: Reply to a user's message with /cache_invalidate_user"},
    "admin_cache_invalidating_user": {"fa": "🔄 در حال پاک‌سازی کش برای کاربر {user_id}...", "en": "🔄 Invalidating cache for user {user_id}..."},
    "admin_cache_invalidate_user_ok": {"fa": "✅ کش کاربر پاک شد.\n👤 User ID: {user_id}\n⏱️ زمان: {sec:.2f} ثانیه", "en": "✅ User cache invalidated successfully!\n👤 User ID: {user_id}\n⏱️ Time taken: {sec:.2f} seconds"},
    "admin_cache_invalidate_user_none": {"fa": "⚠️ کش برای کاربر {user_id} پیدا نشد.\n⏱️ زمان: {sec:.2f} ثانیه", "en": "⚠️ No cache found for user {user_id}\n⏱️ Time taken: {sec:.2f} seconds"},
    "admin_cache_invalidate_user_failed": {"fa": "❌ خطا در پاک‌سازی کش کاربر: {err}", "en": "❌ Failed to invalidate user cache: {err}"},
    "admin_cache_invalidate_pattern_usage": {"fa": "روش استفاده: /cache_invalidate_pattern <pattern>\nمثال: /cache_invalidate_pattern user:*", "en": "Usage: /cache_invalidate_pattern <pattern>\nExample: /cache_invalidate_pattern user:*"},
    "admin_cache_invalidating_pattern": {"fa": "🔄 در حال پاک‌سازی کش با الگو: {pattern}", "en": "🔄 Invalidating cache with pattern: {pattern}"},
    "admin_cache_invalidate_pattern_ok": {"fa": "✅ پاک‌سازی با الگو انجام شد!\n🔍 الگو: {pattern}\n🗑️ کلیدهای حذف‌شده: {count}\n⏱️ زمان: {sec:.2f} ثانیه", "en": "✅ Pattern cache invalidation completed!\n🔍 Pattern: {pattern}\n🗑️ Deleted keys: {count}\n⏱️ Time taken: {sec:.2f} seconds"},
    "admin_cache_invalidate_pattern_failed": {"fa": "❌ خطا در پاک‌سازی کش با الگو: {err}", "en": "❌ Failed to invalidate pattern cache: {err}"},
    "admin_cache_restarting": {"fa": "🔄 در حال راه‌اندازی مجدد Redis...", "en": "🔄 Restarting Redis cache connection..."},
    "admin_cache_restart_ok": {"fa": "✅ Redis راه‌اندازی مجدد شد.\n⏱️ زمان: {sec:.2f} ثانیه", "en": "✅ Redis cache restarted successfully!\n⏱️ Time taken: {sec:.2f} seconds"},
    "admin_cache_restart_failed": {"fa": "❌ خطا در راه‌اندازی مجدد Redis\n⏱️ زمان: {sec:.2f} ثانیه", "en": "❌ Failed to restart Redis cache\n⏱️ Time taken: {sec:.2f} seconds"},
    "admin_cache_restart_error": {"fa": "❌ خطا در راه‌اندازی مجدد کش: {err}", "en": "❌ Failed to restart cache: {err}"},
    "admin_cache_health_unavailable": {"fa": "🏥 وضعیت کش: در دسترس نیست\n❌ کش Redis متصل نیست", "en": "🏥 Cache Health: Unavailable\n❌ Redis cache is not connected"},
    "admin_cache_health_failed": {"fa": "❌ خطا در بررسی سلامت کش: {err}", "en": "❌ Failed to check cache health: {err}"},

    # Admin - DB index tools
    "admin_db_indexes_creating": {"fa": "🔄 در حال ساخت ایندکس‌های دیتابیس...", "en": "🔄 Creating database indexes..."},
    "admin_db_indexes_created": {"fa": "✅ ایندکس‌ها ساخته شد!\n⏱️ زمان: {sec:.2f} ثانیه\n📊 این کار سرعت کوئری‌ها را بهتر می‌کند.", "en": "✅ Database indexes created successfully!\n⏱️ Time taken: {sec:.2f} seconds\n📊 This will improve query performance significantly."},
    "admin_db_analyzing": {"fa": "🔍 در حال تحلیل عملکرد دیتابیس...", "en": "🔍 Analyzing database performance..."},
    "admin_db_postgres_only_analysis": {"fa": "ℹ️ این گزارش فقط برای PostgreSQL در دسترس است.", "en": "ℹ️ Analysis is available only on PostgreSQL."},
    "admin_db_postgres_only_index_stats": {"fa": "ℹ️ آمار ایندکس فقط برای PostgreSQL در دسترس است.", "en": "ℹ️ Index stats are available only on PostgreSQL."},
    "admin_db_no_index_usage": {"fa": "📊 آماری از استفاده ایندکس موجود نیست.", "en": "📊 No index usage statistics available"},
    "admin_db_vacuum_running": {"fa": "🧹 در حال اجرای VACUUM ANALYZE...", "en": "🧹 Running VACUUM ANALYZE to update table statistics..."},
    "admin_db_postgres_only_vacuum": {"fa": "ℹ️ VACUUM ANALYZE فقط در PostgreSQL انجام می‌شود.", "en": "ℹ️ VACUUM ANALYZE is a PostgreSQL operation. Skipping on this database."},
    "admin_db_vacuum_done": {"fa": "✅ VACUUM ANALYZE انجام شد!\n⏱️ زمان: {sec:.2f} ثانیه\n📊 آمار جدول‌ها بروزرسانی شد.", "en": "✅ VACUUM ANALYZE completed successfully!\n⏱️ Time taken: {sec:.2f} seconds\n📊 Table statistics have been updated."},
    "admin_db_postgres_only_slow": {"fa": "ℹ️ آمار کوئری‌های کند نیازمند PostgreSQL + pg_stat_statements است.", "en": "ℹ️ Slow query stats require PostgreSQL with pg_stat_statements."},
    "admin_db_no_slow_queries": {"fa": "📊 آماری از کوئری‌های کند موجود نیست.", "en": "📊 No slow query statistics available"},
    "admin_db_postgres_only_table_stats": {"fa": "ℹ️ آمار جدول‌ها فقط برای PostgreSQL در دسترس است.", "en": "ℹ️ Table statistics view is available only on PostgreSQL."},
    "admin_db_no_table_stats": {"fa": "📊 آماری از جدول‌ها موجود نیست.", "en": "📊 No table statistics available"},
    "admin_db_postgres_only_health": {"fa": "🏥 سلامت دیتابیس فقط برای PostgreSQL در این نسخه فعال است.", "en": "🏥 Database Health is available only on PostgreSQL in this build."},
    "admin_db_failed_create_indexes": {"fa": "❌ خطا در ساخت ایندکس‌ها: {err}", "en": "❌ Failed to create indexes: {err}"},
    "admin_db_failed_analyze_indexes": {"fa": "❌ خطا در تحلیل ایندکس‌ها: {err}", "en": "❌ Failed to analyze indexes: {err}"},
    "admin_db_analysis_title": {"fa": "📊 **تحلیل عملکرد دیتابیس**", "en": "📊 **Database Performance Analysis**"},
    "admin_db_suggested_indexes": {"fa": "💡 **ایندکس‌های پیشنهادی:**", "en": "💡 **Suggested Indexes:**"},
    "admin_db_more_suggestions": {"fa": "... و {count} پیشنهاد دیگر", "en": "... and {count} more suggestions"},
    "admin_db_no_suggestions": {"fa": "✅ ایندکس جدیدی پیشنهاد نشد", "en": "✅ No additional indexes suggested"},
    "admin_db_index_usage_stats_heading": {"fa": "📈 **آمار استفاده از ایندکس‌ها:**", "en": "📈 **Index Usage Statistics:**"},
    "admin_db_usage_line": {"fa": "• {table}.{index}: {scans} اسکن", "en": "• {table}.{index}: {scans} scans"},
    "admin_db_index_stats_title": {"fa": "📊 **آمار استفاده از ایندکس‌ها**", "en": "📊 **Index Usage Statistics**"},
    "admin_db_label_scans": {"fa": "اسکن‌ها", "en": "Scans"},
    "admin_db_label_tuples_read": {"fa": "رکوردهای خوانده‌شده", "en": "Tuples Read"},
    "admin_db_label_tuples_fetched": {"fa": "رکوردهای واکشی‌شده", "en": "Tuples Fetched"},
    "admin_db_label_efficiency": {"fa": "کارایی", "en": "Efficiency"},
    "admin_db_na": {"fa": "نامشخص", "en": "N/A"},
    "admin_db_index_stats_total_scans": {"fa": "📈 **مجموع اسکن ایندکس‌ها: {total}**", "en": "📈 **Total Index Scans: {total}**"},
    "admin_db_part": {"fa": "*بخش {i}/{n}*", "en": "*Part {i}/{n}*"},
    "admin_db_failed_index_stats": {"fa": "❌ خطا در دریافت آمار ایندکس: {err}", "en": "❌ Failed to get index stats: {err}"},
    "admin_db_failed_vacuum": {"fa": "❌ خطا در اجرای VACUUM ANALYZE: {err}", "en": "❌ Failed to run VACUUM ANALYZE: {err}"},
    "admin_db_failed_slow_queries": {"fa": "❌ خطا در دریافت کوئری‌های کند: {err}", "en": "❌ Failed to get slow queries: {err}"},
    "admin_db_slow_title": {"fa": "🐌 **کندترین کوئری‌ها (بر اساس میانگین زمان)**", "en": "🐌 **Slowest Queries (by average time)**"},
    "admin_db_slow_query_heading": {"fa": "**{i}. کوئری**", "en": "**{i}. Query**"},
    "admin_db_label_calls": {"fa": "تعداد اجرا", "en": "Calls"},
    "admin_db_label_total_time": {"fa": "زمان کل", "en": "Total Time"},
    "admin_db_label_avg_time": {"fa": "میانگین زمان", "en": "Avg Time"},
    "admin_db_label_rows": {"fa": "ردیف‌ها", "en": "Rows"},
    "admin_db_label_query": {"fa": "کوئری", "en": "Query"},
    "admin_db_table_stats_title": {"fa": "📊 **آمار جدول‌ها**", "en": "📊 **Table Statistics**"},
    "admin_db_table_stats_distinct_line": {"fa": "• {col}: {val} مقدار متمایز", "en": "• {col}: {val} distinct values"},
    "admin_db_failed_table_stats": {"fa": "❌ خطا در دریافت آمار جدول‌ها: {err}", "en": "❌ Failed to get table sizes: {err}"},
    "admin_db_health_title": {"fa": "🏥 **گزارش سلامت دیتابیس**", "en": "🏥 **Database Health Report**"},
    "admin_db_health_table_stats_heading": {"fa": "📊 **آمار جدول‌ها:**", "en": "📊 **Table Statistics:**"},
    "admin_db_health_rows_line": {"fa": "• {table}: {rows} ردیف", "en": "• {table}: {rows} rows"},
    "admin_db_health_dead_suffix": {"fa": " ({dead} مرده)", "en": " ({dead} dead)"},
    "admin_db_health_total_rows": {"fa": "📈 **مجموع ردیف‌ها: {total}**", "en": "📈 **Total Rows: {total}**"},
    "admin_db_health_index_usage_heading": {"fa": "🔍 **استفاده از ایندکس:**", "en": "🔍 **Index Usage:**"},
    "admin_db_health_total_indexes": {"fa": "تعداد ایندکس‌ها", "en": "Total Indexes"},
    "admin_db_health_total_scans": {"fa": "مجموع اسکن‌ها", "en": "Total Scans"},
    "admin_db_health_avg_scans": {"fa": "میانگین اسکن به ازای هر ایندکس", "en": "Avg Scans per Index"},
    "admin_db_health_score": {"fa": "🏆 **امتیاز سلامت: {score}/100**", "en": "🏆 **Health Score: {score}/100**"},
    "admin_db_health_status_ok": {"fa": "✅ دیتابیس سالم است", "en": "✅ Database is healthy"},
    "admin_db_health_status_attention": {"fa": "⚠️ دیتابیس نیاز به بررسی دارد", "en": "⚠️ Database needs attention"},
    "admin_db_health_status_bad": {"fa": "❌ دیتابیس نیاز به بهینه‌سازی دارد", "en": "❌ Database needs optimization"},
    "admin_db_failed_db_health": {"fa": "❌ خطا در دریافت سلامت دیتابیس: {err}", "en": "❌ Failed to get database health: {err}"},
}


def t(lang: str, key: str) -> str:
    lang = normalize_lang(lang)
    table = STRINGS.get(key) or {}
    return table.get(lang) or table.get("fa") or key


def variants(key: str) -> set[str]:
    table = STRINGS.get(key) or {}
    return {v for v in table.values() if v}


def text_matches(key: str) -> Callable:
    vals = variants(key)

    def _pred(m) -> bool:
        try:
            return (getattr(m, "text", "") or "").strip() in vals
        except Exception:
            return False

    return _pred
