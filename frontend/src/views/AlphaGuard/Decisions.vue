<template>
  <div v-loading="loading" class="page-grid">
    <el-card shadow="never">
      <template #header><div class="header-row"><strong>结构化决策时间线</strong><el-button text @click="load">刷新</el-button></div></template>
      <el-alert type="info" :closable="false" show-icon title="Normal、Top、Consensus 与 HardRisk 是四个独立对象；模型失败不会显示为 HOLD。" />
      <el-table :data="events" size="small" highlight-current-row @row-click="selectEvent">
        <el-table-column prop="created_at" label="时间" min-width="180" />
        <el-table-column prop="event_type" label="事件" min-width="210" />
        <el-table-column prop="analysis_id" label="Analysis" min-width="170" />
        <el-table-column prop="snapshot_id" label="Snapshot" min-width="170" />
        <el-table-column prop="reason" label="原因" min-width="240" />
        <el-table-column prop="trace_id" label="Trace" min-width="180" />
      </el-table>
      <el-empty v-if="!loading && !events.length" description="尚无真实决策事件；空数据不会伪装成 HOLD 或正常交易" />
    </el-card>

    <el-card v-if="selected" shadow="never">
      <template #header><strong>对象链</strong></template>
      <el-tabs>
        <el-tab-pane label="NormalTradePlan"><pre>{{ pretty(objects.normal) }}</pre></el-tab-pane>
        <el-tab-pane label="TopReviewDecision"><pre>{{ pretty(objects.top) }}</pre></el-tab-pane>
        <el-tab-pane label="ConsensusDecision"><pre>{{ pretty(objects.consensus) }}</pre></el-tab-pane>
        <el-tab-pane label="RiskDecision"><pre>{{ pretty(objects.risk) }}</pre></el-tab-pane>
        <el-tab-pane label="BenchmarkSafety"><pre>{{ pretty(objects.benchmark) }}</pre></el-tab-pane>
      </el-tabs>
      <div class="trace-hint">缺失对象显示为 null，绝不由前端补出交易含义。</div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { alphaguardApi, type DecisionEvent } from '@/api/alphaguard'

const loading = ref(false)
const events = ref<DecisionEvent[]>([])
const selected = ref<DecisionEvent | null>(null)
const objects = reactive<Record<string, unknown>>({ normal: null, top: null, consensus: null, risk: null, benchmark: null })
const pretty = (value: unknown) => JSON.stringify(value, null, 2)

async function load() {
  loading.value = true
  try {
    events.value = (await alphaguardApi.decisionEvents({ limit: 500 })).data.items
  } finally {
    loading.value = false
  }
}
async function selectEvent(row: DecisionEvent) {
  selected.value = row
  objects.normal = row.plan_id ? (await alphaguardApi.normalPlan(row.plan_id)).data : null
  objects.top = row.review_id ? (await alphaguardApi.topReview(row.review_id)).data : null
  objects.consensus = row.consensus_id ? (await alphaguardApi.consensus(row.consensus_id)).data : null
  objects.risk = row.risk_decision_id ? (await alphaguardApi.riskDecision(row.risk_decision_id)).data : null
  objects.benchmark = null
}
onMounted(load)
</script>

<style scoped>
.page-grid { display: grid; gap: 16px; }
.header-row { display: flex; justify-content: space-between; align-items: center; }
pre { max-height: 460px; overflow: auto; padding: 12px; background: var(--el-fill-color-light); border-radius: 6px; white-space: pre-wrap; }
.trace-hint { color: var(--el-text-color-secondary); font-size: 13px; }
</style>

