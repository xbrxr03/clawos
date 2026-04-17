/* SPDX-License-Identifier: AGPL-3.0-or-later */
import type { ReactNode } from 'react'

export type AppNavItem = {
  section: string
  label: string
  to: string
  description: string
  icon: ReactNode
}

export const appNav: AppNavItem[] = [
  { section: 'Overview', to: '/', label: 'Overview', description: 'Signal-rich snapshot of services, approvals, conversation, and today.', icon: <IconHome /> },
  { section: 'Overview', to: '/jarvis', label: 'JARVIS', description: 'Flagship voice chamber with live transcription, spectrum, and cinematic status.', icon: <IconJarvis /> },
  { section: 'Operate', to: '/tasks', label: 'Tasks', description: 'Live queue for delegated work, missions, and execution history.', icon: <IconTasks /> },
  { section: 'Operate', to: '/approvals', label: 'Approvals', description: 'Human review for sensitive tool calls and irreversible actions.', icon: <IconShield /> },
  { section: 'Operate', to: '/workflows', label: 'Workflows', description: 'Run local-first automations with live progress and output.', icon: <IconWorkflow /> },
  { section: 'Operate', to: '/studio', label: 'Pack Studio', description: 'Compose and prepare pack flows, approvals, and deployment posture.', icon: <IconStudio /> },
  { section: 'Knowledge', to: '/brain', label: 'Kizuna', description: 'Living 3D knowledge graph — drop files and watch your brain build itself.', icon: <IconBrain /> },
  { section: 'Knowledge', to: '/workbench', label: 'Workbench', description: 'Fetch pages, inspect source material, and hand context to Nexus.', icon: <IconWorkbench /> },
  { section: 'Knowledge', to: '/research', label: 'Research', description: 'Citation-backed research sessions with resumable runs.', icon: <IconResearch /> },
  { section: 'Knowledge', to: '/memory', label: 'Memory', description: '14-layer memory state — pinned, workflow, vector, keyword, taosmd backends, and retention.', icon: <IconDatabase /> },
  { section: 'Platform', to: '/packs', label: 'Packs', description: 'Curated ClawOS outcomes with defaults, dashboards, and eval posture.', icon: <IconLayers /> },
  { section: 'Platform', to: '/skills', label: 'Skills', description: 'Browse and install 13,000+ skills from ClawHub with signature verification.', icon: <IconSkills /> },
  { section: 'Platform', to: '/providers', label: 'Providers', description: 'Local Ollama first, with cloud posture and testing when needed.', icon: <IconNodes /> },
  { section: 'Platform', to: '/models', label: 'Models', description: 'Ollama runtime inventory and model posture for this machine.', icon: <IconCpu /> },
  { section: 'Platform', to: '/registry', label: 'Registry', description: 'Trust-aware extension catalog and local A2A identity surface.', icon: <IconGrid /> },
  { section: 'Platform', to: '/mcp', label: 'MCP', description: 'Install, connect, and inspect model-context protocol servers and tools.', icon: <IconMCP /> },
  // Federation nav hidden until a2ad endpoints are exposed through dashd — post-v0.1.
  // { section: 'Platform', to: '/federation', label: 'Federation', description: 'Peer trust, agent-card identity, and multi-node ClawOS posture.', icon: <IconFederation /> },
  { section: 'System', to: '/traces', label: 'Traces', description: 'Release confidence, eval suites, and execution timeline history.', icon: <IconPulse /> },
  { section: 'System', to: '/license', label: 'License', description: 'Activate your ClawOS key, view tier features, and manage machine binding.', icon: <IconLicense /> },
  { section: 'System', to: '/settings', label: 'Settings', description: 'Desktop posture, support tooling, startup behavior, and recovery.', icon: <IconSettings /> },
]

function IconHome() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M2.25 7.3 8 2.75l5.75 4.55v5.7a.75.75 0 0 1-.75.75h-2.9v-4h-4.2v4H3a.75.75 0 0 1-.75-.75V7.3Z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/></svg>
}

function IconJarvis() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="4.5" stroke="currentColor" strokeWidth="1.2"/><circle cx="8" cy="8" r="1.8" fill="currentColor" opacity=".7"/><path d="M8 1.75v1.8M8 12.45v1.8M1.75 8h1.8M12.45 8h1.8M3.2 3.2l1.25 1.25M11.55 11.55l1.25 1.25M12.8 3.2l-1.25 1.25M4.45 11.55 3.2 12.8" stroke="currentColor" strokeWidth="1.05" strokeLinecap="round"/></svg>
}

function IconTasks() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M4 4.25h8M4 8h8M4 11.75h5.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>
}

function IconShield() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 1.75 13.25 3.5v4.2c0 2.42-1.52 4.66-5.25 6.55C4.27 12.36 2.75 10.12 2.75 7.7V3.5L8 1.75Z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/></svg>
}

function IconWorkflow() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="5" cy="4" r="1.75" stroke="currentColor" strokeWidth="1.2"/><circle cx="11" cy="12" r="1.75" stroke="currentColor" strokeWidth="1.2"/><path d="M6.3 5 9.7 10.9M10.8 4h2.45m-7.2 8H3.6" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>
}

function IconLayers() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 2.25 13 5 8 7.75 3 5 8 2.25ZM3 8.1l5 2.65 5-2.65M3 11.1l5 2.65 5-2.65" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" strokeLinecap="round"/></svg>
}

function IconNodes() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="4" cy="4" r="1.75" stroke="currentColor" strokeWidth="1.2"/><circle cx="12" cy="4" r="1.75" stroke="currentColor" strokeWidth="1.2"/><circle cx="8" cy="12" r="1.75" stroke="currentColor" strokeWidth="1.2"/><path d="M5.45 4h5.1M5.1 5.2 7.05 10M10.9 5.2 8.95 10" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>
}

function IconGrid() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="2.25" y="2.25" width="4.5" height="4.5" rx="1" stroke="currentColor" strokeWidth="1.2"/><rect x="9.25" y="2.25" width="4.5" height="4.5" rx="1" stroke="currentColor" strokeWidth="1.2"/><rect x="2.25" y="9.25" width="4.5" height="4.5" rx="1" stroke="currentColor" strokeWidth="1.2"/><rect x="9.25" y="9.25" width="4.5" height="4.5" rx="1" stroke="currentColor" strokeWidth="1.2"/></svg>
}

function IconPulse() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M1.75 8h2.7l1.4-2.8 2.1 5.6 1.8-3.3h4.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/></svg>
}

function IconCpu() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="4" y="4" width="8" height="8" rx="1.6" stroke="currentColor" strokeWidth="1.2"/><path d="M6.1 1.75v2M9.9 1.75v2M6.1 12.25v2M9.9 12.25v2M1.75 6.1h2M1.75 9.9h2M12.25 6.1h2M12.25 9.9h2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>
}

function IconDatabase() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><ellipse cx="8" cy="4" rx="4.75" ry="2" stroke="currentColor" strokeWidth="1.2"/><path d="M3.25 4v4c0 1.1 2.12 2 4.75 2s4.75-.9 4.75-2V4M3.25 8v4c0 1.1 2.12 2 4.75 2s4.75-.9 4.75-2V8" stroke="currentColor" strokeWidth="1.2"/></svg>
}

function IconStudio() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="2" y="2" width="5" height="5" rx="1.2" stroke="currentColor" strokeWidth="1.2"/><rect x="9" y="2" width="5" height="5" rx="1.2" stroke="currentColor" strokeWidth="1.2"/><rect x="2" y="9" width="5" height="5" rx="1.2" stroke="currentColor" strokeWidth="1.2"/><path d="M11.5 9v5M9 11.5h5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>
}

function IconFederation() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="5.25" stroke="currentColor" strokeWidth="1.2"/><path d="M8 2.75C8 2.75 6 5.5 6 8s2 5.25 2 5.25M8 2.75C8 2.75 10 5.5 10 8s-2 5.25-2 5.25M2.75 8h10.5" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"/></svg>
}

function IconMCP() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="1.75" y="5.75" width="3.5" height="3.5" rx="1" stroke="currentColor" strokeWidth="1.2"/><rect x="10.75" y="5.75" width="3.5" height="3.5" rx="1" stroke="currentColor" strokeWidth="1.2"/><rect x="6.25" y="1.75" width="3.5" height="3.5" rx="1" stroke="currentColor" strokeWidth="1.2"/><rect x="6.25" y="10.75" width="3.5" height="3.5" rx="1" stroke="currentColor" strokeWidth="1.2"/><path d="M5.25 7.5h5.5M8 5.25V3.5M8 12.75v-2" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"/></svg>
}

function IconResearch() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="7" cy="7" r="4.25" stroke="currentColor" strokeWidth="1.2"/><path d="m10.25 10.25 3 3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/><path d="M5.5 7h3M7 5.5v3" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"/></svg>
}

function IconWorkbench() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="1.75" y="2.75" width="12.5" height="8.5" rx="1.5" stroke="currentColor" strokeWidth="1.2"/><path d="M5.5 13.25h5M8 11.25v2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/><circle cx="8" cy="7" r="1.75" stroke="currentColor" strokeWidth="1.1"/><path d="M4.5 7h1.75M10.25 7H12" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"/></svg>
}

function IconSettings() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="m6.85 2.1.31 1.44a4.77 4.77 0 0 1 1.68 0l.31-1.44 1.57.45-.52 1.38c.46.25.88.57 1.24.95l1.33-.66.84 1.41-1.14.95c.1.27.17.56.21.85l1.46.18v1.63l-1.46.18a4.66 4.66 0 0 1-.21.84l1.14.96-.84 1.4-1.33-.65c-.36.37-.78.69-1.24.95l.52 1.38-1.57.45-.31-1.44a4.77 4.77 0 0 1-1.68 0l-.31 1.44-1.57-.45.52-1.38a4.6 4.6 0 0 1-1.24-.95l-1.33.65-.84-1.4 1.14-.96a4.66 4.66 0 0 1-.21-.84l-1.46-.18V7.38l1.46-.18c.04-.29.11-.58.21-.85l-1.14-.95.84-1.41 1.33.66c.36-.38.78-.7 1.24-.95l-.52-1.38 1.57-.45Z" stroke="currentColor" strokeWidth="1.05" strokeLinejoin="round"/><circle cx="8" cy="8.19" r="2.05" stroke="currentColor" strokeWidth="1.2"/></svg>
}

function IconSkills() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="2" y="9" width="5" height="5" rx="1.2" stroke="currentColor" strokeWidth="1.2"/><rect x="9" y="2" width="5" height="5" rx="1.2" stroke="currentColor" strokeWidth="1.2"/><path d="M4.5 9V7A2.5 2.5 0 0 1 7 4.5H9" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"/><circle cx="11.5" cy="11.5" r="2.25" stroke="currentColor" strokeWidth="1.1"/><path d="M13 13l1.25 1.25" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"/></svg>
}

function IconLicense() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="2.75" y="2.75" width="10.5" height="10.5" rx="2" stroke="currentColor" strokeWidth="1.2"/><path d="M5.5 8h5M5.5 5.5h5M5.5 10.5h3" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"/></svg>
}

function IconBrain() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M6 2.75c-1.65 0-2.75 1.1-2.75 2.75 0 .55.17 1.07.47 1.5-.3.43-.47.95-.47 1.5 0 1.65 1.1 2.75 2.75 2.75" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/><path d="M10 2.75c1.65 0 2.75 1.1 2.75 2.75 0 .55-.17 1.07-.47 1.5.3.43.47.95.47 1.5 0 1.65-1.1 2.75-2.75 2.75" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/><path d="M6 11.25v2M10 11.25v2M6 5.5h4M8 3.5v5" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"/><circle cx="8" cy="8" r="1.25" fill="currentColor" opacity=".6"/></svg>
}
