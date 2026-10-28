import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 12_000 },
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.APP_BASE_URL || 'http://127.0.0.1:8094',
    browserName: 'chromium',
    channel: process.env.PLAYWRIGHT_CHANNEL || (process.env.CI ? undefined : 'msedge'),
    viewport: { width: 1440, height: 1000 },
    locale: 'id-ID',
    timezoneId: 'Asia/Jakarta',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
});
