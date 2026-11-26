import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'

import zhCn from 'element-plus/es/locale/lang/zh-cn'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'

import App from './App.vue'
import router from './router'
import { setupGlobalComponents } from './components'
import { setupDeliverableDownloadInterceptor } from './utils/deliverableDownload'
import { useAuthStore } from './stores/auth'
import { useAppStore } from './stores/app'
import './styles/index.scss'
import './styles/dark-theme.scss'

// 创建应用实例
const app = createApp(App)

// 注册Element Plus图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// 使用插件
const pinia = createPinia()
app.use(pinia)
app.use(router)
// 设置全局中文 locale（Element Plus）
dayjs.locale('zh-cn')
app.use(ElementPlus, {
  size: 'default',
  zIndex: 3000,
  locale: zhCn,
  // 配置消息提示
  message: {
    max: 3, // 最多同时显示3个消息
    grouping: true, // 启用消息分组，相同内容的消息不会重复显示
    duration: 3000, // 默认显示时长3秒
  },
})

// 注册全局组件
setupGlobalComponents(app)

// 智能助手交付物下载拦截（历史消息中的下载链接浏览器导航不带 JWT，全局委托改走 fetch+blob）
setupDeliverableDownloadInterceptor()

// 全局错误处理
app.config.errorHandler = (err, _vm, info) => {
  console.error('全局错误:', err, info)

  if (err && typeof err === 'object') {
    const error = err as any
    // 仅凭明确的状态码/业务码判定认证错误。
    // 此前还按消息文本匹配（含 "Token" 字样即判定），任何组件抛出带
    // Token 字样的普通报错都会误触发"清认证 + 跳登录页"。
    const authErrorCode = Number(error.code)
    const isAuthError =
      !error.__skipGlobalAuthRedirect && (
        error.response?.status === 401 ||
        authErrorCode === 401 ||
        [40101, 40102, 40103].includes(authErrorCode)
      )

    if (isAuthError) {
      console.log('🔒 全局错误处理：检测到认证错误，跳转登录页')
      const authStore = useAuthStore()
      authStore.clearAuthInfo()
      router.push('/login')
    }
  }

  // 这里可以集成错误监控服务
}

// 全局警告处理
app.config.warnHandler = (msg, _vm, trace) => {
  console.warn('全局警告:', msg, trace)
}

// 初始化认证状态
const initApp = async () => {
  const authStore = useAuthStore()
  const appStore = useAppStore()

  try {

    console.log('🔄 初始化应用状态...')

    // 应用主题
    appStore.applyTheme()
    console.log('🎨 主题已应用:', appStore.theme)

    // 设置网络状态监听
    window.addEventListener('online', () => {
      console.log('🌐 网络已连接')
      appStore.setOnlineStatus(true)
      appStore.checkApiConnection()
    })

    window.addEventListener('offline', () => {
      console.log('📱 网络已断开')
      appStore.setOnlineStatus(false)
      appStore.setApiConnected(false)
    })

    // 检查API连接状态
    console.log('🔍 检查API连接状态...')
    const apiConnected = await appStore.checkApiConnection()

    if (apiConnected) {
      await appStore.fetchApiVersion()
    }

    if (apiConnected) {
      console.log('✅ API连接正常，检查认证状态...')
      // 检查本地存储的认证信息（设置较短的超时时间）
      const checkPromise = authStore.checkAuthStatus()
      const timeoutPromise = new Promise((_, reject) => {
        setTimeout(() => reject(new Error('认证检查超时')), 5000) // 5秒超时
      })

      await Promise.race([checkPromise, timeoutPromise])
      console.log('✅ 认证状态初始化完成')
    } else {
      console.log('⚠️ API连接失败，跳过认证检查')
    }
  } catch (error: unknown) {
    console.warn('⚠️ 应用初始化失败，但应用将继续启动:', error)
    // 如果是网络错误，不影响应用启动
    if ((error as any)?.code === 'ECONNABORTED' || (error as any)?.message?.includes('timeout')) {
      console.log('📱 离线模式：应用将在没有后端连接的情况下启动')
    }
  } finally {
    // 只要本地存在 token 就启动自动刷新定时器（含弱网/API 不可达场景：
    // 此前 apiConnected=false 时定时器不启动，token 过期后没有任何主动
    // 补救，只能等下一个 API 请求被动触发刷新，引发页面弹跳）
    if (authStore.isAuthenticated) {
      try {
        const { setupTokenRefreshTimer } = await import('./utils/auth')
        setupTokenRefreshTimer()
      } catch (e) {
        console.warn('启动 Token 刷新定时器失败:', e)
      }
    }
    // 无论认证状态如何，都挂载应用
    app.mount('#app')
    console.log('🚀 应用已挂载')
  }
}

// 启动应用
initApp()

// 开发环境下的调试信息
if (import.meta.env.DEV) {
  console.log('🚀 TradingAgents-CN v3.0.0 前端应用已启动')
  console.log('📊 当前环境:', import.meta.env.MODE)
  console.log('🔗 API地址:', import.meta.env.VITE_API_BASE_URL || '/api')
}
