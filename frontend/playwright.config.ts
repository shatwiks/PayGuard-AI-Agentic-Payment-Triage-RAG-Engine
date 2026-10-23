import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  use: {
    baseURL: 'http://localhost:3001',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    channel: 'msedge',
    headless: true,
  },
  projects: [
    {
      name: 'msedge',
      use: {
        channel: 'msedge',
        viewport: { width: 1440, height: 900 },
      },
    },
  ],
});
