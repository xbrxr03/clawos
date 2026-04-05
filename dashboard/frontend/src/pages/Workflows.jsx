import { useState, useEffect, useRef } from 'react'
import { Card, Row, Badge, SectionLabel, Empty } from '../components/ui.jsx'

const CATEGORIES = ['all', 'files', 'documents', 'developer', 'content', 'system', 'data']

const CAT_COLORS = {
  files: 'blue',
  documents: 'purple',
  developer: 'green',
  content: 'orange',
  system: 'red',
  data: 'blue',
}

function formatPlatforms(wf) {
  if (!wf.platforms || wf.platforms.length === 0) return 'all platforms'
  return wf.platforms.join(', ')
}

export function Workflows() {
  const [workflows, setWorkflows] = useState([])
  const [category, setCategory] = useState('all')
  const [search, setSearch] = useState('')
  const [running, setRunning] = useState(null)
  const [output, setOutput] = useState('')
  const [outTitle, setOutTitle] = useState('')
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const wsRef = useRef(null)

  useEffect(() => {
    const params = new URLSearchParams()
    if (category !== 'all') params.set('category', category)
    if (search) params.set('search', search)
    setLoading(true)
    fetch(`/api/workflows/list?${params}`)
      .then(r => r.json())
      .then(data => {
        setWorkflows(Array.isArray(data) ? data : [])
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [category, search])

  useEffect(() => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const sock = new WebSocket(`${proto}://${location.host}/ws`)
    wsRef.current = sock
    sock.onmessage = ({ data }) => {
      try {
        const msg = JSON.parse(data)
        if (msg.type === 'workflow_progress' && msg.data) {
          if (msg.data.status !== 'running') setRunning(null)
          if (msg.data.output) setOutput(msg.data.output)
        }
        if (msg.type === 'workflow_error' && msg.data) {
          setRunning(null)
          setOutput(`Error: ${msg.data.error}`)
        }
      } catch {}
    }
    return () => sock.close()
  }, [])

  async function runWorkflow(wf) {
    setRunning(wf.id)
    setOutput('')
    setOutTitle(wf.name)
    try {
      const response = await fetch(`/api/workflows/${wf.id}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ args: {}, workspace: 'nexus_default' }),
      })
      const result = await response.json()
      const text = result.output || result.error || ''
      setOutput(text)
      setHistory(h => [
        { id: wf.id, name: wf.name, status: result.status || 'ok', ts: Date.now() },
        ...h,
      ].slice(0, 20))
    } catch (error) {
      setOutput(`Failed: ${error.message}`)
    }
    setRunning(null)
  }

  const filtered = search
    ? workflows.filter(w =>
        w.name.toLowerCase().includes(search.toLowerCase()) ||
        w.description.toLowerCase().includes(search.toLowerCase()) ||
        (w.tags || []).some(t => t.includes(search.toLowerCase())))
    : workflows

  return (
    <div className="fade-up" style={{ padding: '0 0 48px' }}>
      <div style={{ padding: '32px 24px 12px' }}>
        <div style={{ fontSize: 24, fontWeight: 700, letterSpacing: '-0.5px' }}>Workflows</div>
        <div style={{ fontSize: 13, color: 'var(--text-2)', marginTop: 4 }}>
          One-command tasks · {workflows.length} available · offline on supported platforms
        </div>
      </div>

      <div style={{ padding: '0 20px 12px' }}>
        <input
          placeholder="Search workflows..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{
            width: '100%',
            padding: '9px 14px',
            borderRadius: 8,
            boxSizing: 'border-box',
            border: '1px solid var(--border)',
            background: 'var(--surface)',
            color: 'var(--text)',
            fontSize: 13,
            outline: 'none',
          }}
        />
      </div>

      <div style={{ padding: '0 20px 14px', display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {CATEGORIES.map(c => (
          <button
            key={c}
            onClick={() => setCategory(c)}
            style={{
              padding: '5px 12px',
              borderRadius: 20,
              fontSize: 12,
              cursor: 'pointer',
              border: '1px solid var(--border)',
              background: category === c ? 'var(--blue)' : 'var(--surface)',
              color: category === c ? '#fff' : 'var(--text-2)',
              fontWeight: category === c ? 500 : 400,
              transition: 'all 0.15s',
            }}
          >
            {c}
          </button>
        ))}
      </div>

      <SectionLabel>{loading ? 'Loading...' : `${filtered.length} workflows`}</SectionLabel>
      <div style={{ padding: '0 20px' }}>
        {loading ? (
          <Card><Empty>Loading workflows...</Empty></Card>
        ) : filtered.length === 0 ? (
          <Card><Empty>No workflows match</Empty></Card>
        ) : (
          <Card>
            {filtered.map(wf => (
              <Row
                key={wf.id}
                left={
                  <Badge color={CAT_COLORS[wf.category] || 'blue'}>
                    {wf.category}
                  </Badge>
                }
                center={
                  <div>
                    <div style={{ fontWeight: 500, fontSize: 13 }}>{wf.name}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-2)', marginTop: 2 }}>
                      {wf.description}
                    </div>
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 6 }}>
                      {wf.destructive && <Badge color="orange">destructive</Badge>}
                      <Badge color={wf.needs_agent ? 'blue' : 'green'}>
                        {wf.needs_agent ? 'agent' : 'direct'}
                      </Badge>
                      <Badge color="gray">{formatPlatforms(wf)}</Badge>
                    </div>
                    {wf.requires?.length > 0 && (
                      <div style={{ fontSize: 10, color: 'var(--text-3)', marginTop: 4 }}>
                        requires: {wf.requires.join(', ')}
                      </div>
                    )}
                  </div>
                }
                right={
                  <button
                    disabled={running !== null}
                    onClick={() => runWorkflow(wf)}
                    style={{
                      padding: '5px 14px',
                      borderRadius: 7,
                      fontSize: 12,
                      cursor: running ? 'not-allowed' : 'pointer',
                      border: 'none',
                      fontWeight: 500,
                      background: running === wf.id ? 'var(--surface)' : 'var(--blue)',
                      color: running === wf.id ? 'var(--text-2)' : '#fff',
                      opacity: running !== null && running !== wf.id ? 0.4 : 1,
                      transition: 'all 0.15s',
                    }}
                  >
                    {running === wf.id ? '...' : 'Run'}
                  </button>
                }
              />
            ))}
          </Card>
        )}
      </div>

      {output && (
        <>
          <SectionLabel>Output - {outTitle}</SectionLabel>
          <div style={{ padding: '0 20px' }}>
            <Card>
              <pre style={{
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                fontSize: 12,
                fontFamily: 'JetBrains Mono, monospace',
                color: 'var(--text-2)',
                margin: 0,
                padding: '4px 0',
                maxHeight: 400,
                overflowY: 'auto',
              }}>
                {output}
              </pre>
            </Card>
          </div>
        </>
      )}

      {history.length > 0 && (
        <>
          <SectionLabel>Recent Runs</SectionLabel>
          <div style={{ padding: '0 20px' }}>
            <Card>
              {history.map((h, i) => (
                <Row
                  key={i}
                  left={<Badge color={h.status === 'ok' ? 'green' : 'red'}>{h.status}</Badge>}
                  center={<span style={{ fontSize: 13 }}>{h.name}</span>}
                  right={<span style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'monospace' }}>{new Date(h.ts).toLocaleTimeString()}</span>}
                />
              ))}
            </Card>
          </div>
        </>
      )}
    </div>
  )
}
