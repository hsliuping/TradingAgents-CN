<template>
  <div class="unified-task-center">
    <div class="page-header">
      <h1 class="page-title">
        <el-icon><List /></el-icon>
        统一任务中心
      </h1>
      <p class="page-description">查看并管理所有类型的分析任务（股票分析、持仓分析、交易复盘等）</p>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" style="margin-bottom: 16px">
      <el-col :span="4">
        <el-card shadow="never">
          <div class="stat">
            <div class="value">{{ stats.total }}</div>
            <div class="label">总任务</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never">
          <div class="stat">
            <div class="value">{{ stats.pending }}</div>
            <div class="label">等待中</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never">
          <div class="stat">
            <div class="value">{{ stats.processing }}</div>
            <div class="label">进行中</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never">
          <div class="stat">
            <div class="value">{{ stats.completed }}</div>
            <div class="label">已完成</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never">
          <div class="stat">
            <div class="value">{{ stats.failed }}</div>
            <div class="label">失败</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never">
          <div class="stat">
            <div class="value">{{ stats.cancelled }}</div>
            <div class="label">已取消</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选表单 -->
    <el-card class="filter-card" shadow="never">
      <el-form :inline="true" @submit.prevent>
        <el-form-item label="任务类型">
          <el-select v-model="filters.taskType" clearable placeholder="全部" style="width: 140px">
            <el-option label="全部" value="" />
            <el-option v-for="(name, type) in TaskTypeNames" :key="type" :label="name" :value="type" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" clearable placeholder="全部" style="width: 120px">
            <el-option label="全部" value="" />
            <el-option v-for="(name, status) in TaskStatusNames" :key="status" :label="name" :value="status" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="applyFilters" :loading="loading">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
          <el-button @click="refreshList" :loading="loading">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 任务列表 -->
    <el-card class="list-card" shadow="never">
      <el-table :data="taskList" v-loading="loading" style="width: 100%">
        <el-table-column prop="task_id" label="任务ID" width="200" show-overflow-tooltip />
        <el-table-column label="任务类型" width="120">
          <template #default="{ row }">
            {{ TaskTypeNames[row.task_type] || row.task_type }}
          </template>
        </el-table-column>
        <el-table-column label="股票/代码" width="120">
          <template #default="{ row }">
            {{ row.symbol || row.code || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="市场" width="80">
          <template #default="{ row }">
            {{ row.market || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="TaskStatusColors[row.status]">
              {{ TaskStatusNames[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="150">
          <template #default="{ row }">
            <el-progress 
              :percentage="row.progress" 
              :status="row.status === 'failed' ? 'exception' : (row.status === 'completed' ? 'success' : undefined)"
            />
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="160">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="执行时间" width="100">
          <template #default="{ row }">
            {{ row.execution_time > 0 ? row.execution_time.toFixed(2) + 's' : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="text" size="small" @click="viewDetail(row)">详情</el-button>
            <el-button 
              v-if="row.status === 'pending' || row.status === 'processing'" 
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
              @click="showError(row)"
            >
              查看错误
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadList"
        @current-change="loadList"
        style="margin-top: 16px; justify-content: flex-end"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { List, Refresh } from '@element-plus/icons-vue'
import {
  getTaskList,
  getTaskStatistics,
  cancelTask as cancelTaskApi,
  getTaskDetail,
  TaskType,
  TaskStatus,
  TaskTypeNames,
  TaskStatusNames,
  TaskStatusColors,
  type TaskListItem,
  type TaskStatistics
} from '@/api/unifiedTasks'

// ==================== 状态管理 ====================

const loading = ref(false)
const taskList = ref<TaskListItem[]>([])
const stats = ref<TaskStatistics>({
  total: 0,
  pending: 0,
  processing: 0,
  completed: 0,
  failed: 0,
  cancelled: 0
})

// 分页
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

// 筛选
const filters = ref({
  taskType: '',
  status: ''
})

// 定时刷新
let refreshTimer: any = null

// ==================== 方法 ====================

/**
 * 加载任务列表
 */
const loadList = async () => {
  loading.value = true
  try {
    // 不传 limit 参数，让后端返回所有记录，由前端处理分页
    const params: any = {
      skip: (currentPage.value - 1) * pageSize.value
    }

    if (filters.value.taskType) {
      params.task_type = filters.value.taskType
    }
    if (filters.value.status) {
      params.status = filters.value.status
    }

    const res = await getTaskList(params)
    const data = (res as any)?.data?.data || (res as any)?.data || {}

    // 获取所有任务，然后在前端进行分页
    const allTasks = data.tasks || []
    const startIdx = (currentPage.value - 1) * pageSize.value
    const endIdx = startIdx + pageSize.value

    taskList.value = allTasks.slice(startIdx, endIdx)
    total.value = allTasks.length
  } catch (e: any) {
    ElMessage.error(e?.message || '加载任务列表失败')
  } finally {
    loading.value = false
  }
}

/**
 * 加载统计信息
 */
const loadStats = async () => {
  try {
    const res = await getTaskStatistics()
    const data = (res as any)?.data?.data || (res as any)?.data || {}
    stats.value = data
  } catch (e: any) {
    console.error('加载统计信息失败:', e)
  }
}

/**
 * 应用筛选
 */
const applyFilters = () => {
  currentPage.value = 1
  loadList()
}

/**
 * 重置筛选
 */
const resetFilters = () => {
  filters.value = {
    taskType: '',
    status: ''
  }
  currentPage.value = 1
  loadList()
}

/**
 * 刷新列表
 */
const refreshList = () => {
  loadList()
  loadStats()
}

/**
 * 查看任务详情
 */
const viewDetail = async (row: TaskListItem) => {
  try {
    const res = await getTaskDetail(row.task_id)
    const data = (res as any)?.data?.data || (res as any)?.data || {}

    // 使用 ElMessageBox 显示详情
    await ElMessageBox.alert(
      `<pre>${JSON.stringify(data, null, 2)}</pre>`,
      '任务详情',
      {
        confirmButtonText: '确定',
        dangerouslyUseHTMLString: true,
        customStyle: {
          width: '800px'
        }
      }
    )
  } catch (e: any) {
    if (e !== 'cancel' && e !== 'close') {
      ElMessage.error(e?.message || '获取任务详情失败')
    }
  }
}

/**
 * 取消任务
 */
const cancelTask = async (row: TaskListItem) => {
  try {
    await ElMessageBox.confirm(
      `确定要取消任务 "${row.task_id}" 吗？`,
      '确认操作',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    loading.value = true
    await cancelTaskApi(row.task_id)
    ElMessage.success('任务已取消')
    await refreshList()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.message || '取消任务失败')
    }
  } finally {
    loading.value = false
  }
}

/**
 * 显示错误信息
 */
const showError = async (row: TaskListItem) => {
  const errorMessage = row.error_message || '未知错误'

  await ElMessageBox.alert(
    errorMessage.replace(/\n/g, '<br>'),
    '错误详情',
    {
      confirmButtonText: '确定',
      type: 'error',
      dangerouslyUseHTMLString: true,
      customStyle: {
        width: '600px'
      }
    }
  )
}

/**
 * 格式化时间
 */
const formatTime = (time: string) => {
  if (!time) return '-'
  const date = new Date(time)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

/**
 * 设置定时刷新
 */
const setupAutoRefresh = () => {
  // 每 10 秒刷新一次
  refreshTimer = setInterval(() => {
    loadList()
    loadStats()
  }, 10000)
}

// ==================== 生命周期 ====================

onMounted(() => {
  loadList()
  loadStats()
  setupAutoRefresh()
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
})
</script>

<style scoped lang="scss">
.unified-task-center {
  padding: 20px;

  .page-header {
    margin-bottom: 20px;

    .page-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 24px;
      font-weight: 600;
      color: #303133;
      margin: 0 0 8px 0;
    }

    .page-description {
      color: #909399;
      font-size: 14px;
      margin: 0;
    }
  }

  .stat {
    text-align: center;
    padding: 12px 0;

    .value {
      font-size: 28px;
      font-weight: 600;
      color: #409EFF;
      margin-bottom: 4px;
    }

    .label {
      font-size: 14px;
      color: #909399;
    }
  }

  .filter-card {
    margin-bottom: 16px;
  }

  .list-card {
    :deep(.el-card__body) {
      padding: 20px;
    }
  }
}
</style>


