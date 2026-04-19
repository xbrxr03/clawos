/* SPDX-License-Identifier: AGPL-3.0-or-later */
/* InstallOverlay — fullscreen live install progress.
 *
 * Shown when install.sh is actively streaming milestones to setupd
 * (state.install_milestones.length > 0 && !state.install_complete).
 * Fades out automatically once the 'ready' milestone fires and
 * state.install_complete flips true, handing off to the wizard welcome.
 *
 * Data source: state.install_milestones (upserted by install.sh via
 * POST /api/setup/install-milestone, broadcast via /ws/setup).
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import type { InstallMilestone, SetupState } from '../../../lib/commandCenterApi'
import { BootLog, Orb, ProgressBar, type BootLogEntry } from '../atoms'

interface Props {
  state: SetupState
  /** Called once the overlay finishes its fade-out animation. */
  onDone?: () => void
}

/** Natural ordering of install phases — drives stable ordering + % calc. */
const PHASE_ORDER: string[] = [
  'preflight',
  'deps',
  'core',
  'bootstrap',
  'model',
  'memory',
  'voice',
  'services',
  'verify',
  'ready',
]

function orderIndex(id: string): number {
  const idx = PHASE_ORDER.indexOf(id)
  return idx < 0 ? PHASE_ORDER.length : idx
}

function toBootEntries(milestones: InstallMilestone[]): BootLogEntry[] {
  // Stable sort by known phase order, then by insertion order (ts).
  const sorted = [...milestones].sort((a, b) => {
    const ia = orderIndex(a.id)
    const ib = orderIndex(b.id)
    if (ia !== ib) return ia - ib
    return (a.ts || '').localeCompare(b.ts || '')
  })
  return sorted.map((m) => ({
    id: m.id,
    label: m.label || m.id,
    status: m.status,
    detail: m.detail || '',
    ts: m.ts,
    duration_ms: m.duration_ms ?? null,
  }))
}

function computePct(milestones: InstallMilestone[]): number {
  if (!milestones.length) return 0
  const total = PHASE_ORDER.length
  // Count phases that have reached 'done' status. Running counts as 0.5.
  let credit = 0
  const seen = new Set<string>()
  for (const m of milestones) {
    if (seen.has(m.id)) continue
    seen.add(m.id)
    if (m.status === 'done') credit += 1
    else if (m.status === 'running') credit += 0.5
  }
  const pct = Math.min(99, Math.round((credit / total) * 100))
  return pct
}

function phaseLabel(m: InstallMilestone | undefined): string {
  if (!m) return 'waking nexus…'
  if (m.status === 'error') return `${m.label} — failed`
  if (m.status === 'running') return m.label
  if (m.status === 'done' && m.id === 'ready') return 'ready'
  return m.label
}

export function InstallOverlay({ state, onDone }: Props) {
  const milestones = useMemo<InstallMilestone[]>(
    () => (state.install_milestones as InstallMilestone[] | undefined) || [],
    [state.install_milestones],
  )
  const entries = useMemo(() => toBootEntries(milestones), [milestones])
  const pct = useMemo(() => {
    if (state.install_complete) return 100
    return computePct(milestones)
  }, [milestones, state.install_complete])

  const current = useMemo(() => {
    // Last running wins; else last done.
    const running = [...milestones].reverse().find((m) => m.status === 'running')
    if (running) return running
    return [...milestones].reverse().find((m) => m.status === 'done')
  }, [milestones])

  const hasError = useMemo(() => milestones.some((m) => m.status === 'error'), [milestones])

  // Handoff fade — after install_complete, pause a beat then notify parent.
  const [fading, setFading] = useState(false)
  const doneRef = useRef(false)
  useEffect(() => {
    if (!state.install_complete || doneRef.current) return
    doneRef.current = true
    const fadeTimer = window.setTimeout(() => setFading(true), 1100)
    const doneTimer = window.setTimeout(() => {
      onDone?.()
    }, 2100)
    return () => {
      window.clearTimeout(fadeTimer)
      window.clearTimeout(doneTimer)
    }
  }, [state.install_complete, onDone])

  return (
    <div
      className={`install-overlay${fading ? ' fading' : ''}`}
      role="status"
      aria-live="polite"
      aria-label="ClawOS installation in progress"
    >
      <div className="install-backdrop" />
      <div className="install-stage">
        <div className="install-brand">
          <Orb listening={!state.install_complete && !hasError} size={118} />
          <div className="eyebrow" style={{ marginTop: 24 }}>
            OPENCLAW · CLAWOS · INSTALLING
          </div>
          <h1 className="wiz-title" style={{ fontSize: 36, margin: '10px 0 0' }}>
            {state.install_complete ? 'Welcome home.' : 'Bringing ClawOS online.'}
          </h1>
          <p className="wiz-subtitle" style={{ margin: '10px auto 0', maxWidth: 520 }}>
            {state.install_complete
              ? 'All services up. Handing you to the setup wizard…'
              : 'Your private assistant is assembling itself. No data leaves this machine.'}
          </p>
        </div>

        <div className="panel hud install-progress">
          <div className="install-meter">
            <ProgressBar pct={pct} />
            <div className="install-meter-foot">
              <span>{phaseLabel(current)}</span>
              <span>{pct.toFixed(0)}%</span>
            </div>
          </div>

          <div className="install-log-title">BOOT LOG</div>
          <BootLog entries={entries} emptyLabel="waiting for install.sh…" />
        </div>

        {hasError && (
          <div className="note err" style={{ marginTop: 18, maxWidth: 620 }}>
            <span>✕</span>
            An install step reported an error. Check the terminal running
            install.sh — you can re-run it safely (installs are idempotent).
          </div>
        )}
      </div>
    </div>
  )
}
