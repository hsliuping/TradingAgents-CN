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
      <el-card shadow="never">
        <template #header><div class="header-row"><strong>MVP 准备度</strong><el-button text @click="load">刷新</el-button></div></template>
        <div class="readiness-row">
          <el-tag :type="readinessType" size="large">{{ readiness?.overall_status || 'UNKNOWN' }}</el-tag>
          <span>{{ readiness?.system_mode || '—' }}</span>
          <span>代码 {{ shortHash(readiness?.code_commit) }}</span>
          <span>构建 {{ readiness?.build_version || '—' }}</span>
        </div>
        <el-alert
          v-if="readiness?.blocking_items.length"
          type="warning"
          :closable="false"
          :title="`当前有 ${readiness.blocking_items.length} 个阻断项，系统不会伪装成可运行`"
        />
        <el-descriptions :column="4" border class="readiness-flags">
          <el-descriptions-item label="自动模拟">{{ yesNo(readiness?.paper_execution_ready) }}</el-descriptions-item>
          <el-descriptions-item label="评价">{{ yesNo(readiness?.evaluation_ready) }}</el-descriptions-item>
          <el-descriptions-item label="实验框架">{{ yesNo(readiness?.experiment_ready) }}</el-descriptions-item>
          <el-descriptions-item label="Challenger">{{ yesNo(readiness?.challenger_ready) }}</el-descriptions-item>
          <el-descriptions-item label="实盘"><el-tag type="danger">始终关闭</el-tag></el-descriptions-item>
        </el-descriptions>
      </el-card>

      <div class="metric-grid">
        <el-card v-for="item in sampleItems" :key="item.key" shadow="hover">
          <el-statistic :title="item.label" :value="item.value" />
          <div class="metric-note">{{ item.value === 0 ? '尚无真实样本' : '真实持久化记录' }}</div>
        </el-card>
      </div>

      <el-card shadow="never">
        <template #header><strong>数据与服务阻断</strong></template>
        <el-table :data="notReadyData" size="small">
          <el-table-column prop="component" label="组件" min-width="190" />
          <el-table-column prop="status" label="状态" width="120" />
          <el-table-column prop="record_count" label="记录数" width="100" />
          <el-table-column label="原因" min-width="300">
            <template #default="{ row }">{{ row.blocking_reasons.join('；') || row.warnings.join('；') }}</template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!notReadyData.length" description="当前没有数据阻断" />
      </el-card>

      <el-card shadow="never">
        <template #header><strong>未解决告警</strong></template>
        <el-table :data="overview?.open_alerts || []" size="small">
          <el-table-column prop="severity" label="级别" width="100" />
          <el-table-column prop="code" label="代码" min-width="210" />
          <el-table-column prop="title" label="摘要" min-width="220" />
          <el-table-column prop="occurrence_count" label="次数" width="80" />
          <el-table-column prop="last_seen_at" label="最近出现" min-width="180" />
        </el-table>
        <el-empty v-if="!(overview?.open_alerts.length)" description="尚无持久化告警；刷新运维检查后会聚合真实异常" />
      </el-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  alphaguardOperationsApi,
  type OperationsOverview
} from '@/api/alphaguardOperations'

const loading = ref(false)
const loadError = ref('')
const overview = ref<OperationsOverview | null>(null)
const readiness = computed(() => overview.value?.readiness ?? null)
const readinessType = computed(() => {
  const status = readiness.value?.overall_status
  return status === 'READY_FOR_PAPER' ? 'success' : status === 'UNSAFE' ? 'danger' : 'warning'
})
const notReadyData = computed(() =>
  (readiness.value?.data_readiness || []).filter(item => item.status !== 'READY')
)
const labels: Record<string, string> = {
  ag_candidates: '候选',
  ag_evidence_snapshots: '证据快照',
  ag_quant_proposals: '量化提案',
  ag_decision_contexts: '决策上下文',
  ag_risk_decisions: '风险决策',
  ag_paper_fills: '模拟成交',
  ag_eval_subjects: '评价样本',
  ag_exp_runs: '实验运行'
}
const sampleItems = computed(() =>
  Object.entries(overview.value?.sample_counts || {}).map(([key, value]) => ({
    key,
    label: labels[key] || key,
    value
  }))
)
const yesNo = (value?: boolean) => value ? 'READY' : 'NOT READY'
const shortHash = (value?: string) => value ? value.slice(0, 10) : '—'

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    overview.value = (await alphaguardOperationsApi.overview()).data
  } catch (error: any) {
    loadError.value = `${error?.message || '未知错误'}；请到运维中心检查 error_code 与 trace_id。`
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.page-grid { display: grid; gap: 16px; }
.header-row, .readiness-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.readiness-flags { margin-top: 16px; }
.metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
.metric-note { color: var(--el-text-color-secondary); font-size: 12px; margin-top: 8px; }
</style>

