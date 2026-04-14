/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { FormEvent, startTransition, useEffect, useMemo, useState } from 'react'
import { Badge, Card } from '../components/ui.jsx'
import { commandCenterApi, type JarvisConfig, type JarvisHealth, type JarvisSession, type JarvisTurn } from '../lib/commandCenterApi'

const SPECTRUM_BARS = Array.from({ length: 21 }, (_, index) => index)
const SPECTRUM_PROFILE = [0.22, 0.3, 0.36, 0.42, 0.5, 0.64, 0.74, 0.84, 0.96, 1, 0.92, 0.84, 0.74, 0.66, 0.56, 0.48, 0.4, 0.34, 0.28, 0.24, 0.2]

function orbLabel(state: string) {
  if (state === 'listening') return 'Listening'
  if (state === 'thinking') return 'Thinking'
  if (state === 'speaking') return 'Speaking'
  return 'Stand by'
}

function captionFromSession(session: JarvisSession) {
  if (session.state === 'listening') return session.last_utterance || 'Listening for your next command...'
  if (session.live_caption) return session.live_caption
  if (session.last_response) return session.last_response
  return 'Hello Sir. JARVIS is standing by.'
}

function sourceLabel(source: string) {
  if (source.startsWith('jarvis-ui:voice')) return 'Voice'
  if (source.startsWith('jarvis-ui:text')) return 'Console'
  if (source.startsWith('scheduler')) return 'Briefing'
  if (source.startsWith('whatsapp')) return 'WhatsApp'
  return source
}

export function JarvisVoicePage({ jarvisSession }: { jarvisSession: JarvisSession }) {
  const [session, setSession] = useState<JarvisSession>(jarvisSession)
  const [health, setHealth] = useState<JarvisHealth | null>(null)
  const [config, setConfig] = useState<JarvisConfig | null>(null)
  const [draft, setDraft] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [statusMessage, setStatusMessage] = useState('')
  const [busy, setBusy] = useState<'talk' | 'send' | 'save' | 'mode' | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    startTransition(() => setSession(jarvisSession))
  }, [jarvisSession])

  useEffect(() => {
    const load = async () => {
      try {
        const [healthPayload, configPayload] = await Promise.all([
          commandCenterApi.getJarvisHealth(),
          commandCenterApi.getJarvisConfig(),
        ])
        setHealth(healthPayload)
        setConfig(configPayload)
      } catch (loadError: any) {
        setError(loadError?.message || 'Failed to load JARVIS status')
      }
    }
    void load()
    const id = window.setInterval(() => void load(), 10000)
    return () => window.clearInterval(id)
  }, [])

  const unavailable = !health?.openclaw_running
  const caption = captionFromSession(session)
  const turns = useMemo(() => (session.recent_turns || []).slice().reverse(), [session.recent_turns])
  const providerBadge = health?.provider_status?.active || config?.tts_provider_preference || 'piper'
  const sourceEntries = Object.entries(health?.briefing_sources || {})
  const voiceEnabled = config ? config.voice_enabled !== false : session.voice_enabled !== false

  const updateSession = (next?: JarvisSession) => {
    if (!next) return
    startTransition(() => setSession(next))
  }

  const refreshStatus = async () => {
    try {
      const [nextSession, nextHealth, nextConfig] = await Promise.all([
        commandCenterApi.getJarvisSession(),
        commandCenterApi.getJarvisHealth(),
        commandCenterApi.getJarvisConfig(),
      ])
      updateSession(nextSession)
      setHealth(nextHealth)
      setConfig(nextConfig)
    } catch {}
  }

  const runPushToTalk = async () => {
    setBusy('talk')
    setError('')
    setStatusMessage('Listening for JARVIS...')
    try {
      const result = await commandCenterApi.pushToTalkJarvis()
      updateSession(result.session)
      setStatusMessage(result.reply ? `JARVIS replied: ${result.reply}` : result.error || result.issues?.[0] || 'No speech detected')
      await refreshStatus()
    } catch (talkError: any) {
      setError(talkError?.message || 'Push-to-talk failed')
    } finally {
      setBusy(null)
    }
  }

  const sendDraft = async (event?: FormEvent) => {
    event?.preventDefault()
    if (!draft.trim()) return
    setBusy('send')
    setError('')
    setStatusMessage('Sending to JARVIS...')
    try {
      const result = await commandCenterApi.sendJarvisChat(draft.trim())
      updateSession(result.session)
      setDraft('')
      setStatusMessage(result.reply ? `JARVIS replied: ${result.reply}` : 'Message delivered')
      await refreshStatus()
    } catch (sendError: any) {
      setError(sendError?.message || 'Message failed')
    } finally {
      setBusy(null)
    }
  }

  const saveConfig = async () => {
    if (!config) return
    setBusy('save')
    setError('')
    setStatusMessage('Updating JARVIS voice profile...')
    try {
      const result = await commandCenterApi.setJarvisConfig({
        voice_enabled: config.voice_enabled,
        input_mode: config.input_mode,
        wake_phrase: config.wake_phrase,
        tts_provider_preference: config.tts_provider_preference,
        elevenlabs_voice_id: config.elevenlabs_voice_id,
        elevenlabs_api_key: apiKey.trim() || undefined,
      })
      updateSession(result.session)
      if (result.config) setConfig(result.config)
      setApiKey('')
      setStatusMessage('JARVIS voice settings updated')
      await refreshStatus()
    } catch (saveError: any) {
      setError(saveError?.message || 'Unable to save JARVIS config')
    } finally {
      setBusy(null)
    }
  }

  const switchMode = async (mode: string) => {
    setBusy('mode')
    setError('')
    try {
      const nextSession = await commandCenterApi.setJarvisMode(mode)
      updateSession(nextSession)
      setConfig((current) => current ? { ...current, voice_enabled: mode !== 'off', input_mode: mode === 'off' ? current.input_mode : mode } : current)
      setStatusMessage(`JARVIS mode set to ${mode.replace(/_/g, ' ')}`)
      await refreshStatus()
    } catch (modeError: any) {
      setError(modeError?.message || 'Could not change JARVIS mode')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="jarvis-room fade-up">
      <div className="jarvis-room-grid">
        <section className="jarvis-stage" data-state={session.state || 'idle'}>
          <div className="jarvis-stage-header">
            <div>
              <div className="jarvis-kicker">OpenClaw Voice Room</div>
              <h1 className="jarvis-title">JARVIS Command Chamber</h1>
              <p className="jarvis-subtitle">OpenClaw-backed conversation, live captions, and cinematic voice response in one dedicated room.</p>
            </div>
            <div className="jarvis-badges">
              <Badge color={health?.openclaw_running ? 'green' : 'orange'}>{health?.openclaw_running ? 'OpenClaw live' : 'OpenClaw unavailable'}</Badge>
              <Badge color={providerBadge.startsWith('elevenlabs') ? 'blue' : 'gray'}>{providerBadge}</Badge>
            </div>
          </div>

          <div className="jarvis-orb-stack">
            <button
              type="button"
              className="jarvis-orb-button"
              onClick={() => void runPushToTalk()}
              disabled={busy !== null || unavailable || !voiceEnabled}
              aria-label="Activate JARVIS push to talk"
            >
              <span className="jarvis-orb-ring jarvis-orb-ring-outer" />
              <span className="jarvis-orb-ring jarvis-orb-ring-middle" />
              <span className="jarvis-orb-ring jarvis-orb-ring-inner" />
              <span className="jarvis-orb-core" />
              <span className="jarvis-orb-label">{orbLabel(String(session.state || 'idle'))}</span>
            </button>

            <div className="jarvis-caption-bubble">
              <div className="jarvis-caption-label">Live Caption</div>
              <div className="jarvis-caption-text">{caption}</div>
            </div>

            <div className="jarvis-spectrum" data-state={session.state || 'idle'} aria-hidden="true">
              {SPECTRUM_BARS.map((bar) => (
                <span
                  key={bar}
                  className="jarvis-spectrum-bar"
                  style={{ ['--bar-index' as any]: bar, ['--bar-profile' as any]: SPECTRUM_PROFILE[bar] }}
                />
              ))}
            </div>
          </div>

          <form className="jarvis-composer" onSubmit={(event) => void sendDraft(event)}>
            <input
              className="jarvis-composer-input"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder={unavailable ? 'OpenClaw is unavailable right now' : 'Message JARVIS or say “Hey Jarvis, what’s up?”'}
              disabled={busy !== null || unavailable}
            />
            <button type="button" className="jarvis-mic-button" onClick={() => void runPushToTalk()} disabled={busy !== null || unavailable || !voiceEnabled}>
              {busy === 'talk' ? 'Listening...' : 'Mic'}
            </button>
            <button type="submit" className="jarvis-send-button" disabled={busy !== null || unavailable || !draft.trim()}>
              {busy === 'send' ? 'Sending...' : 'Send'}
            </button>
          </form>

          <div className="jarvis-stage-footer">
            <div className="jarvis-stage-note">Replies are spoken out loud by default unless JARVIS voice is turned off.</div>
            {statusMessage ? <div className="jarvis-stage-status">{statusMessage}</div> : null}
            {error ? <div className="jarvis-stage-error">{error}</div> : null}
          </div>
        </section>

        <aside className="jarvis-sidepanel">
          <Card className="jarvis-panel jarvis-panel-transcript">
            <div className="jarvis-panel-kicker">Transcript</div>
            <div className="jarvis-panel-title">Recent turns</div>
            <div className="jarvis-transcript-list">
              {turns.length ? turns.map((turn: JarvisTurn) => (
                <div key={turn.id} className={`jarvis-turn jarvis-turn-${turn.role || 'assistant'}`}>
                  <div className="jarvis-turn-meta">
                    <span>{turn.role === 'user' ? 'You' : 'JARVIS'}</span>
                    <span>{sourceLabel(turn.source || '')}</span>
                  </div>
                  <div className="jarvis-turn-text">{turn.text}</div>
                </div>
              )) : (
                <div className="jarvis-empty-copy">No transcript yet. Start with a typed message or press the orb to talk.</div>
              )}
            </div>
          </Card>

          <Card className="jarvis-panel">
            <div className="jarvis-panel-kicker">Voice Profile</div>
            <div className="jarvis-panel-title">JARVIS audio and routing</div>
            <div className="jarvis-config-grid">
              <label className="jarvis-field">
                <span>Voice output</span>
                <select
                  value={config?.voice_enabled === false ? 'off' : (config?.input_mode || 'push_to_talk')}
                  onChange={(event) => void switchMode(event.target.value)}
                  disabled={busy !== null}
                >
                  <option value="push_to_talk">Push to talk</option>
                  <option value="wake_word">Wake word</option>
                  <option value="off">Voice off</option>
                </select>
              </label>

              <label className="jarvis-field">
                <span>Preferred voice provider</span>
                <select
                  value={config?.tts_provider_preference || 'elevenlabs'}
                  onChange={(event) => setConfig((current) => current ? { ...current, tts_provider_preference: event.target.value } : current)}
                  disabled={busy !== null}
                >
                  <option value="elevenlabs">ElevenLabs</option>
                  <option value="piper">Piper fallback</option>
                </select>
              </label>

              <label className="jarvis-field">
                <span>Wake phrase</span>
                <input
                  value={config?.wake_phrase || 'Hey Jarvis'}
                  onChange={(event) => setConfig((current) => current ? { ...current, wake_phrase: event.target.value } : current)}
                  disabled={busy !== null}
                />
              </label>

              <label className="jarvis-field">
                <span>ElevenLabs voice ID</span>
                <input
                  value={config?.elevenlabs_voice_id || ''}
                  onChange={(event) => setConfig((current) => current ? { ...current, elevenlabs_voice_id: event.target.value } : current)}
                  disabled={busy !== null}
                />
              </label>

              <label className="jarvis-field jarvis-field-full">
                <span>ElevenLabs API key</span>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  placeholder={config?.elevenlabs_key_set ? 'Saved - paste to update' : 'Paste to enable ElevenLabs'}
                  disabled={busy !== null}
                />
              </label>
            </div>

            <button type="button" className="jarvis-save-button" onClick={() => void saveConfig()} disabled={busy !== null}>
              {busy === 'save' ? 'Saving...' : 'Save JARVIS voice'}
            </button>
          </Card>

          <Card className="jarvis-panel">
            <div className="jarvis-panel-kicker">Status</div>
            <div className="jarvis-panel-title">OpenClaw and briefing posture</div>
            <div className="jarvis-status-list">
              <div className="jarvis-status-row">
                <span>OpenClaw gateway</span>
                <span>{health?.openclaw_running ? `Live on ${health.gateway_port}` : 'Unavailable'}</span>
              </div>
              <div className="jarvis-status-row">
                <span>Microphone</span>
                <span>{health?.microphone_ok ? health.microphone_backend : 'Unavailable'}</span>
              </div>
              <div className="jarvis-status-row">
                <span>Playback</span>
                <span>{health?.playback_backend || 'Unavailable'}</span>
              </div>
              <div className="jarvis-status-row">
                <span>Wake word</span>
                <span>{health?.wake_word_ok ? 'Supported' : 'Not available'}</span>
              </div>
            </div>

            <div className="jarvis-source-cloud">
              {sourceEntries.map(([key, value]) => (
                <span key={key} className={`jarvis-source-pill jarvis-source-pill-${value}`}>{key}: {value}</span>
              ))}
            </div>
          </Card>
        </aside>
      </div>
    </div>
  )
}
