import { useState, useEffect } from 'react'
import { Card, Row, StatusDot, Badge, SectionLabel, Ts, Btn, Empty } from '../components/ui.jsx'
import { api } from '../lib/api.js'

// Tasks
const TABS = ['active','queued','failed','completed']

export function Tasks({ tasks }) {
  const [input, setInput] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function submitTask() {
    if (!input.trim()) return;
    setSubmitting(true);
    try {
      await fetch('/api/tasks/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ intent: input.trim() }),
      });
      setInput('');
    } catch(e) { console.error(e); }
    setSubmitting(false);
  }
  const [tab, setTab]     = useState('active')
  const [expanded, setEx] = useState(null)
  const items = tasks[tab] ?? []

  return (
    <div className="fade-up" style={{ padding: '0 0 48px' }}>
      <div style={{ padding: '32px 24px 0' }}>
        <div style={{ fontSize: 24, fontWeight: 700, letterSpacing: '-0.5px' }}>Tasks</div>
      <div style={{ display: 'flex', gap: 8, margin: '16px 0' }}>
        <input
          type="text"
          placeholder="Submit a task to Nexus..."
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && submitTask()}
          style={{ flex: 1, padding: '10px 14px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.05)', color: '#f5f5f7', fontSize: 14, outline: 'none' }}
        />
        <button onClick={submitTask} disabled={submitting} style={{ padding: '10px 20px', borderRadius: 8, border: 'none', background: '#2997FF', color: '#fff', fontSize: 14, cursor: 'pointer', opacity: submitting ? 0.6 : 1 }}>
          {submitting ? '...' : 'Run'}
        </button>
      </div>
      </div>

      <div style={{ padding: '16px 20px 0' }}>
        <div className="seg">
          {TABS.map(t => (
            <button
              key={t}
              className={`seg-btn${tab === t ? ' active' : ''}`}
              onClick={() => setTab(t)}
            >
              {t}
              {tasks[t]?.length > 0 && (
                <span style={{ marginLeft: 5, fontSize: 10, opacity: 0.7 }}>({tasks[t].length})</span>
              )}
            </button>
          ))}
        </div>
      </div>

      <SectionLabel>{tab}</SectionLabel>
      <div style={{ padding: '0 20px' }}>
        {items.length === 0 ? (
          <Card><Empty>No {tab} tasks</Empty></Card>
        ) : (
          <Card>
            {items.map(t => (
              <div key={t.id}>
                <Row
                  onClick={() => setEx(e => e === t.id ? null : t.id)}
                  left={<StatusDot status={t.status} />}
                  center={
                    <div>
                      <div className="mono" style={{ fontSize: 13 }}>{t.description ?? t.id}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>
                        {t.id}{t.agent ? ` - ${t.agent}` : ''}
                      </div>
                    </div>
                  }
                  right={
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Ts value={t.created_at} />
                      <Badge color={t.status === 'active' ? 'green' : t.status === 'queued' ? 'blue' : t.status === 'failed' ? 'red' : 'gray'}>
                        {t.status}
                      </Badge>
                    </div>
                  }
                  chevron
                />
                {expanded === t.id && t.log && (
                  <div className="detail-panel">
                    <pre style={{ whiteSpace: 'pre-wrap', maxHeight: 200, overflowY: 'auto' }}>{t.log}</pre>
                  </div>
                )}
              </div>
            ))}
          </Card>
        )}
      </div>
    </div>
  )
}

// Approvals
export function Approvals({ approvals }) {
  const [deciding, setDeciding] = useState({})

  async function decide(id, action) {
    setDeciding(d => ({ ...d, [id]: action }))
    try { await (action === 'approve' ? api.approve(id) : api.deny(id)) }
    catch(e) { console.error(e) }
    finally { setDeciding(d => { const n={...d}; delete n[id]; return n }) }
  }

  return (
    <div className="fade-up" style={{ padding: '0 0 48px' }}>
      <div style={{ padding: '32px 24px 0' }}>
        <div style={{ fontSize: 24, fontWeight: 700, letterSpacing: '-0.5px' }}>Approvals</div>
        <div style={{ fontSize: 13, color: 'var(--text-2)', marginTop: 4 }}>
          Sensitive actions awaiting human review
        </div>
      </div>

      <SectionLabel>Inbox {approvals.length > 0 ? `- ${approvals.length}` : ''}</SectionLabel>

      {approvals.length === 0 ? (
        <div style={{ padding: '0 20px' }}>
          <Card><Empty>All clear - no pending approvals</Empty></Card>
        </div>
      ) : (
        <div style={{ padding: '0 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          {approvals.map(a => {
            const riskColor = a.risk === 'high' ? 'var(--red)' : a.risk === 'low' ? 'var(--blue)' : 'var(--orange)'
            const riskBadge = a.risk === 'high' ? 'red' : a.risk === 'low' ? 'blue' : 'orange'
            return (
              <div key={a.id} className="glass" style={{ overflow: 'hidden' }}>
                {/* Colored top bar */}
                <div style={{ height: 2, background: riskColor, boxShadow: `0 0 8px ${riskColor}` }} />
                <div style={{ padding: '16px' }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8, marginBottom: 12 }}>
                    <div>
                      <div className="mono" style={{ fontSize: 15, fontWeight: 500 }}>{a.tool ?? 'unknown.tool'}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 3 }}>
                        task: {a.task_id ?? '-'} - agent: {a.agent ?? '-'}
                      </div>
                    </div>
                    <Badge color={riskBadge}>{a.risk ?? 'medium'} risk</Badge>
                  </div>

                  {a.action && (
                    <div style={{
                      background: 'rgba(0,0,0,0.3)',
                      borderRadius: 10,
                      padding: '10px 12px',
                      marginBottom: 12,
                      fontFamily: 'JetBrains Mono, monospace',
                      fontSize: 12,
                      color: 'var(--text)',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-all',
                      border: '1px solid var(--border)',
                    }}>
                      {typeof a.action === 'string' ? a.action : JSON.stringify(a.action, null, 2)}
                    </div>
                  )}

                  {a.reason && (
                    <div style={{ fontSize: 12, color: 'var(--text-2)', fontStyle: 'italic', marginBottom: 14 }}>
                      "{a.reason}"
                    </div>
                  )}

                  {a.timeout_at && <TimeoutBar timeoutAt={a.timeout_at} />}

                  <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
                    <Btn variant="success" onClick={() => decide(a.id, 'approve')} disabled={!!deciding[a.id]}>
                      {deciding[a.id] === 'approve' ? 'Approving...' : 'Approve'}
                    </Btn>
                    <Btn variant="danger" onClick={() => decide(a.id, 'deny')} disabled={!!deciding[a.id]}>
                      {deciding[a.id] === 'deny' ? 'Denying...' : 'Deny'}
                    </Btn>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function TimeoutBar({ timeoutAt }) {
  const [rem, setRem] = useState(0)
  useEffect(() => {
    const tick = () => setRem(Math.max(0, Math.ceil((timeoutAt * 1000 - Date.now()) / 1000)))
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [timeoutAt])
  const pct = (rem / 120) * 100
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-3)', marginBottom: 4 }}>
        <span>Auto-deny in</span>
        <span className="mono">{rem}s</span>
      </div>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${pct}%`, background: rem < 30 ? 'var(--red)' : 'var(--orange)' }} />
      </div>
    </div>
  )
}

// Models
const SUGGESTED = [
  { name: 'qwen2.5:7b',       size: '4.7GB', note: 'Default - best balance'  },
  { name: 'qwen2.5-coder:7b', size: '4.7GB', note: 'Better tool calling'     },
  { name: 'gemma3:4b',        size: '2.5GB', note: 'Low RAM option'          },
  { name: 'llama3.1:8b',      size: '4.9GB', note: 'General purpose'         },
]

export function Models({ models, pullProgress }) {
  const [input, setInput]     = useState('')
  const [deleting, setDeleting] = useState(null)
  const installed     = models.models ?? []
  const installedNames = new Set(installed.map(m => m.name))

  async function pull(name) {
    const t = (name || input).trim()
    if (!t) return
    setInput('')
    try { await api.pullModel(t) } catch(e) { console.error(e) }
  }

  async function del(name) {
    setDeleting(name)
    try { await api.deleteModel(name) } catch(e) { console.error(e) }
    setDeleting(null)
  }

  return (
    <div className="fade-up" style={{ padding: '0 0 48px' }}>
      <div style={{ padding: '32px 24px 0' }}>
        <div style={{ fontSize: 24, fontWeight: 700, letterSpacing: '-0.5px' }}>Models</div>
        <div style={{ fontSize: 13, color: 'var(--text-2)', marginTop: 4 }}>Ollama model management</div>
      </div>

      <SectionLabel>Pull a model</SectionLabel>
      <div style={{ padding: '0 20px', display: 'flex', gap: 10 }}>
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && pull()}
          placeholder="e.g. qwen2.5:14b"
        />
        <Btn variant="primary" onClick={() => pull()}>Pull</Btn>
      </div>

      <SectionLabel>Installed - {installed.length}</SectionLabel>
      <div style={{ padding: '0 20px' }}>
        {installed.length === 0 ? (
          <Card><Empty>No models - is Ollama running?</Empty></Card>
        ) : (
          <Card>
            {installed.map(m => {
              const prog = pullProgress[m.name]
              const pct  = prog?.total > 0 ? Math.round((prog.completed / prog.total) * 100) : 0
              return (
                <div key={m.name}>
                  <Row
                    left={<StatusDot status={m.running ? 'active' : 'completed'} />}
                    center={
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                          <span className="mono" style={{ fontSize: 13 }}>{m.name}</span>
                          {m.name === models.default && <Badge color="blue">default</Badge>}
                          {m.running && <Badge color="green">running</Badge>}
                        </div>
                        {prog && (
                          <div>
                            <div className="progress-bar"><div className="progress-fill" style={{ width: `${pct}%` }} /></div>
                            <div style={{ fontSize: 10, color: 'var(--text-3)', marginTop: 2 }}>{prog.status} {pct}%</div>
                          </div>
                        )}
                      </div>
                    }
                    right={
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <span className="ts">{m.size_gb} GB</span>
                        {m.name !== models.default && (
                          <button
                            onClick={() => del(m.name)}
                            disabled={deleting === m.name}
                            style={{ background:'none', border:'none', color:'var(--red)', cursor:'pointer', fontSize:12, fontFamily:'inherit', opacity: deleting===m.name ? 0.5:1 }}
                          >
                            Delete
                          </button>
                        )}
                      </div>
                    }
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
          {SUGGESTED.map(s => (
            <Row
              key={s.name}
              left={<StatusDot status={installedNames.has(s.name) ? 'active' : 'completed'} />}
              center={
                <div>
                  <div className="mono" style={{ fontSize: 13 }}>{s.name}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>{s.note} - {s.size}</div>
                </div>
              }
              right={
                installedNames.has(s.name)
                  ? <Badge color="green">installed</Badge>
                  : (
                    <button
                      onClick={() => pull(s.name)}
                      disabled={!!pullProgress[s.name]}
                      style={{ background:'none', border:'none', color:'var(--blue)', cursor:'pointer', fontSize:13, fontFamily:'inherit' }}
                    >
                      {pullProgress[s.name] ? 'Pulling...' : 'Get'}
                    </button>
                  )
              }
            />
          ))}
        </Card>
      </div>
    </div>
  )
}

// Memory
export function Memory() {
  const [stats, setStats]   = useState(null)
  const [wss, setWss]       = useState([])
  const [sel, setSel]       = useState(null)
  const [loading, setLoad]  = useState(true)

  async function load() {
    setLoad(true)
    try {
      const [s, w] = await Promise.all([api.memory(), api.workspaces()])
      setStats(s); setWss(w)
      if (w.length && !sel) setSel(w[0].name)
    } catch(e) { console.error(e) }
    finally { setLoad(false) }
  }
  useEffect(() => { load() }, [])

  const ws = wss.find(w => w.name === sel)

  return (
    <div className="fade-up" style={{ padding: '0 0 48px' }}>
      <div style={{ padding: '32px 24px 0', display:'flex', alignItems:'flex-end', justifyContent:'space-between' }}>
        <div>
          <div style={{ fontSize: 24, fontWeight: 700, letterSpacing: '-0.5px' }}>Memory</div>
          <div style={{ fontSize: 13, color: 'var(--text-2)', marginTop: 4 }}>4-layer memory system</div>
        </div>
        <Btn size="sm" onClick={load} disabled={loading}>{loading ? '...' : 'Refresh'}</Btn>
      </div>

      <SectionLabel>Layers</SectionLabel>
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:10, padding:'0 20px' }}>
        <div className="stat-card">
          <div className="stat-val" style={{ color:'var(--green)' }}>{stats?.pinned_lines ?? '-'}<span className="stat-unit">lines</span></div>
          <div className="stat-label">PINNED.md - Layer 1</div>
        </div>
        <div className="stat-card">
          <div className="stat-val" style={{ color:'var(--blue)' }}>{stats?.workflow_lines ?? '-'}<span className="stat-unit">lines</span></div>
          <div className="stat-label">WORKFLOW.md - Layer 2</div>
        </div>
        <div className="stat-card">
          <div className="stat-val" style={{ color:'var(--purple)' }}>{stats?.chroma_size_mb ?? '-'}<span className="stat-unit">MB</span></div>
          <div className="stat-label">ChromaDB - Layer 3</div>
        </div>
        <div className="stat-card">
          <div className="stat-val" style={{ color:'var(--orange)' }}>{stats?.sqlite_size_mb ?? '-'}<span className="stat-unit">MB</span></div>
          <div className="stat-label">SQLite FTS5 - Layer 4</div>
        </div>
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'1fr 2fr', gap:12, padding:'0 20px', marginTop:14 }}>
        <div>
          <div className="section-label" style={{ padding:'0 0 8px' }}>Workspaces</div>
          <Card>
            {wss.length === 0 ? <Empty>None found</Empty> : wss.map(w => (
              <Row
                key={w.name}
                onClick={() => setSel(w.name)}
                left={<span style={{ width:7, height:7, borderRadius:'50%', background: sel===w.name ? 'var(--blue)':'var(--text-3)', flexShrink:0 }} />}
                center={
                  <div>
                    <div className="mono" style={{ fontSize:13 }}>{w.name}</div>
                    <div style={{ display:'flex', gap:5, marginTop:3 }}>
                      {w.has_pinned   && <Badge color="green">PINNED</Badge>}
                      {w.has_workflow && <Badge color="blue">WORKFLOW</Badge>}
                    </div>
                  </div>
                }
                chevron
              />
            ))}
          </Card>
        </div>

        <div>
          <div className="section-label" style={{ padding:'0 0 8px' }}>{sel ?? 'Select a workspace'}</div>
          {ws ? (
            <Card>
              {ws.pinned_preview && (
                <div style={{ padding:'12px 16px', borderBottom:'1px solid var(--sep)' }}>
                  <div style={{ fontSize:10, color:'var(--text-3)', marginBottom:6, letterSpacing:'0.06em', textTransform:'uppercase' }}>PINNED.md</div>
                  <pre style={{ fontFamily:'JetBrains Mono,monospace', fontSize:11, color:'var(--text)', whiteSpace:'pre-wrap', maxHeight:120, overflowY:'auto' }}>
                    {ws.pinned_preview}
                  </pre>
                </div>
              )}
              {ws.workflow_preview && (
                <div style={{ padding:'12px 16px' }}>
                  <div style={{ fontSize:10, color:'var(--text-3)', marginBottom:6, letterSpacing:'0.06em', textTransform:'uppercase' }}>WORKFLOW.md</div>
                  <pre style={{ fontFamily:'JetBrains Mono,monospace', fontSize:11, color:'var(--text)', whiteSpace:'pre-wrap', maxHeight:120, overflowY:'auto' }}>
                    {ws.workflow_preview}
                  </pre>
                </div>
              )}
              {!ws.pinned_preview && !ws.workflow_preview && <Empty>No memory files</Empty>}
            </Card>
          ) : (
            <Card><Empty>Select a workspace</Empty></Card>
          )}
        </div>
      </div>
    </div>
  )
}

// Nexus Command
export function NexusCommand() {
  const [messages, setMessages] = useState([])
  const [input, setInput]       = useState('')
  const [loading, setLoading]   = useState(false)
  const bottomRef               = useState(null)

  async function send() {
    const text = input.trim()
    if (!text || loading) return
    const userMsg = { role: 'user', text, ts: Date.now() }
    setMessages(m => [...m, userMsg])
    setInput('')
    setLoading(true)
    try {
      const r = await fetch('/api/nexus/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      })
      const data = await r.json()
      setMessages(m => [...m, {
        role: 'nexus',
        text: data.reply ?? data.error ?? '(no response)',
        tool_steps: data.tool_steps ?? [],
        ts: Date.now(),
      }])
    } catch(e) {
      setMessages(m => [...m, { role: 'nexus', text: `Error: ${e.message}`, ts: Date.now(), error: true }])
    }
    setLoading(false)
  }

  return (
    <div className="fade-up" style={{ padding: '0 0 0', display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <div style={{ padding: '32px 24px 16px', borderBottom: '1px solid var(--sep)', flexShrink: 0 }}>
        <div style={{ fontSize: 24, fontWeight: 700, letterSpacing: '-0.5px' }}>Nexus Command</div>
        <div style={{ fontSize: 13, color: 'var(--text-2)', marginTop: 4 }}>Chat directly with your local Nexus agent</div>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {messages.length === 0 && (
          <div style={{ color: 'var(--text-3)', fontSize: 13, textAlign: 'center', marginTop: 40 }}>
            Send a message to start chatting with Nexus
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: m.role === 'user' ? 'flex-end' : 'flex-start',
          }}>
            {/* Tool steps chips */}
            {m.role === 'nexus' && m.tool_steps?.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 6, maxWidth: '75%' }}>
                {m.tool_steps.map((s, j) => (
                  <div key={j} style={{
                    display: 'flex', alignItems: 'center', gap: 4,
                    padding: '2px 8px', borderRadius: 6, fontSize: 10,
                    background: s.denied ? 'rgba(248,113,113,0.1)' : s.pending_approval ? 'rgba(251,146,60,0.1)' : 'rgba(52,211,153,0.1)',
                    border: `1px solid ${s.denied ? 'rgba(248,113,113,0.2)' : s.pending_approval ? 'rgba(251,146,60,0.2)' : 'rgba(52,211,153,0.2)'}`,
                    color: s.denied ? 'var(--red)' : s.pending_approval ? 'var(--orange)' : 'var(--green)',
                    fontFamily: 'JetBrains Mono, monospace',
                  }}>
                    <span>{s.denied ? 'x' : s.pending_approval ? 'wait' : 'ok'}</span>
                    <span>{s.tool}</span>
                    {s.target && <span style={{ opacity: 0.7 }}>({s.target.length > 30 ? s.target.slice(0,30)+'...' : s.target})</span>}
                  </div>
                ))}
              </div>
            )}
            <div style={{
              maxWidth: '75%',
              padding: '10px 14px',
              borderRadius: m.role === 'user' ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
              background: m.role === 'user' ? 'var(--blue)' : m.error ? 'rgba(248,113,113,0.12)' : 'var(--surface)',
              border: m.role === 'user' ? 'none' : `1px solid ${m.error ? 'rgba(248,113,113,0.2)' : 'var(--border)'}`,
              color: m.role === 'user' ? '#fff' : m.error ? 'var(--red)' : 'var(--text)',
              fontSize: 13,
              lineHeight: 1.6,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}>
              {m.text}
            </div>
            <div style={{ fontSize: 10, color: 'var(--text-3)', marginTop: 3, paddingLeft: 4, paddingRight: 4 }}>
              {m.role === 'user' ? 'you' : 'nexus'} - {new Date(m.ts).toLocaleTimeString()}
            </div>
          </div>
        ))}
        {loading && (
          <div style={{ display: 'flex', alignItems: 'flex-start' }}>
            <div style={{
              padding: '10px 14px', borderRadius: '14px 14px 14px 4px',
              background: 'var(--surface)', border: '1px solid var(--border)',
              fontSize: 13, color: 'var(--text-3)',
            }}>
              thinking...
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div style={{ padding: '12px 20px 20px', borderTop: '1px solid var(--sep)', flexShrink: 0, display: 'flex', gap: 10 }}>
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
          placeholder="Ask Nexus anything..."
          disabled={loading}
          autoFocus
          style={{
            flex: 1, padding: '12px 16px', borderRadius: 12,
            border: '1px solid var(--border)', background: 'var(--surface)',
            color: 'var(--text)', fontSize: 14, outline: 'none',
            opacity: loading ? 0.6 : 1,
          }}
        />
        <button
          onClick={send}
          disabled={loading || !input.trim()}
          style={{
            padding: '12px 20px', borderRadius: 12, border: 'none',
            background: 'var(--blue)', color: '#fff', fontSize: 14,
            cursor: loading ? 'not-allowed' : 'pointer',
            opacity: loading || !input.trim() ? 0.5 : 1,
            transition: 'opacity 0.15s',
          }}
        >
          Send
        </button>
      </div>
    </div>
  )
}

// Runtime Network
const RT_COLORS = {
  nexus:    { primary: '#4f8ef7', dim: 'rgba(79,142,247,0.1)',  border: 'rgba(79,142,247,0.25)'  },
  picoclaw: { primary: '#f59e0b', dim: 'rgba(245,158,11,0.1)',  border: 'rgba(245,158,11,0.25)'  },
  openclaw: { primary: '#a78bfa', dim: 'rgba(167,139,250,0.1)', border: 'rgba(167,139,250,0.25)' },
}

const BUBBLE_PALETTE = [
  '#4f8ef7','#34d399','#f59e0b','#a78bfa','#f87171','#38bdf8','#fb923c','#a3e635','#e879f9','#2dd4bf',
]

function wsColor(name) {
  let h = 0
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) % BUBBLE_PALETTE.length
  return BUBBLE_PALETTE[h]
}

function AgentBubble({ name, turns, active, onReset, resetting }) {
  const color   = wsColor(name)
  const initial = name.charAt(0).toUpperCase()
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5, cursor: 'default' }}
         title={`${name} - ${turns} turns - click to reset`}
         onClick={onReset}>
      <div style={{ position: 'relative' }}>
        <div style={{
          width: 48, height: 48, borderRadius: '50%',
          background: color + '18',
          border: `2px solid ${color}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 18, fontWeight: 700, color,
          boxShadow: active ? `0 0 14px ${color}55` : 'none',
          opacity: resetting ? 0.4 : 1,
          transition: 'opacity 0.2s, box-shadow 0.2s',
          cursor: 'pointer',
        }}>
          {initial}
        </div>
        {turns > 0 && (
          <div style={{
            position: 'absolute', bottom: -1, right: -1,
            background: color, color: '#fff', fontSize: 9, fontWeight: 700,
            borderRadius: 8, padding: '1px 5px', border: '1.5px solid #080b14',
          }}>{turns}</div>
        )}
        {active && (
          <div style={{
            position: 'absolute', top: 0, right: 0,
            width: 10, height: 10, borderRadius: '50%',
            background: 'var(--green)', border: '1.5px solid #080b14',
            boxShadow: '0 0 6px var(--green)',
          }} />
        )}
      </div>
      <div style={{
        fontSize: 9, color: 'var(--text-3)', maxWidth: 58,
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        textAlign: 'center', fontFamily: 'JetBrains Mono, monospace',
      }}>{name}</div>
    </div>
  )
}

function PeerBubble({ peer }) {
  const color   = '#a78bfa'
  const label   = peer.name || peer.host || 'peer'
  const initial = label.charAt(0).toUpperCase()
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5 }}
         title={peer.url ?? label}>
      <div style={{
        width: 44, height: 44, borderRadius: '50%',
        background: color + '18', border: `2px solid ${color}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 16, fontWeight: 700, color,
        boxShadow: `0 0 10px ${color}44`,
      }}>{initial}</div>
      <div style={{
        fontSize: 9, color: 'var(--text-3)', maxWidth: 58,
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        textAlign: 'center',
      }}>{label}</div>
    </div>
  )
}

function RuntimeZone({ name, label, icon, colors, installed, running, model, emptyText, children }) {
  return (
    <div style={{
      flex: 1, borderRadius: 16, overflow: 'hidden',
      border: `1px solid ${running ? colors.border : 'var(--border)'}`,
      background: 'rgba(8,11,20,0.55)',
      display: 'flex', flexDirection: 'column',
      minHeight: 300,
      transition: 'border-color 0.3s',
    }}>
      <div style={{ height: 3, background: running ? colors.primary : 'rgba(255,255,255,0.04)', transition: 'background 0.3s' }} />

      {/* Header */}
      <div style={{ padding: '16px 18px 14px', borderBottom: '1px solid var(--sep)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 38, height: 38, borderRadius: 11, flexShrink: 0,
            background: running ? colors.dim : 'rgba(255,255,255,0.04)',
            border: `1px solid ${running ? colors.border : 'rgba(255,255,255,0.07)'}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 18, transition: 'all 0.3s',
          }}>{icon}</div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 14, fontWeight: 700, letterSpacing: '-0.2px' }}>{label}</div>
            <div style={{ fontSize: 10, color: 'var(--text-3)', marginTop: 2, fontFamily: 'JetBrains Mono, monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {model}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5, flexShrink: 0 }}>
            <div style={{
              width: 7, height: 7, borderRadius: '50%',
              background: running ? colors.primary : installed ? 'var(--orange)' : 'rgba(255,255,255,0.2)',
              boxShadow: running ? `0 0 7px ${colors.primary}` : 'none',
              transition: 'all 0.3s',
            }} />
            <span style={{ fontSize: 11, color: running ? colors.primary : 'var(--text-3)', transition: 'color 0.3s' }}>
              {running ? 'running' : installed ? 'idle' : 'not found'}
            </span>
          </div>
        </div>
      </div>

      {/* Sub-agents area */}
      <div style={{
        flex: 1, padding: '16px 18px',
        display: 'flex', flexWrap: 'wrap', gap: 14, alignContent: 'flex-start',
      }}>
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
  const items = events.filter(e =>
    ['task_update','audit_event','approval_pending','approval_resolved'].includes(e.type)
  ).slice(0, 80)

  function label(e) {
    const d = e.data ?? {}
    if (e.type === 'task_update')       return `${d.status ?? 'update'}: ${(d.intent ?? d.description ?? '').slice(0, 55)}`
    if (e.type === 'audit_event')       return `${(d.decision ?? '').toUpperCase()} ${d.tool ?? ''} ${d.target ? `-> ${String(d.target).slice(0, 25)}` : ''}`
    if (e.type === 'approval_pending')  return `approval pending: ${d.tool ?? ''} on ${String(d.target ?? '').slice(0, 25)}`
    if (e.type === 'approval_resolved') return `${d.decision === 'approved' ? 'approved' : 'denied'} ${d.approval_id?.slice(0, 8)}`
    return e.type
  }

  function color(e) {
    if (e.type === 'approval_pending')  return 'var(--orange)'
    if (e.type === 'approval_resolved') return e.data?.decision === 'approved' ? 'var(--green)' : 'var(--red)'
    if (e.type === 'audit_event') {
      const d = e.data?.decision ?? ''
      if (d === 'approved' || d === 'allow') return 'var(--green)'
      if (d === 'denied'   || d === 'deny')  return 'var(--red)'
    }
    if (e.type === 'task_update') {
      const s = e.data?.status ?? ''
      if (s === 'completed') return 'var(--green)'
      if (s === 'failed')    return 'var(--red)'
      if (s === 'running')   return 'var(--blue)'
    }
    return 'var(--text-3)'
  }

  return (
    <div style={{
      width: 272, flexShrink: 0,
      borderLeft: '1px solid var(--sep)',
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
    }}>
      <div style={{ padding: '14px 16px 12px', borderBottom: '1px solid var(--sep)', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--green)', boxShadow: '0 0 5px var(--green)' }} />
          <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'var(--text-2)' }}>
            Live Activity
          </span>
        </div>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: '4px 0' }}>
        {items.length === 0 ? (
          <div style={{ padding: '28px 16px', fontSize: 12, color: 'var(--text-3)', textAlign: 'center' }}>
            Waiting for activity...
          </div>
        ) : items.map((e, i) => (
          <div key={i} style={{ padding: '8px 16px', borderBottom: '1px solid rgba(255,255,255,0.025)' }}>
            <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.2)', fontFamily: 'JetBrains Mono,monospace', marginBottom: 2 }}>
              {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </div>
            <div style={{ fontSize: 11, color: color(e), lineHeight: 1.45, wordBreak: 'break-word' }}>
              {label(e)}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export function Agents({ events = [], runtimes = {} }) {
  const [sessions,  setSessions]  = useState([])
  const [peers,     setPeers]     = useState([])
  const [loading,   setLoading]   = useState(true)
  const [resetting, setResetting] = useState(null)

  async function load() {
    setLoading(true)
    try {
      const [agts, prs] = await Promise.all([
        api.agents(),
        fetch('/api/peers').then(r => r.json()).catch(() => ({ peers: [] })),
      ])
      setSessions(agts.sessions ?? [])
      setPeers(prs.peers ?? [])
    } catch(e) { console.error(e) }
    finally { setLoading(false) }
  }

  async function resetSession(workspace_id) {
    setResetting(workspace_id)
    try { await api.resetAgent(workspace_id) } catch(e) { console.error(e) }
    setResetting(null)
    api.agents().then(d => setSessions(d.sessions ?? [])).catch(() => {})
  }

  useEffect(() => { load() }, [])

  // Poll sessions every 6s
  useEffect(() => {
    const id = setInterval(() => {
      api.agents().then(d => setSessions(d.sessions ?? [])).catch(() => {})
    }, 6000)
    return () => clearInterval(id)
  }, [])

  const nexus    = runtimes.nexus    ?? {}
  const picoclaw = runtimes.picoclaw ?? {}
  const openclaw = runtimes.openclaw ?? {}
  const total    = [nexus, picoclaw, openclaw].filter(r => r.running).length

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ padding: '20px 24px 16px', borderBottom: '1px solid var(--sep)', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-0.5px' }}>Runtime Network</div>
          <div style={{ fontSize: 12, color: 'var(--text-2)', marginTop: 3 }}>
            {total} runtime{total !== 1 ? 's' : ''} active - {sessions.length} session{sessions.length !== 1 ? 's' : ''} - {peers.length} peer{peers.length !== 1 ? 's' : ''}
          </div>
        </div>
        <Btn size="sm" onClick={load} disabled={loading}>{loading ? '...' : 'Refresh'}</Btn>
      </div>

      {/* Body */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Three zones */}
        <div style={{ flex: 1, padding: '16px', display: 'flex', gap: 12, overflow: 'hidden' }}>

          {/* Nexus */}
          <RuntimeZone
            name="nexus" label="Nexus" icon="N"
            colors={RT_COLORS.nexus}
            installed={nexus.installed ?? true}
            running={nexus.running}
            model={`local - ${nexus.model ?? 'qwen2.5:7b'}`}
            emptyText="No active sessions - chat in Nexus Command"
          >
            {sessions.length > 0 ? sessions.map(s => (
              <AgentBubble
                key={s.workspace_id}
                name={s.workspace_id}
                turns={s.turn}
                active={s.turn > 0}
                resetting={resetting === s.workspace_id}
                onReset={() => resetSession(s.workspace_id)}
              />
            )) : undefined}
          </RuntimeZone>

          {/* PicoClaw */}
          <RuntimeZone
            name="picoclaw" label="PicoClaw" icon="P"
            colors={RT_COLORS.picoclaw}
            installed={picoclaw.installed}
            running={picoclaw.running}
            model="edge - on-device inference"
            emptyText={
              picoclaw.running ? 'Running - no sub-agents exposed'
              : picoclaw.installed ? 'Installed - not running'
              : 'Not installed on this device'
            }
          />

          {/* OpenClaw */}
          <RuntimeZone
            name="openclaw" label="OpenClaw" icon="O"
            colors={RT_COLORS.openclaw}
            installed={openclaw.installed}
            running={openclaw.running}
            model={`gateway - ${openclaw.model ?? 'cloud'}`}
            emptyText={
              !openclaw.installed ? 'Not installed'
              : !openclaw.running ? 'Gateway offline'
              : 'No peers discovered yet'
            }
          >
            {peers.length > 0 ? peers.map((p, i) => (
              <PeerBubble key={i} peer={p} />
            )) : undefined}
          </RuntimeZone>
        </div>

        {/* Live activity feed */}
        <LiveFeed events={events} />
      </div>
    </div>
  )
}

// Audit
export function Audit({ events }) {
  const [entries, setEntries] = useState([])
  const [loading, setLoad]    = useState(true)
  const [live, setLive]       = useState(true)
  const [expanded, setEx]     = useState(null)

  async function load() {
    setLoad(true)
    try {
      const d = await api.audit(200)
      setEntries(d.entries ?? [])
    } catch(e) { console.error(e) }
    finally { setLoad(false) }
  }
  useEffect(() => { load() }, [])

  useEffect(() => {
    if (!live) return
    const fresh = events.filter(e => e.type === 'audit_event')
    if (!fresh.length) return
    setEntries(p => {
      const seen = new Set(p.map(e => e.entry_hash))
      return [...fresh.map(e => e.data).filter(e => !seen.has(e.entry_hash)), ...p]
    })
  }, [events, live])

  const dColor = d => d==='approved'?'var(--green)':d==='denied'?'var(--red)':d==='pending'?'var(--orange)':'var(--text-3)'
  const dBadge = d => d==='approved'?'green':d==='denied'?'red':d==='pending'?'orange':'gray'
  const tColor = t => !t?'var(--text)':t.includes('shell')||t.includes('exec')?'var(--red)':t.includes('file')||t.includes('write')?'var(--orange)':t.includes('web')||t.includes('http')?'var(--blue)':'var(--green)'

  return (
    <div className="fade-up" style={{ padding: '0 0 48px' }}>
      <div style={{ padding:'32px 24px 0', display:'flex', alignItems:'flex-end', justifyContent:'space-between' }}>
        <div>
          <div style={{ fontSize:24, fontWeight:700, letterSpacing:'-0.5px' }}>Audit Log</div>
          <div style={{ fontSize:13, color:'var(--text-2)', marginTop:4 }}>Merkle-chained tamper-evident journal</div>
        </div>
        <div style={{ display:'flex', gap:8 }}>
          <button
            onClick={() => setLive(l => !l)}
            style={{
              background: live ? 'var(--green-dim)' : 'var(--glass-2)',
              border: `1px solid ${live ? 'rgba(52,211,153,0.3)' : 'var(--border)'}`,
              color: live ? 'var(--green)' : 'var(--text-2)',
              borderRadius: 8, padding:'5px 12px', fontSize:12,
              fontWeight:500, cursor:'pointer', fontFamily:'inherit',
            }}
          >
            {live ? 'Live On' : 'Live Off'}
          </button>
          <Btn size="sm" onClick={load} disabled={loading}>{loading ? '...' : 'Reload'}</Btn>
        </div>
      </div>

      <SectionLabel>{entries.length} entries</SectionLabel>
      <div style={{ padding:'0 20px' }}>
        <Card>
          {entries.length === 0 ? <Empty>No audit entries yet</Empty> : entries.map((entry, i) => {
            const key      = entry.entry_hash ?? i
            const decision = entry.decision ?? entry.action ?? entry.event ?? 'event'
            const isOpen   = expanded === key

            return (
              <div key={key}>
                <Row
                  onClick={() => setEx(e => e === key ? null : key)}
                  left={<span style={{ width:7, height:7, borderRadius:'50%', background:dColor(decision), flexShrink:0 }} />}
                  center={
                    <span className="mono" style={{ fontSize:12, color:tColor(entry.tool), overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                      {entry.tool ?? entry.type ?? '-'}
                    </span>
                  }
                  right={
                    <div style={{ display:'flex', alignItems:'center', gap:8 }}>
                      <Badge color={dBadge(decision)}>{decision}</Badge>
                      <span className="ts">{(entry.entry_hash ?? '').slice(0,7)}</span>
                      <Ts value={entry.timestamp} />
                      <svg width="6" height="11" viewBox="0 0 6 11" fill="none" style={{ transform: isOpen?'rotate(90deg)':'none', transition:'.15s', flexShrink:0 }}>
                        <path d="M1 1l4 4.5L1 10" stroke="var(--text-3)" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </div>
                  }
                />
                {isOpen && (
                  <div className="detail-panel">
                    {[['task_id',entry.task_id],['agent_id',entry.agent_id],['tool',entry.tool],['target',entry.target]]
                      .filter(([,v])=>v)
                      .map(([k,v]) => (
                        <div key={k} style={{ marginBottom:3 }}>
                          <span style={{ color:'var(--text-3)' }}>{k.padEnd(10,' ')}</span>
                          <span>{v}</span>
                        </div>
                      ))
                    }
                    {entry.prev_hash  && <div style={{ marginTop:6, color:'var(--text-3)' }}>prev: {entry.prev_hash.slice(0,48)}...</div>}
                    {entry.entry_hash && <div style={{ color:'var(--text-2)' }}># {entry.entry_hash.slice(0,48)}...</div>}
                    <details style={{ marginTop:6 }}>
                      <summary style={{ cursor:'pointer', color:'var(--text-3)', fontSize:10 }}>raw JSON</summary>
                      <pre style={{ marginTop:4, fontSize:10, color:'var(--text-2)', whiteSpace:'pre-wrap', wordBreak:'break-all', maxHeight:180, overflowY:'auto' }}>
                        {JSON.stringify(entry,null,2)}
                      </pre>
                    </details>
                  </div>
                )}
              </div>
            )
          })}
        </Card>
      </div>
    </div>
  )
}

