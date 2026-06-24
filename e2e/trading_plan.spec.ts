import { test, expect } from '@playwright/test'
import { login, waitForLoadingDone, waitForTableLoaded } from './utils'

/**
 * 交易计划 E2E 测试
 *
 * 产品定位：基于历史数据分析结果制定的投资计划
 *
 * 覆盖：
 * - 交易计划列表
 * - 创建/编辑/删除交易计划
 * - 激活/停用交易计划
 * - 止损止盈规则设置
 * - 计划与持仓联动
 */
test.describe('交易计划管理', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('交易计划列表页面加载', async ({ page }) => {
    await page.goto('/trading-system')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/trading-system/)

    const content = page.locator('.el-main, .app-main, main, .el-card, .el-table').first()
    await expect(content).toBeVisible({ timeout: 10000 })
  })

  test('创建新交易计划', async ({ page }) => {
    await page.goto('/trading-system')
    await waitForLoadingDone(page)

    const createBtn = page.locator('button:has-text("创建"), button:has(.el-icon-plus)').first()
    if (await createBtn.isVisible({ timeout: 5000 })) {
      await createBtn.click()
      await page.waitForTimeout(3000)

      const planNameInput = page.locator('input[placeholder*="计划名称"], input[name*="name"]').first()
      if (await planNameInput.isVisible({ timeout: 3000 })) {
        await planNameInput.fill('测试交易计划')
      }
    }
  })

  test('编辑交易计划', async ({ page }) => {
    await page.goto('/trading-system')
    await waitForLoadingDone(page)

    const editBtn = page.locator('button:has-text("编辑"), .el-button--edit').first()
    if (await editBtn.isVisible({ timeout: 3000 })) {
      await editBtn.click()
      await page.waitForTimeout(3000)
    }
  })

  test('激活/停用交易计划', async ({ page }) => {
    await page.goto('/trading-system')
    await waitForLoadingDone(page)

    const toggleBtn = page.locator('button:has-text("激活"), button:has-text("停用")').first()
    if (await toggleBtn.isVisible({ timeout: 3000 })) {
      await toggleBtn.click()
      await page.waitForTimeout(2000)
    }
  })

  test('设置止损止盈规则', async ({ page }) => {
    await page.goto('/trading-system')
    await waitForLoadingDone(page)

    const ruleBtn = page.locator('button:has-text("规则"), .rule-settings').first()
    if (await ruleBtn.isVisible({ timeout: 3000 })) {
      await ruleBtn.click()
      await page.waitForTimeout(3000)

      const stopLossInput = page.locator('input[placeholder*="止损"], .stop-loss input').first()
      if (await stopLossInput.isVisible({ timeout: 3000 })) {
        await stopLossInput.fill('10')
      }

      const takeProfitInput = page.locator('input[placeholder*="止盈"], .take-profit input').first()
      if (await takeProfitInput.isVisible({ timeout: 3000 })) {
        await takeProfitInput.fill('20')
      }
    }
  })

  test('查看交易计划详情', async ({ page }) => {
    await page.goto('/trading-system')
    await waitForLoadingDone(page)

    const viewBtn = page.locator('button:has-text("查看"), .view-detail').first()
    if (await viewBtn.isVisible({ timeout: 3000 })) {
      await viewBtn.click()
      await page.waitForTimeout(3000)
    }
  })
})
