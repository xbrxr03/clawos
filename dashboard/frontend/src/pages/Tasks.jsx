import { useState } from 'react'
import { Card, SectionHeader, StatusDot, Badge, Empty, Timestamp } from '../components/ui.jsx'
import { ListTodo } from 'lucide-react'
import { clsx } from 'clsx'

const TABS = ['active', 'queued', 'failed', 'completed']

export function Tasks({ tasks }) {
  const [tab, setTab] = useState('active')
  const items = tasks[tab] ?? []

  return (
    <div className="p-6 space-y-4 fade-in">
      <div>
        <h1 className="text-lg font-semibold text-claw-text">Tasks</h1>
        <p className="text-sm text-claw-dim mt-0.5">Agent task queue and execution history</p>
      </div>

      <Card>
        {/* Tabs */}
        <div className="flex border-b border-claw-border">
          {TABS.map(t => {
            const count = tasks[t]?.length ?? 0
            return (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={clsx(
                  'px-4 py-3 text-sm font-medium flex items-center gap-2 border-b-2 -mb-px transition-colors',
                  tab === t
                    ? 'border-claw-accent text-claw-accent'
                    : 'border-transparent text-claw-dim hover:text-claw-text'
                )}
              >
                {t}
                <span className={clsx(
                  'text-xs font-mono px-1.5 rounded',
                  tab === t ? 'bg-claw-accent/10 text-claw-accent' : 'bg-claw-muted text-claw-dim'
                )}>
                  {count}
                </span>
              </button>
            )
          })}
        </div>

        {/* Task list */}
        {items.length === 0 ? (
          <Empty icon={ListTodo} message={`No ${tab} tasks`} />
        ) : (
          <div className="divide-y divide-claw-border">
            {items.map(task => (
              <TaskRow key={task.id} task={task} />
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}

function TaskRow({ task }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div
      className="px-4 py-3 hover:bg-claw-muted/20 cursor-pointer"
      onClick={() => setExpanded(e => !e)}
    >
      <div className="flex items-center gap-3">
        <StatusDot status={task.status} />
        <div className="flex-1 min-w-0">
          <div className="text-sm text-claw-text truncate font-mono">
            {task.description ?? task.id}
          </div>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-xs text-claw-dim font-mono">{task.id}</span>
            {task.agent && <Badge variant="default">{task.agent}</Badge>}
          </div>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          <Timestamp value={task.created_at} />
          <Badge variant={
            task.status === 'active' ? 'accent' :
            task.status === 'queued' ? 'info' :
            task.status === 'failed' ? 'danger' : 'completed'
          }>
            {task.status}
          </Badge>
        </div>
      </div>

      {expanded && task.log && (
        <div className="mt-3 bg-claw-bg rounded p-3 font-mono text-xs text-claw-dim border border-claw-border">
          <pre className="whitespace-pre-wrap max-h-48 overflow-y-auto">{task.log}</pre>
        </div>
      )}
    </div>
  )
}
