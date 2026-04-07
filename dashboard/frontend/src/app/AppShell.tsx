/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { type PropsWithChildren, type ReactNode, useEffect, useMemo, useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { appNav } from './navigation'
import { Badge, ShortcutKey } from '../components/ui.jsx'
import { commandCenterApi } from '../lib/commandCenterApi'

type AppShellProps = PropsWithChildren<{
  connected: boolean
  services: Record<string, any>
  approvals: any[]
  events: any[]
  voiceSession?: Record<string, any>
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
  voiceSession,
  inspector,
  theme,
  onToggleTheme,
}: AppShellProps) {
  const location = useLocation()
  const navigate = useNavigate()
  const [commandOpen, setCommandOpen] = useState(false)
  const [commandQuery, setCommandQuery] = useState('')
  const [voiceBusy, setVoiceBusy] = useState(false)
  const [voiceMessage, setVoiceMessage] = useState('')
  const serviceList = Object.values(services || {})
  const upCount = serviceList.filter((item: any) => item.status === 'up' || item.status === 'running').length
  const activeItem = appNav.find((item) => item.to === location.pathname) ?? appNav[0]
  const voiceMode = String(voiceSession?.mode || 'off').replace(/_/g, ' ')
  const voiceState = String(voiceSession?.state || 'idle')
  const voiceDot = voiceState === 'listening' ? 'green pulse' : voiceState === 'speaking' ? 'blue pulse' : voiceState === 'thinking' ? 'orange pulse' : 'gray'
  const voiceEnabled = voiceSession?.mode !== 'off'

  const commandResults = useMemo(() => {
    const query = commandQuery.trim().toLowerCase()
    if (!query) return appNav
    return appNav.filter((item) => {
      const haystack = `${item.label} ${item.description} ${item.to}`.toLowerCase()
      return haystack.includes(query)
    })
  }, [commandQuery])

  async function runPushToTalk() {
    if (voiceBusy || !voiceEnabled) return
    setVoiceBusy(true)
    setVoiceMessage('Listening now...')
    try {
      const result = await commandCenterApi.pushToTalk()
      if (result.error) {
        setVoiceMessage(result.error)
      } else if (result.transcript) {
        setVoiceMessage(`Heard: "${result.transcript}"`)
      } else {
        setVoiceMessage(result.issues?.[0] || 'No speech detected in that round.')
      }
    } catch (error: any) {
      setVoiceMessage(error.message || 'Push-to-talk failed.')
    } finally {
      setVoiceBusy(false)
    }
  }

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      const isTyping =
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.tagName === 'SELECT' ||
          target.isContentEditable)

      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setCommandOpen(true)
        return
      }

      if (event.key === '?' && !isTyping) {
        event.preventDefault()
        setCommandOpen(true)
        return
      }

      if ((event.metaKey || event.ctrlKey) && event.shiftKey && event.code === 'Space' && !isTyping) {
        event.preventDefault()
        void runPushToTalk()
        return
      }

      if (event.key === 'Escape') {
        setCommandOpen(false)
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [voiceBusy, voiceEnabled])

  useEffect(() => {
    setCommandQuery('')
    setCommandOpen(false)
  }, [location.pathname])

  return (
    <>
      <div className="shell-root">
        <aside className="shell-sidebar">
          <div className="shell-brand">
            <div className="shell-brand-mark">
              <svg width="18" height="18" viewBox="0 0 16 16" fill="none">
                <path d="M8 2.1 13.25 5v5.97L8 13.9 2.75 10.97V5L8 2.1Z" stroke="white" strokeWidth="1.2" strokeLinejoin="round" />
                <circle cx="8" cy="8" r="2.1" fill="white" />
              </svg>
            </div>
            <div className="shell-brand-copy">
              <div className="shell-brand-title">ClawOS</div>
              <div className="shell-brand-subtitle">Nexus Command Center</div>
            </div>
          </div>

          <button type="button" className="command-launch" onClick={() => setCommandOpen(true)}>
            <span className="command-launch-copy">
              <span className="command-launch-title">Ask Nexus or jump to a surface</span>
              <span className="command-launch-subtitle">{activeItem.description}</span>
            </span>
            <span className="command-launch-keys">
              <ShortcutKey>Ctrl</ShortcutKey>
              <ShortcutKey>K</ShortcutKey>
            </span>
          </button>

          <div className="shell-nav">
            {appNav.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) => `shell-nav-link${isActive ? ' active' : ''}`}
              >
                <span className="shell-nav-icon">{item.icon}</span>
                <span className="shell-nav-copy">
                  <span className="shell-nav-title">{item.label}</span>
                  <span className="shell-nav-description">{item.description}</span>
                </span>
                {item.label === 'Approvals' && approvals.length > 0 ? (
                  <Badge color="red">{approvals.length}</Badge>
                ) : null}
              </NavLink>
            ))}
          </div>

          <div className="shell-sidebar-footer">
            <div className="shell-sidebar-health">
              <div className="shell-health-row">
                <div className="shell-health-copy">
                  <span className={`dot ${connected ? 'green pulse' : 'red'}`} />
                  <span>{connected ? 'Nexus connected' : 'Reconnecting to Nexus'}</span>
                </div>
                <Badge color={connected ? 'green' : 'red'}>{connected ? 'live' : 'syncing'}</Badge>
              </div>
              <div className="shell-health-stats">
                <span>{upCount}/{serviceList.length || 0} services healthy</span>
                <span>{events.length} recent events</span>
              </div>
            </div>
          </div>
        </aside>

        <section className="shell-window">
          <div className="shell-window-topbar">
            <div className="shell-window-controls">
              <span />
              <span />
              <span />
            </div>
            <div className="shell-window-breadcrumbs">
              <span>Command Center</span>
              <span>/</span>
              <span>{activeItem.label}</span>
            </div>
            <div className="shell-window-actions">
              <div className="shell-status-chip">
                <span className={`dot ${connected ? 'green pulse' : 'red'}`} />
                <span>{connected ? 'Connected' : 'Offline'}</span>
              </div>
              <div className="shell-status-chip">
                <span className={`dot ${voiceDot}`} />
                <span>{voiceState}</span>
              </div>
              <button type="button" className="btn sm" onClick={() => void runPushToTalk()} disabled={voiceBusy || !voiceEnabled}>
                {voiceBusy ? 'Listening...' : voiceEnabled ? 'Talk now' : 'Voice off'}
              </button>
              <button type="button" className="btn sm" onClick={onToggleTheme}>
                {theme === 'dark' ? 'Light' : 'Dark'}
              </button>
              <button type="button" className="btn sm" onClick={() => setCommandOpen(true)}>
                Shortcuts
              </button>
            </div>
          </div>

          <div className="shell-window-body">
            <div className="shell-main">
              <header className="shell-header">
                <div>
                  <div className="section-label">Now Viewing</div>
                  <div className="shell-header-title">{activeItem.label}</div>
                  <div className="shell-header-description">{activeItem.description}</div>
                </div>
                <div className="shell-header-meta">
                  <Badge color="blue">{serviceList.length || 0} services</Badge>
                  <Badge color={approvals.length ? 'orange' : 'green'}>
                    {approvals.length ? `${approvals.length} approvals` : 'No blockers'}
                  </Badge>
                  <Badge color={voiceSession?.mode === 'off' ? 'gray' : voiceState === 'listening' || voiceState === 'speaking' ? 'blue' : 'green'}>
                    Voice {voiceMode}
                  </Badge>
                  {voiceMessage ? <span className="mono" style={{ color: 'var(--text-3)', fontSize: 11 }}>{voiceMessage}</span> : null}
                  <div className="shell-shortcut-hint">
                    <ShortcutKey>?</ShortcutKey>
                    <span>show shortcuts</span>
                  </div>
                </div>
              </header>

              <div className="shell-content">{children}</div>
            </div>

            {inspector ? <aside className="shell-inspector">{inspector}</aside> : null}
          </div>
        </section>
      </div>

      {commandOpen ? (
        <div className="command-overlay" role="presentation" onClick={() => setCommandOpen(false)}>
          <div className="command-modal" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <div className="command-modal-header">
              <div>
                <div className="section-label">Quick Actions</div>
                <div className="panel-title">Jump anywhere in ClawOS</div>
                <div className="panel-description">
                  Use <ShortcutKey>Ctrl</ShortcutKey> <ShortcutKey>K</ShortcutKey> any time, or press <ShortcutKey>Esc</ShortcutKey> to close this palette.
                </div>
              </div>
            </div>

            <input
              autoFocus
              type="text"
              className="command-modal-input"
              value={commandQuery}
              onChange={(event) => setCommandQuery(event.target.value)}
              placeholder="Search pages, surfaces, and tools"
            />

            <div className="command-results">
              {commandResults.map((item) => (
                <button
                  key={item.to}
                  type="button"
                  className="command-result"
                  onClick={() => {
                    navigate(item.to)
                    setCommandOpen(false)
                  }}
                >
                  <span className="command-result-icon">{item.icon}</span>
                  <span className="command-result-copy">
                    <span className="command-result-title">{item.label}</span>
                    <span className="command-result-description">{item.description}</span>
                  </span>
                </button>
              ))}
              {commandResults.length === 0 ? (
                <div className="command-empty">
                  <div className="empty-title">No results yet</div>
                  <div className="empty-body">Try a route name like "workflows", "registry", or "research".</div>
                </div>
              ) : null}
            </div>

            <div className="command-shortcuts">
              <div className="command-shortcuts-row">
                <span>Open command palette</span>
                <span><ShortcutKey>Ctrl</ShortcutKey> <ShortcutKey>K</ShortcutKey></span>
              </div>
              <div className="command-shortcuts-row">
                <span>Open shortcuts help</span>
                <span><ShortcutKey>?</ShortcutKey></span>
              </div>
              <div className="command-shortcuts-row">
                <span>Push to talk</span>
                <span><ShortcutKey>Ctrl</ShortcutKey> <ShortcutKey>Shift</ShortcutKey> <ShortcutKey>Space</ShortcutKey></span>
              </div>
              <div className="command-shortcuts-row">
                <span>Close palette</span>
                <span><ShortcutKey>Esc</ShortcutKey></span>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </>
  )
}
