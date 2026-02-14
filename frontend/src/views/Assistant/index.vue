<template>
  <div class="assistant-page">
    <!-- 紧凑头部 -->
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
        <el-tag v-if="loading" type="info" size="small">思考中...</el-tag>
        <el-button
          v-else-if="messages.length > 0"
          type="default"
          size="small"
          link
          @click="handleClear"
        >
          清空对话
        </el-button>
      </div>
    </div>

    <!-- 对话区域 -->
    <div class="chat-body">
      <!-- 消息列表 -->
      <div ref="messagesContainer" class="messages-container">
        <el-empty
          v-if="messages.length === 0 && !loading"
          description="输入问题开始对话，例如：茅台最近一周走势如何？白酒板块资金流向怎样？"
          :image-size="80"
        />
        <div v-else class="messages-list">
          <!-- 思考中占位气泡 -->
          <div v-if="loading" class="message-item message-assistant thinking-bubble">
            <div class="message-avatar">
              <el-icon><ChatDotRound /></el-icon>
            </div>
            <div class="message-content thinking-content">
              <span class="thinking-text">{{ analysisMode === 'planned' ? '正在规划并执行深度分析' : '智能助手正在分析并调用工具' }}</span>
              <span class="thinking-dots">
                <span class="dot">.</span><span class="dot">.</span><span class="dot">.</span>
              </span>
            </div>
          </div>
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
                  <el-tag v-for="t in msg.tools_used" :key="t" size="small" type="info">{{ t }}</el-tag>
                </div>
                <!-- 规划分析来源标签 -->
                <div v-if="msg.source" class="message-plan-info">
                  <el-tag :type="msg.source === 'seed_flow' ? 'success' : msg.source === 'llm_plan' ? 'primary' : 'warning'" size="small" effect="plain">
                    {{ msg.source === 'seed_flow' ? '🌱 种子流程' : msg.source === 'llm_plan' ? '🧠 LLM 规划' : '⚡ ReAct' }}
                  </el-tag>
                  <el-tag v-if="msg.supplemented" type="warning" size="small" effect="plain">📎 已补充</el-tag>
                </div>
                <!-- 执行步骤折叠面板 -->
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
        </div>
      </div>

      <!-- 输入区域 -->
      <div class="input-area">
        <div class="input-row">
          <el-input
            v-model="inputMessage"
            type="textarea"
            :rows="2"
            :autosize="{ minRows: 2, maxRows: 5 }"
            placeholder="输入您的问题，如：600519 的 PE 是多少？光伏板块最近表现如何？"
            :disabled="loading"
            @keydown.enter.ctrl="handleSend"
          />
          <el-button
            type="primary"
            :loading="loading"
            :disabled="!inputMessage.trim()"
            class="send-btn"
            @click="handleSend"
          >
            发送
          </el-button>
        </div>
        <span class="input-tip">Ctrl+Enter 发送</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'
import { ChatDotRound, User, DataAnalysis, QuestionFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'
import { assistantApi } from '@/api/assistant'
import type { MessageItem } from '@/api/assistant'

marked.setOptions({ breaks: true, gfm: true })

const renderMarkdown = (content: string): string => {
  if (!content?.trim()) return ''
  try {
    return marked.parse(content) as string
  } catch {
    return content
  }
}

const inputMessage = ref('')
const loading = ref(false)
const analysisMode = ref<'react' | 'planned'>('react')

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

const messages = ref<DisplayMessage[]>([])
const messagesContainer = ref<HTMLElement | null>(null)

const loadConversation = async () => {
  try {
    const res = await assistantApi.getConversation()
    if (res.messages?.length) {
      messages.value = res.messages.map((m: MessageItem) => ({
        role: m.role as 'user' | 'assistant',
        content: m.content,
        tools_used: m.tools_used
      }))
      nextTick(scrollToBottom)
    }
  } catch {
    // 未登录或网络异常时静默忽略
  }
}

const handleClear = () => {
  ElMessageBox.confirm('确定清空所有对话记录吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      await assistantApi.clearConversation()
      messages.value = []
      ElMessage.success('已清空对话')
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : '清空失败'
      ElMessage.error(errMsg)
    }
  }).catch(() => {})
}

onMounted(loadConversation)

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      const el = messagesContainer.value
      el.scrollTop = el.scrollHeight
    }
  })
}

const handleSend = async () => {
  const text = inputMessage.value?.trim()
  if (!text || loading.value) return

  messages.value.push({ role: 'user', content: text })
  inputMessage.value = ''
  scrollToBottom()

  loading.value = true
  try {
    if (analysisMode.value === 'planned') {
      const res = await assistantApi.plannedAnalysis(text)
      messages.value.push({
        role: 'assistant',
        content: res.reply,
        tools_used: res.tools_used?.length ? res.tools_used : undefined,
        source: res.source,
        supplemented: res.supplemented,
        step_results: res.step_results,
      })
    } else {
      const res = await assistantApi.chat(text)
      messages.value.push({
        role: 'assistant',
        content: res.reply,
        tools_used: res.tools_used?.length ? res.tools_used : undefined,
      })
    }
    scrollToBottom()
  } catch (e: unknown) {
    const errMsg = e instanceof Error ? e.message : '请求失败，请稍后重试'
    ElMessage.error(errMsg)
    messages.value.push({
      role: 'assistant',
      content: `抱歉，处理您的请求时出错：${errMsg}`,
      tools_used: []
    })
    scrollToBottom()
  } finally {
    loading.value = false
  }
}
</script>

<style lang="scss" scoped>
/* ========== 全屏 flex 布局 ========== */
.assistant-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 60px);  /* 减去顶部导航栏高度 */
  padding: 0 16px 16px;
  overflow: hidden;
}

/* ========== 紧凑头部：一行放下标题 + 提示 + 模式 + 操作 ========== */
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

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.page-title {
  font-size: 18px;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;

  .title-icon {
    font-size: 22px;
  }
}

.risk-tag {
  font-size: 12px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;

  .mode-help {
    color: var(--el-text-color-secondary);
    cursor: pointer;
    font-size: 16px;
  }
}

/* ========== 对话主体：flex:1 填满剩余空间 ========== */
.chat-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;  /* 关键：允许 flex 子元素收缩 */
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  margin-top: 12px;
  background: var(--el-bg-color);
}

/* ========== 消息容器：flex:1 自适应高度 ========== */
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

/* ========== 消息气泡 ========== */
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

.message-tools {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.message-plan-info {
  margin-top: 8px;
  display: flex;
  gap: 6px;
  align-items: center;
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

  &:last-child { border-bottom: none; }

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
}

/* ========== 思考中动画 ========== */
.thinking-bubble { opacity: 0.95; }
.thinking-content {
  display: flex;
  align-items: baseline;
  gap: 2px;
}
.thinking-text { color: var(--el-text-color-secondary); }
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

/* ========== 输入区域：底部固定 ========== */
.input-area {
  flex-shrink: 0;
  padding: 12px 16px;
  border-top: 1px solid var(--el-border-color-lighter);

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
}
</style>
