// Configuración en tiempo de compilación (variables VITE_*).
const env = import.meta.env

/** Base de la API; vacío = mismo origen. Sin "/" final. */
export const API_BASE = (env.VITE_API_BASE_URL ?? '').trim().replace(/\/+$/, '')

export const SUPABASE_URL = (env.VITE_SUPABASE_URL ?? '').trim()
export const SUPABASE_ANON_KEY = (env.VITE_SUPABASE_ANON_KEY ?? '').trim()

/** Con ambas variables se activa el login con Supabase; si no, modo local. */
export const SUPABASE_ENABLED = Boolean(SUPABASE_URL && SUPABASE_ANON_KEY)

export const APP_NAME = 'Playlist Creator'
