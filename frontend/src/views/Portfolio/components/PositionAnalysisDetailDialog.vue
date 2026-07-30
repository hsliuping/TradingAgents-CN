<template>
  <el-dialog
    v-model="visible"
    title="分析报告详情"
    width="900px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <div v-if="report" class="analysis-detail">
      <!-- 风险提示 -->
      <div class="risk-disclaimer">
        <el-alert
          type="warning"
          :closable="false"
          show-icon
        >
          <template #title>
            <span style="font-size: 14px;">
              <strong>⚠️ 重要提示：</strong>本次分析所有分析结论用于学习和验证AI证券分析技术，不作为真实交易操盘指导。
            </span>
          </template>
        </el-alert>
      </div>

      <!-- 持仓快照 -->
      <div class="section">
        <h3>📊 持仓快照</h3>
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item :label="securityCodeLabel">{{ report.position_snapshot?.code || '-' }}</el-descriptions-item>
          <el-descriptions-item :label="securityNameLabel">{{ report.position_snapshot?.name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="持仓数量">{{ report.position_snapshot?.quantity || 0 }} 股</el-descriptions-item>
          <el-descriptions-item label="成本价">¥{{ (report.position_snapshot?.cost_price || 0).toFixed(2) }}</el-descriptions-item>
          <el-descriptions-item label="当前价">¥{{ (report.position_snapshot?.current_price || 0).toFixed(2) }}</el-descriptions-item>
          <el-descriptions-item label="持仓市值">¥{{ (report.position_snapshot?.market_value || 0).toFixed(2) }}</el-descriptions-item>
          <el-descriptions-item label="浮动盈亏">
            <span :class="pnlClass(report.position_snapshot?.unrealized_pnl || 0)">
              {{ formatPnl(report.position_snapshot?.unrealized_pnl || 0) }}
              ({{ formatPct(report.position_snapshot?.unrealized_pnl_pct || 0) }})
            </span>
          </el-descriptions-item>
          <el-descriptions-item :label="industryLabel">{{ industryValue }}</el-descriptions-item>
        </el-descriptions>
      </div>

      <!-- 分析观点 -->
      <div class="section">
        <h3>💡 分析观点</h3>
        <div class="action-section">
          <div class="action-badge" :class="getActionClass(report.action)">
            {{ getActionText(report.action) }}
          </div>
          <div class="confidence">
            置信度: <el-progress :percentage="report.confidence || 0" :stroke-width="8" style="width: 120px; display: inline-flex;" />
          </div>
        </div>
        <div class="reason-section">
          <h4>分析理由</h4>
          <div class="markdown-content" v-html="renderMarkdown(report.action_reason || '暂无')"></div>
        </div>
      </div>

      <!-- 价格参考区间 -->
      <div class="section" v-if="report.price_targets">
        <h3>🎯 价格参考区间</h3>
        <el-row :gutter="20">
          <el-col :span="8">
            <div class="target-card loss-bg">
              <div class="label">风险控制参考价</div>
              <div class="value">¥{{ (report.price_targets.stop_loss_price || 0).toFixed(2) }}</div>
              <div class="pct">{{ (report.price_targets.stop_loss_pct || 0).toFixed(1) }}%</div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="target-card neutral-bg">
              <div class="label">成本价</div>
              <div class="value">¥{{ (report.price_targets.breakeven_price || 0).toFixed(2) }}</div>
              <div class="pct">0%</div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="target-card profit-bg">
              <div class="label">收益预期参考价</div>
              <div class="value">¥{{ (report.price_targets.take_profit_price || 0).toFixed(2) }}</div>
              <div class="pct">+{{ (report.price_targets.take_profit_pct || 0).toFixed(1) }}%</div>
            </div>
          </el-col>
        </el-row>
      </div>

      <!-- 风险与机会评估 -->
      <div class="section">
        <h3>⚠️ 风险评估</h3>
        <div class="markdown-content" v-html="renderMarkdown(report.risk_assessment || '暂无')"></div>
      </div>

      <div class="section">
        <h3>⭐ 机会评估</h3>
        <div class="markdown-content" v-html="renderMarkdown(report.opportunity_assessment || '暂无')"></div>
      </div>

      <!-- 详细分析 -->
      <div class="section" v-if="report.detailed_analysis">
        <h3>📝 详细分析</h3>
        <div class="markdown-content" v-html="renderMarkdown(report.detailed_analysis)"></div>
      </div>

      <div class="section">
        <TaskGrowthPanel :task-id="growthTaskId" />
      </div>

      <!-- 分析时间 -->
      <div class="section">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="分析时间">{{ formatTime(report.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="执行时长">{{ report.execution_time || 0 }} 秒</el-descriptions-item>
        </el-descriptions>
      </div>
    </div>

    <template #footer>
      <el-button @click="handleClose">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { type PositionAnalysisResult } from '@/api/portfolio'
import { marked } from 'marked'
import TaskGrowthPanel from '@/components/growth/TaskGrowthPanel.vue'
import { getMarketByStockCode } from '@/utils/market'

type PositionSnapshot = {
  code?: string
  name?: string
  quantity?: number
  cost_price?: number
  current_price?: number
  market_value?: number
  unrealized_pnl?: number
  unrealized_pnl_pct?: number
  industry?: string
}

// 配置marked选项
marked.setOptions({ breaks: true, gfm: true })

const props = defineProps<{
  modelValue: boolean
  report: (PositionAnalysisResult & { position_snapshot?: PositionSnapshot }) | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()

const visible = ref(false)
const growthTaskId = computed(() => props.report?.task_id || props.report?.analysis_id || null)
const isEtfReport = computed(() => {
  const code = props.report?.position_snapshot?.code
  return !!code && getMarketByStockCode(code) === 'ETF'
})
const securityCodeLabel = computed(() => isEtfReport.value ? 'ETF代码' : '股票代码')
const securityNameLabel = computed(() => isEtfReport.value ? 'ETF名称' : '股票名称')
const industryLabel = computed(() => isEtfReport.value ? '产品分类' : '所属行业')
const industryValue = computed(() => {
  if (isEtfReport.value) return 'ETF/基金'
  return props.report?.position_snapshot?.industry || '未知'
})

watch(() => props.modelValue, (val) => {
  visible.value = val
})

watch(visible, (val) => emit('update:modelValue', val))

const handleClose = () => emit('update:modelValue', false)

// Markdown渲染
const renderMarkdown = (content: string) => {
  if (!content) return ''
  try {
    return marked.parse(content) as string
  } catch (e) {
    return `<pre style="white-space: pre-wrap; font-family: inherit;">${content}</pre>`
  }
}

// 格式化时间
const formatTime = (time: string) => {
  if (!time) return '-'
  const date = new Date(time)
  return date.toLocaleString('zh-CN')
}

// 格式化盈亏
const formatPnl = (pnl: number) => {
  if (pnl === undefined || pnl === null) return '¥0.00'
  const prefix = pnl >= 0 ? '+' : ''
  return `${prefix}¥${Math.abs(pnl).toFixed(2)}`
}

// 格式化百分比
const formatPct = (pct: number) => {
  if (pct === undefined || pct === null) return '0.00%'
  const prefix = pct >= 0 ? '+' : ''
  return `${prefix}${pct.toFixed(2)}%`
}

// 盈亏样式
const pnlClass = (pnl: number) => {
  if (pnl > 0) return 'text-success'
  if (pnl < 0) return 'text-danger'
  return ''
}

// 分析观点样式
const getActionClass = (action: string) => {
  if (action === 'buy' || action === 'add') return 'action-buy'
  if (action === 'sell' || action === 'reduce') return 'action-sell'
  return 'action-hold'
}

// 分析观点文本（兼容新旧术语，统一显示为研究结论倾向）
const getActionText = (action: string) => {
  const map: Record<string, string> = {
    // 旧交易指令/市场观点术语
    buy: '乐观',
    add: '偏多',
    hold: '中性',
    reduce: '偏空',
    sell: '审慎',
    // 旧市场观点术语
    '看涨': '乐观',
    '看跌': '审慎',
    '增持观点': '偏多',
    '减持观点': '偏空',
    '观望观点': '待验证',
    // 新合规术语
    '乐观': '乐观',
    '审慎': '审慎',
    '中性': '中性',
    '偏多': '偏多',
    '偏空': '偏空',
    '待验证': '待验证'
  }
  return map[action] || action
}
</script>

<style scoped>
.analysis-detail {
  max-height: 70vh;
  overflow-y: auto;
}

.section {
  margin-bottom: 24px;
}

.section h3 {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
  color: #303133;
}

.section h4 {
  font-size: 14px;
  font-weight: 500;
  margin: 12px 0 8px 0;
  color: #606266;
}

.text-success {
  color: #67c23a;
}

.text-danger {
  color: #f56c6c;
}

.action-section {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 16px;
}

.action-badge {
  padding: 8px 20px;
  border-radius: 4px;
  font-size: 18px;
  font-weight: 600;
}

.action-buy {
  background: #f0f9ff;
  color: #409eff;
  border: 2px solid #409eff;
}

.action-sell {
  background: #fef0f0;
  color: #f56c6c;
  border: 2px solid #f56c6c;
}

.action-hold {
  background: #f4f4f5;
  color: #909399;
  border: 2px solid #909399;
}

.confidence {
  display: flex;
  align-items: center;
  gap: 8px;
}

.reason-section {
  background: #f5f7fa;
  padding: 16px;
  border-radius: 4px;
}

.target-card {
  padding: 16px;
  border-radius: 8px;
  text-align: center;
}

.target-card .label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 8px;
}

.target-card .value {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 4px;
}

.target-card .pct {
  font-size: 14px;
}

.loss-bg {
  background: #fef0f0;
  color: #f56c6c;
}

.neutral-bg {
  background: #f4f4f5;
  color: #909399;
}

.profit-bg {
  background: #f0f9ff;
  color: #67c23a;
}

.markdown-content {
  line-height: 1.8;
}

.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3),
.markdown-content :deep(h4) {
  margin-top: 16px;
  margin-bottom: 8px;
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  padding-left: 24px;
}

.markdown-content :deep(li) {
  margin: 4px 0;
}

.markdown-content :deep(p) {
  margin: 8px 0;
}

.markdown-content :deep(code) {
  background: #f5f7fa;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Courier New', monospace;
}

.markdown-content :deep(pre) {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  overflow-x: auto;
}

.risk-disclaimer {
  margin-bottom: 24px;
}

.risk-disclaimer :deep(.el-alert) {
  background: linear-gradient(135deg, #fff3cd 0%, #ffe69c 100%);
  border: 2px solid #ffc107;
  border-radius: 12px;
  padding: 16px 20px;
  box-shadow: 0 4px 12px rgba(255, 193, 7, 0.2);
}
</style>

