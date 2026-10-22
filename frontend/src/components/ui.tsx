import type { ReactNode } from 'react'
import { ApiError } from '../api/http'

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <header className="page-head">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  )
}

export function Card({ title, caption, children, className = '' }: { title?: string; caption?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      {title && <h2>{title}</h2>}
      {caption && <p className="caption">{caption}</p>}
      {children}
    </section>
  )
}

export function Kpi({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="kpi">
      <span className="kpi-label">{label}</span>
      <span className="kpi-value">{value}</span>
      {hint && <span className="kpi-hint">{hint}</span>}
    </div>
  )
}

export function Pill({ tone = 'neutral', children }: { tone?: 'neutral' | 'high' | 'medium' | 'low' | 'info' | 'warn'; children: ReactNode }) {
  return <span className={`pill pill-${tone}`}>{children}</span>
}

export function RiskPill({ category }: { category: string }) {
  const tone = category === 'High' ? 'high' : category === 'Medium' ? 'medium' : category === 'Low' ? 'low' : 'neutral'
  return <Pill tone={tone}>{category} risk</Pill>
}

export function Skeleton({ h = 16, w = '100%' }: { h?: number; w?: string }) {
  return <div className="skeleton" style={{ height: h, width: w }} aria-hidden="true" />
}

export function PageSkeleton() {
  return (
    <div role="status" aria-label="Loading">
      <div className="grid g3">
        {[0, 1, 2].map((i) => <div className="card" key={i}><Skeleton h={14} w="50%" /><div style={{ height: 12 }} /><Skeleton h={30} w="40%" /></div>)}
      </div>
      <div className="grid g2" style={{ marginTop: 16 }}>
        {[0, 1].map((i) => <div className="card" key={i}><Skeleton h={14} w="35%" /><div style={{ height: 12 }} /><Skeleton h={180} /></div>)}
      </div>
    </div>
  )
}

export function ErrorState({ error, onRetry, title = 'Something went wrong' }: { error?: Error | ApiError; onRetry?: () => void; title?: string }) {
  const api = error instanceof ApiError ? error : undefined
  return (
    <div className="state state-error" role="alert">
      <h2>{title}</h2>
      <p>{error?.message ?? 'Unexpected error.'}</p>
      {api?.requestId && <p className="muted small">Request ID: <code>{api.requestId}</code></p>}
      {onRetry && <button className="btn" onClick={onRetry}>Try again</button>}
    </div>
  )
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="state">
      <h2>{title}</h2>
      {children && <p className="muted">{children}</p>}
      {action}
    </div>
  )
}

export function DataNotice({ text }: { text?: string }) {
  if (!text) return null
  return <div className="notice" role="note"><strong>Synthetic data.</strong> {text}</div>
}

export function KeyValueList({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="kv">
      {items.map(([k, v]) => (
        <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
      ))}
    </dl>
  )
}

export function StatusDot({ tone }: { tone: 'ok' | 'bad' | 'idle' | 'warn' }) {
  return <span className={`dot dot-${tone}`} aria-hidden="true" />
}
