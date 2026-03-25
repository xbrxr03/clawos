import { useState } from 'react'
import { Card, Row, Dot, Badge, Empty, SectionLabel, Time } from '../components/ui.jsx'
import { clsx } from 'clsx'

const TABS = [
  { key: 'active',    label: 'Active',    color: '#30d158' },
  { key: 'queued',    label: 'Queued',    color: '#0a84ff' },
  { key: 'failed',    label: 'Failed',    color: '#ff453a' },
  { key: 'completed', label: 'Completed', color: 'rgba(255,255,255,0.3)' },
]

export function Tasks({ tasks }) {
  const [tab, setTab] = useState('active')
  const items = tasks[tab] ?? []
  const activeTab = TABS.find(t => t.key === tab)

  return (
    <div className="p-6 overflow-y-auto h-full fade-up">

      {/* Segmented control */}
      <div
        className="flex rounded-[10px] p-0.5 mb-5"
        style={{ background: 'rgba(255,255,255,0.08)' }}
      >
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={clsx(
              'flex-1 py-1.5 rounded-[8px] text-xs font-semibold transition-all flex items-center justify-center gap-1.5',
              tab === t.key ? 'text-white' : 'text-white/40'
            )}
            style={tab === t.key ? { background: 'rgba(255,255,255,0.15)' } : {}}
          >
            {t.label}
            <span
              className="text-xs font-bold rounded-full w-4 h-4 flex items-center justify-center"
              style={{
                background: tab === t.key ? t.color : 'transparent',
                color: tab === t.key ? '#000' : 'rgba(255,255,255,0.3)',
                fontSize: 10,
              }}
            >
              {tasks[t.key]?.length ?? 0}
            </span>
          </button>
        ))}
      </div>

      {items.length === 0 ? (
        <Card><Empty icon="✓" message={`No ${tab} tasks`} /></Card>
      ) : (
        <>
          <SectionLabel>{activeTab?.label} Tasks</SectionLabel>
          <Card>
            {items.map(task => (
              <TaskRow key={task.id} task={task} color={activeTab?.color} />
            ))}
          </Card>
        </>
      )}
    </div>
  )
}

function TaskRow({ task, color }) {
  const [open, setOpen] = useState(false)
  return (
    <div>
      <Row
        left={<Dot status={task.status} />}
        center={
          <div>
            <div className="text-sm font-medium truncate">{task.description ?? task.id}</div>
            <div className="text-xs mt-0.5 truncate" style={{ color: 'rgba(255,255,255,0.3)' }}>
              {task.id} {task.agent ? `· ${task.agent}` : ''}
            </div>
          </div>
        }
        right={<Time value={task.created_at} />}
        onClick={() => setOpen(o => !o)}
        chevron={!!task.log}
      />
      {open && task.log && (
        <div className="px-4 pb-3" style={{ background: 'rgba(0,0,0,0.3)' }}>
          <pre className="text-xs font-mono whitespace-pre-wrap max-h-40 overflow-y-auto"
            style={{ color: 'rgba(255,255,255,0.5)' }}>
            {task.log}
          </pre>
        </div>
      )}
    </div>
  )
}
