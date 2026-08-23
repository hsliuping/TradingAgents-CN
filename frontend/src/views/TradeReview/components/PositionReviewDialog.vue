<template>
    <el-dialog
    v-model="visible"
    :title="props.source === 'paper' ? '模拟交易复盘' : '持仓操作复盘'"
    width="600px"
    :close-on-click-modal="false"
  >
    <div v-if="positionData" class="position-info">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="股票代码">{{ positionData.code }}</el-descriptions-item>
        <el-descriptions-item label="股票名称">{{ positionData.name }}</el-descriptions-item>
        <el-descriptions-item label="市场">
          <el-tag size="small">{{ positionData.market }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="复盘类型">
          <el-tag size="small" :type="positionData.type === 'current' ? 'primary' : 'success'">
            {{ positionData.type === 'current' ? '当前持仓' : '历史持仓' }}
          </el-tag>
        </el-descriptions-item>
        <template v-if="positionData.type === 'current'">
          <el-descriptions-item label="持仓数量">{{ positionData.quantity }}</el-descriptions-item>
          <el-descriptions-item label="成本价">{{ positionData.cost_price?.toFixed(2) }}</el-descriptions-item>
          <el-descriptions-item label="浮动盈亏" :span="2">
            <span :class="(positionData.unrealized_pnl || 0) >= 0 ? 'positive' : 'negative'">
              {{ formatPnl(positionData.unrealized_pnl) }}
            </span>
          </el-descriptions-item>
        </template>
        <template v-else>
          <el-descriptions-item label="已实现盈亏">
            <span :class="(positionData.realized_pnl || 0) >= 0 ? 'positive' : 'negative'">
              {{ formatPnl(positionData.realized_pnl) }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="持有天数">{{ positionData.hold_days }} 天</el-descriptions-item>
        </template>
      </el-descriptions>
    </div>

    <el-divider content-position="left">复盘分析内容</el-divider>

    <el-form :model="form" label-width="100px">
      <!-- 流程选择 -->
      <el-form-item v-if="workflowsSorted.length > 0" label="分析流程">
        <div style="display: flex; align-items: center; width: 100%">
          <el-select
            v-model="selectedWorkflowId"
            size="small"
            style="flex: 1"
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
            <el-icon style="margin-left: 8px; color: #909399; cursor: help"><InfoFilled /></el-icon>
          </el-tooltip>
        </div>
      </el-form-item>
      <!-- 🆕 移除分析版本选择，统一使用工作流分析 -->
      <el-form-item label="复盘分析内容">
        <el-alert type="info" :closable="false" show-icon>
          <template #title>
            使用多维度工作流引擎进行深度分析，预计需要1-3分钟完成
          </template>
        </el-alert>
      </el-form-item>
      <el-form-item v-if="canUseTradingPlanCheck" label="关联交易计划">
        <el-select
          v-model="form.trading_system_id"
          placeholder="选择交易计划（可选）"
          clearable
          :loading="loadingTradingSystems"
          style="width: 100%"
        >
          <el-option
            v-for="system in tradingSystems"
            :key="system.id"
            :label="system.name"
            :value="system.id || system.name"
          >
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>{{ system.name }}</span>
              <div style="display: flex; gap: 4px; align-items: center">
                <el-tag v-if="system.is_active" size="small" type="success">默认</el-tag>
                <el-tag size="small" type="info">{{ getStyleLabel(system.style) }}</el-tag>
              </div>
            </div>
          </el-option>
        </el-select>
        <div class="form-tip">选择后将按照交易计划规则进行执行一致性检查</div>
      </el-form-item>
      <el-form-item v-else label="执行一致性检查">
        <div class="form-tip">高级学员可关联交易计划，对复盘结果进行执行一致性检查。</div>
      </el-form-item>
      <el-form-item label="分析维度">
        <div class="dimensions-list">
          <div class="dimension-item">
            <el-tag type="info" size="large">时机</el-tag>
            <span class="dimension-desc">分析买入和卖出的时机选择是否合理</span>
          </div>
          <div class="dimension-item">
            <el-tag type="info" size="large">仓位</el-tag>
            <span class="dimension-desc">评估仓位管理的合理性和风险控制</span>
          </div>
          <div class="dimension-item">
            <el-tag type="info" size="large">情绪</el-tag>
            <span class="dimension-desc">分析操作决策中的情绪因素和纪律执行</span>
          </div>
          <div class="dimension-item">
            <el-tag type="info" size="large">归因</el-tag>
            <span class="dimension-desc">分析收益来源，区分是能力还是运气</span>
          </div>
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">
        开始复盘
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { InfoFilled } from '@element-plus/icons-vue'
import { reviewApi, type TradeRecord } from '@/api/review'
import * as tradingSystemApi from '@/api/tradingSystem'
import type { TradingSystem } from '@/api/tradingSystem'
import { useLicenseStore } from '@/stores/license'
import { workflowApi, isSelectableAnalysisWorkflow, type WorkflowSummary } from '@/api/workflow'

interface PositionData {
  code: string
  name: string
  market: string
  type: 'current' | 'history'
  quantity?: number
  cost_price?: number
  unrealized_pnl?: number
  realized_pnl?: number
  hold_days?: number
  cleared_at?: string
}

const props = defineProps<{
  modelValue: boolean
  positionData: PositionData | null
  source?: 'paper' | 'real'  // 数据源: paper(模拟交易) 或 real(用户持仓)
  workflowId?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'success', reviewId: string): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})
const licenseStore = useLicenseStore()
const canUseTradingPlanCheck = computed(() => licenseStore.hasFeature('trading_plan_check'))

const form = ref({
  // 🆕 移除 analysis_version，统一使用工作流分析
  // 🆕 移除 dimensions，改为固定维度：时机、仓位、情绪、归因
  // 🆕 移除 notes，后端未使用此字段
  trading_system_id: ''
})

const submitting = ref(false)

// 流程选择
const workflows = ref<WorkflowSummary[]>([])
const selectedWorkflowId = ref<string>('')

const parseVersion = (v: string): number[] => {
  const parts = String(v || '0.0.0').split('.')
  return parts.map(p => parseInt(p, 10) || 0)
}

const workflowsSorted = computed(() => {
  const arr = workflows.value.filter(
    (w: WorkflowSummary) => isSelectableAnalysisWorkflow(w, 'trade_review')
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

// 交易计划相关
const tradingSystems = ref<TradingSystem[]>([])
const loadingTradingSystems = ref(false)

// 加载交易计划列表
const loadTradingSystems = async () => {
  if (!canUseTradingPlanCheck.value) {
    tradingSystems.value = []
    form.value.trading_system_id = ''
    return
  }

  loadingTradingSystems.value = true
  try {
    const res = await tradingSystemApi.getTradingSystems()
    tradingSystems.value = res.data?.systems || []
    
    // 🔥 自动选中默认交易计划（is_active: true）
    const activeSystem = tradingSystems.value.find(system => system.is_active)
    if (activeSystem && activeSystem.id) {
      form.value.trading_system_id = activeSystem.id
    }
  } catch (e: any) {
    console.error('加载交易计划列表失败:', e)
  } finally {
    loadingTradingSystems.value = false
  }
}

watch(visible, async (val) => {
  if (!val) {
    // 关闭对话框时重置表单
    form.value = {
      // 🆕 移除 analysis_version、dimensions 和 notes
      trading_system_id: ''
    }
  } else {
    if (!licenseStore.licenseInfo) {
      await licenseStore.verifyLicense()
    }
    // 打开对话框时，重新加载交易计划列表并自动选中默认计划
    await loadTradingSystems()
    // 加载工作流列表
    await loadWorkflows()
  }
})

const formatPnl = (val?: number) => {
  if (val === undefined || val === null) return '-'
  const prefix = val >= 0 ? '+' : ''
  return prefix + val.toFixed(2)
}

const getStyleLabel = (style: string) => {
  const labels: Record<string, string> = {
    short_term: '短线',
    medium_term: '中线',
    long_term: '长线'
  }
  return labels[style] || style
}

const parseTime = (value?: string) => {
  if (!value) return null
  const timestamp = new Date(value).getTime()
  return Number.isNaN(timestamp) ? null : timestamp
}

const getTradeSortTime = (trade: TradeRecord) => {
  return parseTime(trade.timestamp) ?? parseTime(trade.created_at) ?? 0
}

const segmentPositionTrades = (trades: TradeRecord[]) => {
  const sortedTrades = [...trades].sort((left, right) => getTradeSortTime(left) - getTradeSortTime(right))
  const segments: TradeRecord[][] = []
  let startIndex = 0

  sortedTrades.forEach((trade, index) => {
    if (trade.quantity_after === 0) {
      const segment = sortedTrades.slice(startIndex, index + 1)
      if (segment.length) {
        segments.push(segment)
      }
      startIndex = index + 1
    }
  })

  if (startIndex < sortedTrades.length) {
    segments.push(sortedTrades.slice(startIndex))
  }

  return segments.filter(segment => segment.length > 0)
}

const selectTradesForPositionCycle = (trades: TradeRecord[], positionData: PositionData, source: 'paper' | 'real') => {
  if (source !== 'real' || trades.length === 0) {
    return trades
  }

  const segments = segmentPositionTrades(trades)
  if (segments.length === 0) {
    return trades
  }

  if (positionData.type === 'current') {
    const activeSegment = [...segments].reverse().find(segment => {
      const lastTrade = segment[segment.length - 1]
      return (lastTrade.quantity_after ?? 0) > 0
    })
    return activeSegment || segments[segments.length - 1]
  }

  const closedSegments = segments.filter(segment => {
    const lastTrade = segment[segment.length - 1]
    return lastTrade.quantity_after === 0
  })

  if (closedSegments.length === 0) {
    return segments[segments.length - 1]
  }

  const clearedAt = parseTime(positionData.cleared_at)
  if (clearedAt === null) {
    return closedSegments[closedSegments.length - 1]
  }

  let bestSegment = closedSegments[0]
  let bestDiff = Math.abs(getTradeSortTime(closedSegments[0][closedSegments[0].length - 1]) - clearedAt)

  closedSegments.slice(1).forEach(segment => {
    const endTime = getTradeSortTime(segment[segment.length - 1])
    const diff = Math.abs(endTime - clearedAt)
    if (diff < bestDiff) {
      bestSegment = segment
      bestDiff = diff
    }
  })

  return bestSegment
}

const handleSubmit = async () => {
  if (!props.positionData) {
    ElMessage.error('持仓数据不存在')
    return
  }

  try {
    submitting.value = true

    const source = props.source || 'real'  // 默认用户持仓
    
    // 1. 获取该股票的所有交易记录
    const tradesRes = await reviewApi.getTradesByCode(props.positionData.code, source)
    const trades = tradesRes.data?.trades || []

    if (trades.length === 0) {
      ElMessage.warning('该股票暂无可分析的交易记录')
      return
    }

    const reviewTrades = selectTradesForPositionCycle(trades, props.positionData, source)

    if (reviewTrades.length === 0) {
      ElMessage.warning('未找到与当前持仓周期对应的交易记录')
      return
    }

    // 2. 获取当前持仓周期的交易ID列表
    const tradeIds = reviewTrades.map(t => t.trade_id)

    // 3. 创建复盘分析（统一使用工作流分析）
    const reviewRes = await reviewApi.createTradeReview({
      trade_ids: tradeIds,
      review_type: 'complete_trade',
      code: props.positionData.code,
      source: source,  // 使用传入的数据源
      trading_system_id: canUseTradingPlanCheck.value ? (form.value.trading_system_id || undefined) : undefined,
      workflow_id: selectedWorkflowId.value || undefined,
      use_workflow: true  // 🆕 统一使用工作流分析
    })

    if (reviewRes.data) {
      console.log('[PositionReviewDialog] 复盘创建成功，reviewId:', reviewRes.data.review_id)
      // 先触发 success 事件，让父组件打开详情页面
      emit('success', reviewRes.data.review_id)
      console.log('[PositionReviewDialog] 已触发 success 事件')
      // 延迟关闭对话框，确保详情页面先打开
      setTimeout(() => {
        visible.value = false
        console.log('[PositionReviewDialog] 对话框已关闭')
      }, 200)
    }
  } catch (e: any) {
    ElMessage.error(e.message || '复盘失败')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped lang="scss">
.position-info {
  margin-bottom: 16px;
}
.positive { color: #f56c6c; }  // 中国习惯：红色表示盈利（正数）
.negative { color: #67c23a; }  // 中国习惯：绿色表示亏损（负数）
.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
.dimensions-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.dimension-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.dimension-desc {
  font-size: 14px;
  color: #606266;
  flex: 1;
}
.version-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;

  .version-desc {
    font-size: 13px;
    color: #606266;
  }
}
</style>

