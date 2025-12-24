<template>
  <el-dialog
    v-model="visible"
    :title="`📋 ${stockInfo.name || stockInfo.code} 操作历史`"
    width="800px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <!-- 股票信息摘要 -->
    <div class="stock-summary">
      <div class="stock-info">
        <span class="stock-code">{{ stockInfo.code }}</span>
        <span class="stock-name">{{ stockInfo.name }}</span>
        <el-tag :type="getMarketTagType(stockInfo.market)" size="small">{{ getMarketName(stockInfo.market) }}</el-tag>
      </div>
      <div class="analysis-controls">
        <el-select
          v-model="selectedTradingSystemId"
          placeholder="选择交易计划（可选）"
          clearable
          size="small"
          style="width: 200px; margin-right: 8px"
          :loading="loadingTradingSystems"
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
        <el-button type="primary" size="small" :loading="analyzing" @click="handleAnalyze">
          <el-icon v-if="!analyzing"><DataAnalysis /></el-icon>
          {{ analyzing ? '分析中...' : '操作分析' }}
        </el-button>
      </div>
    </div>

    <!-- 操作记录表格 -->
    <el-table :data="changes" v-loading="loading" stripe size="small" max-height="400">
      <el-table-column prop="trade_time" label="交易时间" width="150">
        <template #default="{ row }">
          {{ formatDateTime(row.trade_time) }}
        </template>
      </el-table-column>
      <el-table-column prop="change_type" label="操作类型" width="90">
        <template #default="{ row }">
          <el-tag :type="getChangeTypeTag(row.change_type)" size="small">{{ getChangeTypeName(row.change_type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="数量变化" width="130">
        <template #default="{ row }">
          <span :class="row.quantity_change >= 0 ? 'text-buy' : 'text-sell'">
            {{ row.quantity_change >= 0 ? '+' : '' }}{{ row.quantity_change }}
          </span>
          <div class="sub-text">{{ row.quantity_before }} → {{ row.quantity_after }}</div>
        </template>
      </el-table-column>
      <el-table-column label="成交价" width="100">
        <template #default="{ row }">
          {{ getCurrencySymbol(row.currency) }}{{ (row.price || 0).toFixed(2) }}
        </template>
      </el-table-column>
      <el-table-column label="成本价变化" width="130">
        <template #default="{ row }">
          {{ getCurrencySymbol(row.currency) }}{{ row.cost_price_after.toFixed(2) }}
          <div class="sub-text" v-if="row.cost_price_before !== row.cost_price_after">
            {{ row.cost_price_before.toFixed(2) }} → {{ row.cost_price_after.toFixed(2) }}
          </div>
        </template>
      </el-table-column>
      <el-table-column label="资金变化" width="120">
        <template #default="{ row }">
          <span :class="row.cash_change >= 0 ? 'text-buy' : 'text-sell'">
            {{ row.cash_change >= 0 ? '+' : '' }}{{ getCurrencySymbol(row.currency) }}{{ Math.abs(row.cash_change).toFixed(2) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="说明" min-width="100" show-overflow-tooltip />
    </el-table>

    <!-- 分页 -->
    <div class="pagination-bar" v-if="total > pageSize">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, prev, pager, next"
        small
        @current-change="loadData"
      />
    </div>

    <!-- 空状态 -->
    <el-empty v-if="!loading && changes.length === 0" description="暂无操作记录" />

    <!-- 操作分析报告展示 -->
    <el-card v-if="reviewReport" class="review-card" shadow="never">
      <template #header>
        <div class="review-header">
          <span>📊 操作分析报告</span>
          <div style="display: flex; align-items: center; gap: 8px">
            <el-tag v-if="reviewReport.trading_system_name" type="success" size="small">
              🎯 {{ reviewReport.trading_system_name }}
            </el-tag>
            <el-tag :type="getScoreTagType(reviewReport.ai_review?.overall_score)" size="small">
              评分: {{ reviewReport.ai_review?.overall_score || 0 }}分
            </el-tag>
          </div>
        </div>
      </template>
      <div class="review-content">
        <div class="review-summary">{{ reviewReport.ai_review?.summary || '暂无分析摘要' }}</div>
        <el-row :gutter="16" class="review-scores">
          <el-col :span="8" v-if="reviewReport.ai_review?.timing_score">
            <div class="score-item">
              <span class="score-label">买卖时机</span>
              <span class="score-value">{{ reviewReport.ai_review.timing_score }}分</span>
            </div>
          </el-col>
          <el-col :span="8" v-if="reviewReport.ai_review?.position_score">
            <div class="score-item">
              <span class="score-label">仓位控制</span>
              <span class="score-value">{{ reviewReport.ai_review.position_score }}分</span>
            </div>
          </el-col>
          <el-col :span="8" v-if="reviewReport.ai_review?.discipline_score">
            <div class="score-item">
              <span class="score-label">交易纪律</span>
              <span class="score-value">{{ reviewReport.ai_review.discipline_score }}分</span>
            </div>
          </el-col>
        </el-row>
        <div v-if="reviewReport.ai_review?.suggestions?.length" class="review-suggestions">
          <div class="section-title">💡 改进建议</div>
          <ul>
            <li v-for="(suggestion, idx) in reviewReport.ai_review.suggestions" :key="idx">{{ suggestion }}</li>
          </ul>
        </div>
      </div>
    </el-card>

    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { DataAnalysis } from '@element-plus/icons-vue'
import { portfolioApi, type PositionChange } from '@/api/portfolio'
import { reviewApi, type TradeReviewReport, type ReviewListItem } from '@/api/review'
import * as tradingSystemApi from '@/api/tradingSystem'
import type { TradingSystem } from '@/api/tradingSystem'

interface StockInfo {
  code: string
  name?: string
  market: string
}

const props = defineProps<{
  modelValue: boolean
  stock: StockInfo | null
  source?: 'real' | 'paper'  // 数据源：真实持仓或模拟持仓
}>()
const emit = defineEmits(['update:modelValue'])

const router = useRouter()
const visible = ref(props.modelValue)
const loading = ref(false)
const analyzing = ref(false)
const changes = ref<PositionChange[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(50)
const reviewReport = ref<TradeReviewReport | null>(null)

// 交易计划相关
const tradingSystems = ref<TradingSystem[]>([])
const selectedTradingSystemId = ref<string>('')
const loadingTradingSystems = ref(false)

const stockInfo = computed(() => props.stock || { code: '', name: '', market: '' })

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

watch(() => props.modelValue, (val) => {
  visible.value = val
  if (val && props.stock) {
    currentPage.value = 1
    reviewReport.value = null  // 重置分析报告
    selectedTradingSystemId.value = ''  // 重置交易计划选择
    loadData()
    loadExistingReview()  // 加载已有的复盘报告
  }
})

watch(visible, (val) => emit('update:modelValue', val))

const loadData = async () => {
  if (!props.stock?.code) return
  loading.value = true
  try {
    const res = await portfolioApi.getPositionChanges({
      code: props.stock.code,
      market: props.stock.market || undefined,
      limit: pageSize.value,
      skip: (currentPage.value - 1) * pageSize.value
    })
    changes.value = res.data?.items || []
    total.value = res.data?.total || 0
  } catch (e: any) {
    ElMessage.error(e.message || '加载操作历史失败')
  } finally {
    loading.value = false
  }
}

const handleClose = () => emit('update:modelValue', false)

// 加载已有的复盘报告
const loadExistingReview = async () => {
  if (!props.stock?.code) return
  try {
    const res = await reviewApi.getReviewHistory({ code: props.stock.code, pageSize: 1 })
    if (res.data?.items?.length > 0) {
      const latestReview = res.data.items[0]
      // 获取详细报告
      const detailRes = await reviewApi.getReviewDetail(latestReview.review_id)
      if (detailRes.data) {
        reviewReport.value = detailRes.data
      }
    }
  } catch (e) {
    // 没有报告不报错
    console.log('暂无复盘报告')
  }
}

// 操作分析
const handleAnalyze = async () => {
  if (!props.stock?.code) return

  analyzing.value = true
  try {
    // 根据 source 参数获取对应的交易记录
    const source = props.source || 'real'
    const tradesRes = await reviewApi.getTradesByCode(props.stock.code, source)
    const trades = tradesRes.data?.trades || []

    if (trades.length === 0) {
      ElMessage.warning('该股票暂无可分析的交易记录')
      return
    }

    // 获取交易ID列表
    const tradeIds = trades.map(t => t.trade_id)

    // 创建复盘分析
    const reviewRes = await reviewApi.createTradeReview({
      trade_ids: tradeIds,
      review_type: 'complete_trade',
      code: props.stock.code,
      source: source,  // 传递数据源参数
      trading_system_id: selectedTradingSystemId.value || undefined  // 传递交易计划ID
    })

    if (reviewRes.data) {
      reviewReport.value = reviewRes.data
      ElMessage.success('操作分析完成')
    }
  } catch (e: any) {
    ElMessage.error(e.message || '操作分析失败')
  } finally {
    analyzing.value = false
  }
}

const formatDateTime = (dt: string) => {
  if (!dt) return '-'
  const d = new Date(dt)
  return d.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

const getMarketName = (m: string) => ({ CN: 'A股', HK: '港股', US: '美股' }[m] || m)
const getMarketTagType = (m: string) => ({ CN: 'danger', HK: 'warning', US: 'primary' }[m] || 'info') as any
const getCurrencySymbol = (c: string) => ({ CNY: '¥', HKD: 'HK$', USD: '$' }[c] || c)
const getChangeTypeName = (t: string) => ({ buy: '买入', add: '加仓', reduce: '减仓', sell: '卖出', adjust: '调整', dividend: '分红', split: '拆股', merge: '合股' }[t] || t)
const getChangeTypeTag = (t: string) => ({ buy: 'success', add: 'primary', reduce: 'warning', sell: 'danger', adjust: 'info', dividend: '', split: '', merge: '' }[t] || 'info') as any
const getScoreTagType = (score: number | undefined) => {
  if (!score) return 'info'
  if (score >= 80) return 'success'
  if (score >= 60) return 'warning'
  return 'danger'
}
const getStyleLabel = (style: string) => {
  const labels: Record<string, string> = {
    short_term: '短线',
    medium_term: '中线',
    long_term: '长线'
  }
  return labels[style] || style
}
</script>

<style scoped>
.stock-summary { margin-bottom: 16px; display: flex; align-items: center; justify-content: space-between; }
.stock-info { display: flex; align-items: center; gap: 12px; }
.stock-code { font-weight: 600; color: #409eff; font-size: 15px; }
.stock-name { font-size: 15px; color: #303133; }
.analysis-controls { display: flex; align-items: center; }
.pagination-bar { margin-top: 16px; display: flex; justify-content: flex-end; }
.text-buy { color: #f56c6c; }
.text-sell { color: #67c23a; }
.sub-text { font-size: 11px; color: #909399; }

/* 复盘报告样式 */
.review-card { margin-top: 16px; background: #f8f9fa; }
.review-header { display: flex; justify-content: space-between; align-items: center; }
.review-content { font-size: 14px; }
.review-summary { color: #606266; line-height: 1.6; margin-bottom: 12px; }
.review-scores { margin-bottom: 12px; }
.score-item { text-align: center; padding: 8px; background: #fff; border-radius: 4px; }
.score-label { display: block; font-size: 12px; color: #909399; }
.score-value { display: block; font-size: 18px; font-weight: 600; color: #409eff; margin-top: 4px; }
.review-suggestions { margin-top: 12px; }
.section-title { font-weight: 600; color: #303133; margin-bottom: 8px; }
.review-suggestions ul { margin: 0; padding-left: 20px; color: #606266; }
.review-suggestions li { margin-bottom: 4px; }
</style>

