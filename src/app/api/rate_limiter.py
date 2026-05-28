"""
Rate Limiting Middleware for aiohttp

Protects against abuse and DDoS attacks by limiting requests per IP address.
Features:
- Configurable default limit (100 requests/minute)
- Per-endpoint custom limits (stricter for auth endpoints)
- Automatic cleanup of expired entries
- Memory-efficient storage
"""

import asyncio
import time
from collections import defaultdict
from typing import Awaitable, Callable, Dict, Optional

from aiohttp import web

from app.core.settings import TRUST_PROXY_HEADERS

# Default rate limit settings
DEFAULT_REQUESTS_PER_MINUTE = 100
DEFAULT_WINDOW_SECONDS = 60

# Stricter limits for sensitive endpoints (requests per minute)
ENDPOINT_LIMITS: Dict[str, int] = {
    # Authentication endpoints - stricter limits to prevent brute force
    "/api/admin/login": 10,
    "/api/admin/verify-2fa": 10,
    "/api/admin/logout": 20,
    "/api/dashboard/login": 15,
    # Admin sensitive operations (state-changing)
    "/api/admin/broadcast": 5,
    "/api/admin/notifications/send": 15,
    "/api/admin/receipts": 30,          # approve/deny/pending listing
    "/api/admin/sessions": 30,          # revoke/revoke-others
    "/api/admin/settings": 40,          # settings updates
    "/api/admin/ui": 60,                # theme / uploads
    # Purchase endpoints - moderate limits
    "/api/dashboard/purchase/start": 20,
    "/api/dashboard/purchase/receipt": 20,
    # Ticket creation - prevent spam
    "/api/dashboard/tickets": 30,  # POST creates ticket
}


class RateLimiter:
    """
    In-memory rate limiter that tracks requests by IP address and endpoint.
    
    Uses a sliding window approach with automatic cleanup of expired entries.
    """
    
    def __init__(
        self,
        default_limit: int = DEFAULT_REQUESTS_PER_MINUTE,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
        endpoint_limits: Optional[Dict[str, int]] = None,
        cleanup_interval: int = 60
    ):
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self.endpoint_limits = endpoint_limits or ENDPOINT_LIMITS
        self.cleanup_interval = cleanup_interval
        
        # Storage: {ip_address: {endpoint: [(timestamp, count), ...]}}
        # Using a simpler approach: {(ip, endpoint): [timestamps]}
        self._requests: Dict[tuple, list] = defaultdict(list)
        self._last_cleanup = time.time()
        self._lock = asyncio.Lock()
    
    def _get_client_ip(self, request: web.Request) -> str:
        """
        Extract client IP address from request.
        Handles X-Forwarded-For header for proxy setups.
        """
        if TRUST_PROXY_HEADERS:
            # Check for forwarded IP (behind proxy/load balancer)
            forwarded = request.headers.get('X-Forwarded-For')
            if forwarded:
                # Take the first IP in the chain (original client)
                return forwarded.split(',')[0].strip()
            
            # Check X-Real-IP header
            real_ip = request.headers.get('X-Real-IP')
            if real_ip:
                return real_ip.strip()
        
        # Fall back to direct connection IP
        peername = request.transport.get_extra_info('peername')
        if peername:
            return peername[0]
        
        return 'unknown'
    
    def _get_limit_for_endpoint(self, path: str, method: str) -> int:
        """
        Get the rate limit for a specific endpoint.
        Returns custom limit if defined, otherwise default.
        """
        # Check exact match first
        if path in self.endpoint_limits:
            return self.endpoint_limits[path]
        
        # Check for prefix matches (for parameterized routes)
        for endpoint, limit in self.endpoint_limits.items():
            if path.startswith(endpoint.rstrip('/')):
                return limit
        
        return self.default_limit
    
    def _cleanup_old_entries(self, current_time: float) -> None:
        """Remove expired request timestamps."""
        cutoff = current_time - self.window_seconds
        keys_to_delete = []
        
        for key, timestamps in self._requests.items():
            # Filter out old timestamps
            self._requests[key] = [ts for ts in timestamps if ts > cutoff]
            # Mark empty entries for deletion
            if not self._requests[key]:
                keys_to_delete.append(key)
        
        # Remove empty entries
        for key in keys_to_delete:
            del self._requests[key]
    
    async def is_rate_limited(self, request: web.Request) -> tuple[bool, int, int]:
        """
        Check if a request should be rate limited.
        
        Returns:
            tuple: (is_limited, remaining_requests, retry_after_seconds)
        """
        current_time = time.time()
        ip = self._get_client_ip(request)
        path = request.path
        method = request.method
        
        # Create a key combining IP and endpoint for per-endpoint tracking
        key = (ip, path)
        limit = self._get_limit_for_endpoint(path, method)
        
        async with self._lock:
            # Periodic cleanup
            if current_time - self._last_cleanup > self.cleanup_interval:
                self._cleanup_old_entries(current_time)
                self._last_cleanup = current_time
            
            # Get timestamps for this IP/endpoint combination
            timestamps = self._requests[key]
            
            # Filter to only include requests within the current window
            cutoff = current_time - self.window_seconds
            valid_timestamps = [ts for ts in timestamps if ts > cutoff]
            self._requests[key] = valid_timestamps
            
            request_count = len(valid_timestamps)
            remaining = max(0, limit - request_count)
            
            if request_count >= limit:
                # Calculate retry-after (time until oldest request expires)
                if valid_timestamps:
                    oldest = min(valid_timestamps)
                    retry_after = int(oldest + self.window_seconds - current_time) + 1
                else:
                    retry_after = self.window_seconds
                return True, 0, retry_after
            
            # Record this request
            self._requests[key].append(current_time)
            return False, remaining - 1, 0
    
    def get_stats(self) -> Dict:
        """Get current rate limiter statistics."""
        return {
            'tracked_keys': len(self._requests),
            'total_timestamps': sum(len(ts) for ts in self._requests.values()),
            'default_limit': self.default_limit,
            'window_seconds': self.window_seconds,
        }


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def reset_rate_limiter() -> None:
    """Reset the global rate limiter (useful for testing)."""
    global _rate_limiter
    _rate_limiter = None


@web.middleware
async def rate_limit_middleware(
    request: web.Request,
    handler: Callable[[web.Request], Awaitable[web.Response]]
) -> web.Response:
    """
    aiohttp middleware that enforces rate limiting on /api/ routes.
    
    Adds rate limit headers to all responses:
    - X-RateLimit-Limit: Maximum requests allowed
    - X-RateLimit-Remaining: Requests remaining in current window
    - X-RateLimit-Reset: Seconds until the rate limit resets
    
    Returns 429 Too Many Requests when limit is exceeded.
    """
    path = request.path
    
    # Only apply rate limiting to API routes
    if not path.startswith('/api/'):
        return await handler(request)
    
    # Skip rate limiting for WebSocket upgrades
    if request.headers.get('Upgrade', '').lower() == 'websocket':
        return await handler(request)
    
    rate_limiter = get_rate_limiter()
    is_limited, remaining, retry_after = await rate_limiter.is_rate_limited(request)
    
    limit = rate_limiter._get_limit_for_endpoint(path, request.method)
    
    if is_limited:
        # Return 429 Too Many Requests
        response = web.json_response(
            {
                'error': 'Too Many Requests',
                'message': f'Rate limit exceeded. Please retry after {retry_after} seconds.',
                'retry_after': retry_after
            },
            status=429
        )
        response.headers['X-RateLimit-Limit'] = str(limit)
        response.headers['X-RateLimit-Remaining'] = '0'
        response.headers['X-RateLimit-Reset'] = str(retry_after)
        response.headers['Retry-After'] = str(retry_after)
        return response
    
    # Process the request normally
    response = await handler(request)
    
    # Add rate limit headers to successful responses
    # Only add headers if response is not None (some handlers may return None)
    if response is not None:
        response.headers['X-RateLimit-Limit'] = str(limit)
        response.headers['X-RateLimit-Remaining'] = str(remaining)
        response.headers['X-RateLimit-Reset'] = str(rate_limiter.window_seconds)
    
    return response


def create_rate_limiter_middleware(
    default_limit: int = DEFAULT_REQUESTS_PER_MINUTE,
    window_seconds: int = DEFAULT_WINDOW_SECONDS,
    endpoint_limits: Optional[Dict[str, int]] = None
) -> Callable:
    """
    Factory function to create a rate limiter middleware with custom settings.
    
    Args:
        default_limit: Default requests per window (default: 100)
        window_seconds: Time window in seconds (default: 60)
        endpoint_limits: Dict mapping endpoint paths to custom limits
    
    Returns:
        Configured middleware function
    """
    global _rate_limiter
    _rate_limiter = RateLimiter(
        default_limit=default_limit,
        window_seconds=window_seconds,
        endpoint_limits=endpoint_limits or ENDPOINT_LIMITS
    )
    return rate_limit_middleware
