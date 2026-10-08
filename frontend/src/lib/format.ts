import type { ItemResult, JobListEntry } from './types'

const rtf = new Intl.RelativeTimeFormat('es', { numeric: 'auto' })

/** "hace 5 minutos", "ayer", etc. */
export function relativeTime(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return ''
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return ''
  const diff = Math.round((t - now) / 1000) // negativo = pasado
  const abs = Math.abs(diff)
  if (abs < 45) return 'hace un momento'
  if (abs < 3600) return rtf.format(Math.round(diff / 60), 'minute')
  if (abs < 86400) return rtf.format(Math.round(diff / 3600), 'hour')
  if (abs < 86400 * 30) return rtf.format(Math.round(diff / 86400), 'day')
  if (abs < 86400 * 365) return rtf.format(Math.round(diff / (86400 * 30)), 'month')
  return rtf.format(Math.round(diff / (86400 * 365)), 'year')
}

export function fullDate(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString('es', { dateStyle: 'long', timeStyle: 'short' })
}

/** Duración entre dos fechas ISO: "12 s", "3 min 4 s". */
export function duration(start: string | null, end: string | null): string {
  if (!start || !end) return ''
  const secs = Math.max(0, Math.round((new Date(end).getTime() - new Date(start).getTime()) / 1000))
  if (secs < 60) return `${secs} s`
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return s ? `${m} min ${s} s` : `${m} min`
}

/** Mismas reglas que el backend: una por línea, sin vacías ni comentarios (#). */
export function parseSongLines(text: string): string[] {
  return text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l && !l.startsWith('#'))
}

export function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`
}

export function percent(processed: number, total: number): number {
  if (total <= 0) return 0
  return Math.min(100, Math.round((processed / total) * 100))
}

export function isActive(job: Pick<JobListEntry, 'status'>): boolean {
  return job.status === 'queued' || job.status === 'running'
}

/** Canciones que conviene reintentar. En un job fallido también las que quedaron pendientes. */
export function retryQueries(items: ItemResult[], includePending: boolean): string[] {
  return items
    .filter((i) => i.status === 'not_found' || i.status === 'error' || (includePending && i.status === 'pending'))
    .map((i) => i.query)
}

/** Comprueba que el valor sea un enlace con ?list=... o un ID de playlist. */
export function looksLikePlaylistRef(value: string): boolean {
  const v = value.trim()
  if (!v) return false
  if (/^https?:\/\//i.test(v)) return /[?&]list=[\w-]+/.test(v)
  return /^[\w-]{10,}$/.test(v)
}
