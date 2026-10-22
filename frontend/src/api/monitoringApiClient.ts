import { MONITORING_BASE_URL } from '../config'
import { requestJson } from './http'
import type { MonitoringHealth, MonitoringRequestsResponse, MonitoringSummary, PredictionEvaluation } from '../types/monitoring'

const BASE = MONITORING_BASE_URL

/**
 * Client for the Monitoring API only. Read-only on purpose: the Main API already sends
 * monitoring events after each analysis, so the frontend must NOT post events (duplicates).
 */
export const monitoringApiClient = {
  getHealth: () => requestJson<MonitoringHealth>(BASE, '/api/monitoring/health'),
  getSummary: () => requestJson<MonitoringSummary>(BASE, '/api/monitoring/summary'),
  getPredictionEvaluation: (horizon: '30d' | '90d') =>
    requestJson<PredictionEvaluation>(BASE, '/api/monitoring/prediction-evaluation?horizon=' + horizon),
  getRequests: (limit: number, status?: string) => {
    const p = new URLSearchParams({ limit: String(limit) })
    if (status) p.set('status', status)
    return requestJson<MonitoringRequestsResponse>(BASE, `/api/monitoring/requests?${p.toString()}`)
  },
}
