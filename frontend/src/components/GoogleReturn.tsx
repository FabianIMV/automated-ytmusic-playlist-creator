import { useEffect, useRef } from 'react'
import { SUPABASE_ENABLED } from '../config'
import { useAccount } from '../context/AccountContext'
import { clearConnectFlag, hasConnectFlag, useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { api, ApiError } from '../lib/api'

/**
 * Cierra el modo simple al volver del redirect de Google.
 *
 * Supabase solo entrega `provider_refresh_token` en la sesión recién creada (justo tras el
 * intercambio PKCE); en sesiones restauradas ya no viene. Por eso el flag de localStorage: si está
 * y la sesión trae el token, se envía una única vez al backend y no se guarda en ningún otro lado.
 * Cubre tanto el evento SIGNED_IN como la sesión que ya existe al cargar, porque ambos terminan
 * en `session`.
 */
export function GoogleReturn() {
  const { session } = useAuth()
  const { refresh, openConnect } = useAccount()
  const { toast } = useToast()
  const running = useRef(false)

  const refreshToken = session?.provider_refresh_token ?? null

  useEffect(() => {
    if (!SUPABASE_ENABLED || !refreshToken || running.current || !hasConnectFlag()) return
    running.current = true
    clearConnectFlag() // se borra antes de llamar: el token es de un solo uso aquí
    void (async () => {
      try {
        const status = await api.connectGoogle(refreshToken)
        const name = status.account?.name
        toast('success', name ? `Conectado a YouTube como ${name}.` : 'Conectado a YouTube.')
      } catch (err) {
        toast('error', err instanceof ApiError ? err.message : 'No se pudo conectar YouTube con Google.')
        openConnect()
      } finally {
        await refresh()
        running.current = false
      }
    })()
  }, [refreshToken, refresh, openConnect, toast])

  return null
}
