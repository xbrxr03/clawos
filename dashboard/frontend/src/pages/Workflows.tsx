/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { useEffect, useMemo, useState } from 'react'
import { Badge, Card, Empty, PageHeader, PanelHeader, SectionLabel, Skeleton, SkeletonText, StatusDot } from '../components/ui.jsx'
import { commandCenterApi, type WorkflowRecord, type WorkflowRunResult } from '../lib/commandCenterApi'

const CATEGORIES = ['all', 'files', 'documents', 'developer', 'content', 'system', 'data']
const HERO_WORKFLOW_IDS = new Set(['organize-downloads', 'summarize-pdf'])

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

type LiveProgress = {
  id: string
  status: string
  output?: string
  message?: string
  phase?: string
  progress?: number
  updatedAt: number
}

type WorkflowDraft = Record<string, string | boolean>

function formatPlatforms(workflow: WorkflowRecord) {
  if (!workflow.platforms || workflow.platforms.length === 0) return 'all platforms'
  return workflow.platforms.join(', ')
}

function formatBytes(value?: number) {
  if (!value || value <= 0) return '0B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = value
  let unit = units[0]
  for (const candidate of units) {
    unit = candidate
    if (size < 1024 || candidate === units[units.length - 1]) break
    size /= 1024
  }
  return unit === 'B' ? `${Math.round(size)}${unit}` : `${size.toFixed(1)}${unit}`
}

function normalizeProgressStatus(status?: string) {
  if (status === 'failed') return 'failed'
  if (status === 'queued') return 'queued'
  if (status === 'ok' || status === 'skipped') return 'completed'
  return 'running'
}

function progressColor(status?: string) {
  if (status === 'failed') return 'red'
  if (status === 'queued') return 'blue'
  if (status === 'ok' || status === 'skipped') return 'green'
  return 'orange'
}

function progressWidth(progress?: number, status?: string) {
  if (typeof progress === 'number') return `${Math.max(8, Math.min(100, progress))}%`
  if (status === 'queued') return '28%'
  if (status === 'ok' || status === 'skipped' || status === 'failed') return '100%'
  return '72%'
}

function defaultDraftFor(workflowId?: string | null): WorkflowDraft {
  if (workflowId === 'organize-downloads') return { target_dir: '', dry_run: true }
  if (workflowId === 'summarize-pdf') return { file: '' }
  return {}
}

function heroButtonLabel(workflowId: string, draft: WorkflowDraft) {
  if (workflowId === 'organize-downloads') {
    return draft.dry_run === false ? 'Organize Downloads Now' : 'Preview Downloads Cleanup'
  }
  if (workflowId === 'summarize-pdf') return 'Summarize PDF'
  return 'Run Selected Workflow'
}

function buildWorkflowArgs(workflowId: string, draft: WorkflowDraft) {
  if (workflowId === 'organize-downloads') {
    const args: Record<string, string | boolean> = { dry_run: draft.dry_run !== false }
    const targetDir = String(draft.target_dir || '').trim()
    if (targetDir) args.target_dir = targetDir
    return args
  }
  if (workflowId === 'summarize-pdf') {
    const file = String(draft.file || '').trim()
    return file ? { file } : {}
  }
  return {}
}

export function Workflows() {
  const [workflows, setWorkflows] = useState<WorkflowRecord[]>([])
  const [category, setCategory] = useState('all')
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [runningId, setRunningId] = useState<string | null>(null)
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [liveProgress, setLiveProgress] = useState<LiveProgress | null>(null)
  const [progressFeed, setProgressFeed] = useState<LiveProgress[]>([])
  const [results, setResults] = useState<Record<string, WorkflowRunResult>>({})
  const [drafts, setDrafts] = useState<Record<string, WorkflowDraft>>({})
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
          const next: LiveProgress = {
            id: message.data.id || runningId || 'workflow',
            status: message.data.status || 'running',
            output: message.data.output,
            message: message.data.message || message.data.output,
            phase: message.data.phase,
            progress: typeof message.data.progress === 'number' ? message.data.progress : undefined,
            updatedAt: Date.now(),
          }
          setLiveProgress(next)
          setProgressFeed((current) => [next, ...current].slice(0, 48))
          if (message.data.status && message.data.status !== 'running' && message.data.status !== 'queued') {
            setRunningId(null)
          }
        }
        if (message.type === 'workflow_error' && message.data) {
          const next: LiveProgress = {
            id: message.data.id || runningId || 'workflow',
            status: 'failed',
            output: message.data.error,
            message: message.data.message || message.data.error,
            phase: message.data.phase,
            progress: typeof message.data.progress === 'number' ? message.data.progress : 100,
            updatedAt: Date.now(),
          }
          setRunningId(null)
          setLiveProgress(next)
          setProgressFeed((current) => [next, ...current].slice(0, 48))
          setResults((current) => ({
            ...current,
            [next.id]: { ...(current[next.id] || {}), status: 'failed', error: message.data.error },
          }))
        }
      } catch {}
    }
    return () => socket.close()
  }, [runningId])

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

  useEffect(() => {
    if (!selectedWorkflow) return
    setDrafts((current) => {
      if (current[selectedWorkflow.id]) return current
      return { ...current, [selectedWorkflow.id]: defaultDraftFor(selectedWorkflow.id) }
    })
  }, [selectedWorkflow])

  const stats = useMemo(() => {
    const direct = workflows.filter((workflow) => !workflow.needs_agent).length
    const agent = workflows.filter((workflow) => workflow.needs_agent).length
    const destructive = workflows.filter((workflow) => workflow.destructive).length
    return { total: workflows.length, direct, agent, destructive }
  }, [workflows])

  const selectedDraft = selectedWorkflow ? drafts[selectedWorkflow.id] || defaultDraftFor(selectedWorkflow.id) : {}
  const selectedResult = selectedWorkflow ? results[selectedWorkflow.id] : undefined
  const selectedProgressFeed = useMemo(
    () => (selectedWorkflow ? progressFeed.filter((entry) => entry.id === selectedWorkflow.id).slice(0, 6) : []),
    [progressFeed, selectedWorkflow]
  )

  function updateDraft(workflowId: string, key: string, value: string | boolean) {
    setDrafts((current) => ({
      ...current,
      [workflowId]: { ...(current[workflowId] || defaultDraftFor(workflowId)), [key]: value },
    }))
  }

  async function runWorkflow(workflow: WorkflowRecord) {
    const args = buildWorkflowArgs(workflow.id, drafts[workflow.id] || defaultDraftFor(workflow.id))
    if (workflow.id === 'summarize-pdf' && !String(args.file || '').trim()) {
      setError('Enter a PDF path before running Summarize PDF.')
      return
    }

    setSelectedId(workflow.id)
    setRunningId(workflow.id)
    setLiveProgress({
      id: workflow.id,
      status: 'queued',
      message: 'Queued in the dashboard. Live workflow events will stream below.',
      progress: 4,
      updatedAt: Date.now(),
    })
    setResults((current) => ({ ...current, [workflow.id]: {} }))
    setError('')

    try {
      const result = await commandCenterApi.runWorkflow(workflow.id, {
        args,
        workspace: 'nexus_default',
      })
      setResults((current) => ({ ...current, [workflow.id]: result }))
      setHistory((current) => [
        { id: workflow.id, name: workflow.name, status: result.status || 'ok', ts: Date.now() },
        ...current,
      ].slice(0, 12))
    } catch (err: any) {
      const message = err.message || 'Failed to run workflow'
      setError(message)
      setResults((current) => ({
        ...current,
        [workflow.id]: { status: 'failed', error: message },
      }))
    } finally {
      setRunningId(null)
    }
  }

  const liveOutput =
    selectedResult?.output ||
    selectedResult?.error ||
    (liveProgress?.id === selectedWorkflow?.id ? liveProgress.output || liveProgress.message : '') ||
    ''

  return (
    <div className="fade-up" style={{ padding: '0 0 48px' }}>
      <div style={{ padding: '32px 24px 18px' }}>
        <PageHeader
          eyebrow="Workflow Library"
          title="Run the highest-value automations without leaving the dashboard."
          description="Search, filter, launch, and review deterministic workflows with live progress, hero inputs, and a local run history."
          meta={
            <>
              <Badge color="blue">{stats.total} available</Badge>
              <Badge color={runningId ? 'orange' : 'green'}>{runningId ? 'Run in progress' : 'Ready'}</Badge>
              <Badge color="gray">{history.length} recent runs</Badge>
            </>
          }
        />
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
            <div style={{ display: 'grid', gap: 10 }}>
              {Array.from({ length: 3 }).map((_, index) => (
                <Card key={index} style={{ padding: 18 }}>
                  <Skeleton width="28%" height={14} />
                  <div style={{ height: 12 }} />
                  <SkeletonText lines={3} />
                  <div style={{ height: 12 }} />
                  <div style={{ display: 'flex', gap: 8 }}>
                    <Skeleton width="96px" height={24} radius={999} />
                    <Skeleton width="120px" height={24} radius={999} />
                  </div>
                </Card>
              ))}
            </div>
          ) : error && workflows.length === 0 ? (
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
                            {HERO_WORKFLOW_IDS.has(workflow.id) ? <Badge color="orange">hero demo</Badge> : null}
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
                        {workflow.timeout_s ? <Badge color="gray">{workflow.timeout_s}s budget</Badge> : null}
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
            <PanelHeader
              eyebrow="Execution"
              title={selectedWorkflow ? selectedWorkflow.name : 'Select a workflow'}
              description={selectedWorkflow ? selectedWorkflow.description : 'Pick a workflow from the library to inspect its posture and run it.'}
              aside={selectedWorkflow ? <Badge color={runningId === selectedWorkflow.id ? 'orange' : 'blue'}>{runningId === selectedWorkflow.id ? 'live' : 'ready'}</Badge> : null}
            />
            {selectedWorkflow ? (
              <div style={{ display: 'grid', gap: 14 }}>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <Badge color={CATEGORY_COLORS[selectedWorkflow.category] || 'blue'}>{selectedWorkflow.category}</Badge>
                  <Badge color={selectedWorkflow.needs_agent ? 'purple' : 'green'}>
                    {selectedWorkflow.needs_agent ? 'agent-mediated' : 'direct run'}
                  </Badge>
                  <Badge color="gray">{formatPlatforms(selectedWorkflow)}</Badge>
                  {HERO_WORKFLOW_IDS.has(selectedWorkflow.id) ? <Badge color="orange">hero workflow</Badge> : null}
                  {selectedWorkflow.destructive ? <Badge color="orange">approval-sensitive</Badge> : null}
                </div>

                {HERO_WORKFLOW_IDS.has(selectedWorkflow.id) ? (
                  <div className="glass" style={{ padding: 14, display: 'grid', gap: 12 }}>
                    <div className="section-label">Hero run setup</div>
                    {selectedWorkflow.id === 'organize-downloads' ? (
                      <>
                        <label style={{ display: 'grid', gap: 6 }}>
                          <span style={{ fontSize: 12, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>
                            Downloads folder
                          </span>
                          <input
                            value={String(selectedDraft.target_dir || '')}
                            placeholder="Leave blank to use ~/Downloads"
                            onChange={(event) => updateDraft(selectedWorkflow.id, 'target_dir', event.target.value)}
                            style={inputStyle}
                          />
                        </label>
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                          <button
                            className={`btn${selectedDraft.dry_run !== false ? ' primary' : ''}`}
                            onClick={() => updateDraft(selectedWorkflow.id, 'dry_run', true)}
                          >
                            Preview only
                          </button>
                          <button
                            className={`btn${selectedDraft.dry_run === false ? ' primary' : ''}`}
                            onClick={() => updateDraft(selectedWorkflow.id, 'dry_run', false)}
                          >
                            Apply live
                          </button>
                        </div>
                        <div style={{ fontSize: 13, color: 'var(--text-3)', lineHeight: 1.55 }}>
                          Start with a preview for demos. When the plan looks good, rerun in apply mode to actually move the files.
                        </div>
                      </>
                    ) : (
                      <>
                        <label style={{ display: 'grid', gap: 6 }}>
                          <span style={{ fontSize: 12, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>
                            PDF path
                          </span>
                          <input
                            value={String(selectedDraft.file || '')}
                            placeholder="/Users/you/Documents/brief.pdf"
                            onChange={(event) => updateDraft(selectedWorkflow.id, 'file', event.target.value)}
                            style={inputStyle}
                          />
                        </label>
                        <div style={{ fontSize: 13, color: 'var(--text-3)', lineHeight: 1.55 }}>
                          Paste a local PDF path and ClawOS will extract the text, summarize it, and return a structured briefing with live progress.
                        </div>
                      </>
                    )}
                  </div>
                ) : null}

                <button className="btn primary" disabled={!!runningId} onClick={() => runWorkflow(selectedWorkflow)}>
                  {runningId === selectedWorkflow.id ? 'Running selected workflow...' : heroButtonLabel(selectedWorkflow.id, selectedDraft)}
                </button>

                {liveProgress && liveProgress.id === selectedWorkflow.id ? (
                  <div className="glass" style={{ padding: 14, display: 'grid', gap: 10 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <StatusDot status={normalizeProgressStatus(liveProgress.status)} />
                        <span style={{ fontWeight: 600 }}>Live progress</span>
                      </div>
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        {typeof liveProgress.progress === 'number' ? <Badge color="gray">{liveProgress.progress}%</Badge> : null}
                        <Badge color={progressColor(liveProgress.status)}>{liveProgress.status}</Badge>
                      </div>
                    </div>
                    <div style={{ color: 'var(--text-3)', fontSize: 13, lineHeight: 1.55 }}>
                      {liveProgress.message || liveProgress.output || 'ClawOS is streaming updates here as the workflow runs.'}
                    </div>
                    <div style={{ height: 8, borderRadius: 999, background: 'var(--surface)', border: '1px solid var(--border)', overflow: 'hidden' }}>
                      <div
                        style={{
                          width: progressWidth(liveProgress.progress, liveProgress.status),
                          height: '100%',
                          borderRadius: 999,
                          background: `var(--${progressColor(liveProgress.status)})`,
                        }}
                      />
                    </div>
                  </div>
                ) : null}

                {selectedProgressFeed.length ? (
                  <div className="glass" style={{ padding: 14, display: 'grid', gap: 8 }}>
                    <div className="section-label">Progress feed</div>
                    {selectedProgressFeed.map((entry, index) => (
                      <div
                        key={`${entry.id}-${entry.phase || 'phase'}-${entry.updatedAt}-${index}`}
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          gap: 12,
                          padding: '10px 12px',
                          borderRadius: 12,
                          background: 'var(--surface)',
                          border: '1px solid var(--border)',
                        }}
                      >
                        <div style={{ display: 'grid', gap: 4 }}>
                          <div style={{ fontWeight: 600 }}>
                            {entry.phase ? entry.phase.replace(/-/g, ' ') : 'workflow'}
                          </div>
                          <div style={{ fontSize: 12, color: 'var(--text-3)', lineHeight: 1.45 }}>
                            {entry.message || entry.output || 'Waiting for the next event.'}
                          </div>
                        </div>
                        <div style={{ display: 'grid', gap: 6, justifyItems: 'end' }}>
                          <Badge color={progressColor(entry.status)}>{entry.status}</Badge>
                          {typeof entry.progress === 'number' ? <span style={{ fontSize: 11, color: 'var(--text-3)' }}>{entry.progress}%</span> : null}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : null}

                {selectedResult?.metadata ? (
                  <HeroInsights workflowId={selectedWorkflow.id} metadata={selectedResult.metadata} />
                ) : null}

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
                      color: liveOutput ? 'var(--text-2)' : 'var(--text-3)',
                      fontSize: 12,
                      fontFamily: 'var(--font-mono)',
                    }}
                  >
                    {liveOutput || 'Run a workflow to inspect output, errors, or generated notes here.'}
                  </pre>
                </div>
              </div>
            ) : (
              <Empty>Select a workflow from the library to inspect and run it.</Empty>
            )}
          </Card>

          <Card style={{ padding: 18 }}>
            <PanelHeader
              eyebrow="History"
              title="Recent runs"
              description="A local memory of the latest launches from this session."
              aside={<Badge color="gray">{history.length}</Badge>}
            />
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
                    <Badge color={entry.status === 'ok' ? 'green' : entry.status === 'skipped' ? 'blue' : 'red'}>{entry.status}</Badge>
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

function HeroInsights({ workflowId, metadata }: { workflowId: string; metadata: Record<string, any> }) {
  if (workflowId === 'organize-downloads') {
    const categoryCounts = Object.entries(metadata.category_counts || {}) as Array<[string, number]>
    return (
      <div className="glass" style={{ padding: 14, display: 'grid', gap: 12 }}>
        <div className="section-label">Run insights</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 8 }}>
          <InsightCard label="Files" value={String(metadata.files_moved || 0)} />
          <InsightCard label="Folders" value={String(metadata.folders_created || 0)} />
          <InsightCard label="Volume" value={formatBytes(metadata.total_bytes)} />
          <InsightCard label="Mode" value={metadata.dry_run ? 'preview' : 'applied'} />
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {categoryCounts.map(([name, count]) => (
            <Badge key={name} color="gray">
              {name}: {count}
            </Badge>
          ))}
        </div>
      </div>
    )
  }

  if (workflowId === 'summarize-pdf') {
    const keywords = Array.isArray(metadata.keywords) ? metadata.keywords : []
    return (
      <div className="glass" style={{ padding: 14, display: 'grid', gap: 12 }}>
        <div className="section-label">Run insights</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 8 }}>
          <InsightCard label="Pages" value={String(metadata.pages_used || 0)} />
          <InsightCard label="Words" value={String(metadata.word_count || 0)} />
          <InsightCard label="Read time" value={`${metadata.read_minutes || 0} min`} />
          <InsightCard label="Highlights" value={String(metadata.bullet_count || 0)} />
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {keywords.map((term: string) => (
            <Badge key={term} color="gray">{term}</Badge>
          ))}
        </div>
      </div>
    )
  }

  return null
}

function InsightCard({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        padding: '12px 14px',
        borderRadius: 12,
        background: 'var(--surface)',
        border: '1px solid var(--border)',
      }}
    >
      <div style={{ fontSize: 11, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>{label}</div>
      <div style={{ marginTop: 8, fontSize: 20, fontWeight: 700, letterSpacing: '-0.04em' }}>{value}</div>
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

const inputStyle = {
  width: '100%',
  padding: '11px 14px',
  borderRadius: 12,
  border: '1px solid var(--border)',
  background: 'var(--surface)',
  color: 'var(--text)',
  outline: 'none',
} as const
