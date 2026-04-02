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
import { ElMessage } from 'element-plus'
import embeddedNanobotApi, {
  type EmbeddedNanobotChatResponse,
  type EmbeddedNanobotStreamCallbacks,
  type EmbeddedNanobotStatusResponse,
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
      activeStreamController = embeddedNanobotApi.chatStream(payload, callbacks)
    })
    draftMessage.value = ''
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

  .status-line {
    color: var(--el-text-color-secondary);
    word-break: break-all;
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
  }
}
</style>