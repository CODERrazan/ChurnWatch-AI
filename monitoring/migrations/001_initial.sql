-- ChurnWatch Monitoring schema (Supabase PostgreSQL).
-- Apply once in Supabase Dashboard > SQL Editor, or with psql.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS monitoring_requests (
    prediction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    request_status TEXT NOT NULL CHECK (request_status IN ('available','unavailable')),
    assessment_type TEXT NOT NULL,
    risk_category TEXT NOT NULL CHECK (risk_category IN ('Low','Medium','High')),
    customer_id TEXT,
    snapshot_date DATE,
    evaluation_status TEXT NOT NULL DEFAULT 'not_evaluated'
);

CREATE TABLE IF NOT EXISTS llm_responses (
    prediction_id UUID PRIMARY KEY REFERENCES monitoring_requests(prediction_id) ON DELETE CASCADE,
    executive_summary TEXT,
    response_json JSONB,
    response_status TEXT NOT NULL CHECK (response_status IN ('available','unavailable'))
);

CREATE TABLE IF NOT EXISTS llm_request_metrics (
    prediction_id UUID PRIMARY KEY REFERENCES monitoring_requests(prediction_id) ON DELETE CASCADE,
    latency_ms DOUBLE PRECISION CHECK (latency_ms IS NULL OR latency_ms >= 0),
    prompt_tokens BIGINT CHECK (prompt_tokens IS NULL OR prompt_tokens >= 0),
    completion_tokens BIGINT CHECK (completion_tokens IS NULL OR completion_tokens >= 0),
    reasoning_tokens BIGINT CHECK (reasoning_tokens IS NULL OR reasoning_tokens >= 0),
    total_tokens BIGINT CHECK (total_tokens IS NULL OR total_tokens >= 0)
);

CREATE TABLE IF NOT EXISTS monitoring_errors (
    error_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    prediction_id UUID NOT NULL REFERENCES monitoring_requests(prediction_id) ON DELETE CASCADE,
    error_category TEXT NOT NULL,
    safe_detail TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS churn_evaluations (
    evaluation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    prediction_id UUID NOT NULL REFERENCES monitoring_requests(prediction_id) ON DELETE CASCADE,
    horizon_days SMALLINT NOT NULL CHECK (horizon_days IN (30,90)),
    label_eligible BOOLEAN NOT NULL,
    actual_churn SMALLINT CHECK (actual_churn IS NULL OR actual_churn IN (0,1)),
    rule_alert_match BOOLEAN,
    llm_correctness_status TEXT NOT NULL DEFAULT 'not_evaluated'
        CHECK (llm_correctness_status IN ('not_evaluated','human_reviewed','automated_evaluation')),
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(prediction_id,horizon_days)
);

CREATE INDEX IF NOT EXISTS idx_monitoring_requests_created_at ON monitoring_requests(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_monitoring_requests_status ON monitoring_requests(request_status);
CREATE INDEX IF NOT EXISTS idx_churn_evaluations_eligible ON churn_evaluations(label_eligible,horizon_days);
