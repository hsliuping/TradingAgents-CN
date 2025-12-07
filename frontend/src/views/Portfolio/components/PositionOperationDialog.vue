<template>
  <el-dialog v-model="visible" :title="`${position?.code} - ${position?.name} 持仓操作`" width="600px">
    <el-form v-if="position" :model="form" label-width="100px">
      <!-- 操作类型选择 -->
      <el-form-item label="操作类型">
        <el-radio-group v-model="form.operation_type">
          <el-radio value="add">增仓</el-radio>
          <el-radio value="reduce">减仓</el-radio>
          <el-radio value="dividend">分红</el-radio>
          <el-radio value="split">拆股</el-radio>
          <el-radio value="merge">合股</el-radio>
          <el-radio value="adjust">调整成本价</el-radio>
        </el-radio-group>
      </el-form-item>

      <!-- 增仓/减仓 -->
      <template v-if="form.operation_type === 'add' || form.operation_type === 'reduce'">
        <el-form-item label="数量">
          <el-input-number v-model="form.quantity" :min="1" :max="1000000" :step="1" />
        </el-form-item>
        <el-form-item label="价格">
          <el-input-number v-model="form.price" :min="0.01" :max="100000" :step="0.01" :precision="2" />
        </el-form-item>
        <el-form-item label="日期">
          <el-date-picker v-model="form.date" type="date" />
        </el-form-item>
      </template>

      <!-- 分红 -->
      <template v-if="form.operation_type === 'dividend'">
        <el-form-item label="分红金额">
          <el-input-number v-model="form.dividend_amount" :min="0" :step="0.01" :precision="2" />
        </el-form-item>
        <el-form-item label="分红日期">
          <el-date-picker v-model="form.date" type="date" />
        </el-form-item>
      </template>

      <!-- 拆股/合股 -->
      <template v-if="form.operation_type === 'split' || form.operation_type === 'merge'">
        <el-form-item label="比例">
          <el-input v-model="form.ratio" placeholder="例如: 2:1 或 1:2" />
        </el-form-item>
        <el-form-item label="操作日期">
          <el-date-picker v-model="form.date" type="date" />
        </el-form-item>
      </template>

      <!-- 调整成本价 -->
      <template v-if="form.operation_type === 'adjust'">
        <el-form-item label="当前成本价">
          <span class="text-gray-500">{{ position?.cost_price?.toFixed(2) }}</span>
        </el-form-item>
        <el-form-item label="新成本价">
          <el-input-number v-model="form.new_cost_price" :min="0.01" :max="100000" :step="0.01" :precision="2" />
        </el-form-item>
        <el-form-item label="操作日期">
          <el-date-picker v-model="form.date" type="date" />
        </el-form-item>
      </template>

      <el-form-item label="备注">
        <el-input v-model="form.notes" type="textarea" rows="3" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { PositionItem } from '@/api/portfolio'

interface AggregatedPosition extends PositionItem {
  position_count: number
  positions: PositionItem[]
}

const props = defineProps<{
  modelValue: boolean
  position: AggregatedPosition | null
  operationType?: 'add' | 'reduce' | 'dividend' | 'split' | 'merge' | 'adjust' | 'other'
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'refresh'): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const submitting = ref(false)
const form = ref({
  operation_type: 'add',
  quantity: 0,
  price: 0,
  dividend_amount: 0,
  ratio: '',
  new_cost_price: 0,
  date: new Date(),
  notes: ''
})

// 重置表单
watch(() => visible.value, (val) => {
  if (val) {
    // 根据 operationType 初始化操作类型
    const typeMap: Record<string, string> = {
      'add': 'add',
      'reduce': 'reduce',
      'dividend': 'dividend',
      'split': 'split',
      'merge': 'merge',
      'adjust': 'adjust',
      'other': 'dividend'
    }
    const initialType = typeMap[props.operationType || 'add'] || 'add'

    form.value = {
      operation_type: initialType,
      quantity: 0,
      price: 0,
      dividend_amount: 0,
      ratio: '',
      new_cost_price: props.position?.cost_price || 0,
      date: new Date(),
      notes: ''
    }
  }
})

const handleSubmit = async () => {
  submitting.value = true
  try {
    const { portfolioApi } = await import('@/api/portfolio')

    if (!props.position) {
      ElMessage.error('持仓信息不存在')
      return
    }

    const code = props.position.code
    const market = props.position.market

    // 构建操作请求
    const operationData: any = {
      operation_type: form.value.operation_type,
      code,
      market,
      notes: form.value.notes || undefined,
      operation_date: form.value.date ? new Date(form.value.date).toISOString() : undefined
    }

    // 根据操作类型添加不同的参数
    if (form.value.operation_type === 'add' || form.value.operation_type === 'reduce') {
      if (!form.value.quantity || form.value.quantity <= 0) {
        ElMessage.error('请输入有效的数量')
        return
      }
      if (!form.value.price || form.value.price <= 0) {
        ElMessage.error('请输入有效的价格')
        return
      }
      operationData.quantity = form.value.quantity
      operationData.price = form.value.price
    } else if (form.value.operation_type === 'dividend') {
      if (!form.value.dividend_amount || form.value.dividend_amount <= 0) {
        ElMessage.error('请输入有效的分红金额')
        return
      }
      operationData.dividend_amount = form.value.dividend_amount
    } else if (form.value.operation_type === 'split' || form.value.operation_type === 'merge') {
      if (!form.value.ratio || !form.value.ratio.includes(':')) {
        ElMessage.error('请输入有效的比例，如 2:1')
        return
      }
      operationData.ratio = form.value.ratio
    } else if (form.value.operation_type === 'adjust') {
      if (!form.value.new_cost_price || form.value.new_cost_price <= 0) {
        ElMessage.error('请输入有效的新成本价')
        return
      }
      operationData.new_cost_price = form.value.new_cost_price
    }

    // 调用统一的持仓操作API
    const result = await portfolioApi.operatePosition(operationData)

    // 根据操作类型显示不同的成功信息
    if (form.value.operation_type === 'reduce' && result.profit !== undefined) {
      const profitText = result.profit >= 0 ? `盈利 ${result.profit.toFixed(2)}` : `亏损 ${Math.abs(result.profit).toFixed(2)}`
      ElMessage.success(`${result.message}，${profitText}元 (${result.profit_pct?.toFixed(2)}%)`)
    } else {
      ElMessage.success(result.message || '操作成功')
    }

    visible.value = false
    emit('refresh')
  } catch (e: any) {
    ElMessage.error(e.message || '操作失败')
  } finally {
    submitting.value = false
  }
}
</script>
