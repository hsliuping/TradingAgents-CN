<template>
  <div v-loading="loading" class="page-grid">
    <el-result
      v-if="loadError"
      icon="warning"
      title="AlphaGuard 状态暂不可用"
      :sub-title="loadError"
    >
      <template #extra><el-button @click="load">重试</el-button></template>
    </el-result>

    <template v-else>
      <section class="status-band">
        <div>
          <div class="eyebrow">自动模拟运行总览</div>
          <div class="status-title">
            <el-tag :type="readinessType" size="large">{{ readiness?.overall_status || 'UNKNOWN' }}</el-tag>
            <strong>{{ currentTradeDate || '暂无生产交易日' }}</strong>
          </div>
          <p>{{ readinessExplanation }}</p>
        </div>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
      </section>

      <div class="readiness-strip">
        <div v-for="item in readinessFlags" :key="item.label" class="readiness-item">
          <span>{{ item.label }}</span>
          <el-tag :type="item.ready ? 'success' : 'info'" size="small">
            {{ item.ready ? 'READY' : 'NOT READY' }}
          </el-tag>
        </div>
      </div>

      <el-alert
        type="info"
        :closable="false"
        show-icon
        :title="statusNotice"
      />

      <div class="metric-grid">
        <el-card v-for="item in metrics" :key="item.label" shadow="never">
          <el-statistic :title="item.label" :value="item.value" />
          <div class="metric-note">{{ item.note }}</div>
        </el-card>
      </div>

      <section class="two-column">
        <div class="plain-section">
          <div class="section-header"><strong>当前 Proposal 分布</strong><span>{{ proposalTotal }} 条</span></div>
          <div class="proposal-grid">
            <div v-for="item in proposalDistribution" :key="item.status" class="proposal-row">
              <el-tag :type="proposalType(item.status)">{{ item.status }}</el-tag>
              <strong>{{ item.count }}</strong>
            </div>
          </div>
          <el-empty v-if="!proposalDistribution.length" description="尚无生产 Proposal" />
        </div>

        <div class="plain-section">
          <div class="section-header"><strong>模型与风控到达情况</strong><span>只展示真实对象</span></div>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="Normal / Context">{{ sampleCount('ag_decision_contexts') }}</el-descriptions-item>
            <el-descriptions-item label="HardRisk">{{ sampleCount('ag_risk_decisions') }}</el-descriptions-item>
            <el-descriptions-item label="模拟成交">{{ sampleCount('ag_paper_fills') }}</el-descriptions-item>
          </el-descriptions>
          <p class="muted">未到达不会显示为 HOLD 或通过；请在决策链查看每个阶段的阻断原因。</p>
        </div>
      </section>

      <section class="plain-section">
        <div class="section-header"><strong>三个自动模拟账户</strong><span>PAPER · CNY</span></div>
        <el-table :data="accounts" size="small">
          <el-table-column prop="account_type" label="账户" min-width="180" />
          <el-table-column label="可用现金" min-width="130"><template #default="{ row }">¥{{ money(row.cash_available) }}</template></el-table-column>
          <el-table-column label="冻结现金" min-width="120"><template #default="{ row }">¥{{ money(row.cash_reserved) }}</template></el-table-column>
          <el-table-column prop="status" label="状态" width="100" />
          <el-table-column label="实盘" width="100"><template #default><el-tag type="danger" size="small">关闭</el-tag></template></el-table-column>
        </el-table>
      </section>

      <section class="plain-section">
        <div class="section-header"><strong>数据阻断与开放告警</strong><span>{{ notReadyData.length }} 阻断 · {{ overview?.open_alerts.length || 0 }} 告警</span></div>
        <el-table :data="notReadyData" size="small">
          <el-table-column prop="component" label="组件" min-width="190" />
          <el-table-column prop="status" label="状态" width="120" />
          <el-table-column prop="record_count" label="记录数" width="100" />
          <el-table-column label="原因" min-width="300">
            <template #default="{ row }">{{ row.blocking_reasons.join('；') || row.warnings.join('；') }}</template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!notReadyData.length" description="当前没有生产数据阻断" />
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { alphaguardApi, type CandidateEntry, type QuantProposalSummary } from '@/api/alphaguard'
import { alphaguardEvaluationApi, type EvaluationOverview } from '@/api/alphaguardEvaluations'
import { alphaguardPaperApi, type AutomaticPaperAccount } from '@/api/alphaguardPaper'
import { alphaguardOperationsApi, type OperationsOverview } from '@/api/alphaguardOperations'

const loading = ref(false)
const loadError = ref('')
const overview = ref<OperationsOverview | null>(null)
const proposals = ref<QuantProposalSummary[]>([])
const candidates = ref<CandidateEntry[]>([])
const accounts = ref<AutomaticPaperAccount[]>([])
const evaluation = ref<EvaluationOverview | null>(null)
const readiness = computed(() => overview.value?.readiness ?? null)
const readinessType = computed(() => readiness.value?.overall_status === 'READY_FOR_PAPER' ? 'success' : readiness.value?.overall_status === 'UNSAFE' ? 'danger' : 'warning')
const notReadyData = computed(() => (readiness.value?.data_readiness || []).filter(item => item.status !== 'READY'))
const currentTradeDate = computed(() => proposals.value.map(item => item.trade_date || '').sort().slice(-1)[0]?.slice(0, 10) || '')
const currentProposals = computed(() => proposals.value.filter(item => (item.trade_date || '').slice(0, 10) === currentTradeDate.value))
const proposalTotal = computed(() => currentProposals.value.length)
const proposalDistribution = computed(() => {
  const counts: Record<string, number> = {}
  for (const item of currentProposals.value) counts[item.status] = (counts[item.status] || 0) + 1
  return Object.entries(counts).map(([status, count]) => ({ status, count }))
})
const requiredData = new Set(['TRADING_CALENDAR', 'QFQ_PRICE_DATA', 'RAW_PRICE_DATA', 'FINANCIAL_DATA', 'NEWS_DATA', 'ANNOUNCEMENT_DATA', 'MARKET_CONTEXT', 'MODEL_PROVIDER', 'CHAMPION_ASSIGNMENTS'])
const dataReady = computed(() => {
  const ready = new Set((readiness.value?.data_readiness || []).filter(item => item.status === 'READY').map(item => item.component))
  return [...requiredData].every(item => ready.has(item))
})
const regimeReady = computed(() => currentProposals.value.length > 0 && currentProposals.value.some(item => !item.reason_codes?.includes('REGIME_INSUFFICIENT_DATA')))
const readinessFlags = computed(() => [
  { label: 'DATA', ready: dataReady.value },
  { label: 'PAPER', ready: Boolean(readiness.value?.paper_execution_ready) },
  { label: 'EVALUATION', ready: Boolean(readiness.value?.evaluation_ready) },
  { label: 'REGIME', ready: regimeReady.value },
  { label: 'EXPERIMENT', ready: Boolean(readiness.value?.experiment_ready) },
  { label: 'CHALLENGER', ready: Boolean(readiness.value?.challenger_ready) },
  { label: 'LIVE', ready: false }
])
const metrics = computed(() => [
  { label: '候选标的', value: candidates.value.length || sampleCount('ag_candidates'), note: 'USER_SELECTED 候选' },
  { label: '当前日 Snapshot', value: new Set(candidates.value.map(item => item.latest_snapshot_id).filter(Boolean)).size || new Set(currentProposals.value.map(item => item.snapshot_id)).size, note: currentTradeDate.value || '尚无交易日' },
  { label: '评价样本', value: evaluation.value?.evaluated_subjects ?? 0, note: '历史研究与生产评价主体' },
  { label: '开放告警', value: overview.value?.open_alerts.length ?? 0, note: '未解决运维告警' }
])
const readinessExplanation = computed(() => readiness.value?.overall_status === 'DEGRADED_PAPER'
  ? '系统可以运行，但部分决策能力因数据或版本条件保持安全关闭。'
  : '所有状态均来自后端 readiness，不由页面人工改写。')
const statusNotice = computed(() => regimeReady.value
  ? 'DEGRADED_PAPER 不是系统故障：当前数据与 Regime 可展示；Challenger 和实盘仍按安全边界保持关闭。'
  : 'DEGRADED_PAPER 不是系统故障：自动模拟、评价和数据链可运行；Regime 当前因数据或版本条件 fail-closed，Challenger 与实盘保持关闭。')

function sampleCount(key: string) { return overview.value?.sample_counts[key] ?? 0 }
function money(value: string | number | null | undefined) { const n = Number(value ?? 0); return Number.isFinite(n) ? n.toFixed(2) : '0.00' }
function proposalType(status: string) { return status === 'TRIGGERED' ? 'success' : status === 'INSUFFICIENT_DATA' ? 'warning' : status === 'REJECTED' ? 'danger' : 'info' }

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const [overviewRes, candidateRes, proposalRes, accountRes, evaluationRes] = await Promise.all([
      alphaguardOperationsApi.overview(),
      alphaguardApi.candidates({ limit: 500 }),
      alphaguardApi.quantProposals({ limit: 500 }),
      alphaguardPaperApi.getAccounts(),
      alphaguardEvaluationApi.overview()
    ])
    overview.value = overviewRes.data
    candidates.value = candidateRes.data.items
    proposals.value = proposalRes.data.items
    accounts.value = accountRes.data.items.filter(item => item.account_type !== 'PAPER_CHALLENGER')
    evaluation.value = evaluationRes.data
  } catch (error: any) {
    loadError.value = `${error?.message || '未知错误'}；请到运维中心检查 error_code 与 trace_id。`
  } finally { loading.value = false }
}

onMounted(load)
</script>

<style scoped>
.page-grid { display: grid; gap: 16px; }
.status-band { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; padding: 20px 0; border-bottom: 1px solid var(--el-border-color-light); }
.eyebrow { color: var(--el-text-color-secondary); font-size: 13px; margin-bottom: 8px; }
.status-title { display: flex; align-items: center; gap: 12px; font-size: 20px; }
.status-band p, .muted { color: var(--el-text-color-secondary); margin: 10px 0 0; }
.readiness-strip { display: grid; grid-template-columns: repeat(7, minmax(110px, 1fr)); gap: 8px; overflow-x: auto; }
.readiness-item { min-width: 110px; padding: 10px 12px; border: 1px solid var(--el-border-color-light); border-radius: 6px; display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.metric-grid { display: grid; grid-template-columns: repeat(4, minmax(150px, 1fr)); gap: 12px; }
.metric-note { color: var(--el-text-color-secondary); font-size: 12px; margin-top: 8px; }
.two-column { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
.plain-section { padding: 16px 0; border-top: 1px solid var(--el-border-color-light); }
.section-header { display: flex; justify-content: space-between; gap: 16px; margin-bottom: 12px; color: var(--el-text-color-secondary); }
.section-header strong { color: var(--el-text-color-primary); }
.proposal-grid { display: grid; gap: 8px; }
.proposal-row { display: flex; align-items: center; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--el-border-color-extra-light); }
@media (max-width: 900px) { .metric-grid { grid-template-columns: repeat(2, 1fr); } .two-column { grid-template-columns: 1fr; } .readiness-strip { grid-template-columns: repeat(7, 130px); } }
@media (max-width: 560px) { .status-band { flex-direction: column; } .metric-grid { grid-template-columns: 1fr; } }
</style>
