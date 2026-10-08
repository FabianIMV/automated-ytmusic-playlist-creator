import type { Session } from '@supabase/supabase-js'
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { SUPABASE_ENABLED } from '../config'
import { setTokenProvider, setUnauthorizedHandler } from '../lib/api'
import { supabasePromise } from '../lib/supabase'
import { useToast } from './ToastContext'

type AuthStatus = 'disabled' | 'loading' | 'signed-out' | 'signed-in'

interface AuthApi {
  status: AuthStatus
  session: Session | null
  /** Login con Google. Con `youtube: true` pide además el permiso de YouTube (modo simple). */
  signInWithGoogle: (opts?: { youtube?: boolean }) => Promise<void>
  /** Autoriza a la app a usar YouTube con Google (modo simple); al volver se conecta sola. */
  connectYouTubeWithGoogle: () => Promise<void>
  signOut: () => Promise<void>
  getAccessToken: () => Promise<string | null>
}

const AuthContext = createContext<AuthApi | null>(null)

const YOUTUBE_SCOPE = 'https://www.googleapis.com/auth/youtube'

/** Marca que, al volver del redirect de Google, hay que enviar el refresh token al backend. */
const CONNECT_FLAG = 'ytpc:connect-youtube'

export function hasConnectFlag(): boolean {
  try {
    return window.localStorage.getItem(CONNECT_FLAG) === '1'
  } catch {
    return false
  }
}

export function clearConnectFlag(): void {
  try {
    window.localStorage.removeItem(CONNECT_FLAG)
  } catch {
    /* sin almacenamiento: no hay nada que limpiar */
  }
}

function setConnectFlag(): boolean {
  try {
    window.localStorage.setItem(CONNECT_FLAG, '1')
    return true
  } catch {
    return false
  }
}

async function currentToken(): Promise<string | null> {
  const client = await supabasePromise
  if (!client) return null
  const { data } = await client.auth.getSession()
  return data.session?.access_token ?? null
}

// El token se registra al cargar el módulo: así ninguna petición sale antes que él.
if (SUPABASE_ENABLED) setTokenProvider(currentToken)

export function AuthProvider({ children }: { children: ReactNode }) {
  const { toast } = useToast()
  const [session, setSession] = useState<Session | null>(null)
  const [status, setStatus] = useState<AuthStatus>(SUPABASE_ENABLED ? 'loading' : 'disabled')

  useEffect(() => {
    if (!SUPABASE_ENABLED) return
    let active = true
    let unsubscribe: (() => void) | undefined
    void supabasePromise.then(async (client) => {
      if (!client || !active) return
      const { data } = await client.auth.getSession()
      if (!active) return
      setSession(data.session)
      setStatus(data.session ? 'signed-in' : 'signed-out')
      const { data: sub } = client.auth.onAuthStateChange((_event, next) => {
        setSession(next)
        setStatus(next ? 'signed-in' : 'signed-out')
      })
      unsubscribe = () => sub.subscription.unsubscribe()
    })
    return () => {
      active = false
      unsubscribe?.()
    }
  }, [])

  // Si el backend rechaza el token, se cierra la sesión local y se vuelve al login.
  useEffect(() => {
    if (!SUPABASE_ENABLED) return
    setUnauthorizedHandler((message) => {
      toast('error', message)
      void supabasePromise.then((client) => client?.auth.signOut())
    })
    return () => setUnauthorizedHandler(null)
  }, [toast])

  const startGoogle = useCallback(
    async (youtube: boolean) => {
      const client = await supabasePromise
      if (!client) return
      if (youtube) {
        // Sin el flag no podríamos saber, al volver, que hay que conectar YouTube.
        if (!setConnectFlag()) {
          toast('error', 'Tu navegador bloquea el almacenamiento local, necesario para conectar con Google.')
          return
        }
      } else {
        clearConnectFlag() // un intento anterior abandonado no debe contaminar este login
      }
      const { error } = await client.auth.signInWithOAuth({
        provider: 'google',
        options: {
          // Siempre vuelve a la raíz de la app (sin #ruta ni query) para que calce con
          // las Redirect URLs de Supabase, también bajo el subpath de GitHub Pages.
          redirectTo: window.location.origin + window.location.pathname,
          ...(youtube
            ? { scopes: YOUTUBE_SCOPE, queryParams: { access_type: 'offline', prompt: 'consent' } }
            : {}),
        },
      })
      if (error) {
        if (youtube) clearConnectFlag()
        toast('error', `No se pudo iniciar sesión con Google: ${error.message}`)
      }
    },
    [toast],
  )

  const signInWithGoogle = useCallback((opts?: { youtube?: boolean }) => startGoogle(Boolean(opts?.youtube)), [startGoogle])
  const connectYouTubeWithGoogle = useCallback(() => startGoogle(true), [startGoogle])

  const signOut = useCallback(async () => {
    const client = await supabasePromise
    await client?.auth.signOut()
  }, [])

  const value = useMemo<AuthApi>(
    () => ({ status, session, signInWithGoogle, connectYouTubeWithGoogle, signOut, getAccessToken: currentToken }),
    [status, session, signInWithGoogle, connectYouTubeWithGoogle, signOut],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthApi {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth debe usarse dentro de <AuthProvider>')
  return ctx
}
