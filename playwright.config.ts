import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright E2E 测试配置
 *
 * 前置条件:
 * 1. 后端服务运行在 http://localhost:8000
 * 2. 前端 dev server 运行在 http://localhost:3000
 *
 * 运行: npx playwright test
 * 运行UI模式: npx playwright test --ui
 * 查看报告: npx playwright show-report
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false, // 串行执行，避免测试数据冲突
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1, // 单worker，避免并发问题
  reporter: [
    ['html', { outputFolder: 'e2e-reports/html' }],
    ['list'],
  ],
  timeout: 60000, // 60秒超时
  expect: {
    timeout: 10000,
  },
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:3002',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    locale: 'zh-CN',
    timezone: 'Asia/Shanghai',
    actionTimeout: 15000,
    navigationTimeout: 30000,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
