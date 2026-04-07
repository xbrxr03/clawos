/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { useCallback, useEffect, useRef, useState } from 'react'
import { Badge, Card, Empty, SectionLabel } from '../components/ui.jsx'
import { commandCenterApi } from '../lib/commandCenterApi'

// ── Node types ────────────────────────────────────────────────────────────────
type NodeKind = 'trigger' | 'step' | 'approval' | 'tool' | 'output'

const NODE_COLORS: Record<NodeKind, string> = {
  trigger: '#4d8ff7',
  step: '#58d2d4',
  approval: '#f59e0b',
  tool: '#a78bfa',
  output: '#34d399',
}

const NODE_LABELS: Record<NodeKind, string> = {
  trigger: 'Trigger',
  step: 'Step',
  approval: 'Approval',
  tool: 'Tool',
  output: 'Output',
}

const NODE_W = 160
const NODE_H = 56

type GraphNode = {
  id: string
  kind: NodeKind
  label: string
  x: number
  y: number
}

type GraphEdge = {
  id: string
  from: string
  to: string
}

type Program = {
  id: string
  name: string
  pack_id: string
  summary: string
  checkpoints: string[]
  approval_points: string[]
  triggers: string[]
  nodes?: GraphNode[]
  edges?: GraphEdge[]
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function uid() {
  return Math.random().toString(36).slice(2, 10)
}

function nodeCenterX(node: GraphNode) { return node.x + NODE_W / 2 }
function nodeCenterY(node: GraphNode) { return node.y + NODE_H / 2 }

function programToGraph(program: Program): { nodes: GraphNode[]; edges: GraphEdge[] } {
  if (program.nodes && program.edges) return { nodes: program.nodes, edges: program.edges }
  const nodes: GraphNode[] = []
  const edges: GraphEdge[] = []
  let x = 60, y = 60

  program.triggers.forEach((t) => {
    nodes.push({ id: uid(), kind: 'trigger', label: t, x, y })
    y += 90
  })
  const triggerIds = nodes.map((n) => n.id)
  x = 280; y = 60

  program.checkpoints.forEach((c, i) => {
    const id = uid()
    nodes.push({ id, kind: 'step', label: c, x, y })
    if (i === 0) triggerIds.forEach((tid) => edges.push({ id: uid(), from: tid, to: id }))
    else {
      const prev = nodes[nodes.length - 2]
      edges.push({ id: uid(), from: prev.id, to: id })
    }
    y += 90
  })
  x = 500; y = 60

  program.approval_points.forEach((a, i) => {
    const id = uid()
    nodes.push({ id, kind: 'approval', label: a, x, y })
    const lastStep = nodes.filter((n) => n.kind === 'step').pop()
    if (lastStep) edges.push({ id: uid(), from: lastStep.id, to: id })
    y += 90
  })

  // Output node
  const outId = uid()
  nodes.push({ id: outId, kind: 'output', label: 'Result', x: x + 220, y: 60 })
  const lastNonOutput = nodes.slice(0, -1).pop()
  if (lastNonOutput) edges.push({ id: uid(), from: lastNonOutput.id, to: outId })

  return { nodes, edges }
}

// ── Canvas ────────────────────────────────────────────────────────────────────
function GraphCanvas({
  nodes,
  edges,
  selected,
  onSelect,
  onNodeMove,
  onConnect,
  onDeleteNode,
}: {
  nodes: GraphNode[]
  edges: GraphEdge[]
  selected: string | null
  onSelect: (id: string | null) => void
  onNodeMove: (id: string, x: number, y: number) => void
  onConnect: (fromId: string, toId: string) => void
  onDeleteNode: (id: string) => void
}) {
  const svgRef = useRef<SVGSVGElement>(null)
  const dragging = useRef<{ id: string; ox: number; oy: number } | null>(null)
  const connecting = useRef<string | null>(null)
  const [connLine, setConnLine] = useState<{ x1: number; y1: number; x2: number; y2: number } | null>(null)

  const getNodeById = (id: string) => nodes.find((n) => n.id === id)

  const svgPoint = (e: React.MouseEvent) => {
    const svg = svgRef.current!
    const rect = svg.getBoundingClientRect()
    return { x: e.clientX - rect.left, y: e.clientY - rect.top }
  }

  const onMouseDown = (e: React.MouseEvent, nodeId: string) => {
    e.stopPropagation()
    const node = getNodeById(nodeId)!
    const pt = svgPoint(e)
    if (e.altKey) {
      // Start connection
      connecting.current = nodeId
      setConnLine({ x1: nodeCenterX(node), y1: nodeCenterY(node), x2: pt.x, y2: pt.y })
    } else {
      dragging.current = { id: nodeId, ox: pt.x - node.x, oy: pt.y - node.y }
      onSelect(nodeId)
    }
  }

  const onMouseMove = (e: React.MouseEvent) => {
    const pt = svgPoint(e)
    if (dragging.current) {
      onNodeMove(dragging.current.id, pt.x - dragging.current.ox, pt.y - dragging.current.oy)
    }
    if (connecting.current) {
      const node = getNodeById(connecting.current)!
      setConnLine({ x1: nodeCenterX(node), y1: nodeCenterY(node), x2: pt.x, y2: pt.y })
    }
  }

  const onMouseUp = (e: React.MouseEvent, targetId?: string) => {
    if (connecting.current && targetId && targetId !== connecting.current) {
      onConnect(connecting.current, targetId)
    }
    dragging.current = null
    connecting.current = null
    setConnLine(null)
  }

  const onSVGMouseUp = (e: React.MouseEvent) => {
    onMouseUp(e)
    if (!dragging.current && !connecting.current) onSelect(null)
  }

  return (
    <svg
      ref={svgRef}
      style={{ width: '100%', height: '100%', userSelect: 'none', cursor: 'default' }}
      onMouseMove={onMouseMove}
      onMouseUp={onSVGMouseUp}
    >
      <defs>
        <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">
          <path d="M0,0 L0,6 L8,3 z" fill="rgba(255,255,255,0.25)" />
        </marker>
      </defs>

      {/* Edges */}
      {edges.map((edge) => {
        const from = getNodeById(edge.from)
        const to = getNodeById(edge.to)
        if (!from || !to) return null
        return (
          <line
            key={edge.id}
            x1={nodeCenterX(from)} y1={nodeCenterY(from)}
            x2={nodeCenterX(to)} y2={nodeCenterY(to)}
            stroke="rgba(255,255,255,0.18)"
            strokeWidth={1.5}
            markerEnd="url(#arrow)"
          />
        )
      })}

      {/* Connection preview */}
      {connLine && (
        <line
          x1={connLine.x1} y1={connLine.y1} x2={connLine.x2} y2={connLine.y2}
          stroke="rgba(77,143,247,0.6)" strokeWidth={1.5} strokeDasharray="5,3"
        />
      )}

      {/* Nodes */}
      {nodes.map((node) => {
        const isSelected = node.id === selected
        const color = NODE_COLORS[node.kind]
        return (
          <g
            key={node.id}
            onMouseDown={(e) => onMouseDown(e, node.id)}
            onMouseUp={(e) => { e.stopPropagation(); onMouseUp(e, node.id) }}
            style={{ cursor: 'grab' }}
          >
            <rect
              x={node.x} y={node.y}
              width={NODE_W} height={NODE_H}
              rx={12}
              fill={isSelected ? `${color}33` : 'rgba(14,20,32,0.9)'}
              stroke={isSelected ? color : 'rgba(255,255,255,0.12)'}
              strokeWidth={isSelected ? 1.5 : 1}
            />
            {/* Kind label */}
            <text
              x={node.x + 12} y={node.y + 18}
              fill={color}
              fontSize={9}
              fontFamily="monospace"
              textAnchor="start"
            >
              {NODE_LABELS[node.kind]}
            </text>
            {/* Node label */}
            <text
              x={node.x + NODE_W / 2} y={node.y + NODE_H / 2 + 5}
              fill="rgba(255,255,255,0.88)"
              fontSize={12}
              fontWeight={500}
              fontFamily="system-ui, sans-serif"
              textAnchor="middle"
            >
              {node.label.length > 18 ? node.label.slice(0, 16) + '…' : node.label}
            </text>
            {/* Delete button on selected */}
            {isSelected && (
              <g onClick={(e) => { e.stopPropagation(); onDeleteNode(node.id) }} style={{ cursor: 'pointer' }}>
                <circle cx={node.x + NODE_W - 10} cy={node.y + 10} r={8} fill="rgba(239,68,68,0.8)" />
                <text x={node.x + NODE_W - 10} y={node.y + 14} textAnchor="middle" fill="white" fontSize={10}>×</text>
              </g>
            )}
          </g>
        )
      })}
    </svg>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export function StudioPage() {
  const [programs, setPrograms] = useState<Program[]>([])
  const [active, setActive] = useState<Program | null>(null)
  const [nodes, setNodes] = useState<GraphNode[]>([])
  const [edges, setEdges] = useState<GraphEdge[]>([])
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  // New program form
  const [newName, setNewName] = useState('')
  const [newPackId, setNewPackId] = useState('')
  const [newSummary, setNewSummary] = useState('')

  const load = async () => {
    try {
      const data = await commandCenterApi.listStudioPrograms()
      setPrograms(Array.isArray(data) ? data as Program[] : [])
    } catch { setMessage('Failed to load programs') }
  }

  useEffect(() => { load() }, [])

  const openProgram = (program: Program) => {
    const { nodes: n, edges: e } = programToGraph(program)
    setActive(program)
    setNodes(n)
    setEdges(e)
    setSelectedNode(null)
    setMessage('')
  }

  const saveProgram = async () => {
    if (!active) return
    setBusy(true)
    try {
      const payload: Program = {
        ...active,
        nodes,
        edges,
        checkpoints: nodes.filter((n) => n.kind === 'step').map((n) => n.label),
        approval_points: nodes.filter((n) => n.kind === 'approval').map((n) => n.label),
        triggers: nodes.filter((n) => n.kind === 'trigger').map((n) => n.label),
      }
      await commandCenterApi.saveStudioProgram(payload)
      setPrograms((prev) => {
        const exists = prev.find((p) => p.id === payload.id)
        return exists ? prev.map((p) => (p.id === payload.id ? payload : p)) : [...prev, payload]
      })
      setActive(payload)
      setMessage('Saved.')
    } catch (err: any) {
      setMessage(err.message || 'Save failed')
    } finally {
      setBusy(false)
    }
  }

  const deployProgram = async () => {
    if (!active) return
    setBusy(true)
    try {
      await saveProgram()
      const result = await commandCenterApi.deployStudioProgram(active.id) as any
      setMessage(`Deployed — task ${result.task_id}`)
    } catch (err: any) {
      setMessage(err.message || 'Deploy failed')
    } finally {
      setBusy(false)
    }
  }

  const deleteProgram = async (id: string) => {
    try {
      await commandCenterApi.deleteStudioProgram(id)
      setPrograms((prev) => prev.filter((p) => p.id !== id))
      if (active?.id === id) { setActive(null); setNodes([]); setEdges([]) }
    } catch (err: any) {
      setMessage(err.message || 'Delete failed')
    }
  }

  const createProgram = () => {
    if (!newName.trim()) return
    const prog: Program = {
      id: `user-${uid()}`,
      name: newName.trim(),
      pack_id: newPackId.trim() || 'custom',
      summary: newSummary.trim(),
      checkpoints: [],
      approval_points: [],
      triggers: ['manual'],
      nodes: [],
      edges: [],
    }
    const { nodes: n, edges: e } = programToGraph({ ...prog, triggers: ['manual'] })
    setActive(prog)
    setNodes(n)
    setEdges(e)
    setNewName(''); setNewPackId(''); setNewSummary('')
    setMessage('')
  }

  const addNode = (kind: NodeKind) => {
    const label = kind === 'trigger' ? 'New Trigger'
      : kind === 'step' ? 'New Step'
      : kind === 'approval' ? 'New Approval'
      : kind === 'tool' ? 'New Tool'
      : 'Output'
    setNodes((prev) => [...prev, { id: uid(), kind, label, x: 80 + prev.length * 30, y: 80 + prev.length * 20 }])
  }

  const updateNodeLabel = (id: string, label: string) => {
    setNodes((prev) => prev.map((n) => (n.id === id ? { ...n, label } : n)))
  }

  const deleteNode = useCallback((id: string) => {
    setNodes((prev) => prev.filter((n) => n.id !== id))
    setEdges((prev) => prev.filter((e) => e.from !== id && e.to !== id))
    setSelectedNode(null)
  }, [])

  const selectedNodeData = nodes.find((n) => n.id === selectedNode) || null

  return (
    <div className="fade-up" style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* Left sidebar */}
      <div style={{ width: 240, flexShrink: 0, borderRight: '1px solid var(--sep)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: '16px 14px 10px', borderBottom: '1px solid var(--sep)' }}>
          <div style={{ fontSize: 18, fontWeight: 700, letterSpacing: '-0.04em' }}>Pack Studio</div>
          <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 3 }}>Visual workflow builder</div>
        </div>

        {/* New program */}
        <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--sep)', display: 'flex', flexDirection: 'column', gap: 6 }}>
          <input
            value={newName} onChange={(e) => setNewName(e.target.value)}
            placeholder="Program name"
            style={{ padding: '6px 8px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text)', fontSize: 12 }}
          />
          <input
            value={newPackId} onChange={(e) => setNewPackId(e.target.value)}
            placeholder="Pack ID (optional)"
            style={{ padding: '6px 8px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text)', fontSize: 12 }}
          />
          <button className="btn primary" onClick={createProgram} disabled={!newName.trim()}>New Program</button>
        </div>

        {/* Program list */}
        <div style={{ flex: 1, overflow: 'auto', padding: 8, display: 'flex', flexDirection: 'column', gap: 5 }}>
          {programs.length === 0 ? (
            <div style={{ padding: 12, fontSize: 12, color: 'var(--text-3)' }}>No programs yet.</div>
          ) : programs.map((prog) => (
            <div
              key={prog.id}
              className="glass"
              style={{ padding: '9px 10px', cursor: 'pointer', borderColor: active?.id === prog.id ? 'rgba(77,143,247,0.3)' : undefined, background: active?.id === prog.id ? 'rgba(77,143,247,0.06)' : undefined }}
              onClick={() => openProgram(prog)}
            >
              <div style={{ fontSize: 12, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{prog.name}</div>
              <div style={{ marginTop: 3, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                <Badge color="gray">{prog.pack_id}</Badge>
                {prog.checkpoints.length > 0 && <Badge color="blue">{prog.checkpoints.length} steps</Badge>}
              </div>
              <button
                className="btn sm"
                style={{ marginTop: 6, color: 'var(--red)', fontSize: 10 }}
                onClick={(e) => { e.stopPropagation(); deleteProgram(prog.id) }}
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Canvas */}
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {active ? (
          <>
            {/* Canvas toolbar */}
            <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--sep)', display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <div style={{ fontSize: 14, fontWeight: 600, marginRight: 4 }}>{active.name}</div>
              {(['trigger', 'step', 'approval', 'tool', 'output'] as NodeKind[]).map((kind) => (
                <button
                  key={kind}
                  type="button"
                  onClick={() => addNode(kind)}
                  style={{
                    padding: '4px 10px',
                    borderRadius: 8,
                    border: `1px solid ${NODE_COLORS[kind]}44`,
                    background: `${NODE_COLORS[kind]}18`,
                    color: NODE_COLORS[kind],
                    cursor: 'pointer',
                    fontSize: 11,
                    fontWeight: 500,
                  }}
                >
                  + {NODE_LABELS[kind]}
                </button>
              ))}
              <div style={{ flex: 1 }} />
              <div style={{ fontSize: 11, color: 'var(--text-3)' }}>Alt+drag to connect nodes</div>
              <button className="btn" onClick={saveProgram} disabled={busy}>Save</button>
              <button className="btn primary" onClick={deployProgram} disabled={busy}>Deploy</button>
            </div>

            {message && (
              <div style={{ padding: '6px 14px', fontSize: 12, color: 'var(--text-2)', borderBottom: '1px solid var(--sep)', background: 'var(--surface)' }}>
                {message}
              </div>
            )}

            {/* Canvas + inspector split */}
            <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
              <div style={{ flex: 1, overflow: 'hidden', background: 'rgba(8,12,20,0.6)' }}>
                <GraphCanvas
                  nodes={nodes}
                  edges={edges}
                  selected={selectedNode}
                  onSelect={setSelectedNode}
                  onNodeMove={(id, x, y) => setNodes((prev) => prev.map((n) => (n.id === id ? { ...n, x, y } : n)))}
                  onConnect={(from, to) => setEdges((prev) => [...prev.filter((e) => !(e.from === from && e.to === to)), { id: uid(), from, to }])}
                  onDeleteNode={deleteNode}
                />
              </div>

              {/* Node inspector */}
              <div style={{ width: 220, flexShrink: 0, borderLeft: '1px solid var(--sep)', padding: 12, overflow: 'auto' }}>
                {selectedNodeData ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>Node editor</div>
                    <div>
                      <SectionLabel>Kind</SectionLabel>
                      <Badge color="gray">{NODE_LABELS[selectedNodeData.kind]}</Badge>
                    </div>
                    <div>
                      <SectionLabel>Label</SectionLabel>
                      <input
                        value={selectedNodeData.label}
                        onChange={(e) => updateNodeLabel(selectedNodeData.id, e.target.value)}
                        style={{ width: '100%', padding: '6px 8px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text)', fontSize: 12 }}
                      />
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-3)' }}>
                      Edges: {edges.filter((e) => e.from === selectedNodeData.id || e.to === selectedNodeData.id).length}
                    </div>
                    <button className="btn sm" style={{ color: 'var(--red)' }} onClick={() => deleteNode(selectedNodeData.id)}>Delete node</button>
                  </div>
                ) : (
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>Canvas</div>
                    <div style={{ fontSize: 12, color: 'var(--text-3)', lineHeight: 1.6 }}>
                      Click a node to edit it.<br />
                      Alt+drag from a node to connect.<br />
                      Use toolbar to add new nodes.
                    </div>
                    <div style={{ marginTop: 12 }}>
                      <SectionLabel>Nodes</SectionLabel>
                      <div style={{ fontSize: 12, color: 'var(--text-2)', marginTop: 4 }}>{nodes.length} nodes, {edges.length} edges</div>
                    </div>
                    {(['trigger', 'step', 'approval', 'tool', 'output'] as NodeKind[]).map((kind) => {
                      const count = nodes.filter((n) => n.kind === kind).length
                      return count > 0 ? (
                        <div key={kind} style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
                          <span style={{ fontSize: 12, color: NODE_COLORS[kind] }}>{NODE_LABELS[kind]}</span>
                          <Badge color="gray">{count}</Badge>
                        </div>
                      ) : null
                    })}
                  </div>
                )}
              </div>
            </div>
          </>
        ) : (
          <div style={{ flex: 1, display: 'grid', placeItems: 'center' }}>
            <Empty>Select a program from the list or create a new one to start building.</Empty>
          </div>
        )}
      </div>
    </div>
  )
}
