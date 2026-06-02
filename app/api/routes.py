from fastapi import APIRouter, HTTPException, Depends, Request, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator
import time
import uuid
from datetime import datetime

from ..services.ai_service import ai_service
from ..core.config import settings

router = APIRouter()
security = HTTPBearer()

# Request/Response Models
class PredictionRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000, description="Text to analyze")
    use_cache: bool = Field(default=True, description="Whether to use cache")
    
    @validator('text')
    def validate_text(cls, v):
        if not v.strip():
            raise ValueError('Text cannot be empty')
        return v.strip()

class PredictionResponse(BaseModel):
    request_id: str
    text: str
    sentiment: str
    confidence: float
    model_version: str
    processing_time_ms: float
    cached: bool
    timestamp: str
    metadata: Optional[Dict[str, Any]] = None

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str
    uptime_seconds: float
    environment: str
    services: Dict[str, str]

class AnalyticsResponse(BaseModel):
    total_predictions: int
    sentiment_distribution: list
    recent_activity: list

# API Key verification
async def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify API key from request"""
    # In production, validate against database
    if credentials.credentials:
        return credentials.credentials
    raise HTTPException(status_code=401, detail="Invalid API Key")

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Enhanced health check with service status"""
    from ..core.database import db
    from ..core.redis import cache
    
    services = {
        "api": "healthy",
        "database": "healthy",
        "redis": "healthy"
    }
    
    overall_status = "healthy"
    
    # Check database
    try:
        await db.fetchval("SELECT 1")
    except Exception as e:
        services["database"] = f"error: {str(e)[:50]}"
        overall_status = "degraded"
    
    # Check Redis
    try:
        await cache.client.ping()
    except Exception as e:
        services["redis"] = f"error: {str(e)[:50]}"
        overall_status = "degraded"
    
    return HealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow().isoformat(),
        version=settings.APP_VERSION,
        uptime_seconds=time.time() - router.startup_time if hasattr(router, 'startup_time') else 0,
        environment=settings.ENVIRONMENT,
        services=services
    )

@router.post("/predict", response_model=PredictionResponse)
async def predict(
    request: PredictionRequest,
    req: Request,
    api_key: str = Depends(verify_api_key)
):
    """AI prediction endpoint"""
    try:
        start_time = time.time()
        
        # Rate limiting check (simplified)
        client_ip = req.client.host
        
        # Make prediction
        result = await ai_service.predict(
            text=request.text,
            use_cache=request.use_cache
        )
        
        return PredictionResponse(
            request_id=result.request_id,
            text=result.text,
            sentiment=result.sentiment,
            confidence=result.confidence,
            model_version=result.model_version,
            processing_time_ms=result.processing_time_ms,
            cached=result.cached,
            timestamp=datetime.utcnow().isoformat(),
            metadata=result.metadata
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Prediction failed")

@router.get("/predictions", response_model=Dict[str, Any])
async def get_predictions(
    limit: int = Query(default=10, le=100),
    offset: int = Query(default=0, ge=0),
    api_key: str = Depends(verify_api_key)
):
    """Get prediction history"""
    predictions = await ai_service.get_prediction_history(limit=limit, offset=offset)
    return {
        "predictions": predictions,
        "count": len(predictions),
        "limit": limit,
        "offset": offset
    }

@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(api_key: str = Depends(verify_api_key)):
    """Get prediction analytics"""
    analytics = await ai_service.get_analytics()
    if 'error' in analytics:
        raise HTTPException(status_code=500, detail=analytics['error'])
    return analytics

@router.get("/")
async def root():
    """API root with documentation links"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "endpoints": {
            "health": "/health",
            "predict": "/predict",
            "predictions": "/predictions",
            "analytics": "/analytics",
            "docs": "/docs"
        }
    }
