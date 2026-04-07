/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { useEffect, useMemo, useState } from 'react'
import { Badge, Card, Empty, PageHeader, PanelHeader, SectionLabel, Skeleton, SkeletonText, StatusDot } from '../components/ui.jsx'
import { commandCenterApi, type ProviderProfile } from '../lib/commandCenterApi'

const STATUS_COLORS: Record<string, string> = {
  online: 'green',
  configured: 'blue',
  needs_credentials: 'orange',
  offline: 'red',
  unknown: 'gray',
}

export function ProvidersPage() {
  const [providers, setProviders] = useState<ProviderProfile[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const data = await commandCenterApi.listProviders()
      setProviders(Array.isArray(data) ? data : [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load().catch(() => setMessage('Failed to load providers'))
  }, [])

  useEffect(() => {
    const selected = providers.find((item) => item.selected) || providers[0]
    if (selected) setSelectedId(selected.id)
  }, [providers])

  const selected = useMemo(
    () => providers.find((provider) => provider.id === selectedId) || null,
    [providers, selectedId],
  )
  const stats = useMemo(
    () => ({
      total: providers.length,
      online: providers.filter((provider) => provider.status === 'online').length,
      selected: providers.filter((provider) => provider.selected).length,
      cloudReady: providers.filter((provider) => provider.kind !== 'local').length,
    }),
    [providers],
  )

  const runTest = async (profileId: string) => {
    setBusy(`test:${profileId}`)
    try {
      const result = await commandCenterApi.testProvider(profileId)
      setMessage(result.detail || `${profileId} tested`)
      await load()
    } catch (error: any) {
      setMessage(error.message || `Failed to test ${profileId}`)
    } finally {
      setBusy(null)
    }
  }

  const switchProvider = async (profileId: string) => {
    setBusy(`switch:${profileId}`)
    try {
      await commandCenterApi.switchProvider(profileId)
      setMessage(`Selected provider profile: ${profileId}`)
      await load()
    } catch (error: any) {
      setMessage(error.message || `Failed to switch ${profileId}`)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="fade-up" style={{ padding: '0 0 48px' }}>
      <div style={{ padding: '32px 24px 18px' }}>
        <PageHeader
          eyebrow="Providers"
          title="Provider posture with health, switching, and inline testing."
          description="Keep local Ollama first, but make cloud and compatible backends visible when they materially improve the job."
          meta={
            <>
              <Badge color="blue">{stats.total} profiles</Badge>
              <Badge color={stats.online ? 'green' : 'orange'}>{stats.online} online</Badge>
              <Badge color="gray">{stats.cloudReady} non-local</Badge>
            </>
          }
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 10, padding: '0 20px 16px' }}>
        <MetricCard label="Profiles" value={stats.total} tone="blue" />
        <MetricCard label="Online" value={stats.online} tone="green" />
        <MetricCard label="Selected" value={stats.selected} tone="orange" />
        <MetricCard label="Cloud-ready" value={stats.cloudReady} tone="purple" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, padding: '0 20px' }}>
        <div style={{ display: 'grid', gap: 10 }}>
          {loading ? (
            Array.from({ length: 3 }).map((_, index) => (
              <Card key={index} style={{ padding: 18 }}>
                <Skeleton width="30%" height={14} />
                <div style={{ height: 12 }} />
                <SkeletonText lines={2} />
              </Card>
            ))
          ) : providers.length === 0 ? (
            <Card><Empty>No provider profiles have been registered yet.</Empty></Card>
          ) : (
            providers.map((profile) => (
              <Card
                key={profile.id}
                style={{
                  padding: 18,
                  cursor: 'pointer',
                  borderColor: profile.id === selectedId ? 'rgba(77, 143, 247, 0.28)' : undefined,
                }}
                onClick={() => setSelectedId(profile.id)}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                      <StatusDot status={profile.status === 'online' ? 'up' : profile.status === 'offline' ? 'down' : 'pending'} />
                      <div style={{ fontSize: 16, fontWeight: 600 }}>{profile.name}</div>
                      <Badge color={STATUS_COLORS[profile.status || 'unknown'] || 'gray'}>{profile.status || 'unknown'}</Badge>
                      {profile.selected ? <Badge color="green">selected</Badge> : null}
                    </div>
                    <div style={{ marginTop: 8, color: 'var(--text-3)', fontSize: 13 }}>{profile.endpoint}</div>
                  </div>
                  <div style={{ display: 'grid', gap: 8, flexShrink: 0 }}>
                    <button className="btn" disabled={busy !== null} onClick={(event) => { event.stopPropagation(); runTest(profile.id) }}>
                      {busy === `test:${profile.id}` ? 'Testing...' : 'Test'}
                    </button>
                    {!profile.selected && (
                      <button className="btn primary" disabled={busy !== null} onClick={(event) => { event.stopPropagation(); switchProvider(profile.id) }}>
                        {busy === `switch:${profile.id}` ? 'Switching...' : 'Select'}
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
                eyebrow="Selected profile"
                title={selected.name}
                description={selected.detail || 'Provider profile posture and fallback chain.'}
                aside={<Badge color={STATUS_COLORS[selected.status || 'unknown'] || 'gray'}>{selected.status || 'unknown'}</Badge>}
              />

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <Detail label="Kind" value={selected.kind} />
                <Detail label="Auth mode" value={selected.auth_mode} />
                <Detail label="Default model" value={selected.default_model} />
                <Detail label="Privacy" value={selected.privacy_posture || 'local-first'} />
                <Detail label="Cost" value={selected.cost_posture || 'variable'} />
                <Detail label="Auth env" value={selected.auth_env || 'not required'} />
              </div>

              <div>
                <SectionLabel>Fallback order</SectionLabel>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {(selected.fallback_order || []).map((item) => <Badge key={item} color="gray">{item}</Badge>)}
                  {(!selected.fallback_order || selected.fallback_order.length === 0) && <Badge color="gray">none</Badge>}
                </div>
              </div>

              <div className="glass" style={{ padding: 14 }}>
                <div className="section-label">Endpoint</div>
                <div className="mono" style={{ marginTop: 6, wordBreak: 'break-all' }}>{selected.endpoint}</div>
              </div>
            </div>
          ) : (
            <Empty>Select a provider profile to inspect its posture and fallback strategy.</Empty>
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

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="glass" style={{ padding: 14 }}>
      <div className="section-label">{label}</div>
      <div className="mono" style={{ marginTop: 6 }}>{value}</div>
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
