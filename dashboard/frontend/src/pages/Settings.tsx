/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { type Key, type ReactNode, useEffect, useMemo, useState } from 'react'
import { Badge, Card, PageHeader, PanelHeader } from '../components/ui.jsx'
import { commandCenterApi, type DashboardHealth, type DesktopPosture, type GatewayHealth, type JarvisConfig, type JarvisHealth } from '../lib/commandCenterApi'
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
  const [gateway, setGateway] = useState<GatewayHealth | null>(null)
  const [jarvisHealth, setJarvisHealth] = useState<JarvisHealth | null>(null)
  const [jarvisConfig, setJarvisConfig] = useState<JarvisConfig | null>(null)
  const [bundlePath, setBundlePath] = useState('')
  const [shellMode, setShellMode] = useState(false)
  const [serviceMessage, setServiceMessage] = useState('')
  const [busy, setBusy] = useState<string | null>(null)

  useEffect(() => {
    commandCenterApi.getHealth().then(setHealth).catch(() => null)
    commandCenterApi.getDesktopPosture().then(setPosture).catch(() => null)
    commandCenterApi.getGatewayHealth().then(setGateway).catch(() => null)
    commandCenterApi.getJarvisHealth().then(setJarvisHealth).catch(() => null)
    commandCenterApi.getJarvisConfig().then(setJarvisConfig).catch(() => null)
    desktopBridge.isDesktopShell().then(setShellMode).catch(() => setShellMode(false))
    const id = window.setInterval(() => {
      commandCenterApi.getGatewayHealth().then(setGateway).catch(() => null)
      commandCenterApi.getJarvisHealth().then(setJarvisHealth).catch(() => null)
      commandCenterApi.getJarvisConfig().then(setJarvisConfig).catch(() => null)
    }, 15000)
    return () => window.clearInterval(id)
  }, [])

  const runtimeRows = useMemo<[string, string][]>(() => [
    ['Dashboard host', String(health?.host ?? '127.0.0.1')],
    ['Dashboard port', String(health?.port ?? 7070)],
    ['Local only', health?.local_only ? 'Yes' : 'No'],
    ['Auth required', health?.auth_required ? 'Yes' : 'No'],
    ['Desktop shell', shellMode ? 'Connected' : 'Browser mode'],
    ['Launch on login', posture?.launch_on_login_enabled ? 'Enabled' : 'Disabled'],
    ['Autostart mode', String(posture?.autostart_kind ?? 'unknown')],
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
    <div className="fade-up" style={{ padding: '0 0 48px' }}>
      <div style={{ padding: '24px 20px 16px' }}>
        <PageHeader
          eyebrow="Settings"
          title="Desktop posture, grouped like a native settings app."
          description="Runtime controls, startup behavior, support tooling, and phone-bridge posture are collected into compact grouped sections with immediate feedback."
          meta={
            <>
              <Badge color={health?.auth_required ? 'green' : 'orange'}>{health?.auth_required ? 'Auth required' : 'Auth open'}</Badge>
              <Badge color={shellMode ? 'blue' : 'gray'}>{shellMode ? 'Desktop shell' : 'Browser mode'}</Badge>
              <Badge color={gateway?.whatsapp === 'linked' ? 'green' : gateway?.whatsapp === 'not linked' ? 'gray' : 'orange'}>
                {gateway?.whatsapp || 'WhatsApp unknown'}
              </Badge>
            </>
          }
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.12fr 0.88fr', gap: 16, padding: '0 20px' }}>
        <div style={{ display: 'grid', gap: 16 }}>
          <Card style={{ padding: 18 }}>
            <PanelHeader
              eyebrow="Runtime Profile"
              title="Current dashboard posture"
              description="The live host, auth, shell, and startup state for this command center instance."
            />
            <div className="setting-group">
              {runtimeRows.map(([label, value]) => (
                <SettingRow
                  key={label}
                  label={label}
                  description={runtimeDescription(label)}
                  value={String(value)}
                />
              ))}
            </div>
          </Card>

          <Card style={{ padding: 18 }}>
            <PanelHeader
              eyebrow="Runtime Control"
              title="Desktop-managed service actions"
              description="Native lifecycle controls appear automatically when Command Center is running inside the desktop shell."
              aside={<Badge color={shellMode ? 'green' : 'gray'}>{shellMode ? 'available' : 'desktop only'}</Badge>}
            />
            <div className="setting-group">
              <SettingActionRow
                label="Start services"
                description="Bring the desktop-managed stack online."
                action={<button className="btn sm" onClick={() => runServiceAction('start')} disabled={!shellMode || busy !== null}>Start</button>}
              />
              <SettingActionRow
                label="Restart services"
                description="Restart the managed services without leaving the dashboard."
                action={<button className="btn sm" onClick={() => runServiceAction('restart')} disabled={!shellMode || busy !== null}>Restart</button>}
              />
              <SettingActionRow
                label="Stop services"
                description="Stop the stack from the desktop shell when native controls are available."
                action={<button className="btn danger sm" onClick={() => runServiceAction('stop')} disabled={!shellMode || busy !== null}>Stop</button>}
              />
            </div>
          </Card>

          <JarvisVoiceCard health={jarvisHealth} config={jarvisConfig} />

          <ElevenLabsCard />
          <CalendarCard config={jarvisConfig} />

          <Card style={{ padding: 18 }}>
            <PanelHeader
              eyebrow="Startup"
              title="Launch on login"
              description="Use the platform-native startup mechanism for Linux, macOS, and the desktop image."
              aside={<Badge color={posture?.launch_on_login_enabled ? 'green' : 'gray'}>{posture?.launch_on_login_enabled ? 'enabled' : 'disabled'}</Badge>}
            />
            <div className="setting-group">
              <SettingRow
                label="Autostart behavior"
                description="Writes or removes the platform-native startup file for this machine."
                value={posture?.autostart_kind ?? 'unknown'}
              />
              <div className="setting-row">
                <div className="setting-row-copy">
                  <div className="setting-row-title">Launch on login</div>
                  <div className="setting-row-description">Toggle whether ClawOS should be ready as soon as you sign in.</div>
                </div>
                <button
                  className="btn"
                  onClick={toggleLaunchOnLogin}
                  disabled={busy !== null || !posture?.launch_on_login_supported}
                  style={{ minWidth: 92 }}
                >
                  <span className={`toggle${posture?.launch_on_login_enabled ? ' active' : ''}`} aria-hidden="true" />
                  <span>{posture?.launch_on_login_enabled ? 'On' : 'Off'}</span>
                </button>
              </div>
              {posture?.launch_on_login_path ? (
                <SettingRow
                  label="Autostart file"
                  description="The current platform-native file that controls startup behavior."
                  value={posture.launch_on_login_path}
                />
              ) : null}
            </div>
          </Card>
        </div>

        <div style={{ display: 'grid', gap: 16 }}>
          <Card style={{ padding: 18 }}>
            <PanelHeader
              eyebrow="Phone Bridge"
              title="WhatsApp connection posture"
              description="Connection state, routing posture, and the last observed activity for the personal command-center bridge."
              aside={<Badge color={gateway?.whatsapp === 'linked' ? 'green' : gateway?.whatsapp === 'not linked' ? 'gray' : 'orange'}>{gateway?.whatsapp || 'unknown'}</Badge>}
            />
            <div className="setting-group">
              <SettingRow label="Linked phone" description="The currently paired WhatsApp number for gatewayd." value={gateway?.linked_phone || 'Not linked'} />
              <SettingRow label="Routes" description="How many JID-to-workspace mappings are currently remembered." value={String(gateway?.routes_count ?? 0)} />
              <SettingRow label="Approval queue" description="Pending approvals that can be decided by replying yes or no from the paired phone." value={String(gateway?.approval_queue ?? 0)} />
              <SettingRow label="Last route" description="Most recent workspace selected for an inbound WhatsApp message." value={gateway?.last_workspace || 'No inbound traffic yet'} />
              <SettingRow label="Last activity" description="Latest observed WhatsApp message or bridge-side event." value={gateway?.last_message_at || gateway?.last_ready_at || 'Waiting for activity'} />
            </div>
            {gateway?.last_preview ? (
              <div className="log-terminal" style={{ marginTop: 12 }}>
                Last preview: {gateway.last_preview}
              </div>
            ) : null}
            {gateway?.last_disconnect_reason ? (
              <div style={{ marginTop: 10, fontSize: 12, color: 'var(--orange)' }}>
                Last disconnect reason: {gateway.last_disconnect_reason}
              </div>
            ) : null}
          </Card>

          <Card style={{ padding: 18 }}>
            <PanelHeader
              eyebrow="Support"
              title="Bundles and release channels"
              description="Quick access to the support-bundle flow and the current packaging targets."
            />
            <div className="setting-group">
              <SettingRow label="ISO" description="Bootable desktop image target." value="clawos-x.y.z-amd64.iso" />
              <SettingRow label="Linux desktop" description="Debian package target for desktop installs." value="clawos-command-center_x.y.z_amd64.deb" />
              <SettingRow label="macOS desktop" description="Desktop bundle target for Apple Silicon." value="ClawOS-Command-Center-x.y.z.dmg" />
              <SettingActionRow
                label="Support bundle"
                description="Create a diagnostics bundle from the desktop shell or dashboard API."
                action={<button className="btn primary sm" onClick={createBundle} disabled={busy !== null}>Create</button>}
              />
            </div>
            {bundlePath ? (
              <div style={{ marginTop: 10, fontSize: 12, color: 'var(--text-2)' }}>
                Bundle: <span className="mono">{bundlePath}</span>
              </div>
            ) : null}
          </Card>

          <Card style={{ padding: 18 }}>
            <PanelHeader
              eyebrow="Paths"
              title="Open known directories"
              description="Jump directly to the logs, config, workspace, or support folders that matter during debugging."
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

function runtimeDescription(label: string) {
  const descriptions: Record<string, string> = {
    'Dashboard host': 'The loopback or desktop-shell endpoint that serves the dashboard.',
    'Dashboard port': 'The port the frontend is expected to reach for health and API traffic.',
    'Local only': 'Whether the dashboard is restricted to the local machine or loopback trust boundary.',
    'Auth required': 'Whether the dashboard is protected by a session or bearer gate before actions run.',
    'Desktop shell': 'Shows whether native bridge features like path opening and service control are available.',
    'Launch on login': 'Reflects the persisted desktop posture rather than the current login session.',
    'Autostart mode': 'The platform-specific startup mechanism in use for this device.',
  }

  return descriptions[label] || 'Current runtime setting.'
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
        eyebrow="JARVIS Voice"
        title="Voice settings now live in the JARVIS chamber"
        description="JARVIS now owns OpenClaw routing, cinematic voice, and briefing posture. Manage provider selection, wake phrase, transcripts, and live voice state from the dedicated room."
        aside={
          <Badge color={health?.openclaw_running ? 'green' : 'orange'}>
            {health?.openclaw_running ? 'OpenClaw live' : 'OpenClaw unavailable'}
          </Badge>
        }
      />
      <div className="setting-group">
        <SettingRow
          label="Brain routing"
          description="JARVIS is separate from Nexus and routes through the shared OpenClaw main agent."
          value={health?.openclaw_running ? 'OpenClaw main agent' : 'Waiting for OpenClaw'}
        />
        <SettingRow
          label="Voice provider"
          description="ElevenLabs is primary for JARVIS, with Piper staying available as the fallback lane."
          value={health?.provider_status?.fallback ? `${activeProvider} (fallback)` : activeProvider}
        />
        <SettingRow
          label="Voice mode"
          description="Typed and spoken turns share the same JARVIS UI thread and answer out loud unless voice is turned off."
          value={voiceMode}
        />
        <SettingRow
          label="Briefing sources"
          description="Weather, headlines, calendar, tasks, and last-project context can mix live and demo sources in v1."
          value={briefingSources.length ? `${liveCount} live / ${demoCount} demo` : 'Loading status'}
        />
        <SettingActionRow
          label="JARVIS chamber"
          description="Open the dedicated voice room to configure ElevenLabs, Piper fallback, wake phrase, and the live transcript cockpit."
          action={<a className="btn primary sm" href="/jarvis">Open JARVIS</a>}
        />
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
        title="ElevenLabs JARVIS voice"
        description="Upgrade from Piper (offline) to a cinematic JARVIS voice. Paste your ElevenLabs API key — ClawOS wires the rest."
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
              width: '100%', background: 'var(--surface-2)', border: '1px solid var(--border)',
              borderRadius: 6, padding: '8px 12px', color: 'var(--text)', fontSize: 13,
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
              width: '100%', background: 'var(--surface-2)', border: '1px solid var(--border)',
              borderRadius: 6, padding: '8px 12px', color: 'var(--text)', fontSize: 13, fontFamily: 'monospace',
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
        eyebrow="JARVIS Briefing"
        title="Google Calendar"
        description="Connect your calendar so JARVIS reads your real schedule during morning briefings. No OAuth — just paste your secret ICS link."
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
              width: '100%', background: 'var(--surface-2)', border: '1px solid var(--border)',
              borderRadius: 6, padding: '8px 12px', color: 'var(--text)', fontSize: 12,
              fontFamily: 'monospace',
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
