import { useEffect, useRef, useCallback, useState } from 'react'

const WS_URL = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`

export function useClawOS() {
  const ws = useRef(null)
  const reconnectTimer = useRef(null)
  const [connected, setConnected] = useState(false)
  const [snapshot, setSnapshot] = useState(null)
  const [events, setEvents] = useState([])          // live event stream
  const [approvals, setApprovals] = useState([])
  const [services, setServices] = useState({})
  const [tasks, setTasks] = useState({ active: [], queued: [], failed: [], completed: [] })
  const [models, setModels] = useState({ models: [], default: 'qwen2.5:7b' })
  const [pullProgress, setPullProgress] = useState({}) // model → progress

  const pushEvent = useCallback((evt) => {
    setEvents(prev => [evt, ...prev].slice(0, 200))
  }, [])

  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) return

    const sock = new WebSocket(WS_URL)
    ws.current = sock

    sock.onopen = () => {
      setConnected(true)
      // keep-alive ping every 20s
      const ping = setInterval(() => {
        if (sock.readyState === WebSocket.OPEN) sock.send('ping')
      }, 20000)
      sock._ping = ping
    }

    sock.onclose = () => {
      setConnected(false)
      clearInterval(sock._ping)
      reconnectTimer.current = setTimeout(connect, 3000)
    }

    sock.onerror = () => sock.close()

    sock.onmessage = (e) => {
      let msg
      try { msg = JSON.parse(e.data) } catch { return }

      pushEvent(msg)

      switch (msg.type) {
        case 'snapshot':
          setSnapshot(msg.data)
          setApprovals(msg.data.approvals ?? [])
          setServices(msg.data.services ?? {})
          setTasks(msg.data.tasks ?? { active: [], queued: [], failed: [], completed: [] })
          setModels(msg.data.models ?? { models: [], default: 'qwen2.5:7b' })
          break

        case 'service_health':
          setServices(msg.data)
          break

        case 'approval_pending':
          setApprovals(prev => [msg.data, ...prev])
          break

        case 'approval_resolved':
          setApprovals(prev => prev.filter(a => a.id !== msg.data.approval_id))
          break

        case 'task_update':
          setTasks(prev => {
            const next = { ...prev }
            const t = msg.data
            // Remove from all buckets, add to correct one
            for (const k of Object.keys(next)) {
              next[k] = next[k].filter(x => x.id !== t.id)
            }
            const bucket = t.status in next ? t.status : 'active'
            next[bucket] = [t, ...next[bucket]]
            return next
          })
          break

        case 'model_pull_progress':
          setPullProgress(prev => ({
            ...prev,
            [msg.model]: msg.data,
          }))
          break

        case 'model_pull_error':
          setPullProgress(prev => {
            const next = { ...prev }
            delete next[msg.model]
            return next
          })
          break
      }
    }
  }, [pushEvent])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      ws.current?.close()
    }
  }, [connect])

  return { connected, snapshot, events, approvals, services, tasks, models, pullProgress }
}
