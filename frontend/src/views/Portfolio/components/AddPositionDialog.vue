<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    :title="isEdit ? '编辑持仓' : '添加持仓'"
    width="500px"
    destroy-on-close
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
      <el-form-item label="股票代码" prop="code">
        <el-input v-model="form.code" placeholder="如: 600519" :disabled="isEdit" />
      </el-form-item>
      <el-form-item label="股票名称" prop="name">
        <el-input v-model="form.name" placeholder="可选，自动获取" />
      </el-form-item>
      <el-form-item label="市场" prop="market">
        <el-select v-model="form.market" style="width: 100%">
          <el-option label="A股" value="CN" />
          <el-option label="港股" value="HK" />
          <el-option label="美股" value="US" />
        </el-select>
      </el-form-item>
      <el-form-item label="持仓数量" prop="quantity">
        <el-input-number v-model="form.quantity" :min="1" :step="100" style="width: 100%" />
      </el-form-item>
      <el-form-item label="成本价" prop="cost_price">
        <el-input-number v-model="form.cost_price" :min="0.01" :precision="2" :step="0.1" style="width: 100%" />
      </el-form-item>
      <el-form-item label="买入日期" prop="buy_date">
        <el-date-picker v-model="form.buy_date" type="date" placeholder="选择日期" style="width: 100%" />
      </el-form-item>
      <el-form-item label="备注" prop="notes">
        <el-input v-model="form.notes" type="textarea" :rows="2" placeholder="可选" />
      </el-form-item>
    </el-form>
    
    <template #footer>
      <el-button @click="$emit('update:visible', false)">取消</el-button>
      <el-button type="primary" @click="handleSubmit" :loading="submitting">
        {{ isEdit ? '保存' : '添加' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { portfolioApi, type PositionItem, type PositionCreatePayload } from '@/api/portfolio'

const props = defineProps<{
  visible: boolean
  editData?: PositionItem | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  'success': []
}>()

const formRef = ref<FormInstance>()
const submitting = ref(false)

const isEdit = computed(() => !!props.editData)

const form = ref<PositionCreatePayload & { buy_date?: Date | string }>({
  code: '',
  name: '',
  market: 'CN',
  quantity: 100,
  cost_price: 10,
  buy_date: undefined,
  notes: ''
})

const rules: FormRules = {
  code: [{ required: true, message: '请输入股票代码', trigger: 'blur' }],
  quantity: [{ required: true, message: '请输入持仓数量', trigger: 'blur' }],
  cost_price: [{ required: true, message: '请输入成本价', trigger: 'blur' }]
}

watch(() => props.visible, (val) => {
  if (val && props.editData) {
    form.value = {
      code: props.editData.code,
      name: props.editData.name || '',
      market: props.editData.market || 'CN',
      quantity: props.editData.quantity,
      cost_price: props.editData.cost_price,
      buy_date: props.editData.buy_date ? new Date(props.editData.buy_date) : undefined,
      notes: props.editData.notes || ''
    }
  } else if (val) {
    form.value = {
      code: '',
      name: '',
      market: 'CN',
      quantity: 100,
      cost_price: 10,
      buy_date: undefined,
      notes: ''
    }
  }
})

const handleSubmit = async () => {
  if (!formRef.value) return
  
  try {
    await formRef.value.validate()
    submitting.value = true
    
    const payload: PositionCreatePayload = {
      code: form.value.code,
      name: form.value.name || undefined,
      market: form.value.market,
      quantity: form.value.quantity,
      cost_price: form.value.cost_price,
      buy_date: form.value.buy_date ? new Date(form.value.buy_date).toISOString().split('T')[0] : undefined,
      notes: form.value.notes || undefined
    }
    
    if (isEdit.value && props.editData) {
      await portfolioApi.updatePosition(props.editData.id, {
        name: payload.name,
        quantity: payload.quantity,
        cost_price: payload.cost_price,
        buy_date: payload.buy_date,
        notes: payload.notes
      })
      ElMessage.success('更新成功')
    } else {
      await portfolioApi.addPosition(payload)
      ElMessage.success('添加成功')
    }
    
    emit('success')
  } catch (e: any) {
    if (e !== 'cancel' && e.message) {
      ElMessage.error(e.message)
    }
  } finally {
    submitting.value = false
  }
}
</script>

