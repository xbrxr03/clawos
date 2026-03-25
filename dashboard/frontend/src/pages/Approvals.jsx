import { useState } from 'react'
import { Card, Row, Empty, SectionLabel, Button, ProgressBar, Time } from '../components/ui.jsx'
import { api } from '../lib/api.js'

export function Approvals({ approvals }) {
  const [deciding, setDeciding] = useState({})

  async function decide(id, action) {
    setDeciding(d => ({ ...d, [id]: action }))
    try { await (action === 'approve' ? api.approve(id) : api.deny(id)) }
    catch (e) { console.error(e) }
    finally { setDeciding(d => { const n = {...d}; delete n[id]; return n }) }
  }

  return (
    <div className="p-6 overflow-y-auto h-full fade-up">

      {/* Header pill */}
      {approvals.length > 0 && (
        <div
          className="flex items-center gap-2 px-4 py-2.5 rounded-[12px] mb-5 text-sm font-medium"
          style={{ background: '#ff9f0a18', color: '#ff9f0a' }}
        >
          <span>⚠️</span>
          <span>{approvals.length} action{approvals.length > 1 ? 's' : ''} waiting for your approval</span>
        </div>
      )}

      {approvals.length === 0 ? (
        <>
          <SectionLabel>Approvals</SectionLabel>
          <Card><Empty icon="🛡️" message="All clear — no pending approvals" /></Card>
        </>
      ) : (
        <>
          <SectionLabel>Pending</SectionLabel>
          <div className="space-y-3">
            {approvals.map(a => (
              <ApprovalCard
                key={a.id}
                approval={a}
                deciding={deciding[a.id]}
                onApprove={() => decide(a.id, 'approve')}
                onDeny={() => decide(a.id, 'deny')}
              />
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function ApprovalCard({ approval, deciding, onApprove, onDeny }) {
  const riskColor = approval.risk === 'high' ? '#ff453a' : approval.risk === 'low' ? '#30d158' : '#ff9f0a'

  return (
    <div className="ios-card overflow-hidden">
      {/* Risk stripe */}
      <div className="h-0.5 w-full" style={{ background: riskColor }} />

      <div className="p-4 space-y-3">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-base font-semibold">{approval.tool ?? 'action'}</span>
              <span
                className="text-xs font-semibold px-2 py-0.5 rounded-full"
                style={{ background: `${riskColor}20`, color: riskColor }}
              >
                {approval.risk ?? 'medium'} risk
              </span>
            </div>
            <div className="text-sm mt-0.5" style={{ color: 'rgba(255,255,255,0.4)' }}>
              {approval.agent ?? 'agent'} · {approval.task_id ?? '—'}
            </div>
          </div>
          <Time value={approval.created_at} />
        </div>

        {/* Action */}
        {approval.action && (
          <div
            className="rounded-[10px] p-3"
            style={{ background: 'rgba(0,0,0,0.4)' }}
          >
            <div className="text-xs mb-1" style={{ color: 'rgba(255,255,255,0.3)' }}>
              Requested action
            </div>
            <pre className="text-xs font-mono whitespace-pre-wrap break-all"
              style={{ color: 'rgba(255,255,255,0.8)' }}>
              {typeof approval.action === 'string' ? approval.action : JSON.stringify(approval.action, null, 2)}
            </pre>
          </div>
        )}

        {/* Reason */}
        {approval.reason && (
          <p className="text-sm italic" style={{ color: 'rgba(255,255,255,0.4)' }}>
            "{approval.reason}"
          </p>
        )}

        {/* Timeout */}
        {approval.timeout_at && <TimeoutBar timeoutAt={approval.timeout_at} />}

        {/* Buttons */}
        <div className="flex gap-2 pt-1">
          <button
            onClick={onApprove}
            disabled={!!deciding}
            className="flex-1 py-2.5 rounded-[10px] text-sm font-semibold transition-opacity disabled:opacity-40"
            style={{ background: '#30d15820', color: '#30d158' }}
          >
            {deciding === 'approve' ? 'Approving...' : '✓ Approve'}
          </button>
          <button
            onClick={onDeny}
            disabled={!!deciding}
            className="flex-1 py-2.5 rounded-[10px] text-sm font-semibold transition-opacity disabled:opacity-40"
            style={{ background: '#ff453a20', color: '#ff453a' }}
          >
            {deciding === 'deny' ? 'Denying...' : '✕ Deny'}
          </button>
        </div>
      </div>
    </div>
  )
}

function TimeoutBar({ timeoutAt }) {
  const total = 120
  const remaining = Math.max(0, (new Date(timeoutAt * 1000) - Date.now()) / 1000)
  const pct = (remaining / total) * 100
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs" style={{ color: 'rgba(255,255,255,0.3)' }}>
        <span>Auto-deny in</span>
        <span className="tabular">{Math.ceil(remaining)}s</span>
      </div>
      <ProgressBar value={pct} color="#ff9f0a" />
    </div>
  )
}
