import { useState, useEffect } from 'react'
import { Card, Row, SectionLabel, Empty, Badge } from '../components/ui.jsx'
import { api } from '../lib/api.js'

const LAYERS = [
  { key: 'pinned_lines',   label: 'PINNED.md',   unit: 'lines', color: '#30d158', desc: 'Always injected · Layer 1' },
  { key: 'workflow_lines', label: 'WORKFLOW.md',  unit: 'lines', color: '#0a84ff', desc: 'Task state · Layer 2'      },
  { key: 'chroma_size_mb', label: 'ChromaDB',     unit: 'MB',    color: '#bf5af2', desc: 'Vector search · Layer 3'  },
  { key: 'sqlite_size_mb', label: 'SQLite FTS5',  unit: 'MB',    color: '#ff9f0a', desc: 'Keyword search · Layer 4' },
]

export function Memory() {
  const [stats, setStats] = useState(null)
  const [workspaces, setWorkspaces] = useState([])
  const [selected, setSelected] = useState(null)

  useEffect(() => {
    Promise.all([api.memory(), api.workspaces()]).then(([s, w]) => {
      setStats(s)
      setWorkspaces(w)
      if (w.length > 0) setSelected(w[0].name)
    }).catch(console.error)
  }, [])

  const ws = workspaces.find(w => w.name === selected)

  return (
    <div className="p-6 overflow-y-auto h-full fade-up space-y-1">

      {/* Layer cards */}
      <SectionLabel>Memory Layers</SectionLabel>
      <div className="grid grid-cols-2 gap-2">
        {LAYERS.map(({ key, label, unit, color, desc }) => (
          <div key={key} className="ios-card p-4">
            <div className="text-2xl font-bold tabular" style={{ color }}>
              {stats?.[key] ?? '—'}
              <span className="text-sm font-normal ml-1" style={{ color: 'rgba(255,255,255,0.3)' }}>
                {unit}
              </span>
            </div>
            <div className="text-sm font-medium mt-1">{label}</div>
            <div className="text-xs mt-0.5" style={{ color: 'rgba(255,255,255,0.3)' }}>{desc}</div>
          </div>
        ))}
      </div>

      {/* History */}
      {stats?.history_lines !== undefined && (
        <>
          <SectionLabel>History</SectionLabel>
          <Card>
            <Row
              left={<span style={{ fontSize: 20 }}>📜</span>}
              center={
                <div>
                  <div className="text-sm font-medium">HISTORY.md</div>
                  <div className="text-xs mt-0.5" style={{ color: 'rgba(255,255,255,0.3)' }}>
                    Timestamped interaction log
                  </div>
                </div>
              }
              right={
                <span className="text-sm tabular" style={{ color: 'rgba(255,255,255,0.4)' }}>
                  {stats.history_lines} lines
                </span>
              }
            />
          </Card>
        </>
      )}

      {/* Workspaces */}
      <SectionLabel>Workspaces — {workspaces.length}</SectionLabel>
      {workspaces.length === 0 ? (
        <Card><Empty icon="📁" message="No workspaces found" /></Card>
      ) : (
        <Card>
          {workspaces.map(w => (
            <Row
              key={w.name}
              left={
                <div
                  className="w-8 h-8 rounded-[8px] flex items-center justify-center text-sm"
                  style={{ background: selected === w.name ? '#0a84ff22' : 'rgba(255,255,255,0.06)' }}
                >
                  📂
                </div>
              }
              center={
                <div>
                  <div className="text-sm font-medium">{w.name}</div>
                  <div className="flex items-center gap-1.5 mt-1">
                    {w.has_pinned   && <Badge color="#30d158">PINNED</Badge>}
                    {w.has_workflow && <Badge color="#0a84ff">WORKFLOW</Badge>}
                  </div>
                </div>
              }
              onClick={() => setSelected(w.name)}
              chevron
            />
          ))}
        </Card>
      )}

      {/* Selected workspace preview */}
      {ws && (
        <>
          <SectionLabel>{ws.name}</SectionLabel>
          {ws.pinned_preview && (
            <Card>
              <div className="px-4 pt-3 pb-1 text-xs font-semibold uppercase tracking-wider"
                style={{ color: 'rgba(255,255,255,0.3)' }}>PINNED.md</div>
              <div className="px-4 pb-4">
                <pre className="text-xs font-mono whitespace-pre-wrap max-h-28 overflow-y-auto"
                  style={{ color: 'rgba(255,255,255,0.6)' }}>
                  {ws.pinned_preview}
                </pre>
              </div>
            </Card>
          )}
          {ws.workflow_preview && (
            <Card>
              <div className="px-4 pt-3 pb-1 text-xs font-semibold uppercase tracking-wider"
                style={{ color: 'rgba(255,255,255,0.3)' }}>WORKFLOW.md</div>
              <div className="px-4 pb-4">
                <pre className="text-xs font-mono whitespace-pre-wrap max-h-28 overflow-y-auto"
                  style={{ color: 'rgba(255,255,255,0.6)' }}>
                  {ws.workflow_preview}
                </pre>
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  )
}
