# WebSocket 通知系统

## 📋 概述

WebSocket 通知系统是对 SSE + Redis PubSub 方案的替代，解决了 Redis 连接泄漏问题。

### ✅ 优势

| 特性 | SSE + Redis PubSub | WebSocket |
|------|-------------------|-----------|
| **连接管理** | 每个 SSE 连接创建独立的 PubSub 连接 ❌ | 直接管理 WebSocket 连接 ✅ |
| **Redis 连接** | 不使用连接池，容易泄漏 ❌ | 不需要 Redis PubSub ✅ |
| **双向通信** | 单向（服务器→客户端）❌ | 双向（服务器↔客户端）✅ |
| **实时性** | 较好 ⚠️ | 更好 ✅ |
| **连接数限制** | 受 Redis 连接数限制 ❌ | 只受服务器资源限制 ✅ |
| **自动重连** | 浏览器自动重连 ✅ | 需要手动实现 ⚠️ |

---

## 🚀 快速开始

### 后端 API

#### 1. WebSocket 通知端点

```
ws://localhost:8000/api/ws/notifications?token=<jwt_token>
```

**消息格式**：

```json
{
  "type": "notification",  // 消息类型: notification, heartbeat, connected
  "data": {
    "id": "...",
    "title": "分析完成",
    "content": "000001 分析已完成",
    "type": "analysis",
    "link": "/stocks/000001",
    "source": "analysis",
    "created_at": "2025-10-23T12:00:00",
    "status": "unread"
  }
}
```

#### 2. WebSocket 任务进度端点

```
ws://localhost:8000/api/ws/tasks/<task_id>?token=<jwt_token>
```

**消息格式**：

```json
{
  "type": "progress",  // 消息类型: progress, completed, error, heartbeat
  "data": {
    "task_id": "...",
    "message": "正在分析...",
    "step": 1,
    "total_steps": 5,
    "progress": 20.0,
    "timestamp": "2025-10-23T12:00:00"
  }
}
```

#### 3. WebSocket 连接统计

```
GET /api/ws/stats
```

**响应**：

```json
{
  "total_users": 5,
  "total_connections": 8,
  "users": {
    "admin": 2,
    "user1": 1,
    "user2": 1
  }
}
```

---

## 💻 前端集成

### Vue 3 + TypeScript 示例

#### 1. 创建 WebSocket Store

```typescript
// stores/websocket.ts
import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { useAuthStore } from './auth'

export const useWebSocketStore = defineStore('websocket', () => {
  const ws = ref<WebSocket | null>(null)
  const connected = ref(false)
  const reconnectTimer = ref<number | null>(null)
  const reconnectAttempts = ref(0)
  const maxReconnectAttempts = 5

  // 连接 WebSocket
  function connect() {
    try {
      // 关闭现有连接
      if (ws.value) {
        ws.value.close()
        ws.value = null
      }

      const authStore = useAuthStore()
      const token = authStore.token || localStorage.getItem('auth-token') || ''
      const base = import.meta.env.VITE_API_BASE_URL || ''
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsHost = base.replace(/^https?:\/\//, '').replace(/\/$/, '')
      const url = `${wsProtocol}//${wsHost}/api/ws/notifications?token=${encodeURIComponent(token)}`

      console.log('[WS] 连接到:', url)

      const socket = new WebSocket(url)
      ws.value = socket

      socket.onopen = () => {
        console.log('[WS] 连接成功')
        connected.value = true
        reconnectAttempts.value = 0
      }

      socket.onclose = (event) => {
        console.log('[WS] 连接关闭:', event.code, event.reason)
        connected.value = false
        ws.value = null

        // 自动重连
        if (reconnectAttempts.value < maxReconnectAttempts) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.value), 30000)
          console.log(`[WS] ${delay}ms 后重连 (尝试 ${reconnectAttempts.value + 1}/${maxReconnectAttempts})`)
          
          reconnectTimer.value = window.setTimeout(() => {
            reconnectAttempts.value++
            connect()
          }, delay)
        } else {
          console.error('[WS] 达到最大重连次数，停止重连')
        }
      }

      socket.onerror = (error) => {
        console.error('[WS] 连接错误:', error)
        connected.value = false
      }

      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          handleMessage(message)
        } catch (error) {
          console.error('[WS] 解析消息失败:', error)
        }
      }
    } catch (error) {
      console.error('[WS] 连接失败:', error)
      connected.value = false
    }
  }

  // 处理消息
  function handleMessage(message: any) {
    console.log('[WS] 收到消息:', message)

    switch (message.type) {
      case 'connected':
        console.log('[WS] 连接确认:', message.data)
        break

      case 'notification':
        // 处理通知
        handleNotification(message.data)
        break

      case 'heartbeat':
        // 心跳消息，无需处理
        break

      default:
        console.warn('[WS] 未知消息类型:', message.type)
    }
  }

  // 处理通知
  function handleNotification(data: any) {
    // 添加到通知列表
    const notificationsStore = useNotificationsStore()
    notificationsStore.addNotification(data)

    // 显示桌面通知
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification(data.title, {
        body: data.content,
        icon: '/favicon.ico'
      })
    }
  }

  // 断开连接
  function disconnect() {
    if (reconnectTimer.value) {
      clearTimeout(reconnectTimer.value)
      reconnectTimer.value = null
    }

    if (ws.value) {
      ws.value.close()
      ws.value = null
    }

    connected.value = false
    reconnectAttempts.value = 0
  }

  // 发送消息
  function send(message: any) {
    if (ws.value && connected.value) {
      ws.value.send(JSON.stringify(message))
    } else {
      console.warn('[WS] 未连接，无法发送消息')
    }
  }

  return {
    ws,
    connected,
    connect,
    disconnect,
    send
  }
})
```

#### 2. 在 App.vue 中初始化

```vue
<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useWebSocketStore } from '@/stores/websocket'
import { useAuthStore } from '@/stores/auth'

const wsStore = useWebSocketStore()
const authStore = useAuthStore()

onMounted(() => {
  // 用户登录后连接 WebSocket
  if (authStore.isAuthenticated) {
    wsStore.connect()
  }
})

onUnmounted(() => {
  // 组件卸载时断开连接
  wsStore.disconnect()
})
</script>
```

---

## 🔧 配置

### 环境变量

```env
# WebSocket 配置（可选）
WS_HEARTBEAT_INTERVAL=30  # 心跳间隔（秒）
WS_MAX_CONNECTIONS_PER_USER=3  # 每个用户最大连接数
```

### Nginx 配置

如果使用 Nginx 作为反向代理，需要确保以下配置：

```nginx
location /api/ {
    proxy_pass http://backend/api/;

    # WebSocket 支持（必需）
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";

    # 超时设置（重要！）
    # WebSocket 长连接需要更长的超时时间
    proxy_connect_timeout 120s;
    proxy_send_timeout 3600s;  # 1小时
    proxy_read_timeout 3600s;  # 1小时

    # 禁用缓存
    proxy_buffering off;
    proxy_cache off;
}
```

**关键配置说明**：

1. **`proxy_http_version 1.1`**：WebSocket 需要 HTTP/1.1
2. **`Upgrade` 和 `Connection` 头**：用于协议升级
3. **`proxy_send_timeout` 和 `proxy_read_timeout`**：
   - 设置为 3600s（1小时）或更长
   - 如果设置太短（如 120s），WebSocket 连接会被意外关闭
   - 后端有心跳机制（每 30 秒），可以保持连接活跃
4. **`proxy_buffering off`**：禁用缓冲，确保实时性

---

## 📊 监控

### 查看连接统计

```bash
curl http://localhost:8000/api/ws/stats
```

**响应示例**：

```json
{
  "total_users": 5,
  "total_connections": 8,
  "users": {
    "admin": 2,
    "user1": 1,
    "user2": 1
  }
}
```

---

## 🔄 迁移指南

### 从 SSE 迁移到 WebSocket

#### 1. 后端无需修改

通知服务会自动尝试 WebSocket，失败时降级到 Redis PubSub（兼容 SSE）。

#### 2. 前端修改

**旧代码（SSE）**：

```typescript
const sse = new EventSource('/api/notifications/stream?token=...')
sse.addEventListener('notification', (event) => {
  const data = JSON.parse(event.data)
  // 处理通知
})
```

**新代码（WebSocket）**：

```typescript
const ws = new WebSocket('ws://localhost:8000/api/ws/notifications?token=...')
ws.onmessage = (event) => {
  const message = JSON.parse(event.data)
  if (message.type === 'notification') {
    // 处理通知
  }
}
```

---

## ⚠️ 注意事项

1. **自动重连**：WebSocket 需要手动实现重连逻辑（示例代码已包含）
2. **心跳机制**：服务器每 30 秒发送一次心跳，保持连接活跃
3. **连接限制**：每个用户可以有多个连接（例如多个浏览器标签页）
4. **兼容性**：旧的 SSE 客户端仍然可以工作（通过 Redis PubSub）

---

## 🎉 总结

WebSocket 方案彻底解决了 Redis 连接泄漏问题，提供了更好的实时性和连接管理。推荐所有新项目使用 WebSocket 替代 SSE。

