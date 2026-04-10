// SPDX-License-Identifier: AGPL-3.0-or-later
/**
 * License — ClawOS activation and tier management page.
 *
 * Shows current tier (Free / Premium / Pro), handles key activation
 * and deactivation. Key format: CLAW-XXXX-XXXX-XXXX-XXXX.
 * Validation happens against Supabase (requires internet) with 72h offline grace.
 */
import React, { useEffect, useState } from 'react'

// ── Types ─────────────────────────────────────────────────────────────────────

interface LicenseStatus {
  tier: 'free' | 'premium' | 'pro'
  key?: string
  activated_at?: string
  email?: string
  valid: boolean
  offline_grace?: boolean
}

const TIER_DETAILS = {
  free: {
    label: 'Free',
    color: 'var(--text-3)',
    badge: 'gray',
    features: [
      'Ollama offline models',
      'Core Jarvis loop',
      'Dashboard + voice (Piper)',
      '5 workflows',
      'Community skills',
      'AGPL open source',
    ],
    missing: [
      'All 29 workflows',
      'OpenRouter cloud models',
      'RAG + Knowledge base',
      'A2A federation',
      'Skill publishing',
      'ElevenLabs TTS',
    ],
  },
  premium: {
    label: 'Premium',
    color: '#7c6af5',
    badge: 'purple',
    features: [
      'Everything in Free',
      'All 29 workflows',
      'OpenRouter cloud models',
      'RAG + Kizuna knowledge graph',
      'A2A agent federation',
      'Skill publishing to ClawHub',
      'ElevenLabs TTS (Daniel voice)',
    ],
    missing: [],
  },
  pro: {
    label: 'Pro',
    color: '#f59e0b',
    badge: 'orange',
    features: [
      'Everything in Premium',
      'Enterprise workflows',
      'Remote A2A multi-node',
      'Team workspaces',
      'Priority support',
    ],
    missing: [],
  },
}

// ── Main component ────────────────────────────────────────────────────────────

export function LicensePage() {
  const [status, setStatus] = useState<LicenseStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [activating, setActivating] = useState(false)
  const [deactivating, setDeactivating] = useState(false)
  const [key, setKey] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const fetchStatus = async () => {
    try {
      const r = await fetch('/api/license', { credentials: 'include' })
      if (r.ok) {
        setStatus(await r.json())
      }
    } catch { /* non-fatal */ } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStatus()
  }, [])

  const activate = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = key.trim().toUpperCase()
    if (!trimmed.startsWith('CLAW-')) {
      setError('Key must start with CLAW-')
      return
    }
    setActivating(true)
    setError('')
    setSuccess('')
    try {
      const r = await fetch('/api/license/activate', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: trimmed }),
      })
      const data = await r.json()
      if (!r.ok) {
        setError(data.detail || 'Activation failed')
      } else {
        setSuccess(`Activated! You're now on ${data.tier || 'premium'}.`)
        setKey('')
        fetchStatus()
      }
    } catch (e: any) {
      setError(e.message || 'Activation failed')
    } finally {
      setActivating(false)
    }
  }

  const deactivate = async () => {
    if (!confirm('Deactivate this machine? Your license key can be used on another device.')) return
    setDeactivating(true)
    setError('')
    try {
      const r = await fetch('/api/license/deactivate', {
        method: 'POST',
        credentials: 'include',
      })
      const data = await r.json()
      if (!r.ok) {
        setError(data.detail || 'Deactivation failed')
      } else {
        setSuccess('License deactivated. You\'re back on Free.')
        fetchStatus()
      }
    } catch (e: any) {
      setError(e.message || 'Deactivation failed')
    } finally {
      setDeactivating(false)
    }
  }

  const tier = status?.tier || 'free'
  const tierDetail = TIER_DETAILS[tier] || TIER_DETAILS.free
  const isPaid = tier === 'premium' || tier === 'pro'

  return (
    <div className="fade-up" style={{ padding: '0 0 48px' }}>

      {/* Header */}
      <div style={{ padding: '24px 20px 16px' }}>
        <div style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--text-3)' }}>
          License
        </div>
        <div style={{ fontSize: 28, fontWeight: 700, letterSpacing: '-0.03em', marginTop: 4 }}>
          ClawOS License
        </div>
        <div style={{ color: 'var(--text-2)', fontSize: 14, marginTop: 6 }}>
          Pay once. Own it forever. No subscription. No cloud. No data collected.
        </div>
      </div>

      <div style={{ padding: '0 20px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

        {/* Current tier */}
        <div style={{
          background: 'var(--panel)',
          border: `1px solid ${isPaid ? tierDetail.color + '40' : 'var(--border)'}`,
          borderRadius: 14,
          padding: 20,
          display: 'grid',
          gap: 14,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-3)' }}>
              Current Tier
            </div>
            {status?.offline_grace && (
              <span style={{ fontSize: 10, background: 'rgba(251,191,36,0.12)', color: '#fbbf24', borderRadius: 4, padding: '2px 7px', fontWeight: 600 }}>
                Offline grace
              </span>
            )}
          </div>

          {loading ? (
            <div style={{ color: 'var(--text-3)', fontSize: 14 }}>Checking license...</div>
          ) : (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{
                  fontSize: 32, fontWeight: 800, letterSpacing: '-0.04em',
                  color: tierDetail.color,
                }}>
                  {tierDetail.label}
                </div>
                {isPaid && <span style={{ fontSize: 20 }}>✓</span>}
              </div>

              {status?.key && (
                <div style={{ fontFamily: 'monospace', fontSize: 13, color: 'var(--text-2)' }}>
                  {status.key.slice(0, 9)}···{status.key.slice(-4)}
                </div>
              )}

              {status?.activated_at && (
                <div style={{ fontSize: 12, color: 'var(--text-3)' }}>
                  Activated {status.activated_at.slice(0, 10)}
                  {status.email ? ` · ${status.email}` : ''}
                </div>
              )}

              {/* Features */}
              <div style={{ display: 'grid', gap: 6 }}>
                {tierDetail.features.map((f, i) => (
                  <div key={i} style={{ display: 'flex', gap: 8, fontSize: 12, color: 'var(--text-2)', alignItems: 'center' }}>
                    <span style={{ color: 'var(--green)', flexShrink: 0 }}>✓</span>
                    {f}
                  </div>
                ))}
                {tierDetail.missing.map((f, i) => (
                  <div key={i} style={{ display: 'flex', gap: 8, fontSize: 12, color: 'var(--text-3)', alignItems: 'center' }}>
                    <span style={{ flexShrink: 0 }}>✕</span>
                    {f}
                  </div>
                ))}
              </div>

              {isPaid && (
                <button
                  className="btn"
                  style={{ fontSize: 12, justifySelf: 'start' }}
                  onClick={deactivate}
                  disabled={deactivating}
                >
                  {deactivating ? 'Deactivating...' : 'Deactivate this machine'}
                </button>
              )}
            </>
          )}
        </div>

        {/* Activation form */}
        <div style={{ display: 'grid', gap: 14, alignContent: 'start' }}>

          {!isPaid && (
            <div style={{
              background: 'linear-gradient(135deg, rgba(124,106,245,0.12) 0%, rgba(167,139,250,0.06) 100%)',
              border: '1px solid rgba(124,106,245,0.3)',
              borderRadius: 14,
              padding: 20,
              display: 'grid',
              gap: 14,
            }}>
              <div style={{ fontWeight: 700, fontSize: 18, letterSpacing: '-0.02em' }}>
                Upgrade to Premium
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-2)', lineHeight: 1.6 }}>
                All 29 workflows, OpenRouter cloud models, Kizuna brain, A2A federation,
                ElevenLabs voice. <strong>$10 once — no subscription ever.</strong>
              </div>
              <a
                href="https://clawos.dev#premium"
                target="_blank"
                rel="noopener noreferrer"
                className="btn primary"
                style={{ textDecoration: 'none', textAlign: 'center', fontSize: 13 }}
              >
                Get Premium — $10 →
              </a>
            </div>
          )}

          <div style={{
            background: 'var(--panel)',
            border: '1px solid var(--border)',
            borderRadius: 14,
            padding: 20,
            display: 'grid',
            gap: 12,
          }}>
            <div style={{ fontWeight: 600, fontSize: 15 }}>
              {isPaid ? 'License Key' : 'Activate a key'}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-2)' }}>
              Paste your CLAW-XXXX-XXXX-XXXX-XXXX key below. Your machine is bound locally —
              the key can be transferred to another device at any time.
            </div>

            {error && (
              <div style={{ fontSize: 12, color: 'var(--red)', padding: '8px 12px', background: 'rgba(239,68,68,0.08)', borderRadius: 8 }}>
                {error}
              </div>
            )}

            {success && (
              <div style={{ fontSize: 12, color: 'var(--green)', padding: '8px 12px', background: 'rgba(34,197,94,0.08)', borderRadius: 8 }}>
                {success}
              </div>
            )}

            <form onSubmit={activate} style={{ display: 'grid', gap: 10 }}>
              <input
                type="text"
                value={key}
                onChange={e => setKey(e.target.value.toUpperCase())}
                placeholder="CLAW-XXXX-XXXX-XXXX-XXXX"
                style={{ fontFamily: 'monospace', letterSpacing: '0.06em' }}
                disabled={activating}
              />
              <button
                className="btn primary"
                type="submit"
                disabled={activating || !key.trim()}
              >
                {activating ? 'Validating...' : 'Activate'}
              </button>
            </form>
          </div>

          {/* Tier comparison */}
          <div style={{
            background: 'var(--panel)',
            border: '1px solid var(--border)',
            borderRadius: 14,
            padding: 20,
          }}>
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 12 }}>What you get</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              {(['free', 'premium'] as const).map(t => (
                <div key={t}>
                  <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: TIER_DETAILS[t].color, marginBottom: 8 }}>
                    {TIER_DETAILS[t].label}
                    {t === 'free' ? ' · $0' : ' · $10 once'}
                  </div>
                  {TIER_DETAILS[t].features.map((f, i) => (
                    <div key={i} style={{ fontSize: 11, color: 'var(--text-2)', display: 'flex', gap: 6, marginBottom: 4 }}>
                      <span style={{ color: 'var(--green)', flexShrink: 0 }}>✓</span>
                      {f}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default LicensePage
