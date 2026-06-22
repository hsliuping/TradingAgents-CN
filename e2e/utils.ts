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
  await page.waitForSelector('input[placeholder*="用户名"], input[type="text"]', { timeout: 10000 })

  // 填写用户名和密码
  const usernameInput = page.locator('input[placeholder*="用户名"], input[type="text"]').first()
  const passwordInput = page.locator('input[type="password"]').first()
  await usernameInput.fill(TEST_USER.username)
  await passwordInput.fill(TEST_USER.password)

  // 勾选用户协议复选框（页面上有两个checkbox：记住我、同意协议）
  // Element Plus 的 checkbox 需要点击 label 或 span
  // 第二个 checkbox 是"同意协议"
  const agreementLabel = page.locator('.el-checkbox:has-text("同意")').first()
  if (await agreementLabel.isVisible({ timeout: 3000 }).catch(() => false)) {
    await agreementLabel.click()
  } else {
    // 降级：直接点击第二个checkbox的input
    const checkboxes = page.locator('.el-checkbox__input input[type="checkbox"]')
    const count = await checkboxes.count()
    if (count >= 2) {
      await checkboxes.nth(1).click({ force: true })
    }
  }

  // 点击登录按钮
  const loginButton = page.locator('button:has-text("登录"), button[type="submit"]').first()
  await loginButton.click()

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
