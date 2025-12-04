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
              <el-progress 
                :percentage="report.ai_review?.timing_score || 0" 
                :color="getProgressColor(report.ai_review?.timing_score)"
              />
              <span class="label">时机评分</span>
            </div>
            <div class="sub-score-item">
              <el-progress 
                :percentage="report.ai_review?.position_score || 0" 
                :color="getProgressColor(report.ai_review?.position_score)"
              />
              <span class="label">仓位评分</span>
            </div>
            <div class="sub-score-item">
              <el-progress 
                :percentage="report.ai_review?.discipline_score || 0" 
                :color="getProgressColor(report.ai_review?.discipline_score)"
              />
              <span class="label">纪律评分</span>
            </div>
          </div>
        </div>

        <!-- 交易摘要 -->
        <el-descriptions title="交易摘要" :column="3" border size="small" class="section">
          <el-descriptions-item label="股票代码">{{ report.trade_info?.code }}</el-descriptions-item>
          <el-descriptions-item label="持仓天数">{{ report.trade_info?.holding_days }}天</el-descriptions-item>
          <el-descriptions-item label="实现盈亏">
            <span :class="(report.trade_info?.realized_pnl || 0) >= 0 ? 'positive' : 'negative'">
              {{ formatPnl(report.trade_info?.realized_pnl) }}
              ({{ formatPct(report.trade_info?.realized_pnl_pct) }})
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="买入均价">{{ report.trade_info?.avg_buy_price?.toFixed(2) }}</el-descriptions-item>
          <el-descriptions-item label="卖出均价">{{ report.trade_info?.avg_sell_price?.toFixed(2) }}</el-descriptions-item>
          <el-descriptions-item label="手续费">{{ report.trade_info?.total_commission?.toFixed(2) }}</el-descriptions-item>
        </el-descriptions>

        <!-- 收益分析 -->
        <el-descriptions title="收益分析" :column="3" border size="small" class="section">
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

        <!-- AI分析 -->
        <div class="section">
          <h4>AI分析总结</h4>
          <p class="summary">{{ report.ai_review?.summary }}</p>
        </div>

        <!-- 优缺点 -->
        <el-row :gutter="16" class="section">
          <el-col :span="12">
            <div class="analysis-card strengths">
              <h4><el-icon><CircleCheck /></el-icon> 做得好的地方</h4>
              <ul>
                <li v-for="(item, idx) in (report.ai_review?.strengths || [])" :key="idx">{{ item }}</li>
              </ul>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="analysis-card weaknesses">
              <h4><el-icon><Warning /></el-icon> 需要改进的地方</h4>
              <ul>
                <li v-for="(item, idx) in (report.ai_review?.weaknesses || [])" :key="idx">{{ item }}</li>
              </ul>
            </div>
          </el-col>
        </el-row>

        <!-- 建议 -->
        <div class="section" v-if="report.ai_review?.suggestions?.length">
          <h4><el-icon><Pointer /></el-icon> 改进建议</h4>
          <ul class="suggestions">
            <li v-for="(item, idx) in report.ai_review?.suggestions" :key="idx">{{ item }}</li>
          </ul>
        </div>

        <!-- 详细分析 -->
        <el-collapse class="section">
          <el-collapse-item title="时机分析" name="timing" v-if="report.ai_review?.timing_analysis">
            <p>{{ report.ai_review?.timing_analysis }}</p>
          </el-collapse-item>
          <el-collapse-item title="仓位分析" name="position" v-if="report.ai_review?.position_analysis">
            <p>{{ report.ai_review?.position_analysis }}</p>
          </el-collapse-item>
          <el-collapse-item title="情绪分析" name="emotion" v-if="report.ai_review?.emotion_analysis">
            <p>{{ report.ai_review?.emotion_analysis }}</p>
          </el-collapse-item>
        </el-collapse>
      </template>
    </div>

    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
      <el-button v-if="report && !report.is_case_study" type="primary" @click="saveCase">
        保存到案例库
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { CircleCheck, Warning, Pointer } from '@element-plus/icons-vue'
import { reviewApi, type TradeReviewReport } from '@/api/review'

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

const loadReport = async () => {
  if (!props.reviewId) return

  try {
    loading.value = true
    const res = await reviewApi.getReviewDetail(props.reviewId)
    if (res.success) {
      report.value = res.data || null
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

const saveCase = async () => {
  if (!report.value) return
  try {
    const res = await reviewApi.saveAsCase({ review_id: report.value.review_id })
    if (res.success) {
      ElMessage.success('已保存到案例库')
      report.value.is_case_study = true
    }
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
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
        .el-progress { flex: 1; }
        .label { width: 70px; font-size: 13px; color: #606266; }
      }
    }
  }

  .summary {
    padding: 12px 16px;
    background: #f5f7fa;
    border-radius: 4px;
    line-height: 1.6;
  }

  .analysis-card {
    padding: 16px;
    border-radius: 8px;
    height: 100%;

    &.strengths { background: #f0f9eb; }
    &.weaknesses { background: #fef0f0; }

    h4 { margin: 0 0 12px 0; font-size: 14px; }
    ul { margin: 0; padding-left: 20px; li { margin-bottom: 6px; } }
  }

  .suggestions {
    padding-left: 20px;
    li { margin-bottom: 8px; line-height: 1.5; }
  }

  .positive { color: #67c23a; }
  .negative { color: #f56c6c; }
  .warning { color: #e6a23c; }
}
</style>

