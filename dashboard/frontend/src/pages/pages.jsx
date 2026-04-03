import { useState, useEffect } from 'react'
import { Card, Row, StatusDot, Badge, SectionLabel, Ts, Btn, Empty } from '../components/ui.jsx'
import { api } from '../lib/api.js'

// ── Tasks ─────────────────────────────────────────────────────────────────────
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
                        {t.id}{t.agent ? ` · ${t.agent}` : ''}
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

// ── Approvals ─────────────────────────────────────────────────────────────────
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

      <SectionLabel>Inbox {approvals.length > 0 ? `· ${approvals.length}` : ''}</SectionLabel>

      {approvals.length === 0 ? (
        <div style={{ padding: '0 20px' }}>
          <Card><Empty>All clear — no pending approvals</Empty></Card>
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
                        task: {a.task_id ?? '—'} · agent: {a.agent ?? '—'}
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
                      ✓ {deciding[a.id] === 'approve' ? 'Approving…' : 'Approve'}
                    </Btn>
                    <Btn variant="danger" onClick={() => decide(a.id, 'deny')} disabled={!!deciding[a.id]}>
                      ✕ {deciding[a.id] === 'deny' ? 'Denying…' : 'Deny'}
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

// ── Models ────────────────────────────────────────────────────────────────────
const SUGGESTED = [
  { name: 'qwen2.5:7b',       size: '4.7GB', note: 'Default · best balance'  },
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

      <SectionLabel>Installed · {installed.length}</SectionLabel>
      <div style={{ padding: '0 20px' }}>
        {installed.length === 0 ? (
          <Card><Empty>No models — is Ollama running?</Empty></Card>
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
                  <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>{s.note} · {s.size}</div>
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
                      {pullProgress[s.name] ? 'Pulling…' : 'Get'}
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

// ── Memory ────────────────────────────────────────────────────────────────────
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
        <Btn size="sm" onClick={load} disabled={loading}>{loading ? '…' : 'Refresh'}</Btn>
      </div>

      <SectionLabel>Layers</SectionLabel>
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:10, padding:'0 20px' }}>
        <div className="stat-card">
          <div className="stat-val" style={{ color:'var(--green)' }}>{stats?.pinned_lines ?? '—'}<span className="stat-unit">lines</span></div>
          <div className="stat-label">PINNED.md · Layer 1</div>
        </div>
        <div className="stat-card">
          <div className="stat-val" style={{ color:'var(--blue)' }}>{stats?.workflow_lines ?? '—'}<span className="stat-unit">lines</span></div>
          <div className="stat-label">WORKFLOW.md · Layer 2</div>
        </div>
        <div className="stat-card">
          <div className="stat-val" style={{ color:'var(--purple)' }}>{stats?.chroma_size_mb ?? '—'}<span className="stat-unit">MB</span></div>
          <div className="stat-label">ChromaDB · Layer 3</div>
        </div>
        <div className="stat-card">
          <div className="stat-val" style={{ color:'var(--orange)' }}>{stats?.sqlite_size_mb ?? '—'}<span className="stat-unit">MB</span></div>
          <div className="stat-label">SQLite FTS5 · Layer 4</div>
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

// ── Nexus Command ─────────────────────────────────────────────────────────────
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
      setMessages(m => [...m, { role: 'nexus', text: data.reply ?? data.error ?? '(no response)', ts: Date.now() }])
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
              {m.role === 'user' ? 'you' : 'nexus'} · {new Date(m.ts).toLocaleTimeString()}
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
              thinking…
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
          placeholder="Ask Nexus anything…"
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

// ── Audit ─────────────────────────────────────────────────────────────────────
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
            {live ? '⬤ Live' : '○ Live'}
          </button>
          <Btn size="sm" onClick={load} disabled={loading}>{loading ? '…' : 'Reload'}</Btn>
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
                      {entry.tool ?? entry.type ?? '—'}
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
                    {entry.prev_hash  && <div style={{ marginTop:6, color:'var(--text-3)' }}>↑ {entry.prev_hash.slice(0,48)}…</div>}
                    {entry.entry_hash && <div style={{ color:'var(--text-2)' }}># {entry.entry_hash.slice(0,48)}…</div>}
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
