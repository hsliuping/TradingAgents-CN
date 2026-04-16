<template>
  <div class="operation-logs">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1 class="page-title">
        <el-icon><Document /></el-icon>
        操作日志
      </h1>
      <p class="page-description">
        系统操作日志查看、过滤和分析
      </p>
    </div>

    <!-- 筛选控制面板 -->
    <el-card class="filter-panel" shadow="never">
      <el-form :model="filterForm" :inline="true" @submit.prevent="loadLogs">
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="filterForm.dateRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            format="YYYY-MM-DD HH:mm:ss"
            value-format="YYYY-MM-DD HH:mm:ss"
            style="width: 350px"
          />
        </el-form-item>

        <el-form-item label="操作类型">
          <el-select v-model="filterForm.actionType" clearable placeholder="全部类型" style="width: 150px">
            <el-option label="全部类型" value="" />
            <el-option label="股票分析" value="stock_analysis" />
            <el-option label="配置管理" value="config_management" />
            <el-option label="缓存操作" value="cache_operation" />
            <el-option label="数据导入" value="data_import" />
            <el-option label="数据导出" value="data_export" />
            <el-option label="系统设置" value="system_settings" />
          </el-select>
        </el-form-item>

        <el-form-item label="操作状态">
          <el-select v-model="filterForm.success" clearable placeholder="全部状态" style="width: 120px">
            <el-option label="全部状态" value="" />
            <el-option label="成功" :value="true" />
            <el-option label="失败" :value="false" />
          </el-select>
        </el-form-item>

        <el-form-item label="关键词">
          <el-input
            v-model="filterForm.keyword"
            placeholder="搜索操作内容"
            style="width: 200px"
            @keyup.enter="loadLogs"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="loadLogs" :loading="loading">
            <el-icon><Search /></el-icon>
            查询
          </el-button>
          <el-button @click="resetFilter">
            <el-icon><Refresh /></el-icon>
            重置
          </el-button>
          <el-button @click="exportLogs">
            <el-icon><Download /></el-icon>
            导出
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 统计概览 -->
    <el-row :gutter="24" style="margin-top: 24px">
      <el-col :span="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-content">
            <div class="stat-value">{{ stats.totalLogs }}</div>
            <div class="stat-label">总日志数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-content">
            <div class="stat-value">{{ stats.successLogs }}</div>
            <div class="stat-label">成功操作</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-content">
            <div class="stat-value">{{ stats.failedLogs }}</div>
            <div class="stat-label">失败操作</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-content">
            <div class="stat-value">{{ stats.successRate }}%</div>
            <div class="stat-label">成功率</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 操作类型分布图表 -->
    <el-row :gutter="24" style="margin-top: 24px">
      <el-col :span="12">
        <el-card class="chart-card" shadow="never">
          <template #header>
            <h3>📊 操作类型分布</h3>
          </template>
          <div ref="actionTypeChart" class="chart-container"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="chart-card" shadow="never">
          <template #header>
            <h3>📈 操作趋势</h3>
          </template>
          <div ref="operationTrendChart" class="chart-container"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 日志列表 -->
    <el-card class="logs-table" shadow="never" style="margin-top: 24px">
      <template #header>
        <div class="table-header">
          <h3>📋 操作日志列表</h3>
          <div class="table-actions">
            <el-button size="small" @click="loadLogs">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
            <el-button size="small" @click="clearLogs" type="danger">
              <el-icon><Delete /></el-icon>
              清空日志
            </el-button>
          </div>
        </div>
      </template>

      <el-table
        :data="logs"
        v-loading="loading"
        style="width: 100%"
        :default-sort="{ prop: 'timestamp', order: 'descending' }"
        @row-click="viewLogDetails"
      >
        <el-table-column prop="timestamp" label="时间" width="180" sortable>
          <template #default="{ row }">
            {{ formatDateTime(row.timestamp) }}
          </template>
        </el-table-column>

        <el-table-column prop="action_type" label="操作类型" width="120">
          <template #default="{ row }">
            <el-tag :type="getActionTypeTag(row.action_type)" size="small">
              {{ getActionTypeName(row.action_type) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="action" label="操作内容" min-width="200">
          <template #default="{ row }">
            <div class="action-content">
              <div class="action-title">{{ row.action }}</div>
              <div v-if="row.details && row.details.stock_symbol" class="action-detail">
                股票: {{ row.details.stock_symbol }}
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="success" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.success ? 'success' : 'danger'" size="small">
              {{ row.success ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="duration_ms" label="耗时" width="100">
          <template #default="{ row }">
            <span v-if="row.duration_ms">{{ row.duration_ms }}ms</span>
            <span v-else>-</span>
          </template>
        </el-table-column>

        <el-table-column prop="ip_address" label="IP地址" width="120" />

        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button size="small" @click.stop="viewLogDetails(row)">
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-if="totalLogs > 0"
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="totalLogs"
        :page-sizes="[20, 50, 100, 200]"
        layout="total, sizes, prev, pager, next, jumper"
        style="margin-top: 16px; text-align: right"
        @size-change="loadLogs"
        @current-change="loadLogs"
      />
    </el-card>

    <!-- 日志详情对话框 -->
    <el-dialog
      v-model="detailDialogVisible"
      title="操作日志详情"
      width="600px"
    >
      <div v-if="selectedLog" class="log-details">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="操作时间">
            {{ formatDateTime(selectedLog.timestamp) }}
          </el-descriptions-item>
          <el-descriptions-item label="操作类型">
            <el-tag :type="getActionTypeTag(selectedLog.action_type)">
              {{ getActionTypeName(selectedLog.action_type) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="操作内容" :span="2">
            {{ selectedLog.action }}
          </el-descriptions-item>
          <el-descriptions-item label="操作状态">
            <el-tag :type="selectedLog.success ? 'success' : 'danger'">
              {{ selectedLog.success ? '成功' : '失败' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="耗时">
            {{ selectedLog.duration_ms ? selectedLog.duration_ms + 'ms' : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="IP地址">
            {{ selectedLog.ip_address || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="会话ID">
            {{ selectedLog.session_id || '-' }}
          </el-descriptions-item>
        </el-descriptions>

        <!-- 错误信息 -->
        <div v-if="!selectedLog.success && selectedLog.error_message" class="error-section">
          <h4>错误信息</h4>
          <el-alert
            :title="selectedLog.error_message"
            type="error"
            :closable="false"
            show-icon
          />
        </div>

        <!-- 详细信息 -->
        <div v-if="selectedLog.details" class="details-section">
          <h4>详细信息</h4>
          <el-input
            :model-value="JSON.stringify(selectedLog.details, null, 2)"
            type="textarea"
            :rows="8"
            readonly
          />
        </div>
      </div>
    </el-dialog>

    <!-- 空状态 -->
    <el-empty
      v-if="!loading && logs.length === 0"
      description="暂无操作日志"
      :image-size="200"
    >
      <template #description>
        <div class="empty-description">
          <p>暂无符合条件的操作日志</p>
          <div class="empty-tips">
            <h4>💡 如何产生操作日志？</h4>
            <ul>
              <li>进行股票分析操作</li>
              <li>修改系统配置</li>
              <li>执行缓存管理操作</li>
              <li>进行数据导入导出</li>
            </ul>
          </div>
        </div>
      </template>
    </el-empty>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Document,
  Search,
  Refresh,
  Download,
  Delete
} from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import {
  OperationLogsApi,
  type OperationLog,
  type OperationLogStats,
  getActionTypeName,
  getActionTypeTagColor,
  formatDateTime
} from '@/api/operationLogs'

type TagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

// 响应式数据
const loading = ref(false)
const detailDialogVisible = ref(false)
const selectedLog = ref<OperationLog | null>(null)
const currentPage = ref(1)
const pageSize = ref(20)
const totalLogs = ref(0)

// 图表引用
const actionTypeChart = ref<HTMLDivElement | null>(null)
const operationTrendChart = ref<HTMLDivElement | null>(null)

// 筛选表单
const filterForm = reactive({
  dateRange: [] as string[],
  actionType: '',
  success: '' as '' | boolean,
  keyword: ''
})

// 统计数据
const stats = reactive({
  totalLogs: 0,
  successLogs: 0,
  failedLogs: 0,
  successRate: 0
})

// 日志数据
const logs = ref<OperationLog[]>([])

// 统计数据详细信息
const statsData = ref<OperationLogStats | null>(null)

// 方法
const getActionTypeTag = (actionType: string): TagType => {
  return getActionTypeTagColor(actionType)
}

const loadLogs = async () => {
  loading.value = true
  try {
    // 构建查询参数
    const queryParams = {
      page: currentPage.value,
      page_size: pageSize.value,
      start_date: filterForm.dateRange[0] || undefined,
      end_date: filterForm.dateRange[1] || undefined,
      action_type: filterForm.actionType || undefined,
      success: filterForm.success !== '' ? filterForm.success : undefined,
      keyword: filterForm.keyword || undefined
    }

    // 调用API获取日志列表
    const response = await OperationLogsApi.getOperationLogs(queryParams)
    logs.value = response.logs
    totalLogs.value = response.total

    await loadStats()
    await nextTick()
    renderCharts()

  } catch (error) {
    console.error('加载操作日志失败:', error)
    ElMessage.error('加载操作日志失败')
  } finally {
    loading.value = false
  }
}

const loadStats = async () => {
  try {
    const response = await OperationLogsApi.getOperationLogStats(30)
    statsData.value = response
    stats.totalLogs = response.total_logs
    stats.successLogs = response.success_logs
    stats.failedLogs = response.failed_logs
    stats.successRate = response.success_rate
  } catch (error) {
    console.error('获取统计数据失败:', error)
  }
}

const resetFilter = () => {
  Object.assign(filterForm, {
    dateRange: [],
    actionType: '',
    success: '',
    keyword: ''
  })
  loadLogs()
}

const exportLogs = async () => {
  try {
    loading.value = true

    const params = {
      start_date: filterForm.dateRange[0] || undefined,
      end_date: filterForm.dateRange[1] || undefined,
      action_type: filterForm.actionType || undefined
    }

    const blob = await OperationLogsApi.exportOperationLogsCSV(params)

    // 创建下载链接
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `operation_logs_${new Date().toISOString().slice(0, 10)}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)

    ElMessage.success('操作日志导出成功')
  } catch (error) {
    console.error('导出操作日志失败:', error)
    ElMessage.error('导出操作日志失败')
  } finally {
    loading.value = false
  }
}

const clearLogs = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要清空所有操作日志吗？此操作无法恢复！',
      '确认清空',
      {
        type: 'error',
        confirmButtonText: '确定清空',
        cancelButtonText: '取消'
      }
    )

    loading.value = true

    const response = await OperationLogsApi.clearOperationLogs()

    if (response.success) {
      ElMessage.success(response.message)
      loadLogs()
    } else {
      ElMessage.error(response.message || '清空操作日志失败')
    }

  } catch (error) {
    if (error !== 'cancel') {
      console.error('清空操作日志失败:', error)
      ElMessage.error('清空操作日志失败')
    }
  } finally {
    loading.value = false
  }
}

const viewLogDetails = (row: any) => {
  selectedLog.value = row
  detailDialogVisible.value = true
}

const renderCharts = () => {
  if (!statsData.value) return

  // 操作类型分布图
  if (actionTypeChart.value) {
    const chart1 = echarts.init(actionTypeChart.value)

    const pieData = Object.entries(statsData.value.action_type_distribution).map(([type, count]) => ({
      value: count,
      name: getActionTypeName(type)
    }))

    chart1.setOption({
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie',
        radius: '60%',
        data: pieData
      }]
    })
  }

  // 操作趋势图
  if (operationTrendChart.value) {
    const chart2 = echarts.init(operationTrendChart.value)

    const hourlyData = statsData.value.hourly_distribution
    const hours = hourlyData.map(item => item.hour)
    const counts = hourlyData.map(item => item.count)

    chart2.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: hours
      },
      yAxis: { type: 'value' },
      series: [{
        data: counts,
        type: 'line',
        smooth: true,
        areaStyle: {}
      }]
    })
  }
}

// 生命周期
onMounted(() => {
  loadLogs()
})
</script>

<style lang="scss" scoped>
.operation-logs {
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

  .stat-card {
    .stat-content {
      text-align: center;
      
      .stat-value {
        font-size: 24px;
        font-weight: 600;
        color: var(--el-color-primary);
        margin-bottom: 8px;
      }
      
      .stat-label {
        font-size: 14px;
        color: var(--el-text-color-regular);
      }
    }
  }

  .chart-card {
    .chart-container {
      height: 250px;
    }
  }

  .logs-table {
    .table-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      
      h3 {
        margin: 0;
      }
      
      .table-actions {
        display: flex;
        gap: 8px;
      }
    }
    
    .action-content {
      .action-title {
        font-weight: 500;
        margin-bottom: 2px;
      }
      
      .action-detail {
        font-size: 12px;
        color: var(--el-text-color-placeholder);
      }
    }
  }

  .log-details {
    .error-section,
    .details-section {
      margin-top: 16px;
      
      h4 {
        margin: 0 0 8px 0;
        font-size: 14px;
        color: var(--el-text-color-primary);
      }
    }
  }

  .empty-description {
    .empty-tips {
      margin-top: 16px;
      text-align: left;
      
      h4 {
        margin: 0 0 8px 0;
        color: var(--el-text-color-primary);
      }
      
      ul {
        margin: 0;
        padding-left: 20px;
        
        li {
          margin-bottom: 4px;
          color: var(--el-text-color-regular);
        }
      }
    }
  }
}
</style>
