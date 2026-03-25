import { useState } from 'react'
import { Card, Row, Dot, Badge, Empty, SectionLabel, ProgressBar } from '../components/ui.jsx'
import { api } from '../lib/api.js'

const SUGGESTED = [
  { name: 'qwen2.5:7b',       size: '4.7GB', note: 'Default · best balance'   },
  { name: 'qwen2.5-coder:7b', size: '4.7GB', note: 'Better tool calling'      },
  { name: 'gemma3:4b',        size: '2.5GB', note: 'Low RAM'                  },
  { name: 'llama3.1:8b',      size: '4.9GB', note: 'General purpose'          },
]

export function Models({ models, pullProgress }) {
  const [input, setInput] = useState('')
  const [deleting, setDeleting] = useState(null)

  async function pull(name) {
    const t = name || input.trim()
    if (!t) return
    try { await api.pullModel(t) } catch {}
    setInput('')
  }

  async function del(name) {
    setDeleting(name)
    try { await api.deleteModel(name) } catch {}
    setDeleting(null)
  }

  const installed = models.models ?? []
  const installedNames = new Set(installed.map(m => m.name))

  return (
    <div className="p-6 overflow-y-auto h-full fade-up space-y-1">

      {/* Pull input */}
      <SectionLabel>Pull Model</SectionLabel>
      <Card>
        <div className="p-3 flex gap-2">
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && pull()}
            placeholder="qwen2.5:14b"
            className="flex-1 rounded-[8px] px-3 py-2 text-sm font-mono outline-none"
            style={{
              background: 'rgba(255,255,255,0.06)',
              color: '#fff',
              border: '1px solid rgba(255,255,255,0.08)',
            }}
          />
          <button
            onClick={() => pull()}
            className="px-4 py-2 rounded-[8px] text-sm font-semibold"
            style={{ background: '#0a84ff', color: '#fff' }}
          >
            Pull
          </button>
        </div>
      </Card>

      {/* Installed */}
      <SectionLabel>Installed — {installed.length}</SectionLabel>
      <Card>
        {installed.length === 0 ? (
          <Empty icon="💾" message="No models — is Ollama running?" />
        ) : installed.map(m => {
          const progress = pullProgress[m.name]
          return (
            <div key={m.name}>
              <Row
                left={<Dot status={m.running ? 'active' : 'completed'} />}
                center={
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium">{m.name}</span>
                    {m.name === models.default && <Badge color="#0a84ff">default</Badge>}
                    {m.running && <Badge color="#30d158">running</Badge>}
                  </div>
                }
                right={
                  <div className="flex items-center gap-3">
                    <span className="text-sm tabular" style={{ color: 'rgba(255,255,255,0.4)' }}>
                      {m.size_gb} GB
                    </span>
                    {m.name !== models.default && (
                      <button
                        onClick={() => del(m.name)}
                        disabled={deleting === m.name}
                        className="text-xs px-2 py-1 rounded-[6px] disabled:opacity-40"
                        style={{ background: '#ff453a18', color: '#ff453a' }}
                      >
                        {deleting === m.name ? '...' : 'Delete'}
                      </button>
                    )}
                  </div>
                }
              />
              {progress && (
                <div className="px-4 pb-3 space-y-1">
                  <div className="flex justify-between text-xs" style={{ color: 'rgba(255,255,255,0.4)' }}>
                    <span>{progress.status ?? 'downloading'}</span>
                    <span className="tabular">
                      {progress.total > 0 ? Math.round((progress.completed / progress.total) * 100) : 0}%
                    </span>
                  </div>
                  <ProgressBar
                    value={progress.total > 0 ? (progress.completed / progress.total) * 100 : 0}
                    color="#0a84ff"
                  />
                </div>
              )}
            </div>
          )
        })}
      </Card>

      {/* Suggested */}
      <SectionLabel>Suggested for GTX 1060 (6 GB)</SectionLabel>
      <Card>
        {SUGGESTED.map(m => {
          const isInstalled = installedNames.has(m.name)
          const isPulling = !!pullProgress[m.name]
          return (
            <Row
              key={m.name}
              left={
                <div className="w-8 h-8 rounded-[8px] flex items-center justify-center text-sm"
                  style={{ background: 'rgba(255,255,255,0.06)' }}>
                  🧠
                </div>
              }
              center={
                <div>
                  <div className="text-sm font-medium">{m.name}</div>
                  <div className="text-xs mt-0.5" style={{ color: 'rgba(255,255,255,0.3)' }}>
                    {m.note} · {m.size}
                  </div>
                </div>
              }
              right={
                isInstalled ? (
                  <Badge color="#30d158">installed</Badge>
                ) : (
                  <button
                    onClick={() => pull(m.name)}
                    disabled={isPulling}
                    className="text-xs px-3 py-1.5 rounded-[8px] font-semibold disabled:opacity-40"
                    style={{ background: '#0a84ff18', color: '#0a84ff' }}
                  >
                    {isPulling ? 'Pulling...' : '↓ Pull'}
                  </button>
                )
              }
            />
          )
        })}
      </Card>
    </div>
  )
}
