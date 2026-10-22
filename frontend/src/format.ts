export const num = (n: number | null | undefined, digits = 0) =>
  n == null ? '—' : n.toLocaleString('en-US', { maximumFractionDigits: digits })

export const pct = (rate: number | null | undefined, digits = 1) =>
  rate == null ? '—' : `${(rate * 100).toFixed(digits)}%`

export const labelize = (s: string) => s.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase())

const FLAGS = new Set([
  'regular_salary_inflow', 'autopay_enabled', 'loan_active', 'debit_card_active', 'digital_banking_enrolled',
])

export function fmtValue(key: string, v: unknown): string {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'number') {
    if (FLAGS.has(key)) return v === 1 ? 'Yes' : v === 0 ? 'No' : String(v)
    if (key.endsWith('_pct')) return `${num(v, 2)}%`
    if (key.endsWith('_sar')) return `${num(v, 2)} SAR`
    if (key.endsWith('_hours')) return `${num(v, 1)} h`
    return num(v, 2)
  }
  return String(v)
}

export const shortId = (id: string) => (id.length > 12 ? `${id.slice(0, 8)}…` : id)

/**
 * The API returns customer_insights as a list, but the live response put several bullets into
 * ONE string separated by " - ". This only splits for display; it does not change the content.
 */
export function splitInsights(items: string[]): string[] {
  return items
    .flatMap((s) => s.split(/\s+-\s+/))
    .map((s) => s.replace(/^\s*-\s*/, '').trim())
    .filter(Boolean)
}
