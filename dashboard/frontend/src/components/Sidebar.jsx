import { NavLink } from 'react-router-dom'
import { clsx } from 'clsx'

const TABS = [
  { to: '/',          emoji: '􀟶', sf: '⬡',  label: 'Overview'  },
  { to: '/tasks',     emoji: '􀏖', sf: '≡',   label: 'Tasks'     },
  { to: '/approvals', emoji: '􀉻', sf: '⚠',   label: 'Approvals' },
  { to: '/models',    emoji: '􀧘', sf: '⬡',   label: 'Models'    },
  { to: '/memory',    emoji: '􀖆', sf: '◈',   label: 'Memory'    },
  { to: '/audit',     emoji: '􀒗', sf: '≣',   label: 'Audit'     },
]

// SF Symbol approximations using unicode
const ICONS = {
  '/':          () => <GridIcon />,
  '/tasks':     () => <ListIcon />,
  '/approvals': () => <ShieldIcon />,
  '/models':    () => <ChipIcon />,
  '/memory':    () => <DbIcon />,
  '/audit':     () => <LogIcon />,
}

export function Sidebar({ connected, approvalCount }) {
  return (
    <aside
      className="w-64 flex-shrink-0 flex flex-col h-screen"
      style={{ background: '#111113', borderRight: '1px solid rgba(255,255,255,0.06)' }}
    >
      {/* Header */}
      <div className="px-5 pt-8 pb-6">
        <div className="flex items-center gap-3">
          <div
            className="w-9 h-9 rounded-[10px] flex items-center justify-center text-white font-bold text-base"
            style={{ background: 'linear-gradient(135deg, #0a84ff, #bf5af2)' }}
          >
            ✦
          </div>
          <div>
            <div className="text-base font-semibold tracking-tight">ClawOS</div>
            <div className="flex items-center gap-1.5 mt-0.5">
              <div
                className={clsx('w-1.5 h-1.5 rounded-full', connected ? 'pulse' : '')}
                style={{ background: connected ? '#30d158' : '#ff453a' }}
              />
              <span className="text-xs" style={{ color: 'rgba(255,255,255,0.4)' }}>
                {connected ? 'live' : 'offline'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 space-y-0.5">
        {TABS.map(({ to, label }) => {
          const Icon = ICONS[to]
          return (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) => clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded-[10px] transition-all text-sm font-medium',
                isActive
                  ? 'text-white'
                  : 'text-white/40 hover:text-white/70 hover:bg-white/5'
              )}
              style={({ isActive }) => isActive ? { background: 'rgba(255,255,255,0.1)' } : {}}
            >
              {({ isActive }) => (
                <>
                  <span style={{ color: isActive ? '#0a84ff' : 'rgba(255,255,255,0.35)', fontSize: 16 }}>
                    <Icon />
                  </span>
                  <span>{label}</span>
                  {label === 'Approvals' && approvalCount > 0 && (
                    <span
                      className="ml-auto text-xs font-bold w-5 h-5 rounded-full flex items-center justify-center"
                      style={{ background: '#ff453a', color: '#fff', fontSize: 11 }}
                    >
                      {approvalCount}
                    </span>
                  )}
                </>
              )}
            </NavLink>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="px-5 py-5 border-t" style={{ borderColor: 'rgba(255,255,255,0.06)' }}>
        <div className="text-xs" style={{ color: 'rgba(255,255,255,0.2)' }}>
          github.com/xbrxr03/clawos
        </div>
      </div>
    </aside>
  )
}

// Inline SVG icons matching SF Symbols style
function GridIcon() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><rect x="1" y="1" width="6" height="6" rx="1.5"/><rect x="9" y="1" width="6" height="6" rx="1.5"/><rect x="1" y="9" width="6" height="6" rx="1.5"/><rect x="9" y="9" width="6" height="6" rx="1.5"/></svg>
}
function ListIcon() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><line x1="5" y1="4" x2="14" y2="4"/><line x1="5" y1="8" x2="14" y2="8"/><line x1="5" y1="12" x2="14" y2="12"/><circle cx="2" cy="4" r="1" fill="currentColor" stroke="none"/><circle cx="2" cy="8" r="1" fill="currentColor" stroke="none"/><circle cx="2" cy="12" r="1" fill="currentColor" stroke="none"/></svg>
}
function ShieldIcon() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M8 1.5L2 4v4c0 3 2.5 5.5 6 6 3.5-.5 6-3 6-6V4L8 1.5z"/></svg>
}
function ChipIcon() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><rect x="4" y="4" width="8" height="8" rx="1.5"/><line x1="6" y1="1" x2="6" y2="4"/><line x1="10" y1="1" x2="10" y2="4"/><line x1="6" y1="12" x2="6" y2="15"/><line x1="10" y1="12" x2="10" y2="15"/><line x1="1" y1="6" x2="4" y2="6"/><line x1="1" y1="10" x2="4" y2="10"/><line x1="12" y1="6" x2="15" y2="6"/><line x1="12" y1="10" x2="15" y2="10"/></svg>
}
function DbIcon() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><ellipse cx="8" cy="4" rx="5" ry="2"/><path d="M3 4v4c0 1.1 2.24 2 5 2s5-.9 5-2V4"/><path d="M3 8v4c0 1.1 2.24 2 5 2s5-.9 5-2V8"/></svg>
}
function LogIcon() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><rect x="2" y="2" width="12" height="12" rx="2"/><line x1="5" y1="6" x2="11" y2="6"/><line x1="5" y1="9" x2="11" y2="9"/><line x1="5" y1="12" x2="8" y2="12"/></svg>
}
