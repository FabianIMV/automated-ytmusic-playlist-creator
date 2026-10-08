import {
  AlertTriangle,
  ArrowLeft,
  Check,
  CheckCircle2,
  Copy,
  ExternalLink,
  FlaskConical,
  Globe,
  Link2,
  ListPlus,
  Lock,
  RotateCcw,
  SearchX,
  WifiOff,
} from 'lucide-react'
import { useMemo, useState, type ReactNode } from 'react'
import { ITEM_META, ItemStatusBubble, JobStatusBadge } from '../components/status'
import { Badge, Button, buttonClass, Notice, Skeleton, Thumb, TONE_TEXT, type Tone } from '../components/ui'
import { useAccount } from '../context/AccountContext'
import { useToast } from '../context/ToastContext'
import { api, ApiError } from '../lib/api'
import { duration, fullDate, isActive, percent, plural, relativeTime, retryQueries } from '../lib/format'
import { useJob, useTick } from '../lib/hooks'
import type { ItemResult, Job, Privacy } from '../lib/types'
import { navigate } from '../lib/useHashRoute'

const PRIVACY_LABEL: Record<Privacy, { label: string; icon: ReactNode }> = {
  PUBLIC: { label: 'Pública', icon: <Globe className="size-3.5" aria-hidden /> },
  UNLISTED: { label: 'No listada', icon: <Link2 className="size-3.5" aria-hidden /> },
  PRIVATE: { label: 'Privada', icon: <Lock className="size-3.5" aria-hidden /> },
}

function statusLine(job: Job): string {
  if (job.message) return job.message
  switch (job.status) {
    case 'queued':
      return 'En cola, esperando su turno…'
    case 'running':
      return job.dry_run ? 'Buscando canciones…' : 'Buscando y agregando canciones…'
    case 'completed':
      return job.dry_run ? 'Prueba terminada: no se escribió nada en tu cuenta.' : 'Listo: tu playlist ya está en YouTube Music.'
    case 'failed':
      return 'El proceso se detuvo antes de terminar.'
  }
}

function Stat({ tone, icon, value, label }: { tone: Tone; icon: ReactNode; value: number; label: string }) {
  return (
    <div className="flex items-center gap-2.5 rounded-xl border border-line bg-surface px-3 py-2 last:odd:col-span-2 sm:last:odd:col-span-1">
      <span className={TONE_TEXT[tone]}>{icon}</span>
      <div className="leading-tight">
        <p className="text-lg font-semibold tabular-nums">{value}</p>
        <p className="text-xs text-muted">{label}</p>
      </div>
    </div>
  )
}

function statusName(s: ItemResult['status']): string {
  return { pending: 'En cola', found: 'Encontrada', duplicate: 'Duplicada', not_found: 'No encontrada', error: 'Error' }[s]
}

function ItemRow({ item, active }: { item: ItemResult; active: boolean }) {
  const { track } = item
  const meta = track ? [track.artists.join(', '), track.album, track.duration].filter(Boolean).join(' · ') : ''
  const mismatch = track && !item.query.toLowerCase().includes(track.title.toLowerCase())

  let subtitle: ReactNode = meta
  let subtitleClass = 'text-muted'
  if (item.status === 'not_found') subtitle = 'No se encontró en YouTube Music'
  else if (item.status === 'pending') subtitle = active ? 'Buscando…' : 'En cola'
  else if (item.status === 'error' && item.error) {
    subtitle = item.error
    subtitleClass = 'text-bad'
  }

  return (
    <li
      className={`flex items-center gap-3 px-3 py-2.5 sm:px-4 ${active ? 'animate-pulse-row border-l-2 border-accent' : 'border-l-2 border-transparent'} ${
        item.status === 'pending' && !active ? 'opacity-60' : ''
      }`}
      aria-current={active ? 'step' : undefined}
    >
      <span className="hidden w-6 shrink-0 text-right text-xs text-faint tabular-nums sm:block">{item.index + 1}</span>
      <Thumb src={track?.thumbnail} className="size-11" />
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-2">
          <span className="truncate text-sm font-medium">{track?.title ?? item.query}</span>
          {track?.result_type === 'video' && (
            <span className="shrink-0 rounded border border-line-strong px-1.5 text-[10px] font-semibold tracking-wide text-muted uppercase">
              Video
            </span>
          )}
        </p>
        {subtitle && <p className={`line-clamp-2 text-[13px] break-words ${subtitleClass}`}>{subtitle}</p>}
        {mismatch && <p className="truncate text-xs text-faint">Buscada: {item.query}</p>}
      </div>
      <span className={`hidden w-28 shrink-0 text-right text-xs font-medium sm:block ${active ? 'text-accent-text' : TONE_TEXT[ITEM_META[item.status].tone]}`}>
        {active ? 'Buscando…' : statusName(item.status)}
      </span>
      <ItemStatusBubble status={item.status} active={active} />
      <span className="sr-only sm:hidden">{active ? 'Buscando' : statusName(item.status)}</span>
    </li>
  )
}

export function JobView({ id }: { id: string }) {
  const { job, error, offline } = useJob(id)
  const { me, openConnect, openConnectAdvanced } = useAccount()
  const { toast } = useToast()
  const [busy, setBusy] = useState<'retry' | 'create' | null>(null)
  const [filter, setFilter] = useState<'all' | 'issues'>('all')
  useTick(30_000)

  const active = job ? isActive(job) : false
  const firstPending = useMemo(
    () => (job && job.status === 'running' ? job.items.find((i) => i.status === 'pending')?.index : undefined),
    [job],
  )

  if (error) {
    return (
      <div className="card animate-fade-up mx-auto max-w-lg p-8 text-center">
        <div className="mx-auto grid size-12 place-items-center rounded-full bg-warn/12 text-warn">
          <SearchX className="size-6" aria-hidden />
        </div>
        <h1 className="mt-4 text-xl font-semibold">No encontramos este trabajo</h1>
        <p className="mt-1.5 text-sm text-muted">{error.message}</p>
        <p className="mt-1 text-xs text-faint">
          Los trabajos se guardan en memoria: si el servidor se reinició, el historial anterior se pierde.
        </p>
        <div className="mt-6 flex flex-col justify-center gap-2 sm:flex-row">
          <a href="#/historial" className={buttonClass('secondary', 'md')}>
            Ir al historial
          </a>
          <a href="#/" className={buttonClass('primary', 'md')}>
            Crear una playlist
          </a>
        </div>
      </div>
    )
  }

  if (!job) {
    return (
      <div className="space-y-4" aria-busy="true" aria-label="Cargando trabajo">
        <Skeleton className="h-5 w-24" />
        <div className="card space-y-4 p-6">
          <Skeleton className="h-7 w-2/3" />
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="h-3 w-full" />
          <div className="flex gap-3">
            <Skeleton className="h-14 w-28" />
            <Skeleton className="h-14 w-28" />
            <Skeleton className="h-14 w-28" />
          </div>
        </div>
        {offline && <Notice tone="warn">Sin conexión con el servidor. Reintentando…</Notice>}
      </div>
    )
  }

  const { summary } = job
  const pct = percent(summary.processed, summary.total)
  const finished = job.status === 'completed' || job.status === 'failed'
  const quotaExceeded = /cuota|quota/i.test(job.error ?? '')
  const failedOrRetryable = retryQueries(job.items, job.status === 'failed')
  const foundQueries = job.items.filter((i) => i.status === 'found').map((i) => i.query)
  const issues = job.items.filter((i) => i.status === 'not_found' || i.status === 'error')
  const shown = filter === 'issues' ? issues : job.items
  const privacy = PRIVACY_LABEL[job.privacy]

  async function launch(kind: 'retry' | 'create', songs: string[], overrides: { dry_run: boolean; playlist_id?: string }) {
    if (!job) return
    setBusy(kind)
    try {
      const next = await api.createPlaylist({
        source: { type: 'songs', songs },
        name: job.name ?? undefined,
        description: job.description ?? undefined,
        privacy: job.privacy,
        ...overrides,
      })
      navigate({ name: 'job', id: next.id })
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        toast('info', 'Primero conecta tu cuenta de YouTube Music para crear la playlist.')
        openConnect()
      } else {
        toast('error', err instanceof ApiError ? err.message : 'No se pudo crear el nuevo trabajo.')
      }
    } finally {
      setBusy(null)
    }
  }

  // Reintento: mismas búsquedas fallidas, en la misma playlist (o de nuevo en modo prueba).
  const onRetry = () =>
    launch('retry', failedOrRetryable, { dry_run: job.dry_run, playlist_id: job.playlist_id ?? undefined })
  // De prueba a real: con las canciones que sí se encontraron.
  const onCreateFromDryRun = () =>
    launch('create', foundQueries, { dry_run: false, playlist_id: job.playlist_id ?? undefined })

  return (
    <div className="space-y-5">
      <a
        href="#/historial"
        className="inline-flex items-center gap-1.5 rounded-md text-sm text-muted transition-colors duration-150 hover:text-fg"
      >
        <ArrowLeft className="size-4" aria-hidden />
        Historial
      </a>

      {offline && (
        <Notice tone="warn" title="Sin conexión con el servidor">
          <span className="inline-flex items-center gap-1.5">
            <WifiOff className="size-4" aria-hidden />
            Reintentando… el trabajo sigue corriendo en el servidor.
          </span>
        </Notice>
      )}

      <section className="card animate-fade-up p-4 sm:p-6" aria-labelledby="job-title" aria-live="off">
        <div className="flex flex-col-reverse items-start gap-2 sm:flex-row sm:justify-between sm:gap-4">
          <div className="min-w-0 sm:flex-1">
            <h1 id="job-title" className="text-balance text-2xl font-semibold tracking-tight break-words">
              {job.name ?? 'Playlist'}
            </h1>
            {(job.artist || job.event_info) && (
              <p className="mt-0.5 text-sm text-muted">{[job.artist, job.event_info].filter(Boolean).join(' · ')}</p>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {job.dry_run && (
              <Badge tone="info" icon={<FlaskConical className="size-3.5" aria-hidden />}>
                Prueba
              </Badge>
            )}
            {!job.dry_run && (
              <Badge tone="neutral" icon={privacy.icon}>
                {privacy.label}
              </Badge>
            )}
            <JobStatusBadge status={job.status} />
          </div>
        </div>

        {/* Progreso */}
        <div className="mt-5">
          <div className="mb-2 flex items-baseline justify-between gap-3 text-sm">
            <p className="text-muted" role="status">
              {statusLine(job)}
            </p>
            <p className="shrink-0 font-medium tabular-nums">
              {summary.processed} / {summary.total}
              <span className="ml-2 text-muted">{pct}%</span>
            </p>
          </div>
          <div
            className="relative h-2.5 overflow-hidden rounded-full bg-surface-2"
            role="progressbar"
            aria-label="Progreso de la búsqueda"
            aria-valuemin={0}
            aria-valuemax={summary.total}
            aria-valuenow={summary.processed}
          >
            <div
              className={`h-full rounded-full transition-[width] duration-300 ease-out ${
                job.status === 'failed'
                  ? 'bg-bad'
                  : job.status === 'completed'
                    ? 'bg-ok'
                    : 'bg-[linear-gradient(90deg,#ff7a59,#e0325a,#c13aa8)]'
              }`}
              style={{ width: `${pct}%` }}
            />
            {active && <div className="progress-shine absolute inset-0 overflow-hidden rounded-full" aria-hidden />}
          </div>
        </div>

        {/* Resumen */}
        <div className="mt-5 grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
          <Stat tone="ok" icon={<Check className="size-5" aria-hidden />} value={summary.found} label="Encontradas" />
          {!job.dry_run && (
            <Stat tone="accent" icon={<ListPlus className="size-5" aria-hidden />} value={summary.added} label="Agregadas" />
          )}
          <Stat tone="info" icon={<Copy className="size-5" aria-hidden />} value={summary.duplicates} label="Duplicadas" />
          <Stat tone="warn" icon={<SearchX className="size-5" aria-hidden />} value={summary.not_found} label="No encontradas" />
          <Stat tone="bad" icon={<AlertTriangle className="size-5" aria-hidden />} value={summary.errors} label="Errores" />
        </div>

        {job.status === 'failed' && job.error && (
          <Notice tone="bad" title="El trabajo falló" className="mt-5">
            {job.error}
          </Notice>
        )}

        {job.status === 'failed' && quotaExceeded && (
          <Notice tone="info" title="Se agotó la cuota diaria de YouTube" className="mt-3">
            Las canciones que no alcanzaron a procesarse quedaron pendientes. Puedes reintentar mañana
            {me?.ytmusic.mode !== 'browser' ? ' o usar el modo avanzado.' : '.'}
            {me?.ytmusic.mode !== 'browser' && (
              <Button size="sm" variant="secondary" className="mt-3" onClick={openConnectAdvanced}>
                Usar modo avanzado
              </Button>
            )}
          </Notice>
        )}

        {finished && (
          <div className="mt-5 flex flex-col gap-2.5 border-t border-line pt-5 sm:flex-row sm:flex-wrap sm:items-center">
            {job.playlist_url && !job.dry_run && (
              <a href={job.playlist_url} target="_blank" rel="noopener noreferrer" className={buttonClass('primary', 'lg')}>
                <ExternalLink className="size-4" aria-hidden />
                Abrir en YouTube Music
              </a>
            )}
            {job.dry_run && foundQueries.length > 0 && (
              <Button
                variant="primary"
                size="lg"
                onClick={onCreateFromDryRun}
                loading={busy === 'create'}
                disabled={busy !== null}
                icon={<ListPlus className="size-4" />}
              >
                Crear playlist con estos resultados
              </Button>
            )}
            {failedOrRetryable.length > 0 && (
              <Button
                variant="secondary"
                size="lg"
                onClick={onRetry}
                loading={busy === 'retry'}
                disabled={busy !== null}
                icon={<RotateCcw className="size-4" />}
              >
                {job.status === 'failed' ? 'Reintentar las que faltan' : 'Reintentar no encontradas'} ({failedOrRetryable.length})
              </Button>
            )}
            <a href="#/" className={buttonClass('ghost', 'lg')}>
              Nueva playlist
            </a>
          </div>
        )}

        <p className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-faint">
          <span title={fullDate(job.created_at)}>Creado {relativeTime(job.created_at)}</span>
          {finished && job.started_at && job.finished_at && <span>Duración: {duration(job.started_at, job.finished_at)}</span>}
          {job.playlist_url && !job.dry_run && (
            <span className="inline-flex items-center gap-1">
              <CheckCircle2 className="size-3.5 text-ok" aria-hidden />
              Playlist creada
            </span>
          )}
        </p>
      </section>

      {/* Lista por canción */}
      <section className="card animate-fade-up overflow-hidden" aria-labelledby="items-title">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3 sm:px-6">
          <h2 id="items-title" className="font-semibold">
            Canciones <span className="font-normal text-muted">({plural(job.items.length, 'pista', 'pistas')})</span>
          </h2>
          {issues.length > 0 && (
            <div role="group" aria-label="Filtrar canciones" className="flex gap-1 rounded-lg border border-line bg-surface p-0.5 text-[13px]">
              {(
                [
                  { id: 'all', label: `Todas (${job.items.length})` },
                  { id: 'issues', label: `Con problemas (${issues.length})` },
                ] as const
              ).map((f) => (
                <button
                  key={f.id}
                  type="button"
                  aria-pressed={filter === f.id}
                  onClick={() => setFilter(f.id)}
                  className={`rounded-md px-2.5 py-1 font-medium transition-colors duration-150 ${
                    filter === f.id ? 'bg-accent/15 text-accent-text' : 'text-muted hover:text-fg'
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
          )}
        </div>
        <ul className="divide-y divide-line">
          {shown.map((item) => (
            <ItemRow key={item.index} item={item} active={item.index === firstPending} />
          ))}
        </ul>
      </section>
    </div>
  )
}
