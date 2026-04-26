/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { type PropsWithChildren, useEffect, useMemo, useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { appNav } from './navigation'
import { ShortcutKey } from '../components/ui.jsx'
import { desktopBridge } from '../desktop/bridge'
import { commandCenterApi } from '../lib/commandCenterApi'

type AppShellProps = PropsWithChildren<{
  connected: boolean
  services: Record<string, any>
  approvals: any[]
  events: any[]
  voiceSession?: Record<string, any>
  jarvisSession?: Record<string, any>
  inspector?: React.ReactNode
  theme: 'dark' | 'light'
  onToggleTheme: () => void
}>

// Nav items with glyph chars + route groups matching the design
const NAV_GROUPS: { title: string; items: { to: string; glyph: string; label: string; badge?: 'approvals' }[] }[] = [
  {
    title: 'Assistant',
    items: [
      { to: '/',          glyph: '◈', label: 'Overview' },
      { to: '/briefing',  glyph: '☀', label: 'Briefing' },
      { to: '/jarvis',    glyph: '◉', label: 'Jarvis' },
    ],
  },
  {
    title: 'Agents',
    items: [
      { to: '/workflows',  glyph: '▤', label: 'Workflows' },
      { to: '/brain',      glyph: '❋', label: 'Brain' },
      { to: '/memory',     glyph: '▦', label: 'Memory' },
      { to: '/approvals',  glyph: '▢', label: 'Approvals', badge: 'approvals' },
      { to: '/packs',      glyph: '✦', label: 'Store' },
      { to: '/traces',     glyph: '◎', label: 'Traces' },
    ],
  },
  {
    title: 'System',
    items: [
      { to: '/models',    glyph: '◐', label: 'Models' },
      { to: '/providers', glyph: '⬡', label: 'Providers' },
      { to: '/mcp',       glyph: '⊞', label: 'MCP' },
      { to: '/settings',  glyph: '⚙', label: 'Settings' },
    ],
  },
]

export function AppShell({
  children,
  connected,
  services,
  approvals,
  events,
  voiceSession,
  jarvisSession,
  theme,
  onToggleTheme,
}: AppShellProps) {
  const location = useLocation()
  const navigate = useNavigate()
  const [commandOpen, setCommandOpen] = useState(false)
  const [commandQuery, setCommandQuery] = useState('')
  const [voiceBusy, setVoiceBusy] = useState(false)
  const [voiceMessage, setVoiceMessage] = useState('')
  const [desktopShell, setDesktopShell] = useState(false)
  const [now, setNow] = useState(new Date())
  const isJarvisRoute = location.pathname.startsWith('/jarvis')

  const serviceEntries = Object.entries(services || {})
  const upCount = serviceEntries.filter(([, v]: any) => v?.status === 'up' || v?.status === 'running').length
  const total = serviceEntries.length

  const activeVoiceSession = isJarvisRoute ? jarvisSession : voiceSession
  const voiceEnabled = isJarvisRoute
    ? activeVoiceSession?.voice_enabled !== false
    : activeVoiceSession?.mode !== 'off'

  const commandResults = useMemo(() => {
    const q = commandQuery.trim().toLowerCase()
    if (!q) return appNav
    return appNav.filter((item) => {
      const hay = `${item.label} ${item.description} ${item.to} ${item.section}`.toLowerCase()
      return hay.includes(q)
    })
  }, [commandQuery])

  async function runPushToTalk() {
    if (voiceBusy || !voiceEnabled) return
    setVoiceBusy(true)
    setVoiceMessage('Listening…')
    try {
      const result = isJarvisRoute
        ? await commandCenterApi.pushToTalkJarvis()
        : await commandCenterApi.pushToTalk()
      const r = result as any
      setVoiceMessage(r.error || (r.transcript ? `Heard: "${r.transcript}"` : r.reply || 'Done.'))
    } catch (e: any) {
      setVoiceMessage(e.message || 'Push-to-talk failed.')
    } finally {
      setVoiceBusy(false)
    }
  }

  useEffect(() => {
    desktopBridge.isDesktopShell().then(setDesktopShell).catch(() => {})
  }, [])

  useEffect(() => {
    const iv = setInterval(() => setNow(new Date()), 30_000)
    return () => clearInterval(iv)
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes((e.target as HTMLElement)?.tagName)
        || (e.target as HTMLElement)?.isContentEditable
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault(); setCommandOpen(true); return
      }
      if (e.key === '?' && !typing) { e.preventDefault(); setCommandOpen(true); return }
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.code === 'Space' && !typing) {
        e.preventDefault(); void runPushToTalk(); return
      }
      if (e.key === 'Escape') setCommandOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [voiceBusy, voiceEnabled, isJarvisRoute])

  useEffect(() => {
    setCommandQuery('')
    setCommandOpen(false)
    setVoiceMessage('')
  }, [location.pathname])

  const timeStr = now.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
  const dateStr = now.toLocaleString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })

  return (
    <>
      <div className="desktop">
        {/* Menubar */}
        <div className="menubar">
          <span className="name">clawOS</span>
          <span className="m-item">File</span>
          <span className="m-item">Edit</span>
          <span className="m-item">View</span>
          <span className="m-item">Jarvis</span>
          <span className="m-item">Help</span>
          <div className="right">
            <span className="dot" style={{ background: connected ? 'var(--success)' : 'var(--danger)', color: connected ? 'var(--success)' : 'var(--danger)' }} />
            <span>{upCount}/{total} services</span>
            {approvals.length > 0 && (
              <span style={{ color: 'var(--warn)' }}>{approvals.length} pending</span>
            )}
            <span>{dateStr} · {timeStr}</span>
          </div>
        </div>

        {/* App grid */}
        <div className="app">
          {/* Sidebar */}
          <aside className="side">
            <div className="brand">
              <div className="logo">◈</div>
              <div>
                <div className="n">clawOS</div>
                <div className="v">v0.1.0 · dashboard</div>
              </div>
            </div>

            {NAV_GROUPS.map(({ title, items }) => (
              <div key={title}>
                <div className="nav-title">{title}</div>
                {items.map(({ to, glyph, label, badge }) => (
                  <NavLink
                    key={to}
                    to={to}
                    end={to === '/'}
                    className={({ isActive }) => `nav-i${isActive ? ' active' : ''}`}
                  >
                    <span className="g">{glyph}</span>
                    <span style={{ flex: 1 }}>{label}</span>
                    {badge === 'approvals' && approvals.length > 0 && (
                      <span className="badge">{approvals.length}</span>
                    )}
                  </NavLink>
                ))}
              </div>
            ))}

            <div className="side-foot">
              <div style={{ color: connected ? 'var(--success)' : 'var(--danger)' }}>
                {connected ? '● nexus connected' : '○ nexus offline'}
              </div>
              <div>events · {events.length}</div>
              <div>{theme === 'dark' ? (
                <button
                  style={{ background: 'none', border: 'none', color: 'var(--ink-3)', cursor: 'pointer', padding: 0, fontSize: 10, fontFamily: 'var(--mono)' }}
                  onClick={onToggleTheme}
                >
                  ☀ light mode
                </button>
              ) : (
                <button
                  style={{ background: 'none', border: 'none', color: 'var(--ink-3)', cursor: 'pointer', padding: 0, fontSize: 10, fontFamily: 'var(--mono)' }}
                  onClick={onToggleTheme}
                >
                  ● dark mode
                </button>
              )}</div>
            </div>
          </aside>

          {/* Content */}
          <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden', position: 'relative' }}>
            {desktopShell && (
              <div className="shell-window-topbar">
                <div className="shell-window-controls" aria-hidden>
                  <span /><span /><span />
                </div>
                <div className="shell-window-title">ClawOS Command Center</div>
                <div className="shell-window-action-spacer" />
              </div>
            )}
            <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column', position: 'relative' }}>
              {children}
            </div>
          </div>
        </div>
      </div>

      {/* Command palette */}
      {commandOpen && (
        <div className="command-overlay" role="presentation" onClick={() => setCommandOpen(false)}>
          <div
            className="command-modal"
            role="dialog"
            aria-modal
            onClick={(e) => e.stopPropagation()}
            style={{
              background: 'var(--panel-strong)',
              backdropFilter: 'blur(20px) saturate(140%)',
              border: '1px solid var(--panel-br-strong)',
              borderRadius: 16,
              padding: 20,
              display: 'grid',
              gap: 12,
              width: 'min(680px, calc(100vw - 32px))',
              maxHeight: 'min(80vh, 640px)',
              boxShadow: '0 24px 80px rgba(0,0,0,0.6)',
            }}
          >
            <div>
              <div className="eyebrow">Command Center</div>
              <div style={{ fontSize: 20, fontWeight: 600, letterSpacing: '-0.02em', marginTop: 6 }}>
                Jump anywhere in clawOS
              </div>
            </div>

            <div className="search" style={{ marginBottom: 0 }}>
              <span className="sym">⌕</span>
              <input
                autoFocus
                placeholder="Search pages, surfaces, and tools…"
                value={commandQuery}
                onChange={(e) => setCommandQuery(e.target.value)}
              />
            </div>

            <div style={{ display: 'grid', gap: 6, overflowY: 'auto', maxHeight: 360 }}>
              {commandResults.map((item) => (
                <button
                  key={item.to}
                  type="button"
                  onClick={() => { navigate(item.to); setCommandOpen(false) }}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 12,
                    padding: '10px 12px', borderRadius: 10,
                    border: '1px solid var(--panel-br)',
                    background: 'rgba(255,255,255,0.02)',
                    color: 'var(--ink-1)', cursor: 'pointer',
                    textAlign: 'left', transition: 'all 0.12s',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-faint)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.02)')}
                >
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 14, color: 'var(--ink-3)', width: 20, textAlign: 'center' }}>
                    {item.icon as any}
                  </span>
                  <span style={{ flex: 1, display: 'grid', gap: 2 }}>
                    <span style={{ fontSize: 13, fontWeight: 600 }}>{item.label}</span>
                    <span style={{ fontSize: 11, color: 'var(--ink-3)', fontFamily: 'var(--mono)' }}>
                      {item.section} / {item.description}
                    </span>
                  </span>
                </button>
              ))}
              {commandResults.length === 0 && (
                <div className="empty" style={{ minHeight: 80 }}>
                  <div className="empty-title">No results</div>
                  <div className="empty-body">Try "workflows", "memory", or "settings".</div>
                </div>
              )}
            </div>

            <div style={{ display: 'flex', gap: 16, borderTop: '1px solid var(--panel-br)', paddingTop: 10, fontSize: 11, color: 'var(--ink-3)', fontFamily: 'var(--mono)' }}>
              <span><ShortcutKey>Ctrl K</ShortcutKey> open</span>
              <span><ShortcutKey>Esc</ShortcutKey> close</span>
              <span><ShortcutKey>Ctrl ⇧ Space</ShortcutKey> talk</span>
              {voiceMessage && <span style={{ marginLeft: 'auto', color: 'var(--accent-text)' }}>{voiceMessage}</span>}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
