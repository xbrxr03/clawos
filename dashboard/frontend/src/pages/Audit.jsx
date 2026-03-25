import { useState, useEffect, useRef } from 'react'
import { Card, Empty, Badge, Button, Timestamp } from '../components/ui.jsx'
import { BookOpen, RefreshCw, ChevronDown, ChevronRight, Link } from 'lucide-react'
import { api } from '../lib/api.js'
import { clsx } from 'clsx'

export function Audit({ events }) {
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState({})
  const [liveMode, setLiveMode] = useState(true)
  const bottomRef = useRef(null)

  async function load() {
    setLoading(true)
    try {
      const data = await api.audit(200)
      setEntries(data.entries ?? [])
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  // In live mode, prepend new audit events from WS
  useEffect(() => {
    if (!liveMode) return
    const auditEvents = events.filter(e => e.type === 'audit_event')
    if (auditEvents.length === 0) return
    setEntries(prev => {
      const existingHashes = new Set(prev.map(e => e.entry_hash))
      const newOnes = auditEvents.map(e => e.data).filter(e => !existingHashes.has(e.entry_hash))
      return [...newOnes, ...prev]
    })
  }, [events, liveMode])

  function toggle(hash) {
    setExpanded(e => ({ ...e, [hash]: !e[hash] }))
  }

  const toolColor = (tool) => {
    if (!tool) return 'text-claw-dim'
    if (tool.includes('shell') || tool.includes('exec')) return 'text-red-400'
    if (tool.includes('file') || tool.includes('write')) return 'text-amber-400'
    if (tool.includes('web') || tool.includes('http')) return 'text-blue-400'
    return 'text-claw-accent'
  }

  return (
    <div className="p-6 space-y-4 fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-claw-text">Audit Log</h1>
          <p className="text-sm text-claw-dim mt-0.5">Merkle-chained tamper-evident event journal</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setLiveMode(l => !l)}
            className={clsx(
              'text-xs px-3 py-1.5 rounded border transition-colors',
              liveMode
                ? 'bg-claw-accent/10 border-claw-accent/30 text-claw-accent'
                : 'bg-claw-muted border-claw-border text-claw-dim hover:text-claw-text'
            )}
          >
            {liveMode ? '⬤ Live' : '○ Live'}
          </button>
          <Button variant="ghost" onClick={load} disabled={loading}>
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
            Reload
          </Button>
        </div>
      </div>

      <Card>
        <div className="px-4 py-3 border-b border-claw-border flex items-center gap-4">
          <BookOpen size={14} className="text-claw-accent" />
          <span className="text-sm font-medium">{entries.length} entries</span>
          <span className="text-xs text-claw-dim">Most recent first</span>
        </div>

        {entries.length === 0 ? (
          <Empty icon={BookOpen} message="No audit entries yet" />
        ) : (
          <div className="divide-y divide-claw-border font-mono text-xs max-h-[calc(100vh-280px)] overflow-y-auto">
            {entries.map((entry, i) => {
              const hash = entry.entry_hash ?? i
              const isOpen = expanded[hash]
              const decision = entry.decision ?? entry.action ?? entry.event

              return (
                <div
                  key={hash}
                  className="hover:bg-claw-muted/20 cursor-pointer"
                  onClick={() => toggle(hash)}
                >
                  <div className="flex items-center gap-3 px-4 py-2.5">
                    {/* Expand chevron */}
                    {isOpen
                      ? <ChevronDown size={12} className="text-claw-dim flex-shrink-0" />
                      : <ChevronRight size={12} className="text-claw-dim flex-shrink-0" />
                    }

                    {/* Decision badge */}
                    <Badge variant={
                      decision === 'approved' ? 'accent' :
                      decision === 'denied'   ? 'danger' :
                      decision === 'pending'  ? 'warn'   : 'default'
                    }>
                      {decision ?? 'event'}
                    </Badge>

                    {/* Tool */}
                    <span className={clsx('flex-1 truncate', toolColor(entry.tool))}>
                      {entry.tool ?? entry.type ?? '—'}
                    </span>

                    {/* Agent */}
                    {entry.agent_id && (
                      <span className="text-claw-dim truncate max-w-24">{entry.agent_id}</span>
                    )}

                    {/* Hash fragment */}
                    <span className="text-claw-muted w-16 text-right truncate">
                      {(entry.entry_hash ?? '').slice(0, 8)}
                    </span>

                    {/* Timestamp */}
                    <Timestamp value={entry.timestamp} />
                  </div>

                  {/* Expanded detail */}
                  {isOpen && (
                    <div className="px-4 pb-3 pt-1 bg-claw-bg/50">
                      <div className="grid grid-cols-2 gap-x-6 gap-y-1 mb-2">
                        {entry.task_id  && <Field label="task_id"   value={entry.task_id} />}
                        {entry.agent_id && <Field label="agent_id"  value={entry.agent_id} />}
                        {entry.tool     && <Field label="tool"      value={entry.tool} />}
                        {entry.target   && <Field label="target"    value={entry.target} />}
                      </div>

                      {/* Merkle chain */}
                      <div className="mt-2 space-y-0.5">
                        {entry.prev_hash && (
                          <div className="flex items-center gap-2 text-claw-muted">
                            <Link size={10} />
                            <span>prev: {entry.prev_hash.slice(0, 32)}...</span>
                          </div>
                        )}
                        {entry.entry_hash && (
                          <div className="flex items-center gap-2 text-claw-dim">
                            <Link size={10} />
                            <span>hash: {entry.entry_hash.slice(0, 32)}...</span>
                          </div>
                        )}
                      </div>

                      {/* Full JSON */}
                      <details className="mt-2">
                        <summary className="text-claw-muted cursor-pointer hover:text-claw-dim">
                          raw entry
                        </summary>
                        <pre className="mt-1 text-claw-dim bg-claw-bg rounded p-2 border border-claw-border overflow-x-auto whitespace-pre-wrap break-all">
                          {JSON.stringify(entry, null, 2)}
                        </pre>
                      </details>
                    </div>
                  )}
                </div>
              )
            })}
            <div ref={bottomRef} />
          </div>
        )}
      </Card>
    </div>
  )
}

function Field({ label, value }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="text-claw-dim w-20 flex-shrink-0">{label}</span>
      <span className="text-claw-text truncate">{value}</span>
    </div>
  )
}
