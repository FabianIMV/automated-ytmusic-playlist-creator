import { AlertTriangle, CheckCircle2, Info, LoaderCircle, Music2, XCircle } from 'lucide-react'
import { useState, type ButtonHTMLAttributes, type ReactNode } from 'react'

/* ---------- Botones ---------- */

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
export type ButtonSize = 'sm' | 'md' | 'lg'

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary:
    'text-on-accent bg-[linear-gradient(135deg,#e0325a,#b5207a)] shadow-[0_10px_28px_-10px_rgb(224_50_90/0.75)] hover:brightness-110',
  secondary: 'bg-surface-2 text-fg border border-line-strong hover:border-fg/40',
  ghost: 'text-muted hover:text-fg hover:bg-surface-2',
  danger: 'text-bad border border-bad/35 bg-bad/10 hover:bg-bad/15',
}

const BUTTON_SIZES: Record<ButtonSize, string> = {
  sm: 'h-9 px-3 text-[13px]',
  md: 'h-10 px-4 text-sm',
  lg: 'h-12 px-6 text-[15px]',
}

/** Clases de botón, reutilizables en enlaces (<a>) con aspecto de botón. */
export function buttonClass(variant: ButtonVariant = 'secondary', size: ButtonSize = 'md', extra = ''): string {
  return [
    'inline-flex shrink-0 items-center justify-center gap-2 rounded-xl font-semibold whitespace-nowrap select-none',
    'transition duration-150 ease-out active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50',
    BUTTON_VARIANTS[variant],
    BUTTON_SIZES[size],
    extra,
  ].join(' ')
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
  icon?: ReactNode
}

export function Button({
  variant = 'secondary',
  size = 'md',
  loading = false,
  icon,
  className = '',
  children,
  disabled,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={buttonClass(variant, size, className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? <Spinner className="size-4" /> : icon}
      {children}
    </button>
  )
}

export function Spinner({ className = 'size-4' }: { className?: string }) {
  return <LoaderCircle className={`${className} animate-spin`} aria-hidden />
}

/* ---------- Avisos y etiquetas ---------- */

export type Tone = 'ok' | 'warn' | 'bad' | 'info' | 'accent' | 'neutral'

const TONE_BOX: Record<Tone, string> = {
  ok: 'border-ok/30 bg-ok/10 text-ok',
  warn: 'border-warn/35 bg-warn/10 text-warn',
  bad: 'border-bad/35 bg-bad/10 text-bad',
  info: 'border-info/30 bg-info/10 text-info',
  accent: 'border-accent/35 bg-accent/10 text-accent-text',
  neutral: 'border-line bg-surface-2 text-muted',
}

export const TONE_TEXT: Record<Tone, string> = {
  ok: 'text-ok',
  warn: 'text-warn',
  bad: 'text-bad',
  info: 'text-info',
  accent: 'text-accent-text',
  neutral: 'text-muted',
}

export const TONE_BUBBLE: Record<Tone, string> = {
  ok: 'bg-ok/12 text-ok',
  warn: 'bg-warn/12 text-warn',
  bad: 'bg-bad/12 text-bad',
  info: 'bg-info/12 text-info',
  accent: 'bg-accent/15 text-accent-text',
  neutral: 'bg-surface-2 text-muted',
}

export function Badge({ tone = 'neutral', icon, children }: { tone?: Tone; icon?: ReactNode; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap ${TONE_BOX[tone]}`}
    >
      {icon}
      {children}
    </span>
  )
}

const NOTICE_ICONS: Record<Exclude<Tone, 'accent' | 'neutral'>, ReactNode> = {
  ok: <CheckCircle2 className="size-5" aria-hidden />,
  warn: <AlertTriangle className="size-5" aria-hidden />,
  bad: <XCircle className="size-5" aria-hidden />,
  info: <Info className="size-5" aria-hidden />,
}

interface NoticeProps {
  tone?: Exclude<Tone, 'accent' | 'neutral'>
  title?: string
  children?: ReactNode
  action?: ReactNode
  className?: string
}

export function Notice({ tone = 'info', title, children, action, className = '' }: NoticeProps) {
  return (
    <div
      role={tone === 'bad' || tone === 'warn' ? 'alert' : 'status'}
      className={`flex items-start gap-3 rounded-xl border px-4 py-3 text-sm ${TONE_BOX[tone]} ${className}`}
    >
      <span className="mt-0.5 shrink-0">{NOTICE_ICONS[tone]}</span>
      <div className="min-w-0 flex-1">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={`text-fg/90 ${title ? 'mt-0.5' : ''} break-words`}>{children}</div>}
      </div>
      {action && <div className="shrink-0 self-center">{action}</div>}
    </div>
  )
}

/* ---------- Imágenes ---------- */

export function Avatar({ src, name, className = 'size-8' }: { src?: string | null; name?: string | null; className?: string }) {
  const [failedSrc, setFailedSrc] = useState<string | null>(null)
  const initial = (name ?? '?').trim().charAt(0).toUpperCase() || '?'
  if (!src || failedSrc === src) {
    return (
      <span
        className={`${className} grid shrink-0 place-items-center rounded-full bg-[linear-gradient(135deg,#e0325a,#7a2bb5)] text-xs font-semibold text-white`}
        aria-hidden
      >
        {initial}
      </span>
    )
  }
  return (
    <img
      src={src}
      alt=""
      referrerPolicy="no-referrer"
      onError={() => setFailedSrc(src)}
      className={`${className} shrink-0 rounded-full bg-surface-2 object-cover`}
    />
  )
}

/** Miniatura de canción con respaldo si no hay imagen o falla la carga. */
export function Thumb({ src, className = 'size-10' }: { src?: string | null; className?: string }) {
  const [failedSrc, setFailedSrc] = useState<string | null>(null)
  if (!src || failedSrc === src) {
    return (
      <span className={`${className} grid shrink-0 place-items-center rounded-lg bg-surface-2 text-faint`} aria-hidden>
        <Music2 className="size-4" />
      </span>
    )
  }
  return (
    <img
      src={src}
      alt=""
      loading="lazy"
      referrerPolicy="no-referrer"
      onError={() => setFailedSrc(src)}
      className={`${className} shrink-0 rounded-lg bg-surface-2 object-cover`}
    />
  )
}

export function Logo({ className = 'size-9' }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden>
      <defs>
        <linearGradient id="logo-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#ff6b4a" />
          <stop offset="1" stopColor="#c0267f" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="16" fill="url(#logo-g)" />
      <path
        d="M26 41V19l17-4v22"
        fill="none"
        stroke="#fff"
        strokeWidth="4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="21" cy="42" r="6" fill="#fff" />
      <circle cx="38" cy="38" r="6" fill="#fff" />
    </svg>
  )
}

/* ---------- Formularios ---------- */

interface SegmentedOption<T extends string> {
  value: T
  label: string
  icon?: ReactNode
}

interface SegmentedProps<T extends string> {
  name: string
  label: string
  value: T
  onChange: (value: T) => void
  options: SegmentedOption<T>[]
  disabled?: boolean
}

/** Control segmentado accesible (radios nativos). */
export function Segmented<T extends string>({ name, label, value, onChange, options, disabled }: SegmentedProps<T>) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className={`grid grid-flow-col auto-cols-fr gap-1 rounded-xl border border-line bg-surface p-1 ${disabled ? 'opacity-55' : ''}`}
    >
      {options.map((opt) => (
        <label
          key={opt.value}
          className={[
            'flex min-h-9 items-center justify-center gap-1.5 rounded-lg border border-transparent px-2 py-1.5 text-[13px] font-medium text-muted',
            'transition-colors duration-150 hover:text-fg',
            'has-checked:border-accent/45 has-checked:bg-accent/15 has-checked:text-accent-text',
            'has-focus-visible:ring-2 has-focus-visible:ring-accent-text',
            disabled ? 'cursor-not-allowed' : 'cursor-pointer',
          ].join(' ')}
        >
          <input
            type="radio"
            name={name}
            value={opt.value}
            checked={value === opt.value}
            disabled={disabled}
            onChange={() => onChange(opt.value)}
            className="sr-only"
          />
          {opt.icon && <span className="hidden min-[400px]:inline-flex">{opt.icon}</span>}
          <span className="whitespace-nowrap">{opt.label}</span>
        </label>
      ))}
    </div>
  )
}

interface SwitchProps {
  checked: boolean
  onChange: (checked: boolean) => void
  label: string
  description?: string
}

export function Switch({ checked, onChange, label, description }: SwitchProps) {
  return (
    <label className="flex cursor-pointer items-start gap-3">
      <input
        type="checkbox"
        role="switch"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="peer sr-only"
      />
      <span
        aria-hidden
        className="relative mt-0.5 h-6 w-10 shrink-0 rounded-full border border-line-strong bg-surface-2 transition-colors duration-150 after:absolute after:top-0.5 after:left-0.5 after:size-4.5 after:rounded-full after:bg-fg/80 after:transition-transform after:duration-150 peer-checked:border-accent peer-checked:bg-accent peer-checked:after:translate-x-4 peer-checked:after:bg-white peer-focus-visible:ring-2 peer-focus-visible:ring-accent-text peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-canvas"
      />
      <span className="min-w-0">
        <span className="block text-sm font-medium text-fg">{label}</span>
        {description && <span className="block text-[13px] text-muted">{description}</span>}
      </span>
    </label>
  )
}

export function FieldLabel({ htmlFor, children, hint }: { htmlFor?: string; children: ReactNode; hint?: ReactNode }) {
  return (
    <div className="mb-1.5 flex items-baseline justify-between gap-3">
      <label htmlFor={htmlFor} className="text-[13px] font-semibold text-fg">
        {children}
      </label>
      {hint && <span className="text-xs text-faint">{hint}</span>}
    </div>
  )
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`animate-skeleton rounded-lg bg-surface-2 ${className}`} aria-hidden />
}
