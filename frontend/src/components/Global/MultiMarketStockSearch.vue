<template>
  <div class="multi-market-stock-search">
    <div class="search-header">
      <MarketSelector
        v-model="selectedMarket"
        size="default"
        @change="handleMarketChange"
      />
      <el-input
        v-model="searchQuery"
        :placeholder="getPlaceholder()"
        clearable
        @input="handleSearch"
        @clear="handleClear"
        class="search-input"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
    </div>

    <div v-if="loading" class="search-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>搜索中...</span>
    </div>

    <div v-else-if="searchResults.length > 0" class="search-results">
      <div
        v-for="stock in searchResults"
        :key="`${stock.market}-${stock.code}`"
        class="result-item"
        @click="handleSelectStock(stock)"
      >
        <div class="stock-info">
          <div class="stock-code-name">
            <span class="stock-code">{{ formatStockCode(stock) }}</span>
            <span class="stock-name">{{ stock.name }}</span>
            <span v-if="stock.name_en" class="stock-name-en">{{ stock.name_en }}</span>
          </div>
          <div class="stock-meta">
            <el-tag size="small" type="info">{{ getMarketLabel(stock.market) }}</el-tag>
            <el-tag v-if="stock.industry" size="small">{{ stock.industry }}</el-tag>
            <span v-if="stock.pe" class="stock-pe">PE: {{ stock.pe.toFixed(2) }}</span>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="searchQuery && !loading" class="no-results">
      <el-empty description="未找到相关股票" :image-size="80" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Search, Loading } from '@element-plus/icons-vue'
import { searchStocks, type StockInfo } from '@/api/multiMarket'
import { ElMessage } from 'element-plus'
import MarketSelector from './MarketSelector.vue'

interface Emits {
  (e: 'select', stock: StockInfo): void
}

const emit = defineEmits<Emits>()

const selectedMarket = ref('CN')
const searchQuery = ref('')
const searchResults = ref<StockInfo[]>([])
const loading = ref(false)

let searchTimer: ReturnType<typeof setTimeout> | null = null

const getPlaceholder = () => {
  const placeholders: Record<string, string> = {
    CN: '输入股票代码或名称（如：000001 或 平安银行）',
    HK: '输入股票代码或名称（如：00700 或 腾讯）',
    US: '输入股票代码或名称（如：AAPL 或 Apple）'
  }
  return placeholders[selectedMarket.value] || '输入股票代码或名称'
}

const getMarketLabel = (market: string) => {
  const labels: Record<string, string> = {
    CN: 'A股',
    HK: '港股',
    US: '美股'
  }
  return labels[market] || market
}

const formatStockCode = (stock: StockInfo) => {
  if (stock.market === 'HK') {
    // 港股代码格式化为5位（如：00700）
    return stock.code.padStart(5, '0')
  }
  return stock.code
}

const handleMarketChange = () => {
  // 切换市场时清空搜索结果
  searchResults.value = []
  searchQuery.value = ''
}

const handleSearch = () => {
  if (searchTimer) {
    clearTimeout(searchTimer)
  }

  if (!searchQuery.value.trim()) {
    searchResults.value = []
    return
  }

  // 防抖：500ms后执行搜索
  searchTimer = setTimeout(async () => {
    await performSearch()
  }, 500)
}

const performSearch = async () => {
  if (!searchQuery.value.trim()) {
    return
  }

  loading.value = true
  try {
    const response = await searchStocks(selectedMarket.value, searchQuery.value.trim(), 20)
    searchResults.value = response.data?.stocks || []
  } catch (error: any) {
    console.error('搜索失败:', error)
    ElMessage.error(error.message || '搜索失败')
    searchResults.value = []
  } finally {
    loading.value = false
  }
}

const handleClear = () => {
  searchResults.value = []
}

const handleSelectStock = (stock: StockInfo) => {
  emit('select', stock)
  // 清空搜索
  searchQuery.value = ''
  searchResults.value = []
}
</script>

<style scoped lang="scss">
.multi-market-stock-search {
  width: 100%;
}

.search-header {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.search-input {
  flex: 1;
}

.search-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 20px;
  color: var(--el-text-color-secondary);
}

.search-results {
  max-height: 400px;
  overflow-y: auto;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
}

.result-item {
  padding: 12px 16px;
  cursor: pointer;
  border-bottom: 1px solid var(--el-border-color-lighter);
  transition: background-color 0.2s;

  &:last-child {
    border-bottom: none;
  }

  &:hover {
    background-color: var(--el-fill-color-light);
  }
}

.stock-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stock-code-name {
  display: flex;
  align-items: center;
  gap: 8px;
}

.stock-code {
  font-weight: 600;
  font-size: 14px;
  color: var(--el-text-color-primary);
}

.stock-name {
  font-size: 14px;
  color: var(--el-text-color-regular);
}

.stock-name-en {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.stock-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.stock-pe {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.no-results {
  padding: 20px;
  text-align: center;
}
</style>

