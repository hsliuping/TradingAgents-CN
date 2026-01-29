<template>
  <div class="scheduled-tasks">
    <el-card class="tasks-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <el-icon class="header-icon"><Clock /></el-icon>
          <span class="header-title">定时任务管理</span>
          <el-button 
            type="primary" 
            size="small" 
            :loading="loading"
            @click="loadTasks"
          >
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <div v-loading="loading" class="tasks-content">
        <div v-if="error" class="error-message">
          <el-alert
            :title="error"
            type="error"
            :closable="false"
            show-icon
          />
        </div>

        <div v-else-if="taskGroups.length > 0" class="task-groups">
          <!-- 历史数据同步任务 -->
          <div class="task-group">
            <h4 class="group-title">
              <el-icon class="title-icon"><DataLine /></el-icon>
              历史数据同步
            </h4>
            <div class="task-list">
              <div 
                v-for="task in getTasksByType('historical')" 
                :key="task.id"
                class="task-item"
              >
                <div class="task-header">
                  <div class="task-info">
                    <div class="task-name-row">
                      <span class="task-name">{{ task.display_name || task.name }}</span>
                      <el-tag 
                        :type="getDataSourceTagType(extractDataSource(task.id, task.name))" 
                        size="small"
                        class="source-tag"
                      >
                        {{ extractDataSource(task.id, task.name).toUpperCase() }}
                        <span class="priority-badge">优先级: {{ getDataSourcePriority(extractDataSource(task.id, task.name)) }}</span>
                      </el-tag>
                    </div>
                    <div class="task-meta">
                      <el-tag :type="!task.paused ? 'success' : 'info'" size="small">
                        {{ !task.paused ? '已启用' : '已暂停' }}
                      </el-tag>
                      <el-tag v-if="task.has_suspended_execution" type="warning" size="small" style="margin-left: 8px;">
                        ⏸️ 有挂起的任务
                      </el-tag>
                      <span v-if="formatScheduleDescription(task.trigger)" class="task-schedule">
                        <el-icon><Timer /></el-icon>
                        {{ formatScheduleDescription(task.trigger) }}
                      </span>
                      <span v-if="task.next_run_time && !task.paused" class="task-next-time">
                        下次执行: {{ formatTime(task.next_run_time) }}
                      </span>
                    </div>
                  </div>
                  <div class="task-actions">
                    <div class="action-group">
                      <div class="action-label">
                        <span v-if="task.paused" class="status-hint">任务已暂停，点击开关启用定时执行</span>
                        <span v-else class="status-hint">任务已启用，点击开关可暂停定时执行</span>
                      </div>
                      <div class="action-controls">
                        <el-switch
                          :model-value="!task.paused"
                          @change="(value: boolean) => handleToggleTask(task.id, value)"
                          :loading="taskToggling[task.id]"
                          active-text="启用"
                          inactive-text="暂停"
                        />
                        <el-dropdown
                          v-if="isHistoricalTask(task.id)"
                          trigger="click"
                          @command="(cmd: string) => handleTriggerTask(task.id, cmd === 'full')"
                        >
                          <el-button
                            size="small"
                            type="primary"
                            :loading="taskTriggering[task.id]"
                            style="margin-left: 8px"
                          >
                            立即执行
                            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
                          </el-button>
                          <template #dropdown>
                            <el-dropdown-menu>
                              <el-dropdown-item 
                                command="incremental"
                                :disabled="taskTriggering[task.id]"
                              >
                                增量同步（仅同步新数据）
                              </el-dropdown-item>
                              <el-dropdown-item 
                                command="full"
                                :disabled="taskTriggering[task.id]"
                              >
                                全量同步（同步所有历史数据）
                              </el-dropdown-item>
                            </el-dropdown-menu>
                          </template>
                        </el-dropdown>
                        <el-button
                          v-else
                          size="small"
                          type="primary"
                          :loading="taskTriggering[task.id]"
                          @click="handleTriggerTask(task.id)"
                          style="margin-left: 8px"
                        >
                          立即执行
                        </el-button>
                      </div>
                    </div>
                  </div>
                </div>
                <!-- 挂起的任务显示 -->
                <div v-if="task.has_suspended_execution && task.suspended_execution" class="suspended-execution">
                  <el-alert
                    type="warning"
                    :closable="false"
                    show-icon
                  >
                    <template #title>
                      <span>任务已挂起（服务重启导致中断）</span>
                    </template>
                    <template #default>
                      <div class="suspended-info">
                        <div>进度: {{ task.suspended_execution.progress }}%</div>
                        <div v-if="task.suspended_execution.processed_items !== undefined && task.suspended_execution.total_items !== undefined">
                          已处理: {{ task.suspended_execution.processed_items }}/{{ task.suspended_execution.total_items }}
                        </div>
                        <div v-if="task.suspended_execution.started_at">
                          开始时间: {{ formatTime(task.suspended_execution.started_at) }}
                        </div>
                        <el-button
                          size="small"
                          type="primary"
                          @click="handleResumeSuspendedTask(task.id, task.suspended_execution.execution_id)"
                          style="margin-top: 8px;"
                        >
                          继续执行
                        </el-button>
                      </div>
                    </template>
                  </el-alert>
                </div>
                <!-- 任务进度显示 -->
                <div v-if="taskProgress[task.id]" class="task-progress">
                  <el-progress
                    :percentage="taskProgress[task.id].progress || 0"
                    :status="getProgressStatus(taskProgress[task.id].status)"
                    :stroke-width="6"
                  />
                  <div class="progress-info">
                    <div class="progress-row">
                      <span v-if="taskProgress[task.id].message" class="progress-message">
                        {{ taskProgress[task.id].message }}
                      </span>
                      <span v-if="taskProgress[task.id].processed_items !== undefined && taskProgress[task.id].total_items !== undefined" class="progress-count">
                        {{ taskProgress[task.id].processed_items }}/{{ taskProgress[task.id].total_items }}
                      </span>
                    </div>
                    <div v-if="taskProgress[task.id].status === 'running'" class="progress-details">
                      <span v-if="taskProgress[task.id].started_at" class="progress-time">
                        开始时间: {{ formatTime(taskProgress[task.id].started_at) }}
                      </span>
                      <span class="progress-percentage">
                        完成度: {{ taskProgress[task.id].progress || 0 }}%
                      </span>
                      <span v-if="taskProgress[task.id].started_at" class="progress-elapsed">
                        已用时间: {{ calculateElapsedTime(taskProgress[task.id].started_at) }}
                      </span>
                      <span v-if="taskProgress[task.id].started_at && (taskProgress[task.id].progress || 0) > 0" class="progress-remaining">
                        剩余时间: {{ calculateRemainingTime(taskProgress[task.id].started_at, taskProgress[task.id].progress || 0) }}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 财务数据同步任务 -->
          <div class="task-group">
            <h4 class="group-title">
              <el-icon class="title-icon"><Money /></el-icon>
              财务数据同步
            </h4>
            <div class="task-list">
              <div 
                v-for="task in getTasksByType('financial')" 
                :key="task.id"
                class="task-item"
              >
                <div class="task-header">
                  <div class="task-info">
                    <div class="task-name-row">
                      <span class="task-name">{{ task.display_name || task.name }}</span>
                      <el-tag 
                        :type="getDataSourceTagType(extractDataSource(task.id, task.name))" 
                        size="small"
                        class="source-tag"
                      >
                        {{ extractDataSource(task.id, task.name).toUpperCase() }}
                        <span class="priority-badge">优先级: {{ getDataSourcePriority(extractDataSource(task.id, task.name)) }}</span>
                      </el-tag>
                    </div>
                    <div class="task-meta">
                      <el-tag :type="!task.paused ? 'success' : 'info'" size="small">
                        {{ !task.paused ? '已启用' : '已暂停' }}
                      </el-tag>
                      <el-tag v-if="task.has_suspended_execution" type="warning" size="small" style="margin-left: 8px;">
                        ⏸️ 有挂起的任务
                      </el-tag>
                      <span v-if="formatScheduleDescription(task.trigger)" class="task-schedule">
                        <el-icon><Timer /></el-icon>
                        {{ formatScheduleDescription(task.trigger) }}
                      </span>
                      <span v-if="task.next_run_time && !task.paused" class="task-next-time">
                        下次执行: {{ formatTime(task.next_run_time) }}
                      </span>
                    </div>
                  </div>
                  <div class="task-actions">
                    <div class="action-group">
                      <div class="action-label">
                        <span v-if="task.paused" class="status-hint">任务已暂停，点击开关启用定时执行</span>
                        <span v-else class="status-hint">任务已启用，点击开关可暂停定时执行</span>
                      </div>
                      <div class="action-controls">
                        <el-switch
                          :model-value="!task.paused"
                          @change="(value: boolean) => handleToggleTask(task.id, value)"
                          :loading="taskToggling[task.id]"
                          active-text="启用"
                          inactive-text="暂停"
                        />
                        <el-dropdown
                          v-if="isHistoricalTask(task.id)"
                          trigger="click"
                          @command="(cmd: string) => handleTriggerTask(task.id, cmd === 'full')"
                        >
                          <el-button
                            size="small"
                            type="primary"
                            :loading="taskTriggering[task.id]"
                            style="margin-left: 8px"
                          >
                            立即执行
                            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
                          </el-button>
                          <template #dropdown>
                            <el-dropdown-menu>
                              <el-dropdown-item 
                                command="incremental"
                                :disabled="taskTriggering[task.id]"
                              >
                                增量同步（仅同步新数据）
                              </el-dropdown-item>
                              <el-dropdown-item 
                                command="full"
                                :disabled="taskTriggering[task.id]"
                              >
                                全量同步（同步所有历史数据）
                              </el-dropdown-item>
                            </el-dropdown-menu>
                          </template>
                        </el-dropdown>
                        <el-button
                          v-else
                          size="small"
                          type="primary"
                          :loading="taskTriggering[task.id]"
                          @click="handleTriggerTask(task.id)"
                          style="margin-left: 8px"
                        >
                          立即执行
                        </el-button>
                      </div>
                    </div>
                  </div>
                </div>
                <!-- 挂起的任务显示 -->
                <div v-if="task.has_suspended_execution && task.suspended_execution" class="suspended-execution">
                  <el-alert
                    type="warning"
                    :closable="false"
                    show-icon
                  >
                    <template #title>
                      <span>任务已挂起（服务重启导致中断）</span>
                    </template>
                    <template #default>
                      <div class="suspended-info">
                        <div>进度: {{ task.suspended_execution.progress }}%</div>
                        <div v-if="task.suspended_execution.processed_items !== undefined && task.suspended_execution.total_items !== undefined">
                          已处理: {{ task.suspended_execution.processed_items }}/{{ task.suspended_execution.total_items }}
                        </div>
                        <div v-if="task.suspended_execution.started_at">
                          开始时间: {{ formatTime(task.suspended_execution.started_at) }}
                        </div>
                        <el-button
                          size="small"
                          type="primary"
                          @click="handleResumeSuspendedTask(task.id, task.suspended_execution.execution_id)"
                          style="margin-top: 8px;"
                        >
                          继续执行
                        </el-button>
                      </div>
                    </template>
                  </el-alert>
                </div>
                <!-- 任务进度显示 -->
                <div v-if="taskProgress[task.id]" class="task-progress">
                  <el-progress
                    :percentage="taskProgress[task.id].progress || 0"
                    :status="getProgressStatus(taskProgress[task.id].status)"
                    :stroke-width="6"
                  />
                  <div class="progress-info">
                    <div class="progress-row">
                      <span v-if="taskProgress[task.id].message" class="progress-message">
                        {{ taskProgress[task.id].message }}
                      </span>
                      <span v-if="taskProgress[task.id].processed_items !== undefined && taskProgress[task.id].total_items !== undefined" class="progress-count">
                        {{ taskProgress[task.id].processed_items }}/{{ taskProgress[task.id].total_items }}
                      </span>
                    </div>
                    <div v-if="taskProgress[task.id].status === 'running'" class="progress-details">
                      <span v-if="taskProgress[task.id].started_at" class="progress-time">
                        开始时间: {{ formatTime(taskProgress[task.id].started_at) }}
                      </span>
                      <span class="progress-percentage">
                        完成度: {{ taskProgress[task.id].progress || 0 }}%
                      </span>
                      <span v-if="taskProgress[task.id].started_at" class="progress-elapsed">
                        已用时间: {{ calculateElapsedTime(taskProgress[task.id].started_at) }}
                      </span>
                      <span v-if="taskProgress[task.id].started_at && (taskProgress[task.id].progress || 0) > 0" class="progress-remaining">
                        剩余时间: {{ calculateRemainingTime(taskProgress[task.id].started_at, taskProgress[task.id].progress || 0) }}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 新闻数据同步任务 -->
          <div class="task-group">
            <h4 class="group-title">
              <el-icon class="title-icon"><Document /></el-icon>
              新闻数据同步
            </h4>
            <div class="task-list">
              <div 
                v-for="task in getTasksByType('news')" 
                :key="task.id"
                class="task-item"
              >
                <div class="task-header">
                  <div class="task-info">
                    <div class="task-name-row">
                      <span class="task-name">{{ task.display_name || task.name }}</span>
                      <el-tag 
                        :type="getDataSourceTagType(extractDataSource(task.id, task.name))" 
                        size="small"
                        class="source-tag"
                      >
                        {{ extractDataSource(task.id, task.name).toUpperCase() }}
                        <span class="priority-badge">优先级: {{ getDataSourcePriority(extractDataSource(task.id, task.name)) }}</span>
                      </el-tag>
                    </div>
                    <div class="task-meta">
                      <el-tag :type="!task.paused ? 'success' : 'info'" size="small">
                        {{ !task.paused ? '已启用' : '已暂停' }}
                      </el-tag>
                      <el-tag v-if="task.has_suspended_execution" type="warning" size="small" style="margin-left: 8px;">
                        ⏸️ 有挂起的任务
                      </el-tag>
                      <span v-if="formatScheduleDescription(task.trigger)" class="task-schedule">
                        <el-icon><Timer /></el-icon>
                        {{ formatScheduleDescription(task.trigger) }}
                      </span>
                      <span v-if="task.next_run_time && !task.paused" class="task-next-time">
                        下次执行: {{ formatTime(task.next_run_time) }}
                      </span>
                    </div>
                  </div>
                  <div class="task-actions">
                    <div class="action-group">
                      <div class="action-label">
                        <span v-if="task.paused" class="status-hint">任务已暂停，点击开关启用定时执行</span>
                        <span v-else class="status-hint">任务已启用，点击开关可暂停定时执行</span>
                      </div>
                      <div class="action-controls">
                        <el-switch
                          :model-value="!task.paused"
                          @change="(value: boolean) => handleToggleTask(task.id, value)"
                          :loading="taskToggling[task.id]"
                          active-text="启用"
                          inactive-text="暂停"
                        />
                        <el-dropdown
                          v-if="isHistoricalTask(task.id)"
                          trigger="click"
                          @command="(cmd: string) => handleTriggerTask(task.id, cmd === 'full')"
                        >
                          <el-button
                            size="small"
                            type="primary"
                            :loading="taskTriggering[task.id]"
                            style="margin-left: 8px"
                          >
                            立即执行
                            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
                          </el-button>
                          <template #dropdown>
                            <el-dropdown-menu>
                              <el-dropdown-item 
                                command="incremental"
                                :disabled="taskTriggering[task.id]"
                              >
                                增量同步（仅同步新数据）
                              </el-dropdown-item>
                              <el-dropdown-item 
                                command="full"
                                :disabled="taskTriggering[task.id]"
                              >
                                全量同步（同步所有历史数据）
                              </el-dropdown-item>
                            </el-dropdown-menu>
                          </template>
                        </el-dropdown>
                        <el-button
                          v-else
                          size="small"
                          type="primary"
                          :loading="taskTriggering[task.id]"
                          @click="handleTriggerTask(task.id)"
                          style="margin-left: 8px"
                        >
                          立即执行
                        </el-button>
                      </div>
                    </div>
                  </div>
                </div>
                <!-- 挂起的任务显示 -->
                <div v-if="task.has_suspended_execution && task.suspended_execution" class="suspended-execution">
                  <el-alert
                    type="warning"
                    :closable="false"
                    show-icon
                  >
                    <template #title>
                      <span>任务已挂起（服务重启导致中断）</span>
                    </template>
                    <template #default>
                      <div class="suspended-info">
                        <div>进度: {{ task.suspended_execution.progress }}%</div>
                        <div v-if="task.suspended_execution.processed_items !== undefined && task.suspended_execution.total_items !== undefined">
                          已处理: {{ task.suspended_execution.processed_items }}/{{ task.suspended_execution.total_items }}
                        </div>
                        <div v-if="task.suspended_execution.started_at">
                          开始时间: {{ formatTime(task.suspended_execution.started_at) }}
                        </div>
                        <el-button
                          size="small"
                          type="primary"
                          @click="handleResumeSuspendedTask(task.id, task.suspended_execution.execution_id)"
                          style="margin-top: 8px;"
                        >
                          继续执行
                        </el-button>
                      </div>
                    </template>
                  </el-alert>
                </div>
                <!-- 任务进度显示 -->
                <div v-if="taskProgress[task.id]" class="task-progress">
                  <el-progress
                    :percentage="taskProgress[task.id].progress || 0"
                    :status="getProgressStatus(taskProgress[task.id].status)"
                    :stroke-width="6"
                  />
                  <div class="progress-info">
                    <div class="progress-row">
                      <span v-if="taskProgress[task.id].message" class="progress-message">
                        {{ taskProgress[task.id].message }}
                      </span>
                      <span v-if="taskProgress[task.id].processed_items !== undefined && taskProgress[task.id].total_items !== undefined" class="progress-count">
                        {{ taskProgress[task.id].processed_items }}/{{ taskProgress[task.id].total_items }}
                      </span>
                    </div>
                    <div v-if="taskProgress[task.id].status === 'running'" class="progress-details">
                      <span v-if="taskProgress[task.id].started_at" class="progress-time">
                        开始时间: {{ formatTime(taskProgress[task.id].started_at) }}
                      </span>
                      <span class="progress-percentage">
                        完成度: {{ taskProgress[task.id].progress || 0 }}%
                      </span>
                      <span v-if="taskProgress[task.id].started_at" class="progress-elapsed">
                        已用时间: {{ calculateElapsedTime(taskProgress[task.id].started_at) }}
                      </span>
                      <span v-if="taskProgress[task.id].started_at && (taskProgress[task.id].progress || 0) > 0" class="progress-remaining">
                        剩余时间: {{ calculateRemainingTime(taskProgress[task.id].started_at, taskProgress[task.id].progress || 0) }}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="empty-state">
          <el-empty description="暂无定时任务" />
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Clock,
  Refresh,
  DataLine,
  Money,
  Document,
  Timer,
  ArrowDown
} from '@element-plus/icons-vue'
import {
  getJobs,
  getJobProgress,
  triggerJob,
  pauseJob,
  resumeJob,
  type JobStatus,
  type JobProgress
} from '@/api/scheduler'
import {
  getDataSourcesStatus,
  type DataSourceStatus
} from '@/api/sync'

// 响应式数据
const loading = ref(false)
const error = ref('')
const allTasks = ref<JobStatus[]>([])
const dataSources = ref<DataSourceStatus[]>([])
const taskProgress = ref<Record<string, JobProgress>>({})
const taskToggling = ref<Record<string, boolean>>({})
const taskTriggering = ref<Record<string, boolean>>({})
const progressPollingTimer = ref<NodeJS.Timeout | null>(null)

// 任务类型关键词映射
const taskTypeKeywords: Record<string, string[]> = {
  historical: ['历史数据', 'historical'],
  financial: ['财务数据', 'financial'],
  news: ['新闻数据', 'news']
}

// 从任务ID或名称中提取数据源名称
const extractDataSource = (jobId: string | undefined, jobName: string | undefined): string => {
  const id = (jobId || '').toLowerCase()
  const name = (jobName || '').toLowerCase()
  
  if (id.includes('akshare') || name.includes('akshare')) return 'akshare'
  if (id.includes('tushare') || name.includes('tushare')) return 'tushare'
  if (id.includes('baostock') || name.includes('baostock')) return 'baostock'
  
  return 'unknown'
}

// 从任务ID或名称中提取任务类型
const extractTaskType = (jobId: string | undefined, jobName: string | undefined): string | null => {
  const id = (jobId || '').toLowerCase()
  const name = (jobName || '').toLowerCase()
  
  for (const [type, keywords] of Object.entries(taskTypeKeywords)) {
    if (keywords.some(keyword => id.includes(keyword.toLowerCase()) || name.includes(keyword.toLowerCase()))) {
      return type
    }
  }
  
  return null
}

// 判断任务是否是我们关心的类型
const isRelevantTask = (task: JobStatus): boolean => {
  if (!task || !task.id) return false
  const taskType = extractTaskType(task.id, task.name)
  return taskType !== null && ['historical', 'financial', 'news'].includes(taskType)
}

// 获取数据源优先级
const getDataSourcePriority = (sourceName: string): number => {
  const source = dataSources.value.find(s => s.name.toLowerCase() === sourceName.toLowerCase())
  return source?.priority || 999 // 未找到的优先级最低
}

// 按数据源优先级和任务类型分组任务
const groupedTasks = computed(() => {
  const groups: Record<string, Record<string, JobStatus[]>> = {
    historical: {},
    financial: {},
    news: {}
  }
  
  // 过滤相关任务
  const relevantTasks = allTasks.value.filter(isRelevantTask)
  
  // 按类型和数据源分组
  relevantTasks.forEach(task => {
    const taskType = extractTaskType(task.id, task.name)
    const dataSource = extractDataSource(task.id, task.name)
    
    if (taskType && ['historical', 'financial', 'news'].includes(taskType)) {
      if (!groups[taskType][dataSource]) {
        groups[taskType][dataSource] = []
      }
      groups[taskType][dataSource].push(task)
    }
  })
  
  // 按数据源优先级排序
  Object.keys(groups).forEach(type => {
    const sortedSources = Object.keys(groups[type]).sort((a, b) => {
      return getDataSourcePriority(b) - getDataSourcePriority(a) // 优先级高的在前
    })
    
        const sortedGroup: Record<string, JobStatus[]> = {}
    sortedSources.forEach(source => {
      sortedGroup[source] = groups[type][source]
    })
    groups[type] = sortedGroup
  })
  
  return groups
})

// 计算属性：任务分组
const taskGroups = computed(() => {
  const groups = []
  if (Object.keys(groupedTasks.value.historical).length > 0) groups.push('historical')
  if (Object.keys(groupedTasks.value.financial).length > 0) groups.push('financial')
  if (Object.keys(groupedTasks.value.news).length > 0) groups.push('news')
  return groups
})

// 根据类型获取任务（按数据源优先级排序）
const getTasksByType = (type: string): JobStatus[] => {
  const tasks: JobStatus[] = []
  const group = groupedTasks.value[type] || {}
  
  // 按数据源优先级顺序添加任务
  Object.keys(group).sort((a, b) => {
    return getDataSourcePriority(b) - getDataSourcePriority(a)
  }).forEach(source => {
    tasks.push(...group[source])
  })
  
  return tasks
}

// 加载数据源状态
const loadDataSources = async () => {
  try {
    const response = await getDataSourcesStatus()
    if (response.success) {
      dataSources.value = response.data
    }
  } catch (err: any) {
    console.error('加载数据源状态失败:', err)
  }
}

// 加载任务列表
const loadTasks = async () => {
  try {
    loading.value = true
    error.value = ''
    
    // 先加载数据源信息
    await loadDataSources()
    
    // 加载所有任务
    const response = await getJobs()
    if (response.success) {
      // 保存所有任务
      allTasks.value = response.data
      
      // 🔍 调试：打印所有任务信息
      console.log('📋 获取到的所有任务:', allTasks.value.length, '个')
      allTasks.value.forEach((task, index) => {
        console.log(`任务 ${index + 1}:`, {
          id: task.id,
          name: task.name,
          paused: task.paused,
          extractedType: extractTaskType(task.id, task.name),
          extractedSource: extractDataSource(task.id, task.name),
          isRelevant: isRelevantTask(task)
        })
      })
      
      // 只加载已启用任务的进度（未启用的任务不需要进度）
      const relevantTasks = allTasks.value.filter(isRelevantTask)
      console.log('✅ 过滤后的相关任务:', relevantTasks.length, '个')
      
      for (const task of relevantTasks) {
        if (!task.paused) {  // paused=false 表示已启用
          await loadTaskProgress(task.id)
        }
      }
      
      // 开始轮询进度（只轮询已启用的任务）
      startProgressPolling()
    } else {
      error.value = response.message || '获取任务列表失败'
    }
  } catch (err: any) {
    console.error('加载定时任务失败:', err)
    error.value = err.message || '网络请求失败'
  } finally {
    loading.value = false
  }
}

// 加载任务进度
const loadTaskProgress = async (jobId: string) => {
  try {
    const response = await getJobProgress(jobId)
    if (response.success && response.data) {
      taskProgress.value[jobId] = response.data
    }
  } catch (err: any) {
    console.error(`加载任务 ${jobId} 进度失败:`, err)
  }
}

// 切换任务启用状态
const handleToggleTask = async (jobId: string, enabled: boolean) => {
  try {
    taskToggling.value[jobId] = true
    
    if (enabled) {
      await resumeJob(jobId)
      ElMessage.success('任务已启用')
      // 启用后加载进度
      await loadTaskProgress(jobId)
      startProgressPolling()
    } else {
      await pauseJob(jobId)
      ElMessage.success('任务已暂停')
      // 暂停后清除进度
      delete taskProgress.value[jobId]
    }
    
    // 更新任务状态
    const task = allTasks.value.find(t => t.id === jobId)
    if (task) {
      task.paused = !enabled  // paused=false 表示已启用
    }
    
    // 重新加载任务列表以获取最新状态
    await loadTasks()
  } catch (err: any) {
    ElMessage.error(`操作失败: ${err.message}`)
    // 恢复状态
    const task = allTasks.value.find(t => t.id === jobId)
    if (task) {
      task.paused = enabled  // 恢复原状态
    }
  } finally {
    taskToggling.value[jobId] = false
  }
}

// 判断是否是历史数据同步任务
const isHistoricalTask = (jobId: string): boolean => {
  return jobId.includes('historical_sync')
}

// 计算已用时间
const calculateElapsedTime = (startedAt: string): string => {
  if (!startedAt) return '--'
  
  try {
    const start = new Date(startedAt)
    const now = new Date()
    const diffMs = now.getTime() - start.getTime()
    
    if (diffMs < 0) return '--'
    
    const seconds = Math.floor(diffMs / 1000)
    const minutes = Math.floor(seconds / 60)
    const hours = Math.floor(minutes / 60)
    
    if (hours > 0) {
      return `${hours}小时${minutes % 60}分钟`
    } else if (minutes > 0) {
      return `${minutes}分钟${seconds % 60}秒`
    } else {
      return `${seconds}秒`
    }
  } catch (e) {
    return '--'
  }
}

// 计算剩余时间
const calculateRemainingTime = (startedAt: string, progress: number): string => {
  if (!startedAt || progress <= 0) return '--'
  
  try {
    const start = new Date(startedAt)
    const now = new Date()
    const elapsedMs = now.getTime() - start.getTime()
    
    if (elapsedMs < 0 || progress >= 100) return '--'
    
    // 已花时间 / 进度百分比 = 预计总时间
    const totalMs = elapsedMs / (progress / 100)
    const remainingMs = totalMs - elapsedMs
    
    if (remainingMs < 0) return '--'
    
    const seconds = Math.floor(remainingMs / 1000)
    const minutes = Math.floor(seconds / 60)
    const hours = Math.floor(minutes / 60)
    
    if (hours > 0) {
      return `${hours}小时${minutes % 60}分钟`
    } else if (minutes > 0) {
      return `${minutes}分钟${seconds % 60}秒`
    } else {
      return `${seconds}秒`
    }
  } catch (e) {
    return '--'
  }
}

// 恢复挂起的任务
const handleResumeSuspendedTask = async (jobId: string, executionId: string) => {
  try {
    const { resumeSuspendedExecution } = await import('@/api/scheduler')
    const response = await resumeSuspendedExecution(executionId)
    
    if (response.success) {
      ElMessage.success('任务已恢复执行，将从上次进度位置继续')
      
      // 🔥 立即清除挂起任务显示（不需要等待后端查询）
      // 找到对应的任务并清除挂起状态
      const taskIndex = allTasks.value.findIndex(t => t.id === jobId)
      if (taskIndex !== -1) {
        allTasks.value[taskIndex].has_suspended_execution = false
        allTasks.value[taskIndex].suspended_execution = undefined
      }
      
      // 重新加载任务列表（确保数据同步）
      await loadTasks()
      
      // 加载进度并开始轮询
      await loadTaskProgress(jobId)
      startProgressPolling()
    } else {
      ElMessage.error(`恢复任务失败: ${response.message || '未知错误'}`)
    }
  } catch (err: any) {
    ElMessage.error(`恢复任务失败: ${err.message}`)
    console.error('恢复挂起任务失败:', err)
  }
}

// 触发任务执行
const handleTriggerTask = async (jobId: string, fullSync: boolean = false) => {
  try {
    // 🔥 检查是否有挂起任务
    const task = allTasks.value.find(t => t.id === jobId)
    if (task?.has_suspended_execution && task.suspended_execution) {
      // 有挂起任务，提示用户选择
      const suspendedExec = task.suspended_execution
      const progress = suspendedExec.progress || 0
      const processed = suspendedExec.processed_items || 0
      const total = suspendedExec.total_items || 0
      
      try {
        await ElMessageBox.confirm(
          `检测到有挂起任务（进度: ${progress}%，已处理: ${processed}/${total}）\n\n请选择：`,
          '检测到挂起任务',
          {
            confirmButtonText: '从挂起任务继续执行',
            cancelButtonText: '重新开始',
            distinguishCancelAndClose: true,
            type: 'warning',
            center: true
          }
        )
        
        // 用户选择"从挂起任务继续执行"
        if (suspendedExec.execution_id) {
          await handleResumeSuspendedTask(jobId, suspendedExec.execution_id)
          return
        }
      } catch (action: any) {
        // 用户选择"重新开始"或取消
        if (action === 'cancel') {
          // 用户选择重新开始，先清除挂起任务
          if (suspendedExec.execution_id) {
            try {
              const { cancelSuspendedExecution } = await import('@/api/scheduler')
              await cancelSuspendedExecution(suspendedExec.execution_id)
              ElMessage.success('已清除挂起任务，将重新开始执行')
              
              // 🔥 立即清除挂起任务显示（不需要等待重新加载）
              const taskIndex = allTasks.value.findIndex(t => t.id === jobId)
              if (taskIndex !== -1) {
                allTasks.value[taskIndex].has_suspended_execution = false
                allTasks.value[taskIndex].suspended_execution = undefined
              }
              
              // 重新加载任务列表，确保数据同步
              await loadTasks()
            } catch (err: any) {
              console.warn(`清除挂起任务失败: ${err.message}`)
              // 即使清除失败，也继续执行新任务
            }
          }
          // 继续执行下面的代码（重新开始）
        } else {
          // 用户关闭对话框，不执行任何操作
          return
        }
      }
    }
    
    // 执行新任务（重新开始）
    taskTriggering.value[jobId] = true
    
    const options: { incremental?: boolean } = {}
    if (isHistoricalTask(jobId)) {
      options.incremental = !fullSync  // fullSync=true 时，incremental=false（全量同步）
    }
    
    await triggerJob(jobId, options)
    const syncMode = isHistoricalTask(jobId) ? (fullSync ? '全量同步' : '增量同步') : ''
    ElMessage.success(`任务已触发执行${syncMode ? `（${syncMode}）` : ''}`)
    
    // 开始轮询进度
    await loadTaskProgress(jobId)
    startProgressPolling()
  } catch (err: any) {
    // 忽略用户取消对话框的错误
    if (err !== 'cancel' && err !== 'close') {
      ElMessage.error(`触发任务失败: ${err.message}`)
    }
  } finally {
    taskTriggering.value[jobId] = false
  }
}

// 开始进度轮询
const startProgressPolling = () => {
  if (progressPollingTimer.value) {
    clearInterval(progressPollingTimer.value)
  }
  
  progressPollingTimer.value = setInterval(async () => {
    let hasRunningTask = false
    
    // 只轮询已启用的相关任务
    const relevantTasks = allTasks.value.filter(isRelevantTask).filter(t => !t.paused)
    
    for (const task of relevantTasks) {
      await loadTaskProgress(task.id)
      
      // 检查是否有运行中的任务
      const progress = taskProgress.value[task.id]
      if (progress && progress.status === 'running') {
        hasRunningTask = true
      }
    }
    
    // 如果没有运行中的任务，停止轮询
    if (!hasRunningTask) {
      stopProgressPolling()
    }
  }, 3000) // 每3秒轮询一次
}

// 停止进度轮询
const stopProgressPolling = () => {
  if (progressPollingTimer.value) {
    clearInterval(progressPollingTimer.value)
    progressPollingTimer.value = null
  }
}

// 获取进度状态
const getProgressStatus = (status?: string): 'success' | 'exception' | 'warning' => {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'exception'
  return 'warning'
}

// 获取数据源标签类型
const getDataSourceTagType = (sourceName: string): 'success' | 'warning' | 'info' | 'danger' => {
  const priority = getDataSourcePriority(sourceName)
  if (priority >= 3) return 'success'
  if (priority >= 2) return 'warning'
  if (priority >= 1) return 'info'
  return 'danger'
}

// 格式化时间
const formatTime = (isoString?: string) => {
  if (!isoString) return '-'
  try {
    const date = new Date(isoString)
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  } catch {
    return isoString
  }
}

// 从trigger字符串中提取CRON表达式
const extractCronFromTrigger = (trigger?: string): string => {
  if (!trigger) return ''
  
  // 尝试匹配 cron[minute='X', hour='Y', ...] 格式
  const cronMatch = trigger.match(/cron\[(.*?)\]/)
  if (cronMatch) {
    const params = cronMatch[1]
    const minuteMatch = params.match(/minute='([^']*)'/)
    const hourMatch = params.match(/hour='([^']*)'/)
    const dayMatch = params.match(/day='([^']*)'/)
    const monthMatch = params.match(/month='([^']*)'/)
    const dayOfWeekMatch = params.match(/day_of_week='([^']*)'/)
    
    const minute = minuteMatch ? minuteMatch[1] : '*'
    const hour = hourMatch ? hourMatch[1] : '*'
    const day = dayMatch ? dayMatch[1] : '*'
    const month = monthMatch ? monthMatch[1] : '*'
    const dayOfWeek = dayOfWeekMatch ? dayOfWeekMatch[1] : '*'
    
    return `${minute} ${hour} ${day} ${month} ${dayOfWeek}`
  }
  
  // 如果已经是CRON格式（5个空格分隔的数字/符号）
  const parts = trigger.trim().split(/\s+/)
  if (parts.length === 5) {
    return trigger.trim()
  }
  
  return ''
}

// 格式化调度描述（将CRON表达式转换为人类可读的描述）
const formatScheduleDescription = (trigger?: string): string => {
  if (!trigger) return ''
  
  const cron = extractCronFromTrigger(trigger)
  if (!cron) {
    // 如果不是CRON格式，尝试显示原始trigger
    if (trigger.includes('interval')) {
      const intervalMatch = trigger.match(/interval\[seconds=(\d+)\]/)
      if (intervalMatch) {
        const seconds = parseInt(intervalMatch[1])
        if (seconds < 60) {
          return `每${seconds}秒执行一次`
        } else if (seconds < 3600) {
          return `每${Math.floor(seconds / 60)}分钟执行一次`
        } else {
          return `每${Math.floor(seconds / 3600)}小时执行一次`
        }
      }
    }
    return trigger
  }
  
  const parts = cron.split(' ')
  if (parts.length !== 5) return cron
  
  const [minute, hour, day, month, dayOfWeek] = parts
  
  // 解析时间
  const hourNum = parseInt(hour)
  const minuteNum = parseInt(minute)
  const timeStr = hourNum >= 0 && hourNum < 24 && minuteNum >= 0 && minuteNum < 60
    ? `${hourNum.toString().padStart(2, '0')}:${minuteNum.toString().padStart(2, '0')}`
    : ''
  
  // 解析频率
  let freqDesc = ''
  if (dayOfWeek === '*') {
    freqDesc = '每天'
  } else if (dayOfWeek === '1-5') {
    freqDesc = '工作日（周一至周五）'
  } else if (dayOfWeek === '0,6' || dayOfWeek === '6,0') {
    freqDesc = '周末（周六、周日）'
  } else if (dayOfWeek === '1') {
    freqDesc = '每周一'
  } else if (dayOfWeek === '2') {
    freqDesc = '每周二'
  } else if (dayOfWeek === '3') {
    freqDesc = '每周三'
  } else if (dayOfWeek === '4') {
    freqDesc = '每周四'
  } else if (dayOfWeek === '5') {
    freqDesc = '每周五'
  } else if (dayOfWeek === '6') {
    freqDesc = '每周六'
  } else if (dayOfWeek === '0') {
    freqDesc = '每周日'
  } else if (dayOfWeek.includes(',')) {
    freqDesc = `每周${dayOfWeek.split(',').map(d => {
      const dayNames = ['日', '一', '二', '三', '四', '五', '六']
      return dayNames[parseInt(d)] || d
    }).join('、')}`
  } else {
    freqDesc = `CRON: ${cron}`
  }
  
  return timeStr ? `${freqDesc} ${timeStr} 执行` : freqDesc
}

// 组件挂载时加载数据
onMounted(() => {
  loadTasks()
})

// 组件卸载时停止轮询
onUnmounted(() => {
  stopProgressPolling()
})
</script>

<style scoped lang="scss">
.scheduled-tasks {
  .tasks-card {
    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      
      .header-icon {
        margin-right: 8px;
        color: var(--el-color-primary);
      }
      
      .header-title {
        font-weight: 600;
        flex: 1;
      }
    }
  }

  .tasks-content {
    min-height: 200px;
  }

  .task-groups {
    .task-group {
      margin-bottom: 32px;
      
      &:last-child {
        margin-bottom: 0;
      }
      
      .group-title {
        display: flex;
        align-items: center;
        margin: 0 0 16px 0;
        font-size: 16px;
        font-weight: 600;
        color: var(--el-text-color-primary);
        
        .title-icon {
          margin-right: 8px;
          color: var(--el-color-primary);
        }
      }
      
      .task-list {
        .task-item {
          padding: 16px;
          margin-bottom: 12px;
          border: 1px solid var(--el-border-color-light);
          border-radius: 8px;
          background: var(--el-bg-color-page);
          
          &:last-child {
            margin-bottom: 0;
          }
          
          .task-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            
            .task-info {
              flex: 1;
              
              .task-name-row {
                display: flex;
                align-items: center;
                gap: 8px;
                margin-bottom: 8px;
                flex-wrap: wrap;
                
                .task-name {
                  font-weight: 600;
                  font-size: 14px;
                  color: var(--el-text-color-primary);
                }
                
                .source-tag {
                  .priority-badge {
                    margin-left: 4px;
                    font-size: 11px;
                    opacity: 0.8;
                  }
                }
              }
              
              .task-meta {
                display: flex;
                align-items: center;
                gap: 12px;
                flex-wrap: wrap;
                
                .task-schedule {
                  display: flex;
                  align-items: center;
                  gap: 4px;
                  font-size: 12px;
                  color: var(--el-color-primary);
                  font-weight: 500;
                }
                
                .task-next-time {
                  font-size: 12px;
                  color: var(--el-text-color-secondary);
                }
              }
            }
            
            .task-actions {
              display: flex;
              align-items: center;
              
              .action-group {
                display: flex;
                flex-direction: column;
                gap: 8px;
                width: 100%;
                
                .action-label {
                  .status-hint {
                    font-size: 12px;
                    color: var(--el-text-color-secondary);
                    display: block;
                  }
                }
                
                .action-controls {
                  display: flex;
                  align-items: center;
                  justify-content: flex-end;
                }
              }
            }
          }
          
          .task-progress {
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid var(--el-border-color-lighter);
            
            .progress-info {
              margin-top: 8px;
              font-size: 12px;
              color: var(--el-text-color-secondary);
              
              .progress-row {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 6px;
                
                .progress-message {
                  flex: 1;
                  margin-right: 12px;
                }
                
                .progress-count {
                  font-weight: 500;
                  color: var(--el-color-primary);
                }
              }
              
              .progress-details {
                display: flex;
                flex-wrap: wrap;
                gap: 16px;
                margin-top: 8px;
                padding-top: 8px;
                border-top: 1px solid var(--el-border-color-lighter);
                
                .progress-time,
                .progress-percentage,
                .progress-elapsed,
                .progress-remaining {
                  font-size: 11px;
                  color: var(--el-text-color-regular);
                  
                  &:before {
                    content: '';
                    display: inline-block;
                    width: 4px;
                    height: 4px;
                    border-radius: 50%;
                    background-color: var(--el-color-primary);
                    margin-right: 6px;
                    vertical-align: middle;
                  }
                }
                
                .progress-percentage {
                  color: var(--el-color-primary);
                  font-weight: 500;
                }
                
                .progress-elapsed {
                  color: var(--el-color-warning);
                }
                
                .progress-remaining {
                  color: var(--el-color-info);
                }
              }
            }
          }
        }
      }
    }
  }

  .error-message {
    margin-bottom: 16px;
  }

  .empty-state {
    text-align: center;
    padding: 40px 0;
  }
}

@media (max-width: 768px) {
  .scheduled-tasks {
    .task-groups {
      .task-group {
        .task-list {
          .task-item {
            .task-header {
              flex-direction: column;
              align-items: flex-start;
              gap: 12px;
              
              .task-actions {
                width: 100%;
                justify-content: space-between;
              }
            }
          }
        }
      }
    }
  }
}
</style>
