/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { FormEvent, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Badge, Card, PageHeader, PanelHeader, SectionLabel, StatusDot, Ts } from '../components/ui.jsx'
import { GettingStartedCard } from '../components/GettingStartedCard'
import { LaunchJarvisButton } from '../components/LaunchJarvisButton'
import {
  commandCenterApi,
  type AttentionEvent,
  type Briefing,
  type Mission,
  type PresencePayload,
  type VoiceSession,
} from '../lib/commandCenterApi'

type ServiceMap = Record<string, { status?: string; latency_ms?: number }>
type TaskMap = Record<string, Array<{ id?: string; description?: string; status?: string }>>
type EventRecord = { type?: string; data?: Record<string, any>; timestamp?: string | number }
type ApprovalRecord = { id?: string; tool?: string; risk?: string; target?: string }
type ModelRecord = { default?: string; models?: Array<{ name?: string; running?: boolean }> }
type RuntimeRecord = Record<string, { installed?: boolean; running?: boolean; model?: string }>

type ConversationMessage = {
  id: string
  role: 'assistant' | 'user'
  content: string
  meta?: string
}

export function Overview({
  services,
  tasks,
  approvals,
  events,
  models,
  runtimes = {},
  voiceSession: liveVoiceSession = null,
}: {
  services: ServiceMap
  tasks: TaskMap
  approvals: ApprovalRecord[]
  events: EventRecord[]
  models: ModelRecord
  runtimes?: RuntimeRecord
  voiceSession?: VoiceSession | null
}) {
  const navigate = useNavigate()
  const [presence, setPresence] = useState<PresencePayload | null>(null)
  const [briefing, setBriefing] = useState<Briefing | null>(null)
  const [signals, setSignals] = useState<AttentionEvent[]>([])
  const [missions, setMissions] = useState<Mission[]>([])
  const [liveApprovals, setLiveApprovals] = useState<ApprovalRecord[]>(approvals || [])
  const [voiceSession, setVoiceSession] = useState<VoiceSession | null>(null)
  const [draft, setDraft] = useState('')
  const [conversation, setConversation] = useState<ConversationMessage[]>([
    {
      id: 'nexus-welcome',
      role: 'assistant',
      content: 'Nexus is online and watching the trusted lanes for you.',
      meta: 'Ready',
    },
  ])
  const [working, setWorking] = useState(false)
  const [conversationStatus, setConversationStatus] = useState('')
  const [voiceBusy, setVoiceBusy] = useState(false)
  const [suggestions, setSuggestions] = useState<any[]>([])

  useEffect(() => {
    Promise.all([
      commandCenterApi.getPresence(),
      commandCenterApi.getTodayBriefing(),
      commandCenterApi.listAttention(),
      commandCenterApi.listMissions(),
      commandCenterApi.listApprovals(),
      fetch('/api/suggestions', { credentials: 'include' }).then(r => r.ok ? r.json() : { suggestions: [] }),
    ])
      .then(([presencePayload, briefingPayload, attentionPayload, missionPayload, approvalPayload, suggestionsPayload]) => {
        setPresence(presencePayload)
        setBriefing(briefingPayload)
        setSignals(Array.isArray(attentionPayload) ? attentionPayload : [])
        setMissions(Array.isArray(missionPayload) ? missionPayload : [])
        setLiveApprovals(Array.isArray(approvalPayload) ? approvalPayload : [])
        setSuggestions((suggestionsPayload as any)?.suggestions || [])
      })
      .catch(() => null)
  }, [])

  const dismissSuggestion = async (id: string) => {
    setSuggestions(current => current.filter(s => s.id !== id))
    await fetch(`/api/suggestions/${id}`, { method: 'DELETE', credentials: 'include' }).catch(() => null)
  }

  useEffect(() => {
    if (liveVoiceSession) {
      setVoiceSession(liveVoiceSession)
    }
  }, [liveVoiceSession])

  useEffect(() => {
    setLiveApprovals((current) => (current.length ? current : approvals || []))
  }, [approvals])

  const taskCounts = {
    active: tasks.active?.length ?? 0,
    queued: tasks.queued?.length ?? 0,
    failed: tasks.failed?.length ?? 0,
    completed: tasks.completed?.length ?? 0,
  }

  const serviceEntries = Object.entries(services || {})
  const healthyServices = serviceEntries.filter(([, item]) => item?.status === 'up' || item?.status === 'running').length
  const runningModels = (models.models || []).filter((item) => item.running).length
  const assistantName = presence?.profile?.assistant_identity || 'Nexus'
  const voiceMode = voiceSession?.mode || presence?.voice_session?.mode || 'push_to_talk'
  const voiceState = voiceSession?.state || presence?.voice_session?.state || 'idle'
  const tone = presence?.profile?.tone || 'calm'

  const timeline = useMemo(() => events.slice(0, 6), [events])
  const serviceCoverage = serviceEntries.length ? Math.round((healthyServices / serviceEntries.length) * 100) : 0
  const runtimeHighlights = Object.entries(runtimes || {})
    .slice(0, 5)
    .map(([name, item]) => ({
      name,
      status: item?.running ? 'running' : item?.installed ? 'installed' : 'missing',
      model: item?.model || 'unassigned',
    }))
  const topSignals = signals.slice(0, 4)
  const topMissions = missions.slice(0, 4)
  const serviceHealthRows = serviceEntries.slice(0, 4)

  const activityMix = useMemo(() => {
    const counts = { workflow: 0, service: 0, audit: 0, other: 0 }
    events.slice(0, 24).forEach((event) => {
      if ((event.type || '').startsWith('workflow_')) counts.workflow += 1
      else if (event.type === 'service_health') counts.service += 1
      else if (event.type === 'audit_event') counts.audit += 1
      else counts.other += 1
    })
    return counts
  }, [events])

  const approvalMix = {
    high: liveApprovals.filter((item) => item.risk === 'high').length,
    medium: liveApprovals.filter((item) => !item.risk || item.risk === 'medium').length,
    low: liveApprovals.filter((item) => item.risk === 'low').length,
  }

  const submitConversation = async (event: FormEvent) => {
    event.preventDefault()
    const message = draft.trim()
    if (!message || working) return

    setWorking(true)
    setConversationStatus('Nexus is thinking...')
    const assistantMsgId = `assistant-${Date.now()}`
    setConversation((current) => [
      ...current,
      { id: `user-${Date.now()}`, role: 'user', content: message },
      { id: assistantMsgId, role: 'assistant', content: '...', meta: 'Thinking' },
    ])
    setDraft('')

    try {
      const response = await commandCenterApi.sendConversationMessage(message)
      const taskId = response.task_id
      if (!taskId) throw new Error('No task ID returned')

      let result = ''
      for (let i = 0; i < 60; i++) {
        await new Promise((r) => setTimeout(r, 500))
        const task = await commandCenterApi.getTask(taskId)
        if (task.status === 'completed') { result = task.result || '(no response)'; break }
        if (task.status === 'failed') { result = task.error || 'Task failed.'; break }
      }
      if (!result) result = 'Nexus did not respond in time.'

      setConversation((current) =>
        current.map((msg) =>
          msg.id === assistantMsgId ? { ...msg, content: result, meta: undefined } : msg,
        ),
      )
      setConversationStatus('')
    } catch (error: any) {
      setConversation((current) =>
        current.map((msg) =>
          msg.id === assistantMsgId
            ? { ...msg, content: error.message || 'Something went wrong.', meta: 'Error' }
            : msg,
        ),
      )
      setConversationStatus(error.message || 'Nexus could not process that request.')
    } finally {
      setWorking(false)
    }
  }

  const pushToTalk = async () => {
    if (voiceBusy || voiceMode === 'off') return
    setVoiceBusy(true)
    setConversationStatus('Listening for a local voice round trip...')
    try {
      const response = await commandCenterApi.pushToTalk()
      setConversation((current) => {
        const next = [...current]
        if (response.transcript) {
          next.push({
            id: `voice-user-${Date.now()}`,
            role: 'user',
            content: response.transcript,
            meta: 'Voice',
          })
        }
        if (response.response) {
          next.push({
            id: `voice-assistant-${Date.now()}`,
            role: 'assistant',
            content: response.response,
            meta: response.playback_ok ? 'Spoken' : 'Ready',
          })
        }
        return next.slice(-6)
      })
      setConversationStatus(
        response.error ||
          response.issues?.[0] ||
          (response.transcript ? 'Voice round trip complete.' : 'No speech detected in that round.')
      )
    } catch (error: any) {
      setConversationStatus(error.message || 'Voice round trip failed.')
    } finally {
      setVoiceBusy(false)
    }
  }

  const startMission = async (title: string, summary: string) => {
    try {
      const response = await commandCenterApi.startMission(title, summary)
      if (response.mission) {
        setMissions((current) => [response.mission as Mission, ...current].slice(0, 6))
      }
    } catch {
      setConversationStatus('Nexus could not start that mission right now.')
    }
  }

  return (
    <div className="fade-up" style={{ padding: '0 0 48px' }}>
      <div style={{ padding: '24px 20px 16px' }}>
        <PageHeader
          eyebrow="Overview"
          title="Command center at a glance."
          description="A compact read on services, approvals, live activity, missions, and conversation so you can keep moving without hunting for status."
          meta={
            <>
              <Badge color={serviceCoverage >= 80 ? 'green' : serviceCoverage >= 50 ? 'orange' : 'red'}>
                {serviceCoverage}% healthy
              </Badge>
              <Badge color={liveApprovals.length ? 'orange' : 'green'}>
                {liveApprovals.length ? `${liveApprovals.length} approvals waiting` : 'No blockers'}
              </Badge>
              <Badge color={voiceState === 'idle' ? 'gray' : 'blue'}>{voiceState}</Badge>
            </>
          }
          actions={
            <>
              <button className="btn primary" onClick={() => navigate('/workflows')}>Open workflows</button>
              <button className="btn" onClick={() => navigate('/settings')}>Open settings</button>
            </>
          }
        />
      </div>

      <div style={{ padding: '0 20px 16px' }}>
        <Card
          style={{
            padding: 20,
            display: 'grid',
            gap: 14,
            background:
              'linear-gradient(180deg, rgba(90, 200, 250, 0.12), rgba(90, 200, 250, 0.03) 48%, var(--surface-1))',
            border: '1px solid rgba(90, 200, 250, 0.18)',
          }}
        >
          <div style={{ display: 'grid', gap: 6 }}>
            <div style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--text-3)' }}>
              Zero-Terminal Launch
            </div>
            <div style={{ fontSize: 30, fontWeight: 700, letterSpacing: '-0.05em' }}>
              Bring up JARVIS without leaving the dashboard.
            </div>
            <div style={{ maxWidth: 720, fontSize: 13, color: 'var(--text-2)', lineHeight: 1.6 }}>
              Launch the real OpenClaw TUI in-place, keep OAuth links clickable, and tear the PTY down automatically when the modal closes.
            </div>
          </div>
          <LaunchJarvisButton />
        </Card>
      </div>

      <GettingStartedCard />

      <div style={{ padding: '0 20px 16px', display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 10 }}>
        <OverviewStat label="Healthy Services" value={`${healthyServices}/${serviceEntries.length || 0}`} meta="local runtime posture" tone="green" progress={serviceCoverage} />
        <OverviewStat label="Active Tasks" value={taskCounts.active} meta={`${taskCounts.queued} queued`} tone="blue" progress={Math.min(100, (taskCounts.active + taskCounts.queued) * 12 || 8)} />
        <OverviewStat label="Pending Decisions" value={liveApprovals.length} meta={liveApprovals.length ? 'review lane active' : 'clear'} tone={liveApprovals.length ? 'orange' : 'green'} progress={liveApprovals.length ? Math.min(100, liveApprovals.length * 20) : 10} />
        <OverviewStat label="Running Models" value={runningModels} meta={voiceMode.replace(/_/g, ' ')} tone="purple" progress={Math.min(100, runningModels * 24 || 8)} />
      </div>

      <div style={{ padding: '0 20px', display: 'grid', gridTemplateColumns: '1.1fr 0.9fr', gap: 12 }}>
        <Card style={{ padding: 18, display: 'grid', gap: 12 }}>
          <PanelHeader
            eyebrow="Running Lanes"
            title={`${assistantName} and the active runtimes`}
            description="Compact runtime rows with current posture, model assignment, and service health."
            aside={<Badge color={voiceState === 'idle' ? 'gray' : 'blue'}>{voiceState}</Badge>}
          />
          <div className="grouped-list">
            {runtimeHighlights.length === 0 ? (
              <div className="row"><span style={{ color: 'var(--text-3)' }}>No runtime adapters have reported posture yet.</span></div>
            ) : (
              runtimeHighlights.map((runtime) => (
                <div key={runtime.name} className="row">
                  <span className={`dot ${runtime.status === 'running' ? 'green' : runtime.status === 'installed' ? 'orange' : 'gray'}`} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                      <span style={{ fontWeight: 600, textTransform: 'capitalize' }}>{runtime.name}</span>
                      <Badge color={runtime.status === 'running' ? 'green' : runtime.status === 'installed' ? 'orange' : 'gray'}>
                        {runtime.status}
                      </Badge>
                    </div>
                    <div className="mono" style={{ marginTop: 4, fontSize: 11, color: 'var(--text-3)' }}>{runtime.model}</div>
                  </div>
                </div>
              ))
            )}
            {serviceHealthRows.map(([name, item]) => (
              <div key={name} className="row">
                <span className={`dot ${(item?.status === 'up' || item?.status === 'running') ? 'green' : item?.status === 'degraded' ? 'orange' : 'red'}`} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600 }}>{name}</div>
                  <div style={{ marginTop: 4, color: 'var(--text-3)', fontSize: 11 }}>
                    {item?.status || 'unknown'}{item?.latency_ms ? ` - ${item.latency_ms}ms` : ''}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card style={{ padding: 18, display: 'grid', gap: 12 }}>
          <PanelHeader
            eyebrow="Recent Logs"
            title="Latest command center activity"
            description="The most recent runtime events in a compact console-style strip."
            aside={<Badge color="gray">{timeline.length}</Badge>}
          />
          <div className="log-terminal" style={{ minHeight: 250 }}>
            {timeline.length === 0 ? (
              <div style={{ color: 'var(--text-3)' }}>Waiting for fresh runtime activity.</div>
            ) : (
              timeline.map((event, index) => (
                <div key={`${event.type || 'event'}-${index}`} style={{ display: 'grid', gridTemplateColumns: '72px 84px 1fr', gap: 10, padding: '3px 0', alignItems: 'start' }}>
                  <Ts value={event.data?.timestamp || event.timestamp || Date.now()} />
                  <span style={{ color: toneForEvent(event), textTransform: 'uppercase', fontSize: 10 }}>{event.type || 'event'}</span>
                  <span style={{ color: 'var(--text-2)' }}>{eventSummary(event)}</span>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>

      <div style={{ padding: '12px 20px 0', display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 12 }}>
        <MetricMeter label="Workflow Activity" value={activityMix.workflow} total={Math.max(events.length, 1)} tone="blue" />
        <MetricMeter label="Audit Signals" value={activityMix.audit} total={Math.max(events.length, 1)} tone="orange" />
        <MetricMeter label="Low-Friction Approvals" value={approvalMix.low} total={Math.max(liveApprovals.length, 1)} tone="green" />
      </div>

      <SectionLabel>Today</SectionLabel>
      <div style={{ padding: '0 20px', display: 'grid', gridTemplateColumns: '1.1fr 0.9fr', gap: 12 }}>
        <Card style={{ padding: 18, display: 'grid', gap: 14 }}>
          <PanelHeader
            eyebrow="Briefing"
            title={briefing?.headline || 'Today is under control.'}
            description={briefing?.summary || 'Nexus is preparing the next briefing and watching for changes that matter.'}
          />
          <div className="grouped-list">
            {(briefing?.items || []).length === 0 ? (
              <div className="row"><span style={{ color: 'var(--text-3)' }}>No briefing items have landed yet.</span></div>
            ) : (
              (briefing?.items || []).map((item, index) => (
                <div key={`${item.title}-${index}`} className="row" style={{ alignItems: 'flex-start' }}>
                  <span className={`dot ${item.priority === 'high' ? 'red' : item.priority === 'medium' ? 'orange' : 'blue'}`} style={{ marginTop: 6 }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
                      <div style={{ fontWeight: 600 }}>{item.title}</div>
                      <Badge color={item.priority === 'high' ? 'red' : item.priority === 'medium' ? 'orange' : 'blue'}>
                        {item.priority || 'low'}
                      </Badge>
                    </div>
                    <div style={{ marginTop: 6, color: 'var(--text-2)', lineHeight: 1.55 }}>{item.body}</div>
                  </div>
                </div>
              ))
            )}
          </div>
        </Card>

        <Card style={{ padding: 18, display: 'grid', gap: 14 }}>
          <PanelHeader
            eyebrow="Signals"
            title="Only the interruptions that matter"
            description="The attention lane stays compact until something deserves your eyes or voice."
            aside={<Badge color="blue">{topSignals.length}</Badge>}
          />
          <div className="grouped-list">
            {topSignals.length === 0 ? (
              <div className="row"><span style={{ color: 'var(--text-3)' }}>Nothing urgent. Nexus is quietly on watch.</span></div>
            ) : (
              topSignals.map((signal) => (
                <div key={signal.id} className="row" style={{ alignItems: 'flex-start' }}>
                  <span className={`dot ${signal.urgency === 'high' ? 'red' : signal.urgency === 'medium' ? 'orange' : 'blue'}`} style={{ marginTop: 6 }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
                      <div style={{ fontWeight: 600 }}>{signal.title}</div>
                      <Badge color={signal.urgency === 'high' ? 'red' : signal.urgency === 'medium' ? 'orange' : 'gray'}>
                        {signal.surface === 'spoken-visual' ? 'spoken + visual' : signal.surface || 'visual'}
                      </Badge>
                    </div>
                    <div style={{ marginTop: 6, color: 'var(--text-2)', lineHeight: 1.55 }}>{signal.summary}</div>
                  </div>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>

      {suggestions.length > 0 && (
        <>
          <SectionLabel>Kizuna Noticed</SectionLabel>
          <div style={{ padding: '0 20px 4px', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 10 }}>
            {suggestions.map((s: any) => (
              <Card key={s.id} style={{ padding: 16, display: 'grid', gap: 10, borderLeft: `3px solid ${suggestionColor(s.category)}` }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                  <div style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.1em', color: suggestionColor(s.category) }}>
                    {s.category?.replace(/_/g, ' ') || 'noticed'}
                  </div>
                  <button
                    onClick={() => dismissSuggestion(s.id)}
                    style={{ background: 'none', border: 'none', color: 'var(--text-3)', cursor: 'pointer', fontSize: 14, lineHeight: 1, padding: 0 }}
                  >
                    ✕
                  </button>
                </div>
                <div style={{ fontWeight: 600, fontSize: 14 }}>{s.title}</div>
                <div style={{ color: 'var(--text-2)', fontSize: 12, lineHeight: 1.55 }}>{s.body}</div>
                {s.action_label && (
                  <button
                    className="btn primary"
                    style={{ fontSize: 12, padding: '6px 14px', justifySelf: 'start' }}
                    onClick={() => s.action_route && navigate(s.action_route)}
                  >
                    {s.action_label}
                  </button>
                )}
              </Card>
            ))}
          </div>
        </>
      )}

      <EvolutionLog />

      <SectionLabel>Conversation</SectionLabel>
      <div style={{ padding: '0 20px', display: 'grid', gridTemplateColumns: '1.15fr 0.85fr', gap: 12 }}>
        <Card style={{ padding: 18, display: 'grid', gap: 14 }}>
          <PanelHeader
            eyebrow="Talk To Nexus"
            title={`Voice and text with ${assistantName}`}
            description={`Tone: ${tone}. Voice mode: ${voiceMode.replace(/_/g, ' ')}.`}
            aside={<Badge color={voiceState === 'idle' ? 'gray' : 'green'}>{voiceState}</Badge>}
          />

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 10 }}>
            <MiniInfo label="Input device" value={voiceSession?.device_label || 'Default input'} />
            <MiniInfo label="Last utterance" value={voiceSession?.last_utterance || 'Waiting for voice input'} />
            <MiniInfo label="Last response" value={voiceSession?.last_response || 'No spoken reply yet'} />
          </div>

          <div style={{ display: 'grid', gap: 10 }}>
            {conversation.slice(-4).map((message) => (
              <div
                key={message.id}
                className={`conversation-bubble${message.role === 'user' ? ' user' : ''}`}
                style={{
                  marginLeft: message.role === 'assistant' ? 0 : 52,
                  marginRight: message.role === 'assistant' ? 52 : 0,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, marginBottom: 6 }}>
                  <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-3)' }}>
                    {message.role === 'assistant' ? assistantName : 'You'}
                  </div>
                  {message.meta ? <span className="mono" style={{ fontSize: 11, color: 'var(--text-3)' }}>{message.meta}</span> : null}
                </div>
                <div style={{ fontSize: 13, lineHeight: 1.6 }}>{message.content}</div>
              </div>
            ))}
          </div>

          <form onSubmit={submitConversation} style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 10 }}>
            <input
              type="text"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Ask Nexus to prepare, act, or brief you"
            />
            <button className="btn primary" type="submit" disabled={working || !draft.trim()}>
              {working ? 'Acting' : 'Send'}
            </button>
          </form>

          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center' }}>
            {conversationStatus ? <div style={{ color: 'var(--text-2)', fontSize: 12 }}>{conversationStatus}</div> : <div />}
            <div style={{ color: 'var(--text-3)', fontSize: 12 }}>
              <Ts value={voiceSession?.updated_at} /> {voiceMode === 'off' ? 'Voice is disabled right now.' : 'Ctrl+Shift+Space also starts push-to-talk.'}
            </div>
          </div>
        </Card>

        <Card style={{ padding: 18, display: 'grid', gap: 12 }}>
          <PanelHeader
            eyebrow="Quick Actions"
            title="Start trusted work quickly"
            description="Mission shortcuts stay close to the conversation lane."
          />
          <button className="btn" onClick={pushToTalk} disabled={voiceBusy || voiceMode === 'off'}>
            {voiceBusy ? 'Listening...' : voiceMode === 'off' ? 'Voice off' : 'Push to talk'}
          </button>
          <button className="btn" onClick={() => startMission('Refresh today briefing', 'Rebuild the briefing after schedule or inbox changes.')}>
            Refresh today briefing
          </button>
          <button className="btn" onClick={() => startMission('Pre-meeting packet', 'Prepare a concise packet for the next important meeting.')}>
            Prepare meeting packet
          </button>
          <button className="btn" onClick={() => startMission('Inbox triage loop', 'Review drafts, reminders, and follow-ups without sending risky content.')}>
            Start inbox triage
          </button>
          <button className="btn primary" onClick={() => navigate('/packs')}>Open packs</button>
        </Card>
      </div>

      <SectionLabel>Mission And Review</SectionLabel>
      <div style={{ padding: '0 20px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <Card style={{ padding: 18, display: 'grid', gap: 12 }}>
          <PanelHeader
            eyebrow="Mission Queue"
            title="Long-running objectives"
            description="Active work with checkpoints, summaries, and the current trust lane."
            aside={<Badge color="blue">{topMissions.length}</Badge>}
          />
          <div className="grouped-list">
            {topMissions.length === 0 ? (
              <div className="row"><span style={{ color: 'var(--text-3)' }}>No active missions yet.</span></div>
            ) : (
              topMissions.map((mission) => (
                <div key={mission.id} className="row" style={{ alignItems: 'flex-start' }}>
                  <span className={`dot ${mission.blocked ? 'red' : mission.status === 'active' ? 'blue' : 'gray'}`} style={{ marginTop: 6 }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
                      <div style={{ fontWeight: 600 }}>{mission.title}</div>
                      <Badge color={mission.blocked ? 'red' : mission.status === 'active' ? 'blue' : 'gray'}>
                        {mission.blocked ? 'blocked' : mission.status || 'idle'}
                      </Badge>
                    </div>
                    <div style={{ marginTop: 6, color: 'var(--text-2)', lineHeight: 1.55 }}>{mission.summary}</div>
                    <div style={{ marginTop: 8, display: 'flex', gap: 12, color: 'var(--text-3)', fontSize: 11 }}>
                      <span className="mono">{mission.checkpoint || 'monitoring'}</span>
                      <span className="mono">{mission.trust_lane || 'automatic'}</span>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </Card>

        <Card style={{ padding: 18, display: 'grid', gap: 12 }}>
          <PanelHeader
            eyebrow="Pending Decisions"
            title="Approval pressure"
            description="The review lane stays visible, but compact."
            aside={<Badge color={liveApprovals.length ? 'orange' : 'green'}>{liveApprovals.length ? 'Pending' : 'Clear'}</Badge>}
          />
          <div className="grouped-list">
            {liveApprovals.length === 0 ? (
              <div className="row"><span style={{ color: 'var(--text-3)' }}>No decisions are waiting right now.</span></div>
            ) : (
              liveApprovals.slice(0, 4).map((approval, index) => (
                <div key={approval.id || index} className="row" style={{ alignItems: 'flex-start' }}>
                  <span className={`dot ${approval.risk === 'high' ? 'red' : approval.risk === 'low' ? 'blue' : 'orange'}`} style={{ marginTop: 6 }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
                      <div style={{ fontWeight: 600 }}>{approval.tool || 'Sensitive action'}</div>
                      <Badge color={approval.risk === 'high' ? 'red' : approval.risk === 'low' ? 'blue' : 'orange'}>
                        {approval.risk || 'medium'}
                      </Badge>
                    </div>
                    <div style={{ marginTop: 6, color: 'var(--text-2)' }}>{approval.target || 'Awaiting decision'}</div>
                  </div>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>
    </div>
  )
}

type EvolutionEntry = { date: string; title: string; what_happened: string; root_cause: string; what_learned: string; fix_shipped: string }

function EvolutionLog() {
  const [entries, setEntries] = useState<EvolutionEntry[]>([])
  const [open, setOpen] = useState(false)

  useEffect(() => {
    fetch('/api/evolution', { credentials: 'include' })
      .then(r => r.ok ? r.json() : { entries: [] })
      .then(d => setEntries(d.entries || []))
      .catch(() => null)
  }, [])

  if (!entries.length) return null

  return (
    <>
      <SectionLabel>
        <span style={{ cursor: 'pointer', userSelect: 'none' }} onClick={() => setOpen(o => !o)}>
          What Kizuna Learned {open ? '▾' : '▸'} <span style={{ fontSize: 11, color: 'var(--text-3)', fontWeight: 400 }}>{entries.length} entries</span>
        </span>
      </SectionLabel>
      {open && (
        <div style={{ padding: '0 20px 4px', display: 'grid', gap: 10 }}>
          {entries.map((e, i) => (
            <Card key={i} style={{ padding: 16, display: 'grid', gap: 8, borderLeft: '3px solid var(--accent)' }}>
              <div style={{ display: 'flex', gap: 12, alignItems: 'baseline' }}>
                <span style={{ fontSize: 11, color: 'var(--text-3)' }}>{e.date}</span>
                <span style={{ fontWeight: 600, fontSize: 14 }}>{e.title}</span>
              </div>
              {e.what_happened && <div style={{ fontSize: 12, color: 'var(--text-2)', lineHeight: 1.5 }}><strong>What happened:</strong> {e.what_happened}</div>}
              {e.what_learned && <div style={{ fontSize: 12, color: 'var(--text-2)', lineHeight: 1.5 }}><strong>Learned:</strong> {e.what_learned}</div>}
              {e.fix_shipped && <div style={{ fontSize: 12, color: 'var(--green)', lineHeight: 1.5 }}><strong>Fix:</strong> {e.fix_shipped}</div>}
            </Card>
          ))}
        </div>
      )}
    </>
  )
}

function OverviewStat({
  label,
  value,
  meta,
  tone,
  progress,
}: {
  label: string
  value: string | number
  meta: string
  tone: 'blue' | 'green' | 'orange' | 'purple'
  progress: number
}) {
  return (
    <Card style={{ padding: 16, display: 'grid', gap: 10 }}>
      <div style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--text-3)' }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 700, letterSpacing: '-0.04em' }}>{value}</div>
      <div style={{ fontSize: 12, color: 'var(--text-2)' }}>{meta}</div>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${Math.max(10, Math.min(100, progress))}%`, background: toneColor(tone) }} />
      </div>
    </Card>
  )
}

function MetricMeter({
  label,
  value,
  total,
  tone,
}: {
  label: string
  value: number
  total: number
  tone: 'blue' | 'green' | 'orange'
}) {
  const width = Math.max(8, Math.round((Math.max(value, 0) / Math.max(total, 1)) * 100))
  return (
    <Card style={{ padding: 16, display: 'grid', gap: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
        <div style={{ fontSize: 12, color: 'var(--text-2)' }}>{label}</div>
        <div className="mono" style={{ fontSize: 11, color: toneColor(tone) }}>{value}/{total}</div>
      </div>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${width}%`, background: toneColor(tone) }} />
      </div>
    </Card>
  )
}

function MiniInfo({ label, value }: { label: string; value: string }) {
  return (
    <div className="glass" style={{ padding: 12 }}>
      <div style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--text-3)' }}>{label}</div>
      <div style={{ marginTop: 8, color: 'var(--text)', lineHeight: 1.5 }}>{value}</div>
    </div>
  )
}

function toneColor(tone: 'blue' | 'green' | 'orange' | 'purple') {
  if (tone === 'green') return 'var(--green)'
  if (tone === 'orange') return 'var(--orange)'
  if (tone === 'purple') return 'var(--purple)'
  return 'var(--blue)'
}

function toneForEvent(event: EventRecord) {
  if (event.type === 'workflow_error') return 'var(--red)'
  if (event.type === 'workflow_progress') return 'var(--blue)'
  if (event.type === 'audit_event') return 'var(--orange)'
  if (event.type === 'service_health') return 'var(--green)'
  return 'var(--text-3)'
}

function suggestionColor(category: string) {
  if (category === 'approval_needed') return 'var(--red)'
  if (category === 'system_health') return 'var(--orange)'
  if (category === 'nexus_noticed') return 'var(--purple)'
  if (category === 'briefing_ready') return 'var(--blue)'
  if (category === 'brain_update') return '#7c6af5'
  if (category === 'workflow_nudge') return 'var(--green)'
  return 'var(--text-3)'
}

function eventSummary(event: EventRecord) {
  const data = event.data || {}
  if (event.type === 'workflow_progress') {
    return `${data.id || 'workflow'} is ${data.status || 'running'}${data.output ? `: ${String(data.output).slice(0, 90)}` : ''}`
  }
  if (event.type === 'workflow_error') {
    return `${data.id || 'workflow'} failed${data.error ? `: ${String(data.error).slice(0, 90)}` : ''}`
  }
  if (event.type === 'service_health') {
    return 'Service health snapshot refreshed.'
  }
  if (event.type === 'audit_event') {
    return JSON.stringify(data).slice(0, 110)
  }
  return JSON.stringify(data).slice(0, 110) || 'No details yet.'
}
