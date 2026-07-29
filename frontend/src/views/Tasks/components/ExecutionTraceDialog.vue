<template>
  <el-dialog
    v-model="visible"
    title="执行轨迹"
    width="1150px"
    :close-on-click-modal="false"
    destroy-on-close
    class="execution-trace-dialog"
  >
    <div v-loading="listLoading" class="trace-container">
      <!-- 顶部说明 -->
      <div class="trace-tip">
        <el-icon><InfoFilled /></el-icon>
        <span>本次分析共产生 <b>{{ total }}</b> 条 Agent 执行轨迹。点击某行查看详情（含 Prompt 全文、LLM 原始返回）。</span>
      </div>

      <!-- 轨迹列表 -->
      <el-table
        :data="traces"
        highlight-current-row
        @row-click="handleRowClick"
        size="small"
        border
        style="margin-bottom: 16px"
      >
        <el-table-column label="Agent" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <span>{{ row.agent_id }}</span>
            <el-tag v-if="row.manager_type" size="small" style="margin-left: 6px">
              {{ managerTypeName(row.manager_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="校验状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="validationTagType(row.validation?.validation_status)" size="small">
              {{ validationText(row.validation?.validation_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="执行" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.success ? 'success' : 'danger'" size="small">
              {{ row.success ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="耗时" width="90" align="right">
          <template #default="{ row }">
            {{ formatDuration(row.execution_duration_ms) }}
          </template>
        </el-table-column>
        <el-table-column label="Token" width="90" align="right">
          <template #default="{ row }">
            {{ row.token_usage?.total_tokens ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column label="股票" width="90">
          <template #default="{ row }">{{ row.ticker || '-' }}</template>
        </el-table-column>
        <el-table-column label="开始时间" width="160">
          <template #default="{ row }">{{ formatTime(row.started_at) }}</template>
        </el-table-column>
      </el-table>

      <!-- 详情区 -->
      <div v-loading="detailLoading" class="trace-detail">
        <template v-if="selectedDetail">
          <el-collapse v-model="activeNames">
            <!-- 基本信息 -->
            <el-collapse-item title="基本信息" name="basic">
              <el-descriptions :column="3" border size="small">
                <el-descriptions-item label="trace_id">
                  <el-text copyable size="small">{{ selectedDetail.trace_id }}</el-text>
                </el-descriptions-item>
                <el-descriptions-item label="Agent">{{ selectedDetail.agent_id }}</el-descriptions-item>
                <el-descriptions-item label="版本">{{ selectedDetail.agent_version || '-' }}</el-descriptions-item>
                <el-descriptions-item label="类型">{{ selectedDetail.agent_type || '-' }}</el-descriptions-item>
                <el-descriptions-item label="manager">{{ selectedDetail.manager_type || '-' }}</el-descriptions-item>
                <el-descriptions-item label="股票">{{ selectedDetail.ticker || '-' }}</el-descriptions-item>
                <el-descriptions-item label="分析日期">{{ selectedDetail.analysis_date || '-' }}</el-descriptions-item>
                <el-descriptions-item label="模型">{{ selectedDetail.llm_config?.model_name || '-' }}</el-descriptions-item>
                <el-descriptions-item label="执行耗时">{{ formatDuration(selectedDetail.execution_duration_ms) }}</el-descriptions-item>
                <el-descriptions-item label="LLM 耗时">{{ formatDuration(selectedDetail.llm_duration_ms) }}</el-descriptions-item>
                <el-descriptions-item label="LLM 调用次数">{{ selectedDetail.llm_call_count ?? '-' }}</el-descriptions-item>
                <el-descriptions-item label="工具调用次数">{{ selectedDetail.tool_calls?.length ?? 0 }}</el-descriptions-item>
                <el-descriptions-item label="开始">{{ formatTime(selectedDetail.started_at) }}</el-descriptions-item>
                <el-descriptions-item label="完成">{{ selectedDetail.finished_at ? formatTime(selectedDetail.finished_at) : '-' }}</el-descriptions-item>
              </el-descriptions>
            </el-collapse-item>

            <!-- 输入快照 -->
            <el-collapse-item title="输入快照（上游传入了什么）" name="inputs">
              <div v-if="selectedDetail.inputs?.input_keys?.length" class="input-keys">
                <el-tag v-for="k in selectedDetail.inputs.input_keys" :key="k" size="small" style="margin: 2px">
                  {{ k }} <span class="len">({{ selectedDetail.inputs.input_lengths[k] ?? 0 }}字)</span>
                </el-tag>
              </div>
              <el-text v-else type="info" size="small">无输入记录</el-text>
            </el-collapse-item>

            <!-- Prompt 全文 -->
            <el-collapse-item name="prompts">
              <template #title>
                System Prompt 全文
                <el-button v-if="selectedDetail.prompts?.system_prompt_full" link size="small" @click.stop="copyText(selectedDetail.prompts.system_prompt_full)">复制</el-button>
              </template>
              <pre v-if="selectedDetail.prompts?.system_prompt_full" class="prompt-block">{{ selectedDetail.prompts.system_prompt_full }}</pre>
              <el-text v-else type="info" size="small">无全文（旧数据可能只存了哈希）</el-text>
            </el-collapse-item>

            <el-collapse-item name="user-prompt">
              <template #title>
                User Prompt 全文
                <el-button v-if="selectedDetail.prompts?.user_prompt_full" link size="small" @click.stop="copyText(selectedDetail.prompts.user_prompt_full)">复制</el-button>
              </template>
              <pre v-if="selectedDetail.prompts?.user_prompt_full" class="prompt-block">{{ selectedDetail.prompts.user_prompt_full }}</pre>
              <el-text v-else type="info" size="small">无全文</el-text>
            </el-collapse-item>

            <!-- 工具调用详情 -->
            <el-collapse-item
              v-if="selectedDetail.tool_calls?.length"
              :title="`工具调用详情（${selectedDetail.tool_calls.length} 次调用）`"
              name="tool_calls"
            >
              <div class="tool-call-list">
                <div v-for="(tc, idx) in selectedDetail.tool_calls" :key="idx" class="tool-call-item">
                  <div class="tool-call-header">
                    <el-tag :type="tc.success ? 'success' : 'danger'" size="small">
                      {{ tc.success ? '成功' : '失败' }}
                    </el-tag>
                    <span class="tool-name">{{ tc.tool_name }}</span>
                    <span v-if="tc.duration_ms" class="tool-duration">{{ formatDuration(tc.duration_ms) }}</span>
                    <span class="tool-result-len">结果 {{ tc.result_length }} 字符</span>
                  </div>
                  <div v-if="tc.error" class="tool-call-error">
                    <el-text type="danger" size="small">{{ tc.error }}</el-text>
                  </div>
                  <div class="tool-call-args">
                    <span class="tool-label">参数:</span>
                    <pre class="json-block compact">{{ JSON.stringify(tc.tool_args, null, 2) }}</pre>
                  </div>
                  <div v-if="tc.result_preview" class="tool-call-result">
                    <span class="tool-label">结果预览:</span>
                    <pre class="json-block compact">{{ tc.result_preview }}</pre>
                  </div>
                </div>
              </div>
            </el-collapse-item>

            <!-- LLM 原始返回 -->
            <el-collapse-item name="output">
              <template #title>
                LLM 原始返回（{{ selectedDetail.output?.output_raw_length ?? 0 }} 字符）
                <el-button v-if="selectedDetail.output?.output_raw_full" link size="small" @click.stop="copyText(selectedDetail.output.output_raw_full)">复制</el-button>
              </template>
              <pre v-if="selectedDetail.output?.output_raw_full" class="prompt-block">{{ selectedDetail.output.output_raw_full }}</pre>
              <el-text v-else-if="selectedDetail.output?.output_raw_preview" type="warning" size="small">
                仅有前 500 字符预览（旧数据）：<pre class="prompt-block">{{ selectedDetail.output.output_raw_preview }}</pre>
              </el-text>
              <el-text v-else type="info" size="small">无输出记录</el-text>
            </el-collapse-item>

            <!-- 解析结果 -->
            <el-collapse-item title="解析结果" name="parsed">
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="解析类型">{{ selectedDetail.output?.output_parsed_type || '-' }}</el-descriptions-item>
                <el-descriptions-item label="解析成功">{{ selectedDetail.output?.output_parsed_success ?? '-' }}</el-descriptions-item>
                <el-descriptions-item label="解析字段" :span="2">
                  <el-tag v-for="k in (selectedDetail.output?.output_parsed_keys || [])" :key="k" size="small" style="margin: 2px">{{ k }}</el-tag>
                  <span v-if="!selectedDetail.output?.output_parsed_keys?.length">-</span>
                </el-descriptions-item>
              </el-descriptions>
            </el-collapse-item>

            <!-- 校验结果 -->
            <el-collapse-item title="校验结果（为什么没通过）" name="validation">
              <el-descriptions :column="1" border size="small">
                <el-descriptions-item label="校验状态">
                  <el-tag :type="validationTagType(selectedDetail.validation?.validation_status)" size="small">
                    {{ validationText(selectedDetail.validation?.validation_status) }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item v-if="selectedDetail.validation?.validation_error" label="错误信息">
                  <span class="error-text">{{ selectedDetail.validation.validation_error }}</span>
                </el-descriptions-item>
                <el-descriptions-item v-if="selectedDetail.validation?.validation_details" label="错误详情">
                  <pre class="json-block">{{ JSON.stringify(selectedDetail.validation.validation_details, null, 2) }}</pre>
                </el-descriptions-item>
              </el-descriptions>
              <el-text v-if="!selectedDetail.validation?.validation_status" type="info" size="small">未回填校验状态</el-text>
            </el-collapse-item>

            <!-- Token 用量 -->
            <el-collapse-item title="Token 用量" name="tokens">
              <el-descriptions :column="3" border size="small">
                <el-descriptions-item label="输入 Token">{{ selectedDetail.token_usage?.input_tokens ?? '-' }}</el-descriptions-item>
                <el-descriptions-item label="输出 Token">{{ selectedDetail.token_usage?.output_tokens ?? '-' }}</el-descriptions-item>
                <el-descriptions-item label="总计">{{ selectedDetail.token_usage?.total_tokens ?? '-' }}</el-descriptions-item>
              </el-descriptions>
            </el-collapse-item>

            <!-- 异常信息 -->
            <el-collapse-item v-if="!selectedDetail.success" title="异常信息" name="error">
              <el-descriptions :column="1" border size="small">
                <el-descriptions-item label="异常类型">{{ selectedDetail.error_type || '-' }}</el-descriptions-item>
                <el-descriptions-item label="异常信息">
                  <span class="error-text">{{ selectedDetail.error_message }}</span>
                </el-descriptions-item>
              </el-descriptions>
            </el-collapse-item>
          </el-collapse>
        </template>
        <el-empty v-else description="点击上方某条轨迹查看详情" :image-size="80" />
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { InfoFilled } from '@element-plus/icons-vue'
import { formatTime } from '@/utils/datetime'
import {
  ExecutionTraceApi,
  type ExecutionTrace,
} from '@/api/executionTrace'

const props = defineProps<{
  modelValue: boolean
  taskId: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
})

// ==================== 列表 ====================

const listLoading = ref(false)
const traces = ref<ExecutionTrace[]>([])
const total = ref(0)

async function loadList() {
  if (!props.taskId) return
  listLoading.value = true
  selectedDetail.value = null
  try {
    const res = await ExecutionTraceApi.getTraces({ task_id: props.taskId, limit: 200 })
    traces.value = res.data?.items || []
    total.value = res.data?.total || 0
  } catch (e: any) {
    ElMessage.error(e.message || '加载执行轨迹失败')
    traces.value = []
    total.value = 0
  } finally {
    listLoading.value = false
  }
}

// 打开对话框时加载列表
watch(
  () => [props.modelValue, props.taskId],
  ([open, tid]) => {
    if (open && tid) loadList()
  },
)

// ==================== 详情 ====================

const detailLoading = ref(false)
const selectedDetail = ref<ExecutionTrace | null>(null)
const activeNames = ref<string[]>(['basic', 'validation'])

async function handleRowClick(row: ExecutionTrace) {
  detailLoading.value = true
  try {
    const res = await ExecutionTraceApi.getTraceDetail(row.trace_id)
    selectedDetail.value = res.data
    // 自动展开有问题的分组
    const names = ['basic', 'inputs']
    if (res.data.validation?.validation_status === 'failed') names.push('validation')
    if (!res.data.success) names.push('error')
    names.push('prompts', 'output', 'parsed', 'tokens')
    if (res.data.tool_calls?.length) names.push('tool_calls')
    activeNames.value = names
  } catch (e: any) {
    ElMessage.error(e.message || '加载轨迹详情失败')
  } finally {
    detailLoading.value = false
  }
}

// ==================== 辅助 ====================

function managerTypeName(t: string): string {
  const map: Record<string, string> = { risk: '风险', research: '研究' }
  return map[t] || t
}

function validationTagType(s?: string | null): 'success' | 'danger' | 'info' {
  if (s === 'passed') return 'success'
  if (s === 'failed') return 'danger'
  return 'info'
}

function validationText(s?: string | null): string {
  if (s === 'passed') return '通过'
  if (s === 'failed') return '失败'
  return '未校验'
}

function formatDuration(ms?: number | null): string {
  if (!ms && ms !== 0) return '-'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

function copyText(text: string) {
  navigator.clipboard.writeText(text).then(
    () => ElMessage.success('已复制'),
    () => ElMessage.error('复制失败'),
  )
}
</script>

<style lang="scss" scoped>
.execution-trace-dialog {
  :deep(.el-dialog__body) {
    max-height: 75vh;
    overflow-y: auto;
  }
}

.trace-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
  padding: 8px 12px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.input-keys .len {
  color: var(--el-text-color-secondary);
  font-size: 11px;
}

.prompt-block {
  max-height: 360px;
  overflow: auto;
  background: var(--el-fill-color-darker);
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
}

.json-block {
  max-height: 240px;
  overflow: auto;
  background: var(--el-fill-color-darker);
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  margin: 0;
}

.error-text {
  color: var(--el-color-danger);
  font-family: monospace;
  font-size: 12px;
}

.trace-detail {
  min-height: 120px;
}

.tool-call-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tool-call-item {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 4px;
  padding: 10px 12px;
  background: var(--el-fill-color-lighter);
}

.tool-call-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.tool-name {
  font-weight: 600;
  font-size: 13px;
}

.tool-duration,
.tool-result-len {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.tool-call-error {
  margin-bottom: 6px;
}

.tool-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 2px;
  display: block;
}

.json-block.compact {
  max-height: 120px;
  font-size: 11px;
  padding: 8px;
}
</style>
