import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: 'http://127.0.0.1:4173',
    browserName: 'chromium',
  },
  webServer: {
    command: 'npm run preview',
    url: 'http://127.0.0.1:4173/client/',
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
