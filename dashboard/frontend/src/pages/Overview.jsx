import { StatCard, Card, Row, StatusDot, Badge, SectionLabel, Ts, Empty } from '../components/ui.jsx'

export function Overview({ services, tasks, approvals, events, models }) {
  const counts = {
    active:    tasks.active?.length    ?? 0,
    queued:    tasks.queued?.length    ?? 0,
    failed:    tasks.failed?.length    ?? 0,
    completed: tasks.completed?.length ?? 0,
  }

  const svcEntries = Object.entries(services)
  const upCount    = svcEntries.filter(([,s]) => s.status === 'up').length

  return (
    <div className="fade-up" style={{ padding: '0 0 48px' }}>
      {/* Header */}
      <div style={{ padding: '32px 24px 0' }}>
        <div style={{ fontSize: 24, fontWeight: 700, letterSpacing: '-0.5px' }}>Overview</div>
        <div style={{ fontSize: 13, color: 'var(--text-2)', marginTop: 4 }}>
          Agent runtime · {upCount}/{svcEntries.length} services up
        </div>
      </div>

      {/* Task counts */}
      <SectionLabel>Tasks</SectionLabel>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 10, padding: '0 20px' }}>
        <StatCard label="Active"    value={counts.active}    color="var(--green)"  />
        <StatCard label="Queued"    value={counts.queued}    color="var(--blue)"   />
        <StatCard label="Failed"    value={counts.failed}    color="var(--red)"    />
        <StatCard label="Completed" value={counts.completed} color="var(--text-2)" />
      </div>

      {/* Alert */}
      {approvals.length > 0 && (
        <div style={{ padding: '14px 20px 0' }}>
          <div style={{
            background: 'var(--orange-dim)',
            border: '1px solid rgba(251,146,60,0.25)',
            borderRadius: 'var(--radius-lg)',
            padding: '14px 16px',
            display: 'flex', alignItems: 'center', gap: 12,
          }}>
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path d="M9 2L16.5 15H1.5L9 2Z" stroke="#fb923c" strokeWidth="1.5" strokeLinejoin="round"/>
              <path d="M9 7v4M9 12.5v.5" stroke="#fb923c" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
            <div>
              <div style={{ fontWeight: 500, color: 'var(--orange)', fontSize: 13 }}>
                {approvals.length} pending approval{approvals.length > 1 ? 's' : ''}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-2)', marginTop: 2 }}>
                Agents waiting for human review
              </div>
            </div>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, padding: '0 20px', marginTop: 14 }}>
        {/* Services */}
        <div>
          <div className="section-label" style={{ padding: '0 0 8px' }}>Services</div>
          <Card>
            {svcEntries.length === 0 ? (
              <div className="row"><span style={{ color: 'var(--text-2)', fontSize: 13 }}>Polling…</span></div>
            ) : svcEntries.map(([name, s]) => (
              <Row
                key={name}
                left={<StatusDot status={s.status} />}
                center={<span className="mono" style={{ fontSize: 13 }}>{name}</span>}
                right={
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    {s.latency_ms != null && <span className="ts">{s.latency_ms}ms</span>}
                    <Badge color={s.status === 'up' ? 'green' : s.status === 'degraded' ? 'orange' : 'red'}>
                      {s.status}
                    </Badge>
                  </div>
                }
              />
            ))}
          </Card>
        </div>

        {/* Live events */}
        <div>
          <div className="section-label" style={{ padding: '0 0 8px' }}>Live events</div>
          <Card style={{ maxHeight: 280, overflowY: 'auto' }}>
            {events.length === 0 ? (
              <div className="row"><span style={{ color: 'var(--text-2)', fontSize: 13 }}>Waiting…</span></div>
            ) : events.slice(0, 30).map((e, i) => {
              const color = e.type?.includes('error') || e.type?.includes('fail') ? 'var(--red)'
                : e.type?.includes('approval') ? 'var(--orange)' : 'var(--green)'
              return (
                <Row
                  key={i}
                  left={<span style={{ width:6, height:6, borderRadius:'50%', background:color, flexShrink:0 }} />}
                  center={<span className="mono" style={{ fontSize: 11, color: 'var(--text-2)' }}>{e.type}</span>}
                  right={<Ts value={e.data?.timestamp ?? Date.now()} />}
                />
              )
            })}
          </Card>
        </div>
      </div>

      {/* Models */}
      <SectionLabel>Models</SectionLabel>
      <div style={{ padding: '0 20px' }}>
        <Card>
          {(models.models ?? []).length === 0 ? (
            <Empty>No models — is Ollama running?</Empty>
          ) : (models.models ?? []).map(m => (
            <Row
              key={m.name}
              left={<StatusDot status={m.running ? 'active' : 'completed'} />}
              center={
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span className="mono" style={{ fontSize: 13 }}>{m.name}</span>
                  {m.name === models.default && <Badge color="blue">default</Badge>}
                  {m.running && <Badge color="green">running</Badge>}
                </div>
              }
              right={<span className="ts">{m.size_gb} GB</span>}
            />
          ))}
        </Card>
      </div>
    </div>
  )
}
