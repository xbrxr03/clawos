/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { useEffect, useState } from 'react'
import { commandCenterApi } from '../lib/commandCenterApi'

const CATS: Record<string, string> = {
  files: 'var(--blue)', documents: 'var(--violet)', developer: 'var(--success)',
  content: 'var(--warn)', system: 'var(--danger)', data: 'var(--blue)',
}
const ICONS: Record<string, string> = {
  files: '▤', documents: '¶', developer: '{}', content: '✎', system: '⚙', data: '▦',
}

type Wf = {
  id: string; name: string; category: string; description: string
  cmd: string; hero: boolean; destructive: boolean; platforms: string[]
  last: { status: string; t: string; output: string | null } | null
}

const STATIC_WFS: Wf[] = [
  { id: 'organize-downloads', name: 'Organize downloads', category: 'files', description: 'Sort ~/Downloads by file type, move stale files to archive, rename duplicates.', cmd: 'clawctl wf organize-downloads', hero: true, destructive: false, platforms: ['linux', 'macos'], last: { status: 'completed', t: '08:14', output: 'Moved 23 files · 1.4 GB freed · 3 duplicates renamed' } },
  { id: 'summarize-pdf', name: 'Summarize PDF', category: 'documents', description: 'Extract text from a PDF, run through qwen2.5 for a structured summary.', cmd: 'clawctl wf summarize-pdf <path>', hero: true, destructive: false, platforms: ['all'], last: { status: 'completed', t: 'yesterday', output: "3-page summary of 'ReAct paper' → ~/notes/react-summary.md" } },
  { id: 'pr-review', name: 'PR review', category: 'developer', description: 'Fetch PR diff, generate inline comments, post review draft to GitHub.', cmd: 'clawctl wf pr-review <pr-url>', hero: false, destructive: false, platforms: ['all'], last: { status: 'completed', t: '08:12', output: 'PR #142 — 3 inline comments, 1 suggestion' } },
  { id: 'repo-summary', name: 'Repo summary', category: 'developer', description: 'Analyze repo structure, README, recent commits. Output a structured overview.', cmd: 'clawctl wf repo-summary <path>', hero: false, destructive: false, platforms: ['all'], last: null },
  { id: 'morning-briefing', name: 'Morning briefing', category: 'content', description: 'Compile calendar, git, disk, and messages into a spoken briefing via JARVIS voice.', cmd: 'clawctl wf morning-briefing', hero: false, destructive: false, platforms: ['all'], last: { status: 'completed', t: '08:09', output: 'Briefing delivered via JARVIS voice' } },
  { id: 'daily-digest', name: 'Daily digest', category: 'content', description: 'End-of-day summary: tasks done, approvals decided, memory growth, upcoming tomorrow.', cmd: 'clawctl wf daily-digest', hero: false, destructive: false, platforms: ['all'], last: { status: 'completed', t: 'yesterday', output: 'Digest: 8 tasks, 5 approvals, +142 brain facts' } },
  { id: 'disk-report', name: 'Disk report', category: 'system', description: 'Scan all volumes, identify large + stale files, output a structured cleanup report.', cmd: 'clawctl wf disk-report', hero: false, destructive: false, platforms: ['linux', 'macos'], last: { status: 'completed', t: '08:06', output: '82% used · 14 GB pruneable in ~/downloads/old' } },
  { id: 'clean-stale', name: 'Clean stale files', category: 'files', description: 'Delete files not accessed in 30+ days from specified directories. Requires approval.', cmd: 'clawctl wf clean-stale <dir>', hero: false, destructive: true, platforms: ['linux', 'macos'], last: { status: 'pending', t: 'now', output: null } },
  { id: 'proofread', name: 'Proofread', category: 'documents', description: 'Grammar, style, and tone check on any text file. Outputs annotated diff.', cmd: 'clawctl wf proofread <path>', hero: false, destructive: false, platforms: ['all'], last: null },
  { id: 'lead-research', name: 'Lead research', category: 'data', description: 'Given a company name, scrape public info, build a brief, save to memory.', cmd: 'clawctl wf lead-research <company>', hero: false, destructive: false, platforms: ['all'], last: null },
  { id: 'meeting-notes', name: 'Meeting notes', category: 'content', description: 'Transcribe audio, extract action items, send follow-up draft. Approval gate on sends.', cmd: 'clawctl wf meeting-notes <audio>', hero: false, destructive: false, platforms: ['all'], last: { status: 'completed', t: 'yesterday', output: 'Design review — 4 action items extracted' } },
  { id: 'backup-config', name: 'Backup config', category: 'system', description: 'Snapshot ~/.clawos to a timestamped tarball. Includes policy, memory, audit chain.', cmd: 'clawctl wf backup-config', hero: false, destructive: false, platforms: ['all'], last: { status: 'completed', t: '02:00', output: 'Backup: clawos-backup-20260423-0200.tar.gz (4.2 MB)' } },
  { id: 'csv-analyze', name: 'CSV analyze', category: 'data', description: 'Load a CSV, describe columns, compute stats, answer questions conversationally.', cmd: 'clawctl wf csv-analyze <path>', hero: false, destructive: false, platforms: ['all'], last: null },
  { id: 'invoice-gen', name: 'Invoice generator', category: 'data', description: 'Fill an invoice template from your contact + project data. Outputs PDF.', cmd: 'clawctl wf invoice <client>', hero: false, destructive: false, platforms: ['all'], last: null },
  { id: 'wiki-build', name: 'Build wiki', category: 'documents', description: 'Turn a folder of markdown notes into a structured wiki with backlinks.', cmd: 'clawctl wf wiki-build <dir>', hero: false, destructive: false, platforms: ['all'], last: null },
]

type RunState = { pct: number; status: 'running' | 'completed' | 'failed' }
type HistEntry = { id: string; name: string; status: string; ts: number }

export function Workflows() {
  const [wfs, setWfs] = useState<Wf[]>(STATIC_WFS)
  const [cat, setCat] = useState('all')
  const [selId, setSelId] = useState('organize-downloads')
  const [running, setRunning] = useState<Record<string, RunState>>({})
  const [history, setHistory] = useState<HistEntry[]>([])
  const [liveOutput, setLiveOutput] = useState<Record<string, string>>({})
  const [runError, setRunError] = useState('')

  useEffect(() => {
    commandCenterApi
      .listWorkflows({ category: cat === 'all' ? undefined : cat })
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          const staticById = Object.fromEntries(STATIC_WFS.map((w) => [w.id, w]))
          setWfs(
            data.map((w) => ({
              cmd: `clawctl wf ${w.id}`,
              hero: false,
              last: null,
              ...staticById[w.id],
              ...w,
            }))
          )
        }
      })
      .catch(() => {})
  }, [cat])

  useEffect(() => {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const socket = new WebSocket(`${proto}://${window.location.host}/ws`)
    socket.onmessage = ({ data }) => {
      try {
        const msg = JSON.parse(data)
        if (msg.type === 'workflow_progress' && msg.data) {
          const id = msg.data.id as string
          const pct = typeof msg.data.progress === 'number' ? msg.data.progress : 72
          const st: string = msg.data.status || 'running'
          if (st === 'ok' || st === 'completed') {
            setRunning((r) => ({ ...r, [id]: { pct: 100, status: 'completed' } }))
          } else if (st === 'failed') {
            setRunning((r) => ({ ...r, [id]: { pct: 100, status: 'failed' } }))
          } else {
            setRunning((r) => ({ ...r, [id]: { pct, status: 'running' } }))
          }
          if (msg.data.output) setLiveOutput((o) => ({ ...o, [id]: msg.data.output }))
        }
      } catch {}
    }
    return () => socket.close()
  }, [])

  const filtered = cat === 'all' ? wfs : wfs.filter((w) => w.category === cat)
  const selWf = wfs.find((w) => w.id === selId) ?? null

  async function runWf(wf: Wf) {
    setSelId(wf.id)
    setRunError('')
    setRunning((r) => ({ ...r, [wf.id]: { pct: 4, status: 'running' } }))

    const iv = setInterval(() => {
      setRunning((r) => {
        const cur = r[wf.id]
        if (!cur || cur.status !== 'running') { clearInterval(iv); return r }
        return { ...r, [wf.id]: { ...cur, pct: Math.min(88, cur.pct + 2 + Math.random() * 4) } }
      })
    }, 200)

    try {
      const result = await commandCenterApi.runWorkflow(wf.id, { args: {}, workspace: 'nexus_default' })
      clearInterval(iv)
      const st: RunState['status'] = result.status === 'failed' ? 'failed' : 'completed'
      setRunning((r) => ({ ...r, [wf.id]: { pct: 100, status: st } }))
      if (result.output) setLiveOutput((o) => ({ ...o, [wf.id]: result.output! }))
      setHistory((h) =>
        [{ id: wf.id, name: wf.name, status: result.status || 'ok', ts: Date.now() }, ...h].slice(0, 12)
      )
    } catch (err: any) {
      clearInterval(iv)
      setRunning((r) => ({ ...r, [wf.id]: { pct: 100, status: 'failed' } }))
      setRunError(err.message || 'Run failed')
    }
  }

  const run = selId ? running[selId] : undefined
  const selOut = selId ? liveOutput[selId] : undefined

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', height: '100%', overflow: 'hidden', flex: 1 }}>
      {/* Left — library */}
      <main className="main">
        <div className="main-head">
          <div>
            <h1>Workflows</h1>
            <div className="sub">one-command automations · run from dashboard, CLI, or voice</div>
          </div>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink-3)' }}>
            {filtered.length} workflows
          </span>
        </div>

        <div className="tabs">
          {[['all','ALL'],['files','FILES'],['documents','DOCS'],['developer','DEV'],['content','CONTENT'],['system','SYSTEM'],['data','DATA']].map(([k, l]) => (
            <button key={k} className={`tab${cat === k ? ' sel' : ''}`} onClick={() => setCat(k)}>{l}</button>
          ))}
        </div>

        <div className="wf-grid">
          {filtered.map((w) => {
            const r = running[w.id]
            const color = CATS[w.category] || 'var(--ink-3)'
            const icon = ICONS[w.category] || '◆'
            return (
              <div key={w.id} className={`wf${selId === w.id ? ' sel' : ''}`} onClick={() => setSelId(w.id)}>
                <div className="wf-bar" style={{ background: color }} />
                <div className="wf-top">
                  <div className="wf-icon" style={{ background: `${color}1a`, border: `1px solid ${color}33`, color }}>{icon}</div>
                  <div className="wf-name">{w.name}</div>
                  {w.destructive && <span className="tag tag-w">DESTR</span>}
                  {w.hero && <span className="tag tag-b">HERO</span>}
                  {w.last?.status === 'completed' && (
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--success)', boxShadow: '0 0 6px var(--success)', flexShrink: 0 }} />
                  )}
                  {w.last?.status === 'pending' && (
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--warn)', boxShadow: '0 0 6px var(--warn)', flexShrink: 0 }} />
                  )}
                </div>
                <div className="wf-desc">{w.description}</div>
                <div className="wf-meta">
                  <span className="m">{w.category}</span>
                  <span className="m">{w.platforms.join(', ')}</span>
                  {w.last && <span className="m">{w.last.t}</span>}
                </div>
                {r?.status === 'running' && (
                  <div className="wf-progress">
                    <div className="wf-progress-fill" style={{ width: `${r.pct}%`, background: color }} />
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </main>

      {/* Right — detail rail */}
      <aside className="rail">
        {!selWf ? (
          <div style={{ padding: '40px 22px', textAlign: 'center', color: 'var(--ink-3)', fontSize: 12.5, lineHeight: 1.6 }}>
            Select a workflow to see details, run history, and output.
          </div>
        ) : (
          <>
            <div className="r-head">
              <h2>{selWf.name}</h2>
              <div className="meta">
                <span>{selWf.category}</span>
                <span>{selWf.platforms.join(', ')}</span>
                {selWf.destructive && <span style={{ color: 'var(--warn)' }}>approval-sensitive</span>}
                {selWf.hero && <span style={{ color: 'var(--blue)' }}>hero workflow</span>}
              </div>
            </div>

            <div style={{ flex: 1, overflowY: 'auto' }}>
              <div className="r-sect">
                <h4>Description</h4>
                <div style={{ fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.6 }}>{selWf.description}</div>
              </div>

              <div className="r-sect">
                <h4>Command</h4>
                <div className="r-output">{selWf.cmd}</div>
              </div>

              {selWf.last && (
                <div className="r-sect">
                  <h4>Last run</h4>
                  <div className="r-row">
                    <span className="k">status</span>
                    <span className="v" style={{
                      color: selWf.last.status === 'completed' ? 'var(--success)'
                        : selWf.last.status === 'pending' ? 'var(--warn)'
                        : 'var(--ink-1)'
                    }}>
                      {selWf.last.status}
                    </span>
                  </div>
                  <div className="r-row"><span className="k">time</span><span className="v">{selWf.last.t}</span></div>
                  {selWf.last.output && (
                    <>
                      <h4 style={{ marginTop: 10 }}>Output</h4>
                      <div className="r-output">{selWf.last.output}</div>
                    </>
                  )}
                </div>
              )}

              {(selOut || runError || run) && (
                <div className="r-sect">
                  <h4>Live output</h4>
                  {run?.status === 'running' && (
                    <div className="wf-progress" style={{ marginBottom: 8 }}>
                      <div className="wf-progress-fill" style={{ width: `${run.pct}%`, background: CATS[selWf.category] || 'var(--accent)' }} />
                    </div>
                  )}
                  {selOut && <div className="r-output">{selOut}</div>}
                  {runError && (
                    <div className="r-output" style={{ color: 'var(--danger)', borderColor: 'oklch(70% 0.2 25 / 0.25)' }}>
                      {runError}
                    </div>
                  )}
                </div>
              )}

              {history.length > 0 && (
                <div className="r-sect">
                  <h4>Run history</h4>
                  {history.slice(0, 6).map((h) => (
                    <div key={`${h.id}-${h.ts}`} className="wf-hist">
                      <span className="dot" style={{
                        background: h.status === 'ok' || h.status === 'completed' ? 'var(--success)' : 'var(--danger)',
                        boxShadow: `0 0 4px ${h.status === 'ok' || h.status === 'completed' ? 'var(--success)' : 'var(--danger)'}`,
                      }} />
                      <span style={{ color: h.status === 'ok' || h.status === 'completed' ? 'var(--ink-2)' : 'var(--danger)' }}>
                        {h.name}
                      </span>
                      <span className="t">{new Date(h.ts).toLocaleTimeString()}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="r-btns">
              {run?.status === 'running' ? (
                <button className="btn-run" disabled>
                  <span style={{ animation: 'blink 1s ease-in-out infinite' }}>●</span>{' '}
                  Running… {Math.floor(run.pct)}%
                </button>
              ) : run?.status === 'completed' ? (
                <button className="btn-sec" style={{ flex: 1, color: 'var(--success)' }}>✓ Completed</button>
              ) : (
                <button className="btn-run" onClick={() => runWf(selWf)}>▸ Run {selWf.name}</button>
              )}
              <button className="btn-sec">Schedule</button>
            </div>
          </>
        )}
      </aside>
    </div>
  )
}
