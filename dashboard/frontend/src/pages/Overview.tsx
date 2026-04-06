import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Badge, Card, SectionLabel, StatusDot, Ts } from '../components/ui.jsx'
import { commandCenterApi } from '../lib/commandCenterApi'

type ServiceMap = Record<string, { status?: string; latency_ms?: number }>
type TaskMap = Record<string, Array<{ id?: string; description?: string; status?: string }>>
type EventRecord = { type?: string; data?: Record<string, any>; timestamp?: string | number }
type ApprovalRecord = { id?: string; tool?: string; risk?: string; target?: string }
type ModelRecord = { default?: string; models?: Array<{ name?: string; running?: boolean }> }
type RuntimeRecord = Record<string, { installed?: boolean; running?: boolean; model?: string }>

const QUICK_ACTIONS = [
  { id: 'repo-summary', label: 'Summarize repository', subtitle: 'Read structure, risks, and modules' },
  { id: 'disk-report', label: 'Inspect storage', subtitle: 'Capture local disk posture and growth' },
  { id: 'find-todos', label: 'Review TODOs', subtitle: 'Scan codebase backlog and loose ends' },
  { id: 'organize-downloads', label: 'Organize downloads', subtitle: 'Clean local clutter into structure' },
]

function metricValue(value: number | string, suffix?: string) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
      <span style={{ fontSize: 32, fontWeight: 700, letterSpacing: '-0.05em' }}>{value}</span>
      {suffix && <span style={{ color: 'var(--text-3)', fontSize: 13 }}>{suffix}</span>}
    </div>
  )
}

export function Overview({
  services,
  tasks,
  approvals,
  events,
  models,
  runtimes = {},
}: {
  services: ServiceMap
  tasks: TaskMap
  approvals: ApprovalRecord[]
  events: EventRecord[]
  models: ModelRecord
  runtimes?: RuntimeRecord
}) {
  const navigate = useNavigate()
  const [runningAction, setRunningAction] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState('')
  const [primaryPack, setPrimaryPack] = useState('daily-briefing-os')
  const [providerProfile, setProviderProfile] = useState('local-ollama')
  const [traceCount, setTraceCount] = useState(0)

  const serviceEntries = Object.entries(services || {})
  const upCount = serviceEntries.filter(([, item]) => item?.status === 'up' || item?.status === 'running').length
  const taskCounts = {
    active: tasks.active?.length ?? 0,
    queued: tasks.queued?.length ?? 0,
    failed: tasks.failed?.length ?? 0,
    completed: tasks.completed?.length ?? 0,
  }
  const runningModels = (models.models || []).filter((item) => item.running).length
  const defaultModel = models.default || models.models?.[0]?.name || 'qwen2.5:7b'

  useEffect(() => {
    Promise.all([
      commandCenterApi.listPacks(),
      commandCenterApi.listProviders(),
      commandCenterApi.listTraces(),
    ])
      .then(([packs, providers, traces]) => {
        const primary = (packs || []).find((item: any) => item.primary) || packs?.[0]
        const provider = (providers || []).find((item: any) => item.selected) || providers?.[0]
        setPrimaryPack(primary?.name || primary?.id || 'daily-briefing-os')
        setProviderProfile(provider?.name || provider?.id || 'local-ollama')
        setTraceCount(Array.isArray(traces) ? traces.length : 0)
      })
      .catch(() => null)
  }, [])

  const activity = useMemo(
    () => events.slice(0, 8).map((event, index) => ({ ...event, id: `${event.type || 'event'}-${index}` })),
    [events],
  )

  const runtimeCards = [
    { id: 'nexus', label: 'Nexus', subtitle: 'Primary local agent runtime' },
    { id: 'picoclaw', label: 'PicoClaw', subtitle: 'Low-footprint edge runtime' },
    { id: 'openclaw', label: 'OpenClaw', subtitle: 'Optional gateway and skills layer' },
  ]

  const runQuickAction = async (workflowId: string) => {
    setRunningAction(workflowId)
    setActionMessage('')
    try {
      const result = await commandCenterApi.runWorkflow(workflowId)
      setActionMessage(result.output || result.error || `${workflowId} started`)
    } catch (error: any) {
      setActionMessage(error.message || `Failed to run ${workflowId}`)
    } finally {
      setRunningAction(null)
    }
  }

  return (
    <div className="fade-up" style={{ padding: '0 0 40px' }}>
      <div style={{ padding: '28px 24px 0', display: 'grid', gap: 16 }}>
        <div
          className="glass"
          style={{
            padding: 24,
            display: 'grid',
            gridTemplateColumns: '1.15fr 0.85fr',
            gap: 18,
            alignItems: 'stretch',
            background:
              'radial-gradient(circle at top left, rgba(77,143,247,0.18), transparent 38%), linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02))',
          }}
        >
          <div style={{ display: 'grid', gap: 14 }}>
            <div className="section-label">Command Center Home</div>
            <div style={{ fontSize: 34, fontWeight: 700, letterSpacing: '-0.06em', lineHeight: 1.05, maxWidth: 620 }}>
              Calm local operations for models, memory, workflows, and approvals.
            </div>
            <div style={{ color: 'var(--text-3)', fontSize: 14, maxWidth: 560 }}>
              ClawOS is running as a local-first control plane. Use this surface to inspect system posture, launch guided workflows, and keep approvals moving without leaving the command center.
            </div>

            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <button className="btn primary" onClick={() => navigate('/workflows')}>Browse workflows</button>
              <button className="btn" onClick={() => navigate('/settings')}>Open settings</button>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <MetricPanel label="Services healthy" value={`${upCount}/${serviceEntries.length || 0}`} tone="blue" />
            <MetricPanel label="Pending approvals" value={approvals.length} tone={approvals.length ? 'orange' : 'green'} />
            <MetricPanel label="Active tasks" value={taskCounts.active} tone={taskCounts.active ? 'green' : 'gray'} />
            <MetricPanel label="Running models" value={runningModels} tone={runningModels ? 'blue' : 'gray'} />
          </div>
        </div>
      </div>

      <SectionLabel>Quick actions</SectionLabel>
      <div style={{ padding: '0 24px', display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 12 }}>
        {QUICK_ACTIONS.map((item) => (
          <Card key={item.id} style={{ padding: 16, display: 'grid', gap: 12 }}>
            <div style={{ display: 'grid', gap: 6 }}>
              <div style={{ fontSize: 15, fontWeight: 600 }}>{item.label}</div>
              <div style={{ color: 'var(--text-3)', fontSize: 12, lineHeight: 1.5 }}>{item.subtitle}</div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 }}>
              <span className="mono" style={{ color: 'var(--text-3)', fontSize: 11 }}>{item.id}</span>
              <button className="btn" onClick={() => runQuickAction(item.id)} disabled={runningAction !== null}>
                {runningAction === item.id ? 'Running' : 'Run'}
              </button>
            </div>
          </Card>
        ))}
      </div>

      {actionMessage && (
        <div style={{ padding: '12px 24px 0' }}>
          <Card style={{ padding: 14, color: 'var(--text-2)' }}>{actionMessage}</Card>
        </div>
      )}

      <SectionLabel>Competitive posture</SectionLabel>
      <div style={{ padding: '0 24px', display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 12 }}>
        <Card style={{ padding: 18, display: 'grid', gap: 10 }}>
          <div className="section-label">Primary pack</div>
          <div style={{ fontSize: 18, fontWeight: 600 }}>{primaryPack}</div>
          <div style={{ color: 'var(--text-3)', fontSize: 13 }}>
            Outcome-first onboarding replaces the generic dashboard pattern.
          </div>
        </Card>

        <Card style={{ padding: 18, display: 'grid', gap: 10 }}>
          <div className="section-label">Provider posture</div>
          <div style={{ fontSize: 18, fontWeight: 600 }}>{providerProfile}</div>
          <div style={{ color: 'var(--text-3)', fontSize: 13 }}>
            Local by default, hybrid convenience when it materially improves execution.
          </div>
        </Card>

        <Card style={{ padding: 18, display: 'grid', gap: 10 }}>
          <div className="section-label">Trace buffer</div>
          <div style={{ fontSize: 18, fontWeight: 600 }}>{traceCount} recent records</div>
          <div style={{ color: 'var(--text-3)', fontSize: 13 }}>
            Product-grade visibility across setup, providers, packs, and delegated work.
          </div>
        </Card>
      </div>

      <SectionLabel>System posture</SectionLabel>
      <div style={{ padding: '0 24px', display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
        <Card style={{ padding: 18, display: 'grid', gap: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 16, fontWeight: 600 }}>Task queue</div>
              <div style={{ color: 'var(--text-3)', fontSize: 12, marginTop: 4 }}>Current flow through the local agent system</div>
            </div>
            <Badge color={taskCounts.failed ? 'red' : 'blue'}>{taskCounts.failed ? 'Attention' : 'Stable'}</Badge>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <SmallMetric label="Queued" value={taskCounts.queued} />
            <SmallMetric label="Completed" value={taskCounts.completed} />
            <SmallMetric label="Active" value={taskCounts.active} />
            <SmallMetric label="Failed" value={taskCounts.failed} tone={taskCounts.failed ? 'var(--red)' : undefined} />
          </div>
        </Card>

        <Card style={{ padding: 18, display: 'grid', gap: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 16, fontWeight: 600 }}>Runtime posture</div>
              <div style={{ color: 'var(--text-3)', fontSize: 12, marginTop: 4 }}>Installed runtimes and current model assignments</div>
            </div>
            <Badge color="blue">{defaultModel}</Badge>
          </div>

          <div style={{ display: 'grid', gap: 10 }}>
            {runtimeCards.map((runtime) => {
              const item = runtimes[runtime.id] || {}
              const status = item.running ? 'running' : item.installed ? 'degraded' : 'down'
              return (
                <div
                  key={runtime.id}
                  style={{
                    borderRadius: 14,
                    padding: 14,
                    background: 'var(--surface-2)',
                    border: '1px solid var(--border)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    gap: 12,
                  }}
                >
                  <div style={{ minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <StatusDot status={status} />
                      <div style={{ fontSize: 13, fontWeight: 600 }}>{runtime.label}</div>
                    </div>
                    <div style={{ marginTop: 6, fontSize: 12, color: 'var(--text-3)' }}>{runtime.subtitle}</div>
                  </div>
                  <div style={{ textAlign: 'right', minWidth: 0 }}>
                    <div style={{ fontSize: 12, color: 'var(--text-2)' }}>{item.running ? 'Running' : item.installed ? 'Installed' : 'Not installed'}</div>
                    <div className="mono" style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 4 }}>
                      {item.model || 'No model assigned'}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </Card>

        <Card style={{ padding: 18, display: 'grid', gap: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 16, fontWeight: 600 }}>Approvals and trust</div>
              <div style={{ color: 'var(--text-3)', fontSize: 12, marginTop: 4 }}>Sensitive actions waiting for human review</div>
            </div>
            <Badge color={approvals.length ? 'orange' : 'green'}>{approvals.length ? 'Pending' : 'Clear'}</Badge>
          </div>

          {approvals.length === 0 ? (
            <div style={{ color: 'var(--text-3)', fontSize: 13 }}>No approvals are waiting right now.</div>
          ) : (
            <div style={{ display: 'grid', gap: 10 }}>
              {approvals.slice(0, 3).map((approval, index) => (
                <div key={approval.id || index} style={{ padding: 14, borderRadius: 14, background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{approval.tool || 'Sensitive action'}</div>
                    <Badge color={approval.risk === 'high' ? 'red' : approval.risk === 'low' ? 'blue' : 'orange'}>
                      {approval.risk || 'medium'}
                    </Badge>
                  </div>
                  <div style={{ marginTop: 6, fontSize: 12, color: 'var(--text-3)' }}>
                    {approval.target || 'Awaiting decision'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <SectionLabel>Operational view</SectionLabel>
      <div style={{ padding: '0 24px', display: 'grid', gridTemplateColumns: '1.05fr 0.95fr', gap: 12 }}>
        <Card style={{ padding: 18 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
            <div>
              <div style={{ fontSize: 16, fontWeight: 600 }}>Service health</div>
              <div style={{ color: 'var(--text-3)', fontSize: 12, marginTop: 4 }}>Latency and runtime status across the local stack</div>
            </div>
            <Badge color={upCount === serviceEntries.length ? 'green' : 'orange'}>{upCount === serviceEntries.length ? 'Healthy' : 'Degraded'}</Badge>
          </div>

          <div style={{ display: 'grid', gap: 8 }}>
            {serviceEntries.length === 0 ? (
              <div style={{ color: 'var(--text-3)', fontSize: 13 }}>Waiting for service health.</div>
            ) : (
              serviceEntries.map(([name, item]) => (
                <div
                  key={name}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'minmax(0, 1fr) auto auto',
                    gap: 12,
                    alignItems: 'center',
                    padding: '12px 14px',
                    borderRadius: 12,
                    background: 'var(--surface-2)',
                    border: '1px solid var(--border)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                    <StatusDot status={item.status || 'unknown'} />
                    <span className="mono" style={{ fontSize: 12 }}>{name}</span>
                  </div>
                  <span style={{ fontSize: 12, color: 'var(--text-3)' }}>{item.latency_ms ? `${item.latency_ms} ms` : 'pending'}</span>
                  <Badge color={item.status === 'up' || item.status === 'running' ? 'green' : item.status === 'degraded' ? 'orange' : 'red'}>
                    {item.status || 'unknown'}
                  </Badge>
                </div>
              ))
            )}
          </div>
        </Card>

        <Card style={{ padding: 18 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
            <div>
              <div style={{ fontSize: 16, fontWeight: 600 }}>Live activity</div>
              <div style={{ color: 'var(--text-3)', fontSize: 12, marginTop: 4 }}>Recent event flow from the runtime and policy engine</div>
            </div>
            <Badge color="blue">{activity.length} events</Badge>
          </div>

          <div style={{ display: 'grid', gap: 10 }}>
            {activity.length === 0 ? (
              <div style={{ color: 'var(--text-3)', fontSize: 13 }}>Waiting for new activity.</div>
            ) : (
              activity.map((event) => (
                <div key={event.id} style={{ padding: 14, borderRadius: 14, background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
                    <span className="mono" style={{ fontSize: 11, color: 'var(--text-2)' }}>{event.type || 'event'}</span>
                    <Ts value={event.data?.timestamp || event.timestamp || Date.now()} />
                  </div>
                  <div style={{ marginTop: 8, color: 'var(--text-3)', fontSize: 12, lineHeight: 1.5 }}>
                    {eventSummary(event)}
                  </div>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>
    </div>
  )
}

function MetricPanel({ label, value, tone }: { label: string; value: string | number; tone: 'blue' | 'green' | 'orange' | 'gray' }) {
  const color =
    tone === 'green' ? 'var(--green)' : tone === 'orange' ? 'var(--orange)' : tone === 'blue' ? 'var(--blue)' : 'var(--text)'
  return (
    <div
      style={{
        borderRadius: 18,
        padding: 16,
        border: '1px solid var(--border)',
        background: 'rgba(255,255,255,0.05)',
      }}
    >
      {metricValue(value)}
      <div style={{ marginTop: 6, fontSize: 12, color }}>{label}</div>
    </div>
  )
}

function SmallMetric({ label, value, tone }: { label: string; value: string | number; tone?: string }) {
  return (
    <div style={{ borderRadius: 12, padding: 12, background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
      <div style={{ fontSize: 24, fontWeight: 700, letterSpacing: '-0.04em', color: tone || 'var(--text)' }}>{value}</div>
      <div style={{ marginTop: 4, color: 'var(--text-3)', fontSize: 12 }}>{label}</div>
    </div>
  )
}

function eventSummary(event: EventRecord) {
  const data = event.data || {}
  if (event.type === 'workflow_progress') {
    return `${data.id || 'workflow'} is ${data.status || 'running'}${data.output ? `: ${String(data.output).slice(0, 90)}` : ''}`
  }
  if (event.type === 'workflow_error') {
    return `${data.id || 'workflow'} failed${data.error ? `: ${String(data.error).slice(0, 90)}` : ''}`
  }
  if (event.type === 'service_health') {
    return 'Service health snapshot refreshed.'
  }
  if (event.type === 'audit_event') {
    return JSON.stringify(data).slice(0, 110)
  }
  return JSON.stringify(data).slice(0, 110) || 'No details yet.'
}
