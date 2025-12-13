<template>
  <el-dialog
    v-model="visible"
    :title="dialogTitle"
    width="500px"
    :close-on-click-modal="false"
  >
    <el-form :model="form" label-width="100px">
      <el-form-item label="复盘周期" required>
        <el-radio-group v-model="form.period_type" @change="updateDateRange">
          <el-radio value="week">周度</el-radio>
          <el-radio value="month">月度</el-radio>
          <el-radio value="quarter">季度</el-radio>
          <el-radio value="year">年度</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="时间范围" required>
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          style="width: 100%"
          :shortcuts="dateShortcuts"
        />
      </el-form-item>

      <el-form-item>
        <el-alert type="info" :closable="false" show-icon>
          <template #title>
            {{ alertText }}
          </template>
        </el-alert>
      </el-form-item>
    </el-form>
    
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" :disabled="!dateRange" @click="submit">
        开始复盘
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { reviewApi, type PeriodType } from '@/api/review'

const props = withDefaults(defineProps<{
  modelValue: boolean
  source?: 'paper' | 'position'  // 数据源: paper(模拟交易) 或 position(持仓操作)
}>(), {
  source: 'paper'
})
const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'success', reviewId: string): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const dialogTitle = computed(() => {
  return props.source === 'position' ? '发起阶段性复盘（持仓操作）' : '发起阶段性复盘（模拟交易）'
})

const alertText = computed(() => {
  return props.source === 'position'
    ? '阶段性复盘将分析选定时间段内的所有持仓操作，生成综合评估报告'
    : '阶段性复盘将分析选定时间段内的所有模拟交易，生成综合评估报告'
})

const form = ref<{ period_type: PeriodType }>({
  period_type: 'month'
})

const dateRange = ref<[string, string] | null>(null)
const submitting = ref(false)

// 日期快捷选项
const dateShortcuts = [
  {
    text: '上周',
    value: () => {
      const end = new Date()
      const start = new Date()
      const day = end.getDay() || 7
      end.setDate(end.getDate() - day)
      start.setDate(end.getDate() - 6)
      return [start, end]
    }
  },
  {
    text: '本月',
    value: () => {
      const end = new Date()
      const start = new Date(end.getFullYear(), end.getMonth(), 1)
      return [start, end]
    }
  },
  {
    text: '上月',
    value: () => {
      const end = new Date()
      end.setDate(0) // 上月最后一天
      const start = new Date(end.getFullYear(), end.getMonth(), 1)
      return [start, end]
    }
  },
  {
    text: '本季度',
    value: () => {
      const end = new Date()
      const quarter = Math.floor(end.getMonth() / 3)
      const start = new Date(end.getFullYear(), quarter * 3, 1)
      return [start, end]
    }
  },
  {
    text: '今年',
    value: () => {
      const end = new Date()
      const start = new Date(end.getFullYear(), 0, 1)
      return [start, end]
    }
  }
]

// 根据周期类型更新日期范围
const updateDateRange = (type: PeriodType) => {
  const now = new Date()
  let start: Date, end: Date
  
  switch (type) {
    case 'week':
      end = new Date()
      start = new Date()
      start.setDate(end.getDate() - 7)
      break
    case 'month':
      end = new Date()
      start = new Date(now.getFullYear(), now.getMonth(), 1)
      break
    case 'quarter':
      end = new Date()
      const quarter = Math.floor(now.getMonth() / 3)
      start = new Date(now.getFullYear(), quarter * 3, 1)
      break
    case 'year':
      end = new Date()
      start = new Date(now.getFullYear(), 0, 1)
      break
  }
  
  const formatDate = (d: Date) => d.toISOString().split('T')[0]
  dateRange.value = [formatDate(start), formatDate(end)]
}

const submit = async () => {
  if (!dateRange.value || dateRange.value.length !== 2) {
    ElMessage.warning('请选择时间范围')
    return
  }

  try {
    submitting.value = true
    const res = await reviewApi.createPeriodicReview({
      period_type: form.value.period_type,
      start_date: dateRange.value[0],
      end_date: dateRange.value[1],
      source: props.source
    })

    if (res.success && res.data?.review_id) {
      ElMessage.success('阶段性复盘完成')
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

// 初始化日期范围
watch(visible, (val) => {
  if (val) {
    updateDateRange(form.value.period_type)
  }
})
</script>

