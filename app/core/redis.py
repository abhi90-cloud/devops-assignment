import redis.asyncio as redis
import json
import logging
from typing import Optional, Any
from .config import settings

logger = logging.getLogger(__name__)

class RedisCache:
    def __init__(self):
        self.client: Optional[redis.Redis] = None
    
    async def connect(self):
        """Create Redis connection"""
        try:
            self.client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD,
                db=settings.REDIS_DB,
                decode_responses=True,
                socket_keepalive=True,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            await self.client.ping()
            logger.info(f"Redis connected: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def close(self):
        """Close Redis connection"""
        if self.client:
            await self.client.close()
            logger.info("Redis connection closed")
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            value = await self.client.get(key)
            return json.loads(value) if value else None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: int = None):
        """Set value in cache"""
        try:
            ttl = ttl or settings.CACHE_TTL
            await self.client.setex(
                key, 
                ttl, 
                json.dumps(value)
            )
            return True
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False
    
    async def delete(self, key: str):
        """Delete key from cache"""
        try:
            await self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False
    
    async def clear_pattern(self, pattern: str):
        """Clear keys matching pattern"""
        try:
            keys = await self.client.keys(pattern)
            if keys:
                await self.client.delete(*keys)
            return len(keys)
        except Exception as e:
            logger.error(f"Redis clear pattern error: {e}")
            return 0
    
    async def increment(self, key: str, amount: int = 1):
        """Increment counter"""
        try:
            return await self.client.incrby(key, amount)
        except Exception as e:
            logger.error(f"Redis increment error: {e}")
            return 0

# Global Redis cache instance
cache = RedisCache()
