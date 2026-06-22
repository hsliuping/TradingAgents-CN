import { test, expect } from '@playwright/test'
import { login, waitForLoadingDone, waitForTableLoaded } from './utils'

/**
 * 持仓与交易管理 E2E 测试
 *
 * 覆盖:
 * - 持仓页面加载
 * - 模拟交易页面加载
 * - 交易计划列表
 * - 交易复盘页面
 */
test.describe('持仓与交易管理', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('持仓页面加载并显示持仓列表', async ({ page }) => {
    await page.goto('/portfolio')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/portfolio/)

    // 验证有内容区域
    const content = page.locator('.el-main, .app-main, main, .el-card').first()
    await expect(content).toBeVisible({ timeout: 10000 })
  })

  test('模拟交易页面加载', async ({ page }) => {
    await page.goto('/paper')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/paper/)

    const content = page.locator('.el-main, .app-main, main, .el-card').first()
    await expect(content).toBeVisible({ timeout: 10000 })
  })

  test('交易计划列表页面加载', async ({ page }) => {
    await page.goto('/trading-system')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/trading-system/)

    const content = page.locator('.el-main, .app-main, main, .el-card, .el-table').first()
    await expect(content).toBeVisible({ timeout: 10000 })
  })

  test('交易复盘页面加载', async ({ page }) => {
    await page.goto('/review')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/review/)

    const content = page.locator('.el-main, .app-main, main, .el-card, .el-table').first()
    await expect(content).toBeVisible({ timeout: 10000 })
  })
})

/**
 * 设置页面 E2E 测试
 */
test.describe('设置页面', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('设置首页加载', async ({ page }) => {
    await page.goto('/settings')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/settings/)
  })

  test('配置管理页面加载', async ({ page }) => {
    await page.goto('/settings/config')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/settings\/config/)
  })

  test('定时分析配置页面加载', async ({ page }) => {
    await page.goto('/settings/scheduled-analysis')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/settings\/scheduled-analysis/)
  })

  test('自选股分组页面加载', async ({ page }) => {
    await page.goto('/settings/watchlist-groups')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/settings\/watchlist-groups/)
  })
})

/**
 * 报告页面 E2E 测试
 */
test.describe('报告页面', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('报告列表页面加载', async ({ page }) => {
    await page.goto('/reports')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/reports/)

    const content = page.locator('.el-main, .app-main, main, .el-card, .el-table').first()
    await expect(content).toBeVisible({ timeout: 10000 })
  })

  test('Token 统计页面加载', async ({ page }) => {
    await page.goto('/reports/token')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/reports\/token/)
  })
})
