/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { useEffect, useMemo, useState } from 'react'
import { Badge, Card, Empty, PageHeader, PanelHeader, Skeleton, SkeletonText, StatusDot, Ts } from '../components/ui.jsx'
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
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [categoryFilter, setCategoryFilter] = useState('all')
  const [selectedId, setSelectedId] = useState('')

  useEffect(() => {
    setLoading(true)
    Promise.all([commandCenterApi.listTraces(), commandCenterApi.listEvals()])
      .then(([traceData, evalData]) => {
        setTraces(Array.isArray(traceData) ? traceData : [])
        setEvals(Array.isArray(evalData) ? evalData : [])
      })
      .catch(() => setMessage('Failed to load traces or evals'))
      .finally(() => setLoading(false))
  }, [])

  const statusOptions = useMemo(
    () => ['all', ...Array.from(new Set(traces.map((trace) => trace.status).filter(Boolean)))],
    [traces],
  )
  const categoryOptions = useMemo(
    () => ['all', ...Array.from(new Set(traces.map((trace) => trace.category).filter(Boolean)))],
    [traces],
  )

  const filteredTraces = useMemo(() => {
    const query = search.trim().toLowerCase()
    return traces.filter((trace) => {
      if (statusFilter !== 'all' && trace.status !== statusFilter) return false
      if (categoryFilter !== 'all' && trace.category !== categoryFilter) return false
      if (!query) return true
      const haystack = [
        trace.title,
        trace.category,
        trace.pack_id,
        trace.provider,
        ...(trace.tools || []),
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
      return haystack.includes(query)
    })
  }, [categoryFilter, search, statusFilter, traces])

  useEffect(() => {
    if (!filteredTraces.length) {
      setSelectedId('')
      return
    }
    if (!selectedId || !filteredTraces.some((trace) => trace.id === selectedId)) {
      setSelectedId(filteredTraces[0].id)
    }
  }, [filteredTraces, selectedId])

  const selectedTrace = useMemo(
    () => filteredTraces.find((trace) => trace.id === selectedId) || null,
    [filteredTraces, selectedId],
  )

  const exportFiltered = () => {
    const payload = {
      exported_at: new Date().toISOString(),
      filters: {
        search,
        status: statusFilter,
        category: categoryFilter,
      },
      traces: filteredTraces,
      evals,
    }

    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'clawos-traces-export.json'
    link.click()
    URL.revokeObjectURL(url)
    setMessage(`Exported ${filteredTraces.length} trace${filteredTraces.length === 1 ? '' : 's'} to clawos-traces-export.json`)
  }

  return (
    <div className="fade-up" style={{ padding: '0 0 48px' }}>
      <div style={{ padding: '32px 24px 18px' }}>
        <PageHeader
          eyebrow="Traces"
          title="Trace history with filters, timeline context, and export."
          description="Inspect recent activity across packs, setup, providers, and delegated work. Narrow the stream, then export the exact window you want to review."
          meta={
            <>
              <Badge color="blue">{filteredTraces.length} visible</Badge>
              <Badge color="gray">{evals.length} eval suites</Badge>
            </>
          }
          actions={<button className="btn primary" onClick={exportFiltered} disabled={loading || filteredTraces.length === 0}>Export filtered traces</button>}
        />
      </div>

      <div style={{ padding: '0 20px 16px' }}>
        <Card style={{ padding: 16 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1.3fr 0.7fr 0.7fr', gap: 10 }}>
            <input
              placeholder="Search traces, pack ids, providers, or tools"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              style={{
                width: '100%',
                padding: '11px 14px',
                borderRadius: 12,
                border: '1px solid var(--border)',
                background: 'var(--surface)',
                color: 'var(--text)',
                outline: 'none',
              }}
            />
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
              style={{
                width: '100%',
                padding: '11px 14px',
                borderRadius: 12,
                border: '1px solid var(--border)',
                background: 'var(--surface)',
                color: 'var(--text)',
                outline: 'none',
              }}
            >
              {statusOptions.map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
            <select
              value={categoryFilter}
              onChange={(event) => setCategoryFilter(event.target.value)}
              style={{
                width: '100%',
                padding: '11px 14px',
                borderRadius: 12,
                border: '1px solid var(--border)',
                background: 'var(--surface)',
                color: 'var(--text)',
                outline: 'none',
              }}
            >
              {categoryOptions.map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
          </div>
        </Card>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.08fr 0.92fr', gap: 14, padding: '0 20px' }}>
        <Card style={{ padding: 18 }}>
          <PanelHeader
            eyebrow="Timeline"
            title="Recent traces"
            description="A filterable event stream across setup, packs, providers, research, and delegated work."
            aside={<Badge color="blue">{filteredTraces.length}</Badge>}
          />

          {loading ? (
            <div style={{ display: 'grid', gap: 10 }}>
              {Array.from({ length: 3 }).map((_, index) => (
                <Card key={index} style={{ padding: 14, background: 'var(--surface)' }}>
                  <Skeleton width="34%" height={14} />
                  <div style={{ height: 10 }} />
                  <SkeletonText lines={3} />
                </Card>
              ))}
            </div>
          ) : filteredTraces.length === 0 ? (
            <Empty>No traces matched the current filters.</Empty>
          ) : (
            <div style={{ display: 'grid', gap: 10 }}>
              {filteredTraces.map((trace) => {
                const selected = trace.id === selectedId
                return (
                  <button
                    key={trace.id}
                    type="button"
                    onClick={() => setSelectedId(trace.id)}
                    className="glass"
                    style={{
                      padding: 14,
                      textAlign: 'left',
                      borderRadius: 16,
                      border: selected ? '1px solid rgba(77, 143, 247, 0.36)' : '1px solid var(--border)',
                      background: selected ? 'rgba(77, 143, 247, 0.08)' : 'var(--surface-2)',
                      display: 'grid',
                      gap: 10,
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'flex-start' }}>
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <StatusDot status={trace.status === 'failed' ? 'failed' : trace.status === 'completed' ? 'completed' : 'active'} />
                          <div style={{ fontSize: 14, fontWeight: 600 }}>{trace.title}</div>
                        </div>
                        <div style={{ marginTop: 6, color: 'var(--text-3)', fontSize: 12 }}>
                          {trace.category}{trace.pack_id ? ` - ${trace.pack_id}` : ''}{trace.provider ? ` - ${trace.provider}` : ''}
                        </div>
                      </div>
                      <div style={{ display: 'grid', justifyItems: 'end', gap: 6 }}>
                        <Badge color={STATUS_COLORS[trace.status] || 'gray'}>{trace.status}</Badge>
                        <Ts value={trace.finished_at || trace.started_at || Date.now()} />
                      </div>
                    </div>

                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      {(trace.tools || []).slice(0, 4).map((tool) => <Badge key={tool} color="gray">{tool}</Badge>)}
                      {trace.approvals ? <Badge color="orange">{trace.approvals} approvals</Badge> : null}
                      {trace.citations ? <Badge color="blue">{trace.citations} citations</Badge> : null}
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </Card>

        <div style={{ display: 'grid', gap: 14 }}>
          <Card style={{ padding: 18 }}>
            <PanelHeader
              eyebrow="Detail"
              title={selectedTrace ? selectedTrace.title : 'Trace detail'}
              description={selectedTrace ? 'The exact metadata and posture for the selected trace.' : 'Select a trace to inspect metadata, tools, and timing.'}
              aside={selectedTrace ? <Badge color={STATUS_COLORS[selectedTrace.status] || 'gray'}>{selectedTrace.status}</Badge> : null}
            />

            {selectedTrace ? (
              <div style={{ display: 'grid', gap: 16 }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <Detail label="Category" value={selectedTrace.category} />
                  <Detail label="Provider" value={selectedTrace.provider || 'local-first'} />
                  <Detail label="Pack" value={selectedTrace.pack_id || 'none'} />
                  <Detail label="Approvals" value={String(selectedTrace.approvals || 0)} />
                </div>

                <div>
                  <div className="section-label">Tools</div>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
                    {(selectedTrace.tools || []).length ? (
                      (selectedTrace.tools || []).map((tool) => <Badge key={tool} color="gray">{tool}</Badge>)
                    ) : (
                      <Badge color="gray">none recorded</Badge>
                    )}
                  </div>
                </div>

                <div className="glass" style={{ padding: 14 }}>
                  <div className="section-label">Metadata</div>
                  <pre
                    style={{
                      margin: '8px 0 0',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      color: 'var(--text-2)',
                      fontSize: 11,
                      fontFamily: 'var(--font-mono)',
                    }}
                  >
                    {JSON.stringify(selectedTrace.metadata || {}, null, 2) || '{}'}
                  </pre>
                </div>
              </div>
            ) : (
              <Empty>Select a trace from the timeline to inspect it.</Empty>
            )}
          </Card>

          <Card style={{ padding: 18 }}>
            <PanelHeader
              eyebrow="Quality gates"
              title="Eval suites"
              description="Release confidence checks aligned to packs and demo quality."
              aside={<Badge color="gray">{evals.length}</Badge>}
            />

            {loading ? (
              <div style={{ display: 'grid', gap: 10 }}>
                {Array.from({ length: 2 }).map((_, index) => (
                  <Card key={index} style={{ padding: 14, background: 'var(--surface)' }}>
                    <Skeleton width="42%" height={14} />
                    <div style={{ height: 10 }} />
                    <SkeletonText lines={2} />
                  </Card>
                ))}
              </div>
            ) : evals.length === 0 ? (
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

                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 10 }}>
                      {(suite.checks || []).map((check) => <Badge key={check} color="gray">{check}</Badge>)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>

      {message && (
        <div style={{ padding: '16px 20px 0' }}>
          <Card style={{ padding: 14, color: 'var(--text-2)' }}>{message}</Card>
        </div>
      )}
    </div>
  )
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="glass" style={{ padding: 14 }}>
      <div className="section-label">{label}</div>
      <div className="mono" style={{ marginTop: 6 }}>{value}</div>
    </div>
  )
}
