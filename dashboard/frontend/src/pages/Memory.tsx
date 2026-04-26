/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { useEffect, useState } from 'react'
import { commandCenterApi } from '../lib/commandCenterApi'

const TIERS = [
  { name: 'Pinned', tier: 'Tier 1', count: 42, unit: 'lines', desc: 'Hand-curated facts and identity your agents always see.', color: 'var(--success)', pct: 80 },
  { name: 'Workflow', tier: 'Tier 2', count: 186, unit: 'lines', desc: 'Rolling working memory for the active session and jobs in flight.', color: 'var(--blue)', pct: 55 },
  { name: 'Vector (ChromaDB)', tier: 'Tier 3', count: 1847, unit: 'entries', desc: 'Semantic embeddings for recall by meaning, not keywords.', color: 'var(--violet)', pct: 70 },
  { name: 'Keyword (FTS5)', tier: 'Tier 4', count: 3421, unit: 'entries', desc: 'SQLite full-text index for fast literal lookups and filters.', color: 'var(--accent)', pct: 45 },
]

const BACKENDS = [
  { name: 'Archive', desc: 'Append-only SQLite archive of every memory write.' },
  { name: 'Knowledge Graph', desc: 'Temporal triples with edge timestamps (Kizuna).' },
  { name: 'Vector Memory', desc: 'Decay-weighted embedding store.' },
  { name: 'Intent Classifier', desc: 'Routes queries to the right memory tier.' },
  { name: 'Secret Filter', desc: 'Regex + entropy scrub before ingest.' },
  { name: 'Retention', desc: 'Ebbinghaus decay + reinforcement scheduling.' },
]

const AUXILIARY = [
  { name: 'RAG docs', desc: 'Per-workspace document chunks (via ragd).' },
  { name: 'Knowledge Brain', desc: 'Kizuna 3D knowledge graph (via braind).' },
  { name: 'Agent traces', desc: 'Executed tool calls + approvals (via policyd).' },
  { name: 'Skill learnings', desc: 'LEARNED.md self-improvement log (via ACE loop).' },
]

const STATIC_ENTRIES = [
  { kind: 'pinned', src: 'user', ts: '08:14', content: 'I prefer early morning briefings at 7am, not 8am.' },
  { kind: 'workflow', src: 'morning-briefing', ts: '08:09', content: "Today's briefing: 3 repos active, 2 calendar blocks, 14 GB disk cleanup pending." },
  { kind: 'vector', src: 'pdf-ingest', ts: '07:58', content: 'ReAct paper: synergizes reasoning + acting in LLMs. Key finding: interleaving trace and action improves task grounding by 34%.' },
  { kind: 'fts', src: 'kizuna-auto', ts: '07:42', content: 'Coltrane → modal jazz → Giant Steps changes → tritone substitution → Debussy whole-tone influence.' },
  { kind: 'pinned', src: 'user', ts: 'yesterday', content: 'My default repo is ~/code/clawos. Model preference: qwen2.5:7b.' },
  { kind: 'workflow', src: 'disk-report', ts: 'yesterday', content: '82% disk used. ~/downloads/old contains 14 GB of files not accessed in 38+ days.' },
]

const KIND_COLORS: Record<string, string> = {
  pinned: 'var(--success)', workflow: 'var(--blue)', vector: 'var(--violet)', fts: 'var(--accent)',
}

export function MemoryPage() {
  const [ws, setWs] = useState('default')
  const [tiers, setTiers] = useState(TIERS)
  const [entries, setEntries] = useState(STATIC_ENTRIES)

  useEffect(() => {
    commandCenterApi.getMemorySummary(ws)
      .then((data) => {
        if (!data) return
        const updated = TIERS.map((t) => {
          if (t.tier === 'Tier 1' && data.pinned_lines != null) return { ...t, count: data.pinned_lines }
          if (t.tier === 'Tier 2' && data.workflow_lines != null) return { ...t, count: data.workflow_lines }
          if (t.tier === 'Tier 3' && data.chroma_count != null) return { ...t, count: data.chroma_count }
          if (t.tier === 'Tier 4' && data.fts_count != null) return { ...t, count: data.fts_count }
          return t
        })
        setTiers(updated)
        if (Array.isArray(data.entries) && data.entries.length > 0) setEntries(data.entries)
      })
      .catch(() => {})
  }, [ws])

  const total = tiers.reduce((s, t) => s + t.count, 0)

  return (
    <main className="main" style={{ display: 'flex', flexDirection: 'column', gap: 16, overflow: 'hidden' }}>
      <div className="main-head">
        <div>
          <h1>Memory</h1>
          <div className="sub">14-layer persistent memory — so your JARVIS actually remembers</div>
        </div>
        <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink-3)', textAlign: 'right' }}>
          <div>{total.toLocaleString()} entries</div>
          <div>4 tiers · 6 backends</div>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 16, paddingBottom: 24 }}>
        {/* Workspace selector */}
        <div className="ws-sel">
          {['default', 'clawos-dev', 'personal'].map((w) => (
            <button key={w} className={`ws${ws === w ? ' sel' : ''}`} onClick={() => setWs(w)}>{w}</button>
          ))}
        </div>

        {/* Core tiers */}
        <div className="p">
          <h3><span className="ic">▦</span>Core memory tiers <span className="tag tag-g">memd · active</span></h3>
          <div className="tiers">
            {tiers.map((t) => (
              <div key={t.name} className="tier">
                <div className="t-accent" style={{ background: t.color }} />
                <div className="t-tier">{t.tier}</div>
                <div className="t-name">{t.name}</div>
                <div className="t-val">{t.count.toLocaleString()}<span className="u">{t.unit}</span></div>
                <div className="t-desc">{t.desc}</div>
                <div className="bar" style={{ marginTop: 10 }}><div className="f" style={{ width: `${t.pct}%`, background: t.color }} /></div>
              </div>
            ))}
          </div>
        </div>

        {/* Advanced backends */}
        <div className="p">
          <h3><span className="ic">◐</span>Advanced memory backends <span className="tag tag-b">taosmd · ready</span></h3>
          <div className="backends">
            {BACKENDS.map((b) => (
              <div key={b.name} className="bk">
                <div className="bk-name">{b.name}</div>
                <div className="bk-desc">{b.desc}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Auxiliary surfaces */}
        <div className="p">
          <h3><span className="ic">◇</span>Auxiliary memory surfaces <span className="tag tag-v">auxiliary</span></h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
            {AUXILIARY.map((a) => (
              <div key={a.name} className="bk">
                <div className="bk-name">{a.name}</div>
                <div className="bk-desc">{a.desc}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Recent entries */}
        <div className="p">
          <h3><span className="ic">⟳</span>Recent entries</h3>
          <div style={{ display: 'grid', gap: 8 }}>
            {entries.map((e, i) => {
              const color = KIND_COLORS[e.kind] || 'var(--ink-3)'
              return (
                <div key={i} className="mem-entry">
                  <div className="mem-entry-top">
                    <span className="kind" style={{ background: `${color}1a`, color, border: `1px solid ${color}33` }}>{e.kind}</span>
                    <span className="src">{e.src}</span>
                    <span className="ts">{e.ts}</span>
                  </div>
                  <div className="content">{e.content}</div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </main>
  )
}
