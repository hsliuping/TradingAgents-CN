import { test, expect } from '@playwright/test'
import { login, waitForLoadingDone, waitForTableLoaded } from './utils'

/**
 * 持仓管理 E2E 测试
 *
 * 产品定位：基于历史数据的投资组合管理
 *
 * 覆盖：
 * - 持仓列表查看
 * - 持仓收益分析
 * - 持仓分布图表
 * - 模拟交易（买入/卖出/交易记录）
 * - 交易复盘（胜率/盈亏/交易明细）
 */
test.describe('持仓管理', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('持仓列表页面加载', async ({ page }) => {
    await page.goto('/portfolio')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/portfolio/)

    const content = page.locator('.el-main, .app-main, main, .el-card').first()
    await expect(content).toBeVisible({ timeout: 10000 })
  })

  test('持仓收益统计', async ({ page }) => {
    await page.goto('/portfolio')
    await waitForLoadingDone(page)

    const totalAssets = page.locator(':text("总资产"), .total-assets').first()
    await expect(totalAssets).toBeVisible({ timeout: 10000 })
  })

  test('持仓统计卡片', async ({ page }) => {
    await page.goto('/portfolio')
    await waitForLoadingDone(page)

    const statCard = page.locator('.stat-card, .stat-value').first()
    await expect(statCard).toBeVisible({ timeout: 10000 })
  })

  test('从持仓发起分析', async ({ page }) => {
    await page.goto('/portfolio')
    await waitForLoadingDone(page)

    const analyzeBtn = page.locator('button:has-text("分析"), .analyze-btn').first()
    if (await analyzeBtn.isVisible({ timeout: 5000 })) {
      await analyzeBtn.click()
      await page.waitForTimeout(3000)
    }
  })
})

test.describe('模拟交易', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('模拟交易页面加载', async ({ page }) => {
    await page.goto('/paper')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/paper/)

    const content = page.locator('.el-main, .app-main, main, .el-card').first()
    await expect(content).toBeVisible({ timeout: 10000 })
  })

  test('买入股票流程', async ({ page }) => {
    await page.goto('/paper')
    await waitForLoadingDone(page)

    const buyTab = page.locator('text=买入, .buy-tab').first()
    if (await buyTab.isVisible({ timeout: 5000 })) {
      await buyTab.click()
    }

    const stockInput = page.locator('input[placeholder*="股票"], input[name*="code"]').first()
    if (await stockInput.isVisible({ timeout: 3000 })) {
      await stockInput.fill('000001')
      await page.waitForTimeout(2000)
    }

    const amountInput = page.locator('input[placeholder*="数量"], input[name*="amount"]').first()
    if (await amountInput.isVisible({ timeout: 3000 })) {
      await amountInput.fill('100')
    }

    const submitBtn = page.locator('button:has-text("买入"), button[type="primary"]').first()
    if (await submitBtn.isVisible({ timeout: 3000 })) {
      await submitBtn.click()
      await page.waitForTimeout(3000)
    }
  })

  test('卖出股票流程', async ({ page }) => {
    await page.goto('/paper')
    await waitForLoadingDone(page)

    const sellTab = page.locator('text=卖出, .sell-tab').first()
    if (await sellTab.isVisible({ timeout: 5000 })) {
      await sellTab.click()
    }

    const stockSelector = page.locator('.stock-selector, .el-select').first()
    if (await stockSelector.isVisible({ timeout: 3000 })) {
      await stockSelector.click()
      await page.waitForTimeout(2000)
    }
  })

  test('查看交易记录', async ({ page }) => {
    await page.goto('/paper')
    await waitForLoadingDone(page)

    const tradeHistoryTab = page.locator('text=交易记录, .history-tab').first()
    if (await tradeHistoryTab.isVisible({ timeout: 5000 })) {
      await tradeHistoryTab.click()
      await waitForTableLoaded(page)
    }
  })

  test('查看持仓明细', async ({ page }) => {
    await page.goto('/paper')
    await waitForLoadingDone(page)

    const positionTab = page.locator('text=持仓, .position-tab').first()
    if (await positionTab.isVisible({ timeout: 5000 })) {
      await positionTab.click()
      await waitForTableLoaded(page)
    }
  })

  test('资产概览', async ({ page }) => {
    await page.goto('/paper')
    await waitForLoadingDone(page)

    const assetOverview = page.locator('.asset-summary, .el-card:has-text("总资产")').first()
    await expect(assetOverview).toBeVisible({ timeout: 10000 })
  })
})

test.describe('交易复盘', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('复盘概览页面加载', async ({ page }) => {
    await page.goto('/review')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/review/)

    const overview = page.locator('.review-overview, .el-card').first()
    await expect(overview).toBeVisible({ timeout: 10000 })
  })

  test('查看交易明细', async ({ page }) => {
    await page.goto('/review')
    await waitForLoadingDone(page)

    const detailTab = page.locator('text=交易明细, .detail-tab').first()
    if (await detailTab.isVisible({ timeout: 5000 })) {
      await detailTab.click()
      await waitForTableLoaded(page)
    }
  })

  test('查看盈亏分析', async ({ page }) => {
    await page.goto('/review')
    await waitForLoadingDone(page)

    const profitTab = page.locator('text=盈亏, text=收益, .profit-tab').first()
    if (await profitTab.isVisible({ timeout: 5000 })) {
      await profitTab.click()
      await page.waitForTimeout(3000)
    }
  })

  test('查看胜率统计', async ({ page }) => {
    await page.goto('/review')
    await waitForLoadingDone(page)

    // 切换到模拟交易复盘标签页才能看到胜率统计
    await page.locator('.el-tabs__item').filter({ hasText: '模拟交易复盘' }).first().click()
    await page.waitForTimeout(3000)
    await waitForLoadingDone(page)

    const winRate = page.locator('.stat-label:has-text("胜率"), :text("胜率")').first()
    await expect(winRate).toBeVisible({ timeout: 10000 })
  })
})
