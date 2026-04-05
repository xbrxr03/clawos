import { useEffect, useMemo, useState } from 'react'
import { Badge, Card, Empty, SectionLabel } from '../components/ui.jsx'
import { commandCenterApi, type WorkflowRecord } from '../lib/commandCenterApi'

const CATEGORIES = ['all', 'files', 'documents', 'developer', 'content', 'system', 'data']

const CATEGORY_COLORS: Record<string, string> = {
  files: 'blue',
  documents: 'purple',
  developer: 'green',
  content: 'orange',
  system: 'red',
  data: 'blue',
}

type HistoryEntry = {
  id: string
  name: string
  status: string
  ts: number
}

function formatPlatforms(workflow: WorkflowRecord) {
  if (!workflow.platforms || workflow.platforms.length === 0) return 'all platforms'
  return workflow.platforms.join(', ')
}

export function Workflows() {
  const [workflows, setWorkflows] = useState<WorkflowRecord[]>([])
  const [category, setCategory] = useState('all')
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [runningId, setRunningId] = useState<string | null>(null)
  const [output, setOutput] = useState('')
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    setError('')
    commandCenterApi
      .listWorkflows({ category, search })
      .then((data) => setWorkflows(Array.isArray(data) ? data : []))
      .catch((err) => setError(err.message || 'Failed to load workflows'))
      .finally(() => setLoading(false))
  }, [category, search])

  useEffect(() => {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const socket = new WebSocket(`${proto}://${window.location.host}/ws`)
    socket.onmessage = ({ data }) => {
      try {
        const message = JSON.parse(data)
        if (message.type === 'workflow_progress' && message.data) {
          if (message.data.status !== 'running') setRunningId(null)
          if (message.data.output) setOutput(message.data.output)
        }
        if (message.type === 'workflow_error' && message.data) {
          setRunningId(null)
          setOutput(`Error: ${message.data.error}`)
        }
      } catch {}
    }
    return () => socket.close()
  }, [])

  useEffect(() => {
    if (!workflows.length) {
      setSelectedId(null)
      return
    }
    if (!selectedId || !workflows.some((workflow) => workflow.id === selectedId)) {
      setSelectedId(workflows[0].id)
    }
  }, [selectedId, workflows])

  const selectedWorkflow = useMemo(
    () => workflows.find((workflow) => workflow.id === selectedId) || null,
    [selectedId, workflows]
  )

  const stats = useMemo(() => {
    const direct = workflows.filter((workflow) => !workflow.needs_agent).length
    const agent = workflows.filter((workflow) => workflow.needs_agent).length
    const destructive = workflows.filter((workflow) => workflow.destructive).length
    return { total: workflows.length, direct, agent, destructive }
  }, [workflows])

  async function runWorkflow(workflow: WorkflowRecord) {
    setSelectedId(workflow.id)
    setRunningId(workflow.id)
    setOutput('')
    setError('')
    try {
      const result = await commandCenterApi.runWorkflow(workflow.id)
      const text = result.output || result.error || ''
      setOutput(text)
      setHistory((current) => [
        { id: workflow.id, name: workflow.name, status: result.status || 'ok', ts: Date.now() },
        ...current,
      ].slice(0, 12))
    } catch (err: any) {
      setError(err.message || 'Failed to run workflow')
    } finally {
      setRunningId(null)
    }
  }

  return (
    <div className="fade-up" style={{ padding: '0 0 48px' }}>
      <div style={{ padding: '32px 24px 18px' }}>
        <div style={{ fontSize: 28, fontWeight: 700, letterSpacing: '-0.05em' }}>Workflow Library</div>
        <div style={{ fontSize: 14, color: 'var(--text-3)', marginTop: 6, maxWidth: 720 }}>
          Local-first automations for repository work, document handling, system cleanup, and daily operations.
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 10, padding: '0 20px 16px' }}>
        <MetricCard label="Available" value={stats.total} tone="blue" />
        <MetricCard label="Direct" value={stats.direct} tone="green" />
        <MetricCard label="Agent" value={stats.agent} tone="purple" />
        <MetricCard label="Guarded" value={stats.destructive} tone="orange" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.15fr 0.85fr', gap: 14, padding: '0 20px' }}>
        <div style={{ display: 'grid', gap: 14 }}>
          <Card style={{ padding: 16 }}>
            <div style={{ display: 'grid', gap: 12 }}>
              <input
                placeholder="Search workflows, tags, or categories"
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
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {CATEGORIES.map((item) => (
                  <button
                    key={item}
                    className={`btn${category === item ? ' primary' : ''}`}
                    style={{ minHeight: 34, padding: '0 12px' }}
                    onClick={() => setCategory(item)}
                  >
                    {item}
                  </button>
                ))}
              </div>
            </div>
          </Card>

          <SectionLabel>{loading ? 'Loading library' : `${workflows.length} workflows`}</SectionLabel>
          {loading ? (
            <Card><Empty>Loading workflows...</Empty></Card>
          ) : error ? (
            <Card><Empty>{error}</Empty></Card>
          ) : workflows.length === 0 ? (
            <Card><Empty>No workflows matched the current filters.</Empty></Card>
          ) : (
            <div style={{ display: 'grid', gap: 10 }}>
              {workflows.map((workflow) => {
                const selected = selectedId === workflow.id
                return (
                  <div
                    key={workflow.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => setSelectedId(workflow.id)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault()
                        setSelectedId(workflow.id)
                      }
                    }}
                    style={{
                      textAlign: 'left',
                      padding: 0,
                      background: 'transparent',
                      cursor: 'pointer',
                    }}
                  >
                    <Card
                      style={{
                        padding: 18,
                        borderColor: selected ? 'rgba(77, 143, 247, 0.28)' : undefined,
                        boxShadow: selected ? '0 22px 52px rgba(15, 23, 42, 0.18)' : undefined,
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                            <div style={{ fontSize: 16, fontWeight: 600 }}>{workflow.name}</div>
                            <Badge color={CATEGORY_COLORS[workflow.category] || 'blue'}>{workflow.category}</Badge>
                            <Badge color={workflow.needs_agent ? 'purple' : 'green'}>
                              {workflow.needs_agent ? 'agent' : 'direct'}
                            </Badge>
                            {workflow.destructive ? <Badge color="orange">guarded</Badge> : null}
                          </div>
                          <div style={{ marginTop: 8, color: 'var(--text-2)', lineHeight: 1.55 }}>
                            {workflow.description}
                          </div>
                        </div>

                        <button
                          className={`btn${runningId === workflow.id ? '' : ' primary'}`}
                          disabled={!!runningId}
                          onClick={(event) => {
                            event.stopPropagation()
                            runWorkflow(workflow)
                          }}
                        >
                          {runningId === workflow.id ? 'Running...' : 'Run'}
                        </button>
                      </div>

                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 12 }}>
                        <Badge color="gray">{formatPlatforms(workflow)}</Badge>
                        {workflow.requires?.length ? <Badge color="gray">requires {workflow.requires.join(', ')}</Badge> : null}
                      </div>
                    </Card>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        <div style={{ display: 'grid', gap: 14 }}>
          <Card style={{ padding: 18 }}>
            <div className="section-label">Execution</div>
            {selectedWorkflow ? (
              <div style={{ display: 'grid', gap: 14 }}>
                <div>
                  <div style={{ fontSize: 20, fontWeight: 700, letterSpacing: '-0.03em' }}>{selectedWorkflow.name}</div>
                  <div style={{ marginTop: 6, color: 'var(--text-3)', lineHeight: 1.55 }}>
                    {selectedWorkflow.description}
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <Badge color={CATEGORY_COLORS[selectedWorkflow.category] || 'blue'}>{selectedWorkflow.category}</Badge>
                  <Badge color={selectedWorkflow.needs_agent ? 'purple' : 'green'}>
                    {selectedWorkflow.needs_agent ? 'agent-mediated' : 'direct run'}
                  </Badge>
                  <Badge color="gray">{formatPlatforms(selectedWorkflow)}</Badge>
                  {selectedWorkflow.destructive ? <Badge color="orange">approval-sensitive</Badge> : null}
                </div>

                <button className="btn primary" disabled={!!runningId} onClick={() => runWorkflow(selectedWorkflow)}>
                  {runningId === selectedWorkflow.id ? 'Running selected workflow...' : 'Run Selected Workflow'}
                </button>

                <div className="glass" style={{ padding: 14 }}>
                  <div className="section-label">Output</div>
                  <pre
                    style={{
                      margin: 0,
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      minHeight: 220,
                      maxHeight: 320,
                      overflowY: 'auto',
                      color: output ? 'var(--text-2)' : 'var(--text-3)',
                      fontSize: 12,
                      fontFamily: 'var(--font-mono)',
                    }}
                  >
                    {output || 'Run a workflow to inspect output, errors, or generated notes here.'}
                  </pre>
                </div>
              </div>
            ) : (
              <Empty>Select a workflow from the library to inspect and run it.</Empty>
            )}
          </Card>

          <Card style={{ padding: 18 }}>
            <div className="section-label">Recent runs</div>
            {history.length === 0 ? (
              <Empty>No workflow runs yet.</Empty>
            ) : (
              <div style={{ display: 'grid', gap: 10 }}>
                {history.map((entry) => (
                  <div
                    key={`${entry.id}-${entry.ts}`}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      gap: 12,
                      padding: '12px 14px',
                      borderRadius: 12,
                      background: 'var(--surface)',
                      border: '1px solid var(--border)',
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 600 }}>{entry.name}</div>
                      <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 4 }}>
                        {new Date(entry.ts).toLocaleTimeString()}
                      </div>
                    </div>
                    <Badge color={entry.status === 'ok' ? 'green' : 'red'}>{entry.status}</Badge>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}

function MetricCard({ label, value, tone }: { label: string; value: number; tone: 'blue' | 'green' | 'purple' | 'orange' }) {
  const toneValue = {
    blue: 'var(--blue)',
    green: 'var(--green)',
    purple: 'var(--purple)',
    orange: 'var(--orange)',
  }[tone]

  return (
    <Card style={{ padding: 18 }}>
      <div style={{ fontSize: 12, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>{label}</div>
      <div style={{ marginTop: 8, fontSize: 30, lineHeight: 1, fontWeight: 700, letterSpacing: '-0.05em', color: toneValue }}>
        {value}
      </div>
    </Card>
  )
}
