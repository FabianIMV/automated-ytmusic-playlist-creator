import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api } from '../lib/api'
import type { Me, YTMusicStatus } from '../lib/types'

interface AccountApi {
  me: Me | null
  loading: boolean
  error: string | null
  /** Vuelve a consultar /api/me (usuario + estado de YouTube Music). */
  refresh: () => Promise<void>
  /** Actualiza el estado de YouTube Music sin otra petición (tras conectar/desconectar). */
  setYtmusic: (status: YTMusicStatus) => void
  connectOpen: boolean
  /** Abre el modal de conexión (en la vista por defecto: la simple si está disponible). */
  openConnect: () => void
  /** Lo abre directamente en la vista del modo avanzado (cURL). */
  openConnectAdvanced: () => void
  /** Vista con la que se abrió el modal. */
  connectInitial: 'default' | 'advanced'
  closeConnect: () => void
}

const AccountContext = createContext<AccountApi | null>(null)

export function AccountProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [connectOpen, setConnectOpen] = useState(false)
  const [connectInitial, setConnectInitial] = useState<'default' | 'advanced'>('default')

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      setMe(await api.me())
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo cargar tu cuenta.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const setYtmusic = useCallback((ytmusic: YTMusicStatus) => {
    setMe((cur) => (cur ? { ...cur, ytmusic } : cur))
  }, [])

  const openConnect = useCallback(() => {
    setConnectInitial('default')
    setConnectOpen(true)
  }, [])
  const openConnectAdvanced = useCallback(() => {
    setConnectInitial('advanced')
    setConnectOpen(true)
  }, [])
  const closeConnect = useCallback(() => setConnectOpen(false), [])

  const value = useMemo<AccountApi>(
    () => ({
      me,
      loading,
      error,
      refresh,
      setYtmusic,
      connectOpen,
      openConnect,
      openConnectAdvanced,
      connectInitial,
      closeConnect,
    }),
    [me, loading, error, refresh, setYtmusic, connectOpen, openConnect, openConnectAdvanced, connectInitial, closeConnect],
  )

  return <AccountContext.Provider value={value}>{children}</AccountContext.Provider>
}

export function useAccount(): AccountApi {
  const ctx = useContext(AccountContext)
  if (!ctx) throw new Error('useAccount debe usarse dentro de <AccountProvider>')
  return ctx
}
