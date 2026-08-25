<template>
  <div class="reports">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1 class="page-title">
        <el-icon><Document /></el-icon>
        分析报告
      </h1>
      <p class="page-description">
        查看和管理股票分析报告，支持多种格式导出（批量导出最多 10 个）
      </p>
    </div>

    <!-- 筛选和操作栏 -->
    <el-card class="filter-card" shadow="never">
      <el-row :gutter="16" align="middle">
        <el-col :span="6">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索股票代码或名称"
            clearable
            @input="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-col>
        
        <el-col :span="4">
          <el-select v-model="marketFilter" placeholder="市场筛选" clearable @change="handleMarketChange">
            <el-option label="A股" value="A股" />
          </el-select>
        </el-col>
        
        <el-col :span="6">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            @change="handleDateChange"
          />
        </el-col>
        
        <el-col :span="8">
          <div class="action-buttons">
            <el-dropdown @command="(format: string) => exportSelected(format)">
              <el-button :disabled="selectedReports.length === 0" :loading="batchExporting">
                <el-icon><Download /></el-icon>
                批量导出
                <span v-if="selectedReports.length > 0">({{ selectedReports.length }}/10)</span>
                <el-icon class="el-icon--right"><arrow-down /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="markdown">Markdown</el-dropdown-item>
                  <el-dropdown-item command="docx">Word 文档</el-dropdown-item>
                  <el-dropdown-item command="pdf">PDF</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-button @click="refreshReports">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 报告列表 -->
    <el-card class="reports-list-card" shadow="never">
      <el-table
        ref="tableRef"
        :data="filteredReports"
        @selection-change="handleSelectionChange"
        v-loading="loading"
        style="width: 100%"
      >
        <el-table-column type="selection" width="55" :selectable="isRowSelectable" />
        
        <el-table-column prop="title" label="报告标题" min-width="200">
          <template #default="{ row }">
            <div class="report-title">
              <el-link type="primary" @click="viewReport(row)">
                {{ row.stock_code }} - {{ row.stock_name }}
              </el-link>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column prop="type" label="报告类型" width="120">
          <template #default="{ row }">
            <el-tag :type="getTypeColor(row.type)">
              {{ getTypeText(row.type) }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="format" label="格式" width="100">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">
              {{ row.format.toUpperCase() }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="model_info" label="分析模型" width="180">
          <template #default="{ row }">
            <el-tag v-if="row.model_info && row.model_info !== 'Unknown'" type="info" size="small">
              {{ row.model_info }}
            </el-tag>
            <span v-else class="text-gray">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="research_depth" label="分析深度" width="100" align="center">
          <template #default="{ row }">
            <el-tooltip v-if="row.research_depth" :content="getResearchDepthDescription(row.research_depth)" placement="top">
              <el-tag type="warning" size="small" style="cursor: help;">
                深度 {{ row.research_depth }}
              </el-tag>
            </el-tooltip>
            <span v-else class="text-gray">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>

        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button type="text" size="small" @click="viewReport(row)">
              查看
            </el-button>
            <el-dropdown
              v-if="row.status === 'completed'"
              trigger="click"
              @command="(format) => downloadReport(row, format)"
            >
              <el-button type="text" size="small">
                下载 <el-icon class="el-icon--right"><arrow-down /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="markdown">
                    <el-icon><document /></el-icon> Markdown
                  </el-dropdown-item>
                  <el-dropdown-item command="docx">
                    <el-icon><document /></el-icon> Word 文档
                  </el-dropdown-item>
                  <el-dropdown-item command="pdf">
                    <el-icon><document /></el-icon> PDF
                  </el-dropdown-item>
                  <el-dropdown-item command="json" divided>
                    <el-icon><document /></el-icon> JSON (原始数据)
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-button
              type="text"
              size="small"
              @click="deleteReport(row)"
              style="color: var(--el-color-danger)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>

        <template #empty>
          <el-empty v-if="!loading" description="暂无分析报告" :image-size="120">
            <template #description>
              <p>暂无分析报告，执行一次股票分析即可生成报告</p>
            </template>
          </el-empty>
        </template>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[20, 50, 100]"
          :total="totalReports"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Document,
  Search,
  Download,
  Refresh,
  ArrowDown
} from '@element-plus/icons-vue'
import { ApiClient } from '@/api/request'

type ElTagType = 'primary' | 'success' | 'info' | 'warning' | 'danger'

interface ReportListItem {
  id: string | number
  title?: string
  stock_code: string
  stock_name?: string
  analysis_date?: string
  type: string
  format: string
  status: string
  model_info?: string
  research_depth?: number
  created_at: string
}

// 使用路由
const router = useRouter()

// 响应式数据
const loading = ref(false)
const searchKeyword = ref('')
const marketFilter = ref('')
const dateRange = ref<[string, string] | null>(null)
const selectedReports = ref<ReportListItem[]>([])
const currentPage = ref(1)
const pageSize = ref(20)
const totalReports = ref(0)

const reports = ref<ReportListItem[]>([])

// 计算属性
const filteredReports = computed<ReportListItem[]>(() => {
  // 现在数据直接从API获取，不需要前端筛选
  return reports.value
})

// API调用函数
const fetchReports = async () => {
  loading.value = true
  try {
    const params = new URLSearchParams({
      page: currentPage.value.toString(),
      page_size: pageSize.value.toString()
    })

    if (searchKeyword.value) {
      params.append('search_keyword', searchKeyword.value)
    }
    if (marketFilter.value) {
      params.append('market_filter', marketFilter.value)
    }
    if (dateRange.value) {
      params.append('start_date', dateRange.value[0])
      params.append('end_date', dateRange.value[1])
    }

    const result = await ApiClient.get<any>(`/api/reports/list?${params}`)

    if (result.success) {
      reports.value = Array.isArray(result.data?.reports) ? result.data.reports as ReportListItem[] : []
      totalReports.value = result.data.total
    } else {
      throw new Error(result.message || '获取报告列表失败')
    }
  } catch (error) {
    console.error('获取报告列表失败:', error)
    ElMessage.error('获取报告列表失败')
  } finally {
    loading.value = false
  }
}

// 方法
const handleSearch = () => {
  currentPage.value = 1
  fetchReports()
}

const handleDateChange = () => {
  currentPage.value = 1
  fetchReports()
}

const handleMarketChange = () => {
  currentPage.value = 1
  fetchReports()
}

const MAX_BATCH_EXPORT = 10
let isCorrectingSelection = false

const handleSelectionChange = (selection: ReportListItem[]) => {
  if (isCorrectingSelection) return
  if (selection.length > MAX_BATCH_EXPORT) {
    isCorrectingSelection = true
    const toKeep = selection.slice(0, MAX_BATCH_EXPORT)
    selectedReports.value = toKeep
    ElMessage.warning(`最多选择 ${MAX_BATCH_EXPORT} 个报告`)
    nextTick(() => {
      tableRef.value?.clearSelection()
      toKeep.forEach((row) => tableRef.value?.toggleRowSelection(row, true))
      isCorrectingSelection = false
    })
  } else {
    selectedReports.value = selection
  }
}

const isRowSelectable = (row: ReportListItem) => {
  if (selectedReports.value.length < MAX_BATCH_EXPORT) return true
  return selectedReports.value.some((r) => r.id === row.id)
}

const tableRef = ref<{
  clearSelection: () => void
  toggleRowSelection: (row: ReportListItem, selected?: boolean) => void
} | null>(null)

const viewReport = (report: ReportListItem) => {
  // 跳转到报告详情页面
  router.push(`/reports/view/${report.id}`)
}

const downloadReport = async (report: ReportListItem, format: string = 'markdown') => {
  try {
    // 显示加载提示
    const loadingMsg = ElMessage({
      message: `正在生成${getFormatName(format)}格式报告...`,
      type: 'info',
      duration: 0
    })

    const res: any = await ApiClient.get(`/api/reports/${report.id}/download`, { format }, { responseType: 'blob', showLoading: false })

    loadingMsg.close()

    // 兼容：响应拦截器直接返回 Blob；兼容返回 { data: Blob } 的旧实现
    const blob = res instanceof Blob ? res : (res?.data instanceof Blob ? res.data : new Blob([res]))
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url

    // 根据格式设置文件扩展名
    const ext = getFileExtension(format)
    // 清理股票名称中的特殊字符（用于文件名）
    const cleanStockName = (report.stock_name || '')
      .replace(/[/\\:*?"<>|]/g, '') // 移除文件名不允许的字符
      .replace(/\s+/g, '_') // 空格替换为下划线
      .trim()
    // 构建文件名：股票代码_股票名称_分析报告_日期
    const fileName = cleanStockName
      ? `${report.stock_code}_${cleanStockName}_分析报告_${report.analysis_date}.${ext}`
      : `${report.stock_code}_分析报告_${report.analysis_date}.${ext}`
    a.download = fileName

    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)

    ElMessage.success(`${getFormatName(format)}报告下载成功`)
  } catch (error: any) {
    console.error('下载报告失败:', error)

    // 显示详细错误信息
    if (error.message && error.message.includes('pandoc')) {
      ElMessage.error({
        message: 'Word 导出需要安装 pandoc 工具（PDF 导出不需要 pandoc）',
        duration: 5000
      })
    } else if (error.message && (error.message.includes('weasyprint') || error.message.includes('pdfkit'))) {
      ElMessage.error({
        message: 'PDF 导出需要安装 PDF 引擎：pip install weasyprint（推荐）',
        duration: 5000
      })
    } else {
      ElMessage.error(`下载报告失败: ${error.message || '未知错误'}`)
    }
  }
}

// 辅助函数：获取格式名称
const getFormatName = (format: string): string => {
  const names: Record<string, string> = {
    'markdown': 'Markdown',
    'docx': 'Word',
    'pdf': 'PDF',
    'json': 'JSON'
  }
  return names[format] || format
}

// 辅助函数：获取文件扩展名
const getFileExtension = (format: string): string => {
  const extensions: Record<string, string> = {
    'markdown': 'md',
    'docx': 'docx',
    'pdf': 'pdf',
    'json': 'json'
  }
  return extensions[format] || 'txt'
}

const deleteReport = async (report: ReportListItem) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除报告 "${report.title}" 吗？`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    // 调用删除API
    const result = await ApiClient.delete(`/api/reports/${report.id}`)

    if (result.success) {
      ElMessage.success('报告已删除')
      refreshReports()
    } else {
      throw new Error(result.message || '删除失败')
    }
  } catch (error: unknown) {
    if (!(error instanceof Error && error.message === 'cancel')) {
      console.error('删除报告失败:', error)
      ElMessage.error('删除报告失败')
    }
  }
}

const batchExporting = ref(false)

const exportSelected = async (format: string = 'markdown') => {
  const toExport = selectedReports.value
    .filter((r) => r.status === 'completed')
    .slice(0, MAX_BATCH_EXPORT)
  if (toExport.length === 0) {
    ElMessage.warning('请选择已完成的报告进行导出')
    return
  }
  batchExporting.value = true
  let successCount = 0
  try {
    for (let i = 0; i < toExport.length; i++) {
      const report = toExport[i]
      try {
        const res: any = await ApiClient.get(`/api/reports/${report.id}/download`, { format }, { responseType: 'blob', showLoading: false })
        // 兼容：响应拦截器直接返回 Blob；兼容返回 { data: Blob } 的旧实现
        const blob = res instanceof Blob ? res : (res?.data instanceof Blob ? res.data : new Blob([res]))
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        const ext = getFileExtension(format)
        const cleanStockName = (report.stock_name || '').replace(/[/\\:*?"<>|]/g, '').replace(/\s+/g, '_').trim()
        const fileName = cleanStockName
          ? `${report.stock_code}_${cleanStockName}_分析报告_${report.analysis_date}.${ext}`
          : `${report.stock_code}_分析报告_${report.analysis_date}.${ext}`
        a.download = fileName
        document.body.appendChild(a)
        a.click()
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)
        successCount++
        if (i < toExport.length - 1) { await new Promise(r => setTimeout(r, 300)) }
      } catch (e) {
        console.error(`导出 ${report.stock_code} 失败:`, e)
        ElMessage.error(`导出 ${report.stock_code} 失败`)
      }
    }
    ElMessage.success(`批量导出完成，成功 ${successCount}/${toExport.length} 个`)
  } finally {
    batchExporting.value = false
  }
}

const refreshReports = () => {
  fetchReports()
}

const getTypeColor = (type: string): ElTagType => {
  const colorMap: Record<string, ElTagType> = {
    single: 'primary',
    batch: 'success',
    portfolio: 'warning'
  }
  return colorMap[type] || 'info'
}

const getTypeText = (type: string) => {
  const textMap: Record<string, string> = {
    single: '单股分析',
    batch: '批量分析',
    portfolio: '投资组合'
  }
  return textMap[type] || type
}

const getStatusType = (status: string): ElTagType => {
  const statusMap: Record<string, ElTagType> = {
    completed: 'success',
    processing: 'warning',
    failed: 'danger'
  }
  return statusMap[status] || 'info'
}

const getStatusText = (status: string) => {
  const statusMap: Record<string, string> = {
    completed: '已完成',
    processing: '生成中',
    failed: '失败'
  }
  return statusMap[status] || status
}

import { formatDateTime } from '@/utils/datetime'

const formatTime = (time: string) => {
  return formatDateTime(time)
}

const handleSizeChange = (size: number) => {
  pageSize.value = size
  currentPage.value = 1
  fetchReports()
}

const handleCurrentChange = (page: number) => {
  currentPage.value = page
  fetchReports()
}

// 获取分析深度描述
const getResearchDepthDescription = (depth: number) => {
  const descMap: Record<number, string> = {
    1: '快速分析 - 基础技术面和基本面分析',
    2: '标准分析 - 包含技术面、基本面和市场情绪分析',
    3: '深度分析 - 全面的多维度分析，包含详细的行业和竞争分析',
    4: '专家级分析 - 最全面的分析，包含所有维度和深度研究',
    5: '顶级分析 - 最高级别的分析深度，包含所有可能的分析维度'
  }
  return descMap[depth] || `分析深度: ${depth}`
}

// 生命周期
onMounted(() => {
  fetchReports()
})
</script>

<style lang="scss" scoped>
.reports {
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

  .reports-list-card {
    .report-title {
      .report-subtitle {
        font-size: 12px;
        color: var(--el-text-color-placeholder);
        margin-top: 2px;
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
