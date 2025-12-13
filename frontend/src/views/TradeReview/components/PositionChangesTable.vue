<template>
  <div class="position-changes-table">
    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="code" label="股票代码" width="100" />
      <el-table-column prop="name" label="股票名称" width="120" />
      <el-table-column prop="market" label="市场" width="70">
        <template #default="{ row }">
          <el-tag size="small" :type="getMarketType(row.market)">{{ row.market }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="current_quantity" label="持仓数量" width="100" align="right" />
      <el-table-column prop="cost_price" label="成本价" width="100" align="right">
        <template #default="{ row }">
          {{ row.cost_price?.toFixed(2) || '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="unrealized_pnl" label="浮动盈亏" width="120" align="right">
        <template #default="{ row }">
          <span :class="row.unrealized_pnl >= 0 ? 'positive' : 'negative'">
            {{ formatPnl(row.unrealized_pnl) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="unrealized_pnl_pct" label="盈亏比例" width="100" align="right">
        <template #default="{ row }">
          <span :class="row.unrealized_pnl_pct >= 0 ? 'positive' : 'negative'">
            {{ formatPct(row.unrealized_pnl_pct) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link size="small" @click="handleStartReview(row)">
            发起复盘
          </el-button>
          <el-button type="success" link size="small" @click="handleViewReport(row)">
            查看报告
          </el-button>
          <el-button type="info" link size="small" @click="handleViewHistory(row)">
            复盘历史
          </el-button>
        </template>
      </el-table-column>
    </el-table>
    
    <el-empty v-if="!loading && items.length === 0" description="暂无持仓数据" />
  </div>
</template>

<script setup lang="ts">
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

defineProps<{
  items: PositionChangeItem[]
  loading: boolean
}>()

const emit = defineEmits<{
  (e: 'start-review', item: PositionChangeItem): void
  (e: 'view-report', item: PositionChangeItem): void
  (e: 'view-history', item: PositionChangeItem): void
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

const handleStartReview = (item: PositionChangeItem) => {
  emit('start-review', item)
}

const handleViewReport = (item: PositionChangeItem) => {
  emit('view-report', item)
}

const handleViewHistory = (item: PositionChangeItem) => {
  emit('view-history', item)
}
</script>

<style scoped lang="scss">
.position-changes-table {
  .positive { color: #67c23a; }
  .negative { color: #f56c6c; }
}
</style>

