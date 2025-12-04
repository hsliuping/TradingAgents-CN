<template>
  <div class="usage-statistics-container">
    <el-card class="header-card">
      <template #header>
        <div class="card-header">
          <span class="title">
            <el-icon><DataAnalysis /></el-icon>
            使用统计与计费
          </span>
          <div class="header-actions">
            <el-select v-model="selectedDays" @change="loadData" style="width: 120px; margin-right: 10px;">
              <el-option label="最近7天" :value="7" />
              <el-option label="最近30天" :value="30" />
              <el-option label="最近90天" :value="90" />
            </el-select>
            <el-button type="primary" :icon="Refresh" @click="loadData">刷新</el-button>
          </div>
        </div>
      </template>

      <!-- 统计概览 -->
      <el-row :gutter="20" class="stats-overview">
        <el-col :span="6">
          <el-statistic title="总请求数" :value="statistics.total_requests">
            <template #prefix>
              <el-icon><Document /></el-icon>
            </template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <el-statistic title="总输入 Token" :value="statistics.total_input_tokens">
            <template #prefix>
              <el-icon><Upload /></el-icon>
            </template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <el-statistic title="总输出 Token" :value="statistics.total_output_tokens">
            <template #prefix>
              <el-icon><Download /></el-icon>
            </template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <div class="cost-statistic">
            <div class="cost-label">
              <el-icon><Money /></el-icon>
              <span>总成本</span>
            </div>
            <div class="cost-values">
              <div v-for="(cost, currency) in statistics.cost_by_currency" :key="currency" class="cost-item">
                <span class="cost-amount">{{ cost.toFixed(4) }}</span>
                <span class="cost-currency">{{ getCurrencySymbol(currency) }}</span>
              </div>
              <div v-if="Object.keys(statistics.cost_by_currency || {}).length === 0" class="cost-item">
                <span class="cost-amount">0.0000</span>
                <span class="cost-currency">元</span>
              </div>
            </div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 图表区域 -->
    <el-row :gutter="20" style="margin-top: 20px;">
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>按供应商统计</span>
          </template>
          <div ref="providerChartRef" style="height: 300px;"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>按模型统计</span>
          </template>
          <div ref="modelChartRef" style="height: 300px;"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px;">
      <el-col :span="24">
        <el-card>
          <template #header>
            <span>每日成本趋势</span>
          </template>
          <div ref="dailyChartRef" style="height: 300px;"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 使用记录表格 -->
    <el-card style="margin-top: 20px;">
      <template #header>
        <div class="card-header">
          <span>使用记录</span>
          <el-button type="danger" size="small" @click="handleDeleteOldRecords">
            清理旧记录
          </el-button>
        </div>
      </template>

      <el-table :data="records" style="width: 100%" v-loading="loading">
        <el-table-column prop="timestamp" label="时间" width="180">
          <template #default="{ row }">
            {{ formatTimestamp(row.timestamp) }}
          </template>
        </el-table-column>
        <el-table-column prop="provider" label="供应商" width="120" />
        <el-table-column prop="model_name" label="模型" width="180" />
        <el-table-column prop="input_tokens" label="输入 Token" width="120" align="right" />
        <el-table-column prop="output_tokens" label="输出 Token" width="120" align="right" />
        <el-table-column prop="cost" label="成本" width="140" align="right">
          <template #default="{ row }">
            {{ row.cost.toFixed(4) }} {{ getCurrencySymbol(row.currency || 'CNY') }}
          </template>
        </el-table-column>
        <el-table-column prop="analysis_type" label="分析类型" width="150" />
        <el-table-column prop="session_id" label="会话ID" show-overflow-tooltip />
      </el-table>

      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="totalRecords"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadRecords"
        @current-change="loadRecords"
        style="margin-top: 20px; justify-content: center;"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { DataAnalysis, Refresh, Document, Upload, Download, Money } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import {
  getUsageRecords,
  getUsageStatistics,
  deleteOldRecords,
  type UsageRecord,
  type UsageStatistics
} from '@/api/usage'

// 数据
const selectedDays = ref(7)
const loading = ref(false)
const statistics = ref<UsageStatistics>({
  total_requests: 0,
  total_input_tokens: 0,
  total_output_tokens: 0,
  total_cost: 0,
  cost_by_currency: {},
  by_provider: {},
  by_model: {},
  by_date: {}
})
const records = ref<UsageRecord[]>([])
const currentPage = ref(1)
const pageSize = ref(20)
const totalRecords = ref(0)

// 图表引用
const providerChartRef = ref<HTMLElement>()
const modelChartRef = ref<HTMLElement>()
const dailyChartRef = ref<HTMLElement>()

// 图表实例
let providerChart: echarts.ECharts | null = null
let modelChart: echarts.ECharts | null = null
let dailyChart: echarts.ECharts | null = null

// 格式化时间戳
const formatTimestamp = (timestamp: string) => {
  return new Date(timestamp).toLocaleString('zh-CN')
}

// 获取货币符号
const getCurrencySymbol = (currency: string) => {
  const symbols: Record<string, string> = {
    'CNY': '元',
    'USD': '$',
    'EUR': '€',
    'GBP': '£',
    'JPY': '¥'
  }
  return symbols[currency] || currency
}

// 加载统计数据
const loadStatistics = async () => {
  try {
    const res = await getUsageStatistics({ days: selectedDays.value })
    if (res.success) {
      statistics.value = res.data
      await nextTick()
      renderCharts()
    }
  } catch (error) {
    console.error('加载统计数据失败:', error)
    ElMessage.error('加载统计数据失败')
  }
}

// 加载使用记录
const loadRecords = async () => {
  try {
    loading.value = true
    const res = await getUsageRecords({
      limit: pageSize.value
    })
    if (res.success) {
      records.value = res.data.records
      totalRecords.value = res.data.total
    }
  } catch (error) {
    console.error('加载使用记录失败:', error)
    ElMessage.error('加载使用记录失败')
  } finally {
    loading.value = false
  }
}

// 加载所有数据
const loadData = async () => {
  await Promise.all([loadStatistics(), loadRecords()])
}

// 渲染图表
const renderCharts = () => {
  renderProviderChart()
  renderModelChart()
  renderDailyChart()
}

// 渲染供应商图表
const renderProviderChart = () => {
  if (!providerChartRef.value) return

  if (!providerChart) {
    providerChart = echarts.init(providerChartRef.value)
  }

  const data = Object.entries(statistics.value.by_provider).map(([name, value]: [string, any]) => ({
    name,
    value: value.cost
  }))

  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: ¥{c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      left: 'left'
    },
    series: [
      {
        name: '成本',
        type: 'pie',
        radius: '50%',
        data,
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }
    ]
  }

  providerChart.setOption(option)
}

// 渲染模型图表
const renderModelChart = () => {
  if (!modelChartRef.value) return

  if (!modelChart) {
    modelChart = echarts.init(modelChartRef.value)
  }

  const data = Object.entries(statistics.value.by_model)
    .map(([name, value]: [string, any]) => ({
      name,
      value: value.cost
    }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 10) // 只显示前10个

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      }
    },
    xAxis: {
      type: 'category',
      data: data.map(item => item.name),
      axisLabel: {
        rotate: 45,
        interval: 0
      }
    },
    yAxis: {
      type: 'value',
      name: '成本(元)'
    },
    series: [
      {
        data: data.map(item => item.value),
        type: 'bar',
        itemStyle: {
          color: '#409EFF'
        }
      }
    ]
  }

  modelChart.setOption(option)
}

// 渲染每日成本图表
const renderDailyChart = () => {
  if (!dailyChartRef.value) return

  if (!dailyChart) {
    dailyChart = echarts.init(dailyChartRef.value)
  }

  const sortedData = Object.entries(statistics.value.by_date)
    .sort(([a], [b]) => a.localeCompare(b))

  const option = {
    tooltip: {
      trigger: 'axis'
    },
    xAxis: {
      type: 'category',
      data: sortedData.map(([date]) => date)
    },
    yAxis: {
      type: 'value',
      name: '成本(元)'
    },
    series: [
      {
        data: sortedData.map(([, value]: [string, any]) => value.cost),
        type: 'line',
        smooth: true,
        itemStyle: {
          color: '#67C23A'
        },
        areaStyle: {
          color: 'rgba(103, 194, 58, 0.2)'
        }
      }
    ]
  }

  dailyChart.setOption(option)
}

// 删除旧记录
const handleDeleteOldRecords = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要删除90天前的旧记录吗？此操作不可恢复。',
      '警告',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    const res = await deleteOldRecords(90)
    if (res.data?.success) {
      ElMessage.success(`已删除 ${res.data.deleted_count} 条旧记录`)
      loadData()
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('删除旧记录失败:', error)
      ElMessage.error('删除旧记录失败')
    }
  }
}

// 组件挂载
onMounted(() => {
  loadData()
})
</script>

<style scoped lang="scss">
.usage-statistics-container {
  padding: 20px;
}

.header-card {
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 16px;
      font-weight: 600;
    }

    .header-actions {
      display: flex;
      align-items: center;
    }
  }
}

.cost-statistic {
  padding: 20px;

  .cost-label {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #909399;
    font-size: 14px;
    margin-bottom: 12px;
  }

  .cost-values {
    display: flex;
    flex-direction: column;
    gap: 8px;

    .cost-item {
      display: flex;
      align-items: baseline;
      gap: 4px;

      .cost-amount {
        font-size: 24px;
        font-weight: 600;
        color: #303133;
      }

      .cost-currency {
        font-size: 14px;
        color: #909399;
      }
    }
  }
}

.stats-overview {
  margin-top: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>

