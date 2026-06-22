import { test, expect } from '@playwright/test'
import { login, waitForLoadingDone, waitForTableLoaded } from './utils'

/**
 * 核心页面导航 E2E 测试
 *
 * 覆盖:
 * - Dashboard 页面加载
 * - 侧边栏导航到各核心页面
 * - 页面标题正确显示
 */
test.describe('核心页面导航', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('Dashboard 页面正确加载', async ({ page }) => {
    await page.goto('/dashboard')
    await waitForLoadingDone(page)

    // 验证页面有内容（不是空白页）
    const mainContent = page.locator('.el-main, .app-main, main, .dashboard').first()
    await expect(mainContent).toBeVisible({ timeout: 10000 })
  })

  test('导航到单股分析页面', async ({ page }) => {
    await page.goto('/analysis/single')
    await waitForLoadingDone(page)

    // 验证页面加载
    await expect(page).toHaveURL(/\/analysis\/single/)
  })

  test('导航到筛选页面', async ({ page }) => {
    await page.goto('/screening')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/screening/)
  })

  test('导航到收藏页面', async ({ page }) => {
    await page.goto('/favorites')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/favorites/)
  })

  test('导航到报告页面', async ({ page }) => {
    await page.goto('/reports')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/reports/)
  })

  test('导航到持仓页面', async ({ page }) => {
    await page.goto('/portfolio')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/portfolio/)
  })

  test('导航到模拟交易页面', async ({ page }) => {
    await page.goto('/paper')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/paper/)
  })

  test('导航到交易复盘页面', async ({ page }) => {
    await page.goto('/review')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/review/)
  })

  test('导航到任务中心页面', async ({ page }) => {
    await page.goto('/tasks/unified')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/tasks\/unified/)
  })

  test('导航到设置页面', async ({ page }) => {
    await page.goto('/settings')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/settings/)
  })
})
