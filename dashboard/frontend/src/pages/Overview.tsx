/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { FormEvent, useEffect, useRef, useState } from 'react'
import {
  commandCenterApi,
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
type ConversationMessage = { id: string; role: 'assistant' | 'user'; content: string }

const QUICK_SUGGESTIONS = ['Run morning brief', 'Show disk report', 'Triage PRs', "What's next?"]

export function Overview({
  services,
  tasks,
  approvals,
  events,
  models,
  runtimes = {},
  voiceSession: _voiceSession = null,
}: {
  services: ServiceMap
  tasks: TaskMap
  approvals: ApprovalRecord[]
  events: EventRecord[]
  models: ModelRecord
  runtimes?: RuntimeRecord
  voiceSession?: VoiceSession | null
}) {
  const [presence, setPresence] = useState<PresencePayload | null>(null)
  const [missions, setMissions] = useState<Mission[]>([])
  const [liveApprovals, setLiveApprovals] = useState<ApprovalRecord[]>(approvals || [])
  const [draft, setDraft] = useState('')
  const [conversation, setConversation] = useState<ConversationMessage[]>([
    { id: 'nexus-welcome', role: 'assistant', content: 'Nexus is online. Services up, trusted lanes watching.' },
  ])
  const [working, setWorking] = useState(false)
  const msgsRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    Promise.all([
      commandCenterApi.getPresence(),
      commandCenterApi.listMissions(),
      commandCenterApi.listApprovals(),
    ])
      .then(([presencePayload, missionPayload, approvalPayload]) => {
        setPresence(presencePayload)
        setMissions(Array.isArray(missionPayload) ? missionPayload : [])
        setLiveApprovals(Array.isArray(approvalPayload) ? approvalPayload : [])
      })
      .catch(() => null)
  }, [])

  useEffect(() => {
    setLiveApprovals((cur) => (cur.length ? cur : approvals || []))
  }, [approvals])

  useEffect(() => {
    if (msgsRef.current) {
      msgsRef.current.scrollTop = msgsRef.current.scrollHeight
    }
  }, [conversation])

  const serviceEntries = Object.entries(services || {})
  const healthyServices = serviceEntries.filter(([, v]) => v?.status === 'up' || v?.status === 'running').length
  const taskCounts = { active: tasks.active?.length ?? 0, queued: tasks.queued?.length ?? 0 }
  const runningModels = (models.models || []).filter((m) => m.running).length
  const serviceCoverage = serviceEntries.length ? Math.round((healthyServices / serviceEntries.length) * 100) : 100
  const assistantName = presence?.profile?.assistant_identity || 'Nexus'

  const runtimeRows = Object.entries(runtimes || {}).slice(0, 3).map(([name, v]) => ({
    name,
    running: !!v?.running,
    model: v?.model || 'unassigned',
    icon: name[0].toUpperCase(),
  }))

  const recentEvents = events.slice(0, 8)
  const activeMissions = missions.filter((m) => m.status === 'active' || m.status === 'running')

  const submitConversation = async (e: FormEvent) => {
    e.preventDefault()
    const message = draft.trim()
    if (!message || working) return
    setWorking(true)
    const assistantId = `a-${Date.now()}`
    setConversation((c) => [
      ...c,
      { id: `u-${Date.now()}`, role: 'user', content: message },
      { id: assistantId, role: 'assistant', content: '…' },
    ])
    setDraft('')
    try {
      const res = await commandCenterApi.sendConversationMessage(message)
      const taskId = (res as any).task_id
      let result = ''
      if (taskId) {
        for (let i = 0; i < 60; i++) {
          await new Promise((r) => setTimeout(r, 500))
          const t = await commandCenterApi.getTask(taskId)
          if (t.status === 'completed') { result = t.result || '(done)'; break }
          if (t.status === 'failed') { result = t.error || 'Task failed.'; break }
        }
      }
      if (!result) result = 'Nexus did not respond in time.'
      setConversation((c) => c.map((m) => m.id === assistantId ? { ...m, content: result } : m))
    } catch (err: any) {
      setConversation((c) =>
        c.map((m) => m.id === assistantId ? { ...m, content: err.message || 'Error.' } : m),
      )
    } finally {
      setWorking(false)
    }
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', height: '100%', overflow: 'hidden', flex: 1 }}>
      {/* ── Main scrollable area ── */}
      <main className="main">
        <div className="main-head">
          <div>
            <h1>Overview</h1>
            <div className="sub">signal-rich snapshot — services, approvals, activity, conversation</div>
          </div>
          <div className="chips">
            <span className="chip">
              <span className="d" style={{ background: 'var(--success)', color: 'var(--success)' }} />
              {healthyServices} up
            </span>
            {liveApprovals.length > 0 && (
              <span className="chip">
                <span className="d" style={{ background: 'var(--warn)', color: 'var(--warn)' }} />
                {liveApprovals.length} approvals
              </span>
            )}
            <span className="chip">
              <span className="d" style={{ background: 'var(--blue)', color: 'var(--blue)' }} />
              {taskCounts.active} running
            </span>
          </div>
        </div>

        {/* Stats row */}
        <div className="stats">
          <StatCard
            label="Services"
            value={`${healthyServices}`}
            unit={`/ ${serviceEntries.length}`}
            meta={serviceCoverage === 100 ? 'all healthy' : `${serviceCoverage}% healthy`}
            metaColor={serviceCoverage >= 80 ? 'var(--success)' : 'var(--warn)'}
            barWidth={serviceCoverage}
            barColor="var(--success)"
          />
          <StatCard
            label="Approvals"
            value={`${liveApprovals.length}`}
            meta={liveApprovals.length ? 'review lane active' : 'clear'}
            metaColor={liveApprovals.length ? 'var(--warn)' : 'var(--ink-3)'}
            barWidth={Math.min(100, liveApprovals.length * 20)}
            barColor="var(--warn)"
          />
          <StatCard
            label="Tasks"
            value={`${taskCounts.active + taskCounts.queued}`}
            meta={`${taskCounts.active} running · ${taskCounts.queued} queued`}
            barWidth={Math.min(100, (taskCounts.active + taskCounts.queued) * 12 || 8)}
            barColor="var(--accent)"
          />
          <StatCard
            label="Models"
            value={`${runningModels}`}
            meta="running models"
            barWidth={Math.min(100, runningModels * 24 || 8)}
            barColor="var(--blue)"
          />
        </div>

        {/* Services + Missions/Approvals */}
        <div className="grid2">
          {/* Services panel */}
          <div className="p">
            <h3>
              <span className="ic">◈</span>Services
              <span className={`tag ${healthyServices === serviceEntries.length ? 'tag-g' : 'tag-w'}`}>
                {healthyServices} UP
              </span>
            </h3>
            {serviceEntries.length === 0 ? (
              <div className="row" style={{ color: 'var(--ink-3)' }}>No services reported yet.</div>
            ) : (
              serviceEntries.map(([name, svc]) => {
                const up = svc?.status === 'up' || svc?.status === 'running'
                return (
                  <div key={name} className="row">
                    <span
                      className="dot"
                      style={{
                        background: up ? 'var(--success)' : 'var(--danger)',
                        boxShadow: `0 0 6px ${up ? 'var(--success)' : 'var(--danger)'}`,
                      }}
                    />
                    <span className="name" style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{name}</span>
                    {svc?.latency_ms != null && (
                      <span className="latency">{svc.latency_ms}ms</span>
                    )}
                  </div>
                )
              })
            )}
          </div>

          {/* Missions + Approvals panel */}
          <div className="p">
            <h3>
              <span className="ic">▸</span>Missions
              <span className="tag tag-b">{activeMissions.length} ACTIVE</span>
            </h3>
            {missions.length === 0 ? (
              <div className="row" style={{ color: 'var(--ink-3)' }}>No active missions yet.</div>
            ) : (
              missions.slice(0, 3).map((mission) => {
                const isRunning = mission.status === 'active' || mission.status === 'running'
                const isDone = mission.status === 'completed'
                return (
                  <div key={mission.id} style={{ padding: '10px 0', borderBottom: '1px dashed var(--panel-br)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                      <span
                        className="dot"
                        style={{
                          background: isDone ? 'var(--success)' : isRunning ? 'var(--accent)' : 'var(--ink-3)',
                          boxShadow: isRunning ? '0 0 8px var(--accent)' : 'none',
                        }}
                      />
                      <span style={{ flex: 1, fontSize: 13, fontWeight: 500 }}>{mission.title}</span>
                      <span style={{
                        fontFamily: 'var(--mono)', fontSize: 10,
                        color: isDone ? 'var(--success)' : isRunning ? 'var(--accent)' : 'var(--ink-3)',
                      }}>
                        {(mission.status || 'idle').toUpperCase()}
                      </span>
                    </div>
                    <div className="bar">
                      <div className="f" style={{
                        width: `${isDone ? 100 : isRunning ? 65 : 0}%`,
                        background: isDone ? 'var(--success)' : 'var(--accent)',
                      }} />
                    </div>
                  </div>
                )
              })
            )}

            <div style={{ marginTop: 14 }}>
              <h3 style={{ marginBottom: 8 }}>
                <span className="ic">▢</span>Approvals
                <span className={`tag ${liveApprovals.length ? 'tag-w' : 'tag-g'}`}>
                  {liveApprovals.length} PENDING
                </span>
              </h3>
              {liveApprovals.length === 0 ? (
                <div className="row" style={{ color: 'var(--ink-3)' }}>No pending approvals.</div>
              ) : (
                liveApprovals.slice(0, 3).map((a, i) => (
                  <div key={a.id || i} className="row">
                    <span
                      className="dot"
                      style={{
                        background: a.risk === 'high' ? 'var(--danger)' : 'var(--warn)',
                        boxShadow: `0 0 6px ${a.risk === 'high' ? 'var(--danger)' : 'var(--warn)'}`,
                      }}
                    />
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 12, flex: 1 }}>{a.tool || 'action'}</span>
                    <span style={{
                      fontFamily: 'var(--mono)', fontSize: 10,
                      color: a.risk === 'high' ? 'var(--danger)' : 'var(--warn)',
                      padding: '1px 7px', borderRadius: 10,
                      background: a.risk === 'high' ? 'oklch(70% 0.2 25 / 0.12)' : 'oklch(80% 0.16 80 / 0.12)',
                      border: `1px solid ${a.risk === 'high' ? 'oklch(70% 0.2 25 / 0.25)' : 'oklch(80% 0.16 80 / 0.25)'}`,
                    }}>
                      {a.risk || 'medium'}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Runtimes */}
        <div className="p">
          <h3><span className="ic">◐</span>Runtimes</h3>
          <div className="grid3">
            {runtimeRows.length > 0 ? (
              runtimeRows.map((r) => (
                <RuntimeCard
                  key={r.name}
                  name={r.name}
                  icon={r.icon}
                  color={r.running ? 'var(--accent)' : 'var(--ink-3)'}
                  running={r.running}
                  model={r.model}
                />
              ))
            ) : (
              [
                { name: 'Nexus', icon: 'N', color: 'var(--accent)', running: false, model: 'no runtime reported' },
                { name: 'PicoClaw', icon: 'P', color: 'var(--warn)', running: false, model: 'edge · on-device' },
                { name: 'OpenClaw', icon: 'O', color: 'var(--violet)', running: false, model: 'gateway · cloud' },
              ].map((r) => <RuntimeCard key={r.name} {...r} />)
            )}
          </div>
        </div>
      </main>

      {/* ── Right rail — Nexus chat + live activity ── */}
      <aside className="rail">
        <div className="live">
          <span className="d" />
          {assistantName} · connected · watching trusted lanes
        </div>
        <div className="rail-head">
          <h3>{assistantName}</h3>
          <div className="sub">chat with your agent directly from the overview</div>
        </div>
        <div className="chat">
          <div className="msgs" ref={msgsRef}>
            {conversation.map((m) => (
              <div key={m.id} className={`msg ${m.role === 'assistant' ? 'a' : 'u'}`}>
                {m.content}
              </div>
            ))}
          </div>
          <div className="suggestions">
            {QUICK_SUGGESTIONS.map((s) => (
              <button key={s} className="sug" type="button" onClick={() => setDraft(s)}>
                {s}
              </button>
            ))}
          </div>
          <form className="chat-input" onSubmit={submitConversation}>
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Ask Nexus anything…"
            />
            <button type="submit" disabled={working || !draft.trim()}>
              {working ? '…' : '↵'}
            </button>
          </form>
        </div>

        {/* Live activity feed */}
        <div style={{ borderTop: '1px solid var(--panel-br)', maxHeight: 200, overflowY: 'auto' }}>
          <div style={{
            padding: '10px 16px',
            fontFamily: 'var(--mono)', fontSize: 9.5,
            color: 'var(--ink-4)', letterSpacing: '0.16em', textTransform: 'uppercase',
          }}>
            Live activity
          </div>
          {recentEvents.length === 0 ? (
            <div style={{ padding: '8px 16px', fontSize: 11, color: 'var(--ink-4)', fontFamily: 'var(--mono)' }}>
              Waiting for activity…
            </div>
          ) : (
            recentEvents.map((e, i) => {
              const color = eventDotColor(e)
              const label = (e.data as any)?.intent || (e.data as any)?.tool || e.type || 'event'
              return (
                <div key={i} style={{
                  padding: '6px 16px', borderBottom: '1px dashed var(--panel-br)',
                  display: 'flex', alignItems: 'center', gap: 8,
                }}>
                  <span style={{
                    width: 5, height: 5, borderRadius: '50%', flexShrink: 0,
                    background: color, boxShadow: `0 0 4px ${color}`,
                  }} />
                  <span style={{
                    flex: 1, fontSize: 11, color: 'var(--ink-2)',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }}>
                    {label}
                  </span>
                </div>
              )
            })
          )}
        </div>
      </aside>
    </div>
  )
}

function StatCard({
  label, value, unit, meta, metaColor, barWidth, barColor,
}: {
  label: string
  value: string
  unit?: string
  meta: string
  metaColor?: string
  barWidth: number
  barColor: string
}) {
  return (
    <div className="stat">
      <div className="s-k">{label}</div>
      <div className="s-v">
        {value}
        {unit && <span className="u">{unit}</span>}
      </div>
      <div className="s-meta" style={metaColor ? { color: metaColor } : undefined}>{meta}</div>
      <div className="bar">
        <div className="f" style={{ width: `${Math.max(4, Math.min(100, barWidth))}%`, background: barColor }} />
      </div>
    </div>
  )
}

function RuntimeCard({
  name, icon, color, running, model,
}: {
  name: string
  icon: string
  color: string
  running: boolean
  model: string
}) {
  return (
    <div style={{
      padding: 14, borderRadius: 10,
      border: `1px solid ${running ? color + '33' : 'var(--panel-br)'}`,
      background: running ? color + '0d' : 'transparent',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <div style={{
          width: 28, height: 28, borderRadius: 8,
          background: running ? color + '22' : 'var(--panel)',
          border: `1px solid ${running ? color + '44' : 'var(--panel-br)'}`,
          display: 'grid', placeItems: 'center',
          fontWeight: 700, fontSize: 13,
          color: running ? color : 'var(--ink-3)',
        }}>
          {icon}
        </div>
        <span style={{ fontWeight: 600, fontSize: 13 }}>{name}</span>
        <span
          className="dot"
          style={{
            marginLeft: 'auto',
            background: running ? 'var(--success)' : 'var(--ink-4)',
            boxShadow: running ? '0 0 6px var(--success)' : 'none',
          }}
        />
      </div>
      <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink-3)' }}>{model}</div>
    </div>
  )
}

function eventDotColor(event: EventRecord): string {
  if (event.type === 'approval_pending') return 'var(--warn)'
  const d = event.data || {}
  if ((d as any).decision === 'approved' || (d as any).decision === 'auto-allow' || (d as any).status === 'completed') {
    return 'var(--success)'
  }
  if ((d as any).decision === 'denied' || (d as any).status === 'failed') return 'var(--danger)'
  return 'var(--blue)'
}
