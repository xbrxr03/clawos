/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { useEffect, useMemo, useState } from 'react'
import { Badge, Card, Empty, PageHeader, PanelHeader, SectionLabel, Skeleton, SkeletonText } from '../components/ui.jsx'
import { commandCenterApi, type UseCasePack } from '../lib/commandCenterApi'

const WAVE_COLORS: Record<string, string> = {
  'wave-1': 'green',
  'wave-2': 'blue',
  'wave-3': 'orange',
}

export function PacksPage() {
  const [packs, setPacks] = useState<UseCasePack[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const data = await commandCenterApi.listPacks()
      setPacks(Array.isArray(data) ? data : [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load().catch(() => setMessage('Failed to load packs'))
  }, [])

  useEffect(() => {
    if (!selectedId && packs.length) {
      const primary = packs.find((item) => item.primary) || packs[0]
      setSelectedId(primary.id)
    }
  }, [packs, selectedId])

  const selected = useMemo(
    () => packs.find((pack) => pack.id === selectedId) || null,
    [packs, selectedId],
  )
  const stats = useMemo(
    () => ({
      total: packs.length,
      primary: packs.filter((pack) => pack.primary).length,
      installed: packs.filter((pack) => pack.primary || pack.secondary).length,
      recommendedExtensions: packs.reduce((max, pack) => Math.max(max, pack.extension_recommendations?.length || 0), 0),
    }),
    [packs],
  )

  const installPack = async (pack: UseCasePack, primary = false) => {
    setBusy(pack.id)
    setMessage('')
    try {
      await commandCenterApi.installPack(pack.id, primary)
      await load()
      setMessage(`${pack.name} is now ${primary ? 'the primary pack' : 'available in your workspace'}.`)
    } catch (error: any) {
      setMessage(error.message || `Failed to install ${pack.name}`)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="fade-up" style={{ padding: '0 0 48px' }}>
      <div style={{ padding: '32px 24px 18px' }}>
        <PageHeader
          eyebrow="Packs"
          title="Outcome-focused packs with install posture and setup defaults."
          description="Inspect the primary pack, compare workflow bundles, and switch the product posture without leaving the dashboard."
          meta={
            <>
              <Badge color="blue">{stats.total} packs</Badge>
              <Badge color={stats.primary ? 'green' : 'gray'}>{stats.primary ? 'Primary selected' : 'No primary yet'}</Badge>
              <Badge color="gray">{stats.installed} installed</Badge>
            </>
          }
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 10, padding: '0 20px 16px' }}>
        <MetricCard label="Available" value={stats.total} tone="blue" />
        <MetricCard label="Installed" value={stats.installed} tone="green" />
        <MetricCard label="Primary" value={stats.primary} tone="orange" />
        <MetricCard label="Best ext. set" value={stats.recommendedExtensions} tone="purple" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.05fr 0.95fr', gap: 14, padding: '0 20px' }}>
        <div style={{ display: 'grid', gap: 10 }}>
          {loading ? (
            Array.from({ length: 3 }).map((_, index) => (
              <Card key={index} style={{ padding: 18 }}>
                <Skeleton width="26%" height={14} />
                <div style={{ height: 12 }} />
                <SkeletonText lines={3} />
              </Card>
            ))
          ) : packs.length === 0 ? (
            <Card><Empty>No packs are available yet.</Empty></Card>
          ) : (
            packs.map((pack) => (
              <Card
                key={pack.id}
                style={{
                  padding: 18,
                  cursor: 'pointer',
                  borderColor: pack.id === selectedId ? 'rgba(77, 143, 247, 0.28)' : undefined,
                }}
                onClick={() => setSelectedId(pack.id)}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                      <div style={{ fontSize: 16, fontWeight: 600 }}>{pack.name}</div>
                      <Badge color={WAVE_COLORS[pack.wave || 'wave-2'] || 'blue'}>{pack.wave || 'wave-1'}</Badge>
                      {pack.primary ? <Badge color="green">primary</Badge> : null}
                      {pack.secondary ? <Badge color="blue">installed</Badge> : null}
                    </div>
                    <div style={{ marginTop: 8, color: 'var(--text-2)', lineHeight: 1.55 }}>{pack.description}</div>
                    <div style={{ marginTop: 10, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      <Badge color="gray">{(pack.default_workflows || []).length} workflows</Badge>
                      <Badge color="gray">{(pack.extension_recommendations || []).length} recommended extensions</Badge>
                      <Badge color="gray">{(pack.provider_recommendations || []).length} provider fits</Badge>
                    </div>
                  </div>

                  <div style={{ display: 'grid', gap: 8, flexShrink: 0 }}>
                    <button className="btn primary" disabled={busy !== null} onClick={(event) => { event.stopPropagation(); installPack(pack, true) }}>
                      {busy === pack.id ? 'Applying...' : pack.primary ? 'Primary Pack' : 'Set Primary'}
                    </button>
                    {!pack.primary && (
                      <button className="btn" disabled={busy !== null} onClick={(event) => { event.stopPropagation(); installPack(pack, false) }}>
                        {pack.secondary ? 'Installed' : 'Install'}
                      </button>
                    )}
                  </div>
                </div>
              </Card>
            ))
          )}
        </div>

        <Card style={{ padding: 20 }}>
          {selected ? (
            <div style={{ display: 'grid', gap: 16 }}>
              <PanelHeader
                eyebrow="Selected pack"
                title={selected.name}
                description={selected.setup_summary || selected.description}
                aside={
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    <Badge color={WAVE_COLORS[selected.wave || 'wave-2'] || 'blue'}>{selected.wave || 'wave-1'}</Badge>
                    {selected.primary ? <Badge color="green">primary</Badge> : null}
                    {selected.secondary ? <Badge color="blue">installed</Badge> : null}
                  </div>
                }
              />

              <div>
                <SectionLabel>Dashboards</SectionLabel>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {(selected.dashboards || []).map((item) => <Badge key={item} color="blue">{item}</Badge>)}
                </div>
              </div>

              <div>
                <SectionLabel>Default workflows</SectionLabel>
                <div style={{ display: 'grid', gap: 8 }}>
                  {(selected.default_workflows || []).map((item) => (
                    <div key={item} className="mono" style={{ padding: '10px 12px', borderRadius: 12, background: 'var(--surface)', border: '1px solid var(--border)' }}>
                      {item}
                    </div>
                  ))}
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <SectionLabel>Recommended extensions</SectionLabel>
                  <div style={{ display: 'grid', gap: 8 }}>
                    {(selected.extension_recommendations || []).map((item) => <Badge key={item} color="gray">{item}</Badge>)}
                  </div>
                </div>
                <div>
                  <SectionLabel>Recommended providers</SectionLabel>
                  <div style={{ display: 'grid', gap: 8 }}>
                    {(selected.provider_recommendations || []).map((item) => <Badge key={item} color="gray">{item}</Badge>)}
                  </div>
                </div>
              </div>

              <div className="glass" style={{ padding: 14 }}>
                <div className="section-label">Policy pack</div>
                <div className="mono" style={{ marginTop: 6 }}>{selected.policy_pack || 'recommended'}</div>
              </div>
            </div>
          ) : (
            <Empty>Select a pack to inspect its setup shape and defaults.</Empty>
          )}
        </Card>
      </div>

      {message && (
        <div style={{ padding: '16px 20px 0' }}>
          <Card style={{ padding: 14, color: 'var(--text-2)' }}>{message}</Card>
        </div>
      )}
    </div>
  )
}

function MetricCard({ label, value, tone }: { label: string; value: number; tone: 'blue' | 'green' | 'orange' | 'purple' }) {
  const toneValue = {
    blue: 'var(--blue)',
    green: 'var(--green)',
    orange: 'var(--orange)',
    purple: 'var(--purple)',
  }[tone]

  return (
    <Card style={{ padding: 18 }}>
      <div style={{ fontSize: 12, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>{label}</div>
      <div style={{ marginTop: 8, fontSize: 30, lineHeight: 1, fontWeight: 700, letterSpacing: '-0.05em', color: toneValue }}>
        {value}
      </div>
    </Card>
  )
}
