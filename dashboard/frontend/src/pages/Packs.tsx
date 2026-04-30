/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { useState } from 'react'

type Framework = {
  id: string
  name: string
  by: string
  color: string
  letter: string
  desc: string
  tags: string[]
  stars: string
  license: string
  size: string
  status: 'running' | 'installed' | 'available'
  cat: 'built-in' | 'ecosystem'
}

const FRAMEWORKS: Framework[] = [
  { id: 'nexus', name: 'Nexus', by: 'clawOS', color: 'var(--accent)', letter: 'N', desc: 'Native Ollama function-calling agent. Always-on, CPU-capable, 7-layer persistent memory, skill loader, A2A federation.', tags: ['built-in', 'offline', 'native-tools', 'memory'], stars: '—', license: 'AGPL-3.0', size: '12 MB', status: 'running', cat: 'built-in' },
  { id: 'picoclaw', name: 'PicoClaw', by: 'Sipeed', color: 'var(--warn)', letter: 'P', desc: 'Lightweight runtime from Sipeed. Auto-activated on ARM hardware — zero configuration, zero cost agentic tasks.', tags: ['arm', 'lightweight', 'edge'], stars: '1.2k', license: 'MIT', size: '4 MB', status: 'running', cat: 'built-in' },
  { id: 'nullclaw', name: 'NullClaw', by: 'clawOS', color: 'var(--ink-2)', letter: 'Ø', desc: 'Stateless, ephemeral, pure function execution. No memory, no state — just input → output. Perfect for one-shot tasks.', tags: ['stateless', 'ephemeral', 'fast'], stars: '—', license: 'AGPL-3.0', size: '2 MB', status: 'installed', cat: 'built-in' },
  { id: 'zeroclaw', name: 'ZeroClaw', by: 'clawOS', color: 'oklch(80% 0.15 30)', letter: 'Z', desc: 'Rust implementation, ultra-lightweight. Sub-millisecond cold start, minimal memory footprint.', tags: ['rust', 'fast', 'minimal'], stars: '—', license: 'AGPL-3.0', size: '8 MB', status: 'available', cat: 'built-in' },
  { id: 'openclaw', name: 'OpenClaw', by: 'openclaw.ai', color: 'var(--violet)', letter: 'O', desc: 'Full agent ecosystem with skills library, MCP support, and multi-channel routing.', tags: ['skills', 'multi-channel', 'mcp'], stars: '8.4k', license: 'MIT', size: '180 MB', status: 'installed', cat: 'ecosystem' },
  { id: 'smolagents', name: 'SmolAgents', by: 'HuggingFace', color: 'oklch(75% 0.2 50)', letter: 'S', desc: 'Code-based agent with 30% fewer LLM calls. Executes Python directly instead of JSON tool calls.', tags: ['code-agent', 'efficient', 'huggingface'], stars: '14k', license: 'Apache-2.0', size: '45 MB', status: 'available', cat: 'ecosystem' },
  { id: 'agentzero', name: 'AgentZero', by: 'frdel', color: 'oklch(70% 0.2 15)', letter: 'A0', desc: 'Self-correcting agent with tool creation and computer use. Creates its own tools at runtime when needed.', tags: ['self-correcting', 'tool-creation', 'computer-use'], stars: '6.2k', license: 'MIT', size: '62 MB', status: 'available', cat: 'ecosystem' },
  { id: 'pocketflow', name: 'PocketFlow', by: 'pocketflow', color: 'oklch(78% 0.14 185)', letter: 'PF', desc: '100-line LLM framework with zero dependencies and MCP support. The smallest serious agent framework.', tags: ['minimal', 'zero-deps', 'mcp'], stars: '3.1k', license: 'MIT', size: '0.3 MB', status: 'available', cat: 'ecosystem' },
  { id: 'langroid', name: 'Langroid', by: 'langroid', color: 'oklch(72% 0.18 150)', letter: 'L', desc: 'Multi-agent message-passing framework with built-in local LLM support. Agents as first-class citizens.', tags: ['multi-agent', 'message-passing', 'local-llm'], stars: '4.5k', license: 'MIT', size: '38 MB', status: 'available', cat: 'ecosystem' },
  { id: 'openai-agents', name: 'OpenAI Agents SDK', by: 'OpenAI', color: 'oklch(76% 0.16 210)', letter: 'OA', desc: 'Provider-agnostic SDK supporting 100+ LLMs. Handoffs, guardrails, and tracing built in.', tags: ['provider-agnostic', 'guardrails', 'tracing'], stars: '18k', license: 'MIT', size: '22 MB', status: 'available', cat: 'ecosystem' },
]

const TABS: [string, string][] = [
  ['all', 'ALL'],
  ['running', 'RUNNING'],
  ['installed', 'INSTALLED'],
  ['built-in', 'BUILT-IN'],
  ['ecosystem', 'ECOSYSTEM'],
]

function tabCount(key: string) {
  if (key === 'all') return FRAMEWORKS.length
  if (key === 'running') return FRAMEWORKS.filter((f) => f.status === 'running').length
  if (key === 'installed') return FRAMEWORKS.filter((f) => f.status !== 'available').length
  if (key === 'built-in') return FRAMEWORKS.filter((f) => f.cat === 'built-in').length
  return FRAMEWORKS.filter((f) => f.cat === 'ecosystem').length
}

export function PacksPage() {
  const [filter, setFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [installing, setInstalling] = useState<string | null>(null)
  const [installed, setInstalled] = useState<Set<string>>(new Set())

  const filtered = FRAMEWORKS.filter((f) => {
    if (filter === 'running' && f.status !== 'running') return false
    if (filter === 'installed' && f.status === 'available' && !installed.has(f.id)) return false
    if (filter === 'built-in' && f.cat !== 'built-in') return false
    if (filter === 'ecosystem' && f.cat !== 'ecosystem') return false
    if (search) {
      const q = search.toLowerCase()
      if (!f.name.toLowerCase().includes(q) && !f.desc.toLowerCase().includes(q) && !f.tags.some((t) => t.includes(q))) return false
    }
    return true
  })

  function install(id: string) {
    setInstalling(id)
    setTimeout(() => {
      setInstalled((s) => new Set([...s, id]))
      setInstalling(null)
    }, 1800)
  }

  const running = FRAMEWORKS.filter((f) => f.status === 'running').length
  const totalInstalled = FRAMEWORKS.filter((f) => f.status !== 'available').length + installed.size

  return (
    <main className="main" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div style={{ flexShrink: 0 }}>
        <div className="main-head">
          <div>
            <h1>Framework Store</h1>
            <div className="sub">install any agent framework — one shared Ollama backend, any framework on top</div>
          </div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink-3)', textAlign: 'right' }}>
            <div>{running} running</div>
            <div>{totalInstalled} installed · {FRAMEWORKS.length} total</div>
          </div>
        </div>

        <div className="search">
          <span className="sym">⌕</span>
          <input
            placeholder="Search frameworks…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <div className="tabs">
          {TABS.map(([k, l]) => (
            <button key={k} className={`tab${filter === k ? ' sel' : ''}`} onClick={() => setFilter(k)}>
              {l} · {tabCount(k)}
            </button>
          ))}
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', paddingBottom: 24 }}>
        {filtered.length === 0 ? (
          <div className="empty" style={{ minHeight: 160 }}>
            <div className="empty-title">No frameworks match</div>
            <div className="empty-body">Try a different filter or clear your search.</div>
          </div>
        ) : (
          <div className="fw-grid">
            {filtered.map((f) => {
              const isInstalled = f.status !== 'available' || installed.has(f.id)
              const isRunning = f.status === 'running'
              return (
                <div key={f.id} className="fw">
                  <div className="bar" style={{ background: f.color }} />
                  <div className="fw-body">
                    <div className="fw-top">
                      <div
                        className="fw-icon"
                        style={{ background: `${f.color}22`, border: `1px solid ${f.color}44`, color: f.color }}
                      >
                        {f.letter}
                      </div>
                      <div className="fw-info">
                        <div className="fw-name">{f.name}</div>
                        <div className="fw-by">{f.by} · {f.license}</div>
                      </div>
                      <span
                        className="status-dot"
                        style={{
                          background: isRunning ? 'var(--success)' : isInstalled ? 'var(--blue)' : 'var(--ink-4)',
                          boxShadow: isRunning ? '0 0 8px var(--success)' : isInstalled ? '0 0 6px var(--blue)' : 'none',
                        }}
                      />
                    </div>

                    <div className="fw-desc">{f.desc}</div>

                    <div className="fw-tags">
                      {f.tags.map((t) => <span key={t} className="fw-tag">{t}</span>)}
                    </div>

                    <div className="fw-stats">
                      {f.stars !== '—' && <span className="s">★ {f.stars}</span>}
                      <span className="s">↓ {f.size}</span>
                      <span
                        className="s"
                        style={{ color: isRunning ? 'var(--success)' : isInstalled ? 'var(--blue)' : 'var(--ink-4)' }}
                      >
                        {isRunning ? 'running' : isInstalled ? 'installed' : 'available'}
                      </span>
                    </div>

                    <div className="fw-foot">
                      {isRunning ? (
                        <button className="btn-running">● Running</button>
                      ) : isInstalled ? (
                        <button className="btn-installed">✓ Installed</button>
                      ) : (
                        <button
                          className="btn-run"
                          style={{ flex: 'none', padding: '8px 14px', fontSize: 12 }}
                          disabled={installing === f.id}
                          onClick={() => install(f.id)}
                        >
                          {installing === f.id ? '⤓ Installing…' : `⤓ Install ${f.name}`}
                        </button>
                      )}
                      <button className="btn-sec" style={{ marginLeft: 'auto', fontSize: 11 }}>Docs →</button>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </main>
  )
}
