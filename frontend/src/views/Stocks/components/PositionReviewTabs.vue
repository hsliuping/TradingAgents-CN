<template>
  <div class="card tabs-card" id="position-review-section">
    <div class="tabs">
      <div
        class="tab"
        :class="{ active: activeTab === 'position' }"
        @click="activeTab = 'position'"
      >
        <span>💼</span>
        <span>持仓分析</span>
        <span v-if="positionSummary.has" class="tab-badge" :class="positionBadgeClass">
          {{ positionBadgeText }}
        </span>
      </div>
      <div
        class="tab"
        :class="{ active: activeTab === 'review' }"
        @click="activeTab = 'review'"
      >
        <span>📈</span>
        <span>交易复盘</span>
        <span v-if="reviewSummary.has" class="tab-badge" :class="reviewBadgeClass">
          {{ reviewBadgeText }}
        </span>
      </div>
      <div class="tab-actions">
        <!-- 持仓历史按钮 -->
        <button
          v-show="activeTab === 'position'"
          class="history-btn"
          @click="$emit('viewPositionHistory')"
        >
          📜 持仓历史
          <span v-if="(positionHistoryCount ?? 0) > 0" class="history-count">{{ positionHistoryCount }}</span>
        </button>
        <!-- 复盘历史下拉 -->
        <el-select
          v-show="activeTab === 'review' && reviewHistory.items.length > 1"
          :model-value="reviewHistory.selectedIndex"
          size="small"
          placeholder="选择历史复盘"
          style="width: 160px"
          @change="(idx: number) => $emit('selectReviewItem', idx)"
        >
          <el-option
            v-for="(item, idx) in reviewHistory.items"
            :key="item.review_id || item.task_id || idx"
            :label="formatAnalysisTime(item.completed_at || item.created_at)"
            :value="idx"
          />
        </el-select>
        <button
          v-show="activeTab === 'review'"
          class="history-btn"
          @click="$emit('viewReviewHistory')"
        >
          📜 复盘历史
          <span v-if="reviewHistory.total > 0" class="history-count">{{ reviewHistory.total }}</span>
        </button>
      </div>
    </div>

    <!-- 持仓分析内容 -->
    <div class="tab-content" :class="{ active: activeTab === 'position' }">
      <div v-if="!positionSummary.has && !positionData.real.has && !positionData.paper.has" class="empty-state">
        <el-empty description="暂无持仓分析记录">
          <el-button type="primary" @click="$emit('goPositionAnalysis')">发起持仓分析</el-button>
        </el-empty>
      </div>
      <div v-else>
        <!-- 持仓快照摘要 -->
        <div v-if="positionSummary.snapshot" class="summary-row">
          <div class="summary-item">
            <div class="label">成本价</div>
            <div class="value">¥{{ fmtPrice(positionSummary.snapshot.cost_price) }}</div>
          </div>
          <div class="summary-item">
            <div class="label">现价</div>
            <div class="value">¥{{ fmtPrice(positionSummary.snapshot.current_price) }}</div>
          </div>
          <div class="summary-item">
            <div class="label">浮动盈亏</div>
            <div class="value" :class="pnlClass(positionSummary.snapshot.unrealized_pnl)">
              {{ formatPnl(positionSummary.snapshot.unrealized_pnl, positionSummary.snapshot.unrealized_pnl_pct) }}
            </div>
          </div>
          <div class="summary-item">
            <div class="label">持有天数</div>
            <div class="value">{{ positionSummary.snapshot.holding_days || '-' }} 天</div>
          </div>
          <div class="summary-item">
            <div class="label">仓位占比</div>
            <div class="value">{{ formatPercent(positionSummary.snapshot.position_pct) }}</div>
          </div>
        </div>

        <!-- 研究结论（合规：不展示操作建议/信心度，仅保留研究性结论） -->
        <div v-if="positionSummary.conclusion || positionSummary.keyPoints?.length" class="ai-advice">
          <div class="advice-label">研究结论</div>
          <div v-if="positionSummary.conclusion" class="advice-conclusion">
            <el-icon class="advice-icon"><InfoFilled /></el-icon>
            <span>{{ positionSummary.conclusion }}</span>
          </div>
          <div v-if="positionSummary.keyPoints?.length" class="advice-keypoints">
            <div class="keypoints-title">⚠ 关键风险点</div>
            <ul class="keypoints-list">
              <li v-for="(point, idx) in positionSummary.keyPoints.slice(0, 3)" :key="idx">{{ point }}</li>
            </ul>
          </div>
          <div v-if="positionSummary.completedAt" class="advice-time">
            分析时间：{{ formatAnalysisTime(positionSummary.completedAt) }}
            <span v-if="positionRelativeTime" class="relative-time">{{ positionRelativeTime }}</span>
            <button
              v-if="positionStale"
              class="stale-btn"
              @click="$emit('goPositionAnalysis')"
            >
              🔄 数据已过期，重新分析
            </button>
          </div>
        </div>

        <!-- 实盘/模拟持仓信息 -->
        <div v-if="positionData.real.has || positionData.paper.has" class="position-info">
          <!-- 二级标签：实盘 / 模拟（仅同时存在两个类型时显示） -->
          <div
            v-if="positionData.real.has && positionData.paper.has"
            class="position-type-tabs"
          >
            <div
              class="position-type-tab"
              :class="{ active: activePositionTab === 'real' }"
              @click="activePositionTab = 'real'"
            >
              <el-tag type="danger" size="small">实盘</el-tag>
            </div>
            <div
              class="position-type-tab"
              :class="{ active: activePositionTab === 'paper' }"
              @click="activePositionTab = 'paper'"
            >
              <el-tag type="warning" size="small">模拟</el-tag>
            </div>
          </div>

          <!-- 实盘持仓 -->
          <div
            v-if="positionData.real.has && activePositionTab === 'real'"
            class="position-section"
          >
            <div v-if="!(positionData.real.has && positionData.paper.has)" class="position-section-title">
              <el-tag type="danger" size="small">实盘</el-tag>
            </div>
            <div class="position-grid">
              <div class="pos-item"><span class="pos-label">持仓数量</span><b class="pos-value">{{ positionData.real.quantity }} 股</b></div>
              <div class="pos-item"><span class="pos-label">成本价</span><b class="pos-value">¥{{ fmtPrice(positionData.real.cost_price) }}</b></div>
              <div class="pos-item"><span class="pos-label">现价</span><b class="pos-value">¥{{ fmtPrice(positionData.real.current_price) }}</b></div>
              <div class="pos-item"><span class="pos-label">市值</span><b class="pos-value">¥{{ fmtPrice(positionData.real.market_value) }}</b></div>
              <div class="pos-item">
                <span class="pos-label">浮动盈亏</span>
                <b class="pos-value" :class="positionData.real.unrealized_pnl >= 0 ? 'positive' : 'negative'">
                  {{ formatPnl(positionData.real.unrealized_pnl, positionData.real.unrealized_pnl_pct) }}
                </b>
              </div>
            </div>
          </div>

          <!-- 模拟持仓 -->
          <div
            v-if="positionData.paper.has && activePositionTab === 'paper'"
            class="position-section"
          >
            <div v-if="!(positionData.real.has && positionData.paper.has)" class="position-section-title">
              <el-tag type="warning" size="small">模拟</el-tag>
            </div>
            <div class="position-grid">
              <div class="pos-item"><span class="pos-label">持仓数量</span><b class="pos-value">{{ positionData.paper.quantity }} 股</b></div>
              <div class="pos-item"><span class="pos-label">成本价</span><b class="pos-value">¥{{ fmtPrice(positionData.paper.cost_price) }}</b></div>
              <div class="pos-item"><span class="pos-label">现价</span><b class="pos-value">¥{{ fmtPrice(positionData.paper.current_price) }}</b></div>
              <div class="pos-item"><span class="pos-label">市值</span><b class="pos-value">¥{{ fmtPrice(positionData.paper.market_value) }}</b></div>
              <div class="pos-item">
                <span class="pos-label">浮动盈亏</span>
                <b class="pos-value" :class="positionData.paper.unrealized_pnl >= 0 ? 'positive' : 'negative'">
                  {{ formatPnl(positionData.paper.unrealized_pnl, positionData.paper.unrealized_pnl_pct) }}
                </b>
              </div>
            </div>
          </div>
        </div>

        <div class="tab-footer">
          <el-button text size="small" @click="$emit('goPositionAnalysis')">
            <el-icon><Plus /></el-icon> 重新分析
          </el-button>
          <el-button text size="small" @click="$emit('viewPositionTaskDetail')">
            <el-icon><View /></el-icon> 查看详情
          </el-button>
        </div>

        <div class="disclaimer">
          本分析基于公开信息和持仓数据生成，仅供研究参考，不构成任何交易建议。
        </div>
      </div>
    </div>

    <!-- 交易复盘内容 -->
    <div class="tab-content" :class="{ active: activeTab === 'review' }">
      <div v-if="!reviewSummary.has" class="empty-state">
        <el-empty description="暂无交易复盘记录">
          <el-button type="primary" @click="$emit('goTradeReview')">发起交易复盘</el-button>
        </el-empty>
      </div>
      <div v-else>
        <!-- 复盘摘要 -->
        <div class="summary-row">
          <div class="summary-item">
            <div class="label">交易次数</div>
            <div class="value">{{ reviewSummary.tradeCount || '-' }} 次</div>
          </div>
          <div class="summary-item" v-if="reviewSummary.riskLevel">
            <div class="label">风险等级</div>
            <div class="value">{{ reviewSummary.riskLevel }}</div>
          </div>
          <div class="summary-item">
            <div class="label">完成时间</div>
            <div class="value">
              {{ formatAnalysisTime(reviewSummary.completedAt) }}
              <span v-if="reviewRelativeTime" class="relative-time">{{ reviewRelativeTime }}</span>
            </div>
          </div>
        </div>

        <!-- 数据过期提示：超过 1 天显示重新复盘按钮 -->
        <div v-if="reviewStale" class="stale-banner">
          <span>⚠ 本次复盘距今较久，市场环境可能已变化</span>
          <button class="stale-btn" @click="$emit('goTradeReview')">
            🔄 重新复盘
          </button>
        </div>

        <!-- 复盘结论 -->
        <div v-if="reviewSummary.summary" class="sub-section">
          <div class="sub-section-title">
            <el-icon><Document /></el-icon>
            <span>复盘结论</span>
          </div>
          <div class="sub-section-content markdown-body" v-html="renderMarkdown(reviewSummary.summary)"></div>
        </div>

        <!-- 研究观察（合规：原"操作建议"改为研究性表述） -->
        <div v-if="reviewSummary.recommendation" class="sub-section">
          <div class="sub-section-title">
            <el-icon><Opportunity /></el-icon>
            <span>研究观察</span>
          </div>
          <div class="sub-section-content markdown-body" v-html="renderMarkdown(reviewSummary.recommendation)"></div>
        </div>

        <div class="tab-footer">
          <el-button text size="small" @click="$emit('goTradeReview')">
            <el-icon><Plus /></el-icon> 重新复盘
          </el-button>
          <el-button text size="small" @click="$emit('viewReviewTaskDetail')">
            <el-icon><View /></el-icon> 查看详情
          </el-button>
        </div>

        <div class="disclaimer">
          本复盘基于历史交易记录生成，用于回顾决策过程，不构成对未来交易的建议。
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Plus, View, InfoFilled, Document, Opportunity } from '@element-plus/icons-vue'
import { renderMarkdown } from '@/utils/markdown'

interface PositionSnapshot {
  cost_price?: number
  current_price?: number
  quantity?: number
  unrealized_pnl?: number
  unrealized_pnl_pct?: number
  holding_days?: number
  position_pct?: number
}

interface PositionSummaryState {
  has: boolean
  taskId: string
  completedAt: string
  snapshot: PositionSnapshot | null
  action: string
  confidence: number | null
  conclusion: string
  keyPoints: string[]
}

interface ReviewSummaryState {
  has: boolean
  taskId: string
  completedAt: string
  riskLevel: string
  confidenceScore: number | null
  summary: string
  recommendation: string
  tradeCount: number | null
}

interface PositionDataState {
  loading: boolean
  real: {
    has: boolean
    quantity: number
    cost_price: number
    current_price: number
    market_value: number
    unrealized_pnl: number
    unrealized_pnl_pct: number
  }
  paper: {
    has: boolean
    quantity: number
    cost_price: number
    current_price: number
    market_value: number
    unrealized_pnl: number
    unrealized_pnl_pct: number
  }
}

const props = defineProps<{
  positionSummary: PositionSummaryState
  reviewSummary: ReviewSummaryState
  positionData: PositionDataState
  reviewHistory: { loading: boolean; items: any[]; total: number; selectedIndex: number }
  positionHistoryCount?: number
}>()

defineEmits<{
  (e: 'goPositionAnalysis'): void
  (e: 'goTradeReview'): void
  (e: 'viewPositionTaskDetail'): void
  (e: 'viewReviewTaskDetail'): void
  (e: 'viewPositionHistory'): void
  (e: 'viewReviewHistory'): void
  (e: 'selectReviewItem', idx: number): void
}>()

const activeTab = ref<'position' | 'review'>('position')

// 持仓分析内部二级标签：实盘 / 模拟（默认优先显示实盘）
const activePositionTab = ref<'real' | 'paper'>('real')

const positionBadgeText = computed(() => {
  const snap = props.positionSummary.snapshot
  const pct = snap?.unrealized_pnl_pct
  if (!snap || pct === undefined || !Number.isFinite(pct)) return '已分析'
  if (pct > 0) return `浮盈 ${pct.toFixed(2)}%`
  return `浮亏 ${Math.abs(pct).toFixed(2)}%`
})

const positionBadgeClass = computed(() => {
  const snap = props.positionSummary.snapshot
  if (!snap) return ''
  const pnl = snap.unrealized_pnl ?? 0
  return pnl >= 0 ? 'badge-up' : 'badge-down'
})

const reviewBadgeText = computed(() => {
  if (props.reviewSummary.tradeCount) return `${props.reviewSummary.tradeCount} 次`
  return '已复盘'
})

const reviewBadgeClass = computed(() => 'badge-info')

// ════════ 数据新鲜度判断 ════════

/** 将时间字符串转为距今天数（小数），无效返回 null */
function daysSince(dateStr: string | null | undefined): number | null {
  if (!dateStr) return null
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return null
  return (Date.now() - d.getTime()) / (1000 * 60 * 60 * 24)
}

/** 天数转相对时间文本 */
function daysToRelative(days: number | null): string {
  if (days === null || days < 0) return ''
  if (days < 1 / 24) return '刚刚'
  if (days < 1) return `${Math.floor(days * 24)}小时前`
  if (days < 30) return `${Math.floor(days)}天前`
  if (days < 365) return `${Math.floor(days / 30)}个月前`
  return `${Math.floor(days / 365)}年前`
}

// 持仓分析数据新鲜度
const positionRelativeTime = computed(() => daysToRelative(daysSince(props.positionSummary.completedAt)))
const positionStale = computed(() => {
  const d = daysSince(props.positionSummary.completedAt)
  return d !== null && d > 1
})

// 交易复盘数据新鲜度
const reviewRelativeTime = computed(() => daysToRelative(daysSince(props.reviewSummary.completedAt)))
const reviewStale = computed(() => {
  const d = daysSince(props.reviewSummary.completedAt)
  return d !== null && d > 1
})

function fmtPrice(v: any) {
  const n = Number(v)
  return Number.isFinite(n) ? n.toFixed(2) : '-'
}

function formatPnl(pnl: any, pct: any): string {
  const p = Number(pnl)
  const pPct = Number(pct)
  const pnlStr = Number.isFinite(p) ? (p >= 0 ? '+' : '') + p.toFixed(2) : '-'
  const pctStr = Number.isFinite(pPct) ? ` (${pPct >= 0 ? '+' : ''}${pPct.toFixed(2)}%)` : ''
  return `${pnlStr}${pctStr}`
}

function formatPercent(v: any): string {
  const n = Number(v)
  if (!Number.isFinite(n)) return '-'
  return n.toFixed(2) + '%'
}

function pnlClass(v: any) {
  const n = Number(v)
  if (!Number.isFinite(n) || n === 0) return ''
  return n > 0 ? 'positive' : 'negative'
}

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
</script>

<style scoped>
.card {
  background: var(--el-bg-color, #fff);
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  border: 1px solid #f1f5f9;
  overflow: hidden;
}

.tabs {
  display: flex;
  border-bottom: 1px solid #f1f5f9;
  align-items: center;
}

.tab {
  padding: 12px 20px;
  font-size: 14px;
  font-weight: 600;
  color: #64748b;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 6px;
}

.tab:hover {
  color: #6b5ce7;
}

.tab.active {
  color: #6b5ce7;
  border-bottom-color: #6b5ce7;
}

.tab-badge {
  padding: 1px 6px;
  background: #f1f5f9;
  border-radius: 3px;
  font-size: 10px;
  color: #94a3b8;
}

.tab.active .tab-badge {
  background: #f5f3ff;
  color: #6b5ce7;
}

.tab-badge.badge-up {
  background: #fef2f2;
  color: #ef4444;
}

.tab-badge.badge-down {
  background: #f0fdf4;
  color: #16a34a;
}

.tab-badge.badge-info {
  background: #eff6ff;
  color: #3b82f6;
}

.tab-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
  padding-right: 12px;
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

.tab-content {
  display: none;
  padding: 16px 20px;
}

.tab-content.active {
  display: block;
}

.empty-state {
  padding: 20px 0;
}

.summary-row {
  display: flex;
  gap: 16px;
  padding: 12px;
  background: #f8fafc;
  border-radius: 8px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.summary-item {
  flex: 1;
  min-width: 100px;
  text-align: center;
}

.summary-item .label {
  font-size: 11px;
  color: #94a3b8;
  margin-bottom: 4px;
}

.summary-item .value {
  font-size: 16px;
  font-weight: 700;
  color: #1e293b;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.summary-item .value.positive {
  color: #ef4444;
}

.summary-item .value.negative {
  color: #16a34a;
}

.ai-advice {
  margin-bottom: 14px;
  padding: 12px;
  background: #f5f3ff;
  border-radius: 8px;
  border-left: 3px solid #6b5ce7;
}

.advice-label {
  font-size: 12px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 6px;
}

.advice-time {
  font-size: 11px;
  color: #64748b;
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.relative-time {
  font-size: 11px;
  font-weight: 500;
  color: #f59e0b;
  background: #fef3c7;
  padding: 1px 6px;
  border-radius: 4px;
}

.stale-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border: 1px solid #f59e0b;
  border-radius: 6px;
  background: #fffbeb;
  color: #b45309;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
  font-family: inherit;
}

.stale-btn:hover {
  background: #f59e0b;
  color: #fff;
}

.stale-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  margin-bottom: 14px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 8px;
  font-size: 12px;
  color: #92400e;
  flex-wrap: wrap;
}

.advice-conclusion {
  display: flex;
  gap: 6px;
  font-size: 13px;
  color: #1e293b;
  line-height: 1.6;
  margin-top: 4px;
}

.advice-icon {
  color: #6b5ce7;
  flex-shrink: 0;
  margin-top: 2px;
}

.advice-keypoints {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed #e2e8f0;
}

.keypoints-title {
  font-size: 12px;
  font-weight: 600;
  color: #ef4444;
  margin-bottom: 6px;
}

.keypoints-list {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
  color: #64748b;
  line-height: 1.8;
}

.position-info {
  margin-top: 14px;
}

.position-type-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.position-type-tab {
  padding: 6px 14px;
  border-radius: 6px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  cursor: pointer;
  transition: all 0.2s;
  opacity: 0.7;
}

.position-type-tab:hover {
  background: #f1f5f9;
  opacity: 0.9;
}

.position-type-tab.active {
  background: #f5f3ff;
  border-color: #6b5ce7;
  opacity: 1;
  box-shadow: 0 1px 2px rgba(107, 92, 231, 0.1);
}

.position-section {
  margin-bottom: 12px;
}

.position-section-title {
  margin-bottom: 8px;
}

.position-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 10px;
  padding: 10px;
  background: #f8fafc;
  border-radius: 6px;
}

.pos-item .pos-label {
  font-size: 10px;
  color: #94a3b8;
  display: block;
}

.pos-item .pos-value {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  display: block;
  margin-top: 2px;
}

.pos-value.positive {
  color: #ef4444;
}

.pos-value.negative {
  color: #16a34a;
}

.sub-section {
  margin-bottom: 14px;
}

.sub-section-title {
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 6px;
  color: #1e293b;
}

.sub-section-content {
  font-size: 13px;
  color: #64748b;
  line-height: 1.7;
  padding: 10px 12px;
  background: #f8fafc;
  border-radius: 6px;
  border-left: 3px solid #6b5ce7;
}

.tab-footer {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed #f1f5f9;
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
  .position-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
