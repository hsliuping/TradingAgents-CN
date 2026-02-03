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
      <!-- 🆕 移除分析版本选择，统一使用工作流分析 -->
      <el-form-item label="复盘分析内容">
        <el-alert type="info" :closable="false" show-icon>
          <template #title>
            使用多维度工作流引擎进行深度分析，预计需要1-3分钟完成
          </template>
        </el-alert>
      </el-form-item>
      <el-form-item label="关联交易计划">
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
            :value="system.id"
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
        <div class="form-tip">选择后将按照交易计划规则进行合规性检查</div>
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
            <span class="dimension-desc">分析交易决策中的情绪因素和纪律执行</span>
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
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { reviewApi } from '@/api/review'
import * as tradingSystemApi from '@/api/tradingSystem'
import type { TradingSystem } from '@/api/tradingSystem'

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
}

const props = defineProps<{
  modelValue: boolean
  positionData: PositionData | null
  source?: 'paper' | 'real'  // 数据源: paper(模拟交易) 或 real(真实持仓)
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'success', reviewId: string): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const form = ref({
  // 🆕 移除 analysis_version，统一使用工作流分析
  // 🆕 移除 dimensions，改为固定维度：时机、仓位、情绪、归因
  // 🆕 移除 notes，后端未使用此字段
  trading_system_id: ''
})

const submitting = ref(false)

// 交易计划相关
const tradingSystems = ref<TradingSystem[]>([])
const loadingTradingSystems = ref(false)

// 加载交易计划列表
const loadTradingSystems = async () => {
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

// 组件挂载时加载交易计划列表（对话框打开时会重新加载，这里可以延迟加载）
onMounted(() => {
  // 延迟加载，避免不必要的请求（对话框打开时会重新加载）
  // loadTradingSystems()
})

watch(visible, async (val) => {
  if (!val) {
    // 关闭对话框时重置表单
    form.value = {
      // 🆕 移除 analysis_version、dimensions 和 notes
      trading_system_id: ''
    }
  } else {
    // 打开对话框时，重新加载交易计划列表并自动选中默认计划
    await loadTradingSystems()
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

const handleSubmit = async () => {
  if (!props.positionData) {
    ElMessage.error('持仓数据不存在')
    return
  }

  try {
    submitting.value = true

    const source = props.source || 'real'  // 默认真实持仓
    
    // 1. 获取该股票的所有交易记录
    const tradesRes = await reviewApi.getTradesByCode(props.positionData.code, source)
    const trades = tradesRes.data?.trades || []

    if (trades.length === 0) {
      ElMessage.warning('该股票暂无可分析的交易记录')
      return
    }

    // 2. 获取交易ID列表
    const tradeIds = trades.map(t => t.trade_id)

    // 3. 创建复盘分析（统一使用工作流分析）
    const reviewRes = await reviewApi.createTradeReview({
      trade_ids: tradeIds,
      review_type: 'complete_trade',
      code: props.positionData.code,
      source: source,  // 使用传入的数据源
      trading_system_id: form.value.trading_system_id || undefined,  // 传递交易计划ID
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

