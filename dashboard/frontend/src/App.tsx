import { FormEvent, Suspense, lazy, useEffect, useState } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AppShell } from './app/AppShell'
import { InspectorRail } from './app/InspectorRail'
import { useCommandCenter } from './hooks/useCommandCenter'

const OverviewPage = lazy(() => import('./pages/Overview').then((mod) => ({ default: mod.Overview })))
const TasksPage = lazy(() => import('./pages/pages.jsx').then((mod) => ({ default: mod.Tasks })))
const ApprovalsPage = lazy(() => import('./pages/pages.jsx').then((mod) => ({ default: mod.Approvals })))
const ModelsPage = lazy(() => import('./pages/pages.jsx').then((mod) => ({ default: mod.Models })))
const MemoryPage = lazy(() => import('./pages/pages.jsx').then((mod) => ({ default: mod.Memory })))
const AuditPage = lazy(() => import('./pages/pages.jsx').then((mod) => ({ default: mod.Audit })))
const AgentsPage = lazy(() => import('./pages/pages.jsx').then((mod) => ({ default: mod.Agents })))
const NexusCommandPage = lazy(() => import('./pages/pages.jsx').then((mod) => ({ default: mod.NexusCommand })))
const WorkflowsPage = lazy(() => import('./pages/Workflows').then((mod) => ({ default: mod.Workflows })))
const SettingsPage = lazy(() => import('./pages/Settings').then((mod) => ({ default: mod.SettingsPage })))
const SetupScreen = lazy(() => import('./pages/setup/SetupPage').then((mod) => ({ default: mod.SetupPage })))

function RouteFallback({ message, compact = false }: { message: string; compact?: boolean }) {
  return (
    <div
      style={{
        minHeight: compact ? 280 : '100vh',
        display: 'grid',
        placeItems: 'center',
        padding: compact ? 32 : 0,
        color: 'var(--text-3)',
      }}
    >
      {message}
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
}: {
  tasks: any
  approvals: any[]
  events: any[]
  models: any
  pullProgress: Record<string, any>
  runtimes: Record<string, any>
  services: Record<string, any>
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
            />
          }
        />
        <Route path="/tasks" element={<TasksPage tasks={tasks} />} />
        <Route path="/approvals" element={<ApprovalsPage approvals={approvals} />} />
        <Route path="/workflows" element={<WorkflowsPage />} />
        <Route path="/models" element={<ModelsPage models={models} pullProgress={pullProgress} />} />
        <Route path="/memory" element={<MemoryPage />} />
        <Route path="/audit" element={<AuditPage events={events} />} />
        <Route path="/agents" element={<AgentsPage events={events} runtimes={runtimes} />} />
        <Route path="/command" element={<NexusCommandPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
    </Suspense>
  )
}

function AuthenticatedApp() {
  const { connected, events, approvals, services, tasks, models, pullProgress, runtimes } = useCommandCenter()
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
      <div style={{ display: 'grid', placeItems: 'center', minHeight: '100vh', color: 'var(--text-3)' }}>
        Loading ClawOS...
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
      <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', padding: 24 }}>
        <form
          onSubmit={login}
          className="glass"
          style={{ width: 'min(420px, 100%)', padding: 24, background: 'var(--panel-solid)' }}
        >
          <div className="section-label">Dashboard access</div>
          <div style={{ fontSize: 28, fontWeight: 700, letterSpacing: '-0.04em' }}>Unlock ClawOS</div>
          <div style={{ marginTop: 10, color: 'var(--text-3)' }}>
            Enter the dashboard token from your local ClawOS config to continue.
          </div>
          <input
            type="password"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            placeholder="Dashboard token"
            style={{
              width: '100%',
              marginTop: 18,
              padding: '12px 14px',
              borderRadius: 12,
              border: '1px solid var(--border)',
              background: 'var(--surface-2)',
              color: 'var(--text)',
            }}
          />
          {error && <div style={{ marginTop: 12, color: 'var(--red)', fontSize: 12 }}>{error}</div>}
          <button type="submit" className="btn primary" style={{ width: '100%', marginTop: 18 }}>
            Unlock Command Center
          </button>
        </form>
      </div>
    )
  }

  return <AuthenticatedApp />
}
