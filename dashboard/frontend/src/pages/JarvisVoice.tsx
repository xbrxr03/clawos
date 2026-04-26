/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { FormEvent, startTransition, useEffect, useMemo, useRef, useState } from 'react'
import { commandCenterApi, type JarvisConfig, type JarvisHealth, type JarvisSession, type JarvisTurn } from '../lib/commandCenterApi'

const STATIC_TURNS = [
  { id: 's1', role: 'user', source: 'jarvis-ui:voice', text: 'Hey Claw, brief me on this morning.', ts: '08:14' },
  { id: 's2', role: 'assistant', source: 'jarvis-briefing', text: 'Good morning. You have three repos with new activity, two calendar blocks before noon, and the disk scan flagged ~14 GB of old downloads. Shall I clear them?', ts: '08:14' },
  { id: 's3', role: 'user', source: 'jarvis-ui:voice', text: "What's the weather looking like today?", ts: '07:42' },
  { id: 's4', role: 'assistant', source: 'jarvis-briefing', text: 'Light rain after 3pm, 14°C. I added your umbrella to the evening checklist.', ts: '07:42' },
  { id: 's5', role: 'user', source: 'jarvis-ui:voice', text: 'Reply to Sarah: running 10 late.', ts: '22:09' },
  { id: 's6', role: 'assistant', source: 'jarvis-briefing', text: 'Message drafted for Sarah. Queued for send at 08:00 so you are not disturbed.', ts: '22:09' },
]

const STATIC_UPCOMING = [
  { time: '09:30', title: 'Design review · meet.google.com' },
  { time: '11:00', title: 'PR triage · clawos' },
  { time: '14:15', title: 'Focus block · 90 min', dim: true },
]

const DOING_STEPS = [
  'calendar · read upcoming events',
  'git · scan clawos + 2 repos',
  'toolbridge · disk scan ~/downloads',
  'compose briefing · piper tts',
]

function stateLabel(state: string) {
  if (state === 'listening') return 'LISTENING'
  if (state === 'thinking') return 'THINKING'
  if (state === 'speaking') return 'SPEAKING'
  return 'STANDING BY'
}

function srcTag(source: string) {
  if (!source) return 'TEXT'
  if (source.includes('voice')) return 'VOICE'
  if (source.includes('brief') || source.includes('scheduler')) return 'BRIEFING'
  if (source.includes('chat') || source.includes('message')) return 'MSG'
  return 'TEXT'
}

function srcClass(source: string) {
  const tag = srcTag(source)
  if (tag === 'VOICE') return 'voice'
  if (tag === 'BRIEFING') return 'brief'
  if (tag === 'WA') return 'wa'
  return ''
}

function Waveform({ active }: { active: boolean }) {
  const ref = useRef<HTMLDivElement>(null)
  const rafRef = useRef(0)
  useEffect(() => {
    const wrap = ref.current
    if (!wrap) return
    const bars = Array.from(wrap.children) as HTMLElement[]
    let t = 0
    const tick = () => {
      t++
      bars.forEach((bar, i) => {
        const base = active ? 28 : 4
        const amp = active ? 24 : 2
        const h = base + Math.sin(t / 180 + i * 0.3) * amp + Math.sin(t / 90 + i * 0.85) * (amp * 0.45) + (active ? (Math.random() - 0.5) * 8 : 0)
        bar.style.height = `${Math.max(3, Math.min(70, h))}px`
      })
      rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafRef.current)
  }, [active])
  return <div className="jarvis-h-wave" ref={ref}>{Array.from({ length: 60 }, (_, i) => <div key={i} className="b" />)}</div>
}

function buildWsUrl(path: string) {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${window.location.host}${path}`
}

export function JarvisVoicePage({ jarvisSession }: { jarvisSession: JarvisSession }) {
  const [session, setSession] = useState<JarvisSession>(jarvisSession)
  const [health, setHealth] = useState<JarvisHealth | null>(null)
  const [config, setConfig] = useState<JarvisConfig | null>(null)
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState<'talk' | 'send' | null>(null)
  const [txFilter, setTxFilter] = useState('all')
  const [upcoming, setUpcoming] = useState<{ time: string; title: string; dim?: boolean }[]>(STATIC_UPCOMING)
  const [xiKey, setXiKey] = useState('')
  const [xiSaving, setXiSaving] = useState(false)
  const [xiMsg, setXiMsg] = useState('')
  const [xiKeySet, setXiKeySet] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => { startTransition(() => setSession(jarvisSession)) }, [jarvisSession])

  // Load health, config, ElevenLabs status, and upcoming events
  useEffect(() => {
    const load = async () => {
      try {
        const [h, c] = await Promise.all([commandCenterApi.getJarvisHealth(), commandCenterApi.getJarvisConfig()])
        setHealth(h); setConfig(c)
        setXiKeySet(!!(h?.provider_status?.elevenlabs_key_set))
      } catch {}
    }
    void load()
    const id = window.setInterval(() => void load(), 10000)
    return () => window.clearInterval(id)
  }, [])

  // Fetch calendar events from morning briefing for Upcoming panel
  useEffect(() => {
    commandCenterApi.getMorningBriefing()
      .then((b) => {
        if (b?.calendar?.events?.length) {
          setUpcoming(b.calendar.events.slice(0, 4).map((ev, i) => ({ time: ev.time, title: ev.title, dim: i >= 3 })))
        }
      })
      .catch(() => {})
  }, [])

  // Real-time session updates via /ws/jarvis
  useEffect(() => {
    let ws: WebSocket
    let dead = false
    const connect = () => {
      if (dead) return
      try {
        ws = new WebSocket(buildWsUrl('/ws/jarvis'))
        wsRef.current = ws
        ws.onmessage = (ev) => {
          try {
            const msg = JSON.parse(ev.data)
            if (msg.type === 'jarvis_session' && msg.data) {
              startTransition(() => setSession((prev) => ({ ...prev, ...msg.data })))
            }
          } catch {}
        }
        ws.onclose = () => { if (!dead) setTimeout(connect, 3000) }
        ws.onerror = () => ws.close()
      } catch {}
    }
    connect()
    return () => { dead = true; wsRef.current?.close() }
  }, [])

  const state = (session.state as string) || 'idle'
  const caption = state === 'listening'
    ? (session.last_utterance || 'Listening…')
    : (session.live_caption || session.last_response || 'Standing by, Sir.')
  const captionIsJarvis = state !== 'listening'

  const turns = useMemo(() => (session.recent_turns || []).slice().reverse(), [session.recent_turns])
  const displayTurns: any[] = turns.length > 0 ? turns : STATIC_TURNS

  const filteredTurns = txFilter === 'all'
    ? displayTurns
    : displayTurns.filter((t) => srcTag(t.source || '').toLowerCase() === txFilter)

  const orbClass = state === 'listening' ? 'listening' : state === 'thinking' ? 'thinking' : state === 'speaking' ? 'speaking' : ''
  const briefingSources = Object.entries(health?.briefing_sources || {})
  const voiceEnabled = config ? config.voice_enabled !== false : session.voice_enabled !== false

  const runPushToTalk = async () => {
    setBusy('talk')
    try {
      const r = await commandCenterApi.pushToTalkJarvis()
      if ((r as any)?.session) startTransition(() => setSession((r as any).session))
    } catch {} finally { setBusy(null) }
  }

  const sendDraft = async (e?: FormEvent) => {
    e?.preventDefault()
    if (!draft.trim()) return
    setBusy('send')
    try {
      const r = await commandCenterApi.sendJarvisChat(draft.trim())
      if ((r as any)?.session) startTransition(() => setSession((r as any).session))
      setDraft('')
    } catch {} finally { setBusy(null) }
  }

  const saveXiKey = async (e: FormEvent) => {
    e.preventDefault()
    if (!xiKey.trim()) return
    setXiSaving(true); setXiMsg('')
    try {
      const r = await commandCenterApi.setElevenLabsConfig(xiKey.trim(), 'nPczCjzI2devNBz1zQrb')
      if (r.ok) { setXiMsg('ElevenLabs key saved. TTS active.'); setXiKeySet(true); setXiKey('') }
    } catch (err: any) {
      setXiMsg(err.message || 'Failed to save key.')
    } finally { setXiSaving(false) }
  }

  const isActive = state === 'thinking' || state === 'speaking'

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', height: '100%', overflow: 'hidden', flex: 1 }}>
      {/* Hero main */}
      <main className="main" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: '24px 28px' }}>
        <div className="main-head" style={{ marginBottom: 0, flexShrink: 0 }}>
          <div>
            <h1>Jarvis</h1>
            <div className="sub">voice · {state} · {xiKeySet ? 'elevenlabs' : 'piper en_US-lessac'} · whisper · wake "Hey Claw"</div>
          </div>
          <div className="chips">
            <span className="chip">
              <span className="d blink" style={{ background: health?.openclaw_running ? 'var(--success)' : 'var(--ink-3)', color: health?.openclaw_running ? 'var(--success)' : 'var(--ink-3)' }} />
              {health?.openclaw_running ? 'openclaw online' : 'openclaw offline'}
            </span>
            <span className="chip">{xiKeySet ? 'elevenlabs · tts' : 'piper · 22kHz'}</span>
          </div>
        </div>

        <div className="jarvis-h-hero">
          <Waveform active={state === 'listening' || state === 'speaking'} />

          <div className={`jarvis-h-orb ${orbClass}`} onClick={() => void runPushToTalk()}>
            <div className="ring3" />
            <div className="ring" />
            <div className="ring2" />
            <div className="core" />
          </div>

          <div className="jarvis-h-chip">
            <span className="d" />{stateLabel(state)}
          </div>

          <div className={`jarvis-h-caption${captionIsJarvis ? ' jv' : ''}`}>
            {caption}
            {state === 'listening' && <span style={{ animation: 'blink 0.8s infinite' }}>▍</span>}
          </div>
        </div>

        {isActive && (
          <div className="jarvis-h-doing">
            <h4>Currently doing</h4>
            {DOING_STEPS.map((s, i) => (
              <div key={i} className={`step ${i < 2 ? 'done' : i === 2 ? 'active' : ''}`}>
                <span className="si">{i >= 3 ? '·' : ''}</span>
                <span>{s}</span>
              </div>
            ))}
          </div>
        )}

        <form className="jarvis-h-ibar" onSubmit={(e) => void sendDraft(e)}>
          <input
            placeholder="Type to Jarvis, or click the orb to speak"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            disabled={busy !== null}
          />
          <button
            type="button"
            className="jarvis-h-mic"
            onClick={() => void runPushToTalk()}
            disabled={busy !== null || !voiceEnabled}
          >
            {busy === 'talk' ? '…' : '◉'}
          </button>
        </form>
      </main>

      {/* Right rail */}
      <aside className="rail" style={{ background: 'rgba(0,0,0,0.3)', borderLeft: '1px solid var(--panel-br)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div className="jarvis-h-sect">
          <h4>Upcoming</h4>
          {upcoming.map(({ time, title, dim }) => (
            <div key={time} className="jarvis-h-row">
              <span className="k">{time}</span>
              <span className={`v${dim ? ' dim' : ''}`}>{title}</span>
            </div>
          ))}
        </div>

        <div className="jarvis-h-sect">
          <h4>Briefing sources</h4>
          {briefingSources.length > 0 ? briefingSources.map(([key, val]) => (
            <div key={key} className="jarvis-h-row">
              <span className="k">{key}</span>
              <span className="v">{String(val)}</span>
            </div>
          )) : (
            <>
              <div className="jarvis-h-row"><span className="k">calendar</span><span className="v">3 events</span></div>
              <div className="jarvis-h-row"><span className="k">git</span><span className="v">8 commits · 2 PRs</span></div>
              <div className="jarvis-h-row"><span className="k">disk</span><span className="v warn">14 GB pruneable</span></div>
              <div className="jarvis-h-row"><span className="k">memory</span><span className="v">142 new facts</span></div>
            </>
          )}
        </div>

        {/* ElevenLabs key input */}
        <div className="jarvis-h-sect" style={{ borderTop: '1px solid var(--panel-br)', paddingTop: 12 }}>
          <h4>ElevenLabs TTS {xiKeySet && <span style={{ color: 'var(--success)', fontSize: 10, marginLeft: 4 }}>● ACTIVE</span>}</h4>
          <form onSubmit={(e) => void saveXiKey(e)} style={{ display: 'grid', gap: 6 }}>
            <input
              type="password"
              placeholder={xiKeySet ? 'Key saved — paste new to replace' : 'Paste API key…'}
              value={xiKey}
              onChange={(e) => setXiKey(e.target.value)}
              style={{ fontSize: 11, padding: '6px 8px', borderRadius: 6, border: '1px solid var(--panel-br)', background: 'var(--panel)', color: 'var(--ink-1)', fontFamily: 'var(--mono)', width: '100%', boxSizing: 'border-box' }}
            />
            <button type="submit" className="btn" disabled={xiSaving || !xiKey.trim()} style={{ fontSize: 11, padding: '5px 10px' }}>
              {xiSaving ? 'Saving…' : 'Save key'}
            </button>
            {xiMsg && <div style={{ fontSize: 11, color: xiMsg.includes('ailed') ? 'var(--danger)' : 'var(--success)' }}>{xiMsg}</div>}
          </form>
        </div>

        <div className="jarvis-h-thead">
          <h3>Transcript</h3>
          <div className="jarvis-h-tfl">
            {[['all', 'ALL'], ['voice', 'VOICE'], ['text', 'TEXT'], ['brief', 'BRIEF']].map(([k, l]) => (
              <button key={k} className={`f${txFilter === k ? ' sel' : ''}`} onClick={() => setTxFilter(k)}>{l}</button>
            ))}
          </div>
        </div>

        <div className="jarvis-h-feed">
          {filteredTurns.map((turn, i) => (
            <div key={(turn as JarvisTurn).id || i} className="jarvis-h-turn">
              <div className="jarvis-h-turn-meta">
                <span className={`src ${srcClass(turn.source || '')}`}>{srcTag(turn.source || '')}</span>
                <span className="t">{(turn as any).ts || ''}</span>
              </div>
              {turn.role === 'user' ? (
                <div className="you">{turn.text}</div>
              ) : (
                <div className="jv">{turn.text}</div>
              )}
            </div>
          ))}
          {filteredTurns.length === 0 && (
            <div className="empty" style={{ minHeight: 80 }}>
              <div style={{ fontSize: 13 }}>No transcript yet.</div>
            </div>
          )}
        </div>
      </aside>
    </div>
  )
}
