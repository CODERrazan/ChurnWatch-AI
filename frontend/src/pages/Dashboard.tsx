import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { mainApiClient } from '../api/mainApiClient'
import { useAsync } from '../hooks/useAsync'
import { Card, DataNotice, EmptyState, ErrorState, Kpi, PageHeader, PageSkeleton, Pill, RiskPill } from '../components/ui'
import { labelize, num, pct, shortId } from '../format'
import type { RetroEvaluation } from '../types/main'

const RISK_COLORS: Record<string, string> = { High: '#F0674D', Medium: '#E8B04A', Low: '#4FB287' }
const tooltipStyle = { background: '#1C2536', border: '1px solid #2B3752', borderRadius: 8, color: '#E6EAF2' }

function Retro({ label, ev }: { label: string; ev: RetroEvaluation }) {
  if (ev.status !== 'available') {
    return <div className="retro"><h3>{label}</h3><p className="muted">Evaluation status: {ev.status}.</p></div>
  }
  const cm = ev.confusion_matrix
  return (
    <div className="retro">
      <h3>{label}</h3>
      <dl className="kv">
        <div><dt>Eligible snapshots</dt><dd>{num(ev.eligible_snapshots)}</dd></div>
        <div><dt>Unique customers</dt><dd>{num(ev.unique_customers)}</dd></div>
        <div><dt>Observed churn outcomes</dt><dd>{num(ev.positive_outcomes)}</dd></div>
        <div><dt>Precision</dt><dd>{pct(ev.precision, 1)}</dd></div>
        <div><dt>Recall</dt><dd>{pct(ev.recall, 1)}</dd></div>
        <div><dt>F1</dt><dd>{pct(ev.f1, 1)}</dd></div>
      </dl>
      {cm && (
        <table className="table compact">
          <thead><tr><th></th><th>Churn observed</th><th>No churn observed</th></tr></thead>
          <tbody>
            <tr><th scope="row">Rule alert (Medium/High)</th><td>{num(cm.true_positive)}</td><td>{num(cm.false_positive)}</td></tr>
            <tr><th scope="row">No alert (Low)</th><td>{num(cm.false_negative)}</td><td>{num(cm.true_negative)}</td></tr>
          </tbody>
        </table>
      )}
      {ev.alert_rule && <p className="caption">Alert rule: {ev.alert_rule}</p>}
      {ev.limitations && <ul className="small muted">{ev.limitations.map((l) => <li key={l}>{l}</li>)}</ul>}
    </div>
  )
}

export default function Dashboard() {
  const q = useAsync(() => mainApiClient.getDashboard(), [])
  const d = q.data

  return (
    <>
      <PageHeader title="Dashboard" subtitle="Retrospective view of the synthetic banking dataset and rule-based risk indicators." />
      {!d && q.status === 'loading' && <PageSkeleton />}
      {q.status === 'error' && <ErrorState error={q.error} onRetry={q.reload} title="Dashboard could not be loaded" />}
      {d && (
        <>
          <DataNotice text={d.data_notice} />
          <div className="grid g3">
            <Kpi label="Total customers" value={num(d.total_customers)} />
            <Kpi label="Historical churn count" value={num(d.historical_churn_count)} hint="Follow-up churn in synthetic outcome labels" />
            <Kpi label="Historical churn rate" value={pct(d.historical_churn_rate, 2)} hint="Retrospective; not a prediction" />
          </div>

          <div className="grid g2">
            <Card title="Risk distribution" caption="Customers by rule-based risk category (points: Low 0–2, Medium 3–5, High 6+). These are indicator points, not churn probabilities.">
              <div className="chart">
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={d.risk_distribution_chart}>
                    <CartesianGrid stroke="#26314A" vertical={false} />
                    <XAxis dataKey="category" stroke="#8A96AD" />
                    <YAxis stroke="#8A96AD" />
                    <Tooltip contentStyle={tooltipStyle} cursor={{ fill: '#ffffff10' }} formatter={(v) => num(Number(v))} />
                    <Bar dataKey="count" name="Customers" radius={[6, 6, 0, 0]}>
                      {d.risk_distribution_chart.map((r) => <Cell key={r.category} fill={RISK_COLORS[r.category] ?? '#5B9DF0'} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>

            <Card title="Churn within 30 days, by snapshot month" caption="Churned ÷ eligible snapshots for each month (retrospective, synthetic). Eligibility depends on whether the 30-day outcome has been observed.">
              <div className="chart">
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart data={d.churn_within_30d_trend.map((t) => ({ ...t, ratePct: t.rate * 100 }))}>
                    <CartesianGrid stroke="#26314A" vertical={false} />
                    <XAxis dataKey="snapshot_month" stroke="#8A96AD" tick={{ fontSize: 11 }} />
                    <YAxis stroke="#8A96AD" tickFormatter={(v) => `${v}%`} />
                    <Tooltip
                      contentStyle={tooltipStyle}
                      formatter={(v) => [`${Number(v).toFixed(2)}%`, 'Rate']}
                      labelFormatter={(l, p) => {
                        const row = p?.[0]?.payload as { churned: number; eligible_snapshots: number } | undefined
                        return row ? `${l} · ${num(row.churned)} of ${num(row.eligible_snapshots)} snapshots` : String(l)
                      }}
                    />
                    <Line type="monotone" dataKey="ratePct" stroke="#5B9DF0" strokeWidth={2} dot={{ r: 3 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>

          <Card title="Historical churn rate by customer segment" caption="Share of customers in each segment with a historical follow-up churn outcome.">
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th>Segment</th><th className="num">Customers</th><th className="num">Churned</th><th>Historical churn rate</th></tr></thead>
                <tbody>
                  {d.churn_rate_by_segment.map((s) => (
                    <tr key={s.customer_segment}>
                      <th scope="row">{s.customer_segment}</th>
                      <td className="num">{num(s.customers)}</td>
                      <td className="num">{num(s.historical_churned)}</td>
                      <td>
                        <div className="meter-row">
                          <div className="meter" aria-hidden="true"><span style={{ width: `${Math.min(100, s.historical_churn_rate * 250)}%` }} /></div>
                          <span>{pct(s.historical_churn_rate, 2)}</span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card title="Churn-associated factors" caption="Average feature values for snapshots with and without an observed 30-day churn. Descriptive association only; it does not show that a feature causes churn.">
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th>Feature</th><th className="num">Churned mean</th><th className="num">Retained mean</th><th className="num">Sample sizes (churned / retained)</th></tr></thead>
                <tbody>
                  {d.key_churn_associated_factors.map((f) => (
                    <tr key={f.feature}>
                      <th scope="row">{labelize(f.feature)}<div className="small muted">{f.interpretation}</div></th>
                      <td className="num">{num(f.churn_mean, 2)}</td>
                      <td className="num">{num(f.retained_mean, 2)}</td>
                      <td className="num">{num(f.churn_sample_size)} / {num(f.retained_sample_size)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card title="Retrospective evaluation of the rule alert" caption="How the rule alert compares with observed outcomes in the synthetic data. Snapshots repeat per customer, so these are descriptive, not performance claims for real banking.">
            <div className="grid g2">
              {Object.entries(d.retrospective_evaluation).map(([k, ev]) => (
                <Retro key={k} label={`${k.replace('d', '')}-day outcome`} ev={ev} />
              ))}
            </div>
          </Card>

          <div className="grid g2">
            <Card title="Data quality">
              <dl className="kv">
                <div><dt>Customer profile rows</dt><dd>{num(d.data_quality.profile_rows)}</dd></div>
                <div><dt>Monthly snapshot rows</dt><dd>{num(d.data_quality.snapshot_rows)}</dd></div>
                <div><dt>Outcome rows</dt><dd>{num(d.data_quality.outcome_rows)}</dd></div>
                <div><dt>Duplicate customer/date pairs</dt><dd>{num(d.data_quality.duplicate_customer_date_pairs)}</dd></div>
              </dl>
              <h3>Missing values by table</h3>
              {Object.entries(d.data_quality.missing_values_by_table).map(([table, cols]) => (
                <div key={table} className="small">
                  <strong>{table}</strong>
                  {Object.keys(cols).length === 0
                    ? <span className="muted"> — none</span>
                    : <ul>{Object.entries(cols).map(([c, n]) => <li key={c}>{c}: {num(n)}</li>)}</ul>}
                </div>
              ))}
            </Card>

            <Card title="Recent analysis activity" caption="Kept in the Main API's memory (up to 20 entries); it resets when the Main API restarts.">
              {d.recent_analysis_activity.length === 0 ? (
                <EmptyState title="No analyses yet">Run an AI analysis on a customer and it will appear here.</EmptyState>
              ) : (
                <div className="table-wrap">
                  <table className="table compact">
                    <thead><tr><th>Customer</th><th>Snapshot</th><th>Risk</th><th>LLM</th><th>Monitoring</th><th>Request</th></tr></thead>
                    <tbody>
                      {d.recent_analysis_activity.map((a) => (
                        <tr key={a.request_id}>
                          <td><Link to={`/customers/${a.customer_id}?snapshot_date=${a.snapshot_date}`}>{a.customer_id}</Link></td>
                          <td>{a.snapshot_date}</td>
                          <td><RiskPill category={a.risk_category} /></td>
                          <td><Pill tone={a.llm_status === 'available' ? 'low' : 'warn'}>{a.llm_status}</Pill></td>
                          <td><Pill tone={a.monitoring_delivery === 'recorded' ? 'low' : 'warn'}>{a.monitoring_delivery}</Pill></td>
                          <td><code title={a.request_id}>{shortId(a.request_id)}</code></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          </div>
        </>
      )}
    </>
  )
}
