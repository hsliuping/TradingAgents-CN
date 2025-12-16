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

    <el-row :gutter="20">
      <!-- 左侧：输入参数 -->
      <el-col :span="8">
        <el-card class="input-card">
          <template #header>
            <div class="card-header">
              <span>执行参数</span>
            </div>
          </template>
          
          <el-form :model="inputs" label-position="top">
            <el-form-item label="股票代码" required>
              <el-input v-model="inputs.ticker" placeholder="如: AAPL, 600519.SH" />
            </el-form-item>

            <el-form-item label="分析日期">
              <el-date-picker v-model="inputs.analysis_date" type="date" placeholder="选择日期" style="width: 100%" />
            </el-form-item>

            <el-form-item label="分析深度">
              <el-select v-model="inputs.research_depth" placeholder="选择分析深度" style="width: 100%">
                <el-option label="快速 (2-4分钟)" value="快速" />
                <el-option label="基础 (4-6分钟)" value="基础" />
                <el-option label="标准 (6-10分钟，推荐)" value="标准" />
                <el-option label="深度 (10-15分钟)" value="深度" />
                <el-option label="全面 (15-25分钟)" value="全面" />
              </el-select>
            </el-form-item>

            <el-form-item label="快速分析模型">
              <el-select v-model="inputs.quick_analysis_model" placeholder="选择模型" style="width: 100%" :loading="modelsLoading">
                <el-option v-for="model in enabledModels" :key="model.model_name" :label="model.model_name" :value="model.model_name" />
              </el-select>
            </el-form-item>

            <el-form-item label="深度分析模型">
              <el-select v-model="inputs.deep_analysis_model" placeholder="选择模型" style="width: 100%" :loading="modelsLoading">
                <el-option v-for="model in enabledModels" :key="model.model_name" :label="model.model_name" :value="model.model_name" />
              </el-select>
            </el-form-item>

            <el-form-item label="回看天数">
              <el-input-number v-model="inputs.lookback_days" :min="1" :max="365" style="width: 100%" />
            </el-form-item>

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
            <!-- 最终交易决策 -->
            <div class="decision-box" v-if="executionResult.final_trade_decision">
              <h4>最终交易决策</h4>
              <div class="decision-content" v-html="formatReport(executionResult.final_trade_decision.substring(0, 500))" />
            </div>

            <!-- 详细报告 -->
            <el-collapse v-model="activeCollapse">
              <!-- 最终决策 -->
              <el-collapse-item title="最终决策详情" name="final" v-if="executionResult.final_trade_decision">
                <div class="report-content" v-html="formatReport(executionResult.final_trade_decision)" />
              </el-collapse-item>

              <!-- 风险评估 -->
              <el-collapse-item title="风险评估" name="risk" v-if="executionResult.risk_assessment">
                <div class="report-content" v-html="formatReport(executionResult.risk_assessment)" />
              </el-collapse-item>

              <!-- 交易员计划 -->
              <el-collapse-item title="交易员计划" name="trader" v-if="executionResult.trader_investment_plan">
                <div class="report-content" v-html="formatReport(executionResult.trader_investment_plan)" />
              </el-collapse-item>

              <!-- 投资计划 -->
              <el-collapse-item title="投资计划" name="investment" v-if="executionResult.investment_plan">
                <div class="report-content" v-html="formatReport(executionResult.investment_plan)" />
              </el-collapse-item>

              <!-- 看涨观点 -->
              <el-collapse-item title="看涨研究" name="bull" v-if="executionResult.bull_report || executionResult.bull_opinion">
                <div class="report-content" v-html="formatReport(executionResult.bull_report || executionResult.bull_opinion)" />
              </el-collapse-item>

              <!-- 看跌观点 -->
              <el-collapse-item title="看跌研究" name="bear" v-if="executionResult.bear_report || executionResult.bear_opinion">
                <div class="report-content" v-html="formatReport(executionResult.bear_report || executionResult.bear_opinion)" />
              </el-collapse-item>

              <!-- 分析师报告 -->
              <el-collapse-item title="大盘分析" name="index" v-if="executionResult.index_report">
                <div class="report-content" v-html="formatReport(executionResult.index_report)" />
              </el-collapse-item>
              <el-collapse-item title="板块分析" name="sector" v-if="executionResult.sector_report">
                <div class="report-content" v-html="formatReport(executionResult.sector_report)" />
              </el-collapse-item>
              <el-collapse-item title="市场分析" name="market" v-if="executionResult.market_report">
                <div class="report-content" v-html="formatReport(executionResult.market_report)" />
              </el-collapse-item>
              <el-collapse-item title="基本面分析" name="fundamentals" v-if="executionResult.fundamentals_report">
                <div class="report-content" v-html="formatReport(executionResult.fundamentals_report)" />
              </el-collapse-item>
              <el-collapse-item title="新闻分析" name="news" v-if="executionResult.news_report">
                <div class="report-content" v-html="formatReport(executionResult.news_report)" />
              </el-collapse-item>
              <el-collapse-item title="情绪分析" name="sentiment" v-if="executionResult.sentiment_report">
                <div class="report-content" v-html="formatReport(executionResult.sentiment_report)" />
              </el-collapse-item>

              <!-- 风险辩论观点 -->
              <el-collapse-item title="激进风险观点" name="risky" v-if="executionResult.risky_opinion">
                <div class="report-content" v-html="formatReport(executionResult.risky_opinion)" />
              </el-collapse-item>
              <el-collapse-item title="保守风险观点" name="safe" v-if="executionResult.safe_opinion">
                <div class="report-content" v-html="formatReport(executionResult.safe_opinion)" />
              </el-collapse-item>
              <el-collapse-item title="中性风险观点" name="neutral" v-if="executionResult.neutral_opinion">
                <div class="report-content" v-html="formatReport(executionResult.neutral_opinion)" />
              </el-collapse-item>

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
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, VideoPlay, CopyDocument } from '@element-plus/icons-vue'
import { workflowApi, type WorkflowDefinition } from '@/api/workflow'
import { configApi, type LLMConfig } from '@/api/config'
import { marked } from 'marked'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()

// 状态
const workflow = ref<WorkflowDefinition | null>(null)
const executing = ref(false)
const executionResult = ref<any>(null)
const executionError = ref<string | null>(null)
const activeCollapse = ref(['report'])
const modelsLoading = ref(false)
const allModels = ref<LLMConfig[]>([])

// 只显示已启用的模型
const enabledModels = computed(() => allModels.value.filter(m => m.enabled))

const inputs = ref({
  ticker: '',
  analysis_date: new Date(),
  research_depth: '标准', // 将在 onMounted 中从用户偏好加载
  quick_analysis_model: '', // 将在 loadModels 中从系统配置加载
  deep_analysis_model: '', // 将在 loadModels 中从系统配置加载
  lookback_days: 30,
  max_debate_rounds: 2
})

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

// 加载模型配置
const loadModels = async () => {
  modelsLoading.value = true
  try {
    console.log('🔍 [工作流执行] 开始加载模型配置...')

    // 获取所有模型配置
    const response = await configApi.getLLMConfigs()
    allModels.value = Array.isArray(response) ? response : []

    // 获取系统默认模型配置
    const defaultModels = await configApi.getDefaultModels()
    console.log('🔍 [工作流执行] 从API获取的默认模型:', defaultModels)

    // 设置默认模型（优先使用系统配置）
    if (!inputs.value.quick_analysis_model) {
      inputs.value.quick_analysis_model = defaultModels.quick_analysis_model || 'qwen-turbo'
    }
    if (!inputs.value.deep_analysis_model) {
      inputs.value.deep_analysis_model = defaultModels.deep_analysis_model || 'qwen-max'
    }

    console.log('✅ [工作流执行] 加载模型配置成功:', {
      quick: inputs.value.quick_analysis_model,
      deep: inputs.value.deep_analysis_model,
      available: enabledModels.value.length
    })
  } catch (error) {
    console.error('❌ [工作流执行] 加载模型配置失败:', error)
    // 降级处理：使用第一个启用的模型
    const enabled = enabledModels.value
    if (enabled.length > 0) {
      if (!inputs.value.quick_analysis_model) {
        inputs.value.quick_analysis_model = enabled[0].model_name
      }
      if (!inputs.value.deep_analysis_model) {
        inputs.value.deep_analysis_model = enabled[0].model_name
      }
    }
  } finally {
    modelsLoading.value = false
  }
}

// 加载工作流
const loadWorkflow = async () => {
  try {
    workflow.value = await workflowApi.get(workflowId.value)
    // 根据节点生成执行步骤
    if (workflow.value?.nodes) {
      executionSteps.value = workflow.value.nodes
        .filter(n => n.type !== 'start' && n.type !== 'end')
        .map(n => ({
          id: n.id,
          name: n.label,
          status: 'pending'
        }))
    }
  } catch (error) {
    console.error('加载工作流失败:', error)
  }
}

// 执行工作流
const executeWorkflow = async () => {
  if (!inputs.value.ticker) {
    ElMessage.warning('请输入股票代码')
    return
  }
  if (!inputs.value.quick_analysis_model || !inputs.value.deep_analysis_model) {
    ElMessage.warning('请选择分析模型')
    return
  }

  executing.value = true
  executionResult.value = null
  executionError.value = null

  // 重置步骤状态
  for (const step of executionSteps.value) {
    step.status = 'pending'
  }

  try {
    const result = await workflowApi.execute(workflowId.value, {
      ticker: inputs.value.ticker,
      analysis_date: inputs.value.analysis_date,
      research_depth: inputs.value.research_depth,
      quick_analysis_model: inputs.value.quick_analysis_model,
      deep_analysis_model: inputs.value.deep_analysis_model,
      lookback_days: inputs.value.lookback_days,
      max_debate_rounds: inputs.value.max_debate_rounds
    })

    if (result.success) {
      executionResult.value = result.result
      for (const step of executionSteps.value) {
        step.status = 'completed'
      }
      ElMessage.success('执行完成')
    } else {
      executionError.value = result.error || '执行失败'
      ElMessage.error(result.error || '执行失败')
    }
  } catch (error: any) {
    executionError.value = error.message || '执行失败'
    ElMessage.error('执行失败')
  } finally {
    executing.value = false
  }
}

// 辅助方法
const goBack = () => {
  router.push('/workflow')
}

const formatReport = (report: string) => {
  if (!report) return ''
  return marked(report)
}

const copyResult = () => {
  if (executionResult.value) {
    navigator.clipboard.writeText(JSON.stringify(executionResult.value, null, 2))
    ElMessage.success('已复制到剪贴板')
  }
}

// 初始化
onMounted(async () => {
  await loadWorkflow()
  await loadModels()

  // 🆕 从用户偏好加载默认设置
  const authStore = useAuthStore()
  const userPrefs = authStore.user?.preferences

  console.log('🔍 [工作流执行] 调试信息:', {
    hasUser: !!authStore.user,
    hasPreferences: !!userPrefs,
    userPrefs: userPrefs,
    currentDepth: inputs.value.research_depth
  })

  if (userPrefs) {
    // 加载默认分析深度
    if (userPrefs.default_depth) {
      // 将数字深度转换为中文描述
      const depthValue = convertDepthToText(userPrefs.default_depth)
      console.log('🔍 [工作流执行] 深度转换:', userPrefs.default_depth, '->', depthValue)
      inputs.value.research_depth = depthValue
    } else {
      console.log('⚠️ [工作流执行] 用户偏好中没有 default_depth')
    }

    console.log('✅ [工作流执行] 已加载用户偏好设置:', {
      depth: inputs.value.research_depth
    })
  } else {
    console.log('⚠️ [工作流执行] 没有找到用户偏好设置')
  }
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
</style>

