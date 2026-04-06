import type { Meta, StoryObj } from '@storybook/react'
import { MemoryRouter } from 'react-router-dom'
import { AppShell } from './AppShell'
import { InspectorRail } from './InspectorRail'

const meta: Meta<typeof AppShell> = {
  component: AppShell,
  title: 'Command Center/App Shell',
  render: (args) => (
    <MemoryRouter>
      <AppShell {...args} />
    </MemoryRouter>
  ),
}

export default meta

export const Default: StoryObj<typeof AppShell> = {
  args: {
    connected: true,
    services: {
      dashd: { status: 'up', latency_ms: 2 },
      agentd: { status: 'up', latency_ms: 14 },
      setupd: { status: 'degraded', latency_ms: 42 },
    },
    approvals: [{ id: 'a1' }, { id: 'a2' }],
    events: [{ type: 'workflow_progress', data: { id: 'repo-summary' } }],
    theme: 'dark',
    onToggleTheme: () => undefined,
    inspector: <InspectorRail approvals={[{ id: 'a1' }]} services={{ dashd: { status: 'up', latency_ms: 2 } }} events={[]} />,
    children: <div style={{ padding: 24 }}>Command Center content canvas</div>,
  },
}
