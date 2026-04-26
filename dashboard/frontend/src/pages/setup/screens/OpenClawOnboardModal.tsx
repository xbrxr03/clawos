/* SPDX-License-Identifier: AGPL-3.0-or-later */
/*
 * OpenClawOnboardModal — 7-step guided GUI replacement for `openclaw onboard`.
 * Triggered from FrameworkScreen when the user selects OpenClaw.
 * Each step calls a /api/setup/openclaw/* endpoint and writes config directly,
 * so the user never needs to touch a terminal.
 */
import { useEffect, useRef, useState } from 'react'

/* ─── API helpers ─────────────────────────────────────────────────────────── */
const H = { 'X-ClawOS-Setup': '1', 'Content-Type': 'application/json' }

async function ocPost(path: string, body?: Record<string, unknown>) {
  const r = await fetch(`/api/setup/openclaw/${path}`, {
    method: 'POST',
    headers: H,
    body: body ? JSON.stringify(body) : undefined,
  })
  return r.json()
}

async function ocGet(path: string) {
  const r = await fetch(`/api/setup/openclaw/${path}`, { headers: H })
  return r.json()
}

/* ─── Hardware RAM detection ─────────────────────────────────────────────── */
type HardwareTier = 'high' | 'mid' | 'low'

function tierFromRam(ramGb: number | undefined): HardwareTier {
  if (!ramGb) return 'mid'
  if (ramGb >= 32) return 'high'
  if (ramGb >= 16) return 'mid'
  return 'low'
}

function localModelForTier(tier: HardwareTier): string {
  if (tier === 'high') return 'qwen3:14b'
  if (tier === 'mid') return 'qwen3:9b'
  return 'qwen2.5:3b'
}

/* ─── Types ──────────────────────────────────────────────────────────────── */
type ProviderChoice = 'ollama_cloud' | 'ollama_local' | 'other'
type OtherProvider = 'anthropic' | 'openai' | 'openrouter'
type Step = 1 | 2 | 3 | 4 | 5 | 6 | 7

interface Props {
  ramGb?: number
  selectedModel?: string
  onDone: () => void
  onDismiss: () => void
}

/* ─── Log line component ─────────────────────────────────────────────────── */
function LogLines({ lines }: { lines: string[] }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight
  }, [lines])
  return (
    <div
      ref={ref}
      style={{
        fontFamily: 'var(--mono)',
        fontSize: 11,
        color: 'var(--ink-2)',
        background: 'var(--surface-2)',
        borderRadius: 6,
        padding: '10px 14px',
        maxHeight: 160,
        overflowY: 'auto',
        marginTop: 16,
        lineHeight: 1.6,
      }}
    >
      {lines.map((l, i) => (
        <div key={i}>{l}</div>
      ))}
      {lines.length === 0 && <div style={{ color: 'var(--ink-4)' }}>Starting…</div>}
    </div>
  )
}

/* ─── CLI escape hatch ───────────────────────────────────────────────────── */
function CliEscape() {
  const [open, setOpen] = useState(false)
  return (
    <div style={{ marginTop: 24, textAlign: 'center' }}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          background: 'none',
          border: 'none',
          color: 'var(--ink-3)',
          fontSize: 12,
          cursor: 'pointer',
          textDecoration: 'underline',
        }}
      >
        Prefer the terminal?
      </button>
      {open && (
        <div
          style={{
            marginTop: 10,
            background: 'var(--surface-2)',
            borderRadius: 6,
            padding: '10px 16px',
            fontSize: 12,
            fontFamily: 'var(--mono)',
            position: 'relative',
            textAlign: 'left',
          }}
        >
          <code style={{ color: 'var(--accent)' }}>openclaw onboard</code>
          <button
            onClick={() => navigator.clipboard.writeText('openclaw onboard')}
            style={{
              position: 'absolute',
              right: 10,
              top: 8,
              background: 'var(--surface-3)',
              border: 'none',
              borderRadius: 4,
              color: 'var(--ink-2)',
              fontSize: 11,
              padding: '2px 8px',
              cursor: 'pointer',
            }}
          >
            copy
          </button>
          <div style={{ color: 'var(--ink-3)', marginTop: 6, fontFamily: 'var(--sans, sans-serif)' }}>
            This covers all setup steps. Run it in your terminal, then come back here.
          </div>
        </div>
      )}
    </div>
  )
}

/* ─── Step pill indicator ────────────────────────────────────────────────── */
function StepPills({ current, total }: { current: Step; total: number }) {
  return (
    <div style={{ display: 'flex', gap: 6, justifyContent: 'center', marginBottom: 24 }}>
      {Array.from({ length: total }, (_, i) => (
        <div
          key={i}
          style={{
            width: i + 1 === current ? 20 : 8,
            height: 4,
            borderRadius: 2,
            background: i + 1 <= current ? 'var(--accent)' : 'var(--surface-3)',
            transition: 'all 0.2s',
          }}
        />
      ))}
    </div>
  )
}

/* ─── Modal ──────────────────────────────────────────────────────────────── */
export function OpenClawOnboardModal({ ramGb, selectedModel, onDone, onDismiss }: Props) {
  const tier = tierFromRam(ramGb)
  const defaultLocalModel = localModelForTier(tier)
  const TOTAL = 7

  const [step, setStep] = useState<Step>(1)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [log, setLog] = useState<string[]>([])

  // Step 2 — Provider
  const [provider, setProvider] = useState<ProviderChoice>('ollama_cloud')
  const [ollamaUrl, setOllamaUrl] = useState('http://127.0.0.1:11434')
  const [model, setModel] = useState(selectedModel || 'kimi-k2.5')
  const [apiKey, setApiKey] = useState('')
  const [otherProvider, setOtherProvider] = useState<OtherProvider>('anthropic')
  const [otherModel, setOtherModel] = useState('claude-opus-4-7')

  // Step 3 — Workspace
  const [workspace, setWorkspace] = useState('~/.openclaw/workspace')

  // Step 4 — Gateway
  const [port, setPort] = useState(18789)
  const [autostart, setAutostart] = useState(true)

  // Step 5 — Channels
  const [channels, setChannels] = useState<Record<string, string>>({})
  const [channelOpen, setChannelOpen] = useState<Record<string, boolean>>({})

  // Step 7 — Health
  const [healthy, setHealthy] = useState<boolean | null>(null)

  const addLog = (line: string) => setLog((l) => [...l, line])

  /* Step 1 — auto-install on mount */
  useEffect(() => {
    let cancelled = false
    setErr('')
    addLog('Fetching openclaw from npm registry…')
    ocPost('install').then((res) => {
      if (cancelled) return
      if (res?.ok) {
        addLog('✓ OpenClaw installed')
        setTimeout(() => setStep(2), 600)
      } else {
        addLog(`✕ ${res?.message || 'Install failed'}`)
        setErr(res?.message || 'Install failed. Check npm is available.')
      }
    }).catch((e: unknown) => {
      if (!cancelled) {
        const msg = e instanceof Error ? e.message : String(e)
        addLog(`✕ ${msg}`)
        setErr(msg)
      }
    })
    return () => { cancelled = true }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  /* Step 2 — confirm provider */
  async function confirmProvider() {
    setBusy(true); setErr('')
    const body = provider === 'ollama_cloud'
      ? { provider: 'ollama_cloud', model: 'kimi-k2.5', ollama_url: 'https://api.ollama.com', api_key: apiKey }
      : provider === 'ollama_local'
        ? { provider: 'ollama_local', model, ollama_url: ollamaUrl }
        : { provider: otherProvider, model: otherModel, api_key: apiKey }
    const res = await ocPost('configure', body).catch(() => null)
    setBusy(false)
    if (res?.ok) setStep(3); else setErr(res?.message || 'Configure failed')
  }

  /* Step 3 — workspace */
  async function confirmWorkspace() {
    setBusy(true); setErr('')
    const res = await ocPost('configure', { workspace_path: workspace.replace('~', '') }).catch(() => null)
    setBusy(false)
    if (res?.ok) setStep(4); else setErr(res?.message || 'Workspace setup failed')
  }

  /* Step 4 — start gateway */
  async function startGateway() {
    setBusy(true); setErr('')
    const res = await ocPost('start', { port, autostart }).catch(() => null)
    setBusy(false)
    if (res?.ok) setStep(5); else setErr(res?.message || 'Gateway start failed')
  }

  /* Step 5 — channels (skippable) */
  async function saveChannels() {
    setBusy(true); setErr('')
    const res = await ocPost('configure', { channels }).catch(() => null)
    setBusy(false)
    if (res?.ok) setStep(6); else setErr(res?.message || 'Channel config failed')
  }

  /* Step 6 — skills (skippable) */
  async function installSkills() {
    setBusy(true); setErr('')
    const res = await ocPost('skills').catch(() => null)
    setBusy(false)
    if (res?.ok) goToDone(); else setErr(res?.message || 'Skills install failed')
  }

  /* Step 7 — health check then done */
  async function goToDone() {
    const res = await ocGet('health').catch(() => null)
    setHealthy(res?.running ?? false)
    setStep(7)
  }

  /* Channel helpers */
  const CHANNEL_LIST = [
    { id: 'discord', label: 'Discord', placeholder: 'Bot token' },
    { id: 'slack', label: 'Slack', placeholder: 'Bot token' },
    { id: 'telegram', label: 'Telegram', placeholder: 'Bot token' },
    { id: 'teams', label: 'Microsoft Teams', placeholder: 'Webhook URL' },
  ]

  const modalStyle: React.CSSProperties = {
    position: 'fixed', inset: 0, zIndex: 9999,
    background: 'var(--surface)',
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    justifyContent: 'flex-start',
    overflowY: 'auto',
    padding: '40px 24px 60px',
  }

  const cardStyle: React.CSSProperties = {
    width: '100%', maxWidth: 560,
    display: 'flex', flexDirection: 'column',
  }

  const inputStyle: React.CSSProperties = {
    width: '100%', background: 'var(--surface-2)',
    border: '1px solid var(--border)', borderRadius: 6,
    color: 'var(--ink-1)', padding: '8px 12px',
    fontSize: 13, fontFamily: 'var(--mono)',
    boxSizing: 'border-box',
  }

  const btnPrimary: React.CSSProperties = {
    background: 'var(--accent)', color: '#fff',
    border: 'none', borderRadius: 6, padding: '10px 24px',
    fontSize: 14, fontWeight: 600, cursor: busy ? 'default' : 'pointer',
    opacity: busy ? 0.6 : 1,
  }

  const btnSecondary: React.CSSProperties = {
    background: 'none', color: 'var(--ink-2)',
    border: '1px solid var(--border)', borderRadius: 6, padding: '10px 24px',
    fontSize: 14, cursor: 'pointer',
  }

  const label: React.CSSProperties = {
    fontSize: 12, color: 'var(--ink-3)',
    marginBottom: 4, display: 'block',
  }

  return (
    <div style={modalStyle}>
      {/* Header */}
      <div style={{ width: '100%', maxWidth: 560, display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
        <button onClick={onDismiss} style={{ background: 'none', border: 'none', color: 'var(--ink-3)', fontSize: 20, cursor: 'pointer', lineHeight: 1 }}>✕</button>
      </div>

      <div style={cardStyle}>
        <StepPills current={step} total={TOTAL} />

        {/* ── Step 1: Install ── */}
        {step === 1 && (
          <>
            <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--ink-1)', margin: '0 0 8px' }}>Installing OpenClaw</h2>
            <p style={{ color: 'var(--ink-3)', fontSize: 13, margin: '0 0 4px' }}>Step 1 of {TOTAL}</p>
            <LogLines lines={log} />
            {err && (
              <div style={{ marginTop: 12, color: 'var(--danger, #e05)' }}>
                {err}
                <button onClick={() => { setErr(''); setLog([]); setStep(1) }} style={{ ...btnSecondary, marginLeft: 12, fontSize: 12, padding: '4px 12px' }}>Retry</button>
              </div>
            )}
          </>
        )}

        {/* ── Step 2: AI Provider ── */}
        {step === 2 && (
          <>
            <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--ink-1)', margin: '0 0 4px' }}>Choose a model for OpenClaw</h2>
            <p style={{ color: 'var(--ink-3)', fontSize: 13, margin: '0 0 20px' }}>Step 2 of {TOTAL} · OpenClaw performs best with a high-quality model.</p>

            {/* Ollama Cloud card */}
            {(['ollama_cloud', 'ollama_local', 'other'] as ProviderChoice[]).map((p) => (
              <div
                key={p}
                onClick={() => setProvider(p)}
                style={{
                  border: `1.5px solid ${provider === p ? 'var(--accent)' : 'var(--border)'}`,
                  borderRadius: 8, padding: '14px 16px', marginBottom: 10, cursor: 'pointer',
                  background: provider === p ? 'color-mix(in srgb, var(--accent) 8%, var(--surface))' : 'var(--surface-2)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--ink-1)' }}>
                    {p === 'ollama_cloud' && 'Ollama Cloud · kimi-k2.5'}
                    {p === 'ollama_local' && 'Local model'}
                    {p === 'other' && 'Other cloud'}
                  </div>
                  {p === 'ollama_cloud' && (
                    <span style={{ fontSize: 10, background: 'var(--accent)', color: '#fff', borderRadius: 4, padding: '1px 6px', fontWeight: 700 }}>RECOMMENDED</span>
                  )}
                </div>
                <div style={{ fontSize: 12, color: 'var(--ink-3)', marginTop: 3 }}>
                  {p === 'ollama_cloud' && 'Best performance · Ollama Pro or free tier · paste your Ollama API key'}
                  {p === 'ollama_local' && (
                    tier === 'low'
                      ? '⚠ Local models on <16GB RAM struggle with agentic tasks — cloud is recommended'
                      : `Runs ${defaultLocalModel} locally · no API key · slower than cloud`
                  )}
                  {p === 'other' && 'Anthropic · OpenAI · OpenRouter'}
                </div>

                {/* Expanded inputs when selected */}
                {provider === p && (
                  <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 8 }} onClick={(e) => e.stopPropagation()}>
                    {p === 'ollama_cloud' && (
                      <>
                        <label style={label}>Ollama API key <a href="https://ollama.com/settings/keys" target="_blank" rel="noreferrer" style={{ color: 'var(--accent)' }}>ollama.com/settings</a></label>
                        <input style={inputStyle} type="password" placeholder="sk-ollama-…" value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
                      </>
                    )}
                    {p === 'ollama_local' && (
                      <>
                        <label style={label}>Model</label>
                        <input style={inputStyle} value={model} onChange={(e) => setModel(e.target.value)} placeholder={defaultLocalModel} />
                        <label style={label}>Ollama URL</label>
                        <input style={inputStyle} value={ollamaUrl} onChange={(e) => setOllamaUrl(e.target.value)} />
                      </>
                    )}
                    {p === 'other' && (
                      <>
                        <label style={label}>Provider</label>
                        <select style={inputStyle} value={otherProvider} onChange={(e) => setOtherProvider(e.target.value as OtherProvider)}>
                          <option value="anthropic">Anthropic</option>
                          <option value="openai">OpenAI</option>
                          <option value="openrouter">OpenRouter</option>
                        </select>
                        <label style={label}>API key</label>
                        <input style={inputStyle} type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="sk-…" />
                        <label style={label}>Model</label>
                        <input style={inputStyle} value={otherModel} onChange={(e) => setOtherModel(e.target.value)} />
                      </>
                    )}
                  </div>
                )}
              </div>
            ))}

            <div style={{ fontSize: 11, color: 'var(--ink-4)', marginTop: 4, marginBottom: 16 }}>
              ClawOS itself (JARVIS, voice, workflows) always runs locally — no API keys required. This model is only used by OpenClaw.
            </div>

            {err && <div style={{ color: 'var(--danger, #e05)', fontSize: 13, marginBottom: 8 }}>{err}</div>}
            <div style={{ display: 'flex', gap: 10 }}>
              <button style={btnSecondary} onClick={() => setStep(1)}>← Back</button>
              <button style={btnPrimary} disabled={busy} onClick={confirmProvider}>{busy ? 'Saving…' : 'Confirm'}</button>
            </div>
          </>
        )}

        {/* ── Step 3: Workspace ── */}
        {step === 3 && (
          <>
            <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--ink-1)', margin: '0 0 4px' }}>Set your workspace</h2>
            <p style={{ color: 'var(--ink-3)', fontSize: 13, margin: '0 0 20px' }}>Step 3 of {TOTAL} · Where OpenClaw stores your agent's memory, skills, and session files.</p>
            <label style={label}>Workspace path</label>
            <input style={{ ...inputStyle, marginBottom: 20 }} value={workspace} onChange={(e) => setWorkspace(e.target.value)} />
            {err && <div style={{ color: 'var(--danger, #e05)', fontSize: 13, marginBottom: 8 }}>{err}</div>}
            <div style={{ display: 'flex', gap: 10 }}>
              <button style={btnSecondary} onClick={() => setStep(2)}>← Back</button>
              <button style={btnPrimary} disabled={busy} onClick={confirmWorkspace}>{busy ? 'Saving…' : 'Continue'}</button>
            </div>
          </>
        )}

        {/* ── Step 4: Gateway ── */}
        {step === 4 && (
          <>
            <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--ink-1)', margin: '0 0 4px' }}>Start the OpenClaw gateway</h2>
            <p style={{ color: 'var(--ink-3)', fontSize: 13, margin: '0 0 20px' }}>Step 4 of {TOTAL} · The gateway routes messages between you and your OpenClaw agents.</p>
            <label style={label}>Gateway port</label>
            <input style={{ ...inputStyle, marginBottom: 12 }} type="number" value={port} onChange={(e) => setPort(Number(e.target.value))} />
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--ink-2)', marginBottom: 20, cursor: 'pointer' }}>
              <input type="checkbox" checked={autostart} onChange={(e) => setAutostart(e.target.checked)} />
              Start automatically on login
            </label>
            {err && <div style={{ color: 'var(--danger, #e05)', fontSize: 13, marginBottom: 8 }}>{err}</div>}
            <div style={{ display: 'flex', gap: 10 }}>
              <button style={btnSecondary} onClick={() => setStep(3)}>← Back</button>
              <button style={btnPrimary} disabled={busy} onClick={startGateway}>{busy ? 'Starting…' : 'Start Gateway'}</button>
            </div>
          </>
        )}

        {/* ── Step 5: Channels ── */}
        {step === 5 && (
          <>
            <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--ink-1)', margin: '0 0 4px' }}>Connect your channels</h2>
            <p style={{ color: 'var(--ink-3)', fontSize: 13, margin: '0 0 20px' }}>Step 5 of {TOTAL} · Optional — add more from the OpenClaw dashboard anytime.</p>
            {CHANNEL_LIST.map(({ id, label: lbl, placeholder }) => (
              <div key={id} style={{ marginBottom: 10 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--ink-2)', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={!!channelOpen[id]}
                    onChange={(e) => {
                      setChannelOpen((o) => ({ ...o, [id]: e.target.checked }))
                      if (!e.target.checked) setChannels((c) => { const n = { ...c }; delete n[id]; return n })
                    }}
                  />
                  {lbl}
                </label>
                {channelOpen[id] && (
                  <input
                    style={{ ...inputStyle, marginTop: 6 }}
                    placeholder={placeholder}
                    value={channels[id] || ''}
                    onChange={(e) => setChannels((c) => ({ ...c, [id]: e.target.value }))}
                  />
                )}
              </div>
            ))}
            {err && <div style={{ color: 'var(--danger, #e05)', fontSize: 13, marginTop: 8, marginBottom: 4 }}>{err}</div>}
            <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
              <button style={btnSecondary} onClick={() => setStep(4)}>← Back</button>
              <button style={{ ...btnSecondary }} disabled={busy} onClick={() => goToDone()}>Skip</button>
              {Object.keys(channels).length > 0 && (
                <button style={btnPrimary} disabled={busy} onClick={saveChannels}>{busy ? 'Saving…' : 'Save Channels'}</button>
              )}
            </div>
          </>
        )}

        {/* ── Step 6: Skills ── */}
        {step === 6 && (
          <>
            <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--ink-1)', margin: '0 0 4px' }}>Install starter skills</h2>
            <p style={{ color: 'var(--ink-3)', fontSize: 13, margin: '0 0 16px' }}>Step 6 of {TOTAL}</p>
            <div style={{ background: 'var(--surface-2)', borderRadius: 8, padding: '12px 16px', marginBottom: 20, fontSize: 13, color: 'var(--ink-2)', lineHeight: 1.7 }}>
              <div style={{ fontWeight: 600, marginBottom: 6 }}>Recommended skills include:</div>
              <div>· File operations — read, write, move, search</div>
              <div>· Code tools — git, lint, run, diff</div>
              <div>· Web search — fetch, summarise, cite</div>
              <div>· Shell — safe subprocess execution</div>
            </div>
            {err && <div style={{ color: 'var(--danger, #e05)', fontSize: 13, marginBottom: 8 }}>{err}</div>}
            <div style={{ display: 'flex', gap: 10 }}>
              <button style={btnSecondary} onClick={() => setStep(5)}>← Back</button>
              <button style={btnSecondary} disabled={busy} onClick={goToDone}>Skip for now</button>
              <button style={btnPrimary} disabled={busy} onClick={installSkills}>{busy ? 'Installing…' : 'Install recommended'}</button>
            </div>
          </>
        )}

        {/* ── Step 7: Done ── */}
        {step === 7 && (
          <>
            <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--ink-1)', margin: '0 0 4px' }}>OpenClaw is ready</h2>
            <p style={{ color: 'var(--ink-3)', fontSize: 13, margin: '0 0 20px' }}>Step 7 of {TOTAL}</p>

            <div style={{
              background: healthy === false ? 'color-mix(in srgb, var(--danger,#e05) 10%, var(--surface))' : 'color-mix(in srgb, var(--success,#0c8) 10%, var(--surface))',
              border: `1px solid ${healthy === false ? 'var(--danger,#e05)' : 'var(--success,#0c8)'}`,
              borderRadius: 8, padding: '12px 16px', marginBottom: 24, fontSize: 13,
            }}>
              {healthy === null && 'Checking gateway…'}
              {healthy === true && `✓ Gateway running on port ${port}`}
              {healthy === false && `⚠ Gateway not responding on port ${port}. Try: clawctl framework start openclaw`}
            </div>

            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <button
                style={{ ...btnPrimary, flex: 1 }}
                onClick={() => window.open(`http://localhost:${port}`, '_blank')}
              >
                Open OpenClaw →
              </button>
              <button style={{ ...btnSecondary, flex: 1 }} onClick={onDone}>
                Continue ClawOS Setup
              </button>
            </div>
          </>
        )}

        <CliEscape />
      </div>
    </div>
  )
}
