<template>
  <el-dialog
    v-model="visible"
    title="📜 历史交易汇总"
    width="950px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <el-alert type="info" :closable="false" show-icon style="margin-bottom: 16px">
      按股票汇总所有交易记录，显示累计买卖数量及已实现盈亏
    </el-alert>

    <!-- 历史持仓表格 -->
    <el-table :data="positions" v-loading="loading" stripe size="small" max-height="450">
      <el-table-column prop="code" label="代码" width="90">
        <template #default="{ row }">
          <span class="code-link" @click="goToStock(row)">{{ row.code }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="名称" width="100" />
      <el-table-column prop="market" label="市场" width="70">
        <template #default="{ row }">
          <el-tag :type="getMarketTagType(row.market)" size="small">{{ getMarketName(row.market) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="买入" width="140">
        <template #default="{ row }">
          <div>{{ row.total_buy_qty }}股</div>
          <div class="sub-text">@ {{ getCurrencySymbol(row.currency) }}{{ row.avg_buy_price.toFixed(2) }}</div>
        </template>
      </el-table-column>
      <el-table-column label="卖出" width="140">
        <template #default="{ row }">
          <div>{{ row.total_sell_qty }}股</div>
          <div class="sub-text">@ {{ getCurrencySymbol(row.currency) }}{{ row.avg_sell_price.toFixed(2) }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="first_buy_date" label="首次买入" width="100">
        <template #default="{ row }">
          {{ formatDate(row.first_buy_date) }}
        </template>
      </el-table-column>
      <el-table-column prop="last_trade_date" label="最后交易" width="100">
        <template #default="{ row }">
          {{ formatDate(row.last_trade_date) }}
        </template>
      </el-table-column>
      <el-table-column prop="realized_pnl" label="已实现盈亏" width="130">
        <template #default="{ row }">
          <span :class="row.realized_pnl >= 0 ? 'text-profit' : 'text-loss'">
            {{ row.realized_pnl >= 0 ? '+' : '' }}{{ getCurrencySymbol(row.currency) }}{{ row.realized_pnl?.toFixed(2) || '0.00' }}
          </span>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div class="pagination-bar">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @size-change="loadData"
        @current-change="loadData"
      />
    </div>

    <!-- 汇总信息 -->
    <div class="summary-bar" v-if="positions.length > 0">
      <span>共 {{ total }} 条记录</span>
      <span class="summary-item">
        总盈亏：
        <span :class="totalPnl >= 0 ? 'text-profit' : 'text-loss'">
          {{ totalPnl >= 0 ? '+' : '' }}¥{{ totalPnl.toFixed(2) }}
        </span>
      </span>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { portfolioApi, type HistoryPositionItem } from '@/api/portfolio'

const router = useRouter()

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits(['update:modelValue'])

const visible = ref(props.modelValue)
const loading = ref(false)
const positions = ref<HistoryPositionItem[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(50)

watch(() => props.modelValue, (val) => {
  visible.value = val
  if (val) loadData()
})

watch(visible, (val) => emit('update:modelValue', val))

const totalPnl = computed(() => positions.value.reduce((sum, p) => sum + (p.realized_pnl || 0), 0))

const loadData = async () => {
  loading.value = true
  try {
    const res = await portfolioApi.getHistoryPositions({
      source: 'real',
      limit: pageSize.value,
      skip: (currentPage.value - 1) * pageSize.value
    })
    positions.value = res.data?.items || []
    total.value = res.data?.total || 0
  } catch (e: any) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

const handleClose = () => emit('update:modelValue', false)

const goToStock = (row: HistoryPositionItem) => {
  router.push({ name: 'StockDetail', params: { code: row.code }, query: { market: row.market } })
}

const formatDate = (dt?: string) => {
  if (!dt) return '-'
  return new Date(dt).toLocaleDateString('zh-CN')
}

const getMarketName = (m: string) => ({ CN: 'A股', HK: '港股', US: '美股' }[m] || m)
const getMarketTagType = (m: string) => ({ CN: 'danger', HK: 'warning', US: 'primary' }[m] || 'info') as any
const getCurrencySymbol = (c: string) => ({ CNY: '¥', HKD: 'HK$', USD: '$' }[c] || c)
</script>

<style scoped>
.pagination-bar { margin-top: 16px; display: flex; justify-content: flex-end; }
.summary-bar { margin-top: 12px; padding: 10px; background: #f5f7fa; border-radius: 4px; display: flex; gap: 20px; font-size: 13px; }
.summary-item { font-weight: 500; }
.text-profit { color: #f56c6c; }
.text-loss { color: #67c23a; }
.code-link { cursor: pointer; color: #409eff; }
.code-link:hover { text-decoration: underline; }
.sub-text { font-size: 12px; color: #909399; }
</style>

