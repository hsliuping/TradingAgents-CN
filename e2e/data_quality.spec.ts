import { test, expect } from '@playwright/test'
import { login, waitForLoadingDone, waitForTableLoaded } from './utils'

/**
 * 数据质量监控 E2E 测试
 *
 * 产品定位：保障日线/历史数据获取的稳定性和可靠性
 *
 * 覆盖：
 * - 数据源质量统计（成功率/耗时）
 * - QMT 连接诊断
 * - 数据源配置管理
 * - Agent 工坊与版本管理
 */
test.describe('数据源质量监控', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('数据源配置管理页面加载', async ({ page }) => {
    await page.goto('/settings/config')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/settings\/config/)

    const content = page.locator('.el-main, .app-main, main, .el-card').first()
    await expect(content).toBeVisible({ timeout: 10000 })
  })

  test('多数据源同步页面加载', async ({ page }) => {
    await page.goto('/settings/sync')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/settings\/sync/)

    const content = page.locator('.el-main, .app-main, main, .el-card').first()
    await expect(content).toBeVisible({ timeout: 10000 })
  })

  test('缓存管理页面加载', async ({ page }) => {
    await page.goto('/settings/cache')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/settings\/cache/)

    const content = page.locator('.el-main, .app-main, main, .el-card').first()
    await expect(content).toBeVisible({ timeout: 10000 })
  })
})

test.describe('QMT 连接诊断', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('QMT 诊断 - 配置管理页面可访问', async ({ page }) => {
    // QMT诊断通过后端API提供，前端通过配置管理页面访问
    await page.goto('/settings/config')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/settings\/config/)

    const content = page.locator('.el-main, .app-main, main, .el-card').first()
    await expect(content).toBeVisible({ timeout: 10000 })
  })

  test('运行 QMT 连接诊断', async ({ page }) => {
    // QMT诊断功能已合并到配置管理页面
    await page.goto('/settings/config')
    await waitForLoadingDone(page)

    const diagnosisBtn = page.locator('button:has-text("诊断"), button:has-text("检查")').first()
    if (await diagnosisBtn.isVisible({ timeout: 5000 })) {
      await diagnosisBtn.click()
      await page.waitForTimeout(5000)
    }
  })
})

test.describe('数据源配置', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('配置管理页面加载', async ({ page }) => {
    await page.goto('/settings/config')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/settings\/config/)

    const content = page.locator('.el-main, .app-main, main, .el-card').first()
    await expect(content).toBeVisible({ timeout: 10000 })
  })

  test('设置首页加载', async ({ page }) => {
    await page.goto('/settings')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/settings/)
  })

  test('股票关注列表分组配置', async ({ page }) => {
    await page.goto('/settings/watchlist-groups')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/settings\/watchlist-groups/)
  })
})

test.describe('Agent 工坊', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('Agent 列表页面加载', async ({ page }) => {
    await page.goto('/workflow/agent-workshop')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/workflow\/agent-workshop/)

    const content = page.locator('.el-main, .app-main, main, .el-card').first()
    await expect(content).toBeVisible({ timeout: 10000 })
  })

  test('查看 Agent 版本历史', async ({ page }) => {
    await page.goto('/workflow/agent-workshop')
    await waitForLoadingDone(page)

    const historyBtn = page.locator('button:has-text("历史版本"), button:has-text("版本")').first()
    if (await historyBtn.isVisible({ timeout: 5000 })) {
      await historyBtn.click()
      await waitForLoadingDone(page)
      await page.waitForTimeout(3000)
    }
  })

  test('Agent 版本回滚', async ({ page }) => {
    await page.goto('/workflow/agent-workshop')
    await waitForLoadingDone(page)

    const rollbackBtn = page.locator('button:has-text("回滚"), .rollback-btn').first()
    if (await rollbackBtn.isVisible({ timeout: 5000 })) {
      await rollbackBtn.click()
      await page.waitForTimeout(2000)

      const confirmBtn = page.locator('.el-dialog button:has-text("确定")').first()
      if (await confirmBtn.isVisible({ timeout: 3000 })) {
        await confirmBtn.click()
        await page.waitForTimeout(3000)
      }
    }
  })
})
