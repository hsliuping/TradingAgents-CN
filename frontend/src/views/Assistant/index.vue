<template>
  <div class="assistant-page">
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">
          <el-icon class="title-icon"><ChatDotRound /></el-icon>
          智能助手
        </h1>
        <el-tag type="warning" size="small" effect="plain" class="risk-tag">
          ⚠️ 分析结论用于学习验证，不构成投资建议
        </el-tag>
      </div>
      <div class="header-right">
        <el-button size="small" @click="handleCreateThread">
          <el-icon><Plus /></el-icon>
          新主题
        </el-button>
        <el-radio-group v-model="analysisMode" size="small">
          <el-radio-button value="react">
            <el-icon style="vertical-align: -2px;"><ChatDotRound /></el-icon> 快速对话
          </el-radio-button>
          <el-radio-button value="planned">
            <el-icon style="vertical-align: -2px;"><DataAnalysis /></el-icon> 深度分析
          </el-radio-button>
        </el-radio-group>
        <el-tooltip :content="analysisMode === 'react' ? 'ReAct 模式：助手逐步调用工具回答问题' : '规划分析：先制定计划，并行执行多步骤，生成综合报告'" placement="bottom">
          <el-icon class="mode-help"><QuestionFilled /></el-icon>
        </el-tooltip>
      </div>
    </div>

    <div class="workspace-body">
      <aside class="thread-sidebar">
        <div class="sidebar-header">
          <div>
            <div class="sidebar-title">研究主题</div>
            <div class="sidebar-subtitle">把不同研究主线分开管理</div>
          </div>
        </div>
        <div class="thread-list">
          <el-empty v-if="!threads.length && !sidebarLoading" description="暂无主题" :image-size="56" />
          <button
            v-for="thread in threads"
            :key="thread.thread_id"
            class="thread-item"
            :class="{ active: selectedThreadId === thread.thread_id }"
            @click="selectThread(thread.thread_id)"
          >
            <div class="thread-item-top">
              <span class="thread-title">{{ thread.title }}</span>
              <el-tag v-if="thread.pinned" type="info" size="small" effect="plain">默认</el-tag>
            </div>
            <div class="thread-preview">{{ thread.current_summary?.abstract || thread.last_user_message || '进入主题开始研究' }}</div>
            <div class="thread-meta">
              <span>{{ thread.message_count }} 条消息</span>
              <span>{{ formatTime(thread.updated_at) }}</span>
            </div>
          </button>
        </div>
      </aside>

      <section class="chat-panel">
        <div class="chat-panel-header">
          <div>
            <div class="current-thread-title">{{ currentThread?.title || '默认主题' }}</div>
            <div class="current-thread-subtitle">
              {{ currentThread?.current_summary?.abstract || '当前主题还没有摘要，先开始一轮研究。' }}
            </div>
          </div>
          <div class="chat-panel-actions">
            <el-tag v-if="loading" type="info" size="small">思考中...</el-tag>
            <el-button
              v-else-if="selectedThreadId"
              type="default"
              size="small"
              link
              @click="handleClear"
            >
              清空当前主题
            </el-button>
          </div>
        </div>

        <div ref="messagesContainer" class="messages-container">
          <el-empty
            v-if="messages.length === 0 && !loading"
            description="输入问题开始对话，例如：宁德时代最近一周走势如何？动力电池行业景气度有什么变化？"
            :image-size="80"
          />
          <div v-else class="messages-list">
            <div
              v-for="(msg, idx) in messages"
              :key="idx"
              :class="['message-item', msg.role === 'user' ? 'message-user' : 'message-assistant']"
            >
              <template v-if="msg.role === 'user'">
                <div class="message-content">
                  <div class="message-text">{{ msg.content }}</div>
                </div>
                <div class="message-avatar">
                  <el-icon><User /></el-icon>
                </div>
              </template>
              <template v-else>
                <div class="message-avatar">
                  <el-icon><ChatDotRound /></el-icon>
                </div>
                <div class="message-content">
                  <div class="message-text markdown-content" v-html="renderMarkdown(msg.content)"></div>
                  <div v-if="msg.tools_used?.length" class="message-tools">
                    <el-tag v-for="tool in msg.tools_used" :key="tool" size="small" type="info">{{ tool }}</el-tag>
                  </div>
                  <div v-if="msg.source" class="message-plan-info">
                    <el-tag :type="msg.source === 'seed_flow' ? 'success' : msg.source === 'llm_plan' ? 'primary' : 'warning'" size="small" effect="plain">
                      {{ msg.source === 'seed_flow' ? '🌱 种子流程' : msg.source === 'llm_plan' ? '🧠 LLM 规划' : '⚡ ReAct' }}
                    </el-tag>
                    <el-tag v-if="msg.supplemented" type="warning" size="small" effect="plain">📎 已补充</el-tag>
                  </div>
                  <el-collapse v-if="msg.step_results?.length" class="step-results-collapse">
                    <el-collapse-item :title="`查看执行步骤 (${msg.step_results.length})`" name="steps">
                      <div v-for="sr in msg.step_results" :key="sr.step_id" class="step-item">
                        <div class="step-header">
                          <span class="step-label">步骤 {{ sr.step_id }}</span>
                          <span class="step-intent">{{ sr.intent }}</span>
                          <el-tag :type="sr.success ? 'success' : 'danger'" size="small">
                            {{ sr.success ? '✓' : '✗' }} {{ sr.duration_ms }}ms
                          </el-tag>
                        </div>
                        <div class="step-tool">🔧 {{ sr.tool }}</div>
                      </div>
                    </el-collapse-item>
                  </el-collapse>
                </div>
              </template>
            </div>

            <div v-if="loading" class="message-item message-assistant thinking-bubble">
              <div class="message-avatar thinking-avatar">
                <el-icon><ChatDotRound /></el-icon>
              </div>
              <div class="message-content thinking-content">
                <div class="thinking-main-row">
                  <span class="thinking-text">{{ loadingHint }}</span>
                  <span class="thinking-dots">
                    <span class="dot">.</span><span class="dot">.</span><span class="dot">.</span>
                  </span>
                </div>
                <div class="thinking-sub-row">已等待 {{ loadingSeconds }}s</div>
              </div>
            </div>
          </div>
        </div>

        <div class="input-area">
          <div class="input-row">
            <el-input
              v-model="inputMessage"
              type="textarea"
              :rows="2"
              :autosize="{ minRows: 2, maxRows: 5 }"
              placeholder="输入您的问题，如：宁德时代估值和行业景气度是否背离？"
              :disabled="loading"
              @keydown.enter.ctrl="handleSend"
            />
            <el-button
              type="primary"
              :loading="loading"
              :disabled="!inputMessage.trim() || !selectedThreadId"
              class="send-btn"
              @click="handleSend"
            >
              发送
            </el-button>
          </div>
          <span class="input-tip">Ctrl+Enter 发送</span>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { ChatDotRound, DataAnalysis, Plus, QuestionFilled, User } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'

import { assistantApi } from '@/api/assistant'
import type { AssistantThreadItem, MessageItem } from '@/api/assistant'

marked.setOptions({ breaks: true, gfm: true })

const renderMarkdown = (content: string): string => {
  if (!content?.trim()) return ''
  try {
    return marked.parse(content) as string
  } catch {
    return content
  }
}

interface DisplayMessage {
  role: 'user' | 'assistant'
  content: string
  tools_used?: string[]
  source?: string
  supplemented?: boolean
  step_results?: Array<{
    step_id: number
    tool: string
    intent: string
    success: boolean
    duration_ms: number
  }>
}

const inputMessage = ref('')
const loading = ref(false)
const sidebarLoading = ref(false)
const analysisMode = ref<'react' | 'planned'>('react')
const loadingSeconds = ref(0)
const threads = ref<AssistantThreadItem[]>([])
const selectedThreadId = ref<string>('')
const messages = ref<DisplayMessage[]>([])
const messagesContainer = ref<HTMLElement | null>(null)

let loadingTimer: ReturnType<typeof setInterval> | null = null

const currentThread = computed(() => threads.value.find(item => item.thread_id === selectedThreadId.value) || null)

const loadingHint = computed(() => {
  if (analysisMode.value === 'planned') {
    if (loadingSeconds.value < 4) return '正在规划分析步骤'
    if (loadingSeconds.value < 10) return '正在并行执行多智能体分析'
    return '正在汇总结论并生成报告'
  }
  if (loadingSeconds.value < 4) return '正在理解问题并匹配工具'
  if (loadingSeconds.value < 10) return '正在调用数据与分析工具'
  return '正在整理答案'
})

const startLoadingIndicator = () => {
  loadingSeconds.value = 0
  if (loadingTimer) clearInterval(loadingTimer)
  loadingTimer = setInterval(() => {
    loadingSeconds.value += 1
  }, 1000)
}

const stopLoadingIndicator = () => {
  if (loadingTimer) {
    clearInterval(loadingTimer)
    loadingTimer = null
  }
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

const formatTime = (value?: string) => {
  if (!value) return '刚刚'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '刚刚'
  return `${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

const mapMessages = (items?: MessageItem[]): DisplayMessage[] => {
  return (items || []).map(item => ({
    role: item.role,
    content: item.content,
    tools_used: item.tools_used,
  }))
}

const loadThreads = async (preferredThreadId?: string) => {
  sidebarLoading.value = true
  try {
    const res = await assistantApi.getThreads()
    threads.value = res.items || []
    const target = preferredThreadId || selectedThreadId.value || threads.value[0]?.thread_id || ''
    if (target) {
      await selectThread(target)
    }
  } catch (error: unknown) {
    const errMsg = error instanceof Error ? error.message : '加载主题失败'
    ElMessage.error(errMsg)
  } finally {
    sidebarLoading.value = false
  }
}

const selectThread = async (threadId: string) => {
  if (!threadId) return
  selectedThreadId.value = threadId
  try {
    const res = await assistantApi.getThreadMessages(threadId)
    messages.value = mapMessages(res.messages)
    if (res.thread) {
      const index = threads.value.findIndex(item => item.thread_id === res.thread?.thread_id)
      if (index >= 0) {
        threads.value[index] = res.thread
      }
    }
    scrollToBottom()
  } catch (error: unknown) {
    const errMsg = error instanceof Error ? error.message : '加载消息失败'
    ElMessage.error(errMsg)
  }
}

const handleCreateThread = async () => {
  try {
    const { value } = await ElMessageBox.prompt('请输入主题名称', '新建主题', {
      confirmButtonText: '创建',
      cancelButtonText: '取消',
      inputPlaceholder: '如：宁德时代估值跟踪',
      inputPattern: /\S+/,
      inputErrorMessage: '主题名称不能为空',
    })
    const thread = await assistantApi.createThread(value)
    await loadThreads(thread.thread_id)
    ElMessage.success('主题已创建')
  } catch {
    // 用户取消时忽略
  }
}

const handleClear = async () => {
  if (!selectedThreadId.value) return
  ElMessageBox.confirm('确定清空当前主题的所有对话吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    await assistantApi.clearThreadMessages(selectedThreadId.value)
    messages.value = []
    await loadThreads(selectedThreadId.value)
    ElMessage.success('已清空当前主题')
  }).catch(() => {})
}

const handleSend = async () => {
  const text = inputMessage.value.trim()
  if (!text || loading.value || !selectedThreadId.value) return

  messages.value.push({ role: 'user', content: text })
  inputMessage.value = ''
  loading.value = true
  startLoadingIndicator()
  scrollToBottom()

  try {
    if (analysisMode.value === 'planned') {
      const res = await assistantApi.plannedAnalysis(text, selectedThreadId.value)
      if (res.conversation_id) selectedThreadId.value = res.conversation_id
      messages.value.push({
        role: 'assistant',
        content: res.reply,
        tools_used: res.tools_used?.length ? res.tools_used : undefined,
        source: res.source,
        supplemented: res.supplemented,
        step_results: res.step_results,
      })
    } else {
      const res = await assistantApi.chat(text, selectedThreadId.value)
      if (res.conversation_id) selectedThreadId.value = res.conversation_id
      messages.value.push({
        role: 'assistant',
        content: res.reply,
        tools_used: res.tools_used?.length ? res.tools_used : undefined,
      })
    }
    await loadThreads(selectedThreadId.value)
    scrollToBottom()
  } catch (error: unknown) {
    const errMsg = error instanceof Error ? error.message : '请求失败，请稍后重试'
    ElMessage.error(errMsg)
    messages.value.push({
      role: 'assistant',
      content: `抱歉，处理您的请求时出错：${errMsg}`,
      tools_used: [],
    })
    scrollToBottom()
  } finally {
    loading.value = false
    stopLoadingIndicator()
  }
}

onMounted(async () => {
  await loadThreads()
})

onBeforeUnmount(() => {
  stopLoadingIndicator()
})
</script>

<style lang="scss" scoped>
.assistant-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 60px);
  padding: 0 16px 16px;
  overflow: hidden;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  padding: 12px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
  gap: 16px;
  flex-wrap: wrap;
}

.header-left,
.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.page-title {
  font-size: 18px;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 6px;
}

.title-icon {
  font-size: 22px;
}

.mode-help {
  color: var(--el-text-color-secondary);
  cursor: pointer;
  font-size: 16px;
}

.workspace-body {
  flex: 1;
  min-height: 0;
  display: flex;
  gap: 12px;
  margin-top: 12px;
}

.thread-sidebar {
  width: 280px;
  flex-shrink: 0;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: var(--el-bg-color);
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.sidebar-header {
  padding: 14px 14px 10px;
  border-bottom: 1px solid var(--el-border-color-extra-light);
}

.sidebar-title {
  font-size: 14px;
  font-weight: 600;
}

.sidebar-subtitle {
  margin-top: 4px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.thread-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.thread-item {
  width: 100%;
  text-align: left;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: var(--el-fill-color-blank);
  padding: 12px;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    border-color: var(--el-color-primary-light-5);
    background: var(--el-color-primary-light-9);
  }

  &.active {
    border-color: var(--el-color-primary);
    background: var(--el-color-primary-light-9);
  }
}

.thread-item-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.thread-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.thread-preview {
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.thread-meta {
  margin-top: 8px;
  display: flex;
  justify-content: space-between;
  gap: 8px;
  color: var(--el-text-color-placeholder);
  font-size: 12px;
}

.chat-panel {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: var(--el-bg-color);
}

.chat-panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--el-border-color-extra-light);
}

.current-thread-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.current-thread-subtitle {
  margin-top: 4px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  min-height: 0;
}

.messages-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.message-item {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  max-width: 92%;

  &.message-user {
    align-self: flex-end;
    flex-direction: row-reverse;

    .message-avatar {
      background: var(--el-color-primary-light-9);
      color: var(--el-color-primary);
    }

    .message-content {
      background: var(--el-color-primary);
      color: #fff;
      border-radius: 12px;
      padding: 10px 16px;
    }

    .message-text {
      color: inherit;
    }
  }

  &.message-assistant {
    align-self: flex-start;

    .message-avatar {
      background: var(--el-fill-color-light);
      color: var(--el-text-color-regular);
    }

    .message-content {
      background: var(--el-fill-color-lighter);
      border-radius: 12px;
      padding: 12px 20px;
    }
  }
}

.message-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 16px;
}

.message-text {
  word-break: break-word;
  line-height: 1.7;
  font-size: 14px;

  &.markdown-content {
    :deep(h1), :deep(h2), :deep(h3), :deep(h4) {
      margin: 12px 0 8px;
      font-weight: 600;
    }

    :deep(h1:first-child), :deep(h2:first-child), :deep(h3:first-child), :deep(h4:first-child) {
      margin-top: 0;
    }

    :deep(h1) { font-size: 18px; }
    :deep(h2) { font-size: 16px; }
    :deep(h3) { font-size: 15px; }
    :deep(h4) { font-size: 14px; }
    :deep(p) { margin: 6px 0; }
    :deep(ul), :deep(ol) {
      margin: 6px 0;
      padding-left: 24px;
    }
    :deep(li) { margin: 3px 0; }
    :deep(strong) { font-weight: 600; }
    :deep(code) {
      background: var(--el-fill-color);
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 0.9em;
    }
    :deep(table) {
      border-collapse: collapse;
      margin: 8px 0;
      font-size: 13px;
    }
    :deep(th), :deep(td) {
      border: 1px solid var(--el-border-color-lighter);
      padding: 4px 10px;
    }
    :deep(th) {
      background: var(--el-fill-color-light);
      font-weight: 600;
    }
  }
}

.message-tools,
.message-plan-info {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.step-results-collapse {
  margin-top: 10px;

  :deep(.el-collapse-item__header) {
    font-size: 13px;
    color: var(--el-text-color-secondary);
    height: 32px;
    line-height: 32px;
  }

  :deep(.el-collapse-item__content) {
    padding-bottom: 4px;
  }
}

.step-item {
  padding: 6px 0;
  border-bottom: 1px solid var(--el-border-color-extra-light);

  &:last-child {
    border-bottom: none;
  }
}

.step-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.step-label {
  font-weight: 600;
  color: var(--el-text-color-primary);
  white-space: nowrap;
}

.step-intent {
  flex: 1;
  color: var(--el-text-color-regular);
}

.step-tool {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 2px;
  padding-left: 2px;
}

.thinking-bubble {
  opacity: 0.95;
}

.thinking-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.thinking-main-row {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.thinking-text {
  color: var(--el-text-color-secondary);
}

.thinking-sub-row {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}

.thinking-avatar {
  animation: thinking-pulse 1.8s ease-in-out infinite;
}

.thinking-dots .dot {
  animation: thinking-blink 1.4s infinite;
  display: inline-block;
  width: 0.5em;
}

.thinking-dots .dot:nth-child(1) { animation-delay: 0s; }
.thinking-dots .dot:nth-child(2) { animation-delay: 0.2s; }
.thinking-dots .dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes thinking-blink {
  0%, 60%, 100% { opacity: 0.2; }
  30% { opacity: 1; }
}

@keyframes thinking-pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.08); }
}

.input-area {
  flex-shrink: 0;
  padding: 12px 16px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.input-row {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.send-btn {
  flex-shrink: 0;
  height: 56px;
  padding: 0 24px;
}

.input-tip {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}

:deep(.el-textarea__inner) {
  resize: none;
}

@media (max-width: 1100px) {
  .workspace-body {
    flex-direction: column;
  }

  .thread-sidebar {
    width: 100%;
    max-height: 220px;
  }
}
</style>