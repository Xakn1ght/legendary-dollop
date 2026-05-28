"""
Error handling configuration for ASSTRO bot
"""

# Custom error messages for different scenarios
ERROR_MESSAGES = {
    # Database errors
    "database_connection": "خطا در اتصال به پایگاه داده. لطفاً بعداً تلاش کنید.",
    "database_timeout": "عملیات پایگاه داده طولانی شد. لطفاً دوباره تلاش کنید.",
    "database_integrity": "خطا در داده‌های ورودی. لطفاً اطلاعات را بررسی کنید.",
    
    # Marzban API errors
    "marzban_connection": "خطا در اتصال به سرور VPN. لطفاً بعداً تلاش کنید.",
    "marzban_auth": "خطا در احراز هویت سرور VPN.",
    "marzban_user_exists": "کاربر VPN قبلاً وجود دارد.",
    "marzban_user_not_found": "کاربر VPN یافت نشد.",
    
    # Telegram API errors
    "telegram_message_too_long": "پیام خیلی طولانی است.",
    "telegram_invalid_chat": "چت نامعتبر است.",
    "telegram_rate_limit": "لطفاً کمی صبر کنید و دوباره تلاش کنید.",
    
    # User permission errors
    "unauthorized_access": "شما مجاز به انجام این عملیات نیستید.",
    "user_not_found": "کاربر یافت نشد.",
    "subscription_not_found": "اشتراک یافت نشد.",
    
    # Validation errors
    "invalid_referral_code": "کد دعوت نامعتبر است.",
    "invalid_plan": "طرح انتخابی نامعتبر است.",
    "invalid_amount": "مبلغ وارد شده نامعتبر است.",
    "insufficient_credit": "اعتبار کافی ندارید.",
    "insufficient_loyalty_points": "امتیاز وفاداری کافی ندارید.",
    
    # General errors
    "general_error": "متأسفانه خطایی رخ داده است. لطفاً بعداً دوباره تلاش کنید.",
    "timeout_error": "عملیات زمان‌بر شد. لطفاً دوباره تلاش کنید.",
    "network_error": "خطا در شبکه. لطفاً اتصال اینترنت خود را بررسی کنید.",
}

# Error recovery strategies
ERROR_RECOVERY = {
    "database_connection": {
        "retry_count": 3,
        "retry_delay": 1,  # seconds
        "fallback_message": "سرویس موقتاً در دسترس نیست. لطفاً بعداً تلاش کنید."
    },
    "marzban_connection": {
        "retry_count": 2,
        "retry_delay": 2,
        "fallback_message": "سرور VPN موقتاً در دسترس نیست. لطفاً بعداً تلاش کنید."
    },
    "telegram_rate_limit": {
        "retry_count": 0,  # Don't retry rate limits
        "retry_delay": 0,
        "fallback_message": "لطفاً کمی صبر کنید و دوباره تلاش کنید."
    }
}

# Error severity levels
ERROR_SEVERITY = {
    "critical": [
        "database_connection",
        "marzban_connection",
        "telegram_auth"
    ],
    "high": [
        "database_timeout",
        "marzban_auth",
        "telegram_rate_limit"
    ],
    "medium": [
        "database_integrity",
        "marzban_user_exists",
        "validation_error"
    ],
    "low": [
        "user_not_found",
        "subscription_not_found",
        "general_error"
    ]
}

# Error monitoring thresholds
ERROR_THRESHOLDS = {
    "max_errors_per_minute": 10,
    "max_errors_per_user_per_hour": 5,
    "max_database_errors_per_hour": 20,
    "max_api_errors_per_hour": 15
}

# Error notification settings
ERROR_NOTIFICATIONS = {
    "notify_admin_on_critical": True,
    "notify_admin_on_high": True,
    "notify_admin_on_medium": False,
    "notify_admin_on_low": False,
    "admin_chat_id": None  # Will be set from settings
}

def get_error_message(error_type: str, default: str = None) -> str:
    """Get user-friendly error message for error type"""
    return ERROR_MESSAGES.get(error_type, default or ERROR_MESSAGES["general_error"])

def get_recovery_strategy(error_type: str) -> dict:
    """Get recovery strategy for error type"""
    return ERROR_RECOVERY.get(error_type, {
        "retry_count": 0,
        "retry_delay": 0,
        "fallback_message": ERROR_MESSAGES["general_error"]
    })

def get_error_severity(error_type: str) -> str:
    """Get severity level for error type"""
    for severity, error_types in ERROR_SEVERITY.items():
        if error_type in error_types:
            return severity
    return "low"

def should_notify_admin(error_type: str) -> bool:
    """Check if admin should be notified for this error type"""
    severity = get_error_severity(error_type)
    return ERROR_NOTIFICATIONS.get(f"notify_admin_on_{severity}", False) 