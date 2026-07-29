<template>
  <div v-loading="loading" class="page-grid">
    <el-result v-if="loadError" icon="warning" title="运维状态加载失败" :sub-title="loadError"><template #extra><el-button @click="load">重试</el-button></template></el-result>
    <template v-else>
    <section class="safety-strip">
      <div><span>SYSTEM_MODE</span><strong>{{ readiness?.system_mode || 'UNKNOWN' }}</strong></div>
      <div><span>LIVE_TRADING_ENABLED</span><el-tag type="danger">{{ readiness?.live_trading_enabled ?? false }}</el-tag></div>
      <div><span>LIVE_EXECUTION_ALLOWED</span><el-tag type="danger">{{ readiness?.live_execution_allowed ?? false }}</el-tag></div>
    </section>
    <el-card shadow="never">
      <template #header><div class="header-row"><strong>系统准备度</strong><el-button @click="load">刷新</el-button></div></template>
      <div class="status-line">
        <el-tag :type="statusType" size="large">{{ readiness?.overall_status || 'UNKNOWN' }}</el-tag>
        <span>Report {{ short(readiness?.report_hash) }}</span>
        <span>Config {{ short(readiness?.config_hash) }}</span>
        <el-tag type="danger">LIVE_READY = false</el-tag>
      </div>
      <el-alert v-if="readiness?.blocking_items.length" type="warning" :closable="false" :title="readiness.blocking_items.join('；')" />
    </el-card>

    <el-tabs type="border-card">
      <el-tab-pane label="服务">
        <el-table :data="services" size="small">
          <el-table-column prop="service_name" label="服务" />
          <el-table-column prop="status" label="状态" />
          <el-table-column prop="latency_ms" label="延迟(ms)" />
          <el-table-column prop="error_code" label="错误代码" min-width="190" />
          <el-table-column prop="sanitized_message" label="脱敏摘要" min-width="260" />
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="数据准备">
        <el-table :data="dataStatuses" size="small">
          <el-table-column prop="component" label="组件" min-width="190" />
          <el-table-column prop="status" label="状态" width="120" />
          <el-table-column prop="record_count" label="记录" width="90" />
          <el-table-column label="覆盖" min-width="190"><template #default="{ row }">{{ row.coverage_start || '—' }} ～ {{ row.coverage_end || '—' }}</template></el-table-column>
          <el-table-column label="阻断" min-width="300"><template #default="{ row }">{{ row.blocking_reasons.join('；') }}</template></el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="任务">
        <el-table :data="jobs" size="small">
          <el-table-column prop="job_name" label="任务" min-width="190" />
          <el-table-column prop="worker_name" label="Worker" min-width="130" />
          <el-table-column prop="status" label="状态" width="110" />
          <el-table-column prop="next_scheduled_at" label="下次执行" min-width="180" />
          <el-table-column prop="backlog_count" label="积压" width="80" />
          <el-table-column prop="error_code" label="错误" min-width="170" />
        </el-table>
        <div v-if="authStore.isAdmin && !isDemo" class="admin-actions">
          <span>管理员受控任务：</span>
          <el-button v-for="name in manualJobs" :key="name" size="small" @click="runJob(name)">{{ name }}</el-button>
        </div>
      </el-tab-pane>
      <el-tab-pane label="告警">
        <el-table :data="alerts" size="small">
          <el-table-column prop="severity" label="级别" width="100" />
          <el-table-column prop="code" label="代码" min-width="220" />
          <el-table-column prop="sanitized_message" label="脱敏摘要" min-width="280" />
          <el-table-column prop="occurrence_count" label="次数" width="80" />
          <el-table-column prop="status" label="状态" width="130" />
          <el-table-column v-if="authStore.isAdmin && !isDemo" label="操作" width="150">
            <template #default="{ row }">
              <el-button link :disabled="row.status !== 'OPEN'" @click="ack(row)">确认</el-button>
              <el-button link type="success" :disabled="row.status === 'RESOLVED'" @click="resolve(row)">解决</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!alerts.length" description="暂无持久化告警" />
      </el-tab-pane>
      <el-tab-pane label="完整性与版本">
        <h4>完整性</h4><pre>{{ pretty(integrity) }}</pre>
        <h4>版本（已脱敏）</h4><pre>{{ pretty(versions) }}</pre>
      </el-tab-pane>
    </el-tabs>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import {
  alphaguardOperationsApi,
  type DataReadiness,
  type JobHealth,
  type OperationalAlert,
  type ServiceHealth,
  type SystemReadiness
} from '@/api/alphaguardOperations'

const authStore = useAuthStore()
const isDemo = import.meta.env.VITE_ALPHAGUARD_DEMO === 'true'
const loading = ref(false)
const loadError = ref('')
const readiness = ref<SystemReadiness | null>(null)
const services = ref<ServiceHealth[]>([])
const dataStatuses = ref<DataReadiness[]>([])
const jobs = ref<JobHealth[]>([])
const alerts = ref<OperationalAlert[]>([])
const manualJobs = ref<string[]>([])
const versions = ref<Record<string, unknown>>({})
const integrity = ref<Record<string, unknown>>({})
const statusType = computed(() => readiness.value?.overall_status === 'READY_FOR_PAPER' ? 'success' : readiness.value?.overall_status === 'UNSAFE' ? 'danger' : 'warning')
const short = (value?: string) => value ? value.slice(0, 12) : '—'
const pretty = (value: unknown) => JSON.stringify(value, null, 2)

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const [r, s, d, j, a, v, i] = await Promise.all([
      alphaguardOperationsApi.readiness(),
      alphaguardOperationsApi.services(),
      alphaguardOperationsApi.dataReadiness(),
      alphaguardOperationsApi.jobs(),
      alphaguardOperationsApi.alerts(),
      alphaguardOperationsApi.versions(),
      alphaguardOperationsApi.integrity()
    ])
    readiness.value = r.data
    services.value = s.data.items
    dataStatuses.value = d.data.items
    jobs.value = j.data.items
    manualJobs.value = j.data.allowed_manual_jobs || []
    alerts.value = a.data.items
    versions.value = v.data
    integrity.value = i.data
  } catch (error: any) {
    loadError.value = `${error?.message || '未知错误'}；页面不会用缓存状态伪装服务健康。`
  } finally {
    loading.value = false
  }
}
async function runJob(name: string) {
  await alphaguardOperationsApi.runJob(name)
  ElMessage.success(`${name} 已进入幂等队列`)
}
async function ack(row: Record<string, unknown>) {
  const alert = row as unknown as OperationalAlert
  await alphaguardOperationsApi.acknowledgeAlert(alert.alert_id)
  await load()
}
async function resolve(row: Record<string, unknown>) {
  const alert = row as unknown as OperationalAlert
  const result = await ElMessageBox.prompt('输入解决说明；历史告警不会删除', '解决告警', { inputValidator: value => String(value || '').length >= 3 || '至少3个字符' })
  await alphaguardOperationsApi.resolveAlert(alert.alert_id, result.value)
  await load()
}
onMounted(load)
</script>

<style scoped>
.page-grid { display: grid; gap: 16px; }
.safety-strip { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.safety-strip > div { min-height: 58px; padding: 10px 14px; border: 1px solid var(--el-border-color-light); border-radius: 6px; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.safety-strip span { color: var(--el-text-color-secondary); font-size: 12px; }
.header-row, .status-line { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.admin-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 16px; padding-top: 12px; border-top: 1px solid var(--el-border-color-light); }
pre { max-height: 420px; overflow: auto; padding: 12px; background: var(--el-fill-color-light); border-radius: 6px; white-space: pre-wrap; }
@media (max-width: 700px) { .safety-strip { grid-template-columns: 1fr; } }
</style>
