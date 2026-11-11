<template>
  <div class="ov-strip">
    <!-- 左：紧凑指标条 -->
    <div class="metric-strip">
      <div class="metric-cell">
        <div class="mc-label">PE-TTM</div>
        <div class="mc-value" :class="{ 'is-loss': isLoss }">
          {{ peText }}
        </div>
        <div class="mc-state" :class="isLoss ? 'state-warn' : 'state-muted'">
          {{ isLoss ? '亏损期 · PE 失真' : valuationText }}
        </div>
      </div>
      <div class="metric-cell">
        <div class="mc-label">PB</div>
        <div class="mc-value">{{ fmtNum(basics.pb) }}</div>
        <div class="mc-state state-muted">市净率</div>
      </div>
      <div class="metric-cell">
        <div class="mc-label">ROE</div>
        <div class="mc-value">{{ fmtPercent(basics.roe) }}</div>
        <div class="mc-state" :class="roeClass">{{ roeText }}</div>
      </div>
      <div class="metric-cell">
        <div class="mc-label">总市值</div>
        <div class="mc-value">{{ fmtAmount(basics.marketCap) }}</div>
        <div class="mc-state state-muted">最新报告期 {{ basics.reportPeriod || '—' }}</div>
      </div>
    </div>

    <!-- 右：需要你知道的风险（真实数据驱动；行业专属风险通过插槽注入） -->
    <div class="risk-panel">
      <div class="rp-head">
        <span class="rp-title"><el-icon><WarningFilled /></el-icon>&nbsp;需要你知道的风险</span>
      </div>
      <!-- 行业世界模型注入的专属风险（如猪周期保险丝/升水灯） -->
      <slot name="industry-risks" />
      <!-- 通用财务/行情风险 -->
      <template v-if="riskItems.length">
        <div v-for="(item, i) in riskItems" :key="'g' + i" class="risk-item">
          <span class="risk-dot" :class="'is-' + item.level"></span>
          <div class="ri-body">{{ item.text }}</div>
        </div>
      </template>
      <div v-if="!riskItems.length && !$slots['industry-risks']" class="risk-empty">
        暂无需特别提示的财务/行情风险。信号由规则与行业研究自动汇总，不构成投资建议。
      </div>
      <div class="rp-foot">档位与提示仅作研究参考，不构成投资建议</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { WarningFilled } from '@element-plus/icons-vue'

interface BasicsData {
  industry: string
  sector: string
  marketCap: number
  pe: number
  pb: number
  ps: number
  roe: number
  debtRatio: number
  dividendYield: number
  currentRatio: number
  reportPeriod: string
}

interface FinancialSnapshotData {
  grossMargin: number
  netprofitMargin: number
  revenue: number
  netProfit: number
}

interface QuoteData {
  price: number
  changePercent: number
}

const props = defineProps<{
  basics: BasicsData
  financialSnapshot: FinancialSnapshotData
  quote: QuoteData
}>()

function fmtNum(v: any) {
  const n = Number(v)
  return Number.isFinite(n) ? n.toFixed(2) : '—'
}
function fmtPercent(v: any) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '—'
  return `${n > 0 ? '+' : ''}${n.toFixed(1)}%`
}
function fmtAmount(v: any) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '—'
  if (n >= 1e8) return (n / 1e8).toFixed(1) + ' 亿'
  if (n >= 1e4) return (n / 1e4).toFixed(1) + ' 万'
  return n.toFixed(0)
}

const peNum = computed(() => Number(props.basics.pe))
const isLoss = computed(() => Number.isFinite(peNum.value) && peNum.value < 0)
const peText = computed(() => {
  if (!Number.isFinite(peNum.value)) return '—'
  return isLoss.value ? '亏损' : peNum.value.toFixed(1)
})
const valuationText = computed(() => {
  const pe = peNum.value
  if (!Number.isFinite(pe)) return '暂无估值数据'
  if (pe < 15) return '估值偏低区间'
  if (pe < 30) return '估值中性区间'
  return '估值偏高区间'
})

const roeClass = computed(() => {
  const roe = Number(props.basics.roe)
  if (!Number.isFinite(roe) || roe < 0) return 'state-warn'
  return roe >= 15 ? 'state-good' : 'state-muted'
})
const roeText = computed(() => {
  const roe = Number(props.basics.roe)
  if (!Number.isFinite(roe)) return '暂无数据'
  if (roe < 0) return '净资产收益率为负'
  if (roe >= 15) return '盈利能力较强'
  if (roe >= 8) return '盈利能力良好'
  return '盈利能力偏弱'
})

// 通用风险项：全部基于真实财务/行情字段，缺失则不产生提示
interface RiskItem { level: 'red' | 'orange' | 'gray'; text: string }
const riskItems = computed<RiskItem[]>(() => {
  const items: RiskItem[] = []
  // 亏损
  if (isLoss.value) {
    items.push({ level: 'orange', text: '公司最近四个季度整体亏损，PE 估值参考意义有限，建议结合 PB、行业专属估值标尺与现金流一起看。' })
  }
  // 净利润为负（与 PE 互证，避免重复，仅在无 PE 时提示）
  const netProfit = Number(props.financialSnapshot.netProfit)
  if (!isLoss.value && Number.isFinite(netProfit) && netProfit < 0) {
    items.push({ level: 'orange', text: '最新报告期净利润为负，关注后续盈利改善节奏与现金流安全。' })
  }
  // 高负债率
  const debt = Number(props.basics.debtRatio)
  if (Number.isFinite(debt) && debt >= 60) {
    items.push({ level: 'orange', text: `资产负债率 ${debt.toFixed(0)}%，处于偏高区间，关注偿债压力与融资成本。` })
  }
  // 当日价格异动（涨跌幅超过 7%）
  const chg = Number(props.quote.changePercent)
  if (Number.isFinite(chg) && Math.abs(chg) >= 7) {
    items.push({
      level: chg <= -7 ? 'red' : 'orange',
      text: `今日价格${chg > 0 ? '大幅上涨' : '大幅下跌'} ${chg.toFixed(2)}%，注意短期波动，先看清是否有基本面变化再决定。`,
    })
  }
  // 盈利能力弱
  const roe = Number(props.basics.roe)
  if (Number.isFinite(roe) && roe >= 0 && roe < 5) {
    items.push({ level: 'gray', text: `ROE 仅 ${roe.toFixed(1)}%，资本回报水平偏低。` })
  }
  return items
})
</script>

<style scoped>
.ov-strip {
  display: grid;
  grid-template-columns: 3fr 2fr;
  gap: 16px;
  align-items: stretch;
  margin-bottom: 16px;
}
.metric-strip {
  background: var(--el-bg-color, #fff);
  border: 1px solid var(--el-border-color-lighter, #f1f5f9);
  border-radius: 12px;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  overflow: hidden;
}
.metric-cell {
  padding: 14px 16px;
  border-right: 1px solid var(--el-border-color-lighter, #f1f5f9);
}
.metric-cell:last-child { border-right: none; }
.mc-label {
  font-size: 12px;
  color: var(--el-text-color-secondary, #94a3b8);
  margin-bottom: 6px;
}
.mc-value {
  font-size: 20px;
  font-weight: 700;
  line-height: 1.2;
  color: var(--el-text-color-primary, #1e293b);
  font-variant-numeric: tabular-nums;
}
.mc-value.is-loss { color: var(--el-text-color-secondary, #909399); }
.mc-state { font-size: 12px; margin-top: 4px; line-height: 1.5; }
.state-muted { color: var(--el-text-color-secondary, #94a3b8); }
.state-good { color: #67c23a; }
.state-warn { color: #e6a23c; }

.risk-panel {
  background: var(--el-bg-color, #fff);
  border: 1px solid var(--el-border-color-lighter, #f1f5f9);
  border-radius: 12px;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
}
.rp-head { margin-bottom: 6px; }
.rp-title { font-size: 13px; font-weight: 700; color: var(--el-text-color-primary, #1e293b); display: flex; align-items: center; gap: 2px; }
.rp-title .el-icon { color: #e6a23c; }
.risk-item {
  display: flex;
  gap: 8px;
  padding: 7px 0;
  border-top: 1px dashed var(--el-border-color-lighter, #eef2f7);
  align-items: flex-start;
}
.risk-dot { width: 8px; height: 8px; border-radius: 50%; margin-top: 5px; flex: none; }
.risk-dot.is-red { background: #f56c6c; box-shadow: 0 0 0 3px rgba(245, 108, 108, .15); }
.risk-dot.is-orange { background: #e6a23c; box-shadow: 0 0 0 3px rgba(230, 162, 60, .15); }
.risk-dot.is-gray { background: #909399; }
.ri-body { font-size: 12px; line-height: 1.6; color: var(--el-text-color-regular, #606266); }
.risk-empty { font-size: 12px; color: var(--el-text-color-secondary, #94a3b8); line-height: 1.7; padding: 8px 0; }
.rp-foot { margin-top: auto; padding-top: 8px; font-size: 11px; color: var(--el-text-color-placeholder, #c0c4cc); }

@media (max-width: 1100px) {
  .ov-strip { grid-template-columns: 1fr; }
}
@media (max-width: 768px) {
  .metric-strip { grid-template-columns: repeat(2, 1fr); }
  .metric-cell:nth-child(2) { border-right: none; }
  .metric-cell:nth-child(1), .metric-cell:nth-child(2) { border-bottom: 1px solid var(--el-border-color-lighter, #f1f5f9); }
}
</style>
