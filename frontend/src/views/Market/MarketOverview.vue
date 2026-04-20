<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2 class="title">股市行情概览</h2>
      </div>
      <div class="actions">
        <el-tag type="info">实时</el-tag>
        <el-button type="primary" @click="refresh">刷新</el-button>
      </div>
    </div>

    <el-dialog v-model="sectorDialogVisible" :title="sectorDialogTitle" width="520px">
      <div class="sector-dialog-list">
        <div v-for="stock in sectorDialogStocks" :key="stock.code" class="sector-dialog-item">
          <span class="sector-dialog-code">{{ stock.code }}</span>
          <span class="sector-dialog-name">{{ stock.name }}</span>
        </div>
        <div v-if="!sectorDialogStocks.length" class="sector-dialog-empty">暂无明细</div>
      </div>
    </el-dialog>
    <el-dialog v-model="sentimentDialogVisible" :title="sentimentDialogTitle" width="520px">
      <div class="sector-dialog-list">
        <div v-for="stock in sentimentDialogStocks" :key="stock.code" class="sector-dialog-item">
          <span class="sector-dialog-code">{{ stock.code }}</span>
          <span class="sector-dialog-name">{{ stock.name }}</span>
        </div>
        <div v-if="!sentimentDialogStocks.length" class="sector-dialog-empty">暂无明细</div>
      </div>
    </el-dialog>
    <el-dialog v-model="conceptDialogVisible" :title="conceptDialogTitle" width="520px">
      <div class="sector-dialog-list">
        <div v-for="stock in conceptDialogStocks" :key="stock.code" class="sector-dialog-item">
          <span class="sector-dialog-code">{{ stock.code }}</span>
          <span class="sector-dialog-name">{{ stock.name || stock.code }}</span>
        </div>
        <div v-if="!conceptDialogStocks.length" class="sector-dialog-empty">暂无明细</div>
      </div>
    </el-dialog>

    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="24">
        <el-card shadow="hover" v-loading="analysisLoading">
          <template #header>
            <div class="card-header">
              <span>涨停分析</span>
              <div class="analysis-actions">
                <el-date-picker
                  v-model="analysisDate"
                  type="date"
                  value-format="YYYY-MM-DD"
                  size="small"
                  @change="loadLimitupAnalysis"
                />
                <el-button size="small" @click="loadLimitupAnalysis">刷新</el-button>
              </div>
            </div>
          </template>
          <div class="zt-title-text">📈 A股涨停概念分析</div>
          <div v-if="limitupAnalysis.selected_date" class="zt-date-text">
            📊 分析日期: {{ limitupAnalysis.selected_date }} (对比前一交易日: {{ limitupAnalysis.previous_date || '-' }})
          </div>

          <div class="zt-subheader-text">📊 市场情绪指标</div>
          <el-row :gutter="12">
            <el-col :xs="24" :sm="8">
              <div
                class="zt-metric-card"
                :class="{ clickable: hasSentimentStocks(limitupAnalysis.sentiment_detail?.yesterday_up) }"
                @click="openSentimentDetail('昨日涨停今日上涨率', limitupAnalysis.sentiment_detail?.yesterday_up)"
              >
                <div class="zt-metric-title">昨日涨停今日上涨率</div>
                <div class="zt-metric-value">{{ formatSentimentText(limitupAnalysis.sentiment.yesterday_up) }}</div>
                <div class="zt-metric-desc">昨日涨停股票今日上涨比例</div>
              </div>
            </el-col>
            <el-col :xs="24" :sm="8">
              <div
                class="zt-metric-card"
                :class="{ clickable: hasSentimentStocks(limitupAnalysis.sentiment_detail?.lianban) }"
                @click="openSentimentDetail('连板晋级率', limitupAnalysis.sentiment_detail?.lianban)"
              >
                <div class="zt-metric-title">连板晋级率</div>
                <div class="zt-metric-value">{{ formatSentimentText(limitupAnalysis.sentiment.lianban) }}</div>
                <div class="zt-metric-desc">昨日涨停今日继续涨停比例</div>
              </div>
            </el-col>
            <el-col :xs="24" :sm="8">
              <div class="zt-metric-card">
                <div class="zt-metric-title">涨停破板率</div>
                <div class="zt-metric-value">{{ formatSentimentText(limitupAnalysis.sentiment.break) }}</div>
                <div class="zt-metric-desc">今日曾触及涨停但未封板比例</div>
              </div>
            </el-col>
          </el-row>

          <div class="zt-subheader-text">📈 涨停和跌停股票数量变化</div>
          <el-row :gutter="12">
            <el-col :xs="24" :sm="8">
              <div class="zt-metric-card">
                <div class="zt-metric-title">上交易日涨跌停数</div>
                <div class="zt-limit-count">
                  <span class="zt-limit-up">{{ limitupAnalysis.limit_change.previous_up }}</span>
                  <span class="zt-limit-separator">/</span>
                  <span class="zt-limit-down">{{ limitupAnalysis.limit_change.previous_down }}</span>
                </div>
              </div>
            </el-col>
            <el-col :xs="24" :sm="8">
              <div class="zt-metric-card">
                <div class="zt-metric-title">选定日期涨跌停数</div>
                <div class="zt-limit-count">
                  <span class="zt-limit-up">{{ limitupAnalysis.limit_change.selected_up }}</span>
                  <span class="zt-limit-separator">/</span>
                  <span class="zt-limit-down">{{ limitupAnalysis.limit_change.selected_down }}</span>
                </div>
              </div>
            </el-col>
            <el-col :xs="24" :sm="8">
              <div class="zt-metric-card">
                <div class="zt-metric-title">涨跌停变化</div>
                <div class="zt-limit-count">
                  <span :class="limitupAnalysis.limit_change.up_change >= 0 ? 'zt-limit-up' : 'zt-limit-down'">
                    {{ formatSigned(limitupAnalysis.limit_change.up_change) }}
                  </span>
                  <span class="zt-limit-separator">/</span>
                  <span :class="limitupAnalysis.limit_change.down_change >= 0 ? 'zt-limit-down' : 'zt-limit-up'">
                    {{ formatSigned(limitupAnalysis.limit_change.down_change) }}
                  </span>
                </div>
              </div>
            </el-col>
          </el-row>

          <div class="zt-subheader-text">📶 连板晋级率分析</div>
          <div v-if="limitupAnalysis.promotion_rates.length" class="zt-promotion-grid">
            <div v-for="item in limitupAnalysis.promotion_rates" :key="`${item.from}-${item.to}`" class="zt-promotion-card">
              <div class="zt-promotion-title">
                <span>{{ item.from }} → {{ item.to }}板</span>
                <span class="zt-promotion-count">{{ item.success }}/{{ item.total }}</span>
              </div>
              <div class="zt-promotion-rate">
                <span>晋级率:</span>
                <span class="zt-promotion-rate-value" :class="promotionRateClass(item)">
                  {{ formatPromotionText(item) }}
                </span>
              </div>
              <div class="zt-progress-bar">
                <div class="zt-progress-fill" :style="promotionRateStyle(item)"></div>
              </div>
              <div v-if="item.stocks && item.stocks.length">
                <div v-for="stock in item.stocks" :key="stock.code" class="zt-stock-item">
                  <span class="zt-stock-name">{{ stock.name || stock.code }}</span>
                  <span class="zt-stock-concept" :title="stock.reason || ''">{{ stock.reason || '-' }}</span>
                </div>
              </div>
              <div v-else class="zt-empty-state">暂无股票</div>
            </div>
          </div>
          <div v-else class="zt-empty-state">没有可用的晋级率数据</div>

          <div class="zt-subheader-text">🧩 涨停概念分析</div>
          <div v-if="limitupAnalysis.concepts.length" ref="conceptChartRef" class="zt-chart-container"></div>
          <el-table v-if="limitupAnalysis.concepts.length" :data="limitupAnalysis.concepts" class="zt-table" stripe>
            <el-table-column prop="concept" label="概念" min-width="140" />
            <el-table-column prop="yesterday" label="昨日" width="90" align="right" />
            <el-table-column prop="today" label="今日" width="90" align="right" />
            <el-table-column label="变化" width="90" align="right">
              <template #default="{ row }">
                <span :class="row.change >= 0 ? 'zt-change-up' : 'zt-change-down'">{{ formatSigned(row.change) }}</span>
              </template>
            </el-table-column>
          </el-table>
          <div v-else class="zt-empty-state">没有可用的概念分析数据</div>

          <div class="zt-subheader-text">🏷️ 板块涨停分布</div>
          <div v-if="sectorLimitUp.length" class="sector-limitup-grid">
            <div v-for="item in sectorLimitUp" :key="item.name" class="sector-limitup-item">
              <span class="sector-limitup-name">{{ item.name }}</span>
              <el-tag type="danger" effect="plain" class="clickable" @click="openSectorDetail(item)">{{ item.count }}</el-tag>
            </div>
          </div>
          <div v-else class="zt-empty-state">暂无板块涨停分布</div>

          <div class="zt-subheader-text">🏆 连续涨停天数分析</div>
          <el-table v-if="limitupAnalysis.continuous.length" :data="limitupAnalysis.continuous" class="zt-table" stripe>
            <el-table-column prop="days" label="连板数" width="90" align="right" />
            <el-table-column prop="name" label="股票简称" min-width="120" />
            <el-table-column label="最新价" width="100" align="right">
              <template #default="{ row }">
                {{ formatNumber(row.price) }}
              </template>
            </el-table-column>
            <el-table-column prop="reason" label="涨停原因类别" min-width="180" show-overflow-tooltip />
            <el-table-column prop="first_time" label="首次涨停时间" width="120" />
            <el-table-column prop="last_time" label="最终涨停时间" width="120" />
            <el-table-column label="涨停封单量" width="120" align="right">
              <template #default="{ row }">
                {{ formatVolume(row.order_volume) }}
              </template>
            </el-table-column>
            <el-table-column label="涨停封单额" width="120" align="right">
              <template #default="{ row }">
                {{ formatAmount(row.order_amount) }}
              </template>
            </el-table-column>
            <el-table-column prop="limit_type" label="涨停类型" width="120" />
          </el-table>
          <div v-else class="zt-empty-state">没有连续涨停数据</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :xs="24" :lg="12">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>热门板块</span>
              <div class="sort-actions">
                <el-button size="small" :type="sectorSort === 'change' ? 'primary' : 'default'" @click="sectorSort = 'change'">
                  按涨跌幅排序
                </el-button>
                <el-button size="small" :type="sectorSort === 'volume' ? 'primary' : 'default'" @click="sectorSort = 'volume'">
                  按成交量排序
                </el-button>
              </div>
            </div>
          </template>
          <div class="sector-list">
            <div v-for="item in sortedSectors" :key="item.name" class="sector-item">
              <div class="sector-name">{{ item.name }}</div>
              <div class="sector-change" :class="trendClass(item.chg)">
                {{ formatPercent(item.chg) }}
                <span class="arrow">{{ (item.chg ?? 0) >= 0 ? '▲' : '▽' }}</span>
              </div>
              <div class="sector-volume">成交量 {{ formatAmount(item.volume) }}</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="12">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>{{ watchlistTitle }}</span>
              <el-button text size="small" @click="openFavorites">编辑</el-button>
            </div>
          </template>
          <div class="watch-list">
            <div v-for="item in watchlist" :key="item.code" class="watch-item">
              <div class="watch-main">
                <div class="watch-code">{{ item.code }}</div>
                <div class="watch-name">{{ item.name }}</div>
              </div>
              <div class="watch-price">{{ formatNumber(item.price) }}</div>
              <div class="watch-change" :class="trendClass(item.chg)">
                {{ formatPercent(item.chg) }}
                <span class="arrow">{{ (item.chg ?? 0) >= 0 ? '▲' : '▽' }}</span>
              </div>
              <div class="watch-volume">成交量：{{ formatAmount(item.volume) }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, nextTick, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { stocksApi } from '@/api/stocks'

type SectorItem = {
  name: string
  chg?: number
  volume?: number
}

type WatchItem = {
  code: string
  name: string
  price?: number
  chg?: number
  volume?: number
}

type MetricItem = {
  name: string
  value: string
  desc: string
}

type SectorLimitUp = {
  name: string
  count: number
  stocks?: Array<{
    code: string
    name: string
  }>
}

type LimitupAnalysisSentimentItem = {
  success: number
  total: number
  rate?: number | null
}

type LimitupAnalysisSentimentDetailItem = {
  success: number
  total: number
  stocks?: Array<{
    code: string
    name?: string
    reason?: string
  }>
}

type LimitupAnalysisSentimentDetail = {
  yesterday_up: LimitupAnalysisSentimentDetailItem
  lianban: LimitupAnalysisSentimentDetailItem
  break: LimitupAnalysisSentimentDetailItem
}

type LimitupAnalysisLimitChange = {
  selected_up: number
  selected_down: number
  previous_up: number
  previous_down: number
  up_change: number
  down_change: number
}

type LimitupAnalysisConceptItem = {
  concept: string
  today: number
  yesterday: number
  change: number
  today_stocks?: Array<{
    code: string
    name?: string
  }>
  yesterday_stocks?: Array<{
    code: string
    name?: string
  }>
}

type LimitupAnalysisContinuousItem = {
  code: string
  name?: string
  days?: number
  price?: number
  reason?: string
  first_time?: string
  last_time?: string
  order_volume?: number
  order_amount?: number
  limit_type?: string
}

type LimitupAnalysisPromotionRate = {
  from: number
  to: number
  success: number
  total: number
  rate?: number | null
  stocks?: Array<{
    code: string
    name?: string
    reason?: string
  }>
}

type LimitupAnalysis = {
  selected_date?: string | null
  previous_date?: string | null
  sentiment: {
    yesterday_up: LimitupAnalysisSentimentItem
    lianban: LimitupAnalysisSentimentItem
    break: LimitupAnalysisSentimentItem
  }
  sentiment_detail: LimitupAnalysisSentimentDetail
  limit_change: LimitupAnalysisLimitChange
  concepts: LimitupAnalysisConceptItem[]
  continuous: LimitupAnalysisContinuousItem[]
  promotion_rates: LimitupAnalysisPromotionRate[]
}

const sectorSort = ref<'change' | 'volume'>('change')

const sectors = ref<SectorItem[]>([])
const watchlist = ref<WatchItem[]>([])
const metrics = ref<MetricItem[]>([])
const sectorLimitUp = ref<SectorLimitUp[]>([])
const analysisDate = ref<string>()
const analysisLoading = ref(false)
const limitupAnalysis = ref<LimitupAnalysis>({
  selected_date: null,
  previous_date: null,
  sentiment: {
    yesterday_up: { success: 0, total: 0, rate: null },
    lianban: { success: 0, total: 0, rate: null },
    break: { success: 0, total: 0, rate: null }
  },
  sentiment_detail: {
    yesterday_up: { success: 0, total: 0, stocks: [] },
    lianban: { success: 0, total: 0, stocks: [] },
    break: { success: 0, total: 0, stocks: [] }
  },
  limit_change: {
    selected_up: 0,
    selected_down: 0,
    previous_up: 0,
    previous_down: 0,
    up_change: 0,
    down_change: 0
  },
  concepts: [],
  continuous: [],
  promotion_rates: []
})
const sectorDialogVisible = ref(false)
const sectorDialogTitle = ref('')
const sectorDialogStocks = ref<Array<{ code: string; name: string }>>([])
const sentimentDialogVisible = ref(false)
const sentimentDialogTitle = ref('')
const sentimentDialogStocks = ref<Array<{ code: string; name: string }>>([])
const conceptDialogVisible = ref(false)
const conceptDialogTitle = ref('')
const conceptDialogStocks = ref<Array<{ code: string; name?: string }>>([])
const conceptChartRef = ref<HTMLElement>()
let conceptChart: echarts.ECharts | null = null

const watchlistSource = ref<'favorites' | 'market'>('favorites')
const router = useRouter()

const sortedSectors = computed(() => {
  const list = [...sectors.value]
  if (sectorSort.value === 'volume') {
    return list.sort((a, b) => (b.volume ?? 0) - (a.volume ?? 0))
  }
  return list.sort((a, b) => (b.chg ?? 0) - (a.chg ?? 0))
})

const metricDisplay = computed<MetricItem[]>(() => {
  const list = metrics.value || []
  if (!list.length) {
    return [
      { name: '市场成交额', value: '-', desc: '全市场成交额' },
      { name: '平均市盈率', value: '-', desc: '动态市盈率均值' },
      { name: '平均换手率', value: '-', desc: '全市场换手率均值' },
      { name: '涨跌家数', value: '-', desc: '上涨/下跌家数' }
    ]
  }
  return list.map((item) => ({
    name: item.name || '-',
    value: item.value || '-',
    desc: item.desc || ''
  }))
})

const watchlistTitle = computed(() => (watchlistSource.value === 'market' ? '热门关注' : '我的自选股'))

function refresh() {
  loadOverview()
}

function openSectorDetail(item: SectorLimitUp) {
  sectorDialogTitle.value = `${item.name} 涨停明细`
  sectorDialogStocks.value = item.stocks || []
  sectorDialogVisible.value = true
}

function openFavorites() {
  router.push('/favorites')
}

function hasSentimentStocks(item?: LimitupAnalysisSentimentDetailItem) {
  return !!(item && item.stocks && item.stocks.length)
}

function openSentimentDetail(title: string, item?: LimitupAnalysisSentimentDetailItem) {
  if (!item || !item.stocks || !item.stocks.length) return
  sentimentDialogTitle.value = `${title} 分子股票`
  sentimentDialogStocks.value = item.stocks.map((stock) => ({
    code: stock.code,
    name: stock.name || stock.code
  }))
  sentimentDialogVisible.value = true
}

function openConceptStocks(concept: string, seriesName: string) {
  const item = limitupAnalysis.value.concepts.find((entry) => entry.concept === concept)
  if (!item) return
  const stocks = seriesName === '昨日' ? item.yesterday_stocks || [] : item.today_stocks || []
  conceptDialogTitle.value = `${concept} ${seriesName} 涨停股票`
  conceptDialogStocks.value = stocks
  conceptDialogVisible.value = true
}

function formatNumber(n?: number) {
  if (n === undefined || n === null || Number.isNaN(n)) return '-'
  const s = Number(n).toFixed(2)
  const [a, b] = s.split('.')
  const withSep = a.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  return `${withSep}.${b}`
}

function formatPercent(n?: number) {
  if (n === undefined || n === null || Number.isNaN(n)) return '-'
  const v = Number(n)
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`
}

function formatSigned(n?: number) {
  if (n === undefined || n === null || Number.isNaN(n)) return '-'
  const v = Number(n)
  return `${v >= 0 ? '+' : ''}${v}`
}

function formatSentimentText(item: LimitupAnalysisSentimentItem) {
  const total = item.total ?? 0
  const success = item.success ?? 0
  if (!total) return `${success}/${total}`
  const rate = item.rate ?? success / total
  return `${success}/${total}=${(Number(rate) * 100).toFixed(1)}%`
}

function formatPromotionText(item: LimitupAnalysisPromotionRate) {
  const total = item.total ?? 0
  const success = item.success ?? 0
  if (!total) return `${success}/${total}`
  const rate = item.rate ?? success / total
  return `${success}/${total}=${(Number(rate) * 100).toFixed(1)}%`
}

function promotionRateClass(item: LimitupAnalysisPromotionRate) {
  const total = item.total ?? 0
  const rate = item.rate ?? (total ? item.success / total : 0)
  return rate >= 0.5 ? 'zt-change-up' : 'zt-change-down'
}

function promotionRateStyle(item: LimitupAnalysisPromotionRate) {
  const total = item.total ?? 0
  const rate = item.rate ?? (total ? item.success / total : 0)
  const width = Math.min(100, Number(rate) * 100)
  const color = rate >= 0.5 ? '#e74c3c' : '#27ae60'
  return { width: `${width}%`, background: color }
}

function renderConceptChart() {
  if (!conceptChartRef.value) return
  if (!conceptChart) {
    conceptChart = echarts.init(conceptChartRef.value)
  }
  const data = limitupAnalysis.value.concepts || []
  const categories = data.map((item) => item.concept)
  const option = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['昨日', '今日'] },
    grid: { left: 40, right: 16, top: 30, bottom: 40 },
    xAxis: { type: 'category', data: categories },
    yAxis: { type: 'value', name: '出现次数' },
    series: [
      {
        name: '昨日',
        type: 'bar',
        data: data.map((item) => item.yesterday),
        itemStyle: { color: '#3498db' }
      },
      {
        name: '今日',
        type: 'bar',
        data: data.map((item) => item.today),
        itemStyle: { color: '#e74c3c' }
      }
    ]
  }
  conceptChart.setOption(option)
  conceptChart.off('click')
  conceptChart.on('click', (params: any) => {
    if (!params || params.componentType !== 'series') return
    openConceptStocks(params.name, params.seriesName || '今日')
  })
}

function formatAmount(n?: number) {
  if (n === undefined || n === null || Number.isNaN(n)) return '-'
  const v = Number(n)
  if (Math.abs(v) >= 1e8) return `${(v / 1e8).toFixed(2)}亿`
  if (Math.abs(v) >= 1e4) return `${(v / 1e4).toFixed(2)}万`
  return v.toFixed(2)
}

function formatVolume(n?: number) {
  if (n === undefined || n === null || Number.isNaN(n)) return '-'
  const v = Number(n)
  if (Math.abs(v) >= 1e4) return `${(v / 1e4).toFixed(2)}万`
  return v.toFixed(0)
}

function trendClass(n?: number) {
  return (n ?? 0) >= 0 ? 'up' : 'down'
}

async function loadOverview() {
  try {
    const res = await stocksApi.getMarketOverview(12)
    if (res.success && res.data) {
      sectors.value = res.data.sectors || []
      watchlist.value = res.data.watchlist || []
      watchlistSource.value = res.data.watchlist_source || 'favorites'
      metrics.value = res.data.metrics || []
      sectorLimitUp.value = res.data.sector_limitup || []
      return
    }
    ElMessage.error('获取行情概览失败')
  } catch (e) {
    ElMessage.error('获取行情概览失败')
  }
}

loadOverview()

async function loadLimitupAnalysis() {
  try {
    analysisLoading.value = true
    const res = await stocksApi.getLimitupAnalysis(analysisDate.value)
    if (res.success && res.data) {
      const sentimentDetail = res.data.sentiment_detail || {
        yesterday_up: { success: 0, total: 0, stocks: [] },
        lianban: { success: 0, total: 0, stocks: [] },
        break: { success: 0, total: 0, stocks: [] }
      }
      limitupAnalysis.value = {
        ...res.data,
        sentiment_detail: sentimentDetail
      }
      analysisDate.value = res.data.selected_date || analysisDate.value
      await nextTick()
      if (limitupAnalysis.value.concepts.length) {
        renderConceptChart()
      }
      return
    }
    ElMessage.error('获取涨停分析失败')
  } catch (e) {
    ElMessage.error('获取涨停分析失败')
  } finally {
    analysisLoading.value = false
  }
}

loadLimitupAnalysis()

onBeforeUnmount(() => {
  if (conceptChart) {
    conceptChart.dispose()
    conceptChart = null
  }
})
</script>

<style lang="scss" scoped>
.page {
  .page-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 16px;

    .title {
      margin: 0;
      font-size: 22px;
      font-weight: 700;
      color: var(--el-text-color-primary);
    }
    .subtitle {
      margin-top: 6px;
      font-size: 13px;
      color: var(--el-text-color-regular);
    }
    .actions {
      display: flex;
      align-items: center;
      gap: 10px;
    }
  }

  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .card-subtitle {
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }
  .sort-actions {
    display: flex;
    gap: 8px;
  }

  .sentiment-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 12px;
  }
  .sentiment-item {
    padding: 12px;
    border-radius: 10px;
    background: var(--el-fill-color-light);
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .sentiment-label {
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }
  .sentiment-value {
    font-size: 18px;
    font-weight: 700;
  }

  .limit-change-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
  }
  .limit-block {
    padding: 12px;
    border-radius: 10px;
    background: var(--el-fill-color-light);
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .limit-title {
    font-weight: 600;
  }
  .limit-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 13px;
    color: var(--el-text-color-regular);
  }
  .limit-row strong {
    color: var(--el-text-color-primary);
  }
  .limit-block .up {
    color: #e53935;
  }
  .limit-block .down {
    color: #2e7d32;
  }

  .promotion-title {
    margin-top: 12px;
    font-size: 13px;
    color: var(--el-text-color-secondary);
  }
  .promotion-grid {
    margin-top: 8px;
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
  }
  .promotion-item {
    flex: 1 1 160px;
    padding: 12px 10px;
    border-radius: 8px;
    background: var(--el-fill-color-lighter);
    display: flex;
    flex-direction: column;
    gap: 8px;
    border: 1px solid var(--el-border-color-light);
    transition: background 0.2s;
  }
  .promotion-item:hover {
    background: var(--el-fill-color-light);
  }
  .promotion-stocks {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .promotion-stock {
    padding: 2px 8px;
    border-radius: 12px;
    background: var(--el-color-primary-light-9);
    color: var(--el-color-primary);
    font-size: 12px;
    border: 1px solid var(--el-color-primary-light-7);
  }
  .promotion-label {
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }
  .promotion-value {
    font-size: 16px;
    font-weight: 700;
  }
  .promotion-empty {
    margin-top: 8px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }

  .sector-limitup-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: 10px;
  }
  .sector-limitup-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 10px;
    border-radius: 10px;
    background: var(--el-fill-color-light);
    font-size: 12px;
  }
  .sector-limitup-name {
    font-weight: 600;
  }
  .clickable {
    cursor: pointer;
  }
  .sector-dialog-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-height: 360px;
    overflow-y: auto;
  }
  .sector-dialog-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 10px;
    border-radius: 8px;
    background: var(--el-fill-color-light);
  }
  .sector-dialog-code {
    font-weight: 600;
  }
  .sector-dialog-name {
    color: var(--el-text-color-regular);
  }
  .sector-dialog-empty {
    padding: 12px;
    text-align: center;
    color: var(--el-text-color-secondary);
  }

  .sector-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .sector-item {
    display: grid;
    grid-template-columns: 1fr auto auto;
    gap: 10px;
    align-items: center;
    padding: 10px 12px;
    border-radius: 10px;
    background: var(--el-fill-color-light);
  }
  .sector-name {
    font-weight: 600;
  }
  .sector-change {
    font-weight: 600;
  }
  .sector-change.up {
    color: #e53935;
  }
  .sector-change.down {
    color: #2e7d32;
  }
  .sector-volume {
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }

  .watch-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .watch-item {
    display: grid;
    grid-template-columns: 1.2fr 0.8fr 0.8fr 1fr;
    gap: 10px;
    align-items: center;
    padding: 10px 12px;
    border-radius: 10px;
    background: var(--el-fill-color-light);
  }
  .watch-main {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .watch-code {
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }
  .watch-name {
    font-weight: 600;
  }
  .watch-price {
    font-weight: 600;
  }
  .watch-change {
    font-weight: 600;
  }
  .watch-change.up {
    color: #e53935;
  }
  .watch-change.down {
    color: #2e7d32;
  }
  .watch-volume {
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }

  .metric-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .metric-item {
    padding: 12px;
    border-radius: 10px;
    background: var(--el-fill-color-light);
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .metric-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-weight: 600;
  }
  .metric-value {
    font-size: 18px;
    font-weight: 700;
  }

  .analysis-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .zt-title-text {
    color: #2c3e50;
    font-size: 24px;
    font-weight: 700;
    margin-bottom: 8px;
    text-align: center;
  }
  .zt-date-text {
    text-align: center;
    color: #7f8c8d;
    font-size: 13px;
    margin-bottom: 12px;
  }
  .zt-subheader-text {
    color: #3498db;
    font-size: 16px;
    font-weight: 600;
    margin-top: 16px;
    margin-bottom: 10px;
    border-bottom: 2px solid #3498db;
    padding-bottom: 4px;
  }
  .zt-metric-card {
    background-color: #f8f9fa;
    border-radius: 10px;
    padding: 14px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.08);
    transition: all 0.3s ease;
  }
  .zt-metric-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 6px 12px rgba(0, 0, 0, 0.12);
  }
  .zt-metric-title {
    color: #7f8c8d;
    font-size: 13px;
    font-weight: 500;
    margin-bottom: 6px;
  }
  .zt-metric-value {
    color: #2c3e50;
    font-size: 18px;
    font-weight: 700;
  }
  .zt-metric-desc {
    font-size: 12px;
    color: #7f8c8d;
    margin-top: 6px;
  }
  .zt-limit-count {
    display: flex;
    justify-content: center;
    gap: 8px;
    font-size: 16px;
  }
  .zt-limit-up {
    color: #e74c3c;
    font-weight: 700;
  }
  .zt-limit-down {
    color: #27ae60;
    font-weight: 700;
  }
  .zt-limit-separator {
    color: #7f8c8d;
  }
  .zt-table {
    border-radius: 10px;
    overflow: hidden;
  }
  .zt-chart-container {
    height: 320px;
    margin-bottom: 12px;
  }
  .zt-change-up {
    color: #e74c3c;
    font-weight: 700;
  }
  .zt-change-down {
    color: #27ae60;
    font-weight: 700;
  }
  .zt-empty-state {
    text-align: center;
    padding: 16px;
    color: #7f8c8d;
    font-size: 14px;
  }
  .zt-promotion-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 12px;
  }
  .zt-promotion-card {
    background-color: #f8f9fa;
    border-radius: 10px;
    padding: 12px;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    border-left: 4px solid #3498db;
    transition: all 0.3s ease;
  }
  .zt-promotion-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.14);
  }
  .zt-promotion-title {
    color: #2c3e50;
    font-size: 14px;
    font-weight: 700;
    margin-bottom: 6px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .zt-promotion-count {
    font-size: 12px;
    color: #7f8c8d;
  }
  .zt-promotion-rate {
    display: flex;
    justify-content: space-between;
    color: #3498db;
    font-size: 13px;
    margin-bottom: 6px;
  }
  .zt-promotion-rate-value {
    font-weight: 700;
  }
  .zt-progress-bar {
    height: 4px;
    background: #ecf0f1;
    border-radius: 2px;
    margin: 6px 0;
  }
  .zt-progress-fill {
    height: 100%;
    border-radius: 2px;
  }
  .zt-stock-item {
    padding: 6px 0;
    border-bottom: 1px solid #eee;
    display: flex;
    justify-content: space-between;
    gap: 8px;
  }
  .zt-stock-item:last-child {
    border-bottom: none;
  }
  .zt-stock-name {
    font-weight: 500;
    color: #2c3e50;
  }
  .zt-stock-concept {
    color: #95a5a6;
    font-size: 12px;
    max-width: 160px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

}
</style>
