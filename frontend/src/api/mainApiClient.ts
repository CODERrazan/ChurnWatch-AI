import { MAIN_API_BASE_URL } from '../config'
import { requestJson } from './http'
import type {
  AnalysisResponse, CustomerDetailResponse, CustomerListResponse, CustomerQuery, DashboardResponse, HealthResponse,
} from '../types/main'

const BASE = MAIN_API_BASE_URL

function withDate(path: string, snapshotDate?: string | null) {
  return snapshotDate ? `${path}?snapshot_date=${encodeURIComponent(snapshotDate)}` : path
}

/** Client for the Main API only. Never used for Monitoring. */
export const mainApiClient = {
  getHealth: () => requestJson<HealthResponse>(BASE, '/api/health'),
  getDashboard: () => requestJson<DashboardResponse>(BASE, '/api/dashboard'),
  getCustomers: (q: CustomerQuery) => {
    const p = new URLSearchParams({ page: String(q.page), page_size: String(q.page_size) })
    if (q.risk_category) p.set('risk_category', q.risk_category)
    if (q.customer_segment) p.set('customer_segment', q.customer_segment)
    if (q.search) p.set('search', q.search)
    return requestJson<CustomerListResponse>(BASE, `/api/customers?${p.toString()}`)
  },
  getCustomer: (id: string, snapshotDate?: string | null) =>
    requestJson<CustomerDetailResponse>(BASE, withDate(`/api/customers/${encodeURIComponent(id)}`, snapshotDate)),
  // Groq allows up to 20 s by default, so allow a longer client timeout. No request body is required.
  analyzeCustomer: (id: string, snapshotDate?: string | null) =>
    requestJson<AnalysisResponse>(BASE, withDate(`/api/customers/${encodeURIComponent(id)}/analyze`, snapshotDate), {
      method: 'POST',
      timeoutMs: 60000,
    }),
}
