<template>
  <div v-loading="loading" class="evaluation-center">
    <el-alert type="warning" :closable="false" show-icon>
      PR-007 结果仅用于离线评价与规则化诊断，不代表严格因果，也不会回写交易决策、
      账户、持仓或订单。
    </el-alert>

    <div class="boundary-grid">
      <div><span>历史研究回放</span><strong>{{ overview?.historical_research_subjects ?? 0 }}</strong><small>研究 lineage，不是账户收益</small></div>
      <div><span>正式生产评价</span><strong>{{ overview?.production_subjects ?? 0 }}</strong><small>真实生产决策对象</small></div>
      <div>
        <span>实际模拟成交评价</span>
        <strong>{{ overview?.actual_trade_subjects ?? 0 }}</strong>
        <small>{{ (overview?.actual_trade_subjects ?? 0) > 0 ? '按实际模拟成交登记' : '当前没有成交' }}</small>
      </div>
    </div>

    <el-card v-if="research.report" shadow="never">
      <template #header><div class="header"><span>Canonical 历史研究报告</span><el-tag type="info">RESEARCH ONLY</el-tag></div></template>
      <el-alert
        v-if="versionDiscontinuityCount"
        type="warning"
        :closable="false"
        show-icon
        :title="`PENDING_VERSION_DISCONTINUITY：${versionDiscontinuityCount} 个 20D 标签保留待处理，不是页面加载失败。`"
      />
      <el-tabs class="research-tabs">
        <el-tab-pane label="期限成熟">
          <el-table :data="researchHorizonRows" size="small">
            <el-table-column prop="horizon" label="期限" width="100" />
            <el-table-column prop="status" label="状态" width="180" />
            <el-table-column prop="count" label="样本" width="100" />
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="Factor表现">
          <el-table :data="factorRows" size="small" max-height="480">
            <el-table-column prop="factor" label="Factor" min-width="220" />
            <el-table-column prop="samples" label="样本" width="80" />
            <el-table-column prop="valid" label="有效" width="80" />
            <el-table-column label="缺失" width="90"><template #default="{ row }">{{ percent(row.missingRate) }}</template></el-table-column>
            <el-table-column v-for="horizon in ['1D','5D','10D','20D']" :key="horizon" :label="`${horizon}平均收益`" min-width="115"><template #default="{ row }">{{ percent(row.returns[horizon]) }}</template></el-table-column>
          </el-table>
          <div class="notice">固定回放分数与样本统计；不使用未来全样本重新归一化。</div>
        </el-tab-pane>
        <el-tab-pane label="Regime表现">
          <el-table :data="regimeRows" size="small">
            <el-table-column prop="regime" label="Regime" min-width="150" />
            <el-table-column prop="samples" label="样本" width="90" />
            <el-table-column label="20D沪深300"><template #default="{ row }">{{ percent(row.benchmark20d) }}</template></el-table-column>
            <el-table-column label="20D MAE"><template #default="{ row }">{{ percent(row.mae20d) }}</template></el-table-column>
            <el-table-column label="最差20D MAE"><template #default="{ row }">{{ percent(row.worstMae20d) }}</template></el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="Strategy表现">
          <el-table :data="strategyRows" size="small">
            <el-table-column prop="status" label="Proposal状态" />
            <el-table-column prop="count" label="样本" />
          </el-table>
          <div class="notice">入场区间评价 {{ strategyValue('entry_touch_evaluated_count') }}，触及 {{ strategyValue('entry_touch_count') }}，触及率 {{ percent(strategyValue('entry_touch_rate')) }}；研究成交为0。</div>
        </el-tab-pane>
        <el-tab-pane label="归因">
          <el-descriptions :column="2" border>
            <el-descriptions-item v-for="item in attributionDistribution" :key="item.label" :label="item.label">{{ item.value }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-card shadow="never">
      <template #header>
        <div class="header">
          <span>评价总览</span>
          <el-button :icon="Refresh" text @click="load">刷新</el-button>
        </div>
      </template>
      <el-row :gutter="12">
        <el-col v-for="item in overviewItems" :key="item.label" :xs="12" :sm="6">
          <el-statistic :title="item.label" :value="item.value" />
        </el-col>
      </el-row>
    </el-card>

    <el-card shadow="never">
      <template #header>四账户对照</template>
      <el-table :data="accountRows" size="small">
        <el-table-column prop="account_type" label="账户" min-width="150" />
        <el-table-column prop="status" label="估值状态" min-width="150" />
        <el-table-column label="收益">
          <template #default="{ row }">{{ percent(row.total_return) }}</template>
        </el-table-column>
        <el-table-column label="最大回撤">
          <template #default="{ row }">{{ percent(row.max_drawdown) }}</template>
        </el-table-column>
        <el-table-column label="费用">
          <template #default="{ row }">¥{{ money(row.total_fees) }}</template>
        </el-table-column>
        <el-table-column label="平均敞口">
          <template #default="{ row }">{{ percent(row.average_exposure_pct) }}</template>
        </el-table-column>
        <el-table-column prop="trade_count" label="成交数" />
        <el-table-column label="估值完整性" min-width="130">
          <template #default="{ row }">
            {{ row.valuation_complete_days }}/{{ row.valuation_complete_days + row.valuation_incomplete_days }} 天
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!accountRows.length" description="四类账户尚无可评价日快照；挑战者不会伪造数据" />
    </el-card>

    <el-card shadow="never">
      <template #header>
        <div class="header">
          <span>模型价值与配对比较</span>
          <span class="notice">
            样本 {{ comparisons.length }}，可配对 {{ pairedComparisonCount }}
          </span>
        </div>
      </template>
      <el-table :data="comparisons" size="small">
        <el-table-column prop="comparison_type" label="比较类型" min-width="190" />
        <el-table-column prop="symbol" label="标的" width="100" />
        <el-table-column prop="pairing_status" label="可比性" width="140" />
        <el-table-column label="10D价值增量" width="140">
          <template #default="{ row }">{{ percent(row.value_added_10d) }}</template>
        </el-table-column>
        <el-table-column label="说明" min-width="220">
          <template #default="{ row }">
            {{ row.comparability_reasons.join('；') || '同一机会、同一价格与期限口径' }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never">
      <template #header>未交易反事实</template>
      <el-table :data="counterfactuals" size="small">
        <el-table-column prop="mode" label="模式" width="180" />
        <el-table-column prop="status" label="状态" width="160" />
        <el-table-column label="净损益">
          <template #default="{ row }">¥{{ money(row.net_pnl) }}</template>
        </el-table-column>
        <el-table-column label="收益率">
          <template #default="{ row }">{{ percent(row.return_pct) }}</template>
        </el-table-column>
        <el-table-column prop="subject_id" label="评价主体" min-width="220" />
      </el-table>
    </el-card>

    <el-card shadow="never">
      <template #header>失败归因</template>
      <el-table :data="attributions.slice(0, 100)" size="small">
        <el-table-column prop="outcome_class" label="结果分类" width="160" />
        <el-table-column prop="primary_category" label="主归因" width="190" />
        <el-table-column label="置信度" width="100">
          <template #default="{ row }">{{ percent(row.confidence) }}</template>
        </el-table-column>
        <el-table-column label="人工覆盖" width="100">
          <template #default="{ row }">{{ row.overrides?.length ?? 0 }}</template>
        </el-table-column>
        <el-table-column prop="machine_explanation" label="规则化诊断" min-width="320" />
      </el-table>
      <div class="notice">机器归因保留原记录；人工覆盖只会追加，不能覆盖机器事实。</div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import {
  alphaguardEvaluationApi,
  type AccountEvaluation,
  type Attribution,
  type CounterfactualEvaluation,
  type EvaluationOverview,
  type PairedComparison,
  type ResearchSummary
} from '@/api/alphaguardEvaluations'

const loading = ref(false)
const overview = ref<EvaluationOverview | null>(null)
const accounts = ref<AccountEvaluation[]>([])
const comparisons = ref<PairedComparison[]>([])
const counterfactuals = ref<CounterfactualEvaluation[]>([])
const attributions = ref<Attribution[]>([])
const research = ref<ResearchSummary>({ status: 'NO_REPORT', report: null })

const researchEvaluation = computed<Record<string, any>>(() => research.value.report?.evaluation_summary || {})
const researchHorizonRows = computed(() => Object.entries((researchEvaluation.value.decision_close_horizon_status || {}) as Record<string, number>).map(([key,count]) => {
  const [horizon,status] = key.split(':'); return { horizon, status, count }
}))
const versionDiscontinuityCount = computed(() => Number((researchEvaluation.value.decision_close_horizon_status || {})['20D:PENDING'] || 0))
const factorRows = computed(() => Object.entries(research.value.report?.factor_summary || {}).map(([factor, raw]) => {
  const item = raw as Record<string, any>; const returns: Record<string, unknown> = {}
  for (const horizon of ['1D','5D','10D','20D']) returns[horizon] = item.horizon_returns?.[horizon]?.average_raw_return ?? null
  const samples = Number(item.sample_count || 0); const missing = Number(item.missing_count || 0)
  return { factor, samples, valid: samples - missing, missingRate: item.missing_rate, returns }
}))
const regimeRows = computed(() => {
  const summary = research.value.report?.regime_summary as Record<string, any> | undefined
  return Object.entries((summary?.distribution || {}) as Record<string, number>).map(([regime,samples]) => {
    const metrics = summary?.forward_metrics?.[regime] || {}
    return { regime, samples, benchmark20d: metrics.benchmark_return_20D?.average, mae20d: metrics.stock_mae_20D?.average, worstMae20d: metrics.stock_mae_20D?.worst }
  })
})
const strategyRows = computed(() => Object.entries((research.value.report?.strategy_summary?.status_distribution || {}) as Record<string, number>).map(([status,count]) => ({status,count})))
const attributionDistribution = computed(() => Object.entries((researchEvaluation.value.attribution_distribution || {}) as Record<string, number>).map(([label,value]) => ({label,value})))

const accountTypes = [
  'PAPER_QUANT',
  'PAPER_NORMAL',
  'PAPER_TOP_CONFIRMED',
  'PAPER_CHALLENGER'
]
const accountRows = computed<AccountEvaluation[]>(() => accountTypes.map(type => {
  const row = accounts.value.find(item => item.account_type === type)
  return row ?? {
    metric_id: `no-data:${type}`,
    account_id: '',
    account_type: type,
    period_start: '',
    period_end: '',
    status: type === 'PAPER_CHALLENGER' ? 'NOT_ACTIVE' : 'NO_DATA',
    total_return: null,
    max_drawdown: null,
    total_fees: null,
    average_exposure_pct: null,
    turnover: null,
    trade_count: 0,
    valuation_complete_days: 0,
    valuation_incomplete_days: 0
  }
}))
const overviewItems = computed(() => [
  { label: '已评价样本', value: overview.value?.evaluated_subjects ?? 0 },
  { label: '待成熟标签', value: overview.value?.pending_horizon_labels ?? 0 },
  { label: '数据不足标签', value: overview.value?.insufficient_data_labels ?? 0 },
  { label: '已交易样本', value: overview.value?.traded_subjects ?? 0 },
  { label: '未交易样本', value: overview.value?.untraded_subjects ?? 0 },
  { label: '反事实样本', value: overview.value?.counterfactual_samples ?? 0 },
  {
    label: '归因完成率',
    value: Number(((overview.value?.attribution_completion_rate ?? 0) * 100).toFixed(2)),
  }
])
const pairedComparisonCount = computed(
  () => comparisons.value.filter(item => item.pairing_status === 'PAIRED').length
)

function numeric(value: string | number | null | undefined) {
  const result = Number(value ?? 0)
  return Number.isFinite(result) ? result : 0
}
function money(value: string | number | null | undefined) {
  return numeric(value).toFixed(2)
}
function percent(value: string | number | null | undefined) {
  return value == null ? '—' : `${(numeric(value) * 100).toFixed(2)}%`
}
function strategyValue(key: string): string | number | null | undefined {
  const value = (research.value.report?.strategy_summary as Record<string, unknown> | undefined)?.[key]
  return typeof value === 'string' || typeof value === 'number' || value == null ? value : 0
}

async function load() {
  loading.value = true
  try {
    const [overviewRes, researchRes, accountRes, comparisonRes, counterfactualRes, attributionRes] =
      await Promise.all([
        alphaguardEvaluationApi.overview(),
        alphaguardEvaluationApi.researchSummary(),
        alphaguardEvaluationApi.accounts(),
        alphaguardEvaluationApi.modelValue(),
        alphaguardEvaluationApi.counterfactuals(),
        alphaguardEvaluationApi.attributions()
      ])
    overview.value = overviewRes.data
    research.value = researchRes.data
    accounts.value = accountRes.data.items
    comparisons.value = comparisonRes.data.items
    counterfactuals.value = counterfactualRes.data.items
    attributions.value = attributionRes.data.items
  } catch (error: any) {
    ElMessage.error(error?.message || '加载 AlphaGuard 评价中心失败')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.evaluation-center { display: grid; gap: 16px; }
.boundary-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.boundary-grid > div { display: grid; gap: 5px; padding: 14px 16px; border: 1px solid var(--el-border-color-light); border-radius: 6px; }
.boundary-grid span, .boundary-grid small { color: var(--el-text-color-secondary); }.boundary-grid strong { font-size: 24px; }
.research-tabs { margin-top: 12px; }
.header { display: flex; align-items: center; justify-content: space-between; }
.notice { margin-top: 12px; color: #909399; font-size: 13px; }
@media (max-width: 700px) { .boundary-grid { grid-template-columns: 1fr; } }
</style>
