<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="持仓分析报告"
    width="800px"
    destroy-on-close
  >
    <div v-if="report" class="analysis-report">
      <!-- 风险提示 -->
      <div class="risk-disclaimer">
        <el-alert
          type="warning"
          :closable="false"
          show-icon
        >
          <template #title>
            <span style="font-size: 14px;">
              <strong>⚠️ 重要提示：</strong>本次分析所有分析结论用于学习和验证AI股票分析技术，不作为真实炒股操盘指导。
            </span>
          </template>
        </el-alert>
      </div>

      <!-- 健康度评分 -->
      <div class="score-section">
        <div class="score-circle" :class="scoreClass">
          <div class="score-value">{{ report.health_score?.toFixed(0) || '-' }}</div>
          <div class="score-label">健康度</div>
        </div>
        <div class="risk-badge">
          <el-tag :type="riskTagType" size="large">风险等级: {{ report.risk_level || '-' }}</el-tag>
        </div>
      </div>

      <!-- 组合概况 -->
      <el-card shadow="never" class="section-card">
        <template #header><span>📊 组合概况</span></template>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="持仓数量">{{ report.portfolio_snapshot?.total_positions }} 只</el-descriptions-item>
          <el-descriptions-item label="总市值">¥{{ formatNumber(report.portfolio_snapshot?.total_value) }}</el-descriptions-item>
          <el-descriptions-item label="总成本">¥{{ formatNumber(report.portfolio_snapshot?.total_cost) }}</el-descriptions-item>
          <el-descriptions-item label="浮动盈亏">
            <span :class="pnlClass(report.portfolio_snapshot?.unrealized_pnl)">
              {{ formatPnl(report.portfolio_snapshot?.unrealized_pnl) }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="盈亏比例">
            <span :class="pnlClass(report.portfolio_snapshot?.unrealized_pnl_pct)">
              {{ formatPct(report.portfolio_snapshot?.unrealized_pnl_pct) }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="分析耗时">{{ report.execution_time?.toFixed(1) }}s</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 集中度分析 -->
      <el-card shadow="never" class="section-card">
        <template #header><span>📈 集中度分析</span></template>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="第一大持仓占比">{{ report.concentration_analysis?.top1_pct?.toFixed(1) }}%</el-descriptions-item>
          <el-descriptions-item label="前三大持仓占比">{{ report.concentration_analysis?.top3_pct?.toFixed(1) }}%</el-descriptions-item>
          <el-descriptions-item label="前五大持仓占比">{{ report.concentration_analysis?.top5_pct?.toFixed(1) }}%</el-descriptions-item>
          <el-descriptions-item label="HHI指数">{{ report.concentration_analysis?.hhi_index?.toFixed(0) }}</el-descriptions-item>
          <el-descriptions-item label="行业数量">{{ report.concentration_analysis?.industry_count }} 个</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- AI分析结果 -->
      <el-card shadow="never" class="section-card">
        <template #header><span>🤖 AI分析建议</span></template>
        
        <div class="ai-section">
          <div class="ai-title">📝 综合评价</div>
          <div class="ai-content">{{ report.ai_analysis?.summary || '暂无' }}</div>
        </div>

        <el-row :gutter="16">
          <el-col :span="12">
            <div class="ai-section">
              <div class="ai-title success">✅ 组合优势</div>
              <ul class="ai-list">
                <li v-for="(item, idx) in report.ai_analysis?.strengths" :key="idx">{{ item }}</li>
              </ul>
              <div v-if="!report.ai_analysis?.strengths?.length" class="ai-empty">暂无</div>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="ai-section">
              <div class="ai-title warning">⚠️ 组合劣势</div>
              <ul class="ai-list">
                <li v-for="(item, idx) in report.ai_analysis?.weaknesses" :key="idx">{{ item }}</li>
              </ul>
              <div v-if="!report.ai_analysis?.weaknesses?.length" class="ai-empty">暂无</div>
            </div>
          </el-col>
        </el-row>

        <div class="ai-section">
          <div class="ai-title primary">💡 调仓建议</div>
          <ul class="ai-list">
            <li v-for="(item, idx) in report.ai_analysis?.suggestions" :key="idx">{{ item }}</li>
          </ul>
          <div v-if="!report.ai_analysis?.suggestions?.length" class="ai-empty">暂无</div>
        </div>
      </el-card>
    </div>
    
    <el-empty v-else description="暂无分析数据" />
    
    <template #footer>
      <el-button @click="$emit('update:visible', false)">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { PortfolioAnalysisReport } from '@/api/portfolio'

const props = defineProps<{
  visible: boolean
  report?: PortfolioAnalysisReport | null
}>()

defineEmits<{
  'update:visible': [value: boolean]
}>()

const scoreClass = computed(() => {
  const score = props.report?.health_score || 0
  if (score >= 80) return 'excellent'
  if (score >= 60) return 'good'
  if (score >= 40) return 'fair'
  return 'poor'
})

const riskTagType = computed(() => {
  const level = props.report?.risk_level
  if (level === '低') return 'success'
  if (level === '中') return 'warning'
  return 'danger'
})

const formatNumber = (val?: number) => {
  if (val === undefined || val === null) return '-'
  return val.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const formatPnl = (val?: number) => {
  if (val === undefined || val === null) return '-'
  const prefix = val >= 0 ? '+' : ''
  return prefix + formatNumber(val)
}

const formatPct = (val?: number) => {
  if (val === undefined || val === null) return '-'
  const prefix = val >= 0 ? '+' : ''
  return prefix + val.toFixed(2) + '%'
}

const pnlClass = (val?: number) => {
  if (val === undefined || val === null) return ''
  return val >= 0 ? 'profit' : 'loss'
}
</script>

<style scoped>
.analysis-report {
  max-height: 70vh;
  overflow-y: auto;
}

.score-section {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 40px;
  margin-bottom: 24px;
  padding: 20px;
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e7ed 100%);
  border-radius: 8px;
}

.score-circle {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: white;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.score-circle.excellent { border: 4px solid #67C23A; }
.score-circle.good { border: 4px solid #409EFF; }
.score-circle.fair { border: 4px solid #E6A23C; }
.score-circle.poor { border: 4px solid #F56C6C; }

.score-value {
  font-size: 36px;
  font-weight: 700;
}

.score-circle.excellent .score-value { color: #67C23A; }
.score-circle.good .score-value { color: #409EFF; }
.score-circle.fair .score-value { color: #E6A23C; }
.score-circle.poor .score-value { color: #F56C6C; }

.score-label {
  font-size: 14px;
  color: #909399;
}

.section-card {
  margin-bottom: 16px;
}

.profit { color: #F56C6C; } /* 红色表示盈利（中国股市规范） */
.loss { color: #67C23A; } /* 绿色表示亏损（中国股市规范） */

.ai-section {
  margin-bottom: 16px;
}

.ai-title {
  font-weight: 600;
  margin-bottom: 8px;
  font-size: 14px;
}

.ai-title.success { color: #67C23A; }
.ai-title.warning { color: #E6A23C; }
.ai-title.primary { color: #409EFF; }

.ai-content {
  color: #606266;
  line-height: 1.6;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 4px;
}

.ai-list {
  margin: 0;
  padding-left: 20px;
  color: #606266;
  line-height: 1.8;
}

.ai-empty {
  color: #909399;
  font-size: 13px;
}

.risk-disclaimer {
  margin-bottom: 24px;
}

.risk-disclaimer :deep(.el-alert) {
  background: linear-gradient(135deg, #fff3cd 0%, #ffe69c 100%);
  border: 2px solid #ffc107;
  border-radius: 12px;
  padding: 16px 20px;
  box-shadow: 0 4px 12px rgba(255, 193, 7, 0.2);
}
</style>

