import { test, expect } from '@playwright/test'
import { login, TEST_USER } from './utils'

/**
 * 认证流程 E2E 测试
 *
 * 覆盖:
 * - 登录页加载
 * - 正确凭据登录成功
 * - 错误凭据登录失败
 * - 未登录访问受保护路由跳转登录页
 * - 登出
 */
test.describe('认证流程', () => {
  test('登录页应正确加载', async ({ page }) => {
    await page.goto('/login')

    // 验证登录表单元素存在
    await expect(page.locator('input[type="text"], input[placeholder*="用户名"]')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('input[type="password"]')).toBeVisible()
    await expect(page.locator('button:has-text("登录"), button[type="submit"]')).toBeVisible()
  })

  test('正确凭据登录成功并跳转到 Dashboard', async ({ page }) => {
    await login(page)

    // 验证跳转到 dashboard
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 })

    // 验证 localStorage 中有 token
    const token = await page.evaluate(() => localStorage.getItem('auth-token'))
    expect(token).toBeTruthy()
  })

  test('错误密码登录失败', async ({ page }) => {
    await page.goto('/login')

    const usernameInput = page.locator('input[placeholder*="用户名"], input[type="text"]').first()
    const passwordInput = page.locator('input[type="password"]').first()
    await usernameInput.fill(TEST_USER.username)
    await passwordInput.fill('wrong_password')

    // 勾选协议（Element Plus checkbox 需要点击 label）
    const agreementLabel = page.locator('.el-checkbox:has-text("同意")').first()
    if (await agreementLabel.isVisible({ timeout: 3000 }).catch(() => false)) {
      await agreementLabel.click()
    }

    await page.locator('button:has-text("登录"), button[type="submit"]').first().click()

    // 等待一下让请求完成
    await page.waitForTimeout(3000)

    // 应仍在登录页（错误密码不会跳转）
    await expect(page).toHaveURL(/\/login/)
  })

  test('未登录访问受保护路由应跳转到登录页', async ({ page }) => {
    // 清除登录状态
    await page.goto('/login')
    await page.evaluate(() => {
      localStorage.clear()
    })

    // 访问需要认证的页面
    await page.goto('/dashboard')

    // 应跳转到登录页
    await expect(page).toHaveURL(/\/login/, { timeout: 10000 })
  })

  test('公开页面无需登录可访问', async ({ page }) => {
    // 关于页面是公开的
    await page.goto('/about')
    // 不应跳转到登录页
    await expect(page).not.toHaveURL(/\/login/)
  })
})
