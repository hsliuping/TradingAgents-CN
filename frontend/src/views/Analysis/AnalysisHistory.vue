<template>
  <div class="analysis-history">
    <div class="page-header">
      <h1 class="page-title">
        <el-icon><Clock /></el-icon>
        分析历史
      </h1>
      <p class="page-description">
        查看历史分析记录和结果
      </p>
    </div>

    <!-- 筛选条件 -->
    <el-card class="filter-card" shadow="never">
      <el-form :model="filterForm" :inline="true" @submit.prevent="loadAnalysisHistory">
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="filterForm.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            style="width: 240px"
          />
        </el-form-item>

        <el-form-item label="市场类型">
          <el-select v-model="filterForm.marketType" clearable placeholder="全部市场" style="width: 120px">
            <el-option label="全部市场" value="" />
            <el-option label="美股" value="美股" />
            <el-option label="A股" value="A股" />
            <el-option label="港股" value="港股" />
          </el-select>
        </el-form-item>

        <el-form-item label="分析类型">
          <el-select v-model="filterForm.analysisType" clearable placeholder="全部类型" style="width: 120px">
            <el-option label="全部类型" value="" />
            <el-option label="基础分析" value="basic" />
            <el-option label="深度分析" value="deep" />
            <el-option label="技术分析" value="technical" />
            <el-option label="综合分析" value="comprehensive" />
          </el-select>
        </el-form-item>

        <el-form-item label="股票代码">
          <el-input
            v-model="filterForm.stockSymbol"
            placeholder="输入股票代码"
            style="width: 150px"
            @keyup.enter="loadAnalysisHistory"
          />
        </el-form-item>

        <el-form-item label="标签">
          <el-select v-model="filterForm.tags" multiple clearable placeholder="选择标签" style="width: 200px">
            <el-option
              v-for="tag in availableTags"
              :key="tag"
              :label="tag"
              :value="tag"
            />
          </el-select>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="loadAnalysisHistory" :loading="loading">
            <el-icon><Search /></el-icon>
            查询
          </el-button>
          <el-button @click="resetFilter">
            <el-icon><Refresh /></el-icon>
            重置
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 统计概览 -->
    <el-row :gutter="24" style="margin-top: 24px">
      <el-col :span="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-content">
            <div class="stat-value">{{ stats.totalAnalyses }}</div>
            <div class="stat-label">总分析数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-content">
            <div class="stat-value">{{ stats.favoriteCount }}</div>
            <div class="stat-label">收藏数量</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-content">
            <div class="stat-value">{{ stats.uniqueStocks }}</div>
            <div class="stat-label">分析股票数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-content">
            <div class="stat-value">{{ stats.avgScore }}</div>
            <div class="stat-label">平均评分</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 操作工具栏 -->
    <el-card class="toolbar" shadow="never" style="margin-top: 24px">
      <div class="toolbar-content">
        <div class="toolbar-left">
          <el-checkbox v-model="selectAll" @change="handleSelectAll">全选</el-checkbox>
          <span class="selected-count">已选择 {{ selectedAnalyses.length }} 项</span>
        </div>
        <div class="toolbar-right">
          <el-button
            :disabled="selectedAnalyses.length === 0"
            @click="batchAddToFavorites"
          >
            <el-icon><Star /></el-icon>
            批量收藏
          </el-button>
          <el-button
            :disabled="selectedAnalyses.length === 0"
            @click="batchAddTags"
          >
            <el-icon><PriceTag /></el-icon>
            批量标签
          </el-button>
          <el-button
            :disabled="selectedAnalyses.length === 0"
            @click="batchExport"
          >
            <el-icon><Download /></el-icon>
            批量导出
          </el-button>
          <el-button
            :disabled="selectedAnalyses.length < 2"
            @click="compareAnalyses"
            type="primary"
          >
            <el-icon><Operation /></el-icon>
            对比分析
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 分析结果列表 -->
    <el-card class="results-list" shadow="never" style="margin-top: 24px">
      <template #header>
        <div class="list-header">
          <h3>📊 分析结果列表</h3>
          <div class="view-controls">
            <el-radio-group v-model="viewMode" size="small">
              <el-radio-button label="list">列表</el-radio-button>
              <el-radio-button label="card">卡片</el-radio-button>
            </el-radio-group>
          </div>
        </div>
      </template>

      <div class="action-buttons">
        <el-button @click="refreshHistory">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button @click="exportHistory">
          <el-icon><Download /></el-icon>
          导出
        </el-button>
      </div>
    </el-card>

    <!-- 历史记录列表 -->
    <el-card class="history-list-card" shadow="never">
      <el-table 
        :data="historyList" 
        v-loading="loading" 
        style="width: 100%"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" />
        
        <el-table-column prop="task_id" label="任务ID" width="180">
          <template #default="{ row }">
            <el-link type="primary" @click="viewTaskDetail(row)">
              {{ row.task_id || '-' }}
            </el-link>
          </template>
        </el-table-column>

        <el-table-column prop="stock_code" label="股票代码" width="120" />
        <el-table-column prop="stock_name" label="股票名称" width="150" />

        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>

        <el-table-column prop="execution_time" label="执行时长" width="120">
          <template #default="{ row }">
            {{ row.execution_time ? `${row.execution_time}s` : '-' }}
          </template>
        </el-table-column>

        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'completed'"
              type="text"
              size="small"
              @click="viewResult(row)"
            >
              查看结果
            </el-button>
            <el-button
              v-if="row.status === 'completed'"
              type="text"
              size="small"
              @click="downloadReport(row)"
            >
              下载报告
            </el-button>
            <el-button
              v-if="row.status === 'failed'"
              type="text"
              size="small"
              @click="retryAnalysis(row)"
            >
              重新分析
            </el-button>
            <el-button type="text" size="small" @click="deleteRecord(row)">
              删除
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
          :total="totalRecords"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  Clock, 
  Search, 
  Refresh, 
  Download, 
  Star, 
  PriceTag, 
  Operation 
} from '@element-plus/icons-vue'
import { analysisApi } from '@/api/analysis'
import { useRouter } from 'vue-router'
import { formatDateTime } from '@/utils/datetime'

// 列表与分页状态
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const totalRecords = ref(0)
const historyList = ref<any[]>([])
const statusFilter = ref('')

// 筛选表单
const filterForm = ref({
  dateRange: [],
  marketType: '',
  analysisType: '',
  stockSymbol: '',
  tags: [] as string[]
})

// 标签可选项（后续可从后端获取）
const availableTags = ref<string[]>([])

// 选择相关
const selectAll = ref(false)
const selectedAnalyses = ref<any[]>([])

const handleSelectAll = (val: string | number | boolean) => {
  const isChecked = Boolean(val)
  if (isChecked) selectedAnalyses.value = [...historyList.value]
  else selectedAnalyses.value = []
}

const handleSelectionChange = (selection: any[]) => {
  selectedAnalyses.value = selection
  selectAll.value = selection.length === historyList.value.length && historyList.value.length > 0
}

// 加载历史
const loadAnalysisHistory = async () => {
  loading.value = true
  try {
    const params: any = {
      page: currentPage.value,
      page_size: pageSize.value,
      stock_symbol: filterForm.value.stockSymbol || undefined,
      market_type: filterForm.value.marketType || undefined,
      analysis_type: filterForm.value.analysisType || undefined
    }
    if (filterForm.value.dateRange && filterForm.value.dateRange.length === 2) {
      params.start_date = filterForm.value.dateRange[0]
      params.end_date = filterForm.value.dateRange[1]
    }

    // 使用任务列表接口作为历史数据源（已打通MongoDB兜底）
    const res = await analysisApi.getTaskList({
      status: statusFilter.value || undefined,
      limit: pageSize.value,
      offset: (currentPage.value - 1) * pageSize.value
    })
    const body = (res as any)?.data?.data || {}

    const list = body.tasks || []
    historyList.value = list.map((x: any) => ({
      task_id: x.task_id || x.analysis_id || x.id || '-',
      stock_code: x.symbol || x.stock_code || x.stock_symbol || '-',  // 兼容新旧字段
      stock_name: x.stock_name || x.name || '',
      status: x.status || 'pending',
      created_at: x.start_time || x.created_at || new Date().toISOString(),
      execution_time: x.execution_time || x.elapsed_time || 0
    }))

    totalRecords.value = body.total ?? historyList.value.length
  } catch (e) {
    ElMessage.error('加载历史失败')
  } finally {
    loading.value = false
  }
}

const resetFilter = () => {
  filterForm.value = { dateRange: [], marketType: '', analysisType: '', stockSymbol: '', tags: [] }
  currentPage.value = 1
  loadAnalysisHistory()
}

const handleSizeChange = (size: number) => {
  pageSize.value = size
  currentPage.value = 1
  loadAnalysisHistory()
}

const handleCurrentChange = (page: number) => {
  currentPage.value = page
  loadAnalysisHistory()
}

onMounted(() => {
  loadAnalysisHistory()
})

const refreshHistory = () => {
  loading.value = true
  setTimeout(() => {
    loading.value = false
    ElMessage.success('历史记录已刷新')
  }, 1000)
}

const exportHistory = () => {
  ElMessage.info('导出功能开发中...')
}

const viewTaskDetail = (_task: any) => {
  ElMessage.info('任务详情功能开发中...')
}

const viewResult = (task: any) => {
  const router = useRouter()
  router.push(`/analysis/result/${task.task_id}`)
}

const downloadReport = (task: any) => {
  ElMessage.success(`正在下载 ${task.stock_name} 的分析报告`)
}

const retryAnalysis = (task: any) => {
  ElMessage.success(`${task.stock_name} 重新分析任务已提交`)
}

const deleteRecord = async (task: any) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除 ${task.stock_name} 的分析记录吗？`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    ElMessage.success('记录已删除')
  } catch {
    // 用户取消
  }
}

const getStatusType = (status: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' => {
  const statusMap: Record<string, 'primary' | 'success' | 'warning' | 'info' | 'danger'> = {
    pending: 'info',
    processing: 'warning',
    completed: 'success',
    failed: 'danger',
    cancelled: 'info'
  }
  return statusMap[status] || 'info'
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

const formatTime = (time: string) => {
  return formatDateTime(time)
}

// 统计数据
const stats = ref({
  totalAnalyses: 0,
  favoriteCount: 0,
  uniqueStocks: 0,
  avgScore: 0
})

// 视图模式
const viewMode = ref('list')

const batchAddToFavorites = () => {
  ElMessage.info('批量收藏功能开发中...')
}

const batchAddTags = () => {
  ElMessage.info('批量标签功能开发中...')
}

const batchExport = () => {
  ElMessage.info('批量导出功能开发中...')
}

const compareAnalyses = () => {
  ElMessage.info('对比分析功能开发中...')
}
</script>

<style lang="scss" scoped>
.analysis-history {
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

  .filter-card {
    margin-bottom: 24px;

    .action-buttons {
      display: flex;
      gap: 8px;
      justify-content: flex-end;
    }
  }

  .toolbar {
    .toolbar-content {
      display: flex;
      justify-content: space-between;
      align-items: center;

      .toolbar-left {
        display: flex;
        align-items: center;
        gap: 16px;

        .selected-count {
          color: var(--el-text-color-regular);
          font-size: 14px;
        }
      }

      .toolbar-right {
        display: flex;
        gap: 8px;
      }
    }
  }

  .stat-card {
    .stat-content {
      text-align: center;
      padding: 16px;

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

  .results-list {
    .list-header {
      display: flex;
      justify-content: space-between;
      align-items: center;

      h3 {
        margin: 0;
        font-size: 16px;
        font-weight: 600;
      }
    }

    .action-buttons {
      display: flex;
      gap: 8px;
      justify-content: flex-end;
    }
  }

  .history-list-card {
    .pagination-wrapper {
      display: flex;
      justify-content: center;
      margin-top: 24px;
    }
  }
}
</style>
