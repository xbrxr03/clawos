/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { useEffect, useState } from 'react'
import { Card, Row, StatusDot, Badge, SectionLabel, Ts, Btn, Empty } from '../components/ui.jsx'
import { api } from '../lib/api.js'

const TABS = ['active', 'queued', 'failed', 'completed']

export function Tasks({ tasks }) {
  const [input, setInput] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [tab, setTab] = useState('active')
  const [expanded, setExpanded] = useState(null)
  const items = tasks[tab] ?? []

  async function submitTask() {
    if (!input.trim()) return
    setSubmitting(true)
    try {
      await fetch('/api/tasks/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ intent: input.trim() }),
      })
      setInput('')
    } catch (error) {
      console.error(error)
    }
    setSubmitting(false)
  }

  return (
    <div className="fade-up" style={{ padding: '0 0 48px' }}>
      <div style={{ padding: '24px 20px 0' }}>
        <div style={{ fontSize: 26, fontWeight: 600, letterSpacing: '-0.03em' }}>Tasks</div>
        <div style={{ fontSize: 13, color: 'var(--text-2)', marginTop: 4 }}>
          Live queue for delegated work, mission execution, and recent outcomes.
        </div>
      </div>

      <div style={{ padding: '16px 20px 0' }}>
        <Card style={{ padding: 16, display: 'grid', gap: 12 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 10 }}>
            <input
              type="text"
              placeholder="Submit a task to Nexus..."
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => event.key === 'Enter' && submitTask()}
              style={{ borderRadius: 999 }}
            />
            <button className="btn primary" onClick={submitTask} disabled={submitting}>
              {submitting ? 'Running...' : 'Run'}
            </button>
          </div>
          <div className="seg">
            {TABS.map((name) => (
              <button
                key={name}
                className={`seg-btn${tab === name ? ' active' : ''}`}
                onClick={() => setTab(name)}
              >
                {name}
                {tasks[name]?.length > 0 ? ` (${tasks[name].length})` : ''}
              </button>
            ))}
          </div>
        </Card>
      </div>

      <SectionLabel>{tab}</SectionLabel>
      <div style={{ padding: '0 20px' }}>
        {items.length === 0 ? (
          <Card><Empty>No {tab} tasks</Empty></Card>
        ) : (
          <Card>
            {items.map((task) => (
              <div key={task.id}>
                <Row
                  onClick={() => setExpanded((current) => current === task.id ? null : task.id)}
                  left={<StatusDot status={task.status} />}
                  center={(
                    <div>
                      <div className="mono" style={{ fontSize: 13 }}>{task.description ?? task.id}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>
                        {task.id}{task.agent ? ` - ${task.agent}` : ''}
                      </div>
                    </div>
                  )}
                  right={(
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Ts value={task.created_at} />
                      <Badge color={task.status === 'active' ? 'green' : task.status === 'queued' ? 'blue' : task.status === 'failed' ? 'red' : 'gray'}>
                        {task.status}
                      </Badge>
                    </div>
                  )}
                  chevron
                />
                {expanded === task.id && task.log ? (
                  <div className="detail-panel">
                    <pre style={{ margin: 0, whiteSpace: 'pre-wrap', maxHeight: 200, overflowY: 'auto' }}>{task.log}</pre>
                  </div>
                ) : null}
              </div>
            ))}
          </Card>
        )}
      </div>
    </div>
  )
}

export function Approvals({ approvals }) {
  const [deciding, setDeciding] = useState({})

  async function decide(id, action) {
    setDeciding((current) => ({ ...current, [id]: action }))
    try {
      await (action === 'approve' ? api.approve(id) : api.deny(id))
    } catch (error) {
      console.error(error)
    } finally {
      setDeciding((current) => {
        const next = { ...current }
        delete next[id]
        return next
      })
    }
  }

  return (
    <div className="fade-up" style={{ padding: '0 0 48px' }}>
      <div style={{ padding: '24px 20px 0' }}>
        <div style={{ fontSize: 26, fontWeight: 600, letterSpacing: '-0.03em' }}>Approvals</div>
        <div style={{ fontSize: 13, color: 'var(--text-2)', marginTop: 4 }}>
          Sensitive actions awaiting human review.
        </div>
      </div>

      <SectionLabel>Inbox {approvals.length > 0 ? `- ${approvals.length}` : ''}</SectionLabel>

      {approvals.length === 0 ? (
        <div style={{ padding: '0 20px' }}>
          <Card><Empty>All clear - no pending approvals</Empty></Card>
        </div>
      ) : (
        <div style={{ padding: '0 20px', display: 'grid', gap: 12 }}>
          {approvals.map((approval) => {
            const riskBadge = approval.risk === 'high' ? 'red' : approval.risk === 'low' ? 'blue' : 'orange'
            const riskColor = approval.risk === 'high' ? 'var(--red)' : approval.risk === 'low' ? 'var(--blue)' : 'var(--orange)'
            return (
              <Card key={approval.id} style={{ padding: 0, overflow: 'hidden' }}>
                <div style={{ height: 3, background: riskColor }} />
                <div style={{ padding: 16, display: 'grid', gap: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'flex-start' }}>
                    <div>
                      <div className="mono" style={{ fontSize: 15, fontWeight: 600 }}>{approval.tool ?? 'unknown.tool'}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 4 }}>
                        task: {approval.task_id ?? '-'} - agent: {approval.agent ?? '-'}
                      </div>
                    </div>
                    <Badge color={riskBadge}>{approval.risk ?? 'medium'} risk</Badge>
                  </div>

                  {approval.action ? (
                    <div className="log-terminal" style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                      {typeof approval.action === 'string' ? approval.action : JSON.stringify(approval.action, null, 2)}
                    </div>
                  ) : null}

                  {approval.reason ? (
                    <div style={{ fontSize: 12, color: 'var(--text-2)', fontStyle: 'italic' }}>
                      "{approval.reason}"
                    </div>
                  ) : null}

                  {approval.timeout_at ? <TimeoutBar timeoutAt={approval.timeout_at} /> : null}

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                    <Btn variant="success" onClick={() => decide(approval.id, 'approve')} disabled={!!deciding[approval.id]}>
                      {deciding[approval.id] === 'approve' ? 'Approving...' : 'Approve'}
                    </Btn>
                    <Btn variant="danger" onClick={() => decide(approval.id, 'deny')} disabled={!!deciding[approval.id]}>
                      {deciding[approval.id] === 'deny' ? 'Denying...' : 'Deny'}
                    </Btn>
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}

function TimeoutBar({ timeoutAt }) {
  const [remaining, setRemaining] = useState(0)

  useEffect(() => {
    const tick = () => setRemaining(Math.max(0, Math.ceil((timeoutAt * 1000 - Date.now()) / 1000)))
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [timeoutAt])

  const pct = (remaining / 120) * 100
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-3)', marginBottom: 4 }}>
        <span>Auto-deny in</span>
        <span className="mono">{remaining}s</span>
      </div>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${pct}%`, background: remaining < 30 ? 'var(--red)' : 'var(--orange)' }} />
      </div>
    </div>
  )
}

const SUGGESTED = [
  { name: 'qwen2.5:7b', size: '4.7GB', note: 'Default - best balance' },
  { name: 'qwen2.5-coder:7b', size: '4.7GB', note: 'Better tool calling' },
  { name: 'gemma3:4b', size: '2.5GB', note: 'Low RAM option' },
  { name: 'llama3.1:8b', size: '4.9GB', note: 'General purpose' },
]

export function Models({ models, pullProgress }) {
  const [input, setInput] = useState('')
  const [deleting, setDeleting] = useState(null)
  const installed = models.models ?? []
  const installedNames = new Set(installed.map((model) => model.name))

  async function pull(name) {
    const target = (name || input).trim()
    if (!target) return
    setInput('')
    try {
      await api.pullModel(target)
    } catch (error) {
      console.error(error)
    }
  }

  async function remove(name) {
    setDeleting(name)
    try {
      await api.deleteModel(name)
    } catch (error) {
      console.error(error)
    }
    setDeleting(null)
  }

  return (
    <div className="fade-up" style={{ padding: '0 0 48px' }}>
      <div style={{ padding: '24px 20px 0' }}>
        <div style={{ fontSize: 26, fontWeight: 600, letterSpacing: '-0.03em' }}>Models</div>
        <div style={{ fontSize: 13, color: 'var(--text-2)', marginTop: 4 }}>Ollama model management with compact runtime posture.</div>
      </div>

      <SectionLabel>Pull a model</SectionLabel>
      <div style={{ padding: '0 20px' }}>
        <Card style={{ padding: 16, display: 'grid', gridTemplateColumns: '1fr auto', gap: 10 }}>
          <input
            type="text"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => event.key === 'Enter' && pull()}
            placeholder="e.g. qwen2.5:14b"
            style={{ borderRadius: 999 }}
          />
          <Btn variant="primary" onClick={() => pull()}>Pull</Btn>
        </Card>
      </div>

      <SectionLabel>Installed - {installed.length}</SectionLabel>
      <div style={{ padding: '0 20px' }}>
        {installed.length === 0 ? (
          <Card><Empty>No models - is Ollama running?</Empty></Card>
        ) : (
          <Card>
            {installed.map((model) => {
              const progress = pullProgress[model.name]
              const pct = progress?.total > 0 ? Math.round((progress.completed / progress.total) * 100) : 0
              return (
                <div key={model.name}>
                  <Row
                    left={<StatusDot status={model.running ? 'active' : 'completed'} />}
                    center={(
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                          <span className="mono" style={{ fontSize: 13 }}>{model.name}</span>
                          {model.name === models.default ? <Badge color="blue">default</Badge> : null}
                          {model.running ? <Badge color="green">running</Badge> : null}
                        </div>
                        {progress ? (
                          <div style={{ marginTop: 8 }}>
                            <div className="progress-bar"><div className="progress-fill" style={{ width: `${pct}%` }} /></div>
                            <div style={{ fontSize: 10, color: 'var(--text-3)', marginTop: 4 }}>{progress.status} {pct}%</div>
                          </div>
                        ) : null}
                      </div>
                    )}
                    right={(
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <span className="ts">{model.size_gb} GB</span>
                        {model.name !== models.default ? (
                          <button
                            className="btn danger sm"
                            onClick={() => remove(model.name)}
                            disabled={deleting === model.name}
                          >
                            Delete
                          </button>
                        ) : null}
                      </div>
                    )}
                  />
                </div>
              )
            })}
          </Card>
        )}
      </div>

      <SectionLabel>Suggested for GTX 1060</SectionLabel>
      <div style={{ padding: '0 20px' }}>
        <Card>
          {SUGGESTED.map((suggestion) => (
            <Row
              key={suggestion.name}
              left={<StatusDot status={installedNames.has(suggestion.name) ? 'active' : 'completed'} />}
              center={(
                <div>
                  <div className="mono" style={{ fontSize: 13 }}>{suggestion.name}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>{suggestion.note} - {suggestion.size}</div>
                </div>
              )}
              right={installedNames.has(suggestion.name) ? (
                <Badge color="green">installed</Badge>
              ) : (
                <button
                  className="btn sm"
                  onClick={() => pull(suggestion.name)}
                  disabled={!!pullProgress[suggestion.name]}
                >
                  {pullProgress[suggestion.name] ? 'Pulling...' : 'Get'}
                </button>
              )}
            />
          ))}
        </Card>
      </div>
    </div>
  )
}

export function Memory() {
  const [stats, setStats] = useState(null)
  const [workspaces, setWorkspaces] = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(true)

  async function load() {
    setLoading(true)
    try {
      const [memoryStats, workspaceList] = await Promise.all([api.memory(), api.workspaces()])
      setStats(memoryStats)
      setWorkspaces(workspaceList)
      if (workspaceList.length && !selected) setSelected(workspaceList[0].name)
    } catch (error) {
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const workspace = workspaces.find((item) => item.name === selected)

  return (
    <div className="fade-up" style={{ padding: '0 0 48px' }}>
      <div style={{ padding: '24px 20px 0', display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: 26, fontWeight: 600, letterSpacing: '-0.03em' }}>Memory</div>
          <div style={{ fontSize: 13, color: 'var(--text-2)', marginTop: 4 }}>Four-layer memory system with workspace previews.</div>
        </div>
        <Btn size="sm" onClick={load} disabled={loading}>{loading ? 'Refreshing...' : 'Refresh'}</Btn>
      </div>

      <SectionLabel>Layers</SectionLabel>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, padding: '0 20px' }}>
        <MemoryStat label="PINNED.md - Layer 1" value={stats?.pinned_lines ?? '-'} unit="lines" tone="var(--green)" />
        <MemoryStat label="WORKFLOW.md - Layer 2" value={stats?.workflow_lines ?? '-'} unit="lines" tone="var(--blue)" />
        <MemoryStat label="ChromaDB - Layer 3" value={stats?.chroma_size_mb ?? '-'} unit="MB" tone="var(--purple)" />
        <MemoryStat label="SQLite FTS5 - Layer 4" value={stats?.sqlite_size_mb ?? '-'} unit="MB" tone="var(--orange)" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 12, padding: '0 20px', marginTop: 14 }}>
        <div>
          <div className="section-label" style={{ paddingBottom: 8 }}>Workspaces</div>
          <Card>
            {workspaces.length === 0 ? (
              <Empty>None found</Empty>
            ) : (
              workspaces.map((workspaceItem) => (
                <Row
                  key={workspaceItem.name}
                  onClick={() => setSelected(workspaceItem.name)}
                  left={<span className={`dot ${selected === workspaceItem.name ? 'blue' : 'gray'}`} />}
                  center={(
                    <div>
                      <div className="mono" style={{ fontSize: 13 }}>{workspaceItem.name}</div>
                      <div style={{ display: 'flex', gap: 5, marginTop: 4 }}>
                        {workspaceItem.has_pinned ? <Badge color="green">PINNED</Badge> : null}
                        {workspaceItem.has_workflow ? <Badge color="blue">WORKFLOW</Badge> : null}
                      </div>
                    </div>
                  )}
                  chevron
                />
              ))
            )}
          </Card>
        </div>

        <div>
          <div className="section-label" style={{ paddingBottom: 8 }}>{selected ?? 'Select a workspace'}</div>
          {workspace ? (
            <Card style={{ padding: 0 }}>
              {workspace.pinned_preview ? (
                <div style={{ padding: '14px 16px', borderBottom: workspace.workflow_preview ? '0.5px solid var(--sep)' : 'none' }}>
                  <div style={{ fontSize: 10, color: 'var(--text-3)', marginBottom: 6, letterSpacing: '0.12em', textTransform: 'uppercase' }}>PINNED.md</div>
                  <pre className="log-terminal" style={{ margin: 0, maxHeight: 140, overflowY: 'auto', whiteSpace: 'pre-wrap' }}>
                    {workspace.pinned_preview}
                  </pre>
                </div>
              ) : null}
              {workspace.workflow_preview ? (
                <div style={{ padding: '14px 16px' }}>
                  <div style={{ fontSize: 10, color: 'var(--text-3)', marginBottom: 6, letterSpacing: '0.12em', textTransform: 'uppercase' }}>WORKFLOW.md</div>
                  <pre className="log-terminal" style={{ margin: 0, maxHeight: 140, overflowY: 'auto', whiteSpace: 'pre-wrap' }}>
                    {workspace.workflow_preview}
                  </pre>
                </div>
              ) : null}
              {!workspace.pinned_preview && !workspace.workflow_preview ? <Empty>No memory files</Empty> : null}
            </Card>
          ) : (
            <Card><Empty>Select a workspace</Empty></Card>
          )}
        </div>
      </div>
    </div>
  )
}

function MemoryStat({ label, value, unit, tone }) {
  return (
    <div className="stat-card">
      <div className="stat-val" style={{ color: tone }}>
        {value}
        <span className="stat-unit">{unit}</span>
      </div>
      <div className="stat-label">{label}</div>
    </div>
  )
}

export function NexusCommand() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)

  async function send() {
    const text = input.trim()
    if (!text || loading) return
    const userMsg = { role: 'user', text, ts: Date.now() }
    setMessages((current) => [...current, userMsg])
    setInput('')
    setLoading(true)
    try {
      const response = await fetch('/api/nexus/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      })
      const data = await response.json()
      setMessages((current) => [...current, {
        role: 'nexus',
        text: data.reply ?? data.error ?? '(no response)',
        tool_steps: data.tool_steps ?? [],
        ts: Date.now(),
      }])
    } catch (error) {
      setMessages((current) => [...current, {
        role: 'nexus',
        text: `Error: ${error.message}`,
        ts: Date.now(),
        error: true,
      }])
    }
    setLoading(false)
  }

  return (
    <div className="fade-up" style={{ padding: '0 0 48px', display: 'grid', gap: 12 }}>
      <div style={{ padding: '24px 20px 0' }}>
        <div style={{ fontSize: 26, fontWeight: 600, letterSpacing: '-0.03em' }}>Nexus Command</div>
        <div style={{ fontSize: 13, color: 'var(--text-2)', marginTop: 4 }}>Chat directly with your local Nexus agent.</div>
      </div>
      <div style={{ padding: '0 20px' }}>
        <Card style={{ padding: 16, display: 'grid', gap: 12 }}>
          <div style={{ display: 'grid', gap: 10, maxHeight: '60vh', overflowY: 'auto' }}>
            {messages.length === 0 ? (
              <div style={{ color: 'var(--text-3)', fontSize: 13, textAlign: 'center', margin: '28px 0' }}>
                Send a message to start chatting with Nexus.
              </div>
            ) : (
              messages.map((message, index) => (
                <div
                  key={index}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: message.role === 'user' ? 'flex-end' : 'flex-start',
                  }}
                >
                  {message.role === 'nexus' && message.tool_steps?.length > 0 ? (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 6, maxWidth: '75%' }}>
                      {message.tool_steps.map((step, stepIndex) => (
                        <div
                          key={stepIndex}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 4,
                            padding: '2px 8px',
                            borderRadius: 999,
                            fontSize: 10,
                            background: step.denied ? 'var(--red-dim)' : step.pending_approval ? 'var(--orange-dim)' : 'var(--green-dim)',
                            border: `0.5px solid ${step.denied ? 'rgba(255, 59, 48, 0.24)' : step.pending_approval ? 'rgba(255, 149, 0, 0.24)' : 'rgba(52, 199, 89, 0.24)'}`,
                            color: step.denied ? 'var(--red)' : step.pending_approval ? 'var(--orange)' : 'var(--green)',
                            fontFamily: 'var(--font-mono)',
                          }}
                        >
                          <span>{step.denied ? 'deny' : step.pending_approval ? 'wait' : 'ok'}</span>
                          <span>{step.tool}</span>
                        </div>
                      ))}
                    </div>
                  ) : null}
                  <div className={`conversation-bubble${message.role === 'user' ? ' user' : ''}`} style={{ maxWidth: '75%' }}>
                    {message.text}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-3)', marginTop: 4 }}>
                    {message.role === 'user' ? 'you' : 'nexus'} - {new Date(message.ts).toLocaleTimeString()}
                  </div>
                </div>
              ))
            )}
            {loading ? (
              <div style={{ display: 'flex', alignItems: 'flex-start' }}>
                <div className="conversation-bubble" style={{ color: 'var(--text-3)' }}>thinking...</div>
              </div>
            ) : null}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 10 }}>
            <input
              type="text"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => event.key === 'Enter' && !event.shiftKey && send()}
              placeholder="Ask Nexus anything..."
              disabled={loading}
              autoFocus
              style={{ borderRadius: 999, opacity: loading ? 0.6 : 1 }}
            />
            <button className="btn primary" onClick={send} disabled={loading || !input.trim()}>
              Send
            </button>
          </div>
        </Card>
      </div>
    </div>
  )
}

const RUNTIME_COLORS = {
  nexus: { primary: '#007AFF', dim: 'rgba(0, 122, 255, 0.12)', border: 'rgba(0, 122, 255, 0.24)' },
  picoclaw: { primary: '#FF9500', dim: 'rgba(255, 149, 0, 0.12)', border: 'rgba(255, 149, 0, 0.24)' },
  openclaw: { primary: '#AF52DE', dim: 'rgba(175, 82, 222, 0.12)', border: 'rgba(175, 82, 222, 0.24)' },
}

const BUBBLE_PALETTE = ['#007AFF', '#34C759', '#FF9500', '#AF52DE', '#FF3B30', '#5AC8FA', '#8E8E93']

function wsColor(name) {
  let hash = 0
  for (let index = 0; index < name.length; index += 1) {
    hash = (hash * 31 + name.charCodeAt(index)) % BUBBLE_PALETTE.length
  }
  return BUBBLE_PALETTE[hash]
}

function AgentBubble({ name, turns, active, onReset, resetting }) {
  const color = wsColor(name)
  const initial = name.charAt(0).toUpperCase()

  return (
    <button
      type="button"
      title={`${name} - ${turns} turns - click to reset`}
      onClick={onReset}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 6,
        border: 'none',
        background: 'transparent',
        cursor: 'pointer',
        opacity: resetting ? 0.5 : 1,
      }}
    >
      <div style={{ position: 'relative' }}>
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: 12,
            background: `${color}20`,
            border: `1px solid ${color}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 16,
            fontWeight: 700,
            color,
          }}
        >
          {initial}
        </div>
        {turns > 0 ? (
          <div
            style={{
              position: 'absolute',
              bottom: -3,
              right: -3,
              background: color,
              color: '#fff',
              fontSize: 9,
              fontWeight: 700,
              borderRadius: 999,
              padding: '1px 5px',
              border: '1px solid var(--surface-1)',
            }}
          >
            {turns}
          </div>
        ) : null}
        {active ? (
          <div
            style={{
              position: 'absolute',
              top: -2,
              right: -2,
              width: 10,
              height: 10,
              borderRadius: '50%',
              background: 'var(--green)',
              border: '1px solid var(--surface-1)',
            }}
          />
        ) : null}
      </div>
      <div
        style={{
          fontSize: 10,
          color: 'var(--text-3)',
          maxWidth: 72,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          textAlign: 'center',
          fontFamily: 'var(--font-mono)',
        }}
      >
        {name}
      </div>
    </button>
  )
}

function PeerBubble({ peer }) {
  const color = '#AF52DE'
  const label = peer.name || peer.host || 'peer'
  const initial = label.charAt(0).toUpperCase()

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }} title={peer.url ?? label}>
      <div
        style={{
          width: 40,
          height: 40,
          borderRadius: 12,
          background: `${color}18`,
          border: `1px solid ${color}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 16,
          fontWeight: 700,
          color,
        }}
      >
        {initial}
      </div>
      <div
        style={{
          fontSize: 10,
          color: 'var(--text-3)',
          maxWidth: 72,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          textAlign: 'center',
        }}
      >
        {label}
      </div>
    </div>
  )
}

function RuntimeZone({ label, icon, colors, installed, running, model, emptyText, children }) {
  return (
    <div
      style={{
        flex: 1,
        borderRadius: 10,
        overflow: 'hidden',
        border: `0.5px solid ${running ? colors.border : 'var(--border)'}`,
        background: 'var(--surface-1)',
        display: 'flex',
        flexDirection: 'column',
        minHeight: 280,
      }}
    >
      <div style={{ height: 3, background: running ? colors.primary : 'var(--surface-3)' }} />
      <div style={{ padding: '14px 16px', borderBottom: '0.5px solid var(--sep)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div
            style={{
              width: 34,
              height: 34,
              borderRadius: 10,
              flexShrink: 0,
              background: running ? colors.dim : 'var(--surface-2)',
              border: `0.5px solid ${running ? colors.border : 'var(--border)'}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 15,
              fontWeight: 700,
            }}
          >
            {icon}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 14, fontWeight: 600 }}>{label}</div>
            <div
              style={{
                fontSize: 10,
                color: 'var(--text-3)',
                marginTop: 2,
                fontFamily: 'var(--font-mono)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {model}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
            <span className={`dot ${running ? 'green' : installed ? 'orange' : 'gray'}`} />
            <span style={{ fontSize: 11, color: running ? colors.primary : 'var(--text-3)' }}>
              {running ? 'running' : installed ? 'idle' : 'not found'}
            </span>
          </div>
        </div>
      </div>

      <div
        style={{
          flex: 1,
          padding: '16px',
          display: 'flex',
          flexWrap: 'wrap',
          gap: 14,
          alignContent: 'flex-start',
        }}
      >
        {children ?? (
          <div style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', paddingTop: 36 }}>
            <span style={{ fontSize: 12, color: 'var(--text-3)' }}>{emptyText ?? 'No active sessions'}</span>
          </div>
        )}
      </div>
    </div>
  )
}

function LiveFeed({ events }) {
  const items = events
    .filter((event) => ['task_update', 'audit_event', 'approval_pending', 'approval_resolved'].includes(event.type))
    .slice(0, 80)

  function label(event) {
    const data = event.data ?? {}
    if (event.type === 'task_update') return `${data.status ?? 'update'}: ${(data.intent ?? data.description ?? '').slice(0, 55)}`
    if (event.type === 'audit_event') return `${(data.decision ?? '').toUpperCase()} ${data.tool ?? ''} ${data.target ? `-> ${String(data.target).slice(0, 25)}` : ''}`
    if (event.type === 'approval_pending') return `approval pending: ${data.tool ?? ''} on ${String(data.target ?? '').slice(0, 25)}`
    if (event.type === 'approval_resolved') return `${data.decision === 'approved' ? 'approved' : 'denied'} ${data.approval_id?.slice(0, 8)}`
    return event.type
  }

  function color(event) {
    if (event.type === 'approval_pending') return 'var(--orange)'
    if (event.type === 'approval_resolved') return event.data?.decision === 'approved' ? 'var(--green)' : 'var(--red)'
    if (event.type === 'audit_event') {
      const decision = event.data?.decision ?? ''
      if (decision === 'approved' || decision === 'allow') return 'var(--green)'
      if (decision === 'denied' || decision === 'deny') return 'var(--red)'
    }
    if (event.type === 'task_update') {
      const status = event.data?.status ?? ''
      if (status === 'completed') return 'var(--green)'
      if (status === 'failed') return 'var(--red)'
      if (status === 'running') return 'var(--blue)'
    }
    return 'var(--text-3)'
  }

  return (
    <div
      style={{
        width: 280,
        flexShrink: 0,
        borderLeft: '0.5px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        background: 'var(--sidebar-bg)',
      }}
    >
      <div style={{ padding: '14px 16px 12px', borderBottom: '0.5px solid var(--border)', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <span className="dot green" />
          <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-2)' }}>
            Live Activity
          </span>
        </div>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: '4px 0' }}>
        {items.length === 0 ? (
          <div style={{ padding: '28px 16px', fontSize: 12, color: 'var(--text-3)', textAlign: 'center' }}>
            Waiting for activity...
          </div>
        ) : (
          items.map((event, index) => (
            <div key={index} style={{ padding: '8px 16px', borderBottom: '0.5px solid var(--sep)' }}>
              <div style={{ fontSize: 10, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', marginBottom: 2 }}>
                {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </div>
              <div style={{ fontSize: 11, color: color(event), lineHeight: 1.45, wordBreak: 'break-word' }}>
                {label(event)}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export function Agents({ events = [], runtimes = {} }) {
  const [sessions, setSessions] = useState([])
  const [peers, setPeers] = useState([])
  const [loading, setLoading] = useState(true)
  const [resetting, setResetting] = useState(null)

  async function load() {
    setLoading(true)
    try {
      const [agentResponse, peerResponse] = await Promise.all([
        api.agents(),
        fetch('/api/peers').then((response) => response.json()).catch(() => ({ peers: [] })),
      ])
      setSessions(agentResponse.sessions ?? [])
      setPeers(peerResponse.peers ?? [])
    } catch (error) {
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  async function resetSession(workspaceId) {
    setResetting(workspaceId)
    try {
      await api.resetAgent(workspaceId)
    } catch (error) {
      console.error(error)
    }
    setResetting(null)
    api.agents().then((data) => setSessions(data.sessions ?? [])).catch(() => {})
  }

  useEffect(() => {
    load()
  }, [])

  useEffect(() => {
    const id = setInterval(() => {
      api.agents().then((data) => setSessions(data.sessions ?? [])).catch(() => {})
    }, 6000)
    return () => clearInterval(id)
  }, [])

  const nexus = runtimes.nexus ?? {}
  const picoclaw = runtimes.picoclaw ?? {}
  const openclaw = runtimes.openclaw ?? {}
  const total = [nexus, picoclaw, openclaw].filter((runtime) => runtime.running).length

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ padding: '20px 24px 16px', borderBottom: '0.5px solid var(--border)', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: 22, fontWeight: 600, letterSpacing: '-0.03em' }}>Runtime Network</div>
          <div style={{ fontSize: 12, color: 'var(--text-2)', marginTop: 3 }}>
            {total} runtime{total !== 1 ? 's' : ''} active - {sessions.length} session{sessions.length !== 1 ? 's' : ''} - {peers.length} peer{peers.length !== 1 ? 's' : ''}
          </div>
        </div>
        <Btn size="sm" onClick={load} disabled={loading}>{loading ? 'Refreshing...' : 'Refresh'}</Btn>
      </div>

      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        <div style={{ flex: 1, padding: '16px', display: 'flex', gap: 12, overflow: 'hidden' }}>
          <RuntimeZone
            label="Nexus"
            icon="N"
            colors={RUNTIME_COLORS.nexus}
            installed={nexus.installed ?? true}
            running={nexus.running}
            model={`local - ${nexus.model ?? 'qwen2.5:7b'}`}
            emptyText="No active sessions - chat in Nexus Command"
          >
            {sessions.length > 0 ? sessions.map((session) => (
              <AgentBubble
                key={session.workspace_id}
                name={session.workspace_id}
                turns={session.turn}
                active={session.turn > 0}
                resetting={resetting === session.workspace_id}
                onReset={() => resetSession(session.workspace_id)}
              />
            )) : undefined}
          </RuntimeZone>

          <RuntimeZone
            label="PicoClaw"
            icon="P"
            colors={RUNTIME_COLORS.picoclaw}
            installed={picoclaw.installed}
            running={picoclaw.running}
            model="edge - on-device inference"
            emptyText={picoclaw.running ? 'Running - no sub-agents exposed' : picoclaw.installed ? 'Installed - not running' : 'Not installed on this device'}
          />

          <RuntimeZone
            label="OpenClaw"
            icon="O"
            colors={RUNTIME_COLORS.openclaw}
            installed={openclaw.installed}
            running={openclaw.running}
            model={`gateway - ${openclaw.model ?? 'cloud'}`}
            emptyText={!openclaw.installed ? 'Not installed' : !openclaw.running ? 'Gateway offline' : 'No peers discovered yet'}
          >
            {peers.length > 0 ? peers.map((peer, index) => (
              <PeerBubble key={index} peer={peer} />
            )) : undefined}
          </RuntimeZone>
        </div>

        <LiveFeed events={events} />
      </div>
    </div>
  )
}

export function Audit({ events }) {
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [live, setLive] = useState(true)
  const [expanded, setExpanded] = useState(null)

  async function load() {
    setLoading(true)
    try {
      const data = await api.audit(200)
      setEntries(data.entries ?? [])
    } catch (error) {
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  useEffect(() => {
    if (!live) return
    const fresh = events.filter((event) => event.type === 'audit_event')
    if (!fresh.length) return
    setEntries((current) => {
      const seen = new Set(current.map((entry) => entry.entry_hash))
      return [...fresh.map((event) => event.data).filter((entry) => !seen.has(entry.entry_hash)), ...current]
    })
  }, [events, live])

  const decisionColor = (decision) => decision === 'approved' ? 'var(--green)' : decision === 'denied' ? 'var(--red)' : decision === 'pending' ? 'var(--orange)' : 'var(--text-3)'
  const decisionBadge = (decision) => decision === 'approved' ? 'green' : decision === 'denied' ? 'red' : decision === 'pending' ? 'orange' : 'gray'
  const toolColor = (tool) => !tool ? 'var(--text)' : tool.includes('shell') || tool.includes('exec') ? 'var(--red)' : tool.includes('file') || tool.includes('write') ? 'var(--orange)' : tool.includes('web') || tool.includes('http') ? 'var(--blue)' : 'var(--green)'

  return (
    <div className="fade-up" style={{ padding: '0 0 48px' }}>
      <div style={{ padding: '24px 20px 0', display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: 26, fontWeight: 600, letterSpacing: '-0.03em' }}>Audit Log</div>
          <div style={{ fontSize: 13, color: 'var(--text-2)', marginTop: 4 }}>Merkle-chained tamper-evident journal.</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn sm" onClick={() => setLive((current) => !current)}>
            <span className={`toggle${live ? ' active' : ''}`} aria-hidden="true" />
            <span>{live ? 'Live On' : 'Live Off'}</span>
          </button>
          <Btn size="sm" onClick={load} disabled={loading}>{loading ? 'Reloading...' : 'Reload'}</Btn>
        </div>
      </div>

      <SectionLabel>{entries.length} entries</SectionLabel>
      <div style={{ padding: '0 20px' }}>
        <Card>
          {entries.length === 0 ? (
            <Empty>No audit entries yet</Empty>
          ) : (
            entries.map((entry, index) => {
              const key = entry.entry_hash ?? index
              const decision = entry.decision ?? entry.action ?? entry.event ?? 'event'
              const isOpen = expanded === key

              return (
                <div key={key}>
                  <Row
                    onClick={() => setExpanded((current) => current === key ? null : key)}
                    left={<span style={{ width: 7, height: 7, borderRadius: '50%', background: decisionColor(decision), flexShrink: 0 }} />}
                    center={<span className="mono" style={{ fontSize: 12, color: toolColor(entry.tool), overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{entry.tool ?? entry.type ?? '-'}</span>}
                    right={(
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Badge color={decisionBadge(decision)}>{decision}</Badge>
                        <span className="ts">{(entry.entry_hash ?? '').slice(0, 7)}</span>
                        <Ts value={entry.timestamp} />
                        <svg width="6" height="11" viewBox="0 0 6 11" fill="none" style={{ transform: isOpen ? 'rotate(90deg)' : 'none', transition: '.15s', flexShrink: 0 }}>
                          <path d="M1 1l4 4.5L1 10" stroke="var(--text-3)" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      </div>
                    )}
                  />
                  {isOpen ? (
                    <div className="detail-panel">
                      {[['task_id', entry.task_id], ['agent_id', entry.agent_id], ['tool', entry.tool], ['target', entry.target]]
                        .filter(([, value]) => value)
                        .map(([keyName, value]) => (
                          <div key={keyName} style={{ marginBottom: 4 }}>
                            <span style={{ color: 'var(--text-3)' }}>{keyName.padEnd(10, ' ')}</span>
                            <span>{value}</span>
                          </div>
                        ))}
                      {entry.prev_hash ? <div style={{ marginTop: 6, color: 'var(--text-3)' }}>prev: {entry.prev_hash.slice(0, 48)}...</div> : null}
                      {entry.entry_hash ? <div style={{ color: 'var(--text-2)' }}># {entry.entry_hash.slice(0, 48)}...</div> : null}
                      <details style={{ marginTop: 6 }}>
                        <summary style={{ cursor: 'pointer', color: 'var(--text-3)', fontSize: 10 }}>raw JSON</summary>
                        <pre style={{ marginTop: 6, fontSize: 10, color: 'var(--text-2)', whiteSpace: 'pre-wrap', wordBreak: 'break-all', maxHeight: 180, overflowY: 'auto' }}>
                          {JSON.stringify(entry, null, 2)}
                        </pre>
                      </details>
                    </div>
                  ) : null}
                </div>
              )
            })
          )}
        </Card>
      </div>
    </div>
  )
}
