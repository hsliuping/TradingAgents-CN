<template>
  <div class="wf-gen-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <el-button text @click="goBack">
          <el-icon><ArrowLeft /></el-icon>
          返回列表
        </el-button>
        <span class="header-divider">|</span>
        <h1>🤖 AI 工作流架构师</h1>
      </div>
      <div class="header-right">
        <el-button v-if="step < 2 && sessionId" text size="small" @click="goBack">
          保存草稿
        </el-button>
      </div>
    </div>

    <!-- 步骤条 -->
    <div class="steps-bar">
      <el-steps :active="step" finish-status="success" align-center>
        <el-step title="需求沟通" />
        <el-step title="方案确认" />
        <el-step title="自动补全" />
        <el-step title="完成" />
      </el-steps>
    </div>

    <!-- 主内容区 -->
    <div class="main-content">
      <!-- 步骤 0: 需求沟通 -->
      <div v-if="step === 0" class="wizard-chat">
        <div ref="chatContainer" class="chat-messages">
          <!-- 首次进入引导语 -->
          <div v-if="chatMessages.length === 0 && !chatLoading" class="requirement-guide">
            <div class="guide-header">
              <el-icon class="guide-icon"><Connection /></el-icon>
              <h3>描述你想要的分析流程</h3>
              <p class="guide-desc">用自然语言描述需求，AI 会分析可用的 Agent、工具和提示词，为你设计完整的工作流方案。</p>
            </div>
            <div class="guide-tips">
              <div class="tip-item">
                <span class="tip-label">💡 建议包含：</span>
                <ul>
                  <li><strong>分析目标</strong>：如 ETF 分析、可转债筛选、行业对比</li>
                  <li><strong>分析维度</strong>：如技术面、基本面、新闻、社交媒体</li>
                  <li><strong>特殊要求</strong>：如需要辩论环节、风险评估、多轮讨论</li>
                </ul>
              </div>
              <div class="tip-item">
                <span class="tip-label">📝 示例：</span>
                <ul class="guide-examples">
                  <li>「我想做一个 ETF 分析流程，需要分析市场走势、基本面和新闻」</li>
                  <li>「设计一个可转债筛选流程，包含技术分析和风险评估」</li>
                  <li>「创建行业对比分析流程，多个分析师并行分析后辩论得出结论」</li>
                </ul>
              </div>
            </div>
            <p class="guide-footer">在下方输入框描述你的需求，按 <kbd>Ctrl+Enter</kbd> 或点击发送即可开始</p>
          </div>
          <!-- 对话消息 -->
          <div v-for="(msg, idx) in chatMessages" :key="idx"
               :class="['chat-msg', msg.role === 'user' ? 'chat-user' : 'chat-ai']">
            <div class="msg-avatar">
              <el-icon v-if="msg.role === 'user'"><User /></el-icon>
              <el-icon v-else><Connection /></el-icon>
            </div>
            <div class="msg-bubble">
              <div class="msg-text" v-html="renderMarkdown(msg.content)"></div>
            </div>
          </div>
          <!-- 思考中 -->
          <div v-if="chatLoading" class="chat-msg chat-ai">
            <div class="msg-avatar"><el-icon><Connection /></el-icon></div>
            <div class="msg-bubble thinking">
              <span class="dot-animation"><span>●</span><span>●</span><span>●</span></span>
              AI 正在分析资源并规划方案...
            </div>
          </div>
        </div>

        <!-- 输入区 -->
        <div class="chat-input-area">
          <el-input
            v-model="userInput"
            type="textarea"
            :rows="3"
            :autosize="{ minRows: 3, maxRows: 8 }"
            :placeholder="chatMessages.length === 0
              ? '描述你想要的分析流程，例如：我想做一个 ETF 综合分析流程...'
              : (canConfirm ? '可以继续补充需求，或点击「确认方案，开始创建」' : '回复 AI 的问题...')"
            :disabled="chatLoading"
            @keydown.enter.ctrl="handleSend"
          />
          <div class="chat-actions">
            <span class="tip">Ctrl+Enter 发送 · 第 {{ currentRound }} 轮</span>
            <div>
              <el-button v-if="canConfirm" type="success" @click="handleConfirm" :loading="chatLoading">
                ✅ 确认方案，开始创建
              </el-button>
              <el-button type="primary" @click="handleSend" :loading="chatLoading" :disabled="!userInput.trim()">
                发送
              </el-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 步骤 1: 方案确认（由 handleConfirm 自动跳过到步骤2） -->

      <!-- 步骤 2: 自动补全进度 -->
      <div v-if="step === 2" class="wizard-generating">
        <div class="gen-status">
          <el-icon class="gen-spinner" :size="40"><Loading /></el-icon>
          <h3>正在创建工作流...</h3>
          <p class="gen-desc">AI 正在生成蓝图、创建提示词、补齐工具并组装工作流</p>
        </div>
        <el-progress :percentage="genProgress" :stroke-width="14"
          style="margin: 24px 0; max-width: 500px; margin-left: auto; margin-right: auto;" />
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
      <div v-if="step === 3" class="wizard-done">
        <el-result
          :icon="confirmResult?.workflow_id ? 'success' : 'error'"
          :title="confirmResult?.workflow_id ? '🎉 工作流创建成功！' : '❌ 创建失败'"
          :sub-title="confirmResult?.workflow_id
            ? `工作流 ID: ${confirmResult.workflow_id}`
            : confirmResult?.error || '请重试或修改需求'"
        >
          <!-- 创建报告 -->
          <template #extra>
            <div v-if="confirmResult?.creation_report" class="creation-report">
              <h4>📋 创建报告</h4>
              <div class="report-section" v-if="confirmResult.creation_report.prompts_created?.length">
                <p class="report-label">✅ 已创建工作流专属提示词：</p>
                <el-tag v-for="p in confirmResult.creation_report.prompts_created" :key="p.agent_id"
                  size="small" type="success" style="margin: 2px 4px;">
                  {{ p.agent_id }} → {{ p.new_role }}
                </el-tag>
              </div>
              <div class="report-section" v-if="confirmResult.creation_report.prompts_default?.length">
                <p class="report-label">📝 使用默认提示词：</p>
                <el-tag v-for="a in confirmResult.creation_report.prompts_default" :key="a"
                  size="small" type="info" style="margin: 2px 4px;">
                  {{ a }}
                </el-tag>
              </div>
              <div class="report-section" v-if="confirmResult.creation_report.skills_created?.length">
                <p class="report-label">🔧 已创建新 Skill：</p>
                <el-tag v-for="s in confirmResult.creation_report.skills_created" :key="s.skill_id"
                  size="small" type="warning" style="margin: 2px 4px;">
                  {{ s.name || s.skill_id }}
                </el-tag>
              </div>
              <div class="report-section" v-if="confirmResult.creation_report.skills_failed?.length">
                <p class="report-label">⚠️ Skill 创建失败：</p>
                <el-tag v-for="s in confirmResult.creation_report.skills_failed" :key="s.name"
                  size="small" type="danger" style="margin: 2px 4px;">
                  {{ s.name }}: {{ s.error }}
                </el-tag>
              </div>
            </div>

            <div class="result-actions">
              <el-button v-if="confirmResult?.workflow_id" type="primary"
                @click="router.push(`/workflow/editor/${confirmResult.workflow_id}`)">
                <el-icon><Edit /></el-icon>
                打开编辑器
              </el-button>
              <el-button v-if="confirmResult?.workflow_id" @click="showOptimizeInput = true">
                <el-icon><RefreshRight /></el-icon>
                迭代优化
              </el-button>
              <el-button v-if="!confirmResult?.workflow_id" @click="step = 0">
                返回修改需求
              </el-button>
              <el-button @click="goBack">返回列表</el-button>
            </div>
          </template>
        </el-result>

        <!-- 迭代优化输入 -->
        <div v-if="showOptimizeInput" class="optimize-section">
          <h4>🔄 迭代优化</h4>
          <p class="optimize-desc">描述运行后发现的问题或改进需求，AI 会调整工作流结构、提示词或工具配置。</p>
          <el-input v-model="optimizeFeedback" type="textarea" :rows="3"
            placeholder="例如：分析结果缺少对比分析维度，能否增加行业对比分析师？" />
          <div class="optimize-actions">
            <el-button @click="showOptimizeInput = false">取消</el-button>
            <el-button type="primary" @click="handleOptimize" :loading="optimizing"
              :disabled="!optimizeFeedback.trim()">
              提交优化
            </el-button>
          </div>
          <!-- 优化结果 -->
          <div v-if="optimizeMessage" class="optimize-result">
            <div class="msg-text" v-html="renderMarkdown(optimizeMessage)"></div>
            <div class="optimize-confirm-actions">
              <el-button type="success" @click="handleConfirmOptimize" :loading="optimizing">
                ✅ 确认并应用优化
              </el-button>
              <el-button @click="optimizeMessage = ''">取消</el-button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, User, Connection, Loading, CircleCheck, MoreFilled, Edit, RefreshRight } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import { workflowGenerationApi } from '@/api/workflowGeneration'
import type { WfConfirmResult } from '@/api/workflowGeneration'

marked.setOptions({ breaks: true, gfm: true })

const renderMarkdown = (content: string): string => {
  if (!content?.trim()) return ''
  try { return marked.parse(content) as string } catch { return content }
}

const route = useRoute()
const router = useRouter()

// ==================== 状态 ====================

const step = ref(0)

interface ChatMsg { role: 'user' | 'ai'; content: string }
const chatMessages = ref<ChatMsg[]>([])
const chatLoading = ref(false)
const userInput = ref('')
const chatContainer = ref<HTMLElement | null>(null)
const sessionId = ref('')
const currentRound = ref(0)

const canConfirm = computed(() => chatMessages.value.length >= 2)

// 生成进度
const genProgress = ref(0)
const genSteps = ref([
  { label: '生成蓝图', status: 'pending' },
  { label: '创建提示词', status: 'pending' },
  { label: '补齐 Skill', status: 'pending' },
  { label: '组装工作流', status: 'pending' },
])

// 结果
const confirmResult = ref<WfConfirmResult | null>(null)

// 优化
const showOptimizeInput = ref(false)
const optimizeFeedback = ref('')
const optimizeMessage = ref('')
const optimizing = ref(false)

// ==================== 方法 ====================

const goBack = () => {
  router.push('/workflow')
}

const scrollChat = () => {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

/** 发送消息 */
const handleSend = async () => {
  const text = userInput.value?.trim()
  if (!text || chatLoading.value) return

  chatMessages.value.push({ role: 'user', content: text })
  userInput.value = ''
  scrollChat()
  chatLoading.value = true

  try {
    if (!sessionId.value) {
      const res = await workflowGenerationApi.startSession({ description: text })
      sessionId.value = res.session_id
      currentRound.value = res.current_round
      chatMessages.value.push({ role: 'ai', content: res.ai_message })
    } else {
      const res = await workflowGenerationApi.respondToSession(sessionId.value, text)
      currentRound.value = res.current_round
      chatMessages.value.push({ role: 'ai', content: res.ai_message })
    }
  } catch (e: any) {
    chatMessages.value.push({ role: 'ai', content: `❌ 出错了: ${e?.message || '请重试'}` })
  } finally {
    chatLoading.value = false
    scrollChat()
  }
}

/** 确认方案并创建 */
const handleConfirm = async () => {
  if (!sessionId.value) {
    ElMessage.warning('请先描述需求')
    return
  }
  chatLoading.value = true
  step.value = 2

  // 模拟进度
  genSteps.value.forEach(s => s.status = 'pending')
  genProgress.value = 0

  const progressSteps = [
    { idx: 0, pct: 25 },
    { idx: 1, pct: 50 },
    { idx: 2, pct: 75 },
    { idx: 3, pct: 90 },
  ]

  // 启动进度模拟
  let progressIdx = 0
  const progressTimer = setInterval(() => {
    if (progressIdx < progressSteps.length) {
      const ps = progressSteps[progressIdx]
      genSteps.value[ps.idx].status = 'running'
      if (ps.idx > 0) genSteps.value[ps.idx - 1].status = 'done'
      genProgress.value = ps.pct
      progressIdx++
    }
  }, 2000)

  try {
    const res = await workflowGenerationApi.confirmAndCreate(sessionId.value)
    clearInterval(progressTimer)
    genSteps.value.forEach(s => s.status = 'done')
    genProgress.value = 100
    confirmResult.value = res

    setTimeout(() => { step.value = 3 }, 600)
  } catch (e: any) {
    clearInterval(progressTimer)
    confirmResult.value = { status: 'failed', session_id: sessionId.value, error: e?.message || '创建失败' }
    step.value = 3
  } finally {
    chatLoading.value = false
  }
}


/** 提交优化 */
const handleOptimize = async () => {
  if (!optimizeFeedback.value.trim() || !sessionId.value) return
  optimizing.value = true
  try {
    const res = await workflowGenerationApi.optimize(sessionId.value, optimizeFeedback.value.trim())
    optimizeMessage.value = res.ai_message
  } catch (e: any) {
    ElMessage.error(`优化失败: ${e?.message || '请重试'}`)
  } finally {
    optimizing.value = false
  }
}

/** 确认并应用优化 */
const handleConfirmOptimize = async () => {
  if (!sessionId.value) return
  optimizing.value = true
  try {
    const res = await workflowGenerationApi.confirmOptimization(sessionId.value)
    if (res.workflow_id) {
      ElMessage.success('优化已应用')
      confirmResult.value = { ...confirmResult.value!, ...res }
      showOptimizeInput.value = false
      optimizeFeedback.value = ''
      optimizeMessage.value = ''
    } else {
      ElMessage.error(res.error || '应用优化失败')
    }
  } catch (e: any) {
    ElMessage.error(`应用失败: ${e?.message || '请重试'}`)
  } finally {
    optimizing.value = false
  }
}

/** 从路由参数恢复草稿 */
const initFromRoute = async () => {
  const sid = route.query.session_id as string
  if (!sid) return
  try {
    const session = await workflowGenerationApi.getSession(sid)
    if (session) {
      sessionId.value = session.session_id
      currentRound.value = session.current_round
      for (const r of session.rounds || []) {
        if (r.user_message) chatMessages.value.push({ role: 'user', content: r.user_message })
        if (r.ai_message) chatMessages.value.push({ role: 'ai', content: r.ai_message })
      }
      scrollChat()
    }
  } catch {
    // 忽略
  }
}

onMounted(() => {
  initFromRoute()
})
</script>

<style lang="scss" scoped>
.wf-gen-page {
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
    .header-divider { color: var(--el-border-color); font-size: 14px; }
    h1 { font-size: 18px; margin: 0; font-weight: 600; }
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

/* ========== 需求沟通 ========== */
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

.requirement-guide {
  padding: 24px 20px;
  color: var(--el-text-color-regular);
  font-size: 14px;
  line-height: 1.7;

  .guide-header {
    text-align: center;
    margin-bottom: 24px;
    .guide-icon { font-size: 48px; color: var(--el-color-primary); margin-bottom: 12px; }
    h3 { font-size: 18px; margin: 0 0 8px; font-weight: 600; color: var(--el-text-color-primary); }
    .guide-desc { margin: 0; color: var(--el-text-color-secondary); font-size: 14px; }
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
    &:last-child { margin-bottom: 0; }
    .tip-label { display: block; font-weight: 500; margin-bottom: 8px; color: var(--el-text-color-primary); }
    ul { margin: 0; padding-left: 20px; color: var(--el-text-color-regular); li { margin-bottom: 6px; } }
    .guide-examples li { color: var(--el-text-color-secondary); font-style: italic; }
  }

  .guide-footer {
    text-align: center; margin: 0; font-size: 13px; color: var(--el-text-color-placeholder);
    kbd { display: inline-block; padding: 2px 6px; font-size: 12px; background: var(--el-fill-color); border: 1px solid var(--el-border-color); border-radius: 4px; }
  }
}

.chat-msg {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;

  &.chat-user { flex-direction: row-reverse; }

  .msg-avatar {
    width: 36px; height: 36px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center; flex-shrink: 0;
    background: var(--el-color-primary-light-8); color: var(--el-color-primary); font-size: 18px;
  }

  &.chat-user .msg-avatar {
    background: var(--el-color-success-light-8); color: var(--el-color-success);
  }

  .msg-bubble {
    max-width: 75%; padding: 12px 16px; border-radius: 12px;
    background: var(--el-bg-color); border: 1px solid var(--el-border-color-lighter);
    line-height: 1.7; font-size: 14px;
    &.thinking { color: var(--el-text-color-secondary); font-style: italic; }
  }

  &.chat-user .msg-bubble {
    background: var(--el-color-primary-light-9); border-color: var(--el-color-primary-light-7);
  }
}

.msg-text {
  :deep(p) { margin: 0 0 6px; }
  :deep(ul), :deep(ol) { margin: 6px 0; padding-left: 24px; }
  :deep(table) {
    border-collapse: collapse; width: 100%; font-size: 13px;
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

.chat-input-area { flex-shrink: 0; }

.chat-actions {
  display: flex; justify-content: space-between; align-items: center; margin-top: 10px;
  .tip { color: var(--el-text-color-placeholder); font-size: 12px; }
}

/* ========== 生成进度 ========== */
.wizard-generating {
  display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 40px 20px;
  .gen-status {
    text-align: center;
    h3 { margin: 16px 0 8px; font-size: 18px; }
    .gen-desc { color: var(--el-text-color-secondary); font-size: 14px; }
  }
}

.gen-spinner { animation: spin 1.5s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.gen-steps {
  display: flex; justify-content: center; flex-wrap: wrap; gap: 24px; margin-top: 24px;
}

.gen-step {
  display: flex; align-items: center; gap: 6px; font-size: 14px; color: var(--el-text-color-secondary);
  &.done { color: var(--el-color-success); }
  &.running { color: var(--el-color-primary); font-weight: 500; }
}

/* ========== 完成 ========== */
.wizard-done {
  display: flex; flex-direction: column; align-items: center; padding: 30px 20px; overflow-y: auto;
}

.creation-report {
  text-align: left; width: 100%; max-width: 600px; margin: 16px auto;
  h4 { margin: 0 0 12px; font-size: 16px; }
  .report-section { margin-bottom: 12px; }
  .report-label { margin: 0 0 6px; font-size: 13px; color: var(--el-text-color-regular); }
}

.result-actions {
  display: flex; gap: 12px; justify-content: center; margin-top: 20px;
}

/* ========== 优化 ========== */
.optimize-section {
  width: 100%; max-width: 600px; margin: 24px auto 0;
  padding: 20px; border: 1px solid var(--el-border-color-lighter); border-radius: 8px;
  background: var(--el-fill-color-lighter);
  h4 { margin: 0 0 8px; }
  .optimize-desc { font-size: 13px; color: var(--el-text-color-secondary); margin: 0 0 12px; }
}

.optimize-actions {
  display: flex; justify-content: flex-end; gap: 10px; margin-top: 12px;
}

.optimize-result {
  margin-top: 16px; padding: 16px; border: 1px solid var(--el-border-color); border-radius: 8px;
  background: var(--el-bg-color);
}

.optimize-confirm-actions {
  display: flex; justify-content: flex-end; gap: 10px; margin-top: 12px;
}
</style>