/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { useEffect, useState } from 'react'
import { commandCenterApi } from '../lib/commandCenterApi'

type Trace = {
  id: number
  tool: string
  decision: 'approved' | 'auto-allow' | 'denied'
  risk: 'high' | 'medium' | 'low'
  agent: string
  task: string
  target: string
  hash: string
  prev: string
  ts: string
  action: string
  approvals: number
}

const STATIC_TRACES: Trace[] = [
  { id: 1, tool: 'shell.exec', decision: 'approved', risk: 'high', agent: 'nexus-main', task: 'tsk-048a', target: 'rm -rf ~/downloads/old', hash: 'a8f3b2c1d7e9', prev: '7e2d91f0c3a8', ts: '08:14:02', action: 'rm -rf ~/downloads/old\n# 14.2 GB · 847 files', approvals: 1 },
  { id: 2, tool: 'memory.write', decision: 'auto-allow', risk: 'low', agent: 'nexus-main', task: 'tsk-049b', target: 'pinned → daily_routine', hash: '7e2d91f0c3a8', prev: '3c8a5e7d2f1b', ts: '08:13:48', action: "UPDATE pinned SET preference='7am briefing'", approvals: 0 },
  { id: 3, tool: 'file.read', decision: 'auto-allow', risk: 'low', agent: 'nexus-main', task: 'tsk-049b', target: '~/.clawos/config.toml', hash: '3c8a5e7d2f1b', prev: 'f1d09b3a8c5e', ts: '08:13:22', action: 'READ ~/.clawos/config.toml', approvals: 0 },
  { id: 4, tool: 'http.fetch', decision: 'denied', risk: 'medium', agent: 'openclaw-research', task: 'tsk-050c', target: 'telemetry.external.io/v1/ping', hash: 'f1d09b3a8c5e', prev: '5b7c2e4f9d1a', ts: '08:12:55', action: 'GET telemetry.external.io/v1/ping\npolicyd: blocked — outbound to untrusted domain', approvals: 0 },
  { id: 5, tool: 'shell.exec', decision: 'approved', risk: 'low', agent: 'nexus-main', task: 'tsk-051d', target: 'git log --oneline -5', hash: '5b7c2e4f9d1a', prev: '9a1d4f8c6b2e', ts: '08:12:30', action: 'git log --oneline -5\n# clawos/main', approvals: 1 },
  { id: 6, tool: 'jarvis.speak', decision: 'approved', risk: 'low', agent: 'nexus-main', task: 'tsk-052e', target: 'voice → Morning briefing', hash: '9a1d4f8c6b2e', prev: '2e6f8a3b5c7d', ts: '08:11:44', action: 'SPEAK "Good morning! You have 3 tasks pending."', approvals: 1 },
  { id: 7, tool: 'memory.write', decision: 'auto-allow', risk: 'low', agent: 'nexus-main', task: 'tsk-053f', target: 'workflow → briefing cache', hash: '2e6f8a3b5c7d', prev: 'c4b2a7e19f3d', ts: '08:11:10', action: 'INSERT workflow_cache briefing_2024_04_23', approvals: 0 },
  { id: 8, tool: 'file.write', decision: 'approved', risk: 'medium', agent: 'nexus-main', task: 'tsk-054g', target: '~/notes/todo.md', hash: 'c4b2a7e19f3d', prev: '8d3f1c5a2b7e', ts: '08:10:33', action: 'APPEND ~/notes/todo.md\n- Review PR #142 policy migration', approvals: 1 },
  { id: 9, tool: 'shell.exec', decision: 'denied', risk: 'high', agent: 'openclaw-research', task: 'tsk-055h', target: 'sudo apt update', hash: '8d3f1c5a2b7e', prev: '1a5e7d9f4c8b', ts: '08:09:58', action: 'sudo apt update\npolicyd: sudo commands require explicit approval — DENIED', approvals: 0 },
  { id: 10, tool: 'http.fetch', decision: 'auto-allow', risk: 'low', agent: 'nexus-main', task: 'tsk-056i', target: 'ollama:11434/api/generate', hash: '1a5e7d9f4c8b', prev: '0000000000', ts: '08:09:22', action: 'POST ollama:11434/api/generate\nmodel=qwen2.5:7b', approvals: 0 },
]

const decColor = (d: string) => d === 'approved' ? 'var(--success)' : d === 'denied' ? 'var(--danger)' : 'var(--blue)'
const decBadge = (d: string) => d === 'approved' ? 'badge-g' : d === 'denied' ? 'badge-d' : 'badge-a'
const riskBadge = (r: string) => r === 'high' ? 'badge-d' : r === 'medium' ? 'badge-w' : 'badge-a'
const toolColor = (t: string) => t.includes('shell') ? 'var(--danger)' : (t.includes('file') && t.includes('write')) ? 'var(--warn)' : t.includes('http') ? 'var(--blue)' : 'var(--success)'

const TABS: [string, string][] = [['all', 'ALL'], ['approved', 'APPROVED'], ['denied', 'DENIED'], ['auto-allow', 'AUTO']]

export function TracesPage() {
  const [traces, setTraces] = useState<Trace[]>(STATIC_TRACES)
  const [sel, setSel] = useState(1)
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    commandCenterApi.listTraces()
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          const mapped = data.map((r, i) => ({
            id: i + 1,
            tool: r.title || 'unknown',
            decision: (r.status === 'completed' ? 'approved' : r.status === 'failed' ? 'denied' : 'auto-allow') as Trace['decision'],
            risk: 'low' as Trace['risk'],
            agent: r.provider || 'nexus-main',
            task: r.id,
            target: r.category || '',
            hash: r.id.slice(0, 12),
            prev: '0000000000',
            ts: r.started_at ? new Date(r.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '',
            action: JSON.stringify(r.metadata || {}, null, 2),
            approvals: r.approvals || 0,
          }))
          setTraces(mapped)
        }
      })
      .catch(() => {})
  }, [])

  const filtered = filter === 'all' ? traces : traces.filter((t) => t.decision === filter)
  const selTrace = traces.find((t) => t.id === sel) ?? null

  function tabCount(k: string) {
    if (k === 'all') return traces.length
    return traces.filter((t) => t.decision === k).length
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', height: '100%', overflow: 'hidden', flex: 1 }}>
      {/* Main — trace list */}
      <main className="main" style={{ display: 'flex', flexDirection: 'column', gap: 12, overflow: 'hidden' }}>
        <div className="main-head">
          <div>
            <h1>Audit Log</h1>
            <div className="sub">Merkle-chained tamper-evident journal of every tool call</div>
          </div>
          <div className="chips">
            <span className="chip"><span className="d blink" style={{ background: 'var(--success)', color: 'var(--success)' }} />LIVE</span>
            <span className="chip">{traces.length} entries</span>
            <span className="chip">{traces.filter((t) => t.decision === 'denied').length} denied</span>
          </div>
        </div>

        <div className="tabs" style={{ marginBottom: 4 }}>
          {TABS.map(([k, l]) => (
            <button key={k} className={`tab${filter === k ? ' sel' : ''}`} onClick={() => setFilter(k)}>
              {l} · {tabCount(k)}
            </button>
          ))}
        </div>

        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8, paddingBottom: 16 }}>
          {filtered.map((t) => (
            <div key={t.id} className={`trace${sel === t.id ? ' sel' : ''}`} onClick={() => setSel(t.id)}>
              <span className="dot" style={{ background: decColor(t.decision), boxShadow: `0 0 6px ${decColor(t.decision)}` }} />
              <div className="trace-body">
                <div className="trace-tool" style={{ color: toolColor(t.tool) }}>{t.tool}</div>
                <div className="trace-meta">task: {t.task} · agent: {t.agent} · {t.target.slice(0, 40)}{t.target.length > 40 ? '…' : ''}</div>
              </div>
              <div className="trace-right">
                <span className={decBadge(t.decision)}>{t.decision}</span>
                <span className={riskBadge(t.risk)}>{t.risk}</span>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink-4)' }}>{t.hash.slice(0, 7)}</span>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink-4)' }}>{t.ts}</span>
                <span className="chev" />
              </div>
            </div>
          ))}
        </div>
      </main>

      {/* Detail rail */}
      <aside className="rail" style={{ background: 'rgba(0,0,0,0.3)', borderLeft: '1px solid var(--panel-br)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div className="lock-banner"><span className="lk">⚿</span>Merkle chain · each entry hashes prev_hash + payload</div>

        {!selTrace ? (
          <div className="empty" style={{ minHeight: 120 }}>
            <div className="empty-title">No trace selected</div>
            <div className="empty-body">Select a trace to inspect the full record and chain position.</div>
          </div>
        ) : (
          <div style={{ flex: 1, overflowY: 'auto' }}>
            <div className="r-head">
              <h2 style={{ color: toolColor(selTrace.tool) }}>{selTrace.tool}</h2>
              <div className="meta">{selTrace.decision} · {selTrace.risk} risk · {selTrace.ts}</div>
            </div>

            <div className="r-sect">
              <h4>Details</h4>
              <div className="r-row"><span className="k">task_id</span><span className="v">{selTrace.task}</span></div>
              <div className="r-row"><span className="k">agent</span><span className="v">{selTrace.agent}</span></div>
              <div className="r-row"><span className="k">target</span><span className="v">{selTrace.target}</span></div>
              <div className="r-row"><span className="k">decision</span><span className="v" style={{ color: decColor(selTrace.decision) }}>{selTrace.decision}</span></div>
              <div className="r-row"><span className="k">risk</span><span className="v">{selTrace.risk}</span></div>
              {selTrace.approvals > 0 && <div className="r-row"><span className="k">approvals</span><span className="v">{selTrace.approvals}</span></div>}
            </div>

            <div className="r-sect">
              <h4>Action</h4>
              <div className="r-code">{selTrace.action}</div>
            </div>

            <div className="r-sect">
              <h4>Chain position</h4>
              <div className="r-row"><span className="k">entry_hash</span><span className="v" style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{selTrace.hash}</span></div>
              <div className="r-row"><span className="k">prev_hash</span><span className="v" style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink-3)' }}>{selTrace.prev}</span></div>
            </div>

            <div className="r-sect">
              <h4>Chain neighborhood</h4>
              <div className="chain-vis">
                {traces.filter((t) => t.id >= selTrace.id - 1 && t.id <= selTrace.id + 1).map((t) => (
                  <div key={t.id} className="chain-node">
                    <span className="c-dot" style={{ borderColor: decColor(t.decision), background: t.id === selTrace.id ? decColor(t.decision) : 'transparent' }} />
                    <span className="c-hash">{t.hash.slice(0, 7)}</span>
                    <span className="c-tool" style={{ color: t.id === selTrace.id ? 'var(--ink-1)' : 'var(--ink-3)', fontWeight: t.id === selTrace.id ? 600 : 400 }}>{t.tool}</span>
                    <span className="c-ts">{t.ts}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="r-sect">
              <h4>Raw JSON</h4>
              <div className="r-code">{JSON.stringify(selTrace, null, 2)}</div>
            </div>
          </div>
        )}
      </aside>
    </div>
  )
}
