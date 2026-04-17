// SPDX-License-Identifier: AGPL-3.0-or-later
/**
 * Kizuna (絆) — 3D Knowledge Graph Page
 *
 * Features:
 * - react-force-graph-3d with UnrealBloom glow effect
 * - Community-colored clusters (Leiden detection)
 * - Node size by PageRank (importance)
 * - Neuron-firing animation when AI traverses the graph
 * - Live ingestion: nodes appear one-by-one as ZIP is processed
 * - Click node → side panel with AI chat seeded on that node
 * - Gap detection overlay (isolated nodes highlighted red)
 * - Semantic search → camera flies to closest node
 * - Drag-and-drop ZIP upload
 */
import React, {
  useCallback, useEffect, useRef, useState, lazy, Suspense,
} from 'react'
// @ts-ignore — JSX component, no type declarations
import StructuredMessage from '../components/StructuredMessage.jsx'

// Lazy-load the heavy 3D graph (only loads on Brain page)
const ForceGraph3D = lazy(() => import('react-force-graph-3d'))

// ── Types ──────────────────────────────────────────────────────────────────────
interface BrainNode {
  id: string
  label: string
  color: string
  size: number
  community: number
  agent_added: boolean
  sources: string[]
  mention_count: number
  pagerank: number
  // ForceGraph adds these at runtime:
  x?: number; y?: number; z?: number
}

interface BrainLink {
  source: string | BrainNode
  target: string | BrainNode
  predicate: string
  agent_added: boolean
}

interface GraphData {
  nodes: BrainNode[]
  links: BrainLink[]
}

interface BrainStatus {
  node_count: number
  edge_count: number
  community_count: number
  ingesting: boolean
  progress?: {
    event?: string
    message?: string
    file_number?: number
    total_files?: number
    nodes_so_far?: number
  }
}

// ── Constants ──────────────────────────────────────────────────────────────────
const EMPTY_GRAPH: GraphData = { nodes: [], links: [] }
const PULSE_DURATION_MS = 600
const NEURON_FIRE_COLOR = '#ffffff'

// ── Helpers ───────────────────────────────────────────────────────────────────
function getNodeId(n: string | BrainNode): string {
  return typeof n === 'string' ? n : n.id
}

// ── Main Component ─────────────────────────────────────────────────────────────
export function BrainPage() {
  const fgRef = useRef<any>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [graph, setGraph] = useState<GraphData>(EMPTY_GRAPH)
  const [status, setStatus] = useState<BrainStatus>({
    node_count: 0, edge_count: 0, community_count: 0, ingesting: false,
  })
  const [selectedNode, setSelectedNode] = useState<BrainNode | null>(null)
  const [showGaps, setShowGaps] = useState(false)
  const [gaps, setGaps] = useState<any[]>([])
  const [gapNodeIds, setGapNodeIds] = useState<Set<string>>(new Set())
  const [searchQuery, setSearchQuery] = useState('')
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState('')
  const [firingNodes, setFiringNodes] = useState<Set<string>>(new Set())
  const [nodeChat, setNodeChat] = useState('')
  const [chatAnswer, setChatAnswer] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [error, setError] = useState('')

  // ── Load graph data ──────────────────────────────────────────────────────────
  useEffect(() => {
    fetchGraph()
    fetchStatus()
    connectWS()
    return () => wsRef.current?.close()
  }, [])

  // ── Bloom post-processing (optional, degrades gracefully) ────────────────────
  useEffect(() => {
    if (!fgRef.current) return
    // Wait one frame for the graph engine to initialise
    const t = setTimeout(() => {
      try {
        const fg = fgRef.current
        if (!fg?.postProcessingComposer) return
        const composer = fg.postProcessingComposer()
        if (!composer) return
        // postprocessing package is a peer dep — import dynamically so it
        // never blocks the page if it isn't installed
        import('postprocessing').then(({ BloomEffect, EffectPass }) => {
          try {
            const camera = fg.camera()
            composer.addPass(
              new EffectPass(camera,
                new BloomEffect({ intensity: 1.8, luminanceThreshold: 0.15, luminanceSmoothing: 0.8 })
              )
            )
          } catch { /* bloom unavailable – silently skip */ }
        }).catch(() => { /* postprocessing not installed – skip */ })
      } catch { /* graph not ready – skip */ }
    }, 500)
    return () => clearTimeout(t)
  }, [graph])

  const fetchGraph = async () => {
    try {
      const r = await fetch('/api/brain/graph', { credentials: 'include' })
      if (r.ok) {
        const data = await r.json()
        setGraph(data)
      }
    } catch (e) {
      setError('Failed to load graph data')
    }
  }

  const fetchStatus = async () => {
    try {
      const r = await fetch('/api/brain/status', { credentials: 'include' })
      if (r.ok) setStatus(await r.json())
    } catch { /* non-fatal */ }
  }

  const fetchGaps = async () => {
    try {
      const r = await fetch('/api/brain/gaps', { credentials: 'include' })
      if (r.ok) {
        const data = await r.json()
        const gapList = data.gaps || []
        setGaps(gapList)
        const ids = new Set<string>()
        gapList.forEach((g: any) => {
          if (g.node_id) ids.add(g.node_id)
          if (g.nodes) g.nodes.forEach((n: string) => ids.add(n))
        })
        setGapNodeIds(ids)
      }
    } catch { /* non-fatal */ }
  }

  // ── WebSocket for real-time progress + neuron firing ────────────────────────
  const connectWS = () => {
    try {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      const ws = new WebSocket(`${proto}://${location.host}/ws/brain`)
      wsRef.current = ws

      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data)
          handleWSMessage(msg)
        } catch { /* ignore */ }
      }

      ws.onclose = () => {
        // Reconnect after 3s
        setTimeout(connectWS, 3000)
      }

      // Keep-alive ping
      const ping = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send('ping')
      }, 25000)
      ws.onclose = () => { clearInterval(ping); setTimeout(connectWS, 3000) }
    } catch { /* no websocket support */ }
  }

  const handleWSMessage = (msg: any) => {
    const { event } = msg

    if (event === 'status' || event === 'heartbeat') {
      fetchStatus()
      return
    }

    if (event === 'file' || event === 'computing' || event === 'saving') {
      setUploadProgress(msg.message || `Processing file ${msg.file_number}/${msg.total_files}...`)
      setStatus(prev => ({
        ...prev,
        ingesting: true,
        node_count: msg.nodes_so_far || prev.node_count,
      }))
      // If new nodes, refresh graph incrementally
      if (msg.nodes_so_far && msg.nodes_so_far > (graph.nodes.length || 0)) {
        fetchGraph()
      }
    }

    if (event === 'complete') {
      setUploadProgress(msg.message || 'Brain updated!')
      setUploading(false)
      fetchGraph()
      fetchStatus()
      // Trigger neuron firing animation on new nodes
      if (graph.nodes.length > 0) {
        fireRandomNeurons(8)
      }
      setTimeout(() => setUploadProgress(''), 4000)
    }

    if (event === 'error') {
      setError(msg.message || 'Ingestion failed')
      setUploading(false)
    }

    // Agent expanded the brain → fire neurons along affected nodes
    if (event === 'expand') {
      fireRandomNeurons(4)
    }
  }

  // ── Neuron firing animation ──────────────────────────────────────────────────
  const fireRandomNeurons = (count: number) => {
    if (graph.nodes.length === 0) return
    const nodeIds = graph.nodes
      .sort(() => Math.random() - 0.5)
      .slice(0, count)
      .map(n => n.id)

    const fire = new Set(nodeIds)
    setFiringNodes(fire)
    setTimeout(() => setFiringNodes(new Set()), PULSE_DURATION_MS)
  }

  // Fire neurons along a path when a node is selected (simulates AI retrieval)
  const fireNeuronPath = useCallback((startNodeId: string) => {
    const node = graph.nodes.find(n => n.id === startNodeId)
    if (!node) return

    // Find neighbors
    const neighborIds: string[] = []
    graph.links.forEach(l => {
      const s = getNodeId(l.source)
      const t = getNodeId(l.target)
      if (s === startNodeId) neighborIds.push(t)
      if (t === startNodeId) neighborIds.push(s)
    })

    // Cascade firing: start node → neighbors → their neighbors
    setFiringNodes(new Set([startNodeId]))
    setTimeout(() => {
      setFiringNodes(new Set([startNodeId, ...neighborIds.slice(0, 6)]))
    }, 150)
    setTimeout(() => {
      setFiringNodes(new Set())
    }, PULSE_DURATION_MS * 2)
  }, [graph])

  // ── Node color with gap/firing override ────────────────────────────────────
  const getNodeColor = useCallback((node: BrainNode) => {
    if (firingNodes.has(node.id)) return NEURON_FIRE_COLOR
    if (showGaps && gapNodeIds.has(node.id)) return '#ef4444'
    return node.color
  }, [firingNodes, showGaps, gapNodeIds])

  // ── Node click → focus camera + side panel ─────────────────────────────────
  const handleNodeClick = useCallback((node: BrainNode) => {
    setSelectedNode(node)
    setChatAnswer('')
    setNodeChat('')
    fireNeuronPath(node.id)

    // Camera fly-to
    if (fgRef.current && node.x !== undefined) {
      const distance = 120
      const distRatio = 1 + distance / Math.hypot(node.x || 0, node.y || 0, node.z || 0)
      fgRef.current.cameraPosition(
        { x: (node.x || 0) * distRatio, y: (node.y || 0) * distRatio, z: (node.z || 0) * distRatio },
        node,
        800,
      )
    }
  }, [fireNeuronPath])

  // ── Search → fly to closest node ───────────────────────────────────────────
  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!searchQuery.trim()) return

    try {
      const r = await fetch(`/api/brain/context?q=${encodeURIComponent(searchQuery)}`, {
        credentials: 'include',
      })
      if (r.ok) {
        const data = await r.json()
        const topNode = data.nodes?.[0]
        if (topNode) {
          const graphNode = graph.nodes.find(n => n.id === topNode.id)
          if (graphNode) handleNodeClick(graphNode)
        }
      }
    } catch { /* non-fatal */ }
  }

  // ── ZIP upload ───────────────────────────────────────────────────────────────
  const handleUpload = async (file: File) => {
    if (!file.name.endsWith('.zip')) {
      setError('Please upload a ZIP file')
      return
    }
    setUploading(true)
    setError('')
    setUploadProgress('Uploading...')

    try {
      const r = await fetch('/api/brain/upload', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/zip' },
        body: file,
      })
      if (!r.ok) {
        const err = await r.json()
        throw new Error(err.detail || 'Upload failed')
      }
      setUploadProgress('Ingestion started — processing files...')
    } catch (e: any) {
      setError(e.message || 'Upload failed')
      setUploading(false)
      setUploadProgress('')
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleUpload(file)
  }

  // ── Node chat ─────────────────────────────────────────────────────────────
  const handleNodeChat = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!nodeChat.trim() || !selectedNode) return
    setChatLoading(true)
    setChatAnswer('')

    try {
      const r = await fetch('/api/chat', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: `[Kizuna context: "${selectedNode.label}"]\n\n${nodeChat}`,
          workspace: 'nexus_default',
        }),
      })
      if (r.ok) {
        const data = await r.json()
        setChatAnswer(data.reply || data.result || '')
        fireNeuronPath(selectedNode.id)
      }
    } catch {
      setChatAnswer('Failed to get response')
    } finally {
      setChatLoading(false)
    }
  }

  const isEmpty = graph.nodes.length === 0

  return (
    <div className="relative w-full h-full bg-[#060609] overflow-hidden flex">

      {/* ── 3D Graph ── */}
      <div
        className="flex-1 relative"
        onDrop={handleDrop}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
      >
        {/* Upload overlay when dragging */}
        {dragging && (
          <div className="absolute inset-0 z-30 bg-violet-900/60 flex items-center justify-center border-2 border-violet-400 border-dashed rounded-xl m-4">
            <div className="text-center">
              <div className="text-5xl mb-3">⬡</div>
              <p className="text-white text-xl font-semibold">Drop ZIP to feed the brain</p>
            </div>
          </div>
        )}

        {/* Empty state */}
        {isEmpty && !uploading && (
          <div className="absolute inset-0 flex items-center justify-center z-10">
            <div className="text-center max-w-sm">
              <div className="text-6xl mb-4 opacity-30">絆</div>
              <h2 className="text-white text-2xl font-bold mb-2">Kizuna is empty</h2>
              <p className="text-white/50 text-sm mb-6">
                Drop a ZIP of your files — notes, PDFs, docs, code —
                and watch your knowledge become a living 3D graph.
              </p>
              <button
                onClick={() => fileInputRef.current?.click()}
                className="px-6 py-3 bg-violet-600 hover:bg-violet-500 text-white rounded-xl font-semibold transition-colors"
              >
                Upload ZIP →
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".zip"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0])}
              />
            </div>
          </div>
        )}

        {/* Upload progress overlay */}
        {uploading && (
          <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-20
                          bg-black/80 backdrop-blur border border-violet-500/40
                          rounded-xl px-5 py-3 flex items-center gap-3">
            <div className="w-3 h-3 rounded-full bg-violet-400 animate-pulse" />
            <span className="text-white/80 text-sm font-medium">{uploadProgress}</span>
            {status.node_count > 0 && (
              <span className="text-violet-400 text-xs">
                {status.node_count} nodes
              </span>
            )}
          </div>
        )}

        {/* Error banner */}
        {error && (
          <div className="absolute top-4 left-1/2 -translate-x-1/2 z-20
                          bg-red-900/80 border border-red-500/50 rounded-lg px-4 py-2">
            <span className="text-red-300 text-sm">{error}</span>
            <button onClick={() => setError('')} className="ml-3 text-red-400 hover:text-red-200">✕</button>
          </div>
        )}

        {/* 3D Graph */}
        {!isEmpty && (
          <Suspense fallback={
            <div className="flex items-center justify-center h-full">
              <div className="text-violet-400 animate-pulse">Loading 3D engine...</div>
            </div>
          }>
            <ForceGraph3D
              ref={fgRef}
              graphData={graph}
              backgroundColor="#060609"
              nodeLabel="label"
              nodeColor={getNodeColor}
              nodeVal={(n: BrainNode) => n.size}
              nodeOpacity={0.9}
              linkColor={(l: BrainLink) =>
                l.agent_added ? 'rgba(167,139,250,0.6)' : 'rgba(255,255,255,0.12)'
              }
              linkWidth={(l: BrainLink) => l.agent_added ? 1.5 : 0.8}
              linkDirectionalParticles={(l: BrainLink) =>
                firingNodes.has(getNodeId(l.source)) || firingNodes.has(getNodeId(l.target)) ? 4 : 0
              }
              linkDirectionalParticleSpeed={0.008}
              linkDirectionalParticleWidth={2}
              linkDirectionalParticleColor={() => '#c4b5fd'}
              onNodeClick={handleNodeClick}
              nodeThreeObject={(node: BrainNode) => {
                // Custom sphere with bloom-compatible material
                const THREE = (window as any).THREE
                if (!THREE) return undefined
                const size = Math.max(2, node.size * 0.4)
                const geo = new THREE.SphereGeometry(size, 12, 12)
                const mat = new THREE.MeshStandardMaterial({
                  color: getNodeColor(node),
                  emissive: getNodeColor(node),
                  emissiveIntensity: firingNodes.has(node.id) ? 3.0 : 0.6,
                  roughness: 0.3,
                  metalness: 0.1,
                })
                return new THREE.Mesh(geo, mat)
              }}
              nodeThreeObjectExtend={false}
              rendererConfig={{
                antialias: true,
                alpha: false,
              }}
            />
          </Suspense>
        )}
      </div>

      {/* ── Controls Sidebar (top-left overlay) ─────────────────────────────── */}
      <div className="absolute top-4 left-4 z-10 flex flex-col gap-2 max-w-xs">

        {/* Header */}
        <div className="bg-black/70 backdrop-blur rounded-xl px-4 py-3 border border-white/10">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-violet-400 text-lg font-bold">絆</span>
            <span className="text-white font-semibold text-sm">Kizuna</span>
            <span className={`ml-auto w-2 h-2 rounded-full ${status.ingesting ? 'bg-yellow-400 animate-pulse' : status.node_count > 0 ? 'bg-green-400' : 'bg-gray-600'}`} />
          </div>
          <div className="text-white/40 text-xs">
            {status.node_count} nodes · {status.edge_count} edges · {status.community_count} clusters
          </div>
        </div>

        {/* Search */}
        <form onSubmit={handleSearch}
              className="bg-black/70 backdrop-blur rounded-xl border border-white/10 overflow-hidden">
          <div className="flex">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search knowledge..."
              className="flex-1 bg-transparent text-white text-xs px-3 py-2.5 outline-none placeholder-white/30"
            />
            <button type="submit"
                    className="px-3 text-violet-400 hover:text-violet-300 transition-colors">
              ↗
            </button>
          </div>
        </form>

        {/* Actions */}
        <div className="flex gap-2">
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="flex-1 bg-violet-600/80 hover:bg-violet-500/80 backdrop-blur
                       text-white text-xs font-semibold px-3 py-2 rounded-xl
                       transition-colors disabled:opacity-50"
          >
            + Upload ZIP
          </button>
          <button
            onClick={() => { setShowGaps(!showGaps); if (!showGaps) fetchGaps() }}
            className={`px-3 py-2 rounded-xl backdrop-blur text-xs font-semibold transition-colors
                        ${showGaps ? 'bg-red-500/80 text-white' : 'bg-black/70 border border-white/10 text-white/50 hover:text-white'}`}
          >
            Gaps
          </button>
          <button
            onClick={() => fireRandomNeurons(10)}
            disabled={isEmpty}
            className="px-3 py-2 rounded-xl backdrop-blur text-xs bg-black/70 border border-white/10
                       text-white/50 hover:text-white disabled:opacity-30 transition-colors"
            title="Fire neurons"
          >
            ⚡
          </button>
        </div>

        {/* Gap list */}
        {showGaps && gaps.length > 0 && (
          <div className="bg-black/80 backdrop-blur rounded-xl border border-red-500/30 p-3 max-h-40 overflow-y-auto">
            <div className="text-red-400 text-xs font-semibold mb-2">
              {gaps.length} disconnected areas
            </div>
            {gaps.slice(0, 6).map((gap, i) => (
              <div key={i} className="text-white/50 text-xs py-1 border-b border-white/5">
                {gap.message}
              </div>
            ))}
          </div>
        )}

        <input
          ref={fileInputRef}
          type="file"
          accept=".zip"
          className="hidden"
          onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0])}
        />
      </div>

      {/* ── Node Detail Panel (right slide-in) ──────────────────────────────── */}
      {selectedNode && (
        <div className="w-80 bg-[#0c0c14]/95 backdrop-blur border-l border-white/8
                        flex flex-col overflow-hidden flex-shrink-0">

          {/* Panel header */}
          <div className="p-4 border-b border-white/8 flex items-start justify-between gap-2">
            <div>
              <div
                className="w-3 h-3 rounded-full mb-2 inline-block mr-2"
                style={{ backgroundColor: selectedNode.color }}
              />
              <span className="text-white font-semibold text-sm leading-snug">
                {selectedNode.label}
              </span>
              <div className="text-white/40 text-xs mt-1">
                {selectedNode.agent_added ? '⚡ AI-added · ' : ''}
                {selectedNode.mention_count}× mentioned ·
                {' '}importance {(selectedNode.pagerank * 1000).toFixed(1)}
              </div>
            </div>
            <button
              onClick={() => setSelectedNode(null)}
              className="text-white/30 hover:text-white/70 transition-colors text-sm flex-shrink-0"
            >
              ✕
            </button>
          </div>

          {/* Sources */}
          {selectedNode.sources?.length > 0 && (
            <div className="px-4 py-3 border-b border-white/8">
              <div className="text-white/40 text-xs font-semibold uppercase tracking-wide mb-2">
                Sources
              </div>
              <div className="flex flex-col gap-1">
                {selectedNode.sources.slice(0, 4).map((s, i) => (
                  <span key={i} className="text-violet-400/80 text-xs truncate">
                    {s.split('/').pop() || s}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Ask Kizuna about this node */}
          <div className="px-4 py-3 border-b border-white/8 flex-1 flex flex-col min-h-0">
            <div className="text-white/40 text-xs font-semibold uppercase tracking-wide mb-3">
              Ask Kizuna
            </div>
            <form onSubmit={handleNodeChat} className="flex flex-col gap-2 flex-1">
              <input
                type="text"
                value={nodeChat}
                onChange={(e) => setNodeChat(e.target.value)}
                placeholder={`Ask about "${selectedNode.label}"...`}
                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2
                           text-white text-xs placeholder-white/30 outline-none
                           focus:border-violet-500/50 transition-colors"
              />
              <button
                type="submit"
                disabled={chatLoading || !nodeChat.trim()}
                className="w-full bg-violet-600/80 hover:bg-violet-500/80 text-white text-xs
                           font-semibold py-2 rounded-lg transition-colors disabled:opacity-50"
              >
                {chatLoading ? 'Thinking...' : 'Ask →'}
              </button>
            </form>

            {chatAnswer && (
              <div className="mt-3 bg-violet-900/20 border border-violet-500/20 rounded-lg p-3
                              text-white/70 text-xs leading-relaxed overflow-y-auto max-h-48">
                <StructuredMessage text={chatAnswer} />
              </div>
            )}
          </div>

          {/* Legend */}
          <div className="px-4 py-3">
            <div className="text-white/30 text-xs font-semibold uppercase tracking-wide mb-2">
              Legend
            </div>
            <div className="flex flex-col gap-1 text-xs text-white/40">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-violet-400" />
                <span>AI-generated nodes</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full border border-white/20" />
                <span>Node size = importance</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-red-500" />
                <span>Disconnected (gap overlay)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-white" />
                <span>Firing neuron</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default BrainPage
