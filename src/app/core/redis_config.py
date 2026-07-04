"""
Redis configuration and connection management for ASSTRO bot
"""

import json
import logging
import pickle
import time
from datetime import timedelta
from typing import Any, Dict, List, Optional, Union

import redis.asyncio as redis

from app.core.settings import REDIS_DB, REDIS_HOST, REDIS_PASSWORD, REDIS_PORT
from app.utils.logger import log_database_operation, log_error

# Redis configuration
REDIS_CONFIG = {
    "host": REDIS_HOST,
    "port": REDIS_PORT,
    "db": REDIS_DB,
    "password": REDIS_PASSWORD,
    "decode_responses": False,  # Keep as bytes for pickle compatibility
    "max_connections": 20,
    "retry_on_timeout": True,
    "socket_keepalive": True,
    "socket_keepalive_options": {},
    "health_check_interval": 30,
    "socket_connect_timeout": 5,
    "socket_timeout": 5,
}

# Cache configuration
CACHE_CONFIG = {
    # Default TTL for different data types (in seconds)
    "default_ttl": 3600,  # 1 hour
    "user_data_ttl": 1800,  # 30 minutes
    "subscription_data_ttl": 900,  # 15 minutes
    "leaderboard_ttl": 300,  # 5 minutes
    "analytics_ttl": 600,  # 10 minutes
    "achievement_ttl": 7200,  # 2 hours
    "challenge_ttl": 1800,  # 30 minutes
    "reward_data_ttl": 3600,  # 1 hour
    "rate_limit_ttl": 60,  # 1 minute
    "session_ttl": 86400,  # 24 hours
    
    # Cache key prefixes
    "key_prefixes": {
        "user": "user:",
        "subscription": "sub:",
        "referral": "ref:",
        "reward": "reward:",
        "achievement": "ach:",
        "challenge": "ch:",
        "leaderboard": "lb:",
        "analytics": "analytics:",
        "rate_limit": "rate:",
        "session": "session:",
        "lock": "lock:",
        "counter": "counter:",
    },
    
    # Cache invalidation patterns
    "invalidation_patterns": {
        "user_data": ["user:*", "sub:*", "ref:*"],
        "subscription_data": ["sub:*", "user:*"],
        "reward_data": ["reward:*", "user:*"],
        "leaderboard_data": ["lb:*"],
        "analytics_data": ["analytics:*"],
    }
}

# Global Redis connection pool
redis_pool: Optional[redis.ConnectionPool] = None
redis_client: Optional[redis.Redis] = None

async def init_redis():
    """Initialize Redis connection pool and client"""
    global redis_pool, redis_client
    
    try:
        # Create connection pool
        redis_pool = redis.ConnectionPool(**REDIS_CONFIG)
        
        # Create Redis client
        redis_client = redis.Redis(connection_pool=redis_pool)
        
        # Test connection
        await redis_client.ping()
        
        logging.info("Redis connection established")
        return True
        
    except Exception as e:
        logging.error(f"Failed to connect to Redis: {e}")
        # Ensure we clean up if half-initialized
        if redis_client:
            await redis_client.close()
        if redis_pool:
            await redis_pool.disconnect()
        redis_pool = None
        redis_client = None
        return False

async def get_redis_client() -> Optional[redis.Redis]:
    """Get Redis client instance"""
    if redis_client is None:
        # Try initializing if not already done
        await init_redis()
    return redis_client

async def close_redis():
    """Close Redis connections"""
    global redis_pool, redis_client
    
    if redis_client:
        await redis_client.close()
        redis_client = None
    
    if redis_pool:
        await redis_pool.disconnect()
        redis_pool = None
    
    logging.info("Redis connections closed")

class RedisCache:
    """Redis caching utility class with in-memory fallback"""
    
    def __init__(self):
        self.client = None
        self.config = CACHE_CONFIG
        # Memory fallback: {key: (value, expire_at)}
        self._memory_cache = {}
    
    async def _get_client(self):
        """Get Redis client"""
        if self.client is None:
            self.client = await get_redis_client()
        return self.client
    
    def _get_key(self, prefix: str, identifier: Union[str, int]) -> str:
        """Generate cache key"""
        return f"{self.config['key_prefixes'].get(prefix, prefix)}{identifier}"
    
    def _serialize(self, data: Any) -> bytes:
        """Serialize data for storage"""
        try:
            return pickle.dumps(data)
        except Exception as e:
            log_error(e, {"operation": "redis_serialize", "data_type": type(data).__name__})
            # Fallback to JSON for simple types
            return json.dumps(data, default=str).encode('utf-8')
    
    def _deserialize(self, data: bytes) -> Any:
        """Deserialize data from storage"""
        try:
            return pickle.loads(data)
        except Exception:
            # Fallback to JSON for simple types
            return json.loads(data.decode('utf-8'))
    
    def _clean_memory_cache(self):
        """Remove expired items from memory cache"""
        now = time.time()
        keys_to_remove = [k for k, (_, exp) in self._memory_cache.items() if exp is not None and exp < now]
        for k in keys_to_remove:
            del self._memory_cache[k]

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set cache value"""
        try:
            client = await self._get_client()
            
            default_ttl = self.config.get("default_ttl", 3600)
            cache_ttl = ttl if ttl is not None else default_ttl

            if client is None:
                # Fallback to memory
                expiry = time.time() + cache_ttl if cache_ttl else None
                self._memory_cache[key] = (value, expiry)
                return True
            
            serialized_value = self._serialize(value)
            result = await client.setex(key, cache_ttl, serialized_value)
            return bool(result)
            
        except Exception as e:
            log_error(e, {"operation": "redis_set", "key": key})
            # Fallback on exception too
            try:
                default_ttl = self.config.get("default_ttl", 3600)
                cache_ttl = ttl if ttl is not None else default_ttl
                expiry = time.time() + cache_ttl if cache_ttl else None
                self._memory_cache[key] = (value, expiry)
                return True
            except:
                return False
    
    async def get(self, key: str) -> Optional[Any]:
        """Get cache value"""
        try:
            client = await self._get_client()
            if client is None:
                # Fallback to memory
                self._clean_memory_cache()
                item = self._memory_cache.get(key)
                if item:
                    val, exp = item
                    if exp is None or exp > time.time():
                        return val
                    else:
                        del self._memory_cache[key]
                return None
            
            data = await client.get(key)
            if data is None:
                return None
            
            return self._deserialize(data)
            
        except Exception as e:
            log_error(e, {"operation": "redis_get", "key": key})
            # Try memory as fallback
            item = self._memory_cache.get(key)
            if item:
                val, exp = item
                if exp is None or exp > time.time():
                    return val
            return None
    
    async def delete(self, key: str) -> bool:
        """Delete cache key"""
        # Always delete from memory too
        if key in self._memory_cache:
            del self._memory_cache[key]

        try:
            client = await self._get_client()
            if client is None:
                return True
            
            result = await client.delete(key)
            return bool(result)
            
        except Exception as e:
            log_error(e, {"operation": "redis_delete", "key": key})
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        try:
            client = await self._get_client()
            if client is None:
                # Fallback to memory
                self._clean_memory_cache()
                return key in self._memory_cache
            
            result = await client.exists(key)
            return bool(result)
            
        except Exception as e:
            log_error(e, {"operation": "redis_exists", "key": key})
            # Check memory
            self._clean_memory_cache()
            return key in self._memory_cache
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set key expiration"""
        try:
            # Handle memory cache
            if key in self._memory_cache:
                val, _ = self._memory_cache[key]
                self._memory_cache[key] = (val, time.time() + ttl)

            client = await self._get_client()
            if client is None:
                return True # Pretend success for memory
            
            result = await client.expire(key, ttl)
            return bool(result)
            
        except Exception as e:
            log_error(e, {"operation": "redis_expire", "key": key})
            return False
    
    async def ttl(self, key: str) -> int:
        """Get key TTL"""
        try:
            client = await self._get_client()
            if client is None:
                 # Fallback to memory
                if key in self._memory_cache:
                    _, exp = self._memory_cache[key]
                    if exp:
                        return int(exp - time.time())
                return -2 # Not found or expired

            return await client.ttl(key)
            
        except Exception as e:
            log_error(e, {"operation": "redis_ttl", "key": key})
            return -1
    
    # Note: Complex types (list, set, hash) are harder to fully fallback to memory 
    # seamlessly without re-implementing Redis logic. 
    # For now, we return None/False if Redis is down for these, 
    # except where critical basic caching is needed.

    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment counter"""
        try:
            client = await self._get_client()
            if client is None:
                # Memory fallback
                if key in self._memory_cache:
                    val, exp = self._memory_cache[key]
                    try:
                        new_val = int(val) + amount
                        self._memory_cache[key] = (new_val, exp)
                        return new_val
                    except:
                        pass
                self._memory_cache[key] = (amount, None)
                return amount
            
            return await client.incrby(key, amount)
            
        except Exception as e:
            log_error(e, {"operation": "redis_increment", "key": key})
            return None
    
    async def decrement(self, key: str, amount: int = 1) -> Optional[int]:
        """Decrement counter"""
        try:
            client = await self._get_client()
            if client is None:
                 # Memory fallback
                if key in self._memory_cache:
                    val, exp = self._memory_cache[key]
                    try:
                        new_val = int(val) - amount
                        self._memory_cache[key] = (new_val, exp)
                        return new_val
                    except:
                        pass
                self._memory_cache[key] = (-amount, None)
                return -amount
            
            return await client.decrby(key, amount)
            
        except Exception as e:
            log_error(e, {"operation": "redis_decrement", "key": key})
            return None
    
    async def set_hash(self, key: str, field: str, value: Any) -> bool:
        """Set hash field"""
        try:
            client = await self._get_client()
            if client is None:
                return False # No memory fallback for hash yet
            
            serialized_value = self._serialize(value)
            result = await client.hset(key, field, serialized_value)
            return bool(result)
            
        except Exception as e:
            log_error(e, {"operation": "redis_set_hash", "key": key, "field": field})
            return False
    
    async def get_hash(self, key: str, field: str) -> Optional[Any]:
        """Get hash field"""
        try:
            client = await self._get_client()
            if client is None:
                return None
            
            data = await client.hget(key, field)
            if data is None:
                return None
            
            return self._deserialize(data)
            
        except Exception as e:
            log_error(e, {"operation": "redis_get_hash", "key": key, "field": field})
            return None
    
    async def get_all_hash(self, key: str) -> Dict[str, Any]:
        """Get all hash fields"""
        try:
            client = await self._get_client()
            if client is None:
                return {}
            
            data = await client.hgetall(key)
            result = {}
            
            for field, value in data.items():
                field_str = field.decode('utf-8') if isinstance(field, bytes) else field
                result[field_str] = self._deserialize(value)
            
            return result
            
        except Exception as e:
            log_error(e, {"operation": "redis_get_all_hash", "key": key})
            return {}
    
    async def delete_hash(self, key: str, field: str) -> bool:
        """Delete hash field"""
        try:
            client = await self._get_client()
            if client is None:
                return False
            
            result = await client.hdel(key, field)
            return bool(result)
            
        except Exception as e:
            log_error(e, {"operation": "redis_delete_hash", "key": key, "field": field})
            return False
    
    async def add_to_set(self, key: str, value: str) -> bool:
        """Add value to set"""
        try:
            client = await self._get_client()
            if client is None:
                return False
            
            result = await client.sadd(key, value)
            return bool(result)
            
        except Exception as e:
            log_error(e, {"operation": "redis_add_to_set", "key": key, "value": value})
            return False
    
    async def is_in_set(self, key: str, value: str) -> bool:
        """Check if value is in set"""
        try:
            client = await self._get_client()
            if client is None:
                return False
            
            result = await client.sismember(key, value)
            return bool(result)
            
        except Exception as e:
            log_error(e, {"operation": "redis_is_in_set", "key": key, "value": value})
            return False
    
    async def get_set_members(self, key: str) -> List[str]:
        """Get all set members"""
        try:
            client = await self._get_client()
            if client is None:
                return []
            
            data = await client.smembers(key)
            return [item.decode('utf-8') if isinstance(item, bytes) else item for item in data]
            
        except Exception as e:
            log_error(e, {"operation": "redis_get_set_members", "key": key})
            return []
    
    async def add_to_list(self, key: str, value: Any, max_length: Optional[int] = None) -> bool:
        """Add value to list"""
        try:
            client = await self._get_client()
            if client is None:
                return False
            
            serialized_value = self._serialize(value)
            
            # Add to list
            await client.lpush(key, serialized_value)
            
            # Trim if max_length specified
            if max_length is not None:
                await client.ltrim(key, 0, max_length - 1)
            
            return True
            
        except Exception as e:
            log_error(e, {"operation": "redis_add_to_list", "key": key})
            return False
    
    async def get_list(self, key: str, start: int = 0, end: int = -1) -> List[Any]:
        """Get list values"""
        try:
            client = await self._get_client()
            if client is None:
                return []
            
            data = await client.lrange(key, start, end)
            return [self._deserialize(item) for item in data]
            
        except Exception as e:
            log_error(e, {"operation": "redis_get_list", "key": key})
            return []
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate keys matching pattern"""
        # Simple memory invalidation by prefix
        count = 0
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            keys_to_remove = [k for k in self._memory_cache.keys() if k.startswith(prefix)]
            for k in keys_to_remove:
                del self._memory_cache[k]
                count += 1
        
        try:
            client = await self._get_client()
            if client is None:
                return count
            
            keys = await client.keys(pattern)
            if keys:
                result = await client.delete(*keys)
                return result + count
            return count
            
        except Exception as e:
            log_error(e, {"operation": "redis_invalidate_pattern", "pattern": pattern})
            return count
    
    async def invalidate_user_data(self, user_id: int) -> bool:
        """Invalidate all user-related cache"""
        try:
            patterns = self.config["invalidation_patterns"]["user_data"]
            total_deleted = 0
            
            for pattern in patterns:
                # Replace wildcards with user_id
                specific_pattern = pattern.replace("*", str(user_id))
                deleted = await self.invalidate_pattern(specific_pattern)
                total_deleted += deleted
            
            return total_deleted > 0
            
        except Exception as e:
            log_error(e, {"operation": "redis_invalidate_user_data", "user_id": user_id})
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get Redis statistics"""
        try:
            client = await self._get_client()
            if client is None:
                return {"memory_cache_size": len(self._memory_cache)}
            
            info = await client.info()
            return {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "uptime_in_seconds": info.get("uptime_in_seconds", 0),
            }
            
        except Exception as e:
            log_error(e, {"operation": "redis_get_stats"})
            return {}

# Global cache instance
cache = RedisCache()

# Cache decorators
def cached(ttl: Optional[int] = None, key_prefix: str = "cache"):
    """Cache decorator for functions"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Generate cache key
            key_parts = [key_prefix, func.__name__]
            key_parts.extend([str(arg) for arg in args])
            key_parts.extend([f"{k}:{v}" for k, v in sorted(kwargs.items())])
            cache_key = ":".join(key_parts)
            
            # Try to get from cache
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator

def cache_invalidate(pattern: str):
    """Cache invalidation decorator"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            await cache.invalidate_pattern(pattern)
            return result
        return wrapper
    return decorator
