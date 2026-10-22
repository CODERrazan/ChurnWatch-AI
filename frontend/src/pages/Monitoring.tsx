import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { monitoringApiClient } from '../api/monitoringApiClient'
import { useAsync } from '../hooks/useAsync'
import { Card, EmptyState, ErrorState, Kpi, PageHeader, PageSkeleton, Pill } from '../components/ui'
import { num, shortId } from '../format'
import type { PredictionEvaluation } from '../types/monitoring'

const riskColors: Record<string, string> = { Low: '#4FB287', Medium: '#E8B04A', High: '#F0674D' }
const tooltipStyle = { background: '#1C2536', border: '1px solid #2B3752', borderRadius: 8, color: '#E6EAF2' }

function conclusion(evaluation: PredictionEvaluation) {
  const enoughRecords = evaluation.evaluated_records >= 100
  const enoughHighRisk = evaluation.high_risk_records >= 30
  const enoughChurn = evaluation.churned_records >= 30
  if (!enoughRecords || !enoughHighRisk || !enoughChurn
    || evaluation.high_risk_precision == null || evaluation.high_risk_recall == null) {
    return {
      title: 'Insufficient data',
      detail: 'Evaluated ' + num(evaluation.evaluated_records) + ' of ' + num(evaluation.total_records) + ' snapshot records; a performance label requires at least 100 evaluated records, 30 High-Risk records, and 30 observed churn outcomes. Current samples: ' + num(evaluation.high_risk_records) + ' High-Risk records and ' + num(evaluation.churned_records) + ' churn outcomes.',
    }
  }
  const precision = evaluation.high_risk_precision
  const recall = evaluation.high_risk_recall
  const metrics = 'High-Risk precision is ' + num(precision * 100, 1) + '% (' + num(evaluation.high_risk_churned) + ' of ' + num(evaluation.high_risk_records) + '); recall is ' + num(recall * 100, 1) + '% (' + num(evaluation.high_risk_churned) + ' of ' + num(evaluation.churned_records) + ' observed churn records).'
  if (precision >= 0.6 && recall >= 0.6) return { title: 'Strong historical performance', detail: metrics }
  if (precision < 0.4 && recall < 0.4) return { title: 'Weak historical performance', detail: metrics }
  return { title: 'Mixed historical performance', detail: metrics }
}

export default function Monitoring() {
  const [status, setStatus] = useState('')
  const [limit, setLimit] = useState(100)
  const [horizon, setHorizon] = useState<'30d' | '90d'>('30d')

  const evaluation = useAsync(() => monitoringApiClient.getPredictionEvaluation(horizon), [horizon])
  // Health first: nothing else is requested until the Monitoring service reports a connected database.
  const health = useAsync(() => monitoringApiClient.getHealth(), [])
  const connected = health.data?.status === 'ok' && health.data.database === 'connected'
  const summary = useAsync(() => (connected ? monitoringApiClient.getSummary() : Promise.reject(new Error('skipped'))), [connected])
  const reqs = useAsync(() => (connected ? monitoringApiClient.getRequests(limit, status || undefined) : Promise.reject(new Error('skipped'))), [connected, limit, status])
  const reloadAll = () => { evaluation.reload(); health.reload(); summary.reload(); reqs.reload() }

  return (
    <>
      <PageHeader
        title="Monitoring"
        subtitle="LLM request history and summary from the separate Monitoring service."
        actions={<button className="btn" onClick={reloadAll}>Refresh</button>}
      />
      <div className="tools">
        <label>Outcome horizon
          <select className="input" value={horizon} onChange={(e) => setHorizon(e.target.value as '30d' | '90d')}>
            <option value="30d">30 days</option><option value="90d">90 days</option>
          </select>
        </label>
      </div>
      {evaluation.status === 'loading' && !evaluation.data && <div className="notice" role="status">Loading historical evaluation…</div>}
      {evaluation.status === 'error' && <ErrorState error={evaluation.error} onRetry={evaluation.reload} title="Historical evaluation could not be loaded" />}
      {evaluation.data && (() => {
        const data = evaluation.data
        const result = conclusion(data)
        const coverage = data.total_records ? data.evaluated_records / data.total_records * 100 : 0
        const highRate = data.risk_categories.find((row) => row.category === 'High')
        const chartData = data.risk_categories.map((row) => ({ ...row, rate_pct: row.churn_rate == null ? 0 : row.churn_rate * 100 }))
        return (
          <section aria-label="Historical prediction evaluation">
            <div className="notice" role="status">
              <strong>{result.title} — {data.horizon} horizon.</strong> {result.detail}
              <div className="caption">Provisional interpretation: strong requires precision and recall ≥60%; weak means both are &lt;40%; otherwise performance is mixed. Conclusions require at least 100 evaluated records, 30 High-Risk records, and 30 observed churn outcomes. Risk categories use the existing heuristic thresholds: Low 0–2, Medium 3–5, High 6+ points.</div>
            </div>
            <div className="grid g2">
              <Kpi label="High-Risk Precision" value={data.high_risk_precision == null ? '—' : num(data.high_risk_precision * 100, 1) + '%'} hint={num(data.high_risk_churned) + ' churned of ' + num(data.high_risk_records) + ' High-Risk records'} />
              <Kpi label="High-Risk Recall" value={data.high_risk_recall == null ? '—' : num(data.high_risk_recall * 100, 1) + '%'} hint={num(data.high_risk_churned) + ' High-Risk among ' + num(data.churned_records) + ' observed churn records'} />
            </div>
            <div className="grid g2">
              <Card title="Historical churn rate by risk category" caption={'Observed ' + data.horizon + ' snapshot outcomes only. Bars show churned / evaluated records; risk points are not probabilities.'}>
                <div className="chart">
                  <ResponsiveContainer width="100%" height={240}>
                    <BarChart data={chartData}>
                      <CartesianGrid stroke="#26314A" vertical={false} />
                      <XAxis dataKey="category" stroke="#8A96AD" />
                      <YAxis stroke="#8A96AD" tickFormatter={(value) => String(value) + '%'} />
                      <Tooltip
                        contentStyle={tooltipStyle}
                        formatter={(value) => [String(Number(value).toFixed(1)) + '%', 'Historical churn']}
                        labelFormatter={(label, payload) => {
                          const row = payload?.[0]?.payload as { churned_records: number; evaluated_records: number } | undefined
                          return row ? String(label) + ': ' + num(row.churned_records) + ' of ' + num(row.evaluated_records) + ' records' : String(label)
                        }}
                      />
                      <Bar dataKey="rate_pct" name="Churn rate" radius={[6, 6, 0, 0]}>
                        {chartData.map((row) => <Cell key={row.category} fill={riskColors[row.category]} />)}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <div className="table-wrap">
                  <table className="table compact">
                    <thead><tr><th>Risk</th><th className="num">Churned / evaluated</th><th className="num">Rate</th></tr></thead>
                    <tbody>{data.risk_categories.map((row) => <tr key={row.category}><th scope="row">{row.category}</th><td className="num">{num(row.churned_records)} / {num(row.evaluated_records)}</td><td className="num">{row.churn_rate == null ? '—' : num(row.churn_rate * 100, 1) + '%'}</td></tr>)}</tbody>
                  </table>
                </div>
              </Card>
              <Card title="Evaluation coverage" caption="Coverage is the share of unique customer/snapshot records with an observed outcome at this horizon.">
                <p><strong>{num(data.evaluated_records)}</strong> evaluated of <strong>{num(data.total_records)}</strong> records ({num(coverage, 1)}%).</p>
                <div className="meter" role="img" aria-label={num(coverage, 1) + ' percent of snapshot records evaluated'} style={{ width: '100%', height: 14 }}>
                  <span style={{ width: Math.min(100, coverage) + '%' }} />
                </div>
                <dl className="kv">
                  <div><dt>Missing or unavailable outcome</dt><dd>{num(data.unavailable_outcome_records)}</dd></div>
                  <div><dt>Unobserved horizon</dt><dd>{num(data.unobserved_records)}</dd></div>
                  <div><dt>Missing label</dt><dd>{num(data.missing_outcome_records)}</dd></div>
                  <div><dt>Unique customers represented</dt><dd>{num(data.unique_evaluated_customers)}</dd></div>
                </dl>
                <p className="caption">Unobserved and missing counts can overlap. Rows are matched by customer ID and snapshot date; the dataset validates each pair as unique.</p>
              </Card>
            </div>
            <p className="caption">{data.limitations.join(' ')}</p>
            {highRate && highRate.evaluated_records === 0 && <EmptyState title="No observed High-Risk records at this horizon">High-Risk precision and recall are unavailable when their evaluation denominators are empty.</EmptyState>}
          </section>
        )
      })()}
      {health.status === 'loading' && !health.data && <PageSkeleton />}
      {health.status === 'error' && (
        <ErrorState
          error={health.error}
          onRetry={health.reload}
          title="Monitoring is unavailable"
        />
      )}
      {health.status === 'error' && (
        <p className="caption">No monitoring data is shown while the service is unavailable. The Main API's analysis still works without it. A 503 usually means the Monitoring database (DATABASE_URL) is not configured, or the service is not running.</p>
      )}
      {health.data && !connected && (
        <EmptyState title="Monitoring is reachable but its database is not connected" action={<button className="btn" onClick={health.reload}>Check again</button>}>
          Status: {health.data.status} · database: {health.data.database}.
        </EmptyState>
      )}
      {connected && (
        <>
          <div className="notice" role="note">Monitoring database reported as connected ({health.data?.storage ?? 'storage not reported'}).</div>
          {summary.status === 'error' && <ErrorState error={summary.error} onRetry={summary.reload} title="Summary could not be loaded" />}
          {summary.data && (
            <>
              <div className="grid g4">
                <Kpi label="Requests" value={num(summary.data.request_count)} />
                <Kpi label="Successful" value={num(summary.data.success_count)} />
                <Kpi label="Failed" value={num(summary.data.failure_count)} />
                <Kpi label="Mean latency" value={summary.data.mean_latency_ms == null ? '—' : `${num(summary.data.mean_latency_ms, 0)} ms`} />
              </div>
              <div className="grid g2">
                <Card title="Token usage">
                  <dl className="kv">
                    <div><dt>Prompt tokens</dt><dd>{num(summary.data.prompt_tokens)}</dd></div>
                    <div><dt>Completion tokens</dt><dd>{num(summary.data.completion_tokens)}</dd></div>
                    <div><dt>Total tokens</dt><dd>{num(summary.data.total_tokens)}</dd></div>
                  </dl>
                </Card>
                <Card title="Errors by category">
                  {Object.keys(summary.data.errors_by_category).length === 0
                    ? <p className="muted">No errors recorded.</p>
                    : <dl className="kv">{Object.entries(summary.data.errors_by_category).map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{num(v)}</dd></div>)}</dl>}
                </Card>
              </div>
              <div className="notice" role="note">{summary.data.correctness_note}</div>
            </>
          )}

          <Card title="Recent requests" caption="Newest first, limited by row count (not paged).">
            <div className="tools">
              <label>LLM request status
                <select className="input" value={status} onChange={(e) => setStatus(e.target.value)}>
                  <option value="">All</option><option value="available">available</option><option value="unavailable">unavailable</option>
                </select>
              </label>
              <label>Rows
                <select className="input" value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
                  {[25, 50, 100, 500].map((n) => <option key={n}>{n}</option>)}
                </select>
              </label>
            </div>
            {reqs.status === 'error' && <ErrorState error={reqs.error} onRetry={reqs.reload} title="Requests could not be loaded" />}
            {reqs.data && reqs.data.requests.length === 0 && <EmptyState title="No requests stored yet">Run an AI analysis, then refresh. Records appear only after the Monitoring service stores them.</EmptyState>}
            {reqs.data && reqs.data.requests.length > 0 && (
              <div className="table-wrap">
                <table className="table compact">
                  <thead><tr><th>Time</th><th>Request</th><th>Customer</th><th>Status</th><th>Risk</th><th className="num">Latency</th><th className="num">Tokens</th><th>Error</th><th>All fields</th></tr></thead>
                  <tbody>
                    {reqs.data.requests.map((r, i) => (
                      <tr key={r.request_id ?? i}>
                        <td>{String(r.created_at ?? r.timestamp ?? '—')}</td>
                        <td><code title={r.request_id}>{r.request_id ? shortId(r.request_id) : '—'}</code></td>
                        <td>{r.customer_id ?? '—'}</td>
                        <td>{r.request_status ? <Pill tone={r.request_status === 'available' ? 'low' : 'warn'}>{r.request_status}</Pill> : '—'}</td>
                        <td>{r.risk_category ?? '—'}</td>
                        <td className="num">{r.latency_ms == null ? '—' : `${num(r.latency_ms, 0)} ms`}</td>
                        <td className="num">{num(r.total_tokens as number | null | undefined)}</td>
                        <td>{r.error_category ?? '—'}</td>
                        <td><details><summary>View</summary><pre className="json">{JSON.stringify(r, null, 2)}</pre></details></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <p className="caption">Row fields have not been verified against a live database yet. Fields that are missing show “—”; “All fields” shows exactly what the service returned.</p>
          </Card>
        </>
      )}
    </>
  )
}
