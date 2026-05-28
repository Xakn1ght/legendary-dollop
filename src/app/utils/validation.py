"""
Input validation utilities for ASSTRO bot
"""

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from aiogram.types import CallbackQuery, Message

from app.utils.logger import ValidationError, log_error


class InputValidator:
    """Comprehensive input validation for bot inputs"""
    
    # Regex patterns for validation
    PATTERNS = {
        'username': r'^[a-zA-Z0-9_]{3,32}$',
        'referral_code': r'^[A-Z0-9]{6}$',
        'phone': r'^\+?[1-9]\d{1,14}$',
        'email': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        'persian_text': r'^[\u0600-\u06FF\s\d\-_\.]+$',
        'english_text': r'^[a-zA-Z0-9\s\-_\.]+$',
        'numeric': r'^\d+$',
        'decimal': r'^\d+(\.\d+)?$',
        'url': r'^https?://[^\s/$.?#].[^\s]*$',
        'file_name': r'^[a-zA-Z0-9\-_\.]+$',
        'safe_text': r'^[a-zA-Z0-9\u0600-\u06FF\s\-_\.\,\!\?\|]+$'
    }
    
    # Length limits
    LENGTH_LIMITS = {
        'username': (3, 32),
        'full_name': (2, 100),
        'referral_code': (6, 6),
        'message': (1, 4096),
        'description': (1, 1000),
        'note': (0, 500),
        'custom_username': (3, 20),
        'gift_message': (0, 200)
    }
    
    # Numeric limits
    NUMERIC_LIMITS = {
        'data_gb': (1, 1000),
        'days': (1, 365),
        'price': (1000, 10000000),  # 1K to 10M Tomans
        'credit': (0, 1000000),
        'loyalty_points': (0, 100000),
        'experience_points': (0, 1000000),
        'level': (1, 100),
        'streak': (0, 365),
        'referral_count': (0, 1000)
    }
    
    @classmethod
    def validate_username(cls, username: str) -> bool:
        """Validate username format"""
        if not username:
            return False
        return bool(re.match(cls.PATTERNS['username'], username))
    
    @classmethod
    def validate_referral_code(cls, code: str) -> bool:
        """Validate referral code format"""
        if not code:
            return False
        return bool(re.match(cls.PATTERNS['referral_code'], code))
    
    @classmethod
    def validate_phone(cls, phone: str) -> bool:
        """Validate phone number format"""
        if not phone:
            return False
        return bool(re.match(cls.PATTERNS['phone'], phone))
    
    @classmethod
    def validate_email(cls, email: str) -> bool:
        """Validate email format"""
        if not email:
            return False
        return bool(re.match(cls.PATTERNS['email'], email))
    
    @classmethod
    def validate_persian_text(cls, text: str) -> bool:
        """Validate Persian text"""
        if not text:
            return False
        return bool(re.match(cls.PATTERNS['persian_text'], text))
    
    @classmethod
    def validate_english_text(cls, text: str) -> bool:
        """Validate English text"""
        if not text:
            return False
        return bool(re.match(cls.PATTERNS['english_text'], text))
    
    @classmethod
    def validate_safe_text(cls, text: str) -> bool:
        """Validate safe text (Persian + English + basic punctuation)"""
        if not text:
            return False
        return bool(re.match(cls.PATTERNS['safe_text'], text))
    
    @classmethod
    def validate_numeric(cls, value: str) -> bool:
        """Validate numeric input"""
        if not value:
            return False
        return bool(re.match(cls.PATTERNS['numeric'], str(value)))
    
    @classmethod
    def validate_decimal(cls, value: str) -> bool:
        """Validate decimal input"""
        if not value:
            return False
        return bool(re.match(cls.PATTERNS['decimal'], str(value)))
    
    @classmethod
    def validate_url(cls, url: str) -> bool:
        """Validate URL format"""
        if not url:
            return False
        return bool(re.match(cls.PATTERNS['url'], url))
    
    @classmethod
    def validate_length(cls, text: str, field: str) -> bool:
        """Validate text length for specific field"""
        if not text:
            return False
        limits = cls.LENGTH_LIMITS.get(field, (1, 1000))
        return limits[0] <= len(text) <= limits[1]
    
    @classmethod
    def validate_numeric_range(cls, value: Union[int, str], field: str) -> bool:
        """Validate numeric value within range"""
        try:
            num_value = int(value)
            limits = cls.NUMERIC_LIMITS.get(field, (0, 1000000))
            return limits[0] <= num_value <= limits[1]
        except (ValueError, TypeError):
            return False
    
    @classmethod
    def validate_plan_name(cls, plan: str) -> bool:
        """Validate subscription plan name"""
        if not plan:
            return False
        # Check if plan contains valid Persian/English text and numbers
        return cls.validate_safe_text(plan) and cls.validate_length(plan, 'description')
    
    @classmethod
    def validate_custom_username(cls, username: str) -> bool:
        """Validate custom username for premium features"""
        if not username:
            return False
        # Must be alphanumeric with underscores, 3-20 characters
        return bool(re.match(r'^[a-zA-Z0-9_]{3,20}$', username))
    
    @classmethod
    def validate_gift_message(cls, message: str) -> bool:
        """Validate gift message"""
        if not message:
            return True  # Empty messages are allowed
        return cls.validate_safe_text(message) and cls.validate_length(message, 'gift_message')
    
    @classmethod
    def sanitize_text(cls, text: str, max_length: int = 1000) -> str:
        """Sanitize text input by removing dangerous characters"""
        if not text:
            return ""
        
        # Remove null bytes and control characters
        text = ''.join(char for char in text if ord(char) >= 32)
        
        # Limit length
        if len(text) > max_length:
            text = text[:max_length]
        
        return text.strip()
    
    @classmethod
    def validate_callback_data(cls, data: str) -> bool:
        """Validate callback data format"""
        if not data:
            return False
        # Callback data should be alphanumeric with underscores and colons
        return bool(re.match(r'^[a-zA-Z0-9_:]+$', data))
    
    @classmethod
    def validate_file_name(cls, filename: str) -> bool:
        """Validate filename for security"""
        if not filename:
            return False
        return bool(re.match(cls.PATTERNS['file_name'], filename))

class MessageValidator:
    """Message-specific validation"""
    
    @staticmethod
    def validate_message_content(message: Message) -> Dict[str, Any]:
        """Validate message content and extract useful information"""
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'content_type': None,
            'text_length': 0,
            'has_media': False
        }
        
        try:
            # Check message type
            if message.text:
                validation_result['content_type'] = 'text'
                validation_result['text_length'] = len(message.text)
                
                # Validate text length
                if len(message.text) > 4096:
                    validation_result['errors'].append('Message too long')
                    validation_result['is_valid'] = False
                
                # Check for suspicious patterns
                if re.search(r'(http|https)://', message.text, re.IGNORECASE):
                    validation_result['warnings'].append('Contains URL')
                
                if re.search(r'[<>]', message.text):
                    validation_result['warnings'].append('Contains HTML-like tags')
                
            elif message.photo:
                validation_result['content_type'] = 'photo'
                validation_result['has_media'] = True
                
            elif message.document:
                validation_result['content_type'] = 'document'
                validation_result['has_media'] = True
                
                # Validate file type
                if message.document.file_name:
                    if not InputValidator.validate_file_name(message.document.file_name):
                        validation_result['errors'].append('Invalid filename')
                        validation_result['is_valid'] = False
                
            elif message.voice:
                validation_result['content_type'] = 'voice'
                validation_result['has_media'] = True
                
            else:
                validation_result['content_type'] = 'other'
                validation_result['warnings'].append('Unsupported content type')
            
        except Exception as e:
            validation_result['errors'].append(f'Validation error: {str(e)}')
            validation_result['is_valid'] = False
        
        return validation_result
    
    @staticmethod
    def validate_callback_query(callback: CallbackQuery) -> Dict[str, Any]:
        """Validate callback query data"""
        validation_result = {
            'is_valid': True,
            'errors': [],
            'data': None
        }
        
        try:
            if callback.data:
                if not InputValidator.validate_callback_data(callback.data):
                    validation_result['errors'].append('Invalid callback data format')
                    validation_result['is_valid'] = False
                else:
                    validation_result['data'] = callback.data
            else:
                validation_result['errors'].append('No callback data')
                validation_result['is_valid'] = False
                
        except Exception as e:
            validation_result['errors'].append(f'Callback validation error: {str(e)}')
            validation_result['is_valid'] = False
        
        return validation_result

class BusinessLogicValidator:
    """Business logic specific validation"""
    
    @staticmethod
    def validate_subscription_creation(user_id: int, plan: str, price: int) -> Dict[str, Any]:
        """Validate subscription creation parameters"""
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': []
        }
        
        try:
            # Validate user_id
            if not isinstance(user_id, int) or user_id <= 0:
                validation_result['errors'].append('Invalid user ID')
                validation_result['is_valid'] = False
            
            # Validate plan
            if not InputValidator.validate_plan_name(plan):
                validation_result['errors'].append('Invalid plan name')
                validation_result['is_valid'] = False
            
            # Validate price
            if not InputValidator.validate_numeric_range(price, 'price'):
                validation_result['errors'].append('Invalid price')
                validation_result['is_valid'] = False
            
        except Exception as e:
            validation_result['errors'].append(f'Subscription validation error: {str(e)}')
            validation_result['is_valid'] = False
        
        return validation_result
    
    @staticmethod
    def validate_referral_creation(referrer_id: int, referee_id: int) -> Dict[str, Any]:
        """Validate referral creation parameters"""
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': []
        }
        
        try:
            # Validate user IDs
            if not isinstance(referrer_id, int) or referrer_id <= 0:
                validation_result['errors'].append('Invalid referrer ID')
                validation_result['is_valid'] = False
            
            if not isinstance(referee_id, int) or referee_id <= 0:
                validation_result['errors'].append('Invalid referee ID')
                validation_result['is_valid'] = False
            
            # Check if same user
            if referrer_id == referee_id:
                validation_result['errors'].append('Cannot refer yourself')
                validation_result['is_valid'] = False
            
        except Exception as e:
            validation_result['errors'].append(f'Referral validation error: {str(e)}')
            validation_result['is_valid'] = False
        
        return validation_result
    
    @staticmethod
    def validate_reward_redemption(user_id: int, reward_type: str, amount: int) -> Dict[str, Any]:
        """Validate reward redemption parameters"""
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': []
        }
        
        try:
            # Validate user_id
            if not isinstance(user_id, int) or user_id <= 0:
                validation_result['errors'].append('Invalid user ID')
                validation_result['is_valid'] = False
            
            # Validate reward type
            valid_reward_types = ['credit', 'loyalty_points', 'traffic', 'days', 'stars', 'star']
            if reward_type not in valid_reward_types:
                validation_result['errors'].append('Invalid reward type')
                validation_result['is_valid'] = False
            
            # Validate amount
            if not InputValidator.validate_numeric_range(amount, reward_type):
                validation_result['errors'].append('Invalid amount')
                validation_result['is_valid'] = False
            
        except Exception as e:
            validation_result['errors'].append(f'Reward validation error: {str(e)}')
            validation_result['is_valid'] = False
        
        return validation_result

# Convenience functions
def validate_input(value: str, field_type: str, **kwargs) -> bool:
    """Convenience function for input validation"""
    validator = InputValidator()
    
    if field_type == 'username':
        return validator.validate_username(value)
    elif field_type == 'referral_code':
        return validator.validate_referral_code(value)
    elif field_type == 'phone':
        return validator.validate_phone(value)
    elif field_type == 'email':
        return validator.validate_email(value)
    elif field_type == 'persian_text':
        return validator.validate_persian_text(value)
    elif field_type == 'english_text':
        return validator.validate_english_text(value)
    elif field_type == 'safe_text':
        return validator.validate_safe_text(value)
    elif field_type == 'numeric':
        return validator.validate_numeric(value)
    elif field_type == 'decimal':
        return validator.validate_decimal(value)
    elif field_type == 'url':
        return validator.validate_url(value)
    elif field_type == 'length':
        field = kwargs.get('field', 'message')
        return validator.validate_length(value, field)
    elif field_type == 'numeric_range':
        field = kwargs.get('field', 'value')
        return validator.validate_numeric_range(value, field)
    else:
        return False

def sanitize_user_input(text: str) -> str:
    """Sanitize user input for safe storage"""
    return InputValidator.sanitize_text(text)

def validate_message(message: Message) -> Dict[str, Any]:
    """Validate incoming message"""
    return MessageValidator.validate_message_content(message)

def validate_callback(callback: CallbackQuery) -> Dict[str, Any]:
    """Validate callback query"""
    return MessageValidator.validate_callback_query(callback) 

def detect_image_type(data: bytes) -> str | None:
    """Return 'jpg' or 'png' when magic bytes match, otherwise None."""
    if not data:
        return None
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    return None

def validate_image_bytes(data: bytes, max_bytes: int) -> tuple[bool, str]:
    """Validate size and magic bytes for images."""
    if not data or len(data) == 0:
        return False, "empty"
    if len(data) > max_bytes:
        return False, "too_large"
    if detect_image_type(data) is None:
        return False, "invalid_type"
    return True, ""
