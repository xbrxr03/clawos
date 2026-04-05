export type SetupState = {
  install_channel?: string
  platform?: string
  architecture?: string
  service_manager?: string
  detected_hardware?: { summary?: string; ram_gb?: number; gpu_name?: string; tier?: string }
  recommended_profile?: string
  selected_runtimes?: string[]
  selected_models?: string[]
  workspace?: string
  voice_enabled?: boolean
  enable_openclaw?: boolean
  launch_on_login?: boolean
  policy_mode?: string
  progress_stage?: string
  logs?: string[]
  completion_marker?: boolean
  last_error?: string
  plan_steps?: string[]
}

export type SetupPlan = {
  summary?: string
  steps?: string[]
}

export type SetupDiagnostics = {
  platform?: string
  python?: string
  service_manager?: string
  clawos_dir?: string
  logs_dir?: string
  support_dir?: string
  cwd?: string
  desktop?: DesktopPosture
}

export type DashboardHealth = {
  status?: string
  auth_required?: boolean
  host?: string
  port?: number
  local_only?: boolean
}

export type DesktopPosture = {
  platform?: string
  autostart_kind?: string
  launch_on_login_supported?: boolean
  launch_on_login_enabled?: boolean
  launch_on_login_path?: string
  command_center_command?: string
  changed_path?: string
  message?: string
  paths?: Record<string, string>
}

export type WorkflowRecord = {
  id: string
  name: string
  description: string
  category: string
  tags?: string[]
  platforms?: string[]
  destructive?: boolean
  needs_agent?: boolean
  requires?: string[]
}

export type WorkflowRunResult = {
  status?: string
  output?: string
  error?: string
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  const text = await response.text()
  let payload: any = {}
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = text
    }
  }
  if (!response.ok) {
    const detail = typeof payload === 'object' ? payload?.detail || payload?.error : payload
    throw new Error(detail || `${init?.method || 'GET'} ${path} -> ${response.status}`)
  }
  return payload as T
}

function setupHeaders(extra?: HeadersInit): HeadersInit {
  return {
    'X-ClawOS-Setup': '1',
    ...(extra || {}),
  }
}

export const commandCenterApi = {
  getHealth: () => fetchJson<DashboardHealth>('/api/health'),
  getDesktopPosture: () => fetchJson<DesktopPosture>('/api/desktop/posture'),
  setLaunchOnLogin: (enabled: boolean, command?: string) =>
    fetchJson<DesktopPosture>('/api/desktop/launch-on-login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled, command }),
    }),
  getSetupState: () => fetchJson<SetupState>('/api/setup/state', { headers: setupHeaders() }),
  getSetupDiagnostics: () => fetchJson<SetupDiagnostics>('/api/setup/diagnostics', { headers: setupHeaders() }),
  planSetup: () => fetchJson<SetupPlan>('/api/setup/plan', { method: 'POST', headers: setupHeaders() }),
  applySetup: () =>
    fetchJson<{ ok?: boolean; status?: string }>('/api/setup/apply', { method: 'POST', headers: setupHeaders() }),
  retrySetup: () =>
    fetchJson<{ ok?: boolean; status?: string }>('/api/setup/retry', { method: 'POST', headers: setupHeaders() }),
  repairSetup: () =>
    fetchJson<{ ok?: boolean; status?: string }>('/api/setup/repair', { method: 'POST', headers: setupHeaders() }),
  cancelSetup: () =>
    fetchJson<{ ok?: boolean; status?: string }>('/api/setup/cancel', { method: 'POST', headers: setupHeaders() }),
  createSupportBundle: () =>
    fetchJson<{ path?: string }>('/api/support/bundle', { method: 'POST', headers: setupHeaders() }),
  listWorkflows: (params: { category?: string; search?: string } = {}) => {
    const query = new URLSearchParams()
    if (params.category && params.category !== 'all') query.set('category', params.category)
    if (params.search) query.set('search', params.search)
    const suffix = query.toString() ? `?${query}` : ''
    return fetchJson<WorkflowRecord[]>(`/api/workflows/list${suffix}`)
  },
  runWorkflow: (id: string, body = { args: {}, workspace: 'nexus_default' }) =>
    fetchJson<WorkflowRunResult>(`/api/workflows/${id}/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
}
