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
        <el-button v-if="step < 3 && sessionId" text size="small" @click="goBack">
          保存草稿
        </el-button>
      </div>
    </div>

    <!-- 步骤条 -->
    <div class="steps-bar">
      <el-steps :active="step" finish-status="success" align-center>
        <el-step title="选择类型" />
        <el-step title="需求沟通" />
        <el-step title="方案确认" />
        <el-step title="自动补全" />
        <el-step title="完成" />
      </el-steps>
    </div>

    <!-- 主内容区 -->
    <div class="main-content">
      <!-- 步骤 0: 选择类型 -->
      <div v-if="step === 0" class="wizard-type-select">
        <div class="type-selector">
          <h3>你要创建什么类型的分析流程？</h3>
          <el-radio-group v-model="selectedWorkflowType" class="type-radio-group">
            <el-radio
              v-for="option in WORKFLOW_TYPE_OPTIONS"
              :key="option.value"
              :label="option.value"
              class="type-radio-item"
            >
              <div class="type-option">
                <div class="type-label">{{ option.label }}</div>
                <div class="type-desc">{{ option.description }}</div>
              </div>
            </el-radio>
          </el-radio-group>
        </div>
        <div class="type-actions">
          <el-button type="primary" size="large" @click="step = 1">
            下一步：描述需求
            <el-icon class="el-icon--right"><ArrowRight /></el-icon>
          </el-button>
        </div>
      </div>

      <!-- 步骤 1: 需求沟通 -->
      <div v-if="step === 1" class="wizard-chat">
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

            <!-- 未完成的草稿 -->
            <div v-if="inProgressDrafts.length > 0" class="draft-section">
              <div class="draft-section-header">
                <h4>📝 未完成的草稿</h4>
                <el-button text size="small" @click="loadDrafts" :loading="draftsLoading">
                  <el-icon><Refresh /></el-icon>
                  刷新
                </el-button>
              </div>
              <div class="draft-cards">
                <div v-for="draft in inProgressDrafts" :key="draft.session_id" class="draft-card">
                  <div class="draft-card-header">
                    <el-tag :type="getStatusTagType(draft.status)" size="small">
                      {{ getStatusLabel(draft.status) }}
                    </el-tag>
                    <span class="draft-time">{{ formatTime(draft.updated_at) }}</span>
                  </div>
                  <div class="draft-card-body">
                    <p class="draft-preview">{{ getDraftPreview(draft) }}</p>
                    <div class="draft-meta">
                      <span>已对话 {{ draft.rounds?.length || 0 }} 轮</span>
                    </div>
                  </div>
                  <div class="draft-card-footer">
                    <el-button type="primary" size="small" @click="resumeSession(draft)">
                      继续完善
                    </el-button>
                    <el-button size="small" text type="danger" @click="handleDeleteDraft(draft)">
                      <el-icon><Delete /></el-icon>
                      删除
                    </el-button>
                  </div>
                </div>
              </div>
            </div>

            <!-- 已完成的工作流（可优化） -->
            <div v-if="completedSessions.length > 0" class="draft-section completed-section">
              <div class="draft-section-header">
                <h4>✅ 已生成的工作流</h4>
                <el-button v-if="inProgressDrafts.length === 0" text size="small" @click="loadDrafts" :loading="draftsLoading">
                  <el-icon><Refresh /></el-icon>
                  刷新
                </el-button>
              </div>
              <div class="draft-cards">
                <div v-for="s in completedSessions" :key="s.session_id" class="draft-card completed-card">
                  <div class="draft-card-header">
                    <el-tag type="success" size="small">{{ s.status === 'published' ? '已发布' : '草稿' }}</el-tag>
                    <span class="draft-time">{{ formatTime(s.updated_at) }}</span>
                  </div>
                  <div class="draft-card-body">
                    <p class="draft-preview">{{ getDraftPreview(s) }}</p>
                    <div class="draft-meta">
                      <span v-if="s.workflow_id">工作流: {{ s.workflow_id }}</span>
                    </div>
                  </div>
                  <div class="draft-card-footer">
                    <el-button type="primary" size="small" @click="resumeSession(s)">
                      <el-icon><RefreshRight /></el-icon>
                      继续优化
                    </el-button>
                    <el-button size="small" text type="danger" @click="handleDeleteDraft(s)">
                      <el-icon><Delete /></el-icon>
                      删除
                    </el-button>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <!-- 优化模式横幅 -->
          <div v-if="isOptimizeMode" class="optimize-mode-banner">
            <el-icon class="banner-icon"><RefreshRight /></el-icon>
            <span class="banner-text">🔄 迭代优化模式 — 描述你想改进的地方，AI 将提出优化方案</span>
            <el-button size="small" text @click="handleCancelOptimize">返回成果页</el-button>
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
              {{ isOptimizeMode ? 'AI 正在分析优化方向...' : 'AI 正在分析资源并规划方案...' }}
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
            :placeholder="isOptimizeMode
              ? (optimizeProposed ? '可以进一步补充说明，或直接点击「确认并应用优化」' : '描述你想改进的地方，例如：增加行业对比维度、调整某个 Agent 的提示词...')
              : (chatMessages.length === 0
                  ? '描述你想要的分析流程，例如：我想做一个 ETF 综合分析流程...'
                  : (canConfirm ? '可以继续补充需求，或点击「确认方案，开始创建」' : '回复 AI 的问题...'))"
            :disabled="chatLoading"
            @keydown.enter.ctrl="handleSend"
          />
          <div class="chat-actions">
            <span class="tip">
              Ctrl+Enter 发送 ·
              <template v-if="isOptimizeMode">优化模式</template>
              <template v-else>第 {{ currentRound }} 轮</template>
            </span>
            <div>
              <!-- 优化模式：AI 已提案 → 显示确认/取消 -->
              <template v-if="isOptimizeMode && optimizeProposed">
                <el-button type="success" @click="handleConfirmOptimize" :loading="optimizing">
                  ✅ 确认并应用优化
                </el-button>
                <el-button @click="handleCancelOptimize">取消</el-button>
              </template>
              <!-- 正常模式：显示确认方案 -->
              <template v-else>
                <el-button v-if="canConfirm && !isOptimizeMode" type="success" @click="handleConfirm" :loading="chatLoading">
                  ✅ 确认方案，开始创建
                </el-button>
                <el-button type="primary" @click="handleSend" :loading="chatLoading" :disabled="!userInput.trim()">
                  {{ isOptimizeMode ? '提交优化' : '发送' }}
                </el-button>
              </template>
            </div>
          </div>
        </div>
      </div>

      <!-- 步骤 2: 方案确认（由 handleConfirm 自动跳过到步骤3） -->

      <!-- 步骤 3: 自动补全进度 -->
      <div v-if="step === 3" class="wizard-generating">
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

      <!-- 步骤 4: 完成 -->
      <div v-if="step === 4" class="wizard-done">
        <el-result
          :icon="confirmResult?.workflow_id ? (published ? 'success' : 'warning') : 'error'"
          :title="confirmResult?.workflow_id
            ? (published ? '🎉 工作流已发布！' : '📝 工作流已创建（草稿）')
            : '❌ 创建失败'"
          :sub-title="confirmResult?.workflow_id
            ? (published
              ? `工作流 ID: ${confirmResult.workflow_id}`
              : `工作流 ID: ${confirmResult.workflow_id} — 需要发布后才会在系统中生效`)
            : confirmResult?.error || '请重试或修改需求'"
        >
          <!-- 创建报告 -->
          <template #extra>
            <div v-if="report" class="creation-report">
              <el-collapse v-model="reportSections">
                <!-- 工作流结构 -->
                <el-collapse-item name="structure">
                  <template #title>
                    <span class="collapse-title">📊 工作流结构</span>
                    <el-tag size="small" type="info" class="collapse-badge">
                      {{ report.workflow_structure?.nodes?.length || 0 }} 节点
                    </el-tag>
                  </template>
                  <p v-if="report.workflow_structure?.summary" class="structure-summary">
                    {{ report.workflow_structure.summary }}
                  </p>
                  <div class="flow-node-list">
                    <template v-for="(node, idx) in report.workflow_structure?.nodes" :key="node.id">
                      <div class="flow-node-chip">
                        <span class="node-icon">{{ getNodeIcon(node.type) }}</span>
                        <span class="node-label">{{ node.label }}</span>
                        <small v-if="node.agent_id" class="node-agent">({{ node.agent_id }})</small>
                      </div>
                      <span v-if="idx < (report.workflow_structure?.nodes?.length || 0) - 1" class="node-arrow">→</span>
                    </template>
                  </div>
                </el-collapse-item>

                <!-- 提示词定制 -->
                <el-collapse-item name="prompts">
                  <template #title>
                    <span class="collapse-title">📝 提示词定制</span>
                    <el-tag v-if="report.prompts_created?.length" size="small" type="success" class="collapse-badge">
                      {{ report.prompts_created.length }} 专属
                    </el-tag>
                    <el-tag v-if="report.prompts_default?.length" size="small" type="info" class="collapse-badge">
                      {{ report.prompts_default.length }} 默认
                    </el-tag>
                  </template>
                  <div v-for="p in report.prompts_created" :key="p.agent_id" class="prompt-card">
                    <div class="prompt-header">
                      <el-tag type="success" size="small">{{ p.template_id ? '✅ 已生成' : '⚠️ 未生成' }}</el-tag>
                      <strong>{{ p.agent_id }}</strong>
                      <span class="prompt-role">→ {{ p.new_role }}</span>
                    </div>
                    <p v-if="p.reshaping_direction" class="prompt-direction">{{ p.reshaping_direction }}</p>
                    <div v-if="p.key_focus_areas?.length" class="focus-areas">
                      <el-tag v-for="area in p.key_focus_areas" :key="area" size="small" style="margin:2px">{{ area }}</el-tag>
                    </div>
                  </div>
                  <div v-if="report.prompts_default?.length" class="default-prompts">
                    <p class="sub-label">使用默认提示词：</p>
                    <div v-for="a in report.prompts_default" :key="getDefaultPromptKey(a)" class="default-item">
                      <el-tag size="small" type="info">{{ getDefaultPromptAgentId(a) }}</el-tag>
                      <span v-if="a.reason" class="default-reason">{{ a.reason }}</span>
                    </div>
                  </div>
                  <p v-if="!report.prompts_created?.length && !report.prompts_default?.length" class="empty-hint">无提示词变更</p>
                </el-collapse-item>

                <!-- Skill 创建 -->
                <el-collapse-item name="skills">
                  <template #title>
                    <span class="collapse-title">🔧 Skill 创建</span>
                    <el-tag v-if="report.skills_created?.length" size="small" type="warning" class="collapse-badge">
                      {{ report.skills_created.length }} 创建
                    </el-tag>
                    <el-tag v-if="report.skills_failed?.length" size="small" type="danger" class="collapse-badge">
                      {{ report.skills_failed.length }} 失败
                    </el-tag>
                  </template>
                  <div v-for="s in report.skills_created" :key="s.skill_id" class="skill-item">
                    <el-tag :type="s.skipped ? 'info' : 'success'" size="small">{{ s.skipped ? '已存在' : '新创建' }}</el-tag>
                    <span>{{ s.name || s.skill_id }}</span>
                  </div>
                  <div v-for="s in report.skills_failed" :key="s.name" class="skill-item">
                    <el-tag type="danger" size="small">失败</el-tag>
                    <span>{{ s.name }}: {{ s.error }}</span>
                  </div>
                  <p v-if="!report.skills_created?.length && !report.skills_failed?.length" class="empty-hint">无需创建 Skill</p>
                </el-collapse-item>

                <!-- 绑定关系 -->
                <el-collapse-item v-if="report.bindings_info?.length" name="bindings">
                  <template #title>
                    <span class="collapse-title">🔗 工具绑定</span>
                    <el-tag size="small" type="primary" class="collapse-badge">{{ report.bindings_created || 0 }} 条</el-tag>
                  </template>
                  <div v-for="b in report.bindings_info" :key="b.skill_id" class="binding-item">
                    <el-tag size="small" type="warning">{{ b.skill_name }}</el-tag>
                    <span class="binding-arrow">→</span>
                    <el-tag size="small" type="primary">{{ b.target_agent_id }}</el-tag>
                  </div>
                </el-collapse-item>
              </el-collapse>
            </div>

            <div class="result-actions">
              <el-button v-if="confirmResult?.workflow_id && !published"
                type="success" @click="handlePublish" :loading="publishing">
                🚀 发布为正式版本
              </el-button>
              <el-button v-if="confirmResult?.workflow_id" type="primary"
                @click="router.push(`/workflow/editor/${confirmResult.workflow_id}`)">
                <el-icon><Edit /></el-icon>
                打开编辑器
              </el-button>
              <el-button v-if="confirmResult?.workflow_id"
                @click="handleStartOptimize">
                <el-icon><RefreshRight /></el-icon>
                迭代优化
              </el-button>
              <el-button v-if="!confirmResult?.workflow_id" @click="step = 1">
                返回修改需求
              </el-button>
              <el-button @click="goBack">返回列表</el-button>
            </div>
          </template>
        </el-result>


      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, ArrowRight, User, Connection, Loading, CircleCheck, MoreFilled, Edit, RefreshRight, Refresh, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'
import { workflowGenerationApi } from '@/api/workflowGeneration'
import type { WfConfirmResult, WfSessionItem } from '@/api/workflowGeneration'

marked.setOptions({ breaks: true, gfm: true })

const renderMarkdown = (content: string): string => {
  if (!content?.trim()) return ''
  try { return marked.parse(content) as string } catch { return content }
}

const route = useRoute()
const router = useRouter()

// ==================== 状态 ====================

const step = ref(0)

// 流程类型选择
const selectedWorkflowType = ref('stock_analysis')

const WORKFLOW_TYPE_OPTIONS = [
  { value: 'stock_analysis', label: '单股研究流程', description: '用于分析单只股票，结果在"研究报告"中查看' },
  { value: 'etf_analysis', label: 'ETF 分析流程', description: '用于分析 ETF 基金' },
  { value: 'position_analysis', label: '持仓分析流程', description: '用于分析持仓股票健康度' },
  { value: 'trade_review', label: '操作复盘流程', description: '用于复盘交易操作' },
  { value: 'general', label: '通用研究流程', description: '自由探索，结果在"流程中心"查看' },
]

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
const report = computed(() => confirmResult.value?.creation_report)
const reportSections = ref(['structure', 'prompts'])

/** 节点类型图标 */
const getNodeIcon = (type: string): string => {
  const icons: Record<string, string> = {
    start: '🟢', end: '🔴', analyst: '📊', researcher: '🔍',
    trader: '💰', risk: '⚠️', manager: '👔', parallel: '⚡',
    merge: '🔗', debate: '💬', post_processor: '📄', condition: '❓',
  }
  return icons[type] || '⬜'
}

// 发布
const published = ref(false)
const publishing = ref(false)

// 优化
const isOptimizeMode = ref(false)    // 是否处于迭代优化模式
const optimizeProposed = ref(false)  // AI 已提出优化方案，等待用户确认
const optimizing = ref(false)

// 草稿
const draftSessions = ref<WfSessionItem[]>([])
const draftsLoading = ref(false)

/** 未完成的草稿（gathering/planning） */
const inProgressDrafts = computed(() =>
  draftSessions.value.filter(s => ['gathering', 'planning'].includes(s.status))
)

/** 已完成的工作流（completed/published，可优化） */
const completedSessions = computed(() =>
  draftSessions.value.filter(s => ['completed', 'published'].includes(s.status))
)

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
    if (isOptimizeMode.value) {
      // 优化模式：调用 optimize API，AI 回复后等待用户确认
      if (!sessionId.value) throw new Error('会话不存在')
      const res = await workflowGenerationApi.optimize(sessionId.value, text)
      chatMessages.value.push({ role: 'ai', content: res.ai_message })
      optimizeProposed.value = true
    } else if (!sessionId.value) {
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
  step.value = 3

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
    const res = await workflowGenerationApi.confirmAndCreate(sessionId.value, {
      workflow_type: selectedWorkflowType.value,
    })
    clearInterval(progressTimer)
    genSteps.value.forEach(s => s.status = 'done')
    genProgress.value = 100
    confirmResult.value = res

    setTimeout(() => { step.value = 4 }, 600)
  } catch (e: any) {
    clearInterval(progressTimer)
    confirmResult.value = { status: 'failed', session_id: sessionId.value, error: e?.message || '创建失败' }
    step.value = 4
  } finally {
    chatLoading.value = false
  }
}


/** 发布草稿工作流为正式版本 */
const handlePublish = async () => {
  if (!sessionId.value) return
  publishing.value = true
  try {
    const result = await workflowGenerationApi.publishSession(sessionId.value)
    published.value = true
    ElMessage.success(result.message || '工作流已发布为正式版本！')
  } catch (e: any) {
    ElMessage.error(`发布失败: ${e?.message || '请重试'}`)
  } finally {
    publishing.value = false
  }
}

/** 进入迭代优化模式：回到对话界面并注入成果摘要 */
const handleStartOptimize = () => {
  isOptimizeMode.value = true
  optimizeProposed.value = false

  // 在对话末尾注入一条成果摘要消息，方便用户了解已生成内容
  const r = report.value
  if (r) {
    const nodes = (r.workflow_structure?.nodes || []).map((n: any) => n.label || n.id)
    const customPrompts = (r.prompts_created || []).map((p: any) => p.agent_id)
    const skills = (r.skills_created || []).map((s: any) => s.name || s.skill_id)
    const lines = [
      `## 📊 当前已生成的工作流成果`,
      ``,
      `**工作流名称**: ${r.workflow_structure?.name || '(未知)'}`,
      `**节点**: ${nodes.length ? nodes.join('、') : '无'}`,
      `**专属提示词**: ${customPrompts.length} 个${customPrompts.length ? '（' + customPrompts.join(', ') + '）' : ''}`,
      `**Skill**: ${skills.length} 个${skills.length ? '（' + skills.join(', ') + '）' : ''}`,
      ``,
      `---`,
      `请描述你想改进的地方，例如：增加某个分析维度、调整某个 Agent 的提示词方向、添加新的工具等。`,
    ]
    chatMessages.value.push({ role: 'ai', content: lines.join('\n') })
  }

  step.value = 1
  scrollChat()
}

/** 取消优化，返回成果页 */
const handleCancelOptimize = () => {
  isOptimizeMode.value = false
  optimizeProposed.value = false
  step.value = 4
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
      // 重置优化模式，回到成果页
      isOptimizeMode.value = false
      optimizeProposed.value = false
      step.value = 4
    } else {
      ElMessage.error(res.error || '应用优化失败')
    }
  } catch (e: any) {
    ElMessage.error(`应用失败: ${e?.message || '请重试'}`)
  } finally {
    optimizing.value = false
  }
}

// ==================== 草稿管理 ====================

/** 加载草稿会话（含未完成 + 已完成可优化） */
const loadDrafts = async () => {
  draftsLoading.value = true
  try {
    const res = await workflowGenerationApi.listSessions({
      status: 'gathering,planning,completed,published',
      page_size: 50,
    })
    draftSessions.value = res.items || []
  } catch {
    draftSessions.value = []
  } finally {
    draftsLoading.value = false
  }
}

/** 获取草稿预览文字 */
const getDraftPreview = (draft: WfSessionItem): string => {
  if (draft.rounds && draft.rounds.length > 0) {
    const firstMsg = draft.rounds[0].user_message
    return firstMsg.length > 80 ? firstMsg.slice(0, 80) + '...' : firstMsg
  }
  return '(无内容)'
}

/** 恢复草稿会话 */
const resumeSession = (draft: WfSessionItem) => {
  sessionId.value = draft.session_id
  currentRound.value = draft.current_round
  chatMessages.value = []
  for (const r of draft.rounds || []) {
    if (r.user_message) chatMessages.value.push({ role: 'user', content: r.user_message })
    if (r.ai_message) chatMessages.value.push({ role: 'ai', content: r.ai_message })
  }

  // 已完成或已发布的会话 -> 直接跳到完成页（step 4）
  if (['completed', 'published'].includes(draft.status) && draft.workflow_id) {
    confirmResult.value = {
      status: draft.status,
      session_id: draft.session_id,
      workflow_id: draft.workflow_id,
      creation_report: draft.creation_report,
    }
    published.value = draft.status === 'published'
    step.value = 4
    return
  }

  step.value = 1
  scrollChat()
}

/** 删除草稿 */
const handleDeleteDraft = async (draft: WfSessionItem) => {
  try {
    await ElMessageBox.confirm('确定删除这个草稿？相关的 draft 资源也会被清理。', '确认删除', {
      type: 'warning',
    })
    await workflowGenerationApi.deleteSession(draft.session_id)
    ElMessage.success('草稿已删除')
    await loadDrafts()
  } catch {
    // 用户取消或删除失败
  }
}

/** 格式化时间 */
const formatTime = (ts: string): string => {
  if (!ts) return ''
  try {
    const d = new Date(ts)
    return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
  } catch {
    return ts
  }
}

/** 获取状态标签 */
const getStatusLabel = (status: string): string => {
  const map: Record<string, string> = {
    gathering: '需求沟通中',
    planning: '规划中',
    completed: '已完成',
    published: '已发布',
    failed: '失败',
  }
  return map[status] || status
}

/** 获取状态标签类型 */
type ElTagType = 'primary' | 'success' | 'info' | 'warning' | 'danger'

const getStatusTagType = (status: string): ElTagType => {
  const map: Record<string, ElTagType> = {
    gathering: 'warning',
    planning: 'info',
    completed: 'success',
    published: 'success',
    failed: 'danger',
  }
  return map[status] || 'info'
}

const getDefaultPromptKey = (item: { agent_id: string; name: string; reason: string }) => item.agent_id || item.name

const getDefaultPromptAgentId = (item: { agent_id: string; name: string; reason: string }) => item.agent_id || item.name

/** 从路由参数恢复会话 */
const initFromRoute = async () => {
  const sid = route.query.session_id as string
  if (!sid) return
  try {
    const session = await workflowGenerationApi.getSession(sid)
    if (!session) return

    // 利用 resumeSession 统一处理（自动区分 in-progress / completed）
    resumeSession(session as WfSessionItem)
  } catch {
    // 忽略
  }
}

onMounted(() => {
  loadDrafts()
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

/* ========== 类型选择 ========== */
.wizard-type-select {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  padding: 32px 20px;
  height: 100%;
  overflow-y: auto;
}

.type-selector {
  width: 100%;
  max-width: 600px;
  text-align: center;

  h3 {
    font-size: 18px;
    font-weight: 600;
    color: var(--el-text-color-primary);
    margin: 0 0 24px;
  }
}

.type-radio-group {
  display: flex;
  flex-direction: column;
  width: 100%;
}

.type-radio-item {
  display: flex;
  align-items: flex-start;
  width: 100%;
  margin: 0 0 12px;
  padding: 14px 16px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  background: var(--el-bg-color);
  transition: border-color 0.2s, background 0.2s;
  height: auto;

  &:hover {
    border-color: var(--el-color-primary-light-5);
  }

  :deep(.el-radio__label) {
    width: 100%;
    padding-left: 8px;
  }
}

.type-option {
  .type-label {
    font-size: 14px;
    font-weight: 600;
    color: var(--el-text-color-primary);
    margin-bottom: 4px;
  }

  .type-desc {
    font-size: 12px;
    color: var(--el-text-color-secondary);
    line-height: 1.5;
  }
}

.type-actions {
  margin-top: 28px;
  text-align: center;
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
  text-align: left; width: 100%; max-width: 700px; margin: 16px auto;
}

.collapse-title { font-weight: 600; font-size: 14px; }
.collapse-badge { margin-left: 8px; }

/* 工作流结构 */
.structure-summary { margin: 0 0 12px; font-size: 13px; color: var(--el-text-color-regular); line-height: 1.6; }
.flow-node-list { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.flow-node-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px 10px; border-radius: 16px; font-size: 12px;
  background: var(--el-fill-color-light); border: 1px solid var(--el-border-color-lighter);
}
.node-icon { font-size: 14px; }
.node-agent { color: var(--el-text-color-placeholder); font-size: 11px; }
.node-arrow { color: var(--el-text-color-placeholder); font-size: 14px; margin: 0 2px; }

/* 提示词定制 */
.prompt-card {
  padding: 10px 12px; margin-bottom: 8px; border-radius: 8px;
  border: 1px solid var(--el-border-color-lighter); background: var(--el-fill-color-blank);
}
.prompt-header { display: flex; align-items: center; gap: 8px; font-size: 13px; flex-wrap: wrap; }
.prompt-role { color: var(--el-text-color-secondary); font-size: 12px; }
.prompt-direction { margin: 6px 0 4px; font-size: 12px; color: var(--el-text-color-regular); line-height: 1.5; }
.focus-areas { margin-top: 4px; }
.default-prompts { margin-top: 12px; }
.sub-label { margin: 0 0 6px; font-size: 12px; color: var(--el-text-color-secondary); font-weight: 500; }
.default-item { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.default-reason { font-size: 12px; color: var(--el-text-color-placeholder); }
.empty-hint { font-size: 12px; color: var(--el-text-color-placeholder); padding: 8px 0; }

/* Skill */
.skill-item { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; font-size: 13px; }

/* 绑定关系 */
.binding-item { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.binding-arrow { color: var(--el-text-color-placeholder); font-weight: bold; }

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

/* ========== 草稿区域 ========== */
.draft-section {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px dashed var(--el-border-color);
}

.draft-section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  h4 { font-size: 15px; margin: 0; font-weight: 600; color: var(--el-text-color-primary); }
}

.draft-cards {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.draft-card {
  width: 280px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 12px;
  background: var(--el-bg-color);
  transition: box-shadow 0.2s;
  &:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
}

.draft-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  .draft-time { font-size: 11px; color: var(--el-text-color-placeholder); }
}

.draft-card-body {
  margin-bottom: 10px;
  .draft-preview {
    font-size: 13px;
    color: var(--el-text-color-regular);
    margin: 0 0 6px;
    line-height: 1.5;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .draft-meta {
    font-size: 11px;
    color: var(--el-text-color-placeholder);
  }
}

.draft-card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.completed-section {
  .draft-section-header h4 { color: var(--el-color-success); }
}

.completed-card {
  border-color: var(--el-color-success-light-5);
  background: var(--el-color-success-light-9);
}

.optimize-mode-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  margin-bottom: 12px;
  background: var(--el-color-warning-light-9);
  border: 1px solid var(--el-color-warning-light-5);
  border-radius: 6px;
  font-size: 13px;
  color: var(--el-color-warning-dark-2);
  flex-shrink: 0;

  .banner-icon { font-size: 15px; }
  .banner-text { flex: 1; }
}
</style>