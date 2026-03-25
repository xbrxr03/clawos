const BASE = '/api'

async function req(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } }
  if (body) opts.body = JSON.stringify(body)
  const r = await fetch(`${BASE}${path}`, opts)
  if (!r.ok) throw new Error(`${method} ${path} → ${r.status}`)
  return r.json()
}

export const api = {
  // Approvals
  approve: (id) => req('POST', `/approvals/${id}/approve`),
  deny:    (id) => req('POST', `/approvals/${id}/deny`),

  // Tasks
  tasks:   ()   => req('GET', '/tasks'),

  // Models
  models:  ()   => req('GET', '/models'),
  pullModel:  (name) => req('POST', `/models/${encodeURIComponent(name)}/pull`),
  deleteModel: (name) => req('DELETE', `/models/${encodeURIComponent(name)}`),

  // Audit
  audit:   (limit = 100, offset = 0) => req('GET', `/audit?limit=${limit}&offset=${offset}`),

  // Memory
  memory:  ()   => req('GET', '/memory'),

  // Workspaces
  workspaces: () => req('GET', '/workspaces'),

  // System
  system:  ()   => req('GET', '/system'),

  // Services
  services: ()  => req('GET', '/services'),
}
