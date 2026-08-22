/**
 * WebSocket 连接工具
 *
 * 统一封装 WebSocket 连接,处理:
 * - 认证: JWT token / 京东云模式(网关注入)
 * - 自动重连(指数退避)
 * - 心跳检测
 * - 消息自动 JSON 解析
 *
 * 用法:
 *   const ws = createWebSocket('/api/ws/xxx', {
 *     onOpen: () => { ... },
 *     onMessage: (data) => { ... },
 *     onError: (err) => { ... },
 *     onClose: () => { ... },
 *     autoReconnect: true,
 *   })
 *   ws.send({ type: 'ping' })
 *   ws.close()
 */

import { isJdyunMode } from '@/utils/config'

export interface CreateWebSocketOptions {
  /** 连接成功回调 */
  onOpen?: () => void
  /** 收到消息回调(已 JSON 解析) */
  onMessage?: (data: any) => void
  /** 连接错误回调 */
  onError?: (error: Event) => void
  /** 连接关闭回调 */
  onClose?: (event: CloseEvent) => void
  /** 是否自动重连,默认 true */
  autoReconnect?: boolean
  /** 最大重连次数,默认 5 */
  maxReconnectAttempts?: number
  /** 初始重连延迟(毫秒),默认 1000 */
  initialReconnectDelay?: number
  /** 最大重连延迟(毫秒),默认 30000 */
  maxReconnectDelay?: number
  /** 心跳间隔(毫秒),默认 30000,设为 0 禁用 */
  heartbeatInterval?: number
  /** 心跳消息内容,默认 { type: 'ping' } */
  heartbeatMessage?: any
  /** 自定义子协议 */
  protocols?: string | string[]
  /** 是否跳过 token 认证(公开 WS) */
  skipAuth?: boolean
}

export interface ManagedWebSocket {
  /** 原生 WebSocket 实例 */
  socket: WebSocket | null
  /** 发送消息(自动 JSON.stringify) */
  send: (data: any) => void
  /** 关闭连接 */
  close: (code?: number, reason?: string) => void
  /** 手动重连 */
  reconnect: () => void
  /** 当前重连次数 */
  reconnectAttempts: number
  /** 是否已连接 */
  isConnected: () => boolean
}

export function createWebSocket(
  path: string,
  options: CreateWebSocketOptions = {},
): ManagedWebSocket {
  const {
    onOpen,
    onMessage,
    onError,
    onClose,
    autoReconnect = true,
    maxReconnectAttempts = 5,
    initialReconnectDelay = 1000,
    maxReconnectDelay = 30000,
    heartbeatInterval = 30000,
    heartbeatMessage = { type: 'ping' },
    protocols,
    skipAuth = false,
  } = options

  let socket: WebSocket | null = null
  let reconnectAttempts = 0
  let shouldReconnect = autoReconnect
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let heartbeatTimer: ReturnType<typeof setInterval> | null = null

  const buildUrl = (): string => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const base = `${wsProtocol}//${host}${path}`

    if (skipAuth) return base

    const token = localStorage.getItem('auth-token') || ''
    // 京东云模式: 不传 token,由网关注入 Basic Auth
    if (token && !isJdyunMode()) {
      return `${base}?token=${encodeURIComponent(token)}`
    }
    return base
  }

  const clearHeartbeat = () => {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
  }

  const startHeartbeat = () => {
    if (heartbeatInterval <= 0) return
    clearHeartbeat()
    heartbeatTimer = setInterval(() => {
      if (socket && socket.readyState === WebSocket.OPEN) {
        try {
          socket.send(JSON.stringify(heartbeatMessage))
        } catch {
          // ignore
        }
      }
    }, heartbeatInterval)
  }

  const connect = () => {
    const url = buildUrl()

    try {
      socket = protocols ? new WebSocket(url, protocols) : new WebSocket(url)
    } catch (error) {
      console.error('[WS] 创建连接失败:', error)
      onError?.(error as unknown as Event)
      scheduleReconnect()
      return
    }

    socket.onopen = () => {
      reconnectAttempts = 0
      startHeartbeat()
      onOpen?.()
    }

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        onMessage?.(data)
      } catch {
        // 非 JSON 消息直接透传
        onMessage?.(event.data)
      }
    }

    socket.onerror = (error) => {
      console.error('[WS] 连接错误:', error)
      onError?.(error)
    }

    socket.onclose = (event) => {
      clearHeartbeat()
      onClose?.(event)

      if (shouldReconnect && reconnectAttempts < maxReconnectAttempts) {
        scheduleReconnect()
      }
    }
  }

  const scheduleReconnect = () => {
    if (!shouldReconnect || reconnectAttempts >= maxReconnectAttempts) return

    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
    }

    const delay = Math.min(
      initialReconnectDelay * Math.pow(2, reconnectAttempts),
      maxReconnectDelay,
    )

    reconnectTimer = setTimeout(() => {
      reconnectAttempts++
      connect()
    }, delay)
  }

  const managed: ManagedWebSocket = {
    get socket() {
      return socket
    },

    send(data: any) {
      if (!socket || socket.readyState !== WebSocket.OPEN) {
        console.warn('[WS] 连接未就绪,消息未发送')
        return
      }
      socket.send(typeof data === 'string' ? data : JSON.stringify(data))
    },

    close(code?: number, reason?: string) {
      shouldReconnect = false
      if (reconnectTimer) {
        clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
      clearHeartbeat()
      if (socket) {
        socket.close(code, reason)
      }
    },

    reconnect() {
      reconnectAttempts = 0
      shouldReconnect = true
      if (socket) {
        socket.close()
      } else {
        connect()
      }
    },

    get reconnectAttempts() {
      return reconnectAttempts
    },

    isConnected() {
      return socket?.readyState === WebSocket.OPEN
    },
  }

  // 初始连接
  connect()

  return managed
}
