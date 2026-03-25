import { useEffect, useRef, useCallback, useState } from 'react'

export function useClawOS() {
  const ws        = useRef(null)
  const retryRef  = useRef(null)
  const [connected,   setConnected]   = useState(false)
  const [events,      setEvents]      = useState([])
  const [approvals,   setApprovals]   = useState([])
  const [services,    setServices]    = useState({})
  const [tasks,       setTasks]       = useState({ active:[], queued:[], failed:[], completed:[] })
  const [models,      setModels]      = useState({ models:[], default:'qwen2.5:7b' })
  const [pullProgress,setPullProgress]= useState({})

  const pushEvent = useCallback(e => setEvents(p => [e, ...p].slice(0, 300)), [])

  const connect = useCallback(() => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const sock  = new WebSocket(`${proto}://${location.host}/ws`)
    ws.current  = sock

    sock.onopen = () => {
      setConnected(true)
      const id = setInterval(() => sock.readyState === 1 && sock.send('ping'), 20000)
      sock._id = id
    }

    sock.onclose = () => {
      setConnected(false)
      clearInterval(sock._id)
      retryRef.current = setTimeout(connect, 3000)
    }

    sock.onerror = () => sock.close()

    sock.onmessage = ({ data }) => {
      let msg; try { msg = JSON.parse(data) } catch { return }
      pushEvent(msg)

      switch (msg.type) {
        case 'snapshot':
          setApprovals(msg.data.approvals ?? [])
          setServices(msg.data.services   ?? {})
          setTasks(msg.data.tasks         ?? { active:[], queued:[], failed:[], completed:[] })
          setModels(msg.data.models       ?? { models:[], default:'qwen2.5:7b' })
          break
        case 'service_health':
          setServices(msg.data)
          break
        case 'approval_pending':
          setApprovals(p => [msg.data, ...p])
          break
        case 'approval_resolved':
          setApprovals(p => p.filter(a => a.id !== msg.data.approval_id))
          break
        case 'task_update':
          setTasks(p => {
            const n = { ...p }
            const t = msg.data
            for (const k of Object.keys(n)) n[k] = n[k].filter(x => x.id !== t.id)
            const b = n[t.status] ? t.status : 'active'
            n[b] = [t, ...n[b]]
            return n
          })
          break
        case 'model_pull_progress':
          setPullProgress(p => ({ ...p, [msg.model]: msg.data }))
          break
      }
    }
  }, [pushEvent])

  useEffect(() => {
    connect()
    return () => { clearTimeout(retryRef.current); ws.current?.close() }
  }, [connect])

  return { connected, events, approvals, services, tasks, models, pullProgress }
}
