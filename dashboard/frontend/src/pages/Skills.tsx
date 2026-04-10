// SPDX-License-Identifier: AGPL-3.0-or-later
/**
 * Skills Marketplace — ClawHub browser with Ed25519 trust verification.
 *
 * Browse skills from ClawHub (hub.openclaw.ai), install with signature
 * verification, manage installed skills. Every install is sandbox-tested
 * before activation. Unsigned skills are blocked by default.
 */
import React, { useCallback, useEffect, useState } from 'react'

// ── Types ─────────────────────────────────────────────────────────────────────

interface Skill {
  id: string
  name: string
  description: string
  author: string
  version: string
  stars?: number
  category?: string
  trust_tier: 'clawos_verified' | 'community' | 'local'
  installed?: boolean
  icon?: string
}

interface InstalledSkill {
  id: string
  name: string
  version: string
  author: string
  trust_tier: string
  installed_at: string
}

// ── Main component ────────────────────────────────────────────────────────────

export function SkillsPage() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Skill[]>([])
  const [installed, setInstalled] = useState<InstalledSkill[]>([])
  const [loading, setLoading] = useState(false)
  const [installing, setInstalling] = useState<string | null>(null)
  const [removingId, setRemovingId] = useState<string | null>(null)
  const [tab, setTab] = useState<'browse' | 'installed'>('browse')
  const [error, setError] = useState('')
  const [toast, setToast] = useState('')
  const [allowCommunity, setAllowCommunity] = useState(true)

  const showToast = (msg: string) => {
    setToast(msg)
    setTimeout(() => setToast(''), 4000)
  }

  const fetchInstalled = useCallback(async () => {
    try {
      const r = await fetch('/api/skills/installed', { credentials: 'include' })
      if (r.ok) {
        const data = await r.json()
        setInstalled(data.skills || [])
      }
    } catch { /* non-fatal */ }
  }, [])

  const search = useCallback(async (q: string) => {
    setLoading(true)
    setError('')
    try {
      const r = await fetch(
        `/api/skills?q=${encodeURIComponent(q)}&limit=24`,
        { credentials: 'include' }
      )
      if (r.ok) {
        const data = await r.json()
        setResults(data.results || [])
      } else {
        setError('Search failed — ClawHub may be unreachable')
      }
    } catch (e: any) {
      setError(e.message || 'Search failed')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    search('')
    fetchInstalled()
  }, [])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    search(query)
  }

  const install = async (skillId: string, name: string) => {
    setInstalling(skillId)
    setError('')
    try {
      const r = await fetch('/api/skills/install', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skill_id: skillId, allow_community: allowCommunity }),
      })
      const data = await r.json()
      if (!r.ok) {
        setError(data.detail || 'Install failed')
      } else {
        showToast(`✓ ${name} installed successfully`)
        fetchInstalled()
        // Mark as installed in results
        setResults(prev => prev.map(s => s.id === skillId ? { ...s, installed: true } : s))
      }
    } catch (e: any) {
      setError(e.message || 'Install failed')
    } finally {
      setInstalling(null)
    }
  }

  const remove = async (skillId: string, name: string) => {
    setRemovingId(skillId)
    try {
      const r = await fetch(`/api/skills/${skillId}`, {
        method: 'DELETE',
        credentials: 'include',
      })
      if (r.ok) {
        showToast(`${name} removed`)
        setInstalled(prev => prev.filter(s => s.id !== skillId))
        setResults(prev => prev.map(s => s.id === skillId ? { ...s, installed: false } : s))
      }
    } catch { /* non-fatal */ } finally {
      setRemovingId(null)
    }
  }

  const installedIds = new Set(installed.map(s => s.id))

  return (
    <div className="fade-up" style={{ padding: '0 0 48px' }}>

      {/* Header */}
      <div style={{ padding: '24px 20px 16px' }}>
        <div style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--text-3)' }}>
          Skills
        </div>
        <div style={{ fontSize: 28, fontWeight: 700, letterSpacing: '-0.03em', marginTop: 4 }}>
          ClawHub Marketplace
        </div>
        <div style={{ color: 'var(--text-2)', fontSize: 14, marginTop: 6, maxWidth: 560 }}>
          Browse 13,000+ skills from ClawHub. Every install is signature-verified and sandbox-tested.
          Unverified skills are flagged — you choose the trust level.
        </div>
      </div>

      {/* Security notice */}
      <div style={{ padding: '0 20px 16px' }}>
        <div style={{
          background: 'rgba(124, 106, 245, 0.08)',
          border: '1px solid rgba(124, 106, 245, 0.25)',
          borderRadius: 10,
          padding: '12px 16px',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
        }}>
          <span style={{ fontSize: 18 }}>🔐</span>
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#a78bfa' }}>Ed25519 signature verification active</div>
            <div style={{ fontSize: 11, color: 'var(--text-2)', marginTop: 2 }}>
              ClawOS-verified skills are signed with Ed25519. Community skills are sandbox-tested before activation.
              Skills cannot access OS, subprocess, or network without explicit permission.
            </div>
          </div>
          <label style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', flexShrink: 0, fontSize: 12, color: 'var(--text-2)' }}>
            <input
              type="checkbox"
              checked={allowCommunity}
              onChange={e => setAllowCommunity(e.target.checked)}
              style={{ accentColor: '#7c6af5' }}
            />
            Allow community
          </label>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ padding: '0 20px 12px', display: 'flex', gap: 8 }}>
        {(['browse', 'installed'] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`btn${tab === t ? ' primary' : ''}`}
            style={{ fontSize: 12 }}
          >
            {t === 'browse' ? 'Browse ClawHub' : `Installed (${installed.length})`}
          </button>
        ))}
      </div>

      {/* Toast */}
      {toast && (
        <div style={{
          position: 'fixed', bottom: 24, right: 24, zIndex: 50,
          background: 'var(--panel-solid)', border: '1px solid var(--border)',
          borderRadius: 10, padding: '12px 18px',
          color: 'var(--green)', fontSize: 13, fontWeight: 600,
          boxShadow: '0 4px 24px rgba(0,0,0,0.4)',
        }}>
          {toast}
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={{ padding: '0 20px 12px' }}>
          <div style={{
            background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.3)',
            borderRadius: 8, padding: '10px 14px',
            color: 'var(--red)', fontSize: 12,
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            {error}
            <button onClick={() => setError('')} style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}>✕</button>
          </div>
        </div>
      )}

      {tab === 'browse' && (
        <>
          {/* Search */}
          <form onSubmit={handleSearch} style={{ padding: '0 20px 16px', display: 'flex', gap: 8 }}>
            <input
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Search skills… e.g. weather, calendar, github"
              style={{ flex: 1 }}
            />
            <button className="btn primary" type="submit" disabled={loading}>
              {loading ? 'Searching...' : 'Search'}
            </button>
          </form>

          {/* Results grid */}
          <div style={{ padding: '0 20px', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 12 }}>
            {results.length === 0 && !loading && (
              <div style={{ gridColumn: '1/-1', textAlign: 'center', padding: '48px 0', color: 'var(--text-3)' }}>
                No skills found. Try a different search term.
              </div>
            )}
            {results.map(skill => {
              const isInstalled = installedIds.has(skill.id)
              const isInstalling = installing === skill.id
              return (
                <div
                  key={skill.id}
                  style={{
                    background: 'var(--panel)',
                    border: '1px solid var(--border)',
                    borderRadius: 12,
                    padding: 16,
                    display: 'grid',
                    gap: 10,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 2 }}>{skill.name}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-3)' }}>by {skill.author} · v{skill.version}</div>
                    </div>
                    <TrustBadge tier={skill.trust_tier} />
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-2)', lineHeight: 1.55 }}>
                    {skill.description}
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    {skill.category && (
                      <span style={{
                        fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.1em',
                        color: 'var(--text-3)', background: 'var(--surface)', borderRadius: 4, padding: '2px 6px',
                      }}>
                        {skill.category}
                      </span>
                    )}
                    {skill.stars !== undefined && (
                      <span style={{ fontSize: 11, color: 'var(--text-3)', marginLeft: 'auto' }}>
                        ★ {skill.stars.toLocaleString()}
                      </span>
                    )}
                  </div>
                  <button
                    className={`btn${isInstalled ? '' : ' primary'}`}
                    style={{ fontSize: 12 }}
                    disabled={isInstalling || isInstalled}
                    onClick={() => install(skill.id, skill.name)}
                  >
                    {isInstalling ? 'Installing...' : isInstalled ? '✓ Installed' : 'Install'}
                  </button>
                </div>
              )
            })}
          </div>
        </>
      )}

      {tab === 'installed' && (
        <div style={{ padding: '0 20px' }}>
          {installed.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text-3)' }}>
              No skills installed yet. Browse ClawHub to install your first skill.
            </div>
          ) : (
            <div style={{ display: 'grid', gap: 10 }}>
              {installed.map(skill => (
                <div
                  key={skill.id}
                  style={{
                    background: 'var(--panel)',
                    border: '1px solid var(--border)',
                    borderRadius: 12,
                    padding: '14px 16px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 14,
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: 14 }}>{skill.name}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 3 }}>
                      v{skill.version} · by {skill.author} · installed {skill.installed_at?.slice(0, 10)}
                    </div>
                  </div>
                  <TrustBadge tier={skill.trust_tier as any} />
                  <button
                    className="btn"
                    style={{ fontSize: 12 }}
                    disabled={removingId === skill.id}
                    onClick={() => remove(skill.id, skill.name)}
                  >
                    {removingId === skill.id ? 'Removing...' : 'Remove'}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function TrustBadge({ tier }: { tier: 'clawos_verified' | 'community' | 'local' }) {
  const colors: Record<string, { bg: string; text: string; label: string }> = {
    clawos_verified: { bg: 'rgba(34,197,94,0.12)', text: '#22c55e', label: 'Verified' },
    community: { bg: 'rgba(251,191,36,0.12)', text: '#fbbf24', label: 'Community' },
    local: { bg: 'rgba(147,197,253,0.12)', text: '#93c5fd', label: 'Local' },
  }
  const c = colors[tier] || colors.community
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase',
      background: c.bg, color: c.text, borderRadius: 4, padding: '3px 7px', flexShrink: 0,
    }}>
      {c.label}
    </span>
  )
}

export default SkillsPage
