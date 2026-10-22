// Monitoring types. Health shape comes from the handoff (mock-tested only);
// request rows are NOT verified against a live database, so every field is optional.

export interface MonitoringHealth {
  status: string
  service: string
  database: string
  storage?: string
}

export interface MonitoringSummary {
  service: string
  request_count: number
  success_count: number
  failure_count: number
  mean_latency_ms: number | null
  prompt_tokens: number | null
  completion_tokens: number | null
  total_tokens: number | null
  errors_by_category: Record<string, number>
  correctness_note: string
}

export interface MonitoringRequestRow {
  request_id?: string
  request_status?: string
  assessment_type?: string
  risk_category?: string
  customer_id?: string
  snapshot_date?: string
  latency_ms?: number | null
  prompt_tokens?: number | null
  completion_tokens?: number | null
  total_tokens?: number | null
  error_category?: string | null
  created_at?: string
  timestamp?: string
  [key: string]: unknown
}

export interface MonitoringRequestsResponse {
  service: string
  requests: MonitoringRequestRow[]
}

export interface PredictionEvaluation {
  service: string
  horizon: '30d' | '90d'
  record_unit: string
  total_records: number
  evaluated_records: number
  unavailable_outcome_records: number
  unobserved_records: number
  missing_outcome_records: number
  unique_evaluated_customers: number
  high_risk_records: number
  high_risk_churned: number
  churned_records: number
  high_risk_precision: number | null
  high_risk_recall: number | null
  risk_categories: { category: 'Low' | 'Medium' | 'High'; evaluated_records: number; churned_records: number; churn_rate: number | null }[]
  limitations: string[]
}
