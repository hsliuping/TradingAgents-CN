<template>
  <div class="assistant-chat-section" id="assistant-chat" ref="chatSectionRef">
    <div class="assistant-chat-header">
      <div class="header-top-row">
        <div class="assistant-chat-title">
          <span>🤖</span>
          <span>智能研究助手 · 全景解读</span>
        </div>
        <span class="header-meta">{{ loadedSummary }}</span>
      </div>
      <div class="header-topic-bar">
        <span class="topic-pin">📌</span>
        <span class="topic-text">当前主题限定于：<strong>{{ code }} {{ stockName || '-' }}</strong></span>
        <span class="topic-hint">超出此股票的问题将引导你前往主页面</span>
      </div>
    </div>
    <div class="chat-messages" ref="messagesRef">
      <div v-if="!messages.length" class="chat-empty">
        <div class="chat-empty-icon">🤖</div>
        <div class="chat-empty-text">
          你好！我已经读取了 <strong>{{ code }} {{ stockName || '-' }}</strong> 的研究数据。<br />
          你可以问我任何关于这只股票的问题，我会结合分析结果、持仓、复盘、基本面为你全景解读。
        </div>
      </div>
      <div
        v-for="(msg, idx) in messages"
        :key="idx"
        class="chat-message"
        :class="msg.role"
      >
        <div class="chat-avatar">
          {{ msg.role === 'user' ? '👤' : '🤖' }}
        </div>
        <div class="chat-bubble markdown-body" v-html="renderMarkdown(msg.content)"></div>
      </div>
      <div v-if="loading" class="chat-message bot">
        <div class="chat-avatar">🤖</div>
        <div class="chat-bubble chat-loading">
          <span class="dot"></span><span class="dot"></span><span class="dot"></span>
        </div>
      </div>
    </div>
    <div class="chat-input-area">
      <textarea
        ref="inputRef"
        v-model="inputText"
        class="chat-input"
        rows="1"
        :placeholder="inputPlaceholder"
        @keydown.enter.exact.prevent="send"
        @keydown.ctrl.enter="send"
      ></textarea>
      <button class="chat-send-btn" @click="send" :disabled="!inputText.trim() || loading">
        {{ loading ? '思考中...' : '发送' }}
      </button>
    </div>
    <div class="chat-disclaimer">
      助手回答基于已加载的研究数据生成，仅供研究参考，不构成投资建议。
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, computed, watch } from 'vue'
import { renderMarkdown } from '@/utils/markdown'

interface ChatMessage {
  role: 'user' | 'bot'
  content: string
}

const props = defineProps<{
  code: string
  stockName: string
  loadedModules: string[]
  initialPrompt?: string
  loading?: boolean
  inputPlaceholder?: string
}>()

const emit = defineEmits<{
  (e: 'ask', prompt: string): void
}>()

const messages = defineModel<ChatMessage[]>('messages', { default: [] })
const inputText = ref('')
const messagesRef = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLTextAreaElement | null>(null)
const chatSectionRef = ref<HTMLElement | null>(null)

const loadedSummary = computed(() => {
  if (!props.loadedModules.length) return '正在加载数据'
  return `已加载：${props.loadedModules.join(' · ')}`
})

function send() {
  const text = inputText.value.trim()
  if (!text || props.loading) return
  // 本地追加用户消息
  messages.value.push({ role: 'user', content: text })
  inputText.value = ''
  emit('ask', text)
  nextTick(() => scrollToBottom())
}

function scrollToBottom() {
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
}

// 接收外部预填问题（来自 AssistantHero 的快捷按钮）
function fillPrompt(prompt: string) {
  inputText.value = prompt
  if (chatSectionRef.value) {
    chatSectionRef.value.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  nextTick(() => {
    inputRef.value?.focus()
  })
}

// 监听 initialPrompt 变化（用于 AssistantHero 点击后填入）
watch(() => props.initialPrompt, (val) => {
  if (val) fillPrompt(val)
})

defineExpose({ fillPrompt, scrollToBottom })
</script>

<style scoped>
.assistant-chat-section {
  background: var(--el-bg-color, #fff);
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  border: 1px solid #f1f5f9;
  overflow: hidden;
  margin-bottom: 16px;
}

.assistant-chat-header {
  padding: 12px 20px;
  background: linear-gradient(135deg, #6b5ce7 0%, #8b5cf6 100%);
  color: #fff;
}

.header-top-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.assistant-chat-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 15px;
  font-weight: 700;
}

.header-meta {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.85);
}

.header-topic-bar {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 12px;
}

.topic-pin {
  font-size: 13px;
}

.topic-text {
  color: rgba(255, 255, 255, 0.95);
}

.topic-text strong {
  color: #fff;
  font-weight: 600;
}

.topic-hint {
  color: rgba(255, 255, 255, 0.7);
  font-size: 11px;
  margin-left: auto;
}

.chat-messages {
  max-height: 380px;
  overflow-y: auto;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chat-empty {
  padding: 20px;
  text-align: center;
}

.chat-empty-icon {
  font-size: 32px;
  margin-bottom: 10px;
}

.chat-empty-text {
  font-size: 13px;
  color: #64748b;
  line-height: 1.7;
}

.chat-message {
  display: flex;
  gap: 10px;
  max-width: 85%;
}

.chat-message.user {
  flex-direction: row-reverse;
  align-self: flex-end;
}

.chat-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
}

.chat-message.bot .chat-avatar {
  background: linear-gradient(135deg, #6b5ce7 0%, #8b5cf6 100%);
}

.chat-message.user .chat-avatar {
  background: #3b82f6;
}

.chat-bubble {
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.6;
}

.chat-message.bot .chat-bubble {
  background: #f8fafc;
  color: #1e293b;
  border-bottom-left-radius: 4px;
}

.chat-message.user .chat-bubble {
  background: #6b5ce7;
  color: #fff;
  border-bottom-right-radius: 4px;
}

.chat-loading {
  display: flex;
  gap: 4px;
  align-items: center;
}

.chat-loading .dot {
  width: 6px;
  height: 6px;
  background: #94a3b8;
  border-radius: 50%;
  animation: dotPulse 1.4s infinite ease-in-out;
}

.chat-loading .dot:nth-child(2) {
  animation-delay: 0.2s;
}

.chat-loading .dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes dotPulse {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
}

.chat-input-area {
  display: flex;
  gap: 8px;
  align-items: flex-end;
  padding: 12px 20px;
  border-top: 1px solid #f1f5f9;
}

.chat-input {
  flex: 1;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 13px;
  resize: none;
  outline: none;
  max-height: 80px;
  min-height: 40px;
  font-family: inherit;
  background: var(--el-bg-color, #fff);
  color: var(--el-text-color-primary, #1e293b);
}

.chat-input:focus {
  border-color: #6b5ce7;
}

.chat-send-btn {
  padding: 10px 20px;
  border-radius: 8px;
  border: none;
  background: linear-gradient(135deg, #6b5ce7 0%, #8b5cf6 100%);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
}

.chat-send-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.chat-send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.chat-disclaimer {
  padding: 8px 20px 12px;
  font-size: 11px;
  color: #94a3b8;
  text-align: center;
}
</style>
