<template>
  <div class="embedded-nanobot-page">
    <div class="page-header">
      <div>
        <h1>Embedded Nanobot 调试页</h1>
        <p>这个页面直接调用项目内嵌的 nanobot runtime，用于验证数据库模型配置、会话键、工具调用和返回内容。</p>
      </div>
      <div class="header-actions">
        <el-button @click="loadStatus" :loading="loadingStatus">刷新状态</el-button>
        <el-button @click="clearMessages" plain>清空本地记录</el-button>
      </div>
    </div>

    <div class="page-grid">
      <el-card class="config-card" shadow="never">
        <template #header>
          <div class="card-header">
            <span>运行配置</span>
          </div>
        </template>

        <div class="status-block">
          <el-tag :type="statusInfo?.enabled ? 'success' : 'danger'">{{ statusInfo?.enabled ? '已启用' : '不可用' }}</el-tag>
          <div class="status-line" v-if="statusInfo?.user_id">用户：{{ statusInfo.user_id }}</div>
          <div class="status-line" v-if="statusInfo?.workspace">工作区：{{ statusInfo.workspace }}</div>
        </div>

        <el-form label-position="top">
          <el-form-item label="会话键">
            <div class="session-key-row">
              <el-input v-model="form.sessionKey" placeholder="例如：embedded:user:debug" />
              <el-button plain :disabled="streaming || sending" @click="createNewSession">新建会话</el-button>
            </div>
          </el-form-item>
          <el-form-item label="模型名称">
            <el-input v-model="form.model" placeholder="留空则按数据库默认配置" />
          </el-form-item>
          <el-form-item label="渠道">
            <el-input v-model="form.channel" placeholder="api" />
          </el-form-item>
          <el-form-item label="聊天标识">
            <el-input v-model="form.chatId" placeholder="留空则沿用会话键" />
          </el-form-item>
          <el-form-item label="技能列表">
            <el-input
              v-model="form.skillNamesText"
              type="textarea"
              :rows="3"
              resize="none"
              placeholder="一行一个 skill 名称；不填则不显式启用 skill"
            />
          </el-form-item>
        </el-form>

        <div class="history-block">
          <div class="card-header">
            <span>数据库会话</span>
            <el-button size="small" text @click="loadThreads" :loading="loadingThreads">刷新</el-button>
          </div>
          <div class="thread-filter-grid">
            <el-select v-model="selectedThreadScope" size="small" placeholder="活动会话" @change="loadThreads">
              <el-option label="活动会话" value="active" />
              <el-option label="已归档会话" value="archived" />
            </el-select>
            <el-input v-model="threadSearchText" size="small" clearable placeholder="搜索标题、摘要、最近问题" />
            <el-select v-model="selectedThreadAgentFilter" size="small" placeholder="全部 Agent">
              <el-option label="全部 Agent" value="all" />
              <el-option
                v-for="option in nanobotThreadAgentOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
            <el-select v-model="selectedThreadTimeFilter" size="small" placeholder="全部时间">
              <el-option label="全部时间" value="all" />
              <el-option label="最近 24 小时" value="24h" />
              <el-option label="最近 7 天" value="7d" />
              <el-option label="最近 30 天" value="30d" />
            </el-select>
          </div>
          <el-empty v-if="!loadingThreads && !threadItems.length" :description="selectedThreadScope === 'archived' ? '暂无已归档会话' : '暂无数据库会话'" :image-size="56" />
          <div v-else class="thread-list">
            <div v-if="loadingThreads" class="status-line">正在加载数据库会话...</div>
            <div v-else-if="!filteredThreadItems.length" class="status-line">{{ selectedThreadScope === 'archived' ? '没有符合筛选条件的已归档会话' : '没有符合筛选条件的会话' }}</div>
            <div
              v-for="thread in filteredThreadItems"
              :key="thread.thread_id"
              :class="['thread-item', { active: selectedThreadId === thread.thread_id }]"
            >
              <button
                type="button"
                class="thread-main"
                @click="loadThreadMessages(thread.thread_id)"
              >
                <div class="thread-title-row">
                  <strong>{{ thread.title || 'Nanobot 会话' }}</strong>
                  <el-tag size="small" effect="plain">{{ thread.message_count }}</el-tag>
                </div>
                <div class="thread-desc">{{ thread.last_user_message || thread.summary || '暂无摘要' }}</div>
                <div class="thread-meta-row">
                  <div class="thread-meta">{{ formatThreadMeta(thread) }}</div>
                  <div class="thread-meta-badges">
                    <el-tag v-if="thread.archived" size="small" type="info" effect="plain">已归档</el-tag>
                    <div v-if="thread.thread_context?.spec_name" class="thread-agent">{{ thread.thread_context.spec_name }}</div>
                  </div>
                </div>
              </button>
              <el-button
                v-if="thread.archived"
                type="primary"
                link
                class="thread-delete-btn"
                @click.stop="handleRestoreThread(thread)"
              >恢复</el-button>
              <el-button
                v-else
                type="danger"
                link
                class="thread-delete-btn"
                @click.stop="handleDeleteThread(thread)"
              >归档</el-button>
            </div>
          </div>
        </div>
      </el-card>

      <el-card class="chat-card" shadow="never">
        <template #header>
          <div class="card-header">
            <span>对话调试</span>
            <div class="header-tags">
              <el-tag v-if="streaming" type="success" effect="plain">执行中</el-tag>
              <el-tag v-if="lastUsageText" type="info" effect="plain">{{ lastUsageText }}</el-tag>
            </div>
          </div>
        </template>

        <div class="message-list" v-if="messages.length">
          <div
            v-for="(item, index) in messages"
            :key="`${item.role}-${index}`"
            :class="['message-item', item.role]"
          >
            <div class="message-role">{{ item.role === 'user' ? '你' : 'Nanobot' }}</div>
            <div class="message-content">{{ item.content }}</div>
            <div class="message-meta" v-if="item.toolsUsed?.length || item.stopReason">
              <span v-if="item.stopReason">结束原因：{{ item.stopReason }}</span>
              <span v-if="item.toolsUsed?.length">工具：{{ item.toolsUsed.join('、') }}</span>
            </div>
          </div>
        </div>
        <el-empty v-else description="还没有发送消息" :image-size="80" />

        <div v-if="currentProgressHint" class="streaming-hint">{{ currentProgressHint }}</div>

        <div class="composer">
          <el-input
            v-model="draftMessage"
            type="textarea"
            :rows="4"
            resize="vertical"
            placeholder="例如：列出当前工作区的顶层目录，并说明你准备如何探索这个项目。"
            @keydown.enter.ctrl.prevent="handleSend"
          />
          <div class="composer-actions">
            <div class="composer-hint">Ctrl + Enter 发送</div>
            <el-button type="primary" :loading="sending" :disabled="!draftMessage.trim()" @click="handleSend">发送</el-button>
          </div>
        </div>
      </el-card>
    </div>

    <div class="result-grid">
      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <span>实时执行轨迹</span>
          </div>
        </template>
        <el-empty v-if="!traceEvents.length" description="暂无执行轨迹" :image-size="60" />
        <div v-else class="trace-list">
          <div v-for="(item, index) in traceEvents" :key="`${item.kind}-${index}`" class="trace-item">
            <div class="trace-kind">{{ item.kind }}</div>
            <div class="trace-message">{{ item.message }}</div>
          </div>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <span>最近一次工具事件</span>
          </div>
        </template>
        <el-empty v-if="!lastToolEventsText" description="暂无工具事件" :image-size="60" />
        <pre v-else class="json-block">{{ lastToolEventsText }}</pre>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <span>最近一次 usage</span>
          </div>
        </template>
        <el-empty v-if="!lastUsageJson" description="暂无 usage" :image-size="60" />
        <pre v-else class="json-block">{{ lastUsageJson }}</pre>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import embeddedNanobotApi, {
  type EmbeddedNanobotChatResponse,
  type EmbeddedNanobotMessageItem,
  type EmbeddedNanobotStreamCallbacks,
  type EmbeddedNanobotStatusResponse,
  type EmbeddedNanobotThreadItem,
} from '@/api/embeddedNanobot'

type DebugMessage = {
  role: 'user' | 'assistant'
  content: string
  toolsUsed?: string[]
  stopReason?: string
}

type TraceItem = {
  kind: string
  message: string
}

const TOOL_STATUS_LABELS: Record<string, string> = {
  started: '开始',
  ok: '完成',
  completed: '完成',
  error: '失败',
}

const loadingStatus = ref(false)
const sending = ref(false)
const streaming = ref(false)
const statusInfo = ref<EmbeddedNanobotStatusResponse | null>(null)
const messages = ref<DebugMessage[]>([])
const lastResponse = ref<EmbeddedNanobotChatResponse | null>(null)
const draftMessage = ref('')
const currentProgressHint = ref('')
const traceEvents = ref<TraceItem[]>([])
const threadItems = ref<EmbeddedNanobotThreadItem[]>([])
const loadingThreads = ref(false)
const selectedThreadId = ref('')
const selectedThreadScope = ref('active')
const threadSearchText = ref('')
const selectedThreadAgentFilter = ref('all')
const selectedThreadTimeFilter = ref('all')
let activeStreamController: AbortController | null = null

const form = ref({
  sessionKey: 'embedded:user:debug',
  model: '',
  channel: 'api',
  chatId: '',
  skillNamesText: '',
})

const sanitizeSessionSegment = (value?: string) => {
  return String(value || 'debug')
    .trim()
    .replace(/[^a-zA-Z0-9_-]+/g, '_')
    .replace(/^_+|_+$/g, '') || 'debug'
}

const generateSessionKey = () => {
  const userSegment = sanitizeSessionSegment(statusInfo.value?.user_id)
  const timestamp = new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 14)
  const randomSuffix = Math.random().toString(36).slice(2, 8)
  return `embedded:user:${userSegment}:${timestamp}:${randomSuffix}`
}

const parseSkillNames = () => {
  return form.value.skillNamesText
    .split(/\r?\n/)
    .map(item => item.trim())
    .filter(Boolean)
}

const stringifyJson = (value: unknown) => {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value || '')
  }
}

const lastToolEventsText = computed(() => {
  const toolEvents = lastResponse.value?.tool_events
  if (!toolEvents?.length) return ''
  return stringifyJson(toolEvents)
})

const lastUsageJson = computed(() => {
  const usage = lastResponse.value?.usage
  if (!usage || !Object.keys(usage).length) return ''
  return stringifyJson(usage)
})

const lastUsageText = computed(() => {
  const usage = lastResponse.value?.usage || {}
  const parts = [
    typeof usage.prompt_tokens === 'number' ? `prompt ${usage.prompt_tokens}` : '',
    typeof usage.completion_tokens === 'number' ? `completion ${usage.completion_tokens}` : '',
    typeof usage.total_tokens === 'number' ? `total ${usage.total_tokens}` : '',
  ].filter(Boolean)
  return parts.join(' | ')
})

const nanobotThreadAgentOptions = computed(() => {
  const seen = new Map<string, string>()
  for (const item of threadItems.value) {
    const specId = String(item.thread_context?.spec_id || '').trim()
    const specName = String(item.thread_context?.spec_name || '').trim()
    if (!specId || seen.has(specId)) continue
    seen.set(specId, specName || specId)
  }
  return Array.from(seen.entries()).map(([value, label]) => ({ value, label }))
})

const filteredThreadItems = computed(() => {
  const keyword = String(threadSearchText.value || '').trim().toLowerCase()
  const now = Date.now()
  const windowMap: Record<string, number> = {
    '24h': 24 * 60 * 60 * 1000,
    '7d': 7 * 24 * 60 * 60 * 1000,
    '30d': 30 * 24 * 60 * 60 * 1000,
  }
  return threadItems.value.filter(item => {
    if (selectedThreadAgentFilter.value !== 'all') {
      if (String(item.thread_context?.spec_id || '').trim() !== selectedThreadAgentFilter.value) {
        return false
      }
    }

    if (selectedThreadTimeFilter.value !== 'all') {
      const timestamp = Date.parse(String(item.updated_at || item.created_at || ''))
      const range = windowMap[selectedThreadTimeFilter.value]
      if (!Number.isFinite(timestamp) || !range || now - timestamp > range) {
        return false
      }
    }

    if (!keyword) return true
    const haystack = [
      item.title,
      item.last_user_message,
      item.summary,
      item.thread_context?.spec_name,
    ].join(' ').toLowerCase()
    return haystack.includes(keyword)
  })
})

const mapThreadMessages = (items: EmbeddedNanobotMessageItem[]): DebugMessage[] => {
  return items.map(item => ({
    role: item.role === 'user' ? 'user' : 'assistant',
    content: String(item.content || ''),
    toolsUsed: item.tools_used || [],
    stopReason: item.stop_reason,
  }))
}

const loadStatus = async () => {
  loadingStatus.value = true
  try {
    statusInfo.value = await embeddedNanobotApi.getStatus()
  } catch (error: any) {
    ElMessage.error(error?.message || '读取 embedded nanobot 状态失败')
  } finally {
    loadingStatus.value = false
  }
}

const loadThreads = async () => {
  loadingThreads.value = true
  try {
    const result = await embeddedNanobotApi.listThreads(20, selectedThreadScope.value === 'archived')
    threadItems.value = result.items || []
  } catch (error: any) {
    threadItems.value = []
    ElMessage.error(error?.message || '读取数据库会话失败')
  } finally {
    loadingThreads.value = false
  }
}

const formatThreadMeta = (thread: EmbeddedNanobotThreadItem) => {
  const raw = String(thread.updated_at || thread.created_at || '').trim()
  if (!raw) return '未知时间'
  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) return raw
  return date.toLocaleString('zh-CN', { hour12: false })
}

const loadThreadMessages = async (threadId: string, silent = false) => {
  try {
    const result = await embeddedNanobotApi.getThreadMessages(threadId)
    selectedThreadId.value = threadId
    form.value.sessionKey = result.thread?.session_key || threadId
    form.value.chatId = result.thread?.thread_id || threadId
    messages.value = mapThreadMessages(result.messages || [])
    const assistantMessages = (result.messages || []).filter(item => item.role === 'assistant')
    const latestAssistant = assistantMessages[assistantMessages.length - 1]
    lastResponse.value = latestAssistant ? {
      content: latestAssistant.content,
      session_key: result.thread?.session_key || threadId,
      thread_id: result.thread?.thread_id || threadId,
      stop_reason: latestAssistant.stop_reason,
      tools_used: latestAssistant.tools_used || [],
      usage: latestAssistant.usage || {},
      tool_events: latestAssistant.tool_events || [],
    } : null
    currentProgressHint.value = ''
  } catch (error: any) {
    if (!silent) {
      ElMessage.error(error?.message || '加载会话消息失败')
    }
  }
}

const handleDeleteThread = async (thread: EmbeddedNanobotThreadItem) => {
  try {
    await ElMessageBox.confirm(`归档会话「${thread.title || thread.thread_id}」后，它会从活动列表隐藏，但历史消息仍会保留。是否继续？`, '归档会话', {
      type: 'warning',
      confirmButtonText: '归档',
      cancelButtonText: '取消',
      confirmButtonClass: 'el-button--danger',
    })
    await embeddedNanobotApi.deleteThread(thread.thread_id)
    if (selectedThreadId.value === thread.thread_id) {
      selectedThreadId.value = ''
      form.value.sessionKey = generateSessionKey()
      form.value.chatId = ''
      clearMessages()
    }
    await loadThreads()
    ElMessage.success('会话已归档')
  } catch (error: any) {
    if (error === 'cancel' || error === 'close' || error?.action === 'cancel' || error?.action === 'close') return
    ElMessage.error(error?.message || '归档会话失败')
  }
}

const handleRestoreThread = async (thread: EmbeddedNanobotThreadItem) => {
  try {
    await embeddedNanobotApi.restoreThread(thread.thread_id)
    await loadThreads()
    ElMessage.success('会话已恢复到活动列表')
  } catch (error: any) {
    ElMessage.error(error?.message || '恢复会话失败')
  }
}

const clearMessages = () => {
  messages.value = []
  lastResponse.value = null
  currentProgressHint.value = ''
  traceEvents.value = []
}

const createNewSession = () => {
  if (streaming.value || sending.value) return
  form.value.sessionKey = generateSessionKey()
  form.value.chatId = ''
  selectedThreadId.value = ''
  clearMessages()
  ElMessage.success('已切换到新的调试会话')
}

const pushTrace = (kind: string, message: string) => {
  if (!message) return
  traceEvents.value.push({ kind, message })
}

const handleSend = async () => {
  if (sending.value || streaming.value) return
  const message = draftMessage.value.trim()
  if (!message) return

  sending.value = true
  streaming.value = true
  currentProgressHint.value = '正在发送请求'
  messages.value.push({ role: 'user', content: message })
  messages.value.push({ role: 'assistant', content: '' })
  const assistantIndex = messages.value.length - 1
  try {
    traceEvents.value = []
    const payload = {
      message,
      session_key: form.value.sessionKey.trim() || undefined,
      model: form.value.model.trim() || undefined,
      channel: form.value.channel.trim() || 'api',
      chat_id: form.value.chatId.trim() || undefined,
      skill_names: parseSkillNames(),
    }
    await new Promise<void>((resolve, reject) => {
      const callbacks: EmbeddedNanobotStreamCallbacks = {
        onStarted(data) {
          currentProgressHint.value = data.message || 'Nanobot 已开始处理请求'
          pushTrace('started', currentProgressHint.value)
        },
        onProgress(data) {
          const msg = data.message || '正在执行'
          currentProgressHint.value = msg
          pushTrace('progress', msg)
        },
        onToken(content) {
          messages.value[assistantIndex].content += content
        },
        onToolEvent(event) {
          const toolName = event.name || 'unknown'
          const status = event.status || 'ok'
          const detail = event.detail ? `：${event.detail}` : ''
          const statusLabel = TOOL_STATUS_LABELS[status] || status
          currentProgressHint.value = status === 'started'
            ? `正在执行工具 ${toolName}`
            : `工具 ${toolName}${statusLabel === '完成' ? ' 已完成' : ` ${statusLabel}`}`
          pushTrace('tool', `${toolName}（${statusLabel}）${detail}`)
        },
        onStepEvent(event) {
          const stepTitle = event.title || event.step || '步骤'
          const status = event.status || 'started'
          const detail = event.detail ? `：${event.detail}` : ''
          const statusLabel = TOOL_STATUS_LABELS[status] || (status === 'completed' ? '完成' : status)
          currentProgressHint.value = status === 'started'
            ? (event.detail || `正在执行 ${stepTitle}`)
            : (event.detail || `${stepTitle} 已完成`)
          pushTrace('step', `${stepTitle}（${statusLabel}）${detail}`)
        },
        onDone(data) {
          lastResponse.value = data
          messages.value[assistantIndex].content = data.content || messages.value[assistantIndex].content
          messages.value[assistantIndex].toolsUsed = data.tools_used || []
          messages.value[assistantIndex].stopReason = data.stop_reason
          currentProgressHint.value = '本轮回复已返回；如果后台日志仍在更新，通常是在做会话归档等收尾动作。'
          pushTrace('done', 'Nanobot 已完成本轮回复；后台可能仍有非阻塞收尾日志。')
          resolve()
        },
        onError(messageText) {
          messages.value[assistantIndex].content = `请求失败：${messageText || '未知错误'}`
          currentProgressHint.value = ''
          reject(new Error(messageText || '未知错误'))
        },
      }
      activeStreamController?.abort()
      activeStreamController = embeddedNanobotApi.chatStream(payload, callbacks)
    })
    draftMessage.value = ''
    await loadThreads()
    if (lastResponse.value?.thread_id) {
      await loadThreadMessages(lastResponse.value.thread_id, true)
    }
  } catch (error: any) {
    ElMessage.error(error?.message || 'Embedded Nanobot 请求失败')
  } finally {
    activeStreamController = null
    streaming.value = false
    sending.value = false
  }
}

onMounted(() => {
  loadStatus()
  loadThreads()
})
</script>

<style scoped lang="scss">
.embedded-nanobot-page {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;

  .page-header {
    display: flex;
    justify-content: space-between;
    gap: 16px;
    align-items: flex-start;

    h1 {
      margin: 0 0 8px;
      font-size: 28px;
    }

    p {
      margin: 0;
      color: var(--el-text-color-secondary);
      max-width: 760px;
      line-height: 1.6;
    }
  }

  .header-actions {
    display: flex;
    gap: 12px;
  }

  .page-grid,
  .result-grid {
    display: grid;
    grid-template-columns: minmax(320px, 380px) minmax(0, 1fr);
    gap: 20px;
  }

  .result-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .header-tags {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .status-block {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 16px;
  }

  .history-block {
    margin-top: 20px;
    padding-top: 16px;
    border-top: 1px solid var(--el-border-color-lighter);
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .thread-filter-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
  }

  .status-line {
    color: var(--el-text-color-secondary);
    word-break: break-all;
  }

  .thread-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
    max-height: 320px;
    overflow: auto;
  }

  .thread-item {
    border: 1px solid var(--el-border-color-light);
    border-radius: 12px;
    background: #fff;
    display: flex;
    gap: 8px;
    align-items: stretch;

    &.active {
      border-color: #9fd5c8;
      background: linear-gradient(135deg, #f0fdf9 0%, #ffffff 100%);
    }
  }

  .thread-main {
    flex: 1;
    border: 0;
    background: transparent;
    padding: 12px;
    text-align: left;
    cursor: pointer;
  }

  .thread-title-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    color: var(--el-text-color-primary);
  }

  .thread-desc {
    margin-top: 8px;
    font-size: 12px;
    line-height: 1.6;
    color: var(--el-text-color-secondary);
  }

  .thread-meta {
    font-size: 11px;
    color: #94a3b8;
  }

  .thread-meta-row {
    margin-top: 6px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }

  .thread-meta-badges {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
  }

  .thread-agent {
    font-size: 11px;
    line-height: 1.4;
    color: #0f766e;
    background: #ecfeff;
    border: 1px solid #a5f3fc;
    border-radius: 999px;
    padding: 2px 8px;
    max-width: 140px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .thread-delete-btn {
    align-self: center;
    padding-right: 12px;
  }

  .session-key-row {
    display: flex;
    gap: 12px;
    align-items: center;

    :deep(.el-input) {
      flex: 1;
    }
  }

  .chat-card {
    min-height: 560px;

    :deep(.el-card__body) {
      display: flex;
      flex-direction: column;
      gap: 16px;
      min-height: 500px;
    }
  }

  .message-list {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 12px;
    max-height: 520px;
    overflow: auto;
    padding-right: 4px;
  }

  .message-item {
    border-radius: 16px;
    padding: 14px 16px;
    border: 1px solid var(--el-border-color-light);
    background: #fff;

    &.user {
      background: linear-gradient(135deg, #eef7ff 0%, #f7fbff 100%);
      border-color: #cfe4ff;
    }

    &.assistant {
      background: linear-gradient(135deg, #fffaf0 0%, #fff 100%);
      border-color: #f2dfb1;
    }
  }

  .message-role {
    font-size: 12px;
    font-weight: 600;
    color: var(--el-text-color-secondary);
    margin-bottom: 8px;
  }

  .message-content {
    white-space: pre-wrap;
    line-height: 1.7;
    word-break: break-word;
  }

  .message-meta {
    margin-top: 10px;
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }

  .composer {
    border-top: 1px solid var(--el-border-color-lighter);
    padding-top: 12px;
  }

  .streaming-hint {
    margin-top: 4px;
    padding: 10px 12px;
    border-radius: 12px;
    background: #f0f9ff;
    color: #075985;
    font-size: 13px;
  }

  .composer-actions {
    margin-top: 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .composer-hint {
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }

  .json-block {
    margin: 0;
    padding: 14px;
    border-radius: 12px;
    background: #0f172a;
    color: #dbeafe;
    overflow: auto;
    max-height: 420px;
    white-space: pre-wrap;
    word-break: break-word;
    font-size: 12px;
    line-height: 1.6;
  }

  .trace-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
    max-height: 420px;
    overflow: auto;
  }

  .trace-item {
    border: 1px solid var(--el-border-color-light);
    border-radius: 12px;
    padding: 12px 14px;
    background: linear-gradient(135deg, #f8fafc 0%, #ffffff 100%);
  }

  .trace-kind {
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    color: #64748b;
    margin-bottom: 6px;
  }

  .trace-message {
    font-size: 13px;
    line-height: 1.6;
    color: var(--el-text-color-primary);
    white-space: pre-wrap;
    word-break: break-word;
  }

  @media (max-width: 1100px) {
    .page-grid,
    .result-grid {
      grid-template-columns: 1fr;
    }

    .page-header {
      flex-direction: column;
    }

    .session-key-row {
      flex-direction: column;
      align-items: stretch;
    }

    .thread-filter-grid {
      grid-template-columns: 1fr;
    }
  }
}
</style>