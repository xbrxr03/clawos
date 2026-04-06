import { FormEvent, useEffect, useState } from 'react'
import { Badge, Card, Empty, SectionLabel } from '../components/ui.jsx'
import { commandCenterApi, type Citation, type ResearchSession } from '../lib/commandCenterApi'

const STATUS_COLORS: Record<string, string> = {
  running: 'orange',
  paused: 'blue',
  done: 'green',
  error: 'red',
}

const RELEVANCE_COLORS: Record<string, string> = {
  primary: 'green',
  supporting: 'blue',
  tangential: 'gray',
}

const PROVIDER_LABELS: Record<string, string> = {
  brave: 'Brave Search',
  tavily: 'Tavily',
  fetch: 'Direct Fetch',
  none: 'No Search',
}

function CitationCard({ citation }: { citation: Citation }) {
  return (
    <div
      className="glass"
      style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 6 }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'flex-start' }}>
        <div style={{ fontSize: 13, fontWeight: 600, flex: 1 }}>{citation.title}</div>
        <Badge color={RELEVANCE_COLORS[citation.relevance] || 'gray'}>{citation.relevance}</Badge>
      </div>
      <blockquote
        style={{
          margin: 0,
          padding: '6px 10px',
          borderLeft: '2px solid var(--border)',
          color: 'var(--text-2)',
          fontSize: 12,
          lineHeight: 1.6,
          fontStyle: 'italic',
        }}
      >
        {citation.excerpt}
      </blockquote>
      <a
        href={citation.url}
        target="_blank"
        rel="noopener noreferrer"
        className="mono"
        style={{ fontSize: 11, color: 'var(--blue)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
      >
        {citation.url}
      </a>
    </div>
  )
}

function SessionRow({
  session,
  active,
  onClick,
  onResume,
  onPause,
  onDelete,
}: {
  session: ResearchSession
  active: boolean
  onClick: () => void
  onResume: () => void
  onPause: () => void
  onDelete: () => void
}) {
  return (
    <div
      className="glass"
      style={{
        padding: 12,
        cursor: 'pointer',
        borderColor: active ? 'rgba(77,143,247,0.35)' : undefined,
        background: active ? 'rgba(77,143,247,0.06)' : undefined,
      }}
      onClick={onClick}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'flex-start' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {session.query}
          </div>
          <div style={{ marginTop: 4, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <Badge color={STATUS_COLORS[session.status] || 'gray'}>{session.status}</Badge>
            <Badge color="gray">{PROVIDER_LABELS[session.provider] || session.provider}</Badge>
            {(session.source_count ?? session.sources?.length ?? 0) > 0 && (
              <Badge color="blue">{session.source_count ?? session.sources?.length} sources</Badge>
            )}
            {(session.citation_count ?? session.citations?.length ?? 0) > 0 && (
              <Badge color="green">{session.citation_count ?? session.citations?.length} citations</Badge>
            )}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, flexShrink: 0 }} onClick={(e) => e.stopPropagation()}>
          {session.status === 'paused' && (
            <button className="btn sm" onClick={onResume}>Resume</button>
          )}
          {session.status === 'running' && (
            <button className="btn sm" onClick={onPause}>Pause</button>
          )}
          <button className="btn sm" onClick={onDelete} style={{ color: 'var(--red)' }}>Delete</button>
        </div>
      </div>
    </div>
  )
}

export function ResearchPage() {
  const [query, setQuery] = useState('')
  const [seedUrls, setSeedUrls] = useState('')
  const [provider, setProvider] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [showConfig, setShowConfig] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const [sessions, setSessions] = useState<ResearchSession[]>([])
  const [activeSession, setActiveSession] = useState<ResearchSession | null>(null)

  const loadSessions = async () => {
    try {
      const data = await commandCenterApi.listResearchSessions()
      setSessions(Array.isArray(data) ? data : [])
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    loadSessions()
  }, [])

  const openSession = async (id: string) => {
    try {
      const full = await commandCenterApi.getResearchSession(id)
      setActiveSession(full)
    } catch {
      // use summary from list
      const summary = sessions.find((s) => s.id === id)
      if (summary) setActiveSession(summary)
    }
  }

  const handleStart = async (event: FormEvent) => {
    event.preventDefault()
    if (!query.trim() && !seedUrls.trim()) return
    setBusy(true)
    setError('')
    try {
      const urls = seedUrls.split('\n').map((u) => u.trim()).filter(Boolean)
      const session = await commandCenterApi.startResearch({
        query: query.trim(),
        seed_urls: urls.length ? urls : undefined,
        provider: provider || undefined,
        api_key: apiKey || undefined,
      })
      setSessions((prev) => [session, ...prev])
      setActiveSession(session)
      setQuery('')
      setSeedUrls('')
    } catch (err: any) {
      setError(err.message || 'Research failed')
    } finally {
      setBusy(false)
    }
  }

  const handleResume = async (id: string) => {
    try {
      const updated = await commandCenterApi.resumeResearchSession(id)
      setSessions((prev) => prev.map((s) => (s.id === id ? updated : s)))
      setActiveSession(updated)
    } catch (err: any) {
      setError(err.message || 'Resume failed')
    }
  }

  const handlePause = async (id: string) => {
    try {
      await commandCenterApi.pauseResearchSession(id)
      await loadSessions()
      if (activeSession?.id === id) {
        const updated = sessions.find((s) => s.id === id)
        if (updated) setActiveSession({ ...updated, status: 'paused' })
      }
    } catch (err: any) {
      setError(err.message || 'Pause failed')
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await commandCenterApi.deleteResearchSession(id)
      setSessions((prev) => prev.filter((s) => s.id !== id))
      if (activeSession?.id === id) setActiveSession(null)
    } catch (err: any) {
      setError(err.message || 'Delete failed')
    }
  }

  const citations = activeSession?.citations ?? []
  const sources = activeSession?.sources ?? []

  return (
    <div className="fade-up" style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* Left: session list + start form */}
      <div
        style={{
          width: 280,
          flexShrink: 0,
          borderRight: '1px solid var(--sep)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        <div style={{ padding: '20px 16px 12px', borderBottom: '1px solid var(--sep)' }}>
          <div style={{ fontSize: 20, fontWeight: 700, letterSpacing: '-0.04em' }}>Research</div>
          <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 4 }}>
            Multi-source research with citations and resumable runs.
          </div>
        </div>

        {/* Start form */}
        <form onSubmit={handleStart} style={{ padding: 12, borderBottom: '1px solid var(--sep)', display: 'flex', flexDirection: 'column', gap: 8 }}>
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Research query…"
            rows={2}
            style={{
              padding: '8px 10px',
              borderRadius: 10,
              border: '1px solid var(--border)',
              background: 'var(--surface-2)',
              color: 'var(--text)',
              fontSize: 13,
              resize: 'none',
              fontFamily: 'inherit',
            }}
          />
          <textarea
            value={seedUrls}
            onChange={(e) => setSeedUrls(e.target.value)}
            placeholder="Seed URLs (one per line, optional)"
            rows={2}
            style={{
              padding: '8px 10px',
              borderRadius: 10,
              border: '1px solid var(--border)',
              background: 'var(--surface-2)',
              color: 'var(--text)',
              fontSize: 12,
              resize: 'none',
              fontFamily: 'var(--font-mono)',
            }}
          />

          <button
            type="button"
            onClick={() => setShowConfig((v) => !v)}
            style={{ background: 'none', border: 'none', color: 'var(--blue)', fontSize: 11, cursor: 'pointer', textAlign: 'left', padding: 0 }}
          >
            {showConfig ? '▾' : '▸'} Search provider (optional)
          </button>

          {showConfig && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                style={{ padding: '6px 8px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text)', fontSize: 12 }}
              >
                <option value="">Auto-detect</option>
                <option value="brave">Brave Search</option>
                <option value="tavily">Tavily</option>
                <option value="fetch">Direct fetch only</option>
              </select>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="API key (if required)"
                style={{ padding: '6px 8px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text)', fontSize: 12 }}
              />
            </div>
          )}

          <button className="btn primary" type="submit" disabled={busy}>
            {busy ? 'Researching…' : 'Start Research'}
          </button>
          {error && <div style={{ fontSize: 11, color: 'var(--red)' }}>{error}</div>}
        </form>

        {/* Session list */}
        <div style={{ flex: 1, overflow: 'auto', padding: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
          {sessions.length === 0 ? (
            <div style={{ padding: 16, color: 'var(--text-3)', fontSize: 12 }}>No sessions yet.</div>
          ) : (
            sessions.map((s) => (
              <SessionRow
                key={s.id}
                session={s}
                active={activeSession?.id === s.id}
                onClick={() => openSession(s.id)}
                onResume={() => handleResume(s.id)}
                onPause={() => handlePause(s.id)}
                onDelete={() => handleDelete(s.id)}
              />
            ))
          )}
        </div>
      </div>

      {/* Right: active session detail */}
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {activeSession ? (
          <>
            {/* Session header */}
            <div style={{ padding: '18px 20px 14px', borderBottom: '1px solid var(--sep)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                <div style={{ fontSize: 18, fontWeight: 700, flex: 1 }}>{activeSession.query}</div>
                <Badge color={STATUS_COLORS[activeSession.status] || 'gray'}>{activeSession.status}</Badge>
                <Badge color="gray">{PROVIDER_LABELS[activeSession.provider] || activeSession.provider}</Badge>
              </div>
              {activeSession.task_id && (
                <div className="mono" style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 6 }}>
                  Task: {activeSession.task_id} — check Tasks page for agent output
                </div>
              )}
            </div>

            <div style={{ flex: 1, overflow: 'auto', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, padding: 14, alignContent: 'start' }}>
              {/* Citations */}
              <div>
                <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 10 }}>
                  Citations
                  {citations.length > 0 && <span style={{ marginLeft: 8, color: 'var(--text-3)', fontSize: 12, fontWeight: 400 }}>{citations.length} found</span>}
                </div>
                {citations.length === 0 ? (
                  <Card style={{ padding: 14 }}>
                    <Empty>No citations extracted yet.</Empty>
                  </Card>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {citations.map((c) => <CitationCard key={c.url} citation={c} />)}
                  </div>
                )}
              </div>

              {/* Sources */}
              <div>
                <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 10 }}>
                  Sources
                  {sources.length > 0 && <span style={{ marginLeft: 8, color: 'var(--text-3)', fontSize: 12, fontWeight: 400 }}>{sources.length} fetched</span>}
                </div>
                {sources.length === 0 ? (
                  <Card style={{ padding: 14 }}>
                    <Empty>No sources fetched yet.</Empty>
                  </Card>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {sources.map((src) => (
                      <div key={src.url} className="glass" style={{ padding: 12 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                          <div style={{ fontSize: 13, fontWeight: 500, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {src.title || src.url}
                          </div>
                          <Badge color={src.fetched ? 'green' : src.error ? 'red' : 'gray'}>
                            {src.fetched ? 'fetched' : src.error ? 'error' : 'pending'}
                          </Badge>
                        </div>
                        {src.snippet && (
                          <div style={{ marginTop: 6, fontSize: 12, color: 'var(--text-2)', lineHeight: 1.5 }}>
                            {src.snippet}
                          </div>
                        )}
                        {src.error && (
                          <div style={{ marginTop: 4, fontSize: 11, color: 'var(--red)' }}>{src.error}</div>
                        )}
                        <a
                          href={src.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="mono"
                          style={{ display: 'block', marginTop: 6, fontSize: 11, color: 'var(--blue)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                        >
                          {src.url}
                        </a>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </>
        ) : (
          <div style={{ flex: 1, display: 'grid', placeItems: 'center' }}>
            <Empty>Start a research session or select one from the list.</Empty>
          </div>
        )}
      </div>
    </div>
  )
}
