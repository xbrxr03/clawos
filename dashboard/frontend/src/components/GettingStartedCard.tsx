/* SPDX-License-Identifier: AGPL-3.0-or-later */
/* GettingStartedCard — pinned onboarding follow-up on the Overview page.
 *
 * Appears only when SummaryScreen ("Open dashboard →") flipped the
 * localStorage flag `clawos:getting-started:pending = 1` on wizard exit.
 * Once the user dismisses (×) or marks it done, we clear the flag and the
 * card never appears again unless they re-run setup.
 */
import { useEffect, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { Badge, Card, PanelHeader } from './ui.jsx'

const LS_KEY = 'clawos:getting-started:pending'
const LS_DONE_ITEMS = 'clawos:getting-started:done'

interface StartItem {
  id: string
  icon: string
  title: string
  body: string
  action: { label: string; onClick: (nav: (path: string) => void) => void }
}

const ITEMS: StartItem[] = [
  {
    id: 'voice',
    icon: '🎙️',
    title: 'Say hello to Jarvis',
    body: 'Try a voice command — everything runs locally on this machine. No audio leaves your device.',
    action: {
      label: 'Open voice',
      onClick: (nav) => nav('/jarvis'),
    },
  },
  {
    id: 'workflows',
    icon: '⚡',
    title: 'Browse 29 automations',
    body: 'Morning briefings, email triage, research synthesis, code review — all running on your hardware.',
    action: {
      label: 'Browse workflows',
      onClick: (nav) => nav('/workflows'),
    },
  },
  {
    id: 'memory',
    icon: '🧠',
    title: 'See your memory brain',
    body: '14 memory layers are wiring themselves up. Watch the knowledge graph grow as you use Jarvis.',
    action: {
      label: 'Open brain',
      onClick: (nav) => nav('/brain'),
    },
  },
  {
    id: 'phone',
    icon: '📱',
    title: 'Pair your phone (optional)',
    body: 'Connect your calendar, email, or messaging apps so Jarvis can handle tasks on your behalf.',
    action: {
      label: 'Connect integrations',
      onClick: (nav) => nav('/settings'),
    },
  },
]

function loadDoneSet(): Set<string> {
  if (typeof window === 'undefined') return new Set()
  try {
    const raw = window.localStorage.getItem(LS_DONE_ITEMS)
    if (!raw) return new Set()
    const arr = JSON.parse(raw)
    return new Set(Array.isArray(arr) ? arr : [])
  } catch {
    return new Set()
  }
}

function saveDoneSet(s: Set<string>): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(LS_DONE_ITEMS, JSON.stringify([...s]))
  } catch {
    /* ignore */
  }
}

export function GettingStartedCard(): ReactNode {
  const navigate = useNavigate()
  const [visible, setVisible] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false
    try {
      return window.localStorage.getItem(LS_KEY) === '1'
    } catch {
      return false
    }
  })
  const [done, setDone] = useState<Set<string>>(() => loadDoneSet())

  const dismiss = () => {
    try {
      window.localStorage.removeItem(LS_KEY)
    } catch {
      /* ignore */
    }
    setVisible(false)
  }

  // Persist done-set as user checks items off.
  useEffect(() => {
    saveDoneSet(done)
  }, [done])

  // If every item is done, auto-dismiss after a short victory beat.
  useEffect(() => {
    if (!visible) return
    if (done.size >= ITEMS.length) {
      const timer = window.setTimeout(() => {
        try {
          window.localStorage.removeItem(LS_KEY)
        } catch {
          /* ignore */
        }
        setVisible(false)
      }, 1800)
      return () => window.clearTimeout(timer)
    }
    return undefined
  }, [done.size, visible])

  if (!visible) return null

  const toggleDone = (id: string) => {
    setDone((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const completePct = Math.round((done.size / ITEMS.length) * 100)
  const allDone = done.size >= ITEMS.length

  return (
    <Card
      style={{
        padding: 20,
        margin: '0 20px 16px',
        display: 'grid',
        gap: 16,
        borderLeft: '3px solid var(--accent, #ffc400)',
        background:
          'linear-gradient(180deg, color-mix(in oklch, var(--accent, #ffc400) 6%, transparent), var(--surface))',
      }}
    >
      <PanelHeader
        eyebrow="Getting Started"
        title={allDone ? 'You are all set.' : 'Welcome home.'}
        description={
          allDone
            ? 'Every kickoff step is done. This card will tuck itself away in a moment.'
            : 'A few quick things to try now that ClawOS is online. Tick them off as you go — or dismiss this card and explore at your own pace.'
        }
        aside={
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <Badge color={allDone ? 'green' : 'blue'}>
              {done.size}/{ITEMS.length} · {completePct}%
            </Badge>
            <button
              type="button"
              aria-label="Dismiss getting started card"
              onClick={dismiss}
              style={{
                width: 26,
                height: 26,
                borderRadius: 8,
                border: '1px solid var(--border)',
                background: 'transparent',
                color: 'var(--text-2)',
                cursor: 'pointer',
                fontSize: 14,
                lineHeight: 1,
              }}
            >
              ×
            </button>
          </div>
        }
      />
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: 10,
        }}
      >
        {ITEMS.map((item) => {
          const isDone = done.has(item.id)
          return (
            <div
              key={item.id}
              style={{
                padding: 14,
                borderRadius: 10,
                border: '1px solid var(--border)',
                background: isDone ? 'color-mix(in oklch, var(--success, #2ecc71) 8%, var(--surface))' : 'var(--surface)',
                display: 'grid',
                gap: 6,
                position: 'relative',
                opacity: isDone ? 0.75 : 1,
                transition: 'opacity 0.2s, background 0.2s',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 18 }} aria-hidden>
                  {item.icon}
                </span>
                <span
                  style={{
                    fontWeight: 600,
                    fontSize: 13,
                    color: 'var(--text)',
                    textDecoration: isDone ? 'line-through' : 'none',
                  }}
                >
                  {item.title}
                </span>
                <button
                  type="button"
                  aria-label={isDone ? `Mark ${item.title} as not done` : `Mark ${item.title} as done`}
                  onClick={() => toggleDone(item.id)}
                  style={{
                    marginLeft: 'auto',
                    width: 20,
                    height: 20,
                    borderRadius: 5,
                    border: `1.5px solid ${isDone ? 'var(--success, #2ecc71)' : 'var(--border)'}`,
                    background: isDone ? 'var(--success, #2ecc71)' : 'transparent',
                    color: '#000',
                    cursor: 'pointer',
                    fontSize: 11,
                    lineHeight: 1,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  {isDone ? '✓' : ''}
                </button>
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-3)', lineHeight: 1.5 }}>{item.body}</div>
              <button
                type="button"
                onClick={() => {
                  item.action.onClick((p) => navigate(p))
                  // Auto-mark this item as done when the user acts on it.
                  setDone((current) => {
                    if (current.has(item.id)) return current
                    const next = new Set(current)
                    next.add(item.id)
                    return next
                  })
                }}
                style={{
                  marginTop: 4,
                  padding: '6px 10px',
                  borderRadius: 8,
                  border: '1px solid var(--border)',
                  background: 'transparent',
                  color: 'var(--text)',
                  fontSize: 12,
                  cursor: 'pointer',
                  justifySelf: 'flex-start',
                }}
              >
                {item.action.label} →
              </button>
            </div>
          )
        })}
      </div>
    </Card>
  )
}
