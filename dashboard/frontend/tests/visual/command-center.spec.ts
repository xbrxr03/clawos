/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { expect, Page, test } from '@playwright/test'

type SessionPayload = {
  auth_required?: boolean
  authenticated?: boolean
}

type SetupStatePayload = {
  install_channel?: string
  platform?: string
  architecture?: string
  service_manager?: string
  detected_hardware?: { summary?: string; ram_gb?: number; gpu_name?: string; tier?: string }
  recommended_profile?: string
  selected_models?: string[]
  workspace?: string
  voice_enabled?: boolean
  enable_openclaw?: boolean
  launch_on_login?: boolean
  policy_mode?: string
  progress_stage?: string
  logs?: string[]
  completion_marker?: boolean
  plan_steps?: string[]
}

async function installWebSocketMock(page: Page, messageType: 'snapshot' | 'setup_state', data: unknown) {
  await page.addInitScript(
    ({ mockMessageType, mockPayload }) => {
      class MockWebSocket {
        static OPEN = 1
        readyState = 1
        onopen: ((event?: Event) => void) | null = null
        onclose: ((event?: Event) => void) | null = null
        onerror: ((event?: Event) => void) | null = null
        onmessage: ((event: MessageEvent<string>) => void) | null = null

        constructor(_url: string) {
          queueMicrotask(() => {
            this.onopen?.(new Event('open'))
            this.onmessage?.(
              new MessageEvent('message', {
                data: JSON.stringify({
                  type: mockMessageType,
                  data: mockPayload,
                }),
              })
            )
          })
        }

        send(_message: string) {}

        close() {
          this.onclose?.(new Event('close'))
        }
      }

      // @ts-expect-error browser test shim
      window.WebSocket = MockWebSocket
    },
    { mockMessageType: messageType, mockPayload: data }
  )
}

async function stubSession(page: Page, payload: SessionPayload) {
  await page.route('**/api/session', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(payload),
    })
  })
}

async function stubCommandCenterData(page: Page) {
  await installWebSocketMock(page, 'snapshot', {
    approvals: [],
    services: {},
    tasks: { active: [], queued: [], failed: [], completed: [] },
    models: { models: [], default: 'qwen2.5:7b' },
  })

  await stubSession(page, { auth_required: false, authenticated: true })

  await page.route('**/api/tasks', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ active: [], queued: [], failed: [], completed: [] }),
    })
  })

  await page.route('**/api/runtimes', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({}),
    })
  })

  await page.route('**/api/packs', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 'daily-briefing-os',
          name: 'Daily Briefing OS',
          primary: true,
          secondary: false,
          description: 'Morning and evening briefings.',
        },
      ]),
    })
  })

  await page.route('**/api/providers', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 'local-ollama',
          name: 'Local Ollama',
          selected: true,
          kind: 'ollama',
          status: 'online',
        },
      ]),
    })
  })

  await page.route('**/api/traces', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 'trace-1',
          title: 'Initial trace',
          category: 'setup',
          status: 'completed',
        },
      ]),
    })
  })
}

async function stubSetupData(page: Page, payload: SetupStatePayload) {
  await installWebSocketMock(page, 'setup_state', payload)

  await page.route('**/api/setup/state', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(payload),
    })
  })

  await page.route('**/api/setup/diagnostics', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        platform: payload.platform || 'darwin',
        service_manager: payload.service_manager || 'launchd',
        desktop: {
          launch_on_login_supported: true,
        },
      }),
    })
  })

  await page.route('**/api/packs', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 'daily-briefing-os',
          name: 'Daily Briefing OS',
          primary: true,
          secondary: false,
          wave: 'wave-1',
        },
        {
          id: 'coding-autopilot',
          name: 'Coding Autopilot',
          primary: false,
          secondary: true,
          wave: 'wave-1',
        },
      ]),
    })
  })

  await page.route('**/api/providers', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 'local-ollama',
          name: 'Local Ollama',
          selected: true,
          kind: 'ollama',
          status: 'online',
        },
        {
          id: 'openai-compatible',
          name: 'OpenAI-Compatible',
          selected: false,
          kind: 'openai-compatible',
          status: 'configured',
        },
      ]),
    })
  })
}

test('command center shell renders', async ({ page }) => {
  await stubCommandCenterData(page)

  await page.goto('/')

  await expect(page.getByText('ClawOS', { exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Workflows' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Browse workflows' })).toBeVisible()
})

test('setup flow renders machine posture and actions', async ({ page }) => {
  await stubSetupData(page, {
    install_channel: 'desktop',
    platform: 'darwin',
    architecture: 'arm64',
    service_manager: 'launchd',
    detected_hardware: {
      summary: 'Apple Silicon balanced profile',
      ram_gb: 24,
      gpu_name: 'Apple M3',
      tier: 'A',
    },
    recommended_profile: 'balanced',
    selected_models: ['qwen2.5:7b'],
    workspace: 'nexus_default',
    voice_enabled: true,
    enable_openclaw: false,
    launch_on_login: true,
    policy_mode: 'recommended',
    progress_stage: 'idle',
    logs: ['Inspection ready', 'Waiting for apply'],
    plan_steps: ['Inspect platform posture', 'Provision local runtime', 'Register launch on login'],
  })

  await page.goto('/setup')

  await expect(page.getByText('ClawOS Setup', { exact: true })).toBeVisible()
  await expect(page.getByText('Recommended profile:', { exact: false })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Apply Setup' })).toBeVisible()
  await expect(page.getByText('Apple Silicon balanced profile')).toBeVisible()
})

test('auth gate renders when dashboard token is required', async ({ page }) => {
  await stubSession(page, { auth_required: true, authenticated: false })

  await page.goto('/')

  await expect(page.getByText('Dashboard access', { exact: true })).toBeVisible()
  await expect(page.getByPlaceholder('Dashboard token')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Unlock Command Center' })).toBeVisible()
})
