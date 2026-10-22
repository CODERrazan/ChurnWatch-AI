export type ApiErrorKind = 'network' | 'timeout' | 'http' | 'parse'

export class ApiError extends Error {
  kind: ApiErrorKind
  status?: number
  code?: string
  requestId?: string | null
  constructor(kind: ApiErrorKind, message: string, extra: { status?: number; code?: string; requestId?: string | null } = {}) {
    super(message)
    this.kind = kind
    this.status = extra.status
    this.code = extra.code
    this.requestId = extra.requestId
  }
}

const CODE_MESSAGES: Record<string, string> = {
  customer_not_found: 'This customer ID was not found.',
  invalid_risk_category: 'The selected risk category is not supported.',
  database_url_missing: 'The Monitoring service has no database configured (database_url_missing).',
  internal_error: 'The service reported an internal error.',
}

function describe(status: number, detail: unknown): { message: string; code?: string } {
  if (Array.isArray(detail)) {
    const msgs = detail.map((d) => (d && typeof d === 'object' && 'msg' in d ? String((d as { msg: unknown }).msg) : '')).filter(Boolean)
    return { message: `Invalid request: ${msgs.join('; ') || 'validation failed'}.` }
  }
  if (detail && typeof detail === 'object') {
    const d = detail as { code?: string; message?: string }
    if (d.code && CODE_MESSAGES[d.code]) return { message: CODE_MESSAGES[d.code], code: d.code }
    if (d.code) return { message: `${d.message ?? 'Request failed'} (${d.code}).`, code: d.code }
    if (d.message) return { message: d.message }
  }
  if (typeof detail === 'string') return { message: detail }
  if (status === 404) return { message: 'Nothing was found for this request (the customer or snapshot may not exist).' }
  return { message: `The service returned HTTP ${status}.` }
}

/**
 * Low-level JSON request. The base URL is always passed in by the caller,
 * so each API client talks only to its own service.
 */
export async function requestJson<T>(
  baseUrl: string,
  path: string,
  opts: { method?: 'GET' | 'POST'; timeoutMs?: number } = {},
): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), opts.timeoutMs ?? 15000)
  let res: Response
  try {
    res = await fetch(`${baseUrl}${path}`, {
      method: opts.method ?? 'GET',
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    })
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw new ApiError('timeout', 'The request timed out. The service may be busy or unreachable.')
    }
    throw new ApiError('network', `Cannot reach the service at ${baseUrl || 'this origin'}. Check that it is running.`)
  } finally {
    clearTimeout(timer)
  }
  const requestId = res.headers.get('x-request-id')
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    if (res.ok) throw new ApiError('parse', 'The service returned a response that is not valid JSON.', { status: res.status, requestId })
  }
  if (!res.ok) {
    const detail = body && typeof body === 'object' && 'detail' in body ? (body as { detail: unknown }).detail : undefined
    const d = describe(res.status, detail)
    throw new ApiError('http', d.message, { status: res.status, code: d.code, requestId })
  }
  return body as T
}

export function toApiError(e: unknown): ApiError {
  return e instanceof ApiError ? e : new ApiError('network', e instanceof Error ? e.message : 'Unexpected error.')
}
