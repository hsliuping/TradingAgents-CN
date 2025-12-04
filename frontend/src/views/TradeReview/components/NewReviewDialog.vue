<template>
  <el-dialog
    v-model="visible"
    title="发起交易复盘"
    width="600px"
    :close-on-click-modal="false"
  >
    <el-form :model="form" label-width="100px">
      <el-form-item label="股票代码" required>
        <el-input v-model="form.code" placeholder="请输入股票代码" @blur="loadTrades" />
      </el-form-item>
      
      <el-form-item label="交易记录" v-if="trades.length > 0">
        <el-table :data="trades" size="small" max-height="250" @selection-change="handleSelectionChange">
          <el-table-column type="selection" width="40" />
          <el-table-column prop="side" label="方向" width="60">
            <template #default="{ row }">
              <el-tag :type="row.side === 'buy' ? 'success' : 'danger'" size="small">
                {{ row.side === 'buy' ? '买入' : '卖出' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="quantity" label="数量" width="80" align="right" />
          <el-table-column prop="price" label="价格" width="80" align="right">
            <template #default="{ row }">{{ row.price?.toFixed(2) }}</template>
          </el-table-column>
          <el-table-column prop="pnl" label="盈亏" width="80" align="right">
            <template #default="{ row }">
              <span v-if="row.pnl !== 0" :class="row.pnl >= 0 ? 'positive' : 'negative'">
                {{ row.pnl?.toFixed(2) }}
              </span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column prop="timestamp" label="时间" min-width="120">
            <template #default="{ row }">{{ formatDateTime(row.timestamp) }}</template>
          </el-table-column>
        </el-table>
        
        <div class="summary" v-if="tradeSummary">
          <span>买入: {{ tradeSummary.total_buy_quantity }}股</span>
          <span>卖出: {{ tradeSummary.total_sell_quantity }}股</span>
          <span :class="tradeSummary.total_pnl >= 0 ? 'positive' : 'negative'">
            盈亏: {{ tradeSummary.total_pnl?.toFixed(2) }}
          </span>
        </div>
      </el-form-item>
      
      <el-form-item label="复盘类型">
        <el-radio-group v-model="form.review_type">
          <el-radio value="complete_trade">完整交易复盘</el-radio>
          <el-radio value="single_trade">单笔交易复盘</el-radio>
        </el-radio-group>
      </el-form-item>
    </el-form>
    
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" :disabled="selectedTradeIds.length === 0" @click="submit">
        开始复盘
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { reviewApi, type TradeRecord, type ReviewType } from '@/api/review'
import { formatDateTime } from '@/utils/datetime'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'success', reviewId: string): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const form = ref<{ code: string; review_type: ReviewType }>({
  code: '',
  review_type: 'complete_trade'
})

const trades = ref<TradeRecord[]>([])
const tradeSummary = ref<any>(null)
const selectedTradeIds = ref<string[]>([])
const submitting = ref(false)

const loadTrades = async () => {
  if (!form.value.code) {
    trades.value = []
    tradeSummary.value = null
    return
  }
  
  try {
    const res = await reviewApi.getTradesByCode(form.value.code)
    if (res.success) {
      trades.value = res.data?.trades || []
      tradeSummary.value = res.data?.summary || null
      // 默认全选
      selectedTradeIds.value = trades.value.map(t => t.trade_id)
    }
  } catch (e: any) {
    ElMessage.error(e.message || '加载交易记录失败')
  }
}

const handleSelectionChange = (selected: TradeRecord[]) => {
  selectedTradeIds.value = selected.map(t => t.trade_id)
}

const submit = async () => {
  if (selectedTradeIds.value.length === 0) {
    ElMessage.warning('请选择要复盘的交易记录')
    return
  }
  
  try {
    submitting.value = true
    const res = await reviewApi.createTradeReview({
      trade_ids: selectedTradeIds.value,
      review_type: form.value.review_type,
      code: form.value.code
    })
    
    if (res.success && res.data?.review_id) {
      ElMessage.success('复盘完成')
      emit('success', res.data.review_id)
    } else {
      ElMessage.error(res.message || '复盘失败')
    }
  } catch (e: any) {
    ElMessage.error(e.message || '复盘失败')
  } finally {
    submitting.value = false
  }
}

// 重置表单
watch(visible, (val) => {
  if (!val) {
    form.value = { code: '', review_type: 'complete_trade' }
    trades.value = []
    tradeSummary.value = null
    selectedTradeIds.value = []
  }
})
</script>

<style scoped lang="scss">
.summary {
  margin-top: 12px;
  font-size: 13px;
  color: #606266;
  span { margin-right: 16px; }
}
.positive { color: #67c23a; }
.negative { color: #f56c6c; }
</style>

