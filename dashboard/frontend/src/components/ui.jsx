/* SPDX-License-Identifier: AGPL-3.0-or-later */
export function StatusDot({ status, size = 7 }) {
  const cls = {
    up: 'green', running: 'green', active: 'green',
    degraded: 'orange', pending: 'orange', queued: 'blue',
    down: 'red', failed: 'red',
    completed: 'gray',
  }[status] ?? 'gray'

  const pulse = ['up', 'running', 'active'].includes(status)

  return (
    <span
      className={`dot ${cls}${pulse ? ' pulse' : ''}`}
      style={{ width: size, height: size }}
    />
  )
}

export function Badge({ children, color = 'gray' }) {
  return <span className={`pill ${color}`}>{children}</span>
}

export function Card({ children, style = undefined, className = '', ...props }) {
  return (
    <div className={`glass surface-card ${className}`.trim()} style={style} {...props}>
      {children}
    </div>
  )
}

export function SectionLabel({ children }) {
  return <div className="section-label">{children}</div>
}

export function PageHeader({ eyebrow = 'Command Center', title, description, meta = null, actions = null }) {
  return (
    <div className="page-header">
      <div className="page-header-main">
        <div className="page-eyebrow">{eyebrow}</div>
        <div className="page-title">{title}</div>
        {description ? <div className="page-description">{description}</div> : null}
      </div>
      {(meta || actions) && (
        <div className="page-header-side">
          {meta ? <div className="page-meta">{meta}</div> : null}
          {actions ? <div className="page-actions">{actions}</div> : null}
        </div>
      )}
    </div>
  )
}

export function PanelHeader({ eyebrow, title, description, aside = null }) {
  return (
    <div className="panel-header">
      <div>
        {eyebrow ? <div className="section-label">{eyebrow}</div> : null}
        <div className="panel-title">{title}</div>
        {description ? <div className="panel-description">{description}</div> : null}
      </div>
      {aside ? <div>{aside}</div> : null}
    </div>
  )
}

export function StatCard({ label, value, unit, color }) {
  return (
    <div className="stat-card">
      <div className="stat-val" style={color ? { color } : {}}>
        {value ?? '-'}
        {unit && <span className="stat-unit">{unit}</span>}
      </div>
      <div className="stat-label">{label}</div>
    </div>
  )
}

export function Empty({ children }) {
  const isPrimitive = typeof children === 'string' || typeof children === 'number'
  const title = isPrimitive ? String(children) : 'Nothing to show yet'
  const body = isPrimitive
    ? 'ClawOS will fill this surface as soon as it has something meaningful to show.'
    : children

  return (
    <div className="empty">
      <div className="empty-visual">
        <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.1">
          <circle cx="12" cy="12" r="9.5" />
          <path d="M8.75 12h6.5M12 8.75v6.5" opacity="0.42" strokeLinecap="round" />
        </svg>
      </div>
      <div className="empty-title">{title}</div>
      <div className="empty-body">{body}</div>
    </div>
  )
}

export function Skeleton({ width = '100%', height = 12, radius = 999, style = undefined, className = '' }) {
  return (
    <span
      className={`skeleton ${className}`.trim()}
      style={{ width, height, borderRadius: radius, ...style }}
    />
  )
}

export function SkeletonText({ lines = 3 }) {
  return (
    <div className="skeleton-stack">
      {Array.from({ length: lines }).map((_, index) => (
        <Skeleton key={index} width={index === lines - 1 ? '68%' : '100%'} height={12} />
      ))}
    </div>
  )
}

export function LoadingPanel({
  eyebrow = 'Loading',
  title = 'Preparing this surface',
  body = 'ClawOS is warming up the current workspace and collecting the latest state.',
}) {
  return (
    <div className="loading-panel">
      <div className="page-eyebrow">{eyebrow}</div>
      <div className="page-title" style={{ fontSize: 30 }}>{title}</div>
      <div className="page-description" style={{ maxWidth: 520 }}>{body}</div>
      <div className="loading-panel-grid">
        <Card style={{ padding: 18 }}>
          <Skeleton width="44%" height={12} />
          <div style={{ height: 14 }} />
          <Skeleton width="100%" height={18} radius={14} />
          <div style={{ height: 10 }} />
          <SkeletonText lines={4} />
        </Card>
        <Card style={{ padding: 18 }}>
          <Skeleton width="36%" height={12} />
          <div style={{ height: 14 }} />
          <Skeleton width="72%" height={18} radius={14} />
          <div style={{ height: 10 }} />
          <SkeletonText lines={5} />
        </Card>
      </div>
    </div>
  )
}

export function Ts({ value }) {
  if (!value) return null
  const d = new Date(typeof value === 'number' && value < 1e12 ? value * 1000 : value)
  return (
    <span className="ts">
      {d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
    </span>
  )
}

export function Btn({ children, onClick, variant = 'default', size, disabled }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`btn${variant !== 'default' ? ` ${variant}` : ''}${size === 'sm' ? ' sm' : ''}`}
    >
      {children}
    </button>
  )
}

export function Row({ left, center, right, onClick, chevron }) {
  return (
    <div className={`row${onClick ? ' clickable' : ''}`} onClick={onClick}>
      {left}
      <div style={{ flex: 1, minWidth: 0 }}>{center}</div>
      {right && <div style={{ flexShrink: 0, color: 'var(--text-2)', fontSize: 13 }}>{right}</div>}
      {chevron && (
        <svg width="6" height="11" viewBox="0 0 6 11" fill="none" style={{ flexShrink: 0 }}>
          <path d="M1 1l4 4.5L1 10" stroke="var(--text-3)" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      )}
    </div>
  )
}

export function ShortcutKey({ children }) {
  return <kbd className="shortcut-key">{children}</kbd>
}
