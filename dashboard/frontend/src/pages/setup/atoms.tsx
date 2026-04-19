/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Shared atoms for the ClawOS first-run wizard.
 * Ported from clawOS-handoff (Claude Design) — typed for React 18 + TS 5.8.
 */
import {
  type CSSProperties,
  type MouseEventHandler,
  type ReactNode,
  useEffect,
  useRef,
  useState,
} from 'react'

/* ──────────────────────────────────────────────────────────
   useTypewriter — emits `text` character-by-character.
   ────────────────────────────────────────────────────────── */
export function useTypewriter(text: string, speed = 14, startDelay = 0, active = true): string {
  const [out, setOut] = useState('')
  useEffect(() => {
    if (!active) {
      setOut(text)
      return
    }
    setOut('')
    let i = 0
    const timer = window.setTimeout(() => {
      const iv = window.setInterval(() => {
        i += 1
        setOut(text.slice(0, i))
        if (i >= text.length) window.clearInterval(iv)
      }, speed)
    }, startDelay)
    return () => window.clearTimeout(timer)
  }, [text, speed, startDelay, active])
  return out
}

/* ──────────────────────────────────────────────────────────
   VoiceEQ — animated sine-wave EQ bars.
   ────────────────────────────────────────────────────────── */
export function VoiceEQ({
  active = true,
  bars = 48,
  intensity = 1,
}: {
  active?: boolean
  bars?: number
  intensity?: number
}) {
  const [heights, setHeights] = useState<number[]>(() => Array(bars).fill(6))
  useEffect(() => {
    let raf = 0
    const tick = (t: number) => {
      const hs: number[] = []
      for (let i = 0; i < bars; i++) {
        const base = active ? 50 : 8
        const amp = active ? 40 * intensity : 3
        const v =
          base +
          Math.sin(t / 180 + i * 0.35) * amp +
          Math.sin(t / 90 + i * 0.9) * (amp * 0.4) +
          (active ? (Math.random() - 0.5) * 16 : 0)
        hs.push(Math.max(4, Math.min(110, v)))
      }
      setHeights(hs)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [active, bars, intensity])
  return (
    <div className="eq" aria-hidden="true">
      {heights.map((h, i) => (
        <div key={i} className="b" style={{ height: `${h}px` }} />
      ))}
    </div>
  )
}

/* ──────────────────────────────────────────────────────────
   Orb — spinning rings + pulsing core, JARVIS identity.
   ────────────────────────────────────────────────────────── */
export function Orb({
  listening = false,
  size = 160,
}: {
  listening?: boolean
  size?: number
}) {
  return (
    <div
      className={`orb${listening ? ' listening' : ''}`}
      style={{ ['--o' as string]: `${size}px` } as CSSProperties}
    >
      <div className="ring" />
      <div className="ring2" />
      <div className="core" />
    </div>
  )
}

/* ──────────────────────────────────────────────────────────
   Choice — card selector (single or multi).
   ────────────────────────────────────────────────────────── */
export function Choice({
  selected,
  glyph,
  title,
  sub,
  tag,
  multi,
  disabled,
  onClick,
}: {
  selected?: boolean
  glyph?: ReactNode
  title: ReactNode
  sub?: ReactNode
  tag?: ReactNode
  multi?: boolean
  disabled?: boolean
  onClick?: MouseEventHandler<HTMLButtonElement>
}) {
  return (
    <button
      type="button"
      className={`choice${selected ? ' selected' : ''}`}
      onClick={onClick}
      disabled={disabled}
    >
      {glyph != null && <div className="glyph">{glyph}</div>}
      <div className="c-body">
        <div className="c-title">{title}</div>
        {sub && <div className="c-sub">{sub}</div>}
      </div>
      {tag && <div className="c-tag">{tag}</div>}
      <div className="c-check" aria-hidden>
        {multi ? '✓' : '●'}
      </div>
    </button>
  )
}

/* ──────────────────────────────────────────────────────────
   Footer — sticky step nav with progress indicator.
   ────────────────────────────────────────────────────────── */
export function Footer({
  onBack,
  onNext,
  nextLabel = 'Continue',
  nextDisabled,
  step,
  total,
  children,
}: {
  onBack?: (() => void) | null
  onNext?: () => void
  nextLabel?: string
  nextDisabled?: boolean
  step: number
  total: number
  children?: ReactNode
}) {
  return (
    <div className="foot">
      {onBack ? (
        <button type="button" className="wiz-btn wiz-btn-ghost" onClick={onBack}>
          ← Back
        </button>
      ) : (
        <button
          type="button"
          className="wiz-btn wiz-btn-ghost"
          disabled
          style={{ opacity: 0.35 }}
        >
          ← Back
        </button>
      )}
      {children}
      <div className="spacer" />
      <div className="progress-txt">
        STEP {String(step).padStart(2, '0')} / {String(total).padStart(2, '0')}
      </div>
      <button
        type="button"
        className="wiz-btn wiz-btn-primary"
        onClick={onNext}
        disabled={nextDisabled}
      >
        {nextLabel} <span className="kbd">⏎</span>
      </button>
    </div>
  )
}

/* ──────────────────────────────────────────────────────────
   Radar — animated hardware-scan HUD.
   ────────────────────────────────────────────────────────── */
export function Radar({
  tier = 'B',
  label = 'SCANNING…',
  blips = [
    { left: '70%', top: '28%' },
    { left: '32%', top: '62%', delay: '0.6s' },
    { left: '55%', top: '75%', delay: '1.2s' },
  ],
  size = 280,
}: {
  tier?: string
  label?: string
  blips?: Array<{ left: string; top: string; delay?: string }>
  size?: number
}) {
  return (
    <div
      className="radar"
      style={{ ['--size' as string]: `${size}px` } as CSSProperties}
    >
      <div className="cross" />
      <div className="cross2" />
      <div className="sweep" />
      {blips.map((b, i) => (
        <div
          key={i}
          className="blip"
          style={{ left: b.left, top: b.top, animationDelay: b.delay }}
        />
      ))}
      <div className="ctr">
        <div>
          <div className="big">TIER {tier}</div>
          <div className="tier-label">{label}</div>
        </div>
      </div>
    </div>
  )
}

/* ──────────────────────────────────────────────────────────
   BootLog — boot-style milestone streamer (welcome + install).
   Each entry: { id, label, status, detail?, ts?, duration_ms? }.
   Status maps to color: pending/running → ink-2, done → ok, error → err,
   warn → warn, idle → dim.
   ────────────────────────────────────────────────────────── */
export type BootLogEntry = {
  id: string
  label: string
  status?: 'pending' | 'running' | 'done' | 'error' | 'warn' | 'idle' | 'ok'
  detail?: string
  ts?: string
  duration_ms?: number | null
}

const STATUS_CLASS: Record<string, string> = {
  pending: 'dim',
  running: 'lab',
  done: 'ok',
  ok: 'ok',
  error: 'err',
  warn: 'warn',
  idle: 'dim',
}

const STATUS_LABEL: Record<string, string> = {
  pending: 'WAIT',
  running: '…',
  done: 'OK',
  ok: 'OK',
  error: 'FAIL',
  warn: 'WARN',
  idle: 'IDLE',
}

export function BootLog({
  entries,
  emptyLabel = 'standby',
  showTimestamps = true,
}: {
  entries: BootLogEntry[]
  emptyLabel?: string
  showTimestamps?: boolean
}) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  // auto-scroll to bottom as new entries stream in
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [entries.length])

  if (!entries.length) {
    return (
      <div className="boot-log">
        <span className="ln dim">├── {emptyLabel}</span>
      </div>
    )
  }

  return (
    <div className="boot-log" ref={containerRef}>
      {entries.map((entry, i) => {
        const status = (entry.status || 'running').toLowerCase()
        const cls = STATUS_CLASS[status] || 'lab'
        const label = STATUS_LABEL[status] || status.toUpperCase()
        const ms =
          showTimestamps && entry.ts
            ? (() => {
                try {
                  return new Date(entry.ts).toISOString().slice(11, 19)
                } catch {
                  return ''
                }
              })()
            : ''
        return (
          <span className="ln" key={`${entry.id}-${i}`} style={{ animationDelay: `${i * 20}ms` }}>
            {ms ? <span className="dim">[{ms}]</span> : null}{' '}
            <span className="lab">{entry.id}</span>{' '}
            <span>{entry.label}</span>
            {entry.detail ? <span className="dim"> · {entry.detail}</span> : null}{' '}
            <span className={cls}>[ {label} ]</span>
          </span>
        )
      })}
    </div>
  )
}

/* ──────────────────────────────────────────────────────────
   WizToggle — themed on/off switch (policy rows, launch-on-login).
   ────────────────────────────────────────────────────────── */
export function WizToggle({
  on,
  onChange,
  disabled,
  ariaLabel,
}: {
  on: boolean
  onChange?: (next: boolean) => void
  disabled?: boolean
  ariaLabel?: string
}) {
  return (
    <button
      type="button"
      className={`wiz-toggle${on ? ' on' : ''}`}
      disabled={disabled}
      aria-pressed={on}
      aria-label={ariaLabel}
      onClick={() => onChange?.(!on)}
    />
  )
}

/* ──────────────────────────────────────────────────────────
   ProgressBar — themed HUD bar with sheen.
   ────────────────────────────────────────────────────────── */
export function ProgressBar({
  pct,
  sheen = true,
}: {
  pct: number
  sheen?: boolean
}) {
  const clamped = Math.max(0, Math.min(100, pct))
  return (
    <div className={`bar${sheen ? ' sheen' : ''}`}>
      <span style={{ width: `${clamped}%` }} />
    </div>
  )
}

/* ──────────────────────────────────────────────────────────
   Readout — mono technical key/value grid.
   ────────────────────────────────────────────────────────── */
export function Readout({
  rows,
}: {
  rows: Array<{ k: string; v: ReactNode; tone?: 'default' | 'accent' | 'ok' }>
}) {
  return (
    <div className="readout">
      {rows.map((r, i) => (
        <div className="row" key={i}>
          <span className="k">{r.k}</span>
          <span className={`v${r.tone && r.tone !== 'default' ? ` ${r.tone}` : ''}`}>{r.v}</span>
        </div>
      ))}
    </div>
  )
}
