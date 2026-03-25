import { Card, Row, Dot, Badge, Stat, AppIcon, SectionLabel, Time } from '../components/ui.jsx'

export function Overview({ services, tasks, approvals, events, models }) {
  const counts = {
    active:    tasks.active?.length    ?? 0,
    queued:    tasks.queued?.length    ?? 0,
    failed:    tasks.failed?.length    ?? 0,
    completed: tasks.completed?.length ?? 0,
  }
  const serviceList = Object.entries(services)
  const upCount = serviceList.filter(([,s]) => s.status === 'up').length

  return (
    <div className="p-6 overflow-y-auto h-full space-y-1 fade-up">

      {/* Hero stats */}
      <SectionLabel>Runtime</SectionLabel>
      <Card>
        <div className="grid grid-cols-4 divide-x" style={{ divideColor: 'rgba(255,255,255,0.08)' }}>
          {[
            { label: 'Active',    value: counts.active,    color: '#30d158' },
            { label: 'Queued',    value: counts.queued,    color: '#0a84ff' },
            { label: 'Failed',    value: counts.failed,    color: '#ff453a' },
            { label: 'Done',      value: counts.completed, color: 'rgba(255,255,255,0.4)' },
          ].map(({ label, value, color }) => (
            <div key={label} className="py-5" style={{ borderRight: '1px solid rgba(255,255,255,0.06)' }}>
              <Stat value={value} label={label} color={color} />
            </div>
          ))}
        </div>
      </Card>

      {/* Services */}
      <SectionLabel>Services — {upCount}/{serviceList.length} up</SectionLabel>
      <Card>
        {serviceList.length === 0 ? (
          <div className="px-4 py-4 text-sm" style={{ color: 'rgba(255,255,255,0.3)' }}>
            Polling services...
          </div>
        ) : serviceList.map(([name, info]) => (
          <Row
            key={name}
            left={<Dot status={info.status} />}
            center={
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">{name}</span>
                <span className="text-xs tabular" style={{ color: 'rgba(255,255,255,0.3)' }}>:{info.port}</span>
              </div>
            }
            right={
              <div className="flex items-center gap-2">
                {info.latency_ms != null && (
                  <span className="text-xs tabular" style={{ color: 'rgba(255,255,255,0.3)' }}>
                    {info.latency_ms}ms
                  </span>
                )}
                <Badge
                  color={info.status === 'up' ? '#30d158' : info.status === 'degraded' ? '#ff9f0a' : '#ff453a'}
                >
                  {info.status}
                </Badge>
              </div>
            }
          />
        ))}
      </Card>

      {/* Models */}
      {(models.models ?? []).length > 0 && (
        <>
          <SectionLabel>Models</SectionLabel>
          <Card>
            {(models.models ?? []).map(m => (
              <Row
                key={m.name}
                left={<Dot status={m.running ? 'active' : 'completed'} />}
                center={
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{m.name}</span>
                    {m.name === models.default && <Badge color="#0a84ff">default</Badge>}
                    {m.running && <Badge color="#30d158">running</Badge>}
                  </div>
                }
                right={
                  <span className="text-sm tabular" style={{ color: 'rgba(255,255,255,0.4)' }}>
                    {m.size_gb} GB
                  </span>
                }
              />
            ))}
          </Card>
        </>
      )}

      {/* Approvals */}
      {approvals.length > 0 && (
        <>
          <SectionLabel>Pending Approvals</SectionLabel>
          <Card>
            {approvals.slice(0, 3).map(a => (
              <Row
                key={a.id}
                left={
                  <div className="w-8 h-8 rounded-[8px] flex items-center justify-center text-sm"
                    style={{ background: '#ff9f0a22' }}>
                    ⚠️
                  </div>
                }
                center={
                  <div>
                    <div className="text-sm font-medium">{a.tool ?? 'action'}</div>
                    <div className="text-xs mt-0.5" style={{ color: 'rgba(255,255,255,0.3)' }}>
                      {a.agent ?? 'agent'} · {a.risk ?? 'medium'} risk
                    </div>
                  </div>
                }
                right={<Time value={a.created_at} />}
                chevron
              />
            ))}
          </Card>
        </>
      )}

      {/* Live events */}
      <SectionLabel>Live Events</SectionLabel>
      <Card>
        {events.length === 0 ? (
          <div className="px-4 py-4 text-sm" style={{ color: 'rgba(255,255,255,0.3)' }}>
            Waiting for events...
          </div>
        ) : events.slice(0, 8).map((evt, i) => (
          <Row
            key={i}
            left={
              <div className="w-1.5 h-1.5 rounded-full mt-1 flex-shrink-0"
                style={{
                  background: evt.type?.includes('error') ? '#ff453a'
                    : evt.type?.includes('approval') ? '#ff9f0a'
                    : 'rgba(255,255,255,0.2)'
                }}
              />
            }
            center={
              <span className="text-sm" style={{ color: 'rgba(255,255,255,0.6)' }}>
                {evt.type}
              </span>
            }
            right={<Time value={Date.now()} />}
          />
        ))}
      </Card>
    </div>
  )
}
