/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { useEffect, useMemo, useState } from 'react'
import { Footer, ProgressBar, Radar } from '../atoms'
import type { ScreenProps } from '../types'

export function HardwareScreen(props: ScreenProps) {
  const { state, onBack, onNext, stepIndex, totalSteps, inspect, busy, updateOptions, ui, setUi } =
    props
  const hw = state.detected_hardware || {}
  const alreadyScanned = !!hw.ram_gb

  // Local scanning UI even if hardware is already detected (user clicked rescan)
  const [rescanning, setRescanning] = useState(false)
  const [progress, setProgress] = useState(alreadyScanned ? 100 : 6)

  // Drive a smooth progress bar while inspect() is in flight
  useEffect(() => {
    if (busy !== 'inspect' && !rescanning) {
      setProgress(alreadyScanned ? 100 : 6)
      return
    }
    let p = progress
    const iv = window.setInterval(() => {
      p = Math.min(92, p + 3.5)
      setProgress(p)
    }, 80)
    return () => window.clearInterval(iv)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [busy, rescanning])

  useEffect(() => {
    if (busy !== 'inspect' && alreadyScanned) {
      setProgress(100)
      setRescanning(false)
    }
  }, [busy, alreadyScanned])

  const tier = (hw.tier || 'B').toString()
  const profileTier = state.recommended_profile || 'balanced'
  const detectedLines = useMemo(() => {
    if (!alreadyScanned) return []
    return [
      { k: 'cpu', v: `${hw.cpu_cores || '?'} cores · ${state.architecture || 'x86_64'}` },
      { k: 'ram', v: `${hw.ram_gb || 0} GB` },
      { k: 'gpu', v: hw.gpu_name || 'CPU only' },
      { k: 'vram', v: hw.gpu_vram_gb ? `${hw.gpu_vram_gb} GB` : '—' },
      { k: 'mic', v: hw.has_mic ? 'detected' : 'not detected' },
      { k: 'ollama', v: hw.ollama_ok ? 'reachable' : 'not running yet' },
      { k: 'tier', v: `Tier ${tier} — ${profileTier}`, ok: true },
    ] as Array<{ k: string; v: string; ok?: boolean }>
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    alreadyScanned,
    hw.cpu_cores,
    hw.ram_gb,
    hw.gpu_name,
    hw.gpu_vram_gb,
    hw.has_mic,
    hw.ollama_ok,
    state.architecture,
    tier,
    profileTier,
  ])

  const runRescan = async () => {
    setRescanning(true)
    setProgress(6)
    await inspect()
    setRescanning(false)
    setProgress(100)
    setUi({ hardware_done: true })
  }

  return (
    <>
      <div className="stage-inner">
        <div className="eyebrow">02 · Hardware</div>
        <h1 className="wiz-title">Meet the machine.</h1>
        <p className="wiz-subtitle">
          Probing CPU, memory, GPU, storage and microphone to pick the right runtimes, model and
          voice posture for you.
        </p>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '320px 1fr',
            gap: 28,
            marginTop: 28,
            alignItems: 'start',
          }}
        >
          <div
            className="panel hud"
            style={{ display: 'grid', placeItems: 'center', padding: 24 }}
          >
            <Radar
              tier={tier}
              label={busy === 'inspect' || rescanning ? 'SCANNING…' : profileTier.toUpperCase()}
            />
            <div style={{ marginTop: 18, width: '100%' }}>
              <ProgressBar pct={progress} />
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  marginTop: 8,
                  fontFamily: 'var(--mono)',
                  fontSize: 10,
                  color: 'var(--ink-3)',
                }}
              >
                <span>PROBE</span>
                <span>{Math.floor(progress)}%</span>
              </div>
            </div>
          </div>

          <div>
            <div className="panel" style={{ padding: 22 }}>
              <div
                style={{
                  fontFamily: 'var(--mono)',
                  fontSize: 10,
                  color: 'var(--ink-3)',
                  letterSpacing: '0.15em',
                  marginBottom: 12,
                  display: 'flex',
                  justifyContent: 'space-between',
                }}
              >
                <span>DETECTED HARDWARE</span>
                <button
                  type="button"
                  className="wiz-btn wiz-btn-ghost"
                  onClick={runRescan}
                  disabled={busy === 'inspect'}
                  style={{ padding: '4px 10px', fontSize: 11 }}
                >
                  {busy === 'inspect' ? 'scanning…' : '↻ rescan'}
                </button>
              </div>
              <div className="readout">
                {detectedLines.map((l, i) => (
                  <div className="row" key={i}>
                    <span className="k">{l.k}</span>
                    <span className={`v ${l.ok ? 'ok' : ''}`}>{l.v}</span>
                  </div>
                ))}
                {!alreadyScanned && (
                  <div className="row">
                    <span className="k">scan</span>
                    <span className="v">
                      <span className="blink">▍</span> probing…
                    </span>
                  </div>
                )}
              </div>
            </div>

            {alreadyScanned && (
              <div className="panel strong" style={{ padding: 20, marginTop: 12 }}>
                <div
                  style={{
                    fontFamily: 'var(--mono)',
                    fontSize: 10,
                    color: 'var(--ink-3)',
                    letterSpacing: '0.15em',
                    marginBottom: 10,
                  }}
                >
                  RECOMMENDATION
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>
                      {profileTier.charAt(0).toUpperCase() + profileTier.slice(1)} profile ·{' '}
                      {state.selected_models?.[0] || 'qwen2.5:3b'}
                    </div>
                    <div style={{ fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.5 }}>
                      Runs comfortably in {hw.ram_gb || '?'} GB with{' '}
                      {hw.gpu_name ? 'GPU-assisted' : 'CPU-only'} inference.
                      {hw.has_mic ? ' Voice ready.' : ' Voice optional (no mic detected).'}
                    </div>
                  </div>
                  <div className="tg">
                    <button
                      type="button"
                      className={profileTier === 'low-ram' ? 'sel' : ''}
                      onClick={() => updateOptions({ recommended_profile: 'low-ram' })}
                    >
                      Low-RAM
                    </button>
                    <button
                      type="button"
                      className={profileTier === 'balanced' ? 'sel' : ''}
                      onClick={() => updateOptions({ recommended_profile: 'balanced' })}
                    >
                      Balanced
                    </button>
                    <button
                      type="button"
                      className={profileTier === 'performance' ? 'sel' : ''}
                      onClick={() => updateOptions({ recommended_profile: 'performance' })}
                    >
                      Performance
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
      <Footer
        onBack={onBack}
        onNext={onNext}
        step={stepIndex + 1}
        total={totalSteps}
        nextDisabled={!alreadyScanned || busy === 'inspect'}
        nextLabel={!alreadyScanned ? 'Scanning…' : 'Continue'}
      />
    </>
  )
}
