"""
Validation configuration for ASSTRO bot
"""

# Input validation rules and limits
VALIDATION_RULES = {
    # Text length limits
    "text_limits": {
        "username": (3, 32),
        "full_name": (2, 100),
        "referral_code": (6, 6),
        "message": (1, 4096),
        "description": (1, 1000),
        "note": (0, 500),
        "custom_username": (3, 20),
        "admin_note": (0, 1000)
    },
    
    # Numeric limits
    "numeric_limits": {
        "data_gb": (1, 1000),
        "days": (1, 365),
        "price": (1000, 10000000),  # 1K to 10M Tomans
        "credit": (0, 1000000),
        "loyalty_points": (0, 100000),
        "experience_points": (0, 1000000),
        "level": (1, 100),
        "streak": (0, 365),
        "referral_count": (0, 1000),
        "chat_id": (1, 999999999999),
        "user_id": (1, 999999999999),
        "subscription_id": (1, 999999999999)
    },
    
    # Regex patterns
    "patterns": {
        "username": r'^[a-zA-Z0-9_]{3,32}$',
        "referral_code": r'^[A-Z0-9]{6}$',
        "phone": r'^\+?[1-9]\d{1,14}$',
        "email": r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        "persian_text": r'^[\u0600-\u06FF\s\d\-_\.]+$',
        "english_text": r'^[a-zA-Z0-9\s\-_\.]+$',
        "numeric": r'^\d+$',
        "decimal": r'^\d+(\.\d+)?$',
        "url": r'^https?://[^\s/$.?#].[^\s]*$',
        "file_name": r'^[a-zA-Z0-9\-_\.]+$',
        "safe_text": r'^[a-zA-Z0-9\u0600-\u06FF\s\-_\.\,\!\?]+$',
        "callback_data": r'^[a-zA-Z0-9_:]+$'
    },
    
    # Allowed file extensions
    "allowed_file_extensions": [
        '.jpg', '.jpeg', '.png', '.gif', '.pdf', '.txt', '.doc', '.docx',
        '.xls', '.xlsx', '.zip', '.rar', '.mp3', '.mp4', '.avi', '.mov'
    ],
    
    # Blocked file extensions (security)
    "blocked_file_extensions": [
        '.exe', '.bat', '.cmd', '.com', '.pif', '.scr', '.vbs', '.js',
        '.jar', '.msi', '.dmg', '.app', '.sh', '.py', '.php', '.html'
    ],
    
    # Security patterns to detect
    "security_patterns": {
        "sql_injection": [
            'union select', 'drop table', 'delete from', 'insert into',
            'update set', '--', '/*', '*/', 'xp_', 'sp_', 'exec', 'execute'
        ],
        "xss": [
            '<script', 'javascript:', 'onload=', 'onerror=', 'onclick=',
            'onmouseover=', 'eval(', 'document.cookie', 'alert(', 'confirm('
        ],
        "command_injection": [
            ';', '&&', '||', '|', '>', '<', '`', '$('
        ]
    }
}

# Rate limiting configuration
RATE_LIMIT_CONFIG = {
    "general": {
        "messages_per_minute": 15,
        "window_seconds": 60
    },
    "commands": {
        "messages_per_minute": 5,
        "window_seconds": 30
    },
    "callbacks": {
        "messages_per_minute": 10,
        "window_seconds": 30
    },
    "admin_commands": {
        "messages_per_minute": 20,
        "window_seconds": 60
    },
    "spam_threshold": {
        "max_violations": 50,
        "block_duration_seconds": 600,  # 10 minutes
        "word_repetition_threshold": 0.7  # 70% repetition
    }
}

# Validation error messages (Persian)
VALIDATION_MESSAGES = {
    "general": {
        "invalid_input": "داده‌های ورودی نامعتبر است.",
        "too_long": "متن خیلی طولانی است.",
        "too_short": "متن خیلی کوتاه است.",
        "invalid_format": "فرمت نامعتبر است.",
        "required_field": "این فیلد الزامی است."
    },
    
    "user_input": {
        "invalid_username": "نام کاربری نامعتبر است. باید ۳ تا ۳۲ کاراکتر و شامل حروف، اعداد و _ باشد.",
        "invalid_referral_code": "کد دعوت نامعتبر است. باید ۶ کاراکتر و شامل حروف بزرگ و اعداد باشد.",
        "invalid_phone": "شماره تلفن نامعتبر است.",
        "invalid_email": "ایمیل نامعتبر است.",
        "invalid_plan": "طرح انتخابی نامعتبر است.",
        "invalid_amount": "مبلغ وارد شده نامعتبر است.",
        "insufficient_credit": "اعتبار کافی ندارید.",
        "insufficient_loyalty_points": "امتیاز وفاداری کافی ندارید."
    },
    
    "security": {
        "sql_injection": "داده‌های ورودی نامعتبر است.",
        "xss": "داده‌های ورودی نامعتبر است.",
        "spam": "لطفاً از ارسال پیام‌های تکراری خودداری کنید.",
        "malicious_file": "نوع فایل مجاز نیست.",
        "command_injection": "داده‌های ورودی نامعتبر است."
    },
    
    "rate_limit": {
        "general": "لطفاً کمی صبر کنید و دوباره تلاش کنید.",
        "command": "لطفاً کمی صبر کنید و دوباره تلاش کنید.",
        "callback": "لطفاً کمی صبر کنید و دوباره تلاش کنید.",
        "user_blocked": "شما موقتاً مسدود شده‌اید. لطفاً بعداً تلاش کنید."
    }
}

# Business logic validation rules
BUSINESS_RULES = {
    "subscription": {
        "max_active_subscriptions": 5,
        "min_plan_price": 1000,
        "max_plan_price": 10000000,
        "min_data_gb": 1,
        "max_data_gb": 1000,
        "min_days": 1,
        "max_days": 365
    },
    
    "referral": {
        "max_referrals_per_user": 100,
        "min_referral_reward": 1,
        "max_referral_reward": 1000
    },
    
    "rewards": {
        "max_daily_rewards": 10,
        "max_weekly_rewards": 50,
        "max_monthly_rewards": 200,
        "min_reward_amount": 1,
        "max_reward_amount": 10000
    },
    
    "admin": {
        "max_users_per_batch": 100,
        "max_messages_per_broadcast": 1000,
        "max_file_size_mb": 50
    }
}

# Validation decorators configuration
VALIDATION_DECORATORS = {
    "enable_input_validation": True,
    "enable_rate_limiting": True,
    "enable_security_checks": True,
    "enable_business_validation": True,
    "log_validation_errors": True,
    "log_security_violations": True
}

def get_validation_rule(category: str, rule_name: str):
    """Get validation rule by category and name"""
    return VALIDATION_RULES.get(category, {}).get(rule_name)

def get_rate_limit_config(limit_type: str):
    """Get rate limit configuration by type"""
    return RATE_LIMIT_CONFIG.get(limit_type, RATE_LIMIT_CONFIG["general"])

def get_validation_message(category: str, message_key: str):
    """Get validation error message by category and key"""
    return VALIDATION_MESSAGES.get(category, {}).get(message_key, VALIDATION_MESSAGES["general"]["invalid_input"])

def get_business_rule(category: str, rule_name: str):
    """Get business rule by category and name"""
    return BUSINESS_RULES.get(category, {}).get(rule_name)

def is_validation_enabled(validation_type: str):
    """Check if specific validation type is enabled"""
    return VALIDATION_DECORATORS.get(f"enable_{validation_type}", True) 