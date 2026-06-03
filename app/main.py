from fastapi import FastAPI, HTTPException, Request, Depends, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from contextlib import asynccontextmanager
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
import logging
import time
import uuid
import json
import os
import asyncpg
import redis.asyncio as redis
import hashlib

# Prometheus metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('request_latency_seconds', 'Request latency in seconds')
PREDICTION_COUNT = Counter('predictions_total', 'Total predictions', ['sentiment'])

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

db_pool = None
redis_client = None
app_start_time = time.time()

security = HTTPBearer(auto_error=False)

class PredictionRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    text: str = Field(..., min_length=1, max_length=1000)
    use_cache: bool = Field(default=True)
    model_version: Optional[str] = Field(default="2.0.0")

class SentimentAnalyzer:
    def __init__(self):
        self.lexicon = {
            'strong_positive': ['excellent', 'outstanding', 'exceptional', 'superb', 'magnificent',
                              'brilliant', 'phenomenal', 'extraordinary', 'remarkable', 'incredible'],
            'positive': ['good', 'great', 'nice', 'wonderful', 'fantastic', 'amazing',
                        'love', 'happy', 'pleased', 'satisfied', 'impressive', 'enjoy'],
            'neutral': ['okay', 'fine', 'average', 'normal', 'standard', 'regular'],
            'negative': ['bad', 'poor', 'terrible', 'awful', 'horrible', 'disappointing',
                        'hate', 'dislike', 'unhappy', 'unsatisfied', 'worse', 'worst'],
            'strong_negative': ['disastrous', 'catastrophic', 'abysmal', 'dreadful', 'horrendous',
                              'appalling', 'atrocious', 'detestable', 'repulsive', 'disgusting']
        }
        self.negations = ['not', 'no', 'never', 'neither', 'hardly', 'barely']
        self.intensifiers = ['very', 'extremely', 'absolutely', 'completely', 'totally', 'highly']

    def analyze(self, text: str) -> tuple:
        text_lower = text.lower()
        words = text_lower.split()
        scores = {k: 0 for k in self.lexicon}
        negation = False
        intensifier = False

        for word in words:
            if word in self.negations:
                negation = True
                continue
            if word in self.intensifiers:
                intensifier = True
                continue
            for sentiment_type, lexicon in self.lexicon.items():
                if word in lexicon:
                    score = 2 if intensifier else 1
                    if negation:
                        if 'positive' in sentiment_type:
                            scores['negative' if 'strong' not in sentiment_type else 'strong_negative'] += score
                        elif 'negative' in sentiment_type:
                            scores['positive' if 'strong' not in sentiment_type else 'strong_positive'] += score
                    else:
                        scores[sentiment_type] += score
            negation = False
            intensifier = False

        positive_score = scores['strong_positive'] * 2 + scores['positive']
        negative_score = scores['strong_negative'] * 2 + scores['negative']
        total = positive_score - negative_score

        if total > 2: sentiment, confidence = 'very_positive', min(0.95, 0.7 + (total * 0.05))
        elif total > 0: sentiment, confidence = 'positive', min(0.9, 0.5 + (total * 0.1))
        elif total == 0: sentiment, confidence = 'neutral', 0.7
        elif total > -2: sentiment, confidence = 'negative', min(0.9, 0.5 + (abs(total) * 0.1))
        else: sentiment, confidence = 'very_negative', min(0.95, 0.7 + (abs(total) * 0.05))

        return sentiment, confidence

analyzer = SentimentAnalyzer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool, redis_client
    logger.info("Starting AI Platform v2.0...")

    try:
        db_pool = await asyncpg.create_pool(
            host=os.getenv('POSTGRES_HOST', 'postgres'),
            port=int(os.getenv('POSTGRES_PORT', 5432)),
            user=os.getenv('POSTGRES_USER', 'devopsadmin'),
            password=os.getenv('POSTGRES_PASSWORD', ''),
            database=os.getenv('POSTGRES_DB', 'devopsdb'),
            min_size=5, max_size=20, command_timeout=60
        )
        async with db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    id SERIAL PRIMARY KEY,
                    request_id UUID DEFAULT gen_random_uuid(),
                    input_text TEXT NOT NULL,
                    sentiment VARCHAR(20),
                    confidence FLOAT,
                    model_version VARCHAR(20),
                    processing_time_ms FLOAT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_pred_created ON predictions(created_at);
                CREATE INDEX IF NOT EXISTS idx_pred_sentiment ON predictions(sentiment);
            """)
        logger.info("Database ready")
    except Exception as e:
        logger.error(f"Database error: {e}")

    try:
        redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'redis'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            password=os.getenv('REDIS_PASSWORD', ''),
            decode_responses=True, socket_keepalive=True
        )
        await redis_client.ping()
        logger.info("Redis ready")
    except Exception as e:
        logger.error(f"Redis error: {e}")

    yield

    if db_pool: await db_pool.close()
    if redis_client: await redis_client.close()

app = FastAPI(title="DevOps AI Platform", version="2.0.0", lifespan=lifespan)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def request_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start = time.time()
    response = await call_next(request)
    process_time = (time.time() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-MS"] = f"{process_time:.2f}"
    
    # Update prometheus metrics
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    REQUEST_LATENCY.observe(process_time / 1000)
    
    return response

@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

async def process_prediction(text: str, use_cache: bool = True):
    request_id = str(uuid.uuid4())
    start_time = time.time()

    if use_cache and redis_client:
        cache_key = f"pred:{hashlib.md5(text.encode()).hexdigest()}"
        cached = await redis_client.get(cache_key)
        if cached:
            result = json.loads(cached)
            return {
                "request_id": request_id, "text": text,
                "sentiment": result['sentiment'], "confidence": result['confidence'],
                "model_version": "2.0.0",
                "processing_time_ms": (time.time() - start_time) * 1000,
                "cached": True, "timestamp": datetime.utcnow().isoformat()
            }

    sentiment, confidence = analyzer.analyze(text)
    processing_time = (time.time() - start_time) * 1000

    # Update prediction counter
    PREDICTION_COUNT.labels(sentiment=sentiment).inc()

    if redis_client:
        cache_key = f"pred:{hashlib.md5(text.encode()).hexdigest()}"
        await redis_client.setex(cache_key, 3600, json.dumps({'sentiment': sentiment, 'confidence': confidence}))

    if db_pool:
        try:
            async with db_pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO predictions (request_id, input_text, sentiment, confidence, model_version, processing_time_ms) VALUES ($1, $2, $3, $4, $5, $6)",
                    request_id, text, sentiment, confidence, "2.0.0", processing_time
                )
        except Exception as e:
            logger.error(f"DB store error: {e}")

    return {
        "request_id": request_id, "text": text,
        "sentiment": sentiment, "confidence": confidence,
        "model_version": "2.0.0", "processing_time_ms": processing_time,
        "cached": False, "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/")
async def root():
    return {
        "name": "DevOps AI Platform", "version": "2.0.0",
        "domain": "ai-backend.astrodirectory.in",
        "endpoints": {
            "health": "/health", "predict": "/predict",
            "predictions": "/predictions", "analytics": "/analytics",
            "metrics": "/metrics", "docs": "/docs"
        }
    }

@app.get("/health")
async def health_check():
    services = {"api": "healthy", "database": "healthy", "redis": "healthy"}
    overall = "healthy"

    if db_pool:
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
        except:
            services["database"] = "error"; overall = "degraded"

    if redis_client:
        try: await redis_client.ping()
        except: services["redis"] = "error"; overall = "degraded"

    return {"status": overall, "timestamp": datetime.utcnow().isoformat(),
            "version": "2.0.0", "uptime_seconds": time.time() - app_start_time,
            "services": services}

@app.post("/predict")
async def predict_json(body: PredictionRequest):
    return await process_prediction(body.text, body.use_cache)

@app.get("/predict")
async def predict_query(text: str = Query(..., min_length=1, max_length=1000),
                       use_cache: bool = Query(default=True)):
    return await process_prediction(text, use_cache)

@app.get("/predictions")
async def get_predictions(limit: int = Query(default=10, le=100)):
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT request_id, input_text, sentiment, confidence, processing_time_ms, created_at FROM predictions ORDER BY created_at DESC LIMIT $1", limit
        )
    predictions = [{
        'request_id': str(row['request_id']), 'text': row['input_text'],
        'sentiment': row['sentiment'], 'confidence': row['confidence'],
        'processing_time_ms': row['processing_time_ms'],
        'created_at': row['created_at'].isoformat()
    } for row in rows]
    return {"predictions": predictions, "count": len(predictions)}

@app.get("/analytics")
async def get_analytics():
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    async with db_pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM predictions")
        distribution = await conn.fetch(
            "SELECT sentiment, COUNT(*) as c, AVG(confidence) as a FROM predictions GROUP BY sentiment ORDER BY c DESC"
        )
        avg_time = await conn.fetchval("SELECT AVG(processing_time_ms) FROM predictions")
        avg_conf = await conn.fetchval("SELECT AVG(confidence) FROM predictions")
    return {
        "total_predictions": total,
        "sentiment_distribution": [
            {'sentiment': r['sentiment'], 'count': r['c'], 'avg_confidence': float(r['a'])} for r in distribution
        ],
        "average_confidence": float(avg_conf or 0),
        "average_processing_time_ms": float(avg_time or 0)
    }
