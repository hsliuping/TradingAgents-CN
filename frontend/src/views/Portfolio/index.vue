<template>
  <div class="portfolio-page">
    <div class="header">
      <div class="title">
        <el-icon style="margin-right:8px"><PieChart /></el-icon>
        <span>持仓分析</span>
        <el-tag type="warning" size="small" style="margin-left: 8px;">专业版</el-tag>
      </div>
      <div class="actions">
        <el-button :icon="Refresh" text size="small" @click="refreshData">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="showAddDialog = true">添加持仓</el-button>
        <el-button type="success" :icon="DataAnalysis" @click="startAnalysis" :loading="analyzing">
          AI分析
        </el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">持仓总市值</div>
          <div class="stat-value">¥{{ formatNumber(stats?.total_value || 0) }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">持仓成本</div>
          <div class="stat-value">¥{{ formatNumber(stats?.total_cost || 0) }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">浮动盈亏</div>
          <div class="stat-value" :class="pnlClass(stats?.unrealized_pnl)">
            {{ formatPnl(stats?.unrealized_pnl) }}
            <span class="pnl-pct">({{ formatPct(stats?.unrealized_pnl_pct) }})</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">持仓数量</div>
          <div class="stat-value">{{ stats?.total_positions || 0 }} 只</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 主内容区 -->
    <el-row :gutter="16" class="main-content">
      <!-- 持仓列表 -->
      <el-col :span="16">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>持仓明细</span>
              <el-radio-group v-model="positionSource" size="small" @change="loadPositions">
                <el-radio-button value="all">全部</el-radio-button>
                <el-radio-button value="real">真实持仓</el-radio-button>
                <el-radio-button value="paper">模拟持仓</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          
          <el-table :data="positions" v-loading="loading" stripe>
            <el-table-column prop="code" label="代码" width="100" />
            <el-table-column prop="name" label="名称" width="120" />
            <el-table-column prop="quantity" label="数量" width="80" align="right" />
            <el-table-column label="成本价" width="100" align="right">
              <template #default="{ row }">{{ row.cost_price?.toFixed(2) }}</template>
            </el-table-column>
            <el-table-column label="现价" width="100" align="right">
              <template #default="{ row }">{{ row.current_price?.toFixed(2) || '-' }}</template>
            </el-table-column>
            <el-table-column label="市值" width="120" align="right">
              <template #default="{ row }">{{ formatNumber(row.market_value) }}</template>
            </el-table-column>
            <el-table-column label="盈亏" width="120" align="right">
              <template #default="{ row }">
                <span :class="pnlClass(row.unrealized_pnl)">
                  {{ formatPnl(row.unrealized_pnl) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="盈亏%" width="80" align="right">
              <template #default="{ row }">
                <span :class="pnlClass(row.unrealized_pnl_pct)">
                  {{ formatPct(row.unrealized_pnl_pct) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="来源" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.source === 'real' ? 'success' : 'info'" size="small">
                  {{ row.source === 'real' ? '真实' : '模拟' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160" fixed="right">
              <template #default="{ row }">
                <el-button link type="success" size="small" @click="analyzePosition(row)">分析</el-button>
                <el-button v-if="row.source === 'real'" link type="primary" size="small" @click="editPosition(row)">编辑</el-button>
                <el-button v-if="row.source === 'real'" link type="danger" size="small" @click="deletePosition(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <!-- 行业分布 -->
      <el-col :span="8">
        <el-card shadow="hover" class="industry-card">
          <template #header><span>行业分布</span></template>
          <div v-if="stats?.industry_distribution?.length" class="industry-list">
            <div v-for="item in stats.industry_distribution" :key="item.industry" class="industry-item">
              <div class="industry-name">{{ item.industry }}</div>
              <div class="industry-bar">
                <el-progress :percentage="item.percentage" :stroke-width="12" :show-text="false" />
              </div>
              <div class="industry-pct">{{ item.percentage.toFixed(1) }}%</div>
            </div>
          </div>
          <el-empty v-else description="暂无数据" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 添加持仓对话框 -->
    <AddPositionDialog 
      v-model:visible="showAddDialog" 
      :edit-data="editingPosition"
      @success="onPositionSaved" 
    />

    <!-- 分析结果对话框 -->
    <AnalysisResultDialog
      v-model:visible="showAnalysisDialog"
      :report="analysisReport"
    />

    <!-- 单股持仓分析对话框 -->
    <PositionAnalysisDialog
      v-model="showPositionAnalysisDialog"
      :position="selectedPosition"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Plus, DataAnalysis, PieChart } from '@element-plus/icons-vue'
import { portfolioApi, type PositionItem, type PortfolioStats, type PortfolioAnalysisReport } from '@/api/portfolio'
import AddPositionDialog from './components/AddPositionDialog.vue'
import AnalysisResultDialog from './components/AnalysisResultDialog.vue'
import PositionAnalysisDialog from './components/PositionAnalysisDialog.vue'

// 状态
const loading = ref(false)
const analyzing = ref(false)
const positions = ref<PositionItem[]>([])
const stats = ref<PortfolioStats | null>(null)
const positionSource = ref<'all' | 'real' | 'paper'>('all')
const showAddDialog = ref(false)
const showAnalysisDialog = ref(false)
const showPositionAnalysisDialog = ref(false)
const editingPosition = ref<PositionItem | null>(null)
const selectedPosition = ref<PositionItem | null>(null)
const analysisReport = ref<PortfolioAnalysisReport | null>(null)

// 格式化方法
const formatNumber = (val?: number) => {
  if (val === undefined || val === null) return '-'
  return val.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const formatPnl = (val?: number) => {
  if (val === undefined || val === null) return '-'
  const prefix = val >= 0 ? '+' : ''
  return prefix + formatNumber(val)
}

const formatPct = (val?: number) => {
  if (val === undefined || val === null) return '-'
  const prefix = val >= 0 ? '+' : ''
  return prefix + val.toFixed(2) + '%'
}

const pnlClass = (val?: number) => {
  if (val === undefined || val === null) return ''
  return val >= 0 ? 'profit' : 'loss'
}

// 数据加载
const loadPositions = async () => {
  loading.value = true
  try {
    const res = await portfolioApi.getPositions(positionSource.value)
    positions.value = res.data?.items || []
  } catch (e: any) {
    ElMessage.error(e.message || '加载持仓失败')
  } finally {
    loading.value = false
  }
}

const loadStats = async () => {
  try {
    const res = await portfolioApi.getStatistics()
    stats.value = res.data || null
  } catch (e: any) {
    console.error('加载统计失败:', e)
  }
}

const refreshData = () => {
  loadPositions()
  loadStats()
}

// 持仓操作
const editPosition = (row: PositionItem) => {
  editingPosition.value = row
  showAddDialog.value = true
}

const deletePosition = async (row: PositionItem) => {
  try {
    await ElMessageBox.confirm(`确定删除持仓 ${row.code} ${row.name || ''} ?`, '确认删除', { type: 'warning' })
    await portfolioApi.deletePosition(row.id)
    ElMessage.success('删除成功')
    refreshData()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.message || '删除失败')
    }
  }
}

const onPositionSaved = () => {
  showAddDialog.value = false
  editingPosition.value = null
  refreshData()
}

// AI分析（整体持仓）
const startAnalysis = async () => {
  if (!positions.value.length) {
    ElMessage.warning('请先添加持仓数据')
    return
  }

  analyzing.value = true
  try {
    const res = await portfolioApi.analyzePortfolio({ include_paper: positionSource.value !== 'real' })
    analysisReport.value = res.data || null
    showAnalysisDialog.value = true
    ElMessage.success('分析完成')
  } catch (e: any) {
    ElMessage.error(e.message || '分析失败')
  } finally {
    analyzing.value = false
  }
}

// 单股持仓分析
const analyzePosition = (row: PositionItem) => {
  selectedPosition.value = row
  showPositionAnalysisDialog.value = true
}

onMounted(() => {
  refreshData()
})
</script>

<style scoped>
.portfolio-page {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.title {
  display: flex;
  align-items: center;
  font-size: 20px;
  font-weight: 600;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  text-align: center;
  padding: 10px 0;
}

.stat-label {
  color: #909399;
  font-size: 14px;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.stat-value .pnl-pct {
  font-size: 14px;
  margin-left: 4px;
}

.profit {
  color: #67C23A;
}

.loss {
  color: #F56C6C;
}

.main-content {
  margin-top: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.industry-card {
  height: 100%;
}

.industry-list {
  max-height: 400px;
  overflow-y: auto;
}

.industry-item {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
}

.industry-name {
  width: 80px;
  font-size: 13px;
  color: #606266;
}

.industry-bar {
  flex: 1;
  margin: 0 12px;
}

.industry-pct {
  width: 50px;
  text-align: right;
  font-size: 13px;
  color: #909399;
}
</style>

