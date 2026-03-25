import { clsx } from 'clsx'

// ── App Icon wrapper ───────────────────────────────────────────────────────────
export function AppIcon({ color = '#0a84ff', children, size = 36 }) {
  return (
    <div
      className="flex items-center justify-center rounded-[10px] flex-shrink-0"
      style={{ width: size, height: size, background: color }}
    >
      {children}
    </div>
  )
}

// ── Section label (above grouped list) ────────────────────────────────────────
export function SectionLabel({ children }) {
  return (
    <div className="px-4 pb-1 pt-5 text-xs font-semibold uppercase tracking-wider"
      style={{ color: 'rgba(255,255,255,0.4)' }}>
      {children}
    </div>
  )
}

// ── iOS grouped card ───────────────────────────────────────────────────────────
export function Card({ children, className }) {
  return (
    <div className={clsx('ios-card', className)}>
      {children}
    </div>
  )
}

// ── Row inside a card ──────────────────────────────────────────────────────────
export function Row({ left, center, right, onClick, chevron = false }) {
  return (
    <div
      className={clsx('ios-row', onClick && 'cursor-pointer active:opacity-60')}
      onClick={onClick}
    >
      {left && <div className="flex-shrink-0">{left}</div>}
      <div className="flex-1 min-w-0">{center}</div>
      {right && <div className="flex-shrink-0 flex items-center gap-1">{right}</div>}
      {chevron && (
        <svg width="8" height="13" viewBox="0 0 8 13" fill="none">
          <path d="M1 1l6 5.5L1 12" stroke="rgba(255,255,255,0.3)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      )}
    </div>
  )
}

// ── Status dot ────────────────────────────────────────────────────────────────
export function Dot({ status }) {
  const color = {
    up:       '#30d158',
    active:   '#30d158',
    running:  '#30d158',
    degraded: '#ff9f0a',
    pending:  '#ff9f0a',
    queued:   '#0a84ff',
    down:     '#ff453a',
    failed:   '#ff453a',
    completed:'rgba(255,255,255,0.3)',
  }[status] ?? 'rgba(255,255,255,0.3)'

  const shouldPulse = ['up','active','running'].includes(status)

  return (
    <div
      className={clsx('rounded-full flex-shrink-0', shouldPulse && 'pulse')}
      style={{ width: 8, height: 8, background: color }}
    />
  )
}

// ── iOS badge ──────────────────────────────────────────────────────────────────
export function Badge({ children, color = '#0a84ff' }) {
  return (
    <span
      className="ios-badge"
      style={{ background: `${color}22`, color }}
    >
      {children}
    </span>
  )
}

// ── iOS button ─────────────────────────────────────────────────────────────────
export function Button({ children, onClick, color = '#0a84ff', variant = 'fill', disabled, size = 'sm' }) {
  const pad = size === 'sm' ? 'px-4 py-1.5 text-sm' : 'px-5 py-2.5 text-base'
  const style = variant === 'fill'
    ? { background: color, color: '#fff' }
    : { background: `${color}18`, color }

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={clsx(
        'rounded-[10px] font-semibold transition-opacity active:opacity-60',
        pad,
        disabled && 'opacity-30 cursor-not-allowed'
      )}
      style={style}
    >
      {children}
    </button>
  )
}

// ── Large number stat ──────────────────────────────────────────────────────────
export function Stat({ value, label, color = '#ffffff' }) {
  return (
    <div className="text-center">
      <div className="text-3xl font-bold tabular" style={{ color }}>{value ?? '—'}</div>
      <div className="text-xs mt-0.5" style={{ color: 'rgba(255,255,255,0.4)' }}>{label}</div>
    </div>
  )
}

// ── Empty state ────────────────────────────────────────────────────────────────
export function Empty({ icon, message }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 gap-3">
      {icon && <div className="text-4xl opacity-20">{icon}</div>}
      <div className="text-sm" style={{ color: 'rgba(255,255,255,0.3)' }}>{message}</div>
    </div>
  )
}

// ── Time ──────────────────────────────────────────────────────────────────────
export function Time({ value }) {
  if (!value) return null
  const d = new Date(typeof value === 'number' && value < 1e12 ? value * 1000 : value)
  return (
    <span className="text-xs tabular" style={{ color: 'rgba(255,255,255,0.3)' }}>
      {d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
    </span>
  )
}

// ── Progress bar ───────────────────────────────────────────────────────────────
export function ProgressBar({ value, color = '#0a84ff' }) {
  return (
    <div className="h-1 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.08)' }}>
      <div
        className="h-full rounded-full transition-all duration-300"
        style={{ width: `${Math.min(100, value)}%`, background: color }}
      />
    </div>
  )
}
