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
