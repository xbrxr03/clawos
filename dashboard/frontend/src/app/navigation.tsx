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
  { to: '/workflows', label: 'Workflows', icon: <IconWorkflow /> },
  { to: '/models', label: 'Models', icon: <IconCpu /> },
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

function IconCpu() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="4" y="4" width="8" height="8" rx="1.6" stroke="currentColor" strokeWidth="1.2"/><path d="M6.1 1.75v2M9.9 1.75v2M6.1 12.25v2M9.9 12.25v2M1.75 6.1h2M1.75 9.9h2M12.25 6.1h2M12.25 9.9h2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>
}

function IconDatabase() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><ellipse cx="8" cy="4" rx="4.75" ry="2" stroke="currentColor" strokeWidth="1.2"/><path d="M3.25 4v4c0 1.1 2.12 2 4.75 2s4.75-.9 4.75-2V4M3.25 8v4c0 1.1 2.12 2 4.75 2s4.75-.9 4.75-2V8" stroke="currentColor" strokeWidth="1.2"/></svg>
}

function IconSettings() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="m6.85 2.1.31 1.44a4.77 4.77 0 0 1 1.68 0l.31-1.44 1.57.45-.52 1.38c.46.25.88.57 1.24.95l1.33-.66.84 1.41-1.14.95c.1.27.17.56.21.85l1.46.18v1.63l-1.46.18a4.66 4.66 0 0 1-.21.84l1.14.96-.84 1.4-1.33-.65c-.36.37-.78.69-1.24.95l.52 1.38-1.57.45-.31-1.44a4.77 4.77 0 0 1-1.68 0l-.31 1.44-1.57-.45.52-1.38a4.6 4.6 0 0 1-1.24-.95l-1.33.65-.84-1.4 1.14-.96a4.66 4.66 0 0 1-.21-.84l-1.46-.18V7.38l1.46-.18c.04-.29.11-.58.21-.85l-1.14-.95.84-1.41 1.33.66c.36-.38.78-.7 1.24-.95l-.52-1.38 1.57-.45Z" stroke="currentColor" strokeWidth="1.05" strokeLinejoin="round"/><circle cx="8" cy="8.19" r="2.05" stroke="currentColor" strokeWidth="1.2"/></svg>
}
