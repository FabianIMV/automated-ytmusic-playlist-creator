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
  signInWithGoogle: () => Promise<void>
  signOut: () => Promise<void>
  getAccessToken: () => Promise<string | null>
}

const AuthContext = createContext<AuthApi | null>(null)

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

  const signInWithGoogle = useCallback(async () => {
    const client = await supabasePromise
    if (!client) return
    const { error } = await client.auth.signInWithOAuth({
      provider: 'google',
      // Siempre vuelve a la raíz de la app (sin #ruta ni query) para que calce con
      // las Redirect URLs de Supabase, también bajo el subpath de GitHub Pages.
      options: { redirectTo: window.location.origin + window.location.pathname },
    })
    if (error) toast('error', `No se pudo iniciar sesión con Google: ${error.message}`)
  }, [toast])

  const signOut = useCallback(async () => {
    const client = await supabasePromise
    await client?.auth.signOut()
  }, [])

  const value = useMemo<AuthApi>(
    () => ({ status, session, signInWithGoogle, signOut, getAccessToken: currentToken }),
    [status, session, signInWithGoogle, signOut],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthApi {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth debe usarse dentro de <AuthProvider>')
  return ctx
}
