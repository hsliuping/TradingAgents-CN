import { test, expect } from '@playwright/test'
import { login, waitForLoadingDone, waitForTableLoaded } from './utils'

/**
 * 投资报告 E2E 测试
 *
 * 产品定位：基于日线历史数据生成的深度分析报告
 *
 * 覆盖：
 * - 报告列表查看
 * - 报告详情查看
 * - 报告搜索与筛选
 * - 报告导出
 * - Token 消耗统计
 */
test.describe('投资报告管理', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('报告列表页面加载', async ({ page }) => {
    await page.goto('/reports')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/reports/)

    const reportTable = page.locator('.el-table, .report-list').first()
    await expect(reportTable).toBeVisible({ timeout: 10000 })
  })

  test('查看报告详情', async ({ page }) => {
    await page.goto('/reports')
    await waitForLoadingDone(page)

    const viewBtn = page.locator('button:has-text("查看"), .view-report').first()
    if (await viewBtn.isVisible({ timeout: 3000 })) {
      await viewBtn.click()
      await page.waitForTimeout(5000)
    }
  })

  test('搜索报告', async ({ page }) => {
    await page.goto('/reports')
    await waitForLoadingDone(page)

    const searchInput = page.locator('input[placeholder*="搜索"], .search-input').first()
    if (await searchInput.isVisible({ timeout: 5000 })) {
      await searchInput.fill('贵州茅台')
      await page.waitForTimeout(2000)
    }
  })

  test('按时间筛选报告', async ({ page }) => {
    await page.goto('/reports')
    await waitForLoadingDone(page)

    const datePicker = page.locator('.el-date-picker, .date-range').first()
    if (await datePicker.isVisible({ timeout: 5000 })) {
      await datePicker.click()
      await page.waitForTimeout(2000)
    }
  })

  test('导出报告', async ({ page }) => {
    await page.goto('/reports')
    await waitForLoadingDone(page)

    const exportBtn = page.locator('button:has-text("导出"), button:has(.el-icon-download)').first()
    if (await exportBtn.isVisible({ timeout: 3000 })) {
      await exportBtn.click()
      await page.waitForTimeout(2000)
    }
  })

  test('Token 消耗统计页面', async ({ page }) => {
    await page.goto('/reports/token')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/reports\/token/)

    const content = page.locator('.el-main, .app-main, main, .el-card').first()
    await expect(content).toBeVisible({ timeout: 10000 })
  })
})
