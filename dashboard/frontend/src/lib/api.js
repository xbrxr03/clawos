const r = (method, path, body) =>
  fetch(`/api${path}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    ...(body ? { body: JSON.stringify(body) } : {}),
  }).then(r => { if (!r.ok) throw new Error(`${method} ${path} → ${r.status}`); return r.json() })

export const api = {
  approve:     id   => r('POST',   `/approvals/${id}/approve`),
  deny:        id   => r('POST',   `/approvals/${id}/deny`),
  tasks:       ()   => r('GET',    '/tasks'),
  models:      ()   => r('GET',    '/models'),
  pullModel:   name => r('POST',   `/models/${encodeURIComponent(name)}/pull`),
  deleteModel: name => r('DELETE', `/models/${encodeURIComponent(name)}`),
  audit:       (n=200) => r('GET', `/audit?limit=${n}`),
  memory:      ()   => r('GET',    '/memory'),
  workspaces:  ()   => r('GET',    '/workspaces'),
  system:      ()   => r('GET',    '/system'),
  services:    ()   => r('GET',    '/services'),
  runtimes:    ()   => r('GET',    '/runtimes'),
  agents:      ()   => r('GET',    '/agents'),
  resetAgent:  id   => r('POST',   `/agents/${encodeURIComponent(id)}/reset`),
}
