import { defineConfig, devices } from '@playwright/test'

const frontendPort = 4175
const backendPort = 18000
const apiBase = `http://127.0.0.1:${backendPort}`

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 90_000,
  expect: {
    timeout: 10_000,
  },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: `http://127.0.0.1:${frontendPort}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    viewport: { width: 1440, height: 1200 },
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      command: `python scripts/browser-e2e-backend.py --host 127.0.0.1 --port ${backendPort}`,
      port: backendPort,
      cwd: '.',
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${frontendPort}`,
      port: frontendPort,
      cwd: '.',
      env: {
        ...process.env,
        VITE_API_BASE_URL: apiBase,
      },
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
})
