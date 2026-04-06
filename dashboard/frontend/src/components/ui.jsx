export function StatusDot({ status, size = 7 }) {
  const cls = {
    up: 'green', running: 'green', active: 'green',
    degraded: 'orange', pending: 'orange', queued: 'blue',
    down: 'red', failed: 'red',
    completed: 'gray',
  }[status] ?? 'gray'

  const pulse = ['up','running','active'].includes(status)

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
    <div className={`glass ${className}`} style={style} {...props}>
      {children}
    </div>
  )
}

export function SectionLabel({ children }) {
  return <div className="section-label">{children}</div>
}

export function StatCard({ label, value, unit, color }) {
  return (
    <div className="stat-card">
      <div className="stat-val" style={color ? { color } : {}}>
        {value ?? '—'}
        {unit && <span className="stat-unit">{unit}</span>}
      </div>
      <div className="stat-label">{label}</div>
    </div>
  )
}

export function Empty({ children }) {
  return (
    <div className="empty">
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1">
        <circle cx="12" cy="12" r="10"/>
        <path d="M8 12h8M12 8v8" opacity="0.4"/>
      </svg>
      {children}
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
          <path d="M1 1l4 4.5L1 10" stroke="var(--text-3)" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      )}
    </div>
  )
}
