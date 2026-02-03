<template>
  <el-dialog
    v-model="visible"
    :title="`${position?.name || position?.code || ''} - 分析历史`"
    width="1000px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <el-alert type="info" :closable="false" show-icon style="margin-bottom: 16px">
      查看该股票的所有分析报告历史记录
    </el-alert>

    <!-- 数据表格 -->
    <el-table :data="historyList" v-loading="loading" stripe>
      <el-table-column label="分析时间" width="160">
        <template #default="{ row }">
          {{ formatTime(row.created_at) }}
        </template>
      </el-table-column>

      <el-table-column label="持仓数量" width="100" align="right">
        <template #default="{ row }">
          {{ row.position_snapshot?.quantity || 0 }} 股
        </template>
      </el-table-column>

      <el-table-column label="成本价" width="100" align="right">
        <template #default="{ row }">
          ¥{{ (row.position_snapshot?.cost_price || 0).toFixed(2) }}
        </template>
      </el-table-column>

      <el-table-column label="当前价" width="100" align="right">
        <template #default="{ row }">
          ¥{{ (row.position_snapshot?.current_price || 0).toFixed(2) }}
        </template>
      </el-table-column>

      <el-table-column label="浮动盈亏" width="140" align="right">
        <template #default="{ row }">
          <span :class="pnlClass(row.position_snapshot?.unrealized_pnl || 0)">
            {{ formatPnl(row.position_snapshot?.unrealized_pnl || 0) }}
            ({{ formatPct(row.position_snapshot?.unrealized_pnl_pct || 0) }})
          </span>
        </template>
      </el-table-column>

      <el-table-column label="分析观点" width="100" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.action" :type="getActionType(row.action)" size="small">
            {{ getActionText(row.action) }}
          </el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>

      <el-table-column label="置信度" width="100" align="center">
        <template #default="{ row }">
          <span v-if="row.confidence">{{ row.confidence }}%</span>
          <span v-else>-</span>
        </template>
      </el-table-column>

      <el-table-column label="持仓类型" width="100" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.position_type === 'simulated' || (position?.source === 'paper')" type="warning" size="small">
            模拟持仓
          </el-tag>
          <el-tag v-else type="success" size="small">
            真实持仓
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column label="状态" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="getStatusType(row.status)">
            {{ getStatusText(row.status) }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column label="操作" width="180" align="center" fixed="right">
        <template #default="{ row }">
          <el-button
            type="primary"
            size="small"
            link
            @click="viewDetail(row)"
            :disabled="row.status !== 'completed'"
          >
            查看详情
          </el-button>
          <el-button
            type="danger"
            size="small"
            link
            @click="handleDelete(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div style="margin-top: 16px; text-align: right">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @current-change="loadData"
        @size-change="loadData"
      />
    </div>

    <!-- 详情对话框 -->
    <PositionAnalysisDetailDialog
      v-model="showDetailDialog"
      :report="selectedReport"
    />
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { portfolioApi, type PositionItem, type PositionAnalysisResult } from '@/api/portfolio'
import PositionAnalysisDetailDialog from './PositionAnalysisDetailDialog.vue'

const props = defineProps<{
  modelValue: boolean
  position: PositionItem | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()

const visible = ref(false)
const loading = ref(false)
const historyList = ref<PositionAnalysisResult[]>([])
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)
const showDetailDialog = ref(false)
const selectedReport = ref<PositionAnalysisResult | null>(null)

const positionId = computed(() => {
  if (!props.position) return null
  return `${props.position.code}_${props.position.market}`
})

watch(() => props.modelValue, (val) => {
  visible.value = val
  if (val && positionId.value) {
    loadData()
  }
})

watch(visible, (val) => emit('update:modelValue', val))

const loadData = async () => {
  if (!positionId.value) return

  loading.value = true
  try {
    // 🔥 根据持仓来源传递 source 参数：模拟持仓 -> paper，真实持仓 -> real
    const source = props.position?.source === 'paper' ? 'paper' : 'real'
    const res = await portfolioApi.getPositionAnalysisHistory(positionId.value, currentPage.value, pageSize.value, source)
    historyList.value = res.data?.items || []
    total.value = res.data?.total || 0
  } catch (e: any) {
    ElMessage.error(e.message || '加载分析历史失败')
  } finally {
    loading.value = false
  }
}

const handleClose = () => emit('update:modelValue', false)

const viewDetail = (row: PositionAnalysisResult) => {
  selectedReport.value = row
  showDetailDialog.value = true
}

// 删除分析记录
const handleDelete = async (row: PositionAnalysisResult) => {
  if (!row.analysis_id) {
    ElMessage.warning('无法获取分析ID，无法删除')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要删除这条分析记录吗？\n分析时间: ${formatTime(row.created_at)}`,
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    // 调用删除接口
    const res = await portfolioApi.deletePositionAnalysis(row.analysis_id)
    if (res.success) {
      ElMessage.success('删除成功')
      // 重新加载数据
      await loadData()
    } else {
      ElMessage.error(res.message || '删除失败')
    }
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.message || '删除失败')
    }
  }
}

// 格式化时间
const formatTime = (time: string) => {
  if (!time) return '-'
  const date = new Date(time)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 格式化盈亏
const formatPnl = (pnl: number) => {
  if (pnl === undefined || pnl === null) return '¥0.00'
  const prefix = pnl >= 0 ? '+' : ''
  return `${prefix}¥${Math.abs(pnl).toFixed(2)}`
}

// 格式化百分比
const formatPct = (pct: number) => {
  if (pct === undefined || pct === null) return '0.00%'
  const prefix = pct >= 0 ? '+' : ''
  return `${prefix}${pct.toFixed(2)}%`
}

// 盈亏样式
const pnlClass = (pnl: number) => {
  if (pnl > 0) return 'text-success'
  if (pnl < 0) return 'text-danger'
  return ''
}

// 分析观点类型
const getActionType = (action: string) => {
  if (action === 'buy' || action === 'add') return 'success'
  if (action === 'sell' || action === 'reduce') return 'danger'
  return 'info'
}

// 分析观点文本（兼容新旧术语）
const getActionText = (action: string) => {
  const map: Record<string, string> = {
    // 旧术语（后端数据可能仍使用）
    buy: '看涨',
    add: '增持观点',
    hold: '中性',
    reduce: '减持观点',
    sell: '看跌',
    // 新术语
    '看涨': '看涨',
    '看跌': '看跌',
    '中性': '中性',
    '增持观点': '增持观点',
    '减持观点': '减持观点',
    '观望观点': '观望观点'
  }
  return map[action] || action
}

// 状态类型
const getStatusType = (status: string) => {
  if (status === 'completed') return 'success'
  if (status === 'processing') return 'warning'
  if (status === 'failed') return 'danger'
  return 'info'
}

// 状态文本
const getStatusText = (status: string) => {
  const map: Record<string, string> = {
    pending: '等待中',
    processing: '分析中',
    completed: '已完成',
    failed: '失败'
  }
  return map[status] || status
}
</script>

<style scoped>
.text-success {
  color: #67c23a;
}

.text-danger {
  color: #f56c6c;
}
</style>


