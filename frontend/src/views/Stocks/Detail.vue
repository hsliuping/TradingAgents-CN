<template>
  <div class="stock-detail-redesign">

    <!-- ════════ 1. 顶部：股票概览 + 操作入口 ════════ -->
    <StockOverview
      :code="code"
      :stock-name="stockName"
      :market-label="marketLabel"
      :is-etf="isEtf"
      :quote="quote"
      :etf-basics="etfBasics"
      :is-fav="isFav"
      :refresh-text="refreshText"
      :sync-status="syncStatus"
      :sync-loading="syncLoading"
      :clear-cache-loading="clearCacheLoading"
      @refresh="refreshMockQuote"
      @analyze="onAnalyze"
      @sync="showSyncDialog"
      @paper-trading="goPaperTrading"
      @toggle-favorite="onToggleFavorite"
      @clear-cache="clearCache"
      @go-position-analysis="goToPositionAnalysis"
      @add-position="showAddPositionDialog"
      @go-trade-review="goToTradeReview"
      @go-trade-review-history="goToReviewHistory"
      @go-api-guide="goToApiGuide"
    />

    <!-- ════════ 2. 智能助手主入口（紧接顶部，突出显示） ════════ -->
    <AssistantHero
      :code="code"
      :stock-name="stockName"
      :has-analysis="assistantHasAnalysis"
      :has-position="assistantHasPosition"
      :has-review="assistantHasReview"
      :has-fundamentals="assistantHasFundamentals"
      :has-kline="assistantHasKline"
      @ask="handleAssistantHeroAsk"
    />

    <!-- ════════ 3. 研究路径（sticky 导航） ════════ -->
    <ResearchFlow
      :steps="researchFlowSteps"
      :active-key="activeFlowKey"
      @step-click="handleFlowStepClick"
    />

    <!-- ════════ 4. K线 + 核心指标 ════════ -->
    <div class="main-grid" id="kline-section">
      <KlineChart
        :title="klineCardTitle"
        :category="klineCategory"
        :values="klineValues"
        :volumes="klineVolumes"
        :period="period"
        :period-options="periodOptions"
        :kline-source="klineSource"
        :last-k-time="lastKTime"
        :last-k-close="lastKClose"
        @update-period="handlePeriodChange"
      />
      <CoreMetrics
        :basics="basics"
        :financial-snapshot="financialSnapshot"
        :factor-warning-entries="detailFactorWarningEntries"
        :factor-diagnostic-entries="detailFactorDiagnosticEntries"
      />
    </div>

    <!-- ════════ 5. 单股分析结果 ════════ -->
    <AnalysisResultCard
      :analysis-status="analysisStatus"
      :analysis-progress="analysisProgress"
      :analysis-message="analysisMessage"
      :last-analysis="lastAnalysis"
      :last-task-info="lastTaskInfo"
      :one-sentence-conclusion="oneSentenceConclusion"
      :report-keys="reportKeys"
      :history-count="analysisHistoryCount"
      @analyze="onAnalyze"
      @view-reports="showReportsDialog = true"
      @open-report="openReport"
      @view-history="goToAnalysisHistory"
    />

    <!-- ════════ 6. 持仓分析 + 交易复盘（标签页切换） ════════ -->
    <PositionReviewTabs
      :position-summary="positionSummary"
      :review-summary="reviewSummary"
      :position-data="positionData"
      :review-history="reviewHistory"
      :position-history-count="positionHistoryCount"
      @go-position-analysis="goToPositionAnalysis"
      @go-trade-review="goToTradeReview"
      @view-position-task-detail="viewPositionTaskDetail"
      @view-review-task-detail="viewReviewTaskDetail"
      @view-position-history="goToPositionHistory"
      @view-review-history="goToReviewHistory"
      @select-review-item="selectReviewItem"
    />

    <!-- ════════ 7. 智能助手对话区 ════════ -->
    <AssistantChat
      ref="assistantChatRef"
      v-model:messages="assistantMessages"
      :code="code"
      :stock-name="stockName"
      :loaded-modules="assistantLoadedModules"
      :initial-prompt="assistantInitialPrompt"
      :loading="assistantLoading"
      input-placeholder="输入问题，例如：结合分析和持仓，我下一步应该重点跟踪什么？"
      @ask="handleAssistantAsk"
    />

    <!-- ════════ 8. 基本面 + 新闻 ════════ -->
    <BottomSection
      :is-etf="isEtf"
      :basics="basics"
      :financial-snapshot="financialSnapshot"
      :etf-basics="etfBasics"
      :financial-raw-sections="financialRawSections"
      :news-items="newsItems"
      :news-filter="newsFilter"
      :news-loading="newsLoading"
      :news-source="newsSource"
      @news-filter-change="(v: string) => newsFilter = v"
    />

    <!-- 回到顶部 -->
    <BackToTop :show-after="600" />

    <!-- 添加持仓对话框 -->
    <AddPositionDialog
      v-model:visible="addPositionDialogVisible"
      :initial-data="addPositionInitialData"
      @success="onAddPositionSuccess"
    />

    <!-- ════════ 对话框（保留原有逻辑） ════════ -->

    <!-- 详细报告对话框 -->
    <el-dialog
      v-model="showReportsDialog"
      title="📊 详细分析报告"
      width="80%"
      :close-on-click-modal="false"
      class="reports-dialog"
    >
      <el-tabs v-model="activeReportTab" type="border-card">
        <el-tab-pane
          v-for="key in reportKeys"
          :key="key"
          :label="formatReportName(key)"
          :name="key"
        >
          <div class="report-content">
            <el-scrollbar height="500px">
              <div class="markdown-body" v-html="renderMarkdown(getReportContent(lastAnalysis?.reports?.[key]))"></div>
            </el-scrollbar>
          </div>
        </el-tab-pane>
      </el-tabs>

      <template #footer>
        <el-button @click="showReportsDialog = false">关闭</el-button>
        <el-button type="primary" @click="exportReport">导出报告</el-button>
      </template>
    </el-dialog>

    <!-- 数据同步对话框 -->
    <el-dialog
      v-model="syncDialogVisible"
      :title="syncDialogTitle"
      width="500px"
    >
      <el-form :model="syncForm" label-width="120px">
        <el-form-item :label="securityCodeLabel">
          <el-input v-model="code" disabled />
        </el-form-item>
        <el-form-item :label="isEtf ? 'ETF名称' : '股票名称'">
          <el-input v-model="stockName" disabled />
        </el-form-item>
        <el-form-item label="同步内容">
          <el-checkbox-group v-model="syncForm.syncTypes">
            <el-checkbox label="realtime">实时行情</el-checkbox>
            <el-checkbox label="historical">历史行情数据</el-checkbox>
            <el-checkbox v-if="!isEtf" label="financial">财务数据</el-checkbox>
            <el-checkbox label="basic">基础数据</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="数据源">
          <el-radio-group v-model="syncForm.dataSource">
            <el-radio label="tushare" :disabled="!availableSyncSources.tushare">Tushare</el-radio>
            <el-radio label="akshare" :disabled="!availableSyncSources.akshare">AKShare</el-radio>
            <el-radio v-if="!isJdyunMode()" label="qmt" :disabled="!availableSyncSources.qmt">QMT</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="历史数据天数" v-if="syncForm.syncTypes.includes('historical')">
          <el-input-number v-model="syncForm.days" :min="1" :max="3650" />
          <span style="margin-left: 10px; color: #909399; font-size: 12px;">
            (最多3650天，约10年)
          </span>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="syncDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSync" :loading="syncLoading">
          开始同步
        </el-button>
      </template>
    </el-dialog>

    <!-- 复盘详情对话框 -->
    <el-dialog
      v-model="reviewDetailVisible"
      title="复盘详情"
      width="800px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <div v-if="reviewDetailLoading" class="detail-loading">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>加载中...</span>
      </div>
      <div v-else-if="currentReviewDetail" class="review-detail-content">
        <!-- 交易摘要 -->
        <el-descriptions title="交易摘要" :column="3" border size="small" class="section">
          <el-descriptions-item label="股票代码">{{ currentReviewDetail.trade_info?.code }}</el-descriptions-item>
          <el-descriptions-item label="持仓天数">{{ currentReviewDetail.trade_info?.holding_days }}天</el-descriptions-item>
          <el-descriptions-item label="盈亏金额">
            <span :class="getTotalPnl() >= 0 ? 'positive' : 'negative'">
              {{ formatPnlValue(getTotalPnl()) }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="买入均价">{{ currentReviewDetail.trade_info?.avg_buy_price?.toFixed(2) }}</el-descriptions-item>
          <el-descriptions-item label="卖出均价">{{ currentReviewDetail.trade_info?.avg_sell_price?.toFixed(2) }}</el-descriptions-item>
          <el-descriptions-item label="收益率">
            <span :class="getTotalPnlPct() >= 0 ? 'positive' : 'negative'">
              {{ formatPct(getTotalPnlPct()) }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="手续费" :span="3">{{ currentReviewDetail.trade_info?.total_commission?.toFixed(2) }}元</el-descriptions-item>
        </el-descriptions>

        <!-- 复盘结论 -->
        <div class="section">
          <h4 class="section-title">复盘结论</h4>
          <div class="summary markdown-content" v-html="renderMarkdown(currentReviewDetail.ai_review?.summary)"></div>
        </div>

        <!-- 优缺点 -->
        <el-row :gutter="16" class="section">
          <el-col :span="12">
            <div class="analysis-card strengths">
              <h4><el-icon><CircleCheck /></el-icon> 做得好的地方</h4>
              <div class="markdown-content" v-html="renderMarkdown((currentReviewDetail.ai_review?.strengths || []).join('\n\n'))"></div>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="analysis-card weaknesses">
              <h4><el-icon><Warning /></el-icon> 暴露的问题</h4>
              <div class="markdown-content" v-html="renderMarkdown((currentReviewDetail.ai_review?.weaknesses || []).join('\n\n'))"></div>
            </div>
          </el-col>
        </el-row>

        <!-- 复盘改进项 -->
        <div class="section" v-if="currentReviewDetail.ai_review?.suggestions?.length">
          <h4 class="section-title"><el-icon><Pointer /></el-icon> 后续改进重点</h4>
          <div class="suggestions markdown-content" v-html="renderMarkdown((currentReviewDetail.ai_review?.suggestions || []).join('\n\n'))"></div>
        </div>

        <!-- 详细分析 -->
        <el-collapse class="section">
          <el-collapse-item title="时机复盘" name="timing" v-if="currentReviewDetail.ai_review?.timing_analysis">
            <div class="markdown-content" v-html="renderMarkdown(currentReviewDetail.ai_review?.timing_analysis)"></div>
          </el-collapse-item>
          <el-collapse-item title="仓位复盘" name="position" v-if="currentReviewDetail.ai_review?.position_analysis">
            <div class="markdown-content" v-html="renderMarkdown(currentReviewDetail.ai_review?.position_analysis)"></div>
          </el-collapse-item>
          <el-collapse-item title="情绪复盘" name="emotion" v-if="currentReviewDetail.ai_review?.emotion_analysis">
            <div class="markdown-content" v-html="renderMarkdown(currentReviewDetail.ai_review?.emotion_analysis)"></div>
          </el-collapse-item>
          <el-collapse-item title="归因复盘" name="attribution" v-if="currentReviewDetail.ai_review?.attribution_analysis">
            <div class="markdown-content" v-html="renderMarkdown(currentReviewDetail.ai_review?.attribution_analysis)"></div>
          </el-collapse-item>
        </el-collapse>
      </div>
      <template #footer>
        <el-button @click="reviewDetailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

  </div>
</template>


<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading, CircleCheck, Warning, Pointer } from '@element-plus/icons-vue'
import { renderMarkdown } from '@/utils/markdown'
import { stocksApi } from '@/api/stocks'
import { assistantApi, type AssistantThreadItem } from '@/api/assistant'
import { ApiClient } from '@/api/request'
import {
  stockSyncApi,
  type SingleStockSyncResponse,
  type StockSyncTaskStatus,
} from '@/api/stockSync'
import { clearAllCache } from '@/api/cache'
import { use as echartsUse } from 'echarts/core'
import { CandlestickChart } from 'echarts/charts'

import { GridComponent, TooltipComponent, DataZoomComponent, LegendComponent, TitleComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsOption } from 'echarts'
import { favoritesApi } from '@/api/favorites'
import { useAuthStore } from '@/stores/auth'
import type { StockInfo } from '@/types/analysis'
import { getFactorDiagnosticEntries, getFactorWarningEntries } from '@/utils/factorPresentation'
import { loadManualSyncSourceState, type ManualSyncDataSource } from '@/utils/dataSource'
import { isJdyunMode } from '@/utils/config'
import { getReportName } from '@/utils/reportPresentation'
import { getTaskList, getTaskDetail, TaskType, TaskStatus } from '@/api/unifiedTasks'
import { reviewApi } from '@/api/review'
import { portfolioApi } from '@/api/portfolio'

// 新版股票详情页子组件
import StockOverview from './components/StockOverview.vue'
import AssistantHero from './components/AssistantHero.vue'
import ResearchFlow from './components/ResearchFlow.vue'
import KlineChart from './components/KlineChart.vue'
import CoreMetrics from './components/CoreMetrics.vue'
import AnalysisResultCard from './components/AnalysisResultCard.vue'
import PositionReviewTabs from './components/PositionReviewTabs.vue'
import AssistantChat from './components/AssistantChat.vue'
import BottomSection from './components/BottomSection.vue'
import BackToTop from './components/BackToTop.vue'
import AddPositionDialog from '@/views/Portfolio/components/AddPositionDialog.vue'


echartsUse([CandlestickChart, GridComponent, TooltipComponent, DataZoomComponent, LegendComponent, TitleComponent, CanvasRenderer])

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const STOCK_SYNC_POLL_INTERVAL_MS = 2000
const STOCK_SYNC_POLL_MAX_ATTEMPTS = 300
let stockDetailDisposed = false


// 分析状态
const analysisStatus = ref<'idle' | 'running' | 'completed' | 'failed'>('idle')
const analysisProgress = ref(0)
const analysisMessage = ref('')
const lastAnalysis = ref<any | null>(null)
const lastTaskInfo = ref<any | null>(null) // 保存任务信息（包含 end_time 等）

// 报告对话框
const showReportsDialog = ref(false)
const activeReportTab = ref('')

const reportKeys = computed(() => Object.keys(lastAnalysis.value?.reports || {}))
const oneSentenceConclusion = computed(() => {
  const traderPlan = getReportContent(lastAnalysis.value?.reports?.trader_investment_plan)
  const conclusion = extractMarkdownSection(traderPlan, '一句话结论')
  return conclusion || lastAnalysis.value?.summary || '-'
})

// 股票代码（从路由参数获取）
watch(
  () => route.params.code,
  (value) => {
    if (String(value || '').trim()) {
      return
    }
    ElMessage.error('股票代码不能为空')
    router.push({ name: 'Dashboard' })
  },
  { immediate: true }
)

const code = computed(() => String(route.params.code || '').toUpperCase())
const symbol = computed(() => code.value.split('.')[0])  // 提取6位代码
const stockName = ref('')
const market = ref('')
const isFav = ref(false)

const ETF_CODE_PREFIXES = ['50', '51', '52', '56', '58', '15', '16', '18']

function isLikelyEtfCode(value: string): boolean {
  const text = String(value || '').trim()
  return /^\d{6}$/.test(text) && ETF_CODE_PREFIXES.some(prefix => text.startsWith(prefix))
}

const isEtf = computed(() => market.value === 'ETF' || isLikelyEtfCode(symbol.value))
const marketLabel = computed(() => isEtf.value ? 'ETF' : (market.value || '-'))
const securityName = computed(() => isEtf.value ? 'ETF' : '股票')
const securityCodeLabel = computed(() => `${securityName.value}代码`)
const syncDialogTitle = computed(() => `同步${securityName.value}数据`)
const klineCardTitle = computed(() => isEtf.value ? 'ETF价格走势' : '价格K线')

// ECharts K线配置
const kOption = ref<EChartsOption>({
  grid: { left: 40, right: 20, top: 20, bottom: 40 },
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'cross' }
  },
  xAxis: {
    type: 'category',
    data: [],
    boundaryGap: true,
    axisLine: { onZero: false }
  },
  yAxis: {
    scale: true,
    type: 'value'
  },
  dataZoom: [
    { type: 'inside', start: 70, end: 100 },
    { start: 70, end: 100 }
  ],
  series: [
    {
      type: 'candlestick',
      name: 'K线',
      data: [],
      itemStyle: {
        color: '#ef4444',
        color0: '#16a34a',
        borderColor: '#ef4444',
        borderColor0: '#16a34a'
      }
    }
  ]
})

const lastKTime = ref<string | null>(null)
const lastKClose = ref<number | null>(null)

// 报价（初始化）
const quote = reactive({
  price: NaN,
  changePercent: NaN,
  open: NaN,
  high: NaN,
  low: NaN,
  prevClose: NaN,
  volume: NaN,
  amount: NaN,
  turnover: NaN,
  amplitude: NaN,
  tradeDate: null as string | null,
  turnoverDate: null as string | null,
  amplitudeDate: null as string | null,
  updatedAt: null as string | null
})

const lastRefreshAt = ref<Date | null>(null)
const refreshText = computed(() => lastRefreshAt.value ? `已刷新 ${lastRefreshAt.value.toLocaleTimeString()}` : '未刷新')

// 同步状态
const syncStatus = ref<any>(null)

// 数据同步对话框
const syncDialogVisible = ref(false)
const syncLoading = ref(false)

// 添加持仓对话框
const addPositionDialogVisible = ref(false)
const addPositionInitialData = computed(() => ({
  code: code.value,
  name: stockName.value,
  market: isEtf.value ? 'ETF' : 'CN',
  cost_price: Number(quote.price) || undefined
}))
const availableSyncSources = reactive<Record<ManualSyncDataSource, boolean>>({
  tushare: true,
  akshare: true,
  qmt: true
})
const syncForm = reactive({
  syncTypes: ['realtime'],  // 默认选中实时行情
  dataSource: 'tushare' as ManualSyncDataSource,
  days: 365
})

watch(isEtf, (value) => {
  if (value) {
    syncForm.syncTypes = syncForm.syncTypes.filter(type => type !== 'financial')
  }
}, { immediate: true })

// 清除缓存
const clearCacheLoading = ref(false)

// 显示同步对话框
function showSyncDialog() {
  syncDialogVisible.value = true
}

// 显示添加持仓对话框
function showAddPositionDialog() {
  addPositionDialogVisible.value = true
}

function onAddPositionSuccess() {
  addPositionDialogVisible.value = false
  // 刷新持仓相关数据
  fetchPositionAnalysisSummary()
  fetchPositionData()
}

async function loadPreferredSyncDataSource() {
  try {
    const sourceState = await loadManualSyncSourceState()
    availableSyncSources.tushare = sourceState.availableSources.tushare
    availableSyncSources.akshare = sourceState.availableSources.akshare
    availableSyncSources.qmt = isJdyunMode() ? false : sourceState.availableSources.qmt

    if (sourceState.preferredSource) {
      // 京东云模式下，若首选是 qmt 则回退
      if (isJdyunMode() && sourceState.preferredSource === 'qmt') {
        // fall through to default selection
      } else {
        syncForm.dataSource = sourceState.preferredSource
        return
      }
    }

    if (availableSyncSources.qmt) {
      syncForm.dataSource = 'qmt'
    } else if (availableSyncSources.akshare) {
      syncForm.dataSource = 'akshare'
    } else if (availableSyncSources.tushare) {
      syncForm.dataSource = 'tushare'
    }
  } catch (error) {
    console.warn('加载同步数据源优先级失败，保留当前默认值', error)
  }
}

const sleep = (ms: number) => new Promise(resolve => window.setTimeout(resolve, ms))

const isTerminalStockSyncStatus = (status?: string): boolean => {
  return status === 'success' || status === 'success_with_errors' || status === 'failed'
}

const buildSingleSyncTaskMessage = (task: StockSyncTaskStatus, symbol: string): string => {
  const result = task.result as SingleStockSyncResponse | null | undefined
  if (!result) {
    return task.error || task.message || `股票 ${symbol} 同步失败`
  }

  const parts = [`股票 ${symbol} 数据同步完成`]

  if (result.realtime_sync) {
    if (result.realtime_sync.success) {
      const dataSourceUsed = (result.realtime_sync as any).data_source_used
      if (dataSourceUsed && dataSourceUsed !== syncForm.dataSource) {
        parts.push(`实时行情同步成功（已自动切换到 ${String(dataSourceUsed).toUpperCase()} 数据源）`)
      } else {
        parts.push('实时行情同步成功')
      }
    } else {
      parts.push(`实时行情同步失败: ${result.realtime_sync.error || '未知错误'}`)
    }
  }

  if (result.historical_sync) {
    parts.push(result.historical_sync.success ? `历史数据 ${result.historical_sync.records || 0} 条` : `历史数据同步失败: ${result.historical_sync.error || '未知错误'}`)
  }
  if (result.financial_sync) {
    parts.push(result.financial_sync.success ? '财务数据同步成功' : `财务数据同步失败: ${result.financial_sync.error || '未知错误'}`)
  }
  if (result.basic_sync) {
    parts.push(result.basic_sync.success ? '基础数据同步成功' : `基础数据同步失败: ${result.basic_sync.error || '未知错误'}`)
  }

  return parts.join('；')
}

const waitForStockSyncTask = async (taskId: string): Promise<StockSyncTaskStatus> => {
  for (let attempt = 0; attempt < STOCK_SYNC_POLL_MAX_ATTEMPTS; attempt += 1) {
    if (stockDetailDisposed) {
      throw new Error('页面已离开，停止等待同步结果')
    }

    const res = await stockSyncApi.getTaskStatus(taskId)
    if (res.success && isTerminalStockSyncStatus(res.data.status)) {
      return res.data
    }

    await sleep(STOCK_SYNC_POLL_INTERVAL_MS)
  }

  throw new Error('同步任务执行超时，请稍后刷新页面查看结果')
}

const monitorSingleSyncTask = async (taskId: string, symbol: string) => {
  try {
    const task = await waitForStockSyncTask(taskId)
    if (stockDetailDisposed) return

    const message = buildSingleSyncTaskMessage(task, symbol)
    if (task.status === 'success') {
      ElMessage.success(message)
    } else if (task.status === 'success_with_errors') {
      ElMessage.warning(message)
    } else {
      ElMessage.error(message)
    }

    await Promise.all([
      fetchQuote(),
      fetchFundamentals(),
      fetchFinancials(),
      fetchKline(),
      fetchSyncStatus(),
    ])
  } catch (error: any) {
    if (!stockDetailDisposed && error?.message !== '页面已离开，停止等待同步结果') {
      ElMessage.error(error?.message || '同步结果查询失败，请稍后刷新页面查看')
    }
  }
}
// 执行同步
async function handleSync() {
  if (syncForm.syncTypes.length === 0) {
    ElMessage.warning('请至少选择一种同步内容')
    return
  }

  syncLoading.value = true
  try {
    const res = await stockSyncApi.syncSingle({
      symbol: code.value,
      sync_realtime: syncForm.syncTypes.includes('realtime'),
      sync_historical: syncForm.syncTypes.includes('historical'),
      sync_financial: syncForm.syncTypes.includes('financial'),
      sync_basic: syncForm.syncTypes.includes('basic'),
      data_source: syncForm.dataSource,
      days: syncForm.days
    })

    if (res.success) {
      ElMessage.success(`股票 ${code.value} 同步任务已提交，后台执行中`)
      syncDialogVisible.value = false
      void monitorSingleSyncTask(res.data.task_id, code.value)
    } else {
      ElMessage.error(res.message || '同步失败')
    }
  } catch (error: any) {
    console.error('同步失败:', error)
    ElMessage.error(error.message || '同步失败，请稍后重试')
  } finally {
    syncLoading.value = false
  }
}

async function refreshMockQuote() {
  // 改为调用后端接口获取真实数据
  await fetchQuote()
}

// 清除缓存
async function clearCache() {
  try {
    await ElMessageBox.confirm(
      '确定要清除所有缓存吗？清除后需要重新从数据源获取数据。',
      '清除缓存',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    clearCacheLoading.value = true
    await clearAllCache()
    ElMessage.success('缓存已清除，正在刷新数据...')

    // 刷新当前页面数据
    await Promise.all([
      fetchQuote(),
      fetchFundamentals(),
      fetchFinancials(),
      fetchKline(),
      fetchNews()
    ])

    ElMessage.success('数据已刷新')
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('清除缓存失败:', error)
      ElMessage.error(error.message || '清除缓存失败')
    }
  } finally {
    clearCacheLoading.value = false
  }
}

async function fetchQuote() {
  // 🔥 参数验证：确保股票代码不为空
  if (!code.value) {
    console.warn('股票代码为空，跳过获取报价')
    return
  }

  try {
    const res = await stocksApi.getQuote(code.value)
    const d: any = (res as any)?.data || {}
    // 后端为 snake_case，前端状态为 camelCase，这里进行映射
    quote.price = Number(d.price ?? d.close ?? quote.price)
    quote.changePercent = Number(d.change_percent ?? quote.changePercent)
    quote.open = Number(d.open ?? quote.open)
    quote.high = Number(d.high ?? quote.high)
    quote.low = Number(d.low ?? quote.low)
    quote.prevClose = Number(d.prev_close ?? quote.prevClose)
    quote.volume = Number.isFinite(d.volume) ? Number(d.volume) : quote.volume
    quote.amount = Number.isFinite(d.amount) ? Number(d.amount) : quote.amount
    quote.turnover = Number.isFinite(d.turnover_rate) ? Number(d.turnover_rate) : quote.turnover
    quote.amplitude = Number.isFinite(d.amplitude) ? Number(d.amplitude) : quote.amplitude

    // 🔥 获取数据日期（用于标注非当天数据）
    quote.tradeDate = d.trade_date || null  // 交易日期（用于成交量、成交额）
    quote.turnoverDate = d.turnover_rate_date || d.trade_date || null
    quote.amplitudeDate = d.amplitude_date || d.trade_date || null
    quote.updatedAt = d.updated_at || null  // 🔥 数据更新时间

    if (d.name) stockName.value = d.name
    market.value = d.market || (isLikelyEtfCode(symbol.value) ? 'ETF' : market.value)
    lastRefreshAt.value = new Date()
  } catch (e) {
    console.error('获取报价失败', e)
  }
}

const etfBasics = reactive({
  fundType: '',
  trackIndex: '',
  fundScale: '' as string | number,
  fundShare: '' as string | number,
  fundShareDate: '',
  management: '',
  custodian: '',
  managementFee: null as string | number | null,
  custodianFee: null as string | number | null,
  unitNav: NaN,
  accumNav: NaN,
  navGrowthRate: null as string | number | null,
  premiumDiscountRate: null as string | number | null,
  latestNavDate: '',
  purchaseStatus: '',
  redemptionStatus: '',
  marketPrice: NaN,
  updatedAt: ''
})

async function fetchFundamentals() {
  try {
    const res = await stocksApi.getFundamentals(code.value)
    const f: any = (res as any)?.data || {}
    // 基本面快照映射（以后台为准）
    if (f.name) stockName.value = f.name
    market.value = f.market || (isLikelyEtfCode(symbol.value) ? 'ETF' : market.value)

    if (f.security_type === 'ETF' || market.value === 'ETF' || isLikelyEtfCode(symbol.value)) {
      detailFactorDiagnostics.value = {}
      detailFactorWarnings.value = {}
      etfBasics.fundType = f.fund_type || f.industry || ''
      etfBasics.trackIndex = f.track_index || f.sector || ''
      etfBasics.fundScale = f.fund_scale || ''
      etfBasics.fundShare = f.fund_share || ''
      etfBasics.fundShareDate = f.fund_share_date || ''
      etfBasics.management = f.management || ''
      etfBasics.custodian = f.custodian || ''
      etfBasics.managementFee = f.management_fee ?? null
      etfBasics.custodianFee = f.custodian_fee ?? null
      etfBasics.unitNav = Number.isFinite(f.unit_nav) ? Number(f.unit_nav) : NaN
      etfBasics.accumNav = Number.isFinite(f.accum_nav) ? Number(f.accum_nav) : NaN
      etfBasics.navGrowthRate = f.nav_growth_rate ?? null
      etfBasics.premiumDiscountRate = f.premium_discount_rate ?? null
      etfBasics.latestNavDate = f.latest_nav_date || ''
      etfBasics.purchaseStatus = f.purchase_status || ''
      etfBasics.redemptionStatus = f.redemption_status || ''
      etfBasics.marketPrice = Number.isFinite(f.market_price) ? Number(f.market_price) : NaN
      etfBasics.updatedAt = f.updated_at || ''
      return
    }

    basics.industry = f.industry || basics.industry
    basics.sector = f.sector || basics.sector || '—'
    // 后端 total_mv 单位：亿元，这里转为元以便与金额格式化函数配合
    basics.marketCap = Number.isFinite(f.total_mv) ? Number(f.total_mv) * 1e8 : basics.marketCap
    // 优先使用 pe_ttm，其次 pe
    basics.pe = Number.isFinite(f.pe_ttm) ? Number(f.pe_ttm) : (Number.isFinite(f.pe) ? Number(f.pe) : basics.pe)
    // 🔥 新增：PB（市净率）
    basics.pb = Number.isFinite(f.pb) ? Number(f.pb) : basics.pb
    // 🔥 新增：PS（市销率）- 优先使用 ps_ttm，其次 ps
    basics.ps = Number.isFinite(f.ps_ttm) ? Number(f.ps_ttm) : (Number.isFinite(f.ps) ? Number(f.ps) : basics.ps)
    // ROE 和负债率
    basics.roe = Number.isFinite(f.roe) ? Number(f.roe) : basics.roe
    const ff: any = f
    basics.debtRatio = Number.isFinite(ff.debt_ratio) ? Number(ff.debt_ratio) : basics.debtRatio
    basics.dividendYield = Number.isFinite(ff.dividend_yield) ? Number(ff.dividend_yield) : basics.dividendYield
    basics.currentRatio = Number.isFinite(ff.current_ratio) ? Number(ff.current_ratio) : basics.currentRatio
    basics.reportPeriod = ff.report_period || basics.reportPeriod
    detailFactorDiagnostics.value = f.factor_diagnostics || {}
    detailFactorWarnings.value = f.factor_warnings || {}

    // 获取PE/PB的实时标识
    basics.peIsRealtime = ff.pe_is_realtime || false
    basics.peSource = ff.pe_source || ''
    basics.peUpdatedAt = ff.pe_updated_at || null
  } catch (e) {
    console.error('获取基本面失败', e)
  }
}

async function fetchFinancials() {
  if (isLikelyEtfCode(symbol.value) || market.value === 'ETF') {
    financialRawSections.value = []
    return
  }

  try {
    const res = await stocksApi.getFinancials(code.value, { includeRaw: true })
    const d: any = (res as any)?.data || {}
    const summary: any = d.summary || {}
    const rawData: Record<string, any[]> = d.raw_data || {}

    basics.dividendYield = Number.isFinite(summary.dividend_yield) ? Number(summary.dividend_yield) : basics.dividendYield
    basics.currentRatio = Number.isFinite(summary.current_ratio) ? Number(summary.current_ratio) : basics.currentRatio
    basics.reportPeriod = summary.report_period || d.report_period || basics.reportPeriod
    basics.roe = Number.isFinite(summary.roe) ? Number(summary.roe) : basics.roe
    basics.debtRatio = Number.isFinite(summary.debt_to_assets) ? Number(summary.debt_to_assets) : basics.debtRatio
    if (Object.keys(detailFactorDiagnostics.value || {}).length === 0 && d.factor_diagnostics) {
      detailFactorDiagnostics.value = d.factor_diagnostics
    }
    if (Object.keys(detailFactorWarnings.value || {}).length === 0 && d.factor_warnings) {
      detailFactorWarnings.value = d.factor_warnings
    }

    financialSnapshot.annDate = summary.ann_date || d.ann_date || ''
    financialSnapshot.dataSource = summary.data_source || d.data_source || ''
    financialSnapshot.grossMargin = Number.isFinite(summary.gross_margin) ? Number(summary.gross_margin) : NaN
    financialSnapshot.netprofitMargin = Number.isFinite(summary.netprofit_margin) ? Number(summary.netprofit_margin) : NaN
    financialSnapshot.revenue = Number.isFinite(summary.revenue) ? Number(summary.revenue) : NaN
    financialSnapshot.netProfit = Number.isFinite(summary.net_profit) ? Number(summary.net_profit) : NaN
    financialSnapshot.nCashflowAct = Number.isFinite(summary.n_cashflow_act) ? Number(summary.n_cashflow_act) : NaN
    financialSnapshot.totalAssets = Number.isFinite(summary.total_assets) ? Number(summary.total_assets) : NaN
    financialSnapshot.totalLiab = Number.isFinite(summary.total_liab) ? Number(summary.total_liab) : NaN

    financialRawSections.value = Object.entries(rawData)
      .filter(([, items]) => Array.isArray(items) && items.length > 0)
      .map(([key, items]) => ({
        key,
        label: financialRawLabels[key] || key,
        count: items.length,
      }))
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    const msg = typeof detail === 'object' ? detail?.message : detail
    if (msg) {
      ElMessage.warning(`${msg}，请点击「同步数据」获取`)
    } else {
      console.error('获取财务明细失败', e)
    }
  }
}

async function fetchSyncStatus() {
  try {
    const res = await ApiClient.get('/api/stock-data/sync-status/quotes')
    const d: any = (res as any)?.data || {}
    syncStatus.value = d
  } catch (e) {
    console.warn('获取同步状态失败', e)
  }
}

let timer: any = null

let authReadyPromise: Promise<void> | null = null

async function ensureAuthReady() {
  if (authReadyPromise) {
    await authReadyPromise
    return
  }

  authReadyPromise = (async () => {
    const storedToken = localStorage.getItem('auth-token')
    const storedRefreshToken = localStorage.getItem('refresh-token')

    if (!authStore.token && storedToken) {
      authStore.token = storedToken
      authStore.isAuthenticated = true
    }

    if (!authStore.refreshToken && storedRefreshToken) {
      authStore.refreshToken = storedRefreshToken
    }

    if (authStore.token) {
      try {
        await authStore.checkAuthStatus()
      } catch (error) {
        console.warn('详情页认证状态恢复失败:', error)
      }
    }
  })()

  try {
    await authReadyPromise
  } finally {
    authReadyPromise = null
  }
}

async function checkFavorite() {
  try {
    const res: any = await favoritesApi.check(code.value)
    const d: any = (res as any)?.data || {}
    isFav.value = !!d.is_favorite
  } catch (e) {
    console.warn('检查关注失败', e)
  }
}
onMounted(async () => {
  stockDetailDisposed = false
  await ensureAuthReady()
  await loadPreferredSyncDataSource()

  // 首次加载：打通后端（并行）
  await Promise.all([
    fetchQuote(),
    fetchFundamentals(),
    fetchFinancials(),
    fetchKline(),
    fetchNews(),
    checkFavorite(),
    fetchLatestAnalysis(),  // 获取最新的历史分析报告
    fetchSyncStatus(),  // 获取同步状态
    fetchPositionAnalysisSummary(),  // 获取持仓分析摘要
    fetchTradeReviewSummary(),  // 获取交易复盘摘要
    fetchReviewHistory(),  // 获取复盘历史列表
    fetchPositionData()  // 获取持仓数据
  ])
  // 每30秒刷新一次报价
  timer = setInterval(fetchQuote, 30000)

  // 初始化股票主题（依赖上面的报告数据，放在 Promise.all 之后）
  // 异步执行不阻塞页面渲染；失败时降级为默认主题
  void initStockAssistantThread()
})
onUnmounted(() => {
  stockDetailDisposed = true
  if (timer) clearInterval(timer)
})



// K线占位相关
const periodOptions = ['日K','周K','月K']
const period = ref('日K')

const klineSource = ref<string | undefined>(undefined)
// 🔥 K线原始数据（供新版 KlineChart 组件使用，含 MA5/MA20 + 成交量）
const klineCategory = ref<string[]>([])
const klineValues = ref<number[][]>([])   // [open, close, low, high]
const klineVolumes = ref<number[]>([])

function periodLabelToParam(p: string): string {
  if (p.includes('5')) return '5m'
  if (p.includes('15')) return '15m'
  if (p.includes('60')) return '60m'
  if (p.includes('日')) return 'day'
  if (p.includes('周')) return 'week'
  if (p.includes('月')) return 'month'
  return '5m'
}

// 当周期切换时刷新K线
watch(period, () => { fetchKline() })

async function fetchKline() {
  await ensureAuthReady()

  try {
    const param = periodLabelToParam(period.value)
    const res = await stocksApi.getKline(code.value, param as any, 200, 'none')
    const d: any = (res as any)?.data || {}
    klineSource.value = d.source
    const items: any[] = Array.isArray(d.items) ? d.items : []

    const category: string[] = []
    const values: number[][] = [] // [open, close, low, high]

    for (const it of items) {
      const t = String(it.time || it.trade_time || it.trade_date || '')
      const o = Number(it.open ?? NaN)
      const h = Number(it.high ?? NaN)
      const l = Number(it.low ?? NaN)
      const c = Number(it.close ?? NaN)
      if (!Number.isFinite(o) || !Number.isFinite(h) || !Number.isFinite(l) || !Number.isFinite(c) || !t) continue
      category.push(t)
      values.push([o, c, l, h])
    }

    if (category.length) {
      lastKTime.value = category[category.length - 1]
      lastKClose.value = values[values.length - 1][1]
    }

    // 🔥 填充新版 KlineChart 组件所需原始数据（含成交量）
    klineCategory.value = category
    klineValues.value = values
    klineVolumes.value = items
      .map((it: any) => Number(it.volume ?? it.vol ?? 0))
      .filter((_v: number, idx: number) => idx < values.length)

    kOption.value = {
      ...kOption.value,
      xAxis: { type: 'category', data: category, boundaryGap: true, axisLine: { onZero: false } },
      series: [
        {
          type: 'candlestick',
          name: 'K线',
          data: values,
          itemStyle: {
            color: '#ef4444',
            color0: '#16a34a',
            borderColor: '#ef4444',
            borderColor0: '#16a34a'
          }
        }
      ]
    }
  } catch (e) {
    console.error('获取K线失败', e)
  }
}


// 新闻
const newsFilter = ref('all')
const newsItems = ref<any[]>([])
const newsLoading = ref(true)
const newsSource = ref<string | undefined>(undefined)

function cleanTitle(s: any): string {
  const t = String(s || '')
  return t.replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').trim()
}

async function fetchNews() {
  newsLoading.value = true
  try {
    const res = await stocksApi.getNews(code.value, 30, 50, true)
    const d: any = (res as any)?.data || {}
    const itemsRaw: any[] = Array.isArray(d.items) ? d.items : []
    newsItems.value = itemsRaw.map((it: any) => {
      const title = cleanTitle(it.title || it.summary || it.name || '')
      const url = it.url || it.link || '#'
      const source = it.source || d.source || ''
      const time = it.time || it.pub_time || it.publish_time || it.pub_date || ''
      const type = it.type || 'news'
      return { title, url, source, time, type }
    })
    newsSource.value = d.source
  } catch (e) {
    console.error('获取新闻失败', e)
  } finally {
    newsLoading.value = false
  }
}

// 基本面（mock）
const basics = reactive({
  industry: '-',
  sector: '-',
  marketCap: NaN,
  pe: NaN,
  pb: NaN,              // 🔥 新增：市净率
  ps: NaN,              // 🔥 新增：市销率
  roe: NaN,
  debtRatio: NaN,
  dividendYield: NaN,
  currentRatio: NaN,
  reportPeriod: '',
  peIsRealtime: false,  // PE是否为实时数据
  peSource: '',         // PE数据来源
  peUpdatedAt: null     // PE更新时间
})

const financialSnapshot = reactive({
  annDate: '',
  dataSource: '',
  grossMargin: NaN,
  netprofitMargin: NaN,
  revenue: NaN,
  netProfit: NaN,
  nCashflowAct: NaN,
  totalAssets: NaN,
  totalLiab: NaN,
})

const financialRawSections = ref<Array<{ key: string; label: string; count: number }>>([])
const detailFactorDiagnostics = ref<StockInfo['factor_diagnostics']>({})
const detailFactorWarnings = ref<StockInfo['factor_warnings']>({})

const financialRawLabels: Record<string, string> = {
  income_statement: '利润表',
  balance_sheet: '资产负债表',
  cashflow_statement: '现金流量表',
  financial_indicators: '财务指标',
  main_business: '主营业务',
}

const detailFactorRow = computed<StockInfo>(() => ({
  symbol: symbol.value,
  name: stockName.value || code.value,
  market: market.value || 'CN',
  factor_diagnostics: detailFactorDiagnostics.value,
  factor_warnings: detailFactorWarnings.value,
}))

const detailFactorWarningEntries = computed(() => getFactorWarningEntries(detailFactorRow.value))
const detailFactorDiagnosticEntries = computed(() => getFactorDiagnosticEntries(detailFactorRow.value))

// 操作
function onAnalyze() {
  router.push({ name: 'SingleAnalysis', query: { stock: code.value } })
}
async function onToggleFavorite() {
  try {
    if (!isFav.value) {
      const payload = {
        symbol: symbol.value,
        stock_code: symbol.value,  // 兼容字段
        stock_name: stockName.value,
        market: market.value
      }
      await favoritesApi.add(payload)
      isFav.value = true
      ElMessage.success('已加入关注列表')
    } else {
      await favoritesApi.remove(code.value)
      isFav.value = false
      ElMessage.success('已移出关注')
    }
  } catch (e: any) {
    console.error('关注操作失败', e)
    ElMessage.error(e?.message || '关注操作失败')
  }
}

function goPaperTrading() {
  router.push({ name: 'PaperTradingHome', query: { code: code.value, market: market.value } })
}

// 获取最新的历史分析报告
async function fetchLatestAnalysis() {
  try {
    const resp = await getTaskList({
      task_type: TaskType.STOCK_ANALYSIS,
      status: TaskStatus.COMPLETED,
      symbol: symbol.value,
      limit: 1
    })

    const tasks = resp?.data?.tasks || []

    if (tasks && tasks.length > 0) {
      const latestTask = tasks[0]

      // 保存任务信息
      lastTaskInfo.value = latestTask

      // 通过 task_id 获取完整结果
      if (latestTask.task_id) {
        try {
          const detailResp = await getTaskDetail(latestTask.task_id)
          const result = detailResp?.data?.result
          if (result) {
            lastAnalysis.value = result
            analysisStatus.value = 'completed'
          }
        } catch (e) {
          console.warn('⚠️ 获取任务结果失败:', e)
        }
      }
    }
  } catch (e) {
    console.warn('⚠️ 获取历史分析报告失败:', e)
  }
}

// ============================================================================
// 持仓分析摘要 & 交易复盘摘要
// 在详情页展示与当前股票相关的最新持仓分析和交易复盘结论
// 数据来源：/api/v2/tasks/list（按 task_type 过滤）+ /api/v2/tasks/{task_id}（拿 result）
// ============================================================================

interface PositionSnapshot {
  cost_price?: number
  current_price?: number
  quantity?: number
  unrealized_pnl?: number
  unrealized_pnl_pct?: number
  holding_days?: number
  position_pct?: number
}

interface PositionSummaryState {
  has: boolean
  taskId: string
  completedAt: string
  snapshot: PositionSnapshot | null
  action: string  // hold/buy/sell/reduce
  confidence: number | null
  conclusion: string
  keyPoints: string[]
}

interface ReviewSummaryState {
  has: boolean
  taskId: string
  completedAt: string
  riskLevel: string
  confidenceScore: number | null
  summary: string
  recommendation: string
  tradeCount: number | null
}

const positionSummary = reactive<PositionSummaryState>({
  has: false,
  taskId: '',
  completedAt: '',
  snapshot: null,
  action: '',
  confidence: null,
  conclusion: '',
  keyPoints: []
})

const reviewSummary = reactive<ReviewSummaryState>({
  has: false,
  taskId: '',
  completedAt: '',
  riskLevel: '',
  confidenceScore: null,
  summary: '',
  recommendation: '',
  tradeCount: null
})

// 复盘历史列表状态
const reviewHistory = reactive<{
  loading: boolean
  items: any[]
  total: number
  selectedIndex: number
}>({
  loading: false,
  items: [],
  total: 0,
  selectedIndex: 0
})

// 复盘详情弹窗状态
const reviewDetailVisible = ref(false)
const reviewDetailLoading = ref(false)
const currentReviewDetail = ref<any>(null)

// 判断任务是否属于当前股票（先从 task 顶层 symbol/code 匹配，再从 task_params 匹配）
function taskMatchesCurrentStock(task: any): boolean {
  const targetCode = symbol.value  // 6位代码（已去掉后缀）
  const targetCodeUpper = code.value  // 完整代码（可能含后缀如 SH）
  const params = task?.task_params || task?.params || {}
  const candidates = [
    task.symbol,        // 从列表 API 的顶层字段匹配
    task.code,
    params.symbol,      // 从 task_params 匹配
    params.code,
    params.stock_code,
    params.symbol_code
  ].filter(Boolean).map((v: any) => String(v).toUpperCase())
  return candidates.some(c => c === targetCode.toUpperCase() || c === targetCodeUpper.toUpperCase() || c.startsWith(targetCode.toUpperCase()))
}

async function fetchPositionAnalysisSummary() {
  try {
    const resp: any = await getTaskList({
      task_type: TaskType.POSITION_ANALYSIS,
      status: TaskStatus.COMPLETED,
      limit: 50
    })
    const tasks = resp?.data?.tasks || resp?.tasks || []
    // 过滤出与当前股票相关的任务，并按完成时间倒序
    const matched = tasks
      .filter((t: any) => taskMatchesCurrentStock(t))
      .sort((a: any, b: any) => {
        const ta = new Date(a.completed_at || a.created_at).getTime()
        const tb = new Date(b.completed_at || b.created_at).getTime()
        return tb - ta
      })

    if (matched.length === 0) {
      positionSummary.has = false
      return
    }

    const latest = matched[0]
    positionSummary.taskId = latest.task_id
    positionSummary.completedAt = latest.completed_at || latest.created_at

    // 拉取任务详情拿 result
    try {
      const detail: any = await getTaskDetail(latest.task_id)
      const result = detail?.data?.result || detail?.result || {}
      const snapshot = result?.position_snapshot || null
      const ai = result?.ai_analysis || {}
      const userView = ai?.user_view || {}

      positionSummary.snapshot = snapshot ? {
        cost_price: snapshot.cost_price,
        current_price: snapshot.current_price,
        quantity: snapshot.quantity,
        unrealized_pnl: snapshot.unrealized_pnl,
        unrealized_pnl_pct: snapshot.unrealized_pnl_pct,
        holding_days: snapshot.holding_days,
        position_pct: snapshot.position_pct
      } : null
      positionSummary.action = ai.action || ''
      positionSummary.confidence = typeof ai.confidence === 'number' ? ai.confidence : null
      positionSummary.conclusion = userView.conclusion || ai.action_reason || ''
      positionSummary.keyPoints = Array.isArray(userView.key_points) ? userView.key_points : []
    } catch (e) {
      console.warn('⚠️ 获取持仓分析详情失败:', e)
    }

    positionSummary.has = true
  } catch (e) {
    console.warn('⚠️ 获取持仓分析摘要失败:', e)
    positionSummary.has = false
  }
}

async function fetchTradeReviewSummary() {
  try {
    const resp: any = await reviewApi.getTradeReviewSummary(code.value)
    const data = resp?.data || {}
    if (!data.has) {
      reviewSummary.has = false
      return
    }
    reviewSummary.taskId = data.task_id || ''
    reviewSummary.completedAt = data.completed_at || ''
    reviewSummary.summary = data.summary || ''
    reviewSummary.recommendation = data.recommendation || ''
    reviewSummary.riskLevel = data.risk_level || ''
    reviewSummary.confidenceScore = data.confidence_score ?? null
    reviewSummary.tradeCount = data.trade_count ?? null
    reviewSummary.has = true
  } catch (e) {
    console.warn('⚠️ 获取交易复盘摘要失败:', e)
    reviewSummary.has = false
  }
}

// 获取当前股票的复盘历史列表
async function fetchReviewHistory() {
  reviewHistory.loading = true
  try {
    const resp: any = await reviewApi.getReviewHistory({
      code: code.value,
      page: 1,
      pageSize: 20
    })
    reviewHistory.items = resp?.data?.items || []
    reviewHistory.total = resp?.data?.total || 0
    reviewHistory.selectedIndex = 0
  } catch (e) {
    console.warn('⚠️ 获取复盘历史失败:', e)
    reviewHistory.items = []
    reviewHistory.total = 0
  } finally {
    reviewHistory.loading = false
  }
}

// 持仓数据状态
const positionData = reactive<{
  loading: boolean
  real: {
    has: boolean
    quantity: number
    cost_price: number
    current_price: number
    market_value: number
    unrealized_pnl: number
    unrealized_pnl_pct: number
  }
  paper: {
    has: boolean
    quantity: number
    cost_price: number
    current_price: number
    market_value: number
    unrealized_pnl: number
    unrealized_pnl_pct: number
  }
}>({
  loading: false,
  real: { has: false, quantity: 0, cost_price: 0, current_price: 0, market_value: 0, unrealized_pnl: 0, unrealized_pnl_pct: 0 },
  paper: { has: false, quantity: 0, cost_price: 0, current_price: 0, market_value: 0, unrealized_pnl: 0, unrealized_pnl_pct: 0 }
})

// 获取当前股票的持仓信息
async function fetchPositionData() {
  positionData.loading = true
  try {
    // 并行获取实盘和模拟持仓
    const [realRes, paperRes] = await Promise.all([
      portfolioApi.getPositions('real').catch(() => ({ success: false, data: { items: [] } })),
      portfolioApi.getPositions('paper').catch(() => ({ success: false, data: { items: [] } }))
    ])

    // 查找当前股票的实盘持仓
    const realPositions = realRes?.data?.items || []
    const realMatch = realPositions.find((p: any) => p.code === symbol.value || p.code === code.value)
    if (realMatch) {
      positionData.real = {
        has: true,
        quantity: realMatch.quantity || 0,
        cost_price: realMatch.cost_price || 0,
        current_price: realMatch.current_price || 0,
        market_value: realMatch.market_value || 0,
        unrealized_pnl: realMatch.unrealized_pnl || 0,
        unrealized_pnl_pct: realMatch.unrealized_pnl_pct || 0
      }
    }

    // 查找当前股票的模拟持仓
    const paperPositions = paperRes?.data?.items || []
    const paperMatch = paperPositions.find((p: any) => p.code === symbol.value || p.code === code.value)
    if (paperMatch) {
      positionData.paper = {
        has: true,
        quantity: paperMatch.quantity || 0,
        cost_price: paperMatch.cost_price || 0,
        current_price: paperMatch.current_price || 0,
        market_value: paperMatch.market_value || 0,
        unrealized_pnl: paperMatch.unrealized_pnl || 0,
        unrealized_pnl_pct: paperMatch.unrealized_pnl_pct || 0
      }
    }
  } catch (e) {
    console.warn('⚠️ 获取持仓数据失败:', e)
  } finally {
    positionData.loading = false
  }
}

// 选择复盘历史项
function selectReviewItem(index: number) {
  reviewHistory.selectedIndex = index
  const item = reviewHistory.items[index]
  if (item) {
    reviewSummary.taskId = item.review_id || item.task_id || ''
    reviewSummary.completedAt = item.completed_at || item.created_at || ''
    reviewSummary.summary = item.summary || ''
    reviewSummary.recommendation = item.recommendation || ''
    reviewSummary.riskLevel = item.risk_level || item.riskLevel || ''
    reviewSummary.confidenceScore = item.confidence_score ?? item.confidenceScore ?? null
    reviewSummary.tradeCount = item.trade_count ?? item.tradeCount ?? null
    reviewSummary.has = true
  }
}

// 查看复盘详情（弹窗展示）
async function viewReviewDetail(reviewId?: string) {
  const targetId = reviewId || reviewSummary.taskId
  if (!targetId) {
    ElMessage.warning('暂无复盘详情')
    return
  }
  
  reviewDetailVisible.value = true
  reviewDetailLoading.value = true
  currentReviewDetail.value = null
  
  try {
    const resp: any = await reviewApi.getReviewDetail(targetId)
    currentReviewDetail.value = resp?.data || resp
  } catch (e) {
    console.warn('⚠️ 获取复盘详情失败:', e)
    ElMessage.error('获取复盘详情失败')
  } finally {
    reviewDetailLoading.value = false
  }
}

// 跳转到持仓分析页面（通过 query 预填股票代码）
function goToPositionAnalysis() {
  router.push({
    path: '/portfolio',
    query: {
      symbol: symbol.value,
      code: code.value
    }
  })
}

// 跳转到交易复盘页面
function goToTradeReview() {
  router.push({
    path: '/review',
    query: {
      symbol: symbol.value,
      code: code.value
    }
  })
}

// 查看持仓分析任务详情（跳转到任务中心）
function viewPositionTaskDetail() {
  if (positionSummary.taskId) {
    router.push({ path: '/tasks/unified', query: { task_id: positionSummary.taskId } })
  }
}

function viewReviewTaskDetail() {
  // 改为本页弹窗展示，不跳转到任务中心
  viewReviewDetail()
}

// 持仓分析相关格式化函数（仅保留对话框所需）

// 格式化盈亏数值
function formatPnlValue(pnl: any): string {
  const n = Number(pnl)
  if (!Number.isFinite(n)) return '-'
  const sign = n > 0 ? '+' : ''
  return `${sign}¥${n.toFixed(2)}`
}

// 获取总盈亏
function getTotalPnl(): number {
  if (!currentReviewDetail.value?.trade_info) return 0
  const info = currentReviewDetail.value.trade_info
  return (info.realized_pnl || 0) + (info.unrealized_pnl || 0)
}

// 获取总收益率
function getTotalPnlPct(): number {
  if (!currentReviewDetail.value?.trade_info) return 0
  const info = currentReviewDetail.value.trade_info
  return info.total_pnl_pct || 0
}

// 格式化百分比
function formatPct(pct: any): string {
  const n = Number(pct)
  if (!Number.isFinite(n)) return '-'
  const sign = n > 0 ? '+' : ''
  return `${sign}${(n * 100).toFixed(2)}%`
}

// fmtConf 已移除：合规要求不展示信心度

// 格式化报告名称
function formatReportName(key: string): string {
  const isEtfAnalysis = Array.isArray(lastAnalysis.value?.analysts) && lastAnalysis.value.analysts.includes('etf_analyst')
  return getReportName(key, isEtfAnalysis)
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function extractMarkdownSection(content: string, heading: string): string {
  if (!content) return ''
  const headingPattern = escapeRegExp(heading)
  const match = content.match(new RegExp(`(?:^|\\n)#{1,6}\\s*${headingPattern}\\s*\\n([\\s\\S]*?)(?=\\n#{1,6}\\s+|$)`, 'i'))
  return match?.[1]?.trim() || ''
}

// 🔥 提取报告内容（支持对象中的 content 字段）
function getReportContent(reportData: any): string {
  if (!reportData) return ''
  
  // 如果是字符串，直接返回
  if (typeof reportData === 'string') {
    return reportData
  }
  
  // 如果是对象，优先提取 content 字段
  if (typeof reportData === 'object') {
    if (reportData.content && typeof reportData.content === 'string') {
      return reportData.content
    }
    if (reportData.markdown && typeof reportData.markdown === 'string') {
      return reportData.markdown
    }
    if (reportData.judge_decision && typeof reportData.judge_decision === 'string') {
      return reportData.judge_decision
    }
  }

  return String(reportData)
}

// 打开指定报告
function openReport(reportKey: string) {
  showReportsDialog.value = true
  activeReportTab.value = reportKey
}

// 导出报告
function exportReport() {
  if (!lastAnalysis.value?.reports) {
    ElMessage.warning('暂无报告可导出')
    return
  }

  // 生成Markdown格式的完整报告
  let fullReport = `# ${code.value} 股票分析报告\n\n`

  // 格式化分析时间用于报告（兼容 completed_at / created_at / end_time）
  const reportTimeSrc = lastTaskInfo.value?.completed_at || lastTaskInfo.value?.created_at || lastTaskInfo.value?.end_time
  const reportTime = reportTimeSrc
    ? new Date(reportTimeSrc).toLocaleString('zh-CN', {
        timeZone: 'Asia/Shanghai',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
      })
    : lastAnalysis.value?.analysis_date

  fullReport += `**分析时间**: ${reportTime}\n`
  fullReport += `**研究观察**: ${lastAnalysis.value.recommendation}\n\n`
  fullReport += `---\n\n`

  for (const [key, content] of Object.entries(lastAnalysis.value.reports)) {
    fullReport += `## ${formatReportName(key)}\n\n`
    fullReport += `${content}\n\n`
    fullReport += `---\n\n`
  }

  // 创建下载链接
  const blob = new Blob([fullReport], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url

  // 使用分析日期作为文件名（简化格式）
  const fileDate = lastAnalysis.value.analysis_date || new Date().toISOString().slice(0, 10)
  link.download = `${code.value}_分析报告_${fileDate}.md`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)

  ElMessage.success('报告已导出')
}

// ============================================================================
// 新版详情页：研究路径 / 智能助手 / 历史导航
// ============================================================================

// 研究路径步骤（根据已加载数据动态计算状态）
const researchFlowSteps = computed<{ key: string; title: string; desc: string; status: 'done' | 'active' | 'pending' }[]>(() => {
  return [
    {
      key: 'kline',
      title: '行情走势',
      desc: 'K线 + 核心指标',
      status: klineValues.value.length > 0 ? 'done' : 'pending',
    },
    {
      key: 'analysis',
      title: '单股分析',
      desc: 'AI 研究报告',
      status: lastAnalysis.value ? 'done' : (analysisStatus.value === 'running' ? 'active' : 'pending'),
    },
    {
      key: 'position-review',
      title: '持仓与复盘',
      desc: '持仓状态 + 交易回顾',
      status: (positionSummary.has || reviewSummary.has) ? 'done' : 'pending',
    },
    {
      key: 'fundamentals',
      title: '基本面',
      desc: '财务数据 + 新闻',
      status: Number.isFinite(basics.pe) || Number.isFinite(financialSnapshot.revenue) ? 'done' : 'pending',
    },
    {
      key: 'assistant',
      title: '智能助手解读',
      desc: '全景涵盖以上所有模块',
      status: 'active',
    },
  ]
})

// 研究路径当前激活步骤（用于 ResearchFlow 高亮）
const activeFlowKey = ref<string>('')

function handleFlowStepClick(key: string) {
  activeFlowKey.value = key
  const idMap: Record<string, string> = {
    kline: 'kline-section',
    analysis: 'analysis-result-section',
    'position-review': 'position-review-section',
    fundamentals: 'bottom-section',
    assistant: 'assistant-chat',
  }
  const targetId = idMap[key]
  if (targetId) {
    const el = document.getElementById(targetId)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }
}

// 智能助手聊天状态
const assistantMessages = ref<Array<{ role: 'user' | 'bot'; content: string }>>([])
const assistantLoading = ref(false)
const assistantInitialPrompt = ref('')
const assistantChatRef = ref<any>(null)

// 股票主题（thread）状态
const stockAssistantThreadId = ref<string>('')
const stockAssistantThreadReady = ref(false)
const stockAssistantStreamController = ref<AbortController | null>(null)

// 已加载模块（用于助手头部展示）
const assistantLoadedModules = computed(() => {
  const mods: string[] = []
  if (klineValues.value.length) mods.push('K线')
  if (lastAnalysis.value) mods.push('单股分析')
  if (positionSummary.has) mods.push('持仓')
  if (reviewSummary.has) mods.push('复盘')
  if (Number.isFinite(basics.pe) || Number.isFinite(financialSnapshot.revenue)) mods.push('基本面')
  return mods
})

// 助手是否已加载各模块（用于 AssistantHero 展示）
const assistantHasAnalysis = computed(() => !!lastAnalysis.value)
const assistantHasPosition = computed(() => positionSummary.has)
const assistantHasReview = computed(() => reviewSummary.has)
const assistantHasFundamentals = computed(() => Number.isFinite(basics.pe) || Number.isFinite(financialSnapshot.revenue))
const assistantHasKline = computed(() => klineValues.value.length > 0)

// 处理助手快捷问题（来自 AssistantHero）
function handleAssistantHeroAsk(prompt: string) {
  assistantInitialPrompt.value = prompt
}

// ════════ 股票主题初始化（对接现有智能助手模块） ════════

const STALE_THRESHOLD_HOURS = 24

// 单股分析报告可用模块目录（用于注入 stock_scope，供 LLM 按需调工具获取完整内容）
// 与后端 core/tools/implementations/assistant_ops/report_query.py 的 _ANALYST_LABELS 保持一致
const STOCK_REPORT_MODULES = [
  { key: 'market_report', title: '市场技术分析', desc: 'K线形态、技术指标、支撑压力位' },
  { key: 'fundamentals_report', title: '基本面研究', desc: '财务数据、估值、行业地位' },
  { key: 'news_report', title: '新闻研究', desc: '近期公告、行业新闻、事件驱动' },
  { key: 'sentiment_report', title: '情绪分析', desc: '社交媒体舆情、机构观点' },
  { key: 'trader_investment_plan', title: '研究整合意见', desc: '多情景研究结论 + 研究观察' },
  { key: 'research_team_decision', title: '研究团队结论', desc: '多情景研究后的团队研究观察汇总' },
  { key: 'risk_management_decision', title: '风险审阅结论', desc: '风险边界 + 后续观察' },
  { key: 'final_trade_decision', title: '综合研究结论', desc: '最终研究观察汇总' },
]

/** 初始化股票主题：创建/获取主题 + 加载历史消息 + 自动关联报告 */
async function initStockAssistantThread() {
  if (!code.value) return
  try {
    const title = `股票研究 · ${code.value} ${stockName.value || ''}`.trim()
    const thread = await assistantApi.createThread(title)
    stockAssistantThreadId.value = thread.thread_id

    // 加载历史消息（若之前已有对话）
    const historyRes = await assistantApi.getThreadMessages(thread.thread_id)
    const hasHistory = !!(historyRes.messages && historyRes.messages.length > 0)
    if (hasHistory) {
      assistantMessages.value = historyRes.messages.map(m => ({
        role: m.role === 'user' ? 'user' as const : 'bot' as const,
        content: m.content,
      }))
    }

    // 自动关联报告（不阻塞主流程）
    void autoLinkReports(thread)
    stockAssistantThreadReady.value = true

    // 仅当首次进入（无历史消息）时，检查报告时效性并主动提醒用户
    if (!hasHistory) {
      checkStaleReportsAndRemind()
    }
  } catch (e) {
    console.warn('初始化股票助手主题失败', e)
    // 失败时降级：仍然允许用户发消息，conversation_id 为空走默认主题
  }
}

/** 检查报告时效性，若有过期报告则主动推一条 bot 消息提醒用户重新分析 */
function checkStaleReportsAndRemind() {
  const scope = buildStockScopeContext()
  const staleItems: string[] = []

  const stockReport = scope.reports?.stock_report
  if (stockReport?.is_stale) {
    staleItems.push(`单股分析报告（${stockReport.completed_at || '未知时间'} 生成，已过期约 ${stockReport.stale_hours} 小时）`)
  }

  const positionReport = scope.reports?.position_report
  if (positionReport?.is_stale) {
    staleItems.push(`持仓分析报告（${positionReport.completed_at || '未知时间'} 生成，已过期约 ${positionReport.stale_hours} 小时）`)
  }

  const reviewData = scope.review_summary
  if (reviewData?.is_stale) {
    staleItems.push(`交易复盘报告（${reviewData.completed_at || '未知时间'} 生成，已过期约 ${reviewData.stale_hours} 小时）`)
  }

  if (staleItems.length === 0) return

  const reminder = [
    `⚠️ 检测到以下报告已过期（超过 ${STALE_THRESHOLD_HOURS} 小时），我不会基于旧报告给出结论：`,
    '',
    ...staleItems.map(s => `• ${s}`),
    '',
    '如果你希望我基于最新数据解读，请点击对应模块的「重新分析」按钮；或在下方回复「重新分析」，我会引导你发起。'
  ].join('\n')

  assistantMessages.value.push({ role: 'bot', content: reminder })
}

/** 自动关联单股分析报告、持仓分析报告、交易复盘报告到主题 */
async function autoLinkReports(thread: AssistantThreadItem) {
  const threadId = thread.thread_id
  const existingKeys = new Set(
    (thread.report_refs || []).map(r => `${r.ref_type}:${r.report_key}`),
  )

  // 关联单股分析报告
  if (lastTaskInfo.value?.task_id) {
    const key = `stock_report:${lastTaskInfo.value.task_id}`
    if (!existingKeys.has(key)) {
      try {
        await assistantApi.attachThreadReport(threadId, 'stock_report', lastTaskInfo.value.task_id)
      } catch (e) {
        console.warn('关联单股分析报告失败', e)
      }
    }
  }

  // 关联持仓分析报告（需要先搜索 candidates 拿到 analysis_id）
  if (positionSummary.has) {
    try {
      const candidates = await assistantApi.getThreadReportCandidates(
        threadId,
        'position_report',
        code.value,
        5,
      )
      const matched = candidates.items.find(
        item => (item.symbol || '').toUpperCase() === code.value.toUpperCase(),
      )
      if (matched) {
        const key = `position_report:${matched.report_key}`
        if (!existingKeys.has(key)) {
          await assistantApi.attachThreadReport(threadId, 'position_report', matched.report_key)
        }
      }
    } catch (e) {
      console.warn('关联持仓分析报告失败', e)
    }
  }

  // 关联交易复盘报告（task_id 即 review_id，直接用 task_id 作为 report_key）
  if (reviewSummary.has && reviewSummary.taskId) {
    const key = `review_report:${reviewSummary.taskId}`
    if (!existingKeys.has(key)) {
      try {
        await assistantApi.attachThreadReport(threadId, 'review_report', reviewSummary.taskId)
      } catch (e) {
        console.warn('关联交易复盘报告失败', e)
      }
    }
  }
}

/** 构建股票上下文（通过 user_context.stock_scope 注入到后端 system prompt） */
function buildStockScopeContext() {
  const now = Date.now()
  const parseTime = (s: string) => (s ? new Date(s).getTime() : 0)
  const calcStale = (ts: number) => {
    if (!ts) return { is_stale: false }
    const hours = Math.round((now - ts) / 3_600_000)
    return { is_stale: hours > STALE_THRESHOLD_HOURS, stale_hours: hours }
  }

  const scope: Record<string, any> = {
    code: code.value,
    stock_name: stockName.value,
    thread_id: stockAssistantThreadId.value,
    reports: {},
  }

  if (lastTaskInfo.value?.task_id) {
    const ts = parseTime(lastTaskInfo.value.completed_at || lastTaskInfo.value.created_at || '')
    // 注入报告目录而非截断摘要正文，LLM 通过 get_report_detail(task_id, module_key) 按需获取完整内容
    const existingKeys = Object.keys(lastAnalysis.value?.reports || {})
    scope.reports.stock_report = {
      task_id: lastTaskInfo.value.task_id,
      completed_at: lastTaskInfo.value.completed_at || lastTaskInfo.value.created_at || '',
      ...calcStale(ts),
      available_modules: STOCK_REPORT_MODULES,
      existing_modules: existingKeys,
    }
  }

  if (positionSummary.has && positionSummary.taskId) {
    const ts = parseTime(positionSummary.completedAt)
    // 持仓报告不注入正文，LLM 通过 get_position_analysis(code, market) 获取完整内容
    scope.reports.position_report = {
      analysis_id: positionSummary.taskId,
      completed_at: positionSummary.completedAt,
      ...calcStale(ts),
    }
  }

  if (reviewSummary.has) {
    const ts = parseTime(reviewSummary.completedAt)
    // 复盘报告不注入正文，LLM 通过 get_trade_review_detail(review_id) 获取完整内容
    // 注意：后端 task_id 即 review_id（见 trade_review_service.py:1908 注释）
    scope.review_summary = {
      task_id: reviewSummary.taskId,
      review_id: reviewSummary.taskId,  // task_id 即 review_id
      completed_at: reviewSummary.completedAt,
      ...calcStale(ts),
      trade_count: reviewSummary.tradeCount ?? undefined,
    }
  }

  if (Number.isFinite(quote.price)) {
    scope.current_quote = {
      price: quote.price,
      change_percent: quote.changePercent,
    }
  }

  return scope
}

// 处理助手发送问题（流式 LLM 对话，对接现有智能助手模块）
async function handleAssistantAsk(prompt: string) {
  if (!prompt.trim() || assistantLoading.value) return

  const conversationId = stockAssistantThreadId.value || undefined
  const stockScope = buildStockScopeContext()

  assistantLoading.value = true

  // 占位一条空的 bot 消息，用于流式追加
  const botMsgIdx = assistantMessages.value.push({ role: 'bot', content: '' }) - 1
  let firstTokenReceived = false

  stockAssistantStreamController.value = assistantApi.chatStream(
    prompt,
    conversationId,
    undefined, // model，使用系统默认
    undefined, // model_config_id
    {
      onToken(content: string) {
        if (!firstTokenReceived) firstTokenReceived = true
        assistantMessages.value[botMsgIdx].content += content
      },
      onDone(data) {
        assistantLoading.value = false
        stockAssistantStreamController.value = null
        // 若服务端返回了 conversation_id（首次创建主题），更新本地
        if (data.conversation_id && !stockAssistantThreadId.value) {
          stockAssistantThreadId.value = data.conversation_id
        }
        // 若回复为空（罕见），给一个友好提示
        if (!assistantMessages.value[botMsgIdx].content.trim()) {
          assistantMessages.value[botMsgIdx].content =
            '抱歉，我暂时无法回答这个问题。请稍后重试。'
        }
      },
      onError(msg: string) {
        assistantLoading.value = false
        stockAssistantStreamController.value = null
        if (!firstTokenReceived) {
          assistantMessages.value[botMsgIdx].content =
            `抱歉，处理您的请求时出错：${msg}\n\n你可以稍后重试，或前往「智能助手」主页面继续对话。`
        } else {
          assistantMessages.value[botMsgIdx].content +=
            `\n\n---\n⚠️ 响应中断：${msg}`
        }
      },
    },
    {
      // extraPayload: 通过 user_context 注入股票上下文
      assistant_role: 'general',
      user_context: {
        stock_scope: stockScope,
      },
    },
  )
}

// 历史记录导航
function goToAnalysisHistory() {
  router.push({ path: '/tasks/unified', query: { type: 'stock_analysis', symbol: code.value } })
}

function goToPositionHistory() {
  router.push({ path: '/tasks/unified', query: { type: 'position_analysis', symbol: code.value } })
}

function goToReviewHistory() {
  router.push({ path: '/tasks/unified', query: { type: 'trade_review', symbol: code.value } })
}

function goToApiGuide() {
  router.push({ name: 'StockDataApiGuide', query: { code: code.value } })
}

// 分析历史记录数量（简化：基于已有报告推断）
const analysisHistoryCount = computed(() => {
  // 实际可从后端获取，这里先用 lastAnalysis 是否存在作为提示
  return lastAnalysis.value ? 1 : 0
})

// 持仓分析历史数量
const positionHistoryCount = computed(() => {
  return positionSummary.has ? 1 : 0
})

// K线周期切换
function handlePeriodChange(p: string) {
  // 仅更新 period，由 watch(period) 自动触发 fetchKline，避免重复请求
  period.value = p
}

</script>

<style scoped lang="scss">
.stock-detail {
  display: flex; flex-direction: column; gap: 16px;
}

/* ════════ 新版详情页布局 ════════ */
.stock-detail-redesign {
  display: flex;
  flex-direction: column;
  gap: 0; /* 子组件自带 margin-bottom */
  padding: 0;
  max-width: 1400px;
  margin: 0 auto;
}

.main-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
  align-items: start;
}

@media (max-width: 1024px) {
  .main-grid {
    grid-template-columns: 1fr;
  }
}

/* 复盘详情对话框样式（保留） */
.review-detail-content {
  .section {
    margin-bottom: 16px;
  }
  .section-title {
    font-size: 15px;
    font-weight: 700;
    margin-bottom: 8px;
    color: var(--el-text-color-primary);
  }
  .summary {
    font-size: 14px;
    line-height: 1.7;
    color: var(--el-text-color-regular);
  }
  .analysis-card {
    padding: 12px;
    border-radius: 8px;
    background: var(--el-fill-color-light);
    h4 {
      font-size: 14px;
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    &.strengths h4 { color: #16a34a; }
    &.weaknesses h4 { color: #ef4444; }
  }
  .suggestions {
    font-size: 13px;
    line-height: 1.7;
    color: var(--el-text-color-regular);
  }
  .positive { color: #ef4444; font-weight: 600; }
  .negative { color: #16a34a; font-weight: 600; }
}

.detail-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px;
  font-size: 14px;
  color: var(--el-text-color-secondary);
}

.reports-dialog {
  .report-content {
    min-height: 500px;
  }
}

.header { display: flex; justify-content: space-between; align-items: center; }
.title { display: flex; flex-direction: column; gap: 8px; }
.title-main { display: flex; align-items: center; gap: 12px; }
.title-meta { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.meta-text { font-size: 12px; color: var(--el-text-color-secondary); }
.code { font-size: 22px; font-weight: 700; }
.name { font-size: 18px; color: var(--el-text-color-regular); }
.actions { display: flex; gap: 8px; }

.quote-card { border-radius: 12px; }
.quote { display: flex; flex-direction: column; gap: 8px; }
.price-row { display: flex; align-items: center; gap: 12px; }
.price { font-size: 32px; font-weight: 800; }
.change { font-size: 16px; font-weight: 700; }
.up { color: #e53935; }
.down { color: #16a34a; }
.stats { display: grid; grid-template-columns: repeat(8, 1fr); gap: 10px; margin-top: 6px; }
.stats .item { display: flex; flex-direction: column; font-size: 12px; color: var(--el-text-color-secondary); }
.stats .item b { color: var(--el-text-color-primary); font-size: 14px; }

.factor-hints {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.factor-hints-title {
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.factor-hints-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.factor-hint-tag {
  cursor: help;
}

.factor-hint-popover {
  display: flex;
  flex-direction: column;
  gap: 6px;
  line-height: 1.6;
}

.factor-hint-popover-title {
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.factor-hint-line {
  color: var(--el-text-color-regular);
  font-size: 13px;
}

.body { margin-top: 4px; }
.card-hd { display: flex; align-items: center; justify-content: space-between; }
.k-chart { height: 320px; }
.legend { margin-top: 8px; font-size: 12px; color: var(--el-text-color-secondary); }

.news-card .news-list { display: flex; flex-direction: column; }
.news-item { padding: 10px 12px; border-bottom: 1px solid var(--el-border-color-lighter); transition: background-color .2s ease; }
.news-item:last-child { border-bottom: none; }
.news-item:hover { background: var(--el-fill-color-light); border-radius: 8px; }
.news-item .row { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
.news-item .left { display: flex; align-items: flex-start; gap: 8px; flex: 1 1 auto; min-width: 0; }
.news-item .tag { flex: 0 0 auto; }
.news-item .title { font-weight: 600; display: flex; align-items: center; gap: 6px; flex: 1 1 auto; min-width: 0; }
.news-item .title a, .news-item .title span { color: var(--el-text-color-primary); text-decoration: none; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; overflow: hidden; }
.news-item .title a:hover { text-decoration: underline; }
.news-item .ext { color: var(--el-text-color-placeholder); font-size: 14px; }
.news-item .title:hover .ext { color: var(--el-color-primary); }
.news-item .right { color: var(--el-text-color-secondary); font-size: 12px; white-space: nowrap; margin-left: 8px; }
.news-item .meta { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 4px; }

.facts { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.fact { display: flex; flex-direction: column; font-size: 12px; }
.fact b { font-size: 14px; color: var(--el-text-color-primary); }
.financial-card { margin-top: 12px; }
.raw-section-summary { margin-top: 12px; display: flex; flex-direction: column; gap: 8px; }
.raw-title { font-size: 12px; color: var(--el-text-color-secondary); }
.raw-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.raw-hint { font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.5; }

.quick-actions { display: flex; flex-direction: column; gap: 8px; }

@media (max-width: 1024px) {
  .stats { grid-template-columns: repeat(4, 1fr); }
  .header { flex-direction: column; align-items: flex-start; gap: 12px; }
  .actions { flex-wrap: wrap; }
}

/* 报告相关样式 */
.reports-section {
  margin-top: 8px;
}

.reports-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  margin-top: 8px;
}

.reports-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.reports-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding: 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
}

.report-tag {
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 13px;
  padding: 6px 12px;
}

.report-tag:hover {
  transform: translateY(-2px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

/* 报告对话框样式 */
.reports-dialog :deep(.el-dialog__body) {
  padding: 0;
}

.report-content {
  padding: 20px;
}

.markdown-body {
  font-size: 14px;
  line-height: 1.8;
  color: var(--el-text-color-primary);
}

.markdown-body h1 {
  font-size: 24px;
  font-weight: 700;
  margin: 20px 0 16px;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--el-border-color);
}

.markdown-body h2 {
  font-size: 20px;
  font-weight: 600;
  margin: 16px 0 12px;
}

.markdown-body h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 12px 0 8px;
}

.markdown-body p {
  margin: 8px 0;
}

.markdown-body ul, .markdown-body ol {
  margin: 8px 0;
  padding-left: 24px;
}

.markdown-body li {
  margin: 4px 0;
}

.markdown-body code {
  background: var(--el-fill-color-light);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
}

.markdown-body pre {
  background: var(--el-fill-color-light);
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 12px 0;
}

.markdown-body blockquote {
  border-left: 4px solid var(--el-color-primary);
  padding-left: 12px;
  margin: 12px 0;
  color: var(--el-text-color-secondary);
}

.markdown-body table {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
}

.markdown-body th, .markdown-body td {
  border: 1px solid var(--el-border-color);
  padding: 8px 12px;
  text-align: left;
}

.markdown-body th {
  background: var(--el-fill-color-light);
  font-weight: 600;
}

.analysis-detail-card .detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 分析时间元信息 */
.analysis-meta {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 8px 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.analysis-meta .analysis-time {
  display: flex;
  align-items: center;
  gap: 6px;
}

.analysis-meta .el-icon {
  font-size: 14px;
}

/* 同步状态提示 */
.sync-status {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  padding: 8px 12px;
  background: #f0f9ff;
  border-radius: 6px;
  border: 1px solid #bae6fd;
  font-size: 13px;
  color: #0369a1;
}

.sync-status .el-icon {
  font-size: 14px;
  color: #0284c7;
}

.sync-info {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

// ============================================================================
// 持仓分析摘要卡片
// ============================================================================
.position-analysis-card {
  margin-top: 16px;
  border-left: 3px solid var(--el-color-primary);

  .card-hd {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
  }

  .card-hd-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-weight: 600;
    color: var(--el-text-color-primary);
  }

  .card-hd-tag {
    margin-left: 4px;
    font-weight: normal;
  }

  .card-hd-actions {
    display: flex;
    gap: 4px;
  }

  .position-summary {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .snapshot-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    padding: 12px;
    background: var(--el-fill-color-lighter);
    border-radius: 6px;
  }

  .snap-item {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .snap-label {
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }

  .snap-value {
    font-size: 15px;
    color: var(--el-text-color-primary);
  }

  .pnl-positive {
    color: var(--el-color-success);
  }

  .pnl-negative {
    color: var(--el-color-danger);
  }

  .ai-advice {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .advice-row {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 14px;
  }

  .advice-label {
    color: var(--el-text-color-secondary);
  }

  .advice-conclusion {
    display: flex;
    align-items: flex-start;
    gap: 6px;
    padding: 10px 12px;
    background: var(--el-color-primary-light-9);
    border-left: 3px solid var(--el-color-primary);
    border-radius: 4px;
    font-size: 14px;
    line-height: 1.5;
    color: var(--el-text-color-primary);
  }

  .advice-icon {
    color: var(--el-color-primary);
    flex-shrink: 0;
    margin-top: 2px;
  }

  .advice-keypoints {
    padding: 10px 12px;
    background: var(--el-color-warning-light-9);
    border-left: 3px solid var(--el-color-warning);
    border-radius: 4px;
  }

  .keypoints-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--el-color-warning-dark);
    margin-bottom: 6px;
  }

  .keypoints-list {
    margin: 0;
    padding-left: 20px;
    font-size: 13px;
    line-height: 1.6;
    color: var(--el-text-color-regular);
  }
}

// ============================================================================
// 交易复盘摘要卡片
// ============================================================================
.trade-review-card {
  margin-top: 16px;
  border-left: 3px solid var(--el-color-success);

  .card-hd {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
  }

  .card-hd-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-weight: 600;
    color: var(--el-text-color-primary);
  }

  .card-hd-tag {
    margin-left: 4px;
    font-weight: normal;
  }

  .card-hd-actions {
    display: flex;
    gap: 4px;
  }

  .review-summary {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .review-meta {
    display: flex;
    gap: 24px;
    padding: 10px 12px;
    background: var(--el-fill-color-lighter);
    border-radius: 6px;
  }

  .meta-item {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 14px;
  }

  .meta-label {
    color: var(--el-text-color-secondary);
  }

  .meta-value {
    color: var(--el-text-color-primary);
  }

  .review-conclusion,
  .review-recommendation {
    padding: 10px 12px;
    background: var(--el-fill-color-lighter);
    border-radius: 6px;
  }

  .review-recommendation {
    background: var(--el-color-success-light-9);
  }

  .conclusion-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    font-weight: 600;
    color: var(--el-text-color-secondary);
    margin-bottom: 6px;
  }

  .conclusion-text {
    font-size: 14px;
    line-height: 1.6;
    color: var(--el-text-color-primary);
  }
}

// ============================================================================
// 复盘详情弹窗
// ============================================================================
.detail-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  gap: 8px;
  color: var(--el-text-color-secondary);
}

.review-detail-content {
  .detail-section {
    margin-bottom: 24px;

    &:last-child {
      margin-bottom: 0;
    }
  }

  .section-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--el-text-color-primary);
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--el-border-color-lighter);
  }

  .content-box {
    padding: 12px;
    background: var(--el-fill-color-lighter);
    border-radius: 6px;
  }

  .review-list {
    padding-left: 20px;
    margin: 0;

    li {
      margin-bottom: 8px;
      font-size: 14px;
      line-height: 1.6;
      color: var(--el-text-color-primary);

      &:last-child {
        margin-bottom: 0;
      }
    }
  }
}

.pnl-positive {
  color: var(--el-color-success) !important;
}

.pnl-negative {
  color: var(--el-color-danger) !important;
}

.positive {
  color: var(--el-color-success) !important;
}

.negative {
  color: var(--el-color-danger) !important;
}

// 复盘详情完整样式
.review-detail-content {
  .section {
    margin-bottom: 20px;

    .section-title {
      font-size: 15px;
      font-weight: 600;
      color: var(--el-text-color-primary);
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
  }

  .summary {
    padding: 12px;
    background: var(--el-fill-color-light);
    border-radius: 8px;
  }

  .analysis-card {
    padding: 16px;
    border-radius: 8px;
    background: var(--el-bg-color-page);

    h4 {
      margin: 0 0 12px;
      font-size: 14px;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 6px;
    }

    &.strengths {
      background: var(--el-color-success-light-9);
      border: 1px solid var(--el-color-success-light-8);
    }

    &.weaknesses {
      background: var(--el-color-danger-light-9);
      border: 1px solid var(--el-color-danger-light-8);
    }
  }

  .suggestions {
    padding: 12px;
    background: var(--el-color-primary-light-9);
    border-radius: 8px;
  }

  .markdown-content {
    :deep(p) {
      margin: 0 0 8px;
      line-height: 1.6;
      color: var(--el-text-color-primary);

      &:last-child {
        margin-bottom: 0;
      }
    }

    :deep(ul), :deep(ol) {
      padding-left: 20px;
      margin: 0 0 8px;
    }

    :deep(li) {
      margin-bottom: 4px;
      line-height: 1.6;
    }
  }
}

// ============================================================================
// 持仓信息卡片
// ============================================================================
.position-card {
  margin-bottom: 16px;

  .position-info {
    .position-section {
      margin-bottom: 16px;

      &:last-child {
        margin-bottom: 0;
      }
    }

    .position-section-title {
      margin-bottom: 10px;
    }

    .position-grid {
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 12px;

      .pos-item {
        text-align: center;

        .pos-label {
          display: block;
          font-size: 12px;
          color: var(--el-text-color-secondary);
          margin-bottom: 4px;
        }

        .pos-value {
          font-size: 14px;
          font-weight: 600;
          color: var(--el-text-color-primary);

          &.positive {
            color: #f56c6c;
          }

          &.negative {
            color: #67c23a;
          }
        }
      }
    }
  }
}
</style>
