/**
 * SSE 流式请求工具
 *
 * 统一封装 fetch + ReadableStream 的 SSE 流式请求,处理:
 * - 认证头自动注入(JWT / App Token / 京东云模式)
 * - 401 统一处理
 * - 空闲超时
 * - SSE 事件解析(event: / data: 格式)
 * - AbortController 管理
 *
 * 用法:
 *   const controller = fetchSSE('/api/xxx/stream', {
 *     method: 'POST',
 *     body: { ... },
 *     onEvent: (eventType, data) => { ... },
 *     onDone: (data) => { ... },
 *     onError: (msg) => { ... },
 *   })
 *   // 取消: controller.abort()
 */

import { isJdyunMode } from '@/utils/config'

export interface SSEOptions {
  method?: 'GET' | 'POST'
  body?: any
  /** 空闲超时(毫秒),默认 90 秒 */
  idleTimeout?: number
  /** 收到 SSE 事件时回调 */
  onEvent?: (eventType: string, data: any) => void
  /** 收到 done 事件或流正常结束时回调 */
  onDone?: (data?: any) => void
  /** 出错时回调(HTTP错误/超时/网络错误) */
  onError?: (message: string) => void
  /** 用户主动取消时回调 */
  onAbort?: () => void
  /** 自定义请求头 */
  headers?: Record<string, string>
  /** 是否跳过认证头(公开接口) */
  skipAuth?: boolean
}

/**
 * 发起 SSE 流式请求
 * @returns AbortController, 调用 .abort() 可取消请求
 */
export function fetchSSE(path: string, options: SSEOptions = {}): AbortController {
  const controller = new AbortController()
  const baseUrl = import.meta.env.VITE_API_BASE_URL || ''
  const {
    method = 'POST',
    body,
    idleTimeout = 90_000,
    onEvent,
    onDone,
    onError,
    onAbort,
    headers: customHeaders,
    skipAuth = false,
  } = options

  // 组装请求头
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...customHeaders,
  }

  if (!skipAuth) {
    const token = localStorage.getItem('auth-token') || ''
    const appToken = localStorage.getItem('app-token') || ''
    // 京东云模式: 不手动加 Authorization,由网关注入 Basic Auth
    if (token && !isJdyunMode()) {
      headers['Authorization'] = `Bearer ${token}`
    }
    if (appToken) {
      headers['X-App-Token'] = appToken
    }
  }

  let idleTimer: ReturnType<typeof setTimeout> | null = null
  let receivedTerminalEvent = false

  const resetIdle = () => {
    if (idleTimer) clearTimeout(idleTimer)
    idleTimer = setTimeout(() => {
      onError?.('连接超时：服务器长时间未响应，请重试')
      controller.abort()
    }, idleTimeout)
  }

  const clearIdle = () => {
    if (idleTimer) {
      clearTimeout(idleTimer)
      idleTimer = null
    }
  }

  // 解析单个 SSE 事件块
  const parseEventBlock = (part: string): { eventType: string; data: any } | null => {
    if (!part.trim() || part.startsWith(': ')) return null

    let eventType = ''
    const dataLines: string[] = []

    for (const rawLine of part.split('\n')) {
      const line = rawLine.replace(/\r$/, '')
      if (line.startsWith('event: ')) {
        eventType = line.slice(7)
      } else if (line.startsWith('data: ')) {
        dataLines.push(line.slice(6))
      }
    }

    const eventData = dataLines.join('\n')
    if (!eventData) return null

    try {
      return { eventType, data: JSON.parse(eventData) }
    } catch {
      return null
    }
  }

  fetch(`${baseUrl}${path}`, {
    method,
    headers,
    credentials: 'include',
    body: body ? JSON.stringify(body) : undefined,
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        if (response.status === 401) {
          onError?.('登录已过期，请重新登录')
        } else {
          onError?.(`HTTP ${response.status}: ${response.statusText}`)
        }
        return
      }

      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      resetIdle()

      try {
        // eslint-disable-next-line no-constant-condition
        while (true) {
          const { done, value } = await reader.read()
          if (done) {
            buffer += decoder.decode()
            break
          }

          resetIdle()
          buffer += decoder.decode(value, { stream: true })
          const parts = buffer.split('\n\n')
          buffer = parts.pop() || ''

          for (const part of parts) {
            const parsed = parseEventBlock(part)
            if (!parsed) continue

            const { eventType, data } = parsed

            if (eventType === 'done') {
              receivedTerminalEvent = true
              clearIdle()
              onDone?.(data)
            } else if (eventType === 'error') {
              receivedTerminalEvent = true
              clearIdle()
              onError?.(data.message || '未知错误')
            } else {
              onEvent?.(eventType, data)
            }
          }
        }

        // 处理 buffer 中剩余的内容
        if (buffer.trim()) {
          const parsed = parseEventBlock(buffer)
          if (parsed) {
            const { eventType, data } = parsed
            if (eventType === 'done') {
              receivedTerminalEvent = true
              onDone?.(data)
            } else if (eventType === 'error') {
              receivedTerminalEvent = true
              onError?.(data.message || '未知错误')
            } else {
              onEvent?.(eventType, data)
            }
          }
        }

        // 流正常结束但没收到 done 事件
        if (!receivedTerminalEvent && !controller.signal.aborted) {
          onDone?.()
        }
      } finally {
        clearIdle()
        reader.releaseLock()
      }
    })
    .catch((err) => {
      clearIdle()
      if (err.name === 'AbortError') {
        onAbort?.()
      } else {
        onError?.(err.message || '网络请求失败，请检查网络连接后重试')
      }
    })

  return controller
}
