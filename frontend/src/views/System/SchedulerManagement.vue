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
              <div class="job-name-main">
                <el-tag :type="row.paused ? 'warning' : 'success'" size="small">
                  {{ row.paused ? '已暂停' : '运行中' }}
                </el-tag>
                <el-tag v-if="isJobRunning(row)" type="danger" size="small">
                  执行中
                </el-tag>
                <span class="name-text">{{ row.name }}</span>
              </div>
              <div v-if="isJobRunning(row)" class="job-running-summary">
                <span v-if="getJobRunningProgress(row) !== null">进度 {{ getJobRunningProgress(row) }}%</span>
                <span v-if="getJobRunningStartedAt(row)">开始于 {{ formatDateTime(getJobRunningStartedAt(row)!) }}</span>
              </div>
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
                :disabled="isJobRunning(row)"
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
        <el-form-item label="执行时间" v-if="editForm.supports_cron">
          <div class="schedule-picker">
            <div class="schedule-row">
              <el-select v-model="editForm.frequency" placeholder="选择频率" style="width: 140px;" @change="updateCronFromUI">
                <el-option label="每天" value="daily" />
                <el-option label="工作日" value="weekdays" />
                <el-option label="周末" value="weekend" />
                <el-option label="每周一" value="monday" />
                <el-option label="每周五" value="friday" />
              </el-select>
              <span class="schedule-sep">的</span>
              <el-time-select
                v-model="editForm.time"
                :start="'05:00'"
                :step="'00:30'"
                :end="'23:30'"
                placeholder="选择时间"
                style="width: 120px;"
                @change="updateCronFromUI"
              />
              <span class="schedule-sep">执行</span>
            </div>
            <div class="schedule-preview">
              <el-tag type="info" size="small">
                <el-icon><Timer /></el-icon>
                {{ formatScheduleDescription(editForm.frequency, editForm.time) }}
              </el-tag>
            </div>
            <div class="schedule-advanced">
              <el-link type="info" :underline="false" @click="editForm.showAdvanced = !editForm.showAdvanced">
                {{ editForm.showAdvanced ? '收起高级选项' : '高级选项（CRON表达式）' }}
                <el-icon><ArrowDown v-if="!editForm.showAdvanced" /><ArrowUp v-else /></el-icon>
              </el-link>
            </div>
            <div v-if="editForm.showAdvanced" class="schedule-cron">
              <el-input
                v-model="editForm.cron_expression"
                placeholder="CRON表达式，如: 0 8 * * 1-5"
                @change="updateUIFromCron"
              >
                <template #prepend>CRON</template>
              </el-input>
              <div class="cron-help">
                格式：分 时 日 月 周 | 例：<code>0 8 * * 1-5</code> = 工作日8:00
              </div>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="执行时间" v-if="!editForm.supports_cron">
          <el-text type="warning">此任务使用间隔触发器，不支持修改执行时间</el-text>
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
                  :type="row.status === 'success' ? 'success' : row.status === 'failed' ? 'danger' : row.status === 'partial' ? 'warning' : row.status === 'running' ? 'info' : 'warning'"
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
            <el-table-column prop="timestamp" label="执行时长" width="120">
              <template #default="{ row }">
                <span v-if="row.execution_time !== undefined && row.execution_time !== null">
                  {{ row.execution_time.toFixed(2) }}秒
                </span>
                <span v-else>
                  {{ calculateExecutionDurationFromTimes(row) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="estimated_time" label="剩余时间" width="180">
              <template #default="{ row }">
                {{ calculateEstimatedCompletionTime(row) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="280" fixed="right">
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
                <!-- 🔥 继续执行按钮：仅对挂起状态的任务显示 -->
                <el-button
                  v-if="row.status === 'suspended'"
                  link
                  type="success"
                  size="small"
                  :loading="actionLoading[`resume_${row.execution_id || row._id}`]"
                  @click="handleResumeSuspendedExecution(row)"
                >
                  继续执行
                </el-button>
                <!-- 🔥 重试失败项按钮：仅对历史数据同步任务显示 -->
                <el-button
                  v-if="isHistoricalSyncJob(row.job_id) && (row.status === 'failed' || row.status === 'partial' || (row.status === 'success' && row.errors && row.errors.length > 0))"
                  link
                  type="success"
                  size="small"
                  :loading="actionLoading[`retry_${row.execution_id || row._id}`]"
                  @click="handleRetryFailedSymbols(row)"
                >
                  重试失败项
                </el-button>
                <el-button
                  v-if="row.status === 'running' || row.status === 'suspended'"
                  link
                  type="warning"
                  size="small"
                  @click="handleCancelExecution(row)"
                >
                  终止
                </el-button>
                <el-button
                  v-if="row.status === 'running' || row.status === 'suspended'"
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
                  :type="row.status === 'success' ? 'success' : row.status === 'failed' ? 'danger' : row.status === 'partial' ? 'warning' : row.status === 'running' ? 'info' : 'warning'"
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
            <el-table-column prop="execution_time" label="执行时长" width="120">
              <template #default="{ row }">
                <span v-if="row.execution_time !== undefined && row.execution_time !== null">
                  {{ row.execution_time.toFixed(2) }}秒
                </span>
                <span v-else>
                  {{ calculateExecutionDurationFromTimes(row) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="scheduled_time" label="计划开始时间" width="180">
              <template #default="{ row }">
                {{ formatDateTime(row.scheduled_time) }}
              </template>
            </el-table-column>
            <el-table-column prop="estimated_time" label="剩余时间" width="180">
              <template #default="{ row }">
                {{ calculateEstimatedCompletionTime(row) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="280" fixed="right">
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
                <!-- 🔥 重试失败项按钮：仅对历史数据同步任务显示 -->
                <el-button
                  v-if="isHistoricalSyncJob(row.job_id) && (row.status === 'failed' || row.status === 'partial' || (row.status === 'success' && row.errors && row.errors.length > 0))"
                  link
                  type="success"
                  size="small"
                  :loading="actionLoading[`retry_${row.execution_id || row._id}`]"
                  @click="handleRetryFailedSymbols(row)"
                >
                  重试失败项
                </el-button>
                <el-button
                  v-if="row.status === 'running' || row.status === 'suspended'"
                  link
                  type="warning"
                  size="small"
                  @click="handleCancelExecution(row)"
                >
                  终止
                </el-button>
                <el-button
                  v-if="row.status === 'running' || row.status === 'suspended'"
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
            :type="currentExecution.status === 'success' ? 'success' : currentExecution.status === 'failed' ? 'danger' : currentExecution.status === 'partial' ? 'warning' : currentExecution.status === 'running' ? 'info' : 'warning'"
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
        <el-descriptions-item label="计划开始时间">
          {{ formatDateTime(currentExecution.scheduled_time) }}
        </el-descriptions-item>
        <el-descriptions-item label="更新时间">
          {{ formatDateTime(currentExecution.updated_at || currentExecution.timestamp) }}
        </el-descriptions-item>
        <el-descriptions-item label="执行时长">
          {{ calculateExecutionDuration(currentExecution) }}
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
  Search,
  ArrowDown,
  ArrowUp
} from '@element-plus/icons-vue'
import {
  getJobs,
  getJobDetail,
  pauseJob,
  resumeJob,
  triggerJob,
  updateJobMetadata,
  rescheduleJob,
  getSchedulerStats,
  getJobExecutions,
  getSingleJobExecutions,
  cancelExecution,
  markExecutionFailed,
  deleteExecution,
  retryFailedSymbols,
  resumeSuspendedExecution,
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
  description: '',
  cron_expression: '',
  original_cron: '',
  supports_cron: false,
  // 友好的时间选择器
  frequency: 'weekdays' as 'daily' | 'weekdays' | 'weekend' | 'monday' | 'friday',
  time: '08:00',
  showAdvanced: false
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

const isJobRunning = (job: Job): boolean => {
  return Boolean(job.has_running_execution)
}

const getRunningJobHint = (job: Job): string => {
  const runningExecution = job.running_execution
  if (!runningExecution) {
    return '该任务已有未完成的执行实例，请等待当前任务完成'
  }

  const progress = runningExecution.progress ?? 0
  const startedAt = runningExecution.started_at
  const parts = [`该任务正在执行中`]
  if (progress > 0) {
    parts.push(`当前进度 ${progress}%`)
  }
  if (startedAt) {
    parts.push(`开始于 ${formatDateTime(startedAt)}`)
  }
  return parts.join('，')
}

const getJobRunningProgress = (job: Job): number | null => {
  if (!job.running_execution) {
    return null
  }

  return job.running_execution.progress ?? 0
}

const getJobRunningStartedAt = (job: Job): string | null => {
  return job.running_execution?.started_at || null
}

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

// 从触发器字符串中提取CRON表达式
const extractCronFromTrigger = (trigger: string): string => {
  // 格式: cron[month='*', day='*', day_of_week='1-5', hour='9', minute='30']
  if (!trigger || !trigger.includes('cron[')) {
    return ''
  }

  // 提取各个字段
  const monthMatch = trigger.match(/month='([^']*)'/)
  const dayMatch = trigger.match(/day='([^']*)'/)
  const dayOfWeekMatch = trigger.match(/day_of_week='([^']*)'/)
  const hourMatch = trigger.match(/hour='([^']*)'/)
  const minuteMatch = trigger.match(/minute='([^']*)'/)

  if (!minuteMatch || !hourMatch) {
    return ''
  }

  // 构建CRON表达式: 分 时 日 月 周
  const minute = minuteMatch[1] || '*'
  const hour = hourMatch[1] || '*'
  const day = dayMatch ? dayMatch[1] : '*'
  const month = monthMatch ? monthMatch[1] : '*'
  const dayOfWeek = dayOfWeekMatch ? dayOfWeekMatch[1] : '*'

  return `${minute} ${hour} ${day} ${month} ${dayOfWeek}`
}

// 从CRON表达式解析出频率和时间
const parseCronToUI = (cron: string) => {
  const parts = cron.split(' ')
  if (parts.length !== 5) return

  const [minute, hour, , , dayOfWeek] = parts

  // 解析时间
  const hourNum = parseInt(hour) || 8
  const minuteNum = parseInt(minute) || 0
  editForm.time = `${hourNum.toString().padStart(2, '0')}:${minuteNum.toString().padStart(2, '0')}`

  // 解析频率
  if (dayOfWeek === '*') {
    editForm.frequency = 'daily'
  } else if (dayOfWeek === '1-5') {
    editForm.frequency = 'weekdays'
  } else if (dayOfWeek === '0,6' || dayOfWeek === '6,0') {
    editForm.frequency = 'weekend'
  } else if (dayOfWeek === '1') {
    editForm.frequency = 'monday'
  } else if (dayOfWeek === '5') {
    editForm.frequency = 'friday'
  } else {
    editForm.frequency = 'weekdays' // 默认
  }
}

// 从UI选择生成CRON表达式
const updateCronFromUI = () => {
  const [hour, minute] = editForm.time.split(':')
  let dayOfWeek = '*'

  switch (editForm.frequency) {
    case 'daily':
      dayOfWeek = '*'
      break
    case 'weekdays':
      dayOfWeek = '1-5'
      break
    case 'weekend':
      dayOfWeek = '0,6'
      break
    case 'monday':
      dayOfWeek = '1'
      break
    case 'friday':
      dayOfWeek = '5'
      break
  }

  editForm.cron_expression = `${parseInt(minute)} ${parseInt(hour)} * * ${dayOfWeek}`
}

// 从CRON表达式更新UI（高级模式下用户直接修改CRON时）
const updateUIFromCron = () => {
  parseCronToUI(editForm.cron_expression)
}

// 格式化调度描述
const formatScheduleDescription = (frequency: string, time: string) => {
  const freqMap: Record<string, string> = {
    daily: '每天',
    weekdays: '工作日（周一至周五）',
    weekend: '周末（周六、周日）',
    monday: '每周一',
    friday: '每周五'
  }
  return `${freqMap[frequency] || frequency} ${time} 执行`
}

const showEditDialog = (job: Job) => {
  editingJob.value = job
  editForm.display_name = job.display_name || ''
  editForm.description = job.description || ''
  editForm.showAdvanced = false

  // 判断是否支持CRON（cron触发器）
  const isCronTrigger = job.trigger && job.trigger.includes('cron[')
  editForm.supports_cron = isCronTrigger

  if (isCronTrigger) {
    const cronExpr = extractCronFromTrigger(job.trigger)
    editForm.cron_expression = cronExpr
    editForm.original_cron = cronExpr
    // 解析CRON到UI选择器
    parseCronToUI(cronExpr)
  } else {
    editForm.cron_expression = ''
    editForm.original_cron = ''
    editForm.frequency = 'weekdays'
    editForm.time = '08:00'
  }

  editDialogVisible.value = true
}

const handleSaveMetadata = async () => {
  if (!editingJob.value) return

  try {
    saveLoading.value = true

    // 如果CRON表达式有修改，先调用reschedule API
    if (editForm.supports_cron && editForm.cron_expression !== editForm.original_cron) {
      if (!editForm.cron_expression.trim()) {
        ElMessage.error('CRON表达式不能为空')
        return
      }
      await rescheduleJob(editingJob.value.id, editForm.cron_expression.trim())
    }

    // 更新元数据
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
    if (isJobRunning(job)) {
      ElMessage.warning(getRunningJobHint(job))
      return
    }

    await ElMessageBox.confirm(
      `确定要立即执行任务"${job.name}"吗？任务将在后台执行。`,
      '确认执行',
      {
        type: 'warning'
      }
    )

    actionLoading[job.id] = true
    
    try {
      await triggerJob(job.id)
      ElMessage.success('任务已触发执行')
      await loadJobs()
      
      // 🔥 2秒后再次刷新任务列表，确保状态已更新
      setTimeout(async () => {
        await loadJobs()
      }, 2000)
    } catch (error: any) {
      // 🔥 处理 409 错误（任务正在运行，需要用户确认是否强制执行）
      if (error.response?.status === 409) {
        const errorDetail = error.response?.data?.detail || {}
        const message = errorDetail.message || '任务已有实例正在运行中'
        const suggestion = errorDetail.suggestion || '是否强制执行？强制执行将跳过并发检查，可能导致重复执行。'
        const runningProgress = errorDetail.running_progress || 0
        const runningStartTime = errorDetail.running_start_time
        
        try {
          await ElMessageBox.confirm(
            `${message}\n\n${runningProgress > 0 ? `当前进度: ${runningProgress}%\n` : ''}${runningStartTime ? `开始时间: ${new Date(runningStartTime).toLocaleString()}\n\n` : ''}${suggestion}`,
            '任务正在运行',
            {
              confirmButtonText: '强制执行',
              cancelButtonText: '取消',
              type: 'warning',
              distinguishCancelAndClose: true
            }
          )
          
          // 用户确认强制执行，传递 force=true
          await triggerJob(job.id, { force: true })
          ElMessage.success('任务已强制执行')
          await loadJobs()
          
          // 🔥 2秒后再次刷新任务列表，确保状态已更新
          setTimeout(async () => {
            await loadJobs()
          }, 2000)
        } catch (confirmError: any) {
          // 用户取消或关闭对话框，不执行任何操作
          if (confirmError !== 'cancel' && confirmError !== 'close') {
            ElMessage.error('强制执行失败: ' + (confirmError.message || '未知错误'))
          }
        }
      } else {
        // 其他错误
        throw error
      }
    }
  } catch (error: any) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error.message || '触发任务失败')
    }
  } finally {
    actionLoading[job.id] = false
    await loadJobs()
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
    partial: '部分成功',  // 🔥 新增：部分成功状态
    missed: '错过',
    suspended: '挂起',
    cancelled: '已取消'
  }
  return statusMap[status] || status
}

// 计算执行时长（更新时间 - 计划开始时间）
const calculateExecutionDuration = (execution: JobExecution | null): string => {
  if (!execution) return '-'
  
  // 如果有 execution_time 字段，直接使用
  if (execution.execution_time !== undefined && execution.execution_time !== null) {
    return `${execution.execution_time.toFixed(2)}秒`
  }
  
  // 否则计算：更新时间 - 计划开始时间
  const scheduledTime = execution.scheduled_time
  const updateTime = execution.updated_at || execution.timestamp
  
  if (!scheduledTime || !updateTime) {
    return '-'
  }
  
  try {
    // 处理时间字符串，确保有时区信息
    let scheduledStr = String(scheduledTime).trim()
    let updateStr = String(updateTime).trim()
    
    // 如果没有时区信息，添加 +08:00（后端存储为 UTC+8）
    if (scheduledStr.match(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/) && 
        !scheduledStr.endsWith('Z') && 
        !scheduledStr.includes('+') && 
        !scheduledStr.includes('-', 10)) {
      scheduledStr += '+08:00'
    }
    
    if (updateStr.match(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/) && 
        !updateStr.endsWith('Z') && 
        !updateStr.includes('+') && 
        !updateStr.includes('-', 10)) {
      updateStr += '+08:00'
    }
    
    const scheduledDate = new Date(scheduledStr)
    const updateDate = new Date(updateStr)
    
    if (isNaN(scheduledDate.getTime()) || isNaN(updateDate.getTime())) {
      return '-'
    }
    
    // 计算时间差（秒）
    const diffSeconds = (updateDate.getTime() - scheduledDate.getTime()) / 1000
    
    if (diffSeconds < 0) {
      return '-'
    }
    
    // 格式化显示
    if (diffSeconds < 60) {
      return `${diffSeconds.toFixed(2)}秒`
    } else if (diffSeconds < 3600) {
      const minutes = Math.floor(diffSeconds / 60)
      const seconds = diffSeconds % 60
      return `${minutes}分${seconds.toFixed(0)}秒`
    } else {
      const hours = Math.floor(diffSeconds / 3600)
      const minutes = Math.floor((diffSeconds % 3600) / 60)
      const seconds = diffSeconds % 60
      return `${hours}小时${minutes}分${seconds.toFixed(0)}秒`
    }
  } catch (e) {
    console.error('计算执行时长失败:', e)
    return '-'
  }
}

// 计算执行时长（更新时间 - 开始时间）
const calculateExecutionDurationFromTimes = (row: JobExecution): string => {
  try {
    // 开始时间：优先使用 timestamp（创建时间），如果没有则使用 scheduled_time（计划开始时间）
    const startTime = row.timestamp || row.scheduled_time
    // 结束时间：使用 updated_at（更新时间），如果没有则使用当前时间（对于运行中的任务）
    const endTime = row.updated_at || (row.status === 'running' ? new Date().toISOString() : null)
    
    if (!startTime || !endTime) {
      return '-'
    }
    
    // 处理时间字符串，确保有时区信息
    let startStr = String(startTime).trim()
    let endStr = String(endTime).trim()
    
    // 如果没有时区信息，添加 +08:00（后端存储为 UTC+8）
    if (startStr.match(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/) && 
        !startStr.endsWith('Z') && 
        !startStr.includes('+') && 
        !startStr.includes('-', 10)) {
      startStr += '+08:00'
    }
    
    if (endStr.match(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/) && 
        !endStr.endsWith('Z') && 
        !endStr.includes('+') && 
        !endStr.includes('-', 10)) {
      endStr += '+08:00'
    }
    
    const startDate = new Date(startStr)
    const endDate = new Date(endStr)
    
    if (isNaN(startDate.getTime()) || isNaN(endDate.getTime())) {
      return '-'
    }
    
    // 计算时间差（秒）
    const diffSeconds = (endDate.getTime() - startDate.getTime()) / 1000
    
    if (diffSeconds < 0) {
      return '-'
    }
    
    // 格式化显示
    if (diffSeconds < 60) {
      return `${diffSeconds.toFixed(2)}秒`
    } else if (diffSeconds < 3600) {
      const minutes = Math.floor(diffSeconds / 60)
      const seconds = diffSeconds % 60
      return `${minutes}分${seconds.toFixed(0)}秒`
    } else {
      const hours = Math.floor(diffSeconds / 3600)
      const minutes = Math.floor((diffSeconds % 3600) / 60)
      const seconds = diffSeconds % 60
      return `${hours}小时${minutes}分${seconds.toFixed(0)}秒`
    }
  } catch (e) {
    console.error('计算执行时长失败:', e)
    return '-'
  }
}

// 计算预计完成时间或剩余时间
const calculateEstimatedCompletionTime = (row: JobExecution): string => {
  try {
    // 如果任务已完成或失败，不显示预计完成时间
    if (row.status !== 'running') {
      return '-'
    }
    
    // 如果没有进度信息，无法计算
    if (row.progress === undefined || row.progress === null || row.progress <= 0) {
      return '计算中...'
    }
    
    // 计算已花时间（秒）
    const startTime = row.timestamp || row.scheduled_time
    const endTime = row.updated_at || new Date().toISOString()
    
    if (!startTime || !endTime) {
      return '计算中...'
    }
    
    // 处理时间字符串，确保有时区信息
    let startStr = String(startTime).trim()
    let endStr = String(endTime).trim()
    
    // 如果没有时区信息，添加 +08:00（后端存储为 UTC+8）
    if (startStr.match(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/) && 
        !startStr.endsWith('Z') && 
        !startStr.includes('+') && 
        !startStr.includes('-', 10)) {
      startStr += '+08:00'
    }
    
    if (endStr.match(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/) && 
        !endStr.endsWith('Z') && 
        !endStr.includes('+') && 
        !endStr.includes('-', 10)) {
      endStr += '+08:00'
    }
    
    const startDate = new Date(startStr)
    const endDate = new Date(endStr)
    
    if (isNaN(startDate.getTime()) || isNaN(endDate.getTime())) {
      return '计算中...'
    }
    
    // 计算已花时间（秒）
    const elapsedSeconds = (endDate.getTime() - startDate.getTime()) / 1000
    
    if (elapsedSeconds <= 0) {
      return '计算中...'
    }
    
    // 进度百分比（0-100）
    const progressPercent = row.progress / 100
    
    // 如果进度已经是100%，说明已完成
    if (progressPercent >= 1) {
      return '即将完成'
    }
    
    // 如果进度为0或接近0，无法准确计算
    if (progressPercent <= 0) {
      return '计算中...'
    }
    
    // 计算预计总时间：已花时间 / 进度百分比
    // 例如：已花100秒，进度50%，预计总时间 = 100 / 0.5 = 200秒
    const estimatedTotalSeconds = elapsedSeconds / progressPercent
    
    // 计算剩余时间：预计总时间 - 已花时间
    const remainingSeconds = estimatedTotalSeconds - elapsedSeconds
    
    if (remainingSeconds <= 0) {
      return '即将完成'
    }
    
    // 格式化剩余时间显示
    if (remainingSeconds < 60) {
      return `剩余 ${remainingSeconds.toFixed(0)}秒`
    } else if (remainingSeconds < 3600) {
      const minutes = Math.floor(remainingSeconds / 60)
      const seconds = Math.floor(remainingSeconds % 60)
      return `剩余 ${minutes}分${seconds}秒`
    } else {
      const hours = Math.floor(remainingSeconds / 3600)
      const minutes = Math.floor((remainingSeconds % 3600) / 60)
      return `剩余 ${hours}小时${minutes}分`
    }
  } catch (e) {
    console.error('计算预计完成时间失败:', e)
    return '计算中...'
  }
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

    // 🔥 立即刷新列表
    if (activeHistoryTab.value === 'execution') {
      await loadExecutions()
    } else {
      await loadHistory()
    }
    
    // 🔥 刷新任务列表
    await loadJobs()
    
    // 🔥 2秒后再次刷新，确保状态已更新为终止
    setTimeout(async () => {
      if (activeHistoryTab.value === 'execution') {
        await loadExecutions()
      } else {
        await loadHistory()
      }
      await loadJobs()
    }, 2000)
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

// 🔥 判断是否为历史数据同步任务
const isHistoricalSyncJob = (jobId: string | undefined): boolean => {
  if (!jobId) return false
  return jobId === 'tushare_historical_sync' ||
         jobId === 'akshare_historical_sync' ||
         jobId === 'baostock_historical_sync'
}

// 🔥 恢复挂起的任务执行
const handleResumeSuspendedExecution = async (row: JobExecution) => {
  const executionId = row.execution_id || row._id
  if (!executionId) {
    ElMessage.error('执行记录ID不存在')
    return
  }

  try {
    // 确认操作
    await ElMessageBox.confirm(
      '确定要继续执行这个挂起的任务吗？\n\n' +
      '• 任务将从上次中断的位置继续执行\n' +
      `• 当前进度: ${row.progress || 0}%\n` +
      (row.processed_items && row.total_items
        ? `• 已处理: ${row.processed_items}/${row.total_items}\n`
        : '') +
      '• 继续执行后将无法撤销',
      '确认继续执行',
      {
        confirmButtonText: '继续执行',
        cancelButtonText: '取消',
        type: 'info'
      }
    )

    actionLoading[`resume_${executionId}`] = true

    await resumeSuspendedExecution(executionId)
    ElMessage.success('任务已恢复执行，将从上次进度位置继续')

    // 刷新列表
    if (activeHistoryTab.value === 'execution') {
      await loadExecutions()
    } else {
      await loadHistory()
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '恢复任务失败')
    }
  } finally {
    actionLoading[`resume_${executionId}`] = false
  }
}

// 🔥 重试失败的股票
const handleRetryFailedSymbols = async (execution: any) => {
  const executionId = execution.execution_id || execution._id
  if (!executionId) {
    ElMessage.error('执行记录ID不存在')
    return
  }

  try {
    // 确认操作
    await ElMessageBox.confirm(
      '确定要重试失败的股票吗？\n\n' +
      '• 只重试可重试的错误（网络错误、API超时等）\n' +
      '• 跳过无数据的错误（股票不存在、日期范围不合理等）\n' +
      '• 重试将创建一个新的任务执行',
      '确认重试失败项',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'info'
      }
    )

    actionLoading[`retry_${executionId}`] = true

    const res = await retryFailedSymbols(executionId)
    
    if (res.success) {
      const data = res.data
      ElMessage.success(
        `重试完成：成功 ${data.success_count}/${data.total_retried} 只股票，` +
        `失败 ${data.error_count} 只，` +
        `无数据 ${data.no_data_count} 只（已跳过）`
      )
      
      // 刷新列表
      if (activeHistoryTab.value === 'execution') {
        await loadExecutions()
      } else {
        await loadHistory()
      }
    } else {
      ElMessage.error(res.message || '重试失败')
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '重试失败项失败')
    }
  } finally {
    actionLoading[`retry_${executionId}`] = false
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
      flex-direction: column;
      gap: 6px;

      .job-name-main {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
      }

      .name-text {
        font-weight: 500;
      }

      .job-running-summary {
        display: flex;
        gap: 12px;
        font-size: 12px;
        color: var(--el-color-danger);
        margin-left: 2px;
        flex-wrap: wrap;
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

.form-tip {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;

  .el-link {
    font-size: 12px;
    vertical-align: baseline;
  }
}

.schedule-picker {
  width: 100%;

  .schedule-row {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .schedule-sep {
    color: var(--el-text-color-secondary);
    font-size: 14px;
  }

  .schedule-preview {
    margin-top: 12px;

    .el-tag {
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
  }

  .schedule-advanced {
    margin-top: 12px;

    .el-link {
      font-size: 12px;
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
  }

  .schedule-cron {
    margin-top: 8px;
    padding: 12px;
    background: var(--el-fill-color-light);
    border-radius: 4px;

    .cron-help {
      margin-top: 8px;
      font-size: 12px;
      color: var(--el-text-color-secondary);

      code {
        background: var(--el-fill-color);
        padding: 2px 6px;
        border-radius: 3px;
        font-family: 'Courier New', monospace;
      }
    }
  }
}
</style>

