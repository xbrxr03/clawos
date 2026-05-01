/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react'

const COMMUNITIES = [
  { id: 0, name: 'Work · Code',   rgb: 'rgb(108,166,255)' },
  { id: 1, name: 'Research · AI', rgb: 'rgb(138,212,150)' },
  { id: 2, name: 'People',        rgb: 'rgb(240,180,110)' },
  { id: 3, name: 'Personal',      rgb: 'rgb(230,140,200)' },
  { id: 4, name: 'Music',         rgb: 'rgb(140,210,215)' },
  { id: 5, name: 'Philosophy',    rgb: 'rgb(238,130,130)' },
]

type GraphNode = { id: string; label: string; c: number; pr: number; sources: string[]; auto?: boolean; isolated?: boolean }
type GraphLink = { src: string; tgt: string; pred: string; auto?: boolean }

const STATIC_NODES: GraphNode[] = [
  { id: 'clawos',        label: 'clawOS',             c: 0, pr: 1.0,  sources: ['GitHub', 'Notes'] },
  { id: 'openclaw',      label: 'OpenClaw',           c: 0, pr: 0.72, sources: ['GitHub', 'Docs'] },
  { id: 'nexus',         label: 'Nexus agent loop',   c: 0, pr: 0.68, sources: ['Code'] },
  { id: 'piper',         label: 'Piper TTS',          c: 0, pr: 0.42, sources: ['GitHub'] },
  { id: 'whisper',       label: 'Whisper',            c: 0, pr: 0.4,  sources: ['GitHub'] },
  { id: 'ollama',        label: 'Ollama',             c: 0, pr: 0.55, sources: ['Docs'] },
  { id: 'pi-mono',       label: 'pi-mono',            c: 0, pr: 0.35, sources: ['GitHub'], auto: true },
  { id: 'react-pattern', label: 'ReAct paper',        c: 1, pr: 0.48, sources: ['ArXiv', 'Notes'] },
  { id: 'leiden',        label: 'Leiden clustering',  c: 1, pr: 0.38, sources: ['Paper'] },
  { id: 'pagerank',      label: 'PageRank',           c: 1, pr: 0.44, sources: ['Notes'] },
  { id: 'rrf',           label: 'RRF hybrid search',  c: 1, pr: 0.36, sources: ['Notes'], auto: true },
  { id: 'chromadb',      label: 'ChromaDB',           c: 1, pr: 0.33, sources: ['Docs'] },
  { id: 'tool-use',      label: 'Tool-use agents',    c: 1, pr: 0.5,  sources: ['Papers'] },
  { id: 'sarah',         label: 'Sarah K.',           c: 2, pr: 0.58, sources: ['Contacts', 'Messages'] },
  { id: 'marco',         label: 'Marco',              c: 2, pr: 0.34, sources: ['Contacts'] },
  { id: 'yuki',          label: 'Yuki T.',            c: 2, pr: 0.3,  sources: ['Email'] },
  { id: 'brother',       label: 'Ben (brother)',      c: 2, pr: 0.4,  sources: ['Photos', 'Messages'] },
  { id: 'tokyo-trip',    label: 'Tokyo 2024',         c: 3, pr: 0.38, sources: ['Photos', 'Notes'] },
  { id: 'apartment',     label: 'Apartment lease',    c: 3, pr: 0.3,  sources: ['Drive'] },
  { id: 'running',       label: 'Marathon training',  c: 3, pr: 0.34, sources: ['Notes', 'Health'] },
  { id: 'coffee-beans',  label: 'Ethiopian Yirgacheffe', c: 3, pr: 0.22, sources: ['Photos'] },
  { id: 'fender',        label: 'Fender Strat',       c: 4, pr: 0.28, sources: ['Photos'] },
  { id: 'jazz-theory',   label: 'Modal jazz theory',  c: 4, pr: 0.3,  sources: ['Notes'] },
  { id: 'miles',         label: 'Miles Davis',        c: 4, pr: 0.32, sources: ['Notes'] },
  { id: 'coltrane',      label: 'Coltrane',           c: 4, pr: 0.25, sources: ['Notes'] },
  { id: 'stoicism',      label: 'Stoicism',           c: 5, pr: 0.18, sources: ['Notes'], isolated: true },
  { id: 'meditations',   label: 'Meditations',        c: 5, pr: 0.2,  sources: ['Notes'], isolated: true },
]

const STATIC_LINKS: GraphLink[] = [
  { src: 'clawos', tgt: 'openclaw', pred: 'builds on' },
  { src: 'clawos', tgt: 'nexus', pred: 'contains' },
  { src: 'clawos', tgt: 'piper', pred: 'uses' },
  { src: 'clawos', tgt: 'whisper', pred: 'uses' },
  { src: 'clawos', tgt: 'ollama', pred: 'depends on' },
  { src: 'openclaw', tgt: 'pi-mono', pred: 'built on', auto: true },
  { src: 'nexus', tgt: 'tool-use', pred: 'implements', auto: true },
  { src: 'nexus', tgt: 'react-pattern', pred: 'follows' },
  { src: 'react-pattern', tgt: 'tool-use', pred: 'related' },
  { src: 'leiden', tgt: 'pagerank', pred: 'complements', auto: true },
  { src: 'rrf', tgt: 'chromadb', pred: 'implemented in' },
  { src: 'pagerank', tgt: 'clawos', pred: 'scores in' },
  { src: 'leiden', tgt: 'clawos', pred: 'clusters in' },
  { src: 'nexus', tgt: 'pagerank', pred: 'ranks memory by' },
  { src: 'chromadb', tgt: 'clawos', pred: 'backs memory of' },
  { src: 'sarah', tgt: 'clawos', pred: 'contributor' },
  { src: 'sarah', tgt: 'tokyo-trip', pred: 'attended' },
  { src: 'marco', tgt: 'clawos', pred: 'reviewer' },
  { src: 'yuki', tgt: 'tokyo-trip', pred: 'guided' },
  { src: 'brother', tgt: 'tokyo-trip', pred: 'attended' },
  { src: 'tokyo-trip', tgt: 'coffee-beans', pred: 'discovered' },
  { src: 'apartment', tgt: 'running', pred: 'route near' },
  { src: 'fender', tgt: 'jazz-theory', pred: 'plays' },
  { src: 'jazz-theory', tgt: 'miles', pred: 'exemplified by' },
  { src: 'miles', tgt: 'coltrane', pred: 'played with' },
  { src: 'coltrane', tgt: 'jazz-theory', pred: 'explored' },
  { src: 'running', tgt: 'miles', pred: 'listens to' },
]

function computeLayout(nodes: GraphNode[], w: number, h: number) {
  const cx = w / 2, cy = h / 2
  const clusters: Record<number, { x: number; y: number }> = {}
  COMMUNITIES.forEach((c, i) => {
    const ang = (i / COMMUNITIES.length) * Math.PI * 2 - Math.PI / 2
    const r = Math.min(w, h) * 0.28
    clusters[c.id] = { x: cx + Math.cos(ang) * r, y: cy + Math.sin(ang) * r }
  })
  if (clusters[5]) {
    clusters[5].x = cx + (clusters[5].x - cx) * 1.45
    clusters[5].y = cy + (clusters[5].y - cy) * 1.45
  }
  const pos: Record<string, { x: number; y: number; z: number }> = {}
  const byC: Record<number, GraphNode[]> = {}
  nodes.forEach(n => { (byC[n.c] = byC[n.c] || []).push(n) })
  Object.entries(byC).forEach(([cid, ns]) => {
    const cidN = Number(cid)
    const center = clusters[cidN] || { x: cx, y: cy }
    ns.forEach((n, i) => {
      const ang = (i / ns.length) * Math.PI * 2 + cidN * 0.7
      const rr = 70 + (1 - n.pr) * 40 + (i % 3) * 12
      const z = Math.sin(ang * 2 + cidN) * 30
      pos[n.id] = { x: center.x + Math.cos(ang) * rr, y: center.y + Math.sin(ang) * rr * 0.78, z }
    })
  })
  return pos
}

export function BrainPage() {
  const wrapRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const wsRef = useRef<WebSocket | null>(null)

  const [size, setSize] = useState({ w: 900, h: 700 })
  const [rot, setRot] = useState({ x: 0, y: 0 })
  const [drag, setDrag] = useState<{ x: number; y: number; rx: number; ry: number } | null>(null)
  const [zoom, setZoom] = useState(1)
  const [t, setT] = useState(0)
  const [selected, setSelected] = useState<string | null>(null)
  const [hover, setHover] = useState<string | null>(null)
  const [firing, setFiring] = useState<Array<{ path: string[]; start: number }>>([])
  const [showGaps, setShowGaps] = useState(false)
  const [searchQ, setSearchQ] = useState('')
  const [nodes, setNodes] = useState<GraphNode[]>(STATIC_NODES)
  const [links, setLinks] = useState<GraphLink[]>(STATIC_LINKS)
  const [ingestProgress, setIngestProgress] = useState({ done: 0, total: 142, file: 'tokyo_trip_notes.md', active: false })
  const [nodeChat, setNodeChat] = useState('')
  const [chatAnswer, setChatAnswer] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [nodeCount, setNodeCount] = useState(STATIC_NODES.length)
  const [edgeCount, setEdgeCount] = useState(STATIC_LINKS.length)

  useEffect(() => {
    const update = () => {
      if (wrapRef.current) {
        const r = wrapRef.current.getBoundingClientRect()
        setSize({ w: r.width, h: r.height })
      }
    }
    update()
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
  }, [])

  useEffect(() => {
    let raf: number
    const start = performance.now()
    const tick = (now: number) => { setT((now - start) / 1000); raf = requestAnimationFrame(tick) }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [])

  useEffect(() => {
    if (drag) return
    const iv = setInterval(() => setRot(r => ({ x: r.x, y: r.y + 0.15 })), 50)
    return () => clearInterval(iv)
  }, [drag])

  useEffect(() => {
    const adj: Record<string, string[]> = {}
    links.forEach(l => { (adj[l.src] = adj[l.src] || []).push(l.tgt); (adj[l.tgt] = adj[l.tgt] || []).push(l.src) })
    const fire = () => {
      const keys = Object.keys(adj)
      if (keys.length === 0) return
      const start = keys[Math.floor(Math.random() * keys.length)]
      const path = [start]
      for (let i = 0; i < 3 + Math.floor(Math.random() * 2); i++) {
        const nexts = adj[path[path.length - 1]] || []
        const next = nexts[Math.floor(Math.random() * nexts.length)]
        if (next && !path.includes(next)) path.push(next)
      }
      setFiring(f => [...f, { path, start: performance.now() }])
    }
    const iv = setInterval(fire, 2200)
    setTimeout(fire, 600)
    return () => clearInterval(iv)
  }, [links])

  useEffect(() => {
    const iv = setInterval(() => setFiring(f => f.filter(x => performance.now() - x.start < 3000)), 500)
    return () => clearInterval(iv)
  }, [])

  useEffect(() => {
    if (!ingestProgress.active) return
    const FILES = ['tokyo_trip_notes.md', 'clawos_architecture.md', 'sarah_email_thread.eml', 'jazz_theory.pdf', 'meditations.epub']
    const iv = setInterval(() => {
      setIngestProgress(p => {
        const next = Math.min(p.done + 1 + Math.floor(Math.random() * 2), p.total)
        return { ...p, done: next, file: next === p.total ? 'complete' : FILES[next % FILES.length], active: next < p.total }
      })
    }, 220)
    return () => clearInterval(iv)
  }, [ingestProgress.active])

  useEffect(() => {
    const loadGraph = async () => {
      try {
        const r = await fetch('/api/brain/graph', { credentials: 'include' })
        if (r.ok) {
          const data = await r.json()
          if (Array.isArray(data.nodes) && data.nodes.length > 0) {
            const mapped: GraphNode[] = data.nodes.map((n: any) => ({
              id: n.id, label: n.label || n.id, c: n.community ?? 0,
              pr: n.pagerank ?? 0.3, sources: n.sources || [], auto: n.agent_added,
            }))
            setNodes(mapped)
            setNodeCount(data.node_count || mapped.length)
            if (Array.isArray(data.links) && data.links.length > 0) {
              const ml: GraphLink[] = data.links.map((l: any) => ({
                src: typeof l.source === 'string' ? l.source : l.source?.id,
                tgt: typeof l.target === 'string' ? l.target : l.target?.id,
                pred: l.predicate || '', auto: l.agent_added,
              })).filter((l: any) => l.src && l.tgt)
              setLinks(ml)
              setEdgeCount(ml.length)
            }
          }
        }
      } catch { /* fallback to static data */ }
    }
    void loadGraph()
    try {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      const ws = new WebSocket(`${proto}://${location.host}/ws/brain`)
      wsRef.current = ws
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data)
          if (msg.event === 'complete') { void loadGraph() }
          if (msg.event === 'file') setIngestProgress(p => ({ ...p, active: true }))
        } catch {}
      }
    } catch {}
    return () => wsRef.current?.close()
  }, [])

  const layout = useMemo(() => computeLayout(nodes, size.w, size.h), [nodes, size.w, size.h])

  const project = useCallback((p: { x: number; y: number; z: number }) => {
    const cx = size.w / 2, cy = size.h / 2
    const dx = p.x - cx, dy = p.y - cy
    const cosY = Math.cos(rot.y * Math.PI / 180), sinY = Math.sin(rot.y * Math.PI / 180)
    const nx = dx * cosY + p.z * sinY, nz = -dx * sinY + p.z * cosY
    const cosX = Math.cos(rot.x * Math.PI / 180), sinX = Math.sin(rot.x * Math.PI / 180)
    const ny = dy * cosX + nz * sinX, finalZ = -dy * sinX + nz * cosX
    const persp = 400 / (400 + finalZ)
    return { x: cx + nx * persp * zoom, y: cy + ny * persp * zoom, scale: persp, z: finalZ }
  }, [size.w, size.h, rot.x, rot.y, zoom])

  const projected = useMemo(() => {
    const out: Record<string, { x: number; y: number; scale: number; z: number }> = {}
    nodes.forEach(n => { out[n.id] = project(layout[n.id] || { x: size.w / 2, y: size.h / 2, z: 0 }) })
    return out
  }, [layout, project, nodes, size.w, size.h])

  const sortedLinks = useMemo(() => links.map(l => {
    const a = projected[l.src], b = projected[l.tgt]
    return a && b ? { ...l, z: (a.z + b.z) / 2 } : null
  }).filter(Boolean).sort((x: any, y: any) => y.z - x.z) as (GraphLink & { z: number })[], [projected, links])

  const sortedNodes = useMemo(() => [...nodes].sort((a, b) => (projected[b.id]?.z ?? 0) - (projected[a.id]?.z ?? 0)), [nodes, projected])

  const linkFire = useCallback((src: string, tgt: string) => {
    const now = performance.now()
    for (const f of firing) {
      for (let i = 0; i < f.path.length - 1; i++) {
        if ((f.path[i] === src && f.path[i + 1] === tgt) || (f.path[i] === tgt && f.path[i + 1] === src)) {
          const dt = (now - f.start) / 1000, segT = i * 0.4
          if (dt >= segT && dt < segT + 1.2) return (dt - segT) / 1.2
        }
      }
    }
    return 0
  }, [firing])

  const nodeFire = useCallback((id: string) => {
    const now = performance.now()
    for (const f of firing) {
      const idx = f.path.indexOf(id)
      if (idx >= 0) {
        const dt = (now - f.start) / 1000, segT = idx * 0.4
        if (dt >= segT && dt < segT + 0.8) return 1 - Math.abs((dt - segT) - 0.3) / 0.5
      }
    }
    return 0
  }, [firing])

  const onDown = (e: React.MouseEvent) => setDrag({ x: e.clientX, y: e.clientY, rx: rot.x, ry: rot.y })
  const onMove = (e: React.MouseEvent) => {
    if (!drag) return
    setRot({ x: Math.max(-50, Math.min(50, drag.rx + (e.clientY - drag.y) * 0.4)), y: drag.ry + (e.clientX - drag.x) * 0.4 })
  }
  const onUp = () => setDrag(null)
  const onWheel = (e: React.WheelEvent) => { e.preventDefault(); setZoom(z => Math.max(0.5, Math.min(2.5, z - e.deltaY * 0.002))) }

  const comm = (c: number) => COMMUNITIES[c] || COMMUNITIES[0]
  const selNode = selected ? nodes.find(n => n.id === selected) ?? null : null
  const selRels = selected ? links.filter(l => l.src === selected || l.tgt === selected).map(l => ({
    pred: l.pred, auto: l.auto,
    other: nodes.find(n => n.id === (l.src === selected ? l.tgt : l.src)),
    dir: l.src === selected ? '→' : '←',
  })).filter(r => r.other) : []

  const searchMatch = (n: GraphNode) => searchQ.length > 0 && n.label.toLowerCase().includes(searchQ.toLowerCase())
  const anyMatch = searchQ.length > 0 && nodes.some(searchMatch)

  const handleUpload = async (file: File) => {
    if (!file.name.endsWith('.zip')) return
    setIngestProgress({ done: 0, total: 142, file: file.name, active: true })
    try {
      await fetch('/api/brain/upload', { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/zip' }, body: file })
    } catch {}
  }

  const handleNodeChat = async (e: FormEvent) => {
    e.preventDefault()
    if (!nodeChat.trim() || !selNode) return
    setChatLoading(true); setChatAnswer('')
    try {
      const r = await fetch('/api/chat', {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: `[Kizuna context: "${selNode.label}"]\n\n${nodeChat}`, workspace: 'nexus_default' }),
      })
      if (r.ok) { const d = await r.json(); setChatAnswer(d.reply || d.result || '') }
    } catch { setChatAnswer('Failed to get response') }
    finally { setChatLoading(false) }
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 360px', height: '100%', overflow: 'hidden', flex: 1 }}>
      {/* Graph canvas */}
      <div style={{ position: 'relative', overflow: 'hidden', cursor: drag ? 'grabbing' : 'grab' }}
        ref={wrapRef}
        onMouseDown={onDown} onMouseMove={onMove} onMouseUp={onUp} onMouseLeave={onUp} onWheel={onWheel}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) void handleUpload(f) }}
      >
        <div className="stars" />
        <svg width={size.w} height={size.h} style={{ position: 'absolute', inset: 0, display: 'block' }}>
          <defs>
            <filter id="brGlow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
            <filter id="brBigGlow" x="-80%" y="-80%" width="260%" height="260%">
              <feGaussianBlur stdDeviation="8" result="b" />
              <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>

          {/* Links */}
          {sortedLinks.map((l, i) => {
            const a = projected[l.src], b = projected[l.tgt]
            if (!a || !b) return null
            const fire = linkFire(l.src, l.tgt)
            const srcN = nodes.find(n => n.id === l.src)
            const color = srcN ? comm(srcN.c).rgb : 'rgba(255,255,255,0.3)'
            const isHoverConn = hover && (l.src === hover || l.tgt === hover)
            const isSelConn = selected && (l.src === selected || l.tgt === selected)
            const isGap = showGaps && (nodes.find(n => n.id === l.src)?.isolated || nodes.find(n => n.id === l.tgt)?.isolated)
            const baseOp = (hover || selected) ? ((isHoverConn || isSelConn) ? 0.55 : 0.08) : 0.28
            const op = Math.max(baseOp, fire * 0.9)
            const w = 0.7 + fire * 2.5 + (l.auto ? 0.3 : 0) + (isSelConn ? 0.7 : 0)
            return (
              <g key={i}>
                <line x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                  stroke={isGap ? 'var(--danger)' : color}
                  strokeOpacity={op} strokeWidth={w}
                  strokeDasharray={l.auto ? '3 3' : undefined}
                  style={fire > 0 ? { filter: 'url(#brGlow)' } : undefined}
                />
                {fire > 0 && (
                  <circle cx={a.x + (b.x - a.x) * fire} cy={a.y + (b.y - a.y) * fire}
                    r={3} fill="#fff" style={{ filter: 'url(#brBigGlow)' }} />
                )}
                {isSelConn && (
                  <text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 4}
                    fill="var(--ink-3)" fontFamily="var(--mono)" fontSize="9" textAnchor="middle" letterSpacing="0.06em">
                    {l.pred.toUpperCase()}
                  </text>
                )}
              </g>
            )
          })}

          {/* Nodes */}
          {sortedNodes.map(n => {
            const p = projected[n.id]; if (!p) return null
            const co = comm(n.c)
            const baseR = 6 + n.pr * 14, r = baseR * p.scale
            const fire = nodeFire(n.id)
            const isHover = hover === n.id, isSel = selected === n.id, isMatch = searchMatch(n)
            const dim = (hover || selected) && !isHover && !isSel
              && !links.some(l => (l.src === (hover || selected) && l.tgt === n.id) || (l.tgt === (hover || selected) && l.src === n.id))
            const showLabel = isHover || isSel || n.pr > 0.5 || fire > 0 || isMatch
            return (
              <g key={n.id} opacity={dim ? 0.2 : 1}
                onMouseEnter={() => setHover(n.id)}
                onMouseLeave={() => setHover(null)}
                onClick={(e) => { e.stopPropagation(); setSelected(n.id); setChatAnswer(''); setNodeChat('') }}
                style={{ cursor: 'pointer' }}
              >
                {(isSel || isHover || fire > 0 || isMatch) && (
                  <circle cx={p.x} cy={p.y} r={r * 2.5} fill={co.rgb} opacity={0.15 + fire * 0.3} style={{ filter: 'url(#brBigGlow)' }} />
                )}
                {showGaps && n.isolated && (
                  <circle cx={p.x} cy={p.y} r={r * 1.8} fill="none" stroke="var(--danger)"
                    strokeWidth="1" strokeDasharray="2 3" opacity={0.6 + Math.sin(t * 4) * 0.3} />
                )}
                <circle cx={p.x} cy={p.y} r={r} fill={co.rgb}
                  stroke={n.auto ? '#fff' : 'rgba(255,255,255,0.2)'}
                  strokeWidth={n.auto ? 0.8 : 0.5}
                  strokeDasharray={n.auto ? '2 2' : undefined}
                  style={{ filter: fire > 0.5 ? 'url(#brBigGlow)' : 'url(#brGlow)' }}
                />
                <circle cx={p.x - r * 0.3} cy={p.y - r * 0.3} r={r * 0.35} fill="rgba(255,255,255,0.45)" />
                {showLabel && (
                  <g>
                    <text x={p.x + r + 6} y={p.y + 3}
                      fill={isSel || isHover ? 'var(--ink-1)' : 'var(--ink-2)'}
                      fontFamily="var(--sans)" fontSize={isSel || isHover ? 13 : 11}
                      fontWeight={isSel || isHover ? 600 : 500}
                      style={{ paintOrder: 'stroke', stroke: 'rgba(0,0,0,0.9)', strokeWidth: 3 }}
                    >{n.label}</text>
                    {(isSel || isHover) && (
                      <text x={p.x + r + 6} y={p.y + 17} fill="var(--ink-4)"
                        fontFamily="var(--mono)" fontSize={9} letterSpacing="0.06em"
                        style={{ paintOrder: 'stroke', stroke: 'rgba(0,0,0,0.9)', strokeWidth: 3 }}
                      >PR · {n.pr.toFixed(2)} · {co.name.toUpperCase()}</text>
                    )}
                  </g>
                )}
              </g>
            )
          })}
        </svg>

        {/* HUD top */}
        <div className="hud-top">
          <div className="hud-stat"><span className="k">Nodes</span><span className="v">{nodeCount}<span className="u">+{ingestProgress.done}</span></span></div>
          <div className="hud-stat"><span className="k">Edges</span><span className="v">{edgeCount}</span></div>
          <div className="hud-stat"><span className="k">Clusters</span><span className="v">{COMMUNITIES.length}<span className="u">· leiden</span></span></div>
          <div className="hud-stat pulse"><span className="k">Firing</span><span className="v">{firing.length > 0 ? firing.length : '—'}<span className="u">· jarvis</span></span></div>
          <div className="brain-search">
            <span className="sym">⌕</span>
            <input placeholder="Search nodes…" value={searchQ} onChange={(e) => setSearchQ(e.target.value)} />
            <span className="sym" style={{ fontSize: 10, opacity: 0.6 }}>{anyMatch ? `${nodes.filter(searchMatch).length} hits` : ''}</span>
          </div>
        </div>

        {/* HUD bottom */}
        <div className="hud-bottom">
          {ingestProgress.active ? (
            <div className="ingest">
              <h4><span className="d" />Ingesting · notes.zip</h4>
              <div className="file">{ingestProgress.file}</div>
              <div className="sub">{ingestProgress.done} / {ingestProgress.total} files · extracting with qwen2.5:3b</div>
              <div className="bar"><div className="f" style={{ width: `${(ingestProgress.done / ingestProgress.total) * 100}%` }} /></div>
            </div>
          ) : (
            <div className="ingest">
              <h4 style={{ color: 'var(--success)' }}><span className="d" style={{ background: 'var(--success)' }} />Drop .zip anywhere to ingest</h4>
              <div className="sub">entities extracted and linked automatically with qwen2.5:3b</div>
            </div>
          )}
          <div className="controls">
            <button className={`ctrl ${showGaps ? 'on' : ''}`} onClick={() => setShowGaps(s => !s)}>
              ⌖ GAPS {showGaps && `· ${nodes.filter(n => n.isolated).length}`}
            </button>
            <button className="ctrl" onClick={() => { setRot({ x: 0, y: 0 }); setZoom(1) }}>⟲ RESET</button>
            <button className="ctrl" onClick={() => fileInputRef.current?.click()}>＋ ADD .ZIP</button>
          </div>
        </div>

        <input ref={fileInputRef} type="file" accept=".zip" style={{ display: 'none' }}
          onChange={(e) => e.target.files?.[0] && void handleUpload(e.target.files[0])} />
      </div>

      {/* Right rail — node inspector */}
      <aside className="rail" style={{ background: 'rgba(0,0,0,0.35)', borderLeft: '1px solid var(--panel-br)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {!selNode ? (
          <div className="brain-rail-empty">
            <div className="big">Click a node</div>
            <p>Your brain is a living graph. Tap any memory to see its sources, relationships, and chat with Jarvis about it.</p>
            <div className="mono">↓  drop .zip to ingest  ↓</div>
            <div className="brain-legend-t" style={{ marginTop: 20 }}>Communities</div>
            {COMMUNITIES.map(c => (
              <div key={c.id} className="brain-legend-row">
                <span className="sw" style={{ background: c.rgb }} />
                <span>{c.name}</span>
                <span style={{ marginLeft: 'auto', fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink-4)' }}>{nodes.filter(n => n.c === c.id).length}</span>
              </div>
            ))}
          </div>
        ) : (
          <>
            <div className="node-head">
              <div className="node-cluster" style={{ color: comm(selNode.c).rgb }}>
                <span className="sw" style={{ background: comm(selNode.c).rgb }} />
                {comm(selNode.c).name}
              </div>
              <h2 style={{ fontSize: 22, fontWeight: 600, letterSpacing: '-0.02em', margin: '8px 0 6px' }}>{selNode.label}</h2>
              <div className="node-pr">pr · {selNode.pr.toFixed(3)} · mentions · {Math.round(selNode.pr * 28)} · {selNode.auto ? 'auto-inferred' : 'user-added'}</div>
            </div>

            <div className="node-sect">
              <h5>Sources</h5>
              <div className="brain-sources">
                {(selNode.sources || []).map(s => <span key={s} className="s">{s}</span>)}
              </div>
            </div>

            <div className="node-sect">
              <h5>Relationships · {selRels.length}</h5>
              {selRels.map((r, i) => (
                <div key={i} className={`brain-rel${r.auto ? ' auto' : ''}`}>
                  <span className="pred">{r.dir} {r.pred}</span>
                  <span className="tgt" onClick={() => { setSelected(r.other!.id); setChatAnswer(''); setNodeChat('') }}>{r.other!.label}</span>
                </div>
              ))}
            </div>

            <div className="brain-chat">
              <div className="brain-msgs">
                <div className="brain-msg u">Tell me about "{selNode.label}" in context of my notes.</div>
                {chatAnswer && <div className="brain-msg a">{chatAnswer}</div>}
                {chatLoading && <div className="brain-msg a" style={{ opacity: 0.5 }}>Thinking…</div>}
                {!chatAnswer && !chatLoading && (
                  <div className="brain-msg a">
                    {selNode.isolated
                      ? 'This node is isolated — no edges to the rest of your brain. Want me to find related concepts and propose links?'
                      : `Connected to ${selRels.length} other memories. Ask me anything about "${selNode.label}".`}
                  </div>
                )}
              </div>
              <form className="brain-chat-ibar" onSubmit={(e) => void handleNodeChat(e)}>
                <input placeholder={`Ask Jarvis about "${selNode.label}"…`}
                  value={nodeChat} onChange={(e) => setNodeChat(e.target.value)} />
                <button type="submit" disabled={chatLoading || !nodeChat.trim()}>↵</button>
              </form>
            </div>
          </>
        )}
      </aside>
    </div>
  )
}

export default BrainPage
