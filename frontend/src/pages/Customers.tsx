import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { mainApiClient } from '../api/mainApiClient'
import { useAsync } from '../hooks/useAsync'
import { Card, DataNotice, EmptyState, ErrorState, PageHeader, RiskPill, Skeleton } from '../components/ui'
import { num } from '../format'

export default function Customers() {
  const [search, setSearch] = useState('')
  const [debounced, setDebounced] = useState('')
  const [risk, setRisk] = useState('')
  const [segment, setSegment] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)

  useEffect(() => {
    const t = setTimeout(() => { setDebounced(search.trim()); setPage(1) }, 300)
    return () => clearTimeout(t)
  }, [search])

  // Segment names come from the dashboard so the filter uses real values.
  const seg = useAsync(() => mainApiClient.getDashboard(), [])
  const segments = seg.data?.churn_rate_by_segment.map((s) => s.customer_segment) ?? []

  const q = useAsync(
    () => mainApiClient.getCustomers({ page, page_size: pageSize, risk_category: risk || undefined, customer_segment: segment || undefined, search: debounced || undefined }),
    [page, pageSize, risk, segment, debounced],
  )
  const d = q.data
  const totalPages = d ? Math.max(1, Math.ceil(d.total / d.page_size)) : 1
  const clear = () => { setSearch(''); setDebounced(''); setRisk(''); setSegment(''); setPage(1) }
  const filtered = !!(debounced || risk || segment)

  return (
    <>
      <PageHeader title="Customer explorer" subtitle="Search and filter customers. Filtering and paging happen on the server." />
      <DataNotice text={d?.data_notice} />
      <Card>
        <div className="tools">
          <label>Customer ID
            <input className="input" type="search" placeholder="e.g. CUST_0002" value={search} onChange={(e) => setSearch(e.target.value)} />
          </label>
          <label>Risk category
            <select className="input" value={risk} onChange={(e) => { setRisk(e.target.value); setPage(1) }}>
              <option value="">All</option><option>High</option><option>Medium</option><option>Low</option>
            </select>
          </label>
          <label>Segment
            <select className="input" value={segment} onChange={(e) => { setSegment(e.target.value); setPage(1) }} disabled={segments.length === 0}>
              <option value="">All</option>
              {segments.map((s) => <option key={s}>{s}</option>)}
            </select>
          </label>
          <label>Rows per page
            <select className="input" value={pageSize} onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1) }}>
              {[25, 50, 100, 200].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
          {filtered && <button className="btn ghost" onClick={clear}>Clear filters</button>}
        </div>
        {seg.status === 'error' && <p className="small muted">Segment list unavailable ({seg.error?.message}). The segment filter is disabled.</p>}

        {q.status === 'error' && <ErrorState error={q.error} onRetry={q.reload} title="Customers could not be loaded" />}
        {!d && q.status === 'loading' && <div role="status" aria-label="Loading"><Skeleton h={220} /></div>}
        {d && d.total === 0 && (
          <EmptyState title="No customers match these filters" action={<button className="btn" onClick={clear}>Clear filters</button>}>
            Try a shorter customer ID or remove a filter.
          </EmptyState>
        )}
        {d && d.total > 0 && d.customers.length === 0 && (
          <EmptyState title="This page has no results" action={<button className="btn" onClick={() => setPage(1)}>Go to page 1</button>}>
            The page number is beyond the last page for these filters.
          </EmptyState>
        )}
        {d && d.customers.length > 0 && (
          <div className={q.status === 'loading' ? 'dim' : ''}>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr><th>Customer</th><th>Segment</th><th>Snapshot</th><th>Risk category</th><th className="num">Risk score</th><th className="num">Risk factors</th></tr>
                </thead>
                <tbody>
                  {d.customers.map((c) => (
                    <tr key={c.customer_id}>
                      <th scope="row"><Link to={`/customers/${c.customer_id}?snapshot_date=${c.snapshot_date}`}>{c.customer_id}</Link></th>
                      <td>{c.customer_segment}</td>
                      <td>{c.snapshot_date}</td>
                      <td><RiskPill category={c.risk_category} /></td>
                      <td className="num">{c.risk_score} <span className="muted small">pts</span></td>
                      <td className="num">{c.risk_factor_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="caption">Risk score unit: {d.customers[0].risk_score_unit}. Sorted High, Medium, Low, then customer ID.</p>
            <div className="pager">
              <button className="btn ghost" disabled={page <= 1 || q.status === 'loading'} onClick={() => setPage(page - 1)}>Previous</button>
              <span>Page {num(d.page)} of {num(totalPages)} · {num(d.total)} customers</span>
              <button className="btn ghost" disabled={page >= totalPages || q.status === 'loading'} onClick={() => setPage(page + 1)}>Next</button>
            </div>
          </div>
        )}
      </Card>
    </>
  )
}
