import { AlertTriangle, ChevronRight, Copy, FlaskConical, History, ListPlus, RefreshCw, SearchX } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { JobStatusBadge } from '../components/status'
import { Badge, Button, buttonClass, Notice, Skeleton } from '../components/ui'
import { api, ApiError } from '../lib/api'
import { fullDate, isActive, percent, relativeTime } from '../lib/format'
import { useTick } from '../lib/hooks'
import type { JobListEntry } from '../lib/types'

function Counter({ children, className }: { children: ReactNode; className: string }) {
  return <span className={`inline-flex items-center gap-1 ${className}`}>{children}</span>
}

function JobRow({ job }: { job: JobListEntry }) {
  const { summary } = job
  const active = isActive(job)
  return (
    <li>
      <a
        href={`#/job/${encodeURIComponent(job.id)}`}
        className="card group flex items-center gap-3 p-4 transition duration-150 hover:-translate-y-px hover:border-line-strong"
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <p className="min-w-0 truncate font-semibold">{job.name ?? 'Playlist sin nombre'}</p>
            <div className="flex shrink-0 items-center gap-1.5">
              {job.dry_run && (
                <Badge tone="info" icon={<FlaskConical className="size-3" aria-hidden />}>
                  Prueba
                </Badge>
              )}
              <JobStatusBadge status={job.status} />
            </div>
          </div>
          <p className="mt-0.5 truncate text-sm text-muted">
            {[job.artist, job.event_info].filter(Boolean).join(' · ') || 'Lista de canciones'}
          </p>

          {active && (
            <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-surface-2" aria-hidden>
              <div
                className="h-full rounded-full bg-[linear-gradient(90deg,#ff7a59,#e0325a,#c13aa8)] transition-[width] duration-300"
                style={{ width: `${percent(summary.processed, summary.total)}%` }}
              />
            </div>
          )}

          <div className="mt-2 flex flex-wrap items-center gap-x-3.5 gap-y-1 text-xs text-muted">
            <span title={fullDate(job.created_at)} className="text-faint">
              {relativeTime(job.created_at)}
            </span>
            {active ? (
              <span className="tabular-nums">
                {summary.processed} / {summary.total} canciones
              </span>
            ) : (
              <>
                <Counter className="text-ok">
                  <span className="font-semibold tabular-nums">{summary.found}</span> encontradas
                </Counter>
                {!job.dry_run && (
                  <Counter className="text-accent-text">
                    <ListPlus className="size-3.5" aria-hidden />
                    <span className="font-semibold tabular-nums">{summary.added}</span> agregadas
                  </Counter>
                )}
                {summary.duplicates > 0 && (
                  <Counter className="text-info">
                    <Copy className="size-3.5" aria-hidden />
                    <span className="font-semibold tabular-nums">{summary.duplicates}</span> duplicadas
                  </Counter>
                )}
                {summary.not_found > 0 && (
                  <Counter className="text-warn">
                    <SearchX className="size-3.5" aria-hidden />
                    <span className="font-semibold tabular-nums">{summary.not_found}</span> no encontradas
                  </Counter>
                )}
                {summary.errors > 0 && (
                  <Counter className="text-bad">
                    <AlertTriangle className="size-3.5" aria-hidden />
                    <span className="font-semibold tabular-nums">{summary.errors}</span> con error
                  </Counter>
                )}
              </>
            )}
          </div>
        </div>
        <ChevronRight
          className="hidden size-5 shrink-0 text-faint transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-fg sm:block"
          aria-hidden
        />
      </a>
    </li>
  )
}

export function HistoryView() {
  const [jobs, setJobs] = useState<JobListEntry[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reload, setReload] = useState(0)
  useTick(30_000)

  // Carga inicial y, mientras haya trabajos activos, refresco cada 3 s.
  useEffect(() => {
    const ctrl = new AbortController()
    let timer: number | undefined
    let cancelled = false
    const load = async () => {
      try {
        const list = await api.listJobs(ctrl.signal)
        if (cancelled) return
        setJobs(list)
        setError(null)
        if (list.some(isActive)) timer = window.setTimeout(load, 3000)
      } catch (err) {
        if (cancelled) return
        setError(err instanceof ApiError ? err.message : 'No se pudo cargar el historial.')
      }
    }
    void load()
    return () => {
      cancelled = true
      ctrl.abort()
      window.clearTimeout(timer)
    }
  }, [reload])

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Historial</h1>
          <p className="mt-1 text-muted">Tus playlists y pruebas recientes, de la más nueva a la más antigua.</p>
        </div>
        <Button size="sm" variant="secondary" onClick={() => setReload((n) => n + 1)} icon={<RefreshCw className="size-4" />}>
          Actualizar
        </Button>
      </div>

      {error && (
        <Notice
          tone="bad"
          title="No pudimos cargar el historial"
          action={
            <Button size="sm" variant="secondary" onClick={() => setReload((n) => n + 1)}>
              Reintentar
            </Button>
          }
        >
          {error}
        </Notice>
      )}

      {jobs === null && !error && (
        <ul className="space-y-3" aria-busy="true" aria-label="Cargando historial">
          {[0, 1, 2].map((i) => (
            <li key={i} className="card space-y-2.5 p-4">
              <Skeleton className="h-5 w-1/2" />
              <Skeleton className="h-4 w-1/3" />
              <Skeleton className="h-3 w-2/3" />
            </li>
          ))}
        </ul>
      )}

      {jobs !== null && jobs.length === 0 && (
        <div className="card animate-fade-up px-6 py-14 text-center">
          <div className="mx-auto grid size-14 place-items-center rounded-full bg-accent/12 text-accent-text">
            <History className="size-7" aria-hidden />
          </div>
          <h2 className="mt-4 text-lg font-semibold">Todavía no hay nada por aquí</h2>
          <p className="mx-auto mt-1 max-w-sm text-sm text-muted">
            Cuando crees una playlist (o hagas una prueba), aparecerá en esta lista para que puedas revisarla.
          </p>
          <a href="#/" className={buttonClass('primary', 'md', 'mt-6')}>
            <ListPlus className="size-4" aria-hidden />
            Crear mi primera playlist
          </a>
        </div>
      )}

      {jobs !== null && jobs.length > 0 && (
        <ul className="animate-fade-up space-y-3">
          {jobs.map((job) => (
            <JobRow key={job.id} job={job} />
          ))}
        </ul>
      )}
    </div>
  )
}
