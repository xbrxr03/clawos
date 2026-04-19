/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { useEffect, useRef } from 'react'
import { FitAddon } from '@xterm/addon-fit'
import { WebLinksAddon } from '@xterm/addon-web-links'
import { Terminal } from '@xterm/xterm'
import '@xterm/xterm/css/xterm.css'

export function JarvisTerminalModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const containerRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!open) return undefined

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }

    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [onClose, open])

  useEffect(() => {
    if (!open || !containerRef.current) return undefined

    const container = containerRef.current
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${protocol}://${location.host}/ws/jarvis`)
    ws.binaryType = 'arraybuffer'

    const term = new Terminal({
      fontFamily: 'var(--mono)',
      fontSize: 13,
      theme: {
        background: '#0a0a0a',
        foreground: '#e5e5e5',
        cursor: '#e5e5e5',
      },
      cursorBlink: true,
      convertEol: true,
    })
    const fitAddon = new FitAddon()
    const linksAddon = new WebLinksAddon((event, uri) => {
      event.preventDefault()
      window.open(uri, '_blank', 'noopener')
    })
    const resizeObserver = new ResizeObserver(() => {
      fitAddon.fit()
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }))
      }
    })
    const dataDisposable = term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) ws.send(data)
    })

    term.loadAddon(fitAddon)
    term.loadAddon(linksAddon)
    term.open(container)
    term.focus()

    const sendResize = () => {
      fitAddon.fit()
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }))
      }
    }

    const handleOpen = () => {
      sendResize()
      term.focus()
    }

    const handleMessage = (event: MessageEvent<ArrayBuffer | string>) => {
      if (event.data instanceof ArrayBuffer) {
        term.write(new Uint8Array(event.data))
        return
      }
      term.write(event.data)
    }

    const handleClose = () => {
      term.write('\r\n[session closed]\r\n')
    }

    const handleError = () => {
      term.write('\r\n[connection error]\r\n')
    }

    resizeObserver.observe(container)
    ws.addEventListener('open', handleOpen)
    ws.addEventListener('message', handleMessage)
    ws.addEventListener('close', handleClose)
    ws.addEventListener('error', handleError)
    requestAnimationFrame(sendResize)

    return () => {
      resizeObserver.disconnect()
      dataDisposable.dispose()
      ws.removeEventListener('open', handleOpen)
      ws.removeEventListener('message', handleMessage)
      ws.removeEventListener('close', handleClose)
      ws.removeEventListener('error', handleError)
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close()
      }
      term.dispose()
    }
  }, [onClose, open])

  if (!open) return null

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="JARVIS terminal"
      style={{
        ['--mono' as string]: 'var(--font-mono)',
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.85)',
        zIndex: 1000,
        display: 'grid',
        placeItems: 'center',
        padding: 16,
      }}
    >
      <div
        style={{
          width: 'min(900px, calc(100vw - 32px))',
          height: 'min(600px, calc(100vh - 32px))',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          borderRadius: 18,
          border: '1px solid rgba(255,255,255,0.12)',
          background: '#050505',
          boxShadow: 'var(--shadow-modal)',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
            padding: '14px 18px',
            borderBottom: '1px solid rgba(255,255,255,0.08)',
            background: 'linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02))',
          }}
        >
          <div style={{ display: 'grid', gap: 2 }}>
            <div style={{ fontSize: 14, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#f5f5f7' }}>
              {'JARVIS \u00b7 kimi-k2.5:cloud'}
            </div>
            <div className="mono" style={{ fontSize: 11, color: 'rgba(245,245,247,0.5)' }}>
              OpenClaw TUI inside the dashboard
            </div>
          </div>
          <button
            type="button"
            aria-label="Close JARVIS terminal"
            onClick={onClose}
            style={{
              width: 34,
              height: 34,
              borderRadius: 10,
              border: '1px solid rgba(255,255,255,0.12)',
              background: 'rgba(255,255,255,0.04)',
              color: '#f5f5f7',
              cursor: 'pointer',
              fontSize: 20,
              lineHeight: 1,
            }}
          >
            {'\u00d7'}
          </button>
        </div>
        <div
          ref={containerRef}
          style={{
            flex: 1,
            minHeight: 0,
            overflow: 'hidden',
            padding: 14,
          }}
        />
      </div>
    </div>
  )
}
