<template>
  <div class="card my-position-card">
    <div class="card-header">
      <div class="section-title">
        <span>💼</span>
        <span>我的持仓</span>
        <el-tag v-if="hasPosition" size="small" :type="isPnlUp ? 'danger' : 'info'" effect="plain" class="pnl-tag">
          {{ isPnlUp ? '浮盈' : '浮亏' }} {{ formatPct(real.unrealized_pnl_pct) }}
        </el-tag>
      </div>
      <span class="header-meta">{{ positionSource }}</span>
    </div>

    <div class="card-body">
      <!-- 有持仓：真实持仓数据 -->
      <div v-if="hasPosition" class="pos-grid">
        <div>
          <div class="pos-num">
            {{ formatQty(real.quantity) }}
            <span class="pos-sub">成本 ¥{{ fmt2(real.cost_price) }}</span>
          </div>
          <div class="pos-line">
            现价 ¥{{ fmt2(currentPrice) }} ·
            <span :class="isPnlUp ? 'up' : 'down'">{{ formatPnl(real.unrealized_pnl) }}</span>
          </div>
          <div class="pos-subline">
            持仓市值 ¥{{ fmtAmount(real.market_value) }}<template v-if="holdMetaText"> · {{ holdMetaText }}</template>
          </div>
        </div>
        <div>
          <div class="pos-label">成本 vs 现价</div>
          <div class="pos-text">
            成本 ¥{{ fmt2(real.cost_price) }}，现价 ¥{{ fmt2(currentPrice) }}，
            <span v-if="costGapPct > 0" class="up">现价高于成本 {{ costGapPct.toFixed(1) }}%</span>
            <span v-else class="down">现价低于成本 {{ Math.abs(costGapPct).toFixed(1) }}%（成本偏高）</span>。
          </div>
        </div>
        <div>
          <div class="pos-label">研究结论（AI 持仓分析）</div>
          <div v-if="positionSummary.has" class="pos-text">
            {{ positionSummary.conclusion || '已生成持仓分析，可在「我的研究」查看完整结论与风险点。' }}
          </div>
          <div v-else class="pos-text pos-muted">还没有针对此持仓的 AI 研究结论，可在「我的研究」发起持仓分析。</div>
        </div>
        <div class="pos-actions">
          <el-button size="small" type="primary" plain @click="$emit('go-position-analysis')">持仓分析</el-button>
          <el-button size="small" plain @click="$emit('go-trade-review')">操作复盘</el-button>
        </div>
      </div>

      <!-- 无持仓：引导空态 -->
      <div v-else class="pos-empty">
        <el-icon :size="30" color="#c0c4cc"><Briefcase /></el-icon>
        <div class="pe-text">你还没有持有这只{{ isEtf ? 'ETF' : '股票' }}</div>
        <div class="pe-sub">记录持仓后，这里会显示成本、浮盈亏、与现价对比和研究对账。</div>
        <el-button size="small" type="primary" plain @click="$emit('add-position')">
          <el-icon><Plus /></el-icon>&nbsp;添加持仓
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Briefcase, Plus } from '@element-plus/icons-vue'

interface PositionBlock {
  has: boolean
  quantity: number
  cost_price: number
  current_price: number
  market_value: number
  unrealized_pnl: number
  unrealized_pnl_pct: number
}

interface PositionSummaryState {
  has: boolean
  conclusion: string
}

const props = defineProps<{
  real: PositionBlock
  isEtf: boolean
  quotePrice: number
  positionSummary: PositionSummaryState
  firstBuyDate?: string | null
  weightPct?: number | null
}>()

defineEmits<{
  (e: 'add-position'): void
  (e: 'go-position-analysis'): void
  (e: 'go-trade-review'): void
}>()

const hasPosition = computed(() => props.real.has && props.real.quantity > 0)
const currentPrice = computed(() => Number.isFinite(props.real.current_price) && props.real.current_price > 0
  ? props.real.current_price
  : props.quotePrice)
const isPnlUp = computed(() => Number(props.real.unrealized_pnl) >= 0)
const costGapPct = computed(() => {
  const cost = Number(props.real.cost_price)
  const cur = Number(currentPrice.value)
  if (!cost || !Number.isFinite(cur)) return 0
  return ((cur - cost) / cost) * 100
})
const positionSource = computed(() => props.real.has ? '来自实盘持仓 · 操作留痕见「我的研究」' : '')

// 持有天数（买入当日算第 1 天）与仓位占比（本股市值 / 组合持仓总市值）
const holdDays = computed(() => {
  if (!props.firstBuyDate) return null
  const d = new Date(props.firstBuyDate)
  if (Number.isNaN(d.getTime())) return null
  const diff = Math.floor((Date.now() - d.getTime()) / 86400000)
  return diff >= 0 ? diff + 1 : null
})
const holdMetaText = computed(() => {
  const parts: string[] = []
  if (holdDays.value != null) parts.push(`持有 ${holdDays.value} 天`)
  const w = Number(props.weightPct)
  if (props.weightPct != null && Number.isFinite(w)) parts.push(`占组合 ${w.toFixed(1)}%`)
  return parts.join(' · ')
})

function fmt2(v: any) {
  const n = Number(v)
  return Number.isFinite(n) ? n.toFixed(2) : '—'
}
function formatQty(v: any) {
  const n = Number(v)
  return Number.isFinite(n) ? n.toLocaleString('zh-CN') + ' 股' : '—'
}
function formatPct(v: any) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '—'
  return `${n > 0 ? '+' : ''}${n.toFixed(2)}%`
}
function formatPnl(v: any) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '—'
  const sign = n > 0 ? '+' : ''
  return `${sign}¥${n.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}`
}
function fmtAmount(v: any) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '—'
  if (n >= 1e8) return (n / 1e8).toFixed(2) + ' 亿'
  if (n >= 1e4) return (n / 1e4).toFixed(1) + ' 万'
  return n.toFixed(0)
}
</script>

<style scoped>
.card {
  background: var(--el-bg-color, #fff);
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, .05);
  border: 1px solid #f1f5f9;
  overflow: hidden;
}
.card-header {
  padding: 14px 20px 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.section-title { font-size: 15px; font-weight: 700; display: flex; align-items: center; gap: 8px; color: #1e293b; }
.pnl-tag { margin-left: 4px; }
.header-meta { font-size: 11px; color: #94a3b8; }
.card-body { padding: 14px 20px 18px; }

.pos-grid {
  display: grid;
  grid-template-columns: 1.1fr 1.3fr 1.8fr auto;
  gap: 20px;
  align-items: start;
}
.pos-num { font-size: 22px; font-weight: 700; color: #1e293b; }
.pos-sub { font-size: 13px; font-weight: 400; color: #94a3b8; margin-left: 6px; }
.pos-line { font-size: 13px; margin-top: 4px; color: #1e293b; }
.pos-subline { font-size: 12px; color: #94a3b8; margin-top: 2px; }
.pos-label { font-size: 12px; color: #94a3b8; margin-bottom: 6px; }
.pos-text { font-size: 13px; line-height: 1.7; color: #303133; }
.pos-muted { color: #94a3b8; }
.up { color: #f56c6c; }
.down { color: #909399; }
.pos-actions { display: flex; flex-direction: column; gap: 8px; }

.pos-empty { text-align: center; padding: 24px 0; color: #94a3b8; }
.pe-text { font-size: 14px; font-weight: 600; color: #64748b; margin: 10px 0 4px; }
.pe-sub { font-size: 12px; margin-bottom: 14px; }

@media (max-width: 1100px) {
  .pos-grid { grid-template-columns: 1fr 1fr; }
  .pos-actions { flex-direction: row; grid-column: 1 / -1; }
}
</style>
