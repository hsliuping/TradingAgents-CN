<template>
  <div class="page-grid">
    <template v-if="!modelsOnly">
      <section class="safety-strip">
        <div><span>系统模式</span><strong>{{ readiness?.system_mode || 'UNKNOWN' }}</strong></div>
        <div><span>实盘开关</span><el-tag type="danger">{{ readiness?.live_trading_enabled ?? false }}</el-tag></div>
        <div><span>实盘执行</span><el-tag type="danger">{{ readiness?.live_execution_allowed ?? false }}</el-tag></div>
      </section>

      <el-card shadow="never">
        <template #header>
          <div class="header-row">
            <strong>系统准备度</strong>
            <el-button :loading="loading" @click="loadOperations">刷新</el-button>
          </div>
        </template>
        <div class="status-line">
          <el-tag :type="statusType" size="large">{{ readiness?.overall_status || 'UNKNOWN' }}</el-tag>
          <span>Report {{ short(readiness?.report_hash) }}</span>
          <span>Config {{ short(readiness?.config_hash) }}</span>
          <el-tag type="danger">LIVE_READY = false</el-tag>
        </div>
        <el-alert
          v-if="readiness?.blocking_items.length"
          type="warning"
          :closable="false"
          :title="readiness.blocking_items.join('；')"
        />
      </el-card>

      <section class="challenger-status" aria-label="模拟挑战者运维状态">
        <div><span>挑战者运行</span><strong>{{ readiness?.challenger_ready ? '已就绪' : '未就绪' }}</strong></div>
        <div><span>活动挑战者</span><strong>{{ challengerStatus?.active_challenger_count ?? 0 }}</strong></div>
        <div><span>模拟账户</span><strong>{{ challengerStatus?.account_status === 'ACTIVE' ? '正常' : '未配置' }}</strong></div>
        <div><span>最近运行</span><strong>{{ displayTime(challengerStatus?.last_run_at) }}</strong></div>
        <div><span>最近成功</span><strong>{{ displayTime(challengerStatus?.last_success_at) }}</strong></div>
        <div><span>最近失败</span><strong>{{ displayTime(challengerStatus?.last_failure_at) }}</strong></div>
        <div><span>待执行任务</span><strong>{{ challengerStatus?.pending_task_count ?? 0 }}</strong></div>
        <div><span>模型调用量</span><strong>{{ challengerStatus?.model_call_count ?? 0 }}</strong></div>
        <div><span>资源预算</span><strong>{{ challengerStatus?.budget_status === 'READY' ? '可用' : '已阻止' }}</strong></div>
        <div><span>订单 / 成交</span><strong>{{ challengerStatus?.order_count ?? 0 }} / {{ challengerStatus?.fill_count ?? 0 }}</strong></div>
        <div><span>评价成熟度</span><strong>{{ challengerStatus?.mature_evaluation_count ?? 0 }} / {{ challengerStatus?.evaluation_subject_count ?? 0 }}</strong></div>
      </section>
      <section class="recommendation-status" aria-label="候选推荐运维状态">
        <div><span>推荐运行时</span><strong>{{ recommendationStatus?.recommendation_runtime_ready ? '可用' : '未就绪' }}</strong></div>
        <div><span>推荐数据</span><strong>{{ recommendationDataLabel }}</strong></div>
        <div><span>全市场覆盖率</span><strong>{{ formatCoverage(recommendationStatus?.coverage_percentage) }}</strong></div>
        <div><span>行情 / 状态完整</span><strong>{{ recommendationStatus?.history_ready_count ?? 0 }} / {{ recommendationStatus?.trade_status_ready_count ?? 0 }}</strong></div>
        <div><span>数据质量通过</span><strong>{{ recommendationStatus?.data_quality_pass_count ?? 0 }}</strong></div>
        <div><span>证券池</span><strong>{{ recommendationStatus?.security_count ?? 0 }}</strong></div>
        <div><span>符合资格</span><strong>{{ recommendationStatus?.eligible_count ?? 0 }}</strong></div>
        <div><span>今日推荐</span><strong>{{ recommendationStatus?.today_recommendation_count ?? 0 }}</strong></div>
        <div><span>待审核</span><strong>{{ recommendationStatus?.pending_review_count ?? 0 }}</strong></div>
        <div><span>已接受 / 已拒绝</span><strong>{{ recommendationStatus?.accepted_count ?? 0 }} / {{ recommendationStatus?.rejected_count ?? 0 }}</strong></div>
        <div><span>最近扫描</span><strong>{{ displayTime(recommendationStatus?.last_success_at) }}</strong></div>
        <div><span>最近同步</span><strong>{{ displayTime(recommendationStatus?.last_sync_at) }}</strong></div>
        <div><span>同步未覆盖证券</span><strong>{{ recommendationStatus?.coverage_failed_symbol_count ?? 0 }}</strong></div>
        <div><span>主要阻断</span><strong>{{ recommendationBlocker }}</strong></div>
        <div><span>最高分</span><strong>{{ recommendationStatus?.top_score ?? '暂无' }}</strong></div>
        <div><span>扫描耗时 / 失败</span><strong>{{ recommendationStatus?.last_duration_ms ?? 0 }} ms / {{ recommendationStatus?.failed_symbol_count ?? 0 }}</strong></div>
        <div><span>策略版本</span><strong>{{ recommendationStatus?.policy_version || '未登记' }}</strong></div>
        <div><span>自动加入候选池</span><strong>永久关闭</strong></div>
      </section>
      <div v-if="canRunAdminOperations" class="recommendation-actions">
        <el-button
          type="primary"
          :loading="runningJob === 'RECOMMENDATION_DATA_SYNC'"
          @click="runRecommendationDataSync"
        >启动全市场数据同步</el-button>
        <span>同步只写版本化行情、交易状态和数据质量，不会调用模型或加入候选池。</span>
      </div>
    </template>

    <el-tabs
      v-model="activeOperationTab"
      type="border-card"
      :class="{ 'operations-tabs--embedded': props.embedded }"
    >
      <el-tab-pane v-if="!modelsOnly" label="服务" name="services">
        <el-result
          v-if="loadError"
          icon="warning"
          title="运维状态加载失败"
          :sub-title="loadError"
        >
          <template #extra><el-button @click="loadOperations">重试</el-button></template>
        </el-result>
        <el-table v-else v-loading="loading" :data="services" size="small">
          <el-table-column prop="service_name" label="服务" />
          <el-table-column prop="status" label="状态" />
          <el-table-column prop="latency_ms" label="延迟(ms)" />
          <el-table-column prop="error_code" label="错误代码" min-width="190" />
          <el-table-column prop="sanitized_message" label="脱敏摘要" min-width="260" />
        </el-table>
      </el-tab-pane>

      <el-tab-pane v-if="!modelsOnly" label="数据准备" name="data-readiness">
        <el-table v-loading="loading" :data="dataStatuses" size="small">
          <el-table-column prop="component" label="组件" min-width="190" />
          <el-table-column prop="status" label="状态" width="120" />
          <el-table-column prop="record_count" label="记录" width="90" />
          <el-table-column label="覆盖" min-width="190">
            <template #default="{ row }">{{ row.coverage_start || '—' }} ～ {{ row.coverage_end || '—' }}</template>
          </el-table-column>
          <el-table-column label="阻断" min-width="300">
            <template #default="{ row }">{{ row.blocking_reasons.join('；') }}</template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane v-if="!modelsOnly" label="任务" name="jobs">
        <el-table v-loading="loading" :data="jobs" size="small">
          <el-table-column prop="job_name" label="任务" min-width="190" />
          <el-table-column prop="worker_name" label="Worker" min-width="130" />
          <el-table-column prop="status" label="状态" width="110" />
          <el-table-column prop="next_scheduled_at" label="下次执行" min-width="180" />
          <el-table-column prop="backlog_count" label="积压" width="80" />
          <el-table-column prop="error_code" label="错误" min-width="170" />
        </el-table>
        <div v-if="canRunAdminOperations" class="admin-actions">
          <span>管理员受控任务：</span>
          <el-button
            v-for="name in manualJobs"
            :key="name"
            size="small"
            :loading="runningJob === name"
            @click="runJob(name)"
          >{{ name }}</el-button>
        </div>
      </el-tab-pane>

      <el-tab-pane v-if="!modelsOnly" label="告警" name="alerts">
        <el-table v-loading="loading" :data="alerts" size="small">
          <el-table-column prop="severity" label="级别" width="100" />
          <el-table-column prop="code" label="代码" min-width="220" />
          <el-table-column prop="sanitized_message" label="脱敏摘要" min-width="280" />
          <el-table-column prop="occurrence_count" label="次数" width="80" />
          <el-table-column prop="status" label="状态" width="130" />
          <el-table-column v-if="canRunAdminOperations" label="操作" width="150">
            <template #default="{ row }">
              <el-button link :disabled="row.status !== 'OPEN'" @click="ack(row)">确认</el-button>
              <el-button link type="success" :disabled="row.status === 'RESOLVED'" @click="resolve(row)">解决</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!alerts.length && !loading" description="暂无持久化告警" />
      </el-tab-pane>

      <el-tab-pane label="模型与 API" name="models">
        <ModelConfigurationPanel />
      </el-tab-pane>

      <el-tab-pane v-if="!modelsOnly" label="完整性与版本" name="integrity">
        <h4>完整性</h4>
        <pre>{{ pretty(integrity) }}</pre>
        <h4>版本（已脱敏）</h4>
        <pre>{{ pretty(versions) }}</pre>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import ModelConfigurationPanel from '@/components/alphaguard/ModelConfigurationPanel.vue'
import {
  alphaguardOperationsApi,
  type DataReadiness,
  type RecommendationOperationsStatus,
  type ChallengerOperationsStatus,
  type JobHealth,
  type OperationalAlert,
  type ServiceHealth,
  type SystemReadiness
} from '@/api/alphaguardOperations'
import { useAuthStore } from '@/stores/auth'

const props = withDefaults(defineProps<{
  modelsOnly?: boolean
  embedded?: boolean
}>(), {
  modelsOnly: false,
  embedded: false
})

const authStore = useAuthStore()
const isDemo = import.meta.env.VITE_ALPHAGUARD_DEMO === 'true'
const isCredentialHost = import.meta.env.VITE_ALPHAGUARD_CREDENTIAL_HOST === 'true'
const modelsOnly = computed(() => props.modelsOnly || isCredentialHost)
const canRunAdminOperations = computed(() => authStore.isAdmin && !isDemo && !isCredentialHost)
const activeOperationTab = ref(modelsOnly.value ? 'models' : 'services')
const loading = ref(false)
const loadError = ref('')
const runningJob = ref('')
const readiness = ref<SystemReadiness | null>(null)
const challengerStatus = ref<ChallengerOperationsStatus | null>(null)
const recommendationStatus = ref<RecommendationOperationsStatus | null>(null)
const services = ref<ServiceHealth[]>([])
const dataStatuses = ref<DataReadiness[]>([])
const jobs = ref<JobHealth[]>([])
const alerts = ref<OperationalAlert[]>([])
const manualJobs = ref<string[]>([])
const versions = ref<Record<string, unknown>>({})
const integrity = ref<Record<string, unknown>>({})

const statusType = computed(() => readiness.value?.overall_status === 'READY_FOR_PAPER'
  ? 'success'
  : readiness.value?.overall_status === 'UNSAFE'
    ? 'danger'
    : 'warning')
const recommendationDataLabel = computed(() => ({
  READY: '已就绪',
  DEGRADED: '已就绪（部分降级）',
  PARTIAL: '部分就绪',
  NOT_READY: '未就绪'
} as Record<string, string>)[recommendationStatus.value?.coverage_status || 'NOT_READY'])
const recommendationReasonLabels: Record<string, string> = {
  ADJUSTED_HISTORY_INSUFFICIENT: '历史复权行情不足',
  RAW_HISTORY_INSUFFICIENT: '历史原始行情不足',
  TRADING_STATUS_NOT_READY: '交易状态未就绪',
  TARGET_QUOTE_MISSING: '目标交易日日线缺失',
  LISTING_DATE_MISSING: '上市日期缺失',
  PRICE_VERSION_DISCONTINUITY: '行情版本不连续',
  BENCHMARK_NOT_READY: '沪深300窗口未就绪',
  PRICE_DATA_ANOMALY: '行情字段异常'
}
const recommendationBlocker = computed(() => {
  const item = Object.entries(recommendationStatus.value?.blocking_reason_counts || {})
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0]
  return item ? `${recommendationReasonLabels[item[0]] || item[0]}（${item[1]}）` : '无'
})

const short = (value?: string) => value ? value.slice(0, 12) : '—'
const displayTime = (value?: string | null) => value ? value.replace('T', ' ').slice(0, 19) : '暂无'
const formatCoverage = (value?: string) => `${(Number(value || 0) * 100).toFixed(1)}%`
const pretty = (value: unknown) => JSON.stringify(value, null, 2)

async function loadOperations() {
  if (modelsOnly.value) return
  loading.value = true
  loadError.value = ''
  try {
    const [overviewResponse, jobsResponse, versionsResponse, integrityResponse] = await Promise.all([
      alphaguardOperationsApi.overview(),
      alphaguardOperationsApi.jobs(),
      alphaguardOperationsApi.versions(),
      alphaguardOperationsApi.integrity()
    ])
    challengerStatus.value = overviewResponse.data.challenger_status
    recommendationStatus.value = overviewResponse.data.recommendation_status
    readiness.value = overviewResponse.data.readiness
    services.value = overviewResponse.data.readiness.service_health
    dataStatuses.value = overviewResponse.data.readiness.data_readiness
    jobs.value = jobsResponse.data.items
    manualJobs.value = jobsResponse.data.allowed_manual_jobs || []
    alerts.value = overviewResponse.data.open_alerts
    versions.value = versionsResponse.data
    integrity.value = integrityResponse.data
  } catch {
    loadError.value = '无法读取后端运维状态；页面不会使用缓存结果。'
  } finally {
    loading.value = false
  }
}

async function runJob(name: string) {
  runningJob.value = name
  try {
    await alphaguardOperationsApi.runJob(name)
    ElMessage.success(`${name} 已进入幂等队列。`)
    await loadOperations()
  } catch {
    ElMessage.error(`${name} 未能启动，请检查服务状态后重试。`)
  } finally {
    runningJob.value = ''
  }
}

async function runRecommendationDataSync() {
  try {
    await ElMessageBox.confirm(
      '将从正式 Provider 分批补齐推荐最低行情窗口。任务支持断点续传，不会调用模型或自动加入候选池。',
      '启动全市场数据同步',
      { confirmButtonText: '启动同步', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  await runJob('RECOMMENDATION_DATA_SYNC')
}

async function ack(row: Record<string, unknown>) {
  const alertId = typeof row.alert_id === 'string' ? row.alert_id : ''
  if (!alertId) {
    ElMessage.error('告警身份无效，操作已阻止。')
    return
  }
  try {
    await alphaguardOperationsApi.acknowledgeAlert(alertId)
    ElMessage.success('告警已确认。')
    await loadOperations()
  } catch {
    ElMessage.error('告警确认失败，请刷新后重试。')
  }
}

async function resolve(row: Record<string, unknown>) {
  const alertId = typeof row.alert_id === 'string' ? row.alert_id : ''
  if (!alertId) {
    ElMessage.error('告警身份无效，操作已阻止。')
    return
  }
  let note = ''
  try {
    const result = await ElMessageBox.prompt(
      '输入解决说明；历史告警不会删除。',
      '解决告警',
      { inputValidator: value => String(value || '').length >= 3 || '至少输入 3 个字符' }
    )
    note = result.value
  } catch {
    return
  }
  try {
    await alphaguardOperationsApi.resolveAlert(alertId, note)
    ElMessage.success('告警已解决。')
    await loadOperations()
  } catch {
    ElMessage.error('告警解决失败，请刷新后重试。')
  }
}

onMounted(loadOperations)
</script>

<style scoped>
.page-grid { display: grid; gap: 16px; min-width: 0; }
.page-grid > .el-tabs { min-width: 0; max-width: 100%; }
.safety-strip { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.safety-strip > div { min-height: 58px; padding: 10px 14px; border: 1px solid var(--el-border-color-light); border-radius: 6px; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.safety-strip span { color: var(--el-text-color-secondary); font-size: 12px; }
.header-row, .status-line { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.status-line > span { min-width: 0; flex: 1 1 280px; overflow-wrap: anywhere; }
.challenger-status { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border: 1px solid var(--el-border-color-light); border-radius: 6px; overflow: hidden; }
.recommendation-status { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); border: 1px solid var(--el-border-color-light); border-radius: 6px; overflow: hidden; }
.challenger-status > div, .recommendation-status > div { min-height: 68px; padding: 11px 14px; border-right: 1px solid var(--el-border-color-light); border-bottom: 1px solid var(--el-border-color-light); display: grid; gap: 6px; }
.challenger-status > div:nth-child(4n) { border-right: 0; }
.recommendation-status > div:nth-child(5n) { border-right: 0; }
.challenger-status span, .recommendation-status span { color: var(--el-text-color-secondary); font-size: 12px; }
.challenger-status strong, .recommendation-status strong { min-width: 0; overflow-wrap: anywhere; }
.admin-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 16px; padding-top: 12px; border-top: 1px solid var(--el-border-color-light); }
.recommendation-actions { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.recommendation-actions span { color: var(--el-text-color-secondary); font-size: 12px; }
pre { max-height: 420px; overflow: auto; padding: 12px; background: var(--el-fill-color-light); border-radius: 6px; white-space: pre-wrap; }
:deep(.operations-tabs--embedded) { border: 0; box-shadow: none; }
:deep(.operations-tabs--embedded > .el-tabs__header) { display: none; }
:deep(.operations-tabs--embedded > .el-tabs__content) { padding: 0; }
@media (max-width: 700px) {
  .safety-strip { grid-template-columns: 1fr; }
  .challenger-status { grid-template-columns: 1fr; }
  .recommendation-status { grid-template-columns: 1fr; }
  .challenger-status > div, .recommendation-status > div { border-right: 0; }
}
</style>
