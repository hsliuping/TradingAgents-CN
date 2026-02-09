<template>
  <el-dialog
    v-model="visible"
    title="发起交易复盘"
    width="600px"
    :close-on-click-modal="false"
  >
    <el-form :model="form" label-width="100px">
      <el-form-item label="股票代码" required>
        <el-input
          v-model="form.code"
          placeholder="请输入股票代码"
          :disabled="!!presetCode"
          @blur="loadTrades"
        />
        <div v-if="presetCode" class="preset-hint">
          从可复盘交易列表选择的股票
        </div>
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
      <el-button 
        type="primary" 
        :loading="submitting" 
        :disabled="isSubmitDisabled" 
        @click="submit"
      >
        开始复盘
      </el-button>
      <!-- 调试信息 -->
      <div v-if="isSubmitDisabled" style="font-size: 12px; color: #909399; margin-top: 8px; padding: 8px; background: #f5f7fa; border-radius: 4px;">
        <div>调试信息:</div>
        <div>• selectedTradeIds.length = {{ selectedTradeIds.length }}</div>
        <div>• trades.length = {{ trades.length }}</div>
        <div>• form.code = {{ form.code || '(空)' }}</div>
        <div>• presetCode = {{ presetCode || '(无)' }}</div>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { reviewApi, type TradeRecord, type ReviewType } from '@/api/review'
import { formatDateTime } from '@/utils/datetime'

const props = defineProps<{
  modelValue: boolean
  presetCode?: string  // 预设的股票代码
  source?: 'paper' | 'real'  // 数据源: paper(模拟交易) 或 real(用户持仓)
}>()
const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'success', reviewId: string): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

// 预设代码 (在模板中使用)
const presetCode = computed(() => props.presetCode)

const form = ref<{ code: string; review_type: ReviewType }>({
  code: '',
  review_type: 'complete_trade'
})

const trades = ref<TradeRecord[]>([])
const tradeSummary = ref<any>(null)
const selectedTradeIds = ref<string[]>([])
const submitting = ref(false)

// 计算属性：按钮是否可用
const isSubmitDisabled = computed(() => {
  const disabled = selectedTradeIds.value.length === 0
  console.log('[NewReviewDialog] 按钮状态检查', {
    selectedTradeIdsCount: selectedTradeIds.value.length,
    tradesCount: trades.value.length,
    code: form.value.code,
    disabled
  })
  return disabled
})

// 监听预设代码变化，自动设置并加载交易记录
watch(() => props.presetCode, (newCode) => {
  if (newCode && visible.value) {
    form.value.code = newCode
    loadTrades()
  }
}, { immediate: true })

// 监听对话框打开，如果有预设代码则自动加载
watch(visible, (isVisible) => {
  if (isVisible && props.presetCode) {
    form.value.code = props.presetCode
    loadTrades()
  } else if (!isVisible) {
    // 关闭时重置
    form.value.code = ''
    trades.value = []
    tradeSummary.value = null
    selectedTradeIds.value = []
  }
})

onMounted(() => {
  console.log('[NewReviewDialog] 组件已挂载', {
    modelValue: props.modelValue,
    presetCode: props.presetCode,
    source: props.source
  })
})

const loadTrades = async () => {
  console.log('[NewReviewDialog] loadTrades 开始', { code: form.value.code })
  
  if (!form.value.code) {
    console.log('[NewReviewDialog] 股票代码为空，清空交易记录')
    trades.value = []
    tradeSummary.value = null
    selectedTradeIds.value = []
    return
  }
  
  try {
    console.log('[NewReviewDialog] 调用 API 获取交易记录', { code: form.value.code })
    const res = await reviewApi.getTradesByCode(form.value.code)
    console.log('[NewReviewDialog] API 响应', res)
    
    if (res.success) {
      trades.value = res.data?.trades || []
      tradeSummary.value = res.data?.summary || null
      // 默认全选
      selectedTradeIds.value = trades.value.map(t => t.trade_id)
      console.log('[NewReviewDialog] 交易记录加载成功', {
        tradesCount: trades.value.length,
        selectedTradeIdsCount: selectedTradeIds.value.length,
        selectedTradeIds: selectedTradeIds.value
      })
    } else {
      console.error('[NewReviewDialog] API 返回失败', res)
      ElMessage.error(res.message || '加载交易记录失败')
    }
  } catch (e: any) {
    console.error('[NewReviewDialog] 加载交易记录异常', e)
    ElMessage.error(e.message || '加载交易记录失败')
  }
}

const handleSelectionChange = (selected: TradeRecord[]) => {
  selectedTradeIds.value = selected.map(t => t.trade_id)
}

const submit = async () => {
  console.log('[NewReviewDialog] 提交复盘请求', {
    selectedTradeIds: selectedTradeIds.value,
    selectedTradeIdsCount: selectedTradeIds.value.length,
    review_type: form.value.review_type,
    code: form.value.code,
    trades: trades.value
  })
  
  if (selectedTradeIds.value.length === 0) {
    console.warn('[NewReviewDialog] 没有选中的交易记录')
    ElMessage.warning('请选择要复盘的交易记录')
    return
  }
  
  try {
    submitting.value = true
    const source = props.source || 'paper'  // 默认使用模拟交易
    const requestData = {
      trade_ids: selectedTradeIds.value,
      review_type: form.value.review_type,
      code: form.value.code,
      source: source  // 传递数据源参数
    }
    console.log('[NewReviewDialog] 调用创建复盘 API', requestData)
    
    const res = await reviewApi.createTradeReview(requestData)
    console.log('[NewReviewDialog] 创建复盘 API 响应', res)
    
    if (res.success && res.data?.review_id) {
      ElMessage.success('复盘完成')
      emit('success', res.data.review_id)
    } else {
      console.error('[NewReviewDialog] 创建复盘失败', res)
      ElMessage.error(res.message || '复盘失败')
    }
  } catch (e: any) {
    console.error('[NewReviewDialog] 创建复盘异常', e)
    ElMessage.error(e.message || '复盘失败')
  } finally {
    submitting.value = false
  }
}

// 对话框显示/隐藏时的处理
watch(visible, async (val) => {
  console.log('[NewReviewDialog] 对话框状态变化', { visible: val, presetCode: props.presetCode })
  
  if (val) {
    // 打开对话框时，如果有预设代码则自动加载
    if (props.presetCode) {
      console.log('[NewReviewDialog] 使用预设代码', props.presetCode)
      form.value.code = props.presetCode
      await loadTrades()
    } else {
      console.log('[NewReviewDialog] 没有预设代码，需要手动输入')
      // 重置状态
      form.value = { code: '', review_type: 'complete_trade' }
      trades.value = []
      tradeSummary.value = null
      selectedTradeIds.value = []
    }
  } else {
    // 关闭对话框时重置表单
    console.log('[NewReviewDialog] 关闭对话框，重置表单')
    form.value = { code: '', review_type: 'complete_trade' }
    trades.value = []
    tradeSummary.value = null
    selectedTradeIds.value = []
  }
})
</script>

<style scoped lang="scss">
.preset-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
.summary {
  margin-top: 12px;
  font-size: 13px;
  color: #606266;
  span { margin-right: 16px; }
}
.positive { color: #f56c6c; }  // 中国习惯：红色表示盈利（正数）
.negative { color: #67c23a; }  // 中国习惯：绿色表示亏损（负数）
</style>

