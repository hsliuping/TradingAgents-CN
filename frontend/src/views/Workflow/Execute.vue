<template>
  <div class="workflow-execute">
    <!-- 顶部信息 -->
    <div class="execute-header">
      <el-button text @click="goBack">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </el-button>
      <div class="workflow-info">
        <h2>{{ workflow?.name || '加载中...' }}</h2>
        <p>{{ workflow?.description }}</p>
      </div>
    </div>

    <!-- 工作流加载失败 -->
    <el-result v-if="workflowLoadError" icon="error" title="工作流加载失败" :sub-title="workflowLoadError">
      <template #extra>
        <el-button type="primary" @click="loadWorkflow">重试</el-button>
        <el-button @click="goBack">返回</el-button>
      </template>
    </el-result>

    <el-row v-else :gutter="20" v-loading="workflowLoading" element-loading-text="加载工作流配置...">
      <!-- 左侧：输入参数 -->
      <el-col :span="8">
        <el-card class="input-card">
          <template #header>
            <div class="card-header">
              <span>执行参数</span>
            </div>
          </template>
          
          <el-form :model="formValues" label-position="top">
            <!-- 动态表单：从 workflow.input_config.fields 生成 -->
            <template v-if="inputFields.length > 0">
              <template v-for="group in groupedFields" :key="group.name">
                <div v-if="group.name" class="field-group-title">{{ group.name }}</div>
                <el-form-item
                  v-for="field in group.fields"
                  :key="field.name"
                  :label="field.label || field.name"
                  :required="field.required"
                >
                  <!-- string: 单行文本 -->
                  <el-input
                    v-if="field.type === 'string'"
                    v-model="formValues[field.name]"
                    :placeholder="field.placeholder || ''"
                  />

                  <!-- textarea: 多行文本 -->
                  <el-input
                    v-else-if="field.type === 'textarea'"
                    v-model="formValues[field.name]"
                    type="textarea"
                    :rows="4"
                    :placeholder="field.placeholder || ''"
                    maxlength="500"
                    show-word-limit
                  />

                  <!-- number: 数字 -->
                  <el-input-number
                    v-else-if="field.type === 'number'"
                    v-model="formValues[field.name]"
                    :min="field.min ?? undefined"
                    :max="field.max ?? undefined"
                    style="width: 100%"
                  />

                  <!-- boolean: 开关 -->
                  <el-switch
                    v-else-if="field.type === 'boolean'"
                    v-model="formValues[field.name]"
                  />

                  <!-- date: 日期选择 -->
                  <el-date-picker
                    v-else-if="field.type === 'date'"
                    v-model="formValues[field.name]"
                    type="date"
                    placeholder="选择日期"
                    style="width: 100%"
                    value-format="YYYY-MM-DD"
                  />

                  <!-- select: 下拉单选 -->
                  <el-select
                    v-else-if="field.type === 'select'"
                    v-model="formValues[field.name]"
                    :placeholder="field.placeholder || '请选择'"
                    style="width: 100%"
                    :loading="modelsLoading"
                  >
                    <!-- 模型字段特殊处理：从 enabledModels 动态填充选项 -->
                    <template v-if="field.name === 'quick_analysis_model' || field.name === 'deep_analysis_model'">
                      <el-option
                        v-for="model in enabledModels"
                        :key="model.model_name"
                        :label="model.model_name"
                        :value="model.model_name"
                      />
                    </template>
                    <!-- 普通选项 -->
                    <template v-else>
                      <el-option
                        v-for="(opt, idx) in (field.options || [])"
                        :key="idx"
                        :label="field.option_labels?.[idx] || String(opt)"
                        :value="opt"
                      />
                    </template>
                  </el-select>

                  <!-- multiselect: 下拉多选 -->
                  <el-select
                    v-else-if="field.type === 'multiselect'"
                    v-model="formValues[field.name]"
                    multiple
                    :placeholder="field.placeholder || '请选择'"
                    style="width: 100%"
                  >
                    <el-option
                      v-for="(opt, idx) in (field.options || [])"
                      :key="idx"
                      :label="field.option_labels?.[idx] || String(opt)"
                      :value="opt"
                    />
                  </el-select>

                  <!-- 参数描述 -->
                  <div v-if="field.description" class="field-description">{{ field.description }}</div>
                </el-form-item>
              </template>
            </template>

            <!-- 无输入参数提示 -->
            <el-empty
              v-else
              description="此流程无需输入参数"
              :image-size="60"
            />

            <el-form-item>
              <el-button type="primary" @click="executeWorkflow" :loading="executing" style="width: 100%">
                <el-icon><VideoPlay /></el-icon>
                开始执行
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- 中间：执行状态 -->
      <el-col :span="8">
        <el-card class="status-card">
          <template #header>
            <div class="card-header">
              <span>执行状态</span>
              <el-tag :type="statusType">{{ statusText }}</el-tag>
            </div>
          </template>
          
          <!-- 执行进度 -->
          <div class="execution-progress">
            <el-timeline>
              <el-timeline-item v-for="step in executionSteps" :key="step.id"
                                :type="step.status === 'running' ? 'primary' : step.status === 'completed' ? 'success' : 'info'"
                                :hollow="step.status === 'pending'">
                <div class="step-item">
                  <span class="step-name">{{ step.name }}</span>
                  <span class="step-time" v-if="step.duration">{{ step.duration }}ms</span>
                </div>
              </el-timeline-item>
            </el-timeline>
          </div>
          
          <!-- 错误信息 -->
          <el-alert v-if="executionError" type="error" :title="executionError" show-icon :closable="false" />
        </el-card>
      </el-col>

      <!-- 右侧：执行结果 -->
      <el-col :span="8">
        <el-card class="result-card">
          <template #header>
            <div class="card-header">
              <span>执行结果</span>
              <el-button v-if="executionResult" size="small" @click="copyResult">
                <el-icon><CopyDocument /></el-icon>
                复制
              </el-button>
            </div>
          </template>
          
          <div v-if="executionResult" class="result-content">
            <!-- 降级节点警告 -->
            <el-alert
              v-if="executionResult.degraded_nodes && Object.keys(executionResult.degraded_nodes).length > 0"
              type="warning"
              :closable="false"
              show-icon
              style="margin-bottom: 16px"
            >
              <template #title>
                部分分析节点执行失败（已降级）
              </template>
              <div style="margin-top: 4px; font-size: 13px; line-height: 1.6">
                <div v-for="(info, nodeId) in executionResult.degraded_nodes" :key="nodeId">
                  <strong>{{ info.label || nodeId }}</strong>：{{ info.error ? info.error.substring(0, 120) : '未知错误' }}
                </div>
                <div style="margin-top: 4px; color: #909399">其余节点的分析结果不受影响，请参考其他报告。</div>
              </div>
            </el-alert>

            <!-- 最终分析结果 -->
            <div class="decision-box" v-if="hasContent(getReportField('final_trade_decision'))">
              <h4>最终分析结果</h4>
              <div class="decision-content" v-html="formatReport(extractContent(getReportField('final_trade_decision')).substring(0, 500))" />
            </div>

            <!-- 详细报告 -->
            <el-collapse v-model="activeCollapse">
              <!-- 动态模式：根据 report_manifest 渲染 -->
              <template v-if="executionResult.report_manifest && executionResult.report_manifest.length > 0">
                <el-collapse-item
                  v-for="m in executionResult.report_manifest.filter((item: any) => hasContent(getReportField(item.field)))"
                  :key="m.field"
                  :title="m.display_name || m.field"
                  :name="m.field"
                >
                  <div class="report-content" v-html="formatReport(getReportField(m.field))" />
                </el-collapse-item>
              </template>

              <!-- 旧逻辑：内置工作流硬编码 -->
              <template v-else>
                <el-collapse-item title="最终决策详情" name="final" v-if="hasContent(getReportField('final_trade_decision'))">
                  <div class="report-content" v-html="formatReport(getReportField('final_trade_decision'))" />
                </el-collapse-item>
                <el-collapse-item title="风险评估" name="risk" v-if="hasContent(getReportField('risk_assessment'))">
                  <div class="report-content" v-html="formatReport(getReportField('risk_assessment'))" />
                </el-collapse-item>
                <el-collapse-item title="交易员计划" name="trader" v-if="hasContent(getReportField('trader_investment_plan'))">
                  <div class="report-content" v-html="formatReport(getReportField('trader_investment_plan'))" />
                </el-collapse-item>
                <el-collapse-item title="投资计划" name="investment" v-if="hasContent(getReportField('investment_plan'))">
                  <div class="report-content" v-html="formatReport(getReportField('investment_plan'))" />
                </el-collapse-item>
                <el-collapse-item title="看涨研究" name="bull" v-if="hasContent(getReportField('bull_report')) || hasContent(getReportField('bull_opinion'))">
                  <div class="report-content" v-html="formatReport(getReportField('bull_report') || getReportField('bull_opinion'))" />
                </el-collapse-item>
                <el-collapse-item title="看跌研究" name="bear" v-if="hasContent(getReportField('bear_report')) || hasContent(getReportField('bear_opinion'))">
                  <div class="report-content" v-html="formatReport(getReportField('bear_report') || getReportField('bear_opinion'))" />
                </el-collapse-item>
                <el-collapse-item title="大盘分析" name="index" v-if="hasContent(getReportField('index_report'))">
                  <div class="report-content" v-html="formatReport(getReportField('index_report'))" />
                </el-collapse-item>
                <el-collapse-item title="板块分析" name="sector" v-if="hasContent(getReportField('sector_report'))">
                  <div class="report-content" v-html="formatReport(getReportField('sector_report'))" />
                </el-collapse-item>
                <el-collapse-item title="市场分析" name="market" v-if="hasContent(getReportField('market_report'))">
                  <div class="report-content" v-html="formatReport(getReportField('market_report'))" />
                </el-collapse-item>
                <el-collapse-item title="基本面分析" name="fundamentals" v-if="hasContent(getReportField('fundamentals_report'))">
                  <div class="report-content" v-html="formatReport(getReportField('fundamentals_report'))" />
                </el-collapse-item>
                <el-collapse-item title="新闻分析" name="news" v-if="hasContent(getReportField('news_report'))">
                  <div class="report-content" v-html="formatReport(getReportField('news_report'))" />
                </el-collapse-item>
                <el-collapse-item title="情绪分析" name="sentiment" v-if="hasContent(getReportField('sentiment_report'))">
                  <div class="report-content" v-html="formatReport(getReportField('sentiment_report'))" />
                </el-collapse-item>
                <el-collapse-item title="激进风险观点" name="risky" v-if="hasContent(getReportField('risky_opinion'))">
                  <div class="report-content" v-html="formatReport(getReportField('risky_opinion'))" />
                </el-collapse-item>
                <el-collapse-item title="保守风险观点" name="safe" v-if="hasContent(getReportField('safe_opinion'))">
                  <div class="report-content" v-html="formatReport(getReportField('safe_opinion'))" />
                </el-collapse-item>
                <el-collapse-item title="中性风险观点" name="neutral" v-if="hasContent(getReportField('neutral_opinion'))">
                  <div class="report-content" v-html="formatReport(getReportField('neutral_opinion'))" />
                </el-collapse-item>
              </template>

              <!-- 原始数据 -->
              <el-collapse-item title="原始数据" name="raw">
                <pre class="raw-data">{{ JSON.stringify(executionResult, null, 2) }}</pre>
              </el-collapse-item>
            </el-collapse>
          </div>
          
          <el-empty v-else description="等待执行结果" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, VideoPlay, CopyDocument } from '@element-plus/icons-vue'
import { workflowApi, type WorkflowDefinition, type InputFieldConfig } from '@/api/workflow'
import { configApi, type LLMConfig } from '@/api/config'
import { analysisApi } from '@/api/analysis'
import { marked } from 'marked'
import { useAuthStore } from '@/stores/auth'
import { fetchTaskResultWithRetry } from '@/utils/taskResult'

const route = useRoute()
const router = useRouter()

// 状态
const workflow = ref<WorkflowDefinition | null>(null)
const workflowLoading = ref(true)
const workflowLoadError = ref<string | null>(null)
const executing = ref(false)
const executionResult = ref<any>(null)
const executionError = ref<string | null>(null)
const activeCollapse = ref(['report'])

// 模型列表（仅用于 select 类型的模型字段动态填充选项）
const modelsLoading = ref(false)
const allModels = ref<LLMConfig[]>([])
const enabledModels = computed(() => allModels.value.filter(m => m.enabled))

// 🆕 动态表单值：formValues[field.name] = 值
const formValues = ref<Record<string, any>>({})

// 🆕 输入参数字段列表（从 workflow.input_config.fields 读取）
const inputFields = computed<InputFieldConfig[]>(() => {
  return workflow.value?.input_config?.fields || []
})

// 🆕 按分组组织字段
const groupedFields = computed(() => {
  const fields = [...inputFields.value].sort((a, b) => (a.order || 0) - (b.order || 0))
  const groups: Array<{ name: string; fields: InputFieldConfig[] }> = []
  const groupMap = new Map<string, InputFieldConfig[]>()

  for (const f of fields) {
    const g = f.group || ''
    if (!groupMap.has(g)) groupMap.set(g, [])
    groupMap.get(g)!.push(f)
  }

  for (const [name, fields] of groupMap) {
    groups.push({ name, fields })
  }
  return groups
})

// 🆕 工作流类型（保留用于 onMounted 判断是否需要加载模型）
const workflowType = computed(() => workflow.value?.workflow_type || 'stock_analysis')

const executionSteps = ref<Array<{
  id: string
  name: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  duration?: number
}>>([])

// 计算属性
const workflowId = computed(() => route.params.id as string)

const statusType = computed(() => {
  if (executing.value) return 'warning'
  if (executionError.value) return 'danger'
  if (executionResult.value) return 'success'
  return 'info'
})

const statusText = computed(() => {
  if (executing.value) return '执行中'
  if (executionError.value) return '执行失败'
  if (executionResult.value) return '执行完成'
  return '待执行'
})

// 加载模型配置（仅加载模型列表，默认值在 initFormValues 中设置）
const loadModels = async () => {
  modelsLoading.value = true
  try {
    console.log('🔍 [工作流执行] 开始加载模型配置...')

    // 获取所有模型配置
    const response = await configApi.getLLMConfigs()
    allModels.value = Array.isArray(response) ? response : []

    console.log('✅ [工作流执行] 加载模型配置成功:', {
      available: enabledModels.value.length
    })
  } catch (error) {
    console.error('❌ [工作流执行] 加载模型配置失败:', error)
  } finally {
    modelsLoading.value = false
  }
}

// 加载工作流
const loadWorkflow = async () => {
  workflowLoading.value = true
  workflowLoadError.value = null
  try {
    workflow.value = await workflowApi.get(workflowId.value)
    if (workflow.value?.nodes) {
      executionSteps.value = workflow.value.nodes
        .filter(n => n.type !== 'start' && n.type !== 'end')
        .map(n => ({
          id: n.id,
          name: n.label,
          status: 'pending'
        }))
    }
    // 🆕 初始化表单默认值
    initFormValues()
  } catch (error: any) {
    console.error('加载工作流失败:', error)
    workflowLoadError.value = error?.message || '无法加载工作流配置，请检查网络或稍后重试'
  } finally {
    workflowLoading.value = false
  }
}

// 🆕 初始化表单默认值：根据 input_config.fields 设置 formValues
const initFormValues = async () => {
  const values: Record<string, any> = {}
  for (const field of inputFields.value) {
    // 设置默认值
    let defaultVal = field.default
    // 特殊处理模型字段：从系统配置加载默认模型
    if (field.name === 'quick_analysis_model' && !defaultVal) {
      try {
        const defaultModels = await configApi.getDefaultModels()
        defaultVal = defaultModels.quick_analysis_model || ''
      } catch { defaultVal = '' }
    } else if (field.name === 'deep_analysis_model' && !defaultVal) {
      try {
        const defaultModels = await configApi.getDefaultModels()
        defaultVal = defaultModels.deep_analysis_model || ''
      } catch { defaultVal = '' }
    } else if (field.name === 'research_depth' && !defaultVal) {
      // 从用户偏好加载默认分析深度
      try {
        const authStore = useAuthStore()
        const userPrefs = authStore.user?.preferences
        if (userPrefs?.default_depth) {
          defaultVal = convertDepthToText(userPrefs.default_depth)
        }
      } catch { /* ignore */ }
    }

    // 类型相关的默认值
    if (defaultVal === null || defaultVal === undefined) {
      switch (field.type) {
        case 'boolean': defaultVal = false; break
        case 'number': defaultVal = undefined; break
        case 'multiselect': defaultVal = []; break
        case 'date':
          if (field.name === 'analysis_date') {
            defaultVal = new Date().toISOString().slice(0, 10)
          } else {
            defaultVal = ''
          }
          break
        default: defaultVal = ''
      }
    }
    values[field.name] = defaultVal
  }
  formValues.value = values
  console.log('🔍 [表单初始化] formValues:', values)
}

// 当前任务ID
const currentTaskId = ref<string | null>(null)
const pollingTimer = ref<ReturnType<typeof setInterval> | null>(null)

// 执行工作流 - 改为异步执行，使用 v2.0 统一任务引擎
const executeWorkflow = async () => {
  // 🆕 校验必填字段
  for (const field of inputFields.value) {
    if (field.required) {
      const val = formValues.value[field.name]
      const empty = val === null || val === undefined || val === '' ||
        (Array.isArray(val) && val.length === 0)
      if (empty) {
        ElMessage.warning(`请填写${field.label || field.name}`)
        return
      }
    }
  }

  executing.value = true
  executionResult.value = null
  executionError.value = null

  // 重置步骤状态
  for (const step of executionSteps.value) {
    step.status = 'pending'
  }

  try {
    // 🆕 构造请求参数：将 formValues 中所有非空值作为请求参数
    const params: Record<string, any> = {}
    for (const field of inputFields.value) {
      const val = formValues.value[field.name]
      if (val !== null && val !== undefined && val !== '') {
        params[field.name] = val
      }
    }

    // 如果没有 ticker 字段但有 analysis_target，复用作为 ticker（工作流引擎需要 ticker 做参数映射）
    if (!params.ticker) {
      if (params.analysis_target) {
        params.ticker = params.analysis_target
      } else if (workflowType.value === 'general') {
        // 通用研究流程兜底
        ElMessage.warning('通用研究流程需要 analysis_target 参数')
        executing.value = false
        return
      }
    }

    // 对通用研究流程，把所有参数合并到 custom_params 中（保持后端兼容）
    if (workflowType.value === 'general') {
      const customParams: Record<string, any> = { ...params }
      delete customParams.ticker  // ticker 已单独传递
      params.custom_params = customParams
    }

    const result = await workflowApi.execute(workflowId.value, params)

    console.log('🔍 工作流执行响应:', result)

    // 获取任务ID（v2.0 返回格式）
    currentTaskId.value = result.task_id || null

    if (!currentTaskId.value) {
      throw new Error('未获取到任务ID')
    }

    console.log('✅ 任务ID:', currentTaskId.value)
    ElMessage.success('任务已提交，正在后台执行...')

    // 开始轮询任务状态
    startPollingTaskStatus()

  } catch (error: any) {
    executionError.value = error.message || '执行失败'
    ElMessage.error('执行失败')
    executing.value = false
  }
}

// 轮询任务状态
const startPollingTaskStatus = () => {
  if (pollingTimer.value) {
    clearInterval(pollingTimer.value)
  }

  if (!currentTaskId.value) {
    console.error('❌ 任务ID为空，无法开始轮询')
    return
  }

  console.log('🔄 开始轮询任务状态:', currentTaskId.value)

  pollingTimer.value = setInterval(async () => {
    try {
      if (!currentTaskId.value) {
        if (pollingTimer.value) {
          clearInterval(pollingTimer.value)
        }
        return
      }

      const response = await analysisApi.getTaskStatus(currentTaskId.value)
      const status = response.data

      console.log('🔍 任务状态:', {
        status: status.status,
        progress: status.progress,
        current_step_name: status.current_step_name,
        current_step: status.current_step,
        message: status.message
      })

      // 构建进度信息对象
      const progressInfo = {
        current_step_name: status.current_step_name,
        current_step: status.current_step,
        current_step_description: status.current_step_description || status.message,
        completed_steps: status.completed_steps,
        progress: status.progress
      }

      // 更新进度信息
      updateProgressInfo(progressInfo)

      // 任务完成
      if (status.status === 'completed') {
        console.log('✅ 任务完成')
        if (pollingTimer.value) {
          clearInterval(pollingTimer.value)
        }

        // 获取任务结果
        executionResult.value = await fetchTaskResultWithRetry(currentTaskId.value, {
          seedData: status.result_data
        })

        // 🔍 调试：检查返回的数据结构
        console.log('🔍 [工作流执行] 任务结果数据:', executionResult.value)
        console.log('🔍 [工作流执行] 数据键:', Object.keys(executionResult.value || {}))
        console.log('🔍 [工作流执行] index_report 存在:', !!executionResult.value?.index_report)
        console.log('🔍 [工作流执行] sector_report 存在:', !!executionResult.value?.sector_report)
        console.log('🔍 [工作流执行] market_report 存在:', !!executionResult.value?.market_report)
        console.log('🔍 [工作流执行] state 存在:', !!executionResult.value?.state)

        // 标记所有步骤完成
        for (const step of executionSteps.value) {
          step.status = 'completed'
        }

        executing.value = false
        ElMessage.success('分析完成！')
      }

      // 任务失败
      if (status.status === 'failed') {
        console.error('❌ 任务失败:', status.error)
        if (pollingTimer.value) {
          clearInterval(pollingTimer.value)
        }

        executionError.value = status.error || status.error_message || '任务执行失败'
        executing.value = false
        ElMessage.error(status.error || status.error_message || '任务执行失败')
      }

    } catch (error) {
      console.error('轮询任务状态失败:', error)
    }
  }, 2000) // 每2秒轮询一次
}

// 更新进度信息
const updateProgressInfo = (progressInfo: any) => {
  if (!progressInfo) return

  console.log('🔍 更新进度信息:', progressInfo)
  console.log('📋 当前步骤列表:', executionSteps.value.map(s => s.name))

  // 获取当前步骤名称
  const currentStepName = progressInfo.current_step_name || progressInfo.current_step
  if (!currentStepName) {
    console.warn('⚠️ 没有当前步骤名称')
    return
  }

  console.log('🎯 当前步骤:', currentStepName)

  // 重置所有步骤状态
  for (const step of executionSteps.value) {
    step.status = 'pending'
  }

  // 找到当前步骤并标记为 running
  let currentStepIndex = -1
  for (let i = 0; i < executionSteps.value.length; i++) {
    const step = executionSteps.value[i]

    // 尝试多种匹配方式
    if (step.name === currentStepName ||
        step.name.includes(currentStepName) ||
        currentStepName.includes(step.name)) {
      console.log('✅ 找到匹配步骤:', step.name, '索引:', i)
      step.status = 'running'
      currentStepIndex = i
      break
    }
  }

  if (currentStepIndex === -1) {
    console.warn('⚠️ 未找到匹配步骤:', currentStepName)
    return
  }

  // 标记当前步骤之前的所有步骤为已完成
  for (let i = 0; i < currentStepIndex; i++) {
    executionSteps.value[i].status = 'completed'
  }

  console.log('📊 更新后的步骤状态:', executionSteps.value.map(s => ({ name: s.name, status: s.status })))
}

// 组件卸载时清理定时器
onUnmounted(() => {
  if (pollingTimer.value) {
    clearInterval(pollingTimer.value)
  }
})

// 辅助方法
const goBack = () => {
  router.push('/workflow')
}

const extractContent = (value: any): string => {
  if (value == null) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'object') {
    const keys = ['content', 'markdown', 'text', 'message', 'report']
    for (const k of keys) {
      const v = (value as any)[k]
      if (typeof v === 'string' && v.trim() !== '') return v
    }
    try {
      return JSON.stringify(value)
    } catch {
      return String(value)
    }
  }
  return String(value)
}

const hasContent = (value: any): boolean => {
  return extractContent(value).trim().length > 0
}

// 🔥 新增：从 executionResult 中获取报告字段（优先从顶层，回退到 state）
const getReportField = (fieldName: string): any => {
  if (!executionResult.value) return null

  // 优先从顶层获取
  if (executionResult.value[fieldName]) {
    return executionResult.value[fieldName]
  }

  // 回退到 state 字段
  if (executionResult.value.state && executionResult.value.state[fieldName]) {
    return executionResult.value.state[fieldName]
  }

  return null
}

const formatReport = (report: any) => {
  const text = extractContent(report)
  if (!text) return ''
  return marked(text)
}

const copyResult = () => {
  if (executionResult.value) {
    navigator.clipboard.writeText(JSON.stringify(executionResult.value, null, 2))
    ElMessage.success('已复制到剪贴板')
  }
}

// 初始化
onMounted(async () => {
  // 加载模型列表（用于 input_config 中模型选择字段的选项填充）
  await loadModels()
  // 加载工作流（内部会调用 initFormValues 初始化表单默认值）
  await loadWorkflow()
})

// 将数字深度转换为中文描述
const convertDepthToText = (depth: string | number): string => {
  // 如果已经是中文描述，直接返回
  if (typeof depth === 'string' && ['快速', '基础', '标准', '深度', '全面'].includes(depth)) {
    return depth
  }

  // 数字到中文的映射
  const numberToText: Record<string, string> = {
    '1': '快速',
    '2': '基础',
    '3': '标准',
    '4': '深度',
    '5': '全面'
  }

  // 返回对应的中文描述，如果找不到则返回默认值 '标准'
  return numberToText[String(depth)] || '标准'
}
</script>

<style scoped lang="scss">
.workflow-execute {
  padding: 20px;
}

.execute-header {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 24px;

  .workflow-info {
    h2 {
      margin: 0;
      font-size: 20px;
    }

    p {
      margin: 4px 0 0;
      color: var(--el-text-color-secondary);
      font-size: 14px;
    }
  }
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.input-card, .status-card, .result-card {
  height: calc(100vh - 180px);
  overflow-y: auto;
}

.execution-progress {
  padding: 16px 0;

  .step-item {
    display: flex;
    justify-content: space-between;

    .step-time {
      font-size: 12px;
      color: var(--el-text-color-secondary);
    }
  }
}

.decision-box {
  text-align: center;
  padding: 20px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
  margin-bottom: 16px;

  h4 {
    margin: 0 0 12px;
    color: var(--el-text-color-secondary);
  }

  .el-tag {
    font-size: 18px;
    padding: 12px 24px;
  }

  .decision-reason {
    margin: 12px 0;
    font-size: 14px;
    color: var(--el-text-color-primary);
  }

  .decision-meta {
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }
}

.report-content {
  font-size: 14px;
  line-height: 1.6;

  :deep(h1), :deep(h2), :deep(h3) {
    margin-top: 16px;
    margin-bottom: 8px;
  }

  :deep(ul), :deep(ol) {
    padding-left: 20px;
  }
}

.raw-data {
  font-size: 12px;
  background: var(--el-fill-color-light);
  padding: 12px;
  border-radius: 4px;
  overflow-x: auto;
  max-height: 300px;
}

.field-group-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
  margin: 12px 0 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--el-border-color-lighter);

  &:first-child {
    margin-top: 0;
  }
}

.field-description {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
  line-height: 1.5;
}
</style>
