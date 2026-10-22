// Types based on real responses from the Main API (verified on port 8001) and the handoff PDF.

export type RiskCategory = 'Low' | 'Medium' | 'High'

export interface HealthResponse {
  status: string
  application: string
  dataset: string
  data_notice: string
  groq: { configured: boolean; model: string }
  monitoring: { url: string; database_connection: string }
}

export interface RetroEvaluation {
  status: string
  evaluation_type?: string
  horizon?: string
  eligible_snapshots?: number
  unique_customers?: number
  positive_outcomes?: number
  risk_distribution?: Record<string, number>
  alert_rule?: string
  confusion_matrix?: { true_positive: number; false_positive: number; true_negative: number; false_negative: number }
  precision?: number
  recall?: number
  f1?: number
  limitations?: string[]
}

export interface DashboardResponse {
  data_notice: string
  total_customers: number
  historical_churn_count: number
  historical_churn_rate: number
  risk_distribution: Record<string, number>
  risk_distribution_chart: { category: string; count: number }[]
  churn_rate_by_segment: {
    customer_segment: string
    customers: number
    historical_churned: number
    historical_churn_rate: number
  }[]
  key_churn_associated_factors: {
    feature: string
    churn_mean: number
    retained_mean: number
    churn_sample_size: number
    retained_sample_size: number
    interpretation: string
  }[]
  churn_within_30d_trend: { snapshot_month: string; eligible_snapshots: number; churned: number; rate: number }[]
  retrospective_evaluation: Record<string, RetroEvaluation>
  data_quality: {
    profile_rows: number
    snapshot_rows: number
    outcome_rows: number
    duplicate_customer_date_pairs: number
    missing_values_by_table: Record<string, Record<string, number>>
  }
  recent_analysis_activity: {
    request_id: string
    customer_id: string
    snapshot_date: string
    risk_category: string
    llm_status: string
    monitoring_delivery: string
  }[]
}

export interface CustomerListItem {
  customer_id: string
  customer_segment: string
  snapshot_date: string
  risk_category: RiskCategory
  risk_score: number
  risk_score_unit: string
  risk_factor_count: number
}

export interface CustomerListResponse {
  data_notice: string
  page: number
  page_size: number
  total: number
  customers: CustomerListItem[]
}

export interface CustomerQuery {
  page: number
  page_size: number
  risk_category?: string
  customer_segment?: string
  search?: string
}

export type SnapshotValue = string | number | null
export type Profile = Record<string, SnapshotValue>
export type Snapshot = Record<string, SnapshotValue>

export interface RiskFactor {
  feature: string
  observed_value: SnapshotValue
  direction: string
  points: number
  interpretation: string
}

export interface RiskAssessment {
  assessment_type: string
  risk_category: RiskCategory
  risk_score: number
  risk_score_unit: string
  thresholds: Record<string, string>
  risk_factors: RiskFactor[]
  limitations: string[]
}

export interface HistoricalOutcome {
  label_30d: number | null
  label_90d: number | null
  label_observed_30d: boolean
  label_observed_90d: boolean
  outcome_source: string
  retrospective_only: boolean
}

export interface CustomerDetailResponse {
  data_notice: string
  customer_id: string
  profile: Profile
  snapshot_date: string
  current_snapshot: Snapshot
  snapshot: Snapshot
  risk_assessment: RiskAssessment
  historical_outcome: HistoricalOutcome
  // Shape of entries is not verified (the list was empty in the checked response).
  analysis_history: Record<string, unknown>[]
}

export interface Recommendation {
  action: string
  rationale: string
  priority: 'high' | 'medium' | 'low'
  suggested_owner: string
  success_indicator: string
}

export interface LlmMetadata {
  provider: string
  model: string
  status: 'available' | 'unavailable' | string
  latency_ms: number | null
  token_usage: {
    prompt_tokens?: number | null
    completion_tokens?: number | null
    total_tokens?: number | null
    reasoning_tokens?: number | null
  } | null
  request_id: string
  error_category: string | null
}

export interface AnalysisMonitoring {
  prediction_id: string
  delivery_status: 'recorded' | 'unavailable' | string
  error_category?: string | null
  evaluation_status: string
  rule_alert_match_30d: boolean | null
  llm_correctness_status: string
}

export interface AnalysisResponse {
  data_notice: string
  request_id: string
  customer_id: string
  profile: Profile
  snapshot_date: string
  current_snapshot: Snapshot
  risk_assessment: RiskAssessment
  executive_summary: string
  customer_insights: string[]
  retention_recommendations: Recommendation[]
  historical_outcome: HistoricalOutcome
  limitations: string[]
  segment_comparison: {
    customer_segment: string
    segment_historical_churn_rate: number
    overall_historical_churn_rate: number
    customers_in_segment: number
    interpretation: string
  }
  llm_metadata: LlmMetadata
  monitoring: AnalysisMonitoring
}
