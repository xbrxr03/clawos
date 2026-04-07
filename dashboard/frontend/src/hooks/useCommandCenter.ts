/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

type ServiceState = Record<string, { status?: string; latency_ms?: number }>
type TaskRecord = Record<string, unknown> & { status?: string }
type TasksState = { active: TaskRecord[]; queued: TaskRecord[]; failed: TaskRecord[]; completed: TaskRecord[] }

const EMPTY_TASKS: TasksState = { active: [], queued: [], failed: [], completed: [] }

export function useCommandCenter() {
  const ws = useRef<WebSocket | null>(null)
  const retryRef = useRef<number | null>(null)
  const [connected, setConnected] = useState(false)
  const [events, setEvents] = useState<any[]>([])
  const [approvals, setApprovals] = useState<any[]>([])
  const [services, setServices] = useState<ServiceState>({})
  const [tasks, setTasks] = useState<TasksState>(EMPTY_TASKS)
  const [models, setModels] = useState<any>({ models: [], default: 'qwen2.5:7b' })
  const [pullProgress, setPullProgress] = useState<Record<string, any>>({})
  const [runtimes, setRuntimes] = useState<Record<string, any>>({})
  const [voiceSession, setVoiceSession] = useState<Record<string, any>>({ mode: 'off', state: 'idle' })

  const pushEvent = useCallback((event: any) => {
    setEvents((prev) => [event, ...prev].slice(0, 200))
  }, [])

  const normalizeTasks = useCallback((data: any): TasksState => {
    if (Array.isArray(data)) {
      const grouped: TasksState = { active: [], queued: [], failed: [], completed: [] }
      data.forEach((task) => {
        const status = String(task?.status || 'active')
        if (status in grouped) {
          grouped[status as keyof TasksState].push(task)
        }
      })
      return grouped
    }

    return {
      active: data?.active ?? [],
      queued: data?.queued ?? [],
      failed: data?.failed ?? [],
      completed: data?.completed ?? [],
    }
  }, [])

  const connect = useCallback(() => {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const socket = new WebSocket(`${proto}://${window.location.host}/ws`)
    ws.current = socket

    socket.onopen = () => {
      setConnected(true)
      socket.send('ping')
    }

    socket.onclose = () => {
      setConnected(false)
      if (retryRef.current) {
        window.clearTimeout(retryRef.current)
      }
      retryRef.current = window.setTimeout(connect, 3000)
    }

    socket.onerror = () => socket.close()

    socket.onmessage = ({ data }) => {
      let message
      try {
        message = JSON.parse(data)
      } catch {
        return
      }

      pushEvent(message)
      switch (message.type) {
        case 'snapshot':
          setApprovals(message.data.approvals ?? [])
          setServices(message.data.services ?? {})
          setTasks(normalizeTasks(message.data.tasks))
          setModels(message.data.models ?? { models: [], default: 'qwen2.5:7b' })
          setVoiceSession(message.data.voice ?? { mode: 'off', state: 'idle' })
          break
        case 'service_health':
          setServices(message.data ?? {})
          break
        case 'approval_pending':
          setApprovals((prev) => [message.data, ...prev])
          break
        case 'approval_resolved':
          setApprovals((prev) => prev.filter((item) => item.id !== message.data.approval_id))
          break
        case 'task_update':
          setTasks((prev) => {
            const next = { ...prev }
            const task = message.data
            for (const key of Object.keys(next) as Array<keyof TasksState>) {
              next[key] = next[key].filter((entry: any) => entry.id !== task.id)
            }
            const bucket = (task.status in next ? task.status : 'active') as keyof TasksState
            next[bucket] = [task, ...next[bucket]]
            return next
          })
          break
        case 'model_pull_progress':
          setPullProgress((prev) => ({ ...prev, [message.model]: message.data }))
          break
        case 'voice_session':
          setVoiceSession(message.data ?? { mode: 'off', state: 'idle' })
          break
      }
    }
  }, [normalizeTasks, pushEvent])

  useEffect(() => {
    connect()
    return () => {
      if (retryRef.current) {
        window.clearTimeout(retryRef.current)
      }
      ws.current?.close()
    }
  }, [connect])

  useEffect(() => {
    const id = window.setInterval(async () => {
      try {
        const response = await fetch('/api/tasks')
        const data = await response.json()
        setTasks(normalizeTasks(data))
      } catch {}
    }, 3000)
    return () => window.clearInterval(id)
  }, [normalizeTasks])

  useEffect(() => {
    const fetchRuntimes = async () => {
      try {
        const response = await fetch('/api/runtimes')
        setRuntimes(await response.json())
      } catch {}
    }
    fetchRuntimes()
    const id = window.setInterval(fetchRuntimes, 10000)
    return () => window.clearInterval(id)
  }, [])

  useEffect(() => {
    const fetchVoiceSession = async () => {
      try {
        const response = await fetch('/api/voice/session')
        setVoiceSession(await response.json())
      } catch {}
    }
    fetchVoiceSession()
    const id = window.setInterval(fetchVoiceSession, 5000)
    return () => window.clearInterval(id)
  }, [])

  const taskStats = useMemo(
    () => ({
      active: tasks.active.length,
      queued: tasks.queued.length,
      failed: tasks.failed.length,
      completed: tasks.completed.length,
    }),
    [tasks]
  )

  return { connected, events, approvals, services, tasks, models, pullProgress, runtimes, voiceSession, taskStats }
}
