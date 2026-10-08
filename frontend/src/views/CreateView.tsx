import {
  AlertTriangle,
  ClipboardList,
  FlaskConical,
  Globe,
  Link2,
  ListPlus,
  Lock,
  Mic2,
  RotateCcw,
  Search,
  X,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Badge, Button, FieldLabel, Notice, Segmented, Switch } from '../components/ui'
import { useAccount } from '../context/AccountContext'
import { useToast } from '../context/ToastContext'
import { api, ApiError } from '../lib/api'
import { looksLikePlaylistRef, parseSongLines, plural } from '../lib/format'
import type { Privacy, Setlist, Source } from '../lib/types'
import { navigate } from '../lib/useHashRoute'

type SourceTab = 'text' | 'setlistfm'

interface SongEntry {
  id: number
  text: string
}

interface Preview {
  setlist: Setlist
  songs: SongEntry[]
  /** Firma de la fuente analizada, para avisar si luego cambió. */
  signature: string
}

const SETLIST_URL = /^https?:\/\/(www\.)?setlist\.fm\/.+/

const EXAMPLE = `Oasis - Wonderwall
Blur - Song 2
Pulp - Common People
The Verve - Bitter Sweet Symphony
Radiohead - Creep`

const PRIVACY_OPTIONS = [
  { value: 'PUBLIC' as const, label: 'Pública', icon: <Globe className="size-4" aria-hidden /> },
  { value: 'UNLISTED' as const, label: 'No listada', icon: <Link2 className="size-4" aria-hidden /> },
  { value: 'PRIVATE' as const, label: 'Privada', icon: <Lock className="size-4" aria-hidden /> },
]

export function CreateView() {
  const { me, openConnect } = useAccount()
  const { toast } = useToast()

  const [tab, setTab] = useState<SourceTab>('text')
  const [text, setText] = useState('')
  const [url, setUrl] = useState('')
  const [parsing, setParsing] = useState(false)
  const [sourceError, setSourceError] = useState<string | null>(null)

  const [preview, setPreview] = useState<Preview | null>(null)
  const [removed, setRemoved] = useState<Set<number>>(new Set())
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [privacy, setPrivacy] = useState<Privacy>('PUBLIC')
  const [useExisting, setUseExisting] = useState(false)
  const [playlistRef, setPlaylistRef] = useState('')
  const [refError, setRefError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState<'dry' | 'create' | null>(null)

  const previewRef = useRef<HTMLElement>(null)

  const lines = useMemo(() => parseSongLines(text), [text])
  const unformatted = useMemo(() => lines.filter((l) => !l.includes(' - ')).length, [lines])
  const signature = tab === 'text' ? `text:${text}` : `url:${url.trim()}`
  const stale = preview !== null && preview.signature !== signature

  const visibleSongs = useMemo(() => (preview ? preview.songs.filter((s) => !removed.has(s.id)) : []), [preview, removed])

  // Al llegar una vista previa nueva, se lleva al usuario hasta ella.
  const previewKey = preview?.signature
  useEffect(() => {
    if (previewKey) previewRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [previewKey, preview?.setlist])

  async function onAnalyze() {
    setSourceError(null)
    let source: Source
    if (tab === 'text') {
      if (lines.length === 0) {
        setSourceError('Escribe o pega al menos una canción para poder analizarla.')
        return
      }
      source = { type: 'text', text }
    } else {
      const trimmed = url.trim()
      if (!SETLIST_URL.test(trimmed)) {
        setSourceError('Pega un enlace de setlist.fm, por ejemplo https://www.setlist.fm/setlist/...')
        return
      }
      source = { type: 'setlistfm', url: trimmed }
    }

    setParsing(true)
    try {
      const setlist = await api.parseSetlist(source)
      setPreview({
        setlist,
        songs: setlist.songs.map((s, i) => ({ id: i, text: s })),
        signature,
      })
      setRemoved(new Set())
      setName(setlist.suggested_name)
      setDescription(setlist.suggested_description)
    } catch (err) {
      setSourceError(err instanceof ApiError ? err.message : 'No se pudo analizar la fuente.')
    } finally {
      setParsing(false)
    }
  }

  async function onSubmit(dryRun: boolean) {
    if (!preview) return
    if (visibleSongs.length === 0) {
      toast('error', 'La lista está vacía. Restaura alguna canción o analiza otra fuente.')
      return
    }
    if (useExisting && !looksLikePlaylistRef(playlistRef)) {
      setRefError('Pega el enlace de la playlist (con «?list=…») o su ID.')
      return
    }
    setRefError(null)
    setSubmitting(dryRun ? 'dry' : 'create')
    try {
      const job = await api.createPlaylist({
        source: { type: 'songs', songs: visibleSongs.map((s) => s.text) },
        name: name.trim() || undefined,
        description,
        privacy,
        playlist_id: useExisting ? playlistRef.trim() : undefined,
        dry_run: dryRun,
      })
      if (!dryRun) {
        // Playlist en marcha: el formulario queda limpio para la siguiente.
        setPreview(null)
        setText('')
        setUrl('')
        setUseExisting(false)
        setPlaylistRef('')
      }
      navigate({ name: 'job', id: job.id })
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        toast('info', 'Primero conecta tu cuenta de YouTube Music para crear la playlist.')
        openConnect()
      } else {
        toast('error', err instanceof ApiError ? err.message : 'No se pudo crear la playlist.')
      }
    } finally {
      setSubmitting(null)
    }
  }

  const ytmusic = me?.ytmusic
  const busy = submitting !== null

  return (
    <div className="space-y-6">
      <section className="pt-2 pb-2">
        <h1 className="text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
          Crea tu playlist{' '}
          <span className="bg-[linear-gradient(120deg,#ff8a5c,#e0325a_55%,#c13aa8)] bg-clip-text text-transparent">
            en segundos
          </span>
        </h1>
        <p className="mt-2 max-w-2xl text-pretty text-muted">
          Pega la lista de canciones de un concierto o un enlace de setlist.fm, revisa el resultado y envíalo a YouTube
          Music.
        </p>
      </section>

      {ytmusic && !ytmusic.connected && (
        <Notice
          tone={ytmusic.error ? 'warn' : 'info'}
          title={ytmusic.error ? 'Tu conexión con YouTube Music venció' : 'Aún no conectas YouTube Music'}
          action={
            <Button size="sm" variant="secondary" onClick={openConnect}>
              {ytmusic.error ? 'Reconectar' : 'Conectar'}
            </Button>
          }
        >
          {ytmusic.error
            ? ytmusic.error
            : 'Puedes probar con «Solo buscar», pero para crear la playlist necesitas conectar tu cuenta.'}
        </Notice>
      )}

      {/* Paso 1: fuente */}
      <section className="card animate-fade-up p-4 sm:p-6" aria-labelledby="source-title">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 id="source-title" className="text-lg font-semibold">
            1. ¿De dónde salen las canciones?
          </h2>
          <div role="tablist" aria-label="Fuente de las canciones" className="flex gap-1 rounded-xl border border-line bg-surface p-1">
            {(
              [
                { id: 'text', label: 'Pegar lista', icon: <ClipboardList className="size-4" aria-hidden /> },
                { id: 'setlistfm', label: 'setlist.fm', icon: <Link2 className="size-4" aria-hidden /> },
              ] as const
            ).map((t) => (
              <button
                key={t.id}
                role="tab"
                type="button"
                id={`tab-${t.id}`}
                aria-selected={tab === t.id}
                aria-controls={`panel-${t.id}`}
                tabIndex={tab === t.id ? 0 : -1}
                onClick={() => {
                  setTab(t.id)
                  setSourceError(null)
                }}
                onKeyDown={(e) => {
                  if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return
                  e.preventDefault()
                  const next: SourceTab = t.id === 'text' ? 'setlistfm' : 'text'
                  setTab(next)
                  setSourceError(null)
                  requestAnimationFrame(() => document.getElementById(`tab-${next}`)?.focus())
                }}
                className={`flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-sm font-medium transition-colors duration-150 ${
                  tab === t.id ? 'bg-accent/15 text-accent-text' : 'text-muted hover:text-fg'
                }`}
              >
                {t.icon}
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {tab === 'text' ? (
          <div role="tabpanel" id="panel-text" aria-labelledby="tab-text">
            <FieldLabel
              htmlFor="songs-text"
              hint={
                text.trim() === '' ? (
                  <button
                    type="button"
                    className="font-medium text-accent-text underline-offset-2 hover:underline"
                    onClick={() => setText(EXAMPLE)}
                  >
                    Usar un ejemplo
                  </button>
                ) : undefined
              }
            >
              Lista de canciones
            </FieldLabel>
            <textarea
              id="songs-text"
              className="field thin-scroll min-h-44 resize-y leading-relaxed"
              rows={8}
              placeholder={'Oasis - Wonderwall\nBlur - Song 2\nPulp - Common People'}
              value={text}
              onChange={(e) => setText(e.target.value)}
              spellCheck={false}
              aria-describedby="songs-hint"
            />
            <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1.5" id="songs-hint">
              <Badge tone={lines.length ? 'accent' : 'neutral'}>{plural(lines.length, 'canción', 'canciones')}</Badge>
              <p className="text-xs text-faint">
                Una por línea, con el formato «Artista - Canción». Se ignoran las líneas vacías y las que empiezan con #.
              </p>
            </div>
            {unformatted > 0 && (
              <p className="mt-2 flex items-center gap-1.5 text-xs text-warn">
                <AlertTriangle className="size-3.5 shrink-0" aria-hidden />
                {plural(unformatted, 'línea no sigue', 'líneas no siguen')} el formato «Artista - Canción»; igualmente se
                buscarán.
              </p>
            )}
          </div>
        ) : (
          <div role="tabpanel" id="panel-setlistfm" aria-labelledby="tab-setlistfm">
            <FieldLabel htmlFor="setlist-url">Enlace del setlist</FieldLabel>
            <input
              id="setlist-url"
              type="url"
              inputMode="url"
              className="field"
              placeholder="https://www.setlist.fm/setlist/…"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') void onAnalyze()
              }}
              autoComplete="off"
              spellCheck={false}
            />
            <p className="mt-2 text-xs text-faint">
              Leeremos el artista, el evento y las canciones directamente desde la página del setlist.
            </p>
          </div>
        )}

        {sourceError && (
          <Notice tone="bad" className="mt-4">
            {sourceError}
          </Notice>
        )}

        <div className="mt-5 flex justify-end">
          <Button
            variant="primary"
            size="lg"
            onClick={onAnalyze}
            loading={parsing}
            icon={<Search className="size-4" />}
            className="w-full sm:w-auto"
          >
            {parsing ? 'Analizando…' : 'Analizar'}
          </Button>
        </div>
      </section>

      {/* Paso 2: vista previa */}
      {preview && (
        <section
          ref={previewRef}
          className="card animate-fade-up scroll-mt-40 p-4 sm:p-6"
          aria-labelledby="preview-title"
        >
          <div className="flex items-start gap-4">
            <div className="grid size-12 shrink-0 place-items-center rounded-xl bg-accent/15 text-accent-text">
              <Mic2 className="size-6" aria-hidden />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold tracking-wider text-faint uppercase">2. Vista previa</p>
              <h2 id="preview-title" className="truncate text-xl font-semibold tracking-tight">
                {preview.setlist.artist ?? 'Lista de canciones'}
              </h2>
              {preview.setlist.event_info && <p className="text-sm text-muted">{preview.setlist.event_info}</p>}
            </div>
          </div>

          {stale && (
            <Notice tone="warn" className="mt-4">
              La fuente cambió desde el último análisis. Pulsa «Analizar» otra vez para actualizar la vista previa.
            </Notice>
          )}

          <div className="mt-5 grid gap-6 lg:grid-cols-2">
            {/* Canciones */}
            <div className="min-w-0">
              <div className="mb-2 flex items-center justify-between gap-3">
                <h3 className="text-[13px] font-semibold">
                  Canciones{' '}
                  <span className="font-normal text-muted">
                    ({removed.size > 0 ? `${visibleSongs.length} de ${preview.songs.length}` : preview.songs.length})
                  </span>
                </h3>
                {removed.size > 0 && (
                  <button
                    type="button"
                    onClick={() => setRemoved(new Set())}
                    className="flex items-center gap-1.5 rounded-md text-xs font-medium text-accent-text hover:underline"
                  >
                    <RotateCcw className="size-3.5" aria-hidden />
                    Restaurar {removed.size}
                  </button>
                )}
              </div>
              {visibleSongs.length === 0 ? (
                <div className="rounded-xl border border-dashed border-line-strong px-4 py-10 text-center text-sm text-muted">
                  Quitaste todas las canciones. Restaura la lista para continuar.
                </div>
              ) : (
                <ol className="thin-scroll max-h-[26rem] overflow-y-auto rounded-xl border border-line bg-canvas/30 p-1">
                  {visibleSongs.map((song, i) => (
                    <li
                      key={song.id}
                      className="group flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 transition-colors duration-150 hover:bg-surface-2"
                    >
                      <span className="w-6 shrink-0 text-right text-xs text-faint tabular-nums">{i + 1}</span>
                      <span className="min-w-0 flex-1 text-sm break-words">{song.text}</span>
                      <button
                        type="button"
                        onClick={() => setRemoved((cur) => new Set(cur).add(song.id))}
                        className="grid size-8 shrink-0 place-items-center rounded-md text-muted transition duration-150 hover:bg-bad/10 hover:text-bad focus-visible:opacity-100 sm:opacity-0 sm:group-hover:opacity-100"
                        aria-label={`Quitar «${song.text}» de la lista`}
                      >
                        <X className="size-4" aria-hidden />
                      </button>
                    </li>
                  ))}
                </ol>
              )}
            </div>

            {/* Ajustes */}
            <div className="min-w-0 space-y-4">
              <div>
                <FieldLabel htmlFor="pl-name" hint={`${name.length}/150`}>
                  Nombre de la playlist
                </FieldLabel>
                <input
                  id="pl-name"
                  className="field"
                  value={name}
                  maxLength={150}
                  onChange={(e) => setName(e.target.value)}
                  disabled={useExisting}
                />
              </div>
              <div>
                <FieldLabel htmlFor="pl-desc">Descripción</FieldLabel>
                <textarea
                  id="pl-desc"
                  className="field thin-scroll resize-y text-sm leading-relaxed"
                  rows={5}
                  value={description}
                  maxLength={5000}
                  onChange={(e) => setDescription(e.target.value)}
                  disabled={useExisting}
                />
              </div>
              <div>
                <p className="mb-1.5 text-[13px] font-semibold">Privacidad</p>
                <Segmented
                  name="privacy"
                  label="Privacidad de la playlist"
                  value={privacy}
                  onChange={setPrivacy}
                  options={PRIVACY_OPTIONS}
                  disabled={useExisting}
                />
              </div>

              <div className="rounded-xl border border-line bg-surface p-3.5">
                <Switch
                  checked={useExisting}
                  onChange={(v) => {
                    setUseExisting(v)
                    setRefError(null)
                  }}
                  label="Agregar a una playlist existente"
                  description="En vez de crear una nueva, se suman las canciones a una que ya tengas."
                />
                {useExisting && (
                  <div className="animate-fade-up mt-3">
                    <FieldLabel htmlFor="pl-ref">Enlace o ID de la playlist</FieldLabel>
                    <input
                      id="pl-ref"
                      className="field"
                      placeholder="https://music.youtube.com/playlist?list=PL…"
                      value={playlistRef}
                      onChange={(e) => {
                        setPlaylistRef(e.target.value)
                        if (refError) setRefError(null)
                      }}
                      autoComplete="off"
                      spellCheck={false}
                      aria-invalid={refError ? true : undefined}
                      aria-describedby="pl-ref-help"
                    />
                    <p id="pl-ref-help" className={`mt-1.5 text-xs ${refError ? 'text-bad' : 'text-faint'}`}>
                      {refError ?? 'El nombre, la descripción y la privacidad no cambian en una playlist existente.'}
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="mt-6 flex flex-col-reverse gap-2.5 border-t border-line pt-5 sm:flex-row sm:items-center sm:justify-end">
            <Button
              variant="secondary"
              size="lg"
              onClick={() => onSubmit(true)}
              loading={submitting === 'dry'}
              disabled={busy || visibleSongs.length === 0}
              icon={<FlaskConical className="size-4" />}
              title="Busca las canciones sin escribir nada en tu cuenta"
            >
              Solo buscar (prueba)
            </Button>
            <Button
              variant="primary"
              size="lg"
              onClick={() => onSubmit(false)}
              loading={submitting === 'create'}
              disabled={busy || visibleSongs.length === 0}
              icon={<ListPlus className="size-4" />}
            >
              {useExisting ? 'Agregar a la playlist' : 'Crear playlist'}
            </Button>
          </div>
          <p className="mt-3 text-xs text-faint sm:text-right">
            «Solo buscar» comprueba qué canciones se encuentran sin tocar tu cuenta de YouTube Music.
          </p>
        </section>
      )}
    </div>
  )
}
