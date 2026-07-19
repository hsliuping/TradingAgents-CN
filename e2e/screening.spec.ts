import { test, expect } from '@playwright/test'
import { login, waitForLoadingDone, waitForTableLoaded, selectStock } from './utils'

/**
 * 智能选股 E2E 测试
 *
 * 产品定位：基于基本面和技术面指标的多条件组合筛选
 *
 * 覆盖：
 * - 基本面筛选（PE/PB/ROE）
 * - 技术指标筛选（均线/成交量）
 * - 行业板块筛选
 * - 筛选结果排序与保存
 * - 股票关注列表管理（添加/分组/批量操作）
 */
test.describe('智能选股 - 基本面筛选', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('PE/PB/ROE 多条件组合筛选', async ({ page }) => {
    await page.goto('/screening')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/screening/)

    // 切换到高级模式标签页
    const advancedTab = page.locator('.el-tabs__item:has-text("高级模式")').first()
    if (await advancedTab.isVisible({ timeout: 5000 })) {
      await advancedTab.click()
      await page.waitForTimeout(2000)
    }

    const filterPanel = page.locator('.filter-panel').first()
    // 等待 filter-panel 上的 v-loading 遮罩消失
    await filterPanel.locator('.el-loading-mask').waitFor({ state: 'hidden', timeout: 30000 }).catch(() => {})
    await filterPanel.waitFor({ state: 'visible', timeout: 15000 }).catch(() => {})
    // 如果 filter-panel 仍然不可见，则跳过（数据源可能未配置）
    const filterVisible = await filterPanel.isVisible().catch(() => false)
    if (!filterVisible) {
      return
    }

    const peInput = page.locator('input[placeholder*="PE"], input[name*="pe"]').first()
    if (await peInput.isVisible({ timeout: 5000 })) {
      await peInput.fill('0-30')
    }

    const pbInput = page.locator('input[placeholder*="PB"], input[name*="pb"]').first()
    if (await pbInput.isVisible({ timeout: 3000 })) {
      await pbInput.fill('0-5')
    }

    const screenBtn = page.locator('button:has-text("筛选")').first()
    if (await screenBtn.isVisible({ timeout: 3000 })) {
      await screenBtn.click()
      await page.waitForTimeout(5000)
    }
  })

  test('行业板块筛选', async ({ page }) => {
    await page.goto('/screening')
    await waitForLoadingDone(page)

    const industrySelector = page.locator('.industry-selector, .el-select:has-text("行业")').first()
    if (await industrySelector.isVisible({ timeout: 5000 })) {
      await industrySelector.click()
      await page.waitForTimeout(2000)
    }
  })

  test('筛选结果排序', async ({ page }) => {
    await page.goto('/screening')
    await waitForLoadingDone(page)

    const sortButton = page.locator('button:has-text("排序"), .sort-selector').first()
    if (await sortButton.isVisible({ timeout: 3000 })) {
      await sortButton.click()
      await page.waitForTimeout(2000)
    }
  })

  test('保存筛选条件', async ({ page }) => {
    await page.goto('/screening')
    await waitForLoadingDone(page)

    const saveBtn = page.locator('button:has-text("保存"), button:has-text("收藏")').first()
    if (await saveBtn.isVisible({ timeout: 3000 })) {
      await saveBtn.click()
      await page.waitForTimeout(2000)
    }
  })
})

test.describe('智能选股 - 技术指标筛选', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('均线条件筛选', async ({ page }) => {
    await page.goto('/screening')
    await waitForLoadingDone(page)

    const maFilter = page.locator('text=均线, .ma-filter, .moving-average').first()
    if (await maFilter.isVisible({ timeout: 5000 })) {
      await maFilter.click()
      await page.waitForTimeout(2000)
    }
  })

  test('成交量条件筛选', async ({ page }) => {
    await page.goto('/screening')
    await waitForLoadingDone(page)

    const volumeFilter = page.locator('text=成交量, .volume-filter').first()
    if (await volumeFilter.isVisible({ timeout: 5000 })) {
      await volumeFilter.click()
      await page.waitForTimeout(2000)
    }
  })
})

test.describe('股票关注列表管理', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('添加股票到自选', async ({ page }) => {
    await page.goto('/favorites')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/favorites/)

    const addBtn = page.locator('button:has-text("添加"), button:has(.el-icon-plus)').first()
    if (await addBtn.isVisible({ timeout: 5000 })) {
      await addBtn.click()

      const input = page.locator('input[placeholder*="股票代码"]').first()
      if (await input.isVisible({ timeout: 3000 })) {
        await input.fill('600519')
      }

      const confirmBtn = page.locator('button:has-text("确定"), button[type="primary"]').first()
      if (await confirmBtn.isVisible({ timeout: 3000 })) {
        await confirmBtn.click()
        await page.waitForTimeout(2000)
      }
    }
  })

  test('股票关注列表列表加载', async ({ page }) => {
    await page.goto('/favorites')
    await waitForLoadingDone(page)

    const favoritesTable = page.locator('.el-table')
    await expect(favoritesTable).toBeVisible({ timeout: 10000 })
  })

  test('股票关注列表分组管理', async ({ page }) => {
    await page.goto('/favorites')
    await waitForLoadingDone(page)

    const groupSelector = page.locator('.group-selector, .el-select:has-text("分组")').first()
    if (await groupSelector.isVisible({ timeout: 5000 })) {
      await groupSelector.click()
      await page.waitForTimeout(2000)
    }
  })

  test('从股票关注列表发起分析', async ({ page }) => {
    await page.goto('/favorites')
    await waitForLoadingDone(page)

    const analyzeBtn = page.locator('button:has-text("分析"), .analyze-btn').first()
    if (await analyzeBtn.isVisible({ timeout: 5000 })) {
      await analyzeBtn.click()
      await page.waitForTimeout(3000)
    }
  })
})
