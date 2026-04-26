/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { useEffect, useRef, useState } from 'react'
import { commandCenterApi, type MorningBriefing } from '../lib/commandCenterApi'

function MiniEQ({ active }: { active: boolean }) {
  const ref = useRef<HTMLDivElement>(null)
  const rafRef = useRef(0)
  useEffect(() => {
    const wrap = ref.current; if (!wrap) return
    const bars = Array.from(wrap.children) as HTMLElement[]
    const tick = (t: number) => {
      bars.forEach((bar, i) => {
        const base = active ? 10 : 3, amp = active ? 10 : 1.5
        const v = base + Math.sin(t / 200 + i * 0.5) * amp + (active ? Math.random() * 4 : 0)
        bar.style.height = `${Math.max(2, Math.min(22, v))}px`
      })
      rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafRef.current)
  }, [active])
  return (
    <div className="mini-eq" ref={ref}>
      {Array.from({ length: 16 }, (_, i) => <div key={i} className="b" />)}
    </div>
  )
}

const STATIC_CALENDAR = [
  { time: '09:30', title: 'Design review · meet.google.com' },
  { time: '11:00', title: 'PR triage · clawOS repo' },
  { time: '14:15', title: 'Focus block · 90 min' },
  { time: '19:00', title: 'Dinner · Izakaya Roku' },
]

export function MorningBriefingPage() {
  const [now, setNow] = useState(new Date())
  const [speaking, setSpeaking] = useState(true)
  const [data, setData] = useState<MorningBriefing | null>(null)

  useEffect(() => {
    const iv = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(iv)
  }, [])

  useEffect(() => {
    const t = setTimeout(() => setSpeaking(false), 8000)
    return () => clearTimeout(t)
  }, [])

  useEffect(() => {
    commandCenterApi.getMorningBriefing().then(setData).catch(() => {})
  }, [])

  const timeStr = now.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: false })
  const dateStr = now.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })

  const calEvents = (data?.calendar?.events?.length ? data.calendar.events : STATIC_CALENDAR)
  const diskPct = data?.system?.disk_pct ?? 82
  const ramTotal = data?.system?.ram_total_gb ?? 32
  const ramUsed = data?.system?.ram_used_gb ?? 14.2
  const approvalCount = data?.approvals?.count ?? 2
  const approvalItems = data?.approvals?.items ?? []
  const nodeCount = data?.brain?.node_count ?? 0
  const edgeCount = data?.brain?.edge_count ?? 0
  const weatherTemp = data?.weather?.temp != null ? `${Math.round(data.weather.temp)}°` : '14°'
  const weatherDesc = data?.weather?.desc ?? 'Light rain after 3pm'
  const servicesUp = data?.system?.services_up ?? 0
  const servicesTotal = data?.system?.services_total ?? 0

  return (
    <div style={{ flex: 1, height: '100%', overflow: 'hidden', position: 'relative' }}>
      <div className="orb-mini">
        <div className="orb-mini-ring" />
        <div className="orb-mini-core" />
      </div>
      <MiniEQ active={speaking} />

      <div className="briefing">
        <div className="bf-hero">
          <div className="bf-time">{timeStr}</div>
          <div className="bf-date">{dateStr}</div>
          <div className="bf-greeting">
            Good morning. Here's where you left off and what's ahead today.
          </div>
        </div>

        <div className="briefing-cards">
          {/* Session continuity — wide */}
          <div className="bcard wide">
            <div className="accent-bar" style={{ background: 'var(--accent)' }} />
            <h3><span className="bcard-icon">◐</span>Where you left off</h3>
            <div className="bcard-items">
              <div className="bcard-item">
                <span className="t">23:48</span>
                <div className="body">
                  <strong>clawOS PR #142 — policy engine refactor</strong><br />
                  You were reviewing the Merkle chain migration. 3 inline comments saved, 1 pending approval. TODO: "verify backward compat with v0.0.9 audit logs."
                </div>
              </div>
              <div className="bcard-item">
                <span className="t">23:22</span>
                <div className="body">
                  <strong>Jazz theory notes</strong> — Added modal interchange section. Kizuna linked it to Coltrane's "Giant Steps" changes automatically.
                </div>
              </div>
            </div>
            <div className="bf-sources">
              <span className="bf-src">memd · session</span>
              <span className="bf-src">kizuna · auto</span>
            </div>
          </div>

          {/* Calendar */}
          <div className="bcard">
            <div className="accent-bar" style={{ background: 'oklch(72% 0.18 220)' }} />
            <h3><span className="bcard-icon">▤</span>Today's calendar</h3>
            <div className="bcard-items">
              {calEvents.slice(0, 4).map((ev, i) => (
                <div key={i} className="bcard-item">
                  <span className="t">{ev.time}</span>
                  <div className="body"><strong>{ev.title}</strong></div>
                </div>
              ))}
            </div>
            {data?.calendar?.source && (
              <div className="bf-sources"><span className="bf-src">{data.calendar.source === 'live' ? 'calendar · live' : 'calendar · demo'}</span></div>
            )}
          </div>

          {/* Git */}
          <div className="bcard">
            <div className="accent-bar" style={{ background: 'oklch(78% 0.19 145)' }} />
            <h3><span className="bcard-icon">⌥</span>Overnight git</h3>
            <div className="bcard-items">
              <div className="bcard-item"><span className="t">repo</span><div className="body"><strong>clawos</strong> — 3 new commits on main, 2 open PRs</div></div>
              <div className="bcard-item"><span className="t">repo</span><div className="body"><strong>openclaw</strong> — Marco merged the A2A federation patch</div></div>
              <div className="bcard-item"><span className="t">ci</span><div className="body">All checks passing <span className="bcard-tag tag-ok">GREEN</span></div></div>
            </div>
          </div>

          {/* System health */}
          <div className="bcard">
            <div className="accent-bar" style={{ background: 'var(--accent)' }} />
            <h3><span className="bcard-icon">◈</span>System health</h3>
            <div className="bcard-stats">
              <div className="bcard-stat"><div className="s-v">{ramTotal}<span className="u">GB</span></div><div className="s-k">RAM</div></div>
              <div className="bcard-stat"><div className="s-v">{ramUsed}<span className="u">GB</span></div><div className="s-k">Used</div></div>
              <div className="bcard-stat"><div className="s-v">{diskPct}<span className="u">%</span></div><div className="s-k">Disk</div></div>
            </div>
            <div className="bcard-pbar"><div className="f" style={{ width: `${diskPct}%`, background: diskPct > 80 ? 'var(--warn)' : 'var(--accent)' }} /></div>
            {diskPct > 80 && (
              <div style={{ marginTop: 8, fontSize: 12, color: 'var(--warn)' }}>
                ⚠ Disk at {diskPct}%. Want me to scan for pruneable files?
              </div>
            )}
            {servicesTotal > 0 && (
              <div style={{ marginTop: 8, fontSize: 12, color: 'var(--ink-3)' }}>
                {servicesUp}/{servicesTotal} services up
              </div>
            )}
          </div>

          {/* Approvals */}
          <div className="bcard">
            <div className="accent-bar" style={{ background: 'var(--warn)' }} />
            <h3><span className="bcard-icon">▢</span>Pending approvals <span className="bcard-tag tag-warn">{approvalCount}</span></h3>
            <div className="bcard-items">
              {approvalItems.length > 0 ? approvalItems.slice(0, 3).map((item: any, i: number) => (
                <div key={i} className="bcard-item">
                  <span className="t" style={{ color: 'var(--warn)' }}>{item.trust_lane?.toUpperCase() || 'MED'}</span>
                  <div className="body"><strong>{item.tool || item.action || 'action'}</strong>{item.description ? ` · ${item.description}` : ''}</div>
                </div>
              )) : (
                <>
                  <div className="bcard-item">
                    <span className="t" style={{ color: 'var(--danger)' }}>HIGH</span>
                    <div className="body"><strong>shell.exec</strong> · rm -rf ~/downloads/old</div>
                  </div>
                  <div className="bcard-item">
                    <span className="t" style={{ color: 'var(--warn)' }}>MED</span>
                    <div className="body"><strong>file.write</strong> · policy.toml — adding curl to auto-allow</div>
                  </div>
                </>
              )}
            </div>
            <div style={{ marginTop: 10 }}>
              <a href="/approvals" className="btn" style={{ fontSize: 11, padding: '6px 12px', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 6 }}>Review queue →</a>
            </div>
          </div>

          {/* Brain */}
          <div className="bcard">
            <div className="accent-bar" style={{ background: 'oklch(70% 0.22 330)' }} />
            <h3><span className="bcard-icon">❋</span>Brain overnight</h3>
            <div className="bcard-items">
              {nodeCount > 0 ? (
                <>
                  <div className="bcard-item"><span className="t">{nodeCount}</span><div className="body">Nodes in graph</div></div>
                  <div className="bcard-item"><span className="t">{edgeCount}</span><div className="body">Connections mapped</div></div>
                </>
              ) : (
                <>
                  <div className="bcard-item"><span className="t">+142</span><div className="body">New facts ingested from tokyo_trip_notes.zip</div></div>
                  <div className="bcard-item"><span className="t">+8</span><div className="body">Auto-inferred connections by Jarvis</div></div>
                </>
              )}
              <div className="bcard-item"><span className="t">gap</span><div className="body">"Stoicism" cluster is isolated — want me to find links? <span className="bcard-tag tag-warn">GAP</span></div></div>
            </div>
          </div>

          {/* Messages */}
          <div className="bcard">
            <div className="accent-bar" style={{ background: 'oklch(78% 0.15 150)' }} />
            <h3><span className="bcard-icon">✉</span>Messages</h3>
            <div className="bcard-items">
              <div className="bcard-item"><span className="t">sarah</span><div className="body">"See you tonight! I booked 7pm at Roku" · 22:14</div></div>
              <div className="bcard-item"><span className="t">ben</span><div className="body">"Happy birthday next week! What do you want?" · 21:30</div></div>
              <div className="bcard-item"><span className="t">marco</span><div className="body">"A2A patch merged, federation tests passing ✓" · 20:45</div></div>
            </div>
          </div>

          {/* Weather — wide */}
          <div className="bcard wide">
            <div className="accent-bar" style={{ background: 'oklch(78% 0.14 185)' }} />
            <h3><span className="bcard-icon">◌</span>Weather</h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginTop: 4 }}>
              <div style={{ fontSize: 36, fontWeight: 200 }}>{weatherTemp}</div>
              <div style={{ fontSize: 12, color: 'var(--ink-2)', lineHeight: 1.6 }}>
                {weatherDesc}<br />
                {data?.weather?.source === 'live'
                  ? <span style={{ color: 'var(--ink-3)' }}>Live via Open-Meteo.</span>
                  : <span style={{ color: 'var(--ink-3)' }}>I added your umbrella to the evening checklist.</span>
                }
              </div>
            </div>
          </div>
        </div>

        <div className="briefing-bottom">
          <button className="btn btn-primary">◉ "Hey Claw" — talk to me</button>
          <a href="/" className="btn" style={{ textDecoration: 'none' }}>Open dashboard</a>
          <a href="/" className="btn" style={{ textDecoration: 'none' }}>Dismiss briefing</a>
        </div>
      </div>
    </div>
  )
}
