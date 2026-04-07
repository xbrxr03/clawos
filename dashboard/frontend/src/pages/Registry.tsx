/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { useEffect, useMemo, useState } from 'react'
import { Badge, Card, Empty, PageHeader, PanelHeader, SectionLabel, Skeleton, SkeletonText } from '../components/ui.jsx'
import { commandCenterApi, type ExtensionManifest } from '../lib/commandCenterApi'

const TRUST_COLORS: Record<string, string> = {
  Verified: 'green',
  Community: 'blue',
  Quarantined: 'red',
}

export function RegistryPage() {
  const [extensions, setExtensions] = useState<ExtensionManifest[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [agentCard, setAgentCard] = useState<Record<string, any> | null>(null)
  const [peers, setPeers] = useState<Array<Record<string, any>>>([])
  const [busy, setBusy] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const [extensionData, a2a] = await Promise.all([
        commandCenterApi.listExtensions(),
        commandCenterApi.getAgentCard(),
      ])
      setExtensions(Array.isArray(extensionData) ? extensionData : [])
      setAgentCard((a2a.card as Record<string, any>) || null)
      setPeers(Array.isArray(a2a.peers) ? (a2a.peers as Array<Record<string, any>>) : [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load().catch(() => setMessage('Failed to load the registry surface'))
  }, [])

  useEffect(() => {
    if (!selectedId && extensions.length) {
      const preferred = extensions.find((item) => item.recommended_for_primary) || extensions[0]
      setSelectedId(preferred.id)
    }
  }, [extensions, selectedId])

  const selected = useMemo(
    () => extensions.find((extension) => extension.id === selectedId) || null,
    [extensions, selectedId],
  )
  const stats = useMemo(
    () => ({
      total: extensions.length,
      installed: extensions.filter((extension) => extension.installed).length,
      verified: extensions.filter((extension) => extension.trust_tier === 'Verified').length,
      recommended: extensions.filter((extension) => extension.recommended_for_primary).length,
    }),
    [extensions],
  )

  const installExtension = async (extension: ExtensionManifest) => {
    setBusy(extension.id)
    setMessage('')
    try {
      await commandCenterApi.installExtension(extension.id)
      await load()
      setMessage(`${extension.name} is now installed.`)
    } catch (error: any) {
      setMessage(error.message || `Failed to install ${extension.name}`)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="fade-up" style={{ padding: '0 0 48px' }}>
      <div style={{ padding: '32px 24px 18px' }}>
        <PageHeader
          eyebrow="Registry"
          title="Trust-first extension installs and local federation identity."
          description="Inspect trust tiers, permissions, and pack alignment before anything is installed, then compare that posture against the node's local A2A identity."
          meta={
            <>
              <Badge color="blue">{stats.total} extensions</Badge>
              <Badge color="green">{stats.verified} verified</Badge>
              <Badge color="gray">{stats.installed} installed</Badge>
            </>
          }
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 10, padding: '0 20px 16px' }}>
        <MetricCard label="Catalog" value={stats.total} tone="blue" />
        <MetricCard label="Installed" value={stats.installed} tone="green" />
        <MetricCard label="Verified" value={stats.verified} tone="orange" />
        <MetricCard label="Recommended" value={stats.recommended} tone="purple" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.05fr 0.95fr', gap: 14, padding: '0 20px' }}>
        <div style={{ display: 'grid', gap: 10 }}>
          {loading ? (
            Array.from({ length: 3 }).map((_, index) => (
              <Card key={index} style={{ padding: 18 }}>
                <Skeleton width="32%" height={14} />
                <div style={{ height: 12 }} />
                <SkeletonText lines={3} />
              </Card>
            ))
          ) : extensions.length === 0 ? (
            <Card><Empty>No extensions are available yet.</Empty></Card>
          ) : (
            extensions.map((extension) => (
              <Card
                key={extension.id}
                style={{
                  padding: 18,
                  cursor: 'pointer',
                  borderColor: extension.id === selectedId ? 'rgba(77, 143, 247, 0.28)' : undefined,
                }}
                onClick={() => setSelectedId(extension.id)}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                      <div style={{ fontSize: 16, fontWeight: 600 }}>{extension.name}</div>
                      <Badge color={TRUST_COLORS[extension.trust_tier || 'Community'] || 'gray'}>
                        {extension.trust_tier || 'Community'}
                      </Badge>
                      {extension.installed ? <Badge color="green">installed</Badge> : null}
                      {extension.recommended_for_primary ? <Badge color="blue">recommended</Badge> : null}
                    </div>
                    <div style={{ marginTop: 8, color: 'var(--text-2)', lineHeight: 1.55 }}>{extension.description}</div>
                    <div style={{ marginTop: 10, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      {(extension.permissions || []).slice(0, 3).map((permission) => (
                        <Badge key={permission} color="gray">{permission}</Badge>
                      ))}
                      {extension.permissions && extension.permissions.length > 3 ? (
                        <Badge color="gray">+{extension.permissions.length - 3} more</Badge>
                      ) : null}
                    </div>
                  </div>

                  <button className="btn primary" disabled={busy !== null || !!extension.installed} onClick={(event) => { event.stopPropagation(); installExtension(extension) }}>
                    {busy === extension.id ? 'Installing...' : extension.installed ? 'Installed' : 'Install'}
                  </button>
                </div>
              </Card>
            ))
          )}
        </div>

        <div style={{ display: 'grid', gap: 14 }}>
          <Card style={{ padding: 20 }}>
            {selected ? (
              <div style={{ display: 'grid', gap: 16 }}>
                <PanelHeader
                  eyebrow="Selected extension"
                  title={selected.name}
                  description={selected.description}
                  aside={
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      <Badge color={TRUST_COLORS[selected.trust_tier || 'Community'] || 'gray'}>
                        {selected.trust_tier || 'Community'}
                      </Badge>
                      {selected.installed ? <Badge color="green">installed</Badge> : null}
                    </div>
                  }
                />
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <Detail label="Category" value={selected.category} />
                  <Detail label="Network" value={selected.network_access || 'local-only'} />
                  <Detail label="Self-hostable" value={selected.self_hostable ? 'Yes' : 'No'} />
                  <Detail label="Platforms" value={(selected.supported_platforms || []).join(', ') || 'all'} />
                </div>

                <div>
                  <SectionLabel>Permissions</SectionLabel>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {(selected.permissions || []).map((item) => <Badge key={item} color="gray">{item}</Badge>)}
                  </div>
                </div>

                <div>
                  <SectionLabel>Pack alignment</SectionLabel>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {(selected.packs || []).map((item) => <Badge key={item} color="gray">{item}</Badge>)}
                  </div>
                </div>
              </div>
            ) : (
              <Empty>Select an extension to inspect its trust and permission posture.</Empty>
            )}
          </Card>

          <Card style={{ padding: 20 }}>
            <div className="section-label">A2A identity</div>
            {agentCard ? (
              <div style={{ display: 'grid', gap: 12 }}>
                <div style={{ fontSize: 20, fontWeight: 700, letterSpacing: '-0.04em' }}>{String(agentCard.name || 'ClawOS node')}</div>
                <div style={{ color: 'var(--text-3)' }}>{String(agentCard.description || 'Local A2A node')}</div>
                <div className="mono" style={{ fontSize: 12, wordBreak: 'break-all' }}>{String(agentCard.url || '')}</div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {((agentCard.skills as Array<{ name?: string }>) || []).map((skill, index) => (
                    <Badge key={`${skill.name || 'skill'}-${index}`} color="gray">{skill.name || 'skill'}</Badge>
                  ))}
                </div>
                <SectionLabel>Peers</SectionLabel>
                {peers.length === 0 ? (
                  <div style={{ color: 'var(--text-3)', fontSize: 13 }}>No trusted peers discovered yet.</div>
                ) : (
                  <div style={{ display: 'grid', gap: 8 }}>
                    {peers.map((peer, index) => (
                      <div key={`${peer.url || peer.ip || 'peer'}-${index}`} className="glass" style={{ padding: 12 }}>
                        <div style={{ fontWeight: 600 }}>{String(peer.name || peer.ip || 'Peer node')}</div>
                        <div className="mono" style={{ marginTop: 4, fontSize: 11 }}>{String(peer.url || '')}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <Empty>Agent-card posture will appear here when the A2A layer is available.</Empty>
            )}
          </Card>
        </div>
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
