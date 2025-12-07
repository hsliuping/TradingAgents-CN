<template>
  <div class="history-positions-table">
    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="code" label="股票代码" width="100" />
      <el-table-column prop="name" label="股票名称" width="120" />
      <el-table-column prop="market" label="市场" width="70">
        <template #default="{ row }">
          <el-tag size="small" :type="getMarketType(row.market)">{{ row.market }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="realized_pnl" label="已实现盈亏" width="120" align="right">
        <template #default="{ row }">
          <span :class="row.realized_pnl >= 0 ? 'positive' : 'negative'">
            {{ formatPnl(row.realized_pnl) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="realized_pnl_pct" label="收益率" width="100" align="right">
        <template #default="{ row }">
          <span :class="row.realized_pnl_pct >= 0 ? 'positive' : 'negative'">
            {{ formatPct(row.realized_pnl_pct) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="hold_days" label="持有天数" width="100" align="right">
        <template #default="{ row }">
          {{ row.hold_days || '-' }} 天
        </template>
      </el-table-column>
      <el-table-column prop="cleared_at" label="清仓时间" width="160">
        <template #default="{ row }">
          {{ formatDateTime(row.cleared_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link size="small" @click="handleStartReview(row)">
            发起复盘
          </el-button>
        </template>
      </el-table-column>
    </el-table>
    
    <el-empty v-if="!loading && items.length === 0" description="暂无历史持仓" />
  </div>
</template>

<script setup lang="ts">
interface HistoryPositionItem {
  code: string
  name: string
  market: string
  realized_pnl: number
  realized_pnl_pct: number
  hold_days: number
  cleared_at: string
}

defineProps<{
  items: HistoryPositionItem[]
  loading: boolean
}>()

const emit = defineEmits<{
  (e: 'start-review', item: HistoryPositionItem): void
}>()

const getMarketType = (market: string) => {
  const map: Record<string, string> = {
    CN: 'danger',
    HK: 'warning',
    US: 'primary'
  }
  return map[market] || 'info'
}

const formatPnl = (val?: number) => {
  if (val === undefined || val === null) return '-'
  const prefix = val >= 0 ? '+' : ''
  return prefix + val.toFixed(2)
}

const formatPct = (val?: number) => {
  if (val === undefined || val === null) return '-'
  const prefix = val >= 0 ? '+' : ''
  return prefix + val.toFixed(2) + '%'
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

const handleStartReview = (item: HistoryPositionItem) => {
  emit('start-review', item)
}
</script>

<style scoped lang="scss">
.history-positions-table {
  .positive { color: #67c23a; }
  .negative { color: #f56c6c; }
}
</style>

