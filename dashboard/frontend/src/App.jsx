import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Sidebar }   from './components/Sidebar.jsx'
import { Overview }  from './pages/Overview.jsx'
import { Tasks }     from './pages/Tasks.jsx'
import { Approvals } from './pages/Approvals.jsx'
import { Models }    from './pages/Models.jsx'
import { Memory }    from './pages/Memory.jsx'
import { Audit }     from './pages/Audit.jsx'
import { useClawOS } from './hooks/useClawOS.js'

export default function App() {
  const { connected, events, approvals, services, tasks, models, pullProgress } = useClawOS()

  return (
    <BrowserRouter>
      <div className="flex h-screen overflow-hidden" style={{ background: '#000' }}>
        <Sidebar connected={connected} approvalCount={approvals.length} />
        <main className="flex-1 overflow-hidden" style={{ background: '#000' }}>
          <Routes>
            <Route path="/"          element={<Overview services={services} tasks={tasks} approvals={approvals} events={events} models={models} />} />
            <Route path="/tasks"     element={<Tasks tasks={tasks} />} />
            <Route path="/approvals" element={<Approvals approvals={approvals} />} />
            <Route path="/models"    element={<Models models={models} pullProgress={pullProgress} />} />
            <Route path="/memory"    element={<Memory />} />
            <Route path="/audit"     element={<Audit events={events} />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
