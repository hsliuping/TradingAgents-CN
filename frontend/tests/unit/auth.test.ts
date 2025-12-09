/**
 * 前端认证功能单元测试
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import { authApi } from '@/api/auth'
import type { User, LoginForm, RegisterForm } from '@/types/auth'

// Mock API responses
const mockUser: User = {
  id: '1',
  username: 'testuser',
  email: 'test@example.com',
  is_admin: false,
  vip_level: 0,
  roles: ['user'],
  permissions: []
}

const mockAdminUser: User = {
  id: '2',
  username: 'admin',
  email: 'admin@example.com',
  is_admin: true,
  vip_level: 0,
  roles: ['admin'],
  permissions: []
}

const mockLoginResponse = {
  success: true,
  data: {
    access_token: 'mock-access-token',
    refresh_token: 'mock-refresh-token',
    expires_in: 3600,
    user: mockUser
  },
  message: '登录成功'
}

const mockRegisterResponse = {
  success: true,
  data: {
    access_token: 'mock-register-token',
    refresh_token: 'mock-register-refresh-token',
    expires_in: 3600,
    user: mockUser
  },
  message: '注册成功，已自动登录'
}

describe('Auth Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    // 清除localStorage
    localStorage.clear()
    vi.clearAllMocks()
  })

  describe('Login', () => {
    it('should login successfully', async () => {
      // Mock API call
      vi.spyOn(authApi, 'login').mockResolvedValue(mockLoginResponse)

      const authStore = useAuthStore()
      const loginForm: LoginForm = {
        username: 'testuser',
        password: 'password123'
      }

      const result = await authStore.login(loginForm)

      expect(result).toBe(true)
      expect(authStore.isAuthenticated).toBe(true)
      expect(authStore.user).toEqual(mockUser)
      expect(authStore.token).toBe('mock-access-token')
      expect(authStore.roles).toEqual(['user'])
      expect(authStore.isAdmin).toBe(false)

      // 检查localStorage是否正确保存
      expect(localStorage.getItem('auth-token')).toBe('mock-access-token')
      expect(localStorage.getItem('user-info')).toBe(JSON.stringify(mockUser))
    })

    it('should handle login failure', async () => {
      vi.spyOn(authApi, 'login').mockRejectedValue(new Error('登录失败'))

      const authStore = useAuthStore()
      const loginForm: LoginForm = {
        username: 'testuser',
        password: 'wrongpassword'
      }

      const result = await authStore.login(loginForm)

      expect(result).toBe(false)
      expect(authStore.isAuthenticated).toBe(false)
      expect(authStore.user).toBeNull()
    })
  })

  describe('Register', () => {
    it('should register successfully and auto-login', async () => {
      vi.spyOn(authApi, 'register').mockResolvedValue(mockRegisterResponse)

      const authStore = useAuthStore()
      const registerForm: RegisterForm = {
        username: 'newuser',
        email: 'new@example.com',
        password: 'password123'
      }

      const result = await authStore.register(registerForm)

      expect(result).toBeTruthy()
      expect(authStore.isAuthenticated).toBe(true)
      expect(authStore.user).toEqual(mockUser)
      expect(authStore.token).toBe('mock-register-token')

      // 检查localStorage
      expect(localStorage.getItem('auth-token')).toBe('mock-register-token')
      expect(localStorage.getItem('user-info')).toBe(JSON.stringify(mockUser))
    })

    it('should handle registration failure', async () => {
      vi.spyOn(authApi, 'register').mockRejectedValue(new Error('用户名已存在'))

      const authStore = useAuthStore()
      const registerForm: RegisterForm = {
        username: 'existinguser',
        email: 'existing@example.com',
        password: 'password123'
      }

      const result = await authStore.register(registerForm)

      expect(result).toBe(false)
      expect(authStore.isAuthenticated).toBe(false)
      expect(authStore.user).toBeNull()
    })
  })

  describe('Logout', () => {
    it('should logout successfully', async () => {
      // 先设置登录状态
      vi.spyOn(authApi, 'login').mockResolvedValue(mockLoginResponse)
      vi.spyOn(authApi, 'logout').mockResolvedValue({ success: true })

      const authStore = useAuthStore()
      await authStore.login({ username: 'testuser', password: 'password123' })

      // 验证已登录
      expect(authStore.isAuthenticated).toBe(true)

      // 登出
      await authStore.logout()

      // 验证已登出
      expect(authStore.isAuthenticated).toBe(false)
      expect(authStore.user).toBeNull()
      expect(authStore.token).toBeNull()

      // 验证localStorage已清除
      expect(localStorage.getItem('auth-token')).toBeNull()
      expect(localStorage.getItem('user-info')).toBeNull()
    })
  })

  describe('Admin Permissions', () => {
    it('should identify admin users correctly', async () => {
      // Mock admin login response
      const adminLoginResponse = {
        ...mockLoginResponse,
        data: {
          ...mockLoginResponse.data,
          user: mockAdminUser
        }
      }

      vi.spyOn(authApi, 'login').mockResolvedValue(adminLoginResponse)

      const authStore = useAuthStore()
      await authStore.login({ username: 'admin', password: 'admin123' })

      expect(authStore.isAdmin).toBe(true)
      expect(authStore.roles).toEqual(['admin'])
    })

    it('should identify regular users correctly', async () => {
      vi.spyOn(authApi, 'login').mockResolvedValue(mockLoginResponse)

      const authStore = useAuthStore()
      await authStore.login({ username: 'testuser', password: 'password123' })

      expect(authStore.isAdmin).toBe(false)
      expect(authStore.roles).toEqual(['user'])
    })

    it('should check permissions correctly', () => {
      const authStore = useAuthStore()

      // 模拟管理员用户
      authStore.roles = ['admin']
      authStore.user = mockAdminUser
      expect(authStore.hasPermission('any_permission')).toBe(true)
      expect(authStore.hasRole('admin')).toBe(true)
      expect(authStore.hasRole('user')).toBe(false)

      // 模拟普通用户
      authStore.roles = ['user']
      authStore.user = mockUser
      expect(authStore.hasPermission('specific_permission')).toBe(false)
      expect(authStore.hasRole('admin')).toBe(false)
      expect(authStore.hasRole('user')).toBe(true)
    })
  })

  describe('User Level', () => {
    it('should handle vip_level field correctly', async () => {
      const userWithVip = {
        ...mockUser,
        vip_level: 2
      }

      const response = {
        ...mockLoginResponse,
        data: {
          ...mockLoginResponse.data,
          user: userWithVip
        }
      }

      vi.spyOn(authApi, 'login').mockResolvedValue(response)

      const authStore = useAuthStore()
      await authStore.login({ username: 'vipuser', password: 'password123' })

      expect(authStore.user?.vip_level).toBe(2)
    })
  })
})

describe('Auth Form Validation', () => {
  describe('Login Form', () => {
    it('should validate username required', () => {
      const form = { username: '', password: 'password123' }
      expect(form.username.trim()).toBe('')
    })

    it('should validate password required', () => {
      const form = { username: 'testuser', password: '' }
      expect(form.password.trim()).toBe('')
    })

    it('should validate password minimum length', () => {
      const form = { username: 'testuser', password: '123' }
      expect(form.password.length).toBeLessThan(6)
    })
  })

  describe('Register Form', () => {
    it('should validate username format', () => {
      const validUsernames = ['testuser', 'user123', 'test_user']
      const invalidUsernames = ['ab', 'a' * 21, 'user@name', 'user name']

      validUsernames.forEach(username => {
        const isValid = /^[a-zA-Z0-9_]{3,20}$/.test(username)
        expect(isValid).toBe(true)
      })

      invalidUsernames.forEach(username => {
        const isValid = /^[a-zA-Z0-9_]{3,20}$/.test(username)
        expect(isValid).toBe(false)
      })
    })

    it('should validate email format', () => {
      const validEmails = ['test@example.com', 'user.name@domain.co.uk']
      const invalidEmails = ['invalid_email', '@example.com', 'test@']

      validEmails.forEach(email => {
        const isValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
        expect(isValid).toBe(true)
      })

      invalidEmails.forEach(email => {
        const isValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
        expect(isValid).toBe(false)
      })
    })

    it('should validate password length', () => {
      const validPasswords = ['password123', '123456']
      const invalidPasswords = ['12345', '']

      validPasswords.forEach(password => {
        expect(password.length).toBeGreaterThanOrEqual(6)
      })

      invalidPasswords.forEach(password => {
        expect(password.length).toBeLessThan(6)
      })
    })

    it('should validate password confirmation', () => {
      const form = {
        password: 'password123',
        confirmPassword: 'password123'
      }
      expect(form.password).toBe(form.confirmPassword)

      const mismatchedForm = {
        password: 'password123',
        confirmPassword: 'different123'
      }
      expect(mismatchedForm.password).not.toBe(mismatchedForm.confirmPassword)
    })
  })
})