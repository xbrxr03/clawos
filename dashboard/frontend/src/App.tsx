/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { Component, FormEvent, ReactNode, Suspense, lazy, useEffect, useState } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AppShell } from './app/AppShell'
import { InspectorRail } from './app/InspectorRail'
import { Card, LoadingPanel, ShortcutKey } from './components/ui.jsx'
import { useCommandCenter } from './hooks/useCommandCenter'

const OverviewPage = lazy(() => import('./pages/Overview').then((mod) => ({ default: mod.Overview })))
const JarvisVoicePage = lazy(() => import('./pages/JarvisVoice').then((mod) => ({ default: mod.JarvisVoicePage })))
const TasksPage = lazy(() => import('./pages/pages.jsx').then((mod) => ({ default: mod.Tasks })))
const ApprovalsPage = lazy(() => import('./pages/pages.jsx').then((mod) => ({ default: mod.Approvals })))
const PacksPage = lazy(() => import('./pages/Packs').then((mod) => ({ default: mod.PacksPage })))
const ModelsPage = lazy(() => import('./pages/pages.jsx').then((mod) => ({ default: mod.Models })))
const AuditPage = lazy(() => import('./pages/pages.jsx').then((mod) => ({ default: mod.Audit })))
const AgentsPage = lazy(() => import('./pages/pages.jsx').then((mod) => ({ default: mod.Agents })))
const NexusCommandPage = lazy(() => import('./pages/pages.jsx').then((mod) => ({ default: mod.NexusCommand })))
const ProvidersPage = lazy(() => import('./pages/Providers').then((mod) => ({ default: mod.ProvidersPage })))
const RegistryPage = lazy(() => import('./pages/Registry').then((mod) => ({ default: mod.RegistryPage })))
const TracesPage = lazy(() => import('./pages/Traces').then((mod) => ({ default: mod.TracesPage })))
const WorkflowsPage = lazy(() => import('./pages/Workflows').then((mod) => ({ default: mod.Workflows })))
const WorkbenchPage = lazy(() => import('./pages/Workbench').then((mod) => ({ default: mod.WorkbenchPage })))
const ResearchPage = lazy(() => import('./pages/Research').then((mod) => ({ default: mod.ResearchPage })))
const MCPManagerPage = lazy(() => import('./pages/MCPManager').then((mod) => ({ default: mod.MCPManagerPage })))
// Federation page hidden until a2ad endpoints are exposed through dashd — tracked post-v0.1.
// const FederationPage = lazy(() => import('./pages/Federation').then((mod) => ({ default: mod.FederationPage })))
const StudioPage = lazy(() => import('./pages/Studio').then((mod) => ({ default: mod.StudioPage })))
const SettingsPage = lazy(() => import('./pages/Settings').then((mod) => ({ default: mod.SettingsPage })))
const BrainPage = lazy(() => import('./pages/Brain').then((mod) => ({ default: mod.BrainPage })))
const MemoryPage = lazy(() => import('./pages/Memory').then((mod) => ({ default: mod.MemoryPage })))
const SkillsPage = lazy(() => import('./pages/Skills').then((mod) => ({ default: mod.SkillsPage })))
const LicensePage = lazy(() => import('./pages/License').then((mod) => ({ default: mod.LicensePage })))
const MorningBriefingPage = lazy(() => import('./pages/MorningBriefing').then((mod) => ({ default: mod.MorningBriefingPage })))
const SetupScreen = lazy(() => import('./pages/setup/SetupPage').then((mod) => ({ default: mod.SetupPage })))

const SETUP_STORAGE_KEYS = [
  'clawos_setup_step_v2',
  'clawos_setup_furthest_v2',
  'clawos_setup_ui_v2',
  'clawos_setup_tweaks_v2',
]

function clearSetupDraftStorage() {
  try {
    SETUP_STORAGE_KEYS.forEach((key) => window.localStorage.removeItem(key))
  } catch {
    /* ignore storage failures */
  }
}

function RouteFallback({ message, compact = false }: { message: string; compact?: boolean }) {
  return (
    <div style={{ minHeight: compact ? 420 : '100vh', padding: compact ? 28 : 36 }}>
      <LoadingPanel
        eyebrow="Loading"
        title={message}
        body="ClawOS is composing the current surface, restoring live state, and warming up the command center."
      />
    </div>
  )
}

class SetupRouteBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  constructor(props: { children: ReactNode }) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error) {
    console.error('Setup route crashed', error)
  }

  reset = () => {
    clearSetupDraftStorage()
    this.setState({ error: null }, () => window.location.assign('/setup'))
  }

  hardReload = () => {
    this.setState({ error: null }, () => window.location.reload())
  }

  render() {
    if (!this.state.error) {
      return this.props.children
    }

    return (
      <div style={{ minHeight: '100vh', padding: 36 }}>
        <LoadingPanel
          eyebrow="Setup"
          title="The wizard crashed before it could render"
          body={this.state.error.message || 'The setup route hit an unexpected frontend error.'}
        />
        <div style={{ display: 'flex', gap: 12, marginTop: 20, flexWrap: 'wrap' }}>
          <button type="button" className="btn primary" onClick={this.reset}>
            Reset setup cache
          </button>
          <button type="button" className="btn" onClick={this.hardReload}>
            Reload page
          </button>
          <a className="btn" href="/">
            Open dashboard
          </a>
        </div>
      </div>
    )
  }
}

function SetupRouteShell() {
  return (
    <SetupRouteBoundary>
      <Suspense fallback={<RouteFallback message="Loading setup..." />}>
        <SetupScreen />
      </Suspense>
    </SetupRouteBoundary>
  )
}

function ShellRoutes({
  tasks,
  approvals,
  events,
  models,
  pullProgress,
  runtimes,
  services,
  voiceSession,
  jarvisSession,
}: {
  tasks: any
  approvals: any[]
  events: any[]
  models: any
  pullProgress: Record<string, any>
  runtimes: Record<string, any>
  services: Record<string, any>
  voiceSession: Record<string, any>
  jarvisSession: Record<string, any>
}) {
  return (
    <Suspense fallback={<RouteFallback message="Loading workspace..." compact />}>
      <Routes>
        <Route
          path="/"
          element={
            <OverviewPage
              services={services}
              tasks={tasks}
              approvals={approvals}
              events={events}
              models={models}
              runtimes={runtimes}
              voiceSession={voiceSession}
            />
          }
        />
        <Route path="/jarvis" element={<JarvisVoicePage jarvisSession={jarvisSession} />} />
        <Route path="/tasks" element={<TasksPage tasks={tasks} />} />
        <Route path="/approvals" element={<ApprovalsPage approvals={approvals} />} />
        <Route path="/packs" element={<PacksPage />} />
        <Route path="/workflows" element={<WorkflowsPage />} />
        <Route path="/providers" element={<ProvidersPage />} />
        <Route path="/registry" element={<RegistryPage />} />
        <Route path="/traces" element={<TracesPage />} />
        <Route path="/models" element={<ModelsPage models={models} pullProgress={pullProgress} />} />
        <Route path="/memory" element={<MemoryPage />} />
        <Route path="/audit" element={<AuditPage events={events} />} />
        <Route path="/agents" element={<AgentsPage events={events} runtimes={runtimes} />} />
        <Route path="/command" element={<NexusCommandPage />} />
        <Route path="/workbench" element={<WorkbenchPage />} />
        <Route path="/research" element={<ResearchPage />} />
        <Route path="/mcp" element={<MCPManagerPage />} />
        <Route path="/studio" element={<StudioPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/brain" element={<BrainPage />} />
        <Route path="/briefing" element={<MorningBriefingPage />} />
        <Route path="/skills" element={<SkillsPage />} />
        <Route path="/license" element={<LicensePage />} />
      </Routes>
    </Suspense>
  )
}

function AuthenticatedApp() {
  const { connected, events, approvals, services, tasks, models, pullProgress, runtimes, voiceSession, jarvisSession } = useCommandCenter()
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    return (window.localStorage.getItem('clawos-theme') as 'dark' | 'light') || 'dark'
  })

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    window.localStorage.setItem('clawos-theme', theme)
  }, [theme])

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/setup"
          element={<SetupRouteShell />}
        />
        <Route
          path="*"
          element={
            <AppShell
              connected={connected}
              services={services}
              approvals={approvals}
              events={events}
              voiceSession={voiceSession}
              jarvisSession={jarvisSession}
              inspector={<InspectorRail approvals={approvals} services={services} events={events} />}
              theme={theme}
              onToggleTheme={() => setTheme((current) => (current === 'dark' ? 'light' : 'dark'))}
            >
              <ShellRoutes
                tasks={tasks}
                approvals={approvals}
                events={events}
                models={models}
                pullProgress={pullProgress}
                runtimes={runtimes}
                services={services}
                voiceSession={voiceSession}
                jarvisSession={jarvisSession}
              />
            </AppShell>
          }
        />
      </Routes>
    </BrowserRouter>
  )
}

export default function CommandCenterApp() {
  const [ready, setReady] = useState(false)
  const [authRequired, setAuthRequired] = useState(false)
  const [authenticated, setAuthenticated] = useState(false)
  const [error, setError] = useState('')
  const isSetupRoute = typeof window !== 'undefined' && window.location.pathname.startsWith('/setup')

  useEffect(() => {
    if (isSetupRoute) {
      setAuthRequired(false)
      setAuthenticated(true)
      setReady(true)
      return
    }

    fetch('/api/session')
      .then((response) => response.json())
      .then((payload) => {
        setAuthRequired(!!payload.auth_required)
        setAuthenticated(!!payload.authenticated)
      })
      .catch(() => {
        setAuthRequired(false)
        setAuthenticated(true)
      })
      .finally(() => setReady(true))
  }, [isSetupRoute])

  const login = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    const response = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    })
    if (!response.ok) {
      setError('Local browser session could not be established.')
      return
    }
    setAuthenticated(true)
  }

  if (!ready) {
    return (
      <div style={{ minHeight: '100vh', padding: 36 }}>
        <LoadingPanel
          eyebrow="ClawOS"
          title="Loading Command Center"
          body="Restoring your local dashboard session, service posture, and the latest Nexus state."
        />
      </div>
    )
  }

  if (authRequired && !authenticated && !isSetupRoute) {
    return (
      <div className="auth-screen">
        <div className="auth-screen-panel">
          <div className="auth-screen-copy">
            <div className="page-eyebrow">Dashboard Access</div>
            <div className="page-title">Continue To ClawOS</div>
            <div className="page-description">
              ClawOS now uses a loopback-only browser session for the local dashboard. Continue to create a private session on this machine.
            </div>
            <div className="auth-screen-tips">
              <div className="auth-tip">
                <span>Privacy-first</span>
                <span>Loopback-only browser session</span>
              </div>
              <div className="auth-tip">
                <span>Quick actions</span>
                <span><ShortcutKey>Ctrl</ShortcutKey> <ShortcutKey>K</ShortcutKey> opens the command palette after unlock</span>
              </div>
              <div className="auth-tip">
                <span>Setup flow</span>
                <span><a href="/setup">Open the first-run wizard</a></span>
              </div>
            </div>
          </div>

          <form onSubmit={login}>
            <Card className="auth-card" style={{ padding: 24, background: 'var(--panel-solid)' }}>
              <div className="section-label">Local Browser Session</div>
              <div className="panel-title">Start dashboard session</div>
              <div className="panel-description">
                This keeps the dashboard private to this machine without asking you to paste a token during setup.
              </div>
              {error ? <div style={{ marginTop: 12, color: 'var(--red)', fontSize: 12 }}>{error}</div> : null}
              <button type="submit" className="btn primary" style={{ width: '100%', marginTop: 18 }}>
                Continue locally
              </button>
            </Card>
          </form>
        </div>
      </div>
    )
  }

  return <AuthenticatedApp />
}
