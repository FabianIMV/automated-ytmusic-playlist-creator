import { createContext, useContext } from 'react'
import type { Health } from '../lib/types'

/** Respuesta de /api/health, ya resuelta (se provee solo cuando el servidor respondió). */
export const HealthContext = createContext<Health | null>(null)

export function useServerHealth(): Health {
  const ctx = useContext(HealthContext)
  if (!ctx) throw new Error('useServerHealth debe usarse dentro de <HealthContext.Provider>')
  return ctx
}
