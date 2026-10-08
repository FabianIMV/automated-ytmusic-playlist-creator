import { useEffect, useMemo, useState } from 'react'

export type Route = { name: 'create' } | { name: 'history' } | { name: 'job'; id: string }

export function parseHash(hash: string): Route {
  const path = hash.startsWith('#/') ? hash.slice(1) : ''
  const parts = path.split('/').filter(Boolean)
  if (parts[0] === 'historial') return { name: 'history' }
  if (parts[0] === 'job' && parts[1]) return { name: 'job', id: decodeURIComponent(parts[1]) }
  return { name: 'create' }
}

export function hrefFor(route: Route): string {
  switch (route.name) {
    case 'history':
      return '#/historial'
    case 'job':
      return `#/job/${encodeURIComponent(route.id)}`
    default:
      return '#/'
  }
}

export function navigate(route: Route): void {
  window.location.hash = hrefFor(route)
}

/** Router mínimo basado en hash: compatible con GitHub Pages (sin rewrites). */
export function useHashRoute(): Route {
  const [hash, setHash] = useState(() => window.location.hash)
  useEffect(() => {
    const onChange = () => setHash(window.location.hash)
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return useMemo(() => parseHash(hash), [hash])
}
