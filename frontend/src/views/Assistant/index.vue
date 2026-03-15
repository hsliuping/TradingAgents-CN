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
                  <div class="thread-preview">{{ data.current_summary?.abstract || data.last_user_message || '进入主题开始研究' }}</div>
                  <div class="thread-meta">
                    <span>{{ data.message_count }} 条消息</span>
                    <span v-if="data.children?.length">{{ data.children.length }} 个子主题</span>
                    <span>{{ formatTime(data.updated_at) }}</span>
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

      <aside class="summary-sidebar">
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
            <div v-else class="summary-empty">继续追问或触发深度分析来推进主题。</div>
          </div>
        </div>
      </aside>
    </div>

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
          <div
            v-else-if="activeReportDetail?.content"
            class="report-dialog-content markdown-content"
            v-html="renderMarkdown(activeReportDetail.content)"
          ></div>
          <div v-else class="report-dialog-summary">{{ activeReportRef.summary || '当前仅记录了该报告的引用，尚未保存更多摘要内容。' }}</div>
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
import { ChatDotRound, DataAnalysis, Delete, Document, FolderOpened, Plus, QuestionFilled, User } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'

import { assistantApi } from '@/api/assistant'
import type {
  AssistantThreadItem,
  AssistantThreadReportSearchResponse,
  AssistantThreadReportDetail,
  AssistantThreadReportRef,
  AssistantThreadSummary,
  MessageItem,
} from '@/api/assistant'

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

interface ThreadTreeNode extends AssistantThreadItem {
  children: ThreadTreeNode[]
}

const inputMessage = ref('')
const loading = ref(false)
const sidebarLoading = ref(false)
const summaryLoading = ref(false)
const analysisMode = ref<'react' | 'planned'>('react')
const loadingSeconds = ref(0)
const threads = ref<AssistantThreadItem[]>([])
const selectedThreadId = ref<string>('')
const messages = ref<DisplayMessage[]>([])
const messagesContainer = ref<HTMLElement | null>(null)
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
const focusPercent = computed(() => Math.max(0, Math.min(100, Math.round((currentSummary.value?.focus_score || 0) * 100))))

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
  flex-wrap: wrap;
  gap: 8px;
  color: var(--el-text-color-placeholder);
  font-size: 12px;
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