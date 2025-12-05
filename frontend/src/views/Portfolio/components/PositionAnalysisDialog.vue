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

    <!-- 分析参数设置 -->
    <div class="analysis-params" v-if="!analysisResult">
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

    <!-- 分析结果展示 -->
    <div v-if="analysisResult" class="analysis-result">
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
        <p>{{ analysisResult.action_reason || '暂无' }}</p>
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
            <p>{{ analysisResult.risk_assessment || '暂无' }}</p>
          </div>
        </el-col>
        <el-col :span="12">
          <div class="assessment-card">
            <h4><el-icon><StarFilled /></el-icon> 机会评估</h4>
            <p>{{ analysisResult.opportunity_assessment || '暂无' }}</p>
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
          <div class="detailed-analysis">
            {{ analysisResult.detailed_analysis || '暂无详细分析' }}
          </div>
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
import { WarningFilled, StarFilled, WalletFilled } from '@element-plus/icons-vue'
import { portfolioApi, type PositionItem, type PositionAnalysisResult, type PositionAnalysisParams, type AccountSummary } from '@/api/portfolio'
import { ElMessage } from 'element-plus'

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

const loading = ref(false)
const analysisResult = ref<PositionAnalysisResult | null>(null)
const enableCapitalAnalysis = ref(false)
const accountSummary = ref<AccountSummary | null>(null)
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
  if (!val) {
    analysisResult.value = null
  } else {
    // 打开对话框时加载资金账户信息
    loadAccountSummary()
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

// 执行分析
const handleAnalyze = async () => {
  if (!props.position) return

  loading.value = true
  try {
    const res = await portfolioApi.analyzePosition(props.position.id, params.value)
    if (res.success && res.data) {
      analysisResult.value = res.data
      ElMessage.success('分析完成')
    } else {
      ElMessage.error(res.message || '分析失败')
    }
  } catch (error: any) {
    ElMessage.error(error.message || '分析失败')
  } finally {
    loading.value = false
  }
}

// 重新分析
const resetAnalysis = () => {
  analysisResult.value = null
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

.profit { color: #67c23a; }
.loss { color: #f56c6c; }

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
  white-space: pre-wrap;
  line-height: 1.6;
  color: #606266;
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

