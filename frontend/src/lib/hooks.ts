import { useEffect, useRef, useState } from 'react'
import { api, ApiError } from './api'
import { isActive } from './format'
import type { Job } from './types'

/** Fuerza un re-render cada `ms` (para refrescar fechas relativas). */
export function useTick(ms = 30_000): number {
  const [tick, setTick] = useState(0)
  useEffect(() => {
    const id = window.setInterval(() => setTick((t) => t + 1), ms)
    return () => window.clearInterval(id)
  }, [ms])
  return tick
}

interface JobState {
  job: Job | null
  /** Error definitivo (404, 401...): se deja de consultar. */
  error: ApiError | null
  /** Fallo transitorio de red: se sigue reintentando. */
  offline: boolean
}

/** Consulta GET /api/jobs/{id} cada ~1 s mientras el job esté en cola o corriendo. */
export function useJob(id: string): JobState {
  const [state, setState] = useState<JobState & { forId: string }>({ job: null, error: null, offline: false, forId: id })
  const timer = useRef<number | undefined>(undefined)

  useEffect(() => {
    const ctrl = new AbortController()
    let cancelled = false

    const tick = async () => {
      try {
        const job = await api.getJob(id, ctrl.signal)
        if (cancelled) return
        setState({ job, error: null, offline: false, forId: id })
        if (isActive(job)) timer.current = window.setTimeout(tick, 1000)
      } catch (err) {
        if (cancelled) return
        if (err instanceof ApiError && err.status !== 0 && err.status < 500) {
          setState((cur) => ({ job: cur.forId === id ? cur.job : null, error: err, offline: false, forId: id }))
          return
        }
        setState((cur) => ({ job: cur.forId === id ? cur.job : null, error: null, offline: true, forId: id }))
        timer.current = window.setTimeout(tick, 2500)
      }
    }
    void tick()

    return () => {
      cancelled = true
      ctrl.abort()
      window.clearTimeout(timer.current)
    }
  }, [id])

  // Si cambió el id y aún no llega el nuevo job, no se muestra el anterior.
  if (state.forId !== id) return { job: null, error: null, offline: false }
  return state
}
