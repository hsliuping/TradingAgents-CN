<template>
  <el-dialog v-model="visible" :title="`${position?.code} - ${position?.name} 持仓明细`" width="800px">
    <div v-if="position" class="position-details">
      <!-- 汇总信息 -->
      <el-card class="summary-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <span>汇总信息</span>
            <div class="action-buttons">
              <el-button type="primary" size="small" @click="handleAddOperation">增仓</el-button>
              <el-button type="warning" size="small" @click="handleReduceOperation">减仓</el-button>
              <el-button type="info" size="small" @click="handleOtherOperation">其他操作</el-button>
            </div>
          </div>
        </template>
        <el-row :gutter="20">
          <el-col :span="6">
            <div class="summary-item">
              <div class="label">总数量</div>
              <div class="value">{{ position.quantity }}</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="summary-item">
              <div class="label">平均成本价</div>
              <div class="value">{{ position.cost_price?.toFixed(2) }}</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="summary-item">
              <div class="label">总成本</div>
              <div class="value">{{ formatNumber(position.quantity * position.cost_price) }}</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="summary-item">
              <div class="label">建仓次数</div>
              <div class="value">{{ position.position_count }}</div>
            </div>
          </el-col>
        </el-row>
      </el-card>

      <!-- 明细表格 -->
      <el-table :data="position.positions" stripe style="margin-top: 16px">
        <el-table-column prop="quantity" label="数量" width="80" align="right" />
        <el-table-column prop="cost_price" label="成本价" width="100" align="right">
          <template #default="{ row }">{{ row.cost_price?.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="成本金额" width="120" align="right">
          <template #default="{ row }">{{ formatNumber(row.quantity * row.cost_price) }}</template>
        </el-table-column>
        <el-table-column prop="current_price" label="现价" width="80" align="right">
          <template #default="{ row }">{{ row.current_price?.toFixed(2) || '-' }}</template>
        </el-table-column>
        <el-table-column label="盈亏" width="100" align="right">
          <template #default="{ row }">
            <span :class="pnlClass(row.unrealized_pnl)">{{ formatPnl(row.unrealized_pnl) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="buy_date" label="建仓日期" width="110">
          <template #default="{ row }">{{ formatDate(row.buy_date) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { portfolioApi, type PositionItem } from '@/api/portfolio'

interface AggregatedPosition extends PositionItem {
  position_count: number
  positions: PositionItem[]
}

const props = defineProps<{
  modelValue: boolean
  position: AggregatedPosition | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'edit', position: PositionItem): void
  (e: 'refresh'): void
  (e: 'operation', data: { type: string; position: AggregatedPosition }): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const formatNumber = (val: number) => {
  return val.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const formatPnl = (val?: number) => {
  if (!val) return '-'
  const sign = val > 0 ? '+' : ''
  return sign + formatNumber(val)
}

const pnlClass = (val?: number) => {
  if (!val) return ''
  if (val > 0) return 'profit'
  if (val < 0) return 'loss'
  return ''
}

const formatDate = (date?: string) => {
  if (!date) return '-'
  return new Date(date).toLocaleDateString('zh-CN')
}

// 编辑单条持仓
const handleEdit = (row: PositionItem) => {
  visible.value = false
  emit('edit', row)
}

// 删除单条持仓
const handleDelete = async (row: PositionItem) => {
  try {
    await ElMessageBox.confirm(
      `确定删除这条建仓记录吗？（数量: ${row.quantity}，成本价: ${row.cost_price?.toFixed(2)}）`,
      '确认删除',
      { type: 'warning' }
    )
    await portfolioApi.deletePosition(row.id)
    ElMessage.success('删除成功')
    emit('refresh')
    // 如果只剩一条记录，关闭对话框
    if (props.position && props.position.positions.length <= 1) {
      visible.value = false
    }
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.message || '删除失败')
    }
  }
}

// 增仓操作
const handleAddOperation = () => {
  if (props.position) {
    emit('operation', { type: 'add', position: props.position })
  }
}

// 减仓操作
const handleReduceOperation = () => {
  if (props.position) {
    emit('operation', { type: 'reduce', position: props.position })
  }
}

// 其他操作（分红、拆股等）
const handleOtherOperation = () => {
  if (props.position) {
    emit('operation', { type: 'other', position: props.position })
  }
}
</script>

<style scoped>
.position-details {
  padding: 0;
}

.summary-card {
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.action-buttons {
  display: flex;
  gap: 8px;
}

.summary-item {
  text-align: center;
}

.summary-item .label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 8px;
}

.summary-item .value {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.profit {
  color: #F56C6C; /* 红色表示盈利（中国股市规范） */
}

.loss {
  color: #67C23A; /* 绿色表示亏损（中国股市规范） */
}
</style>

