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
import { WarningFilled, StarFilled } from '@element-plus/icons-vue'
import { portfolioApi, type PositionItem, type PositionAnalysisResult, type PositionAnalysisParams } from '@/api/portfolio'
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
const params = ref<PositionAnalysisParams>({
  research_depth: '标准',
  include_add_position: true,
  target_profit_pct: 20
})

// 重置状态
watch(visible, (val) => {
  if (!val) {
    analysisResult.value = null
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
    if (res.code === 0 && res.data) {
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
</style>

