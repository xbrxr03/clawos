import { useEffect, useState } from 'react'
import { Badge, Card, Empty, SectionLabel, Ts } from '../components/ui.jsx'
import { commandCenterApi, type EvalSuite, type TraceRecord } from '../lib/commandCenterApi'

const STATUS_COLORS: Record<string, string> = {
  completed: 'green',
  planned: 'blue',
  warning: 'orange',
  failed: 'red',
}

export function TracesPage() {
  const [traces, setTraces] = useState<TraceRecord[]>([])
  const [evals, setEvals] = useState<EvalSuite[]>([])
  const [message, setMessage] = useState('')

  useEffect(() => {
    Promise.all([commandCenterApi.listTraces(), commandCenterApi.listEvals()])
      .then(([traceData, evalData]) => {
        setTraces(Array.isArray(traceData) ? traceData : [])
        setEvals(Array.isArray(evalData) ? evalData : [])
      })
      .catch(() => setMessage('Failed to load traces or evals'))
  }, [])

  return (
    <div className="fade-up" style={{ padding: '0 0 48px' }}>
      <div style={{ padding: '32px 24px 18px' }}>
        <div style={{ fontSize: 28, fontWeight: 700, letterSpacing: '-0.05em' }}>Traces</div>
        <div style={{ fontSize: 14, color: 'var(--text-3)', marginTop: 6, maxWidth: 720 }}>
          Local trace history, pack activity, provider posture, and eval suites that define release confidence.
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 0.9fr', gap: 14, padding: '0 20px' }}>
        <Card style={{ padding: 18 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
            <div>
              <div style={{ fontSize: 18, fontWeight: 600 }}>Recent traces</div>
              <div style={{ color: 'var(--text-3)', fontSize: 12, marginTop: 4 }}>Platform activity captured across setup, providers, packs, and delegated work.</div>
            </div>
            <Badge color="blue">{traces.length}</Badge>
          </div>

          {traces.length === 0 ? (
            <Empty>No traces have been recorded yet.</Empty>
          ) : (
            <div style={{ display: 'grid', gap: 10 }}>
              {traces.map((trace) => (
                <div key={trace.id} className="glass" style={{ padding: 14 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 600 }}>{trace.title}</div>
                      <div style={{ marginTop: 6, color: 'var(--text-3)', fontSize: 12 }}>
                        {trace.category}{trace.pack_id ? ` - ${trace.pack_id}` : ''}{trace.provider ? ` - ${trace.provider}` : ''}
                      </div>
                    </div>
                    <div style={{ display: 'grid', justifyItems: 'end', gap: 6 }}>
                      <Badge color={STATUS_COLORS[trace.status] || 'gray'}>{trace.status}</Badge>
                      <Ts value={trace.finished_at || trace.started_at || Date.now()} />
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 10 }}>
                    {(trace.tools || []).map((tool) => <Badge key={tool} color="gray">{tool}</Badge>)}
                    {trace.approvals ? <Badge color="orange">{trace.approvals} approvals</Badge> : null}
                    {trace.citations ? <Badge color="blue">{trace.citations} citations</Badge> : null}
                  </div>

                  {trace.metadata && Object.keys(trace.metadata).length > 0 && (
                    <div className="mono" style={{ marginTop: 10, fontSize: 11, color: 'var(--text-3)', whiteSpace: 'pre-wrap' }}>
                      {JSON.stringify(trace.metadata, null, 2)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card style={{ padding: 18 }}>
          <div style={{ fontSize: 18, fontWeight: 600 }}>Eval suites</div>
          <div style={{ color: 'var(--text-3)', fontSize: 12, marginTop: 4, marginBottom: 14 }}>
            Quality gates for the packs that define ClawOS competitive posture.
          </div>

          {evals.length === 0 ? (
            <Empty>No eval suites are registered yet.</Empty>
          ) : (
            <div style={{ display: 'grid', gap: 10 }}>
              {evals.map((suite) => (
                <div key={suite.id} className="glass" style={{ padding: 14 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
                    <div>
                      <div style={{ fontWeight: 600 }}>{suite.name}</div>
                      <div style={{ color: 'var(--text-3)', fontSize: 12, marginTop: 6 }}>{suite.description}</div>
                    </div>
                    <div style={{ display: 'grid', justifyItems: 'end', gap: 6 }}>
                      <Badge color={suite.active ? 'green' : 'gray'}>{suite.active ? 'active' : 'available'}</Badge>
                      <Badge color="blue">{suite.pack_id}</Badge>
                    </div>
                  </div>

                  <SectionLabel>Checks</SectionLabel>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {(suite.checks || []).map((check) => <Badge key={check} color="gray">{check}</Badge>)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {message && (
        <div style={{ padding: '16px 20px 0' }}>
          <Card style={{ padding: 14, color: 'var(--text-2)' }}>{message}</Card>
        </div>
      )}
    </div>
  )
}
