<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2 class="title">投资日历</h2>
      </div>
      <div class="actions">
        <el-date-picker
          v-model="range"
          type="daterange"
          unlink-panels
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
        />
        <el-select v-model="minImportance" placeholder="重要性" style="width: 120px">
          <el-option :value="0" label="全部" />
          <el-option :value="3" label="3+" />
          <el-option :value="4" label="4+" />
          <el-option :value="5" label="5" />
        </el-select>
        <el-button :loading="syncing" @click="sync">同步</el-button>
        <el-button type="primary" :loading="loading" @click="fetchList">刷新</el-button>
      </div>
    </div>

    <el-card shadow="hover">
      <el-table :data="events" v-loading="loading" style="width: 100%">
        <el-table-column label="时间" width="160">
          <template #default="{ row }">
            <div class="time-cell">
              <div class="date">{{ row.date }}</div>
              <div class="time">{{ formatTime(row.start_time) }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="类型" width="90" />
        <el-table-column label="重要性" width="100">
          <template #default="{ row }">
            <el-tag :type="importanceType(row.importance)" size="small">{{ row.importance }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="事件" min-width="260" />
        <el-table-column prop="summary" label="摘要" min-width="320" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button type="text" size="small" @click="openDetail(row)">详情</el-button>
            <el-button type="text" size="small" @click="analyze(row)">AI解读</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-drawer v-model="detailOpen" size="520px" title="事件详情">
      <div v-if="selected">
        <div class="detail-title">{{ selected.title }}</div>
        <div class="detail-meta">
          <el-tag :type="importanceType(selected.importance)" size="small">重要性 {{ selected.importance }}</el-tag>
          <el-tag type="info" size="small">{{ selected.category }}</el-tag>
          <el-tag v-if="selected.region" type="info" size="small">{{ selected.region }}</el-tag>
          <el-tag type="info" size="small">{{ selected.date }} {{ formatTime(selected.start_time) }}</el-tag>
        </div>
        <div class="detail-section">
          <div class="detail-label">摘要</div>
          <div class="detail-text">{{ selected.summary || '-' }}</div>
        </div>
        <div class="detail-section">
          <div class="detail-label">内容</div>
          <div class="detail-text">{{ selected.content || '-' }}</div>
        </div>
        <div class="detail-actions">
          <el-button type="primary" :loading="analyzing" @click="analyze(selected)">AI解读</el-button>
          <el-button :loading="loadingLatest" @click="loadLatestAnalysis(selected.event_id)">查看最新解读</el-button>
        </div>
      </div>
    </el-drawer>

    <el-drawer v-model="analysisOpen" size="640px" title="AI 解读">
      <div v-if="analysisTask">
        <div class="analysis-model-config">
          <span class="label">选择模型</span>
          <DeepModelSelector
            v-model="selectedModel"
            :available-models="availableModels"
            type="deep"
            size="small"
            width="260px"
          />
        </div>

        <div class="analysis-meta">
          <el-tag :type="statusType(analysisTask.status)" size="small">{{ analysisTask.status }}</el-tag>
          <el-tag v-if="analysisTask.model_name" type="info" size="small">{{ analysisTask.model_name }}</el-tag>
          <el-tag v-if="analysisTask.model_provider" type="info" size="small">{{ analysisTask.model_provider }}</el-tag>
        </div>

        <div v-if="analysisTask.status === 'failed'" class="analysis-error">
          <el-alert :title="analysisTask.error_message || '分析失败'" type="error" show-icon :closable="false" />
        </div>

        <div v-else-if="analysisTask.status !== 'completed'" class="analysis-wait">
          <el-skeleton :rows="6" animated />
        </div>

        <div v-else class="analysis-body">
          <div class="block">
            <div class="block-title">一句话结论</div>
            <div class="block-text">{{ analysisTask.result?.event_summary }}</div>
          </div>

          <div class="block">
            <div class="block-title">可炒作性</div>
            <div class="tradability">
              <div class="score">{{ analysisTask.result?.tradability?.score }}</div>
              <div class="reason">{{ analysisTask.result?.tradability?.reason }}</div>
            </div>
          </div>

          <div class="block">
            <div class="block-title">题材方向</div>
            <el-table :data="analysisTask.result?.themes || []" size="small">
              <el-table-column prop="theme" label="题材" width="140" />
              <el-table-column prop="rationale" label="理由" />
              <el-table-column prop="confidence" label="置信度" width="90" />
            </el-table>
          </div>

          <div class="block">
            <div class="block-title">受益概念</div>
            <el-table :data="analysisTask.result?.concepts || []" size="small">
              <el-table-column prop="concept" label="概念" width="140" />
              <el-table-column prop="why" label="逻辑" />
              <el-table-column prop="risk" label="风险" />
            </el-table>
          </div>

          <div class="block">
            <div class="block-title">概念股（可为空）</div>
            <el-table :data="analysisTask.result?.related_stocks || []" size="small">
              <el-table-column prop="market" label="市场" width="70" />
              <el-table-column prop="code" label="代码" width="90" />
              <el-table-column prop="name" label="名称" width="120" />
              <el-table-column prop="reason" label="理由" />
              <el-table-column prop="confidence" label="置信度" width="90" />
            </el-table>
          </div>

          <div class="block">
            <div class="block-title">风险</div>
            <el-tag v-for="r in analysisTask.result?.risks || []" :key="r" type="warning" size="small" class="tag">{{ r }}</el-tag>
          </div>

          <div class="block">
            <div class="block-title">验证信号</div>
            <el-tag v-for="r in analysisTask.result?.validation_signals || []" :key="r" type="info" size="small" class="tag">{{ r }}</el-tag>
          </div>

          <div class="block">
            <div class="block-title">信息缺口</div>
            <el-tag v-for="r in analysisTask.result?.unknowns || []" :key="r" type="info" size="small" class="tag">{{ r }}</el-tag>
          </div>

          <el-alert :title="analysisTask.result?.disclaimer" type="info" :closable="false" show-icon />
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { onActivated, onMounted, ref, watch } from 'vue'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { calendarApi, type CalendarEvent, type CalendarAnalysisDoc } from '@/api/calendar'
import { configApi } from '@/api/config'
import DeepModelSelector from '@/components/DeepModelSelector.vue'

const range = ref<[string, string]>([dayjs().format('YYYY-MM-DD'), dayjs().add(14, 'day').format('YYYY-MM-DD')])
const minImportance = ref(4)

const loading = ref(false)
const syncing = ref(false)
const events = ref<CalendarEvent[]>([])

const detailOpen = ref(false)
const selected = ref<CalendarEvent | null>(null)
const analyzing = ref(false)
const analysisOpen = ref(false)
const analysisTask = ref<CalendarAnalysisDoc | null>(null)
const loadingLatest = ref(false)

const availableModels = ref<any[]>([])
const selectedModel = ref<string>('')

function importanceType(v: number) {
  if (v >= 5) return 'danger'
  if (v >= 4) return 'warning'
  if (v >= 3) return 'info'
  return 'success'
}

function statusType(v: string) {
  if (v === 'completed') return 'success'
  if (v === 'failed') return 'danger'
  if (v === 'running' || v === 'processing') return 'warning'
  return 'info'
}

function formatTime(dt: string) {
  const d = dayjs(dt)
  if (!d.isValid()) return ''
  return d.format('HH:mm')
}

async function sync() {
  const [start, end] = range.value
  syncing.value = true
  try {
    await calendarApi.sync({ start, end })
    ElMessage.success('同步已触发')
    await fetchList()
  } catch (e: any) {
    ElMessage.error(e?.message || '同步失败')
  } finally {
    syncing.value = false
  }
}

async function fetchList() {
  const [start, end] = range.value
  loading.value = true
  try {
    const min = minImportance.value > 0 ? minImportance.value : undefined
    const res = await calendarApi.listEvents({ start, end, min_importance: min })
    events.value = res.data.items || []
  } catch (e: any) {
    ElMessage.error(e?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function openDetail(row: CalendarEvent) {
  selected.value = row
  detailOpen.value = true
}

async function analyze(row: CalendarEvent, forceRefresh = false) {
  selected.value = row
  analyzing.value = true
  try {
    const body: { model_name?: string; force_refresh: boolean } = {
      force_refresh: forceRefresh,
    }
    if (selectedModel.value) {
      body.model_name = selectedModel.value
    }
    const res = await calendarApi.analyze(row.event_id, body)
    analysisOpen.value = true
    analysisTask.value = { analysis_id: res.data.analysis_id, task_id: res.data.task_id, event_id: row.event_id, status: res.data.status }
    await pollAnalysis(res.data.task_id)
  } catch (e: any) {
    ElMessage.error(e?.message || '触发失败')
  } finally {
    analyzing.value = false
  }
}

async function loadLatestAnalysis(eventId: string) {
  loadingLatest.value = true
  try {
    const res = await calendarApi.getLatestAnalysis(eventId)
    analysisOpen.value = true
    analysisTask.value = res.data
  } catch (e: any) {
    ElMessage.info('暂无可用解读')
  } finally {
    loadingLatest.value = false
  }
}

async function pollAnalysis(taskId: string) {
  for (let i = 0; i < 60; i++) {
    try {
      const res = await calendarApi.getAnalysis(taskId)
      const doc: any = res.data
      if (doc && doc.status) {
        analysisTask.value = doc
        if (doc.status === 'completed' || doc.status === 'failed') return
      }
    } catch {}
    await new Promise(resolve => setTimeout(resolve, 2000))
  }
}

watch(
  () => selectedModel.value,
  async (newVal, oldVal) => {
    if (!analysisOpen.value) return
    if (!selected.value) return
    if (!newVal || newVal === oldVal) return
    await analyze(selected.value, true)
  },
)

async function initializeModelSettings() {
  try {
    const defaultModels = await configApi.getDefaultModels()
    selectedModel.value = defaultModels.deep_analysis_model || defaultModels.quick_analysis_model
    const llmConfigs = await configApi.getLLMConfigs()
    availableModels.value = llmConfigs.filter((config: any) => config.enabled)
  } catch (e) {
    selectedModel.value = 'deepseek-chat'
  }
}

onMounted(async () => {
  await initializeModelSettings()
  await sync()
})

onActivated(() => {
  fetchList()
})
</script>

<style scoped lang="scss">
.page {
  .page-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 16px;

    .title {
      margin: 0;
      font-size: 22px;
      font-weight: 700;
      color: var(--el-text-color-primary);
    }
    .subtitle {
      margin-top: 6px;
      font-size: 13px;
      color: var(--el-text-color-regular);
    }
    .actions {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
  }

  .time-cell {
    .date {
      font-weight: 600;
      color: var(--el-text-color-primary);
    }
    .time {
      font-size: 12px;
      color: var(--el-text-color-regular);
      margin-top: 2px;
    }
  }

  .detail-title {
    font-size: 18px;
    font-weight: 700;
    color: var(--el-text-color-primary);
    margin-bottom: 8px;
  }

  .detail-meta {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 16px;
  }

  .detail-section {
    margin-bottom: 14px;
    .detail-label {
      font-weight: 600;
      color: var(--el-text-color-primary);
      margin-bottom: 6px;
    }
    .detail-text {
      font-size: 13px;
      color: var(--el-text-color-regular);
      line-height: 1.6;
    }
  }

  .detail-actions {
    display: flex;
    gap: 10px;
  }

  .analysis-meta {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 12px;
  }

  .analysis-model-config {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;

    .label {
      font-size: 13px;
      color: var(--el-text-color-secondary);
    }
  }

  .analysis-body {
    .block {
      margin-bottom: 18px;
      .block-title {
        font-weight: 700;
        color: var(--el-text-color-primary);
        margin-bottom: 8px;
      }
      .block-text {
        font-size: 13px;
        color: var(--el-text-color-regular);
        line-height: 1.7;
      }
    }
  }

  .tradability {
    display: flex;
    gap: 12px;
    align-items: center;
    .score {
      font-size: 28px;
      font-weight: 800;
      color: var(--el-color-primary);
      min-width: 56px;
    }
    .reason {
      color: var(--el-text-color-regular);
      line-height: 1.6;
      font-size: 13px;
    }
  }

  .tag {
    margin: 4px 6px 0 0;
  }
}
</style>
