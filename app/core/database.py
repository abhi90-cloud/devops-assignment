import asyncpg
from typing import Optional
import logging
from contextlib import asynccontextmanager
from .config import settings

logger = logging.getLogger(__name__)

class DatabasePool:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        """Create database connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                host=settings.POSTGRES_HOST,
                port=settings.POSTGRES_PORT,
                user=settings.POSTGRES_USER,
                password=settings.POSTGRES_PASSWORD,
                database=settings.POSTGRES_DB,
                min_size=settings.DB_POOL_MIN,
                max_size=settings.DB_POOL_MAX,
                command_timeout=60,
                ssl=settings.DB_SSL
            )
            logger.info(f"Database pool created: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}")
            
            # Create tables
            await self._create_tables()
            
        except Exception as e:
            logger.error(f"Failed to create database pool: {e}")
            raise
    
    async def _create_tables(self):
        """Create database tables if not exist"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    id SERIAL PRIMARY KEY,
                    request_id UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
                    user_id UUID,
                    input_text TEXT NOT NULL,
                    prediction JSONB NOT NULL,
                    model_version VARCHAR(20),
                    confidence FLOAT,
                    processing_time_ms FLOAT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                
                CREATE INDEX IF NOT EXISTS idx_predictions_request_id ON predictions(request_id);
                CREATE INDEX IF NOT EXISTS idx_predictions_user_id ON predictions(user_id);
                CREATE INDEX IF NOT EXISTS idx_predictions_created_at ON predictions(created_at);
                CREATE INDEX IF NOT EXISTS idx_predictions_confidence ON predictions(confidence);
                
                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    username VARCHAR(50) UNIQUE NOT NULL,
                    email VARCHAR(100) UNIQUE NOT NULL,
                    api_key VARCHAR(64) UNIQUE NOT NULL,
                    is_active BOOLEAN DEFAULT true,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    last_login TIMESTAMP WITH TIME ZONE
                );
                
                CREATE INDEX IF NOT EXISTS idx_users_api_key ON users(api_key);
                CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
                
                CREATE TABLE IF NOT EXISTS api_metrics (
                    id SERIAL PRIMARY KEY,
                    endpoint VARCHAR(200),
                    method VARCHAR(10),
                    status_code INT,
                    response_time_ms FLOAT,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                
                CREATE INDEX IF NOT EXISTS idx_api_metrics_timestamp ON api_metrics(timestamp);
            """)
            logger.info("Database tables created/verified")
    
    async def close(self):
        """Close database pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database pool closed")
    
    @asynccontextmanager
    async def acquire(self):
        """Get a connection from the pool"""
        async with self.pool.acquire() as conn:
            yield conn
    
    async def execute(self, query: str, *args):
        """Execute a query"""
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)
    
    async def fetch(self, query: str, *args):
        """Fetch rows"""
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)
    
    async def fetchrow(self, query: str, *args):
        """Fetch one row"""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)
    
    async def fetchval(self, query: str, *args):
        """Fetch a single value"""
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)

# Global database pool instance
db = DatabasePool()
