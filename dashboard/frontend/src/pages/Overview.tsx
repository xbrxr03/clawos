/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { FormEvent, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Badge, Card, PageHeader, PanelHeader, SectionLabel, StatusDot, Ts } from '../components/ui.jsx'
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
      content: 'Nexus is online. I am tracking your day, your approvals, and anything that needs a decision.',
      meta: 'Ready',
    },
  ])
  const [working, setWorking] = useState(false)
  const [conversationStatus, setConversationStatus] = useState('')
  const [voiceBusy, setVoiceBusy] = useState(false)

  useEffect(() => {
    Promise.all([
      commandCenterApi.getPresence(),
      commandCenterApi.getTodayBriefing(),
      commandCenterApi.listAttention(),
      commandCenterApi.listMissions(),
      commandCenterApi.listApprovals(),
    ])
      .then(([presencePayload, briefingPayload, attentionPayload, missionPayload, approvalPayload]) => {
        setPresence(presencePayload)
        setBriefing(briefingPayload)
        setSignals(Array.isArray(attentionPayload) ? attentionPayload : [])
        setMissions(Array.isArray(missionPayload) ? missionPayload : [])
        setLiveApprovals(Array.isArray(approvalPayload) ? approvalPayload : [])
      })
      .catch(() => null)
  }, [])

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
  const tone = presence?.profile?.tone || 'crisp-executive'

  const timeline = useMemo(() => events.slice(0, 6), [events])
  const serviceCoverage = serviceEntries.length ? Math.round((healthyServices / serviceEntries.length) * 100) : 0
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
  const runtimeHighlights = Object.entries(runtimes || {})
    .slice(0, 4)
    .map(([name, item]) => ({
      name,
      status: item?.running ? 'running' : item?.installed ? 'installed' : 'missing',
      model: item?.model || 'unassigned',
    }))

  const submitConversation = async (event: FormEvent) => {
    event.preventDefault()
    const message = draft.trim()
    if (!message || working) return

    setWorking(true)
    setConversationStatus('Nexus is acting on that now.')
    setConversation((current) => [
      ...current,
      { id: `user-${Date.now()}`, role: 'user', content: message },
      {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: 'Understood. I queued the work and will surface only the parts that need you.',
        meta: 'Queued',
      },
    ])
    setDraft('')

    try {
      const response = await commandCenterApi.sendConversationMessage(message)
      setConversationStatus(response.task_id ? `Task ${response.task_id} queued.` : 'Request queued.')
    } catch (error: any) {
      setConversationStatus(error.message || 'Nexus could not queue that request.')
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
        setSignals((current) => [
          {
            id: `mission-${Date.now()}`,
            title: 'Mission started',
            summary: `${title} is now active in Nexus.`,
            urgency: 'low',
            surface: 'visual',
            category: 'mission',
          },
          ...current,
        ].slice(0, 4))
      }
    } catch {
      setConversationStatus('Nexus could not start that mission right now.')
    }
  }

  const topSignals = signals.slice(0, 4)
  const topMissions = missions.slice(0, 4)

  return (
    <div className="fade-up" style={{ padding: '0 0 40px' }}>
      <div style={{ padding: '28px 24px 0', display: 'grid', gap: 16 }}>
        <PageHeader
          eyebrow="Overview"
          title="Your command center is live."
          description="Real-time posture across services, missions, approvals, and conversation lanes. This is the fastest read on what Nexus is doing for you right now."
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
              <button className="btn" onClick={() => navigate('/settings')}>Refine presence</button>
            </>
          }
        />

        <Card
          style={{
            padding: 24,
            display: 'grid',
            gridTemplateColumns: '1.1fr 0.9fr',
            gap: 18,
            alignItems: 'stretch',
            background:
              'radial-gradient(circle at top left, rgba(77,143,247,0.18), transparent 36%), linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02))',
          }}
        >
          <div style={{ display: 'grid', gap: 14 }}>
            <div className="section-label">Nexus</div>
            <div style={{ fontSize: 36, fontWeight: 700, letterSpacing: '-0.06em', lineHeight: 1.03, maxWidth: 640 }}>
              {assistantName} is ready to run your day, not just answer questions.
            </div>
            <div style={{ color: 'var(--text-3)', fontSize: 14, maxWidth: 580 }}>
              A calm, conversational operator that prepares, acts inside trusted lanes, and surfaces only what matters. The command center is now your desktop home for today, missions, decisions, and signals.
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <MetricPanel label="Voice mode" value={voiceMode.replace('_', ' ')} tone="blue" />
            <MetricPanel label="Voice state" value={voiceState} tone={voiceState === 'idle' ? 'gray' : 'green'} />
            <MetricPanel label="Pending decisions" value={liveApprovals.length} tone={liveApprovals.length ? 'orange' : 'green'} />
            <MetricPanel label="Active missions" value={topMissions.length} tone={topMissions.length ? 'blue' : 'gray'} />
          </div>
        </Card>
      </div>

      <SectionLabel>At A Glance</SectionLabel>
      <div style={{ padding: '0 24px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <Card style={{ padding: 20, display: 'grid', gap: 16 }}>
          <PanelHeader
            eyebrow="Pulse"
            title="Service and task health"
            description="Real usage signals instead of placeholder stats."
            aside={<Badge color={serviceCoverage >= 80 ? 'green' : serviceCoverage >= 50 ? 'orange' : 'red'}>{serviceCoverage}% ready</Badge>}
          />
          <BarRow label="Healthy services" value={healthyServices} total={serviceEntries.length || 1} tone="green" />
          <BarRow label="Active tasks" value={taskCounts.active} total={Math.max(taskCounts.active + taskCounts.queued + taskCounts.completed + taskCounts.failed, 1)} tone="blue" />
          <BarRow label="Queued tasks" value={taskCounts.queued} total={Math.max(taskCounts.active + taskCounts.queued + taskCounts.completed + taskCounts.failed, 1)} tone="orange" />
          <BarRow label="Running models" value={runningModels} total={Math.max((models.models || []).length, 1)} tone="purple" />
        </Card>

        <Card style={{ padding: 20, display: 'grid', gap: 16 }}>
          <PanelHeader
            eyebrow="Flow"
            title="Recent activity mix"
            description="What the command center has been handling in the latest event window."
            aside={<Badge color="blue">{events.length} events</Badge>}
          />
          <BarRow label="Workflow activity" value={activityMix.workflow} total={Math.max(events.length, 1)} tone="blue" />
          <BarRow label="Service health" value={activityMix.service} total={Math.max(events.length, 1)} tone="green" />
          <BarRow label="Audit signals" value={activityMix.audit} total={Math.max(events.length, 1)} tone="orange" />
          <BarRow label="Other events" value={activityMix.other} total={Math.max(events.length, 1)} tone="gray" />
        </Card>
      </div>

      <div style={{ padding: '12px 24px 0', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <Card style={{ padding: 20, display: 'grid', gap: 14 }}>
          <PanelHeader
            eyebrow="Runtimes"
            title="Model posture"
            description="Which execution lanes are warm and what model each lane is carrying."
          />
          {runtimeHighlights.length === 0 ? (
            <div style={{ color: 'var(--text-3)', fontSize: 13 }}>No runtime adapters have reported posture yet.</div>
          ) : (
            <div style={{ display: 'grid', gap: 10 }}>
              {runtimeHighlights.map((runtime) => (
                <div key={runtime.name} style={{ padding: 14, borderRadius: 14, background: 'var(--surface-2)', border: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, textTransform: 'capitalize' }}>{runtime.name}</div>
                    <div className="mono" style={{ marginTop: 4, fontSize: 11, color: 'var(--text-3)' }}>{runtime.model}</div>
                  </div>
                  <Badge color={runtime.status === 'running' ? 'green' : runtime.status === 'installed' ? 'blue' : 'gray'}>
                    {runtime.status}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card style={{ padding: 20, display: 'grid', gap: 14 }}>
          <PanelHeader
            eyebrow="Decisions"
            title="Approval pressure"
            description="Which review lane is most likely to interrupt your flow."
          />
          <BarRow label="High risk" value={liveApprovals.filter((item) => item.risk === 'high').length} total={Math.max(liveApprovals.length, 1)} tone="red" />
          <BarRow label="Medium risk" value={liveApprovals.filter((item) => !item.risk || item.risk === 'medium').length} total={Math.max(liveApprovals.length, 1)} tone="orange" />
          <BarRow label="Low risk" value={liveApprovals.filter((item) => item.risk === 'low').length} total={Math.max(liveApprovals.length, 1)} tone="blue" />
          <div style={{ color: 'var(--text-3)', fontSize: 12 }}>
            {liveApprovals.length === 0
              ? 'No approval queue right now, so Nexus can stay in trusted lanes.'
              : 'Approval-sensitive work is visible here before it becomes a blocker.'}
          </div>
        </Card>
      </div>

      <SectionLabel>Today</SectionLabel>
      <div style={{ padding: '0 24px', display: 'grid', gridTemplateColumns: '1.1fr 0.9fr', gap: 12 }}>
        <Card style={{ padding: 20, display: 'grid', gap: 14 }}>
          <div>
            <div style={{ fontSize: 20, fontWeight: 700, letterSpacing: '-0.03em' }}>{briefing?.headline || 'Today is under control.'}</div>
            <div style={{ marginTop: 8, color: 'var(--text-3)', fontSize: 14 }}>
              {briefing?.summary || 'Nexus is preparing a briefing and watching for any changes that matter.'}
            </div>
          </div>
          <div style={{ display: 'grid', gap: 10 }}>
            {(briefing?.items || []).map((item, index) => (
              <div key={`${item.title}-${index}`} style={{ padding: 14, borderRadius: 14, background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                  <div style={{ fontSize: 14, fontWeight: 600 }}>{item.title}</div>
                  <Badge color={item.priority === 'high' ? 'red' : item.priority === 'medium' ? 'orange' : 'blue'}>
                    {item.priority || 'low'}
                  </Badge>
                </div>
                <div style={{ marginTop: 6, fontSize: 13, color: 'var(--text-3)', lineHeight: 1.5 }}>{item.body}</div>
              </div>
            ))}
          </div>
        </Card>

        <Card style={{ padding: 20, display: 'grid', gap: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 18, fontWeight: 600 }}>Signals</div>
              <div style={{ color: 'var(--text-3)', fontSize: 12, marginTop: 4 }}>
                Nexus only interrupts for things worth your attention.
              </div>
            </div>
            <Badge color="blue">{topSignals.length}</Badge>
          </div>

          <div style={{ display: 'grid', gap: 10 }}>
            {topSignals.length === 0 ? (
              <div style={{ color: 'var(--text-3)', fontSize: 13 }}>Nothing urgent. Nexus is quietly on watch.</div>
            ) : (
              topSignals.map((signal) => (
                <div key={signal.id} style={{ padding: 14, borderRadius: 14, background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center' }}>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{signal.title}</div>
                    <Badge color={signal.urgency === 'high' ? 'red' : signal.urgency === 'medium' ? 'orange' : 'blue'}>
                      {signal.surface === 'spoken-visual' ? 'spoken + visual' : signal.surface || 'log'}
                    </Badge>
                  </div>
                  <div style={{ marginTop: 6, fontSize: 12, color: 'var(--text-3)', lineHeight: 1.5 }}>{signal.summary}</div>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>

      <SectionLabel>Conversation</SectionLabel>
      <div style={{ padding: '0 24px', display: 'grid', gridTemplateColumns: '1fr', gap: 12 }}>
        <Card style={{ padding: 20, display: 'grid', gap: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 18, fontWeight: 600 }}>Talk to {assistantName}</div>
              <div style={{ color: 'var(--text-3)', fontSize: 12, marginTop: 4 }}>
                Tone: {tone}. Voice mode: {voiceMode.replace('_', ' ')}. Follow-up windows stay short by default.
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <Badge color={voiceState === 'idle' ? 'gray' : 'green'}>{voiceState}</Badge>
              <button className="btn" type="button" onClick={pushToTalk} disabled={voiceBusy || voiceMode === 'off'}>
                {voiceBusy ? 'Listening...' : voiceMode === 'off' ? 'Voice off' : 'Push to talk'}
              </button>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
            <SmallMetric label="Input device" value={voiceSession?.device_label || 'Default input'} />
            <SmallMetric label="Last utterance" value={voiceSession?.last_utterance || 'Waiting for voice input'} />
            <SmallMetric label="Last response" value={voiceSession?.last_response || 'No spoken reply yet'} />
          </div>

          <div style={{ display: 'grid', gap: 10 }}>
            {conversation.slice(-4).map((message) => (
              <div
                key={message.id}
                style={{
                  padding: 14,
                  borderRadius: 16,
                  background: message.role === 'assistant' ? 'var(--surface-2)' : 'rgba(77,143,247,0.12)',
                  border: '1px solid var(--border)',
                  marginLeft: message.role === 'assistant' ? 0 : 56,
                  marginRight: message.role === 'assistant' ? 56 : 0,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, marginBottom: 6 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase', color: 'var(--text-3)' }}>
                    {message.role === 'assistant' ? assistantName : 'You'}
                  </div>
                  {message.meta && <span className="mono" style={{ fontSize: 11, color: 'var(--text-3)' }}>{message.meta}</span>}
                </div>
                <div style={{ fontSize: 14, lineHeight: 1.6 }}>{message.content}</div>
              </div>
            ))}
          </div>

          <form onSubmit={submitConversation} style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 10 }}>
            <input
              type="text"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Ask Nexus to prepare, act, or brief you"
              style={{
                width: '100%',
                padding: '12px 14px',
                borderRadius: 14,
                border: '1px solid var(--border)',
                background: 'var(--surface-2)',
                color: 'var(--text)',
              }}
            />
            <button className="btn primary" type="submit" disabled={working || !draft.trim()}>
              {working ? 'Acting' : 'Send'}
            </button>
          </form>

          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center' }}>
            {conversationStatus ? <div style={{ color: 'var(--text-3)', fontSize: 12 }}>{conversationStatus}</div> : <div />}
            <div style={{ color: 'var(--text-3)', fontSize: 12 }}>
              <Ts value={voiceSession?.updated_at} /> {voiceMode === 'off' ? 'Voice is disabled right now.' : 'Ctrl+Shift+Space also starts push-to-talk.'}
            </div>
          </div>
        </Card>
      </div>

      <SectionLabel>Active Missions</SectionLabel>
      <div style={{ padding: '0 24px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <Card style={{ padding: 20, display: 'grid', gap: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
            <div>
              <div style={{ fontSize: 18, fontWeight: 600 }}>Mission queue</div>
              <div style={{ color: 'var(--text-3)', fontSize: 12, marginTop: 4 }}>
                Long-running objectives with checkpoints, summaries, and escalation.
              </div>
            </div>
            <Badge color="blue">{topMissions.length}</Badge>
          </div>

          <div style={{ display: 'grid', gap: 10 }}>
            {topMissions.length === 0 ? (
              <div style={{ color: 'var(--text-3)', fontSize: 13 }}>No active missions yet.</div>
            ) : (
              topMissions.map((mission) => (
                <div key={mission.id} style={{ padding: 14, borderRadius: 14, background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center' }}>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{mission.title}</div>
                    <Badge color={mission.blocked ? 'red' : mission.status === 'active' ? 'blue' : 'gray'}>
                      {mission.blocked ? 'blocked' : mission.status || 'idle'}
                    </Badge>
                  </div>
                  <div style={{ marginTop: 6, fontSize: 12, color: 'var(--text-3)', lineHeight: 1.5 }}>{mission.summary}</div>
                  <div style={{ marginTop: 8, display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                    <span className="mono" style={{ fontSize: 11 }}>{mission.checkpoint || 'monitoring'}</span>
                    <span className="mono" style={{ fontSize: 11 }}>{mission.trust_lane || 'automatic'}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </Card>

        <Card style={{ padding: 20, display: 'grid', gap: 12 }}>
          <div>
            <div style={{ fontSize: 18, fontWeight: 600 }}>Quick starts</div>
            <div style={{ color: 'var(--text-3)', fontSize: 12, marginTop: 4 }}>
              Launch a trusted mission without digging through workflows.
            </div>
          </div>
          <button className="btn" onClick={() => startMission('Refresh today briefing', 'Rebuild the briefing after schedule or inbox changes.')}>
            Refresh today briefing
          </button>
          <button className="btn" onClick={() => startMission('Pre-meeting packet', 'Prepare a concise packet for the next important meeting.')}>
            Pre-meeting packet
          </button>
          <button className="btn" onClick={() => startMission('Inbox triage loop', 'Review drafts, reminders, and follow-ups without sending risky content.')}>
            Inbox triage loop
          </button>
          <button className="btn" onClick={() => navigate('/packs')}>Open packs</button>
        </Card>
      </div>

      <SectionLabel>Pending Decisions</SectionLabel>
      <div style={{ padding: '0 24px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <Card style={{ padding: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
            <div>
              <div style={{ fontSize: 18, fontWeight: 600 }}>Approvals</div>
              <div style={{ color: 'var(--text-3)', fontSize: 12, marginTop: 4 }}>
                Sensitive or irreversible actions still pause for your review.
              </div>
            </div>
            <Badge color={liveApprovals.length ? 'orange' : 'green'}>{liveApprovals.length ? 'Pending' : 'Clear'}</Badge>
          </div>

          <div style={{ display: 'grid', gap: 10 }}>
            {liveApprovals.length === 0 ? (
              <div style={{ color: 'var(--text-3)', fontSize: 13 }}>No decisions are waiting right now.</div>
            ) : (
              liveApprovals.slice(0, 4).map((approval, index) => (
                <div key={approval.id || index} style={{ padding: 14, borderRadius: 14, background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{approval.tool || 'Sensitive action'}</div>
                    <Badge color={approval.risk === 'high' ? 'red' : approval.risk === 'low' ? 'blue' : 'orange'}>
                      {approval.risk || 'medium'}
                    </Badge>
                  </div>
                  <div style={{ marginTop: 6, fontSize: 12, color: 'var(--text-3)' }}>{approval.target || 'Awaiting decision'}</div>
                </div>
              ))
            )}
          </div>
        </Card>

        <Card style={{ padding: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
            <div>
              <div style={{ fontSize: 18, fontWeight: 600 }}>System posture</div>
              <div style={{ color: 'var(--text-3)', fontSize: 12, marginTop: 4 }}>
                Still visible, but secondary to what Nexus is doing for you.
              </div>
            </div>
            <Badge color={healthyServices === serviceEntries.length ? 'green' : 'orange'}>
              {healthyServices}/{serviceEntries.length || 0}
            </Badge>
          </div>

          <div style={{ display: 'grid', gap: 10 }}>
            <SmallMetric label="Healthy services" value={`${healthyServices}/${serviceEntries.length || 0}`} />
            <SmallMetric label="Running models" value={runningModels} />
            <SmallMetric label="Active tasks" value={taskCounts.active} />
            <SmallMetric label="Queued tasks" value={taskCounts.queued} />
          </div>
        </Card>
      </div>

      <SectionLabel>Activity</SectionLabel>
      <div style={{ padding: '0 24px', display: 'grid', gridTemplateColumns: '1fr', gap: 12 }}>
        <Card style={{ padding: 20 }}>
          <div style={{ display: 'grid', gap: 10 }}>
            {timeline.length === 0 ? (
              <div style={{ color: 'var(--text-3)', fontSize: 13 }}>Waiting for fresh runtime activity.</div>
            ) : (
              timeline.map((event, index) => (
                <div key={`${event.type || 'event'}-${index}`} style={{ padding: 14, borderRadius: 14, background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <StatusDot status={event.type === 'workflow_error' ? 'failed' : 'active'} />
                      <span className="mono" style={{ fontSize: 11, color: 'var(--text-2)' }}>{event.type || 'event'}</span>
                    </div>
                    <Ts value={event.data?.timestamp || event.timestamp || Date.now()} />
                  </div>
                  <div style={{ marginTop: 8, color: 'var(--text-3)', fontSize: 12, lineHeight: 1.5 }}>
                    {eventSummary(event)}
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

function MetricPanel({ label, value, tone }: { label: string; value: string | number; tone: 'blue' | 'green' | 'orange' | 'gray' }) {
  const color =
    tone === 'green' ? 'var(--green)' : tone === 'orange' ? 'var(--orange)' : tone === 'blue' ? 'var(--blue)' : 'var(--text)'
  return (
    <div
      style={{
        borderRadius: 18,
        padding: 16,
        border: '1px solid var(--border)',
        background: 'rgba(255,255,255,0.05)',
      }}
    >
      <div style={{ fontSize: 24, fontWeight: 700, letterSpacing: '-0.04em', textTransform: 'capitalize' }}>{value}</div>
      <div style={{ marginTop: 6, fontSize: 12, color }}>{label}</div>
    </div>
  )
}

function SmallMetric({ label, value }: { label: string; value: string | number }) {
  return (
    <div style={{ borderRadius: 12, padding: 12, background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
      <div style={{ fontSize: 24, fontWeight: 700, letterSpacing: '-0.04em', color: 'var(--text)' }}>{value}</div>
      <div style={{ marginTop: 4, color: 'var(--text-3)', fontSize: 12 }}>{label}</div>
    </div>
  )
}

function BarRow({
  label,
  value,
  total,
  tone,
}: {
  label: string
  value: number
  total: number
  tone: 'blue' | 'green' | 'orange' | 'red' | 'gray' | 'purple'
}) {
  const color = {
    blue: 'var(--blue)',
    green: 'var(--green)',
    orange: 'var(--orange)',
    red: 'var(--red)',
    gray: 'var(--text-3)',
    purple: 'var(--purple)',
  }[tone]
  const width = Math.max(8, Math.round((Math.max(value, 0) / Math.max(total, 1)) * 100))

  return (
    <div style={{ display: 'grid', gap: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 13 }}>
        <span style={{ color: 'var(--text-2)' }}>{label}</span>
        <span className="mono" style={{ color }}>{value}/{total}</span>
      </div>
      <div style={{ height: 9, borderRadius: 999, background: 'var(--surface-2)', border: '1px solid var(--border)', overflow: 'hidden' }}>
        <div style={{ width: `${width}%`, height: '100%', borderRadius: 999, background: color }} />
      </div>
    </div>
  )
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
