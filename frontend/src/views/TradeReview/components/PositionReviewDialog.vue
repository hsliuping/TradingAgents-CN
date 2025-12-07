<template>
  <el-dialog
    v-model="visible"
    title="持仓操作复盘"
    width="600px"
    :close-on-click-modal="false"
  >
    <div v-if="positionData" class="position-info">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="股票代码">{{ positionData.code }}</el-descriptions-item>
        <el-descriptions-item label="股票名称">{{ positionData.name }}</el-descriptions-item>
        <el-descriptions-item label="市场">
          <el-tag size="small">{{ positionData.market }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="复盘类型">
          <el-tag size="small" :type="positionData.type === 'current' ? 'primary' : 'success'">
            {{ positionData.type === 'current' ? '当前持仓' : '历史持仓' }}
          </el-tag>
        </el-descriptions-item>
        <template v-if="positionData.type === 'current'">
          <el-descriptions-item label="持仓数量">{{ positionData.quantity }}</el-descriptions-item>
          <el-descriptions-item label="成本价">{{ positionData.cost_price?.toFixed(2) }}</el-descriptions-item>
          <el-descriptions-item label="浮动盈亏" :span="2">
            <span :class="(positionData.unrealized_pnl || 0) >= 0 ? 'positive' : 'negative'">
              {{ formatPnl(positionData.unrealized_pnl) }}
            </span>
          </el-descriptions-item>
        </template>
        <template v-else>
          <el-descriptions-item label="已实现盈亏">
            <span :class="(positionData.realized_pnl || 0) >= 0 ? 'positive' : 'negative'">
              {{ formatPnl(positionData.realized_pnl) }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="持有天数">{{ positionData.hold_days }} 天</el-descriptions-item>
        </template>
      </el-descriptions>
    </div>

    <el-divider content-position="left">复盘分析内容</el-divider>

    <el-form :model="form" label-width="100px">
      <el-form-item label="分析维度">
        <el-checkbox-group v-model="form.dimensions">
          <el-checkbox label="买入时机">买入时机</el-checkbox>
          <el-checkbox label="卖出时机">卖出时机</el-checkbox>
          <el-checkbox label="仓位管理">仓位管理</el-checkbox>
          <el-checkbox label="止盈止损">止盈止损</el-checkbox>
          <el-checkbox label="心理分析">心理分析</el-checkbox>
        </el-checkbox-group>
      </el-form-item>
      <el-form-item label="补充说明">
        <el-input
          v-model="form.notes"
          type="textarea"
          :rows="3"
          placeholder="可以补充操作时的想法、市场情况等"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">
        开始复盘
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'

interface PositionData {
  code: string
  name: string
  market: string
  type: 'current' | 'history'
  quantity?: number
  cost_price?: number
  unrealized_pnl?: number
  realized_pnl?: number
  hold_days?: number
}

const props = defineProps<{
  modelValue: boolean
  positionData: PositionData | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'success'): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const form = ref({
  dimensions: ['买入时机', '卖出时机', '仓位管理'],
  notes: ''
})

const submitting = ref(false)

watch(visible, (val) => {
  if (!val) {
    form.value = {
      dimensions: ['买入时机', '卖出时机', '仓位管理'],
      notes: ''
    }
  }
})

const formatPnl = (val?: number) => {
  if (val === undefined || val === null) return '-'
  const prefix = val >= 0 ? '+' : ''
  return prefix + val.toFixed(2)
}

const handleSubmit = async () => {
  if (form.value.dimensions.length === 0) {
    ElMessage.warning('请至少选择一个分析维度')
    return
  }
  
  try {
    submitting.value = true
    // TODO: 调用 API 创建持仓复盘
    ElMessage.info('持仓复盘功能开发中...')
    // emit('success')
  } catch (e: any) {
    ElMessage.error(e.message || '复盘失败')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped lang="scss">
.position-info {
  margin-bottom: 16px;
}
.positive { color: #67c23a; }
.negative { color: #f56c6c; }
</style>

