import { clsx } from 'clsx'

// ── Status dot ─────────────────────────────────────────────────────────────────
export function StatusDot({ status }) {
  const color = {
    up:       'bg-claw-accent',
    running:  'bg-claw-accent',
    active:   'bg-claw-accent',
    degraded: 'bg-claw-warn',
    pending:  'bg-claw-warn',
    queued:   'bg-claw-info',
    down:     'bg-claw-danger',
    failed:   'bg-claw-danger',
    completed:'bg-claw-dim',
  }[status] ?? 'bg-claw-dim'

  const pulse = ['up', 'running', 'active'].includes(status)

  return (
    <span className={clsx(
      'inline-block w-2 h-2 rounded-full flex-shrink-0',
      color,
      pulse && 'pulse'
    )} />
  )
}

// ── Badge ──────────────────────────────────────────────────────────────────────
export function Badge({ children, variant = 'default' }) {
  const styles = {
    default:   'bg-claw-muted text-claw-dim',
    accent:    'bg-claw-accent/10 text-claw-accent border border-claw-accent/20',
    warn:      'bg-amber-500/10 text-amber-400 border border-amber-500/20',
    danger:    'bg-red-500/10 text-red-400 border border-red-500/20',
    info:      'bg-blue-500/10 text-blue-400 border border-blue-500/20',
    completed: 'bg-claw-muted/50 text-claw-dim',
  }
  return (
    <span className={clsx('px-2 py-0.5 rounded text-xs font-mono font-medium', styles[variant])}>
      {children}
    </span>
  )
}

// ── Card ───────────────────────────────────────────────────────────────────────
export function Card({ children, className }) {
  return (
    <div className={clsx(
      'bg-claw-surface border border-claw-border rounded-lg',
      className
    )}>
      {children}
    </div>
  )
}

// ── Section header ─────────────────────────────────────────────────────────────
export function SectionHeader({ title, count, action }) {
  return (
    <div className="flex items-center justify-between px-4 py-3 border-b border-claw-border">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-claw-text">{title}</span>
        {count !== undefined && (
          <span className="text-xs font-mono text-claw-dim bg-claw-muted px-1.5 py-0.5 rounded">
            {count}
          </span>
        )}
      </div>
      {action}
    </div>
  )
}

// ── Button ─────────────────────────────────────────────────────────────────────
export function Button({ children, onClick, variant = 'default', size = 'sm', disabled }) {
  const base = 'inline-flex items-center gap-1.5 font-medium rounded transition-colors disabled:opacity-40 disabled:cursor-not-allowed'
  const sizes = { sm: 'px-3 py-1.5 text-xs', md: 'px-4 py-2 text-sm' }
  const variants = {
    default: 'bg-claw-muted text-claw-text hover:bg-claw-border',
    accent:  'bg-claw-accent text-claw-bg hover:bg-claw-accent/90',
    danger:  'bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20',
    ghost:   'text-claw-dim hover:text-claw-text hover:bg-claw-muted',
  }
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={clsx(base, sizes[size], variants[variant])}
    >
      {children}
    </button>
  )
}

// ── Empty state ────────────────────────────────────────────────────────────────
export function Empty({ icon: Icon, message }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 gap-3 text-claw-dim">
      {Icon && <Icon size={24} strokeWidth={1.5} />}
      <span className="text-sm">{message}</span>
    </div>
  )
}

// ── Timestamp ──────────────────────────────────────────────────────────────────
export function Timestamp({ value }) {
  if (!value) return null
  const d = new Date(typeof value === 'number' && value < 1e12 ? value * 1000 : value)
  return (
    <span className="font-mono text-xs text-claw-dim">
      {d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
    </span>
  )
}
