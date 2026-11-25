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
        <el-button size="small" @click="showThreadSidebar = !showThreadSidebar">
          <el-icon><Expand v-if="!showThreadSidebar" /><Fold v-else /></el-icon>
          {{ showThreadSidebar ? '隐藏主题栏' : '显示主题栏' }}
        </el-button>
        <el-button size="small" @click="showSummarySidebar = !showSummarySidebar">
          <el-icon><Expand v-if="!showSummarySidebar" /><Fold v-else /></el-icon>
          {{ showSummarySidebar ? '隐藏摘要栏' : '显示摘要栏' }}
        </el-button>
        <el-button size="small" @click="settingsDialogVisible = true">
          <el-icon><Setting /></el-icon>
          助手设置
        </el-button>
        <el-button size="small" @click="handleCreateThread()">
          <el-icon><Plus /></el-icon>
          新主题
        </el-button>
        <el-tag size="small" type="success" effect="plain">
          <el-icon style="vertical-align: -2px;"><ChatDotRound /></el-icon>
          当前仅开放快速对话
        </el-tag>
      </div>
    </div>

    <div class="workspace-body">
      <aside v-if="showThreadSidebar" class="thread-sidebar">
        <div class="sidebar-header">
          <div>
            <div class="sidebar-title">研究主题</div>
            <div class="sidebar-subtitle">支持主线拆解为行业 → 公司 → 子问题</div>
          </div>
          <el-button size="small" text @click="handleCreateThread()">
            <el-icon><Plus /></el-icon>
            根主题
          </el-button>
        </div>
        <div class="thread-list">
          <el-empty v-if="!threads.length && !sidebarLoading" description="暂无主题" :image-size="56" />
          <el-tree
            v-else
            :data="threadTree"
            node-key="thread_id"
            default-expand-all
            highlight-current
            :expand-on-click-node="false"
            :current-node-key="selectedThreadId"
            class="thread-tree"
            @node-click="handleThreadNodeClick"
          >
            <template #default="{ data }">
              <div class="thread-node">
                <div class="thread-node-main">
                  <div class="thread-item-top">
                    <div class="thread-title-wrap">
                      <el-icon class="thread-type-icon">
                        <FolderOpened v-if="data.children?.length" />
                        <Document v-else />
                      </el-icon>
                      <span class="thread-title">{{ data.title }}</span>
                      <el-tag v-if="data.pinned" type="info" size="small" effect="plain">默认</el-tag>
                    </div>
                    <div class="thread-actions" @click.stop>
                      <el-tooltip content="新建子主题" placement="top">
                        <el-button type="primary" link size="small" @click.stop="handleCreateThread(data.thread_id)">
                          <el-icon><Plus /></el-icon>
                        </el-button>
                      </el-tooltip>
                      <el-tooltip v-if="!data.pinned" content="删除主题树" placement="top">
                        <el-button type="danger" link size="small" @click.stop="handleDeleteThread(data.thread_id)">
                          <el-icon><Delete /></el-icon>
                        </el-button>
                      </el-tooltip>
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </el-tree>
        </div>
      </aside>

      <section class="chat-panel">
        <div class="chat-panel-header">
          <div>
            <div v-if="currentThreadPath" class="current-thread-path">{{ currentThreadPath }}</div>
            <div class="current-thread-title">{{ currentThread?.title || '默认主题' }}</div>
            <div class="current-thread-subtitle">
              {{ currentThread?.current_summary?.abstract || '当前主题还没有摘要，先开始一轮研究。' }}
            </div>
          </div>
          <div class="chat-panel-actions">
            <el-tag v-if="loading" type="info" size="small">思考中...</el-tag>
            <el-tag v-else-if="streaming" type="success" size="small">回复中...</el-tag>
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
              :class="['message-item', msg.role === 'user' ? 'message-user' : 'message-assistant', streaming && idx === messages.length - 1 && msg.role === 'assistant' ? 'streaming-message' : '']"
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
                  <div class="message-text markdown-content" v-html="renderMarkdown(msg.content || (streaming && idx === messages.length - 1 ? loadingHint : ''))"></div>
                  <div v-if="msg.tools_used?.length" class="message-tools">
                    <el-tag v-for="tool in msg.tools_used" :key="tool" size="small" type="info">{{ tool }}</el-tag>
                  </div>
                  <el-collapse v-if="msg.plan" class="step-results-collapse">
                    <el-collapse-item :title="`查看分析计划 (${msg.plan.steps.length})`" name="plan">
                      <div v-for="step in msg.plan.steps" :key="step.id" class="step-item">
                        <div class="step-header">
                          <span class="step-label">步骤 {{ step.id }}</span>
                          <span class="step-intent">{{ step.intent }}</span>
                          <el-tag size="small" type="info">{{ step.tool }}</el-tag>
                        </div>
                      </div>
                    </el-collapse-item>
                  </el-collapse>
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
              :disabled="loading || streaming"
              @keydown.enter.ctrl="handleSend"
            />
            <el-button
              type="primary"
              :loading="loading"
              :disabled="!inputMessage.trim() || !selectedThreadId || streaming"
              class="send-btn"
              @click="handleSend"
            >
              发送
            </el-button>
          </div>
          <span class="input-tip">Ctrl+Enter 发送</span>
        </div>
      </section>

      <aside v-if="showSummarySidebar" class="summary-sidebar">
        <div class="summary-header">
          <div>
            <div class="summary-title">研究摘要</div>
            <div class="summary-subtitle">把当前主线、问题和下一步固定下来</div>
          </div>
          <el-button size="small" text :disabled="!selectedThreadId || loading || summaryLoading" @click="handleSummarize">
            {{ summaryLoading ? '总结中...' : '手动总结' }}
          </el-button>
        </div>

        <div class="summary-body">
          <div class="summary-card">
            <div class="summary-card-header">
              <div class="summary-card-title">关联报告</div>
              <el-button size="small" type="primary" plain :disabled="!selectedThreadId" @click="openAttachReportDialog">
                搜索并关联
              </el-button>
            </div>
            <div v-if="currentReportRefs.length" class="report-ref-list">
              <button
                v-for="report in currentReportRefs"
                :key="`${report.ref_type}-${report.report_key}`"
                type="button"
                class="report-ref-item"
                @click="openReportRef(report)"
              >
                <div class="report-ref-top">
                  <span class="report-ref-title">{{ report.title }}</span>
                  <span v-if="report.status" class="report-ref-status">{{ formatReportStatus(report.status) }}</span>
                </div>
                <div class="report-ref-meta">
                  <span v-if="report.symbol">{{ report.symbol }}</span>
                  <span>{{ formatTime(report.created_at || report.linked_at || undefined) }}</span>
                </div>
                <div class="report-ref-summary">{{ report.summary || '点击查看报告引用详情' }}</div>
              </button>
            </div>
            <div v-else class="report-empty-state">
              <div class="summary-empty">当前主题还没有关联报告。</div>
              <el-button type="primary" size="small" :disabled="!selectedThreadId" @click="openAttachReportDialog">
                关联历史报告
              </el-button>
              <div class="report-empty-tip">可搜索宁德时代、比亚迪、股票代码或报告关键词。</div>
            </div>
          </div>

          <div class="summary-card">
            <div class="summary-card-title">当前摘要</div>
            <div class="summary-card-text">
              {{ currentSummary?.abstract || '当前主题还没有摘要，先进行一轮对话或点击手动总结。' }}
            </div>
            <div class="focus-line">
              <span>聚焦度</span>
              <el-progress :percentage="focusPercent" :stroke-width="8" :show-text="false" />
              <span>{{ focusPercent }}%</span>
            </div>
          </div>

          <div class="summary-card">
            <div class="summary-card-title">已确认事实</div>
            <ul v-if="currentSummary?.confirmed_facts?.length" class="summary-list">
              <li v-for="item in currentSummary.confirmed_facts" :key="item">{{ item }}</li>
            </ul>
            <div v-else class="summary-empty">还没有提炼出已确认事实。</div>
          </div>

          <div class="summary-card">
            <div class="summary-card-title">待解决问题</div>
            <ul v-if="currentSummary?.open_questions?.length" class="summary-list">
              <li v-for="item in currentSummary.open_questions" :key="item">{{ item }}</li>
            </ul>
            <div v-else class="summary-empty">当前没有明显待解决问题。</div>
          </div>

          <div class="summary-card">
            <div class="summary-card-title">建议下一步</div>
            <ul v-if="currentSummary?.next_actions?.length" class="summary-list">
              <li v-for="item in currentSummary.next_actions" :key="item">{{ item }}</li>
            </ul>
            <div v-else class="summary-empty">继续追问来推进主题。</div>
          </div>
        </div>
      </aside>
    </div>

    <el-dialog
      v-model="settingsDialogVisible"
      width="760px"
      title="助手设置"
      destroy-on-close
    >
      <section class="assistant-llm-panel assistant-llm-panel-dialog">
        <div class="assistant-llm-header">
          <div>
            <div class="assistant-llm-title">助手模型</div>
            <div class="assistant-llm-subtitle">智能助手优先使用系统“深度推理模型”，以获得更强的推理与工具调用能力</div>
          </div>
          <el-tag size="small" type="success" effect="plain">
            当前模式：快速对话 → 推理模型
          </el-tag>
          <el-tooltip :content="memoryStatusTip" placement="bottom">
            <el-tag
              size="small"
              :type="memoryStatus === 'ok' ? 'success' : memoryStatus === 'off' ? 'info' : 'danger'"
              effect="plain"
            >
              {{ memoryStatus === 'ok' ? '🧠 记忆已启用' : memoryStatus === 'off' ? '🧠 记忆未启用' : '🧠 记忆不可用' }}
            </el-tag>
          </el-tooltip>
        </div>
        <div class="assistant-llm-grid">
          <div class="assistant-llm-item">
            <div class="assistant-llm-label">助手推理模型</div>
            <el-select
              v-model="assistantModel"
              filterable
              clearable
              placeholder="选择助手推理模型"
              :loading="modelsLoading"
            >
              <el-option
                v-for="model in assistantReasoningModels"
                :key="`assistant-reasoning-${getAssistantModelSelectionValue(model)}`"
                :label="formatAssistantModelOptionLabel(model)"
                :value="getAssistantModelSelectionValue(model)"
              >
                <div class="assistant-model-option">
                  <span class="assistant-model-name">{{ formatAssistantModelOptionLabel(model) }}</span>
                  <div class="assistant-model-meta">
                    <el-tag
                      v-if="model.capability_level"
                      :type="getCapabilityTagType(model.capability_level)"
                      size="small"
                      effect="plain"
                    >
                      {{ getCapabilityText(model.capability_level) }}
                    </el-tag>
                    <span class="assistant-model-provider">{{ formatAssistantModelMeta(model) }}</span>
                  </div>
                </div>
              </el-option>
            </el-select>
          </div>
        </div>
      </section>
    </el-dialog>

    <el-dialog
      v-model="reportDialogVisible"
      width="760px"
      title="关联报告详情"
      destroy-on-close
    >
      <template v-if="activeReportRef">
        <div class="report-dialog-body">
          <div class="report-dialog-title">{{ activeReportRef.title }}</div>
          <div class="report-dialog-meta">
            <span v-if="activeReportRef.symbol">股票: {{ activeReportRef.symbol }}</span>
            <span v-if="activeReportDetail?.status || activeReportRef.status">状态: {{ formatReportStatus(activeReportDetail?.status || activeReportRef.status) }}</span>
            <span v-if="activeReportRef.task_id">任务ID: {{ activeReportRef.task_id }}</span>
            <span v-if="activeReportDetail?.analysis_id || activeReportRef.analysis_id">分析ID: {{ activeReportDetail?.analysis_id || activeReportRef.analysis_id }}</span>
            <span>挂载时间: {{ formatTime(activeReportDetail?.linked_at || activeReportRef.linked_at || activeReportRef.created_at || undefined) }}</span>
            <span v-if="activeReportDetail?.created_at">报告时间: {{ formatTime(activeReportDetail.created_at || undefined) }}</span>
          </div>
          <el-skeleton v-if="reportDetailLoading" :rows="8" animated />
          <el-alert
            v-else-if="reportDetailError"
            type="error"
            :closable="false"
            :title="reportDetailError"
            show-icon
          />
          <TaskGrowthPanel
            v-else-if="activeReportTaskId"
            class="assistant-growth-panel"
            :task-id="activeReportTaskId"
          />
          <div
            v-if="activeReportDetail?.content"
            class="report-dialog-content markdown-content"
            v-html="renderMarkdown(activeReportDetail.content)"
          ></div>
          <div v-else-if="!activeReportTaskId" class="report-dialog-summary">{{ activeReportRef.summary || '当前仅记录了该报告的引用，尚未保存更多摘要内容。' }}</div>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="attachReportDialogVisible"
      width="720px"
      title="关联旧报告"
      destroy-on-close
    >
      <div class="attach-report-toolbar">
        <el-radio-group v-model="attachReportType" size="small">
          <el-radio-button value="stock_report">单股报告</el-radio-button>
          <el-radio-button value="position_report">持仓报告</el-radio-button>
        </el-radio-group>
        <el-input
          v-model="attachReportKeyword"
          class="attach-report-search"
          clearable
          placeholder="输入股票代码、公司名或报告关键词，如 宁德时代 / 比亚迪 / 300750"
          @keyup.enter="searchAttachableReports"
        />
        <el-button :loading="attachReportLoading" type="primary" @click="searchAttachableReports">
          搜索
        </el-button>
      </div>

      <div v-if="attachReportSearchHint" class="attach-report-hint">{{ attachReportSearchHint }}</div>

      <div v-if="attachReportResults.length" class="attach-report-list">
        <div
          v-for="report in attachReportResults"
          :key="`${report.ref_type}-${report.report_key}`"
          class="attach-report-item"
        >
          <div class="attach-report-main">
            <div class="attach-report-top">
              <span class="attach-report-title">{{ report.title }}</span>
              <span v-if="report.status" class="report-ref-status">{{ formatReportStatus(report.status) }}</span>
            </div>
            <div class="report-ref-meta">
              <span v-if="report.symbol">{{ report.symbol }}</span>
              <span>{{ formatTime(report.created_at || undefined) }}</span>
              <span v-if="report.analysis_id">分析ID: {{ report.analysis_id }}</span>
              <span v-if="report.task_id">任务ID: {{ report.task_id }}</span>
            </div>
            <div class="report-ref-summary">{{ report.summary || '该报告暂未保存摘要。' }}</div>
          </div>
          <el-button
            type="primary"
            size="small"
            :loading="attachingReportKey === report.report_key"
            @click="attachExistingReport(report)"
          >
            关联到当前主题
          </el-button>
        </div>
      </div>
      <el-empty
        v-else-if="!attachReportLoading"
        description="还没有搜索结果，先搜一下旧报告。"
        :image-size="64"
      />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { ChatDotRound, Delete, Document, Expand, Fold, FolderOpened, Plus, Setting, User } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { renderMarkdown as safeMarkdown } from '@/utils/markdown'
import TaskGrowthPanel from '@/components/growth/TaskGrowthPanel.vue'

import { assistantApi } from '@/api/assistant'
import { configApi } from '@/api/config'
import type {
  AssistantThreadItem,
  PlannedAnalysisPlan,
  PlannedStepResult,
  AssistantThreadReportSearchResponse,
  AssistantThreadReportDetail,
  AssistantThreadReportRef,
  AssistantThreadSummary,
  MessageItem,
} from '@/api/assistant'
import type { LLMConfig } from '@/api/config'

// marked 配置已由 @/utils/markdown 统一管理
const renderMarkdown = (content: string): string => {
  if (!content?.trim()) return ''
  try {
    return safeMarkdown(content)
  } catch {
    return content
  }
}

interface DisplayMessage {
  role: 'user' | 'assistant'
  content: string
  tools_used?: string[]
  plan?: PlannedAnalysisPlan
  source?: 'seed_flow' | 'llm_plan' | 'react'
  supplemented?: boolean
  step_results?: PlannedStepResult[]
}

interface ThreadTreeNode extends AssistantThreadItem {
  children: ThreadTreeNode[]
}

const inputMessage = ref('')
const loading = ref(false)
const streaming = ref(false)
const sidebarLoading = ref(false)
const summaryLoading = ref(false)
const showThreadSidebar = ref(true)
const showSummarySidebar = ref(true)
const loadingSeconds = ref(0)
const streamingToolHint = ref('')
let activeStreamController: AbortController | null = null
const threads = ref<AssistantThreadItem[]>([])
const selectedThreadId = ref<string>('')
const messages = ref<DisplayMessage[]>([])
const modelsLoading = ref(false)
const availableModels = ref<LLMConfig[]>([])
const assistantModel = ref('')
const messagesContainer = ref<HTMLElement | null>(null)
const settingsDialogVisible = ref(false)
const reportDialogVisible = ref(false)
const activeReportRef = ref<AssistantThreadReportRef | null>(null)
const activeReportDetail = ref<AssistantThreadReportDetail | null>(null)
const reportDetailLoading = ref(false)
const reportDetailError = ref('')
const attachReportDialogVisible = ref(false)
const attachReportType = ref<'stock_report' | 'position_report'>('stock_report')
const attachReportKeyword = ref('')
const attachReportLoading = ref(false)
const attachReportResults = ref<AssistantThreadReportRef[]>([])
const attachReportSearchHint = ref('')
const attachingReportKey = ref('')

let loadingTimer: ReturnType<typeof setInterval> | null = null

const currentThread = computed(() => threads.value.find(item => item.thread_id === selectedThreadId.value) || null)
const currentSummary = computed<AssistantThreadSummary | null>(() => currentThread.value?.current_summary || null)
const currentReportRefs = computed<AssistantThreadReportRef[]>(() => currentThread.value?.report_refs || [])
const activeReportTaskId = computed(() => activeReportDetail.value?.task_id || activeReportRef.value?.task_id || null)
const focusPercent = computed(() => Math.max(0, Math.min(100, Math.round((currentSummary.value?.focus_score || 0) * 100))))
const isReasoningModel = (model: LLMConfig): boolean => {
  const features = Array.isArray(model.features) ? model.features : []
  return features.includes('reasoning') || Number(model.capability_level || 0) >= 4
}

const sortAssistantModels = (models: LLMConfig[]): LLMConfig[] => {
  return [...models].sort((left, right) => {
    const reasoningGap = Number(isReasoningModel(right)) - Number(isReasoningModel(left))
    if (reasoningGap !== 0) return reasoningGap

    const capabilityGap = Number(right.capability_level || 0) - Number(left.capability_level || 0)
    if (capabilityGap !== 0) return capabilityGap

    return String(left.model_display_name || left.model_name).localeCompare(
      String(right.model_display_name || right.model_name),
      'zh-CN'
    )
  })
}

const assistantReasoningModels = computed(() => {
  const matched = availableModels.value.filter(model => isReasoningModel(model) || isDeepAnalysisRole(model.suitable_roles))
  return sortAssistantModels(matched.length ? matched : availableModels.value)
})

const getAssistantModelSelectionValue = (model: LLMConfig) => {
  const configId = String(model.config_id || '').trim()
  if (configId) {
    return configId
  }
  return `${model.provider}::${model.model_name}`
}

const selectedAssistantModel = computed(() => {
  return assistantReasoningModels.value.find(model => getAssistantModelSelectionValue(model) === assistantModel.value)
    || availableModels.value.find(model => getAssistantModelSelectionValue(model) === assistantModel.value)
    || null
})

const formatAssistantProviderLabel = (model: LLMConfig) => {
  return model.provider_name || model.provider || '未知厂家'
}

const formatAssistantModelOptionLabel = (model: LLMConfig) => {
  const providerLabel = formatAssistantProviderLabel(model)
  const displayName = model.model_display_name || model.model_name
  return `${providerLabel} / ${displayName}`
}

const formatAssistantModelMeta = (model: LLMConfig) => {
  return `${model.provider} / ${model.model_name}`
}

const findAssistantModelByConfigOrName = (configId?: string, modelName?: string) => {
  const normalizedConfigId = String(configId || '').trim()
  if (normalizedConfigId) {
    const matchedById = availableModels.value.find(model => String(model.config_id || '').trim() === normalizedConfigId)
    if (matchedById) {
      return matchedById
    }
  }

  const normalizedModelName = String(modelName || '').trim()
  if (!normalizedModelName) {
    return null
  }

  return assistantReasoningModels.value.find(model => model.model_name === normalizedModelName)
    || availableModels.value.find(model => model.model_name === normalizedModelName)
    || null
}

const threadLookup = computed(() => {
  const map = new Map<string, AssistantThreadItem>()
  threads.value.forEach(item => {
    map.set(item.thread_id, item)
  })
  return map
})

const getThreadTime = (value?: string) => {
  if (!value) return 0
  const timestamp = new Date(value).getTime()
  return Number.isNaN(timestamp) ? 0 : timestamp
}

const sortThreadItems = (items: AssistantThreadItem[]) => {
  return [...items].sort((a, b) => {
    if (a.pinned !== b.pinned) return a.pinned ? -1 : 1
    return getThreadTime(b.updated_at) - getThreadTime(a.updated_at)
  })
}

const threadTree = computed<ThreadTreeNode[]>(() => {
  const nodes = new Map<string, ThreadTreeNode>()
  threads.value.forEach(item => {
    nodes.set(item.thread_id, {
      ...item,
      children: [],
    })
  })

  const roots: ThreadTreeNode[] = []
  for (const item of sortThreadItems(threads.value)) {
    const node = nodes.get(item.thread_id)
    if (!node) continue
    const parentId = item.parent_thread_id
    if (parentId && nodes.has(parentId)) {
      nodes.get(parentId)?.children.push(node)
    } else {
      roots.push(node)
    }
  }

  const sortNodes = (list: ThreadTreeNode[]) => {
    list.sort((a, b) => {
      if (a.pinned !== b.pinned) return a.pinned ? -1 : 1
      return getThreadTime(b.updated_at) - getThreadTime(a.updated_at)
    })
    list.forEach(node => sortNodes(node.children))
  }

  sortNodes(roots)
  return roots
})

const buildThreadPath = (threadId?: string) => {
  const path: string[] = []
  let current = threadId ? threadLookup.value.get(threadId) || null : null
  let safety = 0
  while (current && safety < 20) {
    path.unshift(current.title)
    current = current.parent_thread_id ? threadLookup.value.get(current.parent_thread_id) || null : null
    safety += 1
  }
  return path.join(' / ')
}

const currentThreadPath = computed(() => buildThreadPath(selectedThreadId.value))

const loadingHint = computed(() => {
  if (streamingToolHint.value) return streamingToolHint.value
  if (loadingSeconds.value < 4) return '正在理解问题并匹配工具'
  if (loadingSeconds.value < 10) return '正在调用数据与分析工具'
  return '正在整理答案'
})

const getCapabilityText = (level: number): string => {
  const texts: Record<number, string> = {
    1: '⚡基础',
    2: '📊标准',
    3: '🎯高级',
    4: '🔥专业',
    5: '👑旗舰'
  }
  return texts[level] || '📊标准'
}

const getCapabilityTagType = (level: number): 'success' | 'info' | 'warning' | 'danger' => {
  if (level >= 4) return 'danger'
  if (level >= 3) return 'warning'
  if (level >= 2) return 'success'
  return 'info'
}

const isDeepAnalysisRole = (roles?: string[]): boolean => {
  if (!roles || !Array.isArray(roles)) return false
  return roles.includes('deep_analysis') || roles.includes('both')
}

const ensureAssistantModelSelections = async () => {
  const defaultModels = await configApi.getDefaultModels()
  const reasoningCandidates = assistantReasoningModels.value
  const defaultAssistantModel = findAssistantModelByConfigOrName(
    defaultModels.deep_reasoning_model_config_id || defaultModels.deep_analysis_model_config_id,
    defaultModels.deep_reasoning_model || defaultModels.deep_analysis_model || defaultModels.quick_analysis_model,
  )
  const currentSelected = selectedAssistantModel.value

  if (!currentSelected && defaultAssistantModel) {
    assistantModel.value = getAssistantModelSelectionValue(defaultAssistantModel)
    return
  }

  if (!currentSelected) {
    const fallbackModel = reasoningCandidates[0] || availableModels.value[0]
    assistantModel.value = fallbackModel ? getAssistantModelSelectionValue(fallbackModel) : ''
  }
}

const loadModels = async () => {
  modelsLoading.value = true
  try {
    const llmConfigs = await configApi.getLLMConfigs()
    availableModels.value = (llmConfigs || []).filter(item => item.enabled)
    await ensureAssistantModelSelections()
  } catch (error: unknown) {
    const errMsg = error instanceof Error ? error.message : '加载可用模型失败'
    ElMessage.error(errMsg)
  } finally {
    modelsLoading.value = false
  }
}

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

const formatReportStatus = (status?: string | null) => {
  if (!status) return '未知'
  const normalized = status.toLowerCase()
  if (normalized === 'completed') return '已完成'
  if (normalized === 'running') return '进行中'
  if (normalized === 'failed') return '失败'
  return status
}

const openReportRef = async (report: AssistantThreadReportRef) => {
  activeReportRef.value = report
  activeReportDetail.value = null
  reportDetailError.value = ''
  reportDialogVisible.value = true

  if (!selectedThreadId.value) {
    return
  }

  reportDetailLoading.value = true
  try {
    const res = await assistantApi.getThreadReportDetail(selectedThreadId.value, report.ref_type, report.report_key)
    activeReportDetail.value = res.detail
  } catch (error: unknown) {
    const errMsg = error instanceof Error ? error.message : '加载关联报告详情失败'
    reportDetailError.value = errMsg
  } finally {
    reportDetailLoading.value = false
  }
}

const searchAttachableReports = async () => {
  if (!selectedThreadId.value) return

  attachReportLoading.value = true
  attachReportSearchHint.value = ''
  try {
    const res: AssistantThreadReportSearchResponse = await assistantApi.getThreadReportCandidates(
      selectedThreadId.value,
      attachReportType.value,
      attachReportKeyword.value.trim() || undefined,
      8,
    )
    attachReportResults.value = res.items || []
    attachReportSearchHint.value = attachReportKeyword.value.trim()
      ? `已搜索“${attachReportKeyword.value.trim()}”，找到 ${res.total} 条结果。`
      : `已加载最近 ${res.total} 条可关联报告。`
  } catch (error: unknown) {
    const errMsg = error instanceof Error ? error.message : '搜索可关联报告失败'
    attachReportResults.value = []
    attachReportSearchHint.value = errMsg
  } finally {
    attachReportLoading.value = false
  }
}

const openAttachReportDialog = async () => {
  if (!selectedThreadId.value) return
  attachReportDialogVisible.value = true
  attachReportKeyword.value = ''
  attachReportResults.value = []
  attachReportSearchHint.value = ''
  await searchAttachableReports()
}

const attachExistingReport = async (report: AssistantThreadReportRef) => {
  if (!selectedThreadId.value) return

  attachingReportKey.value = report.report_key
  try {
    await assistantApi.attachThreadReport(selectedThreadId.value, report.ref_type, report.report_key)
    ElMessage.success('旧报告已关联到当前主题')
    await loadThreads(selectedThreadId.value)
    attachReportResults.value = attachReportResults.value.filter(item => item.report_key !== report.report_key)
  } catch (error: unknown) {
    const errMsg = error instanceof Error ? error.message : '关联旧报告失败'
    ElMessage.error(errMsg)
  } finally {
    attachingReportKey.value = ''
  }
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
    const threadIds = new Set(threads.value.map(item => item.thread_id))
    const target = (preferredThreadId && threadIds.has(preferredThreadId))
      ? preferredThreadId
      : (selectedThreadId.value && threadIds.has(selectedThreadId.value))
        ? selectedThreadId.value
        : threads.value[0]?.thread_id || ''
    if (target) {
      await selectThread(target)
    } else {
      selectedThreadId.value = ''
      messages.value = []
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
  if (activeStreamController) {
    activeStreamController.abort()
    activeStreamController = null
    streaming.value = false
    streamingToolHint.value = ''
  }
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

const handleThreadNodeClick = (data: ThreadTreeNode) => {
  void selectThread(data.thread_id)
}

const getDescendantThreadIds = (threadId: string): string[] => {
  const childIds = threads.value
    .filter(item => item.parent_thread_id === threadId)
    .map(item => item.thread_id)

  return childIds.flatMap(childId => [childId, ...getDescendantThreadIds(childId)])
}

const handleCreateThread = async (parentThreadId?: string) => {
  const parent = parentThreadId ? threadLookup.value.get(parentThreadId) || null : null
  try {
    const { value } = await ElMessageBox.prompt(
      parent ? `请输入「${parent.title}」下的子主题名称` : '请输入主题名称',
      parent ? '新建子主题' : '新建主题',
      {
      confirmButtonText: '创建',
      cancelButtonText: '取消',
      inputPlaceholder: parent ? '如：宁德时代估值、同花顺竞争力、风险点' : '如：电池行业跟踪',
      inputPattern: /\S+/,
      inputErrorMessage: '主题名称不能为空',
    })
    const thread = await assistantApi.createThread(value, parentThreadId)
    await loadThreads(thread.thread_id)
    ElMessage.success(parent ? '子主题已创建' : '主题已创建')
  } catch {
    // 用户取消时忽略
  }
}

const handleDeleteThread = async (threadId: string) => {
  const thread = threadLookup.value.get(threadId)
  if (!thread || thread.pinned) return

  const descendantCount = getDescendantThreadIds(threadId).length
  const confirmText = descendantCount > 0
    ? `确定删除「${thread.title}」及其下 ${descendantCount} 个子主题吗？相关对话和摘要会一起删除。`
    : `确定删除「${thread.title}」吗？相关对话和摘要会一起删除。`

  try {
    await ElMessageBox.confirm(confirmText, '删除主题', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
      confirmButtonClass: 'el-button--danger',
    })
    const res = await assistantApi.deleteThread(threadId)
    const deletedSet = new Set(res.deleted_thread_ids)
    if (deletedSet.has(selectedThreadId.value)) {
      selectedThreadId.value = ''
      messages.value = []
    }
    await loadThreads()
    ElMessage.success(descendantCount > 0 ? '主题树已删除' : '主题已删除')
  } catch {
    // 用户取消时忽略
  }
}

const handleSummarize = async () => {
  if (!selectedThreadId.value || summaryLoading.value) return
  summaryLoading.value = true
  try {
    const res = await assistantApi.summarizeThread(selectedThreadId.value)
    const index = threads.value.findIndex(item => item.thread_id === selectedThreadId.value)
    if (index >= 0) {
      threads.value[index] = {
        ...threads.value[index],
        current_summary: res.summary,
      }
    }
    ElMessage.success('已更新当前主题摘要')
  } catch (error: unknown) {
    const errMsg = error instanceof Error ? error.message : '总结失败'
    ElMessage.error(errMsg)
  } finally {
    summaryLoading.value = false
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

const handleSendStream = (text: string) => {
  let streamMsgIdx = -1
  let firstTokenReceived = false

  activeStreamController = assistantApi.chatStream(
    text,
    selectedThreadId.value,
    selectedAssistantModel.value?.model_name,
    selectedAssistantModel.value?.config_id,
    {
      onToken(content: string) {
        if (!firstTokenReceived) {
          firstTokenReceived = true
          loading.value = false
          streaming.value = true
          streamingToolHint.value = ''
          messages.value.push({ role: 'assistant', content: '' })
          streamMsgIdx = messages.value.length - 1
        }
        messages.value[streamMsgIdx].content += content
        scrollToBottom()
      },
      onToolEvent(event: Record<string, any>) {
        const eName = event.event || ''
        if (eName === 'tool_started') {
          streamingToolHint.value = `正在调用 ${event.tool}...`
        } else if (eName === 'tool_completed') {
          const summary = event.summary ? ` (${JSON.stringify(event.summary)})` : ''
          streamingToolHint.value = `${event.tool} 完成${summary}`
        } else if (eName === 'tool_round_started') {
          streamingToolHint.value = `第 ${event.round} 轮工具调用（${event.tool_count} 个工具）`
        } else if (eName === 'llm_thinking') {
          streamingToolHint.value = event.message || '正在思考…'
        }
      },
      onDone(data) {
        if ((data as any).error) {
          // error 事件已处理过 UI 状态，只做最终清理
          loading.value = false
          streaming.value = false
          streamingToolHint.value = ''
          activeStreamController = null
          stopLoadingIndicator()
          return
        }
        if (data.conversation_id) selectedThreadId.value = data.conversation_id
        if (streamMsgIdx >= 0 && data.tools_used?.length) {
          messages.value[streamMsgIdx].tools_used = data.tools_used
        }
        loading.value = false
        streaming.value = false
        streamingToolHint.value = ''
        activeStreamController = null
        stopLoadingIndicator()
        loadThreads(selectedThreadId.value)
        scrollToBottom()
      },
      onError(msg: string) {
        if (!firstTokenReceived) {
          messages.value.push({
            role: 'assistant',
            content: `抱歉，处理您的请求时出错：${msg}`,
            tools_used: [],
          })
        } else if (streamMsgIdx >= 0) {
          const existing = messages.value[streamMsgIdx].content.trim()
          if (!existing) {
            messages.value[streamMsgIdx].content = `抱歉，处理您的请求时出错：${msg}`
          } else {
            messages.value[streamMsgIdx].content += `\n\n---\n⚠️ 响应中断：${msg}`
          }
        }
        ElMessage.error(msg)
        loading.value = false
        streaming.value = false
        streamingToolHint.value = ''
        activeStreamController = null
        stopLoadingIndicator()
        scrollToBottom()
      },
    },
  )
}

const handleSend = async () => {
  const text = inputMessage.value.trim()
  if (!text || loading.value || streaming.value || !selectedThreadId.value) return

  messages.value.push({ role: 'user', content: text })
  inputMessage.value = ''
  loading.value = true
  streamingToolHint.value = ''
  startLoadingIndicator()
  scrollToBottom()

  handleSendStream(text)
}

// ---- mem0 记忆状态 ----
const memoryStatus = ref<'ok' | 'off' | 'error'>('off')
const memoryStatusTip = ref('正在检测记忆层...')

async function loadMemoryStatus() {
  try {
    const res = await assistantApi.getMemoryHealth()
    const data = (res as any)?.data ?? res
    if (data?.ok) {
      memoryStatus.value = 'ok'
      memoryStatusTip.value = `mem0 记忆层运行正常 (${data.mem0_version || 'unknown'})`
    } else {
      memoryStatus.value = data?.error?.includes('禁用') ? 'off' : 'error'
      memoryStatusTip.value = data?.error || '记忆层不可用'
    }
  } catch {
    memoryStatus.value = 'off'
    memoryStatusTip.value = '记忆层未配置'
  }
}

onMounted(async () => {
  await loadModels()
  await loadThreads()
  loadMemoryStatus()
})

onBeforeUnmount(() => {
  stopLoadingIndicator()
  if (activeStreamController) {
    activeStreamController.abort()
    activeStreamController = null
  }
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

.assistant-llm-panel {
  flex-shrink: 0;
  padding: 14px 16px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(245, 247, 250, 0.96), rgba(255, 250, 240, 0.96));
}

.assistant-llm-panel-dialog {
  margin: 0;
}

.assistant-llm-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.assistant-llm-title {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
}

.assistant-llm-subtitle {
  margin-top: 4px;
  font-size: 12px;
  color: #6b7280;
}

.assistant-llm-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.assistant-llm-item {
  min-width: 0;
}

.assistant-llm-label {
  margin-bottom: 8px;
  font-size: 13px;
  color: #374151;
}

.assistant-model-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.assistant-model-name {
  flex: 1;
  min-width: 0;
}

.assistant-model-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.assistant-model-provider {
  font-size: 12px;
  color: #6b7280;
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

@media (max-width: 960px) {
  .assistant-llm-grid {
    grid-template-columns: 1fr;
  }
}

.header-left,
.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
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
  align-items: stretch;
}

.thread-sidebar {
  width: clamp(220px, 16vw, 260px);
  flex-shrink: 0;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: var(--el-bg-color);
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.sidebar-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
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

:deep(.thread-tree) {
  --el-tree-node-hover-bg-color: transparent;
  background: transparent;
}

:deep(.thread-tree .el-tree-node__content) {
  height: auto;
  align-items: stretch;
  padding: 3px 0;
}

:deep(.thread-tree .el-tree-node__expand-icon) {
  color: var(--el-text-color-secondary);
  padding: 7px 4px;
}

:deep(.thread-tree .el-tree-node.is-current > .el-tree-node__content .thread-node-main) {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.thread-node {
  width: 100%;
  min-width: 0;
}

.thread-node-main {
  width: 100%;
  min-width: 0;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: var(--el-fill-color-blank);
  padding: 10px 12px;
  transition: all 0.2s ease;

  &:hover {
    border-color: var(--el-color-primary-light-5);
    background: var(--el-color-primary-light-9);
  }
}

.thread-item-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.thread-title-wrap {
  display: flex;
  align-items: flex-start;
  flex: 1;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
}

.thread-type-icon {
  color: var(--el-text-color-secondary);
  flex-shrink: 0;
}

.thread-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
  padding-top: 1px;
}

.thread-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  flex: 1 1 100%;
  min-width: 0;
  line-height: 1.45;
  white-space: normal;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.current-thread-path {
  margin-bottom: 4px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.4;
}

.chat-panel {
  flex: 1 1 auto;
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
  padding: 20px 18px;
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
  max-width: 98%;

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
      padding: 10px 14px;
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
      padding: 12px 16px;
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
      width: 100%;
      display: block;
      overflow-x: auto;
    }
    :deep(thead), :deep(tbody), :deep(tr) {
      display: table;
      width: 100%;
      table-layout: fixed;
    }
    :deep(th), :deep(td) {
      border: 1px solid var(--el-border-color-lighter);
      padding: 4px 10px;
      text-align: left;
      word-break: break-word;
    }
    :deep(th) {
      background: var(--el-fill-color-light);
      font-weight: 600;
    }
    :deep(td:empty)::after {
      content: '—';
      color: var(--el-text-color-placeholder);
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

.streaming-message .message-text.markdown-content::after {
  content: '▌';
  animation: streaming-cursor 0.8s steps(2) infinite;
  color: var(--el-color-primary);
  font-weight: 300;
}

@keyframes streaming-cursor {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
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

  .summary-sidebar {
    width: 100%;
  }
}

.summary-sidebar {
  width: clamp(250px, 18vw, 300px);
  flex-shrink: 0;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: var(--el-bg-color);
  display: flex;
  flex-direction: column;
  min-height: 0;
}

@media (min-width: 1400px) {
  .workspace-body {
    gap: 14px;
  }

  .thread-sidebar {
    width: 240px;
  }

  .summary-sidebar {
    width: 280px;
  }

  .messages-container {
    padding-left: 16px;
    padding-right: 16px;
  }

  .message-item {
    max-width: 99%;
  }
}

.summary-header {
  padding: 14px 14px 10px;
  border-bottom: 1px solid var(--el-border-color-extra-light);
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.summary-title {
  font-size: 14px;
  font-weight: 600;
}

.summary-subtitle {
  margin-top: 4px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.summary-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.summary-card {
  border: 1px solid var(--el-border-color-extra-light);
  border-radius: 10px;
  padding: 12px;
  background: var(--el-fill-color-blank);
}

.summary-card-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 8px;
}

.summary-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.summary-card-header .summary-card-title {
  margin-bottom: 0;
}

.summary-card-text,
.summary-empty {
  font-size: 13px;
  line-height: 1.6;
  color: var(--el-text-color-secondary);
}

.summary-list {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  line-height: 1.5;
  color: var(--el-text-color-regular);
}

.report-ref-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.report-empty-state {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 10px;
}

.report-empty-tip {
  font-size: 12px;
  line-height: 1.5;
  color: var(--el-text-color-placeholder);
}

.report-ref-item {
  width: 100%;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: var(--el-fill-color-blank);
  padding: 10px 12px;
  text-align: left;
  cursor: pointer;
  transition: all 0.2s ease;
}

.report-ref-item:hover {
  border-color: var(--el-color-primary-light-5);
  background: var(--el-color-primary-light-9);
}

.report-ref-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.report-ref-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  line-height: 1.5;
}

.report-ref-status {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--el-color-primary);
}

.report-ref-meta {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}

.report-ref-summary {
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.report-dialog-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.report-dialog-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.report-dialog-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.report-dialog-summary {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.7;
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.report-dialog-content {
  max-height: 60vh;
  overflow-y: auto;
  padding-right: 4px;
  line-height: 1.7;
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.assistant-growth-panel {
  margin-bottom: 4px;
}

.attach-report-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.attach-report-search {
  flex: 1;
}

.attach-report-hint {
  margin-bottom: 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.attach-report-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.attach-report-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: var(--el-fill-color-blank);
}

.attach-report-main {
  min-width: 0;
  flex: 1;
}

.attach-report-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.attach-report-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  line-height: 1.5;
}

.focus-line {
  margin-top: 12px;
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>