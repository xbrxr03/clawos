import { useEffect, useState } from 'react'
import { Badge, Card, Empty, SectionLabel } from '../components/ui.jsx'
import { commandCenterApi } from '../lib/commandCenterApi'

type Transport = 'stdio' | 'http'

type MCPServer = {
  id: string
  name: string
  transport: Transport
  command?: string[]
  endpoint?: string
  env?: Record<string, string>
  enabled: boolean
  status: 'disconnected' | 'connected' | 'error'
  error?: string
  tools: MCPTool[]
  resources: MCPResource[]
  prompts: unknown[]
  connected_at?: string
  added_at: string
}

type MCPTool = {
  name: string
  description: string
  server_id?: string
  server_name?: string
  inputSchema?: Record<string, unknown>
  input_schema?: Record<string, unknown>
}

type MCPResource = {
  uri: string
  name: string
  description?: string
  server_id?: string
  server_name?: string
  mimeType?: string
}

type WellKnown = {
  id: string
  name: string
  description: string
  transport: Transport
  command_template: string[]
  env_required?: string[]
  category: string
}

const STATUS_COLORS: Record<string, string> = {
  connected: 'green',
  disconnected: 'gray',
  error: 'red',
}

const CATEGORY_COLORS: Record<string, string> = {
  search: 'blue',
  storage: 'orange',
  web: 'green',
  dev: 'purple',
  memory: 'blue',
  communication: 'orange',
}

function EnvList({ env }: { env?: Record<string, string> }) {
  if (!env || !Object.keys(env).length) return null
  return (
    <div style={{ marginTop: 6, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
      {Object.keys(env).map((k) => (
        <Badge key={k} color="gray">{k}</Badge>
      ))}
    </div>
  )
}

export function MCPManagerPage() {
  const [servers, setServers] = useState<MCPServer[]>([])
  const [wellKnown, setWellKnown] = useState<WellKnown[]>([])
  const [tools, setTools] = useState<MCPTool[]>([])
  const [resources, setResources] = useState<MCPResource[]>([])
  const [selectedServer, setSelectedServer] = useState<MCPServer | null>(null)
  const [activeTab, setActiveTab] = useState<'servers' | 'catalog' | 'tools' | 'call'>('servers')

  // Add server form
  const [addOpen, setAddOpen] = useState(false)
  const [addName, setAddName] = useState('')
  const [addTransport, setAddTransport] = useState<Transport>('stdio')
  const [addCommand, setAddCommand] = useState('')
  const [addEndpoint, setAddEndpoint] = useState('')
  const [addEnv, setAddEnv] = useState('')
  const [addBusy, setAddBusy] = useState(false)

  // Tool call form
  const [callServer, setCallServer] = useState('')
  const [callTool, setCallTool] = useState('')
  const [callArgs, setCallArgs] = useState('{}')
  const [callResult, setCallResult] = useState('')
  const [callBusy, setCallBusy] = useState(false)

  const [message, setMessage] = useState('')
  const [connecting, setConnecting] = useState<string | null>(null)

  const load = async () => {
    try {
      const [srv, wk] = await Promise.all([
        commandCenterApi.listMCPServers(),
        commandCenterApi.listMCPWellKnown(),
      ])
      setServers(Array.isArray(srv) ? srv : [])
      setWellKnown(Array.isArray(wk) ? wk : [])
    } catch {
      setMessage('Failed to load MCP servers')
    }
  }

  const loadToolsResources = async () => {
    try {
      const [t, r] = await Promise.all([
        commandCenterApi.listMCPTools(),
        commandCenterApi.listMCPResources(),
      ])
      setTools(Array.isArray(t) ? t : [])
      setResources(Array.isArray(r) ? r : [])
    } catch {}
  }

  useEffect(() => { load() }, [])
  useEffect(() => {
    if (activeTab === 'tools') loadToolsResources()
  }, [activeTab])

  const connect = async (id: string) => {
    setConnecting(id)
    setMessage('')
    try {
      const updated = await commandCenterApi.connectMCPServer(id)
      setServers((prev) => prev.map((s) => (s.id === id ? updated : s)))
      if (selectedServer?.id === id) setSelectedServer(updated)
      setMessage(updated.status === 'connected'
        ? `Connected to ${updated.name} — ${updated.tools.length} tools available`
        : `Failed: ${updated.error}`)
    } catch (err: any) {
      setMessage(err.message || 'Connect failed')
    } finally {
      setConnecting(null)
    }
  }

  const removeServer = async (id: string) => {
    try {
      await commandCenterApi.removeMCPServer(id)
      setServers((prev) => prev.filter((s) => s.id !== id))
      if (selectedServer?.id === id) setSelectedServer(null)
    } catch (err: any) {
      setMessage(err.message || 'Remove failed')
    }
  }

  const addServer = async () => {
    if (!addName.trim()) return
    setAddBusy(true)
    try {
      let env: Record<string, string> = {}
      if (addEnv.trim()) {
        addEnv.split('\n').forEach((line) => {
          const [k, ...v] = line.split('=')
          if (k && v.length) env[k.trim()] = v.join('=').trim()
        })
      }
      const server = await commandCenterApi.addMCPServer({
        name: addName.trim(),
        transport: addTransport,
        command: addTransport === 'stdio' ? addCommand.trim().split(/\s+/) : undefined,
        endpoint: addTransport === 'http' ? addEndpoint.trim() : undefined,
        env,
      })
      setServers((prev) => [...prev, server])
      setAddOpen(false)
      setAddName(''); setAddCommand(''); setAddEndpoint(''); setAddEnv('')
    } catch (err: any) {
      setMessage(err.message || 'Add failed')
    } finally {
      setAddBusy(false)
    }
  }

  const callToolFn = async () => {
    if (!callServer || !callTool) return
    setCallBusy(true)
    setCallResult('')
    try {
      let args = {}
      try { args = JSON.parse(callArgs) } catch { args = {} }
      const result = await commandCenterApi.callMCPTool(callServer, callTool, args)
      setCallResult(JSON.stringify(result, null, 2))
    } catch (err: any) {
      setCallResult(`Error: ${err.message}`)
    } finally {
      setCallBusy(false)
    }
  }

  const installWellKnown = (wk: WellKnown) => {
    setAddOpen(true)
    setAddName(wk.name)
    setAddTransport(wk.transport)
    setAddCommand(wk.command_template.join(' '))
    setActiveTab('servers')
  }

  const tabs = ['servers', 'catalog', 'tools', 'call'] as const

  return (
    <div className="fade-up" style={{ padding: '0 0 48px' }}>
      <div style={{ padding: '32px 24px 18px' }}>
        <div style={{ fontSize: 28, fontWeight: 700, letterSpacing: '-0.05em' }}>MCP Manager</div>
        <div style={{ fontSize: 14, color: 'var(--text-3)', marginTop: 6, maxWidth: 720 }}>
          Model Context Protocol server registry — connect, inspect tools, relay calls to local agents.
        </div>
      </div>

      {/* Tabs */}
      <div style={{ padding: '0 24px 12px', display: 'flex', gap: 4 }}>
        {tabs.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setActiveTab(t)}
            style={{
              padding: '7px 16px',
              borderRadius: 10,
              border: '1px solid',
              borderColor: activeTab === t ? 'rgba(77,143,247,0.35)' : 'var(--border)',
              background: activeTab === t ? 'rgba(77,143,247,0.12)' : 'transparent',
              color: activeTab === t ? 'var(--blue)' : 'var(--text-2)',
              fontWeight: activeTab === t ? 600 : 400,
              cursor: 'pointer',
              fontSize: 13,
              textTransform: 'capitalize',
            }}
          >
            {t === 'call' ? 'Call Tool' : t.charAt(0).toUpperCase() + t.slice(1)}
            {t === 'servers' && servers.length > 0 && (
              <span style={{ marginLeft: 6, color: 'var(--text-3)', fontWeight: 400, fontSize: 11 }}>
                {servers.filter((s) => s.status === 'connected').length}/{servers.length}
              </span>
            )}
            {t === 'tools' && tools.length > 0 && (
              <span style={{ marginLeft: 6, color: 'var(--text-3)', fontWeight: 400, fontSize: 11 }}>{tools.length}</span>
            )}
          </button>
        ))}
      </div>

      {message && (
        <div style={{ padding: '0 24px 10px' }}>
          <div className="glass" style={{ padding: '10px 14px', fontSize: 13, color: 'var(--text-2)' }}>{message}</div>
        </div>
      )}

      {/* Servers tab */}
      {activeTab === 'servers' && (
        <div style={{ padding: '0 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button className="btn primary" onClick={() => setAddOpen((v) => !v)}>
              {addOpen ? 'Cancel' : '+ Add Server'}
            </button>
          </div>

          {addOpen && (
            <Card style={{ padding: 18 }}>
              <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Add MCP Server</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <div>
                  <SectionLabel>Name</SectionLabel>
                  <input
                    value={addName} onChange={(e) => setAddName(e.target.value)}
                    placeholder="My MCP Server"
                    style={{ width: '100%', padding: '7px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text)', fontSize: 13 }}
                  />
                </div>
                <div>
                  <SectionLabel>Transport</SectionLabel>
                  <select
                    value={addTransport} onChange={(e) => setAddTransport(e.target.value as Transport)}
                    style={{ width: '100%', padding: '7px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text)', fontSize: 13 }}
                  >
                    <option value="stdio">stdio (subprocess)</option>
                    <option value="http">HTTP endpoint</option>
                  </select>
                </div>
                {addTransport === 'stdio' && (
                  <div style={{ gridColumn: '1 / -1' }}>
                    <SectionLabel>Command</SectionLabel>
                    <input
                      value={addCommand} onChange={(e) => setAddCommand(e.target.value)}
                      placeholder="npx -y @modelcontextprotocol/server-filesystem /path"
                      style={{ width: '100%', padding: '7px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text)', fontSize: 12, fontFamily: 'var(--font-mono)' }}
                    />
                  </div>
                )}
                {addTransport === 'http' && (
                  <div style={{ gridColumn: '1 / -1' }}>
                    <SectionLabel>Endpoint URL</SectionLabel>
                    <input
                      value={addEndpoint} onChange={(e) => setAddEndpoint(e.target.value)}
                      placeholder="http://localhost:3000/mcp"
                      style={{ width: '100%', padding: '7px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text)', fontSize: 12, fontFamily: 'var(--font-mono)' }}
                    />
                  </div>
                )}
                <div style={{ gridColumn: '1 / -1' }}>
                  <SectionLabel>Environment variables (KEY=value, one per line)</SectionLabel>
                  <textarea
                    value={addEnv} onChange={(e) => setAddEnv(e.target.value)}
                    rows={3} placeholder="BRAVE_API_KEY=sk-..."
                    style={{ width: '100%', padding: '7px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text)', fontSize: 12, fontFamily: 'var(--font-mono)', resize: 'vertical' }}
                  />
                </div>
              </div>
              <button className="btn primary" style={{ marginTop: 10 }} onClick={addServer} disabled={addBusy}>
                {addBusy ? 'Adding…' : 'Add Server'}
              </button>
            </Card>
          )}

          {servers.length === 0 ? (
            <Card style={{ padding: 18 }}><Empty>No MCP servers configured. Add one above or install from the Catalog tab.</Empty></Card>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              {servers.map((server) => (
                <Card
                  key={server.id}
                  style={{ padding: 16, cursor: 'pointer', borderColor: selectedServer?.id === server.id ? 'rgba(77,143,247,0.3)' : undefined }}
                  onClick={() => setSelectedServer(selectedServer?.id === server.id ? null : server)}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 15, fontWeight: 600 }}>{server.name}</div>
                      <div style={{ marginTop: 6, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        <Badge color={STATUS_COLORS[server.status] || 'gray'}>{server.status}</Badge>
                        <Badge color="gray">{server.transport}</Badge>
                        {server.tools.length > 0 && <Badge color="blue">{server.tools.length} tools</Badge>}
                        {server.resources.length > 0 && <Badge color="orange">{server.resources.length} resources</Badge>}
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 6 }} onClick={(e) => e.stopPropagation()}>
                      <button
                        className="btn primary sm"
                        disabled={connecting === server.id}
                        onClick={() => connect(server.id)}
                      >
                        {connecting === server.id ? '…' : server.status === 'connected' ? 'Refresh' : 'Connect'}
                      </button>
                      <button className="btn sm" onClick={() => removeServer(server.id)} style={{ color: 'var(--red)' }}>
                        Remove
                      </button>
                    </div>
                  </div>

                  {server.status === 'error' && server.error && (
                    <div style={{ marginTop: 8, fontSize: 12, color: 'var(--red)' }}>{server.error}</div>
                  )}

                  {selectedServer?.id === server.id && server.tools.length > 0 && (
                    <div style={{ marginTop: 12 }}>
                      <SectionLabel>Tools</SectionLabel>
                      <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginTop: 4 }}>
                        {server.tools.map((t) => (
                          <button
                            key={t.name}
                            type="button"
                            className="pill gray"
                            style={{ cursor: 'pointer' }}
                            onClick={(e) => { e.stopPropagation(); setCallServer(server.id); setCallTool(t.name); setActiveTab('call') }}
                          >
                            {t.name}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Catalog tab */}
      {activeTab === 'catalog' && (
        <div style={{ padding: '0 20px', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 10 }}>
          {wellKnown.map((wk) => (
            <Card key={wk.id} style={{ padding: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                <div>
                  <div style={{ fontSize: 15, fontWeight: 600 }}>{wk.name}</div>
                  <div style={{ marginTop: 6, display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                    <Badge color={CATEGORY_COLORS[wk.category] || 'gray'}>{wk.category}</Badge>
                    <Badge color="gray">{wk.transport}</Badge>
                  </div>
                </div>
                <button className="btn sm" onClick={() => installWellKnown(wk)}>Add</button>
              </div>
              <div style={{ marginTop: 8, fontSize: 13, color: 'var(--text-2)', lineHeight: 1.5 }}>{wk.description}</div>
              {wk.env_required && wk.env_required.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 4 }}>Requires env:</div>
                  <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    {wk.env_required.map((e) => <Badge key={e} color="orange">{e}</Badge>)}
                  </div>
                </div>
              )}
              <div className="mono" style={{ marginTop: 8, fontSize: 10, color: 'var(--text-3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {wk.command_template.join(' ')}
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Tools tab */}
      {activeTab === 'tools' && (
        <div style={{ padding: '0 20px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          <Card style={{ padding: 18 }}>
            <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Tools <Badge color="blue">{tools.length}</Badge></div>
            {tools.length === 0 ? (
              <Empty>Connect servers to see available tools.</Empty>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {tools.map((t) => (
                  <div key={`${t.server_id}-${t.name}`} className="glass" style={{ padding: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                      <div className="mono" style={{ fontSize: 13, fontWeight: 600 }}>{t.name}</div>
                      <Badge color="gray">{t.server_name}</Badge>
                    </div>
                    <div style={{ marginTop: 4, fontSize: 12, color: 'var(--text-2)' }}>{t.description}</div>
                    <button
                      className="btn sm"
                      style={{ marginTop: 8 }}
                      onClick={() => { setCallServer(t.server_id || ''); setCallTool(t.name); setActiveTab('call') }}
                    >
                      Call tool
                    </button>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card style={{ padding: 18 }}>
            <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Resources <Badge color="orange">{resources.length}</Badge></div>
            {resources.length === 0 ? (
              <Empty>Connect servers with resource support to see them here.</Empty>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {resources.map((r) => (
                  <div key={`${r.server_id}-${r.uri}`} className="glass" style={{ padding: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                      <div style={{ fontSize: 13, fontWeight: 600 }}>{r.name}</div>
                      <Badge color="gray">{r.server_name}</Badge>
                    </div>
                    <div className="mono" style={{ marginTop: 4, fontSize: 11, color: 'var(--text-3)' }}>{r.uri}</div>
                    {r.description && <div style={{ marginTop: 4, fontSize: 12, color: 'var(--text-2)' }}>{r.description}</div>}
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}

      {/* Call tool tab */}
      {activeTab === 'call' && (
        <div style={{ padding: '0 20px' }}>
          <Card style={{ padding: 18, maxWidth: 680 }}>
            <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 14 }}>Call a Tool</div>
            <div style={{ display: 'grid', gap: 10 }}>
              <div>
                <SectionLabel>Server</SectionLabel>
                <select
                  value={callServer}
                  onChange={(e) => setCallServer(e.target.value)}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text)', fontSize: 13 }}
                >
                  <option value="">Select server…</option>
                  {servers.filter((s) => s.status === 'connected').map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <SectionLabel>Tool</SectionLabel>
                <select
                  value={callTool}
                  onChange={(e) => setCallTool(e.target.value)}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text)', fontSize: 13 }}
                >
                  <option value="">Select tool…</option>
                  {(servers.find((s) => s.id === callServer)?.tools || []).map((t) => (
                    <option key={t.name} value={t.name}>{t.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <SectionLabel>Arguments (JSON)</SectionLabel>
                <textarea
                  value={callArgs}
                  onChange={(e) => setCallArgs(e.target.value)}
                  rows={5}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text)', fontSize: 12, fontFamily: 'var(--font-mono)', resize: 'vertical' }}
                />
              </div>
              <button className="btn primary" onClick={callToolFn} disabled={callBusy || !callServer || !callTool}>
                {callBusy ? 'Calling…' : 'Call Tool'}
              </button>
              {callResult && (
                <div>
                  <SectionLabel>Result</SectionLabel>
                  <pre style={{ margin: 0, padding: '10px 12px', borderRadius: 10, background: 'var(--surface)', border: '1px solid var(--border)', fontSize: 12, fontFamily: 'var(--font-mono)', whiteSpace: 'pre-wrap', color: 'var(--text-2)', maxHeight: 320, overflow: 'auto' }}>
                    {callResult}
                  </pre>
                </div>
              )}
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}
