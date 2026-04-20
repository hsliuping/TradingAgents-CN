<template>
  <div class="dianjin-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">
          <el-icon><MagicStick /></el-icon>
          点金术
        </h1>
        <p class="page-description">
          提取自 `dianjin` 桌面工具的高股息低估值筛选策略，按当前股息率、PB、流通市值、MA120 偏离和近三年分红能力进行联合筛选。
        </p>
      </div>
      <div class="page-actions">
        <el-button @click="loadSavedConfig">
          <el-icon><FolderOpened /></el-icon>
          加载配置
        </el-button>
        <el-button @click="saveCurrentConfig">
          <el-icon><Collection /></el-icon>
          保存配置
        </el-button>
      </div>
    </div>

    <el-card class="filter-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>策略参数</span>
          <div class="header-actions">
            <el-button text @click="resetFilters">
              <el-icon><Refresh /></el-icon>
              重置
            </el-button>
          </div>
        </div>
      </template>

      <el-form label-width="150px">
        <el-row :gutter="20">
          <el-col :xs="24" :md="12" :xl="8">
            <el-form-item label="市盈率 PE">
              <div class="range-row">
                <el-input-number v-model="filters.min_pe" :min="0" :precision="2" style="width: 48%" />
                <span>-</span>
                <el-input-number v-model="filters.max_pe" :min="0" :precision="2" style="width: 48%" />
              </div>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12" :xl="8">
            <el-form-item label="当前股息率 %">
              <div class="range-row">
                <el-input-number v-model="filters.min_dividend" :min="0" :precision="2" style="width: 48%" />
                <span>-</span>
                <el-input-number v-model="filters.max_dividend" :min="0" :precision="2" style="width: 48%" />
              </div>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12" :xl="8">
            <el-form-item label="流通市值下限(亿)">
              <el-input-number v-model="filters.min_market_cap" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :xs="24" :md="12" :xl="8">
            <el-form-item label="PB 区间">
              <div class="range-row">
                <el-input-number v-model="filters.min_pb" :min="0" :precision="2" style="width: 48%" />
                <span>-</span>
                <el-input-number v-model="filters.max_pb" :min="0" :precision="2" style="width: 48%" />
              </div>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12" :xl="8">
            <el-form-item label="股价 / MA120 上限">
              <el-input-number v-model="filters.ratio_threshold" :min="0.01" :precision="3" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12" :xl="8">
            <el-form-item label="三年股息模式">
              <el-select v-model="filters.dividend_mode" style="width: 100%">
                <el-option label="任一年 >= 3%（宽松）" value="any" />
                <el-option label="全部年份 >= 3%（严格）" value="all" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :xs="24" :xl="16">
            <el-form-item label="指定股票代码">
              <el-input
                v-model="filters.specific_stocks"
                placeholder="留空为全市场扫描，例如：600036,000001,002415"
                clearable
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12" :xl="4">
            <el-form-item label="K线天数">
              <el-input-number v-model="filters.kline_days" :min="200" :max="3000" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12" :xl="4">
            <el-form-item label="调试数量限制">
              <el-input-number v-model="filters.limit_count" :min="0" :max="5000" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <div class="filter-actions">
          <el-button type="primary" :loading="loading" size="large" @click="runStrategy">
            <el-icon><Search /></el-icon>
            开始筛选
          </el-button>
          <el-button size="large" @click="resetFilters">重置参数</el-button>
        </div>
      </el-form>
    </el-card>

    <el-row v-if="stats" :gutter="16" class="stats-row">
      <el-col :xs="12" :md="8" :xl="4"><el-card shadow="hover"><div class="stat"><span>总样本</span><b>{{ stats.total_samples }}</b></div></el-card></el-col>
      <el-col :xs="12" :md="8" :xl="4"><el-card shadow="hover"><div class="stat"><span>实时行情</span><b>{{ stats.realtime_count }}</b></div></el-card></el-col>
      <el-col :xs="12" :md="8" :xl="4"><el-card shadow="hover"><div class="stat"><span>初筛通过</span><b>{{ stats.first_filter_count }}</b></div></el-card></el-col>
      <el-col :xs="12" :md="8" :xl="4"><el-card shadow="hover"><div class="stat"><span>MA120通过</span><b>{{ stats.ma120_pass_count }}</b></div></el-card></el-col>
      <el-col :xs="12" :md="8" :xl="4"><el-card shadow="hover"><div class="stat"><span>最终结果</span><b>{{ stats.final_count }}</b></div></el-card></el-col>
      <el-col :xs="12" :md="8" :xl="4"><el-card shadow="hover"><div class="stat"><span>耗时</span><b>{{ formatDuration(stats.duration_ms) }}</b></div></el-card></el-col>
    </el-row>

    <el-card v-if="loading && results.length === 0" class="loading-card" shadow="never">
      <div class="loading-header">
        <el-icon class="is-loading"><Loading /></el-icon>
        <div>
          <div class="loading-title">正在按点金术策略自动筛选 A 股股票</div>
          <div class="loading-desc">系统正在依次执行实时估值初筛、MA120 校验和近三年股息率验证，请稍候。</div>
        </div>
      </div>

      <el-skeleton :rows="6" animated />
    </el-card>

    <el-card v-if="results.length > 0" class="result-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>筛选结果（{{ results.length }}）</span>
          <div class="header-actions">
            <el-button type="primary" :disabled="selectedRows.length === 0" @click="batchAnalyze">
              <el-icon><TrendCharts /></el-icon>
              批量分析（{{ selectedRows.length }}）
            </el-button>
            <el-button @click="exportCsv">
              <el-icon><Download /></el-icon>
              导出 CSV
            </el-button>
          </div>
        </div>
      </template>

      <el-table
        :data="paginatedResults"
        stripe
        style="width: 100%"
        @selection-change="handleSelectionChange"
        :row-class-name="getRowClassName"
      >
        <el-table-column type="selection" width="55" />

        <el-table-column prop="code" label="代码" width="110">
          <template #default="{ row }">
            <el-link type="primary" @click="viewStockDetail(row.code)">{{ row.code }}</el-link>
          </template>
        </el-table-column>

        <el-table-column prop="name" label="名称" width="160">
          <template #default="{ row }">
            <div class="name-cell">
              <span :class="{ 'all-pass-name': row.three_year_all_pass }">{{ row.name }}</span>
              <el-tag v-if="row.three_year_all_pass" size="small" type="warning">三年全达标</el-tag>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="price" label="现价" width="100" align="right">
          <template #default="{ row }">{{ formatNumber(row.price, 2) }}</template>
        </el-table-column>

        <el-table-column prop="pe_ttm" label="PE(TTM)" width="110" align="right">
          <template #default="{ row }">{{ formatNumber(row.pe_ttm, 2) }}</template>
        </el-table-column>

        <el-table-column prop="pb" label="PB" width="90" align="right">
          <template #default="{ row }">{{ formatNumber(row.pb, 2) }}</template>
        </el-table-column>

        <el-table-column prop="dividend_yield" label="当前股息率" width="120" align="right">
          <template #default="{ row }">{{ formatPercent(row.dividend_yield) }}</template>
        </el-table-column>

        <el-table-column prop="market_cap" label="流通市值(亿)" width="130" align="right">
          <template #default="{ row }">{{ formatNumber(row.market_cap, 2) }}</template>
        </el-table-column>

        <el-table-column prop="ma120_ratio" label="股价/MA120" width="120" align="right">
          <template #default="{ row }">
            <span :class="{ 'ratio-good': row.ma120_ratio <= 1 }">{{ formatNumber(row.ma120_ratio, 3) }}</span>
          </template>
        </el-table-column>

        <el-table-column :label="`${yearLabels[0]}股息率`" width="120" align="center">
          <template #default="{ row }">
            <span :class="dividendClass(row.three_year_dividend?.[0])">{{ formatPercent(row.three_year_dividend?.[0]) }}</span>
          </template>
        </el-table-column>

        <el-table-column :label="`${yearLabels[1]}股息率`" width="120" align="center">
          <template #default="{ row }">
            <span :class="dividendClass(row.three_year_dividend?.[1])">{{ formatPercent(row.three_year_dividend?.[1]) }}</span>
          </template>
        </el-table-column>

        <el-table-column :label="`${yearLabels[2]}股息率`" width="120" align="center">
          <template #default="{ row }">
            <span :class="dividendClass(row.three_year_dividend?.[2])">{{ formatPercent(row.three_year_dividend?.[2]) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="达标" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="row.three_year_all_pass ? 'warning' : row.three_year_dividend_pass ? 'success' : 'info'">
              {{ row.three_year_all_pass ? '全部达标' : row.three_year_dividend_pass ? '部分达标' : '未达标' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" text @click="analyzeSingle(row.code)">分析</el-button>
            <el-button text @click="toggleFavorite(row)">
              <el-icon><Star /></el-icon>
              {{ isFavorited(row.code) ? '取消自选' : '加入自选' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[20, 50, 100]"
          :total="results.length"
          layout="total, sizes, prev, pager, next, jumper"
        />
      </div>
    </el-card>

    <el-empty v-else-if="hasSearched && !loading" description="未找到符合点金术条件的股票">
      <el-button type="primary" @click="resetFilters">重新筛选</el-button>
    </el-empty>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Collection, Download, FolderOpened, Loading, MagicStick, Refresh, Search, Star, TrendCharts } from '@element-plus/icons-vue'

import { dianjinApi, type DianjinResultItem, type DianjinRunRequest, type DianjinRunStats } from '@/api/dianjin'
import { favoritesApi } from '@/api/favorites'
import { normalizeMarketForAnalysis } from '@/utils/market'

const STORAGE_KEY = 'dianjin-page-config'

type FiltersState = {
  min_pe: number
  max_pe: number
  min_dividend: number
  max_dividend: number
  min_market_cap: number
  ratio_threshold: number
  min_pb: number | null
  max_pb: number | null
  dividend_mode: 'any' | 'all'
  specific_stocks: string
  kline_days: number
  limit_count: number
}

const createDefaultFilters = (): FiltersState => ({
  min_pe: 0.1,
  max_pe: 20,
  min_dividend: 3,
  max_dividend: 15,
  min_market_cap: 50,
  ratio_threshold: 0.88,
  min_pb: null,
  max_pb: null,
  dividend_mode: 'any',
  specific_stocks: '',
  kline_days: 1300,
  limit_count: 0
})

const router = useRouter()
const filters = reactive<FiltersState>(createDefaultFilters())
const loading = ref(false)
const hasSearched = ref(false)
const results = ref<DianjinResultItem[]>([])
const selectedRows = ref<DianjinResultItem[]>([])
const stats = ref<DianjinRunStats | null>(null)
const years = ref<number[]>([])
const favoriteSet = ref<Set<string>>(new Set())
const currentPage = ref(1)
const pageSize = ref(20)

const paginatedResults = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return results.value.slice(start, start + pageSize.value)
})

const yearLabels = computed(() => {
  if (years.value.length === 3) return years.value
  return ['近1年', '近2年', '近3年']
})

const validateFilters = () => {
  if (filters.min_pe > filters.max_pe) {
    ElMessage.warning('PE 最小值不能大于最大值')
    return false
  }
  if (filters.min_dividend > filters.max_dividend) {
    ElMessage.warning('股息率最小值不能大于最大值')
    return false
  }
  if (filters.ratio_threshold <= 0) {
    ElMessage.warning('股价 / MA120 上限必须大于 0')
    return false
  }
  const onlyOnePb = (filters.min_pb === null) !== (filters.max_pb === null)
  if (onlyOnePb) {
    ElMessage.warning('PB 最小值和最大值需要同时填写，或同时留空')
    return false
  }
  if (filters.min_pb !== null && filters.max_pb !== null && filters.min_pb > filters.max_pb) {
    ElMessage.warning('PB 最小值不能大于最大值')
    return false
  }
  return true
}

const runStrategy = async (options?: { silentSuccess?: boolean }) => {
  if (!validateFilters()) return

  loading.value = true
  hasSearched.value = true
  currentPage.value = 1

  try {
    const payload: DianjinRunRequest = {
      min_pe: filters.min_pe,
      max_pe: filters.max_pe,
      min_dividend: filters.min_dividend,
      max_dividend: filters.max_dividend,
      min_market_cap: filters.min_market_cap,
      ratio_threshold: filters.ratio_threshold,
      min_pb: filters.min_pb,
      max_pb: filters.max_pb,
      dividend_mode: filters.dividend_mode,
      specific_stocks: filters.specific_stocks.trim(),
      kline_days: filters.kline_days,
      limit_count: filters.limit_count
    }

    const response = await dianjinApi.run(payload, { timeout: 300000 })
    const data = (response as any)?.data || response
    results.value = data.items || []
    stats.value = data.stats || null
    years.value = data.years || []
    selectedRows.value = []
    if (!options?.silentSuccess) {
      ElMessage.success(`点金术运行完成，共找到 ${results.value.length} 只股票`)
    }
  } catch (error: any) {
    ElMessage.error(error?.message || '点金术运行失败')
  } finally {
    loading.value = false
  }
}

const resetFilters = () => {
  Object.assign(filters, createDefaultFilters())
  results.value = []
  selectedRows.value = []
  stats.value = null
  years.value = []
  hasSearched.value = false
  currentPage.value = 1
}

const saveCurrentConfig = () => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(filters))
  ElMessage.success('点金术配置已保存到浏览器')
}

const loadSavedConfig = async (silent = false) => {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) {
    if (!silent) {
      ElMessage.info('暂无已保存的点金术配置')
    }
    return
  }
  try {
    const parsed = JSON.parse(raw)
    Object.assign(filters, createDefaultFilters(), parsed)
    if (!silent) {
      ElMessage.success('已加载点金术配置')
      await runStrategy({ silentSuccess: true })
    }
  } catch {
    if (!silent) {
      ElMessage.error('加载点金术配置失败')
    }
  }
}

const handleSelectionChange = (rows: DianjinResultItem[]) => {
  selectedRows.value = rows
}

const viewStockDetail = (code: string) => {
  router.push({
    name: 'StockDetail',
    params: { code: String(code).toUpperCase() }
  })
}

const analyzeSingle = (code: string) => {
  router.push({
    name: 'SingleAnalysis',
    query: {
      stock: code,
      market: normalizeMarketForAnalysis('A股')
    }
  })
}

const batchAnalyze = async () => {
  if (selectedRows.value.length === 0) {
    ElMessage.warning('请先选择股票')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定要对选中的 ${selectedRows.value.length} 只股票发起批量分析吗？`,
      '确认批量分析',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'info'
      }
    )
    router.push({
      name: 'BatchAnalysis',
      query: {
        stocks: selectedRows.value.map(item => item.code).join(','),
        market: normalizeMarketForAnalysis('A股')
      }
    })
  } catch {
    // 用户取消
  }
}

const isFavorited = (code: string) => favoriteSet.value.has(code)

const loadFavorites = async () => {
  try {
    const response = await favoritesApi.list()
    const list = (response as any)?.data || response || []
    const nextSet = new Set<string>()
    list.forEach((item: any) => {
      const code = item.symbol || item.stock_code || item.code
      if (code) nextSet.add(String(code))
    })
    favoriteSet.value = nextSet
  } catch (error) {
    console.warn('加载自选列表失败', error)
  }
}

const toggleFavorite = async (row: DianjinResultItem) => {
  try {
    if (favoriteSet.value.has(row.code)) {
      const response = await favoritesApi.remove(row.code)
      if ((response as any)?.success === false) {
        throw new Error((response as any)?.message || '取消自选失败')
      }
      favoriteSet.value.delete(row.code)
      ElMessage.success(`已取消自选：${row.name}`)
      return
    }

    const response = await favoritesApi.add({
      symbol: row.code,
      stock_code: row.code,
      stock_name: row.name,
      market: 'A股'
    })
    if ((response as any)?.success === false) {
      throw new Error((response as any)?.message || '加入自选失败')
    }
    favoriteSet.value.add(row.code)
    ElMessage.success(`已加入自选：${row.name}`)
  } catch (error: any) {
    ElMessage.error(error?.message || '自选操作失败')
  }
}

const exportCsv = () => {
  if (results.value.length === 0) {
    ElMessage.info('暂无可导出的结果')
    return
  }

  const labels = yearLabels.value
  const header = [
    '代码',
    '名称',
    '现价',
    'PE(TTM)',
    'PB',
    '当前股息率(%)',
    '流通市值(亿)',
    '股价/MA120',
    `${labels[0]}股息率(%)`,
    `${labels[1]}股息率(%)`,
    `${labels[2]}股息率(%)`,
    '达标状态'
  ]

  const lines = [
    header.join(','),
    ...results.value.map((item) => {
      const status = item.three_year_all_pass ? '全部达标' : item.three_year_dividend_pass ? '部分达标' : '未达标'
      const values = [
        item.code,
        item.name,
        formatNumber(item.price, 2),
        formatNumber(item.pe_ttm, 2),
        formatNumber(item.pb, 2),
        formatPercentValue(item.dividend_yield),
        formatNumber(item.market_cap, 2),
        formatNumber(item.ma120_ratio, 3),
        formatPercentValue(item.three_year_dividend?.[0]),
        formatPercentValue(item.three_year_dividend?.[1]),
        formatPercentValue(item.three_year_dividend?.[2]),
        status
      ]
      return values.map(csvEscape).join(',')
    })
  ]

  const blob = new Blob(['\uFEFF' + lines.join('\n')], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `点金术_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.csv`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
  ElMessage.success('CSV 导出成功')
}

const csvEscape = (value: string | number) => {
  const text = String(value ?? '')
  if (/[",\n]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`
  }
  return text
}

const formatNumber = (value?: number | null, digits = 2) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-'
  return Number(value).toFixed(digits)
}

const formatPercentValue = (value?: number | null) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '0.00'
  return Number(value).toFixed(2)
}

const formatPercent = (value?: number | null) => `${formatPercentValue(value)}%`

const formatDuration = (ms: number) => {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

const dividendClass = (value?: number) => {
  return Number(value) >= 3 ? 'dividend-pass' : 'dividend-fail'
}

const getRowClassName = ({ row }: { row: DianjinResultItem }) => {
  if (row.three_year_all_pass) return 'row-all-pass'
  if (row.three_year_dividend_pass) return 'row-partial-pass'
  return ''
}

onMounted(async () => {
  await loadSavedConfig(true)
  loadFavorites()
  await runStrategy({ silentSuccess: true })
})
</script>

<style lang="scss" scoped>
.dianjin-page {
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
    margin-bottom: 24px;
  }

  .page-title {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 0 0 8px;
    font-size: 24px;
    font-weight: 600;
  }

  .page-description {
    margin: 0;
    max-width: 960px;
    color: var(--el-text-color-regular);
    line-height: 1.7;
  }

  .page-actions,
  .header-actions {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .filter-card,
  .result-card {
    margin-bottom: 24px;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
  }

  .range-row {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }

  .filter-actions {
    display: flex;
    justify-content: center;
    gap: 16px;
    margin-top: 12px;
  }

  .stats-row {
    margin-bottom: 24px;
  }

  .loading-card {
    margin-bottom: 24px;
  }

  .loading-header {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    margin-bottom: 18px;

    .el-icon {
      margin-top: 2px;
      font-size: 18px;
      color: var(--el-color-primary);
    }
  }

  .loading-title {
    font-size: 16px;
    font-weight: 600;
    color: var(--el-text-color-primary);
  }

  .loading-desc {
    margin-top: 6px;
    font-size: 13px;
    line-height: 1.7;
    color: var(--el-text-color-regular);
  }

  .stat {
    display: flex;
    flex-direction: column;
    gap: 8px;

    span {
      color: var(--el-text-color-secondary);
      font-size: 13px;
    }

    b {
      font-size: 22px;
      color: var(--el-color-primary);
    }
  }

  .name-cell {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .all-pass-name {
    color: #e6a23c;
    font-weight: 600;
  }

  .ratio-good {
    color: #67c23a;
    font-weight: 600;
  }

  .dividend-pass {
    color: #67c23a;
    font-weight: 600;
  }

  .dividend-fail {
    color: #f56c6c;
    font-weight: 600;
  }

  .pagination-wrapper {
    display: flex;
    justify-content: center;
    margin-top: 24px;
  }

  :deep(.row-all-pass) {
    --el-table-tr-bg-color: rgba(230, 162, 60, 0.12);
  }

  :deep(.row-partial-pass) {
    --el-table-tr-bg-color: rgba(103, 194, 58, 0.10);
  }
}
</style>
