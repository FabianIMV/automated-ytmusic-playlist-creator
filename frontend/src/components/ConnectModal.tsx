import { CheckCircle2, KeyRound, LogOut, ShieldCheck } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { useAccount } from '../context/AccountContext'
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

export function ConnectModal() {
  const { me, connectOpen, closeConnect, setYtmusic } = useAccount()
  const { toast } = useToast()
  const status = me?.ytmusic
  const connected = Boolean(status?.connected)

  const [raw, setRaw] = useState('')
  const [saving, setSaving] = useState(false)
  const [removing, setRemoving] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [replacing, setReplacing] = useState(false)

  // Cada vez que se abre, el formulario empieza limpio.
  useEffect(() => {
    if (connectOpen) {
      setRaw('')
      setFormError(null)
      setReplacing(false)
    }
  }, [connectOpen])

  const showForm = !connected || replacing

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
      setYtmusic({ connected: false, account: null, error: null })
      toast('info', 'Cuenta de YouTube Music desconectada.')
      closeConnect()
    } catch (err) {
      toast('error', err instanceof ApiError ? err.message : 'No se pudo desconectar la cuenta.')
    } finally {
      setRemoving(false)
    }
  }

  return (
    <Modal
      open={connectOpen}
      onClose={closeConnect}
      title={connected ? 'Tu cuenta de YouTube Music' : 'Conectar YouTube Music'}
      description={
        connected
          ? 'La app usa esta cuenta para buscar canciones y crear tus playlists.'
          : 'Necesitamos una sesión de tu navegador para crear playlists en tu cuenta.'
      }
    >
      <div className="space-y-5">
        {status?.error && (
          <Notice tone="warn" title="Hay que volver a conectar la cuenta">
            {status.error}
            <span className="mt-1 block text-muted">
              Es normal: Google vence la sesión de vez en cuando. Pega un cURL nuevo para reconectar.
            </span>
          </Notice>
        )}

        {connected && status && (
          <div className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-surface p-3">
            <Avatar src={status.account?.photo_url} name={status.account?.name} className="size-11" />
            <div className="min-w-0 flex-1">
              <p className="truncate font-semibold">{status.account?.name ?? 'Cuenta conectada'}</p>
              {status.account?.handle && <p className="truncate text-sm text-muted">{status.account.handle}</p>}
            </div>
            <Badge tone="ok" icon={<CheckCircle2 className="size-3.5" aria-hidden />}>
              Conectada
            </Badge>
          </div>
        )}

        {connected && !replacing && (
          <div className="flex flex-col gap-2 sm:flex-row">
            <Button variant="danger" onClick={onDisconnect} loading={removing} icon={<LogOut className="size-4" />}>
              Desconectar
            </Button>
            <Button variant="secondary" onClick={() => setReplacing(true)} icon={<KeyRound className="size-4" />}>
              Actualizar credenciales
            </Button>
          </div>
        )}

        {showForm && (
          <form onSubmit={onSubmit} className="space-y-5">
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
                <Button variant="ghost" onClick={() => setReplacing(false)}>
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
            Las credenciales se guardan en el servidor de la app, asociadas a tu cuenta, y solo se usan para buscar y
            agregar canciones. No se devuelven al navegador y puedes desconectarlas cuando quieras.
          </span>
        </p>
      </div>
    </Modal>
  )
}
