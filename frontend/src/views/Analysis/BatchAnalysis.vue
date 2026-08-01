<template>
  <div class="batch-analysis">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">
            <el-icon class="title-icon"><Files /></el-icon>
            批量分析
            <el-tag type="warning" effect="dark" size="small" style="margin-left: 12px; vertical-align: middle;">高级</el-tag>
          </h1>
          
          <!-- 风险提示 -->
          <div class="risk-disclaimer">
            <el-alert
              type="warning"
              :closable="false"
              show-icon
            >
              <template #title>
                <span style="font-size: 14px;">
                  <strong>⚠️ 重要提示：</strong>本次分析仅用于学习、研究和公开信息整理，不提供个股交易指导。
                </span>
              </template>
            </el-alert>
          </div>
          
          <p class="page-description">
            AI驱动的批量研究工作台，高效整理多只股票的研究线索
          </p>
        </div>
      </div>
    </div>

    <!-- 股票列表输入区域 -->
    <div class="analysis-container">
      <el-row :gutter="24">
        <el-col :span="24">
          <el-card class="stock-list-card" shadow="hover">
            <template #header>
              <div class="card-header">
                <h3>📋 股票列表</h3>
                <el-tag :type="stockCodes.length > 0 ? 'success' : 'info'" size="small">
                  {{ stockCodes.length }} 只股票
                </el-tag>
              </div>
            </template>

            <div class="stock-input-section">
              <!-- 市场类型选择 -->
              <div style="margin-bottom: 16px;">
                <el-select v-model="batchForm.market" size="default" style="width: 240px;">
                  <el-option label="🇨🇳 A股市场" value="A股">
                    <span>🇨🇳 A股市场</span>
                    <span style="color: #909399; font-size: 12px; margin-left: 8px;">（6位数字）</span>
                  </el-option>
                  <el-option label="📈 ETF 基金" value="ETF">
                    <span>📈 ETF 基金</span>
                    <span style="color: #909399; font-size: 12px; margin-left: 8px;">（510050、159919 等）</span>
                  </el-option>
                </el-select>
              </div>
              
              <div class="input-area">
                <el-input
                  v-model="stockInput"
                  type="textarea"
                  :rows="8"
                  :placeholder="batchForm.market === 'ETF' 
                    ? etfPlaceholder 
                    : stockPlaceholder"
                  @input="parseStockCodes"
                  class="stock-textarea"
                />
                <div class="input-actions">
                  <el-button type="primary" @click="parseStockCodes" size="small">
                    解析股票代码
                  </el-button>
                  <el-button @click="clearStocks" size="small">清空</el-button>
                </div>
              </div>

              <!-- 股票预览 -->
              <div v-if="stockCodes.length > 0" class="stock-preview">
                <h4>股票预览</h4>
                <div class="stock-tags">
                  <el-tag
                    v-for="(code, index) in stockCodes.slice(0, 20)"
                    :key="code"
                    closable
                    @close="removeStock(index)"
                    class="stock-tag"
                  >
                    {{ code }}
                  </el-tag>
                  <el-tag v-if="stockCodes.length > 20" type="info">
                    +{{ stockCodes.length - 20 }} 更多...
                  </el-tag>
                </div>
              </div>

              <!-- 无效代码提示 -->
              <div v-if="invalidCodes.length > 0" class="invalid-codes">
                <el-alert
                  title="以下股票代码格式可能有误，请检查："
                  type="warning"
                  :closable="false"
                >
                  <div class="invalid-list">
                    <el-tag v-for="code in invalidCodes" :key="code" type="danger" size="small">
                      {{ code }}
                    </el-tag>
                  </div>
                </el-alert>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 分析配置区域 -->
      <el-row :gutter="24" style="margin-top: 24px;">
        <!-- 左侧：分析配置 -->
        <el-col :span="18">
          <el-card class="config-card" shadow="hover">
            <template #header>
              <div class="card-header">
                <h3>⚙️ 分析配置</h3>
                <el-tag type="primary" size="small">批量设置</el-tag>
              </div>
            </template>

            <el-form :model="batchForm" label-width="100px" class="batch-form">
              <!-- 分析参数 -->
              <div class="form-section">
                <h4 class="section-title">⚙️ 分析参数</h4>
                <el-form-item label="分析深度">
                  <el-select v-model="batchForm.depth" placeholder="选择分析深度" size="large" style="width: 100%">
                    <el-option label="⚡ 1级 - 快速分析" value="1">
                      <span>⚡ 1级 - 快速分析</span>
                      <span style="float: right; color: #8492a6; font-size: 13px">2-4分钟/只</span>
                    </el-option>
                    <el-option label="📈 2级 - 基础分析" value="2">
                      <span>📈 2级 - 基础分析</span>
                      <span style="float: right; color: #8492a6; font-size: 13px">4-6分钟/只</span>
                    </el-option>
                    <el-option label="🎯 3级 - 标准分析（推荐）" value="3">
                      <span>🎯 3级 - 标准分析</span>
                      <span style="float: right; color: #8492a6; font-size: 13px">6-10分钟/只 ⭐</span>
                    </el-option>
                    <el-option label="🔍 4级 - 深度分析" value="4">
                      <span>🔍 4级 - 深度分析</span>
                      <span style="float: right; color: #8492a6; font-size: 13px">10-15分钟/只</span>
                    </el-option>
                    <el-option label="🏆 5级 - 全面分析" value="5">
                      <span>🏆 5级 - 全面分析</span>
                      <span style="float: right; color: #8492a6; font-size: 13px">15-25分钟/只</span>
                    </el-option>
                  </el-select>
                </el-form-item>

                <!-- 流程选择 -->
                <el-form-item v-if="workflowsSorted.length > 0" label="分析流程">
                  <div style="display: flex; align-items: center; width: 100%;">
                    <el-select
                      :key="`workflow-select-${batchForm.market}`"
                      v-model="selectedWorkflowId"
                      size="small"
                      style="flex: 1;"
                      placeholder="选择分析流程"
                    >
                      <el-option
                        v-for="workflow in workflowsSorted"
                        :key="workflow.id"
                        :label="`${workflow.name} v${workflow.version}`"
                        :value="workflow.id"
                      />
                    </el-select>
                    <el-tooltip content="选择不同的分析流程，系统会使用该流程对应的智能体和步骤进行批量分析" placement="top">
                      <el-icon style="margin-left: 8px; color: #909399; cursor: help;"><InfoFilled /></el-icon>
                    </el-tooltip>
                  </div>
                </el-form-item>

                <!-- 分析引擎选择 - 已隐藏，默认使用 v2.0 引擎 -->
                <!-- 旧版引擎已移除，统一使用 v2.0 工作流引擎 -->
              </div>

              <!-- 分析师选择 -->
              <div class="form-section">
                <h4 class="section-title">👥 分析师团队</h4>
                <div class="analysts-selection">
                  <el-checkbox-group v-model="batchForm.analysts" class="analysts-group">
                    <div
                    v-for="analyst in availableAnalysts"
                    :key="analyst.id"
                    class="analyst-option"
                  >
                      <el-checkbox :label="analyst.name" class="analyst-checkbox">
                        <div class="analyst-info">
                          <span class="analyst-name">{{ analyst.name }}</span>
                          <span class="analyst-desc">{{ analyst.description }}</span>
                        </div>
                      </el-checkbox>
                    </div>
                  </el-checkbox-group>
                </div>
              </div>

              <!-- 操作按钮 -->
              <div class="form-section">
                <div class="action-buttons" style="display: flex; justify-content: center; align-items: center; width: 100%; text-align: center;">
                  <el-button
                    type="primary"
                    size="large"
                    @click="submitBatchAnalysis"
                    :loading="submitting"
                    :disabled="stockCodes.length === 0"
                    class="submit-btn large-batch-btn"
                    style="width: 320px; height: 56px; font-size: 18px; font-weight: 700; border-radius: 16px;"
                  >
                    <el-icon><TrendCharts /></el-icon>
                    开始批量分析 ({{ stockCodes.length }}只)
                  </el-button>
                </div>
              </div>
            </el-form>
          </el-card>
        </el-col>

        <!-- 右侧：高级配置 -->
        <el-col :span="6">
          <el-card class="advanced-config-card" shadow="hover">
            <template #header>
              <div class="card-header">
                <h3>🔧 高级配置</h3>
              </div>
            </template>

            <div class="config-content">
              <!-- AI模型配置组件 -->
              <ModelConfig
                v-model:quick-analysis-model="modelSettings.quickAnalysisModel"
                v-model:deep-analysis-model="modelSettings.deepAnalysisModel"
                :available-models="availableModels"
                :analysis-depth="batchForm.depth"
              />

              <!-- 分析选项 - 已隐藏，流程内置 -->
              <!-- <div class="config-section">
                <h4 class="config-title">⚙️ 分析选项</h4>
                <div class="analysis-options">
                  <div class="option-item">
                    <el-switch v-model="batchForm.includeSentiment" />
                    <div class="option-content">
                      <div class="option-name">情绪分析</div>
                      <div class="option-desc">分析市场情绪和投资者心理</div>
                    </div>
                  </div>

                  <div class="option-item">
                    <el-switch v-model="batchForm.includeRisk" />
                    <div class="option-content">
                      <div class="option-name">风险评估</div>
                      <div class="option-desc">包含详细的风险因素分析</div>
                    </div>
                  </div>

                  <div class="option-item">
                    <el-select v-model="batchForm.language" size="small" style="width: 120px; flex-shrink: 0;">
                      <el-option label="中文" value="zh-CN" />
                      <el-option label="English" value="en-US" />
                    </el-select>
                    <div class="option-content">
                      <div class="option-name">语言偏好</div>
                    </div>
                  </div>
                </div>
              </div> -->
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 股票预览 -->
    <el-card v-if="stockCodes.length > 0" class="stock-preview-card" shadow="never">
      <template #header>
        <div class="card-header">
          <h3>股票预览 ({{ stockCodes.length }}只)</h3>
          <el-button type="text" @click="validateStocks">
            <el-icon><Check /></el-icon>
            验证股票代码
          </el-button>
        </div>
      </template>

      <div class="stock-grid">
        <div
          v-for="(code, index) in stockCodes"
          :key="index"
          class="stock-item"
          :class="{ invalid: invalidCodes.includes(code) }"
        >
          <span class="stock-code">{{ code }}</span>
          <el-button
            type="text"
            size="small"
            @click="removeStock(index)"
            class="remove-btn"
          >
            <el-icon><Close /></el-icon>
          </el-button>
        </div>
      </div>

      <div v-if="invalidCodes.length > 0" class="invalid-notice">
        <el-alert
          title="发现无效股票代码"
          type="warning"
          :description="`以下股票代码可能无效：${invalidCodes.join(', ')}`"
          show-icon
          :closable="false"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Files, TrendCharts, Check, Close, InfoFilled } from '@element-plus/icons-vue'
import { ANALYSTS, DEFAULT_ANALYSTS, convertAnalystNamesToIds } from '@/constants/analysts'
import { configApi } from '@/api/config'
import { workflowApi, type WorkflowSummary } from '@/api/workflow'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import ModelConfig from '@/components/ModelConfig.vue'
import { resolveModelSelection } from '@/utils/modelSelection'
import { validateStockCode } from '@/utils/stockValidator'
import { isJdyunMode, JDYUN_CHAT_MODELS, loadJdyunChatModels } from '@/utils/config'

// 路由实例（必须在顶层调用）
const router = useRouter()
const route = useRoute()

const submitting = ref(false)
const stockInput = ref('')
const stockCodes = ref<string[]>([])  // 保留用于表单绑定
const symbols = ref<string[]>([])     // 标准化后的代码列表
const invalidCodes = ref<string[]>([])

// 模型设置
const modelSettings = ref({
  quickAnalysisModel: 'qwen-turbo',
  deepAnalysisModel: 'qwen-max'
})

// 流程选择
const workflows = ref<WorkflowSummary[]>([])
const selectedWorkflowId = ref<string>('')

// 输入框提示文本
const stockPlaceholder = '请输入股票代码，每行一个\n支持格式：\n000001\n000002.SZ\n600036.SH'
const etfPlaceholder = '请输入ETF代码，每行一个\n支持格式：\n510050\n510300.SH\n159919.SZ'

const ETF_ANALYST_NAMES = ['ETF分析师', '市场分析师', '新闻分析师']

const normalizeSelectedAnalystsForMarket = (market: string, analysts: string[]) => {
  if (market === 'ETF') {
    return [...ETF_ANALYST_NAMES]
  }

  const disallowedAnalysts = ['ETF分析师']
  return analysts.filter(name => !disallowedAnalysts.includes(name))
}

// 根据市场类型过滤可用的分析师
const availableAnalysts = computed(() => {
  const isETF = batchForm.market === 'ETF'
  const etfAnalystIds = ['etf', 'market', 'news']

  return ANALYSTS.filter(analyst => {
    if (isETF) return etfAnalystIds.includes(analyst.id)
    if (analyst.id === 'etf') return false
    return true
  })
})

const parseVersion = (v: string): number[] => {
  const parts = String(v || '0.0.0').split('.')
  return parts.map(p => parseInt(p, 10) || 0)
}

const workflowsSorted = computed(() => {
  const expectedType = batchForm.market === 'ETF' ? 'etf_analysis' : 'stock_analysis'
  const arr = workflows.value.filter(
    (w: WorkflowSummary) => w.workflow_type === expectedType
  )
  arr.sort((a, b) => {
    const vA = a.version || ''
    const vB = b.version || ''
    const verA = parseVersion(vA)
    const verB = parseVersion(vB)
    for (let i = 0; i < Math.max(verA.length, verB.length); i++) {
      const numA = verA[i] || 0
      const numB = verB[i] || 0
      if (numA !== numB) return numB - numA
    }
    return 0
  })
  return arr
})

// 可用的模型列表（从配置中获取）
const availableModels = ref<any[]>([])

const batchForm = reactive({
  title: '',
  description: '',
  market: 'A股' as 'A股' | 'ETF',  // 市场类型
  depth: '3',  // 默认3级标准分析，将在 onMounted 中从用户偏好加载
  analysts: [...DEFAULT_ANALYSTS],  // 将在 onMounted 中从用户偏好加载
  includeSentiment: true,
  includeRisk: true,
  language: 'zh-CN',
  engine: 'v2' as 'legacy' | 'v2'  // 默认使用 v2.0 引擎（推荐）
})

// 监听市场类型变化，自动切换到对应类型的默认流程
watch(
  () => batchForm.market,
  (newMarket) => {
    const expectedType = newMarket === 'ETF' ? 'etf_analysis' : 'stock_analysis'
    const targetWorkflows = workflows.value.filter(w => w.workflow_type === expectedType)
    
    if (targetWorkflows.length > 0) {
      const defaultWf = targetWorkflows.find(w => w.is_default)
      selectedWorkflowId.value = defaultWf ? defaultWf.id : targetWorkflows[0].id
    }

    // 调整选中的分析师列表，适配新的市场
    batchForm.analysts = normalizeSelectedAnalystsForMarket(newMarket, batchForm.analysts)
  }
)

// 使用通用校验器规范化代码，自动识别市场
const normalizeCodeSmart = (raw: string): { symbol?: string; error?: string } => {
  const code = String(raw || '').trim()
  if (!code) return { error: '空代码' }

  // 自动识别市场
  const v = validateStockCode(code)
  if (v.valid && v.normalizedCode) return { symbol: v.normalizedCode }

  return { error: v.message || '代码格式无效' }
}

const parseStockCodes = () => {
  const codes = stockInput.value
    .split('\n')
    .map(code => code.trim())
    .filter(code => code.length > 0)
    .filter((code, index, arr) => arr.indexOf(code) === index) // 去重

  const normalized: string[] = []
  const invalid: string[] = []
  for (const c of codes) {
    const { symbol } = normalizeCodeSmart(c)
    if (symbol) normalized.push(symbol)
    else invalid.push(c)
  }

  stockCodes.value = normalized
  symbols.value = [...normalized]
  invalidCodes.value = invalid
}

const clearStocks = () => {
  stockInput.value = ''
  stockCodes.value = []
  symbols.value = []
  invalidCodes.value = []
}

// 初始化模型设置
const initializeModelSettings = async () => {
  try {
    console.log('🔍 [批量分析] 开始加载模型配置...')

    // 🔥 京东云模式：先从后端加载可用模型列表，覆盖默认值
    await loadJdyunChatModels()

    // 获取所有可用的模型列表
    const llmConfigs = await configApi.getLLMConfigs()
    let enabledModels = llmConfigs.filter((config: any) => config.enabled)

    // 🔧 京东云模式：仅保留预置的 4 个模型
    if (isJdyunMode()) {
      const jdyunModelSet = new Set<string>(JDYUN_CHAT_MODELS)
      enabledModels = enabledModels.filter((m: any) => jdyunModelSet.has(m.model_name))
      if (enabledModels.length === 0) {
        enabledModels = JDYUN_CHAT_MODELS.map(name => ({
          model_name: name,
          model_display_name: name,
          provider: 'jdyun',
          enabled: true
        })) as any
      }
    }
    availableModels.value = enabledModels

    // 获取默认模型
    const defaultModels = await configApi.getDefaultModels()
    console.log('🔍 [批量分析] 从API获取的默认模型:', defaultModels)

    modelSettings.value.quickAnalysisModel = resolveModelSelection(
      defaultModels.quick_analysis_model,
      availableModels.value,
      defaultModels.default_provider
    )
    modelSettings.value.deepAnalysisModel = resolveModelSelection(
      defaultModels.deep_analysis_model,
      availableModels.value,
      defaultModels.default_provider
    )

    // 🔧 京东云模式：若解析后的默认模型不在白名单内，回退到第一个可用模型
    if (isJdyunMode()) {
      const jdyunModelSet = new Set<string>(JDYUN_CHAT_MODELS)
      if (!jdyunModelSet.has(modelSettings.value.quickAnalysisModel)) {
        modelSettings.value.quickAnalysisModel = availableModels.value[0]?.model_name || JDYUN_CHAT_MODELS[0]
      }
      if (!jdyunModelSet.has(modelSettings.value.deepAnalysisModel)) {
        modelSettings.value.deepAnalysisModel = availableModels.value[0]?.model_name || JDYUN_CHAT_MODELS[0]
      }
    }

    console.log('✅ [批量分析] 加载模型配置成功:', {
      quick: modelSettings.value.quickAnalysisModel,
      deep: modelSettings.value.deepAnalysisModel,
      available: availableModels.value.length,
      availableModels: availableModels.value.map(m => m.model_name),
      jdyunMode: isJdyunMode()
    })
  } catch (error) {
    console.error('❌ [批量分析] 加载默认模型配置失败:', error)
    if (isJdyunMode()) {
      // 京东云模式兜底
      availableModels.value = JDYUN_CHAT_MODELS.map(name => ({
        model_name: name,
        model_display_name: name,
        provider: 'jdyun',
        enabled: true
      })) as any
      modelSettings.value.quickAnalysisModel = JDYUN_CHAT_MODELS[0]
      modelSettings.value.deepAnalysisModel = JDYUN_CHAT_MODELS[0]
    } else {
      // 使用硬编码的默认值
      modelSettings.value.quickAnalysisModel = resolveModelSelection('qwen-turbo', availableModels.value)
      modelSettings.value.deepAnalysisModel = resolveModelSelection('qwen-max', availableModels.value)
    }
    console.log('🔄 [批量分析] 使用兜底默认值:', {
      quick: modelSettings.value.quickAnalysisModel,
      deep: modelSettings.value.deepAnalysisModel
    })
  }
}

// 页面初始化
onMounted(async () => {
  await initializeModelSettings()

  // 🆕 从用户偏好加载默认设置
  const authStore = useAuthStore()
  const userPrefs = authStore.user?.preferences

  console.log('🔍 [批量分析] 调试信息:', {
    hasUser: !!authStore.user,
    hasPreferences: !!userPrefs,
    userPrefs: userPrefs,
    currentDepth: batchForm.depth,
    currentModel: modelSettings.value.quickAnalysisModel
  })

  if (userPrefs) {
    // 加载默认分析深度（需要转换为数字字符串）
    if (userPrefs.default_depth) {
      // 将中文深度转换为数字字符串
      const depthValue = convertDepthToNumber(userPrefs.default_depth)
      console.log('🔍 [批量分析] 深度转换:', userPrefs.default_depth, '->', depthValue)
      batchForm.depth = depthValue
    } else {
      console.log('⚠️ [批量分析] 用户偏好中没有 default_depth')
    }

    // 加载默认分析师
    if (userPrefs.default_analysts && userPrefs.default_analysts.length > 0) {
      batchForm.analysts = [...userPrefs.default_analysts]
    } else {
      console.log('⚠️ [批量分析] 用户偏好中没有 default_analysts')
    }

    console.log('✅ 批量分析已加载用户偏好设置:', {
      depth: batchForm.depth,
      analysts: batchForm.analysts
    })
  } else {
    console.log('⚠️ [批量分析] 没有找到用户偏好设置')
  }

  // 读取路由查询参数以便从筛选页预填充（路由参数优先级最高）
  const q = route.query as any
  if (q?.stocks) {
    const parts = String(q.stocks).split(',').map((s) => s.trim()).filter(Boolean)
    stockCodes.value = parts
    stockInput.value = parts.join('\n')
    // 触发解析以更新 symbols
    parseStockCodes()
  }

  // 加载可用工作流
  try {
    const data = await workflowApi.listAll()
    workflows.value = data
    const targetWorkflows = data.filter(w => w.workflow_type === 'stock_analysis')
    if (targetWorkflows.length > 0) {
      const defaultWf = targetWorkflows.find(w => w.is_default)
      selectedWorkflowId.value = defaultWf ? defaultWf.id : targetWorkflows[0].id
    }
  } catch (e) {
    console.error('加载工作流列表失败:', e)
  }
})

const removeStock = (index: number) => {
  const removedCode = stockCodes.value[index]
  stockCodes.value.splice(index, 1)
  
  // 更新输入框
  stockInput.value = stockCodes.value.join('\n')
  
  // 从无效列表中移除
  const invalidIndex = invalidCodes.value.indexOf(removedCode)
  if (invalidIndex > -1) {
    invalidCodes.value.splice(invalidIndex, 1)
  }
}

const validateStocks = async () => {
  // 按当前市场重新规范化并验证
  const invalid: string[] = []
  const valid: string[] = []
  for (const c of stockCodes.value) {
    const { symbol } = normalizeCodeSmart(c)
    if (symbol) valid.push(symbol)
    else invalid.push(c)
  }
  stockCodes.value = valid
  symbols.value = [...valid]
  invalidCodes.value = invalid

  if (invalid.length === 0) {
    ElMessage.success('所有股票代码验证通过')
  } else {
    ElMessage.warning(`发现 ${invalid.length} 个无效股票代码`)
  }
}

const submitBatchAnalysis = async () => {
  if (stockCodes.value.length === 0) {
    ElMessage.warning('请输入股票代码')
    return
  }

  if (stockCodes.value.length > 10) {
    ElMessage.warning('单次批量分析最多支持10只股票，请减少股票数量')
    return
  }

  try {
    // 🔥 固定使用 v2.0 引擎
    await ElMessageBox.confirm(
      `确定要提交批量分析任务吗？\n市场：${batchForm.market}\n数量：${stockCodes.value.length}只\n分析引擎：v2.0引擎`,
      '确认提交',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'info'
      }
    )

    submitting.value = true

    // 准备批量分析请求参数（真实API调用）
    const batchRequest: Parameters<typeof analysisApi.startBatchAnalysis>[0] = {
      title: '',  // 基础信息已移除，不再使用
      description: '',  // 基础信息已移除，不再使用
      symbols: symbols.value,
      stock_codes: symbols.value,  // 兼容字段
      parameters: {
        // 使用用户选择的市场类型
        market_type: batchForm.market === 'ETF' ? 'ETF' : 'A股',
        research_depth: getDepthDescription(Number.parseInt(batchForm.depth)),  // 转换为中文
        selected_analysts: convertAnalystNamesToIds(batchForm.analysts),
        include_sentiment: batchForm.includeSentiment,
        include_risk: batchForm.includeRisk,
        language: batchForm.language,
        quick_analysis_model: modelSettings.value.quickAnalysisModel,
        deep_analysis_model: modelSettings.value.deepAnalysisModel,
        engine: 'v2',  // 🔥 固定使用 v2.0 引擎（旧版引擎已隐藏）
        workflow_id: selectedWorkflowId.value || undefined
      }
    }

    // 调用真实的批量分析API
    const { analysisApi } = await import('@/api/analysis')
    const response = await analysisApi.startBatchAnalysis(batchRequest)

    if (!response?.success) {
      throw new Error(response?.message || '批量分析提交失败')
    }

    const { batch_id, total_tasks } = response.data

    // 显示成功提示并引导用户去任务中心
    ElMessageBox.confirm(
      `✅ 批量分析任务已成功提交！\n\n📊 股票数量：${total_tasks}只\n📋 批次ID：${batch_id}\n\n任务正在后台执行中，最多同时执行3个任务，其他任务会自动排队等待。\n\n是否前往任务中心查看进度？`,
      '提交成功',
      {
        confirmButtonText: '前往任务中心',
        cancelButtonText: '留在当前页面',
        type: 'success',
        distinguishCancelAndClose: true,
        closeOnClickModal: false
      }
    ).then(() => {
      // 用户点击"前往任务中心"
      router.push({ path: '/tasks/unified', query: { batch_id } })
    }).catch((action) => {
      // 用户点击"留在当前页面"或关闭对话框
      if (action === 'cancel') {
        ElMessage.info('任务正在后台执行，您可以随时前往任务中心查看进度')
      }
    })

  } catch (error: any) {
    // 处理错误
    if (error !== 'cancel') {
      ElMessage.error(error.message || '批量分析提交失败')
    }
  } finally {
    submitting.value = false
  }
}

// 将数字深度转换为中文描述（与后端保持一致）
const getDepthDescription = (depth: number) => {
  const descriptions = ['快速', '基础', '标准', '深度', '全面']
  return descriptions[depth - 1] || '标准'
}

// 将深度值（可能是数字字符串或中文）转换为数字字符串
const convertDepthToNumber = (depth: string): string => {
  // 如果已经是数字字符串（1-5），直接返回
  if (/^[1-5]$/.test(depth)) {
    return depth
  }

  // 中文到数字的映射
  const chineseToNumber: Record<string, string> = {
    '快速': '1',
    '基础': '2',
    '标准': '3',
    '深度': '4',
    '全面': '5'
  }

  // 返回对应的数字字符串，如果找不到则返回默认值 '3'
  return chineseToNumber[depth] || '3'
}

</script>

<style lang="scss" scoped>
.batch-analysis {
  min-height: 100vh;
  background: var(--el-bg-color-page);
  padding: 24px;

  .page-header {
    margin-bottom: 32px;

    .header-content {
      background: var(--el-bg-color);
      padding: 32px;
      border-radius: 16px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
    }

    .title-section {
      .page-title {
        display: flex;
        align-items: center;
        font-size: 32px;
        font-weight: 700;
        color: #1a202c;
        margin: 0 0 12px 0;

        .title-icon {
          margin-right: 12px;
          color: #3b82f6;
        }
      }

      .risk-disclaimer {
        margin: 0 0 12px 0;
      }

      .page-description {
        font-size: 16px;
        color: #64748b;
        margin: 0;
      }
    }
  }

  .analysis-container {
    .stock-list-card, .config-card {
      border-radius: 16px;
      border: none;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);

      :deep(.el-card__header) {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 16px 16px 0 0;
        padding: 20px 24px;

        .card-header {
          display: flex;
          justify-content: space-between;
          align-items: center;

          h3 {
            margin: 0;
            font-size: 18px;
            font-weight: 600;
          }
        }
      }

      :deep(.el-card__body) {
        padding: 24px;
      }
    }

    // 右侧高级配置卡片样式
    .advanced-config-card {
      border-radius: 16px;
      border: none;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);

      :deep(.el-card__header) {
        background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
        color: white;
        border-radius: 16px 16px 0 0;
        padding: 20px 24px;

        .card-header {
          display: flex;
          justify-content: space-between;
          align-items: center;

          h3 {
            margin: 0;
            font-size: 18px;
            font-weight: 600;
          }
        }
      }

      :deep(.el-card__body) {
        padding: 24px;
      }

      .config-content {
        .config-section {
          margin-bottom: 24px;

          &:last-child {
            margin-bottom: 0;
          }

          .analysis-options {
            .option-item {
              display: flex;
              align-items: flex-start;
              gap: 12px;
              padding: 12px 0;
              border-bottom: 1px solid #f3f4f6;

              &:last-child {
                border-bottom: none;
                padding-bottom: 0;
              }

              .option-content {
                flex: 1;
                min-width: 0;  // 防止flex子元素溢出

                .option-name {
                  font-size: 14px;
                  font-weight: 500;
                  color: #374151;
                  margin-bottom: 2px;
                  white-space: nowrap;  // 防止文字换行
                }

                .option-desc {
                  font-size: 12px;
                  color: #6b7280;
                }
              }
            }
          }
        }
      }
    }

    .stock-input-section {
      .input-area {
        margin-bottom: 24px;

        .stock-textarea {
          :deep(.el-textarea__inner) {
            border-radius: 12px;
            border: 2px solid #e2e8f0;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            font-size: 14px;
            line-height: 1.6;

            &:focus {
              border-color: #3b82f6;
              box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
            }
          }
        }

        .input-actions {
          margin-top: 12px;
          display: flex;
          gap: 12px;
        }
      }

      .stock-preview {
        h4 {
          font-size: 16px;
          font-weight: 600;
          color: #1a202c;
          margin: 0 0 12px 0;
        }

        .stock-tags {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;

          .stock-tag {
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            font-weight: 600;
          }
        }
      }

      .invalid-codes {
        margin-top: 16px;

        .invalid-list {
          margin-top: 8px;
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
        }
      }
    }

    .batch-form {
      .form-section {
        margin-bottom: 32px;

        .section-title {
          font-size: 16px;
          font-weight: 600;
          color: #1a202c;
          margin: 0 0 16px 0;
          padding-bottom: 8px;
          border-bottom: 2px solid #e2e8f0;
        }
      }

      .analysts-selection {
        .analysts-group {
          display: flex;
          flex-direction: column;
          gap: 12px;

          .analyst-option {
            .analyst-checkbox {
              width: 100%;

              :deep(.el-checkbox__label) {
                width: 100%;
              }

              :deep(.el-checkbox__input.is-checked .el-checkbox__inner) {
                background-color: #3b82f6;
                border-color: #3b82f6;
              }

              :deep(.el-checkbox__input.is-checked + .el-checkbox__label) {
                color: #3b82f6;
              }

              .analyst-info {
                display: flex;
                flex-direction: column;
                gap: 4px;

                .analyst-name {
                  font-weight: 500;
                  color: #374151;
                }

                .analyst-desc {
                  font-size: 12px;
                  color: #6b7280;
                }
              }
            }
          }
        }
      }
    }

    .action-section {
      margin-top: 24px !important;
      display: flex !important;
      justify-content: center !important;
      align-items: center !important;
      width: 100% !important;
      text-align: center !important;

      .submit-btn.el-button {
        width: 320px !important;
        height: 56px !important;
        font-size: 18px !important;
        font-weight: 700 !important;
        background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
        border: none !important;
        border-radius: 16px !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 15px rgba(59, 130, 246, 0.2) !important;
        min-width: 320px !important;
        max-width: 320px !important;

        &:hover {
          transform: translateY(-3px) !important;
          box-shadow: 0 12px 30px rgba(59, 130, 246, 0.4) !important;
          background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
        }

        &:disabled {
          opacity: 0.6 !important;
          transform: none !important;
          box-shadow: 0 4px 15px rgba(59, 130, 246, 0.1) !important;
        }

        .el-icon {
          margin-right: 8px !important;
          font-size: 20px !important;
        }

        span {
          font-size: 18px !important;
          font-weight: 700 !important;
        }
      }
    }
  }
}
</style>

<style>
/* 全局样式确保按钮样式生效 */
.action-section {
  display: flex !important;
  justify-content: center !important;
  align-items: center !important;
  width: 100% !important;
  text-align: center !important;
}

.large-batch-btn.el-button {
  width: 320px !important;
  height: 56px !important;
  font-size: 18px !important;
  font-weight: 700 !important;
  background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
  border: none !important;
  border-radius: 16px !important;
  transition: all 0.3s ease !important;
  box-shadow: 0 4px 15px rgba(59, 130, 246, 0.2) !important;
  min-width: 320px !important;
  max-width: 320px !important;
}

.large-batch-btn.el-button:hover {
  transform: translateY(-3px) !important;
  box-shadow: 0 12px 30px rgba(59, 130, 246, 0.4) !important;
  background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
}

.large-batch-btn.el-button:disabled {
  opacity: 0.6 !important;
  transform: none !important;
  box-shadow: 0 4px 15px rgba(59, 130, 246, 0.1) !important;
}

.large-batch-btn.el-button .el-icon {
  margin-right: 8px !important;
  font-size: 20px !important;
}

.large-batch-btn.el-button span {
  font-size: 18px !important;
  font-weight: 700 !important;
}

/* 风险提示样式 */
.title-section .risk-disclaimer {
  margin-bottom: 12px;
  margin-top: 0;
}

.risk-disclaimer :deep(.el-alert) {
  background: linear-gradient(135deg, #fff3cd 0%, #ffe69c 100%);
  border: 2px solid #ffc107;
  border-radius: 12px;
  padding: 16px 20px;
  box-shadow: 0 4px 12px rgba(255, 193, 7, 0.2);
}

.risk-disclaimer :deep(.el-alert__icon) {
  font-size: 24px;
  color: #ff6b00;
}
</style>
