import { ListMusic, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { APP_NAME } from '../config'
import { useAuth } from '../context/AuthContext'
import { useServerHealth } from '../context/HealthContext'
import { Button, Logo } from './ui'

function GoogleMark() {
  return (
    <svg viewBox="0 0 48 48" className="size-5" aria-hidden>
      <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.9 2.4 30.4 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.9 6.1C12.4 13.6 17.7 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 3-2.2 5.5-4.7 7.2l7.6 5.9c4.4-4.1 6.9-10.1 6.9-17.6z" />
      <path fill="#FBBC05" d="M10.5 28.7a14.5 14.5 0 0 1 0-9.4l-7.9-6.1a24 24 0 0 0 0 21.6l7.9-6.1z" />
      <path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.6-5.9c-2.1 1.4-4.9 2.3-8.3 2.3-6.3 0-11.6-4.1-13.5-9.8l-7.9 6.1C6.5 42.6 14.6 48 24 48z" />
    </svg>
  )
}

export function LoginScreen() {
  const { signInWithGoogle } = useAuth()
  const health = useServerHealth()
  const [busy, setBusy] = useState(false)

  async function onClick() {
    setBusy(true)
    try {
      // Con el modo simple disponible, un solo clic inicia sesión y autoriza YouTube.
      await signInWithGoogle({ youtube: health.google_connect })
    } finally {
      // Si el navegador redirige, esto no llega a verse; si falla, se puede reintentar.
      setBusy(false)
    }
  }

  return (
    <main className="grid min-h-dvh place-items-center px-4 py-10">
      <div className="animate-fade-up w-full max-w-md">
        <div className="mb-8 flex flex-col items-center text-center">
          <Logo className="size-14 drop-shadow-[0_12px_30px_rgb(224_50_90/0.45)]" />
          <h1 className="mt-5 text-3xl font-semibold tracking-tight">{APP_NAME}</h1>
          <p className="mt-2 max-w-sm text-balance text-muted">
            Convierte la lista de un concierto en una playlist de YouTube Music en un par de clics.
          </p>
        </div>

        <div className="card p-6">
          <h2 className="text-lg font-semibold">Inicia sesión para continuar</h2>
          <p className="mt-1 text-sm text-muted">
            {health.google_connect
              ? 'Usamos tu cuenta de Google para identificarte y, con tu permiso, crear playlists en tu YouTube Music.'
              : 'Usamos tu cuenta de Google solo para identificarte y guardar tu historial.'}
          </p>
          <Button
            variant="secondary"
            size="lg"
            className="mt-5 w-full bg-white text-[#1f1f1f]! hover:border-white/60! hover:brightness-95"
            onClick={onClick}
            loading={busy}
            icon={<GoogleMark />}
          >
            Continuar con Google
          </Button>
          <ul className="mt-6 space-y-2.5 text-[13px] text-muted">
            <li className="flex items-center gap-2.5">
              <ListMusic className="size-4 text-accent-text" aria-hidden />
              Pega una lista o un enlace de setlist.fm
            </li>
            <li className="flex items-center gap-2.5">
              <Sparkles className="size-4 text-accent-text" aria-hidden />
              Revisa el resultado antes de crear la playlist
            </li>
          </ul>
        </div>
      </div>
    </main>
  )
}
