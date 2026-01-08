import { defineStore } from 'pinia'
import { useStorage } from '@vueuse/core'
import { authApi } from '@/api/auth'
import type { User, LoginForm, RegisterForm } from '@/types/auth'

export interface AuthState {
  // 认证状态
  isAuthenticated: boolean
  token: string | null
  refreshToken: string | null
  
  // 用户信息
  user: User | null
  
  // 权限信息
  permissions: string[]
  roles: string[]
  
  // 登录状态
  loginLoading: boolean
  
  // 重定向路径
  redirectPath: string
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => {
    const token = useStorage('auth-token', null).value || null
    const refreshToken = useStorage('refresh-token', null).value || null

    // 验证token格式
    const isValidToken = (token: string | null): boolean => {
      if (!token || typeof token !== 'string') return false
      // 检查是否是mock token（开发时可能设置的测试token）
      if (token === 'mock-token' || token.startsWith('mock-')) {
        console.warn('⚠️ 检测到mock token，将被清除:', token)
        return false
      }
      // JWT token应该有3个部分，用.分隔
      return token.split('.').length === 3
    }

    const validToken = isValidToken(token) ? token : null
    const validRefreshToken = isValidToken(refreshToken) ? refreshToken : null

    // 如果token无效，清除相关数据
    if (!validToken || !validRefreshToken) {
      console.log('🧹 清除无效的认证信息')
      localStorage.removeItem('auth-token')
      localStorage.removeItem('refresh-token')
      localStorage.removeItem('user-info')
    }

    return {
      isAuthenticated: !!validToken,
      token: validToken,
      refreshToken: validRefreshToken,

      user: validToken ? (useStorage('user-info', null).value || null) : null,

      permissions: [],
      roles: [],

      loginLoading: false,
      redirectPath: '/'
    }
  },

  getters: {
    // 用户头像：优先使用用户设置的头像，否则返回 undefined 使用默认图标
    userAvatar(): string | undefined {
      return this.user?.avatar || undefined
    },
    
    // 用户显示名称
    userDisplayName(): string {
      return this.user?.username || this.user?.email || '未知用户'
    },
    
    // 是否为管理员
    isAdmin(): boolean {
      return this.roles.includes('admin')
    },
    
    // 检查权限
    hasPermission(): (permission: string) => boolean {
      return (permission: string) => {
        return this.permissions.includes(permission) || this.isAdmin
      }
    },
    
    // 检查角色
    hasRole(): (role: string) => boolean {
      return (role: string) => {
        return this.roles.includes(role)
      }
    },
    
    // 用户统计信息
    userStats(): Record<string, number> {
      return {
        totalAnalyses: this.user?.total_analyses || 0,
        successfulAnalyses: this.user?.successful_analyses || 0,
        failedAnalyses: this.user?.failed_analyses || 0,
        dailyQuota: this.user?.daily_quota || 1000,
        concurrentLimit: this.user?.concurrent_limit || 3
      }
    }
  },

  actions: {
    // 设置认证信息
    setAuthInfo(token: string, refreshToken?: string, user?: User) {
      this.token = token
      this.isAuthenticated = true

      if (refreshToken) {
        this.refreshToken = refreshToken
      }

      if (user) {
        this.user = user
      }

      // 手动保存到localStorage（确保持久化）
      localStorage.setItem('auth-token', token)
      if (refreshToken) {
        localStorage.setItem('refresh-token', refreshToken)
      }
      if (user) {
        localStorage.setItem('user-info', JSON.stringify(user))
      }

      // 设置API请求头
      this.setAuthHeader(token)

      console.log('✅ 认证信息已保存:', {
        token: token ? '已设置' : '未设置',
        refreshToken: refreshToken ? '已设置' : '未设置',
        user: user ? user.username : '未设置',
        isAuthenticated: this.isAuthenticated
      })
    },
    
    // 清除认证信息
    clearAuthInfo() {
      this.token = null
      this.refreshToken = null
      this.user = null
      this.isAuthenticated = false
      this.permissions = []
      this.roles = []

      // 清除API请求头
      this.setAuthHeader(null)

      // 清除本地存储
      localStorage.removeItem('auth-token')
      localStorage.removeItem('refresh-token')
      localStorage.removeItem('user-info')
    },

    // 跳转到登录页
    redirectToLogin() {
      // 避免在非浏览器环境中使用router
      if (typeof window !== 'undefined') {
        // 使用window.location进行跳转，避免router依赖问题
        const currentPath = window.location.pathname
        if (currentPath !== '/login') {
          console.log('🔄 跳转到登录页...')
          window.location.href = '/login'
        }
      }
    },
    
    // 设置API请求头
    setAuthHeader(token: string | null) {
      // 这里会在API模块中设置Authorization头
      // 具体实现在api/request.ts中
    },
    
    // 登录
    async login(loginForm: LoginForm) {
      // 防止重复登录请求
      if (this.loginLoading) {
        console.log('⏭️ 登录请求进行中，跳过重复调用')
        return false
      }

      try {
        this.loginLoading = true

        const response = await authApi.login(loginForm)

        if (response.success) {
          const { access_token, refresh_token, user } = response.data

          // 设置认证信息
          this.setAuthInfo(access_token, refresh_token, user)

          // 开源版admin用户拥有所有权限
          this.permissions = ['*']
          this.roles = ['admin']

          // 同步用户偏好设置到 appStore
          this.syncUserPreferencesToAppStore()

          // 启动 token 自动刷新定时器
          const { setupTokenRefreshTimer } = await import('@/utils/auth')
          setupTokenRefreshTimer()

          // 不在这里显示成功消息，由调用方显示
          return true
        } else {
          // 不在这里显示错误消息，由调用方显示
          return false
        }
      } catch (error: any) {
        console.error('登录失败:', error)
        // 不在这里显示错误消息，由调用方显示
        return false
      } finally {
        this.loginLoading = false
      }
    },
    
    // 注册
    async register(registerForm: RegisterForm) {
      try {
        const response = await authApi.register(registerForm)
        
        if (response.success) {
          ElMessage.success('注册成功，请登录')
          return true
        } else {
          ElMessage.error(response.message || '注册失败')
          return false
        }
      } catch (error: any) {
        console.error('注册失败:', error)
        ElMessage.error(error.message || '注册失败，请重试')
        return false
      }
    },
    
    // 登出
    async logout() {
      try {
        // 调用登出API
        await authApi.logout()
      } catch (error) {
        console.error('登出API调用失败:', error)
      } finally {
        // 无论API调用是否成功，都清除本地认证信息
        this.clearAuthInfo()
        console.log('✅ 用户已登出，认证信息已清除')

        // 跳转到登录页
        this.redirectToLogin()
      }
    },
    
    // 刷新Token
    async refreshAccessToken() {
      try {
        console.log('🔄 开始刷新Token...')

        if (!this.refreshToken) {
          console.warn('❌ 没有refresh token，无法刷新')
          throw new Error('没有刷新令牌')
        }

        console.log('📝 Refresh token信息:', {
          length: this.refreshToken.length,
          prefix: this.refreshToken.substring(0, 10),
          isValid: this.refreshToken.split('.').length === 3
        })

        // 验证refresh token格式
        if (this.refreshToken.split('.').length !== 3) {
          console.error('❌ Refresh token格式无效')
          throw new Error('Refresh token格式无效')
        }

        const response = await authApi.refreshToken(this.refreshToken)
        console.log('📨 刷新响应:', response)

        if (response.success) {
          const { access_token, refresh_token } = response.data
          console.log('✅ Token刷新成功')
          this.setAuthInfo(access_token, refresh_token)
          return true
        } else {
          console.error('❌ Token刷新失败:', response.message)
          throw new Error(response.message || 'Token刷新失败')
        }
      } catch (error: any) {
        console.error('❌ Token刷新异常:', error)

        // 如果是网络错误或服务器错误，不要立即清除认证信息
        if (error.code === 'NETWORK_ERROR' || error.response?.status >= 500) {
          console.warn('⚠️ 网络或服务器错误，保留认证信息')
          return false
        }

        // 其他错误（如401），清除认证信息
        console.log('🧹 清除认证信息并跳转登录')
        this.clearAuthInfo()
        this.redirectToLogin()

        return false
      }
    },
    
    // 获取用户信息
    async fetchUserInfo() {
      try {
        console.log('📡 正在获取用户信息...')
        const response = await authApi.getUserInfo()

        if (response.success) {
          this.user = response.data
          console.log('✅ 用户信息获取成功:', this.user?.username)

          // 同步用户偏好设置到 appStore
          this.syncUserPreferencesToAppStore()

          return true
        } else {
          console.warn('⚠️ 获取用户信息失败:', response.message)
          throw new Error(response.message || '获取用户信息失败')
        }
      } catch (error) {
        console.error('❌ 获取用户信息失败:', error)
        // 重新抛出错误，让上层处理
        throw error
      }
    },
    
    // 开源版不需要权限检查，admin拥有所有权限
    async fetchUserPermissions() {
      this.permissions = ['*']
      this.roles = ['admin']
      return true
    },
    
    // 更新用户信息
    async updateUserInfo(userInfo: Partial<User>) {
      try {
        const response = await authApi.updateUserInfo(userInfo)

        if (response.success) {
          this.user = { ...this.user!, ...response.data }

          // 同步用户偏好设置到 appStore
          this.syncUserPreferencesToAppStore()

          ElMessage.success('用户信息更新成功')
          return true
        } else {
          ElMessage.error(response.message || '更新失败')
          return false
        }
      } catch (error: any) {
        console.error('更新用户信息失败:', error)
        ElMessage.error(error.message || '更新失败，请重试')
        return false
      }
    },
    
    // 同步用户偏好设置到 appStore
    syncUserPreferencesToAppStore() {
      if (!this.user?.preferences) return

      // 动态导入 appStore 避免循环依赖
      import('./app').then(({ useAppStore }) => {
        const appStore = useAppStore()
        const prefs = this.user!.preferences

        // 同步主题设置
        if (prefs.ui_theme) {
          appStore.setTheme(prefs.ui_theme as 'light' | 'dark' | 'auto')
        }

        // 同步侧边栏宽度
        if (prefs.sidebar_width) {
          appStore.setSidebarWidth(prefs.sidebar_width)
        }

        // 同步语言设置
        if (prefs.language) {
          appStore.setLanguage(prefs.language as 'zh-CN' | 'en-US')
        }

        // 同步分析偏好
        if (prefs.default_market || prefs.default_depth || prefs.auto_refresh !== undefined || prefs.refresh_interval) {
          appStore.updatePreferences({
            defaultMarket: prefs.default_market as any,
            defaultDepth: prefs.default_depth as any,
            autoRefresh: prefs.auto_refresh,
            refreshInterval: prefs.refresh_interval
          })
        }

        console.log('✅ 用户偏好设置已同步到 appStore')
      })
    },

    // 修改密码
    async changePassword(oldPassword: string, newPassword: string) {
      try {
        const response = await authApi.changePassword({
          old_password: oldPassword,
          new_password: newPassword
        })

        if (response.success) {
          ElMessage.success('密码修改成功')
          return true
        } else {
          ElMessage.error(response.message || '密码修改失败')
          return false
        }
      } catch (error: any) {
        console.error('修改密码失败:', error)
        ElMessage.error(error.message || '修改密码失败，请重试')
        return false
      }
    },
    
    // 设置重定向路径
    setRedirectPath(path: string) {
      this.redirectPath = path
    },
    
    // 获取并清除重定向路径
    getAndClearRedirectPath(): string {
      const path = this.redirectPath || '/dashboard'
      this.redirectPath = '/dashboard'
      return path
    },
    
    // 检查认证状态
    async checkAuthStatus() {
      if (this.token) {
        try {
          console.log('🔍 检查token有效性...')
          // 验证token是否有效
          const valid = await this.fetchUserInfo()
          if (valid) {
            this.isAuthenticated = true
            await this.fetchUserPermissions()
            console.log('✅ 认证状态验证成功')
          } else {
            // Token无效，尝试刷新
            console.log('🔄 Token无效，尝试刷新...')
            await this.refreshAccessToken()
          }
        } catch (error) {
          console.error('❌ 检查认证状态失败:', error)
          // 如果是网络错误或超时，不清除认证信息，只是标记为未认证
          if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
            console.warn('⚠️ 网络超时，保留认证信息但标记为未认证状态')
            this.isAuthenticated = false
          } else {
            // 其他错误则清除认证信息
            this.clearAuthInfo()
            this.redirectToLogin()
          }
        }
      } else {
        console.log('📝 没有token，跳过认证检查')
      }
    }
  }
})
