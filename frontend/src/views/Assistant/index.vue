<template>
  <div class="assistant-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <h1 class="page-title">
          <el-icon class="title-icon"><ChatDotRound /></el-icon>
          智能助手
        </h1>
        <div class="risk-disclaimer">
          <el-alert type="warning" :closable="false" show-icon>
            <template #title>
              <span style="font-size: 14px;">
                <strong>⚠️ 重要提示：</strong>分析结论用于学习验证 AI 股票分析技术，不构成投资建议。
              </span>
            </template>
          </el-alert>
        </div>
        <p class="page-description">
          自然语言提问，助手自主选择工具获取数据并生成回答。支持行情、财务、新闻、技术面等查询。
        </p>
      </div>
    </div>

    <!-- 对话区域 -->
    <el-card class="chat-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span>对话</span>
          <el-tag v-if="loading" type="info" size="small">思考中...</el-tag>
        </div>
      </template>

      <!-- 消息列表 -->
      <div ref="messagesContainer" class="messages-container">
        <el-empty
          v-if="messages.length === 0 && !loading"
          description="输入问题开始对话，例如：茅台最近一周走势如何？白酒板块资金流向怎样？"
          :image-size="80"
        />
        <div v-else class="messages-list">
          <div
            v-for="(msg, idx) in messages"
            :key="idx"
            :class="['message-item', msg.role === 'user' ? 'message-user' : 'message-assistant']"
          >
            <div class="message-avatar">
              <el-icon v-if="msg.role === 'user'"><User /></el-icon>
              <el-icon v-else><ChatDotRound /></el-icon>
            </div>
            <div class="message-content">
              <div class="message-text">{{ msg.content }}</div>
              <div v-if="msg.role === 'assistant' && msg.tools_used?.length" class="message-tools">
                <el-tag v-for="t in msg.tools_used" :key="t" size="small" type="info">{{ t }}</el-tag>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区域 -->
      <div class="input-area">
        <el-input
          v-model="inputMessage"
          type="textarea"
          :rows="3"
          placeholder="输入您的问题，如：600519 的 PE 是多少？光伏板块最近表现如何？"
          :disabled="loading"
          @keydown.enter.ctrl="handleSend"
        />
        <div class="input-actions">
          <span class="input-tip">Ctrl+Enter 发送</span>
          <el-button
            type="primary"
            :loading="loading"
            :disabled="!inputMessage.trim()"
            @click="handleSend"
          >
            发送
          </el-button>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { ChatDotRound, User } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { assistantApi } from '@/api/assistant'

const inputMessage = ref('')
const loading = ref(false)
const messages = ref<Array<{ role: 'user' | 'assistant'; content: string; tools_used?: string[] }>>([])
const messagesContainer = ref<HTMLElement | null>(null)

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
    const res = await assistantApi.chat(text)
    messages.value.push({
      role: 'assistant',
      content: res.reply,
      tools_used: res.tools_used?.length ? res.tools_used : undefined
    })
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
.assistant-page {
  padding: 16px;
  max-width: 900px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 20px;

  .page-title {
    font-size: 24px;
    margin: 0 0 12px 0;
    display: flex;
    align-items: center;
    gap: 8px;

    .title-icon {
      font-size: 28px;
    }
  }

  .risk-disclaimer {
    margin-bottom: 8px;
  }

  .page-description {
    color: var(--el-text-color-secondary);
    font-size: 14px;
    margin: 0;
  }
}

.chat-card {
  :deep(.el-card__body) {
    padding: 0;
    display: flex;
    flex-direction: column;
  }
}

.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.messages-container {
  min-height: 320px;
  max-height: 420px;
  overflow-y: auto;
  padding: 16px;
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

  &.message-user {
    .message-avatar {
      background: var(--el-color-primary-light-9);
      color: var(--el-color-primary);
    }
    .message-content {
      background: var(--el-color-primary-light-9);
      border-radius: 12px;
      padding: 12px 16px;
    }
  }

  &.message-assistant {
    .message-avatar {
      background: var(--el-fill-color-light);
      color: var(--el-text-color-regular);
    }
    .message-content {
      background: var(--el-fill-color-lighter);
      border-radius: 12px;
      padding: 12px 16px;
    }
  }
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.message-text {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
}

.message-tools {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.input-area {
  padding: 16px;
  border-top: 1px solid var(--el-border-color-lighter);

  .input-actions {
    margin-top: 12px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .input-tip {
    font-size: 12px;
    color: var(--el-text-color-placeholder);
  }
}
</style>
