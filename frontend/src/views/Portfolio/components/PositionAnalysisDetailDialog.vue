<template>
  <el-dialog
    v-model="visible"
    title="研究报告详情"
    width="900px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <div v-if="report" class="analysis-detail">
      <!-- 风险提示 -->
      <div class="risk-disclaimer">
        <el-alert
          type="warning"
          :closable="false"
          show-icon
        >
          <template #title>
            <span style="font-size: 14px;">
              <strong>⚠️ 重要提示：</strong>本报告仅用于学习、研究和持仓风险识别，不提供交易指导。
            </span>
          </template>
        </el-alert>
      </div>

      <!-- 持仓快照 -->
      <div class="section">
        <h3>📊 持仓快照</h3>
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="股票代码">{{ report.position_snapshot?.code || '-' }}</el-descriptions-item>
          <el-descriptions-item label="股票名称">{{ report.position_snapshot?.name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="持仓数量">{{ report.position_snapshot?.quantity || 0 }} 股</el-descriptions-item>
          <el-descriptions-item label="成本价">¥{{ (report.position_snapshot?.cost_price || 0).toFixed(2) }}</el-descriptions-item>
          <el-descriptions-item label="当前价">¥{{ (report.position_snapshot?.current_price || 0).toFixed(2) }}</el-descriptions-item>
          <el-descriptions-item label="持仓市值">¥{{ (report.position_snapshot?.market_value || 0).toFixed(2) }}</el-descriptions-item>
          <el-descriptions-item label="浮动盈亏">
            <span :class="pnlClass(report.position_snapshot?.unrealized_pnl || 0)">
              {{ formatPnl(report.position_snapshot?.unrealized_pnl || 0) }}
              ({{ formatPct(report.position_snapshot?.unrealized_pnl_pct || 0) }})
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="所属行业">{{ report.position_snapshot?.industry || '未知' }}</el-descriptions-item>
        </el-descriptions>
      </div>

      <!-- 研究观察 -->
      <div class="section">
        <h3>💡 当前结论</h3>
        <div class="summary-panel">
          <p class="summary-conclusion">{{ view.conclusion || report.action_reason || '暂无' }}</p>
          <p v-if="view.position_context" class="summary-context">{{ view.position_context }}</p>
        </div>

        <div class="section-grid">
          <div class="info-card">
            <h4>核心依据</h4>
            <ul>
              <li v-for="item in view.key_points" :key="`detail-point-${item}`">{{ item }}</li>
            </ul>
          </div>
          <div class="info-card">
            <h4>风险提示</h4>
            <ul>
              <li v-for="item in view.risk_focus" :key="`detail-risk-${item}`">{{ item }}</li>
            </ul>
          </div>
          <div class="info-card">
            <h4>后续观察点</h4>
            <ul>
              <li v-for="item in view.watch_items" :key="`detail-watch-${item}`">{{ item }}</li>
            </ul>
          </div>
        </div>

        <div class="uncertainty-box" v-if="view.uncertainty_note">
          <h4>不确定性说明</h4>
          <p>{{ view.uncertainty_note }}</p>
        </div>
      </div>

      <!-- 详细分析 -->
      <div class="section" v-if="appendixSections.length > 0 || report.detailed_analysis">
        <h3>📝 研究附录</h3>
        <template v-if="appendixSections.length > 0">
          <div
            v-for="section in appendixSections"
            :key="`detail-appendix-${section.key}`"
            class="appendix-section"
          >
            <h4>{{ section.title }}</h4>
            <div class="markdown-content" v-html="renderMarkdown(section.content)"></div>
          </div>
        </template>
        <div v-else class="markdown-content" v-html="renderMarkdown(report.detailed_analysis)"></div>
      </div>

      <!-- 分析时间 -->
      <div class="section">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="分析时间">{{ formatTime(report.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="执行时长">{{ report.execution_time || 0 }} 秒</el-descriptions-item>
        </el-descriptions>
      </div>
    </div>

    <template #footer>
      <el-button @click="handleClose">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { type PositionAnalysisResult } from '@/api/portfolio'
import { marked } from 'marked'

// 配置marked选项
marked.setOptions({ breaks: true, gfm: true })

const props = defineProps<{
  modelValue: boolean
  report: PositionAnalysisResult | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()

const visible = ref(false)

const view = computed(() => props.report?.user_view || {
  conclusion: props.report?.action_reason || '',
  position_context: '',
  key_points: [],
  risk_focus: [],
  watch_items: [],
  uncertainty_note: ''
})

const appendixSections = computed(() =>
  (props.report?.appendix_sections || []).filter(section => section?.content)
)

watch(() => props.modelValue, (val) => {
  visible.value = val
})

watch(visible, (val) => emit('update:modelValue', val))

const handleClose = () => emit('update:modelValue', false)

// Markdown渲染
const renderMarkdown = (content: string) => {
  if (!content) return ''
  try {
    return marked.parse(content) as string
  } catch (e) {
    return `<pre style="white-space: pre-wrap; font-family: inherit;">${content}</pre>`
  }
}

// 格式化时间
const formatTime = (time: string) => {
  if (!time) return '-'
  const date = new Date(time)
  return date.toLocaleString('zh-CN')
}

// 格式化盈亏
const formatPnl = (pnl: number) => {
  if (pnl === undefined || pnl === null) return '¥0.00'
  const prefix = pnl >= 0 ? '+' : ''
  return `${prefix}¥${Math.abs(pnl).toFixed(2)}`
}

// 格式化百分比
const formatPct = (pct: number) => {
  if (pct === undefined || pct === null) return '0.00%'
  const prefix = pct >= 0 ? '+' : ''
  return `${prefix}${pct.toFixed(2)}%`
}

// 盈亏样式
const pnlClass = (pnl: number) => {
  if (pnl > 0) return 'text-success'
  if (pnl < 0) return 'text-danger'
  return ''
}

</script>

<style scoped>
.analysis-detail {
  max-height: 70vh;
  overflow-y: auto;
}

.section {
  margin-bottom: 24px;
}

.section h3 {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
  color: #303133;
}

.section h4 {
  font-size: 14px;
  font-weight: 500;
  margin: 12px 0 8px 0;
  color: #606266;
}

.text-success {
  color: #67c23a;
}

.text-danger {
  color: #f56c6c;
}

.summary-panel {
  padding: 18px;
  border-radius: 14px;
  background: linear-gradient(135deg, #f8fafc 0%, #eef4ff 100%);
  border: 1px solid #dbe7ff;
}

.summary-conclusion,
.summary-context {
  margin: 0;
  line-height: 1.8;
  color: #334155;
}

.summary-conclusion {
  font-size: 15px;
  font-weight: 600;
  color: #1f2937;
}

.summary-context {
  margin-top: 10px;
}

.section-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin-top: 16px;
}

.info-card {
  padding: 16px;
  border-radius: 14px;
  background: #f8fafc;
  border: 1px solid #e5edf6;
}

.info-card h4,
.uncertainty-box h4 {
  margin: 0 0 10px 0;
  font-size: 14px;
  color: #1f2937;
}

.info-card ul {
  margin: 0;
  padding-left: 18px;
  color: #475569;
  line-height: 1.8;
}

.uncertainty-box {
  margin-top: 16px;
  padding: 16px;
  border-radius: 14px;
  background: #fff7ed;
  border: 1px solid #fed7aa;
}

.uncertainty-box p {
  margin: 0;
  line-height: 1.8;
  color: #7c2d12;
}

@media (max-width: 900px) {
  .section-grid {
    grid-template-columns: 1fr;
  }
}

.target-card {
  padding: 16px;
  border-radius: 8px;
  text-align: center;
}

.target-card .label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 8px;
}

.target-card .value {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 4px;
}

.target-card .pct {
  font-size: 14px;
}

.loss-bg {
  background: #fef0f0;
  color: #f56c6c;
}

.neutral-bg {
  background: #f4f4f5;
  color: #909399;
}

.profit-bg {
  background: #f0f9ff;
  color: #67c23a;
}

.markdown-content {
  line-height: 1.8;
}

.appendix-section {
  padding: 10px 0;
  border-bottom: 1px solid #ebeef5;
}

.appendix-section:last-child {
  padding-bottom: 0;
  border-bottom: none;
}

.appendix-section h4 {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3),
.markdown-content :deep(h4) {
  margin-top: 16px;
  margin-bottom: 8px;
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  padding-left: 24px;
}

.markdown-content :deep(li) {
  margin: 4px 0;
}

.markdown-content :deep(p) {
  margin: 8px 0;
}

.markdown-content :deep(code) {
  background: #f5f7fa;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Courier New', monospace;
}

.markdown-content :deep(pre) {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  overflow-x: auto;
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

