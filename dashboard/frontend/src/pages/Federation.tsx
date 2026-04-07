/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { useEffect, useState } from 'react'
import { Badge, Card, Empty, SectionLabel } from '../components/ui.jsx'
import { commandCenterApi } from '../lib/commandCenterApi'

type TrustTier = 'trusted' | 'unverified' | 'blocked'

type Peer = {
  id: string
  url: string
  name: string
  trust_tier: TrustTier
  description?: string
  version?: string
  capabilities?: string[]
  skills?: string[]
  last_seen?: string
  last_error?: string
  reachable?: boolean
  added_at: string
}

const TRUST_COLORS: Record<TrustTier, string> = {
  trusted: 'green',
  unverified: 'orange',
  blocked: 'red',
}

const TRUST_DESCRIPTIONS: Record<TrustTier, string> = {
  trusted: 'Tasks accepted without extra gates',
  unverified: 'Tasks require policyd approval',
  blocked: 'All communication rejected',
}

export function FederationPage() {
  const [peers, setPeers] = useState<Peer[]>([])
  const [selected, setSelected] = useState<Peer | null>(null)
  const [keyFingerprint, setKeyFingerprint] = useState('')
  const [message, setMessage] = useState('')
  const [probing, setProbing] = useState<string | null>(null)

  // Add form
  const [addUrl, setAddUrl] = useState('')
  const [addName, setAddName] = useState('')
  const [addTrust, setAddTrust] = useState<TrustTier>('unverified')
  const [addBusy, setAddBusy] = useState(false)

  const load = async () => {
    try {
      const [peerData, keyData] = await Promise.all([
        commandCenterApi.listA2APeers(),
        commandCenterApi.getA2ASigningKey(),
      ])
      setPeers(Array.isArray(peerData) ? peerData : [])
      setKeyFingerprint((keyData as any)?.fingerprint || '')
    } catch {
      setMessage('Failed to load federation data')
    }
  }

  useEffect(() => { load() }, [])

  const addPeer = async () => {
    if (!addUrl.trim()) return
    setAddBusy(true)
    setMessage('')
    try {
      const peer = await commandCenterApi.addA2APeer(addUrl.trim(), addName.trim(), addTrust)
      setPeers((prev) => [...prev, peer as Peer])
      setAddUrl('')
      setAddName('')
    } catch (err: any) {
      setMessage(err.message || 'Add failed')
    } finally {
      setAddBusy(false)
    }
  }

  const removePeer = async (id: string) => {
    try {
      await commandCenterApi.removeA2APeer(id)
      setPeers((prev) => prev.filter((p) => p.id !== id))
      if (selected?.id === id) setSelected(null)
    } catch (err: any) {
      setMessage(err.message || 'Remove failed')
    }
  }

  const setTrust = async (id: string, tier: TrustTier) => {
    try {
      const updated = await commandCenterApi.setA2ATrust(id, tier) as Peer
      setPeers((prev) => prev.map((p) => (p.id === id ? updated : p)))
      if (selected?.id === id) setSelected(updated)
    } catch (err: any) {
      setMessage(err.message || 'Trust update failed')
    }
  }

  const probe = async (id: string) => {
    setProbing(id)
    setMessage('')
    try {
      const updated = await commandCenterApi.probeA2APeer(id) as Peer
      setPeers((prev) => prev.map((p) => (p.id === id ? updated : p)))
      if (selected?.id === id) setSelected(updated)
      setMessage(updated.reachable ? `${updated.name} is reachable` : `${updated.name} is unreachable`)
    } catch (err: any) {
      setMessage(err.message || 'Probe failed')
    } finally {
      setProbing(null)
    }
  }

  const trustedCount = peers.filter((p) => p.trust_tier === 'trusted').length
  const reachableCount = peers.filter((p) => p.reachable).length

  return (
    <div className="fade-up" style={{ padding: '0 0 48px' }}>
      <div style={{ padding: '32px 24px 18px' }}>
        <div style={{ fontSize: 28, fontWeight: 700, letterSpacing: '-0.05em' }}>Federation</div>
        <div style={{ fontSize: 14, color: 'var(--text-3)', marginTop: 6, maxWidth: 720 }}>
          A2A peer registry with trust tiers and signed agent card verification. Trusted peers can delegate tasks directly.
        </div>
        <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <Badge color="blue">{peers.length} peers</Badge>
          <Badge color="green">{trustedCount} trusted</Badge>
          <Badge color="orange">{reachableCount} reachable</Badge>
          {keyFingerprint && (
            <div className="glass" style={{ padding: '4px 10px', borderRadius: 8, fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-3)' }}>
              signing key: {keyFingerprint}
            </div>
          )}
        </div>
      </div>

      {message && (
        <div style={{ padding: '0 24px 10px' }}>
          <div className="glass" style={{ padding: '10px 14px', fontSize: 13, color: 'var(--text-2)' }}>{message}</div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 0.9fr', gap: 14, padding: '0 20px' }}>
        {/* Left: peer list + add form */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Add peer */}
          <Card style={{ padding: 16 }}>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 10 }}>Register peer</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <div style={{ gridColumn: '1 / -1' }}>
                <SectionLabel>Peer URL</SectionLabel>
                <input
                  value={addUrl}
                  onChange={(e) => setAddUrl(e.target.value)}
                  placeholder="http://192.168.1.42:7443"
                  style={{ width: '100%', padding: '7px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text)', fontSize: 12, fontFamily: 'var(--font-mono)' }}
                />
              </div>
              <div>
                <SectionLabel>Name (optional)</SectionLabel>
                <input
                  value={addName}
                  onChange={(e) => setAddName(e.target.value)}
                  placeholder="Workstation B"
                  style={{ width: '100%', padding: '7px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text)', fontSize: 12 }}
                />
              </div>
              <div>
                <SectionLabel>Initial trust tier</SectionLabel>
                <select
                  value={addTrust}
                  onChange={(e) => setAddTrust(e.target.value as TrustTier)}
                  style={{ width: '100%', padding: '7px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text)', fontSize: 12 }}
                >
                  <option value="unverified">Unverified</option>
                  <option value="trusted">Trusted</option>
                  <option value="blocked">Blocked</option>
                </select>
              </div>
            </div>
            <button className="btn primary" style={{ marginTop: 10 }} onClick={addPeer} disabled={addBusy}>
              {addBusy ? 'Adding…' : 'Add Peer'}
            </button>
          </Card>

          {/* Peer list */}
          {peers.length === 0 ? (
            <Card style={{ padding: 18 }}><Empty>No peers registered. Add a peer above or enable mDNS discovery in config.</Empty></Card>
          ) : (
            peers.map((peer) => (
              <Card
                key={peer.id}
                style={{
                  padding: 14,
                  cursor: 'pointer',
                  borderColor: selected?.id === peer.id ? 'rgba(77,143,247,0.3)' : undefined,
                }}
                onClick={() => setSelected(selected?.id === peer.id ? null : peer)}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'flex-start' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 14, fontWeight: 600 }}>{peer.name}</div>
                    <div className="mono" style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {peer.url}
                    </div>
                    <div style={{ marginTop: 6, display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                      <Badge color={TRUST_COLORS[peer.trust_tier]}>{peer.trust_tier}</Badge>
                      <Badge color={peer.reachable ? 'green' : 'gray'}>
                        {peer.reachable ? 'reachable' : 'unknown'}
                      </Badge>
                      {(peer.skills?.length ?? 0) > 0 && <Badge color="blue">{peer.skills!.length} skills</Badge>}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 5, flexShrink: 0 }} onClick={(e) => e.stopPropagation()}>
                    <button
                      className="btn sm"
                      disabled={probing === peer.id}
                      onClick={() => probe(peer.id)}
                    >
                      {probing === peer.id ? '…' : 'Probe'}
                    </button>
                    <button className="btn sm" style={{ color: 'var(--red)' }} onClick={() => removePeer(peer.id)}>
                      Remove
                    </button>
                  </div>
                </div>
                {peer.last_error && (
                  <div style={{ marginTop: 6, fontSize: 11, color: 'var(--red)' }}>{peer.last_error}</div>
                )}
              </Card>
            ))
          )}
        </div>

        {/* Right: selected peer detail */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {selected ? (
            <>
              <Card style={{ padding: 18 }}>
                <div style={{ fontSize: 16, fontWeight: 700 }}>{selected.name}</div>
                {selected.description && (
                  <div style={{ marginTop: 6, color: 'var(--text-2)', fontSize: 13 }}>{selected.description}</div>
                )}
                <div className="mono" style={{ marginTop: 6, fontSize: 11, color: 'var(--text-3)' }}>{selected.url}</div>

                <div style={{ marginTop: 14 }}>
                  <SectionLabel>Trust tier</SectionLabel>
                  <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                    {(['trusted', 'unverified', 'blocked'] as TrustTier[]).map((tier) => (
                      <button
                        key={tier}
                        type="button"
                        onClick={() => setTrust(selected.id, tier)}
                        style={{
                          padding: '5px 12px',
                          borderRadius: 8,
                          border: `1px solid ${selected.trust_tier === tier ? 'rgba(77,143,247,0.4)' : 'var(--border)'}`,
                          background: selected.trust_tier === tier ? 'rgba(77,143,247,0.1)' : 'transparent',
                          color: selected.trust_tier === tier ? 'var(--blue)' : 'var(--text-2)',
                          cursor: 'pointer',
                          fontSize: 12,
                          fontWeight: selected.trust_tier === tier ? 600 : 400,
                        }}
                      >
                        {tier}
                      </button>
                    ))}
                  </div>
                  <div style={{ marginTop: 6, fontSize: 12, color: 'var(--text-3)' }}>
                    {TRUST_DESCRIPTIONS[selected.trust_tier]}
                  </div>
                </div>
              </Card>

              {selected.skills && selected.skills.length > 0 && (
                <Card style={{ padding: 16 }}>
                  <SectionLabel>Skills</SectionLabel>
                  <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginTop: 6 }}>
                    {selected.skills.map((s) => <Badge key={s} color="blue">{s}</Badge>)}
                  </div>
                </Card>
              )}

              {selected.capabilities && selected.capabilities.length > 0 && (
                <Card style={{ padding: 16 }}>
                  <SectionLabel>Capabilities</SectionLabel>
                  <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginTop: 6 }}>
                    {selected.capabilities.map((c) => <Badge key={c} color="gray">{c}</Badge>)}
                  </div>
                </Card>
              )}

              <Card style={{ padding: 16 }}>
                <SectionLabel>Metadata</SectionLabel>
                <div style={{ display: 'grid', gap: 6, marginTop: 6, fontSize: 12, color: 'var(--text-2)' }}>
                  {selected.version && <div>Version: <span className="mono">{selected.version}</span></div>}
                  {selected.last_seen && <div>Last seen: {selected.last_seen}</div>}
                  <div>Added: {selected.added_at}</div>
                  <div>ID: <span className="mono">{selected.id}</span></div>
                </div>
              </Card>
            </>
          ) : (
            <Card style={{ padding: 18 }}>
              <Empty>Select a peer to manage its trust tier, inspect capabilities, and view probe history.</Empty>
            </Card>
          )}

          {/* Trust tier reference */}
          <Card style={{ padding: 16 }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>Trust model</div>
            {(Object.entries(TRUST_DESCRIPTIONS) as [TrustTier, string][]).map(([tier, desc]) => (
              <div key={tier} style={{ display: 'flex', gap: 8, marginBottom: 8, alignItems: 'center' }}>
                <Badge color={TRUST_COLORS[tier]}>{tier}</Badge>
                <span style={{ fontSize: 12, color: 'var(--text-2)' }}>{desc}</span>
              </div>
            ))}
            <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-3)' }}>
              Agent cards are HMAC-SHA256 signed with your local signing key.
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
