<template>
  <el-card class="running-tasks-card" shadow="never">
    <template #header>
      <div class="card-header">
        <span class="header-title">
          <el-icon><VideoPlay /></el-icon>
          进行中任务
          <el-badge v-if="runningTasks.length > 0" :value="runningTasks.length" type="primary" />
        </span>
        <el-button text size="small" @click="$emit('view-all')">
          查看全部 <el-icon><ArrowRight /></el-icon>
        </el-button>
      </div>
    </template>

    <div v-if="loading" class="card-loading">
      <el-skeleton :rows="3" animated />
    </div>

    <div v-else-if="runningTasks.length === 0" class="empty-state">
      <el-icon class="empty-icon"><CircleCheck /></el-icon>
      <p>当前没有进行中的任务</p>
      <el-button type="primary" size="small" @click="$emit('start-analysis')">
        <el-icon><TrendCharts /></el-icon>
        开始新分析
      </el-button>
    </div>

    <div v-else class="task-list">
      <div
        v-for="task in runningTasks.slice(0, 5)"
        :key="task.task_id"
        class="task-item"
        @click="$emit('view-task', task)"
      >
        <div class="task-type-icon" :class="getTaskTypeClass(task)">
          <el-icon><component :is="getTaskTypeIcon(task)" /></el-icon>
        </div>
        <div class="task-info">
          <div class="task-title">
            <span class="task-stock">{{ formatTaskTitle(task) }}</span>
            <el-tag size="small" :type="getStatusTagType(task.status)" effect="light">
              {{ getStatusText(task.status) }}
            </el-tag>
          </div>
          <div class="task-meta">
            <span class="task-progress" v-if="task.progress > 0">
              <el-progress
                :percentage="task.progress"
                :stroke-width="4"
                :show-text="false"
                :duration="1"
                striped
                striped-flow
                style="width: 100px;"
              />
              <span class="progress-text">{{ task.progress }}%</span>
            </span>
            <span class="task-duration" v-else-if="task.started_at">
              已运行 {{ formatDuration(task.started_at) }}
            </span>
            <span class="task-type-label">{{ getTaskTypeLabel(task.task_type) }}</span>
          </div>
        </div>
        <el-icon class="task-arrow"><ArrowRight /></el-icon>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import {
  VideoPlay, ArrowRight, CircleCheck, TrendCharts,
  Files, PieChart, DocumentChecked, Search, DataAnalysis
} from '@element-plus/icons-vue'
import { analysisApi } from '@/api/analysis'

defineEmits<{
  (e: 'view-all'): void
  (e: 'view-task', task: any): void
  (e: 'start-analysis'): void
}>()

const loading = ref(true)
const runningTasks = ref<any[]>([])
let timer: ReturnType<typeof setInterval> | null = null

const RUNNING_STATUSES = ['pending', 'processing', 'running']

const loadRunningTasks = async () => {
  try {
    const res = await analysisApi.getTaskList({ status: 'running', limit: 10 })
    const body: any = (res as any)?.data?.data || (res as any)?.data || res || {}
    const tasks = body.tasks || []
    // 兼容 status=processing 的任务（部分任务用 processing 状态）
    runningTasks.value = tasks.filter((t: any) =>
      RUNNING_STATUSES.includes(t.status) || t.status === 'processing'
    )
  } catch (error) {
    console.error('加载进行中任务失败:', error)
    runningTasks.value = []
  } finally {
    loading.value = false
  }
}

const getTaskTypeIcon = (task: any) => {
  const typeMap: Record<string, any> = {
    stock_analysis: TrendCharts,
    etf_analysis: TrendCharts,
    batch_analysis: Files,
    position_analysis: PieChart,
    trade_review: DocumentChecked,
    portfolio_health: PieChart,
    market_overview: DataAnalysis,
    sector_analysis: Search,
    general: Search
  }
  return typeMap[task.task_type] || TrendCharts
}

const getTaskTypeClass = (task: any) => {
  return `type-${task.task_type || 'default'}`
}

const getTaskTypeLabel = (type?: string) => {
  const labelMap: Record<string, string> = {
    stock_analysis: '单股研究',
    etf_analysis: 'ETF 分析',
    batch_analysis: '批量分析',
    position_analysis: '持仓研究',
    trade_review: '复盘分析',
    portfolio_health: '持仓健康',
    market_overview: '市场概览',
    sector_analysis: '行业分析',
    general: '通用研究'
  }
  return labelMap[type || ''] || '分析任务'
}

const formatTaskTitle = (task: any) => {
  const code = task.stock_code || task.symbol || task.code || ''
  const name = task.stock_name || ''
  if (code && name) return `${code} ${name}`
  if (code) return code
  return task.task_id?.slice(0, 8) || '未命名任务'
}

const getStatusTagType = (status: string): 'success' | 'info' | 'warning' | 'danger' | 'primary' => {
  const map: Record<string, 'success' | 'info' | 'warning' | 'danger' | 'primary'> = {
    pending: 'info',
    processing: 'warning',
    running: 'warning',
    completed: 'success',
    failed: 'danger'
  }
  return map[status] || 'info'
}

const getStatusText = (status: string) => {
  const map: Record<string, string> = {
    pending: '等待中',
    processing: '处理中',
    running: '运行中',
    completed: '已完成',
    failed: '失败'
  }
  return map[status] || status
}

const formatDuration = (startTime: string) => {
  const start = new Date(startTime).getTime()
  if (Number.isNaN(start)) return ''
  const diff = Date.now() - start
  if (diff < 0) return ''
  const minutes = Math.floor(diff / 60000)
  const seconds = Math.floor((diff % 60000) / 1000)
  if (minutes >= 60) {
    const hours = Math.floor(minutes / 60)
    return `${hours}小时${minutes % 60}分`
  }
  if (minutes > 0) return `${minutes}分${seconds}秒`
  return `${seconds}秒`
}

onMounted(() => {
  loadRunningTasks()
  // 每 30 秒刷新一次进行中任务
  timer = setInterval(loadRunningTasks, 30000)
})

onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
})
</script>

<style lang="scss" scoped>
.running-tasks-card {
  height: 100%;

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .header-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 16px;
      font-weight: 600;
      color: var(--el-text-color-primary);
    }
  }

  .card-loading {
    padding: 12px 0;
  }

  .empty-state {
    text-align: center;
    padding: 32px 0;

    .empty-icon {
      font-size: 40px;
      color: var(--el-color-success);
      margin-bottom: 12px;
    }

    p {
      color: var(--el-text-color-secondary);
      margin-bottom: 16px;
    }
  }

  .task-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .task-item {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 12px;
    border: 1px solid var(--el-border-color-lighter);
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.3s ease;

    &:hover {
      border-color: var(--el-color-primary);
      background-color: var(--el-color-primary-light-9);

      .task-arrow {
        transform: translateX(4px);
        color: var(--el-color-primary);
      }
    }
  }

  .task-type-icon {
    width: 36px;
    height: 36px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    background: var(--el-color-primary-light-8);
    color: var(--el-color-primary);
    flex-shrink: 0;

    &.type-batch_analysis,
    &.type-position_analysis {
      background: rgba(230, 162, 60, 0.1);
      color: #e6a23c;
    }

    &.type-trade_review {
      background: rgba(103, 194, 58, 0.1);
      color: #67c23a;
    }
  }

  .task-info {
    flex: 1;
    min-width: 0;
  }

  .task-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 6px;

    .task-stock {
      font-size: 14px;
      font-weight: 600;
      color: var(--el-text-color-primary);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }

  .task-meta {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 12px;
    color: var(--el-text-color-secondary);

    .task-progress {
      display: flex;
      align-items: center;
      gap: 6px;

      .progress-text {
        color: var(--el-color-primary);
        font-weight: 500;
      }
    }

    .task-duration::before {
      content: '⏱ ';
    }
  }

  .task-arrow {
    color: var(--el-text-color-placeholder);
    transition: transform 0.3s ease, color 0.3s ease;
    flex-shrink: 0;
  }
}
</style>
