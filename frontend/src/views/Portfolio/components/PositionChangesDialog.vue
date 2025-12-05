<template>
  <el-dialog
    v-model="visible"
    title="📋 持仓变动记录"
    width="900px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <!-- 筛选条件 -->
    <div class="filter-bar">
      <el-select v-model="filters.market" placeholder="市场" clearable size="small" style="width: 100px">
        <el-option label="全部" value="" />
        <el-option label="A股" value="CN" />
        <el-option label="港股" value="HK" />
        <el-option label="美股" value="US" />
      </el-select>
      <el-select v-model="filters.change_type" placeholder="变动类型" clearable size="small" style="width: 120px">
        <el-option label="全部" value="" />
        <el-option label="买入" value="buy" />
        <el-option label="加仓" value="add" />
        <el-option label="减仓" value="reduce" />
        <el-option label="卖出" value="sell" />
        <el-option label="调整" value="adjust" />
      </el-select>
      <el-input v-model="filters.code" placeholder="股票代码" clearable size="small" style="width: 120px" />
      <el-button type="primary" size="small" @click="loadData">查询</el-button>
      <el-button size="small" @click="resetFilters">重置</el-button>
    </div>

    <!-- 变动记录表格 -->
    <el-table :data="changes" v-loading="loading" stripe size="small" max-height="500">
      <el-table-column prop="created_at" label="时间" width="160">
        <template #default="{ row }">
          {{ formatDateTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column prop="code" label="代码" width="90" />
      <el-table-column prop="name" label="名称" width="100" />
      <el-table-column prop="market" label="市场" width="70">
        <template #default="{ row }">
          <el-tag :type="getMarketTagType(row.market)" size="small">{{ getMarketName(row.market) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="change_type" label="类型" width="80">
        <template #default="{ row }">
          <el-tag :type="getChangeTypeTag(row.change_type)" size="small">{{ getChangeTypeName(row.change_type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="数量变化" width="120">
        <template #default="{ row }">
          <span :class="row.quantity_change >= 0 ? 'text-success' : 'text-danger'">
            {{ row.quantity_change >= 0 ? '+' : '' }}{{ row.quantity_change }}
          </span>
          <div class="sub-text">{{ row.quantity_before }} → {{ row.quantity_after }}</div>
        </template>
      </el-table-column>
      <el-table-column label="成本价" width="120">
        <template #default="{ row }">
          {{ getCurrencySymbol(row.currency) }}{{ row.cost_price_after.toFixed(2) }}
          <div class="sub-text" v-if="row.cost_price_before !== row.cost_price_after">
            {{ row.cost_price_before.toFixed(2) }} → {{ row.cost_price_after.toFixed(2) }}
          </div>
        </template>
      </el-table-column>
      <el-table-column label="资金变化" width="120">
        <template #default="{ row }">
          <span :class="row.cash_change >= 0 ? 'text-success' : 'text-danger'">
            {{ row.cash_change >= 0 ? '+' : '' }}{{ getCurrencySymbol(row.currency) }}{{ Math.abs(row.cash_change).toFixed(2) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="说明" min-width="120" show-overflow-tooltip />
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
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { portfolioApi, type PositionChange, type PositionChangeType } from '@/api/portfolio'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits(['update:modelValue'])

const visible = ref(props.modelValue)
const loading = ref(false)
const changes = ref<PositionChange[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(50)

const filters = ref({
  market: '',
  change_type: '' as PositionChangeType | '',
  code: ''
})

watch(() => props.modelValue, (val) => {
  visible.value = val
  if (val) loadData()
})

watch(visible, (val) => emit('update:modelValue', val))

const loadData = async () => {
  loading.value = true
  try {
    const res = await portfolioApi.getPositionChanges({
      market: filters.value.market || undefined,
      change_type: filters.value.change_type || undefined,
      code: filters.value.code || undefined,
      limit: pageSize.value,
      skip: (currentPage.value - 1) * pageSize.value
    })
    changes.value = res.data?.items || []
    total.value = res.data?.total || 0
  } catch (e: any) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

const resetFilters = () => {
  filters.value = { market: '', change_type: '', code: '' }
  currentPage.value = 1
  loadData()
}

const handleClose = () => emit('update:modelValue', false)

const formatDateTime = (dt: string) => {
  if (!dt) return '-'
  const d = new Date(dt)
  return d.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

const getMarketName = (m: string) => ({ CN: 'A股', HK: '港股', US: '美股' }[m] || m)
const getMarketTagType = (m: string) => ({ CN: 'danger', HK: 'warning', US: 'primary' }[m] || 'info') as any
const getCurrencySymbol = (c: string) => ({ CNY: '¥', HKD: 'HK$', USD: '$' }[c] || c)
const getChangeTypeName = (t: string) => ({ buy: '买入', add: '加仓', reduce: '减仓', sell: '卖出', adjust: '调整' }[t] || t)
const getChangeTypeTag = (t: string) => ({ buy: 'success', add: 'primary', reduce: 'warning', sell: 'danger', adjust: 'info' }[t] || 'info') as any
</script>

<style scoped>
.filter-bar { display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
.pagination-bar { margin-top: 16px; display: flex; justify-content: flex-end; }
.text-success { color: #67c23a; }
.text-danger { color: #f56c6c; }
.sub-text { font-size: 11px; color: #909399; }
</style>

