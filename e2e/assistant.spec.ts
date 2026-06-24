import { test, expect } from '@playwright/test'
import { login, waitForLoadingDone } from './utils'

test.describe('智能助手', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('智能助手页面加载', async ({ page }) => {
    await page.goto('/assistant')
    await waitForLoadingDone(page)

    await expect(page).toHaveURL(/\/assistant/)

    // 页面标题
    const pageTitle = page.locator('h1:has-text("智能助手")')
    await expect(pageTitle).toBeVisible({ timeout: 10000 })

    // 顶部操作按钮
    const newThreadBtn = page.locator('button:has-text("新主题")')
    await expect(newThreadBtn).toBeVisible({ timeout: 5000 })

    // 输入区域
    const inputArea = page.locator('.input-area')
    await expect(inputArea).toBeVisible({ timeout: 5000 })
  })

  test('智能助手 - 快速对话', async ({ page }) => {
    test.setTimeout(120000) // 2分钟超时
    await page.goto('/assistant')
    await waitForLoadingDone(page)

    // 1. 创建新主题
    const newThreadBtn = page.locator('button:has-text("新主题")').first()
    await newThreadBtn.click()
    await page.waitForTimeout(1000)

    // 如果有对话框，填写主题名称
    const dialogInput = page.locator('.el-message-box__input input, .el-message-box input').first()
    if (await dialogInput.isVisible({ timeout: 3000 })) {
      await dialogInput.fill('E2E测试对话')
      // 确认创建（按钮文字是"创建"）
      const confirmBtn = page.locator('.el-message-box button:has-text("创建")').first()
      await confirmBtn.click()
      await page.waitForTimeout(2000)
    }

    // 2. 确保有选中主题，发送按钮启用
    // 尝试选择左侧树中的第一个主题
    const firstTreeNode = page.locator('.thread-tree .el-tree-node').first()
    await firstTreeNode.click()
    await page.waitForTimeout(1000)

    // 3. 输入问题
    const textarea = page.locator('.input-area textarea').first()
    await expect(textarea).toBeVisible({ timeout: 10000 })
    await textarea.fill('你好，请简单介绍一下你自己')
    await page.waitForTimeout(500)

    // 4. 点击发送
    const sendBtn = page.locator('.send-btn').first()
    await expect(sendBtn).toBeEnabled({ timeout: 5000 })
    await sendBtn.click()

    // 5. 等待助手回复（流式输出）
    // 用户消息出现
    const userMsg = page.locator('.message-user').first()
    await expect(userMsg).toBeVisible({ timeout: 30000 })

    // 等待助手回复
    const assistantMsg = page.locator('.message-assistant').first()
    await expect(assistantMsg).toBeVisible({ timeout: 60000 })

    // 6. 验证回复有内容
    const assistantContent = assistantMsg.locator('.message-text, .markdown-content').first()
    await expect(assistantContent).toBeVisible({ timeout: 10000 })
    const contentText = await assistantContent.textContent()
    expect(contentText?.length).toBeGreaterThan(10)
  })

  test('智能助手 - 主题列表', async ({ page }) => {
    await page.goto('/assistant')
    await waitForLoadingDone(page)

    // 显示主题栏
    const showThreadBtn = page.locator('button:has-text("显示主题栏")').first()
    if (await showThreadBtn.isVisible({ timeout: 3000 })) {
      await showThreadBtn.click()
      await page.waitForTimeout(1000)
    }

    // 主题树或空状态
    const threadTree = page.locator('.thread-tree, .el-empty').first()
    await expect(threadTree).toBeVisible({ timeout: 5000 })
  })

  test('智能助手 - 助手设置弹窗', async ({ page }) => {
    await page.goto('/assistant')
    await waitForLoadingDone(page)

    // 点击助手设置
    const settingsBtn = page.locator('button:has-text("助手设置")').first()
    await settingsBtn.click()
    await page.waitForTimeout(1000)

    // 设置对话框出现（标题为"助手设置"的弹窗）
    const dialog = page.locator('.el-dialog:has-text("助手设置"), .el-drawer:has-text("助手设置")').first()
    await expect(dialog).toBeVisible({ timeout: 5000 })

    // 关闭对话框
    const closeBtn = page.locator('.el-dialog__close, .el-drawer__close-btn').first()
    if (await closeBtn.isVisible({ timeout: 3000 })) {
      await closeBtn.click()
    }
  })
})