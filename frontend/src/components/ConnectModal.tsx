import { ArrowLeft, CheckCircle2, Info, KeyRound, Link2, LogOut, RefreshCw, ShieldCheck, Terminal } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { SUPABASE_ENABLED } from '../config'
import { useAccount } from '../context/AccountContext'
import { useAuth } from '../context/AuthContext'
import { useServerHealth } from '../context/HealthContext'
import { useToast } from '../context/ToastContext'
import { api, ApiError } from '../lib/api'
import { Modal } from './Modal'
import { Avatar, Badge, Button, FieldLabel, Notice } from './ui'

const STEPS = [
  <>
    Abre <strong className="font-semibold text-fg">music.youtube.com</strong> con tu sesión iniciada.
  </>,
  <>
    Pulsa <kbd className="rounded border border-line-strong bg-surface-2 px-1.5 py-0.5 font-mono text-xs">F12</kbd> para
    abrir las herramientas de desarrollo y entra en la pestaña <strong className="font-semibold text-fg">Network</strong>{' '}
    (Red).
  </>,
  <>
    Recarga la página o navega un poco y busca una petición <strong className="font-semibold text-fg">POST</strong> llamada{' '}
    <code className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-xs">browse</code>.
  </>,
  <>
    Haz clic derecho sobre ella y elige <strong className="font-semibold text-fg">Copy → Copy as cURL (bash)</strong>.
  </>,
  <>Pega aquí abajo lo que copiaste y pulsa «Conectar».</>,
]

type View = 'simple' | 'advanced'

export function ConnectModal() {
  const { me, connectOpen, connectInitial, closeConnect, setYtmusic } = useAccount()
  const { connectYouTubeWithGoogle } = useAuth()
  const health = useServerHealth()
  const { toast } = useToast()
  const status = me?.ytmusic
  const connected = Boolean(status?.connected)
  const mode = status?.mode ?? null

  // El modo simple necesita que el servidor lo tenga configurado y que haya login con Supabase.
  const simpleAvailable = health.google_connect && SUPABASE_ENABLED

  const [raw, setRaw] = useState('')
  const [saving, setSaving] = useState(false)
  const [removing, setRemoving] = useState(false)
  const [redirecting, setRedirecting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  // Conectada y mirando la vista de otro modo (cambiar de modo / actualizar credenciales).
  const [changing, setChanging] = useState(false)
  const [pickedView, setPickedView] = useState<View>('simple')

  // Cada vez que se abre, el formulario empieza limpio.
  useEffect(() => {
    if (!connectOpen) return
    setRaw('')
    setFormError(null)
    setRedirecting(false)
    setChanging(connectInitial === 'advanced' && connected)
    setPickedView(connectInitial === 'advanced' ? 'advanced' : 'simple')
    // Solo al abrir: el estado de conexión puede cambiar con el modal abierto.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connectOpen])

  const showStatus = connected && !changing
  const view: View = simpleAvailable ? pickedView : 'advanced'

  function switchMode() {
    setChanging(true)
    setFormError(null)
    setPickedView(mode === 'google' ? 'advanced' : 'simple')
  }

  async function onGoogle() {
    setRedirecting(true)
    try {
      await connectYouTubeWithGoogle()
    } finally {
      // Si el navegador redirige, esto no llega a verse; si falla, se puede reintentar.
      setRedirecting(false)
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (raw.trim().length < 10) {
      setFormError('Pega el cURL o los headers completos que copiaste desde las herramientas de desarrollo.')
      return
    }
    setSaving(true)
    setFormError(null)
    try {
      const next = await api.saveCredentials(raw)
      setYtmusic(next)
      setRaw('')
      toast('success', next.account?.name ? `Conectado como ${next.account.name}.` : 'YouTube Music conectado.')
      closeConnect()
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : 'No se pudieron guardar las credenciales.')
    } finally {
      setSaving(false)
    }
  }

  async function onDisconnect() {
    setRemoving(true)
    try {
      await api.deleteCredentials()
      setYtmusic({ connected: false, account: null, error: null, mode: null })
      toast('info', 'Cuenta de YouTube Music desconectada.')
      closeConnect()
    } catch (err) {
      toast('error', err instanceof ApiError ? err.message : 'No se pudo desconectar la cuenta.')
    } finally {
      setRemoving(false)
    }
  }

  const googleExpired = !connected && mode === 'google' && Boolean(status?.error)

  let title = 'Conectar YouTube Music'
  let description = 'Necesitamos una sesión de tu navegador para crear playlists en tu cuenta.'
  if (showStatus) {
    title = 'Tu cuenta de YouTube Music'
    description = 'La app usa esta cuenta para buscar canciones y crear tus playlists.'
  } else if (view === 'simple') {
    description = 'Son un par de clics: sin copiar ni pegar nada.'
  }

  return (
    <Modal open={connectOpen} onClose={closeConnect} title={title} description={description}>
      <div className="space-y-5">
        {googleExpired && (
          <Notice
            tone="warn"
            title="Google revocó o venció el permiso"
            action={
              view === 'simple' || !simpleAvailable ? undefined : (
                <Button size="sm" variant="secondary" onClick={() => setPickedView('simple')}>
                  Modo simple
                </Button>
              )
            }
          >
            {status?.error}
            <span className="mt-1 block text-muted">
              Pasa de vez en cuando (por ejemplo, si quitaste el acceso desde tu cuenta de Google). Vuelve a
              autorizarlo para seguir creando playlists.
            </span>
          </Notice>
        )}

        {!googleExpired && !connected && status?.error && (
          <Notice tone="warn" title="Hay que volver a conectar la cuenta">
            {status.error}
            <span className="mt-1 block text-muted">
              Es normal: Google vence la sesión de vez en cuando.{' '}
              {view === 'advanced' ? 'Pega un cURL nuevo para reconectar.' : 'Vuelve a conectar para seguir.'}
            </span>
          </Notice>
        )}

        {showStatus && status && (
          <>
            <div className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-surface p-3">
              <Avatar src={status.account?.photo_url} name={status.account?.name} className="size-11" />
              <div className="min-w-0 flex-1">
                <p className="truncate font-semibold">{status.account?.name ?? 'Cuenta conectada'}</p>
                {status.account?.handle && <p className="truncate text-sm text-muted">{status.account.handle}</p>}
              </div>
              <div className="flex basis-full flex-wrap items-center gap-1.5 pl-14 sm:basis-auto sm:pl-0">
                {mode && (
                  <Badge
                    tone="neutral"
                    icon={mode === 'google' ? <Link2 className="size-3.5" aria-hidden /> : <Terminal className="size-3.5" aria-hidden />}
                  >
                    {mode === 'google' ? 'Google' : 'Avanzado · cURL'}
                  </Badge>
                )}
                <Badge tone="ok" icon={<CheckCircle2 className="size-3.5" aria-hidden />}>
                  Conectada
                </Badge>
              </div>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
              <Button variant="danger" onClick={onDisconnect} loading={removing} icon={<LogOut className="size-4" />}>
                Desconectar
              </Button>
              {(mode === 'google' || simpleAvailable) && (
                <Button variant="secondary" onClick={switchMode} icon={<RefreshCw className="size-4" />}>
                  Cambiar de modo
                </Button>
              )}
              {mode !== 'google' && (
                <Button
                  variant="ghost"
                  onClick={() => {
                    setChanging(true)
                    setPickedView('advanced')
                  }}
                  icon={<KeyRound className="size-4" />}
                >
                  Actualizar credenciales
                </Button>
              )}
            </div>
          </>
        )}

        {!showStatus && view === 'simple' && (
          <div className="space-y-5">
            <p className="text-sm text-muted">
              Autoriza a la app a crear playlists en tu cuenta de YouTube. Tu YouTube Music Premium usa la misma cuenta.
            </p>

            <Button
              variant="primary"
              size="lg"
              className="w-full"
              onClick={onGoogle}
              loading={redirecting}
              icon={<Link2 className="size-4" />}
            >
              {googleExpired ? 'Volver a conectar con Google' : 'Conectar con Google'}
            </Button>

            <ul className="space-y-2 text-[13px] text-muted">
              <li className="flex items-start gap-2.5">
                <Info className="mt-0.5 size-4 shrink-0 text-faint" aria-hidden />
                <span>
                  Límite de unas 200 canciones por día: es la cuota gratuita de la API de YouTube.
                </span>
              </li>
              <li className="flex items-start gap-2.5">
                <Info className="mt-0.5 size-4 shrink-0 text-faint" aria-hidden />
                <span>
                  Google puede mostrar un aviso de «app no verificada». Es normal: elige{' '}
                  <strong className="font-semibold text-fg">Continuar</strong>.
                </span>
              </li>
            </ul>

            <div className="flex flex-col gap-2 border-t border-line pt-4 sm:flex-row sm:items-center sm:justify-between">
              <Button variant="ghost" size="sm" onClick={() => setPickedView('advanced')} icon={<Terminal className="size-4" />}>
                Usar modo avanzado (cURL)
              </Button>
              {connected && (
                <Button variant="ghost" size="sm" onClick={() => setChanging(false)}>
                  Cancelar
                </Button>
              )}
            </div>
          </div>
        )}

        {!showStatus && view === 'advanced' && (
          <form onSubmit={onSubmit} className="space-y-5">
            {simpleAvailable && (
              <div className="space-y-2">
                <button
                  type="button"
                  onClick={() => setPickedView('simple')}
                  className="inline-flex items-center gap-1.5 rounded-md text-sm font-medium text-accent-text transition-colors duration-150 hover:underline"
                >
                  <ArrowLeft className="size-4" aria-hidden />
                  Volver al modo simple
                </button>
                <p className="text-[13px] text-muted">
                  El modo avanzado conviene para listas grandes o si la búsqueda no encuentra bien tus canciones.
                </p>
              </div>
            )}

            <ol className="space-y-3">
              {STEPS.map((step, i) => (
                <li key={i} className="flex gap-3 text-sm text-muted">
                  <span className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-full border border-accent/40 bg-accent/10 text-xs font-semibold text-accent-text">
                    {i + 1}
                  </span>
                  <span className="min-w-0 flex-1">{step}</span>
                </li>
              ))}
            </ol>

            <div>
              <FieldLabel htmlFor="curl-raw">cURL o headers de la petición</FieldLabel>
              <textarea
                id="curl-raw"
                className="field thin-scroll h-36 resize-y font-mono text-xs leading-relaxed"
                placeholder={"curl 'https://music.youtube.com/...' \\\n  -H 'cookie: ...' \\\n  -H 'authorization: ...'"}
                value={raw}
                onChange={(e) => {
                  setRaw(e.target.value)
                  if (formError) setFormError(null)
                }}
                spellCheck={false}
                autoCapitalize="off"
                autoCorrect="off"
                aria-invalid={formError ? true : undefined}
                aria-describedby={formError ? 'curl-error' : undefined}
              />
            </div>

            {formError && (
              <div id="curl-error">
                <Notice tone="bad" title="No pudimos conectar la cuenta">
                  {formError}
                </Notice>
              </div>
            )}

            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              {connected && (
                <Button variant="ghost" onClick={() => setChanging(false)}>
                  Cancelar
                </Button>
              )}
              <Button type="submit" variant="primary" loading={saving} disabled={raw.trim().length === 0}>
                Conectar
              </Button>
            </div>
          </form>
        )}

        <p className="flex items-start gap-2 rounded-xl bg-surface-2 px-3 py-2.5 text-[13px] text-muted">
          <ShieldCheck className="mt-0.5 size-4 shrink-0 text-ok" aria-hidden />
          <span>
            {(showStatus ? mode === 'google' : view === 'simple')
              ? 'Guardamos en el servidor un permiso de Google (nunca tu contraseña), asociado a tu cuenta, y solo se usa para buscar canciones y crear tus playlists. No se devuelve al navegador y puedes desconectarlo cuando quieras o quitarlo desde tu cuenta de Google.'
              : 'Las credenciales se guardan en el servidor de la app, asociadas a tu cuenta, y solo se usan para buscar y agregar canciones. No se devuelven al navegador y puedes desconectarlas cuando quieras.'}
          </span>
        </p>
      </div>
    </Modal>
  )
}
