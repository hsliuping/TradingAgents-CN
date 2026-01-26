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
        <el-input 
          v-model="form.name" 
          placeholder="可选，自动获取"
          :disabled="loadingStockName"
        >
          <template #suffix>
            <el-icon v-if="loadingStockName" class="is-loading">
              <Loading />
            </el-icon>
          </template>
        </el-input>
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
import { Loading } from '@element-plus/icons-vue'
import { portfolioApi, type PositionItem, type PositionCreatePayload } from '@/api/portfolio'
import { stocksApi } from '@/api/stocks'

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
const loadingStockName = ref(false)
let fetchStockNameTimer: ReturnType<typeof setTimeout> | null = null
// 🔥 记录上一次自动获取名称时对应的股票代码，用于判断名称是否需要更新
const lastFetchedCode = ref<string>('')

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

// 🔥 自动获取股票名称
const fetchStockName = async (code: string) => {
  if (!code || code.trim().length === 0) {
    return
  }
  
  // 编辑模式下不自动获取
  if (isEdit.value) {
    return
  }
  
  // 🔥 修复问题1：对于A股市场，只有当代码长度为6位时才查询
  const trimmedCode = code.trim()
  if (form.value.market === 'CN' && trimmedCode.length !== 6) {
    // A股代码必须是6位，未输入完整时不查询
    return
  }
  
  // 🔥 修复问题3：如果代码改变了，且名称是自动获取的，应该重新查询
  const currentName = form.value.name?.trim() || ''
  const isCodeChanged = trimmedCode !== lastFetchedCode.value
  
  // 如果代码改变了，且名称是自动获取的（通过 lastFetchedCode 判断），允许重新查询
  // 如果名称是用户手动输入的（lastFetchedCode 为空或与当前代码不匹配），不自动覆盖
  if (currentName.length > 0 && currentName !== '可选，自动获取' && !isCodeChanged) {
    // 名称不为空，且代码没有改变，说明是用户手动输入的，不自动覆盖
    return
  }
  
  // 清除之前的定时器
  if (fetchStockNameTimer) {
    clearTimeout(fetchStockNameTimer)
    fetchStockNameTimer = null
  }
  
  // 防抖：500ms 后执行
  fetchStockNameTimer = setTimeout(async () => {
    try {
      loadingStockName.value = true
      const res = await stocksApi.getQuote(trimmedCode)
      
      if (res.success && res.data) {
        const stockName = res.data.name
        if (stockName) {
          form.value.name = stockName
          // 🔥 记录本次查询的股票代码，用于判断名称是否是自动获取的
          lastFetchedCode.value = trimmedCode
          // 如果获取到了市场信息，也自动更新市场
          if (res.data.market) {
            const marketMap: Record<string, string> = {
              'A股': 'CN',
              '港股': 'HK',
              '美股': 'US'
            }
            const marketCode = marketMap[res.data.market] || form.value.market
            if (marketCode !== form.value.market) {
              form.value.market = marketCode
            }
          }
        }
      }
    } catch (error: any) {
      // 静默失败，不显示错误提示（因为股票名称是可选的）
      console.debug('自动获取股票名称失败:', error)
    } finally {
      loadingStockName.value = false
    }
  }, 500)
}

// 监听股票代码变化
watch(() => form.value.code, (newCode, oldCode) => {
  const trimmedNewCode = newCode?.trim() || ''
  const trimmedOldCode = oldCode?.trim() || ''
  
  // 🔥 修复问题2：确保每次代码变化都能触发查询（如果满足条件）
  // 清除之前的定时器，确保新的输入能触发新的查询
  if (fetchStockNameTimer) {
    clearTimeout(fetchStockNameTimer)
    fetchStockNameTimer = null
  }
  
  if (trimmedNewCode.length > 0) {
    // 只有当代码发生变化时才查询（避免重复查询相同代码）
    if (trimmedNewCode !== trimmedOldCode) {
      // 🔥 修复问题3：如果代码改变了，且名称是自动获取的，先清空名称
      // 判断名称是否是自动获取的：如果 lastFetchedCode 等于旧代码，说明名称是自动获取的
      if (lastFetchedCode.value === trimmedOldCode && form.value.name && form.value.name.trim().length > 0) {
        // 名称是自动获取的，代码改变了，清空名称以便重新查询
        form.value.name = ''
        lastFetchedCode.value = ''
      }
      fetchStockName(newCode)
    }
  } else {
    // 清空代码时，也清空名称和记录
    form.value.name = ''
    lastFetchedCode.value = ''
  }
})

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
    // 编辑模式下，重置自动获取记录
    lastFetchedCode.value = ''
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
    // 清除定时器和记录
    if (fetchStockNameTimer) {
      clearTimeout(fetchStockNameTimer)
      fetchStockNameTimer = null
    }
    lastFetchedCode.value = ''
    loadingStockName.value = false
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
    // 错误已在 API 拦截器中显示，这里不再重复显示
    // 只记录日志用于调试
    console.error('添加/更新持仓失败:', e)
  } finally {
    submitting.value = false
  }
}
</script>

