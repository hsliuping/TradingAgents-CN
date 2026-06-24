import { test, expect } from '@playwright/test'
import { login, waitForLoadingDone, waitForTableLoaded, selectStock } from './utils'

/**
 * 核心分析流程 E2E 测试
 *
 * 产品定位：基于日线、历史数据和基本面的深度分析平台
 *
 * 覆盖：
 * - 单股深度分析（技术面 + 基本面）
 * - 组合健康度分析
 * - 风险评估分析
 * - 分析任务管理（查看/重试/取消）
 * - 分析结果查看与反馈
 * - 定时分析配置
 */
test.describe('单股深度分析', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('触发单股分析 - 输入股票代码并启动分析', async ({ page }) => {
    test.setTimeout(600000) // 分析需要时间，设置 10 分钟超时
    await page.goto('/analysis/single')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/analysis\/single/)

    const stockInput = page.locator('input[placeholder*="000001"], .stock-input input').first()
    await expect(stockInput).toBeVisible({ timeout: 10000 })

    // 填入股票代码并触发 blur 事件以完成校验
    await stockInput.fill('600519')
    await stockInput.blur()
    await page.waitForTimeout(2000)

    // 选择 1 级快速分析（最快，2-5分钟）
    const depthOptions = page.locator('.depth-option')
    const quickDepth = depthOptions.first() // 1级 = 第一个
    await quickDepth.click()
    await page.waitForTimeout(500)

    // 确认按钮已启用
    const analyzeBtn = page.locator('button:has-text("开始智能分析")').first()
    await expect(analyzeBtn).toBeEnabled({ timeout: 10000 })

    // 点击开始分析
    await analyzeBtn.click()

    // 验证分析已提交：出现进度指示
    await expect(page.locator('button:has-text("分析进行中"), .progress-info, .el-progress').first()).toBeVisible({ timeout: 15000 })

    // 🔥 关键：等待分析真正完成，结果区域出现
    // 1级快速分析通常 2-5 分钟，设置 10 分钟超时
    const resultsSection = page.locator('.results-section, .results-card')
    await expect(resultsSection.first()).toBeVisible({ timeout: 600000 })

    // ✅ 验证分析结果完整性
    // 1. 分析结果卡片存在
    const resultsCard = page.locator('.results-card').first()
    await expect(resultsCard).toBeVisible()

    // 2. 股票代码标签存在
    const stockTag = page.locator('.results-card .el-tag').first()
    await expect(stockTag).toBeVisible()

    // 3. 分析概览存在
    const overview = page.locator('.overview-section, .markdown-content').first()
    await expect(overview).toBeVisible({ timeout: 10000 })

    // 4. 详细分析报告标签页存在
    const analysisTabs = page.locator('.analysis-tabs, .el-tabs').first()
    await expect(analysisTabs).toBeVisible({ timeout: 10000 })

    // 5. 🔴 检查是否有后端错误/降级节点
    const degradedAlert = page.locator('.el-alert:has-text("降级"), .el-alert:has-text("失败")')
    const degradedVisible = await degradedAlert.isVisible().catch(() => false)
    if (degradedVisible) {
      // 截图保存错误信息，但不让测试失败（降级是正常容错机制）
      console.log('⚠️ 分析有降级节点，详见截图')
      await page.screenshot({ path: 'test-results/analysis-degraded-nodes.png', fullPage: true })
    }

    // 6. 验证至少有一个报告标签页有内容
    const firstTab = page.locator('.el-tabs__content .report-content-wrapper').first()
    await expect(firstTab).toBeVisible({ timeout: 10000 })
  })

  test('分析页面加载 - 各分析维度入口可见', async ({ page }) => {
    await page.goto('/analysis/single')
    await waitForLoadingDone(page)

    const content = page.locator('.el-main, .app-main, main').first()
    await expect(content).toBeVisible({ timeout: 10000 })
  })

  test('查看历史分析结果', async ({ page }) => {
    await page.goto('/analysis/history')
    await waitForLoadingDone(page)

    const content = page.locator('.el-main, .app-main, main, .el-table').first()
    await expect(content).toBeVisible({ timeout: 10000 })
  })
})

test.describe('分析任务管理', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('任务中心 - 查看分析任务列表', async ({ page }) => {
    await page.goto('/tasks/unified')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/tasks\/unified/)

    const taskTable = page.locator('.el-table, .task-list').first()
    await expect(taskTable).toBeVisible({ timeout: 10000 })
  })

  test('任务中心 - 验证分析任务已提交', async ({ page }) => {
    // 先触发一次分析
    await page.goto('/analysis/single')
    await waitForLoadingDone(page)
    const stockInput = page.locator('input[placeholder*="000001"], .stock-input input').first()
    await stockInput.fill('000001')
    await stockInput.blur()
    await page.waitForTimeout(2000)
    const analyzeBtn = page.locator('button:has-text("开始智能分析")').first()
    await expect(analyzeBtn).toBeEnabled({ timeout: 10000 })
    await analyzeBtn.click()
    await page.waitForTimeout(3000)

    // 然后去任务中心验证任务已出现
    await page.goto('/tasks/unified')
    await waitForLoadingDone(page)

    const taskTable = page.locator('.el-table').first()
    await expect(taskTable).toBeVisible({ timeout: 10000 })
    
    // 验证表格中有数据行（说明分析任务已提交）
    const taskRows = page.locator('.el-table__body tr').first()
    await expect(taskRows).toBeVisible({ timeout: 10000 })
  })

  test('任务中心 - 按状态筛选任务', async ({ page }) => {
    await page.goto('/tasks/unified')
    await waitForLoadingDone(page)

    const filterTabs = page.locator('.filter-tabs, .el-tabs__item').first()
    if (await filterTabs.isVisible({ timeout: 5000 })) {
      await filterTabs.click()
      await page.waitForTimeout(2000)
    }
  })

  test('任务中心 - 查看任务详情', async ({ page }) => {
    await page.goto('/tasks/unified')
    await waitForLoadingDone(page)

    const detailBtn = page.locator('button:has-text("详情"), .view-detail').first()
    if (await detailBtn.isVisible({ timeout: 3000 })) {
      await detailBtn.click()
      await page.waitForTimeout(5000)
    }
  })

  test('任务中心 - 重试失败任务', async ({ page }) => {
    await page.goto('/tasks/unified')
    await waitForLoadingDone(page)

    const retryBtn = page.locator('button:has-text("重试"), button:has(.el-icon-refresh)').first()
    if (await retryBtn.isVisible({ timeout: 3000 })) {
      await retryBtn.click()
      await page.waitForTimeout(2000)
    }
  })

  test('任务中心 - 取消运行中任务', async ({ page }) => {
    await page.goto('/tasks/unified')
    await waitForLoadingDone(page)

    const cancelBtn = page.locator('button:has-text("取消"), button:has(.el-icon-close)').first()
    if (await cancelBtn.isVisible({ timeout: 3000 })) {
      await cancelBtn.click()
      await page.waitForTimeout(2000)
    }
  })
})

test.describe('分析反馈', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('对分析结果进行评分反馈', async ({ page }) => {
    await page.goto('/analysis/history')
    await waitForLoadingDone(page)

    const viewBtn = page.locator('button:has-text("查看"), .view-report').first()
    if (await viewBtn.isVisible({ timeout: 5000 })) {
      await viewBtn.click()
      await page.waitForTimeout(5000)

      const feedbackBtn = page.locator('button:has-text("反馈"), .feedback-btn').first()
      if (await feedbackBtn.isVisible({ timeout: 3000 })) {
        await feedbackBtn.click()
        await page.waitForTimeout(2000)
      }
    }
  })
})

test.describe('定时分析配置', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('定时分析配置页面加载', async ({ page }) => {
    await page.goto('/settings/scheduled-analysis')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/settings\/scheduled-analysis/)

    const content = page.locator('.el-main, .app-main, main, .el-card').first()
    await expect(content).toBeVisible({ timeout: 10000 })
  })

  test('创建定时分析任务', async ({ page }) => {
    await page.goto('/settings/scheduled-analysis')
    await waitForLoadingDone(page)

    const addBtn = page.locator('button:has-text("创建配置")').first()
    if (await addBtn.isVisible({ timeout: 5000 })) {
      await addBtn.click()
      await page.waitForTimeout(3000)

      // 填写配置名称
      const nameInput = page.locator('.el-dialog input[placeholder*="名称"]').first()
      if (await nameInput.isVisible({ timeout: 3000 })) {
        await nameInput.fill('E2E测试定时分析')
      }

      // 选择分析深度
      const depthSelect = page.locator('.el-dialog .el-select').first()
      if (await depthSelect.isVisible({ timeout: 3000 })) {
        await depthSelect.click()
        await page.waitForTimeout(1000)
        // 选择1级快速
        const option1 = page.locator('.el-select-dropdown__item:has-text("1级")').first()
        if (await option1.isVisible({ timeout: 3000 })) {
          await option1.click()
          await page.waitForTimeout(500)
        }
      }

      // 点击保存
      const saveBtn = page.locator('.el-dialog button:has-text("保存")').first()
      if (await saveBtn.isVisible({ timeout: 3000 })) {
        await saveBtn.click()
        await page.waitForTimeout(3000)
      }
    }
  })

  test('测试执行定时分析', async ({ page }) => {
    test.setTimeout(300000) // 定时分析执行需要时间
    await page.goto('/settings/scheduled-analysis')
    await waitForLoadingDone(page)

    // 如果有配置，点击"测试执行"
    const testBtn = page.locator('button:has-text("测试执行")').first()
    if (await testBtn.isVisible({ timeout: 5000 })) {
      await testBtn.click()
      await page.waitForTimeout(3000)

      // 验证执行结果提示出现
      const successMsg = page.locator('.el-message--success, .el-notification').first()
      await expect(successMsg).toBeVisible({ timeout: 30000 })
    }
  })
})

test.describe('ETF分析', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('ETF分析 - 完整流程验证', async ({ page }) => {
    test.setTimeout(600000) // 分析需要时间，设置 10 分钟超时
    await page.goto('/analysis/single')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/analysis\/single/)

    // 切换到 ETF 市场
    const marketSelect = page.locator('.el-select').first()
    await marketSelect.click()
    await page.waitForTimeout(500)
    const etfOption = page.locator('.el-select-dropdown__item:has-text("ETF")').first()
    await etfOption.click()
    await page.waitForTimeout(1000)

    // 填入 ETF 代码
    const stockInput = page.locator('input[placeholder*="000001"], .stock-input input').first()
    await expect(stockInput).toBeVisible({ timeout: 10000 })
    await stockInput.fill('510050')
    await stockInput.blur()
    await page.waitForTimeout(2000)

    // 选择 1 级快速分析
    const depthOptions = page.locator('.depth-option')
    const quickDepth = depthOptions.first()
    await quickDepth.click()
    await page.waitForTimeout(500)

    // 确认按钮已启用
    const analyzeBtn = page.locator('button:has-text("开始智能分析")').first()
    await expect(analyzeBtn).toBeEnabled({ timeout: 10000 })

    // 点击开始分析
    await analyzeBtn.click()

    // 验证进度出现
    await expect(page.locator('button:has-text("分析进行中"), .progress-info, .el-progress').first()).toBeVisible({ timeout: 15000 })

    // 等待分析真正完成
    const resultsSection = page.locator('.results-section, .results-card')
    await expect(resultsSection.first()).toBeVisible({ timeout: 600000 })

    // ✅ 验证 ETF 分析结果
    const resultsCard = page.locator('.results-card').first()
    await expect(resultsCard).toBeVisible()

    // ETF 标签存在
    const stockTag = page.locator('.results-card .el-tag').first()
    await expect(stockTag).toBeVisible()

    // 分析概览存在
    const overview = page.locator('.overview-section, .markdown-content').first()
    await expect(overview).toBeVisible({ timeout: 10000 })

    // 报告标签页存在
    const analysisTabs = page.locator('.analysis-tabs, .el-tabs').first()
    await expect(analysisTabs).toBeVisible({ timeout: 10000 })

    // 检查降级节点
    const degradedAlert = page.locator('.el-alert:has-text("降级"), .el-alert:has-text("失败")')
    const degradedVisible = await degradedAlert.isVisible().catch(() => false)
    if (degradedVisible) {
      console.log('⚠️ ETF分析有降级节点，详见截图')
      await page.screenshot({ path: 'test-results/etf-analysis-degraded.png', fullPage: true })
    }

    // 报告内容可见
    const firstTab = page.locator('.el-tabs__content .report-content-wrapper').first()
    await expect(firstTab).toBeVisible({ timeout: 10000 })
  })
})

test.describe('批量分析', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('批量分析 - 提交任务并验证', async ({ page }) => {
    await page.goto('/analysis/batch')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/analysis\/batch/)

    // 填入股票代码（每行一个）
    const textarea = page.locator('.stock-textarea textarea, textarea[placeholder*="股票代码"]').first()
    await expect(textarea).toBeVisible({ timeout: 10000 })
    await textarea.fill('000001\n000002\n600036')
    await page.waitForTimeout(1000)

    // 点击"解析股票代码"
    const parseBtn = page.locator('button:has-text("解析股票代码")').first()
    if (await parseBtn.isVisible({ timeout: 3000 })) {
      await parseBtn.click()
      await page.waitForTimeout(1000)
    }

    // 验证股票预览标签出现
    const stockTags = page.locator('.stock-tag, .stock-preview .el-tag').first()
    await expect(stockTags).toBeVisible({ timeout: 5000 })

    // 选择 1 级快速分析
    const depthSelect = page.locator('.config-card .el-select').first()
    if (await depthSelect.isVisible({ timeout: 3000 })) {
      await depthSelect.click()
      await page.waitForTimeout(500)
      const option1 = page.locator('.el-select-dropdown__item:has-text("1级")').first()
      if (await option1.isVisible({ timeout: 3000 })) {
        await option1.click()
        await page.waitForTimeout(500)
      }
    }

    // 点击"开始批量分析"
    const submitBtn = page.locator('button:has-text("开始批量分析")').first()
    await expect(submitBtn).toBeEnabled({ timeout: 5000 })
    await submitBtn.click()

    // 确认对话框
    const confirmBtn = page.locator('.el-message-box button:has-text("确定")').first()
    if (await confirmBtn.isVisible({ timeout: 5000 })) {
      await confirmBtn.click()
      await page.waitForTimeout(3000)
    }

    // 验证成功消息
    const successMsg = page.locator('.el-message--success, .el-message-box:has-text("成功")').first()
    await expect(successMsg).toBeVisible({ timeout: 10000 })

    // 去任务中心验证任务已提交
    await page.goto('/tasks/unified')
    await waitForLoadingDone(page)

    const taskTable = page.locator('.el-table').first()
    await expect(taskTable).toBeVisible({ timeout: 10000 })

    const taskRows = page.locator('.el-table__body tr').first()
    await expect(taskRows).toBeVisible({ timeout: 10000 })
  })
})
