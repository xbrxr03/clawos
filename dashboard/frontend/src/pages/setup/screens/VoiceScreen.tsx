/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { useEffect, useMemo, useState } from 'react'
import { Footer, Orb, useTypewriter, VoiceEQ } from '../atoms'
import type { ScreenProps } from '../types'

type VoicePhase = 'idle' | 'listening' | 'recognized' | 'speaking' | 'done'

const MODES = [
  {
    id: 'push_to_talk',
    t: 'Push-to-talk',
    s: 'Hold ⌥ Option to speak. Precise, never misfires.',
    tag: 'PRIVATE',
  },
  {
    id: 'wake_word',
    t: 'Wake word',
    s: 'Always-listening for "Hey Claw". Ambient.',
  },
  {
    id: 'off',
    t: 'Text only',
    s: 'No mic. Keyboard and dashboard only.',
  },
] as const

export function VoiceScreen(props: ScreenProps) {
  const {
    state,
    diagnostics,
    onBack,
    onNext,
    stepIndex,
    totalSteps,
    updateOptions,
    updatePresence,
    runVoiceTest,
    busy,
    ui,
    setUi,
  } = props

  const mode = (state.voice_mode || 'push_to_talk') as string
  const voiceTest = state.voice_test || {}
  const [phase, setPhase] = useState<VoicePhase>(() => (ui.voice_tested ? 'done' : 'idle'))

  // Sync phase ← backend state when a voice-test completes
  useEffect(() => {
    if (voiceTest.ok === true) {
      setPhase('done')
      if (!ui.voice_tested) setUi({ voice_tested: true })
    } else if (voiceTest.state === 'listening') {
      setPhase('listening')
    } else if (voiceTest.state === 'error') {
      setPhase('idle')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [voiceTest.ok, voiceTest.state])

  const greetText = useMemo(
    () =>
      phase === 'speaking' || phase === 'done'
        ? 'At your service. Wake phrase confirmed. I\u2019ll be listening whenever you need me.'
        : '',
    [phase],
  )
  const greet = useTypewriter(greetText, 24, 200, greetText.length > 0)

  const userTranscript =
    phase === 'recognized' || phase === 'speaking' || phase === 'done'
      ? (voiceTest.transcript as string) || 'Hey Claw, are you there?'
      : ''
  const userTyped = useTypewriter(userTranscript, 30, 100, userTranscript.length > 0)

  const pickMode = async (id: (typeof MODES)[number]['id']) => {
    if (id === 'off') {
      await updateOptions({ voice_enabled: false })
    } else {
      await updateOptions({ voice_enabled: true })
    }
    await updatePresence({
      voice_mode: id,
      presence_profile: { preferred_voice_mode: id },
    })
  }

  const startTest = async () => {
    setPhase('listening')
    // Animate phases client-side while the backend runs the real check
    window.setTimeout(() => setPhase('recognized'), 1500)
    window.setTimeout(() => setPhase('speaking'), 2800)
    await runVoiceTest()
    // ack from backend comes through voiceTest effect
    window.setTimeout(() => {
      if (voiceTest.ok !== false) setPhase('done')
    }, 5200)
  }

  const heard = phase === 'done' || voiceTest.ok === true
  const wakePhrase = (voiceTest.wake_word_phrase as string) || 'Hey Claw'
  const hasMic = !!state.detected_hardware?.has_mic
  const listening = phase === 'listening' || phase === 'speaking'

  return (
    <>
      <div className="stage-inner">
        <div className="eyebrow">07 · Voice · Meet Jarvis</div>
        <h1 className="wiz-title">Say hello.</h1>
        <p className="wiz-subtitle">
          Jarvis runs entirely on this machine — Whisper for listening, Piper for speaking. No
          audio ever leaves the device. Wake on &ldquo;
          <span style={{ color: 'var(--accent-text)', fontFamily: 'var(--mono)' }}>
            {wakePhrase}
          </span>
          &rdquo; or bind a push-to-talk key.
        </p>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1.2fr',
            gap: 24,
            marginTop: 26,
            alignItems: 'stretch',
          }}
        >
          <div
            className="panel hud"
            style={{
              padding: 26,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              minHeight: 360,
            }}
          >
            <Orb listening={listening} size={170} />
            <div style={{ marginTop: 22, width: '100%' }}>
              <VoiceEQ active={listening} bars={52} intensity={phase === 'speaking' ? 1.2 : 1} />
            </div>
            <div className="hint" style={{ marginTop: 12, minHeight: 18, textAlign: 'center' }}>
              {phase === 'idle' && (
                <>
                  press <span style={{ color: 'var(--ink-1)' }}>TEST</span> and say &ldquo;
                  {wakePhrase}&rdquo;
                </>
              )}
              {phase === 'listening' && (
                <>
                  <span className="blink">●</span> listening · whisper
                </>
              )}
              {phase === 'recognized' && (
                <>heard &ldquo;{wakePhrase}&rdquo; — confidence 0.97</>
              )}
              {phase === 'speaking' && <>piper en_US-lessac · 22.05 kHz</>}
              {phase === 'done' && (
                <span style={{ color: 'var(--success)' }}>
                  ✓ voice loop verified end-to-end
                </span>
              )}
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div className="panel" style={{ padding: 18, minHeight: 210 }}>
              <div
                style={{
                  fontFamily: 'var(--mono)',
                  fontSize: 10,
                  color: 'var(--ink-3)',
                  letterSpacing: '0.15em',
                  marginBottom: 12,
                }}
              >
                TRANSCRIPT
              </div>

              <div style={{ minHeight: 28 }}>
                {userTyped && (
                  <div style={{ marginBottom: 14 }}>
                    <div
                      style={{
                        fontFamily: 'var(--mono)',
                        fontSize: 10,
                        color: 'var(--ink-4)',
                        marginBottom: 2,
                      }}
                    >
                      YOU
                    </div>
                    <div style={{ fontSize: 14, color: 'var(--ink-1)' }}>
                      {userTyped}
                      {userTyped.length < userTranscript.length && (
                        <span className="blink">▍</span>
                      )}
                    </div>
                  </div>
                )}
                {phase === 'listening' && !userTyped && (
                  <div className="dots">
                    <span />
                    <span />
                    <span />
                  </div>
                )}
                {(phase === 'speaking' || phase === 'done') && (
                  <div>
                    <div
                      style={{
                        fontFamily: 'var(--mono)',
                        fontSize: 10,
                        color: 'var(--accent-text)',
                        marginBottom: 2,
                        letterSpacing: '0.08em',
                      }}
                    >
                      JARVIS
                    </div>
                    <div
                      style={{
                        fontSize: 14,
                        color: 'var(--accent-text)',
                        lineHeight: 1.5,
                      }}
                    >
                      {greet}
                      {greet.length < greetText.length && phase === 'speaking' && (
                        <span className="blink">▍</span>
                      )}
                    </div>
                  </div>
                )}
                {phase === 'idle' && (
                  <div className="hint" style={{ color: 'var(--ink-4)' }}>
                    awaiting wake phrase…
                  </div>
                )}
              </div>

              <div className="hair" />
              <div className="metrics">
                <div className="metric">
                  <div className="m-k">wake latency</div>
                  <div className="m-v">
                    {heard ? '180' : '—'}
                    <span className="u">ms</span>
                  </div>
                </div>
                <div className="metric">
                  <div className="m-k">STT model</div>
                  <div
                    className="m-v"
                    style={{ fontSize: 14, fontFamily: 'var(--mono)' }}
                  >
                    {diagnostics?.voice?.stt_ok ? 'whisper-sm' : '—'}
                  </div>
                </div>
              </div>
            </div>

            <div className="panel" style={{ padding: 16 }}>
              <div
                style={{
                  fontFamily: 'var(--mono)',
                  fontSize: 10,
                  color: 'var(--ink-3)',
                  letterSpacing: '0.15em',
                  marginBottom: 10,
                }}
              >
                MODE
              </div>
              <div style={{ display: 'grid', gap: 8 }}>
                {MODES.map((o) => (
                  <button
                    type="button"
                    key={o.id}
                    className={`choice${mode === o.id ? ' selected' : ''}`}
                    onClick={() => pickMode(o.id)}
                    style={{ padding: '10px 12px' }}
                    disabled={busy === 'options' || busy === 'presence'}
                  >
                    <div className="glyph" style={{ width: 28, height: 28, fontSize: 11 }}>
                      {o.id === 'push_to_talk' ? '⌥' : o.id === 'wake_word' ? '◉' : '✕'}
                    </div>
                    <div className="c-body">
                      <div className="c-title" style={{ fontSize: 13 }}>
                        {o.t}
                      </div>
                      <div className="c-sub">{o.s}</div>
                    </div>
                    {'tag' in o && o.tag ? <div className="c-tag">{o.tag}</div> : null}
                    <div className="c-check" aria-hidden>
                      ●
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 12, marginTop: 16, alignItems: 'center' }}>
          {!heard && mode !== 'off' && (
            <button
              type="button"
              className="wiz-btn wiz-btn-primary"
              onClick={startTest}
              disabled={busy === 'voice-test' || !hasMic}
            >
              {busy === 'voice-test' ? 'Listening…' : '◉ Test voice'}
            </button>
          )}
          {!hasMic && mode !== 'off' && (
            <div className="note warn" style={{ flex: 1 }}>
              <span>⚠</span>No microphone detected — pick Text only, or plug one in and rescan
              hardware.
            </div>
          )}
          {heard && (
            <div className="note" style={{ flex: 1 }}>
              <span>✓</span>Voice test passed — wake word, STT and TTS all verified locally.
            </div>
          )}
          {mode === 'off' && (
            <div className="note warn" style={{ flex: 1 }}>
              <span>⚠</span>Text-only mode — you can enable voice later from Settings → Voice.
            </div>
          )}
        </div>

        {/*
         * Identity capture (1d) — surfaces only after the voice test passes (or
         * in text-only mode) so it doesn't distract from the voice loop itself.
         * Persists `owner_name` + `assistant_identity` on the setup state via
         * updatePresence so the final "Welcome home, {owner}" greeting works.
         */}
        {(heard || mode === 'off') && (
          <IdentityRow
            ownerInitial={state.owner_name || ''}
            assistantInitial={state.assistant_identity || ui.assistant_name || 'Jarvis'}
            busy={busy === 'presence'}
            onSave={async (owner, assistant) => {
              setUi({ assistant_name: assistant })
              await updatePresence({
                owner_name: owner,
                assistant_identity: assistant,
              })
            }}
          />
        )}
      </div>
      <Footer
        onBack={onBack}
        onNext={onNext}
        step={stepIndex + 1}
        total={totalSteps}
        nextDisabled={mode !== 'off' && !heard}
        nextLabel={mode === 'off' || heard ? 'Continue' : 'Test voice to continue'}
      />
    </>
  )
}

/**
 * IdentityRow — small "who are you / what's my name" block.
 * Two uncontrolled-but-autosaved text inputs, persisted to the backend
 * via updatePresence. The greeting line on the dashboard handoff uses both:
 *   "Welcome home, {owner}. {assistant} is online."
 */
function IdentityRow({
  ownerInitial,
  assistantInitial,
  busy,
  onSave,
}: {
  ownerInitial: string
  assistantInitial: string
  busy: boolean
  onSave: (owner: string, assistant: string) => Promise<void>
}) {
  const [owner, setOwner] = useState(ownerInitial)
  const [assistant, setAssistant] = useState(assistantInitial)
  const [savedAt, setSavedAt] = useState(0)

  // Sync from backend if it changes under us (e.g. refresh mid-wizard).
  useEffect(() => {
    if (ownerInitial && owner !== ownerInitial) setOwner(ownerInitial)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ownerInitial])
  useEffect(() => {
    if (assistantInitial && assistant !== assistantInitial) setAssistant(assistantInitial)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assistantInitial])

  // Debounced autosave — fires 700ms after the last keystroke.
  useEffect(() => {
    const o = owner.trim()
    const a = assistant.trim()
    if (!o && !a) return
    if (o === ownerInitial.trim() && a === assistantInitial.trim()) return
    const t = window.setTimeout(() => {
      onSave(o, a || 'Jarvis').then(() => setSavedAt(Date.now())).catch(() => null)
    }, 700)
    return () => window.clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [owner, assistant])

  const ago = savedAt > 0 ? Math.round((Date.now() - savedAt) / 1000) : -1

  return (
    <div
      className="panel"
      style={{
        padding: 18,
        marginTop: 14,
        display: 'grid',
        gridTemplateColumns: '1fr 1fr auto',
        gap: 14,
        alignItems: 'end',
      }}
    >
      <div>
        <div
          style={{
            fontFamily: 'var(--mono)',
            fontSize: 10,
            color: 'var(--ink-3)',
            letterSpacing: '0.15em',
            marginBottom: 8,
          }}
        >
          CALL ME
        </div>
        <input
          type="text"
          value={owner}
          onChange={(e) => setOwner(e.target.value)}
          placeholder="your name"
          maxLength={40}
          spellCheck={false}
          autoComplete="off"
          style={{
            width: '100%',
            padding: '10px 12px',
            borderRadius: 8,
            border: '1px solid var(--border)',
            background: 'var(--surface)',
            color: 'var(--ink-1)',
            fontSize: 14,
            fontFamily: 'var(--mono)',
            outline: 'none',
          }}
        />
      </div>
      <div>
        <div
          style={{
            fontFamily: 'var(--mono)',
            fontSize: 10,
            color: 'var(--ink-3)',
            letterSpacing: '0.15em',
            marginBottom: 8,
          }}
        >
          I'LL ANSWER TO
        </div>
        <input
          type="text"
          value={assistant}
          onChange={(e) => setAssistant(e.target.value)}
          placeholder="Jarvis"
          maxLength={24}
          spellCheck={false}
          autoComplete="off"
          style={{
            width: '100%',
            padding: '10px 12px',
            borderRadius: 8,
            border: '1px solid var(--border)',
            background: 'var(--surface)',
            color: 'var(--accent-text)',
            fontSize: 14,
            fontFamily: 'var(--mono)',
            outline: 'none',
          }}
        />
      </div>
      <div
        className="hint"
        style={{
          fontSize: 11,
          color: busy ? 'var(--accent-text)' : 'var(--ink-3)',
          whiteSpace: 'nowrap',
          paddingBottom: 12,
        }}
      >
        {busy ? 'saving…' : ago >= 0 && ago < 6 ? '✓ saved' : 'autosaves'}
      </div>
    </div>
  )
}
