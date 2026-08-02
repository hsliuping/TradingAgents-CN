import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { notificationsApi, type NotificationItem } from '@/api/notifications'
import { useAuthStore } from '@/stores/auth'
import { isJdyunMode } from '@/utils/config'

type NotificationSocketState = {
  socket: WebSocket | null
  reconnectTimer: ReturnType<typeof setTimeout> | null
  reconnectAttempts: number
  shouldReconnect: boolean
  currentToken: string
  isConnecting: boolean
}

declare global {
  interface Window {
    __TA_NOTIFICATION_SOCKET_STATE__?: NotificationSocketState
  }
}

function getGlobalSocketState(): NotificationSocketState {
  if (!window.__TA_NOTIFICATION_SOCKET_STATE__) {
    window.__TA_NOTIFICATION_SOCKET_STATE__ = {
      socket: null,
      reconnectTimer: null,
      reconnectAttempts: 0,
      shouldReconnect: false,
      currentToken: '',
      isConnecting: false,
    }
  }
  return window.__TA_NOTIFICATION_SOCKET_STATE__
}

export const useNotificationStore = defineStore('notifications', () => {
  const items = ref<NotificationItem[]>([])
  const unreadCount = ref(0)
  const loading = ref(false)
  const drawerVisible = ref(false)

  // 🔥 WebSocket 连接状态
  const ws = ref<WebSocket | null>(null)
  const wsConnected = ref(false)
  const maxReconnectAttempts = 10  // 增加重连次数

  const syncSocketRefs = () => {
    const state = getGlobalSocketState()
    ws.value = state.socket
    wsConnected.value = Boolean(state.socket && state.socket.readyState === WebSocket.OPEN)
  }

  const clearReconnectTimer = () => {
    const state = getGlobalSocketState()
    if (state.reconnectTimer) {
      clearTimeout(state.reconnectTimer)
      state.reconnectTimer = null
    }
  }

  // 连接状态
  const connected = computed(() => wsConnected.value)

  const hasUnread = computed(() => unreadCount.value > 0)

  async function refreshUnreadCount() {
    try {
      const res = await notificationsApi.getUnreadCount()
      unreadCount.value = res?.data?.count ?? 0
    } catch {
      // noop
    }
  }

  async function loadList(status: 'unread' | 'all' = 'all') {
    loading.value = true
    try {
      const res = await notificationsApi.getList({ status, page: 1, page_size: 20 })
      items.value = res?.data?.items ?? []
    } catch {
      items.value = []
    } finally {
      loading.value = false
    }
  }

  async function markRead(id: string) {
    await notificationsApi.markRead(id)
    const idx = items.value.findIndex(x => x.id === id)
    if (idx !== -1) items.value[idx].status = 'read'
    if (unreadCount.value > 0) unreadCount.value -= 1
  }

  async function markAllRead() {
    await notificationsApi.markAllRead()
    items.value = items.value.map(x => ({ ...x, status: 'read' }))
    unreadCount.value = 0
  }

  function addNotification(n: Omit<NotificationItem, 'id' | 'status' | 'created_at'> & { id?: string; created_at?: string; status?: 'unread' | 'read' }) {
    const id = n.id || `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
    const created_at = n.created_at || new Date().toISOString()
    const item: NotificationItem = {
      id,
      title: n.title,
      content: n.content,
      type: n.type,
      status: n.status ?? 'unread',
      created_at,
      link: n.link,
      source: n.source
    }
    items.value.unshift(item)
    if (item.status === 'unread') unreadCount.value += 1
  }

  // 🔥 连接 WebSocket（优先）
  function connectWebSocket() {
    try {
      const authStore = useAuthStore()
      const token = authStore.token || localStorage.getItem('auth-token') || ''
      const jdyun = isJdyunMode()

      // 京东云模式：无 JWT token 也可连接，由网关注入 Basic Auth 认证
      // 非京东云模式：必须有 JWT token
      if (!token && !jdyun) {
        console.warn('[WS] 未找到 token，无法连接 WebSocket')
        disconnectWebSocket()
        return
      }

      const state = getGlobalSocketState()
      state.shouldReconnect = true

      if (state.isConnecting) {
        console.debug('[WS] 已在连接中，跳过重复连接请求')
        return
      }

      // 京东云模式下 token 为空时用占位符标识，保证 currentToken 比较逻辑一致
      const connKey = token || (jdyun ? '__jdyun_basic_auth__' : '')
      if (
        state.socket
        && (state.socket.readyState === WebSocket.OPEN || state.socket.readyState === WebSocket.CONNECTING)
        && state.currentToken === connKey
      ) {
        console.debug('[WS] 复用现有通知连接')
        syncSocketRefs()
        return
      }

      clearReconnectTimer()

      if (state.socket) {
        try {
          state.socket.close()
        } catch (error) {
          console.debug('[WS] 关闭旧连接失败:', error)
        } finally {
          state.socket = null
        }
      }

      // WebSocket 连接地址
      // 🔥 统一使用当前访问的服务器地址（开发环境通过 Vite 代理，生产环境通过 Nginx 代理）
      // 京东云模式无 token 时不传 token 参数，由网关注入的 Basic Auth 头认证
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host = window.location.host
      const wsUrl = token
        ? `${wsProtocol}//${host}/api/ws/notifications?token=${encodeURIComponent(token)}`
        : `${wsProtocol}//${host}/api/ws/notifications`

      console.log('[WS] 连接到:', wsUrl, jdyun && !token ? '(京东云 Basic Auth)' : '')

      const socket = new WebSocket(wsUrl)
      state.socket = socket
      state.currentToken = connKey
      state.isConnecting = true
      syncSocketRefs()

      socket.onopen = () => {
        console.log('[WS] 连接成功')
        state.isConnecting = false
        wsConnected.value = true
        state.reconnectAttempts = 0
        syncSocketRefs()
      }

      socket.onclose = (event) => {
        console.log('[WS] 连接关闭:', event.code, event.reason)
        state.isConnecting = false
        wsConnected.value = false
        if (state.socket === socket) {
          state.socket = null
        }
        syncSocketRefs()

        // 自动重连
        if (state.shouldReconnect && state.reconnectAttempts < maxReconnectAttempts) {
          const delay = Math.min(1000 * Math.pow(2, state.reconnectAttempts), 30000)
          console.log(`[WS] ${delay}ms 后重连 (尝试 ${state.reconnectAttempts + 1}/${maxReconnectAttempts})`)

          state.reconnectTimer = setTimeout(() => {
            state.reconnectAttempts++
            connectWebSocket()
          }, delay)
        } else {
          if (state.shouldReconnect) {
            console.error('[WS] 达到最大重连次数，停止重连')
          }
        }
      }

      socket.onerror = (error) => {
        console.error('[WS] 连接错误:', error)
        state.isConnecting = false
        wsConnected.value = false
      }

      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          handleWebSocketMessage(message)
        } catch (error) {
          console.error('[WS] 解析消息失败:', error)
        }
      }
    } catch (error) {
      const state = getGlobalSocketState()
      state.isConnecting = false
      console.error('[WS] 连接失败:', error)
      wsConnected.value = false
    }
  }

  // 处理 WebSocket 消息
  function handleWebSocketMessage(message: any) {
    console.log('[WS] 收到消息:', message)

    switch (message.type) {
      case 'connected':
        console.log('[WS] 连接确认:', message.data)
        break

      case 'notification':
        // 处理通知
        if (message.data && message.data.title && message.data.type) {
          addNotification({
            id: message.data.id,
            title: message.data.title,
            content: message.data.content,
            type: message.data.type,
            link: message.data.link,
            source: message.data.source,
            created_at: message.data.created_at,
            status: message.data.status || 'unread'
          })
        }
        break

      case 'heartbeat':
        // 心跳消息，无需处理
        break

      default:
        console.warn('[WS] 未知消息类型:', message.type)
    }
  }

  // 断开 WebSocket
  function disconnectWebSocket() {
    const state = getGlobalSocketState()
    state.shouldReconnect = false
    state.isConnecting = false
    state.currentToken = ''
    clearReconnectTimer()

    if (state.socket) {
      try {
        state.socket.close()
      } catch (error) {
        console.debug('[WS] 断开连接时关闭失败:', error)
      }
      state.socket = null
    }

    wsConnected.value = false
    state.reconnectAttempts = 0
    syncSocketRefs()
  }

  // 🔥 连接 WebSocket
  function connect() {
    console.log('[Notifications] 开始连接...')
    connectWebSocket()
  }

  // 🔥 断开 WebSocket
  function disconnect() {
    console.log('[Notifications] 断开连接...')
    disconnectWebSocket()
  }

  function setDrawerVisible(v: boolean) {
    drawerVisible.value = v
  }

  return {
    items,
    unreadCount,
    hasUnread,
    loading,
    drawerVisible,
    connected,
    wsConnected,
    refreshUnreadCount,
    loadList,
    markRead,
    markAllRead,
    addNotification,
    connect,
    disconnect,
    connectWebSocket,
    disconnectWebSocket,
    setDrawerVisible
  }
})
