/* SPDX-License-Identifier: AGPL-3.0-or-later */
/**
 * ApprovalOverlay — floating, always-on-top window for sensitive-tool approvals.
 *
 * Rendered in a separate Tauri window (label: "approval-overlay"), borderless,
 * always-on-top. Polls /api/approvals every 1.5s; when a pending request shows
 * up, prompts the user with the task and approve/deny buttons.
 *
 * On decision, POSTs /api/approve/{request_id} with `{approve: bool}` and
 * the dashd backend resolves the policyd asyncio.Event so the agent loop
 * un-blocks.
 */
import { useCallback, useEffect, useRef, useState } from 'react'

type Approval = {
  request_id: string
  tool: string
  target: string
  task_id?: string
  workspace?: string
  content?: string
}

const POLL_MS = 1500

async function fetchPending(): Promise<Approval[]> {
  try {
    const r = await fetch('/api/approvals')
    if (!r.ok) return []
    const data = await r.json()
    return Array.isArray(data) ? data : data.approvals || []
  } catch {
    return []
  }
}

async function decide(requestId: string, approve: boolean): Promise<boolean> {
  try {
    const r = await fetch(`/api/approve/${encodeURIComponent(requestId)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approve }),
    })
    return r.ok
  } catch {
    return false
  }
}

async function hideWindow() {
  try {
    // Tauri 2 invokes through the global __TAURI__ object
    const t = (window as unknown as { __TAURI__?: { core?: { invoke: Function } } })
      .__TAURI__
    if (t?.core?.invoke) await t.core.invoke('hide_approval_overlay')
  } catch {
    /* not running in Tauri — ignore */
  }
}

export function ApprovalOverlay() {
  const [current, setCurrent] = useState<Approval | null>(null)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState<string>('')
  const seenRef = useRef<Set<string>>(new Set())

  const tick = useCallback(async () => {
    const pending = await fetchPending()
    if (pending.length === 0) {
      // No pending — close window after a short grace period
      if (current) {
        setCurrent(null)
        setStatus('')
        await hideWindow()
      }
      return
    }
    // Pick the oldest unseen approval
    const next = pending.find((p) => !seenRef.current.has(p.request_id)) || pending[0]
    if (!current || current.request_id !== next.request_id) {
      seenRef.current.add(next.request_id)
      setCurrent(next)
      setStatus('')
    }
  }, [current])

  useEffect(() => {
    let stopped = false
    const loop = async () => {
      while (!stopped) {
        await tick()
        await new Promise((r) => setTimeout(r, POLL_MS))
      }
    }
    loop()
    return () => {
      stopped = true
    }
  }, [tick])

  // Keyboard shortcuts: Y/N for approve/deny
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (busy || !current) return
      if (e.key === 'y' || e.key === 'Y' || e.key === 'Enter') void onDecide(true)
      if (e.key === 'n' || e.key === 'N' || e.key === 'Escape') void onDecide(false)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current, busy])

  const onDecide = useCallback(
    async (approve: boolean) => {
      if (!current || busy) return
      setBusy(true)
      setStatus(approve ? 'Approving…' : 'Denying…')
      const ok = await decide(current.request_id, approve)
      setBusy(false)
      setStatus(ok ? (approve ? 'Approved.' : 'Denied.') : 'Failed to send decision.')
      // Brief pause so the user sees the result, then refresh
      await new Promise((r) => setTimeout(r, 600))
      setCurrent(null)
      setStatus('')
      await tick()
    },
    [current, busy, tick],
  )

  if (!current) {
    return (
      <div style={overlayStyle.container}>
        <div style={overlayStyle.idle}>Watching for approval requests…</div>
      </div>
    )
  }

  return (
    <div style={overlayStyle.container}>
      <div style={overlayStyle.eyebrow}>NEXUS · APPROVAL REQUIRED</div>
      <div style={overlayStyle.tool}>{current.tool}</div>
      <div style={overlayStyle.target}>{current.target}</div>
      {current.content ? (
        <div style={overlayStyle.snippet}>
          {current.content.length > 180
            ? `${current.content.slice(0, 180)}…`
            : current.content}
        </div>
      ) : null}
      <div style={overlayStyle.buttons}>
        <button
          type="button"
          onClick={() => void onDecide(false)}
          disabled={busy}
          style={overlayStyle.deny}
        >
          Deny <span style={overlayStyle.kbd}>N</span>
        </button>
        <button
          type="button"
          onClick={() => void onDecide(true)}
          disabled={busy}
          style={overlayStyle.approve}
        >
          Approve <span style={overlayStyle.kbd}>Y</span>
        </button>
      </div>
      {status ? <div style={overlayStyle.status}>{status}</div> : null}
    </div>
  )
}

// Inline styles so the overlay works even without dashboard CSS loading
// (Tauri loads the same SPA bundle so CSS is normally available, but this
// keeps the overlay self-contained if anything fails).
const overlayStyle: Record<string, React.CSSProperties> = {
  container: {
    width: '100vw',
    height: '100vh',
    background: 'rgba(15, 18, 24, 0.98)',
    color: '#eef0f5',
    fontFamily:
      'system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
    padding: '18px 22px',
    boxSizing: 'border-box',
    display: 'flex',
    flexDirection: 'column',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: 10,
    boxShadow: '0 10px 40px rgba(0,0,0,0.5)',
  },
  eyebrow: {
    fontSize: 10,
    letterSpacing: '0.18em',
    color: '#8b94a7',
    marginBottom: 10,
  },
  tool: {
    fontSize: 18,
    fontWeight: 600,
    marginBottom: 4,
  },
  target: {
    fontSize: 13,
    color: '#aab2c2',
    fontFamily: 'ui-monospace, "SF Mono", Menlo, monospace',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    marginBottom: 8,
  },
  snippet: {
    fontSize: 12,
    color: '#7a8395',
    fontFamily: 'ui-monospace, "SF Mono", Menlo, monospace',
    background: 'rgba(255,255,255,0.04)',
    padding: '8px 10px',
    borderRadius: 6,
    marginBottom: 12,
    maxHeight: 80,
    overflow: 'hidden',
  },
  buttons: {
    marginTop: 'auto',
    display: 'flex',
    gap: 10,
    justifyContent: 'space-between',
  },
  deny: {
    flex: 1,
    background: 'rgba(220, 70, 70, 0.18)',
    color: '#ff8c8c',
    border: '1px solid rgba(220,70,70,0.4)',
    borderRadius: 8,
    padding: '10px 14px',
    fontSize: 14,
    fontWeight: 600,
    cursor: 'pointer',
  },
  approve: {
    flex: 1,
    background: 'rgba(80, 220, 130, 0.18)',
    color: '#9fffb6',
    border: '1px solid rgba(80,220,130,0.4)',
    borderRadius: 8,
    padding: '10px 14px',
    fontSize: 14,
    fontWeight: 600,
    cursor: 'pointer',
  },
  kbd: {
    marginLeft: 8,
    fontSize: 11,
    fontFamily: 'ui-monospace, "SF Mono", Menlo, monospace',
    opacity: 0.6,
  },
  status: {
    fontSize: 11,
    color: '#6a7384',
    marginTop: 8,
    textAlign: 'right',
  },
  idle: {
    fontSize: 12,
    color: '#6a7384',
    margin: 'auto',
  },
}
