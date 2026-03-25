import { Card, StatusDot, Badge, Timestamp } from '../components/ui.jsx'
import { Activity, Zap, Shield, Database, Cpu, Clock } from 'lucide-react'

export function Overview({ services, tasks, approvals, events, models }) {
  const taskCounts = {
    active:    tasks.active?.length ?? 0,
    queued:    tasks.queued?.length ?? 0,
    failed:    tasks.failed?.length ?? 0,
    completed: tasks.completed?.length ?? 0,
  }

  const serviceList = Object.entries(services)

  return (
    <div className="p-6 space-y-6 fade-in">
      <div>
        <h1 className="text-lg font-semibold text-claw-text">Overview</h1>
        <p className="text-sm text-claw-dim mt-0.5">Agent runtime status</p>
      </div>

      {/* Task summary */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: 'Active',    count: taskCounts.active,    color: 'text-claw-accent', bg: 'bg-claw-accent/5' },
          { label: 'Queued',    count: taskCounts.queued,    color: 'text-claw-info',   bg: 'bg-blue-500/5'    },
          { label: 'Failed',    count: taskCounts.failed,    color: 'text-claw-danger', bg: 'bg-red-500/5'     },
          { label: 'Completed', count: taskCounts.completed, color: 'text-claw-dim',    bg: 'bg-claw-muted/30' },
        ].map(({ label, count, color, bg }) => (
          <Card key={label} className={`p-4 ${bg}`}>
            <div className={`text-2xl font-mono font-semibold ${color}`}>{count}</div>
            <div className="text-xs text-claw-dim mt-1">{label}</div>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* Services */}
        <Card>
          <div className="px-4 py-3 border-b border-claw-border flex items-center gap-2">
            <Shield size={14} className="text-claw-accent" />
            <span className="text-sm font-medium">Services</span>
          </div>
          <div className="divide-y divide-claw-border">
            {serviceList.length === 0 ? (
              <div className="px-4 py-3 text-xs text-claw-dim">Polling services...</div>
            ) : serviceList.map(([name, info]) => (
              <div key={name} className="flex items-center justify-between px-4 py-2.5">
                <div className="flex items-center gap-2.5">
                  <StatusDot status={info.status} />
                  <span className="text-sm font-mono text-claw-text">{name}</span>
                </div>
                <div className="flex items-center gap-3">
                  {info.latency_ms !== null && info.latency_ms !== undefined && (
                    <span className="text-xs font-mono text-claw-dim">{info.latency_ms}ms</span>
                  )}
                  <span className="text-xs font-mono text-claw-dim">:{info.port}</span>
                  <Badge variant={info.status === 'up' ? 'accent' : info.status === 'degraded' ? 'warn' : 'danger'}>
                    {info.status}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Approvals + live events */}
        <Card>
          <div className="px-4 py-3 border-b border-claw-border flex items-center gap-2">
            <Activity size={14} className="text-claw-accent" />
            <span className="text-sm font-medium">Live Events</span>
            {approvals.length > 0 && (
              <span className="ml-auto text-xs text-amber-400 font-mono">
                {approvals.length} pending approval{approvals.length > 1 ? 's' : ''}
              </span>
            )}
          </div>
          <div className="max-h-64 overflow-y-auto">
            {events.length === 0 ? (
              <div className="px-4 py-3 text-xs text-claw-dim">Waiting for events...</div>
            ) : events.slice(0, 20).map((evt, i) => (
              <div key={i} className="flex items-start gap-2 px-4 py-2 border-b border-claw-border/50 hover:bg-claw-muted/30">
                <EventDot type={evt.type} />
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-mono text-claw-dim truncate">{evt.type}</div>
                  {evt.data?.tool && (
                    <div className="text-xs text-claw-text truncate">{evt.data.tool}</div>
                  )}
                </div>
                <Timestamp value={evt.data?.timestamp ?? Date.now()} />
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Models */}
      <Card>
        <div className="px-4 py-3 border-b border-claw-border flex items-center gap-2">
          <Cpu size={14} className="text-claw-accent" />
          <span className="text-sm font-medium">Loaded Models</span>
        </div>
        <div className="divide-y divide-claw-border">
          {(models.models ?? []).length === 0 ? (
            <div className="px-4 py-3 text-xs text-claw-dim">No models found — is Ollama running?</div>
          ) : (models.models ?? []).map(m => (
            <div key={m.name} className="flex items-center justify-between px-4 py-2.5">
              <div className="flex items-center gap-2.5">
                <StatusDot status={m.running ? 'active' : 'completed'} />
                <span className="text-sm font-mono text-claw-text">{m.name}</span>
                {m.name === models.default && (
                  <Badge variant="accent">default</Badge>
                )}
              </div>
              <span className="text-xs font-mono text-claw-dim">{m.size_gb} GB</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}

function EventDot({ type }) {
  const color = type?.includes('error') || type?.includes('fail')
    ? 'bg-claw-danger'
    : type?.includes('approval')
    ? 'bg-claw-warn'
    : 'bg-claw-accent/40'
  return <span className={`w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0 ${color}`} />
}
