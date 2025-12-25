<template>
  <el-dialog
    v-model="visible"
    :title="`复盘详情 - ${report?.trade_info?.code || ''}`"
    width="900px"
    :close-on-click-modal="false"
  >
    <div v-loading="loading" class="review-detail">
      <template v-if="report">
        <!-- 评分概览 -->
        <div class="score-section">
          <div class="overall-score" :class="getScoreClass(report.ai_review?.overall_score)">
            <div class="score-value">{{ report.ai_review?.overall_score || 0 }}</div>
            <div class="score-label">综合评分</div>
          </div>
          <div class="sub-scores">
            <div class="sub-score-item">
              <span class="label">时机评分:</span>
              <el-progress
                :percentage="report.ai_review?.timing_score || 0"
                :color="getProgressColor(report.ai_review?.timing_score || 0)"
                :show-text="false"
              />
              <span class="score">{{ report.ai_review?.timing_score || 0 }}分</span>
            </div>
            <div class="sub-score-item">
              <span class="label">仓位评分:</span>
              <el-progress
                :percentage="report.ai_review?.position_score || 0"
                :color="getProgressColor(report.ai_review?.position_score || 0)"
                :show-text="false"
              />
              <span class="score">{{ report.ai_review?.position_score || 0 }}分</span>
            </div>
            <div class="sub-score-item">
              <span class="label">情绪评分:</span>
              <el-progress
                :percentage="report.ai_review?.emotion_score || 0"
                :color="getProgressColor(report.ai_review?.emotion_score || 0)"
                :show-text="false"
              />
              <span class="score">{{ report.ai_review?.emotion_score || 0 }}分</span>
            </div>
            <div class="sub-score-item">
              <span class="label">归因评分:</span>
              <el-progress
                :percentage="report.ai_review?.attribution_score || 0"
                :color="getProgressColor(report.ai_review?.attribution_score || 0)"
                :show-text="false"
              />
              <span class="score">{{ report.ai_review?.attribution_score || 0 }}分</span>
            </div>
          </div>
        </div>

        <!-- 交易摘要 -->
        <el-descriptions title="交易摘要" :column="3" border size="small" class="section">
          <el-descriptions-item label="股票代码">{{ report.trade_info?.code }}</el-descriptions-item>
          <el-descriptions-item label="持仓天数">{{ report.trade_info?.holding_days }}天</el-descriptions-item>
          <el-descriptions-item label="盈亏金额">
            <span :class="(report.trade_info?.realized_pnl || 0) >= 0 ? 'positive' : 'negative'">
              {{ formatPnl(report.trade_info?.realized_pnl) }}元
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="买入均价">{{ report.trade_info?.avg_buy_price?.toFixed(2) }}</el-descriptions-item>
          <el-descriptions-item label="卖出均价">{{ report.trade_info?.avg_sell_price?.toFixed(2) }}</el-descriptions-item>
          <el-descriptions-item label="收益率">
            <span :class="(report.trade_info?.realized_pnl_pct || 0) >= 0 ? 'positive' : 'negative'">
              {{ formatPct(report.trade_info?.realized_pnl_pct) }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="手续费" :span="3">{{ report.trade_info?.total_commission?.toFixed(2) }}元</el-descriptions-item>
        </el-descriptions>

        <!-- 收益分析 -->
        <el-descriptions title="收益分析" :column="2" border size="small" class="section">
          <el-descriptions-item label="实际收益">
            <span :class="(report.ai_review?.actual_pnl || 0) >= 0 ? 'positive' : 'negative'">
              {{ formatPnl(report.ai_review?.actual_pnl) }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="理论最优">
            <span class="positive">{{ formatPnl(report.ai_review?.optimal_pnl) }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="错失收益" v-if="(report.ai_review?.missed_profit || 0) > 0">
            <span class="warning">{{ formatPnl(report.ai_review?.missed_profit) }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="避免亏损" v-if="(report.ai_review?.avoided_loss || 0) > 0">
            <span class="positive">{{ formatPnl(report.ai_review?.avoided_loss) }}</span>
          </el-descriptions-item>
        </el-descriptions>

        <!-- 关联交易计划 (如果有) -->
        <div v-if="report.trading_system_name" class="section trading-plan-section">
          <h4><el-icon><Document /></el-icon> 关联交易计划</h4>
          <div class="trading-plan-info">
            <el-tag type="primary" size="large">{{ report.trading_system_name }}</el-tag>
            <p class="plan-note">
              本次交易已关联交易计划，AI 分析已结合计划规则进行评估。
              详细的计划执行情况分析请查看下方的"AI分析总结"和"详细分析"部分。
            </p>
          </div>
        </div>

        <!-- AI分析 -->
        <div class="section">
          <h4>AI分析总结</h4>
          <div class="summary markdown-content" v-html="renderMarkdown(report.ai_review?.summary)"></div>
        </div>

        <!-- 优缺点 -->
        <el-row :gutter="16" class="section">
          <el-col :span="12">
            <div class="analysis-card strengths">
              <h4><el-icon><CircleCheck /></el-icon> 做得好的地方</h4>
              <div class="markdown-content" v-html="renderMarkdown((report.ai_review?.strengths || []).join('\n\n'))"></div>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="analysis-card weaknesses">
              <h4><el-icon><Warning /></el-icon> 需要改进的地方</h4>
              <div class="markdown-content" v-html="renderMarkdown((report.ai_review?.weaknesses || []).join('\n\n'))"></div>
            </div>
          </el-col>
        </el-row>

        <!-- 建议 -->
        <div class="section" v-if="report.ai_review?.suggestions?.length">
          <h4><el-icon><Pointer /></el-icon> 改进建议</h4>
          <div class="suggestions markdown-content" v-html="renderMarkdown((report.ai_review?.suggestions || []).join('\n\n'))"></div>
        </div>

        <!-- 交易计划执行情况 (如果有) -->
        <el-row :gutter="16" class="section" v-if="report.ai_review?.plan_adherence || report.ai_review?.plan_deviation">
          <el-col :span="12" v-if="report.ai_review?.plan_adherence">
            <div class="analysis-card plan-adherence">
              <h4><el-icon><CircleCheck /></el-icon> 计划执行良好</h4>
              <div class="markdown-content" v-html="renderMarkdown(report.ai_review.plan_adherence)"></div>
            </div>
          </el-col>
          <el-col :span="12" v-if="report.ai_review?.plan_deviation">
            <div class="analysis-card plan-deviation">
              <h4><el-icon><Warning /></el-icon> 偏离计划之处</h4>
              <div class="markdown-content" v-html="renderMarkdown(report.ai_review.plan_deviation)"></div>
            </div>
          </el-col>
        </el-row>

        <!-- 详细分析 -->
        <el-collapse class="section">
          <el-collapse-item title="时机分析" name="timing" v-if="report.ai_review?.timing_analysis">
            <div class="markdown-content" v-html="renderMarkdown(report.ai_review?.timing_analysis)"></div>
          </el-collapse-item>
          <el-collapse-item title="仓位分析" name="position" v-if="report.ai_review?.position_analysis">
            <div class="markdown-content" v-html="renderMarkdown(report.ai_review?.position_analysis)"></div>
          </el-collapse-item>
          <el-collapse-item title="情绪分析" name="emotion" v-if="report.ai_review?.emotion_analysis">
            <div class="markdown-content" v-html="renderMarkdown(report.ai_review?.emotion_analysis)"></div>
          </el-collapse-item>
          <el-collapse-item title="归因分析" name="attribution" v-if="report.ai_review?.attribution_analysis">
            <div class="markdown-content" v-html="renderMarkdown(report.ai_review?.attribution_analysis)"></div>
          </el-collapse-item>
        </el-collapse>
      </template>
    </div>

    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
      <el-button v-if="report && !report.is_case_study" type="primary" @click="showSaveCaseDialog">
        保存到案例库
      </el-button>
    </template>
  </el-dialog>

  <!-- 保存为案例对话框 -->
  <SaveAsCaseDialog
    v-model="saveCaseDialogVisible"
    :review-id="props.reviewId"
    :stock-code="report?.trade_info?.code"
    @success="handleSaveCaseSuccess"
  />
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { CircleCheck, Warning, Pointer, Document } from '@element-plus/icons-vue'
import { reviewApi, type TradeReviewReport } from '@/api/review'
import { marked } from 'marked'
import SaveAsCaseDialog from './SaveAsCaseDialog.vue'

// 配置 marked 选项
marked.setOptions({ breaks: true, gfm: true })

const props = defineProps<{
  modelValue: boolean
  reviewId: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const loading = ref(false)
const report = ref<TradeReviewReport | null>(null)
const saveCaseDialogVisible = ref(false)

const loadReport = async () => {
  if (!props.reviewId) return

  try {
    loading.value = true
    const res = await reviewApi.getReviewDetail(props.reviewId)
    if (res.success) {
      report.value = res.data || null
      // 🔍 调试日志
      console.log('📊 [复盘详情] API 返回数据:', res.data)
      console.log('📊 [复盘详情] trading_system_id:', res.data?.trading_system_id)
      console.log('📊 [复盘详情] trading_system_name:', res.data?.trading_system_name)
    }
  } catch (e: any) {
    ElMessage.error(e.message || '加载复盘详情失败')
  } finally {
    loading.value = false
  }
}

const getScoreClass = (score?: number) => {
  if (!score) return ''
  if (score >= 80) return 'excellent'
  if (score >= 60) return 'good'
  return 'poor'
}

const getProgressColor = (score?: number) => {
  if (!score) return '#909399'
  if (score >= 80) return '#67c23a'
  if (score >= 60) return '#e6a23c'
  return '#f56c6c'
}

const formatPnl = (value?: number) => {
  if (value === undefined || value === null) return '-'
  const prefix = value >= 0 ? '+' : ''
  return prefix + value.toFixed(2)
}

const formatPct = (value?: number) => {
  if (value === undefined || value === null) return '-'
  const prefix = value >= 0 ? '+' : ''
  return prefix + value.toFixed(2) + '%'
}

const renderMarkdown = (content?: string) => {
  if (!content) return ''
  try {
    return marked.parse(content) as string
  } catch (e) {
    return `<pre style="white-space: pre-wrap; font-family: inherit;">${content}</pre>`
  }
}

const showSaveCaseDialog = () => {
  saveCaseDialogVisible.value = true
}

const handleSaveCaseSuccess = () => {
  if (report.value) {
    report.value.is_case_study = true
  }
}

watch(() => [props.modelValue, props.reviewId], ([show, id]) => {
  if (show && id) {
    loadReport()
  }
}, { immediate: true })
</script>

<style scoped lang="scss">
.review-detail {
  .section {
    margin-bottom: 20px;
    h4 {
      margin: 0 0 12px 0;
      font-size: 14px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
  }

  .score-section {
    display: flex;
    gap: 40px;
    margin-bottom: 24px;
    padding: 20px;
    background: #f5f7fa;
    border-radius: 8px;

    .overall-score {
      text-align: center;
      padding: 16px 32px;
      background: #fff;
      border-radius: 8px;

      .score-value {
        font-size: 48px;
        font-weight: 700;
        line-height: 1;
      }
      .score-label {
        margin-top: 8px;
        font-size: 14px;
        color: #909399;
      }

      &.excellent .score-value { color: #67c23a; }
      &.good .score-value { color: #e6a23c; }
      &.poor .score-value { color: #f56c6c; }
    }

    .sub-scores {
      flex: 1;
      display: flex;
      flex-direction: column;
      justify-content: center;
      gap: 12px;

      .sub-score-item {
        display: flex;
        align-items: center;
        gap: 12px;

        .label {
          width: 70px;
          font-size: 13px;
          color: #606266;
          flex-shrink: 0;
        }

        .el-progress {
          flex: 1;

          // 确保隐藏进度条内部文本
          :deep(.el-progress__text) {
            display: none !important;
          }
        }

        .score {
          width: 40px;
          font-size: 13px;
          color: #303133;
          font-weight: 500;
          text-align: right;
          flex-shrink: 0;
        }
      }
    }
  }

  .summary {
    padding: 12px 16px;
    background: #f5f7fa;
    border-radius: 4px;
    line-height: 1.6;
  }

  .markdown-content {
    line-height: 1.6;

    :deep(h1), :deep(h2), :deep(h3), :deep(h4), :deep(h5), :deep(h6) {
      margin: 16px 0 8px 0;
      color: var(--el-text-color-primary);
    }

    :deep(h1) { font-size: 24px; }
    :deep(h2) { font-size: 20px; }
    :deep(h3) { font-size: 16px; }
    :deep(h4) { font-size: 14px; }

    :deep(p) {
      margin: 8px 0;
      line-height: 1.6;
    }

    :deep(ul), :deep(ol) {
      margin: 8px 0;
      padding-left: 20px;

      li {
        margin: 4px 0;
        line-height: 1.5;
      }
    }

    :deep(code) {
      background: var(--el-fill-color-light);
      padding: 2px 6px;
      border-radius: 4px;
      font-family: 'Consolas', 'Monaco', monospace;
      font-size: 13px;
      color: var(--el-text-color-primary);
    }

    :deep(pre) {
      background: var(--el-fill-color-light);
      color: var(--el-text-color-primary);
      padding: 12px;
      border-radius: 6px;
      overflow-x: auto;
      margin: 12px 0;
      font-size: 13px;

      code {
        background: none;
        padding: 0;
        color: inherit;
      }
    }

    :deep(blockquote) {
      border-left: 4px solid var(--el-color-primary);
      margin: 12px 0;
      padding: 8px 12px;
      color: var(--el-text-color-secondary);
      background: var(--el-fill-color-light);
      border-radius: 4px;
    }

    :deep(strong) {
      font-weight: 600;
      color: var(--el-text-color-primary);
    }

    :deep(em) {
      font-style: italic;
      color: var(--el-text-color-regular);
    }
  }

  .analysis-card {
    padding: 16px;
    border-radius: 8px;
    height: 100%;

    &.strengths { background: #f0f9eb; }
    &.weaknesses { background: #fef0f0; }
    &.plan-adherence { background: #e8f4fd; border: 1px solid #b3d8f2; }
    &.plan-deviation { background: #fff7e6; border: 1px solid #ffd591; }

    h4 { margin: 0 0 12px 0; font-size: 14px; }
    ul { margin: 0; padding-left: 20px; li { margin-bottom: 6px; } }
  }

  .suggestions {
    padding-left: 20px;
    li { margin-bottom: 8px; line-height: 1.5; }
  }

  .trading-plan-section {
    .trading-plan-info {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 16px;
      background: #f0f9ff;
      border-radius: 8px;
      border: 1px solid #d1e7ff;

      .el-tag {
        flex-shrink: 0;
      }

      .plan-note {
        margin: 0;
        font-size: 13px;
        color: #606266;
        line-height: 1.6;
      }
    }

    h4 {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 12px;
      font-size: 14px;
      color: #303133;

      .el-icon {
        color: #409eff;
      }
    }
  }

  .positive { color: #67c23a; }
  .negative { color: #f56c6c; }
  .warning { color: #e6a23c; }
}
</style>

