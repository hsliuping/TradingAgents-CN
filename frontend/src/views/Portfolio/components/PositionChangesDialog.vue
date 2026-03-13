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
      <el-button size="small" @click="resetFilters">重置筛选</el-button>
      <el-button
        v-if="filters.code"
        type="danger"
        size="small"
        plain
        @click="confirmResetPosition"
      >
        重置 {{ filters.code }} 持仓
      </el-button>
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
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="['buy','add','reduce','sell'].includes(row.change_type)"
            type="primary"
            link
            size="small"
            @click="openEdit(row as PositionChange)"
          >
            编辑
          </el-button>
          <el-button
            v-if="['buy','add','reduce','sell','adjust'].includes(row.change_type)"
            type="danger"
            link
            size="small"
            @click="confirmDelete(row as PositionChange)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 单笔记录编辑对话框 -->
    <el-dialog
      v-model="editVisible"
      :title="`编辑${getChangeTypeName(editForm.change_type)}记录`"
      width="420px"
      append-to-body
      @close="resetEditForm"
    >
      <p class="edit-tip">用于修正录入错误（数量、单价）。修改后会自动重算后续记录和持仓。</p>
      <el-form label-width="100px">
        <el-form-item label="股票">
          {{ editForm.code }} {{ editForm.name }}
        </el-form-item>
        <el-form-item label="类型">
          <el-tag :type="getChangeTypeTag(editForm.change_type)" size="small">
            {{ getChangeTypeName(editForm.change_type) }}
          </el-tag>
        </el-form-item>
        <el-form-item :label="editForm.change_type === 'buy' || editForm.change_type === 'add' ? '买入数量' : '卖出数量'" required>
          <el-input-number
            v-model="editForm.quantity"
            :min="1"
            :precision="0"
            controls-position="right"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item :label="editForm.change_type === 'buy' || editForm.change_type === 'add' ? '买入单价' : '卖出单价'" required>
          <el-input-number
            v-model="editForm.price"
            :min="0.01"
            :precision="2"
            :step="0.01"
            controls-position="right"
            style="width: 100%"
          />
          <span class="unit-hint">{{ getCurrencySymbol(editForm.currency) }}/股</span>
        </el-form-item>
        <el-form-item label="交易时间">
          <el-date-picker
            v-model="editForm.trade_time"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="可选"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSubmitting" @click="submitEdit">
          确定
        </el-button>
      </template>
    </el-dialog>

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
import { ElMessage, ElMessageBox } from 'element-plus'
import { portfolioApi, type PositionChange, type PositionChangeType } from '@/api/portfolio'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits(['update:modelValue', 'refresh'])

const visible = ref(props.modelValue)
const loading = ref(false)
const changes = ref<PositionChange[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(50)

const editVisible = ref(false)
const editSubmitting = ref(false)
const editForm = ref<{
  id: string
  code: string
  name: string
  currency: string
  change_type: string
  quantity: number
  price: number
  trade_time?: string
}>({
  id: '',
  code: '',
  name: '',
  currency: 'CNY',
  change_type: '',
  quantity: 0,
  price: 0
})

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

function getEditQuantity(row: PositionChange): number {
  return row.change_type === 'buy' || row.change_type === 'add'
    ? row.quantity_change
    : Math.abs(row.quantity_change)
}

function getEditPrice(row: PositionChange): number {
  if (row.change_type === 'buy' || row.change_type === 'add') {
    if (row.quantity_change > 0 && row.cost_value_before !== undefined && row.cost_value_after !== undefined) {
      return (row.cost_value_after - row.cost_value_before) / row.quantity_change
    }
    return row.cost_price_after
  }
  return row.trade_price ?? 0
}

const openEdit = (row: PositionChange) => {
  editForm.value = {
    id: row.id,
    code: row.code,
    name: row.name,
    currency: row.currency,
    change_type: row.change_type,
    quantity: getEditQuantity(row),
    price: getEditPrice(row),
    trade_time: row.trade_time ? String(row.trade_time).slice(0, 10) : undefined
  }
  editVisible.value = true
}

const resetEditForm = () => {
  editForm.value = { id: '', code: '', name: '', currency: 'CNY', change_type: '', quantity: 0, price: 0 }
}

const confirmDelete = async (row: PositionChange) => {
  try {
    await ElMessageBox.confirm(
      `确定删除该条${getChangeTypeName(row.change_type)}记录？删除后将自动重算后续记录。`,
      '确认删除',
      { type: 'warning' }
    )
    await portfolioApi.deletePositionChange(row.id)
    ElMessage.success('删除成功')
    loadData()
    emit('refresh')
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

const confirmResetPosition = async () => {
  const code = filters.value.code
  if (!code) return
  const market = filters.value.market || 'CN'
  try {
    await ElMessageBox.confirm(
      `确定重置 ${code} 的整个持仓？将删除该股票的所有变动记录和持仓，此操作不可恢复。`,
      '确认重置',
      { type: 'warning' }
    )
    const res = await portfolioApi.resetPosition(code, market)
    ElMessage.success(`重置成功，已删除 ${res.data?.deleted_changes ?? 0} 条记录`)
    filters.value.code = ''
    loadData()
    emit('refresh')
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e.message || '重置失败')
  }
}

const submitEdit = async () => {
  const { id, quantity, price, trade_time } = editForm.value
  if (!quantity || quantity <= 0) {
    ElMessage.warning('请输入有效的数量')
    return
  }
  if (!price || price <= 0) {
    ElMessage.warning('请输入有效的单价')
    return
  }
  editSubmitting.value = true
  try {
    await portfolioApi.updatePositionChange(id, { quantity, price, trade_time })
    ElMessage.success('记录修正成功')
    editVisible.value = false
    loadData()
    emit('refresh')
  } catch (e: any) {
    ElMessage.error(e.message || '修正失败')
  } finally {
    editSubmitting.value = false
  }
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
.text-success { color: #f56c6c; } /* 红色表示成功/盈利（中国股市规范） */
.text-danger { color: #67c23a; } /* 绿色表示危险/亏损（中国股市规范） */
.sub-text { font-size: 11px; color: #909399; }
.edit-tip { font-size: 12px; color: #909399; margin-bottom: 16px; }
.unit-hint { margin-left: 8px; font-size: 12px; color: #909399; }
</style>

