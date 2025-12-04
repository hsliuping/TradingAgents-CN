<template>
  <div class="queue-management">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1 class="page-title">
        <el-icon><List /></el-icon>
        任务中心
      </h1>
      <p class="page-description">
        实时监控和管理分析任务状态
      </p>
    </div>

    <!-- 队列任务列表 -->
    <el-card class="queue-list-card" header="任务队列">
      <template #header>
        <div class="card-header">
          <span>任务队列</span>
          <div class="header-actions">
            <el-button type="text" @click="refreshQueue">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
            <el-button type="text" @click="clearCompleted">
              <el-icon><Delete /></el-icon>
              清理已完成
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="queueTasks" v-loading="loading" style="width: 100%" @mouseenter="isInteracting = true" @mouseleave="isInteracting = false">
        <el-table-column prop="task_id" label="任务ID" width="200">
          <template #default="{ row }">
            <el-link type="primary" @click="viewTaskDetail(row)">
              {{ row.task_id.substring(0, 8) }}...
            </el-link>
          </template>
        </el-table-column>

        <el-table-column prop="stock_code" label="股票代码" width="120" />
        <el-table-column prop="stock_name" label="股票名称" width="150" />

        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="progress" label="进度" width="150">
          <template #default="{ row }">
            <el-progress
              :percentage="row.progress"
              :status="getProgressStatus(row.status)"
              :stroke-width="8"
            />
          </template>
        </el-table-column>

        <el-table-column prop="priority" label="优先级" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.priority > 0" type="warning" size="small">
              高 ({{ row.priority }})
            </el-tag>
            <span v-else>普通</span>
          </template>
        </el-table-column>

        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>

        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'pending'"
              type="text"
              size="small"
              @click="cancelTask(row)"
            >
              取消
            </el-button>
            <el-button
              v-if="row.status === 'failed'"
              type="text"
              size="small"
              @click="retryTask(row)"
            >
              重试
            </el-button>
            <el-button
              v-if="row.status === 'completed'"
              type="text"
              size="small"
              @click="viewResult(row)"
            >
              查看结果
            </el-button>
            <el-button type="text" size="small" @click="viewTaskDetail(row)">
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[20, 50, 100]"
          :total="totalTasks"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <!-- 查看结果弹窗 -->
    <el-dialog v-model="resultDialogVisible" title="任务结果" width="60%">
      <div v-if="resultData">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="股票代码">{{ resultData.stock_symbol || resultData.stock_code || '-' }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ getStatusText(deriveStatusForDialog(resultData, currentTaskRow)) }}</el-descriptions-item>
        </el-descriptions>
        <div style="margin-top: 16px;">
          <h4>建议</h4>
          <div class="markdown-content" v-html="renderMarkdown(resultData.recommendation || '无')"></div>
        </div>
        <div style="margin-top: 16px;">
          <h4>摘要</h4>
          <div class="markdown-content" v-html="renderMarkdown(resultData.summary || '无')"></div>
        </div>
      </div>
      <template #footer>
        <el-button @click="resultDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="openReportDialog">查看报告详情</el-button>
      </template>
    </el-dialog>

    <!-- 任务详情弹窗 -->
    <el-dialog v-model="detailDialogVisible" title="任务详情" width="50%">
      <div v-if="detailData">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="任务ID">{{ detailData.task_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ getStatusText(deriveStatusForDialog(detailData, currentTaskRow)) }}</el-descriptions-item>
          <el-descriptions-item label="进度">{{ (detailData.progress ?? 0) + '%' }}</el-descriptions-item>
          <el-descriptions-item label="开始时间">{{ formatTime(detailData.start_time || detailData.created_at || new Date().toISOString()) }}</el-descriptions-item>
        </el-descriptions>
      </div>
    </el-dialog>

    <!-- 报告详情弹窗 -->
    <el-dialog v-model="reportDialogVisible" title="报告详情" width="70%">
      <template v-if="reportSections.length > 0">
        <el-tabs v-model="activeReportTab">
          <el-tab-pane
            v-for="(sec, idx) in reportSections"
            :key="sec.key || idx"
            :label="sec.title"
            :name="String(idx)"
          >
            <div
              v-if="typeof sec.content === 'string'"
              class="markdown-content"
              v-html="renderMarkdown(sec.content)"
            ></div>
            <div v-else class="json-content">
              <pre>{{ JSON.stringify(sec.content, null, 2) }}</pre>
            </div>
          </el-tab-pane>
        </el-tabs>
      </template>
      <template v-else>
        <el-empty description="暂无可展示的报告内容" />
      </template>
    </el-dialog>

  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'

import { analysisApi } from '@/api/analysis'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { marked } from 'marked'

// 简单Markdown渲染，与单股分析保持一致风格
marked.setOptions({ breaks: true, gfm: true })
const renderMarkdown = (content: string) => {
  if (!content) return ''
  try {
    return marked.parse(content) as string
  } catch (e) {
    return `<pre style="white-space: pre-wrap; font-family: inherit;">${content}</pre>`
  }
}

import {
  List,
  Refresh,
  Delete
} from '@element-plus/icons-vue'

// 路由
const router = useRouter()

// 响应式数据
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const totalTasks = ref(0)



const queueTasks = ref<any[]>([])

// 当前行引用（用于弹窗状态兜底）
const currentTaskRow = ref<any | null>(null)

// 结果/详情/报告 弹窗状态
const resultDialogVisible = ref(false)
const resultData = ref<any | null>(null)
const detailDialogVisible = ref(false)
const detailData = ref<any | null>(null)
const reportDialogVisible = ref(false)
const reportSections = ref<Array<{ key: string; title: string; content: any }>>([])
const activeReportTab = ref('0')

// 是否处于用户交互中（鼠标悬停、选择等），用于抑制自动刷新
const isInteracting = ref(false)

// 定时器
let refreshTimer: NodeJS.Timeout | null = null
// const AUTO_REFRESH_MS = 30000 // 30秒（已关闭自动刷新）


// 方法

// 统一的状态归一化
const normalizeStatusValue = (s?: string): string => {
  if (!s) return 'pending'
  if (s === 'running') return 'processing'
  if (s === 'cancelled') return 'cancelled'
  return s
}

const deriveStatusForDialog = (data: any, row: any): string => {
  const s = data?.status ?? row?.status
  if (s) return normalizeStatusValue(s)
  if (typeof data?.success === 'boolean') return data.success ? 'completed' : 'failed'
  if (typeof data?.progress === 'number') return data.progress >= 100 ? 'completed' : (data.progress > 0 ? 'processing' : 'pending')
  if (data?.summary || data?.recommendation) return 'completed'

  return 'pending'
}

const refreshQueue = async () => {
  loading.value = true
  try {
    const res = await analysisApi.getTaskList({
      limit: pageSize.value,
      offset: (currentPage.value - 1) * pageSize.value,
    })

    // 后端统一返回 ApiResponse，数据在 res.data.data
    const body = res?.data?.data || {}
    const tasksRaw = body?.tasks || []

    const tasks = tasksRaw.map((t: any) => ({
      task_id: t.task_id,
      stock_code: t.stock_code,
      stock_name: t.stock_name || '',
      status: normalizeStatusValue(t.status),
      progress: typeof t.progress === 'number' ? t.progress : 0,
      priority: 0,
      created_at: t.start_time || new Date().toISOString(),
    }))

    queueTasks.value = tasks
    totalTasks.value = body?.total ?? tasks.length
    ElMessage.success('队列数据已刷新')
  } catch (error) {
    ElMessage.error('刷新失败')
  } finally {
    loading.value = false
  }
}

const clearCompleted = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要清理所有已完成的任务吗？',
      '确认清理',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    ElMessage.success('已完成任务已清理')
  } catch {
    // 用户取消
  }
}

const cancelTask = async (task: any) => {
  try {
    await ElMessageBox.confirm(
      `确定要取消任务 ${task.task_id} 吗？`,
      '确认取消',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    ElMessage.success('任务已取消')
  } catch {
    // 用户取消
  }
}

const retryTask = (task: any) => {
  ElMessage.success(`任务 ${task.task_id} 已重新加入队列`)
}

const viewResult = async (task: any) => {
  try {
    currentTaskRow.value = task
    const res = await analysisApi.getTaskResult(task.task_id)
    const payload = res?.data?.data ?? res?.data ?? res
    // 可能返回 { success, data, message }
    const success = (res?.data?.success ?? payload?.success ?? true) as boolean
    const data = payload?.data ?? payload
    if (!success || !data) {
      ElMessage.warning(res?.data?.message || '任务结果暂不可用')
      return
    }
    resultData.value = data
    resultDialogVisible.value = true
  } catch (e) {
    ElMessage.error('获取结果失败')
  }
}

const viewTaskDetail = async (task: any) => {
  try {
    currentTaskRow.value = task
    // 仅调用 /status，避免无效的 /details 404 噪音
    const res = await analysisApi.getTaskStatus(task.task_id)
    // 响应拦截器已返回 response.data，所以 res 就是 ApiResponse<T>
    const data = res?.data
    if (!data) {
      ElMessage.warning('暂无详情数据')
      return
    }
    detailData.value = data
    detailDialogVisible.value = true
  } catch (e) {
    ElMessage.error('获取任务详情失败')
  }
}

const openReportDialog = () => {
  // 优先使用 task_id，其次 analysis_id（后端已兼容 task_id/analysis_id/_id）
  const id = currentTaskRow.value?.task_id
    || resultData.value?.task_id
    || detailData.value?.task_id
    || resultData.value?.analysis_id
    || detailData.value?.result_data?.analysis_id
    || currentTaskRow.value?.analysis_id
  if (!id) {
    ElMessage.warning('未找到报告ID，无法跳转')
    return
  }
  resultDialogVisible.value = false
  router.push({ name: 'ReportDetail', params: { id } })
}


const getStatusType = (status: string): 'success' | 'info' | 'warning' | 'danger' => {
  const statusMap: Record<string, 'success' | 'info' | 'warning' | 'danger'> = {
    pending: 'info',
    processing: 'warning',
    completed: 'success',
    failed: 'danger',
    cancelled: 'info'
  }
  return statusMap[status] ?? 'info'
}

const getStatusText = (status: string) => {
  const statusMap: Record<string, string> = {
    pending: '等待中',
    processing: '处理中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消'
  }
  return statusMap[status] || status
}

const getProgressStatus = (status: string) => {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'exception'
  return undefined
}

const formatTime = (time: string) => {
  return new Date(time).toLocaleString('zh-CN')
}

const handleSizeChange = (size: number) => {
  pageSize.value = size
  currentPage.value = 1
}

const handleCurrentChange = (page: number) => {
  currentPage.value = page
}

// 监听分页变化，自动刷新
watch([currentPage, pageSize], () => {
  refreshQueue()
})

// 生命周期
onMounted(async () => {
  // 首次进入立即拉取一次
  await refreshQueue()
  // 自动刷新已关闭，如需重新启用可恢复为 setInterval
  // refreshTimer = setInterval(() => { refreshQueue() }, AUTO_REFRESH_MS)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
})
</script>

<style lang="scss" scoped>
.queue-management {
  .page-header {
    margin-bottom: 24px;

    .page-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 24px;
      font-weight: 600;
      color: var(--el-text-color-primary);
      margin: 0 0 8px 0;
    }

    .page-description {
      color: var(--el-text-color-regular);
      margin: 0;
    }
  }

  .stats-row {
    margin-bottom: 24px;

    .stat-card {
      .stat-content {
        display: flex;
        align-items: center;
        gap: 16px;

        .stat-icon {
          width: 48px;
          height: 48px;
          border-radius: 12px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 24px;
          color: white;

          &.pending {
            background: linear-gradient(135deg, #909399, #c0c4cc);
          }

          &.processing {
            background: linear-gradient(135deg, #e6a23c, #f7ba2a);
          }

          &.completed {
            background: linear-gradient(135deg, #67c23a, #85ce61);
          }

          &.failed {
            background: linear-gradient(135deg, #f56c6c, #f78989);
          }
        }

        .stat-info {
          .stat-value {
            font-size: 24px;
            font-weight: 600;
            color: var(--el-text-color-primary);
            line-height: 1;
          }

          .stat-label {
            font-size: 14px;
            color: var(--el-text-color-regular);
            margin-top: 4px;
          }
        }
      }
    }
  }

  .queue-list-card {
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;

      .header-actions {
        display: flex;
        gap: 8px;
      }
    }

    .pagination-wrapper {
      display: flex;
      justify-content: center;
      margin-top: 24px;
    }
  }
}
</style>
