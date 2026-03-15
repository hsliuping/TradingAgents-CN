<template>
  <div class="prompt-design-workspace">
    <el-alert type="info" :closable="false" show-icon class="page-alert">
      <template #title>
        <span class="alert-title">
          <el-tag type="success" size="small" effect="dark">Phase 3</el-tag>
          引导式 Prompt 设计 — 按步骤选择分析目标、股票、行业配置，再针对流程中的提示节点进行优化
        </span>
      </template>
    </el-alert>

    <el-card class="wizard-card" shadow="never">
      <el-steps :active="currentStep" finish-status="success" align-center class="wizard-steps">
        <el-step title="分析目标" description="想分析什么" />
        <el-step title="股票与行业" description="选股票、查行业" />
        <el-step title="行业配置" description="使用或新建指引" />
        <el-step title="流程与节点" description="选流程、优化节点" />
      </el-steps>

      <!-- Step 1: 分析目标 -->
      <div v-show="currentStep === 0" class="step-content">
        <div class="step-title">你想分析什么？</div>
        <el-radio-group v-model="wizard.analysisTarget" size="large">
          <el-radio-button value="general">通用分析</el-radio-button>
          <el-radio-button value="industry">行业分析</el-radio-button>
          <el-radio-button value="stock">个股分析</el-radio-button>
        </el-radio-group>
        <p class="step-hint">选择「个股分析」将引导你输入股票、自动查行业、检查行业配置。</p>
      </div>

      <!-- Step 2: 股票与行业 -->
      <div v-show="currentStep === 1" class="step-content">
        <div v-if="wizard.analysisTarget === 'general'" class="step-title">通用分析</div>
        <div v-else-if="wizard.analysisTarget === 'industry'" class="step-title">行业分析 — 输入行业名称</div>
        <div v-else class="step-title">分析哪个股票？</div>
        <template v-if="wizard.analysisTarget === 'stock'">
          <el-input
            v-model="wizard.stockSymbol"
            placeholder="输入股票代码，如 600519"
            style="width: 200px; margin-right: 12px"
            clearable
            @blur="lookupStockIndustry"
          />
          <el-button type="primary" :loading="lookingUp" @click="lookupStockIndustry">查询行业</el-button>
          <div v-if="stockIndustryResult" class="industry-result">
            <el-alert
              :type="stockIndustryResult.success ? 'success' : 'warning'"
              :closable="false"
              show-icon
            >
              <template #title>
                {{ stockIndustryResult.success ? `所属行业：${stockIndustryResult.industry || '未知'}` : stockIndustryResult.message }}
              </template>
              <template v-if="stockIndustryResult.success && stockIndustryResult.name">
                {{ stockIndustryResult.name }}（{{ stockIndustryResult.code }}）
              </template>
            </el-alert>
          </div>
        </template>
        <template v-else-if="wizard.analysisTarget === 'industry'">
          <el-input
            v-model="wizard.industryInput"
            placeholder="输入行业名称，如 白酒、新能源"
            style="width: 220px; margin-right: 12px"
            clearable
          />
          <el-button type="primary" @click="checkIndustryProfileDirect">检查行业配置</el-button>
          <div v-if="industryProfileResult" class="industry-result">
            <el-alert
              :type="industryProfileResult.has_profile ? 'success' : 'info'"
              :closable="false"
              show-icon
            >
              <template #title>
                {{ industryProfileResult.has_profile ? `行业「${wizard.industryInput}」已有分析配置` : `行业「${wizard.industryInput}」暂无分析配置` }}
              </template>
            </el-alert>
          </div>
        </template>
        <p v-else class="step-hint">通用分析无需选择股票，可跳过此步。</p>
      </div>

      <!-- Step 3: 行业配置 -->
      <div v-show="currentStep === 2" class="step-content">
        <div class="step-title">行业配置</div>
        <div v-if="wizard.analysisTarget === 'general'" class="step-hint">
          通用分析无需行业配置，可直接进入下一步选择分析流程。
        </div>
        <div v-else-if="!resolvedIndustry" class="step-hint">
          {{ wizard.analysisTarget === 'industry' ? '请先在上一步输入行业名称并检查。' : '请先在上一步输入股票并查询行业。' }}
        </div>
        <div v-else>
          <el-alert
            :type="industryProfileResult?.has_profile ? 'success' : 'info'"
            :closable="false"
            show-icon
          >
            <template #title>
              {{ industryProfileResult?.has_profile ? `行业「${resolvedIndustry}」已有分析配置` : `行业「${resolvedIndustry}」暂无分析配置` }}
            </template>
            <template #default>
              <template v-if="industryProfileResult?.has_profile">
                {{ industryProfileResult.profile?.display_name }}，{{ industryProfileResult.profile?.dimension_count }} 个分析维度。
                <el-button link type="primary" @click="goToIndustryProfiles">查看/编辑</el-button>
              </template>
              <template v-else>
                <el-button type="primary" @click="openCreateIndustryDialog">在此创建行业配置</el-button>
              </template>
            </template>
          </el-alert>
          <el-form-item v-if="wizard.analysisTarget === 'stock'" label="是否针对个股优化提示词？" class="stock-optimize-item">
            <el-switch v-model="wizard.optimizeForStock" />
            <span class="switch-label">{{ wizard.optimizeForStock ? '是' : '否' }}</span>
          </el-form-item>
        </div>
      </div>

      <!-- Step 4: 流程与节点 -->
      <div v-show="currentStep === 3" class="step-content">
        <div class="step-title">选择分析流程</div>
        <el-select
          v-model="wizard.workflowId"
          placeholder="选择流程"
          style="width: 320px"
          @change="loadWorkflowNodes"
        >
          <el-option
            v-for="wf in workflows"
            :key="wf.id"
            :label="`${wf.name}（${wf.agent_count} 个提示节点）`"
            :value="wf.id"
          />
        </el-select>
        <div v-if="promptNodes.length > 0" class="nodes-section">
          <div class="step-title">流程中的提示节点</div>
          <p class="step-hint">每个节点对应一个 Agent 的提示词，可选择是否优化。</p>
          <el-table :data="promptNodes" stripe size="small">
            <el-table-column prop="label" label="节点" width="180" />
            <el-table-column prop="focus" label="用途说明" min-width="200" />
            <el-table-column label="是否优化" width="100" align="center">
              <template #default="{ row }">
                <el-switch v-model="row.optimize" />
              </template>
            </el-table-column>
          </el-table>
          <div class="node-optimize-actions">
            <el-button type="primary" :disabled="!hasNodeToOptimize" @click="startNodeOptimization">
              对选中节点进行优化
            </el-button>
          </div>
        </div>
      </div>

      <div class="wizard-actions">
        <el-button v-if="currentStep > 0" @click="currentStep--">上一步</el-button>
        <el-button v-if="currentStep < 3" type="primary" @click="currentStep++">下一步</el-button>
      </div>
    </el-card>

    <!-- 行业配置创建弹窗（流程内） -->
    <el-dialog
      v-model="createIndustryDialogVisible"
      title="创建行业配置"
      width="600px"
      :close-on-click-modal="false"
      @closed="resetCreateForm"
    >
      <div class="create-dialog-toolbar">
        <div class="toolbar-main">
          <el-button
            type="primary"
            :loading="generateFormLoading"
            :disabled="!createFormData.industry"
            @click="generateCreateFormDraft"
          >
            <el-icon><MagicStick /></el-icon>
            AI 生成首版草案
          </el-button>
          <el-input
            v-model="createFormUserRequest"
            placeholder="补充要求（可选），如：更关注估值、增加现金流分析"
            clearable
            class="user-request-input"
            @keydown.enter.prevent="generateCreateFormDraft"
          />
        </div>
        <span class="toolbar-hint">由 AI 生成分析维度、关键指标等，可在此基础上修改后保存</span>
      </div>
      <el-form :model="createFormData" label-width="90px">
        <el-form-item label="行业名称" required>
          <el-input v-model="createFormData.industry" disabled placeholder="来自上一步" />
        </el-form-item>
        <el-form-item label="显示名称">
          <el-input v-model="createFormData.display_name" placeholder="如：白酒行业（留空则自动生成）" />
        </el-form-item>
        <el-form-item label="分析重点">
          <el-input v-model="createFormData.analysis_focus" type="textarea" :rows="3" placeholder="该行业分析时的重点关注方向" />
        </el-form-item>
        <el-form-item label="分析维度">
          <div v-for="(dim, idx) in createFormData.analysis_dimensions" :key="idx" class="dimension-row">
            <el-input v-model="dim.name" placeholder="维度名称" style="width: 140px" />
            <el-input v-model="dim.description" placeholder="说明" style="flex: 1; margin: 0 8px" />
            <el-button link type="danger" @click="createFormData.analysis_dimensions.splice(idx, 1)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
          <el-button type="primary" plain size="small" style="margin-top: 8px" @click="addCreateDimension">
            <el-icon><Plus /></el-icon> 添加维度
          </el-button>
        </el-form-item>
        <el-form-item label="关键指标">
          <el-select
            v-model="createFormData.key_metrics"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="输入后回车添加"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="可比公司">
          <el-select
            v-model="createFormData.comparable_companies"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="输入公司名称后回车"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createIndustryDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="createFormSubmitting" @click="submitCreateIndustry">保存</el-button>
      </template>
    </el-dialog>

    <!-- 节点优化对话区（折叠） -->
    <el-card v-if="showChatPanel" class="chat-panel-card" shadow="never">
      <template #header>
        <span>针对「{{ selectedNodeLabel }}」的提示词优化</span>
        <el-button text type="primary" @click="showChatPanel = false">收起</el-button>
      </template>
      <div class="chat-body">
        <div v-for="(msg, idx) in chatMessages" :key="idx" :class="['chat-msg', msg.role]">
          <span class="msg-role">{{ msg.role === 'user' ? '你' : 'AI' }}</span>
          <span class="msg-content">{{ msg.content }}</span>
        </div>
        <div v-if="generating" class="chat-msg assistant">
          <span class="msg-role">AI</span>
          <span class="msg-content">正在分析...</span>
        </div>
        <div class="chat-input-row">
          <el-input
            v-model="chatInput"
            type="textarea"
            :rows="2"
            placeholder="描述你的优化意图"
            @keydown.enter.ctrl.prevent="sendChat"
          />
          <el-button type="primary" :loading="generating" :disabled="!chatInput.trim()" @click="sendChat">发送</el-button>
        </div>

        <div v-if="pendingChanges" class="change-action-panel">
          <el-alert
            type="success"
            :closable="false"
            show-icon
            title="AI 已生成结构化修改建议，可先预览再应用"
          />
          <div class="change-summary">
            <span v-if="pendingTemplateFields.length">模板字段：{{ pendingTemplateFields.join('、') }}</span>
            <span v-if="pendingPolicyScopes.length">策略场景：{{ pendingPolicyScopes.join('、') }}</span>
          </div>
          <div class="change-buttons">
            <el-button :loading="diffLoading" @click="previewSuggestedChanges">预览变更</el-button>
            <el-button type="primary" :loading="applyLoading" @click="applySuggestedChanges">确认应用</el-button>
          </div>
        </div>

        <div v-if="lastApplyResult?.validation_result" class="validation-panel">
          <el-alert
            :type="lastApplyResult.validation_result.passed ? 'success' : 'warning'"
            :closable="false"
            show-icon
            :title="lastApplyResult.validation_result.passed ? '自动验证通过' : '自动验证存在提醒'"
          >
            <template #default>
              {{ lastApplyResult.validation_result.summary }}
            </template>
          </el-alert>
          <div class="change-buttons" style="margin-top: 10px;">
            <el-button type="danger" plain :loading="rollbackLoading" @click="rollbackAppliedChanges">
              回退最近一次应用
            </el-button>
          </div>
        </div>
      </div>
    </el-card>

    <el-dialog
      v-model="diffDialogVisible"
      title="提示词修改前后对比"
      width="1000px"
      destroy-on-close
    >
      <div v-if="diffResult" class="diff-dialog-body">
        <div class="diff-summary">{{ diffResult.diff_summary }}</div>
        <div class="diff-columns">
          <div class="diff-column">
            <div class="diff-title">修改前</div>
            <el-input :model-value="diffResult.before.assembled" type="textarea" :rows="20" readonly />
          </div>
          <div class="diff-column">
            <div class="diff-title">修改后</div>
            <el-input :model-value="diffResult.after.assembled" type="textarea" :rows="20" readonly />
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Delete, MagicStick, Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { analysisProfilesApi } from '@/api/analysisProfiles'
import {
  promptDesignApi,
  type ApplyResponse,
  type ChatResponse,
  type DiffResponse,
  type WorkflowNode,
  type WorkflowItem,
  type StockIndustryResult,
  type IndustryProfileResult,
} from '@/api/promptDesign'
import { labelAgentName, resolveAgentType } from '@/constants/agentLabels'

const router = useRouter()
const currentStep = ref(0)
const lookingUp = ref(false)
const stockIndustryResult = ref<StockIndustryResult | null>(null)
const industryProfileResult = ref<IndustryProfileResult | null>(null)
const workflows = ref<WorkflowItem[]>([])
const promptNodes = ref<(WorkflowNode & { optimize: boolean })[]>([])
const showChatPanel = ref(false)
const chatInput = ref('')
const chatMessages = ref<Array<{ role: 'user' | 'assistant'; content: string }>>([])
const generating = ref(false)
const sessionId = ref('')
const selectedNodeForChat = ref<WorkflowNode | null>(null)
const pendingChanges = ref<ChatResponse['suggested_changes'] | null>(null)
const diffLoading = ref(false)
const applyLoading = ref(false)
const diffDialogVisible = ref(false)
const diffResult = ref<DiffResponse | null>(null)
const lastApplyResult = ref<ApplyResponse | null>(null)
const rollbackLoading = ref(false)

const createIndustryDialogVisible = ref(false)
const createFormSubmitting = ref(false)
const generateFormLoading = ref(false)
const createFormUserRequest = ref('')
const createFormData = reactive({
  industry: '',
  display_name: '',
  analysis_focus: '',
  analysis_dimensions: [] as Array<{ name: string; description: string; importance?: string }>,
  key_metrics: [] as string[],
  comparable_companies: [] as string[],
})

const wizard = reactive({
  analysisTarget: 'stock' as 'general' | 'industry' | 'stock',
  stockSymbol: '',
  industryInput: '',
  optimizeForStock: true,
  workflowId: '',
})

const resolvedIndustry = computed(() => {
  if (wizard.analysisTarget === 'stock' && wizard.stockSymbol) {
    return stockIndustryResult.value?.industry || null
  }
  if (wizard.analysisTarget === 'industry' && wizard.industryInput?.trim()) {
    return wizard.industryInput.trim()
  }
  return null
})

const selectedNodeLabel = computed(() => selectedNodeForChat.value?.label || '')

const hasNodeToOptimize = computed(() => promptNodes.value.some((n) => n.optimize))
const pendingTemplateFields = computed(() => Object.keys(pendingChanges.value?.template_changes || {}))
const pendingPolicyScopes = computed(() => Object.keys(pendingChanges.value?.policy_changes || {}))

const buildPromptContext = () => {
  if (!selectedNodeForChat.value) return null
  return {
    agent_type: resolveAgentType(selectedNodeForChat.value.agent_id),
    agent_name: selectedNodeForChat.value.agent_id,
    analysis_type: wizard.analysisTarget,
    industry: resolvedIndustry.value || undefined,
    stock_symbol: wizard.stockSymbol || undefined,
    workflow_id: wizard.workflowId || undefined,
    node_id: selectedNodeForChat.value.node_id || undefined,
  }
}

const lookupStockIndustry = async () => {
  if (!wizard.stockSymbol?.trim()) {
    ElMessage.warning('请先输入股票代码')
    return
  }
  lookingUp.value = true
  try {
    stockIndustryResult.value = await promptDesignApi.getStockIndustry(wizard.stockSymbol.trim())
    if (stockIndustryResult.value.success && stockIndustryResult.value.industry) {
      industryProfileResult.value = await promptDesignApi.checkIndustryProfile(stockIndustryResult.value.industry)
    } else {
      industryProfileResult.value = null
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '查询失败')
  } finally {
    lookingUp.value = false
  }
}

watch(
  resolvedIndustry,
  (val) => {
    if (val && wizard.analysisTarget === 'stock' && !industryProfileResult.value) {
      promptDesignApi.checkIndustryProfile(val).then((r) => (industryProfileResult.value = r))
    }
  },
  { deep: true }
)

const checkIndustryProfileDirect = async () => {
  if (!wizard.industryInput?.trim()) {
    ElMessage.warning('请先输入行业名称')
    return
  }
  try {
    industryProfileResult.value = await promptDesignApi.checkIndustryProfile(wizard.industryInput.trim())
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '检查失败')
  }
}

const goToIndustryProfiles = () => {
  const industry = resolvedIndustry.value
  router.push({
    path: '/settings/analysis-profiles',
    query: industry ? { industry } : {},
  })
}

const openCreateIndustryDialog = () => {
  const industry = resolvedIndustry.value
  if (!industry) return
  createFormData.industry = industry
  createFormData.display_name = `${industry}行业`
  createFormData.analysis_focus = ''
  createFormData.analysis_dimensions = []
  createFormData.key_metrics = []
  createFormData.comparable_companies = []
  createIndustryDialogVisible.value = true
}

const addCreateDimension = () => {
  createFormData.analysis_dimensions.push({ name: '', description: '', importance: 'high' })
}

const resetCreateForm = () => {
  createFormUserRequest.value = ''
  createFormData.industry = ''
  createFormData.display_name = ''
  createFormData.analysis_focus = ''
  createFormData.analysis_dimensions = []
  createFormData.key_metrics = []
  createFormData.comparable_companies = []
}

const generateCreateFormDraft = async () => {
  const industry = createFormData.industry?.trim()
  if (!industry) return
  const baseRequest = `请为「${industry}」生成一版行业分析配置草案，尽量兼顾当前系统内置数据、MCP、Skill 与手工导入的可行性。`
  const userReq = createFormUserRequest.value?.trim()
  const fullRequest = userReq ? `${baseRequest}\n\n用户补充：${userReq}` : baseRequest
  const hasExisting = createFormData.analysis_dimensions.some((d) => d.name?.trim()) ||
    createFormData.key_metrics.length > 0 || createFormData.analysis_focus?.trim()
  const existingProfile = hasExisting ? {
    industry: createFormData.industry,
    display_name: createFormData.display_name,
    analysis_focus: createFormData.analysis_focus,
    analysis_dimensions: createFormData.analysis_dimensions.filter((d) => d.name?.trim()).map((d) => ({
      name: d.name,
      description: d.description,
      importance: d.importance || 'high',
    })),
    key_metrics: createFormData.key_metrics,
    comparable_companies: createFormData.comparable_companies,
  } : undefined
  generateFormLoading.value = true
  try {
    const res = await analysisProfilesApi.generateIndustry(industry, {
      user_request: fullRequest,
      existing_profile: existingProfile,
    }) as any
    if (res?.success && res?.data?.profile) {
      const p = res.data.profile
      createFormData.display_name = p.display_name || `${industry}行业`
      createFormData.analysis_focus = p.analysis_focus || ''
      createFormData.analysis_dimensions = (p.analysis_dimensions || []).map((d: any) => ({
        name: d.name || '',
        description: d.description || '',
        importance: d.importance || 'high',
      }))
      if (createFormData.analysis_dimensions.length === 0) {
        createFormData.analysis_dimensions = [{ name: '', description: '', importance: 'high' }]
      }
      createFormData.key_metrics = Array.isArray(p.key_metrics) ? [...p.key_metrics] : []
      createFormData.comparable_companies = Array.isArray(p.comparable_companies) ? [...p.comparable_companies] : []
      ElMessage.success('AI 草案已生成，请核对后保存')
    } else {
      ElMessage.error(res?.message || 'AI 生成失败')
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || 'AI 生成失败')
  } finally {
    generateFormLoading.value = false
  }
}

const submitCreateIndustry = async () => {
  if (!createFormData.industry?.trim()) {
    ElMessage.warning('行业名称不能为空')
    return
  }
  const dims = createFormData.analysis_dimensions.filter((d) => d.name?.trim())
  const payload = {
    industry: createFormData.industry.trim(),
    display_name: createFormData.display_name?.trim() || undefined,
    analysis_focus: createFormData.analysis_focus?.trim() || '',
    analysis_dimensions: dims.map((d) => ({
      name: d.name.trim(),
      description: (d.description || '').trim(),
      importance: d.importance || 'high',
      data_source: 'fundamentals',
    })),
    key_metrics: createFormData.key_metrics.filter(Boolean),
    comparable_companies: createFormData.comparable_companies?.filter(Boolean) || [],
    is_active: true,
  }
  createFormSubmitting.value = true
  try {
    const res = await analysisProfilesApi.createIndustry(payload) as any
    if (res?.success) {
      ElMessage.success('行业配置已创建')
      createIndustryDialogVisible.value = false
      industryProfileResult.value = await promptDesignApi.checkIndustryProfile(createFormData.industry.trim())
    } else {
      ElMessage.error(res?.message || '创建失败')
    }
  } catch (e: any) {
    if (e?.response?.status === 409) {
      ElMessage.warning('该行业配置已存在')
      industryProfileResult.value = await promptDesignApi.checkIndustryProfile(createFormData.industry.trim())
      createIndustryDialogVisible.value = false
    } else {
      ElMessage.error(e?.response?.data?.detail || e?.message || '创建失败')
    }
  } finally {
    createFormSubmitting.value = false
  }
}

const loadWorkflows = async () => {
  try {
    const res = await promptDesignApi.listWorkflows()
    workflows.value = res.workflows || []
  } catch {
    workflows.value = []
  }
}

const loadWorkflowNodes = async () => {
  if (!wizard.workflowId) {
    promptNodes.value = []
    return
  }
  try {
    const res = await promptDesignApi.getWorkflowNodes(wizard.workflowId)
    promptNodes.value = (res.nodes || []).map((n) => ({
      ...n,
      label: labelAgentName(n.agent_id) || n.label,
      optimize: false,
    }))
  } catch {
    promptNodes.value = []
  }
}

const startNodeOptimization = () => {
  const toOptimize = promptNodes.value.find((n) => n.optimize)
  if (!toOptimize) return
  selectedNodeForChat.value = toOptimize
  showChatPanel.value = true
  chatMessages.value = []
  sessionId.value = ''
  chatInput.value = ''
  pendingChanges.value = null
  diffResult.value = null
  lastApplyResult.value = null
  chatMessages.value.push({
    role: 'assistant',
    content: `已选择节点「${toOptimize.label}」，用途：${toOptimize.focus || '请描述优化意图'}`,
  })
}

const sendChat = async () => {
  const text = chatInput.value.trim()
  if (!text || !selectedNodeForChat.value) return
  const context = buildPromptContext()
  if (!context) return

  chatMessages.value.push({ role: 'user', content: text })
  chatInput.value = ''
  generating.value = true
  try {
    const res = await promptDesignApi.chat({
      session_id: sessionId.value || undefined,
      message: text,
      ...context,
    })
    if (res.success) {
      sessionId.value = res.session_id
      chatMessages.value.push({ role: 'assistant', content: res.ai_message })
      pendingChanges.value = res.suggested_changes || null
      if (res.suggested_changes) {
        ElMessage.success('已生成结构化修改建议，可先预览再应用')
      }
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '发送失败')
  } finally {
    generating.value = false
  }
}

const previewSuggestedChanges = async () => {
  if (!pendingChanges.value) return
  const context = buildPromptContext()
  if (!context) return
  diffLoading.value = true
  try {
    diffResult.value = await promptDesignApi.diff({
      ...context,
      proposed_template: pendingChanges.value.template_changes,
      proposed_policy: pendingChanges.value.policy_changes,
    })
    diffDialogVisible.value = true
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '预览变更失败')
  } finally {
    diffLoading.value = false
  }
}

const applySuggestedChanges = async () => {
  if (!pendingChanges.value) return
  const context = buildPromptContext()
  if (!context) return

  try {
    await ElMessageBox.confirm('确认应用这次提示词优化建议吗？系统会写入模板或注入策略。', '应用提示词修改', {
      confirmButtonText: '确认应用',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }

  applyLoading.value = true
  try {
    const res = await promptDesignApi.apply({
      session_id: sessionId.value || undefined,
      ...context,
      proposed_template: pendingChanges.value.template_changes,
      proposed_policy: pendingChanges.value.policy_changes,
    })
    if (res.success) {
      pendingChanges.value = null
      lastApplyResult.value = res
      diffResult.value = res.diff
      diffDialogVisible.value = true
      chatMessages.value.push({
        role: 'assistant',
        content: `已应用提示词修改。模板动作：${res.template_action}${res.template?.template_name ? `，模板：${res.template.template_name}` : ''}。自动验证：${res.validation_result.summary}`,
      })
      ElMessage.success(res.validation_result.passed ? '提示词修改已应用，自动验证通过' : '提示词修改已应用，请关注验证提醒')
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '应用修改失败')
  } finally {
    applyLoading.value = false
  }
}

const rollbackAppliedChanges = async () => {
  if (!sessionId.value) return

  try {
    await ElMessageBox.confirm('确认回退当前会话最近一次已应用的提示词修改吗？', '回退提示词修改', {
      confirmButtonText: '确认回退',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }

  rollbackLoading.value = true
  try {
    const res = await promptDesignApi.rollback(sessionId.value)
    if (res.success) {
      const summary = Array.isArray(res.summary) ? res.summary.join('；') : '已完成回退'
      chatMessages.value.push({
        role: 'assistant',
        content: `已回退最近一次提示词应用。${summary}`,
      })
      lastApplyResult.value = null
      pendingChanges.value = null
      ElMessage.success('最近一次提示词应用已回退')
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '回退失败')
  } finally {
    rollbackLoading.value = false
  }
}

watch(currentStep, (step) => {
  if (step === 2 && resolvedIndustry.value && !industryProfileResult.value) {
    promptDesignApi.checkIndustryProfile(resolvedIndustry.value).then((r) => (industryProfileResult.value = r))
  }
})

onMounted(() => {
  loadWorkflows()
})
</script>

<style scoped>
.prompt-design-workspace {
  padding: 20px;
}

.page-alert {
  margin-bottom: 16px;
}

.wizard-card {
  margin-bottom: 16px;
}

.wizard-steps {
  margin-bottom: 24px;
}

.step-content {
  min-height: 180px;
  padding: 16px 0;
}

.step-title {
  font-weight: 600;
  font-size: 16px;
  margin-bottom: 12px;
}

.step-hint {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  margin-top: 12px;
}

.industry-result {
  margin-top: 16px;
}

.stock-optimize-item {
  margin-top: 16px;
}

.switch-label {
  margin-left: 8px;
  font-size: 14px;
}

.nodes-section {
  margin-top: 20px;
}

.node-optimize-actions {
  margin-top: 16px;
}

.wizard-actions {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.chat-panel-card {
  margin-top: 16px;
}

.chat-body {
  padding: 8px 0;
}

.chat-msg {
  margin-bottom: 12px;
}

.chat-msg.user .msg-role {
  color: var(--el-color-primary);
}

.chat-msg .msg-content {
  display: block;
  margin-top: 4px;
  padding: 8px 12px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
}

.chat-input-row {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}

.change-action-panel {
  margin-top: 16px;
  padding: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
}

.change-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 10px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.change-buttons {
  display: flex;
  gap: 10px;
  margin-top: 12px;
}

.diff-dialog-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.validation-panel {
  margin-top: 14px;
}

.diff-summary {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.diff-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.diff-title {
  font-weight: 600;
  margin-bottom: 8px;
}

.chat-input-row .el-input {
  flex: 1;
}

.dimension-row {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.create-dialog-toolbar {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}

.create-dialog-toolbar .toolbar-main {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.create-dialog-toolbar .user-request-input {
  flex: 1;
  min-width: 200px;
}

.create-dialog-toolbar .toolbar-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
