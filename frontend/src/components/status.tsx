import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { mainApiClient } from '../api/mainApiClient'
import { monitoringApiClient } from '../api/monitoringApiClient'
import { toApiError } from '../api/http'
import type { HealthResponse } from '../types/main'
import type { MonitoringHealth } from '../types/monitoring'

export type ServiceState = 'checking' | 'connected' | 'unavailable' | 'degraded'
export interface ServiceInfo { state: ServiceState; message?: string; checkedAt?: Date }

interface Ctx {
  main: ServiceInfo
  monitoring: ServiceInfo
  health: HealthResponse | null
  monitoringHealth: MonitoringHealth | null
  refresh: () => void
}

const StatusContext = createContext<Ctx | null>(null)

/** Checks each service independently. Neither check implies anything about the other. */
export function StatusProvider({ children }: { children: ReactNode }) {
  const [main, setMain] = useState<ServiceInfo>({ state: 'checking' })
  const [monitoring, setMonitoring] = useState<ServiceInfo>({ state: 'checking' })
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [monitoringHealth, setMonitoringHealth] = useState<MonitoringHealth | null>(null)

  const refresh = useCallback(() => {
    setMain((s) => ({ ...s, state: 'checking' }))
    setMonitoring((s) => ({ ...s, state: 'checking' }))
    mainApiClient.getHealth()
      .then((h) => {
        setHealth(h)
        const ok = h.status === 'ok' && h.application === 'available' && h.dataset === 'available'
        setMain({ state: ok ? 'connected' : 'degraded', message: ok ? undefined : 'Health reported a non-available state.', checkedAt: new Date() })
      })
      .catch((e) => { setHealth(null); setMain({ state: 'unavailable', message: toApiError(e).message, checkedAt: new Date() }) })
    monitoringApiClient.getHealth()
      .then((h) => {
        setMonitoringHealth(h)
        const ok = h.status === 'ok' && h.database === 'connected'
        setMonitoring({ state: ok ? 'connected' : 'degraded', message: ok ? undefined : `Status: ${h.status}, database: ${h.database}.`, checkedAt: new Date() })
      })
      .catch((e) => { setMonitoringHealth(null); setMonitoring({ state: 'unavailable', message: toApiError(e).message, checkedAt: new Date() }) })
  }, [])

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 60000)
    return () => clearInterval(t)
  }, [refresh])

  const value = useMemo(() => ({ main, monitoring, health, monitoringHealth, refresh }), [main, monitoring, health, monitoringHealth, refresh])
  return <StatusContext.Provider value={value}>{children}</StatusContext.Provider>
}

export function useStatus() {
  const ctx = useContext(StatusContext)
  if (!ctx) throw new Error('useStatus must be used inside StatusProvider')
  return ctx
}

export const stateLabel: Record<ServiceState, string> = {
  checking: 'Checking…',
  connected: 'Connected',
  unavailable: 'Unavailable',
  degraded: 'Degraded',
}
