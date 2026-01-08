import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { notificationsApi, type NotificationItem } from '@/api/notifications'
import { useAuthStore } from '@/stores/auth'

export const useNotificationStore = defineStore('notifications', () => {
  const items = ref<NotificationItem[]>([])
  const unreadCount = ref(0)
  const loading = ref(false)
  const drawerVisible = ref(false)

  // 🔥 WebSocket 连接状态
  const ws = ref<WebSocket | null>(null)
  const wsConnected = ref(false)
  let wsReconnectTimer: any = null
  let wsReconnectAttempts = 0
  const maxReconnectAttempts = 10  // 增加重连次数

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
      // 若已存在连接，先关闭
      if (ws.value) {
        try { ws.value.close() } catch {}
        ws.value = null
      }
      if (wsReconnectTimer) { clearTimeout(wsReconnectTimer); wsReconnectTimer = null }

      const authStore = useAuthStore()
      const token = authStore.token || localStorage.getItem('auth-token') || ''
      if (!token) {
        console.warn('[WS] 未找到 token，无法连接 WebSocket')
        return
      }

      // WebSocket 连接地址
      // 🔥 统一使用当前访问的服务器地址（开发环境通过 Vite 代理，生产环境通过 Nginx 代理）
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host = window.location.host
      const wsUrl = `${wsProtocol}//${host}/api/ws/notifications?token=${encodeURIComponent(token)}`

      console.log('[WS] 连接到:', wsUrl)

      const socket = new WebSocket(wsUrl)
      ws.value = socket

      socket.onopen = () => {
        console.log('[WS] 连接成功')
        wsConnected.value = true
        wsReconnectAttempts = 0
      }

      socket.onclose = (event) => {
        console.log('[WS] 连接关闭:', event.code, event.reason)
        wsConnected.value = false
        ws.value = null

        // 自动重连
        if (wsReconnectAttempts < maxReconnectAttempts) {
          const delay = Math.min(1000 * Math.pow(2, wsReconnectAttempts), 30000)
          console.log(`[WS] ${delay}ms 后重连 (尝试 ${wsReconnectAttempts + 1}/${maxReconnectAttempts})`)

          wsReconnectTimer = setTimeout(() => {
            wsReconnectAttempts++
            connectWebSocket()
          }, delay)
        } else {
          console.error('[WS] 达到最大重连次数，停止重连')
        }
      }

      socket.onerror = (error) => {
        console.error('[WS] 连接错误:', error)
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
    if (wsReconnectTimer) {
      clearTimeout(wsReconnectTimer)
      wsReconnectTimer = null
    }

    if (ws.value) {
      try { ws.value.close() } catch {}
      ws.value = null
    }

    wsConnected.value = false
    wsReconnectAttempts = 0
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
