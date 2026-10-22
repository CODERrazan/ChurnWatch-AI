-- Supabase REST clients should not access monitoring tables directly.
ALTER TABLE monitoring_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE llm_responses ENABLE ROW LEVEL SECURITY;
ALTER TABLE llm_request_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring_errors ENABLE ROW LEVEL SECURITY;
ALTER TABLE churn_evaluations ENABLE ROW LEVEL SECURITY;
