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
            <el-descriptions-item label="候选记忆数">
              {{ growthSummary.memory_items_count }}
            </el-descriptions-item>
            <el-descriptions-item label="成长建议数">
              {{ growthSummary.suggestions_count }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>

        <!-- 执行轨迹（v4.0 T4 可观测性） -->
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="card-header" style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <el-icon><Histogram /></el-icon>
                <span>执行轨迹</span>
              </div>
              <el-text v-if="trace?.has_trace" type="info" size="small">
                {{ trace.total_steps }} 步 · 总耗时 {{ formatDuration(trace.duration_seconds) }}
              </el-text>
            </div>
          </template>

          <div v-loading="traceLoading">
            <el-table
              v-if="trace?.has_trace"
              :data="trace.steps"
              size="small"
              border
              max-height="420"
            >
              <el-table-column type="expand">
                <template #default="{ row }">
                  <div class="trace-channels">
                    <span class="trace-channels-label">本步变更字段：</span>
                    <el-tag
                      v-for="ch in row.updated_channels"
                      :key="ch"
                      size="small"
                      type="info"
                      style="margin: 2px 6px 2px 0"
                    >
                      {{ ch }}
                    </el-tag>
                    <el-text v-if="!row.updated_channels?.length" type="info" size="small">无</el-text>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="步骤" width="80">
                <template #default="{ row }">
                  {{ row.step >= 0 ? row.step : '准备' }}
                </template>
              </el-table-column>
              <el-table-column label="执行节点" min-width="220">
                <template #default="{ row }">
                  <template v-if="row.nodes?.length">
                    <el-tag
                      v-for="node in row.nodes"
                      :key="node"
                      size="small"
                      style="margin: 2px 6px 2px 0"
                    >
                      {{ nodeLabel(node) }}
                    </el-tag>
                  </template>
                  <el-text v-else type="info" size="small">{{ row.source === 'input' ? '初始状态' : '-' }}</el-text>
                </template>
              </el-table-column>
              <el-table-column label="时间" width="110">
                <template #default="{ row }">
                  {{ formatClock(row.timestamp) }}
                </template>
              </el-table-column>
              <el-table-column label="耗时" width="110">
                <template #default="{ row }">
                  {{ formatDuration(row.elapsed_seconds) }}
                </template>
              </el-table-column>
            </el-table>
            <el-empty
              v-else-if="!traceLoading"
              description="该任务没有断点轨迹（旧版本执行或 checkpointer 未启用）"
              :image-size="60"
            />
          </div>
        </el-card>

        <TaskGrowthPanel
          class="section-card"
          :task-id="taskDetail.task_id"
          :initial-context="growthContext"
          close-on-navigate
          @navigated="visible = false"
          @updated="handleGrowthUpdated"
        />

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

        <!-- 单股研究任务 - 查看报告按钮（即使没有结果数据也显示） -->
        <el-card v-if="isStockAnalysisTask && !hasResult" shadow="never" class="section-card">
          <template #header>
            <div class="card-header">
              <el-icon><Document /></el-icon>
              <span>研究报告</span>
            </div>
          </template>
          <div style="padding: 16px;">
            <el-button
              type="primary"
              @click="goToReport"
            >
              <el-icon><Document /></el-icon>
              查看研究报告
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
import { InfoFilled, Clock, Setting, DataAnalysis, Warning, Document, Histogram } from '@element-plus/icons-vue'
import { TaskType, TaskTypeNames, TaskStatusNames, TaskStatusColors, getTaskTrace, type TaskDetail, type TaskTrace } from '@/api/unifiedTasks'
import type { TaskGrowthContextPayload } from '@/api/workflowGrowth'
import TaskGrowthPanel from '@/components/growth/TaskGrowthPanel.vue'
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
const growthContext = ref<TaskGrowthContextPayload | null>(null)

// 执行轨迹
const trace = ref<TaskTrace | null>(null)
const traceLoading = ref(false)

// 节点名 → 中文展示（未知节点回退原始名）
const NODE_LABELS: Record<string, string> = {
  parallel_analysts: '并行分析师调度',
  fundamentals_analyst_v2: '基本面分析师',
  market_analyst_v2: '技术面分析师',
  news_analyst_v2: '新闻分析师',
  social_analyst_v2: '情绪分析师',
  index_analyst_v2: '指数分析师',
  sector_analyst_v2: '行业分析师',
  merge_analysts: '汇总分析师报告',
  debate: '多空辩论',
  debate_parallel_opening: '多空辩论（并行开场）',
  research_manager_v2: '研究经理决策',
  risk_debate: '风险辩论',
  risky_analyst_v2: '激进风险分析师',
  safe_analyst_v2: '保守风险分析师',
  neutral_analyst_v2: '中性风险分析师',
  risk_manager_v2: '风控经理裁决',
  trader_v2: '交易员投资计划'
}

const nodeLabel = (node: string): string => {
  if (NODE_LABELS[node]) return NODE_LABELS[node]
  if (node.startsWith('msg_clear_')) {
    return `清理上下文：${node.replace('msg_clear_', '').replace(/_v2$/, '')}`
  }
  return node
}

const formatClock = (time?: string | null): string => {
  if (!time) return '-'
  const date = new Date(time)
  return date.toLocaleTimeString('zh-CN', { hour12: false })
}

const formatDuration = (seconds?: number | null): string => {
  if (seconds === null || seconds === undefined) return '-'
  if (seconds < 1) return '<1s'
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m}m${s}s`
}

const loadTrace = async (taskId?: string) => {
  trace.value = null
  if (!taskId) return
  traceLoading.value = true
  try {
    const res = await getTaskTrace(taskId)
    trace.value = ((res as any)?.data?.data || (res as any)?.data || null) as TaskTrace | null
  } catch (error) {
    console.warn('[TaskDetailDialog] 加载执行轨迹失败:', error)
    trace.value = null
  } finally {
    traceLoading.value = false
  }
}

const growthSummary = computed(() => {
  const direct = growthContext.value?.summary
  const fromTask = props.taskDetail?.growth_context
  const fromResult = props.taskDetail?.result?.growth_context

  return {
    memory_items_count: direct?.memory_items_count ?? fromTask?.memory_items_count ?? fromResult?.memory_items_count ?? 0,
    suggestions_count: direct?.suggestions_count ?? fromTask?.suggestions_count ?? fromResult?.suggestions_count ?? 0
  }
})

// 判断是否有结果数据
const hasResult = computed(() => {
  return props.taskDetail?.result && Object.keys(props.taskDetail.result).length > 0
})

// 判断是否是单股研究任务
const isStockAnalysisTask = computed(() => {
  const taskType = props.taskDetail?.task_type
  const isStockAnalysis = taskType === TaskType.STOCK_ANALYSIS || taskType === TaskType.ETF_ANALYSIS
  
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

const handleGrowthUpdated = (context: TaskGrowthContextPayload | null) => {
  growthContext.value = context
}

// 获取报告ID（从任务结果中提取）
const reportId = computed(() => {
  // 对于单股研究任务，优先使用 task_id（因为报告 API 支持通过 task_id 查询）
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

watch(
  () => [props.modelValue, props.taskId, props.taskDetail?.task_id],
  ([visible]) => {
    if (visible) {
      loadTrace(props.taskId || props.taskDetail?.task_id)
    }
  },
  { immediate: true }
)

watch(
  () => [props.modelValue, props.taskDetail?.growth_context, props.taskDetail?.result?.growth_context],
  ([visible]) => {
    if (visible) {
      growthContext.value = (props.taskDetail?.growth_context as TaskGrowthContextPayload | null)
        || (props.taskDetail?.result?.growth_context as TaskGrowthContextPayload | null)
        || null
    }
  },
  { immediate: true }
)

</script>

<style scoped lang="scss">
  .trace-channels {
    padding: 8px 16px;
    line-height: 1.8;
  }

  .trace-channels-label {
    color: #6b7280;
    font-size: 13px;
    margin-right: 6px;
  }

  .growth-item {
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 14px 16px;
    background: linear-gradient(180deg, #ffffff 0%, #fafafa 100%);
  }

  .growth-item-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 8px;
  }

  .growth-item-title-row {
    display: flex;
    flex-direction: column;
    gap: 8px;

    h4 {
      margin: 0;
      font-size: 15px;
      font-weight: 600;
      color: #1f2937;
    }
  }

  .growth-item-tags,
  .growth-actions,
  .growth-evidence {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .growth-summary-text {
    margin: 0 0 10px;
    color: #4b5563;
    line-height: 1.7;
  }

  .growth-content {
    white-space: pre-wrap;
    line-height: 1.7;
    color: #1f2937;
  }

  .growth-evidence {
    margin-top: 10px;
    align-items: center;
  }

  .growth-meta-label {
    color: #6b7280;
    font-size: 13px;
  }
</style>

