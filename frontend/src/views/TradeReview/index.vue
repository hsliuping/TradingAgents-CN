<template>
  <div class="trade-review">
    <!-- 页面头部 -->
    <div class="header">
      <div class="title">
        <el-icon style="margin-right:8px"><TrendCharts /></el-icon>
        <span>操作复盘</span>
        <el-tag v-if="isPro" type="success" size="small" style="margin-left: 8px;">高级</el-tag>
      </div>
      <div class="actions">
        <el-button :icon="Refresh" text size="small" @click="refreshData">刷新</el-button>
      </div>
    </div>

    <!-- 复盘类型切换 -->
    <el-tabs v-model="reviewSource" type="card" class="source-tabs" @tab-change="handleSourceChange">
      <el-tab-pane label="持仓操作复盘" name="position">
        <template #label>
          <el-icon><Wallet /></el-icon>
          <span style="margin-left: 4px">持仓操作复盘</span>
        </template>
      </el-tab-pane>
      <el-tab-pane label="模拟交易复盘" name="paper">
        <template #label>
          <el-icon><Goods /></el-icon>
          <span style="margin-left: 4px">模拟交易复盘</span>
        </template>
      </el-tab-pane>
    </el-tabs>

    <!-- 筛选条件 -->
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" :model="filterForm" class="filter-form">
        <el-form-item label="股票代码">
          <el-input
            v-model="filterForm.code"
            placeholder="输入股票代码"
            clearable
            style="width: 140px"
            @keyup.enter="applyFilter"
          />
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="filterForm.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            style="width: 260px"
            :shortcuts="dateShortcuts"
          />
        </el-form-item>
        <el-form-item v-if="reviewSource === 'paper'">
          <el-button type="primary" :icon="Search" @click="applyFilter">筛选</el-button>
          <el-button :icon="RefreshRight" @click="resetFilter">重置</el-button>
        </el-form-item>
        <el-form-item v-else>
          <el-button type="primary" :icon="Search" @click="applyPositionFilter">筛选</el-button>
          <el-button :icon="RefreshRight" @click="resetPositionFilter">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 模拟交易统计卡片 -->
    <el-row v-if="reviewSource === 'paper'" :gutter="16" class="stats-row" v-loading="loading.stats">
      <el-col :span="4">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">总交易数</div>
          <div class="stat-value">{{ statistics.total_trades }}</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">胜率</div>
          <div class="stat-value" :class="(statistics.win_rate || 0) >= 50 ? 'positive' : 'negative'">
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
          <div class="stat-value" :class="(statistics.total_pnl || 0) >= 0 ? 'positive' : 'negative'">
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

    <!-- ============== 模拟交易复盘内容 ============== -->
    <template v-if="reviewSource === 'paper'">
      <el-tabs v-model="activeTab" class="review-tabs">
        <el-tab-pane label="可复盘持仓" name="positions">
          <ReviewableTradesTable
            :stocks="holdingStocks"
            :loading="loading.trades"
            @start-review="startReview"
            @view-report="viewPaperReport"
            @view-history="viewPaperHistory"
          />
        </el-tab-pane>
        <el-tab-pane label="历史持仓" name="historyPositions">
          <ReviewableTradesTable
            :stocks="completedStocks"
            :loading="loading.trades"
            @start-review="startReview"
            @view-report="viewPaperReport"
            @view-history="viewPaperHistory"
          />
        </el-tab-pane>
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
      <!-- 阶段性复盘功能暂时隐藏，下一版本优化后再推出 -->
      <!-- <el-tab-pane label="阶段性复盘" name="periodic">
        <div class="periodic-header">
          <el-button type="primary" :icon="Plus" @click="showPeriodicDialog = true">
            发起阶段性复盘
          </el-button>
        </div>
        <el-table :data="periodicReviews" v-loading="loading.periodic" stripe>
          <el-table-column label="复盘周期" width="100">
            <template #default="{ row }">
              {{ getPeriodTypeLabel(row.period_type) }}
            </template>
          </el-table-column>
          <el-table-column label="时间范围" width="200">
            <template #default="{ row }">
              {{ formatDate(row.period_start) }} ~ {{ formatDate(row.period_end) }}
            </template>
          </el-table-column>
          <el-table-column prop="total_trades" label="交易数" width="80" align="center" />
          <el-table-column label="胜率" width="80" align="center">
            <template #default="{ row }">
              <span :class="row.win_rate >= 50 ? 'positive' : 'negative'">
                {{ row.win_rate?.toFixed(1) || 0 }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column label="总盈亏" width="120" align="right">
            <template #default="{ row }">
              <span :class="row.total_pnl >= 0 ? 'positive' : 'negative'">
                {{ formatCurrency(row.total_pnl) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="评分" width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="getScoreType(row.overall_score)" size="small">
                {{ row.overall_score }}分
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="创建时间" width="160">
            <template #default="{ row }">
              {{ formatDateTime(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-button type="primary" link @click="viewPeriodicDetail(row.review_id)">
                查看详情
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination
          v-if="periodicTotal > 0"
          class="pagination"
          :current-page="periodicPage"
          :page-size="periodicPageSize"
          :total="periodicTotal"
          layout="total, prev, pager, next"
          @current-change="handlePeriodicPageChange"
        />
      </el-tab-pane> -->
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
      </el-tabs>
    </template>

    <!-- ============== 持仓操作复盘内容 ============== -->
    <template v-else>
      <!-- 持仓统计卡片 -->
      <el-row :gutter="16" class="stats-row" v-loading="loading.positionStats">
        <el-col :span="4">
          <el-card shadow="never" class="stat-card">
            <div class="stat-label">持仓股票数</div>
            <div class="stat-value">{{ positionStats.total_positions }}</div>
          </el-card>
        </el-col>
        <el-col :span="4">
          <el-card shadow="never" class="stat-card">
            <div class="stat-label">操作次数</div>
            <div class="stat-value">{{ positionStats.total_operations }}</div>
          </el-card>
        </el-col>
        <el-col :span="4">
          <el-card shadow="never" class="stat-card">
            <div class="stat-label">已清仓</div>
            <div class="stat-value">{{ positionStats.closed_count }}</div>
          </el-card>
        </el-col>
        <el-col :span="4">
          <el-card shadow="never" class="stat-card">
            <div class="stat-label">已实现盈亏</div>
            <div class="stat-value" :class="(positionStats.realized_pnl || 0) >= 0 ? 'positive' : 'negative'">
              {{ formatCurrency(positionStats.realized_pnl) }}
            </div>
          </el-card>
        </el-col>
        <el-col :span="4">
          <el-card shadow="never" class="stat-card">
            <div class="stat-label">浮动盈亏</div>
            <div class="stat-value" :class="(positionStats.unrealized_pnl || 0) >= 0 ? 'positive' : 'negative'">
              {{ formatCurrency(positionStats.unrealized_pnl) }}
            </div>
          </el-card>
        </el-col>
        <el-col :span="4">
          <el-card shadow="never" class="stat-card">
            <div class="stat-label">总市值</div>
            <div class="stat-value">{{ formatCurrency(positionStats.total_market_value) }}</div>
          </el-card>
        </el-col>
      </el-row>

      <el-tabs v-model="positionTab" class="review-tabs">
        <el-tab-pane label="可复盘持仓" name="positions">
          <PositionChangesTable
            :items="positionChanges"
            :loading="loading.positionChanges"
            @start-review="startPositionReview"
            @view-report="viewLatestReport"
            @view-history="viewStockHistory"
          />
        </el-tab-pane>
        <el-tab-pane label="历史持仓" name="history">
          <HistoryPositionsTable
            :items="historyPositions"
            :loading="loading.historyPositions"
            @start-review="startHistoryPositionReview"
          />
        </el-tab-pane>
        <el-tab-pane label="持仓复盘历史" name="positionReviews">
          <!-- 筛选条件提示 -->
          <div v-if="positionReviewCodeFilter" class="filter-tip">
            <el-tag closable @close="clearPositionReviewFilter">
              筛选条件: {{ positionReviewCodeFilter }}
            </el-tag>
          </div>

          <PositionReviewHistoryTable
            :items="positionReviewHistory"
            :loading="loading.positionReviews"
            :total="positionReviewTotal"
            :page="positionReviewPage"
            :page-size="positionReviewPageSize"
            @view="viewPositionReviewDetail"
            @page-change="handlePositionReviewPageChange"
          />
        </el-tab-pane>
        <!-- 阶段性复盘功能暂时隐藏，下一版本优化后再推出 -->
        <!-- <el-tab-pane label="阶段性复盘" name="positionPeriodic">
          <div class="periodic-header">
            <el-button type="primary" :icon="Plus" @click="showPositionPeriodicDialog = true">
              发起阶段性复盘
            </el-button>
          </div>
          <el-table :data="positionPeriodicReviews" v-loading="loading.positionPeriodic" stripe>
            <el-table-column label="复盘周期" width="100">
              <template #default="{ row }">
                {{ getPeriodTypeLabel(row.period_type) }}
              </template>
            </el-table-column>
            <el-table-column label="时间范围" width="200">
              <template #default="{ row }">
                {{ formatDate(row.period_start) }} ~ {{ formatDate(row.period_end) }}
              </template>
            </el-table-column>
            <el-table-column prop="total_trades" label="交易数" width="80" align="center" />
            <el-table-column label="胜率" width="80" align="center">
              <template #default="{ row }">
                <span :class="row.win_rate >= 50 ? 'positive' : 'negative'">
                  {{ row.win_rate?.toFixed(1) || 0 }}%
                </span>
              </template>
            </el-table-column>
            <el-table-column label="总盈亏" width="120" align="right">
              <template #default="{ row }">
                <span :class="row.total_pnl >= 0 ? 'positive' : 'negative'">
                  {{ formatCurrency(row.total_pnl) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="评分" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="getScoreType(row.overall_score)" size="small">
                  {{ row.overall_score }}分
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="创建时间" width="160">
              <template #default="{ row }">
                {{ formatDateTime(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link @click="viewPeriodicDetail(row.review_id)">
                  查看详情
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            v-if="positionPeriodicTotal > 0"
            class="pagination"
            :current-page="positionPeriodicPage"
            :page-size="positionPeriodicPageSize"
            :total="positionPeriodicTotal"
            layout="total, prev, pager, next"
            @current-change="handlePositionPeriodicPageChange"
          />
        </el-tab-pane> -->
        <el-tab-pane label="案例库" name="positionCases">
          <CaseLibraryTable
            :items="positionCases"
            :loading="loading.positionCases"
            :total="positionCasesTotal"
            :page="positionCasesPage"
            :page-size="positionCasesPageSize"
            @view="viewPositionReviewDetail"
            @delete="deletePositionCase"
            @page-change="handlePositionCasesPageChange"
          />
        </el-tab-pane>
      </el-tabs>
    </template>

    <!-- 复盘详情对话框 -->
    <ReviewDetailDialog
      v-model="showDetailDialog"
      :review-id="selectedReviewId"
    />

    <!-- 阶段性复盘功能暂时隐藏 -->
    <!-- <PeriodicReviewDialog
      v-model="showPeriodicDialog"
      @success="handlePeriodicSuccess"
    /> -->

    <!-- <PeriodicReviewDetailDialog
      v-model="showPeriodicDetailDialog"
      :review-id="selectedPeriodicReviewId"
    /> -->

    <!-- 持仓复盘对话框（真实持仓和模拟交易共用） -->
    <PositionReviewDialog
      v-model="showPositionReviewDialog"
      :position-data="selectedPositionData"
      :source="reviewSource === 'paper' ? 'paper' : 'real'"
      @success="handleReviewSuccess"
    />

    <!-- 持仓操作阶段性复盘对话框暂时隐藏 -->
    <!-- <PeriodicReviewDialog
      v-model="showPositionPeriodicDialog"
      source="position"
      @success="handlePositionPeriodicSuccess"
    /> -->

    <!-- 保存为案例对话框 -->
    <SaveAsCaseDialog
      v-model="showSaveCaseDialog"
      :review-id="saveCaseReviewId"
      :stock-code="saveCaseStockCode"
      @success="handleSaveCaseSuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { TrendCharts, Refresh, Search, RefreshRight, Goods, Wallet } from '@element-plus/icons-vue'
import { reviewApi, type ReviewListItem, type TradingStatistics, type ReviewableStock, type ReviewType, type PeriodicReviewListItem } from '@/api/review'
import { portfolioApi } from '@/api/portfolio'
import { useLicenseStore } from '@/stores/license'
import ReviewHistoryTable from './components/ReviewHistoryTable.vue'
import CaseLibraryTable from './components/CaseLibraryTable.vue'
import ReviewableTradesTable from './components/ReviewableTradesTable.vue'
import ReviewDetailDialog from './components/ReviewDetailDialog.vue'
import PeriodicReviewDialog from './components/PeriodicReviewDialog.vue'
import PeriodicReviewDetailDialog from './components/PeriodicReviewDetailDialog.vue'
import PositionChangesTable from './components/PositionChangesTable.vue'
import HistoryPositionsTable from './components/HistoryPositionsTable.vue'
import PositionReviewHistoryTable from './components/PositionReviewHistoryTable.vue'
import PositionReviewDialog from './components/PositionReviewDialog.vue'
import SaveAsCaseDialog from './components/SaveAsCaseDialog.vue'

// 权限检查
const licenseStore = useLicenseStore()
const isPro = computed(() => licenseStore.isPro && licenseStore.hasFeature('trade_review'))

// 复盘来源类型
type ReviewSourceType = 'paper' | 'position'
const reviewSource = ref<ReviewSourceType>('position')  // 默认显示持仓操作复盘

// 筛选表单
const filterForm = ref<{
  code: string
  dateRange: [string, string] | null
  reviewType: ReviewType | ''
}>({
  code: '',
  dateRange: null,
  reviewType: ''
})

// 日期快捷选项
const dateShortcuts = [
  {
    text: '最近一周',
    value: () => {
      const end = new Date()
      const start = new Date()
      start.setTime(start.getTime() - 3600 * 1000 * 24 * 7)
      return [start, end]
    }
  },
  {
    text: '最近一月',
    value: () => {
      const end = new Date()
      const start = new Date()
      start.setTime(start.getTime() - 3600 * 1000 * 24 * 30)
      return [start, end]
    }
  },
  {
    text: '最近三月',
    value: () => {
      const end = new Date()
      const start = new Date()
      start.setTime(start.getTime() - 3600 * 1000 * 24 * 90)
      return [start, end]
    }
  },
  {
    text: '今年',
    value: () => {
      const end = new Date()
      const start = new Date(end.getFullYear(), 0, 1)
      return [start, end]
    }
  }
]

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
  trades: false,
  periodic: false,
  positionStats: false,
  positionChanges: false,
  historyPositions: false,
  positionReviews: false,
  positionPeriodic: false,
  positionCases: false
})

// 标签页 - 默认显示可复盘持仓
const activeTab = ref('positions')

// 计算属性：筛选持仓中的股票（status === 'holding'）
const holdingStocks = computed(() => {
  return reviewableStocks.value.filter(stock => stock.status === 'holding')
})

// 计算属性：筛选已平仓的股票（status === 'completed'）
const completedStocks = computed(() => {
  return reviewableStocks.value.filter(stock => stock.status === 'completed')
})

// 对话框
const showDetailDialog = ref(false)
const selectedReviewId = ref('')

// 保存案例对话框
const showSaveCaseDialog = ref(false)
const saveCaseReviewId = ref('')
const saveCaseStockCode = ref('')

// 阶段性复盘
const periodicReviews = ref<PeriodicReviewListItem[]>([])
const periodicTotal = ref(0)
const periodicPage = ref(1)
const periodicPageSize = ref(10)
const showPeriodicDialog = ref(false)
const showPeriodicDetailDialog = ref(false)
const selectedPeriodicReviewId = ref('')

// ============== 持仓复盘相关状态 ==============
const positionTab = ref('positions')
const positionStats = ref<{
  total_positions: number
  total_operations: number
  closed_count: number
  realized_pnl: number
  unrealized_pnl: number
  total_market_value: number
}>({
  total_positions: 0,
  total_operations: 0,
  closed_count: 0,
  realized_pnl: 0,
  unrealized_pnl: 0,
  total_market_value: 0
})

// 持仓变动记录（当前持仓的操作记录）
interface PositionChangeItem {
  code: string
  name: string
  market: string
  operations: number
  current_quantity: number
  cost_price: number
  unrealized_pnl: number
  unrealized_pnl_pct: number
  last_operation_time: string
}
const positionChanges = ref<PositionChangeItem[]>([])

// 历史持仓（已清仓）
interface HistoryPositionItem {
  code: string
  name: string
  market: string
  realized_pnl: number
  realized_pnl_pct: number
  hold_days: number
  cleared_at: string
}
const historyPositions = ref<HistoryPositionItem[]>([])

// 持仓复盘历史
interface PositionReviewItem {
  id: string
  code: string
  name: string
  review_type: string
  score: number
  created_at: string
  summary: string
  realized_pnl?: number
}
const positionReviewHistory = ref<PositionReviewItem[]>([])
const positionReviewTotal = ref(0)
const positionReviewPage = ref(1)
const positionReviewPageSize = ref(10)
const positionReviewCodeFilter = ref<string>('')  // 股票代码筛选

// 持仓复盘对话框
const showPositionReviewDialog = ref(false)
const selectedPositionData = ref<any>(null)

// 持仓操作阶段性复盘
const positionPeriodicReviews = ref<PeriodicReviewListItem[]>([])
const positionPeriodicTotal = ref(0)
const positionPeriodicPage = ref(1)
const positionPeriodicPageSize = ref(10)
const showPositionPeriodicDialog = ref(false)

// 持仓操作案例库
const positionCases = ref<ReviewListItem[]>([])
const positionCasesTotal = ref(0)
const positionCasesPage = ref(1)
const positionCasesPageSize = ref(10)

// 格式化金额
const formatCurrency = (value?: number) => {
  if (value === undefined || value === null) return '-'
  const prefix = value >= 0 ? '+' : ''
  return prefix + value.toFixed(2)
}

// 获取筛选参数
const getFilterParams = () => {
  const params: {
    code?: string
    startDate?: string
    endDate?: string
    reviewType?: ReviewType
  } = {}

  if (filterForm.value.code) {
    params.code = filterForm.value.code
  }
  if (filterForm.value.dateRange && filterForm.value.dateRange.length === 2) {
    params.startDate = filterForm.value.dateRange[0]
    params.endDate = filterForm.value.dateRange[1]
  }
  if (filterForm.value.reviewType) {
    params.reviewType = filterForm.value.reviewType
  }

  return params
}

// 加载数据
const loadStatistics = async () => {
  try {
    loading.value.stats = true
    const params = getFilterParams()
    const res = await reviewApi.getTradingStatistics(params.startDate, params.endDate)
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
    const params = getFilterParams()
    const res = await reviewApi.getReviewHistory({
      page: historyPage.value,
      pageSize: historyPageSize.value,
      source: 'paper',  // 模拟交易复盘只显示模拟交易的复盘历史
      ...params
    })
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
    const res = await reviewApi.getCases({ page: casesPage.value, pageSize: casesPageSize.value, source: 'paper' })
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
    const params = getFilterParams()
    const res = await reviewApi.getReviewableTrades({
      code: params.code,
      startDate: params.startDate,
      endDate: params.endDate
    })
    if (res.success) {
      // 使用 all_stocks 显示所有有交易的股票（包括只买入还没卖出的）
      reviewableStocks.value = res.data?.all_stocks || res.data?.completed_stocks || []
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

// 筛选操作
const applyFilter = () => {
  historyPage.value = 1
  refreshData()
}

const resetFilter = () => {
  filterForm.value = {
    code: '',
    dateRange: null,
    reviewType: ''
  }
  historyPage.value = 1
  refreshData()
}

// 事件处理
const viewReviewDetail = (reviewId: string) => {
  selectedReviewId.value = reviewId
  showDetailDialog.value = true
}

const saveAsCase = async (reviewId: string) => {
  // 查找对应的复盘记录，获取股票代码
  const review = reviewHistory.value.find(r => r.review_id === reviewId)
  saveCaseReviewId.value = reviewId
  saveCaseStockCode.value = review?.code || ''
  showSaveCaseDialog.value = true
}

const handleSaveCaseSuccess = () => {
  loadReviewHistory()
  loadCases()
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

const startReview = async (code: string) => {
  try {
    // 从 reviewableStocks 中查找该股票的信息
    const stock = reviewableStocks.value.find(s => s.code === code)
    if (!stock) {
      ElMessage.warning('未找到该股票信息')
      return
    }

    // 获取模拟持仓数据（如果持仓中）
    let positionData: any = {
      code: stock.code,
      name: stock.name || stock.code,
      market: stock.market || 'CN',
      type: stock.status === 'completed' ? 'history' : 'current'
    }

    // 如果是持仓中，尝试获取持仓详情
    if (stock.status === 'holding' || (stock.sell_count || 0) < (stock.buy_count || 0)) {
      try {
        const posRes = await portfolioApi.getPositions('paper')
        const positions = posRes.data?.items || []
        const position = positions.find((p: any) => p.code === code)
        if (position) {
          positionData = {
            code: position.code,
            name: position.name || position.code,
            market: position.market || 'CN',
            type: 'current',
            quantity: position.quantity,
            cost_price: position.cost_price || position.avg_cost,
            unrealized_pnl: position.unrealized_pnl || 0
          }
        }
      } catch (e) {
        console.warn('获取模拟持仓详情失败，使用默认数据', e)
      }
    }

    // 使用 PositionReviewDialog（和真实持仓一样的界面）
    selectedPositionData.value = positionData
    showPositionReviewDialog.value = true
  } catch (e: any) {
    console.error('发起复盘失败:', e)
    ElMessage.error(e.message || '发起复盘失败')
  }
}

// 查看模拟交易该股票最新的复盘报告
const viewPaperReport = async (stock: ReviewableStock) => {
  try {
    // 获取该股票的最新复盘报告（只获取模拟交易的）
    const res = await reviewApi.getReviewHistory({
      page: 1,
      pageSize: 1,
      code: stock.code,
      source: 'paper'  // 只获取模拟交易的复盘报告
    })

    if (res.success && res.data?.items && res.data.items.length > 0) {
      const latestReview = res.data.items[0]
      viewReviewDetail(latestReview.review_id)
    } else {
      ElMessage.warning(`${stock.name || stock.code}(${stock.code}) 暂无复盘报告`)
    }
  } catch (e) {
    console.error('获取最新复盘报告失败:', e)
    ElMessage.error('获取复盘报告失败')
  }
}

// 查看模拟交易该股票的所有复盘历史
const viewPaperHistory = (stock: ReviewableStock) => {
  // 设置筛选条件
  filterForm.value.code = stock.code
  historyPage.value = 1

  // 切换到"复盘历史"标签页
  activeTab.value = 'history'

  // 重新加载数据（会自动使用 filterForm 中的 code 和 source='paper'）
  loadReviewHistory()

  ElMessage.success(`正在查看 ${stock.name || stock.code}(${stock.code}) 的复盘历史`)
}


const handleHistoryPageChange = (page: number) => {
  historyPage.value = page
  loadReviewHistory()
}

const handleCasesPageChange = (page: number) => {
  casesPage.value = page
  loadCases()
}

// 阶段性复盘相关方法
const loadPeriodicReviews = async () => {
  try {
    loading.value.periodic = true
    const res = await reviewApi.getPeriodicReviewHistory(periodicPage.value, periodicPageSize.value)
    if (res.success) {
      periodicReviews.value = res.data?.items || []
      periodicTotal.value = res.data?.total || 0
    }
  } catch (e) {
    console.error('加载阶段性复盘历史失败:', e)
  } finally {
    loading.value.periodic = false
  }
}

const getPeriodTypeLabel = (type: string) => {
  const map: Record<string, string> = {
    week: '周度',
    month: '月度',
    quarter: '季度',
    year: '年度'
  }
  return map[type] || type
}

const formatDate = (dateStr?: string) => {
  if (!dateStr) return '-'
  return dateStr.split('T')[0]
}

const formatDateTime = (dateStr?: string) => {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const getScoreType = (score: number) => {
  if (score >= 80) return 'success'
  if (score >= 60) return 'warning'
  return 'danger'
}

const viewPeriodicDetail = (reviewId: string) => {
  selectedPeriodicReviewId.value = reviewId
  showPeriodicDetailDialog.value = true
}

const handlePeriodicSuccess = (reviewId: string) => {
  showPeriodicDialog.value = false
  selectedPeriodicReviewId.value = reviewId
  showPeriodicDetailDialog.value = true
  loadPeriodicReviews()
}

const handlePeriodicPageChange = (page: number) => {
  periodicPage.value = page
  loadPeriodicReviews()
}

// ============== 持仓复盘相关方法 ==============
const handleSourceChange = (source: ReviewSourceType) => {
  if (source === 'paper') {
    refreshData()
    loadPeriodicReviews()
  } else {
    loadPositionData()
  }
}

const loadPositionData = async () => {
  await Promise.all([
    loadPositionStats(),
    loadPositionChanges(),
    loadHistoryPositions(),
    loadPositionReviewHistory(),
    loadPositionPeriodicReviews(),
    loadPositionCases()
  ])
}

const loadPositionStats = async () => {
  try {
    loading.value.positionStats = true
    // 获取当前持仓
    const posRes = await portfolioApi.getPositions('real')
    const positions = posRes.data?.items || []

    // 获取历史持仓
    const histRes = await portfolioApi.getHistoryPositions({ source: 'real', limit: 100 })
    const history = histRes.data?.items || []

    // 计算统计数据
    let totalMarketValue = 0
    let unrealizedPnl = 0
    let realizedPnl = 0

    positions.forEach((p: any) => {
      totalMarketValue += p.market_value || 0
      unrealizedPnl += p.unrealized_pnl || 0
    })

    history.forEach((h: any) => {
      realizedPnl += h.realized_pnl || 0
    })

    positionStats.value = {
      total_positions: positions.length,
      total_operations: 0, // 后续从变动记录统计
      closed_count: history.length,
      realized_pnl: realizedPnl,
      unrealized_pnl: unrealizedPnl,
      total_market_value: totalMarketValue
    }
  } catch (e) {
    console.error('加载持仓统计失败:', e)
  } finally {
    loading.value.positionStats = false
  }
}

const loadPositionChanges = async () => {
  try {
    loading.value.positionChanges = true
    // 获取当前持仓列表
    const res = await portfolioApi.getPositions('real')
    const positions = res.data?.items || []

    // 转换为可复盘格式
    positionChanges.value = positions.map((p: any) => ({
      code: p.code,
      name: p.name || p.code,
      market: p.market || 'CN',
      operations: 0,
      current_quantity: p.quantity,
      cost_price: p.cost_price || p.avg_cost,
      unrealized_pnl: p.unrealized_pnl || 0,
      unrealized_pnl_pct: p.unrealized_pnl_pct || 0,
      last_operation_time: p.updated_at || p.created_at
    }))
  } catch (e) {
    console.error('加载持仓变动失败:', e)
  } finally {
    loading.value.positionChanges = false
  }
}

const loadHistoryPositions = async () => {
  try {
    loading.value.historyPositions = true
    const res = await portfolioApi.getHistoryPositions({ source: 'real', limit: 50 })
    historyPositions.value = (res.data?.items || []).map((h: any) => ({
      code: h.code,
      name: h.name || h.code,
      market: h.market || 'CN',
      realized_pnl: h.realized_pnl || 0,
      realized_pnl_pct: h.realized_pnl_pct || 0,
      hold_days: h.hold_days || 0,
      cleared_at: h.cleared_at || h.updated_at
    }))
  } catch (e) {
    console.error('加载历史持仓失败:', e)
  } finally {
    loading.value.historyPositions = false
  }
}

const loadPositionReviewHistory = async () => {
  try {
    loading.value.positionReviews = true
    // 调用持仓复盘历史 API
    const res = await reviewApi.getReviewHistory({
      page: positionReviewPage.value,
      pageSize: positionReviewPageSize.value,
      code: positionReviewCodeFilter.value || undefined  // 如果有筛选条件则传入
    })
    if (res.success) {
      // 映射数据字段：review_id -> id, overall_score -> score
      positionReviewHistory.value = (res.data?.items || []).map((item: any) => ({
        id: item.review_id,
        code: item.code,
        name: item.name,
        review_type: item.review_type,
        score: item.overall_score,
        created_at: item.created_at,
        summary: `盈亏: ${item.realized_pnl >= 0 ? '+' : ''}${item.realized_pnl.toFixed(2)}元`,
        realized_pnl: item.realized_pnl
      }))
      positionReviewTotal.value = res.data?.total || 0
    }
  } catch (e) {
    console.error('加载持仓复盘历史失败:', e)
  } finally {
    loading.value.positionReviews = false
  }
}

const startPositionReview = (item: PositionChangeItem) => {
  selectedPositionData.value = {
    code: item.code,
    name: item.name,
    market: item.market,
    type: 'current',
    quantity: item.current_quantity,
    cost_price: item.cost_price,
    unrealized_pnl: item.unrealized_pnl
  }
  showPositionReviewDialog.value = true
}

const startHistoryPositionReview = (item: HistoryPositionItem) => {
  selectedPositionData.value = {
    code: item.code,
    name: item.name,
    market: item.market,
    type: 'history',
    realized_pnl: item.realized_pnl,
    hold_days: item.hold_days
  }
  showPositionReviewDialog.value = true
}

// 查看该股票最新的复盘报告
const viewLatestReport = async (item: PositionChangeItem) => {
  try {
    // 获取该股票的最新复盘报告（只获取真实持仓的）
    const res = await reviewApi.getReviewHistory({
      page: 1,
      pageSize: 1,
      code: item.code,
      source: 'position'  // 只获取真实持仓的复盘报告
    })

    if (res.success && res.data?.items && res.data.items.length > 0) {
      const latestReview = res.data.items[0]
      viewPositionReviewDetail(latestReview.review_id)
    } else {
      ElMessage.warning(`${item.name}(${item.code}) 暂无复盘报告`)
    }
  } catch (e) {
    console.error('获取最新复盘报告失败:', e)
    ElMessage.error('获取复盘报告失败')
  }
}

// 查看该股票的所有复盘历史
const viewStockHistory = (item: PositionChangeItem) => {
  // 设置筛选条件
  positionReviewCodeFilter.value = item.code
  positionReviewPage.value = 1

  // 切换到"持仓复盘历史"标签页
  positionTab.value = 'positionReviews'

  // 重新加载数据
  loadPositionReviewHistory()

  ElMessage.success(`正在查看 ${item.name}(${item.code}) 的复盘历史`)
}

const viewPositionReviewDetail = (reviewId: string) => {
  selectedReviewId.value = reviewId
  showDetailDialog.value = true
}

const handlePositionReviewPageChange = (page: number) => {
  positionReviewPage.value = page
  loadPositionReviewHistory()
}

const clearPositionReviewFilter = () => {
  positionReviewCodeFilter.value = ''
  positionReviewPage.value = 1
  loadPositionReviewHistory()
}

// 统一的复盘成功回调（根据 reviewSource 判断）
const handleReviewSuccess = (reviewId: string) => {
  console.log('[复盘] 复盘成功回调，reviewId:', reviewId, 'reviewSource:', reviewSource.value)
  
  // 先打开详情页面
  selectedReviewId.value = reviewId
  showDetailDialog.value = true
  console.log('[复盘] 已打开详情对话框，showDetailDialog:', showDetailDialog.value, 'selectedReviewId:', selectedReviewId.value)
  
  // 然后关闭复盘对话框
  showPositionReviewDialog.value = false
  selectedPositionData.value = null
  
  // 根据数据源刷新对应的历史数据
  if (reviewSource.value === 'paper') {
    // 模拟交易复盘：异步刷新历史（不阻塞详情页面打开）
    setTimeout(() => {
      loadReviewHistory()
    }, 500)
  } else {
    // 真实持仓复盘：异步刷新历史（不阻塞详情页面打开）
    setTimeout(() => {
      loadPositionReviewHistory()
    }, 500)
  }
}

// 模拟交易复盘成功回调（保留以兼容）
const handlePaperReviewSuccess = handleReviewSuccess

// 真实持仓复盘成功回调（保留以兼容）
const handleRealPositionReviewSuccess = handleReviewSuccess

// 保留旧函数名以兼容（真实持仓）
const handlePositionReviewSuccess = handleReviewSuccess

const applyPositionFilter = () => {
  loadPositionChanges()
  loadHistoryPositions()
}

const resetPositionFilter = () => {
  filterForm.value.code = ''
  filterForm.value.dateRange = null
  loadPositionChanges()
  loadHistoryPositions()
}

// 持仓操作阶段性复盘相关方法
const loadPositionPeriodicReviews = async () => {
  try {
    loading.value.positionPeriodic = true
    const res = await reviewApi.getPeriodicReviewHistory(positionPeriodicPage.value, positionPeriodicPageSize.value, 'position')
    if (res.success) {
      positionPeriodicReviews.value = res.data?.items || []
      positionPeriodicTotal.value = res.data?.total || 0
    }
  } catch (e) {
    console.error('加载持仓操作阶段性复盘历史失败:', e)
  } finally {
    loading.value.positionPeriodic = false
  }
}

const handlePositionPeriodicSuccess = (reviewId: string) => {
  showPositionPeriodicDialog.value = false
  selectedPeriodicReviewId.value = reviewId
  showPeriodicDetailDialog.value = true
  loadPositionPeriodicReviews()
}

const handlePositionPeriodicPageChange = (page: number) => {
  positionPeriodicPage.value = page
  loadPositionPeriodicReviews()
}

// 持仓操作案例库相关方法
const loadPositionCases = async () => {
  try {
    loading.value.positionCases = true
    const res = await reviewApi.getCases({
      page: positionCasesPage.value,
      pageSize: positionCasesPageSize.value,
      source: 'position'  // 只获取持仓操作的案例
    })
    if (res.success) {
      positionCases.value = res.data?.items || []
      positionCasesTotal.value = res.data?.total || 0
    }
  } catch (e) {
    console.error('加载持仓操作案例库失败:', e)
  } finally {
    loading.value.positionCases = false
  }
}

const deletePositionCase = async (reviewId: string) => {
  try {
    const res = await reviewApi.deleteCase(reviewId)
    if (res.success) {
      ElMessage.success('已从案例库删除')
      loadPositionCases()
    }
  } catch (e: any) {
    ElMessage.error(e.message || '删除失败')
  }
}

const handlePositionCasesPageChange = (page: number) => {
  positionCasesPage.value = page
  loadPositionCases()
}

// 初始化
onMounted(async () => {
  // 确保权限状态已刷新
  if (licenseStore.appToken) {
    await licenseStore.verifyLicense(true)
  }
  
  // 调试信息
  console.log('[操作复盘页面] 权限状态', {
    isPro: licenseStore.isPro,
    plan: licenseStore.plan,
    hasTradeReview: licenseStore.hasFeature('trade_review'),
    licenseInfo: licenseStore.licenseInfo
  })
  
  // 根据默认的 reviewSource 加载对应的数据
  if (reviewSource.value === 'paper') {
    refreshData()
    loadPeriodicReviews()
  } else {
    loadPositionData()
  }
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

  .source-tabs {
    margin-bottom: 16px;

    :deep(.el-tabs__item) {
      font-size: 14px;
    }
  }

  .filter-card {
    margin-bottom: 20px;

    .filter-form {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;

      :deep(.el-form-item) {
        margin-bottom: 0;
        margin-right: 16px;
      }
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

    .filter-tip {
      margin-bottom: 16px;
      padding: 8px 12px;
      background: #f5f7fa;
      border-radius: 4px;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .periodic-header {
      margin-bottom: 16px;
    }

    .pagination {
      margin-top: 16px;
      justify-content: flex-end;
    }

    .positive {
      color: #67c23a;
    }

    .negative {
      color: #f56c6c;
    }
  }
}
</style>

