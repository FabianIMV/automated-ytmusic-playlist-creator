import { KeyRound, ServerCrash } from 'lucide-react'
import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { ConnectModal } from './components/ConnectModal'
import { Header } from './components/Header'
import { LoginScreen } from './components/LoginScreen'
import { Button, Logo, Notice, Spinner } from './components/ui'
import { SUPABASE_ENABLED } from './config'
import { AccountProvider, useAccount } from './context/AccountContext'
import { AuthProvider, useAuth } from './context/AuthContext'
import { ToastProvider } from './context/ToastContext'
import { api, ApiError } from './lib/api'
import type { Health } from './lib/types'
import { useHashRoute } from './lib/useHashRoute'
import { CreateView } from './views/CreateView'
import { HistoryView } from './views/HistoryView'
import { JobView } from './views/JobView'

/** Pantalla centrada para estados de arranque (cargando, error, configuración). */
function Centered({ children }: { children: ReactNode }) {
  return (
    <main className="grid min-h-dvh place-items-center px-4 py-10">
      <div className="animate-fade-up w-full max-w-lg">{children}</div>
    </main>
  )
}

function Splash() {
  return (
    <main className="grid min-h-dvh place-items-center" aria-busy="true">
      <div className="flex flex-col items-center gap-4 text-muted">
        <Logo className="size-12 animate-pulse" />
        <span className="sr-only">Cargando…</span>
        <Spinner className="size-5" />
      </div>
    </main>
  )
}

function useHealth() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const ctrl = new AbortController()
    setError(null)
    api
      .health(ctrl.signal)
      .then(setHealth)
      .catch((err: unknown) => {
        if (ctrl.signal.aborted) return
        setError(err instanceof ApiError ? err.message : 'No se pudo contactar con el servidor.')
      })
    return () => ctrl.abort()
  }, [attempt])

  const retry = useCallback(() => setAttempt((n) => n + 1), [])
  return { health, error, retry }
}

function ServerDown({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <Centered>
      <div className="card p-8 text-center">
        <div className="mx-auto grid size-12 place-items-center rounded-full bg-bad/12 text-bad">
          <ServerCrash className="size-6" aria-hidden />
        </div>
        <h1 className="mt-4 text-xl font-semibold">No pudimos conectar con el servidor</h1>
        <p className="mt-1.5 text-sm text-muted">{message}</p>
        <p className="mt-1 text-xs text-faint">
          Comprueba que la API esté en marcha (en desarrollo: http://localhost:8000) o que VITE_API_BASE_URL apunte al
          lugar correcto.
        </p>
        <Button className="mt-6" variant="primary" onClick={onRetry}>
          Reintentar
        </Button>
      </div>
    </Centered>
  )
}

function AuthConfigMissing() {
  return (
    <Centered>
      <div className="card p-8">
        <div className="mx-auto grid size-12 place-items-center rounded-full bg-warn/12 text-warn">
          <KeyRound className="size-6" aria-hidden />
        </div>
        <h1 className="mt-4 text-center text-xl font-semibold">Falta configurar el inicio de sesión</h1>
        <p className="mt-2 text-center text-sm text-muted">
          El servidor exige iniciar sesión con Supabase (<code className="font-mono text-xs">AUTH_MODE=supabase</code>),
          pero este frontend se compiló sin las variables necesarias.
        </p>
        <Notice tone="warn" className="mt-5" title="Cómo solucionarlo">
          Define <code className="font-mono text-xs">VITE_SUPABASE_URL</code> y{' '}
          <code className="font-mono text-xs">VITE_SUPABASE_ANON_KEY</code> en el archivo{' '}
          <code className="font-mono text-xs">.env</code> del frontend y vuelve a compilarlo. Mientras tanto, la API
          rechazará todas las peticiones.
        </Notice>
      </div>
    </Centered>
  )
}

/** Interior de la app una vez resuelto el acceso. */
function Main() {
  const route = useHashRoute()
  const { error, refresh } = useAccount()

  return (
    <div className="flex min-h-dvh flex-col">
      <Header route={route} />
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-6 sm:px-6 sm:py-10">
        {error && (
          <Notice
            tone="bad"
            title="No pudimos cargar tu cuenta"
            className="mb-6"
            action={
              <Button size="sm" variant="secondary" onClick={() => void refresh()}>
                Reintentar
              </Button>
            }
          >
            {error}
          </Notice>
        )}
        {/* La vista de creación sigue montada para no perder la lista al navegar. */}
        <div hidden={route.name !== 'create'}>
          <CreateView />
        </div>
        {route.name === 'history' && <HistoryView />}
        {route.name === 'job' && <JobView key={route.id} id={route.id} />}
      </main>
      <footer className="mx-auto w-full max-w-5xl px-4 pb-8 text-center text-xs text-faint sm:px-6">
        Las playlists se crean en tu cuenta de YouTube Music. Esta app no está afiliada a YouTube ni a Google.
      </footer>
      <ConnectModal />
    </div>
  )
}

function Root() {
  const { health, error, retry } = useHealth()
  const auth = useAuth()

  if (error) return <ServerDown message={error} onRetry={retry} />
  if (!health) return <Splash />

  // El servidor exige Supabase pero el frontend no lo tiene configurado.
  if (health.auth_mode === 'supabase' && !SUPABASE_ENABLED) return <AuthConfigMissing />

  if (SUPABASE_ENABLED) {
    if (auth.status === 'loading') return <Splash />
    if (auth.status === 'signed-out') return <LoginScreen />
  }

  return (
    <AccountProvider>
      <Main />
    </AccountProvider>
  )
}

export default function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <Root />
      </AuthProvider>
    </ToastProvider>
  )
}
