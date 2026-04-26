/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { type Key, type ReactNode, useEffect, useMemo, useState } from 'react'
import { Badge, Card, PageHeader, PanelHeader } from '../components/ui.jsx'
import { commandCenterApi, type DashboardHealth, type DesktopPosture, type JarvisConfig, type JarvisHealth } from '../lib/commandCenterApi'
import { desktopBridge } from '../desktop/bridge'

const JARVIS_VOICE_ID = 'nPczCjzI2devNBz1zQrb' // Brian — deep, cinematic

type PathKind = 'logs' | 'config' | 'workspace' | 'support'

const PATH_LABELS: Record<PathKind, string> = {
  logs: 'Logs',
  config: 'Config',
  workspace: 'Workspace',
  support: 'Support',
}

export function SettingsPage() {
  const [health, setHealth] = useState<DashboardHealth | null>(null)
  const [posture, setPosture] = useState<DesktopPosture | null>(null)
  const [jarvisHealth, setJarvisHealth] = useState<JarvisHealth | null>(null)
  const [jarvisConfig, setJarvisConfig] = useState<JarvisConfig | null>(null)
  const [bundlePath, setBundlePath] = useState('')
  const [shellMode, setShellMode] = useState(false)
  const [serviceMessage, setServiceMessage] = useState('')
  const [busy, setBusy] = useState<string | null>(null)

  useEffect(() => {
    commandCenterApi.getHealth().then(setHealth).catch(() => null)
    commandCenterApi.getDesktopPosture().then(setPosture).catch(() => null)
    commandCenterApi.getJarvisHealth().then(setJarvisHealth).catch(() => null)
    commandCenterApi.getJarvisConfig().then(setJarvisConfig).catch(() => null)
    desktopBridge.isDesktopShell().then(setShellMode).catch(() => setShellMode(false))
    const id = window.setInterval(() => {
      commandCenterApi.getJarvisHealth().then(setJarvisHealth).catch(() => null)
      commandCenterApi.getJarvisConfig().then(setJarvisConfig).catch(() => null)
    }, 15000)
    return () => window.clearInterval(id)
  }, [])

  const runtimeRows = useMemo<[string, string, string][]>(() => [
    ['Host', String(health?.host ?? '127.0.0.1'), 'Loopback address serving the dashboard'],
    ['Port', String(health?.port ?? 7070), 'API + frontend traffic'],
    ['Auth', health?.auth_required ? 'Required' : 'Open', 'Session gate before any action runs'],
    ['Local only', health?.local_only ? 'Yes' : 'No', 'Restricted to loopback trust boundary'],
    ['Shell mode', shellMode ? 'Desktop' : 'Browser', 'Native bridge availability'],
    ['Autostart', String(posture?.autostart_kind ?? 'unknown'), 'Platform startup mechanism'],
  ], [health, posture, shellMode])

  const createBundle = async () => {
    setBusy('bundle')
    setServiceMessage('')
    try {
      if (shellMode) {
        const nativePath = await desktopBridge.createSupportBundle()
        if (nativePath) {
          setBundlePath(nativePath)
          setServiceMessage('Support bundle created from the desktop shell.')
          return
        }
      }
      const payload = await commandCenterApi.createSupportBundle()
      setBundlePath(payload.path || '')
      setServiceMessage('Support bundle created from the dashboard API.')
    } finally {
      setBusy(null)
    }
  }

  const runServiceAction = async (action: 'start' | 'stop' | 'restart') => {
    setBusy(action)
    setServiceMessage('')
    try {
      const result = await desktopBridge.serviceAction(action)
      setServiceMessage(result || `${action} requested`)
      const latestHealth = await commandCenterApi.getHealth()
      setHealth(latestHealth)
    } finally {
      setBusy(null)
    }
  }

  const toggleLaunchOnLogin = async () => {
    if (!posture?.launch_on_login_supported) {
      setServiceMessage('Launch on login is not supported on this platform.')
      return
    }

    setBusy('launch')
    setServiceMessage('')
    try {
      const next = await commandCenterApi.setLaunchOnLogin(!posture.launch_on_login_enabled)
      setPosture(next)
      setServiceMessage(next.message || 'Desktop posture updated')
    } finally {
      setBusy(null)
    }
  }

  const openKnownPath = async (kind: PathKind) => {
    const path = posture?.paths?.[kind]
    if (!path) {
      setServiceMessage(`No ${PATH_LABELS[kind].toLowerCase()} path is available yet.`)
      return
    }

    setBusy(kind)
    setServiceMessage('')
    try {
      if (shellMode) {
        const opened = await desktopBridge.openPath(kind)
        if (opened) {
          setServiceMessage(`${PATH_LABELS[kind]} opened: ${opened}`)
          return
        }
      }
      setServiceMessage(`${PATH_LABELS[kind]}: ${path}`)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="fade-up" style={{ padding: '0 0 48px', overflowY: 'auto', flex: 1, height: '100%' }}>
      <div style={{ padding: '24px 20px 16px' }}>
        <PageHeader
          eyebrow="Settings"
          title="System settings"
          description="Runtime, voice, integrations, and startup controls."
          meta={
            <>
              <Badge color={health?.auth_required ? 'green' : 'orange'}>{health?.auth_required ? 'Auth required' : 'Auth open'}</Badge>
              <Badge color={shellMode ? 'blue' : 'gray'}>{shellMode ? 'Desktop shell' : 'Browser mode'}</Badge>
            </>
          }
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, padding: '0 20px' }}>
        <div style={{ display: 'grid', gap: 16, alignContent: 'start' }}>
          <Card style={{ padding: 18 }}>
            <PanelHeader
              eyebrow="Runtime"
              title="Dashboard posture"
              description="Live host, auth, shell, and startup state."
            />
            <div className="setting-group">
              {runtimeRows.map(([label, value, description]) => (
                <SettingRow key={label} label={label} description={description} value={value} />
              ))}
            </div>
          </Card>

          <Card style={{ padding: 18 }}>
            <PanelHeader
              eyebrow="Services"
              title="Lifecycle controls"
              description="Start, restart, or stop the managed stack. Only available in desktop shell mode."
              aside={<Badge color={shellMode ? 'green' : 'gray'}>{shellMode ? 'available' : 'desktop only'}</Badge>}
            />
            <div className="setting-group">
              <SettingActionRow label="Start" description="Bring the stack online." action={<button className="btn sm" onClick={() => runServiceAction('start')} disabled={!shellMode || busy !== null}>Start</button>} />
              <SettingActionRow label="Restart" description="Restart without leaving the dashboard." action={<button className="btn sm" onClick={() => runServiceAction('restart')} disabled={!shellMode || busy !== null}>Restart</button>} />
              <SettingActionRow label="Stop" description="Shut down the managed stack." action={<button className="btn danger sm" onClick={() => runServiceAction('stop')} disabled={!shellMode || busy !== null}>Stop</button>} />
            </div>
          </Card>

          <JarvisVoiceCard health={jarvisHealth} config={jarvisConfig} />

          <ElevenLabsCard />
          <CalendarCard config={jarvisConfig} />

          <Card style={{ padding: 18 }}>
            <PanelHeader
              eyebrow="Startup"
              title="Launch on login"
              description="Start ClawOS automatically when you sign in."
              aside={<Badge color={posture?.launch_on_login_enabled ? 'green' : 'gray'}>{posture?.launch_on_login_enabled ? 'enabled' : 'disabled'}</Badge>}
            />
            <div className="setting-group">
              <SettingRow label="Mechanism" description="Platform startup method." value={posture?.autostart_kind ?? 'unknown'} />
              <div className="setting-row">
                <div className="setting-row-copy">
                  <div className="setting-row-title">Launch on login</div>
                  <div className="setting-row-description">Start ClawOS as soon as you sign in.</div>
                </div>
                <button className="btn" onClick={toggleLaunchOnLogin} disabled={busy !== null || !posture?.launch_on_login_supported} style={{ minWidth: 72 }}>
                  <span className={`toggle${posture?.launch_on_login_enabled ? ' active' : ''}`} aria-hidden="true" />
                  <span>{posture?.launch_on_login_enabled ? 'On' : 'Off'}</span>
                </button>
              </div>
              {posture?.launch_on_login_path ? (
                <SettingRow label="Autostart file" description="Platform startup file." value={posture.launch_on_login_path} />
              ) : null}
            </div>
          </Card>
        </div>

        <div style={{ display: 'grid', gap: 16, alignContent: 'start' }}>
          <Card style={{ padding: 18 }}>
            <PanelHeader
              eyebrow="Support"
              title="Diagnostics"
              description="Export logs and service state for debugging."
            />
            <div className="setting-group">
              <SettingActionRow label="Support bundle" description="Creates a zip of logs, config, and service health you can share when something breaks." action={<button className="btn primary sm" onClick={createBundle} disabled={busy !== null}>Create</button>} />
            </div>
            {bundlePath ? (
              <div style={{ marginTop: 10, fontSize: 12, color: 'var(--ink-3)' }}>
                Bundle: <span style={{ fontFamily: 'var(--mono)' }}>{bundlePath}</span>
              </div>
            ) : null}
          </Card>

          <Card style={{ padding: 18 }}>
            <PanelHeader
              eyebrow="Paths"
              title="Open directories"
              description="Jump to logs, config, workspace, or support folders."
            />
            <div className="setting-group">
              {(Object.keys(PATH_LABELS) as PathKind[]).map((kind) => (
                <SettingActionRow
                  key={kind}
                  label={PATH_LABELS[kind]}
                  description={posture?.paths?.[kind] || 'Not available yet'}
                  action={<button className="btn sm" onClick={() => openKnownPath(kind)} disabled={busy !== null}>Open</button>}
                />
              ))}
            </div>
          </Card>
        </div>
      </div>

      {serviceMessage ? (
        <div style={{ padding: '16px 20px 0' }}>
          <Card style={{ padding: 14, color: 'var(--text-2)', fontSize: 13 }}>
            {serviceMessage}
          </Card>
        </div>
      ) : null}
    </div>
  )
}


function JarvisVoiceCard({ health, config }: { health: JarvisHealth | null; config: JarvisConfig | null }) {
  const activeProvider = health?.provider_status?.active || config?.tts_provider_preference || 'piper'
  const briefingSources = Object.entries(health?.briefing_sources || {})
  const liveCount = briefingSources.filter(([, status]) => status === 'live').length
  const demoCount = briefingSources.filter(([, status]) => status === 'demo').length
  const voiceMode = config?.voice_enabled === false ? 'voice off' : String(config?.input_mode || 'push_to_talk').replace(/_/g, ' ')

  return (
    <Card style={{ padding: 18 }}>
      <PanelHeader
        eyebrow="Jarvis"
        title="Voice &amp; routing"
        description="Provider, mode, and briefing source status."
        aside={<Badge color={health?.openclaw_running ? 'green' : 'orange'}>{health?.openclaw_running ? 'OpenClaw live' : 'OpenClaw offline'}</Badge>}
      />
      <div className="setting-group">
        <SettingRow label="Routing" description="Brain agent." value={health?.openclaw_running ? 'OpenClaw' : 'Waiting'} />
        <SettingRow label="TTS provider" description="Active voice engine." value={health?.provider_status?.fallback ? `${activeProvider} (fallback)` : activeProvider} />
        <SettingRow label="Voice mode" description="Input method." value={voiceMode} />
        <SettingRow label="Briefing sources" description="Live vs demo data." value={briefingSources.length ? `${liveCount} live / ${demoCount} demo` : 'loading'} />
        <SettingActionRow label="Open Jarvis" description="Configure voice, wake phrase, and transcript cockpit." action={<a className="btn primary sm" href="/jarvis">Open →</a>} />
      </div>
    </Card>
  )
}

function ElevenLabsCard() {
  const [apiKey, setApiKey] = useState('')
  const [voiceId, setVoiceId] = useState(JARVIS_VOICE_ID)
  const [status, setStatus] = useState<{ enabled: boolean; key_set: boolean } | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    commandCenterApi.getElevenLabsConfig()
      .then(s => setStatus(s))
      .catch(() => null)
  }, [])

  const activate = async () => {
    if (!apiKey.trim()) { setError('Paste your ElevenLabs API key first'); return }
    setBusy(true); setMessage(''); setError('')
    try {
      const result = await commandCenterApi.setElevenLabsConfig(apiKey.trim(), voiceId.trim() || JARVIS_VOICE_ID)
      if (result.ok && result.tested) {
        setMessage('✓ JARVIS voice activated — ElevenLabs is live')
        setStatus({ enabled: true, key_set: true })
        setApiKey('')
      }
    } catch (e: any) {
      setError(e?.message || 'Activation failed — check your API key')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card style={{ padding: 18 }}>
      <PanelHeader
        eyebrow="Voice"
        title="ElevenLabs TTS"
        description="Upgrade from Piper to ElevenLabs. Paste your API key — ClawOS wires the rest."
        aside={
          <Badge color={status?.enabled ? 'green' : 'gray'}>
            {status?.enabled ? 'ElevenLabs ✓' : 'Piper (free)'}
          </Badge>
        }
      />
      <div className="setting-group">
        <div className="setting-row" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 10 }}>
          <div className="setting-row-copy">
            <div className="setting-row-title">API Key</div>
            <div className="setting-row-description">
              From <a href="https://elevenlabs.io" target="_blank" rel="noreferrer" style={{ color: 'var(--accent)' }}>elevenlabs.io</a> → Profile → API Keys. Free tier has 10k characters/month.
            </div>
          </div>
          <input
            type="password"
            placeholder={status?.key_set ? '••••••••  (key saved — paste to update)' : 'sk-...'}
            value={apiKey}
            onChange={e => setApiKey(e.target.value)}
            style={{
              width: '100%', background: 'var(--panel)', border: '1px solid var(--panel-br)',
              borderRadius: 6, padding: '8px 12px', color: 'var(--ink-1)', fontSize: 13,
            }}
          />
        </div>
        <div className="setting-row" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 10 }}>
          <div className="setting-row-copy">
            <div className="setting-row-title">Voice ID</div>
            <div className="setting-row-description">Pre-filled with Brian (cinematic, JARVIS-like). Find more at elevenlabs.io/voice-lab.</div>
          </div>
          <input
            type="text"
            value={voiceId}
            onChange={e => setVoiceId(e.target.value)}
            style={{
              width: '100%', background: 'var(--panel)', border: '1px solid var(--panel-br)',
              borderRadius: 6, padding: '8px 12px', color: 'var(--ink-1)', fontSize: 13, fontFamily: 'var(--mono)',
            }}
          />
        </div>
        <div className="setting-row">
          <div className="setting-row-copy">
            <div className="setting-row-title">Activate</div>
            <div className="setting-row-description">Saves key, switches TTS provider, and runs a test synthesis to confirm it works.</div>
          </div>
          <button className="btn primary sm" onClick={activate} disabled={busy}>
            {busy ? 'Testing…' : 'Activate JARVIS voice'}
          </button>
        </div>
      </div>
      {message && <div style={{ marginTop: 10, fontSize: 12, color: 'var(--green)' }}>{message}</div>}
      {error   && <div style={{ marginTop: 10, fontSize: 12, color: 'var(--red,#e53935)' }}>{error}</div>}
    </Card>
  )
}

function CalendarCard({ config }: { config: JarvisConfig | null }) {
  const hasUrl = Boolean(config?.calendar_ics_url)
  const [icsUrl, setIcsUrl] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const save = async () => {
    const url = icsUrl.trim()
    if (!url) { setError('Paste your ICS calendar URL first'); return }
    if (!url.startsWith('http')) { setError('URL must start with http:// or https://'); return }
    setBusy(true); setMessage(''); setError('')
    try {
      await commandCenterApi.setJarvisConfig({ calendar_ics_url: url })
      setMessage('✓ Calendar connected — JARVIS will use real events in your next briefing')
      setIcsUrl('')
    } catch (e: any) {
      setError(e?.message || 'Failed to save calendar URL')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card style={{ padding: 18 }}>
      <PanelHeader
        eyebrow="Jarvis Briefing"
        title="Calendar"
        description="Paste your secret ICS link — no OAuth. Works with Google, Apple, Nextcloud, Outlook."
        aside={<Badge color={hasUrl ? 'green' : 'gray'}>{hasUrl ? 'Connected ✓' : 'Not connected (demo)'}</Badge>}
      />
      <div className="setting-group">
        <div className="setting-row" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 10 }}>
          <div className="setting-row-copy">
            <div className="setting-row-title">Calendar ICS URL</div>
            <div className="setting-row-description">
              In Google Calendar: Settings → click your calendar → scroll to <strong>"Secret address in iCal format"</strong> → copy the link.
              Works with any calendar provider that exports ICS (Apple, Nextcloud, Outlook).
            </div>
          </div>
          <input
            type="text"
            placeholder={hasUrl ? 'Paste to update' : 'https://calendar.google.com/calendar/ical/...'}
            value={icsUrl}
            onChange={e => setIcsUrl(e.target.value)}
            style={{
              width: '100%', background: 'var(--panel)', border: '1px solid var(--panel-br)',
              borderRadius: 6, padding: '8px 12px', color: 'var(--ink-1)', fontSize: 12,
              fontFamily: 'var(--mono)',
            }}
          />
        </div>
        <div className="setting-row">
          <div className="setting-row-copy">
            <div className="setting-row-title">Save</div>
            <div className="setting-row-description">JARVIS will fetch today's events each time you ask for your briefing.</div>
          </div>
          <button className="btn primary sm" onClick={save} disabled={busy}>
            {busy ? 'Saving…' : 'Connect calendar'}
          </button>
        </div>
      </div>
      {message && <div style={{ marginTop: 10, fontSize: 12, color: 'var(--green)' }}>{message}</div>}
      {error   && <div style={{ marginTop: 10, fontSize: 12, color: 'var(--red,#e53935)' }}>{error}</div>}
    </Card>
  )
}

function SettingRow({ label, description, value }: { label: string; description: string; value: string; key?: Key }) {
  return (
    <div className="setting-row">
      <div className="setting-row-copy">
        <div className="setting-row-title">{label}</div>
        <div className="setting-row-description">{description}</div>
      </div>
      <div className="setting-row-value">{value}</div>
    </div>
  )
}

function SettingActionRow({ label, description, action }: { label: string; description: string; action: ReactNode; key?: Key }) {
  return (
    <div className="setting-row">
      <div className="setting-row-copy">
        <div className="setting-row-title">{label}</div>
        <div className="setting-row-description">{description}</div>
      </div>
      <div>{action}</div>
    </div>
  )
}
