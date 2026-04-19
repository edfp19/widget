const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests/e2e',
  timeout: 30000,
  expect: {
    timeout: 5000
  },
  use: {
    baseURL: 'http://127.0.0.1:8080',
    browserName: 'chromium',
    channel: process.env.PLAYWRIGHT_CHANNEL || undefined,
    trace: 'on-first-retry'
  },
  webServer: {
    command: 'uv run python backend/server.py',
    url: 'http://127.0.0.1:8080/example',
    reuseExistingServer: !process.env.CI,
    timeout: 120000
  }
});
