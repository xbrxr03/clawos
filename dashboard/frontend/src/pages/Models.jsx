import { useState } from 'react'
import { Card, Empty, Badge, Button, StatusDot } from '../components/ui.jsx'
import { Cpu, Trash2, Download, RefreshCw } from 'lucide-react'
import { api } from '../lib/api.js'

const SUGGESTED = [
  { name: 'qwen2.5:7b',        size: '4.7GB', note: 'Default — best balance' },
  { name: 'qwen2.5-coder:7b',  size: '4.7GB', note: 'Better tool calling'    },
  { name: 'gemma3:4b',         size: '2.5GB', note: 'Low RAM option'         },
  { name: 'llama3.1:8b',       size: '4.9GB', note: 'General purpose'        },
]

export function Models({ models, pullProgress }) {
  const [pullInput, setPullInput] = useState('')
  const [deleting, setDeleting] = useState(null)

  async function pull(name) {
    const target = name || pullInput.trim()
    if (!target) return
    try { await api.pullModel(target) } catch (e) { console.error(e) }
    setPullInput('')
  }

  async function del(name) {
    setDeleting(name)
    try { await api.deleteModel(name) } catch (e) { console.error(e) }
    setDeleting(null)
  }

  const installed = models.models ?? []
  const installedNames = new Set(installed.map(m => m.name))

  return (
    <div className="p-6 space-y-4 fade-in">
      <div>
        <h1 className="text-lg font-semibold text-claw-text">Models</h1>
        <p className="text-sm text-claw-dim mt-0.5">Manage Ollama models and hardware profiles</p>
      </div>

      {/* Pull custom model */}
      <Card className="p-4">
        <div className="text-xs text-claw-dim mb-2">Pull a model</div>
        <div className="flex gap-2">
          <input
            value={pullInput}
            onChange={e => setPullInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && pull()}
            placeholder="e.g. qwen2.5:14b"
            className="flex-1 bg-claw-bg border border-claw-border rounded px-3 py-1.5 text-sm font-mono text-claw-text placeholder-claw-dim focus:outline-none focus:border-claw-accent"
          />
          <Button variant="accent" onClick={() => pull()}>
            <Download size={12} /> Pull
          </Button>
        </div>
      </Card>

      {/* Installed models */}
      <Card>
        <div className="px-4 py-3 border-b border-claw-border flex items-center gap-2">
          <Cpu size={14} className="text-claw-accent" />
          <span className="text-sm font-medium">Installed</span>
          <span className="text-xs font-mono text-claw-dim bg-claw-muted px-1.5 rounded">{installed.length}</span>
        </div>

        {installed.length === 0 ? (
          <Empty icon={Cpu} message="No models found — is Ollama running?" />
        ) : (
          <div className="divide-y divide-claw-border">
            {installed.map(m => {
              const progress = pullProgress[m.name]
              return (
                <div key={m.name} className="px-4 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <StatusDot status={m.running ? 'active' : 'completed'} />
                      <span className="text-sm font-mono text-claw-text truncate">{m.name}</span>
                      {m.name === models.default && <Badge variant="accent">default</Badge>}
                      {m.running && <Badge variant="accent">running</Badge>}
                    </div>
                    <div className="flex items-center gap-3 flex-shrink-0">
                      <span className="text-xs font-mono text-claw-dim">{m.size_gb} GB</span>
                      <Button
                        variant="ghost"
                        onClick={() => del(m.name)}
                        disabled={deleting === m.name || m.name === models.default}
                      >
                        <Trash2 size={12} className="text-red-400" />
                      </Button>
                    </div>
                  </div>
                  {progress && (
                    <PullProgress progress={progress} />
                  )}
                </div>
              )
            })}
          </div>
        )}
      </Card>

      {/* Suggested models */}
      <Card>
        <div className="px-4 py-3 border-b border-claw-border">
          <span className="text-sm font-medium">Suggested for GTX 1060 (6GB VRAM)</span>
        </div>
        <div className="divide-y divide-claw-border">
          {SUGGESTED.map(m => {
            const isInstalled = installedNames.has(m.name)
            const isPulling = !!pullProgress[m.name]
            return (
              <div key={m.name} className="flex items-center justify-between px-4 py-3 gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-mono text-claw-text">{m.name}</span>
                    {isInstalled && <Badge variant="accent">installed</Badge>}
                  </div>
                  <div className="text-xs text-claw-dim mt-0.5">{m.note} · {m.size}</div>
                </div>
                {!isInstalled && (
                  <Button
                    variant="default"
                    onClick={() => pull(m.name)}
                    disabled={isPulling}
                  >
                    {isPulling ? <RefreshCw size={12} className="animate-spin" /> : <Download size={12} />}
                    {isPulling ? 'Pulling...' : 'Pull'}
                  </Button>
                )}
              </div>
            )
          })}
        </div>
      </Card>
    </div>
  )
}

function PullProgress({ progress }) {
  const pct = progress.total > 0 ? Math.round((progress.completed / progress.total) * 100) : 0
  return (
    <div className="mt-2 space-y-1">
      <div className="flex justify-between text-xs font-mono text-claw-dim">
        <span>{progress.status ?? 'downloading'}</span>
        <span>{pct}%</span>
      </div>
      <div className="h-1 bg-claw-muted rounded-full overflow-hidden">
        <div
          className="h-full bg-claw-accent rounded-full transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}
