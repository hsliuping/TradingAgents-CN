<template>
  <el-dialog
    v-model="visible"
    :title="`复盘详情 - ${report?.trade_info?.code || ''}`"
    width="900px"
    :close-on-click-modal="false"
  >
    <div v-loading="loading" class="review-detail">
      <!-- 🔄 进度显示界面（任务进行中） -->
      <template v-if="report && (report.status === 'pending' || report.status === 'processing')">
        <div class="progress-container">
          <!-- 顶部状态卡片 -->
          <div class="status-card">
            <div class="status-icon">
              <el-icon class="rotating" :size="48" color="#409EFF"><Loading /></el-icon>
            </div>
            <div class="status-content">
              <h2 class="status-title">正在分析交易复盘</h2>
              <div class="stock-info">
                <span class="stock-code">{{ report.trade_info?.code || '000000' }}</span>
                <span class="stock-name">{{ report.trade_info?.name || '加载中...' }}</span>
              </div>
              <el-tag
                :type="report.status === 'processing' ? 'primary' : 'info'"
                size="large"
                effect="light"
              >
                {{ report.status === 'processing' ? '🔄 分析中' : '⏳ 等待中' }}
              </el-tag>
            </div>
          </div>

          <!-- 分析步骤说明 -->
          <div class="analysis-steps">
            <div class="steps-title">
              <el-icon><InfoFilled /></el-icon>
              <span>AI 正在从多个维度分析您的交易</span>
            </div>
            <div class="steps-grid">
              <div class="step-item">
                <div class="step-icon">📊</div>
                <div class="step-text">市场环境分析</div>
              </div>
              <div class="step-item">
                <div class="step-icon">⏰</div>
                <div class="step-text">买卖时机评估</div>
              </div>
              <div class="step-item">
                <div class="step-icon">💰</div>
                <div class="step-text">仓位管理评分</div>
              </div>
              <div class="step-item">
                <div class="step-icon">🧠</div>
                <div class="step-text">交易心理分析</div>
              </div>
              <div class="step-item">
                <div class="step-icon">📈</div>
                <div class="step-text">收益归因分析</div>
              </div>
            </div>
          </div>

          <!-- 预计时间提示 -->
          <div class="time-estimate">
            <el-icon><Clock /></el-icon>
            <span>预计需要 2-5 分钟，请耐心等待...</span>
          </div>

          <!-- 底部操作按钮 -->
          <div class="progress-actions">
            <el-button size="large" @click="visible = false">关闭</el-button>
            <el-button size="large" type="primary" @click="loadReport" :loading="loading">
              刷新状态
            </el-button>
          </div>
        </div>
      </template>

      <!-- ✅ 完整结果显示界面（任务完成） -->
      <template v-else-if="report && report.status === 'completed'">
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

          <!-- 交易计划执行情况 -->
          <el-row :gutter="16" class="plan-execution-row" v-if="report.ai_review?.plan_adherence || report.ai_review?.plan_deviation">
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

      <!-- ❌ 失败状态显示界面 -->
      <template v-else-if="report && report.status === 'failed'">
        <div class="error-container">
          <el-result
            icon="error"
            title="分析失败"
            :sub-title="report.error_message || '未知错误'"
          >
            <template #extra>
              <el-button type="primary" @click="visible = false">关闭</el-button>
            </template>
          </el-result>
        </div>
      </template>

      <!-- ⚠️ 无数据状态 -->
      <template v-else-if="!report && !loading">
        <el-empty description="暂无数据" />
      </template>
    </div>

    <template #footer>
      <span v-if="report && report.status === 'completed'">
        <el-button @click="visible = false">关闭</el-button>
        <el-button v-if="!report.is_case_study" type="primary" @click="showSaveCaseDialog">
          保存到案例库
        </el-button>
      </span>
    </template>
  </el-dialog>

  <!-- 保存为案例对话框 -->
  <SaveAsCaseDialog
    v-model="saveCaseDialogVisible"
    :review-id="props.reviewId"
    :stock-code="report?.trade_info?.code"
    :source="report?.source"
    @success="handleSaveCaseSuccess"
  />
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { CircleCheck, Warning, Pointer, Document, Loading, InfoFilled, Clock } from '@element-plus/icons-vue'
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

      // 🔄 如果状态是 pending 或 processing，启动轮询
      if (report.value && (report.value.status === 'pending' || report.value.status === 'processing')) {
        console.log('🔄 [复盘详情] 任务进行中，启动轮询...')
        startPolling()
      }
    }
  } catch (e: any) {
    // 如果是 404 错误，可能是任务还在创建中，尝试轮询
    if (e.message?.includes('404') || e.message?.includes('不存在')) {
      console.log('🔄 [复盘详情] 数据未找到，可能任务还在创建中，启动轮询...')
      ElMessage.info('复盘任务正在执行中，请稍候...')
      startPolling()
    } else {
      ElMessage.error(e.message || '加载复盘详情失败')
    }
  } finally {
    loading.value = false
  }
}

// 轮询相关
let pollingTimer: number | null = null
const POLLING_INTERVAL = 10000 // 轮询间隔：10秒
const maxPollingAttempts = 60 // 最多轮询60次（10分钟）
let pollingAttempts = 0

const startPolling = () => {
  // 清除之前的定时器
  if (pollingTimer) {
    clearInterval(pollingTimer)
  }

  pollingAttempts = 0

  pollingTimer = window.setInterval(async () => {
    pollingAttempts++

    console.log(`🔄 [复盘详情] 轮询第 ${pollingAttempts} 次...`)

    try {
      const res = await reviewApi.getReviewDetail(props.reviewId)
      if (res.success && res.data) {
        report.value = res.data

        // 如果任务完成或失败，停止轮询
        if (res.data.status === 'completed' || res.data.status === 'failed') {
          console.log(`✅ [复盘详情] 任务${res.data.status === 'completed' ? '完成' : '失败'}，停止轮询`)
          stopPolling()

          if (res.data.status === 'completed') {
            ElMessage.success('复盘完成')
          } else {
            ElMessage.error(res.data.error_message || '复盘失败')
          }
        }
      }
    } catch (e) {
      console.log('🔄 [复盘详情] 轮询失败，继续等待...')
    }

    // 超过最大轮询次数，停止轮询
    if (pollingAttempts >= maxPollingAttempts) {
      console.log('⏱️ [复盘详情] 轮询超时，停止轮询')
      stopPolling()
      ElMessage.warning('复盘任务执行时间较长，请稍后刷新查看')
    }
  }, POLLING_INTERVAL) // 每10秒轮询一次
}

const stopPolling = () => {
  if (pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = null
  }
  pollingAttempts = 0
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
  } else if (!show) {
    // 对话框关闭时，停止轮询
    stopPolling()
  }
}, { immediate: true })
</script>

<style scoped lang="scss">
.review-detail {
  // 🔄 进度显示界面样式
  .progress-container {
    padding: 32px 24px;

    // 顶部状态卡片
    .status-card {
      display: flex;
      align-items: center;
      gap: 24px;
      padding: 32px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      border-radius: 12px;
      margin-bottom: 32px;
      color: white;

      .status-icon {
        .rotating {
          animation: rotate 2s linear infinite;
          filter: drop-shadow(0 2px 8px rgba(255, 255, 255, 0.3));
        }
      }

      .status-content {
        flex: 1;
        text-align: left;

        .status-title {
          margin: 0 0 12px 0;
          font-size: 24px;
          font-weight: 600;
          color: white;
        }

        .stock-info {
          display: flex;
          align-items: center;
          gap: 12px;
          margin-bottom: 16px;

          .stock-code {
            font-size: 18px;
            font-weight: 600;
            color: white;
            background: rgba(255, 255, 255, 0.2);
            padding: 4px 12px;
            border-radius: 6px;
          }

          .stock-name {
            font-size: 16px;
            color: rgba(255, 255, 255, 0.9);
          }
        }

        :deep(.el-tag) {
          background: rgba(255, 255, 255, 0.2);
          border-color: rgba(255, 255, 255, 0.3);
          color: white;
          font-size: 14px;
          padding: 8px 16px;
          height: auto;
        }
      }
    }

    // 分析步骤说明
    .analysis-steps {
      margin-bottom: 32px;

      .steps-title {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 20px;
        font-size: 15px;
        color: #606266;
        justify-content: center;

        .el-icon {
          color: #409EFF;
        }
      }

      .steps-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        gap: 16px;

        .step-item {
          padding: 20px 16px;
          background: #f5f7fa;
          border-radius: 8px;
          text-align: center;
          transition: all 0.3s ease;

          &:hover {
            background: #ecf5ff;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(64, 158, 255, 0.1);
          }

          .step-icon {
            font-size: 32px;
            margin-bottom: 8px;
          }

          .step-text {
            font-size: 13px;
            color: #606266;
            line-height: 1.4;
          }
        }
      }
    }

    // 预计时间提示
    .time-estimate {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 16px;
      background: #fff7e6;
      border: 1px solid #ffe7ba;
      border-radius: 8px;
      margin-bottom: 32px;
      color: #e6a23c;
      font-size: 14px;

      .el-icon {
        font-size: 18px;
      }
    }

    // 底部操作按钮
    .progress-actions {
      display: flex;
      justify-content: center;
      gap: 12px;
    }
  }

  // ❌ 错误显示界面样式
  .error-container {
    padding: 20px;
  }

  @keyframes rotate {
    from {
      transform: rotate(0deg);
    }
    to {
      transform: rotate(360deg);
    }
  }

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
      margin-bottom: 16px;

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

    .plan-execution-row {
      margin-top: 0;
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

