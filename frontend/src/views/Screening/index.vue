<template>
  <div class="stock-screening">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1 class="page-title">
        <el-icon><Search /></el-icon>
        股票筛选
      </h1>
      <p class="page-description">
        通过多维度筛选条件，快速找到符合投资策略的优质股票
      </p>
    </div>

    <!-- 筛选条件面板 -->
    <el-card class="filter-panel" shadow="never">
      <template #header>
        <div class="card-header">
          <div style="display: flex; align-items: center; gap: 12px;">
            <span>筛选条件</span>
            <el-tag v-if="currentDataSource" type="info" size="small" effect="plain">
              <el-icon style="vertical-align: middle; margin-right: 4px;"><Connection /></el-icon>
              当前数据源: {{ currentDataSource.name }}
              <span v-if="currentDataSource.token_source_display" style="margin-left: 4px; opacity: 0.8;">
                ({{ currentDataSource.token_source_display }})
              </span>
            </el-tag>
            <el-tag v-else type="warning" size="small">
              <el-icon style="vertical-align: middle; margin-right: 4px;"><Warning /></el-icon>
              无可用数据源
            </el-tag>
          </div>
          <div class="header-actions">
            <el-button type="text" @click="resetFilters">
              <el-icon><Refresh /></el-icon>
              重置
            </el-button>
          </div>
        </div>
      </template>

      <el-form :model="filters" label-width="120px" class="filter-form">
        <el-row :gutter="24">
          <!-- 基础信息 -->
          <el-col :span="8">
            <el-form-item label="市场类型">
              <el-select v-model="filters.market" placeholder="选择市场">
                <el-option label="A股" value="A股" />
                <el-option label="美股" value="美股" />
                <el-option label="港股" value="港股" />
              </el-select>
            </el-form-item>
          </el-col>

          <el-col :span="8">
            <el-form-item label="行业分类">
              <el-select
                v-model="filters.industry"
                placeholder="选择行业"
                multiple
                collapse-tags
                collapse-tags-tooltip
              >
                <el-option
                  v-for="industry in industryOptions"
                  :key="industry.value"
                  :label="industry.label"
                  :value="industry.value"
                />
              </el-select>
            </el-form-item>
          </el-col>

          <el-col :span="8">
            <el-form-item label="市值范围">
              <el-select v-model="filters.marketCapRange" placeholder="选择市值范围">
                <el-option label="小盘股 (< 100亿)" value="small" />
                <el-option label="中盘股 (100-500亿)" value="medium" />
                <el-option label="大盘股 (> 500亿)" value="large" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="24">
          <!-- 财务指标 -->
          <el-col :span="8">
            <el-form-item label="市盈率 (PE)">
              <el-input-number
                v-model="filters.peRatio.min"
                placeholder="最小值"
                :min="0"
                :precision="2"
                style="width: 45%"
              />
              <span style="margin: 0 8px">-</span>
              <el-input-number
                v-model="filters.peRatio.max"
                placeholder="最大值"
                :min="0"
                :precision="2"
                style="width: 45%"
              />
            </el-form-item>
          </el-col>

          <el-col :span="8">
            <el-form-item label="市净率 (PB)">
              <el-input-number
                v-model="filters.pbRatio.min"
                placeholder="最小值"
                :min="0"
                :precision="2"
                style="width: 45%"
              />
              <span style="margin: 0 8px">-</span>
              <el-input-number
                v-model="filters.pbRatio.max"
                placeholder="最大值"
                :min="0"
                :precision="2"
                style="width: 45%"
              />
            </el-form-item>
          </el-col>

          <el-col :span="8">
            <el-form-item label="ROE (%)">
              <el-input-number
                v-model="filters.roe.min"
                placeholder="最小值"
                :min="0"
                :max="100"
                :precision="2"
                style="width: 45%"
              />
              <span style="margin: 0 8px">-</span>
              <el-input-number
                v-model="filters.roe.max"
                placeholder="最大值"
                :min="0"
                :max="100"
                :precision="2"
                style="width: 45%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="24">
          <!-- 技术指标 -->
          <el-col :span="8">
            <el-form-item label="涨跌幅 (%)">
              <el-input-number
                v-model="filters.changePercent.min"
                placeholder="最小值"
                :precision="2"
                style="width: 45%"
              />
              <span style="margin: 0 8px">-</span>
              <el-input-number
                v-model="filters.changePercent.max"
                placeholder="最大值"
                :precision="2"
                style="width: 45%"
              />
            </el-form-item>
          </el-col>

          <el-col :span="8">
            <el-form-item label="成交量">
              <el-select v-model="filters.volumeLevel" placeholder="选择成交量水平">
                <el-option label="活跃 (高成交量)" value="high" />
                <el-option label="正常 (中等成交量)" value="medium" />
                <el-option label="清淡 (低成交量)" value="low" />
              </el-select>
            </el-form-item>
          </el-col>

          <!-- 技术形态暂不实现，先隐藏 -->
          <el-col :span="8" v-if="false">
            <el-form-item label="技术形态">
              <el-select
                v-model="filters.technicalPattern"
                placeholder="选择技术形态"
                multiple
                collapse-tags
              >
                <el-option label="突破上升趋势" value="breakout_up" />
                <el-option label="回调买入机会" value="pullback" />
                <el-option label="底部反转" value="bottom_reversal" />
                <el-option label="强势整理" value="consolidation" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 筛选按钮 -->
        <el-row>
          <el-col :span="24">
            <div class="filter-actions">
              <el-button
                type="primary"
                @click="performScreening"
                :loading="screeningLoading"
                size="large"
              >
                <el-icon><Search /></el-icon>
                开始筛选
              </el-button>
              <el-button @click="resetFilters" size="large">
                重置条件
              </el-button>
            </div>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <!-- 筛选结果 -->
    <el-card v-if="screeningResults.length > 0" class="results-panel" shadow="never">
      <template #header>
        <div class="card-header">
          <span>筛选结果 ({{ screeningResults.length }}只股票)</span>
          <div class="header-actions">
            <el-button
              type="primary"
              @click="batchAnalyze"
              :disabled="selectedStocks.length === 0"
            >
              <el-icon><TrendCharts /></el-icon>
              批量分析 ({{ selectedStocks.length }})
            </el-button>
            <el-button type="text" @click="exportResults">
              <el-icon><Download /></el-icon>
              导出结果
            </el-button>
          </div>
        </div>
      </template>

      <!-- 结果表格 -->
      <el-table
        :data="paginatedResults"
        @selection-change="handleSelectionChange"
        stripe
        style="width: 100%"
      >
        <el-table-column type="selection" width="55" />

        <el-table-column prop="code" label="股票代码" width="120">
          <template #default="{ row }">
            <el-link type="primary" @click="viewStockDetail(row)">
              {{ row.code }}
            </el-link>
          </template>
        </el-table-column>

        <el-table-column prop="name" label="股票名称" width="150" />

        <el-table-column prop="industry" label="行业" width="120" />

        <el-table-column prop="close" label="当前价格" width="100" align="right">
          <template #default="{ row }">
            <span v-if="row.close">¥{{ row.close?.toFixed(2) }}</span>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="pct_chg" label="涨跌幅" width="100" align="right">
          <template #default="{ row }">
            <span v-if="row.pct_chg !== null && row.pct_chg !== undefined" :class="getChangeClass(row.pct_chg)">
              {{ row.pct_chg > 0 ? '+' : '' }}{{ row.pct_chg?.toFixed(2) }}%
            </span>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="total_mv" label="市值" width="120" align="right">
          <template #default="{ row }">
            {{ formatMarketCap(row.total_mv) }}
          </template>
        </el-table-column>

        <el-table-column prop="pe" label="市盈率" width="130" align="right">
          <template #default="{ row }">
            <span v-if="row.pe">
              {{ row.pe?.toFixed(2) }}
              <el-tag v-if="row.pe_is_realtime" type="success" size="small" style="margin-left: 4px">实时</el-tag>
            </span>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="pb" label="市净率" width="130" align="right">
          <template #default="{ row }">
            <span v-if="row.pb">
              {{ row.pb?.toFixed(2) }}
              <el-tag v-if="row.pe_is_realtime" type="success" size="small" style="margin-left: 4px">实时</el-tag>
            </span>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="roe" label="ROE(%)" width="110" align="right">
          <template #default="{ row }">
            <span v-if="row.roe !== null && row.roe !== undefined">{{ row.roe?.toFixed(2) }}%</span>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="board" label="板块" width="100">
          <template #default="{ row }">
            {{ row.board || '-' }}
          </template>
        </el-table-column>

        <el-table-column prop="exchange" label="交易所" width="140">
          <template #default="{ row }">
            {{ row.exchange || '-' }}
          </template>
        </el-table-column>

        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button type="text" size="small" @click="analyzeSingle(row)">
              分析
            </el-button>
            <el-button type="text" size="small" @click="toggleFavorite(row)">
              <el-icon><Star /></el-icon>
              {{ isFavorited(row.code) ? '取消自选' : '加入自选' }}
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
          :total="screeningResults.length"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <!-- 空状态 -->
    <el-empty
      v-else-if="!screeningLoading && hasSearched"
      description="未找到符合条件的股票"
      :image-size="200"
    >
      <el-button type="primary" @click="resetFilters">
        重新筛选
      </el-button>
    </el-empty>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Collection, TrendCharts, Download, Star, Setting, Connection, Warning } from '@element-plus/icons-vue'
import type { StockInfo } from '@/types/analysis'
import { screeningApi, type FieldConfigResponse, type FieldInfo } from '@/api/screening'
import { favoritesApi } from '@/api/favorites'
import { getCurrentDataSource } from '@/api/sync'
import { normalizeMarketForAnalysis, exchangeCodeToMarket, getMarketByStockCode } from '@/utils/market'

// 响应式数据
const screeningLoading = ref(false)
const hasSearched = ref(false)
const screeningResults = ref<StockInfo[]>([])
const selectedStocks = ref<StockInfo[]>([])
const currentPage = ref(1)
const pageSize = ref(20)

// 路由 & 自选集
const router = useRouter()
const favoriteSet = ref<Set<string>>(new Set())

// 当前数据源
const currentDataSource = ref<{
  name: string
  priority: number
  description: string
  token_source?: 'database' | 'env'
  token_source_display?: string
} | null>(null)

// 字段配置
const fieldConfig = ref<FieldConfigResponse | null>(null)
const fieldsLoading = ref(false)

// 筛选条件
const filters = reactive({
  market: 'A股',
  industry: [] as string[],
  marketCapRange: '',
  peRatio: { min: null, max: null },
  pbRatio: { min: null, max: null },
  roe: { min: null, max: null },
  changePercent: { min: null, max: null },
  volumeLevel: '',
  technicalPattern: [] as string[]
})

// 行业选项（动态加载）
const industryOptions = ref<Array<{label: string, value: string, count?: number}>>([])

// 计算属性
const paginatedResults = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return screeningResults.value.slice(start, end)
})

// 方法
const performScreening = async () => {
  screeningLoading.value = true
  hasSearched.value = true

  try {
    // 基于用户真实选择构建 conditions（只拼选中的项，不注入默认技术条件）
    const children: any[] = []

    // 市场类型（仅作为演示，实际后端暂用CN）
    if (filters.market) {
      // 可作为 universe 选择；当未实现时可忽略
    }

    // 行业分类（如果用户选择了行业）
    if (filters.industry && filters.industry.length > 0) {
      // 直接使用数据库中的行业名称，无需映射
      children.push({ field: 'industry', op: 'in', value: filters.industry })
    }

    // 市值范围映射为区间（单位：亿元 → 转换为万元以匹配后端 market_cap 单位）
    const capRangeMap: Record<string, [number, number] | null> = {
      small: [0, 100 * 10000], // <100亿 → < 100*1e4 万元
      medium: [100 * 10000, 500 * 10000],
      large: [500 * 10000, Number.MAX_SAFE_INTEGER],
    }
    const cap = filters.marketCapRange ? capRangeMap[filters.marketCapRange] : null
    if (cap) {
      children.push({ field: 'market_cap', op: 'between', value: cap })
    }
    // 市盈率/市净率/ROE 条件（仅当填写任一端时才拼接）
    if (filters.peRatio.min != null || filters.peRatio.max != null) {
      const lo = filters.peRatio.min ?? 0
      const hi = filters.peRatio.max ?? Number.MAX_SAFE_INTEGER
      children.push({ field: 'pe', op: 'between', value: [lo, hi] })
    }
    if (filters.pbRatio.min != null || filters.pbRatio.max != null) {
      const lo = filters.pbRatio.min ?? 0
      const hi = filters.pbRatio.max ?? Number.MAX_SAFE_INTEGER
      children.push({ field: 'pb', op: 'between', value: [lo, hi] })
    }
    if (filters.roe.min != null || filters.roe.max != null) {
      const lo = filters.roe.min ?? 0
      const hi = filters.roe.max ?? 100
      children.push({ field: 'roe', op: 'between', value: [lo, hi] })
    }


    // 明确指定：不加任何技术指标相关条件

    const payload = {
      market: 'CN',
      date: undefined,
      adj: 'qfq',
      conditions: { logic: 'AND', children },
      order_by: [{ field: 'market_cap', direction: 'desc' }],
      limit: 500,
      offset: 0,
    }

    const res = await screeningApi.run(payload, { timeout: 120000 })
    const data = (res as any)?.data || res // ApiClient封装会返回 {success,data} 格式
    const items = data?.items || []

    // 直接使用后端返回的数据，字段名已统一
    screeningResults.value = items.map((it: any) => ({
      symbol: it.symbol || it.code,  // 主字段
      code: it.symbol || it.code,    // 兼容字段
      name: it.name || it.symbol || it.code,  // 使用股票名称，如果没有则用代码
      market: it.market || 'A股',
      industry: it.industry,
      area: it.area,
      board: it.board,  // 板块（主板、创业板、科创板等）
      exchange: it.exchange,  // 交易所（上海证券交易所、深圳证券交易所等）

      // 市值信息
      total_mv: it.total_mv,
      circ_mv: it.circ_mv,

      // 财务指标
      pe: it.pe,
      pb: it.pb,
      pe_ttm: it.pe_ttm,
      pb_mrq: it.pb_mrq,
      roe: it.roe,

      // 交易数据
      close: it.close,
      pct_chg: it.pct_chg,
      amount: it.amount,
      turnover_rate: it.turnover_rate,
      volume_ratio: it.volume_ratio,

      // 技术指标
      ma20: it.ma20,
      rsi14: it.rsi14,
      kdj_k: it.kdj_k,
      kdj_d: it.kdj_d,
      kdj_j: it.kdj_j,
      dif: it.dif,
      dea: it.dea,
      macd_hist: it.macd_hist,
    }))

    ElMessage.success(`筛选完成，找到 ${screeningResults.value.length} 只股票`)
  } catch (error) {
    ElMessage.error('筛选失败，请重试')
  } finally {
    screeningLoading.value = false
  }
}

const generateMockResults = (): StockInfo[] => {
  const mockStocks = [
    { code: '000001', name: '平安银行', industry: '银行', close: 12.50, pct_chg: 2.1, total_mv: 2400, pe: 5.2, pb: 0.8 },
    { code: '000002', name: '万科A', industry: '房地产', close: 18.30, pct_chg: -1.5, total_mv: 2100, pe: 8.5, pb: 1.2 },
    { code: '000858', name: '五粮液', industry: '食品饮料', close: 168.50, pct_chg: 3.2, total_mv: 6500, pe: 25.3, pb: 4.5 }
  ]

  return mockStocks.map(stock => ({
    ...stock,
    market: filters.market
  }))
}

const resetFilters = () => {
  Object.assign(filters, {
    market: 'A股',
    industry: [],
    marketCapRange: '',
    peRatio: { min: null, max: null },
    pbRatio: { min: null, max: null },
    roe: { min: null, max: null },
    changePercent: { min: null, max: null },
    volumeLevel: '',
    technicalPattern: []
  })

  screeningResults.value = []
  selectedStocks.value = []
  hasSearched.value = false
  currentPage.value = 1
}

const handleSelectionChange = (selection: StockInfo[]) => {
  selectedStocks.value = selection
}

const batchAnalyze = async () => {
  if (selectedStocks.value.length === 0) {
    ElMessage.warning('请先选择要分析的股票')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要对选中的 ${selectedStocks.value.length} 只股票进行批量分析吗？`,
      '确认批量分析',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'info'
      }
    )

    // 跳转到批量分析页面（携带统一市场参数）
    router.push({
      name: 'BatchAnalysis',
      query: {
        stocks: selectedStocks.value.map(s => s.code).join(','),
        market: normalizeMarketForAnalysis(filters.market)
      }
    })
  } catch {
    // 用户取消
  }
}


const analyzeSingle = (stock: StockInfo) => {
  router.push({
    name: 'SingleAnalysis',
    query: {
      stock: stock.code,
      market: normalizeMarketForAnalysis((stock as any).market || filters.market)
    }
  })
}

const viewStockDetail = (stock: StockInfo) => {
  // 跳转到股票详情页面
  router.push({
    name: 'StockDetail',
    params: { code: stock.code }
  })
}

const isFavorited = (code: string) => favoriteSet.value.has(code)

const toggleFavorite = async (stock: StockInfo) => {
  try {
    const code = stock.code
    if (favoriteSet.value.has(code)) {
      // 取消自选
      const res = await favoritesApi.remove(code)
      if ((res as any)?.success === false) throw new Error((res as any)?.message || '取消失败')
      favoriteSet.value.delete(code)
      ElMessage.success(`已取消自选：${stock.name || code}`)
    } else {
      // 加入自选
      // 根据股票代码判断市场类型
      let marketType = 'A股'
      if ((stock as any).market) {
        // 如果有 market 字段，尝试转换（可能是交易所代码如 "sz", "sh"）
        marketType = exchangeCodeToMarket((stock as any).market)
      } else {
        // 否则根据股票代码判断
        marketType = getMarketByStockCode(code)
      }

      const payload = {
        symbol: code,
        stock_code: code,  // 兼容字段
        stock_name: stock.name || code,
        market: marketType
      }
      const res = await favoritesApi.add(payload)
      if ((res as any)?.success === false) throw new Error((res as any)?.message || '添加失败')
      favoriteSet.value.add(code)
      ElMessage.success(`已加入自选：${stock.name || code}`)
    }
  } catch (error: any) {
    ElMessage.error(error?.message || '自选操作失败')
  }
}

const exportResults = () => {
  // 导出筛选结果
  ElMessage.info('导出功能开发中...')
}

const getChangeClass = (changePercent: number) => {
  if (changePercent > 0) return 'text-red'
  if (changePercent < 0) return 'text-green'
  return ''
}

const formatMarketCap = (marketCap: number) => {
  if (marketCap >= 10000) {
    return `${(marketCap / 10000).toFixed(2)}万亿`
  } else {
    return `${marketCap.toFixed(2)}亿`
  }
}

const handleSizeChange = (size: number) => {
  pageSize.value = size
  currentPage.value = 1
}

const handleCurrentChange = (page: number) => {
  currentPage.value = page
}

// 获取字段配置
const loadFieldConfig = async () => {
  fieldsLoading.value = true
  try {
    const response = await screeningApi.getFields()
    fieldConfig.value = response.data || response
    console.log('字段配置加载成功:', fieldConfig.value)
  } catch (error) {
    console.error('加载字段配置失败:', error)
    ElMessage.error('加载字段配置失败')
  } finally {
    fieldsLoading.value = false
  }
}

// 加载行业列表
const loadIndustries = async () => {
  try {
    const response = await screeningApi.getIndustries()
    const data = response.data || response
    industryOptions.value = data.industries || []
    console.log('行业列表加载成功:', industryOptions.value.length, '个行业')
  } catch (error) {
    console.error('加载行业列表失败:', error)
    ElMessage.error('加载行业列表失败')
    // 如果加载失败，使用默认的行业列表
    industryOptions.value = [
      { label: '银行', value: '银行' },
      { label: '证券', value: '证券' },
      { label: '保险', value: '保险' },
      { label: '房地产', value: '房地产' },
      { label: '医药生物', value: '医药生物' }
    ]
  }
}

// 加载自选列表，初始化 favoriteSet
const loadFavorites = async () => {
  try {
    const resp = await favoritesApi.list()
    const list = (resp as any)?.data || resp
    const set = new Set<string>()
    ;(list || []).forEach((item: any) => {
      // 兼容新旧字段
      const code = item.symbol || item.stock_code || item.code
      if (code) set.add(code)
    })
    favoriteSet.value = set
  } catch (e) {
    console.warn('加载自选列表失败，可能未登录或接口不可用。', e)
  }
}

// 获取当前数据源
const loadCurrentDataSource = async () => {
  try {
    const response = await getCurrentDataSource()
    if (response.success && response.data) {
      currentDataSource.value = response.data
    }
  } catch (e) {
    console.warn('获取当前数据源失败', e)
  }
}

// 生命周期
onMounted(() => {
  // 加载字段配置和行业列表
  loadFieldConfig()
  loadIndustries()
  // 初始化自选状态
  loadFavorites()
  // 加载当前数据源
  loadCurrentDataSource()
})
</script>

<style lang="scss" scoped>
.stock-screening {
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

  .filter-panel {
    margin-bottom: 24px;

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;

      .header-actions {
        display: flex;
        gap: 8px;
      }
    }

    .filter-form {
      .filter-actions {
        display: flex;
        justify-content: center;
        gap: 16px;
        margin-top: 24px;
      }
    }
  }

  .results-panel {
    .pagination-wrapper {
      display: flex;
      justify-content: center;
      margin-top: 24px;
    }
  }

  .text-red {
    color: #f56c6c;
  }

  .text-green {
    color: #67c23a;
  }
}
</style>
