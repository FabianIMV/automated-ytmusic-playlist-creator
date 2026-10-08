import { ChevronDown, KeyRound, LogOut } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'
import { useAccount } from '../context/AccountContext'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { copyText } from '../lib/clipboard'
import { Avatar } from './ui'

/** Menú de usuario (solo con Supabase): token de API y cerrar sesión. */
export function UserMenu() {
  const { me } = useAccount()
  const { session, signOut, getAccessToken } = useAuth()
  const { toast } = useToast()
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const menuId = useId()

  const meta = (session?.user.user_metadata ?? {}) as Record<string, unknown>
  const name = me?.user.name ?? (typeof meta.full_name === 'string' ? meta.full_name : null)
  const email = me?.user.email ?? session?.user.email ?? null
  const avatar = me?.user.avatar_url ?? (typeof meta.avatar_url === 'string' ? meta.avatar_url : null)

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  async function onCopyToken() {
    setOpen(false)
    const token = await getAccessToken()
    if (!token) {
      toast('error', 'No hay una sesión activa. Vuelve a iniciar sesión.')
      return
    }
    const ok = await copyText(token)
    if (ok) toast('success', 'Token copiado. Úsalo como «Bearer Token» en Postman; caduca en aproximadamente una hora.')
    else toast('error', 'No se pudo copiar el token al portapapeles.')
  }

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        aria-label="Menú de usuario"
        className="flex items-center gap-1.5 rounded-full border border-line bg-surface p-1 pr-2 transition-colors duration-150 hover:border-line-strong"
      >
        <Avatar src={avatar} name={name ?? email} className="size-8" />
        <ChevronDown className={`size-4 text-muted transition-transform duration-150 ${open ? 'rotate-180' : ''}`} aria-hidden />
      </button>

      {open && (
        <div
          id={menuId}
          role="menu"
          className="animate-fade-up absolute right-0 z-40 mt-2 w-64 overflow-hidden rounded-xl border border-line-strong bg-raised shadow-2xl"
        >
          <div className="border-b border-line px-4 py-3">
            <p className="truncate text-sm font-semibold">{name ?? 'Tu cuenta'}</p>
            {email && <p className="truncate text-[13px] text-muted">{email}</p>}
          </div>
          <div className="p-1.5">
            <button
              type="button"
              role="menuitem"
              onClick={onCopyToken}
              className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-left text-sm transition-colors duration-150 hover:bg-surface-2"
            >
              <KeyRound className="size-4 text-muted" aria-hidden />
              Copiar token de API
            </button>
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false)
                void signOut()
              }}
              className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-left text-sm transition-colors duration-150 hover:bg-surface-2"
            >
              <LogOut className="size-4 text-muted" aria-hidden />
              Cerrar sesión
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
