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

const short = (value?: string) => value ? value.slice(0, 12) : '—'
const pretty = (value: unknown) => JSON.stringify(value, null, 2)

async function loadOperations() {
  if (modelsOnly.value) return
  loading.value = true
  loadError.value = ''
  try {
    const [readinessResponse, servicesResponse, dataResponse, jobsResponse, alertsResponse, versionsResponse, integrityResponse] = await Promise.all([
      alphaguardOperationsApi.readiness(),
      alphaguardOperationsApi.services(),
      alphaguardOperationsApi.dataReadiness(),
      alphaguardOperationsApi.jobs(),
      alphaguardOperationsApi.alerts(),
      alphaguardOperationsApi.versions(),
      alphaguardOperationsApi.integrity()
    ])
    readiness.value = readinessResponse.data
    services.value = servicesResponse.data.items
    dataStatuses.value = dataResponse.data.items
    jobs.value = jobsResponse.data.items
    manualJobs.value = jobsResponse.data.allowed_manual_jobs || []
    alerts.value = alertsResponse.data.items
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
.page-grid { display: grid; gap: 16px; }
.safety-strip { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.safety-strip > div { min-height: 58px; padding: 10px 14px; border: 1px solid var(--el-border-color-light); border-radius: 6px; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.safety-strip span { color: var(--el-text-color-secondary); font-size: 12px; }
.header-row, .status-line { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.status-line > span { min-width: 0; flex: 1 1 280px; overflow-wrap: anywhere; }
.admin-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 16px; padding-top: 12px; border-top: 1px solid var(--el-border-color-light); }
pre { max-height: 420px; overflow: auto; padding: 12px; background: var(--el-fill-color-light); border-radius: 6px; white-space: pre-wrap; }
:deep(.operations-tabs--embedded) { border: 0; box-shadow: none; }
:deep(.operations-tabs--embedded > .el-tabs__header) { display: none; }
:deep(.operations-tabs--embedded > .el-tabs__content) { padding: 0; }
@media (max-width: 700px) {
  .safety-strip { grid-template-columns: 1fr; }
}
</style>
