<template>
  <div class="floating-chat-container">
    <!-- 浮窗按钮 -->
    <div
      v-if="!visible"
      class="chat-fab"
      @click="openChat"
      title="使用问答助手"
    >
      <el-icon class="fab-icon"><ChatDotRound /></el-icon>
      <span class="fab-label">使用问答</span>
    </div>

    <!-- 聊天抽屉 -->
    <el-drawer
      v-model="visible"
      title="使用问答助手"
      direction="rtl"
      size="440px"
      :with-header="true"
      :append-to-body="true"
      class="usage-helper-drawer"
      :before-close="handleClose"
    >
      <div class="chat-body">
        <!-- 顶部说明 -->
        <div class="chat-intro">
          <div class="chat-intro-text">
            <el-icon color="var(--el-color-primary)"><InfoFilled /></el-icon>
            <span>问我任何关于系统使用的问题，我能查到你的真实状态再回答</span>
          </div>
          <el-tooltip content="重建用户手册向量索引（语义检索不可用时手动补救，无需重启后端）" placement="top">
            <el-button
              text
              size="small"
              type="primary"
              :loading="rebuildingIndex"
              @click="rebuildManualIndex"
            >
              <el-icon><RefreshRight /></el-icon>
              重建手册索引
            </el-button>
          </el-tooltip>
        </div>

        <!-- 消息列表 -->
        <div class="messages" ref="messagesRef">
          <div
            v-for="(msg, i) in messages"
            :key="i"
            :class="['message', msg.role]"
          >
            <div class="bubble">
              <div class="bubble-content" v-html="renderMarkdown(msg.content)"></div>
            </div>
            <div v-if="msg.tools_used?.length" class="tools-used">
              <el-tag
                v-for="t in msg.tools_used"
                :key="t"
                size="small"
                type="info"
                effect="plain"
              >
                <el-icon><Tools /></el-icon>
                {{ t }}
              </el-tag>
            </div>
          </div>

          <!-- 工具调用进度提示 -->
          <div v-if="toolInProgress" class="message assistant">
            <div class="bubble tool-progress">
              <el-icon class="loading-icon"><Loading /></el-icon>
              <span>{{ toolInProgress }}</span>
            </div>
          </div>

          <!-- 思考中占位 -->
          <div v-if="loading && !streamingMessage && !toolInProgress" class="message assistant">
            <div class="bubble">
              <el-icon class="loading-icon"><Loading /></el-icon>
              <span>正在思考...</span>
            </div>
          </div>
        </div>

        <!-- 快捷问题 -->
        <div v-if="messages.length === 0 && !loading" class="quick-questions">
          <div class="quick-title">💡 你可以问我:</div>
          <div class="quick-buttons">
            <el-button
              v-for="q in quickQuestions"
              :key="q"
              size="small"
              round
              @click="sendMessage(q)"
            >
              {{ q }}
            </el-button>
          </div>
        </div>

        <!-- 输入区 -->
        <div class="input-area">
          <el-input
            v-model="inputText"
            type="textarea"
            :rows="2"
            resize="none"
            placeholder="问任何关于系统使用的问题，Ctrl+Enter 发送..."
            :disabled="loading"
            @keydown.ctrl.enter="sendMessage()"
            @keydown.meta.enter="sendMessage()"
          />
          <div class="input-actions">
            <el-button
              text
              size="small"
              @click="clearMessages"
              :disabled="loading || messages.length === 0"
            >
              <el-icon><Delete /></el-icon>
              清空
            </el-button>
            <el-button
              type="primary"
              :loading="loading"
              :disabled="!inputText.trim()"
              @click="sendMessage()"
            >
              {{ loading ? '发送中' : '发送' }}
            </el-button>
          </div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ChatDotRound,
  Loading,
  InfoFilled,
  Tools,
  Delete,
  RefreshRight,
} from '@element-plus/icons-vue'
import { assistantApi } from '@/api/assistant'
import { renderMarkdown } from '@/utils/markdown'
import { isJdyunMode } from '@/utils/config'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  tools_used?: string[]
}

const visible = ref(false)
const inputText = ref('')
const messages = ref<ChatMessage[]>([])
const loading = ref(false)
const rebuildingIndex = ref(false)
const streamingMessage = ref('')
const toolInProgress = ref('')
const messagesRef = ref<HTMLElement>()
const route = useRoute()
const conversationId = ref<string | undefined>(undefined)
let abortController: AbortController | null = null

/** 重建用户手册向量索引：启动时未配置 Embedding Key 导致语义检索不可用时的手动补救 */
const rebuildManualIndex = async () => {
  if (rebuildingIndex.value) return
  rebuildingIndex.value = true
  try {
    const res = await assistantApi.rebuildUserManualIndex()
    ElMessage.success(
      `用户手册索引已重建：${res.sections_count ?? 0} 个切片（${res.manuals_count ?? 0} 份手册）`
    )
  } catch (e: any) {
    ElMessage.error(
      e?.response?.data?.detail || e?.message || '用户手册索引重建失败，请检查 Embedding 配置'
    )
  } finally {
    rebuildingIndex.value = false
  }
}

// 最近浏览器报错收集
const recentErrors: string[] = []
const MAX_ERRORS = 3

const quickQuestions = [
  '今日任务为什么是 0?',
  '怎么加入关注列表?',
  'License 怎么激活?',
  '我能在哪里看研究报告?',
  '怎么配置定时分析?',
  '我现在是什么版本?',
]

// 收集 window.onerror
const errorHandler = (event: ErrorEvent) => {
  const msg = event.message || 'Unknown error'
  const filename = event.filename || ''
  const lineNo = event.lineno || 0
  recentErrors.push(`${msg} (${filename.split('/').pop()}:${lineNo})`)
  if (recentErrors.length > MAX_ERRORS) recentErrors.shift()
}

// 收集未捕获的 Promise rejection
const rejectionHandler = (event: PromiseRejectionEvent) => {
  const reason = event.reason
  const msg = typeof reason === 'string' ? reason : (reason?.message || JSON.stringify(reason))
  recentErrors.push(`Promise rejection: ${msg}`.slice(0, 200))
  if (recentErrors.length > MAX_ERRORS) recentErrors.shift()
}

onMounted(() => {
  window.addEventListener('error', errorHandler)
  window.addEventListener('unhandledrejection', rejectionHandler)
})

onUnmounted(() => {
  window.removeEventListener('error', errorHandler)
  window.removeEventListener('unhandledrejection', rejectionHandler)
  abortController?.abort()
})

const openChat = () => {
  visible.value = true
  nextTick(() => {
    scrollToBottom()
  })
}

const handleClose = (done: () => void) => {
  if (loading.value) {
    ElMessage.warning('对话正在进行中，请稍候')
    return
  }
  done()
}

const clearMessages = () => {
  if (loading.value) return
  messages.value = []
  conversationId.value = undefined
  streamingMessage.value = ''
  toolInProgress.value = ''
}

const collectUserContext = () => {
  return {
    current_route: route.path,
    is_jdyun_mode: isJdyunMode(),
    guide_completed: localStorage.getItem('jdyun_guide_completed') === 'true',
    recent_console_errors: [...recentErrors],
  }
}

const sendMessage = async (text?: string) => {
  const content = (text || inputText.value).trim()
  if (!content || loading.value) return

  // 取消上一次未完成的请求
  if (abortController) {
    abortController.abort()
    abortController = null
  }

  messages.value.push({ role: 'user', content })
  inputText.value = ''
  loading.value = true
  streamingMessage.value = ''
  toolInProgress.value = ''

  const userContext = collectUserContext()

  abortController = assistantApi.chatStream(
    content,
    conversationId.value,
    undefined, // model: 让后端选
    undefined, // model_config_id
    {
      onToken: (token: string) => {
        if (!streamingMessage.value) {
          // 第一个 token 到来时，新建一条助手消息
          messages.value.push({ role: 'assistant', content: '' })
          toolInProgress.value = ''
        }
        streamingMessage.value += token
        const lastMsg = messages.value[messages.value.length - 1]
        if (lastMsg && lastMsg.role === 'assistant') {
          lastMsg.content = streamingMessage.value
        }
        nextTick(() => scrollToBottom())
      },
      onToolEvent: (event: any) => {
        const eventType = event?.event
        if (eventType === 'tool_started') {
          const toolName = event?.tool || event?.tool_name || '工具'
          toolInProgress.value = `正在调用工具: ${toolName}...`
        } else if (eventType === 'tool_completed') {
          toolInProgress.value = ''
        } else if (eventType === 'tool_round_started') {
          toolInProgress.value = `工具调用第 ${event?.round || '?'} 轮...`
        } else if (eventType === 'llm_thinking') {
          toolInProgress.value = event?.message || '正在思考…'
        }
      },
      onDone: (data: any) => {
        if (data.conversation_id) {
          conversationId.value = data.conversation_id
        }
        // 更新最后一条助手消息的工具调用记录
        const lastMsg = messages.value[messages.value.length - 1]
        if (lastMsg && lastMsg.role === 'assistant' && data.tools_used?.length) {
          lastMsg.tools_used = data.tools_used
        }
        // 如果没有收到任何 token（可能直接走工具路径），用 done 的 reply 兜底
        if (!streamingMessage.value && data.reply) {
          messages.value.push({ role: 'assistant', content: data.reply, tools_used: data.tools_used })
        }
        loading.value = false
        streamingMessage.value = ''
        toolInProgress.value = ''
        abortController = null
        nextTick(() => scrollToBottom())
      },
      onError: (msg: string) => {
        loading.value = false
        streamingMessage.value = ''
        toolInProgress.value = ''
        abortController = null
        // 如果流式过程中已经产生部分回复，追加错误信息；否则单独加一条错误消息
        const lastMsg = messages.value[messages.value.length - 1]
        if (lastMsg && lastMsg.role === 'assistant' && lastMsg.content) {
          lastMsg.content += `\n\n❌ **错误**: ${msg}`
        } else {
          messages.value.push({ role: 'assistant', content: `❌ **错误**: ${msg}\n\n请稍后重试，或刷新页面后再试。` })
        }
        nextTick(() => scrollToBottom())
      },
    },
    {
      assistant_role: 'usage_helper',
      user_context: userContext,
    },
  )
}

const scrollToBottom = () => {
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
}

// 抽屉打开时滚动到底部
watch(visible, (v) => {
  if (v) {
    nextTick(() => scrollToBottom())
  }
})
</script>

<style lang="scss" scoped>
.floating-chat-container {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 2000;
  pointer-events: none;
}

.chat-fab {
  pointer-events: auto;
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--el-color-primary), var(--el-color-primary-light-3));
  color: #fff;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 6px 20px rgba(64, 158, 255, 0.45);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  user-select: none;

  &:hover {
    transform: translateY(-3px) scale(1.05);
    box-shadow: 0 10px 28px rgba(64, 158, 255, 0.6);
  }

  &:active {
    transform: translateY(-1px) scale(1.02);
  }

  .fab-icon {
    font-size: 22px;
  }

  .fab-label {
    font-size: 10px;
    margin-top: 2px;
    letter-spacing: 0.5px;
  }
}

.chat-body {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 0 12px 12px;
  overflow: hidden;
}

.chat-intro {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  padding: 10px 12px;
  background: var(--el-color-primary-light-9);
  border-radius: 8px;
  margin-bottom: 12px;
  font-size: 12px;
  color: var(--el-text-color-regular);
  line-height: 1.5;
}

.chat-intro-text {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 4px 4px 12px 0;
  min-height: 200px;

  &::-webkit-scrollbar {
    width: 6px;
  }
  &::-webkit-scrollbar-thumb {
    background: var(--el-border-color);
    border-radius: 3px;
  }
  &::-webkit-scrollbar-track {
    background: transparent;
  }
}

.message {
  margin-bottom: 14px;
  display: flex;
  flex-direction: column;

  &.user {
    align-items: flex-end;

    .bubble {
      background: var(--el-color-primary);
      color: #fff;
      border-bottom-right-radius: 4px;
    }
  }

  &.assistant {
    align-items: flex-start;

    .bubble {
      background: var(--el-fill-color-light);
      color: var(--el-text-color-primary);
      border-bottom-left-radius: 4px;
    }
  }
}

.bubble {
  max-width: 85%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  word-wrap: break-word;
  word-break: break-word;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.bubble-content {
  :deep(p) {
    margin: 0 0 8px 0;
    &:last-child {
      margin-bottom: 0;
    }
  }
  :deep(ul),
  :deep(ol) {
    margin: 6px 0;
    padding-left: 20px;
  }
  :deep(li) {
    margin: 2px 0;
  }
  :deep(code) {
    background: rgba(0, 0, 0, 0.08);
    padding: 1px 4px;
    border-radius: 3px;
    font-family: Consolas, Monaco, monospace;
    font-size: 13px;
  }
  :deep(pre) {
    background: rgba(0, 0, 0, 0.08);
    padding: 8px;
    border-radius: 6px;
    overflow-x: auto;
    margin: 6px 0;
  }
  :deep(strong) {
    font-weight: 600;
  }
}

.tools-used {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
}

.tool-progress {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  font-style: italic;
}

.loading-icon {
  animation: rotate 1.4s linear infinite;
}

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.quick-questions {
  margin-bottom: 12px;
  padding: 10px 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
}

.quick-title {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}

.quick-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.input-area {
  border-top: 1px solid var(--el-border-color-lighter);
  padding-top: 10px;

  :deep(.el-textarea__inner) {
    border-radius: 8px;
    font-size: 14px;
    line-height: 1.5;
    resize: none;
  }
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
  gap: 8px;
}
</style>

<style lang="scss">
/* 京东云版浮窗抽屉全局样式（非 scoped，调整 el-drawer 内部样式） */
.usage-helper-drawer {
  pointer-events: auto;

  .el-drawer__header {
    margin-bottom: 0;
    padding: 16px 20px;
    border-bottom: 1px solid var(--el-border-color-lighter);
    font-weight: 600;
    color: var(--el-text-color-primary);
  }
  .el-drawer__body {
    padding: 0;
  }
}
</style>
