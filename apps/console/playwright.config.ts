import { defineConfig, devices } from '@playwright/test';

/**
 * Two suites, against the built console.
 *
 * `journey` is the HIVE engine view. It deliberately does not start the core
 * service: the console falls back to the recorded snapshot when no service is
 * listening, and that fallback is the path a static host takes.
 *
 * `storyline` is the judge path. It runs against the real HAEGIS service, which
 * serves the built console and the API from one origin exactly as the hosted
 * Space does, with interpretation switched off so no model is called.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: { trace: 'retain-on-failure' },
  projects: [
    {
      name: 'journey',
      testMatch: /(journey|replay)\.spec\.ts/,
      use: { ...devices['Desktop Chrome'], baseURL: 'http://127.0.0.1:4173' },
    },
    {
      name: 'storyline',
      testMatch: /storyline\.spec\.ts/,
      use: { ...devices['Desktop Chrome'], baseURL: 'http://127.0.0.1:8765' },
    },
  ],
  webServer: [
    {
      command: 'pnpm run preview',
      url: 'http://127.0.0.1:4173',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: 'uv run uvicorn aegis.api.app:app --host 127.0.0.1 --port 8765',
      cwd: '../../services/aegis',
      url: 'http://127.0.0.1:8765/healthz',
      env: {
        AEGIS_INTERPRETER: 'off',
        AEGIS_STATIC_DIR: '../../apps/console/dist',
      },
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
