<template>
  <div class="analysis-profiles-container">
    <el-alert type="info" :closable="false" show-icon class="page-alert">
      <template #title>
        <span class="alert-title">
          <el-tag type="info" size="small" effect="dark">智能</el-tag>
          <span>行业/个股分析维度配置 — 用聊天式协作生成行业分析草案，并在保存前透明展示数据覆盖与外部依赖</span>
        </span>
      </template>
    </el-alert>

    <div class="workspace-grid">
      <el-card class="workspace-card chat-card">
        <template #header>
          <div class="card-header">
            <div>
              <div class="card-title">🤖 行业配置助手</div>
              <div class="card-subtitle">多轮沟通生成草案，最后再确认是否保存</div>
            </div>
            <div class="header-actions">
              <el-tag type="info" effect="plain">当前行业：{{ currentIndustryLabel }}</el-tag>
              <el-button text @click="resetConversation()">
                <el-icon><RefreshRight /></el-icon>
                新建对话
              </el-button>
            </div>
          </div>
        </template>

        <div class="session-toolbar">
          <el-select
            v-model="chatIndustry"
            filterable
            clearable
            placeholder="先选择行业，或直接在下方聊天里提到行业名称"
            class="industry-select"
            :loading="industryListLoading"
          >
            <el-option v-for="name in industryList" :key="name" :label="name" :value="name" />
          </el-select>
          <div class="toolbar-actions">
            <el-button type="primary" plain :disabled="!chatIndustry" :loading="generating" @click="startDraftGeneration">
              <el-icon><MagicStick /></el-icon>
              生成首版草案
            </el-button>
            <el-button :disabled="!draftPreview" @click="openDraftInEditor">
              <el-icon><Edit /></el-icon>
              手动精修
            </el-button>
          </div>
        </div>

        <div class="chat-body">
          <div ref="messagesContainer" class="messages-container">
            <div class="messages-list">
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
                  <div class="message-content assistant-content">
                    <div class="message-text">{{ msg.content }}</div>
                  </div>
                </template>
              </div>

              <div v-if="generating" class="message-item message-assistant thinking-bubble">
                <div class="message-avatar">
                  <el-icon><ChatDotRound /></el-icon>
                </div>
                <div class="message-content thinking-content">
                  <span class="thinking-text">正在根据你的要求修订行业草案</span>
                  <span class="thinking-dots">
                    <span class="dot">.</span><span class="dot">.</span><span class="dot">.</span>
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div v-if="draftPreview" class="quick-actions">
            <span class="quick-actions-title">快捷调整</span>
            <el-button size="small" @click="sendQuickPrompt('删除当前草案里需外部数据的维度和指标，保留更容易落地的内容')">删除需外部数据项</el-button>
            <el-button size="small" @click="sendQuickPrompt('补充利润、现金流、资本开支和盈利质量相关维度')">补充利润/现金流</el-button>
            <el-button size="small" @click="sendQuickPrompt('保留运营指标，但在说明里强调需要 MCP、Skill 或外部导入支持')">保留并标注外部依赖</el-button>
            <el-button size="small" @click="sendQuickPrompt('把当前草案收敛成 5 个最关键的核心维度')">收敛成 5 个核心维度</el-button>
            <el-button size="small" type="warning" plain @click="pruneUnsupported">一键裁剪不支持项</el-button>
            <el-button size="small" type="success" @click="handleSaveDraft">保存当前配置</el-button>
          </div>

          <div class="input-area">
            <div class="input-row">
              <el-input
                v-model="chatInput"
                type="textarea"
                :rows="3"
                :autosize="{ minRows: 3, maxRows: 6 }"
                placeholder="例如：先给我一版互联网行业草案；删除没有数据来源的指标；增加现金流和利润质量；保留用户数据类指标但标记需要外部数据。"
                :disabled="generating"
                @keydown.enter.ctrl.prevent="handleSend"
              />
              <el-button
                type="primary"
                class="send-btn"
                :loading="generating"
                :disabled="!chatInput.trim()"
                @click="handleSend"
              >
                <el-icon><Promotion /></el-icon>
                发送
              </el-button>
            </div>
            <span class="input-tip">Ctrl + Enter 发送。你可以继续要求“删除不支持项 / 增加某类指标 / 收敛为更精简框架 / 现在保存”。</span>
          </div>
        </div>
      </el-card>

      <el-card class="workspace-card draft-card">
        <template #header>
          <div class="card-header">
            <div>
              <div class="card-title">📋 当前草案</div>
              <div class="card-subtitle">结构化查看当前版本，随时微调后再保存</div>
            </div>
            <el-tag v-if="draftPreview" :type="overallBadgeType" effect="dark">{{ draftPreview.coverage_summary.overall_label }}</el-tag>
          </div>
        </template>

        <div v-if="draftPreview" class="draft-scroll">
          <el-descriptions :column="2" border size="small" class="summary-descriptions">
            <el-descriptions-item label="行业">{{ draftPreview.profile.display_name || draftPreview.profile.industry }}</el-descriptions-item>
            <el-descriptions-item label="维度数">{{ draftPreview.profile.analysis_dimensions.length }} 项</el-descriptions-item>
            <el-descriptions-item label="关键指标">{{ draftPreview.profile.key_metrics.length }} 项</el-descriptions-item>
            <el-descriptions-item label="可比公司">{{ draftPreview.profile.comparable_companies.length }} 家</el-descriptions-item>
            <el-descriptions-item label="内置数据源">{{ draftPreview.capability_snapshot.counts.builtin_sources }} 类</el-descriptions-item>
            <el-descriptions-item label="MCP / Skill">
              {{ draftPreview.capability_snapshot.counts.enabled_mcp_servers }} / {{ draftPreview.capability_snapshot.counts.active_skills }}
            </el-descriptions-item>
          </el-descriptions>

          <el-alert :type="overallAlertType" :closable="false" show-icon class="summary-alert">
            <template #title>{{ draftPreview.coverage_summary.overall_label }}</template>
            <template #default>
              <ul class="summary-list">
                <li v-for="(rec, idx) in draftPreview.coverage_summary.recommendations" :key="idx">{{ rec }}</li>
              </ul>
            </template>
          </el-alert>

          <div class="draft-section">
            <div class="section-title">分析重点</div>
            <div class="focus-text">{{ draftPreview.profile.analysis_focus || '暂无分析重点说明' }}</div>
          </div>

          <div class="draft-section">
            <div class="section-title">分析维度</div>
            <div class="draft-items">
              <div v-for="(dim, idx) in draftPreview.profile.analysis_dimensions" :key="`${dim.name}-${idx}`" class="draft-item">
                <div class="draft-item-header">
                  <div class="item-title-group">
                    <span class="item-title">{{ dim.name }}</span>
                    <el-tag size="small" :type="statusTagType(draftPreview.dimension_assessments[idx]?.coverage_status)">
                      {{ draftPreview.dimension_assessments[idx]?.coverage_label || '待评估' }}
                    </el-tag>
                    <el-tag size="small" effect="plain">{{ dim.importance || 'high' }}</el-tag>
                  </div>
                  <el-button link type="danger" @click="removeDimensionFromDraft(idx)">
                    <el-icon><Delete /></el-icon>
                  </el-button>
                </div>
                <div class="item-description">{{ dim.description }}</div>
                <div class="item-meta">
                  <el-tag
                    v-for="(src, sourceIdx) in draftPreview.dimension_assessments[idx]?.matched_sources || []"
                    :key="`${dim.name}-${sourceIdx}`"
                    size="small"
                    :type="sourceTagType(src.type)"
                  >
                    {{ src.type_label }} · {{ src.name }}
                  </el-tag>
                  <span v-if="!(draftPreview.dimension_assessments[idx]?.matched_sources || []).length" class="meta-placeholder">暂无明确匹配来源</span>
                </div>
                <div class="item-note">{{ draftPreview.dimension_assessments[idx]?.user_note || '可继续通过聊天要求我改写或删除该维度。' }}</div>
              </div>
            </div>
          </div>

          <div class="draft-section">
            <div class="section-title">关键指标</div>
            <div class="metric-list">
              <div v-for="(metric, idx) in draftPreview.metric_assessments" :key="`${metric.name}-${idx}`" class="metric-item">
                <div class="metric-main">
                  <span>{{ metric.name }}</span>
                  <el-tag size="small" :type="statusTagType(metric.coverage_status)">{{ metric.coverage_label }}</el-tag>
                </div>
                <el-button link type="danger" @click="removeMetricFromDraft(idx)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
            </div>
          </div>

          <div class="draft-section">
            <div class="section-title">可比公司</div>
            <div class="tag-group">
              <el-tag v-for="company in draftPreview.profile.comparable_companies" :key="company" type="info">{{ company }}</el-tag>
              <span v-if="!draftPreview.profile.comparable_companies.length" class="meta-placeholder">暂无可比公司</span>
            </div>
          </div>

          <div class="draft-section">
            <div class="section-title">下一步建议</div>
            <ul class="summary-list compact">
              <li v-for="(guide, idx) in draftPreview.next_step_guidance" :key="idx">{{ guide }}</li>
            </ul>
          </div>
        </div>

        <el-empty
          v-else
          description="先在左侧和助手对话，生成首版行业草案后，这里会实时展示当前配置与数据覆盖情况。"
          :image-size="90"
        />
      </el-card>
    </div>

    <el-card class="saved-card">
      <template #header>
        <div class="card-header">
          <div>
            <div class="card-title">🏭 已保存行业配置</div>
            <div class="card-subtitle">保留列表管理，新增/编辑仍可手动处理</div>
          </div>
          <el-button type="primary" @click="showCreateDialog">
            <el-icon><Plus /></el-icon>
            手动创建
          </el-button>
        </div>
      </template>

      <el-table :data="industryProfiles" v-loading="loading" empty-text="暂无行业配置，可先在上方通过聊天生成并保存">
        <el-table-column prop="display_name" label="行业" min-width="140">
          <template #default="{ row }">
            <span class="industry-name">{{ row.display_name || row.industry }}</span>
          </template>
        </el-table-column>
        <el-table-column label="分析维度" min-width="260">
          <template #default="{ row }">
            <el-tag v-for="dim in (row.analysis_dimensions || []).slice(0, 3)" :key="dim.name" size="small" class="table-tag">
              {{ dim.name }}
            </el-tag>
            <el-tag v-if="(row.analysis_dimensions || []).length > 3" size="small" type="info">
              +{{ row.analysis_dimensions.length - 3 }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="关键指标" min-width="220">
          <template #default="{ row }">
            <el-tag v-for="metric in (row.key_metrics || []).slice(0, 3)" :key="metric" size="small" type="success" class="table-tag">
              {{ metric }}
            </el-tag>
            <el-tag v-if="(row.key_metrics || []).length > 3" size="small" type="info">
              +{{ row.key_metrics.length - 3 }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="editProfile(row)">
              <el-icon><Edit /></el-icon> 编辑
            </el-button>
            <el-button link type="danger" @click="deleteProfile(row)">
              <el-icon><Delete /></el-icon> 删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="editDialogVisible" :title="editMode === 'create' ? '创建行业配置' : '编辑行业配置'" width="780px" top="5vh">
      <el-form :model="formData" label-width="100px">
        <el-form-item label="行业名称" required>
          <el-select
            v-model="formData.industry"
            filterable
            placeholder="搜索并选择行业"
            style="width: 100%"
            :disabled="editMode === 'edit'"
            :loading="industryListLoading"
          >
            <el-option v-for="name in industryList" :key="name" :label="name" :value="name" />
          </el-select>
        </el-form-item>
        <el-form-item label="显示名称">
          <el-input v-model="formData.display_name" placeholder="如：银行业（留空则使用行业名称）" />
        </el-form-item>
        <el-form-item label="分析重点">
          <el-input v-model="formData.analysis_focus" type="textarea" :rows="3" placeholder="该行业分析时的重点关注方向" />
        </el-form-item>
        <el-form-item label="启用状态">
          <el-switch v-model="formData.is_active" />
        </el-form-item>

        <el-divider>分析维度</el-divider>
        <div v-for="(dim, idx) in formData.analysis_dimensions" :key="idx" class="dimension-row">
          <el-input v-model="dim.name" placeholder="维度名称" style="width: 160px" />
          <el-input v-model="dim.description" placeholder="维度说明" style="flex: 1; margin: 0 8px" />
          <el-select v-model="dim.importance" placeholder="重要性" style="width: 110px; margin-right: 8px">
            <el-option label="关键" value="critical" />
            <el-option label="高" value="high" />
            <el-option label="中" value="medium" />
          </el-select>
          <el-button link type="danger" @click="formData.analysis_dimensions.splice(idx, 1)">
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
        <el-button
          type="primary"
          plain
          size="small"
          style="margin-top: 8px"
          @click="formData.analysis_dimensions.push({ name: '', description: '', importance: 'high', data_source: 'fundamentals' })"
        >
          <el-icon><Plus /></el-icon> 添加维度
        </el-button>

        <el-divider>关键指标</el-divider>
        <el-select
          v-model="formData.key_metrics"
          multiple
          filterable
          allow-create
          default-first-option
          :reserve-keyword="false"
          placeholder="输入指标名称后回车"
          style="width: 100%"
        />

        <el-divider>可比公司</el-divider>
        <el-select
          v-model="formData.comparable_companies"
          multiple
          filterable
          allow-create
          default-first-option
          :reserve-keyword="false"
          placeholder="输入公司名称后回车"
          style="width: 100%"
        />
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ChatDotRound, Delete, Edit, MagicStick, Plus, Promotion, RefreshRight, User } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { analysisProfilesApi, type GeneratePreview, type IndustryProfile } from '@/api/analysisProfiles'

type ElTagType = 'primary' | 'success' | 'info' | 'warning' | 'danger'
type ElAlertType = 'success' | 'info' | 'warning' | 'error'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

const route = useRoute()
const loading = ref(false)
const generating = ref(false)
const submitting = ref(false)

const industryProfiles = ref<IndustryProfile[]>([])
const industryList = ref<string[]>([])
const industryListLoading = ref(false)

const chatIndustry = ref('')
const chatInput = ref('')
const messages = ref<ChatMessage[]>([])
const messagesContainer = ref<HTMLElement | null>(null)
const draftPreview = ref<GeneratePreview | null>(null)

const editDialogVisible = ref(false)
const editMode = ref<'create' | 'edit'>('create')
const editingId = ref<string | null>(null)

const emptyForm = (): IndustryProfile => ({
  industry: '',
  display_name: '',
  analysis_dimensions: [],
  analysis_focus: '',
  key_metrics: [],
  comparable_companies: [],
  is_active: true,
})

const formData = ref<IndustryProfile>(emptyForm())

function cloneDeep<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

const statusTagType = (status?: string): ElTagType => {
  if (status === 'directly_usable') return 'success'
  if (status === 'partially_usable') return 'warning'
  if (status === 'external_required') return 'danger'
  return 'info'
}

const sourceTagType = (type?: string): ElTagType => {
  if (type === 'builtin') return 'info'
  if (type === 'mcp') return 'warning'
  if (type === 'skill') return 'success'
  return 'info'
}

const overallBadgeType = computed<ElTagType>(() => {
  const status = draftPreview.value?.coverage_summary?.overall_status
  if (status === 'ready') return 'success'
  if (status === 'review_needed') return 'warning'
  return 'danger'
})

const overallAlertType = computed<ElAlertType>(() => {
  const status = draftPreview.value?.coverage_summary?.overall_status
  if (status === 'ready') return 'success'
  if (status === 'review_needed') return 'warning'
  return 'error'
})

const currentIndustryLabel = computed(() => {
  return chatIndustry.value || draftPreview.value?.profile?.industry || '未选择'
})

const countStatuses = (items: Array<{ coverage_status?: string }> = []) => {
  const counts = {
    directly_usable: 0,
    partially_usable: 0,
    external_required: 0,
    review_recommended: 0,
  }
  items.forEach((item) => {
    const key = item?.coverage_status as keyof typeof counts
    if (key && typeof counts[key] === 'number') counts[key] += 1
  })
  return counts
}

const createDefaultCoverageSummary = () => ({
  overall_status: 'review_needed' as const,
  overall_label: '建议人工复核后保存',
  dimension_counts: countStatuses(),
  metric_counts: countStatuses(),
  recommendations: [] as string[],
})

const normalizeProfile = (profile?: Partial<IndustryProfile> | null): IndustryProfile => ({
  ...emptyForm(),
  ...cloneDeep(profile || {}),
  analysis_dimensions: Array.isArray(profile?.analysis_dimensions) ? cloneDeep(profile.analysis_dimensions) : [],
  key_metrics: Array.isArray(profile?.key_metrics) ? [...profile.key_metrics] : [],
  comparable_companies: Array.isArray(profile?.comparable_companies) ? [...profile.comparable_companies] : [],
})

const normalizePreview = (preview: any): GeneratePreview => ({
  profile: normalizeProfile(preview?.profile),
  coverage_summary: preview?.coverage_summary || createDefaultCoverageSummary(),
  capability_snapshot: preview?.capability_snapshot || {
    builtin_sources: [],
    enabled_mcp_servers: [],
    active_skills: [],
    manual_import: {
      available: true,
      label: '手工导入',
      description: '可手工补充外部数据',
    },
    counts: {
      builtin_sources: 0,
      enabled_mcp_servers: 0,
      active_skills: 0,
    },
    notes: [],
  },
  dimension_assessments: Array.isArray(preview?.dimension_assessments) ? cloneDeep(preview.dimension_assessments) : [],
  metric_assessments: Array.isArray(preview?.metric_assessments) ? cloneDeep(preview.metric_assessments) : [],
  next_step_guidance: Array.isArray(preview?.next_step_guidance) ? [...preview.next_step_guidance] : [],
})

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

const pushMessage = (role: ChatMessage['role'], content: string) => {
  messages.value.push({ role, content })
  scrollToBottom()
}

const buildWelcomeMessage = () => {
  return '你好，我会和你一起迭代生成行业分析配置。\n\n你可以先：\n1. 在上方选择一个行业，点击“生成首版草案”\n2. 或直接在下面发消息，例如“帮我做一个互联网行业配置，删除没有数据来源的项”\n\n我会在每一轮里告诉你哪些数据系统能支持，哪些需要 MCP / Skill / 外部导入，最后再问你是否保存。'
}

const buildAssistantSummary = (preview: GeneratePreview, hadDraft: boolean) => {
  const dimensionCounts = preview.coverage_summary.dimension_counts || countStatuses()
  const metricCounts = preview.coverage_summary.metric_counts || countStatuses()

  return `${hadDraft ? '我已经根据你的最新要求修订了当前草案。' : '我先给你生成了一版首版草案。'}

行业：${preview.profile.display_name || preview.profile.industry}
当前状态：${preview.coverage_summary.overall_label}
维度 ${preview.profile.analysis_dimensions.length} 项：可直接使用 ${dimensionCounts.directly_usable} / 部分可用 ${dimensionCounts.partially_usable} / 需外部数据 ${dimensionCounts.external_required} / 建议复核 ${dimensionCounts.review_recommended}
指标 ${preview.profile.key_metrics.length} 项：可直接使用 ${metricCounts.directly_usable} / 部分可用 ${metricCounts.partially_usable} / 需外部数据 ${metricCounts.external_required} / 建议复核 ${metricCounts.review_recommended}
系统能力：内置数据源 ${preview.capability_snapshot.counts.builtin_sources} 类，MCP ${preview.capability_snapshot.counts.enabled_mcp_servers} 个，Skill ${preview.capability_snapshot.counts.active_skills} 个。

你可以继续让我：
- 删除需外部数据的项
- 增加利润、现金流、资本开支等维度
- 保留运营指标，但明确标注需要外部来源
- 收敛成更精简的 5 个核心维度

如果这版已经合适，我现在也可以帮你保存。`
}

const rebuildCoverageSummary = () => {
  if (!draftPreview.value) return

  const dimensionCounts = countStatuses(draftPreview.value.dimension_assessments)
  const metricCounts = countStatuses(draftPreview.value.metric_assessments)
  const totalExternal = dimensionCounts.external_required + metricCounts.external_required
  const totalReview = dimensionCounts.review_recommended + metricCounts.review_recommended

  let overall_status: 'ready' | 'review_needed' | 'prune_needed' = 'prune_needed'
  let overall_label = '建议先裁剪再保存'

  if (totalExternal === 0 && totalReview <= 1) {
    overall_status = 'ready'
    overall_label = '大部分内容已具备落地基础'
  } else if (totalExternal <= 2 && totalReview <= 3) {
    overall_status = 'review_needed'
    overall_label = '建议人工复核后保存'
  }

  const recommendations: string[] = []
  if (dimensionCounts.directly_usable || metricCounts.directly_usable) {
    recommendations.push('优先保留“可直接使用”的维度和指标，它们最容易被当前系统稳定支撑。')
  }
  if (totalExternal) {
    recommendations.push(`当前仍有 ${totalExternal} 项被识别为“需外部数据”，保存前请确认 MCP / Skill / 手工导入方案。`)
  }
  if (totalReview) {
    recommendations.push(`当前仍有 ${totalReview} 项为“建议复核”，若无法确认来源，建议继续删改。`)
  }
  if (!recommendations.length) {
    recommendations.push('当前草案已经比较适合作为默认行业分析模板。')
  }

  draftPreview.value.coverage_summary = {
    overall_status,
    overall_label,
    dimension_counts: dimensionCounts,
    metric_counts: metricCounts,
    recommendations,
  }
}

const resetConversation = (preserveIndustry = false) => {
  const preserved = preserveIndustry ? chatIndustry.value : ''
  chatIndustry.value = preserved
  chatInput.value = ''
  draftPreview.value = null
  messages.value = [{ role: 'assistant', content: buildWelcomeMessage() }]
  scrollToBottom()
}

const inferIndustryFromText = (text: string) => {
  return industryList.value.find((name) => text.includes(name)) || ''
}

const requestDraft = async (userRequest: string) => {
  const industry = chatIndustry.value.trim()
  if (!industry) {
    ElMessage.warning('请先选择行业，或在消息中明确提到行业名称')
    return
  }

  const hadDraft = Boolean(draftPreview.value)
  generating.value = true
  try {
    const res = await analysisProfilesApi.generateIndustry(industry, {
      user_request: userRequest,
      existing_profile: draftPreview.value?.profile,
    }) as any

    if (res?.success && res.data) {
      draftPreview.value = normalizePreview(res.data)
      pushMessage('assistant', buildAssistantSummary(draftPreview.value, hadDraft))
    } else {
      ElMessage.error(res?.message || '生成失败')
      pushMessage('assistant', '这轮生成失败了。你可以稍后重试，或者换一种更明确的要求继续让我修订。')
    }
  } catch (error: any) {
    ElMessage.error(error?.message || 'AI 生成失败，请稍后重试')
    pushMessage('assistant', '我这轮没有成功生成草案。请稍后重试，或把要求描述得更具体一些。')
  } finally {
    generating.value = false
  }
}

const startDraftGeneration = async () => {
  if (!chatIndustry.value.trim()) {
    ElMessage.warning('请先选择行业')
    return
  }

  const starter = `请先为「${chatIndustry.value.trim()}」生成一版行业分析配置草案，尽量兼顾当前系统内置数据、MCP、Skill 与手工导入的可行性。`
  pushMessage('user', starter)
  await requestDraft(starter)
}

const handleSend = async () => {
  const text = chatInput.value.trim()
  if (!text) return
  chatInput.value = ''

  if (!chatIndustry.value.trim()) {
    const inferred = inferIndustryFromText(text)
    if (inferred) chatIndustry.value = inferred
  }

  pushMessage('user', text)

  if (!chatIndustry.value.trim()) {
    pushMessage('assistant', '我还不知道你要配置哪个行业。请先在上方选择行业，或者在消息里直接说出数据库中存在的行业名称。')
    return
  }

  const normalized = text.replace(/[。！？!?.\s]/g, '')
  if (draftPreview.value && ['保存', '确认保存', '现在保存', '就这样保存'].includes(normalized)) {
    await handleSaveDraft()
    return
  }

  await requestDraft(text)
}

const sendQuickPrompt = async (prompt: string) => {
  if (!draftPreview.value) {
    ElMessage.warning('请先生成一版草案')
    return
  }
  pushMessage('user', prompt)
  await requestDraft(prompt)
}

const removeDimensionFromDraft = (index: number) => {
  if (!draftPreview.value) return
  draftPreview.value.profile.analysis_dimensions.splice(index, 1)
  draftPreview.value.dimension_assessments.splice(index, 1)
  rebuildCoverageSummary()
  ElMessage.success('已删除该维度')
}

const removeMetricFromDraft = (index: number) => {
  if (!draftPreview.value) return
  const metricName = draftPreview.value.metric_assessments[index]?.name
  draftPreview.value.metric_assessments.splice(index, 1)
  if (metricName) {
    draftPreview.value.profile.key_metrics = draftPreview.value.profile.key_metrics.filter((item) => item !== metricName)
  }
  rebuildCoverageSummary()
  ElMessage.success('已删除该指标')
}

const pruneUnsupported = () => {
  if (!draftPreview.value) return

  const removableDimensions = draftPreview.value.dimension_assessments
    .filter((item) => ['external_required', 'review_recommended'].includes(item.coverage_status))
    .map((item) => item.name)

  const removableMetrics = draftPreview.value.metric_assessments
    .filter((item) => ['external_required', 'review_recommended'].includes(item.coverage_status))
    .map((item) => item.name)

  const keepDimensionIndexes = draftPreview.value.dimension_assessments
    .map((item, index) => ({ item, index }))
    .filter(({ item }) => ['directly_usable', 'partially_usable'].includes(item.coverage_status))
    .map(({ index }) => index)

  const nextDimensions = keepDimensionIndexes.map((index) => draftPreview.value!.profile.analysis_dimensions[index])
  const nextDimensionAssessments = keepDimensionIndexes.map((index) => draftPreview.value!.dimension_assessments[index])

  const keepMetricIndexes = draftPreview.value.metric_assessments
    .map((item, index) => ({ item, index }))
    .filter(({ item }) => ['directly_usable', 'partially_usable'].includes(item.coverage_status))
    .map(({ index }) => index)

  const nextMetricAssessments = keepMetricIndexes.map((index) => draftPreview.value!.metric_assessments[index])
  const keptMetricNames = new Set(nextMetricAssessments.map((item) => item.name))

  draftPreview.value.profile.analysis_dimensions = nextDimensions
  draftPreview.value.dimension_assessments = nextDimensionAssessments
  draftPreview.value.metric_assessments = nextMetricAssessments
  draftPreview.value.profile.key_metrics = draftPreview.value.profile.key_metrics.filter((item) => keptMetricNames.has(item))

  rebuildCoverageSummary()

  const removedSummary = [
    removableDimensions.length ? `删除维度：${removableDimensions.join('、')}` : '',
    removableMetrics.length ? `删除指标：${removableMetrics.join('、')}` : '',
  ].filter(Boolean).join('\n')

  pushMessage('assistant', `${removedSummary || '当前没有明显需要裁剪的项。'}\n\n我已经把更难落地的项先裁掉了。现在这版更接近可直接保存的行业模板；如果你还想继续补充或调整，可以继续告诉我。`)
  ElMessage.success('已裁剪不支持项')
}

const showCreateDialog = () => {
  editMode.value = 'create'
  editingId.value = null
  formData.value = { ...emptyForm(), industry: chatIndustry.value || '' }
  editDialogVisible.value = true
}

const openDraftInEditor = () => {
  if (!draftPreview.value) return
  editMode.value = 'create'
  editingId.value = null
  formData.value = normalizeProfile(draftPreview.value.profile)
  editDialogVisible.value = true
}

const editProfile = (row: IndustryProfile) => {
  editMode.value = 'edit'
  editingId.value = row.id || null
  formData.value = normalizeProfile(row)
  editDialogVisible.value = true
}

const handleSaveDraft = async () => {
  if (!draftPreview.value) {
    ElMessage.warning('请先生成草案')
    return
  }

  const payload = normalizeProfile(draftPreview.value.profile)
  if (!payload.industry.trim()) {
    ElMessage.warning('当前草案缺少行业名称，暂时无法保存')
    return
  }

  const existing = industryProfiles.value.find((item) => item.industry === payload.industry)

  try {
    const confirmMessage = existing
      ? `行业「${payload.industry}」已存在配置。是否用当前聊天草案覆盖它？`
      : `确认将当前「${payload.industry}」草案保存为行业配置吗？`

    await ElMessageBox.confirm(confirmMessage, '确认保存', {
      confirmButtonText: existing ? '覆盖保存' : '保存',
      cancelButtonText: '取消',
      type: 'warning',
    })

    let res: any
    if (existing?.id) {
      res = await analysisProfilesApi.updateIndustry(existing.id, payload)
    } else {
      try {
        res = await analysisProfilesApi.createIndustry(payload)
      } catch (createErr: any) {
        // 409 = 行业已存在但本地列表过时，刷新列表后改走 update
        if (createErr?.response?.status === 409 || createErr?.status === 409) {
          await loadProfiles()
          const freshExisting = industryProfiles.value.find((item) => item.industry === payload.industry)
          if (freshExisting?.id) {
            res = await analysisProfilesApi.updateIndustry(freshExisting.id, payload)
          } else {
            throw new Error('行业配置已存在但无法获取 ID，请刷新页面后重试')
          }
        } else {
          throw createErr
        }
      }
    }

    if (res?.success) {
      ElMessage.success(existing?.id ? '已覆盖保存' : '保存成功')
      pushMessage('assistant', `好的，已经把当前草案${existing?.id ? '覆盖保存' : '保存'}为行业配置。后续如果你还想继续优化，也可以随时再回来和我对话。`)
      await loadProfiles()
    } else {
      ElMessage.error(res?.message || '保存失败')
    }
  } catch (error: any) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error?.response?.data?.detail || error?.message || '保存失败')
    }
  }
}

const loadIndustryList = async () => {
  industryListLoading.value = true
  try {
    const res = await analysisProfilesApi.getIndustryList() as any
    if (res?.success) {
      industryList.value = res.data || []
    }
  } catch (error) {
    console.error('加载行业列表失败:', error)
  } finally {
    industryListLoading.value = false
  }
}

const loadProfiles = async () => {
  loading.value = true
  try {
    const res = await analysisProfilesApi.listIndustries() as any
    if (res?.success) {
      industryProfiles.value = res.data || []
    }
  } catch (error) {
    console.error('加载行业配置失败:', error)
    ElMessage.error('加载行业配置失败')
  } finally {
    loading.value = false
  }
}

const submitForm = async () => {
  if (!formData.value.industry.trim()) {
    ElMessage.warning('请输入行业名称')
    return
  }

  submitting.value = true
  try {
    const payload = normalizeProfile(formData.value)
    let res: any
    if (editMode.value === 'create') {
      res = await analysisProfilesApi.createIndustry(payload)
    } else if (editingId.value) {
      res = await analysisProfilesApi.updateIndustry(editingId.value, payload)
    }

    if (res?.success) {
      ElMessage.success(editMode.value === 'create' ? '创建成功' : '更新成功')
      editDialogVisible.value = false
      await loadProfiles()
    } else {
      ElMessage.error(res?.message || '保存失败')
    }
  } catch (error: any) {
    ElMessage.error(error?.message || '保存失败')
  } finally {
    submitting.value = false
  }
}

const deleteProfile = async (row: IndustryProfile) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除行业配置「${row.display_name || row.industry}」吗？`,
      '确认删除',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' },
    )

    const res = await analysisProfilesApi.deleteIndustry(row.id!) as any
    if (res?.success) {
      ElMessage.success('删除成功')
      await loadProfiles()
    } else {
      ElMessage.error(res?.message || '删除失败')
    }
  } catch (error: any) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(async () => {
  await Promise.all([loadProfiles(), loadIndustryList()])
  const qIndustry = route.query.industry as string | undefined
  if (qIndustry?.trim()) {
    chatIndustry.value = qIndustry.trim()
  }
  resetConversation()
})
</script>

<style scoped lang="scss">
.analysis-profiles-container {
  padding: 20px;
}

.page-alert {
  margin-bottom: 16px;
}

.alert-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.workspace-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(320px, 0.95fr);
  gap: 16px;
  margin-bottom: 16px;
}

.workspace-card,
.saved-card {
  border-radius: 12px;
}

.chat-card,
.draft-card {
  min-height: 760px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.card-subtitle {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.session-toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
}

.industry-select {
  flex: 1;
}

.toolbar-actions {
  display: flex;
  gap: 8px;
}

.chat-body {
  display: flex;
  flex-direction: column;
  min-height: 660px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  overflow: hidden;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px 20px 16px;
  background: linear-gradient(180deg, rgba(64, 158, 255, 0.03), transparent 18%);
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
      color: var(--el-text-color-primary);
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
}

.message-content {
  border-radius: 14px;
  padding: 12px 16px;
}

.message-text {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.75;
  font-size: 14px;
}

.assistant-content {
  box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.02);
}

.thinking-bubble {
  opacity: 0.95;
}

.thinking-content {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.thinking-text {
  color: var(--el-text-color-secondary);
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

.quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-extra-light);
}

.quick-actions-title {
  display: inline-flex;
  align-items: center;
  margin-right: 4px;
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
}

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
    height: 72px;
    padding: 0 20px;
  }

  .input-tip {
    display: block;
    margin-top: 6px;
    font-size: 12px;
    color: var(--el-text-color-placeholder);
    line-height: 1.6;
  }

  :deep(.el-textarea__inner) {
    resize: none;
  }
}

.draft-scroll {
  max-height: 690px;
  overflow-y: auto;
  padding-right: 4px;
}

.summary-descriptions,
.summary-alert,
.draft-section {
  margin-bottom: 16px;
}

.summary-list {
  margin: 6px 0 0;
  padding-left: 18px;
  line-height: 1.8;
}

.summary-list.compact {
  margin-top: 0;
}

.section-title {
  margin-bottom: 10px;
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.focus-text {
  padding: 12px;
  border-radius: 10px;
  background: var(--el-fill-color-extra-light);
  color: var(--el-text-color-regular);
  line-height: 1.8;
  white-space: pre-wrap;
}

.draft-items,
.metric-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.draft-item,
.metric-item {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  padding: 12px;
  background: #fff;
}

.draft-item-header,
.metric-item {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
}

.item-title-group {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.item-title,
.industry-name {
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.item-description {
  margin-top: 8px;
  line-height: 1.7;
  color: var(--el-text-color-regular);
}

.item-meta,
.tag-group {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.item-note {
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.7;
}

.meta-placeholder {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}

.metric-main {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.saved-card {
  margin-top: 4px;
}

.table-tag {
  margin-right: 4px;
  margin-bottom: 4px;
}

.dimension-row {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

@media (max-width: 1280px) {
  .workspace-grid {
    grid-template-columns: 1fr;
  }

  .chat-card,
  .draft-card {
    min-height: auto;
  }

  .draft-scroll {
    max-height: none;
  }
}

@media (max-width: 768px) {
  .analysis-profiles-container {
    padding: 12px;
  }

  .card-header,
  .session-toolbar,
  .toolbar-actions,
  .header-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .message-item {
    max-width: 100%;
  }

  .input-area .input-row {
    flex-direction: column;
  }

  .input-area .send-btn {
    width: 100%;
    height: 40px;
  }

  .dimension-row {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }
}
</style>

