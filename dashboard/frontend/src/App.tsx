/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { FormEvent, Suspense, lazy, useEffect, useState } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AppShell } from './app/AppShell'
import { InspectorRail } from './app/InspectorRail'
import { Card, LoadingPanel, ShortcutKey } from './components/ui.jsx'
import { useCommandCenter } from './hooks/useCommandCenter'

const OverviewPage = lazy(() => import('./pages/Overview').then((mod) => ({ default: mod.Overview })))
const TasksPage = lazy(() => import('./pages/pages.jsx').then((mod) => ({ default: mod.Tasks })))
const ApprovalsPage = lazy(() => import('./pages/pages.jsx').then((mod) => ({ default: mod.Approvals })))
const PacksPage = lazy(() => import('./pages/Packs').then((mod) => ({ default: mod.PacksPage })))
const ModelsPage = lazy(() => import('./pages/pages.jsx').then((mod) => ({ default: mod.Models })))
const MemoryPage = lazy(() => import('./pages/pages.jsx').then((mod) => ({ default: mod.Memory })))
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
const FederationPage = lazy(() => import('./pages/Federation').then((mod) => ({ default: mod.FederationPage })))
const StudioPage = lazy(() => import('./pages/Studio').then((mod) => ({ default: mod.StudioPage })))
const SettingsPage = lazy(() => import('./pages/Settings').then((mod) => ({ default: mod.SettingsPage })))
const BrainPage = lazy(() => import('./pages/Brain').then((mod) => ({ default: mod.BrainPage })))
const SkillsPage = lazy(() => import('./pages/Skills').then((mod) => ({ default: mod.SkillsPage })))
const LicensePage = lazy(() => import('./pages/License').then((mod) => ({ default: mod.LicensePage })))
const SetupScreen = lazy(() => import('./pages/setup/SetupPage').then((mod) => ({ default: mod.SetupPage })))

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

function ShellRoutes({
  tasks,
  approvals,
  events,
  models,
  pullProgress,
  runtimes,
  services,
  voiceSession,
}: {
  tasks: any
  approvals: any[]
  events: any[]
  models: any
  pullProgress: Record<string, any>
  runtimes: Record<string, any>
  services: Record<string, any>
  voiceSession: Record<string, any>
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
        <Route path="/federation" element={<FederationPage />} />
        <Route path="/studio" element={<StudioPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/brain" element={<BrainPage />} />
        <Route path="/skills" element={<SkillsPage />} />
        <Route path="/license" element={<LicensePage />} />
      </Routes>
    </Suspense>
  )
}

function AuthenticatedApp() {
  const { connected, events, approvals, services, tasks, models, pullProgress, runtimes, voiceSession } = useCommandCenter()
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
          element={
            <Suspense fallback={<RouteFallback message="Loading setup..." />}>
              <SetupScreen />
            </Suspense>
          }
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
  const [token, setToken] = useState('')
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
      body: JSON.stringify({ token }),
    })
    if (!response.ok) {
      setError('That token was rejected.')
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

  if (isSetupRoute) {
    return (
      <BrowserRouter>
        <Suspense fallback={<RouteFallback message="Loading setup..." />}>
          <Routes>
            <Route path="*" element={<SetupScreen />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    )
  }

  if (authRequired && !authenticated) {
    return (
      <div className="auth-screen">
        <div className="auth-screen-panel">
          <div className="auth-screen-copy">
            <div className="page-eyebrow">Dashboard Access</div>
            <div className="page-title">Unlock ClawOS</div>
            <div className="page-description">
              Your command center is local-first and private by default. Enter the dashboard token from your ClawOS config to continue.
            </div>
            <div className="auth-screen-tips">
              <div className="auth-tip">
                <span>Privacy-first</span>
                <span>Local session cookie after login</span>
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
              <div className="section-label">Local Token</div>
              <div className="panel-title">Dashboard token</div>
              <div className="panel-description">
                Paste the token exactly as it appears in your local ClawOS config.
              </div>
              <input
                type="password"
                value={token}
                onChange={(event) => setToken(event.target.value)}
                placeholder="Dashboard token"
                style={{ width: '100%', marginTop: 18 }}
              />
              {error ? <div style={{ marginTop: 12, color: 'var(--red)', fontSize: 12 }}>{error}</div> : null}
              <button type="submit" className="btn primary" style={{ width: '100%', marginTop: 18 }}>
                Unlock Command Center
              </button>
            </Card>
          </form>
        </div>
      </div>
    )
  }

  return <AuthenticatedApp />
}
