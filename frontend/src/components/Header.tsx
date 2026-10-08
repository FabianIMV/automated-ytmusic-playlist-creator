import { AlertTriangle, Link2 } from 'lucide-react'
import { APP_NAME, SUPABASE_ENABLED } from '../config'
import { useAccount } from '../context/AccountContext'
import { hrefFor, type Route } from '../lib/useHashRoute'
import { UserMenu } from './UserMenu'
import { Avatar, Button, Logo, Skeleton } from './ui'

const NAV: { name: Route['name']; label: string; route: Route }[] = [
  { name: 'create', label: 'Crear', route: { name: 'create' } },
  { name: 'history', label: 'Historial', route: { name: 'history' } },
]

function Nav({ current, className = '' }: { current: Route['name']; className?: string }) {
  return (
    <nav aria-label="Principal" className={`items-center gap-1 ${className}`}>
      {NAV.map((item) => {
        const active = item.name === current
        return (
          <a
            key={item.name}
            href={hrefFor(item.route)}
            aria-current={active ? 'page' : undefined}
            className={`flex-1 rounded-lg px-3.5 py-1.5 text-center text-sm font-medium transition-colors duration-150 sm:flex-none ${
              active ? 'bg-surface-2 text-fg' : 'text-muted hover:text-fg'
            }`}
          >
            {item.label}
          </a>
        )
      })}
    </nav>
  )
}

function YtStatus() {
  const { me, loading, openConnect } = useAccount()
  if (!me) {
    return loading ? <Skeleton className="h-10 w-28 rounded-full sm:w-44" /> : null
  }
  const { ytmusic } = me

  if (ytmusic.connected) {
    return (
      <button
        type="button"
        onClick={openConnect}
        title="Gestionar la conexión con YouTube Music"
        className="flex h-10 max-w-[10.5rem] items-center gap-2 rounded-full border border-line bg-surface py-1 pr-3 pl-1 transition-colors duration-150 hover:border-line-strong sm:max-w-[16rem]"
      >
        <span className="relative">
          <Avatar src={ytmusic.account?.photo_url} name={ytmusic.account?.name} className="size-8" />
          <span className="absolute -right-0.5 -bottom-0.5 size-3 rounded-full border-2 border-canvas bg-ok" aria-hidden />
        </span>
        <span className="min-w-0 truncate text-sm font-medium">
          <span className="sr-only">YouTube Music conectado: </span>
          {ytmusic.account?.name ?? 'Conectado'}
        </span>
      </button>
    )
  }

  return (
    <Button
      variant={ytmusic.error ? 'secondary' : 'primary'}
      size="md"
      onClick={openConnect}
      icon={ytmusic.error ? <AlertTriangle className="size-4 text-warn" /> : <Link2 className="size-4" />}
      className="px-3 sm:px-4"
    >
      <span className="sm:hidden">{ytmusic.error ? 'Reconectar' : 'Conectar'}</span>
      <span className="hidden sm:inline">{ytmusic.error ? 'Reconectar YouTube Music' : 'Conectar YouTube Music'}</span>
    </Button>
  )
}

export function Header({ route }: { route: Route }) {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-canvas/75 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-5xl items-center gap-3 px-4 sm:px-6">
        <a href="#/" className="flex min-w-0 items-center gap-2.5 rounded-lg" aria-label={`${APP_NAME}: ir al inicio`}>
          <Logo className="size-9 shrink-0" />
          <span className="hidden truncate text-[17px] font-semibold tracking-tight min-[420px]:inline">{APP_NAME}</span>
        </a>
        <Nav current={route.name} className="ml-4 hidden sm:flex" />
        <div className="ml-auto flex items-center gap-2">
          <YtStatus />
          {SUPABASE_ENABLED && <UserMenu />}
        </div>
      </div>
      <Nav current={route.name} className="flex px-4 pb-2.5 sm:hidden" />
    </header>
  )
}
