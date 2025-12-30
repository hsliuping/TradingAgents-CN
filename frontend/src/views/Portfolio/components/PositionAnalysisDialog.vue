<template>
  <el-dialog
    v-model="visible"
    title="单股持仓分析"
    width="700px"
    :close-on-click-modal="false"
  >
    <!-- 持仓信息展示 -->
    <div v-if="position" class="position-info">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="股票代码">{{ position.code }}</el-descriptions-item>
        <el-descriptions-item label="股票名称">{{ position.name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="持仓数量">{{ position.quantity }} 股</el-descriptions-item>
        <el-descriptions-item label="成本价">¥{{ position.cost_price.toFixed(2) }}</el-descriptions-item>
        <el-descriptions-item label="当前价">¥{{ position.current_price?.toFixed(2) || '-' }}</el-descriptions-item>
        <el-descriptions-item label="持仓市值">¥{{ position.market_value?.toFixed(2) || '-' }}</el-descriptions-item>
        <el-descriptions-item label="浮动盈亏">
          <span :class="(position.unrealized_pnl || 0) >= 0 ? 'profit' : 'loss'">
            {{ (position.unrealized_pnl || 0) >= 0 ? '+' : '' }}{{ position.unrealized_pnl?.toFixed(2) || '0.00' }}
            ({{ (position.unrealized_pnl_pct || 0) >= 0 ? '+' : '' }}{{ position.unrealized_pnl_pct?.toFixed(2) || '0.00' }}%)
          </span>
        </el-descriptions-item>
        <el-descriptions-item label="所属行业">{{ position.industry || '未知' }}</el-descriptions-item>
      </el-descriptions>
    </div>

    <!-- 分析状态提示 -->
    <div v-if="analysisStatus === 'pending' || analysisStatus === 'processing'" class="analysis-status">
      <el-alert type="info" :closable="false">
        <template #title>
          <el-icon class="is-loading"><Loading /></el-icon>
          {{ analysisStatus === 'pending' ? '分析任务已提交' : '正在分析中' }}...
        </template>
        <template #default>
          <p>预计需要2-5分钟完成，您可以：</p>
          <ul>
            <li>点击下方"手动刷新状态"按钮查看最新进度</li>
            <li>或关闭对话框稍后再来查看（重新打开对话框即可查看结果）</li>
          </ul>
          <el-button
            type="primary"
            size="small"
            :loading="refreshing"
            @click="manualRefreshStatus"
            style="margin-top: 12px;"
          >
            <el-icon v-if="!refreshing"><Refresh /></el-icon>
            {{ refreshing ? '刷新中...' : '手动刷新状态' }}
          </el-button>
        </template>
      </el-alert>
    </div>

    <!-- 分析参数设置 -->
    <div class="analysis-params" v-if="!analysisResult && analysisStatus !== 'pending' && analysisStatus !== 'processing'">
      <el-divider content-position="left">分析设置</el-divider>
      <el-form :model="params" label-width="120px">
        <el-form-item label="目标收益率">
          <el-input-number v-model="params.target_profit_pct" :min="5" :max="100" :step="5" />
          <span class="unit">%</span>
        </el-form-item>
        <el-form-item label="分析加仓建议">
          <el-switch v-model="params.include_add_position" />
        </el-form-item>

        <el-divider content-position="left">
          <el-checkbox v-model="enableCapitalAnalysis">启用资金风险分析</el-checkbox>
        </el-divider>

        <template v-if="enableCapitalAnalysis">
          <el-alert
            v-if="hasAccountCapital"
            type="success"
            :closable="false"
            style="margin-bottom: 12px"
          >
            已从资金账户自动获取数据，总投资资金: ¥{{ (accountSummary?.net_capital?.CNY || 0).toLocaleString() }}
          </el-alert>
          <el-alert
            v-else
            type="info"
            :closable="false"
            style="margin-bottom: 12px"
          >
            未设置资金账户，请手动输入资金总量或前往持仓页面设置资金账户
          </el-alert>
          <el-form-item label="投资资金总量">
            <el-input-number
              v-model="params.total_capital"
              :min="10000"
              :max="100000000"
              :step="10000"
              :precision="0"
              :controls="false"
              style="width: 200px"
            />
            <span class="unit">元</span>
            <span class="tip" v-if="!hasAccountCapital">用于计算仓位占比和风险敞口</span>
          </el-form-item>
          <el-form-item label="单股最大仓位">
            <el-input-number v-model="params.max_position_pct" :min="5" :max="100" :step="5" />
            <span class="unit">%</span>
          </el-form-item>
          <el-form-item label="最大亏损容忍">
            <el-input-number v-model="params.max_loss_pct" :min="1" :max="50" :step="1" />
            <span class="unit">%</span>
          </el-form-item>
        </template>
      </el-form>
    </div>

    <!-- 分析失败提示 -->
    <div v-if="analysisResult && analysisResult.status === 'failed'" class="analysis-failed">
      <el-alert type="error" :closable="false">
        <template #title>分析失败</template>
        <template #default>
          <p>{{ analysisResult.error_message || '分析过程中出现错误' }}</p>
          <el-button type="primary" size="small" @click="resetAnalysis" style="margin-top: 10px">
            重新分析
          </el-button>
        </template>
      </el-alert>
    </div>

    <!-- AI连接错误提示 -->
    <div v-else-if="analysisResult && isAIConnectionError" class="analysis-error">
      <el-alert type="warning" :closable="false">
        <template #title>AI服务连接异常</template>
        <template #default>
          <p>{{ analysisResult.action_reason }}</p>
          <p style="margin-top: 8px; color: #909399; font-size: 12px">
            💡 请检查：1. 网络连接是否正常；2. API Key 是否已配置；3. API 服务是否可用
          </p>
          <el-button type="primary" size="small" @click="resetAnalysis" style="margin-top: 10px">
            重新分析
          </el-button>
        </template>
      </el-alert>
    </div>

    <!-- 分析结果展示 -->
    <div v-else-if="analysisResult" class="analysis-result">
      <el-divider content-position="left">分析结果</el-divider>

      <!-- 操作建议 -->
      <div class="action-section">
        <div class="action-badge" :class="actionClass">
          {{ actionText }}
        </div>
        <div class="confidence">
          置信度: <el-progress :percentage="analysisResult.confidence" :stroke-width="8" style="width: 120px; display: inline-flex;" />
        </div>
      </div>

      <!-- 建议理由 -->
      <div class="reason-section">
        <h4>建议理由</h4>
        <div class="markdown-content" v-html="renderMarkdown(analysisResult.action_reason || '暂无')"></div>
      </div>

      <!-- 价格目标 -->
      <div class="price-targets" v-if="analysisResult.price_targets">
        <h4>价格目标</h4>
        <el-row :gutter="20">
          <el-col :span="8">
            <div class="target-card loss-bg">
              <div class="label">止损价</div>
              <div class="value">¥{{ analysisResult.price_targets.stop_loss_price?.toFixed(2) || '-' }}</div>
              <div class="pct">{{ analysisResult.price_targets.stop_loss_pct?.toFixed(1) || '-' }}%</div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="target-card neutral-bg">
              <div class="label">回本价</div>
              <div class="value">¥{{ analysisResult.price_targets.breakeven_price?.toFixed(2) || '-' }}</div>
              <div class="pct">0%</div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="target-card profit-bg">
              <div class="label">止盈价</div>
              <div class="value">¥{{ analysisResult.price_targets.take_profit_price?.toFixed(2) || '-' }}</div>
              <div class="pct">+{{ analysisResult.price_targets.take_profit_pct?.toFixed(1) || '-' }}%</div>
            </div>
          </el-col>
        </el-row>
      </div>

      <!-- 风险与机会评估 -->
      <el-row :gutter="20" class="assessment-row">
        <el-col :span="12">
          <div class="assessment-card">
            <h4><el-icon><WarningFilled /></el-icon> 风险评估</h4>
            <div class="markdown-content" v-html="renderMarkdown(analysisResult.risk_assessment || '暂无')"></div>
          </div>
        </el-col>
        <el-col :span="12">
          <div class="assessment-card">
            <h4><el-icon><StarFilled /></el-icon> 机会评估</h4>
            <div class="markdown-content" v-html="renderMarkdown(analysisResult.opportunity_assessment || '暂无')"></div>
          </div>
        </el-col>
      </el-row>

      <!-- 资金风险指标（如果启用） -->
      <div v-if="analysisResult.risk_metrics" class="risk-metrics-section">
        <h4><el-icon><WalletFilled /></el-icon> 仓位风险分析</h4>
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="仓位占比">
            <span :class="getRiskLevelClass(analysisResult.risk_metrics.risk_level)">
              {{ analysisResult.risk_metrics.position_pct?.toFixed(2) }}%
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="持仓市值">
            ¥{{ analysisResult.risk_metrics.position_value?.toLocaleString() }}
          </el-descriptions-item>
          <el-descriptions-item label="最大亏损金额">
            <span class="loss">¥{{ analysisResult.risk_metrics.max_loss_amount?.toLocaleString() }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="对总资金影响">
            <span class="loss">{{ analysisResult.risk_metrics.max_loss_impact_pct?.toFixed(2) }}%</span>
          </el-descriptions-item>
          <el-descriptions-item label="可加仓金额">
            <span class="profit">¥{{ analysisResult.risk_metrics.available_add_amount?.toLocaleString() }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="风险等级">
            <el-tag :type="getRiskTagType(analysisResult.risk_metrics.risk_level)" size="small">
              {{ getRiskLevelText(analysisResult.risk_metrics.risk_level) }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>
        <p class="risk-summary">{{ analysisResult.risk_metrics.risk_summary }}</p>
      </div>

      <!-- 详细分析 -->
      <el-collapse>
        <el-collapse-item title="查看详细分析" name="detail">
          <div class="detailed-analysis markdown-content" v-html="renderMarkdown(analysisResult.detailed_analysis || '暂无详细分析')"></div>
        </el-collapse-item>
      </el-collapse>
    </div>

    <template #footer>
      <span class="dialog-footer">
        <el-button @click="visible = false">关闭</el-button>
        <el-button
          v-if="!analysisResult"
          type="primary"
          :loading="loading"
          @click="handleAnalyze"
        >
          开始分析
        </el-button>
        <el-button
          v-else
          type="primary"
          @click="resetAnalysis"
        >
          重新分析
        </el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { WarningFilled, StarFilled, WalletFilled, Loading, Refresh } from '@element-plus/icons-vue'
import { portfolioApi, type PositionItem, type PositionAnalysisResult, type PositionAnalysisParams, type AccountSummary } from '@/api/portfolio'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { marked } from 'marked'

// 配置marked选项
marked.setOptions({ breaks: true, gfm: true })

// Markdown渲染函数（后端已经转换为Markdown格式，前端直接渲染）
const renderMarkdown = (content: string) => {
  if (!content) return ''
  
  try {
    return marked.parse(content) as string
  } catch (e) {
    return `<pre style="white-space: pre-wrap; font-family: inherit;">${content}</pre>`
  }
}

const props = defineProps<{
  modelValue: boolean
  position: PositionItem | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const router = useRouter()
const loading = ref(false)
const refreshing = ref(false)
const analysisResult = ref<PositionAnalysisResult | null>(null)
const enableCapitalAnalysis = ref(false)
const accountSummary = ref<AccountSummary | null>(null)

// 异步分析相关状态
const analysisId = ref<string | null>(null)
const analysisStatus = ref<string>('idle')  // idle, pending, processing, completed, failed

const hasAccountCapital = computed(() => {
  const netCapital = accountSummary.value?.net_capital?.CNY || 0
  return netCapital > 0
})
const params = ref<PositionAnalysisParams>({
  research_depth: '标准',
  include_add_position: true,
  target_profit_pct: 20,
  total_capital: 100000,    // 默认10万
  max_position_pct: 30,     // 默认30%
  max_loss_pct: 10          // 默认10%
})

// 加载资金账户信息
const loadAccountSummary = async () => {
  try {
    const res = await portfolioApi.getAccountSummary()
    if (res.success && res.data) {
      accountSummary.value = res.data
      // 如果有资金账户，自动启用资金分析并填充数据
      // 使用净入金（总投资资金）而不是总资产
      const netCapital = res.data.net_capital?.CNY || 0
      if (netCapital > 0) {
        enableCapitalAnalysis.value = true
        params.value.total_capital = netCapital
        params.value.max_position_pct = res.data.settings?.max_position_pct || 30
        params.value.max_loss_pct = res.data.settings?.max_loss_pct || 10
      }
    }
  } catch (e) {
    console.error('加载资金账户失败', e)
  }
}

// 重置状态
watch(visible, (val) => {
  if (val) {
    // 打开对话框时先重置状态，再加载数据
    // 重要：必须先清空之前的分析结果，避免显示其他股票的缓存数据
    analysisResult.value = null
    analysisId.value = null
    analysisStatus.value = 'idle'

    // 加载资金账户信息和已有分析报告
    loadAccountSummary()
    loadExistingAnalysis()
  }
})

// 不启用资金分析时清除相关参数
watch(enableCapitalAnalysis, (val) => {
  if (!val) {
    params.value.total_capital = undefined
  } else {
    // 恢复资金账户数据或默认值（使用净入金而非总资产）
    const netCapital = accountSummary.value?.net_capital?.CNY || 0
    params.value.total_capital = netCapital > 0 ? netCapital : 100000
  }
})

// 检查是否是AI连接错误
const isAIConnectionError = computed(() => {
  if (!analysisResult.value) return false
  const reason = analysisResult.value.action_reason || ''
  return reason.includes('AI服务') ||
         reason.includes('连接失败') ||
         reason.includes('Connection error') ||
         reason.includes('AI分析暂时不可用') ||
         (analysisResult.value.confidence === 0 && reason.includes('error'))
})

// 操作建议样式
const actionClass = computed(() => {
  if (!analysisResult.value) return ''
  const map: Record<string, string> = {
    add: 'action-add',
    reduce: 'action-reduce',
    hold: 'action-hold',
    clear: 'action-clear'
  }
  return map[analysisResult.value.action] || 'action-hold'
})

const actionText = computed(() => {
  if (!analysisResult.value) return ''
  const map: Record<string, string> = {
    add: '建议加仓',
    reduce: '建议减仓',
    hold: '建议持有',
    clear: '建议清仓'
  }
  return map[analysisResult.value.action] || '建议持有'
})

// 执行分析（异步模式）
const handleAnalyze = async () => {
  if (!props.position) return

  loading.value = true

  try {
    // 第一步：检查是否有单股分析报告缓存
    const cacheRes = await portfolioApi.checkStockAnalysisCache(
      props.position.code,
      props.position.market
    )

    if (cacheRes.success && cacheRes.data) {
      const hasCache = cacheRes.data.has_cache

      // 如果没有缓存，提示用户选择
      if (!hasCache) {
        loading.value = false
        try {
          await ElMessageBox.confirm(
            '当前没有可用的单股分析报告缓存。\n\n' +
            '建议先进行单股分析以获得更准确的持仓分析结果。\n\n' +
            '您可以选择：\n' +
            '• 继续分析：直接进行持仓分析（不使用单股分析报告）\n' +
            '• 先去单股分析：先跳转到单股分析页面进行分析',
            '提示：缺少单股分析报告',
            {
              confirmButtonText: '继续分析',
              cancelButtonText: '先去单股分析',
              type: 'warning',
              distinguishCancelAndClose: true
            }
          )
          // 用户选择"继续分析"，继续执行分析流程
        } catch (action: any) {
          // 用户选择"先去单股分析"或关闭对话框
          if (action === 'cancel') {
            // 跳转到单股分析页面，带上股票代码参数
            const marketMap: Record<string, string> = {
              CN: 'A股',
              HK: '港股',
              US: '美股'
            }
            const marketName = marketMap[props.position.market] || 'A股'
            router.push(`/analysis/single?stock_code=${props.position.code}&market=${marketName}`)
            visible.value = false // 关闭当前对话框
          }
          return // 取消分析，不执行后续流程
        }
      } else {
        // 有缓存，可以显示缓存信息（可选）
        const ageMinutes = cacheRes.data.cache_age_minutes || 0
        const ageText = ageMinutes < 60 
          ? `${ageMinutes}分钟前` 
          : `${Math.floor(ageMinutes / 60)}小时前`
        console.log(`使用缓存报告（${ageText}）`)
      }
    }

    // 第二步：提交分析任务
    loading.value = true
    analysisStatus.value = 'pending'

    const res = await portfolioApi.analyzePositionByCode(
      props.position.code,
      props.position.market,
      params.value
    )

    console.log('[开始分析] 收到响应:', res)
    if (res.success && res.data) {
      // 兼容task_id和analysis_id两种字段名
      analysisId.value = res.data.analysis_id || res.data.task_id
      analysisStatus.value = res.data.status || 'pending'
      
      console.log('[开始分析] 设置analysisId:', analysisId.value, 'status:', analysisStatus.value)

      if (res.data.status === 'completed') {
        // 已有完成的报告，直接获取结果
        await fetchAnalysisResult(analysisId.value)
        ElMessage.success('已有最近的分析报告')
      } else {
        // 任务已提交，不自动轮询，用户可手动刷新
        ElMessage.success(res.data.message || '分析任务已提交，预计需要2-5分钟，请稍后点击"手动刷新状态"查看结果')
      }
    } else {
      ElMessage.error(res.message || '提交分析任务失败')
      analysisStatus.value = 'failed'
    }
  } catch (error: any) {
    // 如果是MessageBox的取消操作，不显示错误
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error.message || '提交分析任务失败')
      analysisStatus.value = 'failed'
    }
  } finally {
    loading.value = false
  }
}



// 获取分析结果
const fetchAnalysisResult = async (id: string) => {
  try {
    const res = await portfolioApi.getPositionAnalysisStatus(id)
    if (res.success && res.data) {
      analysisResult.value = res.data
      analysisStatus.value = res.data.status || 'completed'
    }
  } catch (error) {
    console.error('获取分析结果失败:', error)
  }
}

// 手动刷新状态
const manualRefreshStatus = async () => {
  if (!analysisId.value) {
    console.warn('[手动刷新状态] analysisId为空，无法刷新')
    ElMessage.warning('分析任务ID不存在，请重新开始分析')
    return
  }

  console.log('[手动刷新状态] 开始刷新，analysisId:', analysisId.value)
  refreshing.value = true
  try {
    const res = await portfolioApi.getPositionAnalysisStatus(analysisId.value)
    console.log('[手动刷新状态] 收到响应:', res)
    if (res.success && res.data) {
      analysisStatus.value = res.data.status || 'unknown'

      if (res.data.status === 'completed') {
        analysisResult.value = res.data
        ElMessage.success('分析完成！')
      } else if (res.data.status === 'failed') {
        ElMessage.error(res.data.error_message || '分析失败')
      } else {
        ElMessage.info(`当前状态: ${res.data.status}`)
      }
    } else {
      console.error('[手动刷新状态] 响应失败:', res)
      ElMessage.error(res.message || '获取分析状态失败')
    }
  } catch (error: any) {
    console.error('[手动刷新状态] 请求失败:', error)
    ElMessage.error(error.message || '刷新状态失败')
  } finally {
    refreshing.value = false
  }
}

// 加载已有的分析报告
// 加载已有的分析报告
// 注意：调用此函数前应先清空 analysisResult，避免显示其他股票的缓存数据
const loadExistingAnalysis = async () => {
  if (!props.position) return

  try {
    const res = await portfolioApi.getLatestPositionAnalysis(
      props.position.code,
      props.position.market
    )
    // 只有当后端返回有效数据时才更新状态
    // 如果 res.data 为 null，说明该股票没有分析报告，保持状态为 idle
    if (res.success && res.data) {
      analysisId.value = res.data.analysis_id
      analysisStatus.value = res.data.status || 'unknown'

      if (res.data.status === 'completed') {
        analysisResult.value = res.data
      } else if (res.data.status === 'pending' || res.data.status === 'processing') {
        // 有正在进行的分析，不自动轮询，用户可手动刷新查看状态
        ElMessage.info('检测到正在进行的分析任务，请点击"手动刷新状态"查看最新进度')
      }
    }
    // 如果 res.data 为 null，不做任何操作，保持之前 watch 中重置的 idle 状态
  } catch (error) {
    console.error('加载已有分析报告失败:', error)
  }
}

// 重新分析
const resetAnalysis = () => {
  analysisResult.value = null
  analysisId.value = null
  analysisStatus.value = 'idle'
}

// 风险等级相关辅助方法
const getRiskLevelClass = (level?: string) => {
  const map: Record<string, string> = {
    low: 'risk-low',
    medium: 'risk-medium',
    high: 'risk-high',
    critical: 'risk-critical'
  }
  return map[level || ''] || ''
}

const getRiskTagType = (level?: string): 'success' | 'warning' | 'danger' | 'info' => {
  const map: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
    low: 'success',
    medium: 'warning',
    high: 'danger',
    critical: 'danger'
  }
  return map[level || ''] || 'info'
}

const getRiskLevelText = (level?: string) => {
  const map: Record<string, string> = {
    low: '低风险',
    medium: '中风险',
    high: '高风险',
    critical: '极高风险'
  }
  return map[level || ''] || '未知'
}
</script>

<style scoped>
.position-info {
  margin-bottom: 16px;
}

.profit { color: #f56c6c; } /* 红色表示盈利（中国股市规范） */
.loss { color: #67c23a; } /* 绿色表示亏损（中国股市规范） */

.analysis-status {
  margin: 16px 0;

  ul {
    margin: 8px 0 0 20px;
    padding: 0;
    li {
      margin: 4px 0;
    }
  }

  .is-loading {
    animation: rotating 2s linear infinite;
    margin-right: 8px;
  }
}

@keyframes rotating {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.analysis-params {
  margin: 16px 0;
}

.unit {
  margin-left: 8px;
  color: #909399;
}

.action-section {
  display: flex;
  align-items: center;
  gap: 24px;
  margin: 16px 0;
}

.action-badge {
  padding: 8px 24px;
  border-radius: 20px;
  font-size: 16px;
  font-weight: bold;
}

.action-add { background: #e1f3d8; color: #67c23a; }
.action-reduce { background: #fde2e2; color: #f56c6c; }
.action-hold { background: #faecd8; color: #e6a23c; }
.action-clear { background: #fde2e2; color: #f56c6c; }

.reason-section, .price-targets {
  margin: 16px 0;
}

.reason-section h4, .price-targets h4, .assessment-card h4 {
  margin-bottom: 8px;
  font-size: 14px;
  color: #303133;
}

.target-card {
  text-align: center;
  padding: 12px;
  border-radius: 8px;
}

.loss-bg { background: #fef0f0; }
.neutral-bg { background: #f5f7fa; }
.profit-bg { background: #f0f9eb; }

.target-card .label {
  font-size: 12px;
  color: #909399;
}

.target-card .value {
  font-size: 18px;
  font-weight: bold;
  margin: 4px 0;
}

.target-card .pct {
  font-size: 12px;
  color: #606266;
}

.assessment-row {
  margin: 16px 0;
}

.assessment-card {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 8px;
}

.assessment-card h4 {
  display: flex;
  align-items: center;
  gap: 4px;
}

.detailed-analysis {
  line-height: 1.6;
  color: #606266;
}

.markdown-content {
  line-height: 1.6;
  color: #606266;
}

.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3),
.markdown-content :deep(h4) {
  margin-top: 16px;
  margin-bottom: 8px;
  font-weight: bold;
  color: #303133;
}

.markdown-content :deep(h1) { font-size: 20px; }
.markdown-content :deep(h2) { font-size: 18px; }
.markdown-content :deep(h3) { font-size: 16px; }
.markdown-content :deep(h4) { font-size: 14px; }

.markdown-content :deep(p) {
  margin: 8px 0;
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  margin: 8px 0;
  padding-left: 24px;
}

.markdown-content :deep(li) {
  margin: 4px 0;
}

.markdown-content :deep(code) {
  background: #f5f7fa;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Courier New', monospace;
  font-size: 0.9em;
}

.markdown-content :deep(pre) {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  overflow-x: auto;
  margin: 12px 0;
}

.markdown-content :deep(pre code) {
  background: none;
  padding: 0;
}

.markdown-content :deep(blockquote) {
  border-left: 4px solid #409eff;
  padding-left: 12px;
  margin: 12px 0;
  color: #606266;
}

.markdown-content :deep(strong) {
  font-weight: bold;
  color: #303133;
}

/* 资金风险指标样式 */
.risk-metrics-section {
  margin: 16px 0;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 8px;
}

.risk-metrics-section h4 {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 12px;
  font-size: 14px;
  color: #303133;
}

.risk-summary {
  margin-top: 8px;
  padding: 8px;
  background: #fff;
  border-radius: 4px;
  font-size: 13px;
  color: #606266;
}

.risk-low { color: #67c23a; }
.risk-medium { color: #e6a23c; }
.risk-high { color: #f56c6c; }
.risk-critical { color: #f56c6c; font-weight: bold; }

.tip {
  margin-left: 8px;
  font-size: 12px;
  color: #909399;
}
</style>

