<template>
  <el-dialog
    v-model="visible"
    width="1000px"
    :close-on-click-modal="false"
  >
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
        <span>{{ isEtfPosition ? 'ETF持仓分析' : '单股持仓分析' }}</span>
        <el-button
          type="primary"
          size="small"
          link
          @click="showHistoryDialog = true"
          style="margin-right: 40px;"
        >
          <el-icon><Clock /></el-icon>
          历史记录
        </el-button>
      </div>
    </template>

    <!-- 持仓信息展示 -->
    <div v-if="position" class="position-info">
      <el-descriptions :column="2" border>
        <el-descriptions-item :label="securityCodeLabel">{{ position.code }}</el-descriptions-item>
        <el-descriptions-item :label="securityNameLabel">{{ position.name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="持仓数量">{{ position.quantity }} 股</el-descriptions-item>
        <el-descriptions-item label="成本价">¥{{ position.cost_price.toFixed(2) }}</el-descriptions-item>
        <el-descriptions-item label="当前价">¥{{ position.current_price?.toFixed(2) || '-' }}</el-descriptions-item>
        <el-descriptions-item label="持仓市值">¥{{ position.market_value?.toFixed(2) || '-' }}</el-descriptions-item>
        <el-descriptions-item label="浮动盈亏">
          <span :class="(position.unrealized_pnl || 0) >= 0 ? 'profit' : 'loss'">
            {{ (position.unrealized_pnl || 0) >= 0 ? '+' : '' }}{{ position.unrealized_pnl?.toFixed(2) || '0.00' }}
            ({{ (position.unrealized_pnl_pct || 0) >= 0 ? '+' : '' }}{{ position.unrealized_pnl_pct?.toFixed(2) || '0.00' }}%)
          </span>
        </el-descriptions-item>
        <el-descriptions-item :label="industryLabel">{{ industryValue }}</el-descriptions-item>
      </el-descriptions>
    </div>

    <!-- 分析状态提示 -->
    <div v-if="analysisStatus === 'pending' || analysisStatus === 'processing'" class="analysis-status">
      <el-alert type="info" :closable="false">
        <template #title>
          <el-icon class="is-loading"><Loading /></el-icon>
          {{ analysisStatus === 'pending' ? '分析任务已提交' : '正在分析中' }}...
        </template>
        <template #default>
          <p>预计需要2-5分钟完成，您可以：</p>
          <ul>
            <li>点击下方"手动刷新状态"按钮查看最新进度</li>
            <li>或关闭对话框稍后再来查看（重新打开对话框即可查看结果）</li>
          </ul>
          <el-button
            type="primary"
            size="small"
            :loading="refreshing"
            @click="manualRefreshStatus"
            style="margin-top: 12px;"
          >
            <el-icon v-if="!refreshing"><Refresh /></el-icon>
            {{ refreshing ? '刷新中...' : '手动刷新状态' }}
          </el-button>
        </template>
      </el-alert>
    </div>

    <!-- 分析参数设置 -->
    <div class="analysis-params" v-if="!analysisResult && analysisStatus !== 'pending' && analysisStatus !== 'processing'">
      <el-divider content-position="left">分析设置</el-divider>
      
      <!-- 流程选择 -->
      <div class="config-section" v-if="workflowsSorted.length > 0">
        <el-form-item label="分析流程">
          <div style="display: flex; align-items: center; width: 100%;">
            <el-select
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
            <el-tooltip content="选择不同的分析流程，系统会使用该流程对应的智能体和步骤进行分析" placement="top">
              <el-icon style="margin-left: 8px; color: #909399; cursor: help;"><InfoFilled /></el-icon>
            </el-tooltip>
          </div>
        </el-form-item>
      </div>
      
      <el-form :model="params" label-width="120px">
        <el-form-item label="目标收益率">
          <el-input-number v-model="params.target_profit_pct" :min="5" :max="100" :step="5" />
          <span class="unit">%</span>
        </el-form-item>
        <el-form-item label="分析增持观点">
          <el-switch v-model="params.include_add_position" />
        </el-form-item>

        <el-divider content-position="left">
          <el-checkbox v-model="enableCapitalAnalysis">启用资金风险分析</el-checkbox>
        </el-divider>

        <template v-if="enableCapitalAnalysis">
          <el-alert
            v-if="hasAccountCapital"
            type="success"
            :closable="false"
            style="margin-bottom: 12px"
          >
            已从资金账户自动获取数据，总投资资金: ¥{{ (accountSummary?.net_capital?.CNY || 0).toLocaleString() }}
          </el-alert>
          <el-alert
            v-else
            type="info"
            :closable="false"
            style="margin-bottom: 12px"
          >
            未设置资金账户，请手动输入资金总量或前往持仓页面设置资金账户
          </el-alert>
          <el-form-item label="投资资金总量">
            <el-input-number
              v-model="params.total_capital"
              :min="10000"
              :max="100000000"
              :step="10000"
              :precision="0"
              :controls="false"
              style="width: 200px"
            />
            <span class="unit">元</span>
            <span class="tip" v-if="!hasAccountCapital">用于计算仓位占比和风险敞口</span>
          </el-form-item>
          <el-form-item label="单股最大仓位">
            <el-input-number v-model="params.max_position_pct" :min="5" :max="100" :step="5" />
            <span class="unit">%</span>
          </el-form-item>
          <el-form-item label="最大亏损容忍">
            <el-input-number v-model="params.max_loss_pct" :min="1" :max="50" :step="1" />
            <span class="unit">%</span>
          </el-form-item>
        </template>
      </el-form>
    </div>

    <!-- 分析失败提示 -->
    <div v-if="analysisResult && analysisResult.status === 'failed'" class="analysis-failed">
      <el-alert type="error" :closable="false">
        <template #title>分析失败</template>
        <template #default>
          <p>{{ formatErrorMessage(analysisResult.error_message, '分析过程中出现错误，请稍后重试') }}</p>
          <el-button type="primary" size="small" @click="resetAnalysis" style="margin-top: 10px">
            重新分析
          </el-button>
        </template>
      </el-alert>
    </div>

    <!-- AI连接错误提示 -->
    <div v-else-if="analysisResult && isAIConnectionError" class="analysis-error">
      <el-alert type="warning" :closable="false">
        <template #title>AI服务连接异常</template>
        <template #default>
          <p>{{ analysisResult.action_reason }}</p>
          <p style="margin-top: 8px; color: #909399; font-size: 12px">
            💡 请检查：1. 网络连接是否正常；2. API Key 是否已配置；3. API 服务是否可用
          </p>
          <el-button type="primary" size="small" @click="resetAnalysis" style="margin-top: 10px">
            重新分析
          </el-button>
        </template>
      </el-alert>
    </div>

    <!-- 分析结果展示 -->
    <div v-else-if="analysisResult" class="analysis-result">
      <!-- 风险提示 -->
      <div class="risk-disclaimer">
        <el-alert
          type="warning"
          :closable="false"
          show-icon
        >
          <template #title>
            <div class="disclaimer-content">
              <el-icon class="disclaimer-icon"><WarningFilled /></el-icon>
              <div class="disclaimer-text">
                <p style="margin: 0 0 8px 0;"><strong>⚠️ 重要风险提示与免责声明</strong></p>
                <ul style="margin: 0; padding-left: 20px; line-height: 1.8;">
                  <li><strong>平台性质：</strong>本平台为AI辅助分析技术学习平台，专注于AI技术在证券与ETF分析领域的应用验证和技术学习。</li>
                  <li><strong>分析目的：</strong>所有分析结论仅用于学习和验证AI辅助分析技术，不作为真实交易操盘指导或投资依据。</li>
                  <li><strong>非投资建议：</strong>所有分析结果、评分、建议仅为技术验证参考，不构成任何买卖建议或投资决策依据。</li>
                  <li><strong>数据局限性：</strong>分析基于历史数据和公开信息，可能存在延迟、不完整或不准确的情况，无法预测未来市场走势。</li>
                  <li><strong>投资风险：</strong>股票与ETF投资均存在市场风险、流动性风险、政策风险等多种风险，可能导致本金损失。</li>
                  <li><strong>独立决策：</strong>投资者应基于自身风险承受能力、投资目标和财务状况独立做出投资决策。</li>
                  <li><strong>责任声明：</strong>使用本平台产生的任何投资决策及其后果由使用者自行承担，本平台不承担任何责任。</li>
                </ul>
              </div>
            </div>
          </template>
        </el-alert>
      </div>

      <el-divider content-position="left">分析结果</el-divider>

      <!-- 当前结论 -->
      <div class="overview-panel">
        <div class="overview-header">
          <h3>当前结论</h3>
          <div class="conclusion-content markdown-content" v-html="renderMarkdown(userView.conclusion || '暂无结论')"></div>
        </div>
        <div class="context-chip" v-if="userView.position_context">
          {{ userView.position_context }}
        </div>
      </div>

      <div class="uncertainty-card" v-if="userView.uncertainty_note">
        <h4>不确定性说明</h4>
        <p>{{ userView.uncertainty_note }}</p>
      </div>

      <!-- 资金风险指标（如果启用） -->
      <div v-if="analysisResult.risk_metrics" class="risk-metrics-section">
        <h4><el-icon><WalletFilled /></el-icon> 仓位风险分析</h4>
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="仓位占比">
            <span :class="getRiskLevelClass(analysisResult.risk_metrics.risk_level)">
              {{ analysisResult.risk_metrics.position_pct?.toFixed(2) }}%
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="持仓市值">
            ¥{{ analysisResult.risk_metrics.position_value?.toLocaleString() }}
          </el-descriptions-item>
          <el-descriptions-item label="最大亏损金额">
            <span class="loss">¥{{ analysisResult.risk_metrics.max_loss_amount?.toLocaleString() }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="对总资金影响">
            <span class="loss">{{ analysisResult.risk_metrics.max_loss_impact_pct?.toFixed(2) }}%</span>
          </el-descriptions-item>
          <el-descriptions-item label="可增持金额">
            <span class="profit">¥{{ analysisResult.risk_metrics.available_add_amount?.toLocaleString() }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="风险等级">
            <el-tag :type="getRiskTagType(analysisResult.risk_metrics.risk_level)" size="small">
              {{ getRiskLevelText(analysisResult.risk_metrics.risk_level) }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>
        <p class="risk-summary">{{ analysisResult.risk_metrics.risk_summary }}</p>
      </div>

      <!-- 研究附录 -->
      <el-collapse>
        <el-collapse-item title="查看研究附录" name="detail">
          <template v-if="appendixSections.length > 0">
            <div
              v-for="section in appendixSections"
              :key="section.key"
              class="appendix-section"
            >
              <h4>{{ section.title }}</h4>
              <div class="detailed-analysis markdown-content" v-html="renderMarkdown(section.content)"></div>
            </div>
          </template>
          <div
            v-else
            class="detailed-analysis markdown-content"
            v-html="renderMarkdown(analysisResult.detailed_analysis || '暂无详细分析')"
          ></div>
        </el-collapse-item>
      </el-collapse>
    </div>

    <template #footer>
      <span class="dialog-footer">
        <el-button @click="visible = false">关闭</el-button>
        <el-button
          v-if="!analysisResult"
          type="primary"
          :loading="loading"
          @click="handleAnalyze"
        >
          开始分析
        </el-button>
        <el-button
          v-else
          type="primary"
          @click="resetAnalysis"
        >
          重新分析
        </el-button>
      </span>
    </template>

    <!-- 历史记录对话框 -->
    <PositionAnalysisHistoryDialog
      v-model="showHistoryDialog"
      :position="position"
    />
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { WarningFilled, WalletFilled, Loading, Refresh, Clock, InfoFilled } from '@element-plus/icons-vue'
import { portfolioApi, type PositionItem, type PositionAnalysisResult, type PositionAnalysisParams, type AccountSummary } from '@/api/portfolio'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { renderMarkdown as safeMarkdown } from '@/utils/markdown'
import { getMarketByStockCode } from '@/utils/market'
import { workflowApi, isSelectableAnalysisWorkflow, type WorkflowSummary } from '@/api/workflow'
import PositionAnalysisHistoryDialog from './PositionAnalysisHistoryDialog.vue'

// 配置marked选项
// marked 配置已由 @/utils/markdown 统一管理
// Markdown渲染函数（后端已经转换为Markdown格式，前端直接渲染）
const renderMarkdown = (content: string) => {
  if (!content) return ''
  
  try {
    return safeMarkdown(content)
  } catch (e) {
    return `<pre style="white-space: pre-wrap; font-family: inherit;">${content}</pre>`
  }
}

/**
 * 将后端/网络错误消息转换为用户可理解的友好中文提示。
 * 针对常见的限流、网络、超时等情况做了专门处理。
 */
const formatErrorMessage = (err: any, defaultMsg = '操作失败，请稍后重试'): string => {
  if (!err) return defaultMsg
  const msg = String(err?.message || err?.data?.message || err?.error_message || err || '').toLowerCase()

  // 限流类
  if (
    msg.includes('429') ||
    msg.includes('rate_limit') ||
    msg.includes('rate limit') ||
    msg.includes('tokens limit') ||
    msg.includes('rate_limited') ||
    msg.includes('访问限制') ||
    msg.includes('限流')
  ) {
    return '当前使用AI分析的人数较多，服务繁忙，请稍后再试。（提示：避免短时间内连续发起多次分析）'
  }

  // 网络/连接类
  if (
    msg.includes('network error') ||
    msg.includes('connection error') ||
    msg.includes('failed to fetch') ||
    msg.includes('连接失败') ||
    msg.includes('网络错误')
  ) {
    return '网络连接失败，请检查您的网络状态后重试。'
  }

  // 超时类
  if (msg.includes('timeout') || msg.includes('超时')) {
    return '请求超时，请稍后重试。若频繁出现，请联系管理员。'
  }

  // 余额/额度不足
  if (
    msg.includes('insufficient balance') ||
    msg.includes('quota') ||
    msg.includes('余额不足') ||
    msg.includes('额度不足')
  ) {
    return 'AI分析额度不足，请联系管理员补充额度后再试。'
  }

  // 认证/权限类
  if (msg.includes('401') || msg.includes('403') || msg.includes('unauthorized') || msg.includes('无权限')) {
    return '登录已过期，请刷新页面重新登录后再试。'
  }

  // 服务端错误
  if (msg.includes('500') || msg.includes('502') || msg.includes('503') || msg.includes('server error')) {
    return '服务器暂时不可用，请稍后重试。'
  }

  // 返回原始消息（如果是中文且可读，直接返回）
  const original = String(err?.message || err?.data?.message || err?.error_message || defaultMsg)
  if (/[\u4e00-\u9fa5]/.test(original) && original.length < 100) {
    return original
  }

  return defaultMsg
}

const props = defineProps<{
  modelValue: boolean
  position: PositionItem | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const router = useRouter()
const loading = ref(false)
const refreshing = ref(false)
const analysisResult = ref<PositionAnalysisResult | null>(null)
const enableCapitalAnalysis = ref(false)
const accountSummary = ref<AccountSummary | null>(null)
const showHistoryDialog = ref(false)

// 流程选择
const workflows = ref<WorkflowSummary[]>([])
const selectedWorkflowId = ref<string>('')

const parseVersion = (v: string): number[] => {
  const parts = String(v || '0.0.0').split('.')
  return parts.map(p => parseInt(p, 10) || 0)
}

const workflowsSorted = computed(() => {
  const arr = workflows.value.filter(
    (w: WorkflowSummary) => isSelectableAnalysisWorkflow(w, 'position_analysis')
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

// 异步分析相关状态
const analysisId = ref<string | null>(null)
const analysisStatus = ref<string>('idle')  // idle, pending, processing, completed, failed

const hasAccountCapital = computed(() => {
  const netCapital = accountSummary.value?.net_capital?.CNY || 0
  return netCapital > 0
})
const isEtfPosition = computed(() => {
  if (!props.position) return false
  return props.position.market === 'CN' && getMarketByStockCode(props.position.code) === 'ETF'
})
const securityCodeLabel = computed(() => isEtfPosition.value ? 'ETF代码' : '股票代码')
const securityNameLabel = computed(() => isEtfPosition.value ? 'ETF名称' : '股票名称')
const industryLabel = computed(() => isEtfPosition.value ? '产品分类' : '所属行业')
const industryValue = computed(() => {
  if (!props.position) return '-'
  return isEtfPosition.value ? 'ETF/基金' : (props.position.industry || '未知')
})
const params = ref<PositionAnalysisParams>({
  research_depth: '标准',
  include_add_position: true,
  target_profit_pct: 20,
  total_capital: 100000,    // 默认10万
  max_position_pct: 30,     // 默认30%
  max_loss_pct: 10          // 默认10%
})

// 加载资金账户信息
const loadAccountSummary = async () => {
  try {
    const res = await portfolioApi.getAccountSummary()
    if (res.success && res.data) {
      accountSummary.value = res.data
      // 如果有资金账户，自动启用资金分析并填充数据
      // 使用净入金（总投资资金）而不是总资产
      const netCapital = res.data.net_capital?.CNY || 0
      if (netCapital > 0) {
        enableCapitalAnalysis.value = true
        params.value.total_capital = netCapital
        params.value.max_position_pct = res.data.settings?.max_position_pct || 30
        params.value.max_loss_pct = res.data.settings?.max_loss_pct || 10
      }
    }
  } catch (e) {
    console.error('加载资金账户失败', e)
  }
}

// 重置状态
// 加载可用工作流
const loadWorkflows = async () => {
  try {
    const data = await workflowApi.listAll()
    workflows.value = data
    const targetWorkflows = workflowsSorted.value
    if (targetWorkflows.length > 0) {
      const defaultWf = targetWorkflows.find((w: WorkflowSummary) => w.is_default)
      selectedWorkflowId.value = defaultWf ? defaultWf.id : targetWorkflows[0].id
    }
  } catch (e) {
    console.error('加载工作流列表失败:', e)
  }
}

watch(visible, (val) => {
  if (val) {
    // 打开对话框时先重置状态，再加载数据
    // 重要：必须先清空之前的分析结果，避免显示其他股票的缓存数据
    analysisResult.value = null
    analysisId.value = null
    analysisStatus.value = 'idle'

    // 加载资金账户信息和已有分析报告
    loadAccountSummary()
    loadExistingAnalysis()
    loadWorkflows()
  }
})

// 不启用资金分析时清除相关参数
watch(enableCapitalAnalysis, (val) => {
  if (!val) {
    params.value.total_capital = undefined
  } else {
    // 恢复资金账户数据或默认值（使用净入金而非总资产）
    const netCapital = accountSummary.value?.net_capital?.CNY || 0
    params.value.total_capital = netCapital > 0 ? netCapital : 100000
  }
})

// 检查是否是AI连接错误
const isAIConnectionError = computed(() => {
  if (!analysisResult.value) return false
  const reason = analysisResult.value.action_reason || ''
  return reason.includes('AI服务') ||
         reason.includes('连接失败') ||
         reason.includes('Connection error') ||
         reason.includes('AI分析暂时不可用') ||
         (analysisResult.value.confidence === 0 && reason.includes('error'))
})

// 用户版展示内容（合规化后统一展示 user_view 字段）
const userView = computed(() => analysisResult.value?.user_view || {
  conclusion: analysisResult.value?.action_reason || '暂无结论',
  position_context: '',
  key_points: [] as string[],
  risk_focus: [] as string[],
  watch_items: [] as string[],
  uncertainty_note: ''
})

// 研究附录（仅展示有内容的分节）
const appendixSections = computed(() =>
  (analysisResult.value?.appendix_sections || []).filter(section => section?.content)
)

// 执行分析（异步模式）
const handleAnalyze = async () => {
  if (!props.position) return

  loading.value = true

  try {
    // 第一步：检查是否有单股分析报告缓存
    const cacheRes = await portfolioApi.checkStockAnalysisCache(
      props.position.code,
      props.position.market
    )

    if (cacheRes.success && cacheRes.data) {
      const hasCache = cacheRes.data.has_cache

      // 如果没有缓存，提示用户选择
      if (!hasCache) {
        loading.value = false
        try {
          await ElMessageBox.confirm(
            '当前没有可用的单股分析报告缓存。\n\n' +
            '建议先进行单股分析以获得更准确的持仓分析结果。\n\n' +
            '您可以选择：\n' +
            '• 继续分析：直接进行持仓分析（不使用单股分析报告）\n' +
            '• 先去单股分析：先跳转到单股分析页面进行分析',
            '提示：缺少单股分析报告',
            {
              confirmButtonText: '继续分析',
              cancelButtonText: '先去单股分析',
              type: 'warning',
              distinguishCancelAndClose: true
            }
          )
          // 用户选择"继续分析"，继续执行分析流程
        } catch (action: any) {
          // 用户选择"先去单股分析"或关闭对话框
          if (action === 'cancel') {
            // 跳转到单股分析页面，带上股票代码参数
            const marketName = props.position.market === 'CN'
              ? getMarketByStockCode(props.position.code)
              : 'A股'
            router.push(`/analysis/single?stock_code=${props.position.code}&market=${marketName}`)
            visible.value = false // 关闭当前对话框
          }
          return // 取消分析，不执行后续流程
        }
      } else {
        // 有缓存，可以显示缓存信息（可选）
        const ageMinutes = cacheRes.data.cache_age_minutes || 0
        const ageText = ageMinutes < 60 
          ? `${ageMinutes}分钟前` 
          : `${Math.floor(ageMinutes / 60)}小时前`
        console.log(`使用缓存报告（${ageText}）`)
      }
    }

    // 第二步：提交分析任务
    loading.value = true
    analysisStatus.value = 'pending'

    // 🔥 根据持仓来源设置 position_type：模拟持仓 -> simulated，用户持仓 -> real
    const positionType = props.position.source === 'paper' ? 'simulated' : 'real'
    const analysisParams = {
      ...params.value,
      position_type: positionType,
      workflow_id: selectedWorkflowId.value || undefined
    }

    const res = await portfolioApi.analyzePositionByCode(
      props.position.code,
      props.position.market,
      analysisParams
    )

    console.log('[开始分析] 收到响应:', res)
    if (res.success && res.data) {
      // 设置分析ID和状态
      analysisId.value = res.data.analysis_id || null
      analysisStatus.value = res.data.status || 'pending'
      
      console.log('[开始分析] 设置analysisId:', analysisId.value, 'status:', analysisStatus.value)

      if (res.data.status === 'completed' && analysisId.value) {
        // 已有完成的报告，直接获取结果
        await fetchAnalysisResult(analysisId.value)
        ElMessage.success('已有最近的分析报告')
      } else {
        // 任务已提交，不自动轮询，用户可手动刷新
        ElMessage.success(res.data.message || '分析任务已提交，预计需要2-5分钟，请稍后点击"手动刷新状态"查看结果')
      }
    } else {
      ElMessage.error(formatErrorMessage(res.message, '提交分析任务失败'))
      analysisStatus.value = 'failed'
    }
  } catch (error: any) {
    // 如果是MessageBox的取消操作，不显示错误
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(formatErrorMessage(error, '提交分析任务失败'))
      analysisStatus.value = 'failed'
    }
  } finally {
    loading.value = false
  }
}



// 获取分析结果
const fetchAnalysisResult = async (id: string) => {
  try {
    const res = await portfolioApi.getPositionAnalysisStatus(id)
    if (res.success && res.data) {
      analysisResult.value = res.data
      analysisStatus.value = res.data.status || 'completed'
    }
  } catch (error) {
    console.error('获取分析结果失败:', error)
  }
}

// 手动刷新状态
const manualRefreshStatus = async () => {
  if (!analysisId.value) {
    console.warn('[手动刷新状态] analysisId为空，无法刷新')
    ElMessage.warning('分析任务ID不存在，请重新开始分析')
    return
  }

  console.log('[手动刷新状态] 开始刷新，analysisId:', analysisId.value)
  refreshing.value = true
  try {
    const res = await portfolioApi.getPositionAnalysisStatus(analysisId.value)
    console.log('[手动刷新状态] 收到响应:', res)
    if (res.success && res.data) {
      analysisStatus.value = res.data.status || 'unknown'

      if (res.data.status === 'completed') {
        analysisResult.value = res.data
        ElMessage.success('分析完成！')
      } else if (res.data.status === 'failed') {
        ElMessage.error(formatErrorMessage(res.data.error_message, '分析失败，请稍后重试'))
      } else {
        ElMessage.info(`当前状态: ${res.data.status}`)
      }
    } else {
      console.error('[手动刷新状态] 响应失败:', res)
      ElMessage.error(formatErrorMessage(res.message, '获取分析状态失败'))
    }
  } catch (error: any) {
    console.error('[手动刷新状态] 请求失败:', error)
    ElMessage.error(formatErrorMessage(error, '刷新状态失败，请稍后重试'))
  } finally {
    refreshing.value = false
  }
}

// 加载已有的分析报告
// 加载已有的分析报告
// 注意：调用此函数前应先清空 analysisResult，避免显示其他股票的缓存数据
const loadExistingAnalysis = async () => {
  if (!props.position) return

  try {
    // 🔥 根据持仓来源传递 source 参数：模拟持仓 -> paper，用户持仓 -> real
    const source = props.position.source === 'paper' ? 'paper' : 'real'
    const res = await portfolioApi.getLatestPositionAnalysis(
      props.position.code,
      props.position.market,
      source
    )
    // 只有当后端返回有效数据时才更新状态
    // 如果 res.data 为 null，说明该股票没有分析报告，保持状态为 idle
    if (res.success && res.data) {
      analysisId.value = res.data.analysis_id
      analysisStatus.value = res.data.status || 'unknown'

      if (res.data.status === 'completed') {
        analysisResult.value = res.data
      } else if (res.data.status === 'pending' || res.data.status === 'processing') {
        // 有正在进行的分析，不自动轮询，用户可手动刷新查看状态
        ElMessage.info('检测到正在进行的分析任务，请点击"手动刷新状态"查看最新进度')
      }
    }
    // 如果 res.data 为 null，不做任何操作，保持之前 watch 中重置的 idle 状态
  } catch (error) {
    console.error('加载已有分析报告失败:', error)
  }
}

// 重新分析
const resetAnalysis = () => {
  analysisResult.value = null
  analysisId.value = null
  analysisStatus.value = 'idle'
}

// 风险等级相关辅助方法
const getRiskLevelClass = (level?: string) => {
  const map: Record<string, string> = {
    low: 'risk-low',
    medium: 'risk-medium',
    high: 'risk-high',
    critical: 'risk-critical'
  }
  return map[level || ''] || ''
}

const getRiskTagType = (level?: string): 'success' | 'warning' | 'danger' | 'info' => {
  const map: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
    low: 'success',
    medium: 'warning',
    high: 'danger',
    critical: 'danger'
  }
  return map[level || ''] || 'info'
}

const getRiskLevelText = (level?: string) => {
  const map: Record<string, string> = {
    low: '低风险',
    medium: '中风险',
    high: '高风险',
    critical: '极高风险'
  }
  return map[level || ''] || '未知'
}
</script>

<style scoped>
.position-info {
  margin-bottom: 16px;
}

.profit { color: #f56c6c; } /* 红色表示盈利（中国股市规范） */
.loss { color: #67c23a; } /* 绿色表示亏损（中国股市规范） */

/* 风险提示样式 */
.risk-disclaimer {
  margin: 24px 0;
  animation: fadeInDown 0.5s ease-out;
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

.disclaimer-content {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  font-size: 15px;
  line-height: 1.6;
}

.disclaimer-icon {
  font-size: 24px;
  color: #ff6b00;
  flex-shrink: 0;
  animation: pulse 2s ease-in-out infinite;
  margin-top: 2px;
}

.disclaimer-text {
  color: #856404;
  flex: 1;
}

.disclaimer-text strong {
  color: #d63031;
  font-size: 16px;
  font-weight: 700;
}

.disclaimer-text ul {
  margin: 8px 0;
  padding-left: 20px;
}

.disclaimer-text li {
  margin-bottom: 6px;
}

@keyframes fadeInDown {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes pulse {
  0%, 100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.1);
    opacity: 0.8;
  }
}

.analysis-status {
  margin: 16px 0;

  ul {
    margin: 8px 0 0 20px;
    padding: 0;
    li {
      margin: 4px 0;
    }
  }

  .is-loading {
    animation: rotating 2s linear infinite;
    margin-right: 8px;
  }
}

@keyframes rotating {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.analysis-params {
  margin: 16px 0;
}

.unit {
  margin-left: 8px;
  color: #909399;
}

.overview-panel {
  background: linear-gradient(135deg, #f8fafc 0%, #eef4ff 100%);
  border: 1px solid #dbe7ff;
  border-radius: 16px;
  padding: 20px 24px;
  margin-bottom: 20px;
}

.overview-header h3 {
  margin: 0 0 10px 0;
  font-size: 20px;
  color: #1f2937;
}

.overview-header p {
  margin: 0;
  font-size: 15px;
  line-height: 1.9;
  color: #334155;
}

.context-chip {
  margin-top: 14px;
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.85);
  color: #475569;
  line-height: 1.8;
}

.assessment-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.assessment-card {
  background: #f8fafc;
  border: 1px solid #e5edf6;
  border-radius: 14px;
  padding: 18px;
}

.assessment-card h4,
.uncertainty-card h4 {
  margin: 0 0 10px 0;
  font-size: 15px;
  color: #1f2937;
  display: flex;
  align-items: center;
  gap: 4px;
}

.bullet-list {
  margin: 0;
  padding-left: 18px;
  color: #475569;
  line-height: 1.8;
}

.bullet-list li + li {
  margin-top: 8px;
}

.uncertainty-card {
  margin-bottom: 20px;
  padding: 16px 18px;
  border-radius: 14px;
  background: #fff7ed;
  border: 1px solid #fed7aa;
}

.uncertainty-card p {
  margin: 0;
  color: #7c2d12;
  line-height: 1.8;
}

.appendix-section {
  padding: 12px 0;
  border-bottom: 1px solid #ebeef5;
}

.appendix-section:last-child {
  padding-bottom: 0;
  border-bottom: none;
}

.appendix-section h4 {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

@media (max-width: 900px) {
  .assessment-grid {
    grid-template-columns: 1fr;
  }
}

.detailed-analysis {
  line-height: 1.6;
  color: #606266;
}

.markdown-content {
  line-height: 1.6;
  color: #606266;
}

.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3),
.markdown-content :deep(h4) {
  margin-top: 16px;
  margin-bottom: 8px;
  font-weight: bold;
  color: #303133;
}

.markdown-content :deep(h1) { font-size: 20px; }
.markdown-content :deep(h2) { font-size: 18px; }
.markdown-content :deep(h3) { font-size: 16px; }
.markdown-content :deep(h4) { font-size: 14px; }

.markdown-content :deep(p) {
  margin: 8px 0;
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  margin: 8px 0;
  padding-left: 24px;
}

.markdown-content :deep(li) {
  margin: 4px 0;
}

.markdown-content :deep(code) {
  background: #f5f7fa;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Courier New', monospace;
  font-size: 0.9em;
}

.markdown-content :deep(pre) {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  overflow-x: auto;
  margin: 12px 0;
}

.markdown-content :deep(pre code) {
  background: none;
  padding: 0;
}

.markdown-content :deep(blockquote) {
  border-left: 4px solid #409eff;
  padding-left: 12px;
  margin: 12px 0;
  color: #606266;
}

.markdown-content :deep(strong) {
  font-weight: bold;
  color: #303133;
}

/* 资金风险指标样式 */
.risk-metrics-section {
  margin: 16px 0;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 8px;
}

.risk-metrics-section h4 {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 12px;
  font-size: 14px;
  color: #303133;
}

.risk-summary {
  margin-top: 8px;
  padding: 8px;
  background: #fff;
  border-radius: 4px;
  font-size: 13px;
  color: #606266;
}

.risk-low { color: #67c23a; }
.risk-medium { color: #e6a23c; }
.risk-high { color: #f56c6c; }
.risk-critical { color: #f56c6c; font-weight: bold; }

.tip {
  margin-left: 8px;
  font-size: 12px;
  color: #909399;
}
</style>

