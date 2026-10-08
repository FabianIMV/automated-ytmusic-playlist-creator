import type { SupabaseClient } from '@supabase/supabase-js'
import { SUPABASE_ANON_KEY, SUPABASE_ENABLED, SUPABASE_URL } from '../config'

/**
 * Cliente de Supabase, cargado de forma diferida (así el modo local no descarga la librería).
 * Resuelve a `null` si faltan las variables de entorno.
 */
export const supabasePromise: Promise<SupabaseClient | null> = SUPABASE_ENABLED
  ? import('@supabase/supabase-js').then(({ createClient }) =>
      createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
        auth: {
          flowType: 'pkce', // no choca con el router por hash (#/...)
          persistSession: true,
          autoRefreshToken: true,
          detectSessionInUrl: true,
        },
      }),
    )
  : Promise.resolve(null)
