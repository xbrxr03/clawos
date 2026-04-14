/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { type PropsWithChildren, type ReactNode, useEffect, useMemo, useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { appNav } from './navigation'
import { Badge, ShortcutKey } from '../components/ui.jsx'
import { desktopBridge } from '../desktop/bridge'
import { commandCenterApi } from '../lib/commandCenterApi'

type AppShellProps = PropsWithChildren<{
  connected: boolean
  services: Record<string, any>
  approvals: any[]
  events: any[]
  voiceSession?: Record<string, any>
  jarvisSession?: Record<string, any>
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
  jarvisSession,
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
  const [desktopShell, setDesktopShell] = useState(false)
  const isJarvisRoute = location.pathname.startsWith('/jarvis')

  const serviceEntries = Object.entries(services || {})
  const serviceList = serviceEntries.map(([, value]) => value)
  const upCount = serviceList.filter((item: any) => item.status === 'up' || item.status === 'running').length
  const activeItem = appNav.find((item) => item.to === location.pathname) ?? appNav[0]
  const activeVoiceSession = isJarvisRoute ? jarvisSession : voiceSession
  const voiceState = String(activeVoiceSession?.state || 'idle')
  const voiceDot =
    voiceState === 'listening'
      ? 'green pulse'
      : voiceState === 'speaking'
        ? 'blue pulse'
        : voiceState === 'thinking'
          ? 'orange pulse'
          : 'gray'
  const voiceEnabled = isJarvisRoute ? activeVoiceSession?.voice_enabled !== false : activeVoiceSession?.mode !== 'off'

  const navSections = useMemo(() => {
    const grouped = new Map<string, typeof appNav>()
    appNav.forEach((item) => {
      const current = grouped.get(item.section) || []
      current.push(item)
      grouped.set(item.section, current)
    })
    return Array.from(grouped.entries())
  }, [])

  const servicePreview = useMemo(() => serviceEntries.slice(0, 3), [serviceEntries])

  const commandResults = useMemo(() => {
    const query = commandQuery.trim().toLowerCase()
    if (!query) return appNav
    return appNav.filter((item) => {
      const haystack = `${item.label} ${item.description} ${item.to} ${item.section}`.toLowerCase()
      return haystack.includes(query)
    })
  }, [commandQuery])

  async function runPushToTalk() {
    if (voiceBusy || !voiceEnabled) return
    setVoiceBusy(true)
    setVoiceMessage('Listening now...')
    try {
      const result = isJarvisRoute ? await commandCenterApi.pushToTalkJarvis() : await commandCenterApi.pushToTalk()
      const transcript = (result as any).transcript
      const reply = (result as any).reply || (result as any).response
      if ((result as any).error) {
        setVoiceMessage((result as any).error)
      } else if (transcript) {
        setVoiceMessage(`Heard: "${transcript}"`)
      } else if (reply) {
        setVoiceMessage(`Reply: "${reply}"`)
      } else {
        setVoiceMessage((result as any).issues?.[0] || 'No speech detected in that round.')
      }
    } catch (error: any) {
      setVoiceMessage(error.message || 'Push-to-talk failed.')
    } finally {
      setVoiceBusy(false)
    }
  }

  useEffect(() => {
    desktopBridge.isDesktopShell().then(setDesktopShell).catch(() => setDesktopShell(false))
  }, [])

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
  }, [voiceBusy, voiceEnabled, isJarvisRoute])

  useEffect(() => {
    setCommandQuery('')
    setCommandOpen(false)
    setVoiceMessage('')
  }, [location.pathname])

  return (
    <>
      <div className="shell-root">
        <aside className="shell-sidebar">
          <div className="shell-brand">
            <div className="shell-brand-mark" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 16 16" fill="none">
                <path d="M8 2.1 13.25 5v5.97L8 13.9 2.75 10.97V5L8 2.1Z" stroke="currentColor" strokeWidth="1.15" strokeLinejoin="round" />
                <circle cx="8" cy="8" r="2.05" fill="currentColor" />
              </svg>
            </div>
            <div className="shell-brand-copy">
              <div className="shell-brand-title">ClawOS</div>
              <div className="shell-brand-subtitle">v1.0 command center</div>
            </div>
          </div>

          <button type="button" className="command-launch" onClick={() => setCommandOpen(true)}>
            <span className="command-launch-copy">
              <span className="command-launch-title">Search or jump to a surface</span>
            </span>
            <span className="command-launch-keys">
              <ShortcutKey>Ctrl</ShortcutKey>
              <ShortcutKey>K</ShortcutKey>
            </span>
          </button>

          <div className="shell-nav">
            {navSections.map(([section, items]) => (
              <div key={section} className="shell-nav-group">
                <div className="shell-nav-group-title">{section}</div>
                {items.map((item) => (
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
                    {item.label === 'Approvals' && approvals.length > 0 ? <Badge color="red">{approvals.length}</Badge> : null}
                  </NavLink>
                ))}
              </div>
            ))}
          </div>

          <div className="shell-sidebar-footer">
            <div className="shell-sidebar-health">
              <div className="shell-health-row">
                <div className="shell-health-copy">
                  <span className={`dot ${connected ? 'green pulse' : 'red'}`} />
                  <span>{connected ? 'Nexus connected' : 'Reconnecting to Nexus'}</span>
                </div>
                <Badge color={connected ? 'green' : 'red'}>{connected ? 'live' : 'offline'}</Badge>
              </div>
              {servicePreview.map(([name, item]) => {
                const status = item?.status === 'up' || item?.status === 'running' ? 'green' : item?.status === 'degraded' ? 'orange' : 'red'
                return (
                  <div key={name} className="shell-health-row">
                    <div className="shell-health-copy">
                      <span className={`dot ${status}`} />
                      <span style={{ textTransform: 'capitalize' }}>{name}</span>
                    </div>
                    <span className="ts">{item?.latency_ms ? `${item.latency_ms}ms` : 'idle'}</span>
                  </div>
                )
              })}
              <div className="shell-health-stats">
                <span>{upCount}/{serviceList.length || 0} healthy</span>
                <span>{events.length} events</span>
              </div>
            </div>
          </div>
        </aside>

        <section className={`shell-window${desktopShell ? ' desktop' : ''}${isJarvisRoute ? ' jarvis-route' : ''}`}>
          {desktopShell ? (
            <div className="shell-window-topbar">
              <div className="shell-window-controls" aria-hidden="true">
                <span />
                <span />
                <span />
              </div>
              <div className="shell-window-title">ClawOS Command Center / {activeItem.label}</div>
              <div className="shell-window-action-spacer" />
            </div>
          ) : null}

          <div className={`shell-window-body${isJarvisRoute ? ' shell-window-body-immersive' : ''}`}>
            <div className={`shell-main${isJarvisRoute ? ' shell-main-immersive' : ''}`}>
              <header className="shell-header">
                <div>
                  <div className="section-label">Now Viewing</div>
                  <div className="shell-header-title">{activeItem.label}</div>
                  <div className="shell-header-description">{activeItem.description}</div>
                </div>
                <div className="shell-header-meta">
                  <div className="shell-status-chip">
                    <span className={`dot ${connected ? 'green pulse' : 'red'}`} />
                    <span>{connected ? 'Connected' : 'Offline'}</span>
                  </div>
                  <div className="shell-status-chip">
                    <span className={`dot ${voiceDot}`} />
                    <span>{voiceState}</span>
                  </div>
                  <Badge color="blue">{serviceList.length || 0} services</Badge>
                  <Badge color={approvals.length ? 'orange' : 'green'}>
                    {approvals.length ? `${approvals.length} approvals` : 'No blockers'}
                  </Badge>
                  <button type="button" className="btn sm" onClick={() => void runPushToTalk()} disabled={voiceBusy || !voiceEnabled}>
                    {voiceBusy ? 'Listening...' : voiceEnabled ? 'Talk now' : 'Voice off'}
                  </button>
                  <button type="button" className="btn sm" onClick={onToggleTheme}>
                    {theme === 'dark' ? 'Light' : 'Dark'}
                  </button>
                  <button type="button" className="btn sm" onClick={() => setCommandOpen(true)}>
                    Shortcuts
                  </button>
                  {voiceMessage ? <span className="mono" style={{ color: 'var(--text-3)', fontSize: 11 }}>{voiceMessage}</span> : null}
                  <div className="shell-shortcut-hint">
                    <ShortcutKey>?</ShortcutKey>
                    <span>show shortcuts</span>
                  </div>
                </div>
              </header>

              <div className={`shell-content${isJarvisRoute ? ' shell-content-immersive' : ''}`}>{children}</div>
            </div>

            {!isJarvisRoute && inspector ? <aside className="shell-inspector">{inspector}</aside> : null}
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
                    <span className="command-result-description">{item.section} / {item.description}</span>
                  </span>
                </button>
              ))}
              {commandResults.length === 0 ? (
                <div className="command-empty">
                  <div className="empty-title">No results yet</div>
                  <div className="empty-body">Try a route name like "workflows", "research", or "settings".</div>
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
