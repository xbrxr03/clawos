import type { PropsWithChildren, ReactNode } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { appNav } from './navigation'

type AppShellProps = PropsWithChildren<{
  connected: boolean
  services: Record<string, any>
  approvals: any[]
  events: any[]
  inspector?: ReactNode
  theme: 'dark' | 'light'
  onToggleTheme: () => void
}>

export function AppShell({
  children,
  connected,
  services,
  approvals,
  events,
  inspector,
  theme,
  onToggleTheme,
}: AppShellProps) {
  const location = useLocation()
  const serviceList = Object.values(services || {})
  const upCount = serviceList.filter((item: any) => item.status === 'up' || item.status === 'running').length
  const title = appNav.find((item) => item.to === location.pathname)?.label ?? 'ClawOS'

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', padding: 16, gap: 16 }}>
      <aside
        style={{
          width: 'var(--sidebar-w)',
          flexShrink: 0,
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--border)',
          background: 'linear-gradient(180deg, rgba(8,12,20,0.82), rgba(14,20,32,0.9))',
          boxShadow: 'var(--shadow-window)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        <div style={{ padding: 24, borderBottom: '1px solid var(--sep)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 14,
                background: 'linear-gradient(135deg, rgba(77,143,247,0.95), rgba(88,210,212,0.95))',
                display: 'grid',
                placeItems: 'center',
                color: '#fff',
                boxShadow: '0 14px 30px rgba(77,143,247,0.25)',
              }}
            >
              <svg width="18" height="18" viewBox="0 0 16 16" fill="none">
                <path d="M8 2.1 13.25 5v5.97L8 13.9 2.75 10.97V5L8 2.1Z" stroke="white" strokeWidth="1.2" strokeLinejoin="round" />
                <circle cx="8" cy="8" r="2.1" fill="white" />
              </svg>
            </div>
            <div>
              <div style={{ fontSize: 16, fontWeight: 700, letterSpacing: '-0.02em' }}>ClawOS</div>
              <div style={{ fontSize: 12, color: 'var(--text-3)' }}>Nexus Command Center</div>
            </div>
          </div>
        </div>

        <div style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 6 }}>
          {appNav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: '12px 14px',
                borderRadius: 14,
                textDecoration: 'none',
                color: isActive ? 'var(--text)' : 'var(--text-2)',
                background: isActive ? 'linear-gradient(180deg, rgba(77,143,247,0.18), rgba(77,143,247,0.08))' : 'transparent',
                border: isActive ? '1px solid rgba(77,143,247,0.2)' : '1px solid transparent',
              })}
            >
              {item.icon}
              <span style={{ flex: 1, fontWeight: 500 }}>{item.label}</span>
              {item.label === 'Approvals' && approvals.length > 0 && (
                <span className="pill red">{approvals.length}</span>
              )}
            </NavLink>
          ))}
        </div>

        <div style={{ marginTop: 'auto', padding: 18, borderTop: '1px solid var(--sep)' }}>
          <div
            style={{
              borderRadius: 16,
              padding: 14,
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid var(--border)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className={`dot ${connected ? 'green pulse' : 'red'}`} />
              <span style={{ fontSize: 12, color: 'var(--text-2)' }}>
                {connected ? 'Nexus connected' : 'Reconnecting'}
              </span>
            </div>
            <div style={{ marginTop: 10, fontSize: 12, color: 'var(--text-3)' }}>
              {upCount}/{serviceList.length || 0} services healthy
            </div>
            <div style={{ marginTop: 10, display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-3)' }}>
              <span>{events.length} recent events</span>
              <button
                type="button"
                onClick={onToggleTheme}
                style={{ border: 'none', background: 'transparent', color: 'var(--blue)', cursor: 'pointer', padding: 0 }}
              >
                {theme === 'dark' ? 'Light Mode' : 'Dark Mode'}
              </button>
            </div>
          </div>
        </div>
      </aside>

      <section
        style={{
          flex: 1,
          minWidth: 0,
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--border)',
          background: 'var(--panel)',
          boxShadow: 'var(--shadow-window)',
          display: 'flex',
          overflow: 'hidden',
          backdropFilter: 'blur(var(--blur-panel))',
        }}
      >
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
          <header
            style={{
              minHeight: 'var(--toolbar-h)',
              borderBottom: '1px solid var(--sep)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '0 24px',
              background: 'linear-gradient(180deg, rgba(255,255,255,0.02), transparent)',
            }}
          >
            <div>
              <div style={{ fontSize: 21, fontWeight: 700, letterSpacing: '-0.03em' }}>{title}</div>
              <div style={{ fontSize: 12, color: 'var(--text-3)' }}>Calm, conversational operations with Nexus</div>
            </div>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: 6,
                borderRadius: 14,
                background: 'var(--surface-2)',
                border: '1px solid var(--border)',
                minWidth: 290,
              }}
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ color: 'var(--text-3)' }}>
                <circle cx="7.25" cy="7.25" r="4.75" stroke="currentColor" strokeWidth="1.2" />
                <path d="m10.75 10.75 2.75 2.75" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
              </svg>
              <span style={{ fontSize: 12, color: 'var(--text-3)' }}>Ask Nexus, search missions, approvals</span>
            </div>
          </header>

          <div style={{ flex: 1, overflow: 'auto' }}>{children}</div>
        </div>

        {inspector && (
          <aside
            style={{
              width: 'var(--inspector-w)',
              flexShrink: 0,
              borderLeft: '1px solid var(--sep)',
              background: 'rgba(255,255,255,0.02)',
            }}
          >
            {inspector}
          </aside>
        )}
      </section>
    </div>
  )
}
