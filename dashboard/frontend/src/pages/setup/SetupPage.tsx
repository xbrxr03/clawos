/* SPDX-License-Identifier: AGPL-3.0-or-later
 * ClawOS first-run wizard — JARVIS HUD shell.
 * Ported from clawOS-handoff (Claude Design). Drops the ChromeWindow wrapper
 * (user decision 1). Locks forward navigation — rail click only goes to steps
 * already completed (user decision 2).
 */
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import {
  commandCenterApi,
  type OpenClawImportManifest,
  type ProviderProfile,
  type SetupPersona,
  type SetupDiagnostics,
  type SetupState,
  type UseCasePack,
} from '../../lib/commandCenterApi'
import './setup.css'
import { DEFAULT_UI, type Busy, type ScreenProps, type StepId, type WizardUI } from './types'
import { WelcomeScreen } from './screens/WelcomeScreen'
import { HardwareScreen } from './screens/HardwareScreen'
import { ProfileScreen } from './screens/ProfileScreen'
import { RuntimesScreen } from './screens/RuntimesScreen'
import { FrameworkScreen } from './screens/FrameworkScreen'
import { ModelScreen } from './screens/ModelScreen'
import { VoiceScreen } from './screens/VoiceScreen'
import { PolicyScreen } from './screens/PolicyScreen'
import { SummaryScreen } from './screens/SummaryScreen'
import { InstallOverlay } from './screens/InstallOverlay'

type StepDef = { id: StepId; label: string; Component: (props: ScreenProps) => ReactNode }

const STEPS: StepDef[] = [
  { id: 'welcome', label: 'Welcome', Component: WelcomeScreen },
  { id: 'hardware', label: 'Hardware', Component: HardwareScreen },
  { id: 'profile', label: 'Profile', Component: ProfileScreen },
  { id: 'runtimes', label: 'Runtimes', Component: RuntimesScreen },
  { id: 'framework', label: 'Framework', Component: FrameworkScreen },
  { id: 'model', label: 'Model', Component: ModelScreen },
  { id: 'voice', label: 'Meet Jarvis', Component: VoiceScreen },
  { id: 'policy', label: 'Policy', Component: PolicyScreen },
  { id: 'summary', label: 'Summary', Component: SummaryScreen },
]

const LS_STEP = 'clawos_setup_step_v2'
const LS_FURTHEST = 'clawos_setup_furthest_v2'
const LS_UI = 'clawos_setup_ui_v2'
const LS_TWEAKS = 'clawos_setup_tweaks_v2'

type Theme = 'black' | 'dark' | 'red' | 'mono' | 'light'
type Accent = 'yellow' | 'amber' | 'cyan' | 'blue' | 'crimson' | 'green'
interface Tweaks {
  theme: Theme
  accent: Accent
  flourishes: boolean
}
const DEFAULT_TWEAKS: Tweaks = { theme: 'black', accent: 'yellow', flourishes: true }

const ACCENTS: Record<Accent, { h: number; c: number }> = {
  yellow: { h: 95, c: 0.19 },
  amber: { h: 80, c: 0.17 },
  cyan: { h: 200, c: 0.14 },
  blue: { h: 255, c: 0.16 },
  crimson: { h: 20, c: 0.19 },
  green: { h: 150, c: 0.15 },
}

const THEME_LABELS: Record<Theme, string> = {
  black: 'Black / Yellow',
  dark: 'Dashboard',
  red: 'JARVIS Red',
  mono: 'HUD Mono',
  light: 'Morning',
}

function clampIndex(value: unknown, fallback = 0): number {
  const num = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(num)) return fallback
  return Math.max(0, Math.min(STEPS.length - 1, Math.trunc(num)))
}

function readLSObject<T extends object>(key: string): Partial<T> {
  const value = readLS<unknown>(key, {})
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {}
  return value as Partial<T>
}

function readLS<T>(key: string, fallback: T): T {
  if (typeof window === 'undefined') return fallback
  try {
    const raw = window.localStorage.getItem(key)
    if (raw == null) return fallback
    return JSON.parse(raw) as T
  } catch {
    return fallback
  }
}

function writeLS(key: string, value: unknown) {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* ignore storage quota */
  }
}

export function SetupPage() {
  const freshLaunch = typeof window !== 'undefined' && new URLSearchParams(window.location.search).has('fresh')

  /* ── state ─────────────────────────────────────────────────────────── */
  const [state, setState] = useState<SetupState | null>(null)
  const [diagnostics, setDiagnostics] = useState<SetupDiagnostics | null>(null)
  const [packs, setPacks] = useState<UseCasePack[]>([])
  const [providers, setProviders] = useState<ProviderProfile[]>([])
  const [personas, setPersonas] = useState<SetupPersona[]>([])
  const [importManifest, setImportManifest] = useState<OpenClawImportManifest | null>(null)
  const [busy, setBusy] = useState<Busy>(null)
  const [error, setError] = useState('')

  const [stepIndex, setStepIndex] = useState<number>(() => {
    const isFresh = typeof window !== 'undefined' && new URLSearchParams(window.location.search).has('fresh')
    if (isFresh) {
      try { window.localStorage.removeItem(LS_STEP) } catch { /* ignore */ }
      return 0
    }
    return clampIndex(readLS<unknown>(LS_STEP, 0))
  })
  const [furthest, setFurthest] = useState<number>(() => clampIndex(readLS<unknown>(LS_FURTHEST, 0)))
  const [ui, setUiRaw] = useState<WizardUI>(() => ({
    ...DEFAULT_UI,
    ...readLSObject<WizardUI>(LS_UI),
  }))
  const [tweaks, setTweaks] = useState<Tweaks>(() => ({
    ...DEFAULT_TWEAKS,
    ...readLSObject<Tweaks>(LS_TWEAKS),
  }))
  const [tweaksOpen, setTweaksOpen] = useState(false)
  const [clock, setClock] = useState<Date>(() => new Date())
  // Install overlay dismissal — flips to true after the overlay's fade-out
  // fires, so subsequent re-renders don't re-mount it while milestones linger.
  const [installDismissed, setInstallDismissed] = useState(false)

  const safeStepIndex = clampIndex(stepIndex)
  const safeFurthest = Math.max(safeStepIndex, clampIndex(furthest, safeStepIndex))

  useEffect(() => {
    if (stepIndex !== safeStepIndex) setStepIndex(safeStepIndex)
  }, [safeStepIndex, stepIndex])

  useEffect(() => {
    if (furthest !== safeFurthest) setFurthest(safeFurthest)
  }, [furthest, safeFurthest])

  useEffect(() => writeLS(LS_STEP, safeStepIndex), [safeStepIndex])
  useEffect(() => writeLS(LS_FURTHEST, safeFurthest), [safeFurthest])
  useEffect(() => writeLS(LS_UI, ui), [ui])
  useEffect(() => writeLS(LS_TWEAKS, tweaks), [tweaks])

  /* ── theme ─────────────────────────────────────────────────────────── */
  const rootRef = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    const el = rootRef.current
    if (!el) return
    el.dataset.theme = tweaks.theme
    const { h, c } = ACCENTS[tweaks.accent] || ACCENTS.cyan
    el.style.setProperty('--accent-h', String(h))
    el.style.setProperty('--accent-c', String(c))
  }, [tweaks])

  /* ── clock ─────────────────────────────────────────────────────────── */
  useEffect(() => {
    const iv = window.setInterval(() => setClock(new Date()), 30_000)
    return () => window.clearInterval(iv)
  }, [])

  /* ── API load ──────────────────────────────────────────────────────── */
  const loadState = useCallback(async () => {
    try {
      const fresh = await commandCenterApi.getSetupState()
      setState(fresh)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load setup state'
      setError(msg)
    }
  }, [])

  const loadDiagnostics = useCallback(async () => {
    try {
      setDiagnostics(await commandCenterApi.getSetupDiagnostics())
    } catch {
      /* optional */
    }
  }, [])

  const loadCatalog = useCallback(async () => {
    try {
      const [packData, providerData, personaData] = await Promise.all([
        commandCenterApi.listPacks(),
        commandCenterApi.listProviders(),
        commandCenterApi.listSetupPersonas(),
      ])
      setPacks(Array.isArray(packData) ? packData : [])
      setProviders(Array.isArray(providerData) ? providerData : [])
      setPersonas(Array.isArray(personaData) ? personaData : [])
    } catch {
      /* optional */
    }
  }, [])

  useEffect(() => {
    loadState()
    loadDiagnostics()
    loadCatalog()
  }, [loadState, loadDiagnostics, loadCatalog])

  useEffect(() => {
    if (!state) return
    if (state.selected_persona) {
      if (ui.user_profile === state.selected_persona) return
      setUiRaw((prev) => ({ ...prev, user_profile: state.selected_persona || prev.user_profile }))
      return
    }
    if (ui.user_profile) {
      setUiRaw((prev) => ({ ...prev, user_profile: '' }))
    }
  }, [state?.selected_persona, ui.user_profile])

  /* ── WS: stream setup state ────────────────────────────────────────── */
  useEffect(() => {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const socket = new WebSocket(`${proto}://${window.location.host}/ws/setup?setup=1`)
    const keepalive = window.setInterval(() => {
      if (socket.readyState === WebSocket.OPEN) socket.send('ping')
    }, 15_000)
    socket.onmessage = ({ data }) => {
      try {
        const msg = JSON.parse(data)
        if (msg.type === 'setup_state') setState(msg.data)
      } catch {
        /* ignore malformed frames */
      }
    }
    return () => {
      window.clearInterval(keepalive)
      socket.close()
    }
  }, [])

  /* ── navigation ────────────────────────────────────────────────────── */
  const goto = useCallback(
    (nextIdx: number) => {
      const safe = Math.max(0, Math.min(STEPS.length - 1, nextIdx))
      setStepIndex(safe)
      setFurthest((f) => Math.max(f, safe))
    },
    [setStepIndex, setFurthest],
  )

  const onBack = safeStepIndex > 0 ? () => goto(safeStepIndex - 1) : null

  const onNext = useCallback(() => {
    goto(safeStepIndex + 1)
  }, [goto, safeStepIndex])

  // Rail click: lock forward — only go to steps already reached
  const onRailClick = useCallback(
    (idx: number) => {
      if (idx <= safeFurthest) goto(idx)
    },
    [goto, safeFurthest],
  )

  /* ── keyboard: Enter advances, Esc goes back ───────────────────────── */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null
      if (!target) return
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return
      if (e.key === 'Enter' && !busy) {
        e.preventDefault()
        onNext()
      } else if (e.key === 'Escape' && safeStepIndex > 0) {
        e.preventDefault()
        goto(safeStepIndex - 1)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [busy, goto, onNext, safeStepIndex])

  /* ── completion marker → jump to summary ───────────────────────────── */
  useEffect(() => {
    if (state?.completion_marker && !freshLaunch) {
      setStepIndex(STEPS.length - 1)
      setFurthest(STEPS.length - 1)
    }
  }, [state?.completion_marker, freshLaunch])

  /* ── action wrappers ───────────────────────────────────────────────── */
  const runAction = useCallback(
    async <T,>(key: string, fn: () => Promise<T>): Promise<T | null> => {
      setBusy(key)
      setError('')
      try {
        return await fn()
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : `Request failed for ${key}`
        setError(msg)
        return null
      } finally {
        setBusy(null)
      }
    },
    [],
  )

  const inspect = useCallback(async () => {
    const payload = await runAction('inspect', () => commandCenterApi.inspectSetup())
    if (!payload) return
    if (payload.state) setState(payload.state)
    if (payload.openclaw) setImportManifest(payload.openclaw)
    await loadDiagnostics()
    await loadCatalog()
  }, [runAction, loadDiagnostics, loadCatalog])

  const updateOptions = useCallback(
    async (body: Record<string, unknown>) => {
      const next = await runAction('options', () => commandCenterApi.updateSetupOptions(body))
      if (next) setState(next)
    },
    [runAction],
  )

  const updatePresence = useCallback(
    async (body: Record<string, unknown>) => {
      const next = await runAction('presence', () => commandCenterApi.updateSetupPresence(body))
      if (next) setState(next)
    },
    [runAction],
  )

  const updateAutonomy = useCallback(
    async (body: Record<string, unknown>) => {
      const next = await runAction('autonomy', () => commandCenterApi.updateSetupAutonomy(body))
      if (next) setState(next)
    },
    [runAction],
  )

  const selectPack = useCallback(
    async (packId: string, secondary: string[] = []) => {
      const next = await runAction('pack', () =>
        commandCenterApi.selectSetupPack(
          packId,
          secondary,
          state?.selected_provider_profile || '',
        ),
      )
      if (next) setState(next)
    },
    [runAction, state?.selected_provider_profile],
  )

  const selectProvider = useCallback(
    async (providerId: string) => {
      const response = await runAction('provider', () =>
        commandCenterApi.switchProvider(providerId),
      )
      if (!response) return
      if (response.state) setState(response.state)
      else await loadState()
      await loadCatalog()
    },
    [runAction, loadState, loadCatalog],
  )

  const importOpenClaw = useCallback(async () => {
    const manifest = await runAction('openclaw', () => commandCenterApi.importOpenClaw())
    if (manifest) setImportManifest(manifest)
  }, [runAction])

  const prepareModel = useCallback(async () => {
    const selectedModel = state?.selected_models?.[0] || 'qwen2.5:7b'
    const response = await runAction('model', () =>
      commandCenterApi.prepareSetupModel(selectedModel),
    )
    if (response) await loadState()
  }, [runAction, loadState, state?.selected_models])

  const runVoiceTest = useCallback(async () => {
    const next = await runAction('voice-test', () =>
      commandCenterApi.runSetupVoiceTest('Voice pipeline ready.'),
    )
    if (next) setState(next)
    await loadDiagnostics()
  }, [runAction, loadDiagnostics])

  const planSetup = useCallback(async () => {
    const plan = await runAction('plan', () => commandCenterApi.planSetup())
    if (plan?.steps && state) {
      setState({ ...state, plan_steps: plan.steps })
    }
  }, [runAction, state])

  const applySetup = useCallback(async () => {
    await runAction('apply', () => commandCenterApi.applySetup())
    // state will stream back via /ws/setup — no manual refresh
  }, [runAction])

  const setUi = useCallback((patch: Partial<WizardUI>) => {
    setUiRaw((prev) => ({ ...prev, ...patch }))
  }, [])

  /* ── loading shell ─────────────────────────────────────────────────── */
  const clockStr = `${clock.toLocaleString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  })} · ${clock.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}`

  if (!state) {
    return (
      <div className="clawos-setup-root" ref={rootRef} data-theme={tweaks.theme}>
        <div className="desktop flourishes">
          <div className="menubar">
            <span className="apple"></span>
            <span className="name">ClawOS</span>
            <div className="right">
              <span className="dot" /> <span>booting…</span>
            </div>
          </div>
          <div className="stage-shell">
            <div className="wiz">
              <div className="stage">
                <div className="stage-inner" style={{ paddingTop: 80 }}>
                  <div className="eyebrow">FIRST RUN</div>
                  <h1 className="wiz-title">{error ? 'Setup state is blocked' : 'Warming up the wizard…'}</h1>
                  <p className="wiz-subtitle">
                    {error
                      ? error
                      : 'Restoring setup state, detecting hardware and checking local services.'}
                  </p>
                  {error ? (
                    <div style={{ marginTop: 28, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                      <button
                        className="wiz-btn wiz-btn-primary"
                        type="button"
                        onClick={() => {
                          setError('')
                          loadState()
                          loadDiagnostics()
                          loadCatalog()
                        }}
                      >
                        Retry
                      </button>
                      <a className="wiz-btn wiz-btn-ghost" href="/">
                        Open Dashboard
                      </a>
                    </div>
                  ) : (
                    <div className="boot-log" style={{ marginTop: 28 }}>
                      <span className="ln">
                        <span className="dim">[0000ms]</span> <span className="lab">setupd</span>{' '}
                        loading state snapshot… <span className="lab">[ … ]</span>
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  const step = STEPS[safeStepIndex]
  const Comp = step.Component

  const screenProps: ScreenProps = {
    state,
    diagnostics,
    packs,
    providers,
    personas,
    importManifest,
    busy,
    error,
    ui,
    setUi,
    stepIndex: safeStepIndex,
    totalSteps: STEPS.length,
    onBack,
    onNext,
    inspect,
    updateOptions,
    updatePresence,
    updateAutonomy,
    selectPack,
    selectProvider,
    importOpenClaw,
    prepareModel,
    runVoiceTest,
    planSetup,
    applySetup,
  }

  const ramLabel = state.detected_hardware?.ram_gb
    ? `◐ ${state.detected_hardware.ram_gb}GB`
    : '◐ local'

  // Install overlay visibility: show whenever install.sh has streamed at
  // least one milestone AND the user hasn't sat through the fade-out yet.
  // Once dismissed, it stays gone until the page reloads.
  const installMilestones = state?.install_milestones ?? []
  const installActive =
    !installDismissed &&
    installMilestones.length > 0 &&
    state?.completion_marker !== true &&
    !(freshLaunch && state.install_complete)

  return (
    <div className="clawos-setup-root" ref={rootRef} data-theme={tweaks.theme}>
      {installActive && state ? (
        <InstallOverlay state={state} onDone={() => setInstallDismissed(true)} />
      ) : null}
      <div className={`desktop${tweaks.flourishes ? ' flourishes' : ''}`}>
        <div className="menubar">
          <span className="apple"></span>
          <span className="name">ClawOS</span>
          <span className="m-item">File</span>
          <span className="m-item">Edit</span>
          <span className="m-item">View</span>
          <span className="m-item">Jarvis</span>
          <span className="m-item">Help</span>
          <div className="right">
            <span className="dot" /> <span>nexus online</span>
            <span>{ramLabel}</span>
            <span>{clockStr}</span>
          </div>
        </div>

        <div className="stage-shell">
          <div className="wiz">
            <aside className="rail">
              <div className="rail-brand">
                <div className="rail-logo">◈</div>
                <div>
                  <div className="rail-name">ClawOS</div>
                  <div className="rail-ver">first-run · v0.1.0</div>
                </div>
              </div>
              <div className="rail-title">Setup</div>
              {STEPS.map((s, i) => {
                const reached = i <= safeFurthest
                const isDone = i < safeStepIndex || (i === STEPS.length - 1 && !!state.completion_marker)
                return (
                  <button
                    type="button"
                    key={s.id}
                    className={`step ${i === safeStepIndex ? 'active' : ''} ${isDone ? 'done' : ''}`}
                    onClick={() => onRailClick(i)}
                    disabled={!reached}
                    title={reached ? `Go to ${s.label}` : 'Locked — finish earlier steps first'}
                  >
                    <div className="step-num">
                      <span className="num">{String(i + 1).padStart(2, '0')}</span>
                    </div>
                    <div className="step-label">{s.label}</div>
                  </button>
                )
              })}
              <div className="rail-foot">
                <div>
                  ⌃ ⏎ &nbsp;&nbsp;<span className="k">continue</span>
                </div>
                <div>
                  ESC&nbsp;&nbsp;<span className="k">back</span>
                </div>
                <button
                  type="button"
                  className="step"
                  onClick={() => setTweaksOpen((o) => !o)}
                  style={{ marginTop: 8, padding: '6px 8px', fontSize: 11 }}
                >
                  <div className="step-num" style={{ width: 16, height: 16, fontSize: 9 }}>
                    ◉
                  </div>
                  <span className="step-label">Tweaks</span>
                </button>
              </div>
            </aside>
            <section className="stage">
              {error ? (
                <div className="note err" style={{ marginBottom: 18 }}>
                  <span>✕</span>
                  {error}
                </div>
              ) : null}
              <Comp {...screenProps} />
            </section>
          </div>
        </div>

        {tweaksOpen && (
          <div className="tweaks">
            <h4>
              Appearance
              <span className="close" onClick={() => setTweaksOpen(false)}>
                ×
              </span>
            </h4>

            <div className="tw-row">
              <div className="tw-label">Theme</div>
              <div className="theme-btns">
                {(['black', 'dark', 'red', 'mono', 'light'] as Theme[]).map((t) => (
                  <button
                    type="button"
                    key={t}
                    className={`tb ${tweaks.theme === t ? 'sel' : ''}`}
                    onClick={() => setTweaks({ ...tweaks, theme: t })}
                  >
                    {THEME_LABELS[t]}
                  </button>
                ))}
              </div>
            </div>

            <div className="tw-row">
              <div className="tw-label">Accent</div>
              <div className="swatches">
                {(Object.entries(ACCENTS) as [Accent, { h: number; c: number }][]).map(
                  ([k, v]) => (
                    <div
                      key={k}
                      className={`sw ${tweaks.accent === k ? 'sel' : ''}`}
                      style={{ background: `oklch(72% ${v.c} ${v.h})` }}
                      title={k}
                      onClick={() => setTweaks({ ...tweaks, accent: k })}
                    />
                  ),
                )}
              </div>
            </div>

            <div className="tw-row">
              <label className="tog">
                <input
                  type="checkbox"
                  checked={tweaks.flourishes}
                  onChange={(e) => setTweaks({ ...tweaks, flourishes: e.target.checked })}
                />
                <span>JARVIS flourishes</span>
                <span
                  style={{
                    marginLeft: 'auto',
                    fontSize: 10,
                    color: 'var(--ink-4)',
                    fontFamily: 'var(--mono)',
                  }}
                >
                  scanlines · HUD · orb
                </span>
              </label>
            </div>

            <div className="hair" style={{ margin: '10px 0' }} />
            <button
              type="button"
              className="wiz-btn wiz-btn-ghost"
              style={{ width: '100%', justifyContent: 'center', fontSize: 11 }}
              onClick={() => {
                try {
                  window.localStorage.removeItem(LS_STEP)
                  window.localStorage.removeItem(LS_FURTHEST)
                  window.localStorage.removeItem(LS_UI)
                } catch {
                  /* ignore */
                }
                setStepIndex(0)
                setFurthest(0)
                setUiRaw(DEFAULT_UI)
              }}
            >
              ↺ reset onboarding state
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
