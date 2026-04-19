/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { useEffect, useState } from 'react'
import { Footer, Readout, useTypewriter } from '../atoms'
import type { ScreenProps } from '../types'

const ASCII = `  ██████╗██╗      █████╗ ██╗    ██╗ ██████╗ ███████╗
 ██╔════╝██║     ██╔══██╗██║    ██║██╔═══██╗██╔════╝
 ██║     ██║     ███████║██║ █╗ ██║██║   ██║███████╗
 ██║     ██║     ██╔══██║██║███╗██║██║   ██║╚════██║
 ╚██████╗███████╗██║  ██║╚███╔███╔╝╚██████╔╝███████║
  ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝  ╚═════╝ ╚══════╝`

const BOOT_LINES = [
  { t: 'initd', s: 'loading kernel modules ………………………… ', r: 'ok' },
  { t: 'net', s: 'network: offline-first mode ……………… ', r: 'ok' },
  { t: 'policyd', s: 'approval queue spinning up ……………… ', r: 'ok' },
  { t: 'memd', s: 'memory layers: 14 persistent ……………… ', r: 'ok' },
  { t: 'nexus', s: 'agent loop online ……………………………………… ', r: 'ok' },
  { t: 'jarvis', s: 'wake-word engine standby …………………… ', r: 'idle' },
]

export function WelcomeScreen(props: ScreenProps) {
  const { state, onNext, stepIndex, totalSteps, inspect } = props
  const [phase, setPhase] = useState(0)

  useEffect(() => {
    const steps = [120, 120, 160, 160, 160, 160, 500]
    let cumulative = 0
    const timers = steps.map((d, i) => {
      cumulative += d
      return window.setTimeout(() => setPhase(i + 1), cumulative)
    })
    return () => timers.forEach((t) => window.clearTimeout(t))
  }, [])

  // Kick off hardware probe in the background while the user reads the welcome
  useEffect(() => {
    if (!state.detected_hardware?.ram_gb) {
      inspect().catch(() => null)
    }
  }, [inspect, state.detected_hardware?.ram_gb])

  const greet = useTypewriter(
    "Good to see you. Ready whenever you are.",
    22,
    1400,
    phase >= BOOT_LINES.length,
  )

  const hostname = typeof window !== 'undefined' ? window.location.host : 'claw-host'
  const ramLabel = state.detected_hardware?.ram_gb
    ? `${state.detected_hardware.ram_gb} GB · ${state.detected_hardware.gpu_name || 'CPU only'}`
    : 'probing…'

  return (
    <>
      <div className="stage-inner">
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1.1fr 1fr',
            gap: 48,
            alignItems: 'start',
            marginTop: 12,
          }}
        >
          <div>
            <div className="eyebrow">FIRST RUN · v0.1.0</div>
            <h1 className="wiz-title">Welcome to ClawOS.</h1>
            <p className="wiz-subtitle">
              Take any spare machine and turn it into a private assistant. Voice, 14-layer memory,
              29 automations — all local, no cloud, no subscription. Two minutes to set up.
            </p>

            <div className="hair" />

            <div className="boot-log">
              {BOOT_LINES.slice(0, phase).map((l, i) => (
                <span className="ln" key={i}>
                  <span className="dim">[{String((i + 1) * 17 + 104).padStart(4, '0')}ms]</span>{' '}
                  <span className="lab">{l.t}</span> <span>{l.s}</span>
                  <span className={l.r === 'ok' ? 'ok' : 'warn'}>[ {l.r.toUpperCase()} ]</span>
                </span>
              ))}
              {phase >= BOOT_LINES.length && (
                <span className="ln" style={{ marginTop: 10, display: 'block' }}>
                  <span className="dim">├──</span> <span className="ok">● system ready</span>
                </span>
              )}
              {phase >= BOOT_LINES.length && (
                <span className="ln jarvis-say" style={{ marginTop: 14, display: 'block' }}>
                  {greet}
                  {greet.length < 42 ? <span className="blink">▍</span> : null}
                </span>
              )}
            </div>
          </div>

          <div className="panel hud" style={{ padding: 24 }}>
            <pre className="ascii">{ASCII}</pre>
            <div
              style={{
                marginTop: 18,
                fontFamily: 'var(--mono)',
                fontSize: 11,
                color: 'var(--ink-3)',
                letterSpacing: '0.08em',
              }}
            >
              local · offline · private · free
            </div>
            <div className="hair" />
            <Readout
              rows={[
                { k: 'hostname', v: hostname },
                { k: 'user', v: 'you' },
                { k: 'hardware', v: ramLabel },
                { k: 'privacy', v: '100% local', tone: 'ok' },
              ]}
            />
          </div>
        </div>

        <div className="note" style={{ marginTop: 28 }}>
          <span>↪</span>
          This wizard configures hardware profile, runtimes, model, voice and policy. Everything is
          reversible — change anything later from Settings.
        </div>
      </div>
      <Footer
        onNext={onNext}
        step={stepIndex + 1}
        total={totalSteps}
        nextLabel="Begin setup"
      />
    </>
  )
}
