import { FormEvent, useEffect, useRef, useState } from 'react'
import { Badge, Card, Empty, SectionLabel } from '../components/ui.jsx'
import { commandCenterApi, type WorkbenchPage, type WorkbenchSession } from '../lib/commandCenterApi'

type Mode = 'fetch' | 'research'

const STATUS_COLORS: Record<string, string> = {
  submitted: 'blue',
  analyzing: 'orange',
  done: 'green',
  error: 'red',
}

export function WorkbenchPage() {
  const [url, setUrl] = useState('')
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState<Mode>('fetch')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const [page, setPage] = useState<WorkbenchPage | null>(null)
  const [sessions, setSessions] = useState<WorkbenchSession[]>([])
  const [activeSession, setActiveSession] = useState<WorkbenchSession | null>(null)

  const urlRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    commandCenterApi.listWorkbenchSessions()
      .then((data) => setSessions(Array.isArray(data) ? data : []))
      .catch(() => {})
  }, [])

  const handleFetch = async (event: FormEvent) => {
    event.preventDefault()
    const target = url.trim()
    if (!target) return
    setBusy(true)
    setError('')
    setPage(null)
    try {
      const result = await commandCenterApi.workbenchFetch(target)
      setPage(result)
    } catch (err: any) {
      setError(err.message || 'Fetch failed')
    } finally {
      setBusy(false)
    }
  }

  const handleResearch = async (event: FormEvent) => {
    event.preventDefault()
    const q = query.trim() || url.trim()
    if (!q) return
    setBusy(true)
    setError('')
    try {
      const result = await commandCenterApi.workbenchResearch(query.trim(), url.trim())
      if (result.session) {
        setSessions((prev) => [result.session!, ...prev.slice(0, 49)])
        setActiveSession(result.session)
        if (result.session.page) setPage(result.session.page)
      }
    } catch (err: any) {
      setError(err.message || 'Research failed')
    } finally {
      setBusy(false)
    }
  }

  const handleSubmit = mode === 'fetch' ? handleFetch : handleResearch

  return (
    <div className="fade-up" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Top bar */}
      <div style={{ padding: '20px 24px 14px', borderBottom: '1px solid var(--sep)' }}>
        <div style={{ fontSize: 28, fontWeight: 700, letterSpacing: '-0.05em' }}>Workbench</div>
        <div style={{ fontSize: 14, color: 'var(--text-3)', marginTop: 4 }}>
          Fetch pages, run research, and send content to your local agent.
        </div>

        {/* Mode toggle + URL bar */}
        <form onSubmit={handleSubmit} style={{ marginTop: 14, display: 'flex', gap: 8, alignItems: 'stretch' }}>
          <div
            style={{
              display: 'flex',
              borderRadius: 12,
              border: '1px solid var(--border)',
              overflow: 'hidden',
              flexShrink: 0,
            }}
          >
            {(['fetch', 'research'] as Mode[]).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setMode(m)}
                style={{
                  padding: '8px 16px',
                  border: 'none',
                  borderRadius: 0,
                  cursor: 'pointer',
                  fontSize: 13,
                  fontWeight: 500,
                  background: mode === m ? 'rgba(77,143,247,0.18)' : 'transparent',
                  color: mode === m ? 'var(--blue)' : 'var(--text-2)',
                }}
              >
                {m.charAt(0).toUpperCase() + m.slice(1)}
              </button>
            ))}
          </div>

          <input
            ref={urlRef}
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com"
            style={{
              flex: 1,
              padding: '8px 14px',
              borderRadius: 12,
              border: '1px solid var(--border)',
              background: 'var(--surface-2)',
              color: 'var(--text)',
              fontSize: 13,
              fontFamily: 'var(--font-mono)',
            }}
          />

          {mode === 'research' && (
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Research query (optional)"
              style={{
                flex: 1.2,
                padding: '8px 14px',
                borderRadius: 12,
                border: '1px solid var(--border)',
                background: 'var(--surface-2)',
                color: 'var(--text)',
                fontSize: 13,
              }}
            />
          )}

          <button className="btn primary" type="submit" disabled={busy}>
            {busy ? 'Working…' : mode === 'fetch' ? 'Fetch' : 'Research'}
          </button>
        </form>

        {error && (
          <div style={{ marginTop: 10, fontSize: 13, color: 'var(--red)' }}>{error}</div>
        )}
      </div>

      {/* Main split */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1.1fr 0.9fr', gap: 14, padding: 14, minHeight: 0, overflow: 'hidden' }}>
        {/* Page content panel */}
        <Card style={{ padding: 18, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {page ? (
            <>
              <div style={{ marginBottom: 10 }}>
                <div style={{ fontSize: 16, fontWeight: 600, lineHeight: 1.3 }}>{page.title}</div>
                <div style={{ marginTop: 6, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <Badge color="blue">{page.word_count.toLocaleString()} words</Badge>
                  <Badge color="gray">{page.links.length} links</Badge>
                  <a
                    href={page.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mono"
                    style={{ fontSize: 11, color: 'var(--blue)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 260 }}
                  >
                    {page.url}
                  </a>
                </div>
              </div>

              <div style={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div>
                  <SectionLabel>Extracted text</SectionLabel>
                  <pre
                    style={{
                      margin: 0,
                      fontFamily: 'inherit',
                      fontSize: 13,
                      color: 'var(--text-2)',
                      whiteSpace: 'pre-wrap',
                      lineHeight: 1.6,
                      maxHeight: 320,
                      overflow: 'auto',
                      padding: '10px 12px',
                      borderRadius: 10,
                      background: 'var(--surface)',
                      border: '1px solid var(--border)',
                    }}
                  >
                    {page.text}
                  </pre>
                </div>

                {page.links.length > 0 && (
                  <div>
                    <SectionLabel>Links found</SectionLabel>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      {page.links.map((link) => (
                        <a
                          key={link}
                          href={link}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="mono"
                          style={{ fontSize: 11, color: 'var(--blue)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                        >
                          {link}
                        </a>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </>
          ) : (
            <Empty>Fetch a URL to see the extracted content here.</Empty>
          )}
        </Card>

        {/* AI / research panel */}
        <Card style={{ padding: 18, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Agent Research</div>

          {activeSession ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, flex: 1, overflow: 'auto' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                <div style={{ fontSize: 14, fontWeight: 500 }}>{activeSession.query}</div>
                <Badge color={STATUS_COLORS[activeSession.status] || 'gray'}>{activeSession.status}</Badge>
              </div>

              {activeSession.task_id && (
                <div className="glass" style={{ padding: 12 }}>
                  <SectionLabel>Task ID</SectionLabel>
                  <div className="mono" style={{ fontSize: 11, marginTop: 4 }}>{activeSession.task_id}</div>
                  <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-3)' }}>
                    Agent is processing. Check the Tasks page to track progress and view the result.
                  </div>
                </div>
              )}

              {activeSession.url && (
                <div>
                  <SectionLabel>Source</SectionLabel>
                  <a
                    href={activeSession.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mono"
                    style={{ fontSize: 11, color: 'var(--blue)', wordBreak: 'break-all' }}
                  >
                    {activeSession.url}
                  </a>
                </div>
              )}

              {activeSession.page && (
                <div>
                  <SectionLabel>Page context sent</SectionLabel>
                  <div style={{ fontSize: 13, color: 'var(--text-2)' }}>
                    {activeSession.page.word_count.toLocaleString()} words from "{activeSession.page.title}"
                  </div>
                </div>
              )}
            </div>
          ) : (
            <Empty>Switch to Research mode and submit a URL or query to run an agent analysis.</Empty>
          )}
        </Card>
      </div>

      {/* Session history */}
      {sessions.length > 0 && (
        <div style={{ padding: '0 14px 14px' }}>
          <Card style={{ padding: 14 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <SectionLabel>Recent sessions</SectionLabel>
              <Badge color="gray">{sessions.length}</Badge>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {sessions.map((session) => (
                <button
                  key={session.id}
                  type="button"
                  onClick={() => {
                    setActiveSession(session)
                    if (session.page) setPage(session.page)
                    if (session.url) setUrl(session.url)
                    setMode('research')
                  }}
                  style={{
                    padding: '6px 12px',
                    borderRadius: 10,
                    border: `1px solid ${activeSession?.id === session.id ? 'rgba(77,143,247,0.4)' : 'var(--border)'}`,
                    background: activeSession?.id === session.id ? 'rgba(77,143,247,0.1)' : 'var(--surface)',
                    color: 'var(--text-2)',
                    cursor: 'pointer',
                    fontSize: 12,
                    maxWidth: 220,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                  }}
                >
                  <span
                    className={`dot ${STATUS_COLORS[session.status] === 'green' ? 'green' : STATUS_COLORS[session.status] === 'orange' ? 'orange' : 'gray'}`}
                    style={{ width: 6, height: 6, flexShrink: 0 }}
                  />
                  {session.query}
                </button>
              ))}
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}
