/**
 * 认证功能端到端测试
 */

import { test, expect } from '@playwright/test'

test.describe('Authentication Flow', () => {
  test.beforeEach(async ({ page }) => {
    // 清理localStorage
    await page.evaluate(() => {
      localStorage.clear()
    })
  })

  test('should show login and register tabs', async ({ page }) => {
    await page.goto('/login')

    // 检查页面标题
    await expect(page).toHaveTitle(/登录.*A股-智能体/)

    // 检查登录Tab
    await expect(page.locator('text=登录')).toBeVisible()
    await expect(page.locator('input[placeholder="请输入用户名"]')).toBeVisible()
    await expect(page.locator('input[placeholder="请输入密码"]')).toBeVisible()

    // 切换到注册Tab
    await page.click('text=注册')
    await expect(page.locator('input[placeholder="请输入用户名 (3-20位字母数字下划线)"]')).toBeVisible()
    await expect(page.locator('input[placeholder="请输入邮箱地址"]')).toBeVisible()
    await expect(page.locator('input[placeholder="请输入密码 (至少6位)"]')).toBeVisible()
    await expect(page.locator('input[placeholder="请再次确认密码"]')).toBeVisible()
  })

  test('should register a new user successfully', async ({ page }) => {
    await page.goto('/login')
    await page.click('text=注册')

    // 填写注册表单
    const timestamp = Date.now()
    const username = `testuser${timestamp}`
    const email = `test${timestamp}@example.com`
    const password = 'testpass123'

    await page.fill('input[placeholder="请输入用户名 (3-20位字母数字下划线)"]', username)
    await page.fill('input[placeholder="请输入邮箱地址"]', email)
    await page.fill('input[placeholder="请输入密码 (至少6位)"]', password)
    await page.fill('input[placeholder="请再次确认密码"]', password)

    // Mock API响应
    await page.route('/api/auth/register', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          data: {
            access_token: 'mock-token',
            refresh_token: 'mock-refresh-token',
            expires_in: 3600,
            user: {
              id: '1',
              username: username,
              email: email,
              is_admin: false,
              vip_level: 0
            }
          },
          message: '注册成功，已自动登录'
        })
      })
    })

    // 提交注册表单
    await page.click('button:has-text("注册")')

    // 验证成功消息
    await expect(page.locator('text=注册成功，已自动登录')).toBeVisible()

    // 验证重定向到dashboard
    await expect(page).toHaveURL('/dashboard')
  })

  test('should validate registration form', async ({ page }) => {
    await page.goto('/login')
    await page.click('text=注册')

    // 测试用户名验证
    await page.fill('input[placeholder="请输入用户名 (3-20位字母数字下划线)"]', 'ab')
    await page.fill('input[placeholder="请输入邮箱地址"]', 'test@example.com')
    await page.fill('input[placeholder="请输入密码 (至少6位)"]', 'testpass123')
    await page.fill('input[placeholder="请再次确认密码"]', 'testpass123')
    await page.click('button:has-text("注册")')

    // 应该显示错误信息
    await expect(page.locator('text=用户名长度为3-20位')).toBeVisible()

    // 测试邮箱验证
    await page.fill('input[placeholder="请输入用户名 (3-20位字母数字下划线)"]', 'validuser')
    await page.fill('input[placeholder="请输入邮箱地址"]', 'invalid-email')
    await page.click('button:has-text("注册")')

    // 应该显示邮箱格式错误
    await expect(page.locator('text=请输入正确的邮箱格式')).toBeVisible()

    // 测试密码长度验证
    await page.fill('input[placeholder="请输入用户名 (3-20位字母数字下划线)"]', 'validuser')
    await page.fill('input[placeholder="请输入邮箱地址"]', 'valid@example.com')
    await page.fill('input[placeholder="请输入密码 (至少6位)"]', '123')
    await page.click('button:has-text("注册")')

    // 应该显示密码长度错误
    await expect(page.locator('text=密码至少6位')).toBeVisible()
  })

  test('should validate password confirmation', async ({ page }) => {
    await page.goto('/login')
    await page.click('text=注册')

    await page.fill('input[placeholder="请输入用户名 (3-20位字母数字下划线)"]', 'testuser')
    await page.fill('input[placeholder="请输入邮箱地址"]', 'test@example.com')
    await page.fill('input[placeholder="请输入密码 (至少6位)"]', 'password123')
    await page.fill('input[placeholder="请再次确认密码"]', 'different123')
    await page.click('button:has-text("注册")')

    // 应该显示密码不匹配错误
    await expect(page.locator('text=两次输入密码不一致')).toBeVisible()
  })

  test('should handle login successfully', async ({ page }) => {
    await page.goto('/login')

    // Mock登录API响应
    await page.route('/api/auth/login', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          data: {
            access_token: 'mock-login-token',
            refresh_token: 'mock-refresh-token',
            expires_in: 3600,
            user: {
              id: '1',
              username: 'testuser',
              email: 'test@example.com',
              is_admin: false,
              vip_level: 0
            }
          },
          message: '登录成功'
        })
      })
    })

    // 填写登录表单
    await page.fill('input[placeholder="请输入用户名"]', 'testuser')
    await page.fill('input[placeholder="请输入密码"]', 'password123')
    await page.click('button:has-text("登录")')

    // 验证登录成功
    await expect(page.locator('text=登录成功')).toBeVisible()
    await expect(page).toHaveURL('/dashboard')
  })

  test('should handle login failure', async ({ page }) => {
    await page.goto('/login')

    // Mock登录失败响应
    await page.route('/api/auth/login', async route => {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: '用户名或密码错误'
        })
      })
    })

    // 填写登录表单
    await page.fill('input[placeholder="请输入用户名"]', 'wronguser')
    await page.fill('input[placeholder="请输入密码"]', 'wrongpass')
    await page.click('button:has-text("登录")')

    // 验证错误消息
    await expect(page.locator('text=用户名或密码错误')).toBeVisible()
    // 应该仍在登录页面
    await expect(page).toHaveURL('/login')
  })

  test('should handle duplicate registration', async ({ page }) => {
    await page.goto('/login')
    await page.click('text=注册')

    const username = 'existinguser'
    const email = 'existing@example.com'

    // Mock用户名已存在响应
    await page.route('/api/auth/register', async route => {
      await route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: '用户名已存在'
        })
      })
    })

    // 填写注册表单
    await page.fill('input[placeholder="请输入用户名 (3-20位字母数字下划线)"]', username)
    await page.fill('input[placeholder="请输入邮箱地址"]', email)
    await page.fill('input[placeholder="请输入密码 (至少6位)"]', 'testpass123')
    await page.fill('input[placeholder="请再次确认密码"]', 'testpass123')
    await page.click('button:has-text("注册")')

    // 验证错误消息
    await expect(page.locator('text=用户名已存在')).toBeVisible()
    // 应该仍在登录页面
    await expect(page).toHaveURL('/login')
  })

  test('should redirect authenticated user from login to dashboard', async ({ page }) => {
    // 模拟已登录用户
    await page.goto('/login')
    await page.evaluate(() => {
      localStorage.setItem('auth-token', 'mock-token')
      localStorage.setItem('user-info', JSON.stringify({
        id: '1',
        username: 'testuser',
        email: 'test@example.com',
        is_admin: false,
        vip_level: 0
      }))
    })

    await page.reload()

    // 应该重定向到dashboard
    await expect(page).toHaveURL('/dashboard')
  })

  test('should prevent access to admin routes for normal users', async ({ page }) => {
    // 模拟普通用户登录
    await page.evaluate(() => {
      localStorage.setItem('auth-token', 'mock-token')
      localStorage.setItem('user-info', JSON.stringify({
        id: '1',
        username: 'normaluser',
        email: 'user@example.com',
        is_admin: false,
        vip_level: 0
      }))
    })

    // 尝试访问管理员路由
    await page.goto('/settings/config')

    // 应该重定向到dashboard并显示权限不足消息
    await expect(page).toHaveURL('/dashboard')
    await expect(page.locator('text=您没有权限访问此页面')).toBeVisible()
  })

  test('should allow admin users to access all routes', async ({ page }) => {
    // 模拟管理员登录
    await page.evaluate(() => {
      localStorage.setItem('auth-token', 'mock-token')
      localStorage.setItem('user-info', JSON.stringify({
        id: '1',
        username: 'admin',
        email: 'admin@example.com',
        is_admin: true,
        vip_level: 0
      }))
    })

    // Mock获取用户信息的API
    await page.route('/api/auth/me', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          data: {
            id: '1',
            username: 'admin',
            email: 'admin@example.com',
            is_admin: true,
            vip_level: 0,
            roles: ['admin']
          }
        })
      })
    })

    // 访问管理员路由
    await page.goto('/settings/config')

    // 应该能正常访问
    await expect(page.locator('text=配置管理')).toBeVisible()
  })
})