import { Card, SectionHeader, Empty, Badge, Timestamp, Button } from '../components/ui.jsx'
import { ShieldAlert, Check, X, Terminal } from 'lucide-react'
import { api } from '../lib/api.js'
import { useState } from 'react'

export function Approvals({ approvals }) {
  const [deciding, setDeciding] = useState({}) // id → 'approving' | 'denying'

  async function decide(id, action) {
    setDeciding(d => ({ ...d, [id]: action === 'approve' ? 'approving' : 'denying' }))
    try {
      await (action === 'approve' ? api.approve(id) : api.deny(id))
    } catch (e) {
      console.error(e)
    } finally {
      setDeciding(d => { const n = { ...d }; delete n[id]; return n })
    }
  }

  return (
    <div className="p-6 space-y-4 fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-claw-text">Approvals</h1>
          <p className="text-sm text-claw-dim mt-0.5">Sensitive actions waiting for human approval</p>
        </div>
        {approvals.length > 0 && (
          <div className="flex items-center gap-2 text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 px-3 py-1.5 rounded-full">
            <ShieldAlert size={12} />
            {approvals.length} pending
          </div>
        )}
      </div>

      {approvals.length === 0 ? (
        <Card>
          <Empty icon={ShieldAlert} message="No pending approvals — all quiet" />
        </Card>
      ) : (
        <div className="space-y-3">
          {approvals.map(approval => (
            <ApprovalCard
              key={approval.id}
              approval={approval}
              deciding={deciding[approval.id]}
              onApprove={() => decide(approval.id, 'approve')}
              onDeny={() => decide(approval.id, 'deny')}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function ApprovalCard({ approval, deciding, onApprove, onDeny }) {
  const riskColor = {
    high:   'border-red-500/30 bg-red-500/5',
    medium: 'border-amber-500/30 bg-amber-500/5',
    low:    'border-claw-border bg-claw-surface',
  }[approval.risk ?? 'medium']

  return (
    <div className={`rounded-lg border p-4 space-y-3 ${riskColor}`}>
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-claw-text">{approval.tool ?? 'unknown.tool'}</span>
            <Badge variant={approval.risk === 'high' ? 'danger' : approval.risk === 'low' ? 'default' : 'warn'}>
              {approval.risk ?? 'medium'} risk
            </Badge>
            {approval.agent && <Badge variant="default">{approval.agent}</Badge>}
          </div>
          <div className="text-xs text-claw-dim font-mono mt-1">
            task: {approval.task_id ?? '—'} · id: {approval.id}
          </div>
        </div>
        <Timestamp value={approval.created_at} />
      </div>

      {/* Action being requested */}
      {approval.action && (
        <div className="bg-claw-bg rounded p-3 border border-claw-border">
          <div className="text-xs text-claw-dim mb-1.5">Requested action</div>
          <div className="flex items-start gap-2">
            <Terminal size={12} className="text-claw-dim mt-0.5 flex-shrink-0" />
            <pre className="font-mono text-xs text-claw-text whitespace-pre-wrap break-all">
              {typeof approval.action === 'string'
                ? approval.action
                : JSON.stringify(approval.action, null, 2)}
            </pre>
          </div>
        </div>
      )}

      {/* Reason */}
      {approval.reason && (
        <p className="text-xs text-claw-dim italic">"{approval.reason}"</p>
      )}

      {/* Timeout indicator */}
      {approval.timeout_at && (
        <TimeoutBar timeoutAt={approval.timeout_at} />
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 pt-1">
        <Button
          variant="accent"
          onClick={onApprove}
          disabled={!!deciding}
        >
          <Check size={12} />
          {deciding === 'approving' ? 'Approving...' : 'Approve'}
        </Button>
        <Button
          variant="danger"
          onClick={onDeny}
          disabled={!!deciding}
        >
          <X size={12} />
          {deciding === 'denying' ? 'Denying...' : 'Deny'}
        </Button>
      </div>
    </div>
  )
}

function TimeoutBar({ timeoutAt }) {
  const total = 120 // 120s timeout as per policyd
  const remaining = Math.max(0, (new Date(timeoutAt * 1000) - Date.now()) / 1000)
  const pct = (remaining / total) * 100

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-claw-dim">
        <span>Auto-deny in</span>
        <span className="font-mono">{Math.ceil(remaining)}s</span>
      </div>
      <div className="h-1 bg-claw-muted rounded-full overflow-hidden">
        <div
          className="h-full bg-amber-500 rounded-full transition-all duration-1000"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}
