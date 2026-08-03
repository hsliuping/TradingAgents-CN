import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { notificationsApi, type NotificationItem } from '@/api/notifications'
import { useAuthStore } from '@/stores/auth'

export type NotificationConnectionStatus =
  | 'DISCONNECTED'
  | 'CONNECTING'
  | 'CONNECTED'
  | 'RETRYING'
  | 'DEGRADED'
  | 'UNAUTHENTICATED'
  | 'FORBIDDEN'
  | 'SERVICE_UNAVAILABLE'

const WS_PROTOCOL = 'alphaguard.notifications.v1'

export const useNotificationStore = defineStore('notifications', () => {
  const items = ref<NotificationItem[]>([])
  const unreadCount = ref(0)
  const loading = ref(false)
  const drawerVisible = ref(false)
  const ws = ref<WebSocket | null>(null)
  const connectionStatus = ref<NotificationConnectionStatus>('DISCONNECTED')
  const lastSuccessAt = ref<string | null>(null)
  const retryCount = ref(0)
  const degradedMessage = ref('')
  const restServiceStatus = ref<'READY' | 'DEGRADED' | 'UNKNOWN'>('UNKNOWN')
  let wsReconnectTimer: ReturnType<typeof setTimeout> | null = null
  let connectionGeneration = 0
  let manuallyDisconnected = false
  const maxReconnectAttempts = 6

  const connected = computed(() => connectionStatus.value === 'CONNECTED')
  const wsConnected = connected
  const degraded = computed(() =>
    restServiceStatus.value === 'DEGRADED'
    || ['DEGRADED', 'SERVICE_UNAVAILABLE'].includes(connectionStatus.value)
  )
  const hasUnread = computed(() => unreadCount.value > 0)

  function classifyHttpFailure(error: any) {
    const status = Number(error?.response?.status || 0)
    if (status === 401) {
      connectionStatus.value = 'UNAUTHENTICATED'
      degradedMessage.value = '登录已失效，通知已停止；核心功能不受影响。'
    } else if (status === 403) {
      connectionStatus.value = 'FORBIDDEN'
      degradedMessage.value = '当前账号无通知权限；核心功能不受影响。'
    } else {
      connectionStatus.value = connectionStatus.value === 'CONNECTED' ? 'CONNECTED' : 'SERVICE_UNAVAILABLE'
      degradedMessage.value = '通知服务暂不可用，页面与交易安全链可继续使用。'
    }
    restServiceStatus.value = 'DEGRADED'
  }

  async function refreshUnreadCount() {
    try {
      const res = await notificationsApi.getUnreadCount()
      unreadCount.value = res?.data?.count ?? 0
      restServiceStatus.value = res?.data?.service_status || 'READY'
      if (restServiceStatus.value === 'DEGRADED') {
        degradedMessage.value = res.message || '通知未读数暂不可用，已安全显示为0。'
      }
    } catch (error) {
      unreadCount.value = 0
      classifyHttpFailure(error)
    }
  }

  async function loadList(status: 'unread' | 'all' = 'all') {
    loading.value = true
    try {
      const res = await notificationsApi.getList({ status, page: 1, page_size: 20 })
      items.value = res?.data?.items ?? []
      restServiceStatus.value = res?.data?.service_status || 'READY'
      if (restServiceStatus.value === 'DEGRADED') {
        degradedMessage.value = '通知列表暂不可用，核心功能不受影响。'
      }
    } catch (error) {
      items.value = []
      classifyHttpFailure(error)
    } finally {
      loading.value = false
    }
  }

  async function markRead(id: string) {
    try {
      await notificationsApi.markRead(id)
      const idx = items.value.findIndex(x => x.id === id)
      if (idx !== -1) items.value[idx].status = 'read'
      if (unreadCount.value > 0) unreadCount.value -= 1
    } catch (error) {
      classifyHttpFailure(error)
    }
  }

  async function markAllRead() {
    try {
      await notificationsApi.markAllRead()
      items.value = items.value.map(x => ({ ...x, status: 'read' }))
      unreadCount.value = 0
    } catch (error) {
      classifyHttpFailure(error)
    }
  }

  function addNotification(n: Omit<NotificationItem, 'id' | 'status' | 'created_at'> & { id?: string; created_at?: string; status?: 'unread' | 'read' }) {
    const id = n.id || `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
    const created_at = n.created_at || new Date().toISOString()
    const item: NotificationItem = { ...n, id, created_at, status: n.status ?? 'unread' }
    items.value.unshift(item)
    if (item.status === 'unread') unreadCount.value += 1
  }

  function clearReconnectTimer() {
    if (wsReconnectTimer) clearTimeout(wsReconnectTimer)
    wsReconnectTimer = null
  }

  function scheduleReconnect(generation: number) {
    if (manuallyDisconnected || generation !== connectionGeneration) return
    if (retryCount.value >= maxReconnectAttempts) {
      connectionStatus.value = 'DEGRADED'
      degradedMessage.value = '通知实时连接重试已停止；仍可手动刷新，核心功能不受影响。'
      return
    }
    const delay = Math.min(1000 * 2 ** retryCount.value, 30000)
    connectionStatus.value = 'RETRYING'
    retryCount.value += 1
    clearReconnectTimer()
    wsReconnectTimer = setTimeout(() => {
      if (generation === connectionGeneration && !manuallyDisconnected) connectWebSocket(false)
    }, delay)
  }

  function connectWebSocket(resetAttempts = true) {
    const authStore = useAuthStore()
    const token = authStore.token || localStorage.getItem('auth-token') || ''
    connectionGeneration += 1
    const generation = connectionGeneration
    manuallyDisconnected = false
    clearReconnectTimer()
    if (resetAttempts) retryCount.value = 0
    if (ws.value) {
      const previous = ws.value
      ws.value = null
      try { previous.close(1000, 'REPLACED') } catch {}
    }
    if (!token) {
      connectionStatus.value = 'UNAUTHENTICATED'
      degradedMessage.value = '未登录，通知连接未启动。'
      return
    }
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${wsProtocol}//${window.location.host}/api/ws/notifications`
    connectionStatus.value = 'CONNECTING'
    const socket = new WebSocket(wsUrl, [WS_PROTOCOL, `auth.${token}`])
    ws.value = socket

    socket.onopen = () => {
      if (generation !== connectionGeneration) return
      connectionStatus.value = 'CONNECTED'
      lastSuccessAt.value = new Date().toISOString()
      retryCount.value = 0
      degradedMessage.value = ''
    }
    socket.onclose = event => {
      if (generation !== connectionGeneration) return
      ws.value = null
      if (manuallyDisconnected || event.code === 1000) {
        connectionStatus.value = 'DISCONNECTED'
        return
      }
      if (event.code === 4401 || event.code === 1008) {
        connectionStatus.value = 'UNAUTHENTICATED'
        degradedMessage.value = '通知鉴权失败，请重新登录；核心功能不受影响。'
        return
      }
      if (event.code === 4403) {
        connectionStatus.value = 'FORBIDDEN'
        degradedMessage.value = '当前账号无通知权限；核心功能不受影响。'
        return
      }
      connectionStatus.value = 'SERVICE_UNAVAILABLE'
      degradedMessage.value = '通知实时连接中断，正在有限重试。'
      scheduleReconnect(generation)
    }
    socket.onerror = () => {
      if (generation === connectionGeneration) connectionStatus.value = 'SERVICE_UNAVAILABLE'
    }
    socket.onmessage = event => {
      if (generation !== connectionGeneration) return
      try {
        const message = JSON.parse(event.data)
        if (message.type === 'connected' || message.type === 'heartbeat') {
          lastSuccessAt.value = new Date().toISOString()
        } else if (message.type === 'notification' && message.data?.title && message.data?.type) {
          addNotification({ ...message.data, status: message.data.status || 'unread' })
        }
      } catch {
        degradedMessage.value = '收到无法识别的通知消息，已忽略。'
      }
    }
  }

  function disconnectWebSocket() {
    manuallyDisconnected = true
    connectionGeneration += 1
    clearReconnectTimer()
    if (ws.value) {
      try { ws.value.close(1000, 'CLIENT_DISCONNECT') } catch {}
      ws.value = null
    }
    connectionStatus.value = 'DISCONNECTED'
    retryCount.value = 0
  }

  function connect() { connectWebSocket(true) }
  function disconnect() { disconnectWebSocket() }
  function setDrawerVisible(v: boolean) { drawerVisible.value = v }

  return {
    items, unreadCount, hasUnread, loading, drawerVisible, connected, wsConnected,
    connectionStatus, lastSuccessAt, retryCount, degraded, degradedMessage, restServiceStatus,
    refreshUnreadCount, loadList, markRead, markAllRead, addNotification,
    connect, disconnect, connectWebSocket, disconnectWebSocket, setDrawerVisible
  }
})
