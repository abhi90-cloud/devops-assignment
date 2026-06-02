from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, List
import os
from functools import lru_cache

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "DevOps AI Platform"
    APP_VERSION: str = "2.0.0"
    ENVIRONMENT: str = Field(default="production")
    DEBUG: bool = Field(default=False)
    LOG_LEVEL: str = Field(default="INFO")
    
    # Server
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)
    WORKERS: int = Field(default=4)
    
    # Database
    POSTGRES_HOST: str = Field(default="postgres")
    POSTGRES_PORT: int = Field(default=5432)
    POSTGRES_USER: str = Field(default="devopsadmin")
    POSTGRES_PASSWORD: str = Field(default="")
    POSTGRES_DB: str = Field(default="devopsdb")
    DB_POOL_MIN: int = Field(default=5)
    DB_POOL_MAX: int = Field(default=20)
    DB_SSL: bool = Field(default=False)
    
    # Redis
    REDIS_HOST: str = Field(default="redis")
    REDIS_PORT: int = Field(default=6379)
    REDIS_PASSWORD: str = Field(default="")
    REDIS_DB: int = Field(default=0)
    CACHE_TTL: int = Field(default=3600)
    
    # Security
    SECRET_KEY: str = Field(default="change-me-in-production")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_EXPIRE_MINUTES: int = Field(default=30)
    CORS_ORIGINS: List[str] = Field(default=["*"])
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = Field(default=100)
    RATE_LIMIT_PERIOD: int = Field(default=60)
    
    # AI Model Configuration
    MODEL_VERSION: str = Field(default="v2.0.0")
    MODEL_CONFIDENCE_THRESHOLD: float = Field(default=0.7)
    MAX_TEXT_LENGTH: int = Field(default=1000)
    
    # Monitoring
    PROMETHEUS_ENABLED: bool = Field(default=True)
    SENTRY_DSN: Optional[str] = Field(default=None)
    
    # Backup
    BACKUP_RETENTION_DAYS: int = Field(default=7)
    S3_BACKUP_BUCKET: Optional[str] = Field(default=None)
    
    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
