import { useState, useEffect } from 'react'
import { Card, Empty, Badge, Button } from '../components/ui.jsx'
import { Database, FileText, RefreshCw } from 'lucide-react'
import { api } from '../lib/api.js'

export function Memory() {
  const [stats, setStats] = useState(null)
  const [workspaces, setWorkspaces] = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(true)

  async function load() {
    setLoading(true)
    try {
      const [s, w] = await Promise.all([api.memory(), api.workspaces()])
      setStats(s)
      setWorkspaces(w)
      if (w.length > 0 && !selected) setSelected(w[0].name)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const ws = workspaces.find(w => w.name === selected)

  return (
    <div className="p-6 space-y-4 fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-claw-text">Memory</h1>
          <p className="text-sm text-claw-dim mt-0.5">4-layer memory system status</p>
        </div>
        <Button variant="ghost" onClick={load} disabled={loading}>
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
          Refresh
        </Button>
      </div>

      {/* Layer stats */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: 'PINNED.md',    value: stats?.pinned_lines,   unit: 'lines', color: 'text-claw-accent', desc: 'Layer 1 · always injected' },
          { label: 'WORKFLOW.md',  value: stats?.workflow_lines,  unit: 'lines', color: 'text-claw-info',   desc: 'Layer 2 · task state'      },
          { label: 'ChromaDB',     value: stats?.chroma_size_mb,  unit: 'MB',    color: 'text-purple-400',  desc: 'Layer 3 · vector search'   },
          { label: 'SQLite FTS5',  value: stats?.sqlite_size_mb,  unit: 'MB',    color: 'text-claw-warn',   desc: 'Layer 4 · keyword search'  },
        ].map(({ label, value, unit, color, desc }) => (
          <Card key={label} className="p-4">
            <div className={`text-xl font-mono font-semibold ${color}`}>
              {value !== undefined && value !== null ? value : '—'}
              <span className="text-xs ml-1 text-claw-dim font-normal">{unit}</span>
            </div>
            <div className="text-xs font-mono text-claw-text mt-1">{label}</div>
            <div className="text-xs text-claw-dim mt-0.5">{desc}</div>
          </Card>
        ))}
      </div>

      {/* HISTORY lines */}
      {stats?.history_lines !== undefined && (
        <Card className="p-4 flex items-center gap-4">
          <FileText size={16} className="text-claw-dim flex-shrink-0" />
          <div>
            <span className="text-sm font-mono text-claw-text">HISTORY.md</span>
            <span className="text-xs text-claw-dim ml-2">{stats.history_lines} lines · timestamped interaction log</span>
          </div>
        </Card>
      )}

      {/* Workspaces */}
      <div className="grid grid-cols-3 gap-4">
        {/* Workspace list */}
        <Card className="col-span-1">
          <div className="px-4 py-3 border-b border-claw-border flex items-center gap-2">
            <Database size={14} className="text-claw-accent" />
            <span className="text-sm font-medium">Workspaces</span>
            <span className="text-xs font-mono text-claw-dim bg-claw-muted px-1.5 rounded ml-auto">
              {workspaces.length}
            </span>
          </div>
          {workspaces.length === 0 ? (
            <Empty icon={Database} message="No workspaces found" />
          ) : (
            <div className="divide-y divide-claw-border">
              {workspaces.map(w => (
                <button
                  key={w.name}
                  onClick={() => setSelected(w.name)}
                  className={`w-full text-left px-4 py-3 hover:bg-claw-muted/30 transition-colors ${
                    selected === w.name ? 'bg-claw-accent/5 border-l-2 border-claw-accent' : ''
                  }`}
                >
                  <div className="text-sm font-mono text-claw-text truncate">{w.name}</div>
                  <div className="flex items-center gap-2 mt-1">
                    {w.has_pinned   && <Badge variant="accent">PINNED</Badge>}
                    {w.has_workflow && <Badge variant="info">WORKFLOW</Badge>}
                  </div>
                </button>
              ))}
            </div>
          )}
        </Card>

        {/* Workspace detail */}
        <Card className="col-span-2">
          {!ws ? (
            <Empty icon={FileText} message="Select a workspace" />
          ) : (
            <div>
              <div className="px-4 py-3 border-b border-claw-border">
                <span className="text-sm font-medium font-mono">{ws.name}</span>
                <div className="text-xs text-claw-dim mt-0.5">{ws.path}</div>
              </div>

              {ws.pinned_preview ? (
                <div className="p-4 border-b border-claw-border">
                  <div className="text-xs text-claw-dim mb-2 font-mono">PINNED.md preview</div>
                  <pre className="text-xs font-mono text-claw-text bg-claw-bg rounded p-3 border border-claw-border whitespace-pre-wrap max-h-32 overflow-y-auto">
                    {ws.pinned_preview}
                  </pre>
                </div>
              ) : (
                <div className="px-4 py-3 border-b border-claw-border text-xs text-claw-dim">
                  No PINNED.md in this workspace
                </div>
              )}

              {ws.workflow_preview ? (
                <div className="p-4">
                  <div className="text-xs text-claw-dim mb-2 font-mono">WORKFLOW.md preview</div>
                  <pre className="text-xs font-mono text-claw-text bg-claw-bg rounded p-3 border border-claw-border whitespace-pre-wrap max-h-32 overflow-y-auto">
                    {ws.workflow_preview}
                  </pre>
                </div>
              ) : (
                <div className="px-4 py-3 text-xs text-claw-dim">No active workflow</div>
              )}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
