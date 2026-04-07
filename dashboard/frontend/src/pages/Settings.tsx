/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { useEffect, useMemo, useState } from 'react'
import { Badge, Card, PageHeader, PanelHeader } from '../components/ui.jsx'
import { commandCenterApi, type DashboardHealth, type DesktopPosture, type GatewayHealth } from '../lib/commandCenterApi'
import { desktopBridge } from '../desktop/bridge'

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
  const [bundlePath, setBundlePath] = useState('')
  const [shellMode, setShellMode] = useState(false)
  const [serviceMessage, setServiceMessage] = useState('')
  const [busy, setBusy] = useState<string | null>(null)

  useEffect(() => {
    commandCenterApi.getHealth().then(setHealth).catch(() => null)
    commandCenterApi.getDesktopPosture().then(setPosture).catch(() => null)
    commandCenterApi.getGatewayHealth().then(setGateway).catch(() => null)
    desktopBridge.isDesktopShell().then(setShellMode).catch(() => setShellMode(false))
    const id = window.setInterval(() => {
      commandCenterApi.getGatewayHealth().then(setGateway).catch(() => null)
    }, 15000)
    return () => window.clearInterval(id)
  }, [])

  const runtimeRows = useMemo<[string, string][]>(
    () => [
      ['Dashboard host', String(health?.host ?? '127.0.0.1')],
      ['Dashboard port', String(health?.port ?? 7070)],
      ['Local only', health?.local_only ? 'Yes' : 'No'],
      ['Auth required', health?.auth_required ? 'Yes' : 'No'],
      ['Desktop shell', shellMode ? 'Connected' : 'Browser mode'],
      ['Launch on login', posture?.launch_on_login_enabled ? 'Enabled' : 'Disabled'],
      ['Autostart mode', String(posture?.autostart_kind ?? 'unknown')],
    ],
    [health, posture, shellMode],
  )

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
      <div style={{ padding: '32px 24px 18px' }}>
        <PageHeader
          eyebrow="Settings"
          title="Runtime, startup, and support posture."
          description="Every control here is grouped by purpose, carries a clear description, and returns feedback immediately when something changes."
          meta={
            <>
              <Badge color={health?.auth_required ? 'green' : 'orange'}>{health?.auth_required ? 'Auth required' : 'Auth open'}</Badge>
              <Badge color={shellMode ? 'blue' : 'gray'}>{shellMode ? 'Desktop shell' : 'Browser mode'}</Badge>
              <Badge color={gateway?.whatsapp === 'linked' ? 'green' : gateway?.whatsapp === 'not linked' ? 'gray' : 'orange'}>
                {gateway?.whatsapp || 'WhatsApp unknown'}
              </Badge>
              <Badge color={posture?.launch_on_login_enabled ? 'green' : 'gray'}>
                {posture?.launch_on_login_enabled ? 'Launch on login on' : 'Launch on login off'}
              </Badge>
            </>
          }
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.15fr 0.85fr', gap: 16, padding: '0 20px' }}>
        <div style={{ display: 'grid', gap: 16 }}>
          <Card style={{ padding: 20 }}>
            <PanelHeader
              eyebrow="Runtime profile"
              title="Current dashboard posture"
              description="The live host, auth, and startup state for this Command Center instance."
            />
            <div style={{ display: 'grid', gap: 12 }}>
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

          <Card style={{ padding: 20 }}>
            <PanelHeader
              eyebrow="Runtime control"
              title="Service actions"
              description="Start, restart, or stop the desktop-managed stack when the native shell is available."
              aside={<Badge color={shellMode ? 'green' : 'gray'}>{shellMode ? 'available' : 'desktop only'}</Badge>}
            />
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <button className="btn" onClick={() => runServiceAction('start')} disabled={!shellMode || busy !== null}>Start</button>
              <button className="btn" onClick={() => runServiceAction('restart')} disabled={!shellMode || busy !== null}>Restart</button>
              <button className="btn" onClick={() => runServiceAction('stop')} disabled={!shellMode || busy !== null}>Stop</button>
            </div>
            {!shellMode && (
              <div style={{ marginTop: 10, fontSize: 12, color: 'var(--text-3)' }}>
                Native service controls appear automatically when Command Center is running inside the desktop shell.
              </div>
            )}
          </Card>

          <Card style={{ padding: 20 }}>
            <PanelHeader
              eyebrow="Startup"
              title="Launch on login"
              description="Keep Command Center ready after login on Linux, macOS, and the ClawOS desktop image."
              aside={<Badge color={posture?.launch_on_login_enabled ? 'green' : 'gray'}>{posture?.launch_on_login_enabled ? 'enabled' : 'disabled'}</Badge>}
            />
            <div style={{ display: 'grid', gap: 12 }}>
              <SettingRow
                label="Autostart behavior"
                description="Writes or removes the platform-native startup file for this machine."
                value={posture?.autostart_kind ?? 'unknown'}
              />
              <button className="btn primary" onClick={toggleLaunchOnLogin} disabled={busy !== null || !posture?.launch_on_login_supported}>
                {posture?.launch_on_login_enabled ? 'Disable launch on login' : 'Enable launch on login'}
              </button>
              {posture?.launch_on_login_path && (
                <div style={{ fontSize: 12, color: 'var(--text-3)' }}>
                  Autostart file: <span className="mono">{posture.launch_on_login_path}</span>
                </div>
              )}
            </div>
          </Card>
        </div>

        <div style={{ display: 'grid', gap: 16 }}>
          <Card style={{ padding: 20 }}>
            <PanelHeader
              eyebrow="Phone bridge"
              title="WhatsApp connection posture"
              description="Connection state, routing posture, and the last observed activity for the personal command-center bridge."
              aside={<Badge color={gateway?.whatsapp === 'linked' ? 'green' : gateway?.whatsapp === 'not linked' ? 'gray' : 'orange'}>{gateway?.whatsapp || 'unknown'}</Badge>}
            />
            <div style={{ display: 'grid', gap: 12 }}>
              <SettingRow label="Linked phone" description="The currently paired WhatsApp number for gatewayd." value={gateway?.linked_phone || 'Not linked'} />
              <SettingRow label="Routes" description="How many JID-to-workspace mappings are currently remembered." value={String(gateway?.routes_count ?? 0)} />
              <SettingRow label="Approval queue" description="Pending approvals that can be decided by replying yes or no from the paired phone." value={String(gateway?.approval_queue ?? 0)} />
              <SettingRow label="Last route" description="Most recent workspace selected for an inbound WhatsApp message." value={gateway?.last_workspace || 'No inbound traffic yet'} />
              <SettingRow label="Last activity" description="Latest observed WhatsApp message or bridge-side event." value={gateway?.last_message_at || gateway?.last_ready_at || 'Waiting for activity'} />
              {gateway?.last_preview ? (
                <div style={{ fontSize: 12, color: 'var(--text-3)', lineHeight: 1.6 }}>
                  Last preview: <span className="mono">{gateway.last_preview}</span>
                </div>
              ) : null}
              {gateway?.last_disconnect_reason ? (
                <div style={{ fontSize: 12, color: 'var(--orange)' }}>
                  Last disconnect reason: {gateway.last_disconnect_reason}
                </div>
              ) : null}
            </div>
          </Card>

          <Card style={{ padding: 20 }}>
            <PanelHeader
              eyebrow="Support"
              title="Bundles and release channels"
              description="Quick access to the support bundle flow and the current packaging targets."
            />
            <div style={{ display: 'grid', gap: 10, fontSize: 13 }}>
              <ArtifactRow label="ISO" value="clawos-x.y.z-amd64.iso" />
              <ArtifactRow label="Linux desktop" value="clawos-command-center_x.y.z_amd64.deb" />
              <ArtifactRow label="macOS desktop" value="ClawOS-Command-Center-x.y.z.dmg" />
            </div>
            <div style={{ marginTop: 16, display: 'grid', gap: 10 }}>
              <button className="btn primary" onClick={createBundle} disabled={busy !== null}>
                Create support bundle
              </button>
              {bundlePath && (
                <div style={{ fontSize: 12, color: 'var(--text-3)' }}>
                  Bundle: <span className="mono">{bundlePath}</span>
                </div>
              )}
            </div>
          </Card>

          <Card style={{ padding: 20 }}>
            <PanelHeader
              eyebrow="Paths"
              title="Open known directories"
              description="Jump directly to the logs, config, workspace, or support folders that matter during debugging."
            />
            <div style={{ display: 'grid', gap: 10 }}>
              {(Object.keys(PATH_LABELS) as PathKind[]).map((kind) => (
                <div
                  key={kind}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: 12,
                    padding: '12px 14px',
                    borderRadius: 14,
                    background: 'var(--surface-2)',
                    border: '1px solid var(--border)',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600 }}>{PATH_LABELS[kind]}</div>
                    <div style={{ color: 'var(--text-3)', fontSize: 12, marginTop: 4 }}>
                      {posture?.paths?.[kind] || 'Not available yet'}
                    </div>
                  </div>
                  <button className="btn" onClick={() => openKnownPath(kind)} disabled={busy !== null}>Open</button>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>

      {serviceMessage && (
        <div style={{ padding: '16px 20px 0' }}>
          <Card style={{ padding: 16, color: 'var(--text-2)', fontSize: 13 }}>
            {serviceMessage}
          </Card>
        </div>
      )}
    </div>
  )
}

function runtimeDescription(label: string) {
  const descriptions: Record<string, string> = {
    'Dashboard host': 'The loopback or desktop shell endpoint that serves the dashboard.',
    'Dashboard port': 'The port the frontend is expected to reach for health and API traffic.',
    'Local only': 'Whether the dashboard is restricted to the local machine or loopback trust boundary.',
    'Auth required': 'Whether the dashboard is protected by a session or bearer gate before actions run.',
    'Desktop shell': 'Shows whether native bridge features like path opening and service control are available.',
    'Launch on login': 'Reflects the persisted desktop posture rather than the current login session.',
    'Autostart mode': 'The platform-specific startup mechanism in use for this device.',
  }

  return descriptions[label] || 'Current runtime setting.'
}

function SettingRow({ label, description, value }: { label: string; description: string; value: string }) {
  return (
    <div style={{ padding: '12px 14px', borderRadius: 14, background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ fontWeight: 600 }}>{label}</div>
        <div className="mono">{value}</div>
      </div>
      <div style={{ marginTop: 6, color: 'var(--text-3)', fontSize: 12, lineHeight: 1.55 }}>{description}</div>
    </div>
  )
}

function ArtifactRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ padding: '12px 14px', borderRadius: 14, background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
      <div style={{ fontWeight: 600 }}>{label}</div>
      <div className="mono" style={{ marginTop: 4, color: 'var(--text-3)', fontSize: 12 }}>{value}</div>
    </div>
  )
}
