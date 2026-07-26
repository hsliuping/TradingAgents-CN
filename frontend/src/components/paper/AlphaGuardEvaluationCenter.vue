<template>
  <div v-loading="loading" class="evaluation-center">
    <el-alert type="warning" :closable="false" show-icon>
      PR-007 结果仅用于离线评价与规则化诊断，不代表严格因果，也不会回写交易决策、
      账户、持仓或订单。
    </el-alert>

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
      <el-table :data="attributions" size="small">
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
  type PairedComparison
} from '@/api/alphaguardEvaluations'

const loading = ref(false)
const overview = ref<EvaluationOverview | null>(null)
const accounts = ref<AccountEvaluation[]>([])
const comparisons = ref<PairedComparison[]>([])
const counterfactuals = ref<CounterfactualEvaluation[]>([])
const attributions = ref<Attribution[]>([])

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

async function load() {
  loading.value = true
  try {
    const [overviewRes, accountRes, comparisonRes, counterfactualRes, attributionRes] =
      await Promise.all([
        alphaguardEvaluationApi.overview(),
        alphaguardEvaluationApi.accounts(),
        alphaguardEvaluationApi.modelValue(),
        alphaguardEvaluationApi.counterfactuals(),
        alphaguardEvaluationApi.attributions()
      ])
    overview.value = overviewRes.data
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
.header { display: flex; align-items: center; justify-content: space-between; }
.notice { margin-top: 12px; color: #909399; font-size: 13px; }
</style>
