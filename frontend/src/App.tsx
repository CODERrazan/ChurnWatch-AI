import { NavLink, Route, Routes, Link } from 'react-router-dom'
import { StatusProvider, stateLabel, useStatus, type ServiceState } from './components/status'
import { StatusDot, EmptyState } from './components/ui'
import Dashboard from './pages/Dashboard'
import Customers from './pages/Customers'
import CustomerDetail from './pages/CustomerDetail'
import Analysis from './pages/Analysis'
import AnalysisPicker from './pages/AnalysisPicker'
import Monitoring from './pages/Monitoring'
import ServiceStatus from './pages/ServiceStatus'

const NAV = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/customers', label: 'Customer explorer' },
  { to: '/analysis', label: 'AI analysis' },
  { to: '/monitoring', label: 'Monitoring' },
  { to: '/status', label: 'Service status' },
]

const tone = (s: ServiceState) => (s === 'connected' ? 'ok' : s === 'checking' ? 'idle' : s === 'degraded' ? 'warn' : 'bad')

function Sidebar() {
  const { main, monitoring, health } = useStatus()
  return (
    <aside className="sidebar">
      <Link to="/" className="brand">ChurnWatch AI</Link>
      <nav aria-label="Main navigation">
        {NAV.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => (isActive ? 'nav active' : 'nav')}>
            {n.label}
          </NavLink>
        ))}
      </nav>
      <div className="svc" aria-label="Service status">
        <div><StatusDot tone={tone(main.state)} /> Main API <span className="muted">{stateLabel[main.state]}</span></div>
        <div><StatusDot tone={tone(monitoring.state)} /> Monitoring <span className="muted">{stateLabel[monitoring.state]}</span></div>
        <p className="small muted">{health?.data_notice ?? 'Data notice unavailable until the Main API responds.'}</p>
      </div>
    </aside>
  )
}

export default function App() {
  return (
    <StatusProvider>
      <div className="app">
        <Sidebar />
        <main className="main">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/customers" element={<Customers />} />
            <Route path="/customers/:id" element={<CustomerDetail />} />
            <Route path="/customers/:id/analysis" element={<Analysis />} />
            <Route path="/analysis" element={<AnalysisPicker />} />
            <Route path="/monitoring" element={<Monitoring />} />
            <Route path="/status" element={<ServiceStatus />} />
            <Route path="*" element={<EmptyState title="Page not found" action={<Link className="btn" to="/">Go to dashboard</Link>} />} />
          </Routes>
        </main>
      </div>
    </StatusProvider>
  )
}
