import { useEffect, useMemo, useState } from 'react'
import { commandCenterApi, type DashboardHealth, type DesktopPosture } from '../lib/commandCenterApi'
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
  const [bundlePath, setBundlePath] = useState('')
  const [shellMode, setShellMode] = useState(false)
  const [serviceMessage, setServiceMessage] = useState('')
  const [busy, setBusy] = useState<string | null>(null)

  useEffect(() => {
    commandCenterApi.getHealth().then(setHealth).catch(() => null)
    commandCenterApi.getDesktopPosture().then(setPosture).catch(() => null)
    desktopBridge.isDesktopShell().then(setShellMode).catch(() => setShellMode(false))
  }, [])

  const runtimeRows = useMemo(
    () => [
      ['Dashboard host', health?.host ?? '127.0.0.1'],
      ['Dashboard port', health?.port ?? 7070],
      ['Local only', health?.local_only ? 'Yes' : 'No'],
      ['Auth required', health?.auth_required ? 'Yes' : 'No'],
      ['Desktop shell', shellMode ? 'Connected' : 'Browser mode'],
      ['Launch on login', posture?.launch_on_login_enabled ? 'Enabled' : 'Disabled'],
      ['Autostart mode', posture?.autostart_kind ?? 'unknown'],
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
          return
        }
      }
      const payload = await commandCenterApi.createSupportBundle()
      setBundlePath(payload.path || '')
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
    <div className="fade-up" style={{ padding: 24, display: 'grid', gap: 16 }}>
      <div>
        <div style={{ fontSize: 28, fontWeight: 700, letterSpacing: '-0.04em' }}>Settings</div>
        <div style={{ marginTop: 6, color: 'var(--text-3)' }}>
          Runtime, startup behavior, support posture, and desktop-shell control for ClawOS.
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.15fr 0.85fr', gap: 16 }}>
        <div className="glass" style={{ padding: 20 }}>
          <div className="section-label">Platform profile</div>
          <div style={{ display: 'grid', gap: 14 }}>
            {runtimeRows.map(([label, value]) => (
              <div key={label} style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                <span style={{ color: 'var(--text-3)' }}>{label}</span>
                <span className="mono">{String(value)}</span>
              </div>
            ))}
          </div>

          <div style={{ marginTop: 24 }}>
            <div className="section-label">Runtime control</div>
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
          </div>

          <div style={{ marginTop: 24 }}>
            <div className="section-label">Launch on login</div>
            <div style={{ display: 'grid', gap: 10 }}>
              <div style={{ color: 'var(--text-3)', fontSize: 13 }}>
                Keep Command Center ready after login on Linux, macOS, and the ClawOS desktop image.
              </div>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                <button className="btn" onClick={toggleLaunchOnLogin} disabled={busy !== null || !posture?.launch_on_login_supported}>
                  {posture?.launch_on_login_enabled ? 'Disable launch on login' : 'Enable launch on login'}
                </button>
              </div>
              {posture?.launch_on_login_path && (
                <div style={{ fontSize: 12, color: 'var(--text-3)' }}>
                  Autostart file: <span className="mono">{posture.launch_on_login_path}</span>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="glass" style={{ padding: 20 }}>
          <div className="section-label">Support and paths</div>
          <div style={{ display: 'grid', gap: 10, fontSize: 13 }}>
            <div><strong>ISO</strong><div style={{ color: 'var(--text-3)' }}>clawos-x.y.z-amd64.iso</div></div>
            <div><strong>Linux desktop</strong><div style={{ color: 'var(--text-3)' }}>clawos-command-center_x.y.z_amd64.deb</div></div>
            <div><strong>macOS desktop</strong><div style={{ color: 'var(--text-3)' }}>ClawOS-Command-Center-x.y.z.dmg</div></div>
          </div>

          <div style={{ marginTop: 18, display: 'grid', gap: 10 }}>
            <button className="btn" onClick={createBundle} disabled={busy !== null}>
              Create support bundle
            </button>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <button className="btn" onClick={() => openKnownPath('logs')} disabled={busy !== null}>Logs</button>
              <button className="btn" onClick={() => openKnownPath('config')} disabled={busy !== null}>Config</button>
              <button className="btn" onClick={() => openKnownPath('workspace')} disabled={busy !== null}>Workspace</button>
              <button className="btn" onClick={() => openKnownPath('support')} disabled={busy !== null}>Support</button>
            </div>
            {bundlePath && (
              <div style={{ fontSize: 12, color: 'var(--text-3)' }}>
                Bundle: <span className="mono">{bundlePath}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {serviceMessage && (
        <div className="glass" style={{ padding: 16, color: 'var(--text-2)', fontSize: 13 }}>
          {serviceMessage}
        </div>
      )}
    </div>
  )
}
