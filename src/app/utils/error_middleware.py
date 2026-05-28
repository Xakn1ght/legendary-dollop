import asyncio
import traceback
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.utils.logger import bot_logger, log_error, log_user_action


class ErrorHandlingMiddleware(BaseMiddleware):
    """Middleware to handle and log all errors in the bot"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        try:
            # Extract user information for logging
            user_id = None
            chat_id = None
            
            if isinstance(event, (Message, CallbackQuery)):
                user_id = event.from_user.id if event.from_user else None
                chat_id = event.chat.id if hasattr(event, 'chat') and event.chat else None
                
                # Log user action
                if isinstance(event, Message):
                    action = f"message: {event.text[:50] if event.text else 'no text'}"
                else:  # CallbackQuery
                    action = f"callback: {event.data[:50] if event.data else 'no data'}"
                
                log_user_action(action, user_id=user_id, chat_id=chat_id)
            
            # Execute the handler
            return await handler(event, data)
            
        except TelegramAPIError as e:
            # Handle Telegram API errors
            error_context = {
                "error_type": "telegram_api",
                "user_id": user_id,
                "chat_id": chat_id,
                "api_method": getattr(e, 'method', 'unknown'),
                "api_code": getattr(e, 'code', 'unknown')
            }
            
            if isinstance(e, TelegramBadRequest):
                # Handle bad requests (e.g., message too long, invalid chat)
                bot_logger.warning(f"Telegram Bad Request: {e}", **error_context)
                
                # Try to send a user-friendly error message
                try:
                    if isinstance(event, (Message, CallbackQuery)):
                        error_msg = "متأسفانه مشکلی در پردازش درخواست شما پیش آمد. لطفاً دوباره تلاش کنید."
                        if isinstance(event, Message):
                            await event.answer(error_msg)
                        else:
                            await event.answer(error_msg, show_alert=True)
                except:
                    pass  # Don't let error handling cause more errors
            else:
                # Log other Telegram API errors
                log_error(e, error_context, user_id=user_id)
                
        except Exception as e:
            # Handle all other errors
            handler_name = "unknown"
            if hasattr(handler, '__name__'):
                handler_name = handler.__name__
            elif hasattr(handler, 'func') and hasattr(handler.func, '__name__'):
                # Handle functools.partial objects
                handler_name = handler.func.__name__
            elif hasattr(handler, '__class__') and hasattr(handler.__class__, '__name__'):
                # Handle class instances
                handler_name = handler.__class__.__name__
            
            error_context = {
                "error_type": "general",
                "user_id": user_id,
                "chat_id": chat_id,
                "handler": handler_name,
                "event_type": type(event).__name__
            }
            
            log_error(e, error_context, user_id=user_id)
            
            # Try to send a user-friendly error message
            try:
                if isinstance(event, (Message, CallbackQuery)):
                    error_msg = "متأسفانه خطایی رخ داده است. لطفاً بعداً دوباره تلاش کنید."
                    if isinstance(event, Message):
                        await event.answer(error_msg)
                    else:
                        await event.answer(error_msg, show_alert=True)
            except:
                pass  # Don't let error handling cause more errors

class RateLimitMiddleware(BaseMiddleware):
    """Enhanced rate limiting middleware with multiple strategies"""
    
    def __init__(self, 
                 general_rate_limit: int = 15, 
                 general_window: int = 60,
                 command_rate_limit: int = 5,
                 command_window: int = 30,
                 callback_rate_limit: int = 10,
                 callback_window: int = 30):
        self.general_rate_limit = general_rate_limit
        self.general_window = general_window
        self.command_rate_limit = command_rate_limit
        self.command_window = command_window
        self.callback_rate_limit = callback_rate_limit
        self.callback_window = callback_window
        
        # Separate tracking for different types
        self.user_messages = {}  # {user_id: [timestamps]}
        self.user_commands = {}  # {user_id: [timestamps]}
        self.user_callbacks = {}  # {user_id: [timestamps]}
        
        # Blocked users (temporary bans)
        self.blocked_users = {}  # {user_id: block_until_timestamp}
        
        super().__init__()
    
    def _is_command(self, event) -> bool:
        """Check if event is a command"""
        if isinstance(event, Message) and event.text:
            return event.text.startswith('/')
        return False
    
    def _is_callback(self, event) -> bool:
        """Check if event is a callback query"""
        return isinstance(event, CallbackQuery)
    
    def _cleanup_old_entries(self, user_id: int, current_time: float):
        """Clean up old entries for all tracking types"""
        # Clean general messages
        if user_id in self.user_messages:
            self.user_messages[user_id] = [
                ts for ts in self.user_messages[user_id] 
                if current_time - ts < self.general_window
            ]
        
        # Clean commands
        if user_id in self.user_commands:
            self.user_commands[user_id] = [
                ts for ts in self.user_commands[user_id] 
                if current_time - ts < self.command_window
            ]
        
        # Clean callbacks
        if user_id in self.user_callbacks:
            self.user_callbacks[user_id] = [
                ts for ts in self.user_callbacks[user_id] 
                if current_time - ts < self.callback_window
            ]
    
    def _check_blocked_user(self, user_id: int, current_time: float) -> bool:
        """Check if user is temporarily blocked"""
        if user_id in self.blocked_users:
            if current_time < self.blocked_users[user_id]:
                return True
            else:
                # Remove expired block
                del self.blocked_users[user_id]
        return False
    
    def _block_user(self, user_id: int, duration: int = 300):
        """Temporarily block user (default 5 minutes)"""
        current_time = asyncio.get_event_loop().time()
        self.blocked_users[user_id] = current_time + duration
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if not isinstance(event, (Message, CallbackQuery)):
            return await handler(event, data)
        
        user_id = event.from_user.id if event.from_user else None
        if not user_id:
            return await handler(event, data)
        
        current_time = asyncio.get_event_loop().time()
        
        # Check if user is blocked
        if self._check_blocked_user(user_id, current_time):
            from app.utils.logger import log_rate_limit_violation
            log_rate_limit_violation(user_id, "user_blocked", 0, 0)
            
            try:
                if isinstance(event, Message):
                    await event.answer("شما موقتاً مسدود شده‌اید. لطفاً بعداً تلاش کنید.")
                else:
                    await event.answer("شما موقتاً مسدود شده‌اید. لطفاً بعداً تلاش کنید.", show_alert=True)
            except:
                pass
            return
        
        # Clean up old entries
        self._cleanup_old_entries(user_id, current_time)
        
        # Initialize tracking if needed
        if user_id not in self.user_messages:
            self.user_messages[user_id] = []
        if user_id not in self.user_commands:
            self.user_commands[user_id] = []
        if user_id not in self.user_callbacks:
            self.user_callbacks[user_id] = []
        
        # Check rate limits based on event type
        rate_limit_exceeded = False
        violation_type = ""
        
        if self._is_command(event):
            # Check command rate limit
            if len(self.user_commands[user_id]) >= self.command_rate_limit:
                rate_limit_exceeded = True
                violation_type = "command_rate_limit"
            else:
                self.user_commands[user_id].append(current_time)
        
        elif self._is_callback(event):
            # Check callback rate limit
            if len(self.user_callbacks[user_id]) >= self.callback_rate_limit:
                rate_limit_exceeded = True
                violation_type = "callback_rate_limit"
            else:
                self.user_callbacks[user_id].append(current_time)
        
        else:
            # Check general message rate limit
            if len(self.user_messages[user_id]) >= self.general_rate_limit:
                rate_limit_exceeded = True
                violation_type = "general_rate_limit"
            else:
                self.user_messages[user_id].append(current_time)
        
        # Handle rate limit violation
        if rate_limit_exceeded:
            from app.utils.logger import log_rate_limit_violation
            
            # Log the violation
            if violation_type == "command_rate_limit":
                log_rate_limit_violation(user_id, violation_type, self.command_rate_limit, self.command_window)
            elif violation_type == "callback_rate_limit":
                log_rate_limit_violation(user_id, violation_type, self.callback_rate_limit, self.callback_window)
            else:
                log_rate_limit_violation(user_id, violation_type, self.general_rate_limit, self.general_window)
            
            # Check for repeated violations (spam detection)
            total_violations = (
                len(self.user_messages[user_id]) + 
                len(self.user_commands[user_id]) + 
                len(self.user_callbacks[user_id])
            )
            
            if total_violations > 50:  # Excessive violations
                self._block_user(user_id, 600)  # Block for 10 minutes
                from app.utils.logger import log_spam_detection
                log_spam_detection(user_id, total_violations, 60)
            
            # Send appropriate message
            try:
                if isinstance(event, Message):
                    await event.answer("لطفاً کمی صبر کنید و دوباره تلاش کنید.")
                else:
                    await event.answer("لطفاً کمی صبر کنید و دوباره تلاش کنید.", show_alert=True)
            except:
                pass
            return
        
        # Continue with handler
        return await handler(event, data)

class ValidationMiddleware(BaseMiddleware):
    """Enhanced middleware to validate user permissions, input data, and security"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if not isinstance(event, (Message, CallbackQuery)):
            return await handler(event, data)
        
        user_id = event.from_user.id if event.from_user else None
        if not user_id:
            return await handler(event, data)
        
        # 1. User Permission Validation
        if not await self._validate_user_permissions(user_id, event):
            return
        
        # 2. Input Content Validation
        validation_result = await self._validate_input_content(event)
        if not validation_result['is_valid']:
            await self._handle_validation_error(event, validation_result)
            return
        
        # 3. Security Checks
        if not await self._perform_security_checks(event, user_id):
            return
        
        # Add validation result to data for handlers to use
        data['validation_result'] = validation_result
        
        # Continue with handler
        return await handler(event, data)
    
    async def _validate_user_permissions(self, user_id: int, event) -> bool:
        """Validate user permissions.

        Access for end-users is gated by the /start + referral flow in handlers, not by
        ``allowed_users.json``. That file is only for OG detection and is often a JSON *array*;
        the previous ``str(user_id) in loaded_json`` check treated every non-admin as blocked
        or behaved unpredictably. Keep this middleware hook for future use; do not whitelist here.
        """
        return True
    
    async def _validate_input_content(self, event) -> Dict[str, Any]:
        """Validate input content using validation utilities"""
        from app.utils.validation import validate_callback, validate_message
        
        if isinstance(event, Message):
            return validate_message(event)
        elif isinstance(event, CallbackQuery):
            return validate_callback(event)
        else:
            return {'is_valid': True, 'errors': [], 'warnings': []}
    
    async def _handle_validation_error(self, event, validation_result: Dict[str, Any]):
        """Handle validation errors"""
        error_message = "داده‌های ورودی نامعتبر است."
        
        if validation_result.get('errors'):
            # Use first error as specific message
            first_error = validation_result['errors'][0]
            if 'too long' in first_error.lower():
                error_message = "پیام خیلی طولانی است."
            elif 'invalid filename' in first_error.lower():
                error_message = "نام فایل نامعتبر است."
            elif 'unsupported content' in first_error.lower():
                error_message = "نوع محتوا پشتیبانی نمی‌شود."
        
        try:
            if isinstance(event, Message):
                await event.answer(error_message)
            else:
                await event.answer(error_message, show_alert=True)
        except:
            pass
        
        # Log validation error
        user_id = event.from_user.id if event.from_user else None
        bot_logger.warning(f"Input validation failed for user {user_id}", 
                          errors=validation_result.get('errors', []),
                          warnings=validation_result.get('warnings', []))
    
    async def _perform_security_checks(self, event, user_id: int) -> bool:
        """Perform security checks on input"""
        try:
            # Check for suspicious patterns in text
            if isinstance(event, Message) and event.text:
                text = event.text.lower()
                
                # Check for potential SQL injection patterns
                sql_patterns = [
                    'union select', 'drop table', 'delete from', 
                    'insert into', 'update set', '--', '/*', '*/'
                ]
                
                for pattern in sql_patterns:
                    if pattern in text:
                        bot_logger.warning(f"Potential SQL injection attempt by user {user_id}", 
                                          pattern=pattern, text=text[:100])
                        await self._handle_security_violation(event, "sql_injection")
                        return False
                
                # Check for potential XSS patterns
                xss_patterns = [
                    '<script', 'javascript:', 'onload=', 'onerror=',
                    'onclick=', 'onmouseover=', 'eval(', 'document.cookie'
                ]
                
                for pattern in xss_patterns:
                    if pattern in text:
                        bot_logger.warning(f"Potential XSS attempt by user {user_id}", 
                                          pattern=pattern, text=text[:100])
                        await self._handle_security_violation(event, "xss")
                        return False
                
                # Check for excessive repetition (spam detection)
                if len(text) > 10:
                    words = text.split()
                    if len(words) > 3:
                        word_counts = {}
                        for word in words:
                            word_counts[word] = word_counts.get(word, 0) + 1
                        
                        max_repetition = max(word_counts.values())
                        if max_repetition > len(words) * 0.7:  # 70% repetition
                            bot_logger.warning(f"Potential spam detected for user {user_id}", 
                                              repetition_ratio=max_repetition/len(words))
                            await self._handle_security_violation(event, "spam")
                            return False
            
            # Check for suspicious file uploads
            if isinstance(event, Message) and event.document:
                filename = event.document.file_name.lower()
                dangerous_extensions = ['.exe', '.bat', '.cmd', '.com', '.pif', '.scr']
                
                for ext in dangerous_extensions:
                    if filename.endswith(ext):
                        bot_logger.warning(f"Potential malicious file upload by user {user_id}", 
                                          filename=filename)
                        await self._handle_security_violation(event, "malicious_file")
                        return False
            
        except Exception as e:
            bot_logger.error(f"Error in security checks: {e}")
            # Continue if security checks fail
        
        return True
    
    async def _handle_security_violation(self, event, violation_type: str):
        """Handle security violations"""
        violation_messages = {
            "sql_injection": "داده‌های ورودی نامعتبر است.",
            "xss": "داده‌های ورودی نامعتبر است.",
            "spam": "لطفاً از ارسال پیام‌های تکراری خودداری کنید.",
            "malicious_file": "نوع فایل مجاز نیست."
        }
        
        message = violation_messages.get(violation_type, "عملیات نامعتبر است.")
        
        try:
            if isinstance(event, Message):
                await event.answer(message)
            else:
                await event.answer(message, show_alert=True)
        except:
            pass
        
        # Log security violation
        user_id = event.from_user.id if event.from_user else None
        bot_logger.warning(f"Security violation by user {user_id}", 
                          violation_type=violation_type)

class PerformanceMiddleware(BaseMiddleware):
    """Middleware to track performance metrics"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        import time
        start_time = time.time()
        
        try:
            result = await handler(event, data)
            duration = time.time() - start_time
            
            # Log slow operations
            if duration > 1.0:  # Log operations taking more than 1 second
                user_id = None
                if isinstance(event, (Message, CallbackQuery)) and event.from_user:
                    user_id = event.from_user.id
                
                handler_name = getattr(handler, '__name__', str(handler))
                bot_logger.warning(
                    f"Slow operation detected: {handler_name} took {duration:.2f}s",
                    user_id=user_id,
                    duration=duration,
                    handler=handler_name
                )
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            handler_name = getattr(handler, '__name__', str(handler))
            log_error(e, {
                "handler": handler_name,
                "duration": duration
            })
            raise 