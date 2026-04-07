/* SPDX-License-Identifier: AGPL-3.0-or-later */
type InspectorRailProps = {
  approvals: any[]
  services: Record<string, any>
  events: any[]
}

export function InspectorRail({ approvals, services, events }: InspectorRailProps) {
  const serviceEntries = Object.entries(services || {}).slice(0, 6)
  const eventEntries = events.slice(0, 8)

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: 18, borderBottom: '1px solid var(--sep)' }}>
        <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.1em', color: 'var(--text-3)', textTransform: 'uppercase' }}>
          Inspector
        </div>
      </div>

      <div style={{ padding: 18, borderBottom: '1px solid var(--sep)' }}>
        <div className="section-label">Approvals</div>
        <div className="glass" style={{ padding: 14 }}>
          <div style={{ fontSize: 28, fontWeight: 700, letterSpacing: '-0.04em' }}>{approvals.length}</div>
          <div style={{ marginTop: 6, fontSize: 12, color: 'var(--text-3)' }}>Awaiting human review</div>
        </div>
      </div>

      <div style={{ padding: 18, borderBottom: '1px solid var(--sep)' }}>
        <div className="section-label">Services</div>
        <div className="glass" style={{ overflow: 'hidden' }}>
          {serviceEntries.length === 0 ? (
            <div className="row"><span style={{ color: 'var(--text-3)' }}>No data yet</span></div>
          ) : (
            serviceEntries.map(([name, item]) => (
              <div key={name} className="row">
                <span className={`dot ${(item?.status === 'up' || item?.status === 'running') ? 'green' : item?.status === 'degraded' ? 'orange' : 'red'}`} />
                <div style={{ flex: 1 }}>
                  <div className="mono" style={{ fontSize: 12 }}>{name}</div>
                </div>
                <span className="ts">{item?.latency_ms ? `${item.latency_ms}ms` : '—'}</span>
              </div>
            ))
          )}
        </div>
      </div>

      <div style={{ padding: 18, minHeight: 0, flex: 1 }}>
        <div className="section-label">Activity</div>
        <div className="glass" style={{ height: '100%', overflow: 'auto' }}>
          {eventEntries.length === 0 ? (
            <div className="row"><span style={{ color: 'var(--text-3)' }}>Waiting for activity</span></div>
          ) : (
            eventEntries.map((event, index) => (
              <div key={`${event.type}-${index}`} className="row" style={{ alignItems: 'flex-start' }}>
                <span className="dot blue" style={{ marginTop: 6 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 600 }}>{event.type}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 3, wordBreak: 'break-word' }}>
                    {JSON.stringify(event.data ?? event).slice(0, 120)}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
