<template>
  <div class="stock-header">
    <!-- 左侧：股票概览 -->
    <div class="stock-card">
      <div class="stock-name-row">
        <span class="stock-code">{{ code }}</span>
        <span class="stock-name">{{ stockName || '-' }}</span>
        <span class="market-tag">{{ marketLabel }}</span>
        <template v-if="isEtf">
          <el-tag v-if="etfBasics.fundType" size="small" effect="plain" type="success">{{ etfBasics.fundType }}</el-tag>
          <el-tag v-if="etfBasics.trackIndex" size="small" effect="plain" type="info">跟踪 {{ etfBasics.trackIndex }}</el-tag>
        </template>
      </div>

      <div class="price-row">
        <span class="current-price" :class="changeClass">{{ fmtPrice(quote.price) }}</span>
        <span class="price-change" :class="changeClass">
          {{ fmtPercent(quote.changePercent) }}
        </span>
        <span class="price-meta">
          <span v-if="quote.tradeDate">{{ quote.tradeDate }} 收盘</span>
          <span v-else>{{ refreshText }}</span>
        </span>
        <el-button text size="small" @click="$emit('refresh')" :icon="Refresh">刷新</el-button>
      </div>

      <div class="quick-metrics">
        <div class="quick-metric-item">
          <div class="label">今开</div>
          <div class="value">{{ fmtPrice(quote.open) }}</div>
        </div>
        <div class="quick-metric-item">
          <div class="label">最高</div>
          <div class="value">{{ fmtPrice(quote.high) }}</div>
        </div>
        <div class="quick-metric-item">
          <div class="label">最低</div>
          <div class="value">{{ fmtPrice(quote.low) }}</div>
        </div>
        <div class="quick-metric-item">
          <div class="label">成交量</div>
          <div class="value">{{ fmtVolume(quote.volume) }}</div>
        </div>
        <div class="quick-metric-item">
          <div class="label">成交额</div>
          <div class="value">{{ fmtAmount(quote.amount) }}</div>
        </div>
        <div class="quick-metric-item">
          <div class="label">换手率</div>
          <div class="value">{{ fmtPercent(quote.turnover) }}</div>
        </div>
        <div class="quick-metric-item">
          <div class="label">振幅</div>
          <div class="value">{{ Number.isFinite(quote.amplitude) ? quote.amplitude.toFixed(2) + '%' : '-' }}</div>
        </div>
        <div class="quick-metric-item">
          <div class="label">昨收</div>
          <div class="value">{{ fmtPrice(quote.prevClose) }}</div>
        </div>
      </div>

      <!-- 数据更新提示 -->
      <div class="sync-status" v-if="quote.updatedAt || syncStatus">
        <el-icon><Clock /></el-icon>
        <span class="sync-info">
          <template v-if="quote.updatedAt">
            数据更新: {{ formatQuoteUpdateTime(quote.updatedAt) }}
          </template>
          <template v-else-if="syncStatus">
            后端同步: {{ formatSyncTime(syncStatus.last_sync_time) }}
            <span v-if="syncStatus.interval_seconds">{{ formatSyncInterval(syncStatus.interval_seconds) }}</span>
          </template>
          <el-tag v-if="syncStatus?.data_source" size="small" type="success" style="margin-left: 4px">
            {{ syncStatus.data_source }}
          </el-tag>
        </span>
      </div>
    </div>

    <!-- 右侧：操作入口 -->
    <div class="action-entry">
      <div class="action-placeholder"></div>
      <button class="action-btn action-btn-primary" @click="$emit('sync')" :disabled="syncLoading">
        <span class="icon">🔄</span>
        <span class="title">同步数据</span>
        <span class="desc">更新行情/财务数据</span>
      </button>
      <button class="action-btn" @click="$emit('analyze')">
        <span class="icon">🔬</span>
        <span class="title">{{ isEtf ? '发起ETF研究' : '发起研究' }}</span>
        <span class="desc">AI 多智能体深度分析</span>
      </button>
      <button class="action-btn" @click="$emit('goPositionAnalysis')">
        <span class="icon">💼</span>
        <span class="title">持仓分析</span>
        <span class="desc">查看持仓研究详情</span>
      </button>
      <button class="action-btn" @click="$emit('addPosition')">
        <span class="icon">➕</span>
        <span class="title">添加持仓</span>
        <span class="desc">记录你的持仓信息</span>
      </button>
      <button class="action-btn" @click="$emit('goTradeReview')">
        <span class="icon">📈</span>
        <span class="title">操作复盘</span>
        <span class="desc">回顾历史操作决策</span>
      </button>
      <button class="action-btn" @click="$emit('paperTrading')">
        <span class="icon">📊</span>
        <span class="title">模拟交易</span>
        <span class="desc">进入模拟交易系统</span>
      </button>
      <button class="action-btn" :class="{ 'is-active': isFav }" @click="$emit('toggleFavorite')">
        <span class="icon">⭐</span>
        <span class="title">{{ isFav ? '已关注' : '加入自选' }}</span>
        <span class="desc">{{ isFav ? '点击取消关注' : '添加到关注列表' }}</span>
      </button>
      <button class="action-btn" @click="$emit('clearCache')" :disabled="clearCacheLoading">
        <span class="icon">🧹</span>
        <span class="title">清除缓存</span>
        <span class="desc">强制重新获取数据</span>
      </button>
      <button class="action-btn" @click="$emit('goTradeReviewHistory')">
        <span class="icon">📜</span>
        <span class="title">历史记录</span>
        <span class="desc">查看分析/复盘历史</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Refresh, Clock } from '@element-plus/icons-vue'

interface QuoteData {
  price: number
  changePercent: number
  open: number
  high: number
  low: number
  prevClose: number
  volume: number
  amount: number
  turnover: number
  amplitude: number
  tradeDate: string | null
  turnoverDate: string | null
  amplitudeDate: string | null
  updatedAt: string | null
}

interface EtfBasicsData {
  fundType: string
  trackIndex: string
  fundScale: string | number
  fundShare: string | number
  management: string
  unitNav: number
  accumNav: number
  marketPrice: number
  updatedAt: string
}

const props = defineProps<{
  code: string
  stockName: string
  marketLabel: string
  isEtf: boolean
  quote: QuoteData
  etfBasics: EtfBasicsData
  isFav: boolean
  refreshText: string
  syncStatus: any
  syncLoading: boolean
  clearCacheLoading: boolean
}>()

defineEmits<{
  (e: 'refresh'): void
  (e: 'analyze'): void
  (e: 'sync'): void
  (e: 'paperTrading'): void
  (e: 'toggleFavorite'): void
  (e: 'clearCache'): void
  (e: 'goPositionAnalysis'): void
  (e: 'addPosition'): void
  (e: 'goTradeReview'): void
  (e: 'goTradeReviewHistory'): void
  (e: 'goApiGuide'): void
}>()

const changeClass = computed(() => props.quote.changePercent > 0 ? 'up' : props.quote.changePercent < 0 ? 'down' : '')

function fmtPrice(v: any) {
  const n = Number(v)
  return Number.isFinite(n) ? n.toFixed(2) : '-'
}

function fmtPercent(v: any) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '-'
  return `${n > 0 ? '+' : ''}${n.toFixed(2)}%`
}

function fmtVolume(v: any) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '-'
  if (n >= 1e8) return (n / 1e8).toFixed(2) + '亿'
  if (n >= 1e4) return (n / 1e4).toFixed(2) + '万'
  return String(n)
}

function fmtAmount(v: any) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '-'
  if (n >= 1e8) return (n / 1e8).toFixed(2) + '亿'
  if (n >= 1e4) return (n / 1e4).toFixed(2) + '万'
  return n.toFixed(2)
}

function formatQuoteUpdateTime(timeStr: string | null | undefined): string {
  if (!timeStr) return '-'
  try {
    const d = new Date(timeStr)
    if (isNaN(d.getTime())) return timeStr
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  } catch {
    return String(timeStr)
  }
}

function formatSyncTime(timeStr: string | null | undefined): string {
  if (!timeStr) return '从未同步'
  try {
    const d = new Date(timeStr)
    if (isNaN(d.getTime())) return timeStr
    const now = new Date()
    const diff = (now.getTime() - d.getTime()) / 1000
    if (diff < 60) return `${Math.floor(diff)}秒前`
    if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
    if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`
    return `${Math.floor(diff / 86400)}天前`
  } catch {
    return String(timeStr)
  }
}

function formatSyncInterval(seconds: number): string {
  if (!seconds) return ''
  if (seconds >= 86400) return `· 每${Math.floor(seconds / 86400)}天`
  if (seconds >= 3600) return `· 每${Math.floor(seconds / 3600)}小时`
  if (seconds >= 60) return `· 每${Math.floor(seconds / 60)}分钟`
  return `· 每${seconds}秒`
}
</script>

<style scoped>
.stock-header {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 20px;
  margin-bottom: 16px;
  align-items: start;
}

.stock-card {
  background: var(--el-bg-color, #fff);
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  border: 1px solid #f1f5f9;
}

.stock-name-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.stock-code {
  font-size: 24px;
  font-weight: 700;
  color: #1e293b;
}

.stock-name {
  font-size: 18px;
  color: #64748b;
}

.market-tag {
  padding: 2px 8px;
  background: #eff6ff;
  color: #3b82f6;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.price-row {
  display: flex;
  align-items: baseline;
  gap: 16px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.current-price {
  font-size: 32px;
  font-weight: 700;
  color: #1e293b;
}

.current-price.up { color: #ef4444; }
.current-price.down { color: #16a34a; }

.price-change {
  font-size: 16px;
  font-weight: 600;
  color: #64748b;
}

.price-change.up { color: #ef4444; }
.price-change.down { color: #16a34a; }

.price-meta {
  font-size: 12px;
  color: #94a3b8;
}

.quick-metrics {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  padding-top: 12px;
  border-top: 1px solid #f1f5f9;
}

.quick-metric-item .label {
  font-size: 11px;
  color: #94a3b8;
  margin-bottom: 2px;
}

.quick-metric-item .value {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}

.sync-status {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed #f1f5f9;
  font-size: 12px;
  color: #64748b;
}

.sync-info {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

/* 操作入口 */
.action-entry {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  width: 520px;
}

.action-placeholder {
  visibility: hidden;
  pointer-events: none;
}

.action-btn {
  padding: 14px 16px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: var(--el-bg-color, #fff);
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  text-align: left;
  font-family: inherit;
}

.action-btn:hover:not(:disabled) {
  border-color: #6b5ce7;
  background: #f5f3ff;
  transform: translateY(-1px);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.action-btn-primary {
  background: linear-gradient(135deg, #6b5ce7 0%, #8b5cf6 100%);
  color: #fff;
  border: none;
}

.action-btn-primary:hover:not(:disabled) {
  opacity: 0.9;
  background: linear-gradient(135deg, #6b5ce7 0%, #8b5cf6 100%);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(107, 92, 231, 0.25);
}

.action-btn.is-active {
  border-color: #f59e0b;
  background: #fffbeb;
}

.action-btn .icon {
  font-size: 18px;
}

.action-btn .title {
  font-size: 13px;
  font-weight: 700;
}

.action-btn .desc {
  font-size: 11px;
  color: #94a3b8;
}

.action-btn-primary .desc {
  color: rgba(255, 255, 255, 0.8);
}

@media (max-width: 1024px) {
  .stock-header {
    grid-template-columns: 1fr;
  }
  .action-entry {
    width: 100%;
  }
}
</style>
