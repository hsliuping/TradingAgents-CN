import axios from 'axios'
import type { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import router from '@/router'
import { isTokenValid } from '@/utils/auth'

declare module 'axios' {
  export interface AxiosRequestConfig {
    skipAuth?: boolean
    skipAuthError?: boolean
    skipErrorHandler?: boolean
    showLoading?: boolean
    loadingText?: string
    retryCount?: number
    retryDelay?: number
    _retry?: boolean
    __retryCount?: number
  }
}

// API响应接口
export interface ApiResponse<T = any> {
  success: boolean
  data: T
  message: string
  code?: number
  timestamp?: string
  request_id?: string
}

// 请求配置接口
export interface RequestConfig extends AxiosRequestConfig {
  skipAuth?: boolean
  skipAuthError?: boolean  // 跳过 401 错误的自动处理（用于登录等接口）
  skipErrorHandler?: boolean
  showLoading?: boolean
  loadingText?: string
  retryCount?: number  // 重试次数
  retryDelay?: number  // 重试延迟（毫秒）
  _retry?: boolean
  __retryCount?: number
}

// 消息去重：记录最近显示的错误消息
const recentMessages = new Map<string, number>()
const MESSAGE_THROTTLE_TIME = 3000 // 3秒内相同消息不重复显示

// 401 错误处理标志（避免多个请求同时触发登录跳转）
let isHandling401 = false

// Token 刷新单飞控制，避免并发 401 触发刷新风暴
let refreshTokenPromise: Promise<boolean> | null = null

const maskTokenFingerprint = (token?: string | null): string => {
  if (!token) {
    return 'none'
  }

  if (token.length <= 16) {
    return token
  }

  return `${token.substring(0, 8)}...${token.substring(token.length - 8)}`
}

const ensureSingleFlightTokenRefresh = (authStore: any) => {
  if (!refreshTokenPromise) {
    refreshTokenPromise = authStore.refreshAccessToken()
      .finally(() => {
        refreshTokenPromise = null
      })
  }
  return refreshTokenPromise
}

// 显示错误消息（带去重）
const showErrorMessage = (message: string) => {
  const now = Date.now()
  const lastTime = recentMessages.get(message)

  // 如果3秒内已经显示过相同消息，则跳过
  if (lastTime && now - lastTime < MESSAGE_THROTTLE_TIME) {
    console.log('⏭️ 跳过重复消息:', message)
    return
  }

  // 记录消息显示时间
  recentMessages.set(message, now)

  // 清理过期的消息记录（保持Map不会无限增长）
  if (recentMessages.size > 50) {
    const entries = Array.from(recentMessages.entries())
    entries.sort((a, b) => a[1] - b[1])
    // 删除最旧的25条记录
    entries.slice(0, 25).forEach(([key]) => recentMessages.delete(key))
  }

  ElMessage.error(message)
}

// 处理 401 错误（带防抖）
const handle401Error = (authStore: any, message: string = '登录已过期，请重新登录') => {
  // 如果正在处理 401 错误，跳过
  if (isHandling401) {
    console.log('⏭️ 正在处理 401 错误，跳过重复处理')
    return
  }

  isHandling401 = true

  // 清除认证信息并跳转到登录页
  console.log('🔒 处理 401 错误：清除认证信息并跳转登录页')
  authStore.clearAuthInfo()
  router.push('/login')
  showErrorMessage(message)

  // 3秒后重置标志
  setTimeout(() => {
    isHandling401 = false
  }, 3000)
}

// 创建axios实例
const createAxiosInstance = (): AxiosInstance => {
  const instance = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL || '',
    timeout: 600000, // 增加超时时间到600秒（10分钟，用于长时间操作如交易复盘分析）
    withCredentials: true,  // 🔥 重要：允许发送和接收 Cookie（用于 Session 认证）
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'no-cache',  // 禁用客户端缓存
      'Pragma': 'no-cache'
    }
  })

  // 请求拦截器
  instance.interceptors.request.use(
    async (config: any) => {
      const authStore = useAuthStore()
      const appStore = useAppStore()

      // 添加认证头（总是覆盖为最新Token；支持localStorage兜底，避免早期请求丢Token）
      if (!config.skipAuth) {
        const storedToken = authStore.token || localStorage.getItem('auth-token')
        const shouldTryRefresh = Boolean(
          storedToken
          && !isTokenValid(storedToken)
          && authStore.refreshToken
          && !String(config.url || '').includes('/auth/refresh')
        )

        if (shouldTryRefresh) {
          console.log('🔄 请求发送前检测到 access token 已过期，先尝试刷新', {
            url: config.url,
            staleTokenFingerprint: maskTokenFingerprint(storedToken),
            refreshTokenFingerprint: maskTokenFingerprint(authStore.refreshToken),
          })
          const refreshed = await ensureSingleFlightTokenRefresh(authStore)
          if (!refreshed) {
            console.warn('⚠️ 请求发送前刷新 token 失败，将继续按原有 401 流程处理')
          }
        }

        const token = authStore.token || localStorage.getItem('auth-token')
        if (token) {
          config.headers = config.headers || {}
          config.headers.Authorization = `Bearer ${token}`
        }

        // 添加 App Token 头（用于许可证验证）
        const appToken = localStorage.getItem('app-token')
        if (appToken) {
          config.headers = config.headers || {}
          config.headers['X-App-Token'] = appToken
        }
      }

      // 添加请求ID
      config.headers['X-Request-ID'] = generateRequestId()

      // 添加语言头
      config.headers['Accept-Language'] = appStore.language

      // 显示加载状态
      if (config.showLoading) {
        appStore.setLoading(true, 0)
      }

      // 端点兼容守卫：阻止/修正误用的 /api/stocks/quote（缺少路径参数 {code}）
      try {
        const rawUrl = String(config.url || '')
        const pathOnly = rawUrl.split('?')[0].replace(/\/+$|^\s+|\s+$/g, '')
        if (pathOnly === '/api/stocks/quote' || pathOnly === '/api/stocks/quote/') {
          const code = (config.params && (config.params.code || (config as any).params?.stock_code)) ?? undefined
          if (code) {
            const codeStr = String(code)
            config.url = `/api/stocks/${codeStr}/quote`
            if (config.params) {
              delete (config.params as any).code
              delete (config.params as any).stock_code
            }
          } else {
            console.error('❌ 误用端点: /api/stocks/quote 缺少 code')
            return Promise.reject(new Error('前端误用端点：缺少 code，请改用 /api/stocks/{code}/quote'))
          }
        }

        const base = String(config.baseURL || '')
        const urlStr = String(config.url || '')
        const baseHasApi = /\/api\/?$/.test(base)
        const urlStartsWithApi = urlStr.startsWith('/api/') || urlStr === '/api'
        if (baseHasApi && urlStartsWithApi) {
          config.url = urlStr.replace(/^\/api(\/)?/, '/$1')
        }

        // 统一去除 /api/* 路径末尾斜杠，避免 FastAPI 默认 307 重定向
        const finalUrl = String(config.url || '')
        if (finalUrl.startsWith('/api/') && finalUrl.length > 5) {
          config.url = finalUrl.replace(/\/+(\?|$)/, '$1')
        }
      } catch (e) {
        console.warn('端点兼容检查异常', e)
      }

      return config
    },
    (error) => {
      console.error('❌ 请求拦截器错误:', error)
      return Promise.reject(error)
    }
  )

  // 响应拦截器
  instance.interceptors.response.use(
    (response: AxiosResponse) => {
      const appStore = useAppStore()
      const authStore = useAuthStore()
      const config = response.config as RequestConfig

      // 隐藏加载状态
      if (config.showLoading) {
        appStore.setLoading(false)
      }

      // 检查业务状态码
      const data = response.data as ApiResponse
      if (data && typeof data === 'object' && 'success' in data) {
        if (!data.success) {
          // 检查是否是认证错误（优先处理，不依赖 skipErrorHandler）
          const code = data.code
          if (code === 401 || code === 40101 || code === 40102 || code === 40103) {
            // 如果请求标记为跳过认证错误处理（如登录请求），不自动处理
            if (!config.skipAuthError) {
              console.log('🔒 业务错误：认证失败 (HTTP 200)')
              handle401Error(authStore, data.message || '登录已过期，请重新登录')
            }
            return Promise.reject(new Error(data.message || '认证失败'))
          }

          // 其他业务错误
          if (!config.skipErrorHandler) {
            handleBusinessError(data)
            return Promise.reject(new Error(data.message || '请求失败'))
          }
        }
      }

      // 返回 response.data 而不是 response，这样调用方可以直接访问 ApiResponse
      return response.data
    },
    async (error) => {
      const appStore = useAppStore()
      const authStore = useAuthStore()
      const config = error.config as RequestConfig

      // 隐藏加载状态
      if (config?.showLoading) {
        appStore.setLoading(false)
      }

      // 处理HTTP状态码错误
      if (error.response) {
        const { status, data } = error.response

        switch (status) {
          case 401:
            // 如果是refresh请求本身失败，不要再次尝试刷新（避免无限循环）
            if (config?.url?.includes('/auth/refresh')) {
              console.error('❌ Refresh token请求失败')
              if (config?.skipAuthError) {
                ;(error as any).__skipGlobalAuthRedirect = true
                break
              }
              handle401Error(authStore, '登录已过期，请重新登录')
              break
            }

            // 未授权时优先尝试刷新 token，即使 skipAuthError=true 也不应跳过刷新。
            if (!config?.skipAuth && authStore.refreshToken && !config?._retry) {
              try {
                console.log('🔄 401错误，尝试刷新token...')
                config._retry = true
                const success = await ensureSingleFlightTokenRefresh(authStore)
                if (success) {
                  console.log('✅ Token刷新成功，重试原请求')
                  // 重新发送原请求
                  return instance.request(config)
                } else {
                  console.log('❌ Token刷新失败')
                }
              } catch (refreshError) {
                console.error('❌ Token刷新异常:', refreshError)
              }
            }

            // 如果请求标记为跳过认证错误处理（如局部可降级接口），不要自动登出/跳转。
            if (config?.skipAuthError) {
              ;(error as any).__skipGlobalAuthRedirect = true
              break
            }

            // 清除认证信息并跳转到登录页
            handle401Error(authStore, '登录已过期，请重新登录')
            break

          case 403:
            showErrorMessage('权限不足，无法访问该资源')
            break

          case 400:
            // 参数错误，显示详细的错误信息
            if (!config?.skipErrorHandler) {
              const message = data?.detail || data?.message || error.message || '请求参数错误'
              showErrorMessage(message)
            }
            break

          case 404:
            if (!config?.skipErrorHandler) {
              showErrorMessage('请求的资源不存在')
            }
            break

          case 429:
            showErrorMessage('请求过于频繁，请稍后重试')
            break

          case 500:
            // 优先显示后端返回的详细错误信息
            if (!config?.skipErrorHandler) {
              const message = data?.detail || data?.message || '服务器内部错误，请稍后重试'
              showErrorMessage(message)
              // 将详细错误信息附加到错误对象上，供组件使用
              error.message = message
            }
            break

          case 502:
          case 503:
          case 504:
            showErrorMessage('服务暂时不可用，请稍后重试')
            break

          default:
            if (!config?.skipErrorHandler) {
              const message = data?.detail || data?.message || error.message || '网络请求失败'
              showErrorMessage(message)
            }
        }
      } else if (error.code === 'ECONNABORTED') {
        console.error('🔍 [REQUEST] 请求超时错误:', {
          code: error.code,
          message: error.message,
          timeout: config?.timeout,
          url: config?.url
        })

        // 尝试重试
        if (await shouldRetry(config, error)) {
          return retryRequest(instance, config)
        }

        showErrorMessage('请求超时，请检查网络连接')
      } else if (error.message === 'Network Error') {
        console.error('🔍 [REQUEST] 网络连接错误:', {
          message: error.message,
          code: error.code,
          url: config?.url,
          baseURL: config?.baseURL
        })

        // 尝试重试
        if (await shouldRetry(config, error)) {
          return retryRequest(instance, config)
        }

        showErrorMessage('网络连接失败，请检查网络设置')
      } else if (error.message.includes('Failed to fetch')) {
        console.error('🔍 [REQUEST] Fetch失败错误:', {
          message: error.message,
          code: error.code,
          url: config?.url,
          baseURL: config?.baseURL
        })

        // 尝试重试
        if (await shouldRetry(config, error)) {
          return retryRequest(instance, config)
        }

        showErrorMessage('网络请求失败，请检查服务器连接')
      } else if (!config?.skipErrorHandler) {
        console.error('🔍 [REQUEST] 其他错误:', {
          message: error.message,
          code: error.code,
          name: error.name,
          url: config?.url
        })
        showErrorMessage(error.message || '未知错误')
      }

      return Promise.reject(error)
    }
  )

  return instance
}

// 处理业务错误
const handleBusinessError = (data: ApiResponse) => {
  const { code, message } = data
  const authStore = useAuthStore()

  switch (code) {
    case 401:
    case 40101:  // 未授权
    case 40102:  // Token 无效
    case 40103:  // Token 过期
      console.log('🔒 业务错误：认证失败')
      handle401Error(authStore, message || '登录已过期，请重新登录')
      break
    case 40001:
      showErrorMessage('参数错误')
      break
    case 403:
    case 40003:
      showErrorMessage('权限不足')
      break
    case 40004:
      showErrorMessage('资源不存在')
      break
    case 40005:
      showErrorMessage('操作失败')
      break
    case 50001:
      showErrorMessage('服务器错误')
      break
    default:
      if (message) {
        showErrorMessage(message)
      }
  }
}

// 生成请求ID
const generateRequestId = (): string => {
  return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
}

// 判断是否应该重试
const shouldRetry = async (config: RequestConfig | undefined, error: any): Promise<boolean> => {
  if (!config) return false

  // 获取重试配置（默认重试 2 次）
  let retryCount = 2
  if (config.retryCount !== undefined) {
    retryCount = config.retryCount
  }
  const currentRetry = (config as any).__retryCount || 0

  // 如果已经重试过指定次数，不再重试
  if (currentRetry >= retryCount) {
    console.log(`🔄 已达到最大重试次数 (${retryCount})，停止重试`)
    return false
  }

  // 只对网络错误和超时错误重试
  const shouldRetryError =
    error.code === 'ECONNABORTED' ||
    error.message === 'Network Error' ||
    error.message.includes('Failed to fetch') ||
    (error.response && [502, 503, 504].includes(error.response.status))

  return shouldRetryError
}

// 重试请求
const retryRequest = async (instance: AxiosInstance, config: RequestConfig): Promise<any> => {
  const currentRetry = (config as any).__retryCount || 0
  // 使用显式的默认值处理
  let retryDelay = 1000
  if (config.retryDelay !== undefined) {
    retryDelay = config.retryDelay
  }

  // 增加重试计数
  (config as any).__retryCount = currentRetry + 1

  console.log(`🔄 第 ${currentRetry + 1} 次重试请求: ${config.url}`)

  // 延迟后重试
  await new Promise(resolve => setTimeout(resolve, retryDelay * (currentRetry + 1)))

  return instance.request(config)
}

// 创建请求实例
const request = createAxiosInstance()

// 测试API连接
export const testApiConnection = async (): Promise<boolean> => {
  try {
    await request.get('/api/health', {
      timeout: 5000,
      skipErrorHandler: true
    } as any)

    return true
  } catch (error: any) {
    console.error('❌ API连接测试失败:', error.code || error.message)

    return false
  }
}

// 请求方法封装
export class ApiClient {
  // GET请求
  static async get<T = any>(
    url: string,
    params?: any,
    config?: RequestConfig
  ): Promise<ApiResponse<T>> {
    // 响应拦截器已经返回 response.data，所以这里直接返回
    return await request.get(url, { params, ...config })
  }

  // POST请求
  static async post<T = any>(
    url: string,
    data?: any,
    config?: RequestConfig
  ): Promise<ApiResponse<T>> {
    // 响应拦截器已经返回 response.data，所以这里直接返回
    return await request.post(url, data, config)
  }

  // PUT请求
  static async put<T = any>(
    url: string,
    data?: any,
    config?: RequestConfig
  ): Promise<ApiResponse<T>> {
    // 响应拦截器已经返回 response.data，所以这里直接返回
    return await request.put(url, data, config)
  }

  // DELETE请求
  static async delete<T = any>(
    url: string,
    config?: RequestConfig
  ): Promise<ApiResponse<T>> {
    // 响应拦截器已经返回 response.data，所以这里直接返回
    return await request.delete(url, config)
  }

  // PATCH请求
  static async patch<T = any>(
    url: string,
    data?: any,
    config?: RequestConfig
  ): Promise<ApiResponse<T>> {
    // 响应拦截器已经返回 response.data，所以这里直接返回
    return await request.patch(url, data, config)
  }

  // 上传文件
  static async upload<T = any>(
    url: string,
    file: File,
    onProgress?: (progress: number) => void,
    config?: RequestConfig
  ): Promise<ApiResponse<T>> {
    const formData = new FormData()
    formData.append('file', file)

    // 响应拦截器已经返回 response.data，所以这里直接返回
    return await request.post(url, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          onProgress(progress)
        }
      },
      ...config
    })
  }

  // 下载文件
  static async download(
    url: string,
    filename?: string,
    config?: RequestConfig
  ): Promise<void> {
    // 对于 blob 响应，响应拦截器返回的就是 blob 数据
    const blobData = await request.get(url, {
      responseType: 'blob',
      ...config
    })

    const blob = new Blob([blobData as unknown as BlobPart])
    const downloadUrl = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = downloadUrl
    link.download = filename || 'download'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(downloadUrl)
  }
}

export default request
export { request }
