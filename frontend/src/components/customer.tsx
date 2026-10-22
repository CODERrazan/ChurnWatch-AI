import { Card, KeyValueList, Pill } from './ui'
import { fmtValue, labelize } from '../format'
import type { HistoricalOutcome, RiskAssessment, Snapshot } from '../types/main'

const GROUPS: { title: string; keys: string[] }[] = [
  { title: 'Account at snapshot', keys: ['months_since_start', 'tenure_months', 'age', 'monthly_income_sar', 'active_products_count', 'regular_salary_inflow', 'autopay_enabled', 'loan_active', 'debit_card_active', 'digital_banking_enrolled'] },
  { title: 'Activity and engagement', keys: ['monthly_transaction_count', 'transaction_count_change_3m_pct', 'active_digital_days_30d', 'digital_days_change_3m_pct', 'digital_logins_30d', 'digital_sessions_30d', 'external_transfer_count_30d', 'external_transfer_count_change_3m_pct', 'branch_visits_90d'] },
  { title: 'Balances and payments', keys: ['average_monthly_balance_sar', 'balance_change_3m_pct', 'failed_transaction_rate_pct', 'card_declines_30d', 'missed_salary_inflow_30d', 'bank_fee_charges_90d', 'overdraft_days_90d', 'recurring_payments_count'] },
  { title: 'Support and experience', keys: ['support_tickets_90d', 'unresolved_tickets', 'repeat_contact_same_issue_90d', 'complaints_90d', 'median_resolution_hours', 'nps_score', 'app_crashes_30d', 'failed_login_attempts_30d'] },
]

export function SnapshotGroups({ snapshot }: { snapshot: Snapshot }) {
  const used = new Set<string>(['customer_segment', ...GROUPS.flatMap((g) => g.keys)])
  const other = Object.keys(snapshot).filter((k) => !used.has(k))
  const groups = GROUPS.map((g) => ({ title: g.title, keys: g.keys.filter((k) => k in snapshot) }))
  if (other.length) groups.push({ title: 'Other fields', keys: other })
  return (
    <div className="grid g2">
      {groups.filter((g) => g.keys.length).map((g) => (
        <div key={g.title}>
          <h3>{g.title}</h3>
          <KeyValueList items={g.keys.map((k) => [labelize(k), fmtValue(k, snapshot[k])])} />
        </div>
      ))}
    </div>
  )
}

function OutcomeRow({ label, value, observed }: { label: string; value: number | null; observed: boolean }) {
  // A null label means "not yet observed". It is never shown as 0.
  let text: string
  let tone: 'neutral' | 'low' | 'high' = 'neutral'
  if (!observed || value === null) text = 'Not yet observed'
  else if (value === 1) { text = 'Churn observed'; tone = 'high' }
  else { text = 'No churn observed'; tone = 'low' }
  return (
    <div><dt>{label}</dt><dd><Pill tone={tone}>{text}</Pill></dd></div>
  )
}

export function OutcomePanel({ outcome }: { outcome: HistoricalOutcome }) {
  return (
    <Card title="Historical outcome" caption="Retrospective labels from the synthetic dataset. They are not predictions and are not used to compute the risk score.">
      <dl className="kv">
        <OutcomeRow label="Within 30 days" value={outcome.label_30d} observed={outcome.label_observed_30d} />
        <OutcomeRow label="Within 90 days" value={outcome.label_90d} observed={outcome.label_observed_90d} />
        <div><dt>Source</dt><dd>{outcome.outcome_source}</dd></div>
        <div><dt>Retrospective only</dt><dd>{outcome.retrospective_only ? 'Yes' : 'No'}</dd></div>
      </dl>
    </Card>
  )
}

export function RiskFactors({ assessment }: { assessment: RiskAssessment }) {
  return (
    <Card title="Rule-based risk assessment" caption={`Transparent indicator rules, scored in ${assessment.risk_score_unit}. This is not a trained model and not a churn probability.`}>
      <div className="thresholds">
        {Object.entries(assessment.thresholds).map(([k, v]) => <span key={k}><strong>{k}</strong> {v}</span>)}
      </div>
      <ul className="factors">
        {assessment.risk_factors.map((f) => (
          <li key={f.feature}>
            <div className="factor-head">
              <strong>{labelize(f.feature)}</strong>
              <span className="muted">Observed: {fmtValue(f.feature, f.observed_value)}</span>
              <Pill tone="info">+{f.points} {f.points === 1 ? 'point' : 'points'}</Pill>
            </div>
            <p className="small muted">{f.interpretation}</p>
          </li>
        ))}
      </ul>
      {assessment.risk_factors.length === 0 && <p className="muted">No risk indicators were triggered for this snapshot.</p>}
      <h3>Limitations</h3>
      <ul className="small muted">{assessment.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
    </Card>
  )
}
