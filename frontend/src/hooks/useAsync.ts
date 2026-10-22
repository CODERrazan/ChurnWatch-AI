import { useEffect, useState } from 'react'
import { ApiError, toApiError } from '../api/http'

interface State<T> { status: 'loading' | 'success' | 'error'; data?: T; error?: ApiError }

/** Runs an async function whenever `deps` change. Call reload() to retry. */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [state, setState] = useState<State<T>>({ status: 'loading' })
  const [tick, setTick] = useState(0)
  useEffect(() => {
    let cancelled = false
    setState((s) => ({ status: 'loading', data: s.data }))
    fn()
      .then((data) => { if (!cancelled) setState({ status: 'success', data }) })
      .catch((e) => { if (!cancelled) setState({ status: 'error', error: toApiError(e) }) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])
  return { ...state, reload: () => setTick((t) => t + 1) }
}
