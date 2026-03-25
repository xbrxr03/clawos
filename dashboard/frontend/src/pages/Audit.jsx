import { useState, useEffect } from 'react'
import { Card, SectionLabel, Empty } from '../components/ui.jsx'
import { clsx } from 'clsx'
import { api } from '../lib/api.js'

export function Audit({ events }) {
  const [entries, setEntries] = useState([])
  const [live, setLive] = useState(true)
  const [expanded, setExpanded] = useState(null)

  useEffect(() => { api.audit(200).then(d => setEntries(d.entries ?? [])).catch(() => {}) }, [])

  useEffect(() => {
    if (!live) return
    const fresh = events.filter(e => e.type === 'audit_event').map(e => e.data)
    if (!fresh.length) return
    setEntries(prev => {
      const hashes = new Set(prev.map(e => e.entry_hash))
      return [...fresh.filter(e => !hashes.has(e.entry_hash)), ...prev]
    })
  }, [events, live])

  const decisionColor = (d) => {
    if (d === 'approved') return '#30d158'
    if (d === 'denied')   return '#ff453a'
    if (d === 'pending')  return '#ff9f0a'
    return 'rgba(255,255,255,0.3)'
  }

  const toolColor = (tool) => {
    if (!tool) return 'rgba(255,255,255,0.5)'
    if (tool.includes('shell') || tool.includes('exec')) return '#ff453a'
    if (tool.includes('file') || tool.includes('write')) return '#ff9f0a'
    if (tool.includes('web')  || tool.includes('http'))  return '#0a84ff'
    return '#30d158'
  }

  return (
    <div className="p-6 overflow-y-auto h-full fade-up">

      {/* Controls */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-lg font-semibold">Audit Log</div>
          <div className="text-sm mt-0.5" style={{ color: 'rgba(255,255,255,0.4)' }}>
            {entries.length} entries · Merkle-chained
          </div>
        </div>
        <button
          onClick={() => setLive(l => !l)}
          className="flex items-center gap-2 px-4 py-2 rounded-[10px] text-sm font-semibold transition-all"
          style={{
            background: live ? '#30d15820' : 'rgba(255,255,255,0.08)',
            color: live ? '#30d158' : 'rgba(255,255,255,0.4)',
          }}
        >
          <div className={clsx('w-2 h-2 rounded-full', live && 'pulse')}
            style={{ background: live ? '#30d158' : 'rgba(255,255,255,0.3)' }} />
          {live ? 'Live' : 'Paused'}
        </button>
      </div>

      {entries.length === 0 ? (
        <Card><Empty icon="📋" message="No audit entries yet" /></Card>
      ) : (
        <Card>
          <div className="divide-y" style={{ divideColor: 'rgba(255,255,255,0.06)' }}>
            {entries.map((entry, i) => {
              const hash = entry.entry_hash ?? i
              const isOpen = expanded === hash
              const decision = entry.decision ?? entry.action ?? entry.event

              return (
                <div
                  key={hash}
                  className="cursor-pointer"
                  style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}
                  onClick={() => setExpanded(isOpen ? null : hash)}
                >
                  <div className="flex items-center gap-3 px-4 py-3">
                    {/* Decision dot */}
                    <div className="w-2 h-2 rounded-full flex-shrink-0"
                      style={{ background: decisionColor(decision) }} />

                    {/* Tool */}
                    <span className="text-sm font-mono flex-1 truncate"
                      style={{ color: toolColor(entry.tool) }}>
                      {entry.tool ?? entry.type ?? '—'}
                    </span>

                    {/* Decision badge */}
                    <span
                      className="text-xs font-semibold px-2 py-0.5 rounded-full flex-shrink-0"
                      style={{
                        background: `${decisionColor(decision)}20`,
                        color: decisionColor(decision),
                      }}
                    >
                      {decision ?? 'event'}
                    </span>

                    {/* Hash */}
                    <span className="text-xs font-mono flex-shrink-0"
                      style={{ color: 'rgba(255,255,255,0.2)' }}>
                      {(entry.entry_hash ?? '').slice(0, 7)}
                    </span>

                    {/* Chevron */}
                    <svg width="7" height="11" viewBox="0 0 7 11" fill="none"
                      className={clsx('flex-shrink-0 transition-transform', isOpen && 'rotate-90')}>
                      <path d="M1 1l5 4.5L1 10" stroke="rgba(255,255,255,0.2)" strokeWidth="1.5"
                        strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </div>

                  {isOpen && (
                    <div className="px-4 pb-4 space-y-2" style={{ background: 'rgba(0,0,0,0.3)' }}>
                      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs font-mono">
                        {entry.task_id  && <Field k="task_id"  v={entry.task_id} />}
                        {entry.agent_id && <Field k="agent_id" v={entry.agent_id} />}
                        {entry.target   && <Field k="target"   v={entry.target} />}
                      </div>
                      {entry.prev_hash && (
                        <div className="text-xs font-mono" style={{ color: 'rgba(255,255,255,0.2)' }}>
                          ↑ {entry.prev_hash.slice(0, 40)}...
                        </div>
                      )}
                      <details>
                        <summary className="text-xs cursor-pointer" style={{ color: 'rgba(255,255,255,0.3)' }}>
                          raw JSON
                        </summary>
                        <pre className="mt-2 text-xs font-mono whitespace-pre-wrap break-all overflow-x-auto max-h-40"
                          style={{ color: 'rgba(255,255,255,0.5)' }}>
                          {JSON.stringify(entry, null, 2)}
                        </pre>
                      </details>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </Card>
      )}
    </div>
  )
}

function Field({ k, v }) {
  return (
    <div className="flex gap-2">
      <span style={{ color: 'rgba(255,255,255,0.3)' }}>{k}</span>
      <span className="truncate" style={{ color: 'rgba(255,255,255,0.6)' }}>{v}</span>
    </div>
  )
}
