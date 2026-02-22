<template>
  <div class="skill-create-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <el-button text @click="goBack">
          <el-icon><ArrowLeft /></el-icon>
          返回列表
        </el-button>
        <span class="header-divider">|</span>
        <h1>🛠️ 创建新 Skill</h1>
      </div>
      <div class="header-right">
        <el-button v-if="wizardStep < 2 && sessionId" text size="small" @click="goBack">
          保存草稿
        </el-button>
      </div>
    </div>

    <!-- 步骤条 -->
    <div class="steps-bar">
      <el-steps :active="wizardStep" finish-status="success" align-center>
        <el-step title="需求沟通" />
        <el-step title="规格确认" />
        <el-step title="代码生成" />
        <el-step title="完成" />
      </el-steps>
    </div>

    <!-- 主内容区：充分利用屏幕 -->
    <div class="main-content">
      <!-- 步骤 0: 需求沟通 -->
      <div v-if="wizardStep === 0" class="wizard-chat">
        <div ref="chatContainer" class="chat-messages">
          <!-- 首次进入时的引导语 -->
          <div v-if="chatMessages.length === 0 && !chatLoading" class="requirement-guide">
            <div class="guide-header">
              <el-icon class="guide-icon"><MagicStick /></el-icon>
              <h3>如何描述你的需求？</h3>
              <p class="guide-desc">用自然语言描述你需要的工具，AI 会通过 1～3 轮对话帮你完善需求，然后自动生成代码并验证。</p>
            </div>
            <div class="guide-tips">
              <div class="tip-item">
                <span class="tip-label">💡 建议包含：</span>
                <ul>
                  <li><strong>数据来源</strong>：如东方财富、AKShare、财联社等</li>
                  <li><strong>输入参数</strong>：如股票代码、日期范围、条数限制</li>
                  <li><strong>期望输出</strong>：如新闻列表、行情数据、JSON 格式</li>
                </ul>
              </div>
              <div class="tip-item">
                <span class="tip-label">📝 示例：</span>
                <ul class="guide-examples">
                  <li>「用 AKShare 获取北向资金数据，按日期查询，返回 JSON」</li>
                  <li>「获取东方财富某只股票的最新新闻，需要标题、链接、时间」</li>
                  <li>「从财联社获取某股票的实时快讯，最多 20 条」</li>
                </ul>
              </div>
            </div>
            <p class="guide-footer">在下方输入框描述你的需求，按 <kbd>Ctrl+Enter</kbd> 或点击发送即可开始</p>
          </div>
          <div v-for="(msg, idx) in chatMessages" :key="idx"
               :class="['chat-msg', msg.role === 'user' ? 'chat-user' : 'chat-ai']">
            <div class="msg-avatar">
              <el-icon v-if="msg.role === 'user'"><User /></el-icon>
              <el-icon v-else><MagicStick /></el-icon>
            </div>
            <div class="msg-bubble">
              <div class="msg-text" v-html="renderMarkdown(msg.content)"></div>
            </div>
          </div>
          <div v-if="chatLoading" class="chat-msg chat-ai">
            <div class="msg-avatar"><el-icon><MagicStick /></el-icon></div>
            <div class="msg-bubble thinking">
              <span class="dot-animation">AI 正在分析<span>.</span><span>.</span><span>.</span></span>
            </div>
          </div>
        </div>

        <div v-if="boundaryWarning" class="boundary-alert boundary-collapsible">
          <div class="boundary-header" @click="boundaryExpanded = !boundaryExpanded">
            <el-icon class="boundary-icon"><WarningFilled /></el-icon>
            <span>复杂度提醒 ({{ boundaryCheck?.complexity_score }}/5)</span>
            <el-icon class="boundary-chevron" :class="{ expanded: boundaryExpanded }"><ArrowDown /></el-icon>
          </div>
          <div v-show="boundaryExpanded" class="boundary-content">
            <div v-for="c in boundaryCheck?.concerns" :key="c">• {{ c }}</div>
            <div v-if="boundaryCheck?.decomposition_suggestions?.length" style="margin-top: 6px">
              <strong>建议拆分为：</strong>
              <div v-for="s in boundaryCheck?.decomposition_suggestions" :key="s">→ {{ s }}</div>
            </div>
          </div>
        </div>

        <div class="chat-input-area">
          <el-input
            v-model="userInput"
            type="textarea"
            :rows="3"
            :autosize="{ minRows: 3, maxRows: 8 }"
            :placeholder="chatMessages.length === 0 ? '描述你需要的工具，例如：我需要获取东方财富个股新闻...' : (canConfirm ? '可输入方案选择（如：我选择方案C）或补充说明，确认时一并提交' : '回复 AI 的问题...')"
            :disabled="chatLoading"
            @keydown.enter.ctrl="handleChatSend"
          />
          <div class="chat-actions">
            <span class="tip">Ctrl+Enter 发送 · 第 {{ currentRound }}/{{ expectedRounds }} 轮</span>
            <div>
              <el-button v-if="canConfirm" type="success" @click="handleConfirmSpec" :loading="chatLoading">
                ✅ 确认需求，开始生成
              </el-button>
              <el-button type="primary" @click="handleChatSend" :loading="chatLoading" :disabled="!userInput.trim()">
                发送
              </el-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 步骤 1: 规格确认（当前合并到步骤 0 的确认按钮，预留占位） -->

      <!-- 步骤 2: 生成进度 -->
      <div v-if="wizardStep === 2" class="wizard-generating">
        <div class="gen-status">
          <el-icon class="gen-spinner" :size="40"><Loading /></el-icon>
          <h3>正在生成 Skill...</h3>
          <p class="gen-desc">AI 正在生成代码、验证语法、沙箱执行和质量评估</p>
        </div>
        <el-progress :percentage="Math.round(genProgress * 100) / 100" :stroke-width="14" style="margin: 24px 0; max-width: 500px; margin-left: auto; margin-right: auto;" />
        <div class="gen-steps">
          <div v-for="(s, i) in genSteps" :key="i" :class="['gen-step', s.status]">
            <el-icon v-if="s.status === 'done'"><CircleCheck /></el-icon>
            <el-icon v-else-if="s.status === 'running'" class="is-loading"><Loading /></el-icon>
            <el-icon v-else><MoreFilled /></el-icon>
            <span>{{ s.label }}</span>
          </div>
        </div>
      </div>

      <!-- 步骤 3: 完成 -->
      <div v-if="wizardStep === 3" class="wizard-done">
        <el-result
          :icon="genResult?.success ? 'success' : 'error'"
          :title="genResult?.success ? '🎉 Skill 创建成功！' : '❌ 生成失败'"
          :sub-title="genResult?.success
            ? `工具 ID: ${genResult.skill_id} · 耗时 ${genResult.total_time}s · 评分 ${genResult.final_score ?? '-'}/10`
            : genResult?.error || '请重试或修改需求'"
        >
          <template #extra>
            <el-button v-if="genResult?.success" type="primary" @click="goBack">
              查看 Skill 列表
            </el-button>
            <el-button v-else @click="wizardStep = 0">返回修改需求</el-button>
            <el-button @click="goBack">返回列表</el-button>
          </template>
        </el-result>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, ArrowDown, User, MagicStick, Loading, CircleCheck, MoreFilled, WarningFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import { skillGenerationApi } from '@/api/skillGeneration'
import type { BoundaryCheck, ConfirmResult, SessionDetail } from '@/api/skillGeneration'

marked.setOptions({ breaks: true, gfm: true })

const renderMarkdown = (content: string): string => {
  if (!content?.trim()) return ''
  try { return marked.parse(content) as string } catch { return content }
}

const route = useRoute()
const router = useRouter()

// ==================== 状态 ====================

const wizardStep = ref(0)

interface ChatMsg { role: 'user' | 'ai'; content: string }
const chatMessages = ref<ChatMsg[]>([])
const chatLoading = ref(false)
const userInput = ref('')
const chatContainer = ref<HTMLElement | null>(null)
const sessionId = ref('')
const currentRound = ref(0)
const expectedRounds = ref(3)
const boundaryCheck = ref<BoundaryCheck | null>(null)
const boundaryExpanded = ref(false)
const boundaryWarning = computed(() => boundaryCheck.value && !boundaryCheck.value.within_boundary)

watch(boundaryCheck, () => { boundaryExpanded.value = false })
const canConfirm = computed(() => chatMessages.value.length >= 2)

const genProgress = ref(0)
const genSteps = ref([
  { label: '生成代码', status: 'pending' },
  { label: '语法检查', status: 'pending' },
  { label: '安全扫描', status: 'pending' },
  { label: '沙箱执行', status: 'pending' },
  { label: '质量评估', status: 'pending' },
])
const genResult = ref<ConfirmResult | null>(null)

// ==================== 方法 ====================

const scrollChat = () => {
  nextTick(() => {
    if (chatContainer.value) chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  })
}

const goBack = () => {
  router.push('/workflow/skill-generation')
}

/** 初始化：新建或恢复草稿 */
const initFromRoute = async () => {
  const sid = route.query.sessionId as string
  if (sid) {
    try {
      const session = await skillGenerationApi.getSession(sid)
      sessionId.value = session.session_id
      currentRound.value = session.current_round
      expectedRounds.value = Math.max(3, session.rounds?.length || 0)
      boundaryCheck.value = session.boundary_check || null

      chatMessages.value = []
      for (const round of (session.rounds || [])) {
        chatMessages.value.push({ role: 'user', content: round.user_message })
        chatMessages.value.push({ role: 'ai', content: round.ai_message })
      }

      genResult.value = null
      genProgress.value = 0
      genSteps.value.forEach(s => s.status = 'pending')
      userInput.value = ''

      wizardStep.value = session.status === 'confirmed' ? 1 : 0
      scrollChat()
      ElMessage.success('已恢复草稿')
    } catch (e: any) {
      ElMessage.error('恢复草稿失败: ' + (e?.message || ''))
      wizardStep.value = 0
    }
  } else {
    wizardStep.value = 0
  }
}

const handleChatSend = async () => {
  const text = userInput.value?.trim()
  if (!text || chatLoading.value) return

  chatMessages.value.push({ role: 'user', content: text })
  userInput.value = ''
  scrollChat()
  chatLoading.value = true

  try {
    if (!sessionId.value) {
      const res = await skillGenerationApi.startSession({ description: text })
      sessionId.value = res.session_id
      currentRound.value = res.current_round
      expectedRounds.value = res.expected_rounds
      boundaryCheck.value = res.boundary_check
      chatMessages.value.push({ role: 'ai', content: res.ai_message })
    } else {
      const res = await skillGenerationApi.respondToSession(sessionId.value, text)
      currentRound.value = res.current_round
      expectedRounds.value = res.expected_rounds
      if (res.boundary_check != null) boundaryCheck.value = res.boundary_check
      chatMessages.value.push({ role: 'ai', content: res.ai_message })
    }
    scrollChat()
  } catch (e: any) {
    const msg = e?.message || e?.response?.data?.message || '请求失败'
    ElMessage.error(msg)
    chatMessages.value.push({ role: 'ai', content: `❌ 出错了：${msg}` })
    scrollChat()
  } finally {
    chatLoading.value = false
  }
}

const handleConfirmSpec = async () => {
  if (!sessionId.value) return
  // 将输入框中的内容一并传给后端（如用户选择方案 C、补充说明等）
  const confirmMessage = userInput.value?.trim() || '确认'
  if (userInput.value?.trim()) {
    chatMessages.value.push({ role: 'user', content: userInput.value.trim() })
    userInput.value = ''
    scrollChat()
  }
  chatLoading.value = true
  wizardStep.value = 2

  genSteps.value.forEach(s => s.status = 'pending')
  genProgress.value = 0
  const progressTimer = setInterval(() => {
    if (genProgress.value < 90) {
      genProgress.value = Math.round((genProgress.value + Math.random() * 15) * 100) / 100
      const thresholds = [10, 25, 45, 65, 80]
      thresholds.forEach((t, i) => {
        if (genProgress.value >= t && genSteps.value[i].status === 'pending') {
          genSteps.value[i].status = 'running'
        }
        if (i > 0 && genSteps.value[i].status === 'running') {
          genSteps.value[i - 1].status = 'done'
        }
      })
    }
  }, 800)

  try {
    const res = await skillGenerationApi.confirmSpec(sessionId.value, confirmMessage)
    clearInterval(progressTimer)
    genProgress.value = 100
    genSteps.value.forEach(s => s.status = 'done')
    genResult.value = res
    wizardStep.value = 3
  } catch (e: any) {
    clearInterval(progressTimer)
    genResult.value = {
      status: 'failed', session_id: sessionId.value, skill_id: null,
      spec: null, success: false, total_rounds: 0, total_time: 0,
      final_score: null, error: e?.message || '生成失败'
    }
    wizardStep.value = 3
  } finally {
    chatLoading.value = false
  }
}

onMounted(() => {
  initFromRoute()
})
</script>

<style lang="scss" scoped>
.skill-create-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 60px);
  min-height: 500px;
  padding: 16px 24px;
  background: var(--el-bg-color-page);
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  margin-bottom: 16px;

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;

    .header-divider {
      color: var(--el-border-color);
      font-size: 14px;
    }

    h1 {
      font-size: 18px;
      margin: 0;
      font-weight: 600;
    }
  }
}

.steps-bar {
  flex-shrink: 0;
  margin-bottom: 20px;
  padding: 12px 24px;
  background: var(--el-bg-color);
  border-radius: 8px;
  border: 1px solid var(--el-border-color-lighter);
}

.main-content {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--el-bg-color);
  border-radius: 8px;
  border: 1px solid var(--el-border-color-lighter);
  padding: 20px;
  overflow: hidden;
}

/* ========== 需求沟通（全屏利用） ========== */
.wizard-chat {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
  margin-bottom: 12px;
}

/* 需求提交引导语 */
.requirement-guide {
  padding: 24px 20px;
  color: var(--el-text-color-regular);
  font-size: 14px;
  line-height: 1.7;

  .guide-header {
    text-align: center;
    margin-bottom: 24px;

    .guide-icon {
      font-size: 48px;
      color: var(--el-color-primary);
      margin-bottom: 12px;
    }

    h3 {
      font-size: 18px;
      margin: 0 0 8px;
      font-weight: 600;
      color: var(--el-text-color-primary);
    }

    .guide-desc {
      margin: 0;
      color: var(--el-text-color-secondary);
      font-size: 14px;
    }
  }

  .guide-tips {
    background: var(--el-bg-color);
    border: 1px solid var(--el-border-color-lighter);
    border-radius: 8px;
    padding: 16px 20px;
    margin-bottom: 20px;
  }

  .tip-item {
    margin-bottom: 16px;

    &:last-child {
      margin-bottom: 0;
    }

    .tip-label {
      display: block;
      font-weight: 500;
      margin-bottom: 8px;
      color: var(--el-text-color-primary);
    }

    ul {
      margin: 0;
      padding-left: 20px;
      color: var(--el-text-color-regular);

      li {
        margin-bottom: 6px;
      }
    }

    .guide-examples li {
      color: var(--el-text-color-secondary);
      font-style: italic;
    }
  }

  .guide-footer {
    text-align: center;
    margin: 0;
    font-size: 13px;
    color: var(--el-text-color-placeholder);

    kbd {
      display: inline-block;
      padding: 2px 6px;
      font-size: 12px;
      background: var(--el-fill-color);
      border: 1px solid var(--el-border-color);
      border-radius: 4px;
      font-family: inherit;
    }
  }
}

.chat-msg {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;

  &.chat-user { flex-direction: row-reverse; }

  .msg-avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    background: var(--el-color-primary-light-8);
    color: var(--el-color-primary);
    font-size: 18px;
  }

  &.chat-user .msg-avatar {
    background: var(--el-color-success-light-8);
    color: var(--el-color-success);
  }

  .msg-bubble {
    max-width: 75%;
    padding: 12px 16px;
    border-radius: 12px;
    background: var(--el-bg-color);
    border: 1px solid var(--el-border-color-lighter);
    line-height: 1.7;
    font-size: 14px;

    &.thinking {
      color: var(--el-text-color-secondary);
      font-style: italic;
    }
  }

  &.chat-user .msg-bubble {
    background: var(--el-color-primary-light-9);
    border-color: var(--el-color-primary-light-7);
  }
}

.msg-text {
  :deep(p) { margin: 0 0 6px; }
  :deep(ul), :deep(ol) { margin: 6px 0; padding-left: 24px; }
  :deep(table) {
    border-collapse: collapse;
    width: 100%;
    font-size: 13px;
    th, td { border: 1px solid var(--el-border-color); padding: 8px 12px; }
    th { background: var(--el-fill-color-light); }
  }
}

.dot-animation span {
  animation: blink 1.4s infinite both;
  &:nth-child(2) { animation-delay: 0.2s; }
  &:nth-child(3) { animation-delay: 0.4s; }
}
@keyframes blink { 0%, 80%, 100% { opacity: 0; } 40% { opacity: 1; } }

.boundary-alert {
  flex-shrink: 0;
  margin-bottom: 12px;
}

.boundary-collapsible {
  border: 1px solid var(--el-color-warning-light-5);
  border-radius: 8px;
  background: var(--el-color-warning-light-9);
  overflow: hidden;
}

.boundary-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  cursor: pointer;
  user-select: none;
  font-size: 14px;
  color: var(--el-color-warning-dark-2);
  &:hover { background: var(--el-color-warning-light-8); }

  .boundary-icon { font-size: 18px; color: var(--el-color-warning); }
  .boundary-chevron {
    margin-left: auto;
    transition: transform 0.2s;
    &.expanded { transform: rotate(180deg); }
  }
}

.boundary-content {
  padding: 0 12px 12px 36px;
  font-size: 13px;
  color: var(--el-text-color-regular);
  line-height: 1.6;
}

.chat-input-area {
  flex-shrink: 0;
}

.chat-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;

  .tip { color: var(--el-text-color-placeholder); font-size: 12px; }
}

/* ========== 生成进度 ========== */
.wizard-generating {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;

  .gen-status {
    text-align: center;
    h3 { margin: 16px 0 8px; font-size: 18px; }
    .gen-desc { color: var(--el-text-color-secondary); font-size: 14px; }
  }
}

.gen-spinner { animation: spin 1.5s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.gen-steps {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 24px;
  margin-top: 24px;
}

.gen-step {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: var(--el-text-color-secondary);

  &.done { color: var(--el-color-success); }
  &.running { color: var(--el-color-primary); font-weight: 500; }
}

/* ========== 完成 ========== */
.wizard-done {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}
</style>
