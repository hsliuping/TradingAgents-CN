<template>
  <div class="task-center">
    <div class="page-header">
      <h1 class="page-title">
        <el-icon><List /></el-icon>
        任务中心
      </h1>
      <p class="page-description">统一查看并管理分析任务：进行中 / 已完成 / 失败</p>
    </div>

    <el-card class="tabs-card" shadow="never">
      <el-tabs v-model="activeTab" @tab-click="onTabChange">
        <el-tab-pane label="进行中" name="running" />
        <el-tab-pane label="已完成" name="completed" />
        <el-tab-pane label="失败" name="failed" />
        <el-tab-pane label="全部" name="all" />
      </el-tabs>
    </el-card>

    <!-- 筛选表单 -->
    <el-card class="filter-card" shadow="never">
      <el-form :inline="true" @submit.prevent>
        <el-form-item label="时间范围">
          <el-date-picker v-model="filters.dateRange" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" format="YYYY-MM-DD" value-format="YYYY-MM-DD" style="width: 260px" />
        </el-form-item>
        <el-form-item label="市场">
          <el-select v-model="filters.market" clearable placeholder="全部" style="width: 120px">
            <el-option label="全部" value="" />
            <el-option label="美股" value="美股" />
            <el-option label="A股" value="A股" />
            <el-option label="港股" value="港股" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" clearable placeholder="全部" style="width: 120px">
            <el-option label="全部" value="" />
            <el-option label="进行中" value="processing" />
            <el-option label="已完成" value="completed" />
            <el-option label="失败" value="failed" />
          </el-select>
        </el-form-item>
        <el-form-item label="股票">
          <el-input v-model="filters.stock" placeholder="代码或名称" style="width: 160px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="applyFilters" :loading="loading">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 统计卡片 -->
    <el-row :gutter="16" style="margin-top: 12px">
      <el-col :span="6">
        <el-card shadow="never"><div class="stat"><div class="value">{{ stats.total }}</div><div class="label">总任务</div></div></el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never"><div class="stat"><div class="value">{{ stats.completed }}</div><div class="label">已完成</div></div></el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never"><div class="stat"><div class="value">{{ stats.failed }}</div><div class="label">失败</div></div></el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never"><div class="stat"><div class="value">{{ stats.uniqueStocks }}</div><div class="label">股票数</div></div></el-card>
      </el-col>
    </el-row>


    <el-card class="list-card" shadow="never">
      <div class="list-header">
        <div class="left">
          <el-input v-model="keyword" placeholder="搜索股票代码/名称" clearable style="width: 220px" />
          <el-button @click="refreshList" :loading="loading">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
        <div class="right">
          <el-button @click="exportSelected" :disabled="selectedRows.length===0">
            <el-icon><Download /></el-icon>
            导出所选
          </el-button>
        </div>
      </div>

      <el-table :data="filteredList" v-loading="loading" style="width: 100%" @selection-change="onSelectionChange">
        <el-table-column type="selection" width="50" />
        <el-table-column prop="task_id" label="任务ID" width="220" />
        <el-table-column prop="stock_code" label="股票代码" width="120" />
        <el-table-column prop="stock_name" label="股票名称" width="150" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ getStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度" width="120">
          <template #default="{ row }">
            <el-progress :percentage="row.progress || 0" :status="row.status==='failed'?'exception':(row.status==='completed'?'success':undefined)"/>
          </template>
        </el-table-column>
        <el-table-column prop="start_time" label="开始时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.start_time || row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="350" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status==='completed'" type="text" size="small" @click="openResult(row)">查看结果</el-button>
            <el-button v-if="row.status==='completed'" type="text" size="small" @click="openReport(row)">报告详情</el-button>
            <el-button v-if="row.status==='failed'" type="text" size="small" @click="showErrorDetail(row)">查看错误</el-button>
            <el-button v-if="row.status==='failed'" type="text" size="small" @click="retryTask(row)">重试</el-button>
            <el-button v-if="row.status==='processing' || row.status==='running' || row.status==='pending'" type="text" size="small" @click="markAsFailed(row)">标记失败</el-button>
            <el-button type="text" size="small" @click="deleteTask(row)" style="color: #f56c6c;">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <!-- 结果弹窗组件化 -->
    <TaskResultDialog
      v-model="resultVisible"
      :result="currentResult"
      @close="resultVisible=false"
      @view-report="openReport(currentRow)"
    />


    <!-- 报告详情弹窗组件化（预留） -->
    <TaskReportDialog v-model="reportVisible" :sections="reportSections" @close="reportVisible=false" />

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { List, Refresh, Download } from '@element-plus/icons-vue'
import { analysisApi } from '@/api/analysis'
import TaskResultDialog from '@/components/Global/TaskResultDialog.vue'
import TaskReportDialog from '@/components/Global/TaskReportDialog.vue'

const router = useRouter()
const route = useRoute()

const activeTab = ref<'running'|'completed'|'failed'|'all'>('running')
const loading = ref(false)
const keyword = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const list = ref<any[]>([])
const selectedRows = ref<any[]>([])
// 筛选与统计
const filters = ref<{ dateRange: string[]; market: string; status: string; stock: string }>({
  dateRange: [], market: '', status: '', stock: ''
})
const stats = ref({ total: 0, completed: 0, failed: 0, uniqueStocks: 0 })


// WebSocket 连接管理
let wsConnections: Map<string, WebSocket> = new Map()
let timer: any = null

const setupPolling = () => {
  clearInterval(timer)
  // 定期刷新列表（每 5 秒）
  if (activeTab.value === 'running') {
    timer = setInterval(() => loadList(), 5000)
  }
}

// 连接 WebSocket 获取任务进度
const connectTaskWebSocket = (taskId: string) => {
  if (wsConnections.has(taskId)) {
    return // 已连接
  }

  try {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${wsProtocol}//${host}/api/ws/task/${taskId}`

    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      console.log(`✅ WebSocket 连接成功: ${taskId}`)
    }

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        if (message.type === 'progress_update') {
          // 更新列表中的任务进度
          const taskIndex = list.value.findIndex(t => t.task_id === taskId)
          if (taskIndex >= 0) {
            list.value[taskIndex].progress = message.progress
            list.value[taskIndex].status = message.status
            list.value[taskIndex].message = message.message
            console.log(`📊 更新任务进度: ${taskId} -> ${message.progress}%`)
          }
        }
      } catch (e) {
        console.error('WebSocket 消息解析失败:', e)
      }
    }

    ws.onerror = (error) => {
      console.error(`❌ WebSocket 错误: ${taskId}`, error)
    }

    ws.onclose = () => {
      console.log(`🔌 WebSocket 断开: ${taskId}`)
      wsConnections.delete(taskId)
    }

    wsConnections.set(taskId, ws)
  } catch (e) {
    console.error('WebSocket 连接失败:', e)
  }
}

// 断开所有 WebSocket 连接
const disconnectAllWebSockets = () => {
  wsConnections.forEach((ws) => {
    try {
      ws.close()
    } catch (e) {
      console.error('关闭 WebSocket 失败:', e)
    }
  })
  wsConnections.clear()
}

const statusParam = computed(() => {
  if (activeTab.value === 'all') return undefined
  if (activeTab.value === 'running') return 'processing'
  return activeTab.value
})

const loadList = async () => {
  loading.value = true
  try {
    // 根据筛选与标签页构造参数
    const params: any = {
      page: currentPage.value,
      page_size: pageSize.value,
      status: filters.value.status || statusParam.value,
      stock_code: filters.value.stock || undefined
    }
    if (filters.value.market) params.market_type = filters.value.market
    if (filters.value.dateRange && filters.value.dateRange.length === 2) {
      params.start_date = filters.value.dateRange[0]
      params.end_date = filters.value.dateRange[1]
    }

    const res = await analysisApi.getHistory(params)
    const body = (res as any)?.data?.data || (res as any)?.data || {}
    let tasks = body.tasks || body.analyses || []

    // 当无筛选条件且历史接口为空时，兜底用任务列表接口（保证能看到数据）
    const noExtraFilters = !filters.value.market && !filters.value.stock && (!filters.value.dateRange || filters.value.dateRange.length === 0)
    if (tasks.length === 0 && noExtraFilters) {
      try {
        const res2 = await analysisApi.getTaskList({
          status: statusParam.value,
          limit: pageSize.value,
          offset: (currentPage.value - 1) * pageSize.value
        })
        const body2 = (res2 as any)?.data?.data || {}
        tasks = body2.tasks || []
        total.value = body2.total ?? tasks.length
      } catch {}
    } else {
      total.value = body.total ?? tasks.length
    }

    list.value = tasks

    // 为运行中的任务连接 WebSocket
    tasks.forEach((task: any) => {
      if (task.status === 'processing' || task.status === 'running' || task.status === 'pending') {
        connectTaskWebSocket(task.task_id)
      }
    })

    // 统计
    const completed = tasks.filter((x:any) => x.status === 'completed').length
    const failed = tasks.filter((x:any) => x.status === 'failed').length
    const uniqueStocks = new Set(tasks.map((x:any) => x.stock_code || x.stock_symbol)).size
    stats.value = { total: tasks.length, completed, failed, uniqueStocks }
  } catch (e:any) {
    ElMessage.error(e?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

// 查询/重置
const applyFilters = () => { currentPage.value = 1; loadList() }
const resetFilters = () => { filters.value = { dateRange: [], market: '', status: '', stock: '' }; currentPage.value = 1; loadList() }

// 报告弹窗状态
const reportVisible = ref(false)
const reportSections = ref<Array<{ key?: string; title: string; content: any }>>([])

const filteredList = computed(() => {
  let arr = list.value
  if (keyword.value) {
    const k = keyword.value.toLowerCase()
    arr = arr.filter((x:any) => (x.stock_code||'').toLowerCase().includes(k) || (x.stock_name||'').toLowerCase().includes(k) || (x.task_id||'').toLowerCase().includes(k))
  }
  return arr
})

const handleSizeChange = (size:number) => { pageSize.value = size; currentPage.value = 1; loadList() }
const handleCurrentChange = (page:number) => { currentPage.value = page; loadList() }
const onTabChange = () => {
  // 使用 nextTick 确保 activeTab 的值已经更新
  nextTick(() => {
    currentPage.value = 1
    loadList()
    setupPolling()
  })
}
const refreshList = () => loadList()
const onSelectionChange = (rows:any[]) => { selectedRows.value = rows }

// 结果与报告
const resultVisible = ref(false)
const currentResult = ref<any>(null)
const currentRow = ref<any>(null)

const openResult = async (row:any) => {
  currentRow.value = row
  try {
    const res = await analysisApi.getTaskResult(row.task_id)
    const body = (res as any)?.data?.data || {}
    currentResult.value = body
    resultVisible.value = true
  } catch (e:any) {
    ElMessage.error('获取结果失败')
  }
}

const openReport = (row:any): void => {
  const id = row?.task_id || row?.analysis_id || row?.id
  if (!id) {
    ElMessage.warning('未找到报告ID')
    return
  }
  void router.push({ name: 'ReportDetail', params: { id } })
}

const retryTask = (_row:any) => { ElMessage.info('重试功能待实现') }

// 显示错误详情
const showErrorDetail = async (row: any) => {
  try {
    const taskId = row.task_id || row.analysis_id || row.id
    if (!taskId) {
      ElMessage.error('任务ID不存在')
      return
    }

    // 获取任务详情
    const res = await analysisApi.getTaskStatus(taskId)
    const task = (res as any)?.data?.data || row

    const errorMessage = task.error_message || task.message || '未知错误'

    // 使用 ElMessageBox 显示错误详情
    await ElMessageBox.alert(
      errorMessage,
      '错误详情',
      {
        confirmButtonText: '确定',
        type: 'error',
        dangerouslyUseHTMLString: true,
        customStyle: {
          width: '600px'
        },
        // 使用 HTML 格式化显示，保留换行
        message: errorMessage.replace(/\n/g, '<br>')
      }
    )
  } catch (e: any) {
    if (e !== 'cancel' && e !== 'close') {
      ElMessage.error(e?.message || '获取错误详情失败')
    }
  }
}

// 标记任务为失败
const markAsFailed = async (row: any) => {
  try {
    await ElMessageBox.confirm(
      `确定要将任务 "${row.stock_name || row.stock_code}" 标记为失败吗？`,
      '确认操作',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    const taskId = row.task_id || row.analysis_id || row.id
    if (!taskId) {
      ElMessage.error('任务ID不存在')
      return
    }

    loading.value = true
    await analysisApi.markTaskAsFailed(taskId)
    ElMessage.success('任务已标记为失败')
    await loadList()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.message || '标记失败')
    }
  } finally {
    loading.value = false
  }
}

// 删除任务
const deleteTask = async (row: any) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除任务 "${row.stock_name || row.stock_code}" 吗？此操作不可恢复！`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'error'
      }
    )

    const taskId = row.task_id || row.analysis_id || row.id
    if (!taskId) {
      ElMessage.error('任务ID不存在')
      return
    }

    loading.value = true
    await analysisApi.deleteTask(taskId)
    ElMessage.success('任务已删除')
    await loadList()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.message || '删除失败')
    }
  } finally {
    loading.value = false
  }
}

// 导出所选任务
const exportSelected = () => {
  try {
    const data = JSON.stringify(selectedRows.value, null, 2)
    const blob = new Blob([data], { type: 'application/json;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `tasks_selected_${Date.now()}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch {
    ElMessage.error('导出失败')
  }
}

onMounted(() => {
  // 根据路由 query 初始化标签页
  const tab = String((route.query as any)?.tab || '').toLowerCase()
  const validTabs = ['running', 'completed', 'failed', 'all']
  if (validTabs.includes(tab)) {
    activeTab.value = tab as any
  }
  loadList(); setupPolling()
})

// 监听路由 query 的 tab 变化，动态切换标签页
watch(() => (route.query as any)?.tab, (newVal) => {
  const tab = String(newVal || '').toLowerCase()
  const validTabs = ['running', 'completed', 'failed', 'all']
  if (validTabs.includes(tab)) {
    activeTab.value = tab as any
    currentPage.value = 1
    loadList()
    setupPolling()
  }
})
onUnmounted(() => {
  clearInterval(timer)
  disconnectAllWebSockets()
})

const getStatusType = (status:string): 'success' | 'info' | 'warning' | 'danger' => {
  const map: Record<string,'success'|'info'|'warning'|'danger'> = {
    pending: 'info', processing: 'warning', completed: 'success', failed: 'danger', cancelled: 'info'
  }
  return map[status] || 'info'
}
import { formatDateTime } from '@/utils/datetime'

const getStatusText = (status:string) => ({ pending:'等待中', processing:'处理中', completed:'已完成', failed:'失败', cancelled:'已取消' } as any)[status] || status
const formatTime = (t:string) => t ? formatDateTime(t) : '-'
</script>

<style scoped lang="scss">
.task-center {
  .page-header { margin-bottom: 24px; }
  .page-title { display:flex; align-items:center; gap:8px; font-size:24px; font-weight:600; margin:0 0 8px 0; }
  .page-description { color: var(--el-text-color-regular); margin:0; }
  .tabs-card { margin-bottom: 16px; }
  .list-header { display:flex; justify-content: space-between; align-items: center; margin-bottom: 12px; gap:8px; }
  .pagination-wrapper { display:flex; justify-content:center; margin-top: 16px; }
}
</style>

