<template>
  <el-dialog
    v-model="visible"
    title="任务详情"
    width="1200px"
    :close-on-click-modal="false"
    destroy-on-close
  >
    <div v-loading="loading" class="task-detail">
      <template v-if="taskDetail">
        <!-- 基本信息 -->
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="card-header">
              <el-icon><InfoFilled /></el-icon>
              <span>基本信息</span>
            </div>
          </template>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="任务ID" :span="2">
              <el-text copyable>{{ taskDetail.task_id }}</el-text>
            </el-descriptions-item>
            <el-descriptions-item label="任务类型">
              <el-tag>{{ TaskTypeNames[taskDetail.task_type] || taskDetail.task_type }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="TaskStatusColors[taskDetail.status]">
                {{ TaskStatusNames[taskDetail.status] || taskDetail.status }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="进度">
              <el-progress 
                :percentage="taskDetail.progress" 
                :status="taskDetail.status === 'failed' ? 'exception' : (taskDetail.status === 'completed' ? 'success' : undefined)"
              />
            </el-descriptions-item>
            <el-descriptions-item label="当前步骤">
              {{ taskDetail.current_step || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="引擎类型">
              {{ taskDetail.engine_type }}
            </el-descriptions-item>
            <el-descriptions-item label="偏好类型">
              {{ taskDetail.preference_type }}
            </el-descriptions-item>
            <el-descriptions-item label="工作流ID">
              {{ taskDetail.workflow_id || '-' }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>

        <!-- 时间信息 -->
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="card-header">
              <el-icon><Clock /></el-icon>
              <span>时间信息</span>
            </div>
          </template>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="创建时间">
              {{ formatTime(taskDetail.created_at) }}
            </el-descriptions-item>
            <el-descriptions-item label="开始时间">
              {{ taskDetail.started_at ? formatTime(taskDetail.started_at) : '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="完成时间">
              {{ taskDetail.completed_at ? formatTime(taskDetail.completed_at) : '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="执行时间">
              {{ taskDetail.execution_time > 0 ? taskDetail.execution_time.toFixed(2) + 's' : '-' }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>

        <!-- 任务参数 -->
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="card-header">
              <el-icon><Setting /></el-icon>
              <span>任务参数</span>
            </div>
          </template>
          <el-descriptions :column="2" border>
            <template v-for="(value, key) in taskDetail.task_params" :key="key">
              <el-descriptions-item :label="formatLabel(key)">
                <template v-if="isArray(value)">
                  <el-tag 
                    v-for="(item, idx) in value" 
                    :key="idx" 
                    style="margin-right: 4px; margin-bottom: 4px"
                  >
                    {{ formatArrayItem(key, item) }}
                  </el-tag>
                </template>
                <template v-else-if="isObject(value)">
                  <el-collapse>
                    <el-collapse-item :title="`查看 ${formatLabel(key)} 详情`" :name="key">
                      <pre class="json-content">{{ JSON.stringify(value, null, 2) }}</pre>
                    </el-collapse-item>
                  </el-collapse>
                </template>
                <template v-else>
                  {{ formatValue(value) }}
                </template>
              </el-descriptions-item>
            </template>
          </el-descriptions>
        </el-card>

        <!-- 执行统计 -->
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="card-header">
              <el-icon><DataAnalysis /></el-icon>
              <span>执行统计</span>
            </div>
          </template>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="重试次数">
              {{ taskDetail.retry_count }} / {{ taskDetail.max_retries }}
            </el-descriptions-item>
            <el-descriptions-item label="Token使用量">
              {{ taskDetail.tokens_used || 0 }}
            </el-descriptions-item>
            <el-descriptions-item label="成本">
              {{ taskDetail.cost ? '¥' + taskDetail.cost.toFixed(4) : '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="用户ID">
              <el-text copyable>{{ taskDetail.user_id }}</el-text>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>

        <!-- 错误信息 -->
        <el-card v-if="taskDetail.error_message" shadow="never" class="section-card error-card">
          <template #header>
            <div class="card-header">
              <el-icon><Warning /></el-icon>
              <span>错误信息</span>
            </div>
          </template>
          <el-alert
            :title="taskDetail.error_message"
            type="error"
            :closable="false"
            show-icon
          />
        </el-card>

        <!-- 单股分析任务 - 查看报告按钮（即使没有结果数据也显示） -->
        <el-card v-if="isStockAnalysisTask && !hasResult" shadow="never" class="section-card">
          <template #header>
            <div class="card-header">
              <el-icon><Document /></el-icon>
              <span>分析报告</span>
            </div>
          </template>
          <div style="padding: 16px;">
            <el-button
              type="primary"
              @click="goToReport"
            >
              <el-icon><Document /></el-icon>
              查看分析报告
            </el-button>
          </div>
        </el-card>

        <!-- 结果数据（如果有） -->
        <el-card v-if="hasResult" shadow="never" class="section-card">
          <template #header>
            <div class="card-header" style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <el-icon><Document /></el-icon>
                <span>结果数据</span>
              </div>
              <el-button
                v-if="isStockAnalysisTask"
                type="primary"
                size="small"
                @click="goToReport"
              >
                <el-icon><Document /></el-icon>
                查看报告
              </el-button>
            </div>
          </template>
          <el-collapse>
            <el-collapse-item title="查看结果详情" name="result">
              <pre class="json-content">{{ JSON.stringify(taskDetail.result, null, 2) }}</pre>
            </el-collapse-item>
          </el-collapse>
        </el-card>
      </template>

      <el-empty v-else-if="!loading" description="暂无数据" />
    </div>

    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { InfoFilled, Clock, Setting, DataAnalysis, Warning, Document } from '@element-plus/icons-vue'
import { TaskType, TaskTypeNames, TaskStatusNames, TaskStatusColors, type TaskDetail } from '@/api/unifiedTasks'
import { convertAnalystIdsToNames } from '@/constants/analysts'

const props = defineProps<{
  modelValue: boolean
  taskId?: string
  taskDetail?: TaskDetail | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const loading = ref(false)
const router = useRouter()

// 判断是否有结果数据
const hasResult = computed(() => {
  return props.taskDetail?.result && Object.keys(props.taskDetail.result).length > 0
})

// 判断是否是单股分析任务
const isStockAnalysisTask = computed(() => {
  const taskType = props.taskDetail?.task_type
  // 兼容字符串和枚举值，以及中文名称
  const isStockAnalysis = taskType === TaskType.STOCK_ANALYSIS || 
                          taskType === 'stock_analysis' ||
                          taskType === '股票分析'
  
  // 调试日志
  if (process.env.NODE_ENV === 'development') {
    console.log('[TaskDetailDialog] 任务类型判断:', {
      taskType,
      TaskType_STOCK_ANALYSIS: TaskType.STOCK_ANALYSIS,
      isStockAnalysis
    })
  }
  
  return isStockAnalysis
})

// 获取报告ID（从任务结果中提取）
const reportId = computed(() => {
  // 对于单股分析任务，优先使用 task_id（因为报告API支持通过 task_id 查询）
  if (isStockAnalysisTask.value && props.taskDetail?.task_id) {
    // 如果有result，优先使用result中的analysis_id
    if (props.taskDetail?.result) {
      const result = props.taskDetail.result
      // 优先使用 analysis_id，其次使用 task_id
      const id = result.analysis_id || props.taskDetail.task_id
      
      // 调试日志（开发环境）
      if (process.env.NODE_ENV === 'development') {
        console.log('[TaskDetailDialog] 报告ID提取:', {
          taskType: props.taskDetail?.task_type,
          task_id: props.taskDetail.task_id,
          result_analysis_id: result.analysis_id,
          result_report_id: result.report_id,
          final_reportId: id
        })
      }
      
      return id
    }
    
    // 如果没有result，直接使用task_id
    return props.taskDetail.task_id
  }
  
  return null
})

// 跳转到报告详情页
const goToReport = () => {
  // 优先使用 reportId，如果没有则使用 task_id
  const id = reportId.value || props.taskDetail?.task_id
  
  if (!id) {
    console.error('[TaskDetailDialog] 无法跳转：缺少报告ID', {
      reportId: reportId.value,
      task_id: props.taskDetail?.task_id,
      taskDetail: props.taskDetail
    })
    ElMessage.error('无法获取报告ID，请稍后重试')
    return
  }
  
  // 调试日志
  if (process.env.NODE_ENV === 'development') {
    console.log('[TaskDetailDialog] 跳转到报告详情页:', {
      reportId: id,
      task_id: props.taskDetail?.task_id,
      task_type: props.taskDetail?.task_type
    })
  }
  
  try {
    router.push(`/reports/view/${id}`)
    visible.value = false // 关闭对话框
  } catch (error) {
    console.error('[TaskDetailDialog] 跳转失败:', error)
    ElMessage.error('跳转失败，请稍后重试')
  }
}

// 格式化标签
const formatLabel = (key: string): string => {
  const labelMap: Record<string, string> = {
    symbol: '股票代码',
    stock_code: '股票代码',
    code: '代码',
    market_type: '市场类型',
    market: '市场',
    analysis_date: '分析日期',
    research_depth: '研究深度',
    selected_analysts: '选择的分析师',
    custom_prompt: '自定义提示词',
    include_sentiment: '包含情绪分析',
    include_risk: '包含风险评估',
    language: '语言',
    quick_analysis_model: '快速分析模型',
    deep_analysis_model: '深度分析模型',
    workflow_id: '工作流ID',
    preference_type: '偏好类型',
    position_type: '持仓类型',
    risk_tolerance: '风险承受度',
    ticker: '股票代码',
    company_name: '公司名称',
    market_name: '市场名称',
    currency_name: '货币名称',
    currency_symbol: '货币符号',
    lookback_days: '回看天数',
    max_debate_rounds: '最大辩论轮数'
  }
  return labelMap[key] || key
}

// 格式化值
const formatValue = (value: any): string => {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'string' && value.length > 100) {
    return value.substring(0, 100) + '...'
  }
  return String(value)
}

// 格式化数组项（特殊处理分析师名称）
const formatArrayItem = (key: string, item: any): string => {
  // 如果是选择的分析师字段，将英文ID转换为中文名称
  if (key === 'selected_analysts' && typeof item === 'string') {
    const chineseNames = convertAnalystIdsToNames([item])
    return chineseNames[0] || item
  }
  return String(item)
}

// 判断是否为数组
const isArray = (value: any): boolean => {
  return Array.isArray(value)
}

// 判断是否为对象
const isObject = (value: any): boolean => {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
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
    minute: '2-digit',
    second: '2-digit'
  })
}
</script>

<style scoped lang="scss">
.task-detail {
  .section-card {
    margin-bottom: 16px;

    &:last-child {
      margin-bottom: 0;
    }

    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      font-weight: 600;
      font-size: 16px;
      width: 100%;
      
      // 确保按钮显示
      .el-button {
        flex-shrink: 0;
        margin-left: auto;
      }
    }

    &.error-card {
      border-color: #f56c6c;
    }
  }

  .json-content {
    background-color: #f5f7fa;
    padding: 12px;
    border-radius: 4px;
    font-size: 12px;
    line-height: 1.6;
    overflow-x: auto;
    max-height: 400px;
    overflow-y: auto;
    margin: 0;
  }

  :deep(.el-descriptions__label) {
    font-weight: 600;
    width: 150px;
  }

  :deep(.el-descriptions__content) {
    word-break: break-word;
  }
}
</style>

