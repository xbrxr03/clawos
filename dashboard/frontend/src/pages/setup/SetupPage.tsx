import { useEffect, useMemo, useState } from 'react'
import {
  commandCenterApi,
  type OpenClawImportManifest,
  type ProviderProfile,
  type SetupDiagnostics,
  type SetupPlan,
  type SetupState,
  type UseCasePack,
} from '../../lib/commandCenterApi'

const TONE_PRESETS = [
  {
    id: 'crisp-executive',
    label: 'Crisp executive',
    body: 'Short, elegant, high-competence answers with minimal filler.',
  },
  {
    id: 'warm-concierge',
    label: 'Warm concierge',
    body: 'More human and reassuring, but still premium and efficient.',
  },
  {
    id: 'technical-operator',
    label: 'Technical operator',
    body: 'System-oriented, explicit, and more literal in tone.',
  },
]

const VOICE_MODES = [
  { id: 'off', label: 'Off', body: 'Quiet visual interaction only.' },
  { id: 'push_to_talk', label: 'Push-to-talk', body: 'Best default for precise control.' },
  { id: 'wake_word', label: 'Wake word', body: 'Ambient readiness with explicit trigger.' },
  { id: 'continuous', label: 'Continuous', body: 'Open follow-up window for active sessions.' },
]

const AUTONOMY_MODES = [
  {
    id: 'mostly-autonomous',
    label: 'Mostly autonomous',
    body: 'Act inside trusted lanes and interrupt only when something meaningful needs you.',
  },
  {
    id: 'trusted-routines',
    label: 'Trusted routines',
    body: 'Run approved routines automatically, but stay conservative elsewhere.',
  },
  {
    id: 'approval-first',
    label: 'Approval first',
    body: 'Recommend and prepare, then wait for you before acting.',
  },
]

const GOAL_OPTIONS = [
  'daily briefing',
  'meeting prep',
  'inbox triage',
  'travel readiness',
  'research memos',
  'reminders',
]

const QUIET_HOUR_PRESETS = [
  { id: 'standard', label: '22:00 to 07:00', start: '22:00', end: '07:00' },
  { id: 'late', label: '00:00 to 08:00', start: '00:00', end: '08:00' },
  { id: 'always-on', label: 'No quiet hours', start: '00:00', end: '00:00' },
]

export function SetupPage() {
  const [state, setState] = useState<SetupState | null>(null)
  const [plan, setPlan] = useState<SetupPlan | null>(null)
  const [diagnostics, setDiagnostics] = useState<SetupDiagnostics | null>(null)
  const [packs, setPacks] = useState<UseCasePack[]>([])
  const [providers, setProviders] = useState<ProviderProfile[]>([])
  const [importManifest, setImportManifest] = useState<OpenClawImportManifest | null>(null)
  const [bundlePath, setBundlePath] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const loadState = async () => {
    try {
      setState(await commandCenterApi.getSetupState())
    } catch (err: any) {
      setError(err.message || 'Failed to load setup state')
    }
  }

  const loadDiagnostics = async () => {
    try {
      setDiagnostics(await commandCenterApi.getSetupDiagnostics())
    } catch {}
  }

  const loadCatalog = async () => {
    try {
      const [packData, providerData] = await Promise.all([commandCenterApi.listPacks(), commandCenterApi.listProviders()])
      setPacks(Array.isArray(packData) ? packData : [])
      setProviders(Array.isArray(providerData) ? providerData : [])
    } catch {}
  }

  useEffect(() => {
    loadState()
    loadDiagnostics()
    loadCatalog()
  }, [])

  useEffect(() => {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const socket = new WebSocket(`${proto}://${window.location.host}/ws/setup?setup=1`)
    const keepalive = window.setInterval(() => {
      if (socket.readyState === WebSocket.OPEN) socket.send('ping')
    }, 15000)

    socket.onmessage = ({ data }) => {
      try {
        const message = JSON.parse(data)
        if (message.type === 'setup_state') {
          setState(message.data)
          if (message.data?.plan_steps?.length) {
            setPlan((current: SetupPlan | null) => current || { steps: message.data.plan_steps })
          }
        }
      } catch {}
    }

    return () => {
      window.clearInterval(keepalive)
      socket.close()
    }
  }, [])

  const hardwareSummary = useMemo(() => {
    if (!state?.detected_hardware) return 'Detecting this machine'
    const hardware = state.detected_hardware
    return `${hardware.summary || `Tier ${hardware.tier || 'B'}`} - ${hardware.ram_gb || '?'} GB RAM - ${hardware.gpu_name || 'CPU only'}`
  }, [state])

  const request = async (action: 'plan' | 'apply' | 'retry' | 'repair') => {
    setBusy(true)
    setError('')
    try {
      if (action === 'plan') setPlan(await commandCenterApi.planSetup())
      if (action === 'apply') await commandCenterApi.applySetup()
      if (action === 'retry') await commandCenterApi.retrySetup()
      if (action === 'repair') await commandCenterApi.repairSetup()
      await loadState()
    } catch (err: any) {
      setError(err.message || `Request failed for ${action}`)
    } finally {
      setBusy(false)
    }
  }

  const inspectSetup = async () => {
    setBusy(true)
    setError('')
    try {
      const payload = await commandCenterApi.inspectSetup()
      if (payload.state) setState(payload.state)
      if (payload.openclaw) setImportManifest(payload.openclaw)
      await loadCatalog()
    } catch (err: any) {
      setError(err.message || 'Failed to inspect setup posture')
    } finally {
      setBusy(false)
    }
  }

  const savePresence = async (body: Record<string, unknown>) => {
    setBusy(true)
    setError('')
    try {
      const next = await commandCenterApi.updateSetupPresence(body)
      setState(next)
    } catch (err: any) {
      setError(err.message || 'Failed to update Nexus presence')
    } finally {
      setBusy(false)
    }
  }

  const saveAutonomy = async (body: Record<string, unknown>) => {
    setBusy(true)
    setError('')
    try {
      const next = await commandCenterApi.updateSetupAutonomy(body)
      setState(next)
    } catch (err: any) {
      setError(err.message || 'Failed to update autonomy policy')
    } finally {
      setBusy(false)
    }
  }

  const selectPack = async (packId: string) => {
    setBusy(true)
    setError('')
    try {
      const next = await commandCenterApi.selectSetupPack(packId, state?.secondary_packs || [], state?.selected_provider_profile || '')
      setState(next)
      await loadCatalog()
    } catch (err: any) {
      setError(err.message || 'Failed to select a pack')
    } finally {
      setBusy(false)
    }
  }

  const selectProvider = async (providerId: string) => {
    setBusy(true)
    setError('')
    try {
      await commandCenterApi.switchProvider(providerId)
      await loadState()
      await loadCatalog()
    } catch (err: any) {
      setError(err.message || 'Failed to select a provider')
    } finally {
      setBusy(false)
    }
  }

  const importOpenClaw = async () => {
    setBusy(true)
    setError('')
    try {
      const manifest = await commandCenterApi.importOpenClaw()
      setImportManifest(manifest)
      await loadState()
      await loadCatalog()
    } catch (err: any) {
      setError(err.message || 'Failed to inspect OpenClaw compatibility')
    } finally {
      setBusy(false)
    }
  }

  const createBundle = async () => {
    setBusy(true)
    setError('')
    try {
      const response = await commandCenterApi.createSupportBundle()
      setBundlePath(response.path || '')
    } catch (err: any) {
      setError(err.message || 'Failed to create support bundle')
    } finally {
      setBusy(false)
    }
  }

  const toggleGoal = async (goal: string) => {
    const current = new Set(state?.primary_goals || [])
    if (current.has(goal)) current.delete(goal)
    else current.add(goal)
    await savePresence({ primary_goals: Array.from(current) })
  }

  const effectivePlan = plan?.steps?.length
    ? plan
    : state?.plan_steps?.length
      ? {
          steps: state.plan_steps,
          summary: `Bring Nexus online for ${state.primary_pack || 'daily-briefing-os'} on ${state.platform || 'this machine'}`,
        }
      : null

  const stageColor =
    state?.progress_stage === 'complete'
      ? 'green'
      : state?.progress_stage === 'error'
        ? 'red'
        : state?.progress_stage === 'applying'
          ? 'blue'
          : 'gray'

  const tone = state?.presence_profile?.tone || 'crisp-executive'
  const autonomyMode = state?.autonomy_policy?.mode || 'mostly-autonomous'
  const quietHours = state?.quiet_hours || state?.autonomy_policy?.quiet_hours || { start: '22:00', end: '07:00' }
  const voiceMode = state?.voice_mode || 'push_to_talk'

  return (
    <div
      className="fade-up"
      style={{
        minHeight: '100vh',
        display: 'grid',
        placeItems: 'center',
        padding: 32,
        background:
          'radial-gradient(circle at top left, rgba(77,143,247,0.24), transparent 30%), radial-gradient(circle at bottom right, rgba(88,210,212,0.18), transparent 24%)',
      }}
    >
      <div
        style={{
          width: 'min(1180px, 100%)',
          display: 'grid',
          gridTemplateColumns: '1.15fr 0.85fr',
          gap: 20,
          padding: 20,
          borderRadius: 28,
          border: '1px solid var(--border)',
          background: 'var(--panel)',
          boxShadow: 'var(--shadow-window)',
          backdropFilter: 'blur(18px)',
        }}
      >
        <div className="glass" style={{ padding: 28 }}>
          <div className="section-label">ClawOS Setup</div>
          <div style={{ fontSize: 34, fontWeight: 700, letterSpacing: '-0.05em', lineHeight: 1.08 }}>
            Bring Nexus online for this machine.
          </div>
          <div style={{ marginTop: 12, fontSize: 15, color: 'var(--text-3)', maxWidth: 580 }}>
            Device onboarding for a calm, conversational operator that prepares, acts, and only interrupts when something meaningful changes.
          </div>

          <div style={{ marginTop: 28, display: 'grid', gap: 16 }}>
            <div className="glass" style={{ padding: 18 }}>
              <div className="section-label">Machine posture</div>
              <div style={{ fontSize: 16, fontWeight: 600 }}>{hardwareSummary}</div>
              <div style={{ marginTop: 8, color: 'var(--text-3)' }}>
                Recommended profile: <span className="mono">{state?.recommended_profile || 'balanced'}</span>
              </div>
            </div>

            <div className="glass" style={{ padding: 18 }}>
              <div className="section-label">Nexus identity</div>
              <div style={{ fontSize: 18, fontWeight: 600 }}>Nexus</div>
              <div style={{ marginTop: 8, color: 'var(--text-3)', fontSize: 13 }}>
                ClawOS is the platform. Nexus is the assistant persona users speak to, delegate to, and read from.
              </div>
            </div>

            <div className="glass" style={{ padding: 18 }}>
              <div className="section-label">Speech style</div>
              <div style={{ display: 'grid', gap: 10, marginTop: 10 }}>
                {TONE_PRESETS.map((preset) => (
                  <button
                    key={preset.id}
                    className={`btn${tone === preset.id ? ' primary' : ''}`}
                    onClick={() => savePresence({ presence_profile: { tone: preset.id }, assistant_identity: 'Nexus' })}
                    disabled={busy}
                    style={{ justifyContent: 'space-between', display: 'flex', alignItems: 'center' }}
                  >
                    <span>{preset.label}</span>
                    <span className="mono" style={{ fontSize: 11, color: 'var(--text-3)' }}>
                      {preset.body}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            <div className="glass" style={{ padding: 18 }}>
              <div className="section-label">Voice mode</div>
              <div style={{ display: 'grid', gap: 10, marginTop: 10 }}>
                {VOICE_MODES.map((mode) => (
                  <button
                    key={mode.id}
                    className={`btn${voiceMode === mode.id ? ' primary' : ''}`}
                    onClick={() => savePresence({ voice_mode: mode.id, presence_profile: { preferred_voice_mode: mode.id } })}
                    disabled={busy}
                    style={{ justifyContent: 'space-between', display: 'flex', alignItems: 'center' }}
                  >
                    <span>{mode.label}</span>
                    <span className="mono" style={{ fontSize: 11, color: 'var(--text-3)' }}>
                      {mode.body}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            <div className="glass" style={{ padding: 18 }}>
              <div className="section-label">Autonomy comfort</div>
              <div style={{ display: 'grid', gap: 10, marginTop: 10 }}>
                {AUTONOMY_MODES.map((mode) => (
                  <button
                    key={mode.id}
                    className={`btn${autonomyMode === mode.id ? ' primary' : ''}`}
                    onClick={() => saveAutonomy({ autonomy_policy: { mode: mode.id } })}
                    disabled={busy}
                    style={{ justifyContent: 'space-between', display: 'flex', alignItems: 'center' }}
                  >
                    <span>{mode.label}</span>
                    <span className="mono" style={{ fontSize: 11, color: 'var(--text-3)' }}>
                      {mode.body}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            <div className="glass" style={{ padding: 18 }}>
              <div className="section-label">Primary goals</div>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 10 }}>
                {GOAL_OPTIONS.map((goal) => {
                  const selected = (state?.primary_goals || []).includes(goal)
                  return (
                    <button
                      key={goal}
                      className={`btn${selected ? ' primary' : ''}`}
                      onClick={() => toggleGoal(goal)}
                      disabled={busy}
                    >
                      {goal}
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="glass" style={{ padding: 18 }}>
              <div className="section-label">Quiet hours</div>
              <div style={{ display: 'grid', gap: 10, marginTop: 10 }}>
                {QUIET_HOUR_PRESETS.map((preset) => {
                  const selected = quietHours?.start === preset.start && quietHours?.end === preset.end
                  return (
                    <button
                      key={preset.id}
                      className={`btn${selected ? ' primary' : ''}`}
                      onClick={() => saveAutonomy({ quiet_hours: { start: preset.start, end: preset.end } })}
                      disabled={busy}
                      style={{ justifyContent: 'space-between', display: 'flex' }}
                    >
                      <span>{preset.label}</span>
                      <span className="mono" style={{ fontSize: 11 }}>{preset.start} - {preset.end}</span>
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="glass" style={{ padding: 18 }}>
              <div className="section-label">Primary pack</div>
              <div style={{ display: 'grid', gap: 10, marginTop: 10 }}>
                {packs.slice(0, 4).map((pack) => (
                  <button
                    key={pack.id}
                    className={`btn${state?.primary_pack === pack.id ? ' primary' : ''}`}
                    onClick={() => selectPack(pack.id)}
                    disabled={busy}
                    style={{ justifyContent: 'space-between', display: 'flex' }}
                  >
                    <span>{pack.name}</span>
                    <span className="mono" style={{ fontSize: 11 }}>{pack.wave}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="glass" style={{ padding: 18 }}>
              <div className="section-label">Provider posture</div>
              <div style={{ display: 'grid', gap: 10, marginTop: 10 }}>
                {providers.slice(0, 4).map((provider) => (
                  <button
                    key={provider.id}
                    className={`btn${state?.selected_provider_profile === provider.id ? ' primary' : ''}`}
                    onClick={() => selectProvider(provider.id)}
                    disabled={busy}
                    style={{ justifyContent: 'space-between', display: 'flex' }}
                  >
                    <span>{provider.name}</span>
                    <span className="mono" style={{ fontSize: 11 }}>{provider.status || provider.kind}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="glass" style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="section-label">Execution</div>
          <div style={{ fontSize: 18, fontWeight: 600 }}>Bring Nexus online</div>
          <div style={{ color: 'var(--text-3)' }}>
            {effectivePlan?.summary || 'Inspect the machine, shape Nexus presence, then bring the command center online.'}
          </div>

          <div className="glass" style={{ padding: 14 }}>
            <div className="section-label">Selected defaults</div>
            <div style={{ display: 'grid', gap: 10, marginTop: 10 }}>
              <Row label="Assistant" value={state?.assistant_identity || 'Nexus'} />
              <Row label="Tone" value={tone} />
              <Row label="Voice mode" value={voiceMode} />
              <Row label="Autonomy" value={autonomyMode} />
              <Row label="Pack" value={state?.primary_pack || 'daily-briefing-os'} />
              <Row label="Provider" value={state?.selected_provider_profile || 'local-ollama'} />
              <Row label="Goals" value={(state?.primary_goals || []).join(', ') || 'daily briefing'} />
              <Row label="Quiet hours" value={`${quietHours?.start || '22:00'} - ${quietHours?.end || '07:00'}`} />
              <Row label="Briefing" value={state?.briefing_enabled === false ? 'Disabled' : 'Enabled'} />
              <Row label="Launch on login" value={state?.launch_on_login === false ? 'Disabled' : 'Enabled'} />
            </div>
          </div>

          {effectivePlan?.steps?.length ? (
            <div className="glass" style={{ padding: 14 }}>
              <div style={{ display: 'grid', gap: 10 }}>
                {effectivePlan.steps.map((step, index) => (
                  <div key={`${step}-${index}`} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                    <span
                      style={{
                        width: 22,
                        height: 22,
                        borderRadius: 999,
                        display: 'grid',
                        placeItems: 'center',
                        background: 'var(--surface-3)',
                        color: 'var(--text-2)',
                        fontSize: 11,
                        flexShrink: 0,
                      }}
                    >
                      {index + 1}
                    </span>
                    <div style={{ color: 'var(--text-2)' }}>{step}</div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{
                width:
                  state?.completion_marker
                    ? '100%'
                    : state?.progress_stage === 'applying'
                      ? '68%'
                      : effectivePlan
                        ? '38%'
                        : '10%',
              }}
            />
          </div>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: 12,
              fontSize: 12,
              color: 'var(--text-3)',
            }}
          >
            <div>
              Stage: <span className="mono">{state?.progress_stage || 'idle'}</span>
            </div>
            <span className={`pill ${stageColor}`}>{state?.completion_marker ? 'Ready' : state?.progress_stage || 'idle'}</span>
          </div>

          <div style={{ display: 'grid', gap: 10 }}>
            <button className="btn" onClick={inspectSetup} disabled={busy}>
              Inspect Machine
            </button>
            <button className="btn" onClick={() => request('plan')} disabled={busy}>
              Build Launch Plan
            </button>
            <button className="btn" onClick={importOpenClaw} disabled={busy}>
              Import OpenClaw
            </button>
            <button className="btn primary" onClick={() => request('apply')} disabled={busy}>
              Apply Setup
            </button>
            <button className="btn" onClick={() => request('retry')} disabled={busy}>
              Retry Last Step
            </button>
            <button className="btn" onClick={() => request('repair')} disabled={busy}>
              Repair Runtime
            </button>
            <button
              className="btn"
              onClick={() => savePresence({ briefing_enabled: !(state?.briefing_enabled !== false) })}
              disabled={busy}
            >
              {state?.briefing_enabled === false ? 'Enable first briefing' : 'Disable first briefing'}
            </button>
            <button className="btn" onClick={createBundle} disabled={busy}>
              Create Support Bundle
            </button>
          </div>

          {error && (
            <div className="glass" style={{ padding: 14, borderColor: 'rgba(255,107,107,0.25)', color: 'var(--red)' }}>
              {error}
            </div>
          )}

          {state?.last_error && (
            <div className="glass" style={{ padding: 14, borderColor: 'rgba(255,107,107,0.25)' }}>
              <div className="section-label">Last setup error</div>
              <div style={{ color: 'var(--red)', marginTop: 6 }}>{state.last_error}</div>
            </div>
          )}

          {importManifest && (
            <div className="glass" style={{ padding: 14 }}>
              <div className="section-label">OpenClaw rescue</div>
              <div style={{ display: 'grid', gap: 8, marginTop: 6, color: 'var(--text-2)' }}>
                <div>Version: <span className="mono">{importManifest.detected_version || 'not found'}</span></div>
                <div>Suggested pack: <span className="mono">{importManifest.suggested_primary_pack || 'daily-briefing-os'}</span></div>
                <div>Providers: <span className="mono">{(importManifest.providers || []).join(', ') || 'none detected'}</span></div>
                <div>Channels: <span className="mono">{(importManifest.channels || []).join(', ') || 'none detected'}</span></div>
              </div>
            </div>
          )}

          <div className="glass" style={{ padding: 14 }}>
            <div className="section-label">Machine profile</div>
            <div style={{ display: 'grid', gap: 8, marginTop: 6, color: 'var(--text-2)' }}>
              <div>Platform: <span className="mono">{diagnostics?.platform || state?.platform || 'local'}</span></div>
              <div>Service manager: <span className="mono">{diagnostics?.service_manager || state?.service_manager || 'auto'}</span></div>
              <div>Install channel: <span className="mono">{state?.install_channel || 'desktop'}</span></div>
              <div>Architecture: <span className="mono">{state?.architecture || 'unknown'}</span></div>
            </div>
          </div>

          {bundlePath && (
            <div className="glass" style={{ padding: 14 }}>
              <div className="section-label">Support bundle</div>
              <div className="mono" style={{ fontSize: 12 }}>{bundlePath}</div>
            </div>
          )}

          <div className="glass" style={{ padding: 16, minHeight: 200 }}>
            <div className="section-label">Log tail</div>
            <div className="mono" style={{ fontSize: 12, color: 'var(--text-2)', display: 'grid', gap: 8 }}>
              {(state?.logs || ['Setup has not started yet.']).slice(-8).map((entry, index) => (
                <div key={`${entry}-${index}`}>{entry}</div>
              ))}
            </div>
          </div>

          {state?.completion_marker && (
            <a className="btn primary" href="/" style={{ textDecoration: 'none' }}>
              Open Nexus
            </a>
          )}
        </div>
      </div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
      <span style={{ color: 'var(--text-3)' }}>{label}</span>
      <span className="mono">{value}</span>
    </div>
  )
}
