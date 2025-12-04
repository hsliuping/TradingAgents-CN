<template>
  <div class="trade-review">
    <!-- 页面头部 -->
    <div class="header">
      <div class="title">
        <el-icon style="margin-right:8px"><TrendCharts /></el-icon>
        <span>操作复盘</span>
      </div>
      <div class="actions">
        <el-button :icon="Refresh" text size="small" @click="refreshData">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="showNewReviewDialog = true">发起复盘</el-button>
      </div>
    </div>

    <!-- 交易统计卡片 -->
    <el-row :gutter="16" class="stats-row" v-loading="loading.stats">
      <el-col :span="4">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">总交易数</div>
          <div class="stat-value">{{ statistics.total_trades }}</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">胜率</div>
          <div class="stat-value" :class="statistics.win_rate >= 50 ? 'positive' : 'negative'">
            {{ statistics.win_rate?.toFixed(1) || 0 }}%
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">盈亏比</div>
          <div class="stat-value">{{ statistics.profit_loss_ratio?.toFixed(2) || '-' }}</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">总盈亏</div>
          <div class="stat-value" :class="statistics.total_pnl >= 0 ? 'positive' : 'negative'">
            {{ formatCurrency(statistics.total_pnl) }}
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">平均盈利</div>
          <div class="stat-value positive">{{ formatCurrency(statistics.avg_profit) }}</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">平均亏损</div>
          <div class="stat-value negative">{{ formatCurrency(statistics.avg_loss) }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 标签页切换 -->
    <el-tabs v-model="activeTab" class="review-tabs">
      <el-tab-pane label="复盘历史" name="history">
        <ReviewHistoryTable 
          :items="reviewHistory" 
          :loading="loading.history"
          :total="historyTotal"
          :page="historyPage"
          :page-size="historyPageSize"
          @view="viewReviewDetail"
          @save-case="saveAsCase"
          @page-change="handleHistoryPageChange"
        />
      </el-tab-pane>
      <el-tab-pane label="案例库" name="cases">
        <CaseLibraryTable
          :items="cases"
          :loading="loading.cases"
          :total="casesTotal"
          :page="casesPage"
          :page-size="casesPageSize"
          @view="viewReviewDetail"
          @delete="deleteCase"
          @page-change="handleCasesPageChange"
        />
      </el-tab-pane>
      <el-tab-pane label="可复盘交易" name="trades">
        <ReviewableTradesTable
          :stocks="reviewableStocks"
          :loading="loading.trades"
          @start-review="startReview"
        />
      </el-tab-pane>
    </el-tabs>

    <!-- 发起复盘对话框 -->
    <NewReviewDialog
      v-model="showNewReviewDialog"
      @success="handleReviewSuccess"
    />

    <!-- 复盘详情对话框 -->
    <ReviewDetailDialog
      v-model="showDetailDialog"
      :review-id="selectedReviewId"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { TrendCharts, Refresh, Plus } from '@element-plus/icons-vue'
import { reviewApi, type ReviewListItem, type TradingStatistics, type ReviewableStock } from '@/api/review'
import ReviewHistoryTable from './components/ReviewHistoryTable.vue'
import CaseLibraryTable from './components/CaseLibraryTable.vue'
import ReviewableTradesTable from './components/ReviewableTradesTable.vue'
import NewReviewDialog from './components/NewReviewDialog.vue'
import ReviewDetailDialog from './components/ReviewDetailDialog.vue'

// 数据
const statistics = ref<Partial<TradingStatistics>>({})
const reviewHistory = ref<ReviewListItem[]>([])
const cases = ref<ReviewListItem[]>([])
const reviewableStocks = ref<ReviewableStock[]>([])

// 分页
const historyTotal = ref(0)
const historyPage = ref(1)
const historyPageSize = ref(10)
const casesTotal = ref(0)
const casesPage = ref(1)
const casesPageSize = ref(10)

// 加载状态
const loading = ref({
  stats: false,
  history: false,
  cases: false,
  trades: false
})

// 标签页
const activeTab = ref('history')

// 对话框
const showNewReviewDialog = ref(false)
const showDetailDialog = ref(false)
const selectedReviewId = ref('')

// 格式化金额
const formatCurrency = (value?: number) => {
  if (value === undefined || value === null) return '-'
  const prefix = value >= 0 ? '+' : ''
  return prefix + value.toFixed(2)
}

// 加载数据
const loadStatistics = async () => {
  try {
    loading.value.stats = true
    const res = await reviewApi.getTradingStatistics()
    if (res.success) {
      statistics.value = res.data || {}
    }
  } catch (e: any) {
    console.error('加载统计失败:', e)
  } finally {
    loading.value.stats = false
  }
}

const loadReviewHistory = async () => {
  try {
    loading.value.history = true
    const res = await reviewApi.getReviewHistory(historyPage.value, historyPageSize.value)
    if (res.success) {
      reviewHistory.value = res.data?.items || []
      historyTotal.value = res.data?.total || 0
    }
  } catch (e: any) {
    console.error('加载复盘历史失败:', e)
  } finally {
    loading.value.history = false
  }
}

const loadCases = async () => {
  try {
    loading.value.cases = true
    const res = await reviewApi.getCases(casesPage.value, casesPageSize.value)
    if (res.success) {
      cases.value = res.data?.items || []
      casesTotal.value = res.data?.total || 0
    }
  } catch (e: any) {
    console.error('加载案例库失败:', e)
  } finally {
    loading.value.cases = false
  }
}

const loadReviewableTrades = async () => {
  try {
    loading.value.trades = true
    const res = await reviewApi.getReviewableTrades()
    if (res.success) {
      reviewableStocks.value = res.data?.completed_stocks || []
    }
  } catch (e: any) {
    console.error('加载可复盘交易失败:', e)
  } finally {
    loading.value.trades = false
  }
}

const refreshData = () => {
  loadStatistics()
  loadReviewHistory()
  loadCases()
  loadReviewableTrades()
}

// 事件处理
const viewReviewDetail = (reviewId: string) => {
  selectedReviewId.value = reviewId
  showDetailDialog.value = true
}

const saveAsCase = async (reviewId: string) => {
  try {
    const res = await reviewApi.saveAsCase({ review_id: reviewId })
    if (res.success) {
      ElMessage.success('已保存到案例库')
      loadReviewHistory()
      loadCases()
    }
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  }
}

const deleteCase = async (reviewId: string) => {
  try {
    const res = await reviewApi.deleteCase(reviewId)
    if (res.success) {
      ElMessage.success('已从案例库移除')
      loadCases()
    }
  } catch (e: any) {
    ElMessage.error(e.message || '删除失败')
  }
}

const startReview = (code: string) => {
  // 将 code 传递给 NewReviewDialog
  selectedReviewId.value = code
  showNewReviewDialog.value = true
}

const handleReviewSuccess = (reviewId: string) => {
  showNewReviewDialog.value = false
  selectedReviewId.value = reviewId
  showDetailDialog.value = true
  refreshData()
}

const handleHistoryPageChange = (page: number) => {
  historyPage.value = page
  loadReviewHistory()
}

const handleCasesPageChange = (page: number) => {
  casesPage.value = page
  loadCases()
}

// 初始化
onMounted(() => {
  refreshData()
})
</script>

<style scoped lang="scss">
.trade-review {
  padding: 20px;

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;

    .title {
      display: flex;
      align-items: center;
      font-size: 20px;
      font-weight: 600;
    }
  }

  .stats-row {
    margin-bottom: 20px;

    .stat-card {
      text-align: center;

      .stat-label {
        font-size: 12px;
        color: #909399;
        margin-bottom: 8px;
      }

      .stat-value {
        font-size: 20px;
        font-weight: 600;

        &.positive {
          color: #67c23a;
        }

        &.negative {
          color: #f56c6c;
        }
      }
    }
  }

  .review-tabs {
    background: #fff;
    padding: 16px;
    border-radius: 4px;
  }
}
</style>

