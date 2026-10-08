import { API_BASE } from '../config'
import type {
  Health,
  Job,
  JobListEntry,
  Me,
  PlaylistRequest,
  Setlist,
  Source,
  YTMusicStatus,
} from './types'

/** Error de la API con el mensaje (`detail`) ya listo para mostrar. */
export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

type TokenProvider = () => Promise<string | null | undefined>
let tokenProvider: TokenProvider | null = null
let unauthorizedHandler: ((message: string) => void) | null = null

export function setTokenProvider(fn: TokenProvider | null): void {
  tokenProvider = fn
}

export function setUnauthorizedHandler(fn: ((message: string) => void) | null): void {
  unauthorizedHandler = fn
}

/** Convierte el `detail` de FastAPI (texto o lista de errores de validación) en un mensaje. */
function detailToMessage(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const parts = detail.map((entry) => {
      if (typeof entry === 'string') return entry
      if (entry && typeof entry === 'object' && 'msg' in entry) {
        const { msg, loc } = entry as { msg?: unknown; loc?: unknown }
        const field = Array.isArray(loc) ? String(loc[loc.length - 1] ?? '') : ''
        return field && field !== 'body' ? `${field}: ${String(msg)}` : String(msg)
      }
      return ''
    })
    return parts.filter(Boolean).join('; ')
  }
  return ''
}

function fallbackMessage(status: number): string {
  if (status === 401) return 'Tu sesión no es válida o expiró. Vuelve a iniciar sesión.'
  if (status === 404) return 'No se encontró el recurso solicitado.'
  if (status >= 500) return 'El servidor tuvo un problema. Inténtalo de nuevo en unos segundos.'
  return `La solicitud falló (HTTP ${status}).`
}

interface RequestOptions {
  body?: unknown
  signal?: AbortSignal
  auth?: boolean
}

async function request<T>(method: string, path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json'

  if (opts.auth !== false && tokenProvider) {
    const token = await tokenProvider()
    if (token) headers.Authorization = `Bearer ${token}`
  }

  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      signal: opts.signal,
    })
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err
    throw new ApiError(0, 'No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.')
  }

  if (res.status === 204) return undefined as T

  const text = await res.text()
  let data: unknown = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = null
    }
  }

  if (!res.ok) {
    const detail =
      data && typeof data === 'object' && 'detail' in data ? detailToMessage((data as { detail: unknown }).detail) : ''
    const message = detail || fallbackMessage(res.status)
    if (res.status === 401 && opts.auth !== false) unauthorizedHandler?.(message)
    throw new ApiError(res.status, message)
  }

  if (data === null) {
    throw new ApiError(
      res.status,
      'El servidor respondió algo inesperado. Revisa que VITE_API_BASE_URL apunte a la API correcta.',
    )
  }
  return data as T
}

export const api = {
  health: (signal?: AbortSignal) => request<Health>('GET', '/api/health', { signal, auth: false }),
  me: (signal?: AbortSignal) => request<Me>('GET', '/api/me', { signal }),
  saveCredentials: (raw: string) => request<YTMusicStatus>('PUT', '/api/ytmusic/credentials', { body: { raw } }),
  deleteCredentials: () => request<void>('DELETE', '/api/ytmusic/credentials'),
  parseSetlist: (source: Source, signal?: AbortSignal) =>
    request<Setlist>('POST', '/api/setlists/parse', { body: source, signal }),
  createPlaylist: (body: PlaylistRequest) => request<Job>('POST', '/api/playlists', { body }),
  listJobs: (signal?: AbortSignal) => request<JobListEntry[]>('GET', '/api/jobs', { signal }),
  getJob: (id: string, signal?: AbortSignal) =>
    request<Job>('GET', `/api/jobs/${encodeURIComponent(id)}`, { signal }),
}
