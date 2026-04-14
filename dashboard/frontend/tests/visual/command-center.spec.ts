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
    models: { models: [], default: 'gemma3:4b' },
    voice: { mode: 'off', state: 'idle' },
    jarvis: {
      thread_key: 'jarvis-ui',
      mode: 'push_to_talk',
      state: 'idle',
      voice_enabled: true,
      live_caption: 'Hello Sir. JARVIS is standing by.',
      last_response: 'Hello Sir. JARVIS is standing by.',
      recent_turns: [
        {
          id: 'assistant-turn',
          role: 'assistant',
          text: 'Hello Sir. JARVIS is standing by.',
          source: 'jarvis-ui:text',
          spoken: true,
          created_at: '2026-04-13T10:00:00Z',
        },
      ],
    },
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

  await page.route('**/api/voice/session', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ mode: 'off', state: 'idle' }),
    })
  })

  await page.route('**/api/health', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'ok', auth_required: false, host: '127.0.0.1', port: 7070, local_only: true }),
    })
  })

  await page.route('**/api/desktop/posture', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        platform: 'win32',
        autostart_kind: 'startup-shortcut',
        launch_on_login_supported: true,
        launch_on_login_enabled: true,
        paths: {
          logs: 'C:/tmp/logs',
          config: 'C:/tmp/config',
          workspace: 'C:/tmp/workspace',
          support: 'C:/tmp/support',
        },
      }),
    })
  })

  await page.route('**/api/gateway/health', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ whatsapp: 'linked', linked_phone: '+15551234567', routes_count: 1, approval_queue: 0 }),
    })
  })

  await page.route('**/api/jarvis/session', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        thread_key: 'jarvis-ui',
        mode: 'push_to_talk',
        state: 'idle',
        voice_enabled: true,
        live_caption: 'Hello Sir. JARVIS is standing by.',
        last_response: 'Hello Sir. JARVIS is standing by.',
        recent_turns: [
          {
            id: 'assistant-turn',
            role: 'assistant',
            text: 'Hello Sir. JARVIS is standing by.',
            source: 'jarvis-ui:text',
            spoken: true,
            created_at: '2026-04-13T10:00:00Z',
          },
        ],
      }),
    })
  })

  await page.route('**/api/jarvis/health', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        openclaw_installed: true,
        openclaw_running: true,
        gateway_port: 18789,
        stt_ok: true,
        tts_ok: true,
        wake_word_ok: true,
        microphone_ok: true,
        microphone_backend: 'fake-recorder',
        playback_backend: 'fake-player',
        provider_status: {
          preferred: 'elevenlabs',
          active: 'elevenlabs',
          fallback: false,
          elevenlabs_key_set: true,
        },
        briefing_sources: {
          weather: 'demo',
          headlines: 'demo',
          calendar: 'demo',
          tasks: 'demo',
          last_project: 'demo',
        },
      }),
    })
  })

  await page.route('**/api/jarvis/config', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          config: {
            voice_enabled: true,
            input_mode: 'push_to_talk',
            wake_phrase: 'Hey Jarvis',
            tts_provider_preference: 'elevenlabs',
            elevenlabs_voice_id: 'jarvis-voice',
            elevenlabs_key_set: true,
          },
          session: {
            thread_key: 'jarvis-ui',
            mode: 'push_to_talk',
            state: 'idle',
            voice_enabled: true,
            recent_turns: [],
          },
        }),
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        voice_enabled: true,
        input_mode: 'push_to_talk',
        wake_phrase: 'Hey Jarvis',
        tts_provider_preference: 'elevenlabs',
        elevenlabs_voice_id: 'jarvis-voice',
        elevenlabs_key_set: true,
      }),
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
  // Overview page has an "Open workflows" button (updated from "Browse workflows" in redesign)
  await expect(page.getByRole('button', { name: 'Open workflows' })).toBeVisible()
})

test('jarvis room renders as a dedicated voice chamber', async ({ page }) => {
  await stubCommandCenterData(page)

  await page.goto('/jarvis')

  await expect(page.getByRole('heading', { name: 'JARVIS Command Chamber' })).toBeVisible()
  await expect(page.getByText('Live Caption', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Activate JARVIS push to talk' })).toBeVisible()
  await expect(page.locator('.shell-inspector')).toHaveCount(0)
})

test('settings page hands JARVIS voice off to the chamber', async ({ page }) => {
  await stubCommandCenterData(page)

  await page.goto('/settings')

  await expect(page.getByText('Voice settings now live in the JARVIS chamber')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Open JARVIS' })).toBeVisible()
  await expect(page.getByText('ElevenLabs JARVIS voice')).toHaveCount(0)
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
    selected_models: ['gemma3:4b'],
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

  // "ClawOS Setup" is the eyebrow text of the PanelHeader
  await expect(page.getByText('ClawOS Setup', { exact: true })).toBeVisible()
  // "Current posture" is the section label above the hardware fact rows
  await expect(page.getByText('Current posture', { exact: false })).toBeVisible()
  // Hardware summary is formatted as "summary - ram GB RAM - gpu"
  await expect(page.getByText('Apple Silicon balanced profile', { exact: false })).toBeVisible()
  // Navigation/action button: "Continue" on non-summary steps, "Launch ClawOS" on summary
  await expect(
    page.getByRole('button', { name: /Continue|Launch ClawOS/i }).first()
  ).toBeVisible()
})

test('auth gate renders when dashboard token is required', async ({ page }) => {
  await stubSession(page, { auth_required: true, authenticated: false })

  await page.goto('/')

  // Auth gate title is "Unlock ClawOS" (updated from "Dashboard access" in redesign)
  await expect(page.getByText('Unlock ClawOS', { exact: true })).toBeVisible()
  await expect(page.getByPlaceholder('Dashboard token')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Unlock Command Center' })).toBeVisible()
})
