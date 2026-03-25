import { NavLink } from 'react-router-dom'
import { clsx } from 'clsx'
import {
  LayoutDashboard, ListTodo, ShieldAlert,
  Cpu, Database, BookOpen, Terminal, Wifi, WifiOff
} from 'lucide-react'

const NAV = [
  { to: '/',          icon: LayoutDashboard, label: 'Overview'   },
  { to: '/tasks',     icon: ListTodo,        label: 'Tasks'      },
  { to: '/approvals', icon: ShieldAlert,     label: 'Approvals'  },
  { to: '/models',    icon: Cpu,             label: 'Models'     },
  { to: '/memory',    icon: Database,        label: 'Memory'     },
  { to: '/audit',     icon: BookOpen,        label: 'Audit Log'  },
]

export function Sidebar({ connected, services, approvalCount }) {
  const upCount = Object.values(services).filter(s => s.status === 'up').length
  const totalCount = Object.keys(services).length

  return (
    <aside className="w-56 flex-shrink-0 bg-claw-surface border-r border-claw-border flex flex-col">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-claw-border">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded bg-claw-accent/10 border border-claw-accent/30 flex items-center justify-center">
            <Terminal size={14} className="text-claw-accent" />
          </div>
          <div>
            <div className="text-sm font-semibold text-claw-text tracking-tight">ClawOS</div>
            <div className="text-xs text-claw-dim font-mono">dashboard</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-3 space-y-0.5">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) => clsx(
              'flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors',
              isActive
                ? 'bg-claw-accent/10 text-claw-accent border border-claw-accent/20'
                : 'text-claw-dim hover:text-claw-text hover:bg-claw-muted'
            )}
          >
            {({ isActive }) => (
              <>
                <Icon size={15} strokeWidth={isActive ? 2 : 1.5} />
                <span>{label}</span>
                {label === 'Approvals' && approvalCount > 0 && (
                  <span className="ml-auto bg-amber-500 text-black text-xs font-bold w-5 h-5 rounded-full flex items-center justify-center">
                    {approvalCount}
                  </span>
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Connection status */}
      <div className="px-4 py-3 border-t border-claw-border">
        <div className="flex items-center gap-2 text-xs">
          {connected
            ? <Wifi size={12} className="text-claw-accent" />
            : <WifiOff size={12} className="text-claw-danger" />
          }
          <span className={connected ? 'text-claw-accent' : 'text-claw-danger'}>
            {connected ? 'live' : 'reconnecting...'}
          </span>
          {connected && totalCount > 0 && (
            <span className="ml-auto text-claw-dim font-mono">
              {upCount}/{totalCount}
            </span>
          )}
        </div>
      </div>
    </aside>
  )
}
