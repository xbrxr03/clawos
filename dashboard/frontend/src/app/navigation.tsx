import type { ReactNode } from 'react'

export type AppNavItem = {
  label: string
  to: string
  icon: ReactNode
}

export const appNav: AppNavItem[] = [
  { to: '/', label: 'Home', icon: <IconHome /> },
  { to: '/tasks', label: 'Tasks', icon: <IconTasks /> },
  { to: '/approvals', label: 'Approvals', icon: <IconShield /> },
  { to: '/packs', label: 'Packs', icon: <IconLayers /> },
  { to: '/workflows', label: 'Workflows', icon: <IconWorkflow /> },
  { to: '/providers', label: 'Providers', icon: <IconNodes /> },
  { to: '/registry', label: 'Registry', icon: <IconGrid /> },
  { to: '/traces', label: 'Traces', icon: <IconPulse /> },
  { to: '/models', label: 'Models', icon: <IconCpu /> },
  { to: '/studio', label: 'Pack Studio', icon: <IconStudio /> },
  { to: '/workbench', label: 'Workbench', icon: <IconWorkbench /> },
  { to: '/research', label: 'Research', icon: <IconResearch /> },
  { to: '/mcp', label: 'MCP', icon: <IconMCP /> },
  { to: '/federation', label: 'Federation', icon: <IconFederation /> },
  { to: '/memory', label: 'Memory/Audit', icon: <IconDatabase /> },
  { to: '/settings', label: 'Settings', icon: <IconSettings /> },
]

function IconHome() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M2.25 7.3 8 2.75l5.75 4.55v5.7a.75.75 0 0 1-.75.75h-2.9v-4h-4.2v4H3a.75.75 0 0 1-.75-.75V7.3Z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/></svg>
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
