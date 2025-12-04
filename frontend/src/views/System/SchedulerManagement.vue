<template>
  <div class="scheduler-management">
    <!-- 页面标题和统计信息 -->
    <el-card class="header-card" shadow="never">
      <div class="header-content">
        <div class="title-section">
          <h2>
            <el-icon><Timer /></el-icon>
            定时任务管理
          </h2>
          <p class="subtitle">管理系统中的所有定时任务，支持暂停、恢复和手动触发</p>
        </div>
        
        <div class="stats-section" v-if="stats">
          <el-statistic title="总任务数" :value="stats.total_jobs">
            <template #prefix>
              <el-icon><List /></el-icon>
            </template>
          </el-statistic>
          <el-statistic title="运行中" :value="stats.running_jobs">
            <template #prefix>
              <el-icon color="#67C23A"><VideoPlay /></el-icon>
            </template>
          </el-statistic>
          <el-statistic title="已暂停" :value="stats.paused_jobs">
            <template #prefix>
              <el-icon color="#E6A23C"><VideoPause /></el-icon>
            </template>
          </el-statistic>
        </div>
      </div>
      
      <div class="actions">
        <el-button @click="loadJobs" :loading="loading" :icon="Refresh">刷新</el-button>
        <el-button @click="showHistoryDialog" :icon="Document">执行历史</el-button>
      </div>
    </el-card>

    <!-- 搜索和筛选 -->
    <el-card class="filter-card" shadow="never">
      <el-form :inline="true" class="filter-form">
        <el-form-item label="任务名称">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索任务名称"
            clearable
            :prefix-icon="Search"
            style="width: 240px"
            @clear="handleSearch"
            @input="handleSearch"
          />
        </el-form-item>

        <el-form-item label="数据源">
          <el-select
            v-model="filterDataSource"
            placeholder="全部数据源"
            clearable
            style="width: 180px"
            @change="handleSearch"
          >
            <el-option label="全部数据源" value="" />
            <el-option label="Tushare" value="Tushare" />
            <el-option label="AKShare" value="AKShare" />
            <el-option label="BaoStock" value="BaoStock" />
            <el-option label="多数据源" value="多数据源" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>

        <el-form-item label="状态">
          <el-select
            v-model="filterStatus"
            placeholder="全部状态"
            clearable
            style="width: 150px"
            @change="handleSearch"
          >
            <el-option label="全部状态" value="" />
            <el-option label="运行中" value="running" />
            <el-option label="已暂停" value="paused" />
          </el-select>
        </el-form-item>

        <el-form-item>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 任务列表 -->
    <el-card class="table-card" shadow="never">
      <el-table
        :data="filteredJobs"
        v-loading="loading"
        stripe
        style="width: 100%"
        :default-sort="{ prop: 'paused', order: 'ascending' }"
      >
        <el-table-column prop="name" label="任务名称" min-width="200" sortable>
          <template #default="{ row }">
            <div class="job-name">
              <el-tag :type="row.paused ? 'warning' : 'success'" size="small">
                {{ row.paused ? '已暂停' : '运行中' }}
              </el-tag>
              <span class="name-text">{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="display_name" label="触发器名称" min-width="150">
          <template #default="{ row }">
            <el-text v-if="row.display_name" size="small">{{ row.display_name }}</el-text>
            <el-text v-else type="info" size="small">-</el-text>
          </template>
        </el-table-column>

        <el-table-column prop="trigger" label="触发器" min-width="180">
          <template #default="{ row }">
            <el-text size="small" type="info">{{ formatTrigger(row.trigger) }}</el-text>
          </template>
        </el-table-column>

        <el-table-column prop="description" label="备注" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <el-text v-if="row.description" size="small">{{ row.description }}</el-text>
            <el-text v-else type="info" size="small">-</el-text>
          </template>
        </el-table-column>

        <el-table-column prop="next_run_time" label="下次执行时间" min-width="180" sortable>
          <template #default="{ row }">
            <div v-if="row.next_run_time">
              <el-text size="small">{{ formatDateTime(row.next_run_time) }}</el-text>
              <br />
              <el-text size="small" type="info">{{ formatRelativeTime(row.next_run_time) }}</el-text>
            </div>
            <el-text v-else type="warning" size="small">已暂停</el-text>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="340" fixed="right">
          <template #default="{ row }">
            <el-button-group>
              <el-button
                size="small"
                :icon="Edit"
                @click="showEditDialog(row)"
              >
                编辑
              </el-button>
              <el-button
                v-if="!row.paused"
                size="small"
                type="warning"
                :icon="VideoPause"
                @click="handlePause(row)"
                :loading="actionLoading[row.id]"
              >
                暂停
              </el-button>
              <el-button
                v-else
                size="small"
                type="success"
                :icon="VideoPlay"
                @click="handleResume(row)"
                :loading="actionLoading[row.id]"
              >
                恢复
              </el-button>
              <el-button
                size="small"
                type="primary"
                :icon="Promotion"
                @click="handleTrigger(row)"
                :loading="actionLoading[row.id]"
              >
                立即执行
              </el-button>
              <el-button
                size="small"
                :icon="View"
                @click="showJobDetail(row)"
              >
                详情
              </el-button>
            </el-button-group>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 编辑任务元数据对话框 -->
    <el-dialog
      v-model="editDialogVisible"
      title="编辑任务信息"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form v-if="editingJob" :model="editForm" label-width="120px">
        <el-form-item label="任务ID">
          <el-text>{{ editingJob.id }}</el-text>
        </el-form-item>
        <el-form-item label="任务名称">
          <el-text>{{ editingJob.name }}</el-text>
        </el-form-item>
        <el-form-item label="触发器名称">
          <el-input
            v-model="editForm.display_name"
            placeholder="请输入触发器名称（可选）"
            clearable
            maxlength="50"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="editForm.description"
            type="textarea"
            :rows="4"
            placeholder="请输入备注信息（可选）"
            clearable
            maxlength="200"
            show-word-limit
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveMetadata" :loading="saveLoading">保存</el-button>
      </template>
    </el-dialog>

    <!-- 任务详情对话框 -->
    <el-dialog
      v-model="detailDialogVisible"
      title="任务详情"
      width="700px"
      :close-on-click-modal="false"
    >
      <el-descriptions v-if="currentJob" :column="1" border>
        <el-descriptions-item label="任务ID">{{ currentJob.id }}</el-descriptions-item>
        <el-descriptions-item label="任务名称">{{ currentJob.name }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="currentJob.paused ? 'warning' : 'success'">
            {{ currentJob.paused ? '已暂停' : '运行中' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="触发器">{{ currentJob.trigger }}</el-descriptions-item>
        <el-descriptions-item label="下次执行时间">
          {{ currentJob.next_run_time ? formatDateTime(currentJob.next_run_time) : '已暂停' }}
        </el-descriptions-item>
        <el-descriptions-item label="执行函数" v-if="currentJob.func">
          <el-text size="small" type="info">{{ currentJob.func }}</el-text>
        </el-descriptions-item>
        <el-descriptions-item label="参数" v-if="currentJob.kwargs">
          <pre class="code-block">{{ JSON.stringify(currentJob.kwargs, null, 2) }}</pre>
        </el-descriptions-item>
      </el-descriptions>

      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="showJobHistory(currentJob!)">查看执行历史</el-button>
      </template>
    </el-dialog>

    <!-- 执行历史对话框 -->
    <el-dialog
      v-model="historyDialogVisible"
      title="执行历史"
      width="1200px"
      :close-on-click-modal="false"
    >
      <el-tabs v-model="activeHistoryTab" @tab-change="handleHistoryTabChange">
        <!-- 手动操作历史 -->
        <el-tab-pane label="手动操作历史" name="manual">
          <el-table :data="historyList" v-loading="historyLoading" stripe max-height="500">
            <el-table-column prop="job_name" label="任务名称" min-width="200" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag
                  :type="row.status === 'success' ? 'success' : row.status === 'failed' ? 'danger' : row.status === 'running' ? 'info' : 'warning'"
                  size="small"
                >
                  {{ formatExecutionStatus(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="progress" label="进度" width="150">
              <template #default="{ row }">
                <div v-if="row.status === 'running' && row.progress !== undefined">
                  <el-progress :percentage="row.progress" :stroke-width="6" />
                  <el-text v-if="row.processed_items && row.total_items" size="small" type="info" style="margin-top: 4px">
                    {{ row.processed_items }}/{{ row.total_items }}
                  </el-text>
                </div>
                <el-text v-else-if="row.progress !== undefined" type="info" size="small">{{ row.progress }}%</el-text>
                <el-text v-else type="info" size="small">-</el-text>
              </template>
            </el-table-column>
            <el-table-column prop="progress_message" label="当前操作" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">
                <el-text v-if="row.progress_message" size="small">
                  {{ row.progress_message }}
                </el-text>
                <el-text v-else-if="row.current_item" size="small">
                  {{ row.current_item }}
                </el-text>
                <el-text v-else type="info" size="small">-</el-text>
              </template>
            </el-table-column>
            <el-table-column prop="timestamp" label="执行时长" width="180">
              <template #default="{ row }">
                <span v-if="row.execution_time !== undefined && row.execution_time !== null">
                  {{ row.execution_time.toFixed(2) }}秒
                </span>
                <span v-else-if="row.status === 'running' && row.timestamp">
                  {{ calculateRunningTime(row.updated_at || row.timestamp) }}
                </span>
                <el-text v-else type="info" size="small">-</el-text>
              </template>
            </el-table-column>
            <el-table-column prop="updated_at" label="更新时间" width="180">
              <template #default="{ row }">
                {{ formatDateTime(row.updated_at || row.timestamp) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="220" fixed="right">
              <template #default="{ row }">
                <el-button
                  v-if="row.error_message || row.status === 'running'"
                  link
                  type="primary"
                  size="small"
                  @click="showExecutionDetail(row)"
                >
                  详情
                </el-button>
                <el-button
                  v-if="row.status === 'running'"
                  link
                  type="warning"
                  size="small"
                  @click="handleCancelExecution(row)"
                >
                  终止
                </el-button>
                <el-button
                  v-if="row.status === 'running'"
                  link
                  type="danger"
                  size="small"
                  @click="handleMarkFailed(row)"
                >
                  标记失败
                </el-button>
                <el-button
                  v-if="row.status !== 'running'"
                  link
                  type="danger"
                  size="small"
                  @click="handleDeleteExecution(row)"
                >
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-pagination
            v-if="historyTotal > historyPageSize"
            class="pagination"
            :current-page="historyPage"
            :page-size="historyPageSize"
            :total="historyTotal"
            layout="total, prev, pager, next"
            @current-change="handleHistoryPageChange"
          />
        </el-tab-pane>

        <!-- 自动执行监控 -->
        <el-tab-pane label="自动执行监控" name="execution">
          <!-- 筛选条件 -->
          <el-form :inline="true" style="margin-bottom: 16px">
            <el-form-item label="状态">
              <el-select
                v-model="executionStatusFilter"
                placeholder="全部状态"
                clearable
                style="width: 150px"
                @change="loadExecutions"
              >
                <el-option label="全部状态" value="" />
                <el-option label="执行中" value="running" />
                <el-option label="成功" value="success" />
                <el-option label="失败" value="failed" />
                <el-option label="错过" value="missed" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button :icon="Refresh" @click="loadExecutions">刷新</el-button>
            </el-form-item>
          </el-form>

          <el-table :data="executionList" v-loading="executionLoading" stripe max-height="500">
            <el-table-column prop="job_name" label="任务名称" min-width="200" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag
                  :type="row.status === 'success' ? 'success' : row.status === 'failed' ? 'danger' : row.status === 'running' ? 'info' : 'warning'"
                  size="small"
                >
                  {{ formatExecutionStatus(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="progress" label="进度" width="150">
              <template #default="{ row }">
                <div v-if="row.status === 'running' && row.progress !== undefined">
                  <el-progress :percentage="row.progress" :stroke-width="6" />
                  <el-text v-if="row.processed_items && row.total_items" size="small" type="info" style="margin-top: 4px">
                    {{ row.processed_items }}/{{ row.total_items }}
                  </el-text>
                </div>
                <el-text v-else-if="row.progress !== undefined" type="info" size="small">{{ row.progress }}%</el-text>
                <el-text v-else type="info" size="small">-</el-text>
              </template>
            </el-table-column>
            <el-table-column prop="progress_message" label="当前操作" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">
                <el-text v-if="row.progress_message" size="small">
                  {{ row.progress_message }}
                </el-text>
                <el-text v-else-if="row.current_item" size="small">
                  {{ row.current_item }}
                </el-text>
                <el-text v-else type="info" size="small">-</el-text>
              </template>
            </el-table-column>
            <el-table-column prop="execution_time" label="执行时长" width="180">
              <template #default="{ row }">
                <span v-if="row.execution_time !== undefined && row.execution_time !== null">
                  {{ row.execution_time.toFixed(2) }}秒
                </span>
                <span v-else-if="row.status === 'running' && row.timestamp">
                  {{ calculateRunningTime(row.updated_at || row.timestamp) }}
                </span>
                <el-text v-else type="info" size="small">-</el-text>
              </template>
            </el-table-column>
            <el-table-column prop="scheduled_time" label="计划时间" width="180">
              <template #default="{ row }">
                {{ formatDateTime(row.scheduled_time) }}
              </template>
            </el-table-column>
            <el-table-column prop="updated_at" label="更新时间" width="180">
              <template #default="{ row }">
                {{ formatDateTime(row.updated_at || row.timestamp) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="220" fixed="right">
              <template #default="{ row }">
                <el-button
                  v-if="row.error_message || row.status === 'running'"
                  link
                  type="primary"
                  size="small"
                  @click="showExecutionDetail(row)"
                >
                  详情
                </el-button>
                <el-button
                  v-if="row.status === 'running'"
                  link
                  type="warning"
                  size="small"
                  @click="handleCancelExecution(row)"
                >
                  终止
                </el-button>
                <el-button
                  v-if="row.status === 'running'"
                  link
                  type="danger"
                  size="small"
                  @click="handleMarkFailed(row)"
                >
                  标记失败
                </el-button>
                <el-button
                  v-if="row.status !== 'running'"
                  link
                  type="danger"
                  size="small"
                  @click="handleDeleteExecution(row)"
                >
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-pagination
            v-if="executionTotal > executionPageSize"
            class="pagination"
            :current-page="executionPage"
            :page-size="executionPageSize"
            :total="executionTotal"
            layout="total, prev, pager, next"
            @current-change="handleExecutionPageChange"
          />
        </el-tab-pane>
      </el-tabs>

      <template #footer>
        <el-button @click="historyDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 执行详情对话框 -->
    <el-dialog
      v-model="executionDetailDialogVisible"
      title="执行详情"
      width="800px"
      :close-on-click-modal="false"
    >
      <el-descriptions v-if="currentExecution" :column="1" border>
        <el-descriptions-item label="任务名称">
          {{ currentExecution.job_name }}
        </el-descriptions-item>
        <el-descriptions-item label="任务ID">
          {{ currentExecution.job_id }}
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag
            :type="currentExecution.status === 'success' ? 'success' : currentExecution.status === 'failed' ? 'danger' : currentExecution.status === 'running' ? 'info' : 'warning'"
          >
            {{ formatExecutionStatus(currentExecution.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="进度" v-if="currentExecution.status === 'running' && currentExecution.progress !== undefined">
          <el-progress :percentage="currentExecution.progress" :stroke-width="8" />
          <div v-if="currentExecution.processed_items && currentExecution.total_items" style="margin-top: 8px">
            <el-text size="small">已处理: {{ currentExecution.processed_items }} / {{ currentExecution.total_items }}</el-text>
          </div>
        </el-descriptions-item>
        <el-descriptions-item label="当前操作" v-if="currentExecution.progress_message || currentExecution.current_item">
          <el-text>{{ currentExecution.progress_message || currentExecution.current_item }}</el-text>
        </el-descriptions-item>
        <el-descriptions-item label="计划时间">
          {{ formatDateTime(currentExecution.scheduled_time) }}
        </el-descriptions-item>
        <el-descriptions-item label="更新时间">
          {{ formatDateTime(currentExecution.updated_at || currentExecution.timestamp) }}
        </el-descriptions-item>
        <el-descriptions-item label="执行时长" v-if="currentExecution.execution_time !== undefined">
          {{ currentExecution.execution_time.toFixed(2) }}秒
        </el-descriptions-item>
        <el-descriptions-item label="错误信息" v-if="currentExecution.error_message">
          <el-text type="danger">{{ currentExecution.error_message }}</el-text>
        </el-descriptions-item>
        <el-descriptions-item label="错误堆栈" v-if="currentExecution.traceback">
          <pre style="max-height: 300px; overflow-y: auto; background: #f5f5f5; padding: 12px; border-radius: 4px;">{{ currentExecution.traceback }}</pre>
        </el-descriptions-item>
      </el-descriptions>

      <template #footer>
        <el-button @click="executionDetailDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Timer,
  List,
  VideoPlay,
  VideoPause,
  Refresh,
  Document,
  Promotion,
  View,
  Edit,
  Search
} from '@element-plus/icons-vue'
import {
  getJobs,
  getJobDetail,
  pauseJob,
  resumeJob,
  triggerJob,
  updateJobMetadata,
  getSchedulerStats,
  getJobExecutions,
  getSingleJobExecutions,
  cancelExecution,
  markExecutionFailed,
  deleteExecution,
  type Job,
  type JobHistory,
  type JobExecution,
  type SchedulerStats
} from '@/api/scheduler'
import { formatDateTime, formatRelativeTime } from '@/utils/datetime'

// 数据
const loading = ref(false)
const jobs = ref<Job[]>([])
const stats = ref<SchedulerStats | null>(null)
const actionLoading = reactive<Record<string, boolean>>({})

// 搜索和筛选
const searchKeyword = ref('')
const filterDataSource = ref('')
const filterStatus = ref('')

// 编辑任务元数据
const editDialogVisible = ref(false)
const editingJob = ref<Job | null>(null)
const editForm = reactive({
  display_name: '',
  description: ''
})
const saveLoading = ref(false)

// 任务详情
const detailDialogVisible = ref(false)
const currentJob = ref<Job | null>(null)

// 执行历史
const historyDialogVisible = ref(false)
const historyLoading = ref(false)
const historyList = ref<JobHistory[]>([])
const historyTotal = ref(0)
const historyPage = ref(1)
const historyPageSize = ref(20)
const currentHistoryJobId = ref<string | null>(null)
const activeHistoryTab = ref('manual')

// 任务执行监控
const executionLoading = ref(false)
const executionList = ref<JobExecution[]>([])
const executionTotal = ref(0)
const executionPage = ref(1)
const executionPageSize = ref(20)
const executionStatusFilter = ref('')
const executionDetailDialogVisible = ref(false)
const currentExecution = ref<JobExecution | null>(null)

// 计算属性
const filteredJobs = computed(() => {
  let result = [...jobs.value]

  // 按任务名称搜索
  if (searchKeyword.value) {
    const keyword = searchKeyword.value.toLowerCase()
    result = result.filter(job =>
      job.name.toLowerCase().includes(keyword) ||
      job.id.toLowerCase().includes(keyword) ||
      (job.display_name && job.display_name.toLowerCase().includes(keyword)) ||
      (job.description && job.description.toLowerCase().includes(keyword))
    )
  }

  // 按数据源筛选
  if (filterDataSource.value) {
    if (filterDataSource.value === '其他') {
      // 其他：不包含 Tushare、AKShare、BaoStock、多数据源
      result = result.filter(job =>
        !job.name.includes('Tushare') &&
        !job.name.includes('AKShare') &&
        !job.name.includes('BaoStock') &&
        !job.name.includes('多数据源')
      )
    } else {
      result = result.filter(job => job.name.includes(filterDataSource.value))
    }
  }

  // 按状态筛选
  if (filterStatus.value) {
    if (filterStatus.value === 'running') {
      result = result.filter(job => !job.paused)
    } else if (filterStatus.value === 'paused') {
      result = result.filter(job => job.paused)
    }
  }

  // 默认排序：运行中的任务优先（paused=false 排在前面）
  result.sort((a, b) => {
    // 先按状态排序（运行中优先）
    if (a.paused !== b.paused) {
      return a.paused ? 1 : -1
    }
    // 状态相同时按名称排序
    return a.name.localeCompare(b.name, 'zh-CN')
  })

  return result
})

// 方法
const loadJobs = async () => {
  loading.value = true
  try {
    const [jobsRes, statsRes] = await Promise.all([getJobs(), getSchedulerStats()])
    // ApiClient.get 返回 ApiResponse<T>，其中 data 字段就是我们需要的数据
    jobs.value = Array.isArray(jobsRes.data) ? jobsRes.data : []
    stats.value = statsRes.data || null
  } catch (error: any) {
    ElMessage.error(error.message || '加载任务列表失败')
    jobs.value = []
    stats.value = null
  } finally {
    loading.value = false
  }
}

const showEditDialog = (job: Job) => {
  editingJob.value = job
  editForm.display_name = job.display_name || ''
  editForm.description = job.description || ''
  editDialogVisible.value = true
}

const handleSaveMetadata = async () => {
  if (!editingJob.value) return

  try {
    saveLoading.value = true
    await updateJobMetadata(editingJob.value.id, {
      display_name: editForm.display_name || undefined,
      description: editForm.description || undefined
    })
    ElMessage.success('任务信息已更新')
    editDialogVisible.value = false
    await loadJobs()
  } catch (error: any) {
    ElMessage.error(error.message || '更新任务信息失败')
  } finally {
    saveLoading.value = false
  }
}

const showJobDetail = async (job: Job) => {
  try {
    const res = await getJobDetail(job.id)
    // request.get 已经返回了 response.data
    currentJob.value = res.data || null
    detailDialogVisible.value = true
  } catch (error: any) {
    ElMessage.error(error.message || '获取任务详情失败')
  }
}

const handlePause = async (job: Job) => {
  try {
    await ElMessageBox.confirm(`确定要暂停任务"${job.name}"吗？`, '确认暂停', {
      type: 'warning'
    })

    actionLoading[job.id] = true
    await pauseJob(job.id)
    ElMessage.success('任务已暂停')
    await loadJobs()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '暂停任务失败')
    }
  } finally {
    actionLoading[job.id] = false
  }
}

const handleResume = async (job: Job) => {
  try {
    actionLoading[job.id] = true
    await resumeJob(job.id)
    ElMessage.success('任务已恢复')
    await loadJobs()
  } catch (error: any) {
    ElMessage.error(error.message || '恢复任务失败')
  } finally {
    actionLoading[job.id] = false
  }
}

const handleTrigger = async (job: Job) => {
  try {
    await ElMessageBox.confirm(
      `确定要立即执行任务"${job.name}"吗？任务将在后台执行。`,
      '确认执行',
      {
        type: 'warning'
      }
    )

    actionLoading[job.id] = true
    await triggerJob(job.id)
    ElMessage.success('任务已触发执行')
    await loadJobs()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '触发任务失败')
    }
  } finally {
    actionLoading[job.id] = false
  }
}

const showJobHistory = async (job: Job) => {
  currentHistoryJobId.value = job.id
  historyPage.value = 1
  detailDialogVisible.value = false
  historyDialogVisible.value = true
  await loadHistory()
}

const showHistoryDialog = async () => {
  currentHistoryJobId.value = null
  historyPage.value = 1
  historyDialogVisible.value = true
  await loadHistory()
}

const loadHistory = async () => {
  historyLoading.value = true
  try {
    const params: any = {
      limit: historyPageSize.value,
      offset: (historyPage.value - 1) * historyPageSize.value,
      is_manual: true  // 只显示手动触发的执行记录
    }

    if (currentHistoryJobId.value) {
      params.job_id = currentHistoryJobId.value
    }

    const res = currentHistoryJobId.value
      ? await getSingleJobExecutions(currentHistoryJobId.value, params)
      : await getJobExecutions(params)

    // 直接使用执行记录，不需要转换格式
    const executions = Array.isArray(res.data?.items) ? res.data.items : []
    historyList.value = executions
    historyTotal.value = res.data?.total || 0
  } catch (error: any) {
    ElMessage.error(error.message || '加载执行历史失败')
    historyList.value = []
    historyTotal.value = 0
  } finally {
    historyLoading.value = false
  }
}

const handleHistoryPageChange = (page: number) => {
  historyPage.value = page
  loadHistory()
}

const handleHistoryTabChange = (tabName: string) => {
  if (tabName === 'execution') {
    executionPage.value = 1
    loadExecutions()
  } else {
    historyPage.value = 1
    loadHistory()
  }
  // 两个标签页都启动自动刷新
  startAutoRefresh()
}

// 自动刷新定时器
let autoRefreshTimer: number | null = null

const startAutoRefresh = () => {
  // 清除旧的定时器
  stopAutoRefresh()

  // 每5秒刷新一次
  autoRefreshTimer = window.setInterval(() => {
    // 根据当前标签页刷新对应的数据
    if (historyDialogVisible.value) {
      if (activeHistoryTab.value === 'execution') {
        loadExecutions()
      } else {
        loadHistory()
      }
    }
  }, 5000)
}

const stopAutoRefresh = () => {
  if (autoRefreshTimer) {
    window.clearInterval(autoRefreshTimer)
    autoRefreshTimer = null
  }
}

// 监听对话框关闭，停止自动刷新
watch(historyDialogVisible, (newVal) => {
  if (!newVal) {
    stopAutoRefresh()
  }
})

const loadExecutions = async () => {
  executionLoading.value = true
  try {
    const params: any = {
      limit: executionPageSize.value,
      offset: (executionPage.value - 1) * executionPageSize.value,
      is_manual: false  // 只显示自动触发的执行记录
    }

    if (currentHistoryJobId.value) {
      params.job_id = currentHistoryJobId.value
    }

    if (executionStatusFilter.value) {
      params.status = executionStatusFilter.value
    }

    const res = currentHistoryJobId.value
      ? await getSingleJobExecutions(currentHistoryJobId.value, params)
      : await getJobExecutions(params)

    executionList.value = Array.isArray(res.data?.items) ? res.data.items : []
    executionTotal.value = res.data?.total || 0
  } catch (error: any) {
    ElMessage.error(error.message || '加载执行历史失败')
    executionList.value = []
    executionTotal.value = 0
  } finally {
    executionLoading.value = false
  }
}

const handleExecutionPageChange = (page: number) => {
  executionPage.value = page
  loadExecutions()
}

const showExecutionDetail = (execution: JobExecution) => {
  currentExecution.value = execution
  executionDetailDialogVisible.value = true
}

const formatExecutionStatus = (status: string) => {
  const statusMap: Record<string, string> = {
    running: '执行中',
    success: '成功',
    failed: '失败',
    missed: '错过'
  }
  return statusMap[status] || status
}

const calculateRunningTime = (startTime: string) => {
  try {
    const start = new Date(startTime)
    const now = new Date()
    const seconds = Math.floor((now.getTime() - start.getTime()) / 1000)

    if (seconds < 60) {
      return `${seconds}秒`
    } else if (seconds < 3600) {
      const minutes = Math.floor(seconds / 60)
      const remainingSeconds = seconds % 60
      return `${minutes}分${remainingSeconds}秒`
    } else {
      const hours = Math.floor(seconds / 3600)
      const minutes = Math.floor((seconds % 3600) / 60)
      return `${hours}小时${minutes}分`
    }
  } catch (error) {
    return '-'
  }
}

const formatTrigger = (trigger: string) => {
  // 简化触发器显示
  if (trigger.includes('cron')) {
    return trigger.replace(/cron\[|\]/g, '')
  }
  if (trigger.includes('interval')) {
    return trigger.replace(/interval\[|\]/g, '')
  }
  return trigger
}

const formatAction = (action: string) => {
  const actionMap: Record<string, string> = {
    pause: '暂停',
    resume: '恢复',
    trigger: '手动触发',
    execute: '执行'
  }
  return actionMap[action] || action
}

const handleSearch = () => {
  // 搜索和筛选会自动通过 computed 属性生效
}

const handleReset = () => {
  searchKeyword.value = ''
  filterDataSource.value = ''
  filterStatus.value = ''
}

// 取消/终止任务执行
const handleCancelExecution = async (execution: any) => {
  try {
    await ElMessageBox.confirm(
      '确定要终止这个任务吗？任务将在下次检查时停止执行。',
      '确认终止',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await cancelExecution(execution._id)
    ElMessage.success('已设置取消标记，任务将在下次检查时停止')

    // 刷新列表
    if (activeHistoryTab.value === 'execution') {
      await loadExecutions()
    } else {
      await loadHistory()
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '终止任务失败')
    }
  }
}

// 标记执行记录为失败
const handleMarkFailed = async (execution: any) => {
  try {
    const { value: reason } = await ElMessageBox.prompt(
      '请输入失败原因（可选）',
      '标记为失败',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        inputPlaceholder: '例如：进程已手动终止',
        inputValue: '进程已手动终止'
      }
    )

    await markExecutionFailed(execution._id, reason || '用户手动标记为失败')
    ElMessage.success('已标记为失败状态')

    // 刷新列表
    if (activeHistoryTab.value === 'execution') {
      await loadExecutions()
    } else {
      await loadHistory()
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '标记失败')
    }
  }
}

// 删除执行记录
const handleDeleteExecution = async (execution: any) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除这条执行记录吗？此操作不可恢复。`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await deleteExecution(execution._id)
    ElMessage.success('执行记录已删除')

    // 刷新列表
    if (activeHistoryTab.value === 'execution') {
      await loadExecutions()
    } else {
      await loadHistory()
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '删除失败')
    }
  }
}

// 生命周期
onMounted(() => {
  loadJobs()
})
</script>

<style scoped lang="scss">
.scheduler-management {
  padding: 20px;

  .header-card {
    margin-bottom: 16px;

    .header-content {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 20px;

      .title-section {
        h2 {
          display: flex;
          align-items: center;
          gap: 8px;
          margin: 0 0 8px 0;
          font-size: 24px;
          font-weight: 600;
        }

        .subtitle {
          margin: 0;
          color: var(--el-text-color-secondary);
          font-size: 14px;
        }
      }

      .stats-section {
        display: flex;
        gap: 40px;
      }
    }

    .actions {
      display: flex;
      gap: 10px;
    }
  }

  .filter-card {
    margin-bottom: 16px;

    .filter-form {
      margin-bottom: 0;

      :deep(.el-form-item) {
        margin-bottom: 0;
      }
    }
  }

  .table-card {
    .job-name {
      display: flex;
      align-items: center;
      gap: 8px;

      .name-text {
        font-weight: 500;
      }
    }
  }

  .code-block {
    background: var(--el-fill-color-light);
    padding: 8px;
    border-radius: 4px;
    font-size: 12px;
    font-family: 'Courier New', monospace;
    overflow-x: auto;
  }

  .pagination {
    margin-top: 20px;
    display: flex;
    justify-content: center;
  }
}
</style>

