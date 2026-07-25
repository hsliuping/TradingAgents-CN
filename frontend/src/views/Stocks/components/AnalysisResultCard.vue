<template>
  <div class="card analysis-result-card" id="analysis-result-section">
    <div class="card-header">
      <div class="section-title">
        <span>📋</span>
        <span>单股分析结果</span>
        <span class="badge">深度研究</span>
      </div>
      <div class="header-right">
        <span v-if="lastTaskInfo?.end_time" class="header-meta">
          {{ formatAnalysisTime(lastTaskInfo.end_time) }} 完成
        </span>
        <button class="history-btn" @click="$emit('viewHistory')">
          📜 历史记录
          <span v-if="(historyCount ?? 0) > 0" class="history-count">{{ historyCount }}</span>
        </button>
      </div>
    </div>

    <div class="card-body">
      <!-- 运行中状态 -->
      <div v-if="analysisStatus === 'running'" class="running-state">
        <el-progress :percentage="analysisProgress" :text-inside="true" :stroke-width="20" style="width:100%" />
        <div class="hint">{{ analysisMessage || '正在生成分析报告…' }}</div>
      </div>

      <!-- 空状态 -->
      <div v-else-if="!lastAnalysis" class="empty-state">
        <el-empty description="暂无单股分析结果">
          <el-button type="primary" @click="$emit('analyze')">发起单股分析</el-button>
        </el-empty>
      </div>

      <!-- 有结果 -->
      <div v-else class="analysis-detail">
        <!-- 研究结论 -->
        <div class="analysis-result-summary">
          <div class="label">研究结论</div>
          <div class="conclusion markdown-body" v-html="renderMarkdown(oneSentenceConclusion)"></div>
        </div>

        <!-- 分析元信息（合规：不展示信心度，仅保留研究性元数据） -->
        <div class="analysis-meta">
          <div class="analysis-meta-item">
            <div class="label">分析时间</div>
            <div class="value">{{ formatAnalysisTime(lastTaskInfo?.end_time) }}</div>
          </div>
          <div class="analysis-meta-item" v-if="reportKeys.length">
            <div class="label">报告数</div>
            <div class="value">{{ reportKeys.length }}</div>
          </div>
          <button
            v-if="hasDetailContent"
            class="collapse-toggle"
            :class="{ collapsed: !detailExpanded }"
            @click="detailExpanded = !detailExpanded"
          >
            {{ detailExpanded ? '收起详情' : '展开详情' }}
            <span class="arrow">▼</span>
          </button>
        </div>

        <!-- 报告列表预览 -->
        <div v-if="reportKeys.length" class="reports-preview">
          <el-tag
            v-for="key in reportKeys"
            :key="key"
            size="small"
            effect="plain"
            class="report-tag"
            @click="$emit('openReport', key)"
          >
            {{ formatReportName(key) }}
          </el-tag>
          <el-button
            type="primary"
            plain
            size="small"
            @click="$emit('viewReports')"
          >
            查看完整报告
          </el-button>
        </div>

        <!-- 详细报告内容（可折叠） -->
        <div v-if="hasDetailContent" class="collapsible" :class="{ collapsed: !detailExpanded }">
          <div class="analysis-sections">
            <div
              v-for="key in detailReportKeys"
              :key="key"
              class="analysis-section"
              :class="getSectionClass(key)"
            >
              <div class="analysis-section-title">
                <span>{{ getSectionIcon(key) }}</span>
                {{ formatReportName(key) }}
              </div>
              <div
                class="analysis-section-content markdown-body"
                v-html="renderMarkdown(getReportContent(lastAnalysis?.reports?.[key]))"
              ></div>
            </div>
          </div>
        </div>

        <div class="disclaimer">
          本分析由 AI 多智能体系统基于公开信息生成，仅供研究参考，不构成任何交易建议。
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { renderMarkdown } from '@/utils/markdown'
import { getReportName } from '@/utils/reportPresentation'

const props = defineProps<{
  analysisStatus: 'idle' | 'running' | 'completed' | 'failed'
  analysisProgress: number
  analysisMessage: string
  lastAnalysis: any
  lastTaskInfo: any
  oneSentenceConclusion: string
  reportKeys: string[]
  historyCount?: number
}>()

defineEmits<{
  (e: 'analyze'): void
  (e: 'viewReports'): void
  (e: 'openReport', key: string): void
  (e: 'viewHistory'): void
}>()

const detailExpanded = ref(false)

// 详细报告中需要展示的子报告 key（不含 trader_investment_plan，因为已在结论中展示）
const DETAIL_REPORT_KEYS = [
  'market_analysis',
  'fundamentals_analysis',
  'news_analysis',
  'risk_assessment',
  'social_sentiment',
  'trader_investment_plan',
]

const detailReportKeys = computed(() => {
  if (!props.reportKeys.length) return []
  return DETAIL_REPORT_KEYS.filter(k => props.reportKeys.includes(k))
})

const hasDetailContent = computed(() => detailReportKeys.value.length > 0)

function formatAnalysisTime(dateStr: any): string {
  if (!dateStr) return '-'
  try {
    const d = new Date(dateStr)
    if (isNaN(d.getTime())) return String(dateStr)
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  } catch {
    return String(dateStr)
  }
}

// fmtConf 已移除：合规要求不展示信心度/操作建议

function formatReportName(key: string): string {
  return getReportName(key) || key
}

function getReportContent(reportData: any): string {
  if (!reportData) return ''
  if (typeof reportData === 'string') return reportData
  if (typeof reportData === 'object') {
    return reportData.content || reportData.report || reportData.text || reportData.summary || ''
  }
  return ''
}

function getSectionClass(key: string): string {
  if (key === 'risk_assessment') return 'danger'
  if (key === 'news_analysis') return 'warning'
  return ''
}

function getSectionIcon(key: string): string {
  const icons: Record<string, string> = {
    market_analysis: '📈',
    fundamentals_analysis: '💰',
    news_analysis: '📰',
    risk_assessment: '⚠️',
    social_sentiment: '💬',
    trader_investment_plan: '🎯',
  }
  return icons[key] || '📄'
}
</script>

<style scoped>
.card {
  background: var(--el-bg-color, #fff);
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  border: 1px solid #f1f5f9;
  overflow: hidden;
}

.card-header {
  padding: 14px 20px;
  border-bottom: 1px solid #f1f5f9;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.section-title {
  font-size: 15px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 8px;
  color: #1e293b;
}

.badge {
  padding: 2px 8px;
  background: #f5f3ff;
  color: #6b5ce7;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-meta {
  font-size: 12px;
  color: #94a3b8;
}

.history-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: var(--el-bg-color, #fff);
  color: #64748b;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
  font-family: inherit;
}

.history-btn:hover {
  border-color: #6b5ce7;
  color: #6b5ce7;
  background: #f5f3ff;
}

.history-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  background: #6b5ce7;
  color: #fff;
  border-radius: 8px;
  font-size: 10px;
  font-weight: 700;
}

.card-body {
  padding: 16px 20px;
}

.running-state {
  padding: 20px 0;
}

.hint {
  margin-top: 10px;
  font-size: 13px;
  color: #64748b;
  text-align: center;
}

.empty-state {
  padding: 20px 0;
}

.analysis-result-summary {
  padding: 14px;
  background: linear-gradient(135deg, #f5f3ff 0%, #ede9fe 100%);
  border-radius: 8px;
  border-left: 3px solid #6b5ce7;
  margin-bottom: 14px;
}

.analysis-result-summary .label {
  font-size: 11px;
  color: #6b5ce7;
  font-weight: 700;
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.analysis-result-summary .conclusion {
  font-size: 14px;
  color: #1e293b;
  line-height: 1.7;
}

.analysis-meta {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  align-items: center;
  margin-bottom: 14px;
  padding: 10px 14px;
  background: #f8fafc;
  border-radius: 8px;
}

.analysis-meta-item .label {
  font-size: 11px;
  color: #94a3b8;
}

.analysis-meta-item .value {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}

.collapse-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #6b5ce7;
  cursor: pointer;
  font-weight: 600;
  padding: 4px 8px;
  border-radius: 4px;
  transition: background 0.2s;
  margin-left: auto;
  border: none;
  background: none;
  font-family: inherit;
}

.collapse-toggle:hover {
  background: #f5f3ff;
}

.collapse-toggle .arrow {
  transition: transform 0.2s;
  font-size: 10px;
}

.collapse-toggle.collapsed .arrow {
  transform: rotate(-90deg);
}

.reports-preview {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
  margin-bottom: 14px;
}

.report-tag {
  cursor: pointer;
}

.collapsible {
  overflow: hidden;
  transition: max-height 0.4s ease, margin 0.4s ease;
  max-height: 2000px;
}

.collapsible.collapsed {
  max-height: 0 !important;
  margin: 0 !important;
}

.analysis-sections {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 14px;
}

.analysis-section {
  padding: 12px;
  background: #f8fafc;
  border-radius: 8px;
  border-left: 3px solid #3b82f6;
}

.analysis-section.warning {
  border-left-color: #f59e0b;
}

.analysis-section.danger {
  border-left-color: #ef4444;
}

.analysis-section-title {
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 6px;
  color: #1e293b;
}

.analysis-section-content {
  font-size: 12px;
  color: #64748b;
  line-height: 1.7;
}

.disclaimer {
  margin-top: 12px;
  padding: 8px 12px;
  background: #f1f5f9;
  border-radius: 6px;
  font-size: 11px;
  color: #94a3b8;
}

@media (max-width: 1024px) {
  .analysis-sections {
    grid-template-columns: 1fr;
  }
}
</style>
