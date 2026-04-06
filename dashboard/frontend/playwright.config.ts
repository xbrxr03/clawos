import { defineConfig } from '@playwright/test'

const env =
  (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env ?? {}
const isCI = Boolean(env.CI)

export default defineConfig({
  testDir: './tests/visual',
  outputDir: './test-results',
  reporter: isCI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: 'http://127.0.0.1:4173',
    viewport: { width: 1440, height: 960 },
  },
  webServer: {
    command: 'npm run preview -- --host 127.0.0.1 --port 4173',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: !isCI,
    timeout: 120000,
  },
})
