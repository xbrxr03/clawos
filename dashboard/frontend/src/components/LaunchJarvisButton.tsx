/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { useState } from 'react'
import '../pages/setup/setup.css'
import { JarvisTerminalModal } from './JarvisTerminalModal'

export function LaunchJarvisButton() {
  const [open, setOpen] = useState(false)

  return (
    <>
      <div
        className="clawos-setup-root"
        style={{
          position: 'relative',
          inset: 'auto',
          overflow: 'visible',
          background: 'transparent',
          display: 'grid',
          gap: 8,
          padding: 0,
        }}
      >
        <div style={{ display: 'grid', gap: 8, justifyItems: 'start' }}>
          <button
            type="button"
            className="wiz-btn wiz-btn-primary"
            onClick={() => setOpen(true)}
            style={{
              padding: '12px 18px',
              fontSize: 14,
              borderRadius: 10,
            }}
          >
            {'\u26a1 Launch JARVIS'}
          </button>
          <div className="mono" style={{ fontSize: 11, color: 'var(--text-3)' }}>
            {'OpenClaw TUI \u00b7 kimi-k2.5 (Ollama Cloud)'}
          </div>
        </div>
      </div>
      <JarvisTerminalModal open={open} onClose={() => setOpen(false)} />
    </>
  )
}
