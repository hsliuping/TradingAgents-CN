<template>
  <el-dialog
    v-model="visible"
    title="阶段性复盘详情"
    width="800px"
    :close-on-click-modal="false"
  >
    <div v-loading="loading" class="periodic-detail">
      <template v-if="detail">
        <!-- 基本信息 -->
        <el-descriptions :column="3" border class="info-section">
          <el-descriptions-item label="复盘周期">
            {{ getPeriodTypeLabel(detail.period_type) }}
          </el-descriptions-item>
          <el-descriptions-item label="开始日期">
            {{ formatDate(detail.period_start) }}
          </el-descriptions-item>
          <el-descriptions-item label="结束日期">
            {{ formatDate(detail.period_end) }}
          </el-descriptions-item>
        </el-descriptions>

        <!-- 统计数据 -->
        <el-card shadow="never" class="stats-section">
          <template #header>
            <span>交易统计</span>
          </template>
          <el-row :gutter="16">
            <el-col :span="4">
              <div class="stat-item">
                <div class="label">总交易数</div>
                <div class="value">{{ detail.statistics?.total_trades || 0 }}</div>
              </div>
            </el-col>
            <el-col :span="4">
              <div class="stat-item">
                <div class="label">胜率</div>
                <div class="value" :class="(detail.statistics?.win_rate || 0) >= 50 ? 'positive' : 'negative'">
                  {{ detail.statistics?.win_rate?.toFixed(1) || 0 }}%
                </div>
              </div>
            </el-col>
            <el-col :span="4">
              <div class="stat-item">
                <div class="label">盈亏比</div>
                <div class="value">{{ detail.statistics?.profit_loss_ratio?.toFixed(2) || '-' }}</div>
              </div>
            </el-col>
            <el-col :span="4">
              <div class="stat-item">
                <div class="label">总盈亏</div>
                <div class="value" :class="(detail.statistics?.total_pnl || 0) >= 0 ? 'positive' : 'negative'">
                  {{ formatPnl(detail.statistics?.total_pnl) }}
                </div>
              </div>
            </el-col>
            <el-col :span="4">
              <div class="stat-item">
                <div class="label">平均盈利</div>
                <div class="value positive">{{ formatPnl(detail.statistics?.avg_profit) }}</div>
              </div>
            </el-col>
            <el-col :span="4">
              <div class="stat-item">
                <div class="label">平均亏损</div>
                <div class="value negative">{{ formatPnl(detail.statistics?.avg_loss) }}</div>
              </div>
            </el-col>
          </el-row>
        </el-card>

        <!-- AI分析 -->
        <el-card shadow="never" class="ai-section">
          <template #header>
            <div class="ai-header">
              <span>AI分析报告</span>
              <el-tag :type="getScoreType(detail.ai_review?.overall_score || 0)" size="large">
                {{ detail.ai_review?.overall_score || 0 }}分
              </el-tag>
            </div>
          </template>
          
          <div class="ai-content">
            <div class="summary">{{ detail.ai_review?.summary }}</div>
            
            <el-divider />
            
            <div class="analysis-item" v-if="detail.ai_review?.trading_style">
              <div class="item-title">交易风格</div>
              <div class="item-content">{{ detail.ai_review.trading_style }}</div>
            </div>
            
            <div class="analysis-item" v-if="detail.ai_review?.common_mistakes?.length">
              <div class="item-title">常见错误</div>
              <ul>
                <li v-for="(item, idx) in detail.ai_review.common_mistakes" :key="idx">{{ item }}</li>
              </ul>
            </div>
            
            <div class="analysis-item" v-if="detail.ai_review?.improvement_areas?.length">
              <div class="item-title">改进方向</div>
              <ul>
                <li v-for="(item, idx) in detail.ai_review.improvement_areas" :key="idx">{{ item }}</li>
              </ul>
            </div>
            
            <div class="analysis-item" v-if="detail.ai_review?.action_plan?.length">
              <div class="item-title">行动计划</div>
              <ul>
                <li v-for="(item, idx) in detail.ai_review.action_plan" :key="idx">{{ item }}</li>
              </ul>
            </div>
            
            <el-row :gutter="16" v-if="detail.ai_review?.best_trade || detail.ai_review?.worst_trade">
              <el-col :span="12" v-if="detail.ai_review?.best_trade">
                <div class="trade-analysis best">
                  <div class="trade-title">最佳交易</div>
                  <div class="trade-content">{{ detail.ai_review.best_trade }}</div>
                </div>
              </el-col>
              <el-col :span="12" v-if="detail.ai_review?.worst_trade">
                <div class="trade-analysis worst">
                  <div class="trade-title">最差交易</div>
                  <div class="trade-content">{{ detail.ai_review.worst_trade }}</div>
                </div>
              </el-col>
            </el-row>
          </div>
        </el-card>
      </template>
    </div>
    
    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { reviewApi, type PeriodicReviewReport, type PeriodType } from '@/api/review'

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
const detail = ref<PeriodicReviewReport | null>(null)

const getPeriodTypeLabel = (type: PeriodType) => {
  const map: Record<string, string> = {
    week: '周度',
    month: '月度',
    quarter: '季度',
    year: '年度'
  }
  return map[type] || type
}

const formatDate = (dateStr?: string) => {
  if (!dateStr) return '-'
  return dateStr.split('T')[0]
}

const formatPnl = (value?: number) => {
  if (value === undefined || value === null) return '-'
  const prefix = value >= 0 ? '+' : ''
  return prefix + value.toFixed(2)
}

const getScoreType = (score: number) => {
  if (score >= 80) return 'success'
  if (score >= 60) return 'warning'
  return 'danger'
}

const loadDetail = async () => {
  if (!props.reviewId) return
  
  try {
    loading.value = true
    const res = await reviewApi.getPeriodicReviewDetail(props.reviewId)
    if (res.success) {
      detail.value = res.data
    }
  } catch (e) {
    console.error('加载阶段性复盘详情失败:', e)
  } finally {
    loading.value = false
  }
}

watch(() => props.reviewId, (val) => {
  if (val && visible.value) {
    loadDetail()
  }
})

watch(visible, (val) => {
  if (val && props.reviewId) {
    loadDetail()
  } else if (!val) {
    detail.value = null
  }
})
</script>

<style scoped lang="scss">
.periodic-detail {
  .info-section {
    margin-bottom: 16px;
  }

  .stats-section {
    margin-bottom: 16px;

    .stat-item {
      text-align: center;

      .label {
        font-size: 12px;
        color: #909399;
        margin-bottom: 4px;
      }

      .value {
        font-size: 18px;
        font-weight: 600;

        &.positive { color: #f56c6c; }  // 中国习惯：红色表示盈利（正数）
        &.negative { color: #67c23a; }  // 中国习惯：绿色表示亏损（负数）
      }
    }
  }

  .ai-section {
    .ai-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .ai-content {
      .summary {
        font-size: 14px;
        line-height: 1.6;
        color: #303133;
      }

      .analysis-item {
        margin-bottom: 16px;

        .item-title {
          font-weight: 600;
          margin-bottom: 8px;
          color: #303133;
        }

        .item-content {
          color: #606266;
          line-height: 1.6;
        }

        ul {
          margin: 0;
          padding-left: 20px;

          li {
            margin-bottom: 4px;
            color: #606266;
          }
        }
      }

      .trade-analysis {
        padding: 12px;
        border-radius: 4px;

        &.best {
          background: #f0f9eb;
          border: 1px solid #e1f3d8;
        }

        &.worst {
          background: #fef0f0;
          border: 1px solid #fde2e2;
        }

        .trade-title {
          font-weight: 600;
          margin-bottom: 8px;
        }

        .trade-content {
          font-size: 13px;
          line-height: 1.5;
        }
      }
    }
  }
}
</style>

