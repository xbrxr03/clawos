/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { Footer, WizToggle } from '../atoms'
import type { ScreenProps } from '../types'

type Policy = {
  id: string
  t: string
  s: string
  risk: 'low' | 'med' | 'high'
  gate?: boolean
  locked?: boolean
  /** map policy id → SetupState.autonomy_policy field */
  field: string
}

// These fields write into state.autonomy_policy.* when toggled.
const POLICIES: Policy[] = [
  {
    id: 'files_read',
    field: 'files_read',
    t: 'Read files',
    s: 'Let agents read anything in your workspace.',
    risk: 'low',
  },
  {
    id: 'files_write',
    field: 'files_write',
    t: 'Write & modify files',
    s: 'Require approval per file mutation.',
    risk: 'med',
    gate: true,
  },
  {
    id: 'shell',
    field: 'shell',
    t: 'Run shell commands',
    s: 'Non-destructive commands auto, sudo needs approval.',
    risk: 'med',
    gate: true,
  },
  {
    id: 'network',
    field: 'network',
    t: 'Outbound network',
    s: 'Let tools fetch URLs and call external APIs.',
    risk: 'low',
  },
  {
    id: 'notifs',
    field: 'notifs',
    t: 'Send notifications',
    s: 'Desktop toasts and proactive briefings.',
    risk: 'low',
  },
  {
    id: 'delete',
    field: 'delete',
    t: 'Delete / destructive ops',
    s: 'Always requires explicit approval, always logged.',
    risk: 'high',
    gate: true,
    locked: true,
  },
]

const POLICY_DEFAULTS: Record<string, boolean> = {
  files_read: true,
  files_write: true,
  shell: true,
  network: true,
  notifs: true,
  delete: true,
}

export function PolicyScreen(props: ScreenProps) {
  const { state, onBack, onNext, stepIndex, totalSteps, updateAutonomy, updateOptions, busy } =
    props

  // Merge backend autonomy_policy with local defaults
  const policy: Record<string, boolean> = {
    ...POLICY_DEFAULTS,
    ...((state.autonomy_policy as unknown as Record<string, boolean>) || {}),
  }

  const toggle = async (p: Policy) => {
    if (p.locked) return
    const next = { ...policy, [p.field]: !policy[p.field] }
    await updateAutonomy(next)
  }

  const toggleWhatsApp = async () => {
    await updateOptions({ whatsapp_enabled: !state.whatsapp_enabled })
  }

  const toggleLaunchOnLogin = async () => {
    await updateOptions({ launch_on_login: !state.launch_on_login })
  }

  return (
    <>
      <div className="stage-inner">
        <div className="eyebrow">08 · Policy</div>
        <h1 className="wiz-title">Permissions, your way.</h1>
        <p className="wiz-subtitle">
          Every tool call is gated, audited and logged with a Merkle-chained receipt. Flip
          capabilities on or off — the gated ones still ask for approval each time.
        </p>

        <div className="panel" style={{ padding: 4, marginTop: 26 }}>
          {POLICIES.map((p, i) => (
            <div
              key={p.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 14,
                padding: '14px 18px',
                borderTop: i === 0 ? 'none' : '1px solid var(--panel-br)',
              }}
            >
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background:
                    p.risk === 'high'
                      ? 'var(--danger)'
                      : p.risk === 'med'
                        ? 'var(--warn)'
                        : 'var(--success)',
                  boxShadow: '0 0 10px currentColor',
                  color:
                    p.risk === 'high'
                      ? 'var(--danger)'
                      : p.risk === 'med'
                        ? 'var(--warn)'
                        : 'var(--success)',
                  flexShrink: 0,
                }}
              />
              <div style={{ flex: 1 }}>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    fontSize: 13.5,
                    fontWeight: 600,
                  }}
                >
                  {p.t}
                  {p.gate && (
                    <span
                      className="c-tag"
                      style={{
                        background: 'rgba(255,255,255,0.04)',
                        color: 'var(--ink-2)',
                        borderColor: 'var(--panel-br)',
                      }}
                    >
                      APPROVAL GATE
                    </span>
                  )}
                  {p.locked && (
                    <span
                      className="c-tag"
                      style={{
                        background: 'oklch(70% 0.2 25 / 0.15)',
                        color: 'oklch(80% 0.2 25)',
                        borderColor: 'oklch(70% 0.2 25 / 0.3)',
                      }}
                    >
                      LOCKED
                    </span>
                  )}
                </div>
                <div style={{ fontSize: 12, color: 'var(--ink-3)', marginTop: 2 }}>{p.s}</div>
              </div>
              <WizToggle
                on={!!policy[p.field]}
                onChange={() => toggle(p)}
                disabled={p.locked || busy === 'autonomy'}
                ariaLabel={p.t}
              />
            </div>
          ))}
        </div>

        {/* Collapsed whatsapp + launch-on-login toggles — keeps parity with old flow */}
        <div className="panel" style={{ padding: 4, marginTop: 12 }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 14,
              padding: '14px 18px',
              borderTop: 'none',
            }}
          >
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--success)', flexShrink: 0 }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13.5, fontWeight: 600 }}>Launch on login</div>
              <div style={{ fontSize: 12, color: 'var(--ink-3)', marginTop: 2 }}>
                Start ClawOS automatically when you sign in.
              </div>
            </div>
            <WizToggle
              on={state.launch_on_login !== false}
              onChange={toggleLaunchOnLogin}
              disabled={busy === 'options'}
              ariaLabel="Launch on login"
            />
          </div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 14,
              padding: '14px 18px',
              borderTop: '1px solid var(--panel-br)',
            }}
          >
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--warn)', flexShrink: 0 }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13.5, fontWeight: 600 }}>
                WhatsApp bridge{' '}
                <span
                  className="c-tag"
                  style={{
                    background: 'rgba(255,255,255,0.04)',
                    color: 'var(--ink-2)',
                    borderColor: 'var(--panel-br)',
                  }}
                >
                  PAIR LATER
                </span>
              </div>
              <div style={{ fontSize: 12, color: 'var(--ink-3)', marginTop: 2 }}>
                Prepare the phone bridge. QR pairing happens from the dashboard after launch.
              </div>
            </div>
            <WizToggle
              on={!!state.whatsapp_enabled}
              onChange={toggleWhatsApp}
              disabled={busy === 'options'}
              ariaLabel="WhatsApp bridge"
            />
          </div>
        </div>

        <div className="note" style={{ marginTop: 18 }}>
          <span>ℹ</span>
          Every approval and denial is written to{' '}
          <span
            style={{
              fontFamily: 'var(--mono)',
              color: 'var(--ink-1)',
              margin: '0 4px',
            }}
          >
            ~/.clawos/audit.log
          </span>{' '}
          with a Merkle hash. You can review, revoke or roll back any time.
        </div>
      </div>
      <Footer onBack={onBack} onNext={onNext} step={stepIndex + 1} total={totalSteps} />
    </>
  )
}
