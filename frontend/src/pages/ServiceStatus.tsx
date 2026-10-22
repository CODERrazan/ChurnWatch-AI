import { Card, KeyValueList, PageHeader, Pill, StatusDot } from '../components/ui'
import { stateLabel, useStatus, type ServiceInfo } from '../components/status'
import { MAIN_API_BASE_URL, MONITORING_BASE_URL, MONITORING_DIRECT_URL } from '../config'

const tone = (s: ServiceInfo['state']) => (s === 'connected' ? 'ok' : s === 'checking' ? 'idle' : s === 'degraded' ? 'warn' : 'bad')

export default function ServiceStatus() {
  const { main, monitoring, health, monitoringHealth, refresh } = useStatus()
  return (
    <>
      <PageHeader title="Service status" subtitle="Each service is checked independently from this browser." actions={<button className="btn" onClick={refresh}>Check again</button>} />
      <div className="grid g2">
        <Card title="Main API">
          <p><StatusDot tone={tone(main.state)} /> <strong>{stateLabel[main.state]}</strong> {main.checkedAt && <span className="muted small">checked {main.checkedAt.toLocaleTimeString()}</span>}</p>
          {main.message && <p className="small muted">{main.message}</p>}
          <KeyValueList items={[
            ['URL used by this app', MAIN_API_BASE_URL],
            ['Application', health?.application ?? 'Not checked'],
            ['Dataset', health?.dataset ?? 'Not checked'],
          ]} />
        </Card>
        <Card title="Monitoring API">
          <p><StatusDot tone={tone(monitoring.state)} /> <strong>{stateLabel[monitoring.state]}</strong> {monitoring.checkedAt && <span className="muted small">checked {monitoring.checkedAt.toLocaleTimeString()}</span>}</p>
          {monitoring.message && <p className="small muted">{monitoring.message}</p>}
          <KeyValueList items={[
            ['Browser path', MONITORING_BASE_URL],
            ['Proxy target / direct URL', MONITORING_DIRECT_URL],
            ['Database (reported by Monitoring)', monitoringHealth?.database ?? 'Not available'],
          ]} />
        </Card>
      </div>
      <Card title="What is and is not verified" caption="Configuration values are shown for information. They do not prove connectivity.">
        <dl className="kv">
          <div><dt>Groq</dt><dd>{health ? <Pill tone="warn">{health.groq.configured ? 'Configured, not verified' : 'Not configured'}</Pill> : <Pill>Not checked</Pill>} {health && <span className="muted small">{health.groq.model}. The health check does not call Groq.</span>}</dd></div>
          <div><dt>Monitoring database (as seen by the Main API)</dt><dd>{health ? <Pill>{health.monitoring.database_connection === 'not_checked_by_main_api' ? 'Not checked by Main API' : health.monitoring.database_connection}</Pill> : <Pill>Not checked</Pill>}</dd></div>
          <div><dt>Monitoring URL configured in Main API</dt><dd>{health?.monitoring.url ?? 'Not available'}</dd></div>
        </dl>
      </Card>
    </>
  )
}
