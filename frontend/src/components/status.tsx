import { AlertTriangle, Check, Clock, Copy, SearchX, XCircle } from 'lucide-react'
import type { ReactNode } from 'react'
import type { ItemStatus, JobStatus } from '../lib/types'
import { Badge, Spinner, TONE_BUBBLE, type Tone } from './ui'

interface Meta {
  label: string
  tone: Tone
  icon: ReactNode
}

const ICON = 'size-4'

export const ITEM_META: Record<ItemStatus, Meta> = {
  pending: { label: 'En cola', tone: 'neutral', icon: <Clock className={ICON} aria-hidden /> },
  found: { label: 'Encontrada', tone: 'ok', icon: <Check className={ICON} aria-hidden /> },
  duplicate: { label: 'Duplicada', tone: 'info', icon: <Copy className={ICON} aria-hidden /> },
  not_found: { label: 'No encontrada', tone: 'warn', icon: <SearchX className={ICON} aria-hidden /> },
  error: { label: 'Error', tone: 'bad', icon: <AlertTriangle className={ICON} aria-hidden /> },
}

/** Círculo de color con el ícono del estado de una canción. */
export function ItemStatusBubble({ status, active }: { status: ItemStatus; active?: boolean }) {
  if (active) {
    return (
      <span className={`grid size-8 shrink-0 place-items-center rounded-full ${TONE_BUBBLE.accent}`}>
        <Spinner className={ICON} />
      </span>
    )
  }
  const meta = ITEM_META[status]
  return <span className={`grid size-8 shrink-0 place-items-center rounded-full ${TONE_BUBBLE[meta.tone]}`}>{meta.icon}</span>
}

export const JOB_META: Record<JobStatus, Meta> = {
  queued: { label: 'En cola', tone: 'neutral', icon: <Clock className="size-3.5" aria-hidden /> },
  running: { label: 'En curso', tone: 'accent', icon: <Spinner className="size-3.5" /> },
  completed: { label: 'Completado', tone: 'ok', icon: <Check className="size-3.5" aria-hidden /> },
  failed: { label: 'Falló', tone: 'bad', icon: <XCircle className="size-3.5" aria-hidden /> },
}

export function JobStatusBadge({ status }: { status: JobStatus }) {
  const meta = JOB_META[status]
  return (
    <Badge tone={meta.tone} icon={meta.icon}>
      {meta.label}
    </Badge>
  )
}
