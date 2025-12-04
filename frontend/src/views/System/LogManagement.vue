<template>
  <div class="log-management">
    <el-card class="header-card">
      <template #header>
        <div class="card-header">
          <span>📋 日志管理</span>
          <div class="header-actions">
            <el-button type="primary" :icon="Refresh" @click="loadLogFiles" :loading="loading">
              刷新
            </el-button>
            <el-button type="success" :icon="Download" @click="showExportDialog">
              导出日志
            </el-button>
          </div>
        </div>
      </template>

      <!-- 统计信息 -->
      <el-row :gutter="20" class="statistics">
        <el-col :span="6">
          <el-statistic title="日志文件数" :value="statistics.total_files" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="总大小 (MB)" :value="statistics.total_size_mb" :precision="2" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="错误日志文件" :value="statistics.error_files" />
        </el-col>
        <el-col :span="6">
          <el-button type="primary" @click="loadStatistics">刷新统计</el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 日志文件列表 -->
    <el-card class="table-card">
      <template #header>
        <div class="card-header">
          <span>日志文件列表</span>
          <el-input
            v-model="searchKeyword"
            placeholder="搜索文件名"
            :prefix-icon="Search"
            style="width: 300px"
            clearable
          />
        </div>
      </template>

      <el-table
        :data="filteredLogFiles"
        v-loading="loading"
        stripe
        style="width: 100%"
      >
        <el-table-column prop="name" label="文件名" min-width="200">
          <template #default="{ row }">
            <el-tag :type="getLogTypeColor(row.type)" size="small">
              {{ row.type }}
            </el-tag>
            {{ row.name }}
          </template>
        </el-table-column>
        <el-table-column prop="size_mb" label="大小 (MB)" width="120" sortable>
          <template #default="{ row }">
            {{ row.size_mb.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="modified_at" label="修改时间" width="180" sortable>
          <template #default="{ row }">
            {{ formatDate(row.modified_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" :icon="View" @click="viewLog(row)">
              查看
            </el-button>
            <el-button type="success" size="small" :icon="Download" @click="downloadLog(row)">
              下载
            </el-button>
            <el-popconfirm
              title="确定要删除这个日志文件吗？"
              @confirm="deleteLog(row)"
            >
              <template #reference>
                <el-button type="danger" size="small" :icon="Delete">
                  删除
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 查看日志对话框 -->
    <el-dialog
      v-model="viewDialogVisible"
      title="查看日志"
      width="80%"
      :close-on-click-modal="false"
    >
      <div class="log-viewer">
        <!-- 过滤选项 -->
        <el-form :inline="true" class="filter-form">
          <el-form-item label="日志级别">
            <el-select v-model="viewFilter.level" placeholder="全部" clearable style="width: 120px">
              <el-option label="ERROR" value="ERROR" />
              <el-option label="WARNING" value="WARNING" />
              <el-option label="INFO" value="INFO" />
              <el-option label="DEBUG" value="DEBUG" />
            </el-select>
          </el-form-item>
          <el-form-item label="关键词">
            <el-input v-model="viewFilter.keyword" placeholder="搜索关键词" clearable style="width: 200px" />
          </el-form-item>
          <el-form-item label="行数">
            <el-input-number v-model="viewFilter.lines" :min="100" :max="10000" :step="100" style="width: 150px" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="loadLogContent" :loading="viewLoading">
              应用过滤
            </el-button>
          </el-form-item>
        </el-form>

        <!-- 统计信息 -->
        <el-descriptions v-if="logContent" :column="4" border size="small" class="log-stats">
          <el-descriptions-item label="总行数">{{ logContent.stats.total_lines }}</el-descriptions-item>
          <el-descriptions-item label="过滤后">{{ logContent.stats.filtered_lines }}</el-descriptions-item>
          <el-descriptions-item label="ERROR">
            <el-tag type="danger" size="small">{{ logContent.stats.error_count }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="WARNING">
            <el-tag type="warning" size="small">{{ logContent.stats.warning_count }}</el-tag>
          </el-descriptions-item>
        </el-descriptions>

        <!-- 日志内容 -->
        <div class="log-content" v-loading="viewLoading">
          <pre v-if="logContent">{{ logContent.lines.join('\n') }}</pre>
          <el-empty v-else description="暂无日志内容" />
        </div>
      </div>
    </el-dialog>

    <!-- 导出对话框 -->
    <el-dialog
      v-model="exportDialogVisible"
      title="导出日志"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form :model="exportForm" label-width="100px">
        <el-form-item label="选择文件">
          <el-select
            v-model="exportForm.filenames"
            multiple
            placeholder="留空表示导出全部"
            style="width: 100%"
          >
            <el-option
              v-for="file in logFiles"
              :key="file.name"
              :label="file.name"
              :value="file.name"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="日志级别">
          <el-select v-model="exportForm.level" placeholder="全部" clearable>
            <el-option label="ERROR" value="ERROR" />
            <el-option label="WARNING" value="WARNING" />
            <el-option label="INFO" value="INFO" />
            <el-option label="DEBUG" value="DEBUG" />
          </el-select>
        </el-form-item>
        <el-form-item label="导出格式">
          <el-radio-group v-model="exportForm.format">
            <el-radio label="zip">ZIP 压缩包</el-radio>
            <el-radio label="txt">合并文本文件</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="exportDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="exportLogs" :loading="exportLoading">
          导出
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Download, Search, View, Delete } from '@element-plus/icons-vue'
import { LogsApi, type LogFileInfo, type LogContentResponse, type LogStatistics } from '@/api/logs'

// 数据
const loading = ref(false)
const viewLoading = ref(false)
const exportLoading = ref(false)
const logFiles = ref<LogFileInfo[]>([])
const searchKeyword = ref('')
const statistics = ref<LogStatistics>({
  total_files: 0,
  total_size_mb: 0,
  error_files: 0,
  recent_errors: [],
  log_types: {}
})

// 查看日志
const viewDialogVisible = ref(false)
const currentLogFile = ref<LogFileInfo | null>(null)
const logContent = ref<LogContentResponse | null>(null)
const viewFilter = ref({
  level: undefined as string | undefined,
  keyword: '',
  lines: 1000
})

// 导出日志
const exportDialogVisible = ref(false)
const exportForm = ref({
  filenames: [] as string[],
  level: undefined as string | undefined,
  format: 'zip' as 'zip' | 'txt'
})

// 计算属性
const filteredLogFiles = computed(() => {
  if (!searchKeyword.value) return logFiles.value
  return logFiles.value.filter(file =>
    file.name.toLowerCase().includes(searchKeyword.value.toLowerCase())
  )
})

// 方法
const loadLogFiles = async () => {
  loading.value = true
  try {
    logFiles.value = await LogsApi.listLogFiles()
    ElMessage.success('日志文件列表加载成功')
  } catch (error: any) {
    ElMessage.error(`加载失败: ${error.message || error}`)
  } finally {
    loading.value = false
  }
}

const loadStatistics = async () => {
  try {
    statistics.value = await LogsApi.getStatistics(7)
  } catch (error: any) {
    ElMessage.error(`加载统计失败: ${error.message || error}`)
  }
}

const viewLog = async (file: LogFileInfo) => {
  currentLogFile.value = file
  viewDialogVisible.value = true
  await loadLogContent()
}

const loadLogContent = async () => {
  if (!currentLogFile.value) return
  
  viewLoading.value = true
  try {
    logContent.value = await LogsApi.readLogFile({
      filename: currentLogFile.value.name,
      lines: viewFilter.value.lines,
      level: viewFilter.value.level as any,
      keyword: viewFilter.value.keyword || undefined
    })
  } catch (error: any) {
    ElMessage.error(`加载日志内容失败: ${error.message || error}`)
  } finally {
    viewLoading.value = false
  }
}

const downloadLog = async (file: LogFileInfo) => {
  try {
    const blob = await LogsApi.exportLogs({
      filenames: [file.name],
      format: 'zip'
    })
    
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${file.name}.zip`
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
    
    ElMessage.success('日志下载成功')
  } catch (error: any) {
    ElMessage.error(`下载失败: ${error.message || error}`)
  }
}

const deleteLog = async (file: LogFileInfo) => {
  try {
    await LogsApi.deleteLogFile(file.name)
    ElMessage.success('日志文件已删除')
    await loadLogFiles()
  } catch (error: any) {
    ElMessage.error(`删除失败: ${error.message || error}`)
  }
}

const showExportDialog = () => {
  exportForm.value = {
    filenames: [],
    level: undefined,
    format: 'zip'
  }
  exportDialogVisible.value = true
}

const exportLogs = async () => {
  exportLoading.value = true
  try {
    const blob = await LogsApi.exportLogs({
      filenames: exportForm.value.filenames.length > 0 ? exportForm.value.filenames : undefined,
      level: exportForm.value.level as any,
      format: exportForm.value.format
    })
    
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5)
    a.download = `logs_export_${timestamp}.${exportForm.value.format}`
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
    
    ElMessage.success('日志导出成功')
    exportDialogVisible.value = false
  } catch (error: any) {
    ElMessage.error(`导出失败: ${error.message || error}`)
  } finally {
    exportLoading.value = false
  }
}

const getLogTypeColor = (type: string) => {
  const colors: Record<string, string> = {
    error: 'danger',
    webapi: 'primary',
    worker: 'success',
    access: 'info',
    other: ''
  }
  return colors[type] || ''
}

const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleString('zh-CN')
}

// 生命周期
onMounted(() => {
  loadLogFiles()
  loadStatistics()
})
</script>

<style scoped lang="scss">
.log-management {
  padding: 20px;

  .header-card {
    margin-bottom: 20px;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .header-actions {
      display: flex;
      gap: 10px;
    }
  }

  .statistics {
    margin-top: 20px;
  }

  .table-card {
    margin-top: 20px;
  }

  .log-viewer {
    .filter-form {
      margin-bottom: 20px;
      padding: 15px;
      background-color: #f5f7fa;
      border-radius: 4px;
    }

    .log-stats {
      margin-bottom: 15px;
    }

    .log-content {
      max-height: 500px;
      overflow-y: auto;
      background-color: #1e1e1e;
      color: #d4d4d4;
      padding: 15px;
      border-radius: 4px;
      font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
      font-size: 12px;
      line-height: 1.5;

      pre {
        margin: 0;
        white-space: pre-wrap;
        word-wrap: break-word;
      }
    }
  }
}
</style>

