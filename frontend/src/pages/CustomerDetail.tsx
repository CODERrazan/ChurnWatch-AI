import { Link, useParams, useSearchParams } from 'react-router-dom'
import { mainApiClient } from '../api/mainApiClient'
import { useAsync } from '../hooks/useAsync'
import { Card, DataNotice, EmptyState, ErrorState, KeyValueList, PageHeader, PageSkeleton, RiskPill } from '../components/ui'
import { OutcomePanel, RiskFactors, SnapshotGroups } from '../components/customer'
import { fmtValue, labelize } from '../format'

export default function CustomerDetail() {
  const { id = '' } = useParams()
  const [params] = useSearchParams()
  const snapshotDate = params.get('snapshot_date')
  const q = useAsync(() => mainApiClient.getCustomer(id, snapshotDate), [id, snapshotDate])
  const d = q.data
  const analysisLink = `/customers/${encodeURIComponent(id)}/analysis${snapshotDate ? `?snapshot_date=${snapshotDate}` : ''}`

  return (
    <>
      <p className="crumb"><Link to="/customers">← Customer explorer</Link></p>
      {!d && q.status === 'loading' && <PageSkeleton />}
      {q.status === 'error' && (
        <ErrorState error={q.error} onRetry={q.reload} title={q.error?.status === 404 ? 'Customer or snapshot not found' : 'Customer could not be loaded'} />
      )}
      {d && (
        <>
          <PageHeader
            title={d.customer_id}
            subtitle={`${String(d.profile.customer_segment ?? '')} · Snapshot ${d.snapshot_date}`}
            actions={<Link className="btn primary" to={analysisLink}>Run AI analysis</Link>}
          />
          <DataNotice text={d.data_notice} />

          <div className="hero">
            <div className="hero-main">
              <RiskPill category={d.risk_assessment.risk_category} />
              <div className="hero-score">{d.risk_assessment.risk_score}<span> points</span></div>
              <p className="caption">{d.risk_assessment.risk_score_unit}</p>
            </div>
            <div className="tile"><span>Tenure</span><strong>{fmtValue('tenure_months', d.current_snapshot.tenure_months)} months</strong></div>
            <div className="tile"><span>Monthly income</span><strong>{fmtValue('monthly_income_sar', d.profile.monthly_income_sar)}</strong></div>
            <div className="tile"><span>Risk factors</span><strong>{d.risk_assessment.risk_factors.length}</strong></div>
          </div>

          <RiskFactors assessment={d.risk_assessment} />

          <div className="grid g2">
            <Card title="Customer profile" caption="Profile values recorded at the start of the data window.">
              <KeyValueList items={Object.entries(d.profile).map(([k, v]) => [labelize(k), fmtValue(k, v)])} />
            </Card>
            <OutcomePanel outcome={d.historical_outcome} />
          </div>

          <Card title="Snapshot details" caption={`Selected features at ${d.snapshot_date}. Identifiers, scenario flags and future labels are excluded by the API.`}>
            <SnapshotGroups snapshot={d.current_snapshot} />
          </Card>

          <Card title="Analysis history" caption="Kept in the Main API's memory (up to 20 entries); it resets when the Main API restarts and is not durable storage.">
            {d.analysis_history.length === 0 ? (
              <EmptyState title="No analyses since the last restart" action={<Link className="btn" to={analysisLink}>Run AI analysis</Link>} />
            ) : (
              <div className="table-wrap">
                <table className="table compact">
                  <thead><tr>{Object.keys(d.analysis_history[0]).map((k) => <th key={k}>{labelize(k)}</th>)}</tr></thead>
                  <tbody>
                    {d.analysis_history.map((h, i) => (
                      <tr key={i}>{Object.keys(d.analysis_history[0]).map((k) => <td key={k}>{h[k] == null ? '—' : typeof h[k] === 'object' ? JSON.stringify(h[k]) : String(h[k])}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}
    </>
  )
}
