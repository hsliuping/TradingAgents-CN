<template>
  <el-dialog
    v-model="visible"
    title="保存到案例库"
    width="500px"
    @close="handleClose"
  >
    <el-form :model="form" label-width="80px">
      <el-form-item label="股票代码">
        <el-input v-model="stockCode" disabled />
      </el-form-item>
      
      <el-form-item label="标签">
        <el-select
          v-model="form.tags"
          multiple
          filterable
          allow-create
          placeholder="选择或创建标签（可选）"
          style="width: 100%"
        >
          <el-option
            v-for="tag in availableTags"
            :key="tag"
            :label="tag"
            :value="tag"
          />
        </el-select>
        <div style="margin-top: 8px; font-size: 12px; color: #909399;">
          提示：可以输入新标签并按回车创建
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">
        保存
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { reviewApi } from '@/api/review'

const props = defineProps<{
  modelValue: boolean
  reviewId: string
  stockCode?: string
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
  tags: [] as string[]
})

const submitting = ref(false)

// 常用标签（可以从后端获取）
const availableTags = ref([
  '成功案例',
  '失败案例',
  '止损及时',
  '止盈过早',
  '追涨杀跌',
  '逆势操作',
  '仓位管理',
  '情绪化交易',
  '纪律性强',
  '需要改进'
])

const stockCode = computed(() => props.stockCode || '')

const handleClose = () => {
  form.value.tags = []
}

const submit = async () => {
  try {
    submitting.value = true
    const res = await reviewApi.saveAsCase({
      review_id: props.reviewId,
      tags: form.value.tags
    })
    
    if (res.success) {
      ElMessage.success('已保存到案例库')
      emit('success')
      visible.value = false
    }
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    submitting.value = false
  }
}

// 监听对话框打开，重置表单
watch(visible, (val) => {
  if (val) {
    form.value.tags = []
  }
})
</script>

<style scoped lang="scss">
// 样式可以根据需要添加
</style>

