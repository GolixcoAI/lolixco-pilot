-- LolixCopilot — Phase 2 Forward-Only Database Migration
-- Extends analyses table with structured media intelligence, provider metadata,
-- usage telemetry, and user correction/feedback fields.
-- Preserves all existing records and adheres to Row Level Security (RLS).

-- 1. Add columns to analyses table idempotently
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS provider TEXT;
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS model TEXT;
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS source_identification JSONB;
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS audio_intelligence JSONB;
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS usage_metadata JSONB;
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS user_feedback JSONB;

-- 2. Indexes for performant lookup by media asset and creation time
CREATE INDEX IF NOT EXISTS idx_analyses_media_id ON analyses(media_id);
CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON analyses(created_at DESC);

-- 3. Document column semantics
COMMENT ON COLUMN analyses.provider IS 'AI provider used for inference: baseten, meta, or mock';
COMMENT ON COLUMN analyses.model IS 'Model identifier used for inference';
COMMENT ON COLUMN analyses.source_identification IS 'Structured video classification, recognized franchise, characters, and scenes';
COMMENT ON COLUMN analyses.audio_intelligence IS 'Structured audio/soundtrack recognition, genre, tempo, and match confidence';
COMMENT ON COLUMN analyses.usage_metadata IS 'Inference execution metrics: token counts, latency ms, request ID';
COMMENT ON COLUMN analyses.user_feedback IS 'User-provided corrections or validation for identified source and soundtrack';
