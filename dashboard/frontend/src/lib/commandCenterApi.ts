export type SetupState = {
  install_channel?: string
  platform?: string
  architecture?: string
  service_manager?: string
  detected_hardware?: { summary?: string; ram_gb?: number; gpu_name?: string; tier?: string }
  recommended_profile?: string
  selected_runtimes?: string[]
  selected_models?: string[]
  selected_provider_profile?: string
  primary_pack?: string
  secondary_packs?: string[]
  installed_extensions?: string[]
  workspace?: string
  assistant_identity?: string
  presence_profile?: PresenceProfile
  autonomy_policy?: AutonomyPolicy
  quiet_hours?: Record<string, string>
  primary_goals?: string[]
  voice_mode?: string
  briefing_enabled?: boolean
  voice_enabled?: boolean
  enable_openclaw?: boolean
  launch_on_login?: boolean
  policy_mode?: string
  progress_stage?: string
  logs?: string[]
  completion_marker?: boolean
  last_error?: string
  plan_steps?: string[]
  imported_openclaw?: Record<string, unknown>
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

export type UseCasePack = {
  id: string
  name: string
  category: string
  description: string
  wave?: string
  setup_summary?: string
  dashboards?: string[]
  default_workflows?: string[]
  extension_recommendations?: string[]
  provider_recommendations?: string[]
  policy_pack?: string
  eval_suite_id?: string
  installed?: boolean
  primary?: boolean
  secondary?: boolean
}

export type ProviderProfile = {
  id: string
  name: string
  kind: string
  endpoint: string
  auth_mode: string
  default_model: string
  fallback_order?: string[]
  local_only?: boolean
  privacy_posture?: string
  cost_posture?: string
  auth_env?: string
  selected?: boolean
  status?: string
  detail?: string
}

export type ExtensionManifest = {
  id: string
  name: string
  category: string
  description: string
  trust_tier?: string
  permissions?: string[]
  network_access?: string
  supported_platforms?: string[]
  packs?: string[]
  requires_secrets?: string[]
  self_hostable?: boolean
  installed?: boolean
  recommended_for_primary?: boolean
}

export type TraceRecord = {
  id: string
  title: string
  category: string
  status: string
  provider?: string
  pack_id?: string
  citations?: number
  approvals?: number
  tools?: string[]
  metadata?: Record<string, unknown>
  started_at?: string
  finished_at?: string
}

export type EvalSuite = {
  id: string
  name: string
  pack_id: string
  description: string
  checks?: string[]
  status?: string
  active?: boolean
}

export type PresenceProfile = {
  assistant_identity?: string
  tone?: string
  verbosity?: string
  interruption_threshold?: string
  notification_style?: string
  follow_up_behavior?: string
  presence_level?: string
  preferred_voice_mode?: string
}

export type AutonomyPolicy = {
  mode?: string
  automatic_lanes?: string[]
  trusted_lanes?: string[]
  approval_required?: string[]
  quiet_hours?: Record<string, string>
  escalation_rule?: string
}

export type AttentionEvent = {
  id?: string
  title?: string
  summary?: string
  urgency?: string
  surface?: string
  category?: string
  timestamp?: string
  acknowledged?: boolean
}

export type Briefing = {
  id?: string
  title?: string
  headline?: string
  summary?: string
  items?: Array<{ title?: string; body?: string; priority?: string }>
  generated_at?: string
}

export type Mission = {
  id?: string
  title?: string
  summary?: string
  status?: string
  checkpoint?: string
  blocked?: boolean
  trust_lane?: string
  next_action?: string
  updated_at?: string
}

export type VoiceSession = {
  mode?: string
  state?: string
  follow_up_open?: boolean
  device_label?: string
  last_utterance?: string
  last_response?: string
  updated_at?: string
}

export type PresencePayload = {
  profile?: PresenceProfile
  autonomy_policy?: AutonomyPolicy
  voice_session?: VoiceSession
}

export type OpenClawImportManifest = {
  source_path?: string
  config_path?: string
  detected_version?: string
  channels?: string[]
  providers?: string[]
  skills?: string[]
  env_summary?: Record<string, unknown>
  migration_actions?: string[]
  blockers?: string[]
  warnings?: string[]
  suggested_primary_pack?: string
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

function maybeSetupHeaders(extra?: HeadersInit): HeadersInit | undefined {
  if (typeof window !== 'undefined' && window.location.pathname.startsWith('/setup')) {
    return setupHeaders(extra)
  }
  return extra
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
  inspectSetup: () =>
    fetchJson<{ state?: SetupState; openclaw?: OpenClawImportManifest }>('/api/setup/inspect', {
      method: 'POST',
      headers: setupHeaders(),
    }),
  getSetupDiagnostics: () => fetchJson<SetupDiagnostics>('/api/setup/diagnostics', { headers: setupHeaders() }),
  selectSetupPack: (pack_id: string, secondary_packs: string[] = [], provider_profile = '') =>
    fetchJson<SetupState>('/api/setup/select-pack', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...setupHeaders() },
      body: JSON.stringify({ pack_id, secondary_packs, provider_profile }),
    }),
  importOpenClaw: (source_path = '') =>
    fetchJson<OpenClawImportManifest>('/api/setup/import/openclaw', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...setupHeaders() },
      body: JSON.stringify({ source_path }),
    }),
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
  getPresence: () => fetchJson<PresencePayload>('/api/presence', { headers: maybeSetupHeaders() }),
  updatePresence: (body: Record<string, unknown>) =>
    fetchJson<PresencePayload>('/api/presence', {
      method: 'POST',
      headers: maybeSetupHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(body),
    }),
  listAttention: () => fetchJson<AttentionEvent[]>('/api/attention'),
  getTodayBriefing: () => fetchJson<Briefing>('/api/briefings/today'),
  listMissions: () => fetchJson<Mission[]>('/api/missions'),
  startMission: (title: string, summary = '', trust_lane = 'trusted-automatic') =>
    fetchJson<{ ok?: boolean; mission?: Mission }>('/api/missions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, summary, trust_lane }),
    }),
  getVoiceSession: () => fetchJson<VoiceSession>('/api/voice/session'),
  setVoiceMode: (mode: string) =>
    fetchJson<VoiceSession>('/api/voice/mode', {
      method: 'POST',
      headers: maybeSetupHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ mode }),
    }),
  updateSetupPresence: (body: Record<string, unknown>) =>
    fetchJson<SetupState>('/api/setup/presence', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...setupHeaders() },
      body: JSON.stringify(body),
    }),
  updateSetupAutonomy: (body: Record<string, unknown>) =>
    fetchJson<SetupState>('/api/setup/autonomy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...setupHeaders() },
      body: JSON.stringify(body),
    }),
  listPacks: () => fetchJson<UseCasePack[]>('/api/packs', { headers: maybeSetupHeaders() }),
  installPack: (pack_id: string, primary = false, provider_profile = '') =>
    fetchJson<{ ok?: boolean; pack?: UseCasePack; state?: SetupState }>('/api/packs/install', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pack_id, primary, provider_profile }),
    }),
  listProviders: () => fetchJson<ProviderProfile[]>('/api/providers', { headers: maybeSetupHeaders() }),
  testProvider: (id: string) =>
    fetchJson<{ ok?: boolean; status?: string; detail?: string; profile?: ProviderProfile }>('/api/providers/test', {
      method: 'POST',
      headers: maybeSetupHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ id }),
    }),
  switchProvider: (id: string) =>
    fetchJson<{ ok?: boolean; provider?: ProviderProfile; state?: SetupState }>('/api/providers/switch', {
      method: 'POST',
      headers: maybeSetupHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ id }),
    }),
  listExtensions: () => fetchJson<ExtensionManifest[]>('/api/extensions', { headers: maybeSetupHeaders() }),
  installExtension: (id: string) =>
    fetchJson<{ ok?: boolean; extension?: ExtensionManifest; state?: SetupState }>('/api/extensions/install', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id }),
    }),
  listTraces: () => fetchJson<TraceRecord[]>('/api/traces'),
  listEvals: () => fetchJson<EvalSuite[]>('/api/evals', { headers: maybeSetupHeaders() }),
  getAgentCard: () => fetchJson<{ card?: Record<string, unknown>; peers?: Array<Record<string, unknown>> }>('/api/a2a/agent-card'),
  delegateA2ATask: (peer_url: string, intent: string, workspace = 'nexus_default') =>
    fetchJson<{ ok?: boolean; result?: string }>('/api/a2a/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ peer_url, intent, workspace }),
    }),
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
  sendConversationMessage: (message: string, workspace = 'nexus_default') =>
    fetchJson<{ task_id?: string; status?: string }>('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, workspace }),
    }),
  listApprovals: () => fetchJson<any[]>('/api/approvals'),
}
