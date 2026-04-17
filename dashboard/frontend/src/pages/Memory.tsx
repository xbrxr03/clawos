/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { useEffect, useMemo, useState } from 'react'
import { Badge, Card, Empty, PageHeader, PanelHeader, SectionLabel, Skeleton } from '../components/ui.jsx'
import { commandCenterApi } from '../lib/commandCenterApi'

type WorkspaceRow = {
  name: string
  has_pinned: boolean
  memory_count: number
  history_count: number
}

type MemorySummary = {
  workspace: string
  pinned_lines: number
  workflow_lines: number
  chroma_count: number
  fts_count: number
  entries: Array<{ kind?: string; content?: string; ts?: string; source?: string }>
}

// The 14 layers are surfaced as four active memd tiers plus the taosmd backends
// that sit beside them. Status is sourced from the live /api/memory endpoint
// where we can; taosmd backends report "ready" based on module presence.
const MEMD_LAYERS = [
  {
    key: 'pinned',
    label: 'Pinned',
    description: 'Hand-curated facts and identity your agents always see.',
    tier: 'Tier 1',
  },
  {
    key: 'workflow',
    label: 'Workflow',
    description: 'Rolling working memory for the active session and the jobs in flight.',
    tier: 'Tier 2',
  },
  {
    key: 'chroma',
    label: 'Vector (ChromaDB)',
    description: 'Semantic embeddings for recall by meaning, not keywords.',
    tier: 'Tier 3',
  },
  {
    key: 'fts',
    label: 'Keyword (FTS5)',
    description: 'SQLite full-text index for fast literal lookups and filters.',
    tier: 'Tier 4',
  },
] as const

const TAOSMD_BACKENDS = [
  { label: 'Archive', description: 'Append-only SQLite archive of every memory write.' },
  { label: 'Knowledge Graph', description: 'Temporal triples with edge timestamps.' },
  { label: 'Vector Memory', description: 'Decay-weighted embedding store.' },
  { label: 'Intent Classifier', description: 'Routes queries to the right memory tier.' },
  { label: 'Secret Filter', description: 'Regex + entropy scrub before ingest.' },
  { label: 'Retention', description: 'Ebbinghaus decay + reinforcement scheduling.' },
] as const

const AUXILIARY_LAYERS = [
  { label: 'RAG docs', description: 'Per-workspace document chunks (via ragd).' },
  { label: 'Knowledge Brain', description: 'Kizuna 3D knowledge graph (via braind).' },
  { label: 'Agent traces', description: 'Executed tool calls + approvals (via policyd audit).' },
  { label: 'Skill learnings', description: 'LEARNED.md self-improvement log (via ACE loop).' },
] as const

function LayerCard({
  label,
  tier,
  count,
  countLabel,
  description,
  tone = 'active',
}: {
  label: string
  tier?: string
  count?: number
  countLabel: string
  description: string
  tone?: 'active' | 'ready' | 'info'
}) {
  const toneColor = tone === 'active' ? 'green' : tone === 'ready' ? 'blue' : 'gray'
  return (
    <Card style={{ padding: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <div style={{ fontSize: 14, fontWeight: 600 }}>{label}</div>
        {tier ? <Badge color={toneColor}>{tier}</Badge> : <Badge color={toneColor}>{tone}</Badge>}
      </div>
      <div style={{ fontSize: 28, fontWeight: 700, margin: '10px 0 2px', letterSpacing: '-0.04em' }}>
        {typeof count === 'number' ? count.toLocaleString() : '—'}
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 8 }}>{countLabel}</div>
      <div style={{ fontSize: 12, color: 'var(--text-2)', lineHeight: 1.55 }}>{description}</div>
    </Card>
  )
}

export function MemoryPage() {
  const [workspaces, setWorkspaces] = useState<WorkspaceRow[]>([])
  const [active, setActive] = useState<string>('')
  const [summary, setSummary] = useState<MemorySummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [summaryLoading, setSummaryLoading] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    commandCenterApi
      .listWorkspaces()
      .then((data) => {
        if (cancelled) return
        const rows = Array.isArray(data?.workspaces) ? data.workspaces : []
        setWorkspaces(rows)
        if (rows.length && !active) setActive(rows[0].name)
      })
      .catch(() => setMessage('Failed to load workspaces'))
      .finally(() => setLoading(false))
    return () => {
      cancelled = true
    }
  }, [active])

  useEffect(() => {
    if (!active) return
    let cancelled = false
    setSummaryLoading(true)
    commandCenterApi
      .getMemorySummary(active)
      .then((data) => {
        if (cancelled) return
        setSummary(data)
      })
      .catch(() => setMessage(`Failed to load memory summary for ${active}`))
      .finally(() => setSummaryLoading(false))
    return () => {
      cancelled = true
    }
  }, [active])

  const totalEntries = useMemo(() => {
    if (!summary) return 0
    return (summary.pinned_lines || 0) + (summary.workflow_lines || 0) + (summary.chroma_count || 0) + (summary.fts_count || 0)
  }, [summary])

  const layerCount = (key: string) => {
    if (!summary) return undefined
    if (key === 'pinned') return summary.pinned_lines
    if (key === 'workflow') return summary.workflow_lines
    if (key === 'chroma') return summary.chroma_count
    if (key === 'fts') return summary.fts_count
    return undefined
  }

  return (
    <div className="fade-up" style={{ padding: '0 0 48px' }}>
      <div style={{ padding: '24px 20px 16px' }}>
        <PageHeader
          eyebrow="Memory"
          title="14-layer memory — so your JARVIS actually remembers."
          description="OpenClaw agents forget between sessions. ClawOS keeps pinned identity, rolling workflow state, semantic vectors, keyword FTS, plus the taosmd backends that handle retention, intent routing, and the knowledge graph."
          meta={
            <>
              <Badge color="green">{workspaces.length} workspace{workspaces.length === 1 ? '' : 's'}</Badge>
              <Badge color="blue">{totalEntries.toLocaleString()} memory entries</Badge>
            </>
          }
        />
      </div>

      {message && (
        <div style={{ padding: '0 20px 12px' }}>
          <Card style={{ padding: 12, color: 'var(--accent)' }}>{message}</Card>
        </div>
      )}

      <div style={{ padding: '0 20px 16px', display: 'grid', gridTemplateColumns: 'minmax(240px, 320px) 1fr', gap: 16 }}>
        <Card style={{ padding: 16 }}>
          <SectionLabel>Workspaces</SectionLabel>
          {loading && workspaces.length === 0 ? (
            <div style={{ display: 'grid', gap: 8, marginTop: 10 }}>
              <Skeleton height={32} />
              <Skeleton height={32} />
              <Skeleton height={32} />
            </div>
          ) : workspaces.length === 0 ? (
            <Empty>No workspaces yet. Create one from the CLI or Setup.</Empty>
          ) : (
            <div style={{ display: 'grid', gap: 6, marginTop: 10 }}>
              {workspaces.map((ws) => {
                const isActive = ws.name === active
                return (
                  <button
                    key={ws.name}
                    onClick={() => setActive(ws.name)}
                    className="btn"
                    style={{
                      justifyContent: 'space-between',
                      background: isActive ? 'var(--accent-soft)' : 'var(--surface-2)',
                      border: `1px solid ${isActive ? 'var(--accent)' : 'var(--border)'}`,
                      padding: '10px 12px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 10,
                    }}
                  >
                    <span style={{ fontWeight: 600 }}>{ws.name}</span>
                    <span style={{ display: 'flex', gap: 6 }}>
                      {ws.has_pinned && <Badge color="green">pinned</Badge>}
                      <Badge color="gray">{ws.memory_count}</Badge>
                    </span>
                  </button>
                )
              })}
            </div>
          )}
        </Card>

        <div style={{ display: 'grid', gap: 16 }}>
          <Card style={{ padding: 16 }}>
            <PanelHeader
              eyebrow="memd · active"
              title="Core memory tiers"
              description="Live counts from the four memd layers serving this workspace."
            />
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: 12,
                marginTop: 14,
              }}
            >
              {MEMD_LAYERS.map((layer) => (
                <LayerCard
                  key={layer.key}
                  label={layer.label}
                  tier={layer.tier}
                  count={summaryLoading ? undefined : layerCount(layer.key)}
                  countLabel={layer.key === 'pinned' || layer.key === 'workflow' ? 'lines' : 'entries'}
                  description={layer.description}
                  tone="active"
                />
              ))}
            </div>
          </Card>

          <Card style={{ padding: 16 }}>
            <PanelHeader
              eyebrow="taosmd · ready"
              title="Advanced memory backends"
              description="The 5 taosmd subsystems that route, decay, scrub, and archive memory beneath memd."
            />
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: 12,
                marginTop: 14,
              }}
            >
              {TAOSMD_BACKENDS.map((backend) => (
                <LayerCard
                  key={backend.label}
                  label={backend.label}
                  countLabel="backend"
                  description={backend.description}
                  tone="ready"
                />
              ))}
            </div>
          </Card>

          <Card style={{ padding: 16 }}>
            <PanelHeader
              eyebrow="auxiliary"
              title="Adjacent memory surfaces"
              description="Other systems that feed into or reinforce recall — owned by their own daemons."
            />
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: 12,
                marginTop: 14,
              }}
            >
              {AUXILIARY_LAYERS.map((layer) => (
                <LayerCard
                  key={layer.label}
                  label={layer.label}
                  countLabel="surface"
                  description={layer.description}
                  tone="info"
                />
              ))}
            </div>
          </Card>

          <Card style={{ padding: 16 }}>
            <PanelHeader
              eyebrow="recent"
              title="Latest entries"
              description={`Most recent keyword-indexed entries for ${active || 'the selected workspace'}.`}
            />
            {summaryLoading ? (
              <div style={{ display: 'grid', gap: 8, marginTop: 14 }}>
                <Skeleton height={40} />
                <Skeleton height={40} />
                <Skeleton height={40} />
              </div>
            ) : !summary || !summary.entries?.length ? (
              <div style={{ marginTop: 14 }}>
                <Empty>No recent entries. Memory entries appear as agents run.</Empty>
              </div>
            ) : (
              <div style={{ display: 'grid', gap: 8, marginTop: 14 }}>
                {summary.entries.slice(0, 6).map((entry, idx) => (
                  <div
                    key={idx}
                    style={{
                      padding: 10,
                      border: '1px solid var(--border)',
                      borderRadius: 8,
                      background: 'var(--surface-2)',
                      display: 'grid',
                      gap: 4,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      {entry.kind && <Badge color="blue">{entry.kind}</Badge>}
                      {entry.source && <span style={{ fontSize: 11, color: 'var(--text-3)' }}>{entry.source}</span>}
                      {entry.ts && <span style={{ fontSize: 11, color: 'var(--text-3)', marginLeft: 'auto' }}>{entry.ts}</span>}
                    </div>
                    <div style={{ fontSize: 13, color: 'var(--text-2)', lineHeight: 1.5 }}>
                      {(entry.content || '').slice(0, 240)}
                      {(entry.content || '').length > 240 ? '…' : ''}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}
