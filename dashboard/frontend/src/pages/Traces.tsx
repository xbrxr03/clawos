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
      <div style={{ padding: '24px 20px 16px' }}>
        <PageHeader
          eyebrow="Traces"
          title="Console-style history with tighter filtering."
          description="Inspect recent activity across packs, setup, providers, research, and delegated work with a denser filter bar and a compact trace detail rail."
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
          <div style={{ display: 'grid', gridTemplateColumns: '1.25fr auto auto', gap: 10, alignItems: 'center' }}>
            <input
              placeholder="Search traces, pack ids, providers, or tools"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              style={{ borderRadius: 999 }}
            />
            <div className="seg">
              {statusOptions.map((option) => (
                <button
                  key={option}
                  className={`seg-btn${statusFilter === option ? ' active' : ''}`}
                  onClick={() => setStatusFilter(option)}
                >
                  {option}
                </button>
              ))}
            </div>
            <select
              value={categoryFilter}
              onChange={(event) => setCategoryFilter(event.target.value)}
              style={{ minWidth: 180 }}
            >
              {categoryOptions.map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
          </div>
        </Card>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.04fr 0.96fr', gap: 14, padding: '0 20px' }}>
        <Card style={{ padding: 18 }}>
          <PanelHeader
            eyebrow="Timeline"
            title="Recent traces"
            description="A filterable event stream across setup, packs, providers, research, and delegated work."
            aside={<Badge color="blue">{filteredTraces.length}</Badge>}
          />

          {loading ? (
            <div style={{ display: 'grid', gap: 10 }}>
              {Array.from({ length: 4 }).map((_, index) => (
                <Card key={index} style={{ padding: 14, background: 'var(--surface-2)' }}>
                  <Skeleton width="34%" height={12} />
                  <div style={{ height: 10 }} />
                  <SkeletonText lines={3} />
                </Card>
              ))}
            </div>
          ) : filteredTraces.length === 0 ? (
            <Empty>No traces matched the current filters.</Empty>
          ) : (
            <div className="table-shell">
              <table>
                <thead>
                  <tr>
                    <th>Trace</th>
                    <th>Status</th>
                    <th>Category</th>
                    <th>Finished</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTraces.map((trace) => {
                    const selected = trace.id === selectedId
                    return (
                      <tr
                        key={trace.id}
                        onClick={() => setSelectedId(trace.id)}
                        style={{ cursor: 'pointer', background: selected ? 'rgba(0, 122, 255, 0.08)' : undefined }}
                      >
                        <td>
                          <div style={{ display: 'grid', gap: 6 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <StatusDot status={trace.status === 'failed' ? 'failed' : trace.status === 'completed' ? 'completed' : 'active'} />
                              <span style={{ fontWeight: 600 }}>{trace.title}</span>
                            </div>
                            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                              {(trace.tools || []).slice(0, 3).map((tool) => <Badge key={tool} color="gray">{tool}</Badge>)}
                              {trace.approvals ? <Badge color="orange">{trace.approvals} approvals</Badge> : null}
                              {trace.citations ? <Badge color="blue">{trace.citations} citations</Badge> : null}
                            </div>
                          </div>
                        </td>
                        <td><Badge color={STATUS_COLORS[trace.status] || 'gray'}>{trace.status}</Badge></td>
                        <td>{trace.category}</td>
                        <td><Ts value={trace.finished_at || trace.started_at || Date.now()} /></td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
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
              <div style={{ display: 'grid', gap: 14 }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
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

                <div className="log-terminal" style={{ maxHeight: 320, overflowY: 'auto' }}>
                  {JSON.stringify(selectedTrace.metadata || {}, null, 2) || '{}'}
                </div>
              </div>
            ) : (
              <Empty>Select a trace from the timeline to inspect it.</Empty>
            )}
          </Card>

          <Card style={{ padding: 18 }}>
            <PanelHeader
              eyebrow="Quality Gates"
              title="Eval suites"
              description="Release confidence checks aligned to packs and demo quality."
              aside={<Badge color="gray">{evals.length}</Badge>}
            />

            {loading ? (
              <div style={{ display: 'grid', gap: 10 }}>
                {Array.from({ length: 2 }).map((_, index) => (
                  <Card key={index} style={{ padding: 14, background: 'var(--surface-2)' }}>
                    <Skeleton width="42%" height={12} />
                    <div style={{ height: 10 }} />
                    <SkeletonText lines={2} />
                  </Card>
                ))}
              </div>
            ) : evals.length === 0 ? (
              <Empty>No eval suites are registered yet.</Empty>
            ) : (
              <div className="grouped-list">
                {evals.map((suite) => (
                  <div key={suite.id} className="row" style={{ alignItems: 'flex-start' }}>
                    <span className={`dot ${suite.active ? 'green' : 'gray'}`} style={{ marginTop: 6 }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
                        <div style={{ fontWeight: 600 }}>{suite.name}</div>
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                          <Badge color={suite.active ? 'green' : 'gray'}>{suite.active ? 'active' : 'available'}</Badge>
                          <Badge color="blue">{suite.pack_id}</Badge>
                        </div>
                      </div>
                      <div style={{ marginTop: 6, color: 'var(--text-2)', fontSize: 12 }}>{suite.description}</div>
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
                        {(suite.checks || []).map((check) => <Badge key={check} color="gray">{check}</Badge>)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>

      {message ? (
        <div style={{ padding: '16px 20px 0' }}>
          <Card style={{ padding: 14, color: 'var(--text-2)' }}>{message}</Card>
        </div>
      ) : null}
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
