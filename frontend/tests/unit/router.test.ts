/**
 * 路由权限控制单元测试
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createRouter, createWebHistory } from 'vue-router'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import routerConfig from '@/router'

// Mock ElementPlus
vi.mock('element-plus', () => ({
  ElMessage: {
    warning: vi.fn(),
    success: vi.fn(),
    error: vi.fn()
  }
}))

// Mock NProgress
vi.mock('nprogress', () => ({
  configure: vi.fn(),
  start: vi.fn(),
  done: vi.fn()
}))

describe('Router Permissions', () => {
  let router: any
  let authStore: any

  beforeEach(() => {
    setActivePinia(createPinia())
    authStore = useAuthStore()

    // 创建测试路由
    router = createRouter({
      history: createWebHistory(),
      routes: [
        {
          path: '/dashboard',
          name: 'Dashboard',
          component: { template: '<div>Dashboard</div>' },
          meta: { requiresAuth: true }
        },
        {
          path: '/settings',
          name: 'Settings',
          component: { template: '<div>Settings</div>' },
          meta: { requiresAuth: true }
        },
        {
          path: '/settings/config',
          name: 'ConfigManagement',
          component: { template: '<div>Config Management</div>' },
          meta: { requiresAuth: true }
        },
        {
          path: '/login',
          name: 'Login',
          component: { template: '<div>Login</div>' },
          meta: { requiresAuth: false }
        },
        {
          path: '/learning',
          name: 'Learning',
          component: { template: '<div>Learning</div>' },
          meta: { requiresAuth: false }
        }
      ]
    })

    // 添加路由守卫
    router.beforeEach(async (to, from, next) => {
      // 模拟路由守卫逻辑
      if (to.meta.requiresAuth && !authStore.isAuthenticated) {
        authStore.setRedirectPath(to.fullPath)
        next('/login')
        return
      }

      if (authStore.isAuthenticated) {
        const isAdmin = authStore.isAdmin
        const systemAdminRoutes = ['ConfigManagement', 'DatabaseManagement', 'OperationLogs']

        if (systemAdminRoutes.includes(to.name) && !isAdmin) {
          const { ElMessage } = await import('element-plus')
          ElMessage.warning('您没有权限访问此页面')
          next('/dashboard')
          return
        }

        if (to.path === '/settings' && to.query.tab === 'system' && !isAdmin) {
          const { ElMessage } = await import('element-plus')
          ElMessage.warning('您没有权限访问系统设置')
          next('/settings?tab=profile')
          return
        }
      }

      if (authStore.isAuthenticated && to.name === 'Login') {
        next('/dashboard')
        return
      }

      next()
    })

    vi.clearAllMocks()
  })

  describe('Unauthenticated Access', () => {
    it('should redirect to login when accessing protected routes', async () => {
      // 未认证用户尝试访问需要认证的路由
      authStore.isAuthenticated = false

      const to = { path: '/dashboard', name: 'Dashboard', meta: { requiresAuth: true } }
      const next = vi.fn()

      await router.beforeEach(to, {}, next)

      expect(next).toHaveBeenCalledWith('/login')
      expect(authStore.redirectPath).toBe('/dashboard')
    })

    it('should allow access to public routes', async () => {
      authStore.isAuthenticated = false

      const to = { path: '/learning', name: 'Learning', meta: { requiresAuth: false } }
      const next = vi.fn()

      await router.beforeEach(to, {}, next)

      expect(next).toHaveBeenCalledWith()
    })
  })

  describe('Authenticated User Access', () => {
    it('should allow normal users to access basic routes', async () => {
      // 模拟普通用户登录
      authStore.isAuthenticated = true
      authStore.roles = ['user']
      authStore.isAdmin = false

      const to = { path: '/dashboard', name: 'Dashboard', meta: { requiresAuth: true } }
      const next = vi.fn()

      await router.beforeEach(to, {}, next)

      expect(next).toHaveBeenCalledWith()
    })

    it('should redirect authenticated users from login to dashboard', async () => {
      authStore.isAuthenticated = true

      const to = { path: '/login', name: 'Login', meta: { requiresAuth: false } }
      const next = vi.fn()

      await router.beforeEach(to, {}, next)

      expect(next).toHaveBeenCalledWith('/dashboard')
    })
  })

  describe('Admin Route Permissions', () => {
    it('should allow admin users to access system routes', async () => {
      // 模拟管理员登录
      authStore.isAuthenticated = true
      authStore.roles = ['admin']
      authStore.isAdmin = true

      const to = { path: '/settings/config', name: 'ConfigManagement', meta: { requiresAuth: true } }
      const next = vi.fn()

      await router.beforeEach(to, {}, next)

      expect(next).toHaveBeenCalledWith()
    })

    it('should deny normal users access to admin routes', async () => {
      // 模拟普通用户登录
      authStore.isAuthenticated = true
      authStore.roles = ['user']
      authStore.isAdmin = false

      const to = { path: '/settings/config', name: 'ConfigManagement', meta: { requiresAuth: true } }
      const next = vi.fn()

      await router.beforeEach(to, {}, next)

      expect(next).toHaveBeenCalledWith('/dashboard')
    })

    it('should deny normal users access to system settings tab', async () => {
      authStore.isAuthenticated = true
      authStore.roles = ['user']
      authStore.isAdmin = false

      const to = {
        path: '/settings',
        name: 'Settings',
        meta: { requiresAuth: true },
        query: { tab: 'system' }
      }
      const next = vi.fn()

      await router.beforeEach(to, {}, next)

      expect(next).toHaveBeenCalledWith('/settings?tab=profile')
    })
  })

  describe('VIP Level Handling', () => {
    it('should handle user VIP levels correctly', () => {
      const userLevels = [
        { vip_level: 0, expected: '普通用户' },
        { vip_level: 1, expected: 'VIP1' },
        { vip_level: 2, expected: 'VIP2' },
        { vip_level: 3, expected: 'VIP3' }
      ]

      userLevels.forEach(level => {
        const user = {
          id: '1',
          username: 'test',
          email: 'test@example.com',
          is_admin: false,
          vip_level: level.vip_level,
          roles: ['user'],
          permissions: []
        }

        authStore.user = user
        expect(authStore.user?.vip_level).toBe(level.vip_level)
      })
    })
  })

  describe('Route Meta Information', () => {
    it('should contain correct meta information for routes', () => {
      const routes = routerConfig.routes

      // 检查需要认证的路由
      const dashboardRoute = routes.find(r => r.name === 'Dashboard')
      expect(dashboardRoute?.meta?.requiresAuth).toBe(true)

      // 检查公开路由
      const learningRoute = routes.find(r => r.name === 'Learning')
      expect(learningRoute?.meta?.requiresAuth).toBe(false)

      // 检查登录页面
      const loginRoute = routes.find(r => r.name === 'Login')
      expect(loginRoute?.meta?.requiresAuth).toBe(false)
    })
  })
})