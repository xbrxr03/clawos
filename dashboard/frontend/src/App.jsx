import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Sidebar } from './components/Sidebar.jsx'
import { Overview } from './pages/Overview.jsx'
import { Tasks, Approvals, Models, Memory, Audit } from './pages/pages.jsx'
import { Workflows } from './pages/Workflows.jsx'
import { useClawOS } from './hooks/useClawOS.js'

export default function App() {
  const { connected, events, approvals, services, tasks, models, pullProgress, runtimes } = useClawOS()

  return (
    <BrowserRouter>
      <div style={{ display:'flex', height:'100vh', overflow:'hidden', background:'var(--bg)' }}>
        {/* Subtle background gradient */}
        <div style={{
          position:'fixed', inset:0, pointerEvents:'none', zIndex:0,
          background:'radial-gradient(ellipse 80% 50% at 20% 0%, rgba(79,142,247,0.06) 0%, transparent 60%), radial-gradient(ellipse 60% 40% at 80% 100%, rgba(167,139,250,0.04) 0%, transparent 60%)',
        }} />

        <div style={{ position:'relative', zIndex:1, display:'flex', width:'100%', height:'100%' }}>
          <Sidebar
            connected={connected}
            services={services}
            approvalCount={approvals.length}
          />
          <main style={{ flex:1, overflowY:'auto', position:'relative' }}>
            <Routes>
              <Route path="/" element={<Overview services={services} tasks={tasks} approvals={approvals} events={events} models={models} runtimes={runtimes} />} />
              <Route path="/tasks"     element={<Tasks tasks={tasks} />} />
              <Route path="/approvals" element={<Approvals approvals={approvals} />} />
              <Route path="/models"    element={<Models models={models} pullProgress={pullProgress} />} />
              <Route path="/workflows"  element={<Workflows />} />
              <Route path="/memory"    element={<Memory />} />
              <Route path="/audit"     element={<Audit events={events} />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  )
}
