import { defineConfig, devices } from '@playwright/test';

/**
 * The journey suite runs against the built console.
 *
 * It deliberately does not start the core service: the console falls back to
 * the recorded snapshot when no service is listening, and that fallback is the
 * path the hosted demo takes. Running the suite this way proves the public
 * demo behaves the same as a local one. Start the core service before running
 * if you want to exercise the live engine instead.
 */
export default defineConfig({
  testDir: './e2e',
  // The core service holds replay state per scenario, not per client, so two
  // browser contexts driving the same scenario would decide each other's
  // results. One worker keeps the journey honest against either source.
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: 'http://127.0.0.1:4173',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'pnpm run preview',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
