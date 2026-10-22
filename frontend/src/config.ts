const trim = (u: string) => u.replace(/\/+$/, '')

/** Main API (FastAPI). Verified port: 8001. */
export const MAIN_API_BASE_URL = trim(import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8001')

/** Direct Monitoring URL (used by production builds, and as the proxy target in dev). */
export const MONITORING_DIRECT_URL = trim(import.meta.env.VITE_MONITORING_API_BASE_URL ?? 'http://127.0.0.1:8010')

/** In dev the browser goes through the Vite proxy because Monitoring has no CORS. */
export const MONITORING_BASE_URL: string = import.meta.env.DEV ? '/monitoring-proxy' : MONITORING_DIRECT_URL
