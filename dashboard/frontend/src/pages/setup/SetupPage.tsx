/* SPDX-License-Identifier: AGPL-3.0-or-later */
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
import { Badge, Card, LoadingPanel, PanelHeader, ShortcutKey } from '../../components/ui.jsx'

const STEPS = [
  ['welcome', 'Welcome', 'Meet ClawOS and start the first-run flow.'],
  ['hardware', 'Hardware', 'Confirm what this machine can do.'],
  ['packs', 'Pack', 'Choose the outcome pack for your first workspace.'],
  ['providers', 'Provider', 'Default to local Ollama, or pick cloud posture.'],
  ['model', 'Model', 'Prepare the primary model with live progress.'],
  ['voice', 'Voice', 'Enable, skip, or tune the voice posture.'],
  ['whatsapp', 'WhatsApp', 'Prepare the phone bridge path or skip it cleanly.'],
  ['summary', 'Summary', 'Review the plan, then bring ClawOS online.'],
] as const

const MODEL_OPTIONS = [
  ['gemma3:4b', 'Best default — runs on 8 GB RAM, no GPU needed.'],
  ['qwen2.5:7b', 'Larger reasoning model — 16 GB RAM recommended.'],
  ['qwen2.5-coder:7b', 'Sharper for coding-heavy workflows.'],
] as const

const VOICE_OPTIONS = [
  ['off', 'Skip voice for now.'],
  ['push_to_talk', 'Explicit and precise.'],
  ['wake_word', 'Ambient readiness with a wake phrase.'],
] as const

export function SetupPage() {
  const [state, setState] = useState<SetupState | null>(null)
  const [plan, setPlan] = useState<SetupPlan | null>(null)
  const [diagnostics, setDiagnostics] = useState<SetupDiagnostics | null>(null)
  const [packs, setPacks] = useState<UseCasePack[]>([])
  const [providers, setProviders] = useState<ProviderProfile[]>([])
  const [importManifest, setImportManifest] = useState<OpenClawImportManifest | null>(null)
  const [stepIndex, setStepIndex] = useState(0)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState('')

  const step = STEPS[stepIndex]
  const selectedPack = packs.find((pack) => pack.id === state?.primary_pack) || null
  const selectedProvider = providers.find((provider) => provider.id === state?.selected_provider_profile) || null
  const selectedModel = state?.selected_models?.[0] || MODEL_OPTIONS[0][0]
  const modelProgress = state?.model_pull_progress || {}
  const localProvider = !selectedProvider || selectedProvider.id === 'local-ollama'
  const modelReady = !localProvider || Number(modelProgress.percent || 0) >= 100 || state?.progress_stage === 'model-ready'
  const voiceTest = state?.voice_test || {}
  const hardware = state?.detected_hardware || {}
  const hardwareSummary = useMemo(() => {
    if (!state?.detected_hardware) return 'Detecting this machine now'
    return `${hardware.summary || `Tier ${hardware.tier || 'B'}`} - ${hardware.ram_gb || '?'} GB RAM - ${hardware.gpu_name || 'CPU only'}`
  }, [hardware.gpu_name, hardware.ram_gb, hardware.summary, hardware.tier, state?.detected_hardware])

  async function loadState() {
    try {
      setState(await commandCenterApi.getSetupState())
    } catch (err: any) {
      setError(err.message || 'Failed to load setup state')
    }
  }

  async function loadDiagnostics() {
    try {
      setDiagnostics(await commandCenterApi.getSetupDiagnostics())
    } catch {}
  }

  async function loadCatalog() {
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
            setPlan({ summary: 'Bring ClawOS online for this machine.', steps: message.data.plan_steps })
          }
        }
      } catch {}
    }
    return () => {
      window.clearInterval(keepalive)
      socket.close()
    }
  }, [])

  useEffect(() => {
    if (state?.completion_marker) setStepIndex(STEPS.length - 1)
  }, [state?.completion_marker])

  useEffect(() => {
    if (step[0] === 'summary' && !plan?.steps?.length) {
      commandCenterApi.planSetup().then(setPlan).catch(() => null)
    }
  }, [plan?.steps?.length, step])

  async function runAction<T>(key: string, fn: () => Promise<T>) {
    setBusy(key)
    setError('')
    try {
      return await fn()
    } catch (err: any) {
      setError(err.message || `Request failed for ${key}`)
      return null
    } finally {
      setBusy(null)
    }
  }

  async function inspectSetup() {
    const payload = await runAction('inspect', () => commandCenterApi.inspectSetup())
    if (!payload) return
    if (payload.state) setState(payload.state)
    if (payload.openclaw) setImportManifest(payload.openclaw)
    await loadDiagnostics()
    await loadCatalog()
  }

  async function updateOptions(body: Record<string, unknown>) {
    const next = await runAction('options', () => commandCenterApi.updateSetupOptions(body))
    if (next) setState(next)
  }

  async function updatePresence(body: Record<string, unknown>) {
    const next = await runAction('presence', () => commandCenterApi.updateSetupPresence(body))
    if (next) setState(next)
  }

  async function selectPack(packId: string) {
    const next = await runAction('pack', () =>
      commandCenterApi.selectSetupPack(packId, state?.secondary_packs || [], state?.selected_provider_profile || ''),
    )
    if (next) setState(next)
  }

  async function selectProvider(providerId: string) {
    const response = await runAction('provider', () => commandCenterApi.switchProvider(providerId))
    if (!response) return
    if (response.state) setState(response.state)
    await loadState()
    await loadCatalog()
  }

  async function importOpenClaw() {
    const manifest = await runAction('openclaw', () => commandCenterApi.importOpenClaw())
    if (manifest) setImportManifest(manifest)
  }

  async function prepareModel() {
    const response = await runAction('model', () => commandCenterApi.prepareSetupModel(selectedModel))
    if (response) await loadState()
  }

  async function runVoiceTest() {
    const response = await runAction('voice-test', () => commandCenterApi.runSetupVoiceTest('Voice pipeline ready.'))
    if (response) {
      setState(response)
      await loadDiagnostics()
    }
  }

  async function launchSetup() {
    if (state?.completion_marker) {
      window.location.href = '/'
      return
    }
    await runAction('apply', () => commandCenterApi.applySetup())
  }

  function goBack() {
    setStepIndex((current) => Math.max(current - 1, 0))
  }

  function goSkip() {
    if (step[0] === 'voice') {
      updateOptions({ voice_enabled: false }).then(() => updatePresence({ voice_mode: 'off' }))
    }
    if (step[0] === 'whatsapp') {
      updateOptions({ whatsapp_enabled: false })
    }
    setStepIndex((current) => Math.min(current + 1, STEPS.length - 1))
  }

  async function goNext() {
    if (step[0] === 'welcome') {
      await inspectSetup()
      setStepIndex(1)
      return
    }
    if (step[0] === 'model' && localProvider && !modelReady) {
      await prepareModel()
      return
    }
    if (step[0] === 'voice' && state.voice_enabled && (state.voice_mode || 'push_to_talk') !== 'off' && !voiceReady) {
      await runVoiceTest()
      return
    }
    if (step[0] === 'summary') {
      await launchSetup()
      return
    }
    setStepIndex((current) => Math.min(current + 1, STEPS.length - 1))
  }

  if (!state) {
    return (
      <div style={{ minHeight: '100vh', padding: 28 }}>
        <LoadingPanel
          eyebrow="Setup"
          title="Preparing the first-run wizard"
          body="ClawOS is detecting your machine, restoring setup state, and warming up the guided flow."
        />
      </div>
    )
  }

  const progress = state.completion_marker ? 100 : Math.round(((stepIndex + 1) / STEPS.length) * 100)
  const planSteps = plan?.steps?.length ? plan.steps : state.plan_steps || []
  const voiceMode = state.voice_mode || 'push_to_talk'
  const wakeWordReady = voiceMode !== 'wake_word' || voiceTest.wake_word_ok === true
  const voiceReady = !state.voice_enabled || voiceMode === 'off' || (!!voiceTest.ok && wakeWordReady)
  const whatsappStatus = diagnostics?.gateway?.whatsapp || 'not linked'

  return (
    <div
      className="fade-up"
      style={{
        minHeight: '100vh',
        padding: 24,
        background:
          'radial-gradient(circle at top left, rgba(89,166,255,0.22), transparent 28%), radial-gradient(circle at bottom right, rgba(94,217,209,0.16), transparent 24%)',
      }}
    >
      <div style={{ width: 'min(1240px, 100%)', margin: '0 auto', display: 'grid', gridTemplateColumns: '0.92fr 1.08fr', gap: 20 }}>
        <Card style={{ padding: 28, display: 'grid', gap: 20, alignContent: 'space-between' }}>
          <div style={{ display: 'grid', gap: 18 }}>
            <PanelHeader
              eyebrow="ClawOS Setup"
              title="Premium first run, but local-first."
              description="This wizard is the product. It should feel calm, guided, and explicit before ClawOS comes online."
              aside={<Badge color="blue">Step {stepIndex + 1} of {STEPS.length}</Badge>}
            />
            <div className="progress-bar"><div className="progress-fill" style={{ width: `${progress}%` }} /></div>
            <div style={{ display: 'grid', gap: 10 }}>
              {STEPS.map((item, index) => {
                const complete = index < stepIndex || state.completion_marker
                const active = index === stepIndex
                return (
                  <div key={item[0]} style={{ display: 'grid', gridTemplateColumns: '28px 1fr', gap: 12, padding: 12, borderRadius: 16, border: `1px solid ${active ? 'rgba(89,166,255,0.24)' : 'var(--border)'}`, background: active ? 'rgba(89,166,255,0.08)' : 'var(--surface)' }}>
                    <div style={{ width: 28, height: 28, borderRadius: 999, display: 'grid', placeItems: 'center', background: complete ? 'var(--green-dim)' : active ? 'var(--blue-dim)' : 'var(--glass-2)', color: complete ? 'var(--green)' : active ? 'var(--blue)' : 'var(--text-3)', fontSize: 12, fontWeight: 700 }}>
                      {complete ? '✓' : index + 1}
                    </div>
                    <div>
                      <div style={{ fontWeight: 700 }}>{item[1]}</div>
                      <div style={{ color: 'var(--text-3)', fontSize: 12, marginTop: 4 }}>{item[2]}</div>
                    </div>
                  </div>
                )
              })}
            </div>
            <Card style={{ padding: 18, background: 'var(--surface)' }}>
              <div className="section-label">Current posture</div>
              <FactRow label="Machine" value={hardwareSummary} />
              <FactRow label="Pack" value={selectedPack?.name || state.primary_pack || 'daily-briefing-os'} />
              <FactRow label="Provider" value={selectedProvider?.name || state.selected_provider_profile || 'local-ollama'} />
              <FactRow label="Model" value={selectedModel} />
              <FactRow label="Voice" value={voiceMode} />
              <FactRow label="WhatsApp" value={state.whatsapp_enabled ? 'Prepared' : 'Skipped'} />
            </Card>
          </div>
          <Card style={{ padding: 18, background: 'var(--surface)', minHeight: 220 }}>
            <div className="section-label">Live setup log</div>
            <div className="mono" style={{ fontSize: 12, color: 'var(--text-2)', display: 'grid', gap: 8 }}>
              {(state.logs || ['Waiting for setup actions.']).slice(-8).map((entry, index) => <div key={`${entry}-${index}`}>{entry}</div>)}
            </div>
          </Card>
        </Card>

        <Card style={{ padding: 28, display: 'grid', gap: 20 }}>
          <div>
            <div className="page-eyebrow">First Run</div>
            <div className="page-title" style={{ fontSize: 'clamp(30px, 4vw, 42px)' }}>{step[1]}</div>
            <div className="page-description" style={{ maxWidth: 660 }}>{step[2]}</div>
          </div>
          {error ? <Card style={{ padding: 16, borderColor: 'rgba(255,109,118,0.24)', background: 'var(--red-dim)', color: 'var(--red)' }}>{error}</Card> : null}
          {renderStep({
            stepId: step[0],
            busy,
            state,
            diagnostics,
            packs,
            providers,
            selectedPack,
            selectedProvider,
            selectedModel,
            modelProgress,
            localProvider,
            modelReady,
            hardwareSummary,
            voiceMode,
            whatsappStatus,
            planSteps,
            importManifest,
            inspectSetup,
            selectPack,
            selectProvider,
            updateOptions,
            updatePresence,
            importOpenClaw,
            prepareModel,
            runVoiceTest,
            voiceTest,
            voiceReady,
          })}
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginTop: 'auto', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <button type="button" className="btn" onClick={goBack} disabled={stepIndex === 0 || busy !== null}>Back</button>
              {(step[0] === 'voice' || step[0] === 'whatsapp') && !state.completion_marker ? <button type="button" className="btn" onClick={goSkip} disabled={busy !== null}>Skip</button> : null}
            </div>
            <button type="button" className="btn primary" onClick={goNext} disabled={busy !== null}>
              {step[0] === 'model' && localProvider && !modelReady
                ? busy === 'model' ? 'Preparing model...' : 'Prepare model'
                : step[0] === 'voice' && state.voice_enabled && voiceMode !== 'off' && !voiceReady
                  ? busy === 'voice-test' ? 'Testing microphone...' : 'Run voice check'
                : step[0] === 'summary'
                  ? state.completion_marker ? 'Open dashboard' : busy === 'apply' || state.progress_stage === 'applying' ? 'Launching ClawOS...' : 'Launch ClawOS'
                  : 'Continue'}
            </button>
          </div>
          <div style={{ color: 'var(--text-3)', fontSize: 12 }}><ShortcutKey>Ctrl</ShortcutKey> <ShortcutKey>K</ShortcutKey> opens the command palette after setup is complete.</div>
        </Card>
      </div>
    </div>
  )
}

function renderStep({
  stepId,
  busy,
  state,
  diagnostics,
  packs,
  providers,
  selectedPack,
  selectedProvider,
  selectedModel,
  modelProgress,
  localProvider,
  modelReady,
  hardwareSummary,
  voiceMode,
  whatsappStatus,
  planSteps,
  importManifest,
  inspectSetup,
  selectPack,
  selectProvider,
  updateOptions,
  updatePresence,
  importOpenClaw,
  prepareModel,
  runVoiceTest,
  voiceTest,
  voiceReady,
}: any) {
  if (stepId === 'welcome') {
    return (
      <div style={{ display: 'grid', gap: 16 }}>
        <Card style={{ padding: 22, background: 'var(--surface)' }}>
          <PanelHeader eyebrow="Brand" title="ClawOS is local-first intelligence for your machine." description="No terminal required for the happy path. Choose a pack, confirm the machine profile, and let ClawOS do the rest." />
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 14 }}>
            <Badge color="green">Offline-capable</Badge>
            <Badge color="blue">Provider-neutral</Badge>
            <Badge color="orange">Policy-gated</Badge>
            <Badge color="gray">:7070 command center</Badge>
          </div>
        </Card>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 12 }}>
          <Metric title="< 5 minutes" body="Target time from install to first local response." />
          <Metric title="No silent failures" body="Every action shows state, progress, and recovery." />
          <Metric title="Apple-grade feel" body="Calm motion, guided defaults, and polished copy." />
        </div>
        <Card style={{ padding: 20, background: 'var(--surface)' }}>
          <PanelHeader eyebrow="Migration" title="Bringing an OpenClaw install with you?" description="ClawOS can inspect safe config and suggest the right pack without overwriting your current setup." aside={<button type="button" className="btn" onClick={importOpenClaw} disabled={busy === 'openclaw'}>{busy === 'openclaw' ? 'Inspecting...' : 'Inspect OpenClaw'}</button>} />
          {importManifest ? (
            <div style={{ display: 'grid', gap: 10, marginTop: 16 }}>
              <FactRow label="Detected version" value={importManifest.detected_version || 'none found'} />
              <FactRow label="Suggested pack" value={importManifest.suggested_primary_pack || 'daily-briefing-os'} />
              <FactRow label="Providers" value={(importManifest.providers || []).join(', ') || 'none detected'} />
            </div>
          ) : <div className="panel-description" style={{ marginTop: 16 }}>If an OpenClaw install is present, suggested migration actions will appear here.</div>}
        </Card>
      </div>
    )
  }

  if (stepId === 'hardware') {
    return (
      <div style={{ display: 'grid', gap: 16 }}>
        <Card style={{ padding: 22, background: 'var(--surface)' }}>
          <PanelHeader eyebrow="Detection" title={hardwareSummary} description="ClawOS chooses a default profile from the current hardware posture so the first run feels fast, not aspirational." aside={<button type="button" className="btn" onClick={inspectSetup} disabled={busy === 'inspect'}>{busy === 'inspect' ? 'Scanning...' : 'Re-scan machine'}</button>} />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 12, marginTop: 16 }}>
            <Metric title={`Tier ${state.detected_hardware?.tier || 'B'}`} body="Recommended hardware class." />
            <Metric title={`${state.detected_hardware?.ram_gb || '?'} GB`} body="Installed memory." />
            <Metric title={state.detected_hardware?.gpu_name || 'CPU only'} body="Detected accelerator." />
            <Metric title={state.recommended_profile || 'balanced'} body="Selected operating profile." />
          </div>
        </Card>
        <Card style={{ padding: 20, background: 'var(--surface)' }}>
          <PanelHeader eyebrow="Machine posture" title="This is what ClawOS sees right now." description="Everything here becomes part of the setup plan and future support bundle." />
          <div style={{ display: 'grid', gap: 10, marginTop: 16 }}>
            <FactRow label="Platform" value={diagnostics?.platform || state.platform || 'local'} />
            <FactRow label="Architecture" value={state.architecture || 'unknown'} />
            <FactRow label="Service manager" value={diagnostics?.service_manager || state.service_manager || 'auto'} />
            <FactRow label="Microphone" value={state.detected_hardware?.has_mic ? 'Detected' : 'Not detected'} />
            <FactRow label="Ollama" value={state.detected_hardware?.ollama_ok ? 'Reachable' : 'Not running yet'} />
          </div>
        </Card>
      </div>
    )
  }

  if (stepId === 'packs') {
    return (
      <div style={{ display: 'grid', gap: 12 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 12 }}>
          {packs.slice(0, 6).map((pack: UseCasePack) => (
            <ChoiceCard key={pack.id} active={selectedPack?.id === pack.id} title={pack.name} body={pack.setup_summary || pack.description} badge={pack.wave || 'wave-1'} onClick={() => selectPack(pack.id)} disabled={busy === 'pack'} />
          ))}
        </div>
        <Card style={{ padding: 20, background: 'var(--surface)' }}>
          <PanelHeader eyebrow="Selected pack" title={selectedPack?.name || state.primary_pack || 'daily-briefing-os'} description={selectedPack?.description || 'Choose a pack to shape the first workspace, workflows, and policy posture.'} />
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 16 }}>
            {(selectedPack?.default_workflows || []).slice(0, 5).map((item) => <Badge key={item} color="gray">{item}</Badge>)}
          </div>
        </Card>
      </div>
    )
  }

  if (stepId === 'providers') {
    return (
      <div style={{ display: 'grid', gap: 12 }}>
        <Card style={{ padding: 18, background: 'var(--surface)' }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <Badge color="green">Recommended: local Ollama</Badge>
            <Badge color="gray">Cloud visible, not default</Badge>
          </div>
        </Card>
        {providers.map((provider: ProviderProfile) => (
          <ChoiceCard key={provider.id} active={selectedProvider?.id === provider.id} title={provider.name} body={provider.detail || provider.endpoint} badge={provider.id === 'local-ollama' ? 'local-first' : provider.kind} onClick={() => selectProvider(provider.id)} disabled={busy === 'provider'} />
        ))}
      </div>
    )
  }

  if (stepId === 'model') {
    return (
      <div style={{ display: 'grid', gap: 12 }}>
        {MODEL_OPTIONS.map(([model, body]) => (
          <ChoiceCard key={model} active={selectedModel === model} title={model} body={body} badge="local model" onClick={() => updateOptions({ selected_models: [model] })} disabled={busy === 'options' || busy === 'model'} />
        ))}
        <Card style={{ padding: 20, background: 'var(--surface)' }}>
          <PanelHeader eyebrow="Provisioning" title={localProvider ? 'Local model pull' : 'Cloud provider selected'} description={localProvider ? 'This step uses websocket updates, so progress continues even if you revisit other steps.' : 'A non-local provider is selected, so ClawOS safely skips the local pull.'} aside={localProvider ? <button type="button" className="btn" onClick={prepareModel} disabled={busy === 'model'}>{busy === 'model' ? 'Preparing...' : 'Prepare again'}</button> : <Badge color="blue">Skipped</Badge>} />
          <div style={{ marginTop: 16, display: 'grid', gap: 10 }}>
            <div className="progress-bar"><div className="progress-fill" style={{ width: `${localProvider ? Number(modelProgress.percent || 0) : 100}%` }} /></div>
            <FactRow label="Model" value={selectedModel} />
            <FactRow label="Status" value={String(modelProgress.status || (localProvider ? 'Waiting for preparation' : 'Using provider profile'))} />
            <FactRow label="ETA" value={!localProvider ? 'Not needed' : Number(modelProgress.eta_seconds || 0) > 0 ? `${modelProgress.eta_seconds}s remaining` : modelReady ? 'Ready' : 'Calculating'} />
          </div>
        </Card>
      </div>
    )
  }

  if (stepId === 'voice') {
    return (
      <div style={{ display: 'grid', gap: 12 }}>
        <Card style={{ padding: 18, background: 'var(--surface)' }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <Badge color={state.detected_hardware?.has_mic ? 'green' : 'orange'}>{state.detected_hardware?.has_mic ? 'Microphone detected' : 'No microphone detected'}</Badge>
            <Badge color={diagnostics?.voice?.stt_ok ? 'green' : 'orange'}>{diagnostics?.voice?.stt_ok ? 'Whisper ready' : 'Whisper missing'}</Badge>
            <Badge color={diagnostics?.voice?.tts_ok ? 'green' : 'orange'}>{diagnostics?.voice?.tts_ok ? 'Piper ready' : 'Piper missing'}</Badge>
            <Badge color={diagnostics?.voice?.wake_word_ok ? 'blue' : 'gray'}>{diagnostics?.voice?.wake_word_ok ? 'Wake word ready' : 'Wake word optional'}</Badge>
          </div>
        </Card>
        {VOICE_OPTIONS.map(([mode, body]) => (
          <ChoiceCard
            key={mode}
            active={voiceMode === mode}
            title={mode === 'off' ? 'Skip voice for now' : mode.replace('_', ' ')}
            body={body}
            badge={mode === 'off' ? 'skip' : mode === 'wake_word' ? 'ambient' : 'recommended'}
            onClick={async () => {
              if (mode === 'off') await updateOptions({ voice_enabled: false })
              else await updateOptions({ voice_enabled: true })
              await updatePresence({ voice_mode: mode, presence_profile: { preferred_voice_mode: mode } })
            }}
            disabled={busy === 'options' || busy === 'presence' || (!state.detected_hardware?.has_mic && mode !== 'off')}
          />
        ))}
        <Card style={{ padding: 20, background: 'var(--surface)' }}>
          <PanelHeader
            eyebrow="Voice check"
            title={voiceReady ? 'Voice path confirmed.' : voiceMode === 'wake_word' ? 'Confirm microphone and wake word before continuing.' : 'Confirm the microphone before continuing.'}
            description={voiceMode === 'off' ? 'Voice is skipped for this setup, so no test is required.' : voiceMode === 'wake_word' ? 'Wake-word mode now confirms microphone readiness, playback, and whether the local wake detector can arm for "Hey Claw".' : 'The setup wizard now runs a real local microphone check and stores the latest result in setup state.'}
            aside={
              voiceMode === 'off'
                ? <Badge color="gray">Skipped</Badge>
                : <button type="button" className="btn" onClick={runVoiceTest} disabled={busy === 'voice-test' || !state.detected_hardware?.has_mic}>{busy === 'voice-test' ? 'Testing...' : 'Run voice check'}</button>
            }
          />
          <div style={{ display: 'grid', gap: 10, marginTop: 16 }}>
            <FactRow label="Selected mode" value={voiceMode.replace('_', ' ')} />
            <FactRow label="Input device" value={voiceTest.device_label || diagnostics?.voice?.device_label || 'Default input'} />
            <FactRow label="Sample rate" value={`${voiceTest.sample_rate_hz || diagnostics?.voice?.sample_rate_hz || 44100} Hz`} />
            <FactRow label="Last result" value={voiceMode === 'off' ? 'Skipped' : voiceTest.state || 'Not tested yet'} />
            <FactRow label="Transcript" value={voiceTest.transcript || (voiceMode === 'off' ? 'Not needed' : 'Run the voice check to confirm speech is detected')} />
            {voiceMode === 'wake_word' ? <FactRow label="Wake phrase" value={voiceTest.wake_word_phrase || 'Hey Claw'} /> : null}
            {voiceMode === 'wake_word' ? <FactRow label="Wake detector" value={voiceTest.wake_word_ok ? (voiceTest.wake_word_armed ? 'Armed' : 'Ready') : 'Not confirmed'} /> : null}
          </div>
          {Array.isArray(voiceTest.issues) && voiceTest.issues.length ? (
            <div style={{ marginTop: 16, display: 'grid', gap: 8 }}>
              {voiceTest.issues.map((issue: string, index: number) => (
                <div key={`${issue}-${index}`} style={{ color: 'var(--orange)', fontSize: 12 }}>{issue}</div>
              ))}
            </div>
          ) : null}
        </Card>
      </div>
    )
  }

  if (stepId === 'whatsapp') {
    return (
      <div style={{ display: 'grid', gap: 12 }}>
        <Card style={{ padding: 20, background: 'var(--surface)' }}>
          <PanelHeader eyebrow="Phone bridge" title={whatsappStatus === 'linked' ? 'WhatsApp is already linked.' : 'Link later or skip cleanly now.'} description="Milestone 2E handles the full reliability pass. For first run, this step should be explicit and non-blocking." />
          <div style={{ display: 'grid', gap: 10, marginTop: 16 }}>
            <FactRow label="Current status" value={whatsappStatus} />
            <FactRow label="Gateway status" value={diagnostics?.gateway?.status || 'unknown'} />
            <FactRow label="Selected posture" value={state.whatsapp_enabled ? 'Prepare phone bridge' : 'Skip for now'} />
          </div>
        </Card>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <ChoiceCard active={!!state.whatsapp_enabled} title="Prepare WhatsApp" body="Keep the bridge in your launch plan so the QR link can happen after the dashboard is up." badge="recommended" onClick={() => updateOptions({ whatsapp_enabled: true })} disabled={busy === 'options'} />
          <ChoiceCard active={!state.whatsapp_enabled} title="Skip for now" body="Finish setup now and link a phone later without blocking the first-run flow." badge="safe skip" onClick={() => updateOptions({ whatsapp_enabled: false })} disabled={busy === 'options'} />
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      <Card style={{ padding: 22, background: 'var(--surface)' }}>
        <PanelHeader eyebrow="Ready" title={state.completion_marker ? 'ClawOS is ready.' : 'This machine is ready for launch.'} description={state.completion_marker ? 'The setup is complete. Open the dashboard and continue from the command center.' : 'Review the exact posture ClawOS will apply, then start the setup run.'} aside={state.completion_marker ? <Badge color="green">Ready</Badge> : <Badge color="orange">Awaiting launch</Badge>} />
        <div style={{ display: 'grid', gap: 10, marginTop: 18 }}>
          <FactRow label="Pack" value={selectedPack?.name || state.primary_pack || 'daily-briefing-os'} />
          <FactRow label="Provider" value={selectedProvider?.name || state.selected_provider_profile || 'local-ollama'} />
          <FactRow label="Model" value={state.selected_models?.join(', ') || 'gemma3:4b'} />
          <FactRow label="Voice" value={voiceMode} />
          <FactRow label="WhatsApp" value={state.whatsapp_enabled ? 'Prepared for pairing' : 'Skipped'} />
          <FactRow label="Launch on login" value={state.launch_on_login === false ? 'Disabled' : 'Enabled'} />
          {state.completion_marker && (state as any).dashboard_token ? (
            <div style={{ marginTop: 8, padding: '12px 14px', background: 'var(--surface-2, rgba(255,255,255,0.05))', borderRadius: 8, border: '1px solid var(--border)' }}>
              <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Dashboard token</div>
              <code style={{ fontSize: 13, color: 'var(--accent, #7c6af5)', wordBreak: 'break-all', fontFamily: 'monospace' }}>{(state as any).dashboard_token}</code>
              <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 6 }}>Use this to unlock the dashboard on first login.</div>
            </div>
          ) : null}
        </div>
      </Card>
      <Card style={{ padding: 20, background: 'var(--surface)' }}>
        <PanelHeader eyebrow="Setup plan" title="What happens next" description="These are the concrete steps ClawOS will apply for this machine." />
        <div style={{ display: 'grid', gap: 10, marginTop: 16 }}>
          {planSteps.length ? planSteps.map((item: string, index: number) => (
            <div key={`${item}-${index}`} style={{ display: 'grid', gridTemplateColumns: '24px 1fr', gap: 10 }}>
              <div className="mono" style={{ color: 'var(--text-3)' }}>{index + 1}</div>
              <div style={{ color: 'var(--text-2)' }}>{item}</div>
            </div>
          )) : <div className="panel-description">ClawOS will generate the final plan as soon as the current service state stabilizes.</div>}
        </div>
      </Card>
    </div>
  )
}

function Metric({ title, body }: { title: string; body: string }) {
  return (
    <Card style={{ padding: 18, background: 'var(--surface)' }}>
      <div style={{ fontFamily: 'var(--font-display)', fontSize: 22, letterSpacing: '-0.04em' }}>{title}</div>
      <div className="panel-description" style={{ marginTop: 8 }}>{body}</div>
    </Card>
  )
}

function ChoiceCard({ active, title, body, badge, onClick, disabled }: any) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} style={{ textAlign: 'left', padding: 0, border: 'none', background: 'transparent', cursor: disabled ? 'not-allowed' : 'pointer' }}>
      <Card style={{ padding: 18, background: active ? 'rgba(89,166,255,0.08)' : 'var(--surface)', borderColor: active ? 'rgba(89,166,255,0.26)' : 'var(--border)', opacity: disabled ? 0.65 : 1 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start' }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: 16 }}>{title}</div>
            <div className="panel-description" style={{ marginTop: 8 }}>{body}</div>
          </div>
          {badge ? <Badge color={active ? 'blue' : 'gray'}>{badge}</Badge> : null}
        </div>
      </Card>
    </button>
  )
}

function FactRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, marginTop: 10 }}>
      <span style={{ color: 'var(--text-3)' }}>{label}</span>
      <span className="mono" style={{ textAlign: 'right' }}>{value}</span>
    </div>
  )
}
