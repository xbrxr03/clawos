/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { commandCenterApi } from '../../../lib/commandCenterApi'
import { Footer, Orb, ProgressBar } from '../atoms'
import type { ScreenProps } from '../types'
import { PROFILE_PERSONAS } from './ProfileScreen'

function cap(s: string): string {
  if (!s) return 'General'
  return s.charAt(0).toUpperCase() + s.slice(1).replace('_', ' ')
}

function voiceLabel(m?: string): string {
  return (
    {
      push_to_talk: 'Push-to-talk · ⌥',
      wake_word: 'Wake word · Hey Claw',
      off: 'Text only',
    }[m || 'push_to_talk'] || 'Push-to-talk'
  )
}

function launchStageLabel(pct: number, stage: string | undefined): string {
  const s = (stage || '').toLowerCase()
  if (s.startsWith('applying')) return 'applying plan…'
  if (s === 'complete' || s === 'ready') return 'ready'
  if (pct < 20) return 'starting nexus…'
  if (pct < 40) return 'loading memd (14-layer memory)…'
  if (pct < 60) return 'wiring policyd audit chain…'
  if (pct < 80) return 'mounting toolbridge + workflows…'
  if (pct < 95) return 'jarvis coming online…'
  return 'ready'
}

export function SummaryScreen(props: ScreenProps) {
  const {
    state,
    onBack,
    stepIndex,
    totalSteps,
    planSetup,
    applySetup,
    ui,
    setUi,
    busy,
  } = props
  const navigate = useNavigate()
  const [copied, setCopied] = useState(false)

  const openClawCmd = 'ollama launch openclaw --model kimi-k2.5:cloud'
  const copyOpenClawCmd = async () => {
    try {
      await navigator.clipboard.writeText(openClawCmd)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch {
      /* clipboard blocked — silent, the command is still visible on-screen */
    }
  }

  // Kick off plan generation as soon as user lands on summary
  useEffect(() => {
    if (!state.plan_steps?.length) planSetup().catch(() => null)
  }, [planSetup, state.plan_steps?.length])

  const runtimes = (state.selected_runtimes || ['nexus']).join(' + ')
  const persona = PROFILE_PERSONAS.find((p) => p.id === ui.user_profile)
  const modelName = state.selected_models?.[0] || 'qwen2.5:7b'
  const policyCount = useMemo(() => {
    const ap = (state.autonomy_policy as unknown as Record<string, boolean>) || {}
    const vals = Object.values(ap)
    return vals.filter(Boolean).length || 6
  }, [state.autonomy_policy])

  const launchProgress = Number(state.model_pull_progress?.percent || 0)
  const stage = state.progress_stage || ''
  const launching = busy === 'apply' || stage === 'applying'
  const done = !!state.completion_marker

  // Track launch_requested in ui so refresh doesn't drop the in-progress state
  const pct = done ? 100 : launching ? Math.max(12, launchProgress) : 0

  const launch = async () => {
    setUi({ launch_requested: true })
    await applySetup()
  }

  // ── Done phase — maps to handoff summary.jsx "done" state ────────────
  if (done) {
    return (
      <div
        className="stage-inner"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'column',
          textAlign: 'center',
          paddingTop: 40,
        }}
      >
        <Orb listening={true} size={130} />
        <div className="eyebrow" style={{ marginTop: 30 }}>
          SYSTEM ONLINE
        </div>
        <h1 className="wiz-title" style={{ fontSize: 42 }}>
          Welcome home.
        </h1>
        <p className="wiz-subtitle" style={{ margin: '8px auto 0' }}>
          ClawOS is live on this machine. Your private assistant, your hardware, your rules.
        </p>

        <div className="jarvis-say" style={{ marginTop: 28, maxWidth: 520 }}>
          Everything is running. Your dashboard is at localhost:7070 — I&rsquo;ve pinned it to your
          menu bar. Just say the word.
        </div>

        <div style={{ display: 'flex', gap: 12, marginTop: 36, flexWrap: 'wrap', justifyContent: 'center' }}>
          <button
            type="button"
            className="wiz-btn wiz-btn-primary"
            onClick={() => {
              try {
                window.localStorage.setItem('clawos:getting-started:pending', '1')
              } catch {
                /* ignore storage errors */
              }
              // Fire JARVIS greeting through Piper — fire-and-forget so we don't
              // hold up navigation if TTS is slow or the voice model is missing.
              // voiced.speak handles the whole pipeline (ElevenLabs → Piper → null).
              commandCenterApi.speakSetupGreeting().catch(() => null)
              navigate('/')
            }}
          >
            Open dashboard →
          </button>
          <button
            type="button"
            className="wiz-btn"
            onClick={() => window.open('https://github.com/clawos/clawos#readme', '_blank', 'noopener')}
          >
            Take the tour
          </button>
        </div>

        {/* ── NEXT · Start OpenClaw (JARVIS, your AI Butler) ────────────────
            One command drops the user into the OpenClaw TUI with kimi-k2.5
            running on Ollama Cloud. Free credits cover casual use; the
            same binary accepts BYO keys for heavy lifting. */}
        <div
          className="panel hud"
          style={{
            marginTop: 32,
            padding: 22,
            maxWidth: 560,
            width: '100%',
            textAlign: 'left',
          }}
        >
          <div className="eyebrow" style={{ marginBottom: 10 }}>
            NEXT · START OPENCLAW
          </div>
          <div
            style={{
              fontSize: 14,
              color: 'var(--ink-2)',
              marginBottom: 14,
              lineHeight: 1.5,
            }}
          >
            JARVIS, your AI Butler. Copy this command in a terminal to bring
            your agent online:
          </div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '12px 14px',
              borderRadius: 8,
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid var(--panel-br)',
              fontFamily: 'var(--mono)',
              fontSize: 13,
            }}
          >
            <span style={{ flex: 1, color: 'var(--ink-1)', userSelect: 'all' }}>
              {openClawCmd}
            </span>
            <button
              type="button"
              className="wiz-btn"
              style={{ padding: '4px 12px', fontSize: 11, minWidth: 78 }}
              onClick={copyOpenClawCmd}
            >
              {copied ? 'Copied ✓' : 'Copy ⧉'}
            </button>
          </div>
          <div
            style={{
              fontSize: 12,
              color: 'var(--ink-3)',
              marginTop: 14,
              lineHeight: 1.6,
            }}
          >
            Ollama&rsquo;s free tier covers most daily use. Need more?
          </div>
          <ul
            style={{
              margin: '6px 0 0 0',
              paddingLeft: 18,
              fontSize: 12,
              color: 'var(--ink-2)',
              lineHeight: 1.75,
            }}
          >
            <li>
              <strong style={{ color: 'var(--ink-1)' }}>Ollama Pro</strong> —
              same command, higher limits.
            </li>
            <li>
              <strong style={{ color: 'var(--ink-1)' }}>Bring your own key</strong>{' '}
              — Anthropic, OpenAI, or OpenRouter from the dashboard.
            </li>
          </ul>
        </div>

        <div className="hint" style={{ marginTop: 24 }}>
          dashboard · localhost:7070 &nbsp;·&nbsp; voice · &ldquo;Hey Claw&rdquo; &nbsp;·&nbsp; docs ·
          clawctl help
        </div>
      </div>
    )
  }

  const planSteps = state.plan_steps || []

  return (
    <>
      <div className="stage-inner">
        <div className="eyebrow">09 · Summary</div>
        <h1 className="wiz-title">Ready to bring ClawOS online.</h1>
        <p className="wiz-subtitle">
          Review your setup. Anything here can be changed later from the dashboard.
        </p>

        <div className="summary-grid" style={{ marginTop: 26 }}>
          <div className="sum-item">
            <div className="sum-k">Profile</div>
            <div className="sum-v">{cap(persona?.id || ui.user_profile || 'general')}</div>
          </div>
          <div className="sum-item">
            <div className="sum-k">Hardware tier</div>
            <div className="sum-v">
              Tier {state.detected_hardware?.tier || 'B'} ·{' '}
              <span className="m">{state.recommended_profile || 'balanced'}</span>
            </div>
          </div>
          <div className="sum-item">
            <div className="sum-k">Runtimes</div>
            <div className="sum-v m" style={{ fontFamily: 'var(--mono)', fontSize: 13 }}>
              {runtimes}
            </div>
          </div>
          <div className="sum-item">
            <div className="sum-k">Primary model</div>
            <div className="sum-v m" style={{ fontFamily: 'var(--mono)', fontSize: 13 }}>
              {modelName}
            </div>
          </div>
          <div className="sum-item">
            <div className="sum-k">Framework</div>
            <div className="sum-v m" style={{ fontFamily: 'var(--mono)', fontSize: 13 }}>
              {state.selected_framework || 'built-in only'}
            </div>
          </div>
          <div className="sum-item">
            <div className="sum-k">Voice</div>
            <div className="sum-v">{voiceLabel(state.voice_mode)}</div>
          </div>
          <div className="sum-item">
            <div className="sum-k">Permissions</div>
            <div className="sum-v">{policyCount} enabled · all gated</div>
          </div>
        </div>

        <div className="panel hud" style={{ padding: 22, marginTop: 18 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>
                Bring ClawOS online
              </div>
              <div style={{ fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.5 }}>
                Starts Nexus, memd, policyd, toolbridge and dashboard services. No restart
                required. Safe to re-run.
              </div>
            </div>
            {!launching && (
              <button
                type="button"
                className="wiz-btn wiz-btn-primary"
                onClick={launch}
                disabled={busy === 'apply'}
              >
                ⏻ Bring online
              </button>
            )}
          </div>
          {launching && (
            <div style={{ marginTop: 18 }}>
              <ProgressBar pct={pct} />
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  marginTop: 8,
                  fontFamily: 'var(--mono)',
                  fontSize: 11,
                  color: 'var(--ink-2)',
                }}
              >
                <span>{launchStageLabel(pct, stage)}</span>
                <span>{pct.toFixed(0)}%</span>
              </div>
            </div>
          )}
        </div>

        {planSteps.length > 0 && (
          <div className="panel" style={{ padding: 18, marginTop: 12 }}>
            <div
              style={{
                fontFamily: 'var(--mono)',
                fontSize: 10,
                color: 'var(--ink-3)',
                letterSpacing: '0.15em',
                marginBottom: 12,
              }}
            >
              SETUP PLAN
            </div>
            <div style={{ display: 'grid', gap: 10 }}>
              {planSteps.map((item, i) => (
                <div
                  key={`${item}-${i}`}
                  style={{ display: 'grid', gridTemplateColumns: '24px 1fr', gap: 10 }}
                >
                  <div style={{ color: 'var(--ink-3)', fontFamily: 'var(--mono)' }}>{i + 1}</div>
                  <div style={{ color: 'var(--ink-2)', fontSize: 13 }}>{item}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
      <Footer
        onBack={onBack}
        onNext={launch}
        step={stepIndex + 1}
        total={totalSteps}
        nextLabel={launching ? 'Starting…' : 'Bring online'}
        nextDisabled={launching}
      />
    </>
  )
}
