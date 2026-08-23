<template>
  <div class="card metrics-card">
    <div class="card-header">
      <div class="section-title">
        <span>📊</span>
        <span>核心指标</span>
      </div>
      <el-tooltip v-if="basics.reportPeriod" :content="`最新财报期：${basics.reportPeriod}`" placement="top">
        <el-tag size="small" type="info" effect="plain">{{ basics.reportPeriod }}</el-tag>
      </el-tooltip>
    </div>
    <div class="card-body">
      <div class="metrics-grid">
        <!-- 估值 -->
        <div class="metric-card">
          <div class="metric-card-header">
            <span class="metric-name">估值</span>
            <span class="metric-status" :class="valuationStatus.cls">{{ valuationStatus.text }}</span>
          </div>
          <div class="metric-values">
            <div class="metric-value-item">
              <div class="metric-value-label">PE(TTM)</div>
              <el-tooltip :content="fmtNum(basics.pe)" placement="top" :show-after="300">
                <div class="metric-value-number">
                  {{ fmtNum(basics.pe) }}
                  <el-tag v-if="basics.peIsRealtime" type="success" size="small" style="margin-left:4px">实时</el-tag>
                </div>
              </el-tooltip>
            </div>
            <div class="metric-value-item">
              <div class="metric-value-label">PB</div>
              <el-tooltip :content="fmtNum(basics.pb)" placement="top" :show-after="300">
                <div class="metric-value-number">{{ fmtNum(basics.pb) }}</div>
              </el-tooltip>
            </div>
            <div class="metric-value-item">
              <div class="metric-value-label">PS</div>
              <el-tooltip :content="fmtNum(basics.ps)" placement="top" :show-after="300">
                <div class="metric-value-number">{{ fmtNum(basics.ps) }}</div>
              </el-tooltip>
            </div>
          </div>
          <div class="metric-bar">
            <div class="metric-bar-fill" :style="{ width: valuationBar, background: valuationBarColor }"></div>
          </div>
        </div>

        <!-- 盈利能力 -->
        <div class="metric-card">
          <div class="metric-card-header">
            <span class="metric-name">盈利能力</span>
            <span class="metric-status" :class="profitStatus.cls">{{ profitStatus.text }}</span>
          </div>
          <div class="metric-values">
            <div class="metric-value-item">
              <div class="metric-value-label">ROE</div>
              <el-tooltip :content="fmtPercent(basics.roe)" placement="top" :show-after="300">
                <div class="metric-value-number">{{ fmtPercent(basics.roe) }}</div>
              </el-tooltip>
            </div>
            <div class="metric-value-item">
              <div class="metric-value-label">毛利率</div>
              <el-tooltip :content="fmtPercent(financialSnapshot.grossMargin)" placement="top" :show-after="300">
                <div class="metric-value-number">{{ fmtPercent(financialSnapshot.grossMargin) }}</div>
              </el-tooltip>
            </div>
            <div class="metric-value-item">
              <div class="metric-value-label">净利率</div>
              <el-tooltip :content="fmtPercent(financialSnapshot.netprofitMargin)" placement="top" :show-after="300">
                <div class="metric-value-number">{{ fmtPercent(financialSnapshot.netprofitMargin) }}</div>
              </el-tooltip>
            </div>
          </div>
          <div class="metric-bar">
            <div class="metric-bar-fill" :style="{ width: profitBar, background: profitBarColor }"></div>
          </div>
        </div>

        <!-- 财务健康 -->
        <div class="metric-card">
          <div class="metric-card-header">
            <span class="metric-name">财务健康</span>
            <span class="metric-status" :class="healthStatus.cls">{{ healthStatus.text }}</span>
          </div>
          <div class="metric-values">
            <div class="metric-value-item">
              <div class="metric-value-label">负债率</div>
              <el-tooltip :content="fmtPercent(basics.debtRatio)" placement="top" :show-after="300">
                <div class="metric-value-number">{{ fmtPercent(basics.debtRatio) }}</div>
              </el-tooltip>
            </div>
            <div class="metric-value-item">
              <div class="metric-value-label">流动比率</div>
              <el-tooltip :content="fmtRatio(basics.currentRatio)" placement="top" :show-after="300">
                <div class="metric-value-number">{{ fmtRatio(basics.currentRatio) }}</div>
              </el-tooltip>
            </div>
            <div class="metric-value-item">
              <div class="metric-value-label">股息率</div>
              <el-tooltip :content="fmtPercent(basics.dividendYield)" placement="top" :show-after="300">
                <div class="metric-value-number">{{ fmtPercent(basics.dividendYield) }}</div>
              </el-tooltip>
            </div>
          </div>
          <div class="metric-bar">
            <div class="metric-bar-fill" :style="{ width: healthBar, background: healthBarColor }"></div>
          </div>
        </div>

        <!-- 经营规模 -->
        <div class="metric-card">
          <div class="metric-card-header">
            <span class="metric-name">经营规模</span>
          </div>
          <div class="metric-values">
            <div class="metric-value-item">
              <div class="metric-value-label">总市值</div>
              <el-tooltip :content="fmtAmount(basics.marketCap)" placement="top" :show-after="300">
                <div class="metric-value-number">{{ fmtAmount(basics.marketCap) }}</div>
              </el-tooltip>
            </div>
            <div class="metric-value-item">
              <div class="metric-value-label">营收</div>
              <el-tooltip :content="fmtAmount(financialSnapshot.revenue)" placement="top" :show-after="300">
                <div class="metric-value-number">{{ fmtAmount(financialSnapshot.revenue) }}</div>
              </el-tooltip>
            </div>
            <div class="metric-value-item">
              <div class="metric-value-label">净利润</div>
              <el-tooltip :content="fmtAmount(financialSnapshot.netProfit)" placement="top" :show-after="300">
                <div class="metric-value-number">{{ fmtAmount(financialSnapshot.netProfit) }}</div>
              </el-tooltip>
            </div>
          </div>
          <div class="metric-bar">
            <div class="metric-bar-fill" :style="{ width: '70%', background: '#3b82f6' }"></div>
          </div>
          <div v-if="financialSnapshot.annDate" class="metric-footer">
            财报公告：{{ financialSnapshot.annDate }}
          </div>
        </div>
      </div>

      <!-- 因子提示信息 -->
      <div v-if="factorWarningEntries.length || factorDiagnosticEntries.length" class="factor-hints">
        <div class="factor-hints-title">提示信息</div>
        <div class="factor-hints-list">
          <el-popover
            v-for="warning in factorWarningEntries"
            :key="warning.key"
            placement="top-start"
            width="320"
            trigger="hover"
          >
            <template #reference>
              <el-tag :type="warning.tagType" effect="plain" class="factor-hint-tag">{{ warning.label }}</el-tag>
            </template>
            <div class="factor-hint-popover">
              <div class="factor-hint-popover-title">{{ warning.label }}</div>
              <div v-for="condition in warning.conditions" :key="condition" class="factor-hint-line">{{ condition }}</div>
            </div>
          </el-popover>
          <el-popover
            v-for="diagnostic in factorDiagnosticEntries"
            :key="diagnostic.key"
            placement="top-start"
            width="340"
            trigger="hover"
          >
            <template #reference>
              <el-tag :type="diagnostic.tagType" effect="plain" class="factor-hint-tag">{{ diagnostic.label }}</el-tag>
            </template>
            <div class="factor-hint-popover">
              <div class="factor-hint-popover-title">{{ diagnostic.label }}</div>
              <div class="factor-hint-line">状态：{{ diagnostic.state }}</div>
              <div v-if="diagnostic.reason" class="factor-hint-line">原因：{{ diagnostic.reason }}</div>
              <div v-if="diagnostic.missingInputs.length" class="factor-hint-line">缺失输入：{{ diagnostic.missingInputs.join('、') }}</div>
            </div>
          </el-popover>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

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
  peIsRealtime: boolean
}

interface FinancialSnapshotData {
  annDate: string
  dataSource: string
  grossMargin: number
  netprofitMargin: number
  revenue: number
  netProfit: number
  nCashflowAct: number
  totalAssets: number
  totalLiab: number
}

const props = defineProps<{
  basics: BasicsData
  financialSnapshot: FinancialSnapshotData
  factorWarningEntries: Array<{ key: string; label: string; tagType: any; conditions: string[] }>
  factorDiagnosticEntries: Array<{ key: string; label: string; tagType: any; state: string; reason?: string; missingInputs: string[] }>
}>()

function fmtNum(v: any) {
  const n = Number(v)
  return Number.isFinite(n) ? n.toFixed(2) : '-'
}

function fmtPercent(v: any) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '-'
  return `${n > 0 ? '+' : ''}${n.toFixed(2)}%`
}

function fmtRatio(v: any) {
  const n = Number(v)
  return Number.isFinite(n) ? n.toFixed(2) : '-'
}

function fmtAmount(v: any) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '-'
  if (n >= 1e8) return (n / 1e8).toFixed(2) + '亿'
  if (n >= 1e4) return (n / 1e4).toFixed(2) + '万'
  return n.toFixed(2)
}

// 估值状态：PE 越低越便宜（简化判断）
const valuationStatus = computed(() => {
  const pe = props.basics.pe
  if (!Number.isFinite(pe)) return { text: '无数据', cls: 'status-mid' }
  if (pe < 0) return { text: '亏损', cls: 'status-bad' }
  if (pe < 15) return { text: '低估', cls: 'status-good' }
  if (pe < 30) return { text: '中性', cls: 'status-mid' }
  return { text: '偏高', cls: 'status-bad' }
})

const valuationBar = computed(() => {
  const pe = props.basics.pe
  if (!Number.isFinite(pe) || pe < 0) return '0%'
  const pct = Math.min(100, (pe / 50) * 100)
  return pct + '%'
})

const valuationBarColor = computed(() => {
  const cls = valuationStatus.value.cls
  if (cls === 'status-good') return '#3b82f6'
  if (cls === 'status-bad') return '#ef4444'
  return '#f59e0b'
})

// 盈利能力状态
const profitStatus = computed(() => {
  const roe = props.basics.roe
  if (!Number.isFinite(roe)) return { text: '无数据', cls: 'status-mid' }
  if (roe >= 15) return { text: '优秀', cls: 'status-good' }
  if (roe >= 8) return { text: '良好', cls: 'status-mid' }
  if (roe > 0) return { text: '偏弱', cls: 'status-bad' }
  return { text: '亏损', cls: 'status-bad' }
})

const profitBar = computed(() => {
  const roe = props.basics.roe
  if (!Number.isFinite(roe) || roe < 0) return '0%'
  return Math.min(100, (roe / 20) * 100) + '%'
})

const profitBarColor = computed(() => {
  const cls = profitStatus.value.cls
  if (cls === 'status-good') return '#3b82f6'
  if (cls === 'status-bad') return '#ef4444'
  return '#f59e0b'
})

// 财务健康状态
const healthStatus = computed(() => {
  const debt = props.basics.debtRatio
  if (!Number.isFinite(debt)) return { text: '无数据', cls: 'status-mid' }
  if (debt < 40) return { text: '健康', cls: 'status-good' }
  if (debt < 60) return { text: '中性', cls: 'status-mid' }
  return { text: '偏高', cls: 'status-bad' }
})

const healthBar = computed(() => {
  const debt = props.basics.debtRatio
  if (!Number.isFinite(debt) || debt < 0) return '0%'
  return Math.min(100, debt) + '%'
})

const healthBarColor = computed(() => {
  const cls = healthStatus.value.cls
  if (cls === 'status-good') return '#3b82f6'
  if (cls === 'status-bad') return '#ef4444'
  return '#f59e0b'
})
</script>

<style scoped>
.card {
  background: var(--el-bg-color, #fff);
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  border: 1px solid #f1f5f9;
  overflow: hidden;
}

.card-header {
  padding: 14px 20px;
  border-bottom: 1px solid #f1f5f9;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.section-title {
  font-size: 15px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 8px;
  color: #1e293b;
}

.card-body {
  padding: 16px 20px;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.metric-card {
  padding: 12px 10px;
  border-radius: 8px;
  background: #f8fafc;
  border: 1px solid #f1f5f9;
}

.metric-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.metric-name {
  font-size: 12px;
  color: #64748b;
  font-weight: 600;
}

.metric-status {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  font-weight: 600;
}

.status-good {
  background: #eff6ff;
  color: #3b82f6;
}

.status-mid {
  background: #fffbeb;
  color: #f59e0b;
}

.status-bad {
  background: #fef2f2;
  color: #ef4444;
}

.metric-values {
  display: flex;
  gap: 8px;
}

.metric-value-item {
  flex: 1;
  min-width: 0;
}

.metric-value-label {
  font-size: 10px;
  color: #94a3b8;
}

.metric-value-number {
  font-size: 13px;
  font-weight: 700;
  margin-top: 2px;
  color: #1e293b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.metric-bar {
  height: 3px;
  background: #f1f5f9;
  border-radius: 2px;
  margin-top: 8px;
  overflow: hidden;
}

.metric-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.4s;
}

.metric-footer {
  font-size: 10px;
  color: #94a3b8;
  margin-top: 6px;
  border-top: 1px dashed #f1f5f9;
  padding-top: 4px;
}

.factor-hints {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px dashed #f1f5f9;
}

.factor-hints-title {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 8px;
}

.factor-hints-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.factor-hint-tag {
  cursor: help;
}

.factor-hint-popover-title {
  font-weight: 700;
  margin-bottom: 6px;
}

.factor-hint-line {
  font-size: 12px;
  color: #64748b;
  margin-top: 4px;
}

@media (max-width: 1024px) {
  .metrics-grid {
    grid-template-columns: 1fr;
  }
}
</style>
