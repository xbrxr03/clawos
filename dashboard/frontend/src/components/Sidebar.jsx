import { NavLink } from 'react-router-dom'

const NAV = [
  { to: '/',          label: 'Overview',  icon: <IconOverview /> },
  { to: '/tasks',     label: 'Tasks',     icon: <IconTasks />    },
  { to: '/approvals', label: 'Approvals', icon: <IconShield />   },
  { to: '/models',    label: 'Models',    icon: <IconCpu />      },
  { to: '/memory',    label: 'Memory',    icon: <IconDb />       },
  { to: '/audit',     label: 'Audit Log', icon: <IconLog />      },
]

export function Sidebar({ connected, services, approvalCount }) {
  const up    = Object.values(services).filter(s => s.status === 'up').length
  const total = Object.keys(services).length

  return (
    <aside style={{
      width: 'var(--sidebar-w)',
      flexShrink: 0,
      height: '100vh',
      display: 'flex',
      flexDirection: 'column',
      background: 'rgba(8,11,20,0.85)',
      backdropFilter: 'blur(20px)',
      borderRight: '1px solid var(--border)',
    }}>

      {/* Logo */}
      <div style={{ padding: '22px 20px 18px', borderBottom: '1px solid var(--sep)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 34, height: 34, borderRadius: 10,
            background: 'linear-gradient(135deg, #4f8ef7, #a78bfa)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexShrink: 0,
          }}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M8 2L14 5.5V10.5L8 14L2 10.5V5.5L8 2Z" stroke="white" strokeWidth="1.5" strokeLinejoin="round"/>
              <circle cx="8" cy="8" r="2" fill="white"/>
            </svg>
          </div>
          <div>
            <div style={{ fontSize: 15, fontWeight: 600, letterSpacing: '-0.2px' }}>ClawOS</div>
            <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 1 }}>agent runtime</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: '10px 10px', display: 'flex', flexDirection: 'column', gap: 1, overflowY: 'auto' }}>
        {NAV.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            style={({ isActive }) => ({
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '8px 10px',
              borderRadius: 10,
              textDecoration: 'none',
              color: isActive ? 'var(--blue)' : 'var(--text-2)',
              background: isActive ? 'var(--blue-dim)' : 'transparent',
              border: isActive ? '1px solid rgba(79,142,247,0.2)' : '1px solid transparent',
              fontSize: 13,
              fontWeight: isActive ? 500 : 400,
              transition: 'all 0.15s',
              position: 'relative',
            })}
          >
            {({ isActive }) => (
              <>
                <span style={{ opacity: isActive ? 1 : 0.6, display: 'flex' }}>{icon}</span>
                <span style={{ flex: 1 }}>{label}</span>
                {label === 'Approvals' && approvalCount > 0 && (
                  <span style={{
                    background: 'var(--red)',
                    color: '#fff',
                    fontSize: 10,
                    fontWeight: 700,
                    borderRadius: 10,
                    minWidth: 17,
                    height: 17,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: '0 5px',
                    boxShadow: '0 0 8px rgba(248,113,113,0.4)',
                  }}>
                    {approvalCount}
                  </span>
                )}
              </>
            )}
          </NavLink>
        ))}
      
      <a
        href="http://localhost:5180"
        target="_blank"
        rel="noopener noreferrer"
        style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '8px 16px', borderRadius: 8, margin: '2px 8px',
          cursor: 'pointer', color: '#2997FF', textDecoration: 'none',
          fontSize: 14, marginTop: 'auto', fontWeight: 400,
        }}
        title="Open Nexus Command (openclaw-office)"
      >
        ⬡ Nexus Command
      </a>
</nav>

      {/* Footer */}
      <div style={{
        padding: '12px 14px',
        borderTop: '1px solid var(--sep)',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
      }}>
        <div className={`dot ${connected ? 'green pulse' : 'red'}`} />
        <span style={{ fontSize: 12, color: 'var(--text-2)', flex: 1 }}>
          {connected ? 'Connected' : 'Reconnecting…'}
        </span>
        {total > 0 && (
          <span style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'JetBrains Mono, monospace' }}>
            {up}/{total} up
          </span>
        )}
      </div>
    </aside>
  )
}

function IconOverview() {
  return <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <rect x="1" y="1" width="5.5" height="5.5" rx="1.5" stroke="currentColor" strokeWidth="1.2"/>
    <rect x="8.5" y="1" width="5.5" height="5.5" rx="1.5" stroke="currentColor" strokeWidth="1.2"/>
    <rect x="1" y="8.5" width="5.5" height="5.5" rx="1.5" stroke="currentColor" strokeWidth="1.2"/>
    <rect x="8.5" y="8.5" width="5.5" height="5.5" rx="1.5" stroke="currentColor" strokeWidth="1.2"/>
  </svg>
}
function IconTasks() {
  return <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <path d="M2 4h11M2 7.5h11M2 11h7" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
  </svg>
}
function IconShield() {
  return <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <path d="M7.5 1.5L13 3.5V8c0 2.5-2.5 4.5-5.5 5.5C4.5 12.5 2 10.5 2 8V3.5L7.5 1.5Z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
    <path d="M5 7.5l1.5 1.5L10 6" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
}
function IconCpu() {
  return <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <rect x="3" y="3" width="9" height="9" rx="1.5" stroke="currentColor" strokeWidth="1.2"/>
    <rect x="5.5" y="5.5" width="4" height="4" rx="0.5" fill="currentColor" opacity="0.5"/>
    <path d="M5.5 1.5v1.5M9.5 1.5v1.5M5.5 12v1.5M9.5 12v1.5M1.5 5.5H3M1.5 9.5H3M12 5.5h1.5M12 9.5h1.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
  </svg>
}
function IconDb() {
  return <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <ellipse cx="7.5" cy="4" rx="5" ry="2" stroke="currentColor" strokeWidth="1.2"/>
    <path d="M2.5 4v3.5c0 1.1 2.24 2 5 2s5-.9 5-2V4" stroke="currentColor" strokeWidth="1.2"/>
    <path d="M2.5 7.5V11c0 1.1 2.24 2 5 2s5-.9 5-2V7.5" stroke="currentColor" strokeWidth="1.2"/>
  </svg>
}
function IconLog() {
  return <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <rect x="2" y="1.5" width="11" height="12" rx="1.5" stroke="currentColor" strokeWidth="1.2"/>
    <path d="M5 5h5M5 7.5h5M5 10h3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
  </svg>
}
