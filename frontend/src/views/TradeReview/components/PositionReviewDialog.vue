<template>
  <el-dialog
    v-model="visible"
    title="持仓操作复盘"
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
      <el-form-item label="分析版本">
        <el-radio-group v-model="form.analysis_version">
          <el-radio value="v1.0">
            <span class="version-label">
              <el-tag size="small" type="info">v1.0</el-tag>
              <span class="version-desc">传统分析（快速）</span>
            </span>
          </el-radio>
          <el-radio value="v2.0">
            <span class="version-label">
              <el-tag size="small" type="success">v2.0</el-tag>
              <span class="version-desc">工作流分析（深度）</span>
            </span>
          </el-radio>
        </el-radio-group>
        <div class="form-tip">v2.0 使用多维度工作流引擎，分析更全面但耗时更长</div>
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
              <el-tag size="small" type="info">{{ getStyleLabel(system.style) }}</el-tag>
            </div>
          </el-option>
        </el-select>
        <div class="form-tip">选择后将按照交易计划规则进行合规性检查</div>
      </el-form-item>
      <el-form-item label="分析维度">
        <el-checkbox-group v-model="form.dimensions">
          <el-checkbox label="买入时机">买入时机</el-checkbox>
          <el-checkbox label="卖出时机">卖出时机</el-checkbox>
          <el-checkbox label="仓位管理">仓位管理</el-checkbox>
          <el-checkbox label="止盈止损">止盈止损</el-checkbox>
          <el-checkbox label="心理分析">心理分析</el-checkbox>
        </el-checkbox-group>
      </el-form-item>
      <el-form-item label="补充说明">
        <el-input
          v-model="form.notes"
          type="textarea"
          :rows="3"
          placeholder="可以补充操作时的想法、市场情况等"
        />
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
  analysis_version: 'v1.0',  // 默认使用 v1.0
  dimensions: ['买入时机', '卖出时机', '仓位管理'],
  notes: '',
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
  } catch (e: any) {
    console.error('加载交易计划列表失败:', e)
  } finally {
    loadingTradingSystems.value = false
  }
}

// 组件挂载时加载交易计划列表
onMounted(() => {
  loadTradingSystems()
})

watch(visible, (val) => {
  if (!val) {
    form.value = {
      analysis_version: 'v1.0',
      dimensions: ['买入时机', '卖出时机', '仓位管理'],
      notes: '',
      trading_system_id: ''
    }
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
  if (form.value.dimensions.length === 0) {
    ElMessage.warning('请至少选择一个分析维度')
    return
  }

  if (!props.positionData) {
    ElMessage.error('持仓数据不存在')
    return
  }

  try {
    submitting.value = true

    // 1. 获取该股票的所有交易记录（真实持仓）
    const tradesRes = await reviewApi.getTradesByCode(props.positionData.code, 'real')
    const trades = tradesRes.data?.trades || []

    if (trades.length === 0) {
      ElMessage.warning('该股票暂无可分析的交易记录')
      return
    }

    // 2. 获取交易ID列表
    const tradeIds = trades.map(t => t.trade_id)

    // 3. 创建复盘分析
    const reviewRes = await reviewApi.createTradeReview({
      trade_ids: tradeIds,
      review_type: 'complete_trade',
      code: props.positionData.code,
      source: 'real',  // 真实持仓
      trading_system_id: form.value.trading_system_id || undefined,  // 传递交易计划ID
      use_workflow: form.value.analysis_version === 'v2.0'  // 根据选择的版本决定是否使用工作流
    })

    if (reviewRes.data) {
      ElMessage.success('持仓操作复盘完成')
      emit('success', reviewRes.data.review_id)
      visible.value = false
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
.positive { color: #67c23a; }
.negative { color: #f56c6c; }
.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
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

