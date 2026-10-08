// Tipos del contrato de la API (ver docs/ARQUITECTURA.md).

export type Privacy = 'PUBLIC' | 'UNLISTED' | 'PRIVATE'
export type JobStatus = 'queued' | 'running' | 'completed' | 'failed'
export type ItemStatus = 'pending' | 'found' | 'duplicate' | 'not_found' | 'error'
export type AuthMode = 'none' | 'supabase'

export type Source =
  | { type: 'text'; text: string }
  | { type: 'songs'; songs: string[] }
  | { type: 'setlistfm'; url: string }

export interface Setlist {
  artist: string | null
  event_info: string | null
  songs: string[]
  suggested_name: string
  suggested_description: string
}

export interface PlaylistRequest {
  source: Source
  name?: string
  description?: string
  privacy?: Privacy
  playlist_id?: string
  dry_run?: boolean
}

export interface Track {
  video_id: string
  title: string
  artists: string[]
  album: string | null
  duration: string | null
  thumbnail: string | null
  result_type: string | null
}

export interface ItemResult {
  index: number
  query: string
  status: ItemStatus
  track: Track | null
  error: string | null
}

export interface JobSummary {
  total: number
  processed: number
  found: number
  added: number
  duplicates: number
  not_found: number
  errors: number
}

export interface Job {
  id: string
  owner_id: string
  status: JobStatus
  created_at: string
  started_at: string | null
  finished_at: string | null
  dry_run: boolean
  name: string | null
  description: string | null
  privacy: Privacy
  artist: string | null
  event_info: string | null
  playlist_id: string | null
  playlist_url: string | null
  summary: JobSummary
  items: ItemResult[]
  message: string | null
  error: string | null
}

/** GET /api/jobs devuelve los jobs sin `items`. */
export type JobListEntry = Omit<Job, 'items'>

export interface Health {
  status: 'ok'
  version: string
  auth_mode: AuthMode
  /** true si el servidor tiene configurado el modo simple (conexión con Google). */
  google_connect: boolean
}

/** Cómo está conectada la cuenta: permiso de Google (simple) o cURL del navegador (avanzado). */
export type YTMode = 'google' | 'browser'

export interface YTMusicAccount {
  name: string | null
  handle: string | null
  photo_url: string | null
}

export interface YTMusicStatus {
  connected: boolean
  account: YTMusicAccount | null
  error: string | null
  mode: YTMode | null
}

export interface AppUser {
  id: string
  email: string | null
  name: string | null
  avatar_url: string | null
}

export interface Me {
  user: AppUser
  auth_mode: AuthMode
  ytmusic: YTMusicStatus
}
