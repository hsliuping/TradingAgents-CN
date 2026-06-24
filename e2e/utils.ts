/**
 * E2E 测试通用工具函数
 */
import type { Page } from '@playwright/test'

/**
 * 默认测试账号
 */
export const TEST_USER = {
  username: 'admin',
  password: 'admin123',
}

/**
 * 登录流程：访问登录页，填写表单，勾选协议，提交登录
 * 登录成功后自动跳转到 dashboard
 */
export async function login(page: Page): Promise<void> {
  await page.goto('/login')

  // 等待登录表单加载
  await page.waitForSelector('.login-card', { timeout: 10000 })

  // 填写用户名和密码
  await page.locator('.el-form-item').filter({ hasText: '用户名' }).locator('input').fill(TEST_USER.username)
  await page.locator('.el-form-item').filter({ hasText: '密码' }).locator('input').fill(TEST_USER.password)

  // 勾选"我已阅读并同意"协议复选框
  const agreementCheckbox = page.locator('.agreement-check .el-checkbox')
  await agreementCheckbox.click()
  await page.waitForTimeout(500)

  // 点击登录按钮
  await page.locator('button:has-text("登录")').first().click()

  // 等待跳转到 dashboard 或其他已认证页面
  await page.waitForURL(url => !url.toString().includes('/login'), { timeout: 15000 })
}

/**
 * 确保已登录，如果未登录则先登录
 */
export async function ensureLoggedIn(page: Page): Promise<void> {
  const token = await page.evaluate(() => localStorage.getItem('auth-token'))
  if (!token) {
    await login(page)
  }
}

/**
 * 等待 Element Plus 的 loading 遮罩消失
 */
export async function waitForLoadingDone(page: Page): Promise<void> {
  const loadingMask = page.locator('.el-loading-mask')
  if (await loadingMask.isVisible({ timeout: 1000 }).catch(() => false)) {
    await loadingMask.waitFor({ state: 'hidden', timeout: 30000 })
  }
}

/**
 * 等待 Element Plus 的表格加载完成
 */
export async function waitForTableLoaded(page: Page): Promise<void> {
  await page.waitForSelector('table', { timeout: 10000 })
  await waitForLoadingDone(page)
}

/**
 * 获取 Element Plus 的消息提示文本
 */
export async function getElMessage(page: Page): Promise<string | null> {
  const message = page.locator('.el-message__content')
  if (await message.isVisible({ timeout: 2000 }).catch(() => false)) {
    return message.textContent()
  }
  return null
}

/**
 * 选择股票代码（自动完成场景）
 */
export async function selectStock(page: Page, stockCode: string): Promise<void> {
  const input = page.locator('input[placeholder*="000001"], input[placeholder*="股票"], input[placeholder*="代码"], .stock-input input').first()
  await input.fill(stockCode)
  await page.waitForTimeout(1500)
  
  const dropdownOption = page.locator('.el-select-dropdown__item, .el-autocomplete-suggestion li').first()
  if (await dropdownOption.isVisible({ timeout: 3000 })) {
    await dropdownOption.click()
  }
}

/**
 * 等待模态框关闭
 */
export async function waitForModalClose(page: Page): Promise<void> {
  const modal = page.locator('.el-modal')
  if (await modal.isVisible({ timeout: 1000 })) {
    await modal.waitFor({ state: 'hidden', timeout: 10000 })
  }
}

/**
 * 点击确认按钮（处理 Element Plus 对话框）
 */
export async function clickConfirm(page: Page): Promise<void> {
  const confirmBtn = page.locator('.el-dialog__footer button:has-text("确定"), .el-dialog__footer button[type="primary"]').first()
  if (await confirmBtn.isVisible({ timeout: 3000 })) {
    await confirmBtn.click()
    await waitForModalClose(page)
  }
}

/**
 * 点击取消按钮（处理 Element Plus 对话框）
 */
export async function clickCancel(page: Page): Promise<void> {
  const cancelBtn = page.locator('.el-dialog__footer button:has-text("取消")').first()
  if (await cancelBtn.isVisible({ timeout: 3000 })) {
    await cancelBtn.click()
    await waitForModalClose(page)
  }
}

/**
 * 等待侧边栏菜单展开
 */
export async function waitForSidebarMenu(page: Page): Promise<void> {
  await page.waitForSelector('.el-menu, .sidebar-menu', { timeout: 10000 })
}

/**
 * 导航到指定页面（通过侧边栏）
 */
export async function navigateBySidebar(page: Page, menuText: string): Promise<void> {
  await waitForSidebarMenu(page)
  const menuItem = page.locator(`.el-menu-item:has-text("${menuText}"), .sidebar-item:has-text("${menuText}")`).first()
  if (await menuItem.isVisible({ timeout: 5000 })) {
    await menuItem.click()
    await waitForLoadingDone(page)
  }
}

/**
 * 等待表格数据加载完成
 */
export async function waitForTableData(page: Page): Promise<void> {
  await page.waitForSelector('table tbody tr', { timeout: 15000 })
  await waitForLoadingDone(page)
}

/**
 * 验证页面标题
 */
export async function verifyPageTitle(page: Page, title: string): Promise<void> {
  const pageTitle = page.locator('h1, .page-title, .el-page-header__title').first()
  await expect(pageTitle).toHaveText(title, { timeout: 10000 })
}

/**
 * 随机等待（模拟用户思考时间）
 */
export async function randomWait(minMs: number = 500, maxMs: number = 2000): Promise<void> {
  const waitTime = Math.floor(Math.random() * (maxMs - minMs + 1)) + minMs
  await new Promise(resolve => setTimeout(resolve, waitTime))
}
