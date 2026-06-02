import logging
import time
import uuid
import hashlib
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import json
from ..core.config import settings
from ..core.database import db
from ..core.redis import cache

logger = logging.getLogger(__name__)

@dataclass
class PredictionResult:
    request_id: str
    text: str
    sentiment: str
    confidence: float
    model_version: str
    processing_time_ms: float
    cached: bool = False
    metadata: Optional[Dict[str, Any]] = None

class AIService:
    """Advanced AI prediction service with caching and analytics"""
    
    def __init__(self):
        self.model_version = settings.MODEL_VERSION
        self.confidence_threshold = settings.MODEL_CONFIDENCE_THRESHOLD
        self.max_text_length = settings.MAX_TEXT_LENGTH
        
        # Enhanced sentiment lexicons
        self.sentiment_lexicon = {
            'strong_positive': [
                'excellent', 'outstanding', 'exceptional', 'superb', 'magnificent',
                'brilliant', 'phenomenal', 'extraordinary', 'remarkable', 'incredible'
            ],
            'positive': [
                'good', 'great', 'nice', 'wonderful', 'fantastic', 'amazing',
                'love', 'happy', 'pleased', 'satisfied', 'impressive', 'enjoy'
            ],
            'neutral': [
                'okay', 'fine', 'average', 'normal', 'standard', 'regular',
                'moderate', 'fair', 'adequate', 'acceptable'
            ],
            'negative': [
                'bad', 'poor', 'terrible', 'awful', 'horrible', 'disappointing',
                'hate', 'dislike', 'unhappy', 'unsatisfied', 'worse', 'worst'
            ],
            'strong_negative': [
                'disastrous', 'catastrophic', 'abysmal', 'dreadful', 'horrendous',
                'appalling', 'atrocious', 'detestable', 'repulsive', 'disgusting'
            ]
        }
        
        # Context modifiers
        self.context_modifiers = {
            'negation': ['not', 'no', 'never', 'neither', 'hardly', 'barely'],
            'intensifiers': ['very', 'extremely', 'absolutely', 'completely', 'totally', 'highly'],
            'diminishers': ['slightly', 'somewhat', 'a bit', 'kind of', 'sort of']
        }
    
    def _generate_cache_key(self, text: str, **kwargs) -> str:
        """Generate cache key from text and parameters"""
        content = f"{text}:{json.dumps(kwargs, sort_keys=True)}"
        return f"prediction:{hashlib.md5(content.encode()).hexdigest()}"
    
    async def predict(self, text: str, user_id: Optional[str] = None, 
                     use_cache: bool = True) -> PredictionResult:
        """Make AI prediction with caching"""
        start_time = time.time()
        request_id = str(uuid.uuid4())
        
        # Validate input
        if not text or len(text.strip()) == 0:
            raise ValueError("Text input cannot be empty")
        
        if len(text) > self.max_text_length:
            text = text[:self.max_text_length]
        
        # Check cache
        if use_cache:
            cache_key = self._generate_cache_key(text, user_id=user_id)
            cached_result = await cache.get(cache_key)
            if cached_result:
                processing_time = (time.time() - start_time) * 1000
                logger.info(f"Cache hit for prediction: {request_id}")
                return PredictionResult(
                    request_id=request_id,
                    text=text,
                    sentiment=cached_result['sentiment'],
                    confidence=cached_result['confidence'],
                    model_version=self.model_version,
                    processing_time_ms=processing_time,
                    cached=True,
                    metadata=cached_result.get('metadata', {})
                )
        
        # Perform sentiment analysis
        sentiment, confidence, metadata = await self._analyze_sentiment(text)
        
        processing_time = (time.time() - start_time) * 1000
        
        result = PredictionResult(
            request_id=request_id,
            text=text,
            sentiment=sentiment,
            confidence=confidence,
            model_version=self.model_version,
            processing_time_ms=processing_time,
            cached=False,
            metadata=metadata
        )
        
        # Store in cache
        if use_cache:
            cache_key = self._generate_cache_key(text, user_id=user_id)
            await cache.set(cache_key, {
                'sentiment': sentiment,
                'confidence': confidence,
                'metadata': metadata,
                'model_version': self.model_version
            }, ttl=settings.CACHE_TTL)
        
        # Store in database (async)
        await self._store_prediction(result, user_id)
        
        return result
    
    async def _analyze_sentiment(self, text: str) -> tuple:
        """Advanced sentiment analysis algorithm"""
        text_lower = text.lower()
        words = text_lower.split()
        
        scores = {
            'strong_positive': 0,
            'positive': 0,
            'neutral': 0,
            'negative': 0,
            'strong_negative': 0
        }
        
        # Check for negations and intensifiers
        negation_active = False
        intensifier_active = False
        diminisher_active = False
        
        for i, word in enumerate(words):
            # Check context modifiers
            if word in self.context_modifiers['negation']:
                negation_active = True
                continue
            
            if word in self.context_modifiers['intensifiers']:
                intensifier_active = True
                continue
            
            if word in self.context_modifiers['diminishers']:
                diminisher_active = True
                continue
            
            # Check sentiment
            for sentiment_type, lexicon in self.sentiment_lexicon.items():
                if word in lexicon:
                    score = 1
                    if intensifier_active:
                        score = 2
                    elif diminisher_active:
                        score = 0.5
                    
                    if negation_active:
                        # Reverse sentiment
                        if 'positive' in sentiment_type:
                            scores['negative' if 'strong' not in sentiment_type else 'strong_negative'] += score
                        elif 'negative' in sentiment_type:
                            scores['positive' if 'strong' not in sentiment_type else 'strong_positive'] += score
                        else:
                            scores[sentiment_type] += score
                    else:
                        scores[sentiment_type] += score
            
            # Reset context modifiers after each word
            negation_active = False
            intensifier_active = False
            diminisher_active = False
        
        # Calculate final sentiment
        positive_score = scores['strong_positive'] * 2 + scores['positive']
        negative_score = scores['strong_negative'] * 2 + scores['negative']
        total_score = positive_score - negative_score
        
        if total_score > 2:
            sentiment = 'very_positive'
            confidence = min(0.95, 0.7 + (total_score * 0.05))
        elif total_score > 0:
            sentiment = 'positive'
            confidence = min(0.9, 0.5 + (total_score * 0.1))
        elif total_score == 0:
            sentiment = 'neutral'
            confidence = 0.7
        elif total_score > -2:
            sentiment = 'negative'
            confidence = min(0.9, 0.5 + (abs(total_score) * 0.1))
        else:
            sentiment = 'very_negative'
            confidence = min(0.95, 0.7 + (abs(total_score) * 0.05))
        
        metadata = {
            'word_count': len(words),
            'scores': scores,
            'total_score': total_score,
            'analysis_version': '2.0'
        }
        
        return sentiment, confidence, metadata
    
    async def _store_prediction(self, result: PredictionResult, user_id: Optional[str] = None):
        """Store prediction in database"""
        try:
            await db.execute(
                """
                INSERT INTO predictions 
                (request_id, user_id, input_text, prediction, model_version, confidence, processing_time_ms)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                result.request_id,
                user_id,
                result.text,
                json.dumps({
                    'sentiment': result.sentiment,
                    'confidence': result.confidence,
                    'metadata': result.metadata
                }),
                result.model_version,
                result.confidence,
                result.processing_time_ms
            )
            logger.debug(f"Prediction stored: {result.request_id}")
        except Exception as e:
            logger.error(f"Failed to store prediction: {e}")
    
    async def get_prediction_history(self, limit: int = 10, offset: int = 0,
                                    user_id: Optional[str] = None) -> List[Dict]:
        """Get prediction history"""
        try:
            if user_id:
                rows = await db.fetch(
                    """
                    SELECT request_id, input_text, prediction, model_version, 
                           confidence, processing_time_ms, created_at
                    FROM predictions 
                    WHERE user_id = $1
                    ORDER BY created_at DESC 
                    LIMIT $2 OFFSET $3
                    """,
                    user_id, limit, offset
                )
            else:
                rows = await db.fetch(
                    """
                    SELECT request_id, input_text, prediction, model_version,
                           confidence, processing_time_ms, created_at
                    FROM predictions 
                    ORDER BY created_at DESC 
                    LIMIT $1 OFFSET $2
                    """,
                    limit, offset
                )
            
            return [
                {
                    'request_id': str(row['request_id']),
                    'text': row['input_text'],
                    'prediction': json.loads(row['prediction']) if isinstance(row['prediction'], str) else row['prediction'],
                    'model_version': row['model_version'],
                    'confidence': row['confidence'],
                    'processing_time_ms': row['processing_time_ms'],
                    'created_at': row['created_at'].isoformat()
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to fetch predictions: {e}")
            return []
    
    async def get_analytics(self) -> Dict[str, Any]:
        """Get prediction analytics"""
        try:
            total = await db.fetchval("SELECT COUNT(*) FROM predictions")
            
            sentiment_dist = await db.fetch("""
                SELECT 
                    prediction->>'sentiment' as sentiment,
                    COUNT(*) as count,
                    AVG(confidence) as avg_confidence,
                    AVG(processing_time_ms) as avg_processing_time
                FROM predictions 
                GROUP BY prediction->>'sentiment'
                ORDER BY count DESC
            """)
            
            recent_activity = await db.fetch("""
                SELECT 
                    DATE_TRUNC('hour', created_at) as hour,
                    COUNT(*) as count
                FROM predictions 
                WHERE created_at > NOW() - INTERVAL '24 hours'
                GROUP BY hour
                ORDER BY hour DESC
            """)
            
            return {
                'total_predictions': total,
                'sentiment_distribution': [
                    {
                        'sentiment': row['sentiment'],
                        'count': row['count'],
                        'avg_confidence': float(row['avg_confidence'] or 0),
                        'avg_processing_time_ms': float(row['avg_processing_time'] or 0)
                    }
                    for row in sentiment_dist
                ],
                'recent_activity': [
                    {
                        'hour': row['hour'].isoformat(),
                        'count': row['count']
                    }
                    for row in recent_activity
                ]
            }
        except Exception as e:
            logger.error(f"Failed to get analytics: {e}")
            return {'error': str(e)}

# Global AI service instance
ai_service = AIService()
