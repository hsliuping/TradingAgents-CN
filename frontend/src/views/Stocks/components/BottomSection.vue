<template>
  <div class="bottom-grid" id="bottom-section">
    <!-- 基本面数据 -->
    <div class="card">
      <div class="card-header">
        <div class="section-title">
          <span>📚</span>
          <span>{{ isEtf ? 'ETF基础数据' : '基本面数据' }}</span>
        </div>
        <el-tag v-if="basics.peIsRealtime" type="success" size="small">实时</el-tag>
      </div>
      <div class="card-body">
        <!-- ETF 基础 -->
        <div v-if="isEtf" class="snapshot-grid">
          <div class="snapshot-item"><span class="snapshot-label">基金类型</span><span class="snapshot-value">{{ etfBasics.fundType || '-' }}</span></div>
          <div class="snapshot-item"><span class="snapshot-label">跟踪指数</span><span class="snapshot-value">{{ etfBasics.trackIndex || '-' }}</span></div>
          <div class="snapshot-item"><span class="snapshot-label">基金规模</span><span class="snapshot-value">{{ fmtText(etfBasics.fundScale) }}</span></div>
          <div class="snapshot-item"><span class="snapshot-label">基金份额</span><span class="snapshot-value">{{ fmtText(etfBasics.fundShare) }}</span></div>
          <div class="snapshot-item"><span class="snapshot-label">单位净值</span><span class="snapshot-value">{{ fmtPrice(etfBasics.unitNav) }}</span></div>
          <div class="snapshot-item"><span class="snapshot-label">累计净值</span><span class="snapshot-value">{{ fmtPrice(etfBasics.accumNav) }}</span></div>
          <div class="snapshot-item"><span class="snapshot-label">折溢价率</span><span class="snapshot-value">{{ fmtLoosePercent(etfBasics.premiumDiscountRate) }}</span></div>
          <div class="snapshot-item"><span class="snapshot-label">净值增长率</span><span class="snapshot-value">{{ fmtLoosePercent(etfBasics.navGrowthRate) }}</span></div>
          <div class="snapshot-item"><span class="snapshot-label">管理人</span><span class="snapshot-value">{{ etfBasics.management || '-' }}</span></div>
          <div class="snapshot-item"><span class="snapshot-label">托管人</span><span class="snapshot-value">{{ etfBasics.custodian || '-' }}</span></div>
        </div>
        <!-- 股票基本面 -->
        <div v-else class="snapshot-grid">
          <div class="snapshot-item"><span class="snapshot-label">行业</span><span class="snapshot-value">{{ basics.industry }}</span></div>
          <div class="snapshot-item"><span class="snapshot-label">板块</span><span class="snapshot-value">{{ basics.sector }}</span></div>
          <div class="snapshot-item"><span class="snapshot-label">总市值</span><span class="snapshot-value">{{ fmtAmount(basics.marketCap) }}</span></div>
          <div class="snapshot-item"><span class="snapshot-label">PE(TTM)</span><span class="snapshot-value">{{ fmtNum(basics.pe) }}</span></div>
          <div class="snapshot-item"><span class="snapshot-label">PB(市净率)</span><span class="snapshot-value">{{ fmtNum(basics.pb) }}</span></div>
          <div class="snapshot-item"><span class="snapshot-label">PS(TTM)</span><span class="snapshot-value">{{ fmtNum(basics.ps) }}</span></div>
          <div class="snapshot-item"><span class="snapshot-label">ROE</span><span class="snapshot-value">{{ fmtPercent(basics.roe) }}</span></div>
          <div class="snapshot-item"><span class="snapshot-label">负债率</span><span class="snapshot-value">{{ fmtPercent(basics.debtRatio) }}</span></div>
          <div class="snapshot-item"><span class="snapshot-label">股息率</span><span class="snapshot-value">{{ fmtPercent(basics.dividendYield) }}</span></div>
          <div class="snapshot-item"><span class="snapshot-label">流动比率</span><span class="snapshot-value">{{ fmtRatio(basics.currentRatio) }}</span></div>
        </div>
      </div>
    </div>

    <!-- 财务明细 -->
    <div v-if="!isEtf" class="card">
      <div class="card-header">
        <div class="section-title">
          <span>💰</span>
          <span>财务明细快照</span>
        </div>
        <el-tag v-if="financialSnapshot.annDate" size="small" type="info" effect="plain">{{ financialSnapshot.annDate }}</el-tag>
      </div>
      <div class="card-body">
        <div class="snapshot-grid">
          <div class="snapshot-item"><span class="snapshot-label">毛利率</span><span class="snapshot-value">{{ fmtPercent(financialSnapshot.grossMargin) }}</span></div>
          <div class="snapshot-item"><span class="snapshot-label">净利率</span><span class="snapshot-value">{{ fmtPercent(financialSnapshot.netprofitMargin) }}</span></div>
          <div class="snapshot-item"><span class="snapshot-label">营收</span><span class="snapshot-value">{{ fmtAmount(financialSnapshot.revenue) }}</span></div>
          <div class="snapshot-item"><span class="snapshot-label">净利润</span><span class="snapshot-value">{{ fmtAmount(financialSnapshot.netProfit) }}</span></div>
          <div class="snapshot-item"><span class="snapshot-label">经营现金流</span><span class="snapshot-value">{{ fmtAmount(financialSnapshot.nCashflowAct) }}</span></div>
          <div class="snapshot-item"><span class="snapshot-label">总资产</span><span class="snapshot-value">{{ fmtAmount(financialSnapshot.totalAssets) }}</span></div>
          <div class="snapshot-item"><span class="snapshot-label">总负债</span><span class="snapshot-value">{{ fmtAmount(financialSnapshot.totalLiab) }}</span></div>
          <div class="snapshot-item"><span class="snapshot-label">数据源</span><span class="snapshot-value">{{ financialSnapshot.dataSource || '-' }}</span></div>
        </div>
        <div v-if="financialRawSections.length" class="raw-section-summary">
          <div class="raw-title">raw_data 分组</div>
          <div class="raw-tags">
            <el-tag v-for="section in financialRawSections" :key="section.key" size="small" type="info" effect="plain">
              {{ section.label }} {{ section.count }} 条
            </el-tag>
          </div>
          <div class="raw-hint">这些原始分组已经通过主股票接口暴露，后续页面或智能工具可以直接下钻调用。</div>
        </div>
      </div>
    </div>

    <!-- 近期新闻与公告 -->
    <div class="card news-card">
      <div class="card-header">
        <div class="section-title">
          <span>📰</span>
          <span>{{ isEtf ? 'ETF新闻与公告' : '近期新闻与公告' }}</span>
        </div>
        <el-select :model-value="newsFilter" size="small" style="width: 120px" @change="(v: string) => $emit('newsFilterChange', v)">
          <el-option label="全部" value="all" />
          <el-option label="新闻" value="news" />
          <el-option label="公告" value="announcement" />
        </el-select>
      </div>
      <div class="card-body">
        <div v-if="newsLoading" v-loading="true" style="min-height: 120px"></div>
        <el-empty v-else-if="!filteredNews.length" description="暂无新闻" :image-size="60" />
        <div v-else class="news-list">
          <div v-for="(n, i) in filteredNews" :key="i" class="news-item">
            <div class="news-header">
              <div class="news-title">
                <span class="news-tag" :class="n.type === 'announcement' ? 'tag-announcement' : 'tag-news'">
                  {{ n.type === 'announcement' ? '公告' : '新闻' }}
                </span>
                <a v-if="n.url && n.url !== '#'" :href="n.url" target="_blank" rel="noopener" class="news-link">{{ n.title || '查看详情' }}</a>
                <span v-else>{{ n.title || '（无标题）' }}</span>
              </div>
              <div class="news-time">{{ formatNewsTime(n.time) }}</div>
            </div>
            <div class="news-source">{{ n.source || '-' }} · {{ newsSource || '-' }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface BasicsData {
  industry: string
  sector: string
  marketCap: number
  pe: number
  pb: number
  ps: number
  roe: number
  debtRatio: number
  dividendYield: number
  currentRatio: number
  reportPeriod: string
  peIsRealtime: boolean
}

interface FinancialSnapshotData {
  annDate: string
  dataSource: string
  grossMargin: number
  netprofitMargin: number
  revenue: number
  netProfit: number
  nCashflowAct: number
  totalAssets: number
  totalLiab: number
}

interface EtfBasicsData {
  fundType: string
  trackIndex: string
  fundScale: string | number
  fundShare: string | number
  management: string
  custodian: string
  unitNav: number
  accumNav: number
  navGrowthRate: any
  premiumDiscountRate: any
}

const props = defineProps<{
  isEtf: boolean
  basics: BasicsData
  financialSnapshot: FinancialSnapshotData
  etfBasics: EtfBasicsData
  financialRawSections: Array<{ key: string; label: string; count: number }>
  newsItems: any[]
  newsFilter: string
  newsLoading: boolean
  newsSource?: string
}>()

defineEmits<{
  (e: 'newsFilterChange', filter: string): void
}>()

const filteredNews = computed(() => {
  if (props.newsFilter === 'news') return props.newsItems.filter(x => x.type === 'news')
  if (props.newsFilter === 'announcement') return props.newsItems.filter(x => x.type === 'announcement')
  return props.newsItems
})

function fmtNum(v: any) {
  const n = Number(v)
  return Number.isFinite(n) ? n.toFixed(2) : '-'
}

function fmtPercent(v: any) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '-'
  return n.toFixed(2) + '%'
}

function fmtRatio(v: any) {
  const n = Number(v)
  return Number.isFinite(n) ? n.toFixed(2) : '-'
}

function fmtAmount(v: any) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '-'
  if (n >= 1e8) return (n / 1e8).toFixed(2) + '亿'
  if (n >= 1e4) return (n / 1e4).toFixed(2) + '万'
  return n.toFixed(2)
}

function fmtPrice(v: any) {
  const n = Number(v)
  return Number.isFinite(n) ? n.toFixed(2) : '-'
}

function fmtText(v: any) {
  if (v === null || v === undefined || v === '') return '-'
  return String(v)
}

function fmtLoosePercent(v: any) {
  if (v === null || v === undefined || v === '') return '-'
  const n = Number(v)
  if (!Number.isFinite(n)) return String(v)
  return n.toFixed(2) + '%'
}

function formatNewsTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '-'
  try {
    const d = new Date(dateStr)
    if (isNaN(d.getTime())) return String(dateStr)
    const now = new Date()
    const diff = (now.getTime() - d.getTime()) / 1000
    if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
    if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`
    if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}天前`
    return `${d.getMonth() + 1}-${d.getDate()}`
  } catch {
    return String(dateStr)
  }
}
</script>

<style scoped>
.bottom-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}

.news-card {
  grid-column: 1 / -1;
}

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

.card-body {
  padding: 16px 20px;
}

.snapshot-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.snapshot-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #f1f5f9;
  font-size: 13px;
}

.snapshot-label {
  color: #64748b;
}

.snapshot-value {
  font-weight: 600;
  color: #1e293b;
}

.raw-section-summary {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px dashed #f1f5f9;
}

.raw-title {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 8px;
}

.raw-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.raw-hint {
  font-size: 11px;
  color: #94a3b8;
  line-height: 1.6;
}

.news-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.news-item {
  padding: 10px;
  background: #f8fafc;
  border-radius: 6px;
  transition: background 0.2s;
}

.news-item:hover {
  background: #f5f3ff;
}

.news-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
  gap: 8px;
}

.news-title {
  font-size: 13px;
  font-weight: 600;
  flex: 1;
  display: flex;
  align-items: center;
  gap: 6px;
}

.news-link {
  color: #1e293b;
  text-decoration: none;
}

.news-link:hover {
  color: #6b5ce7;
}

.news-tag {
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 600;
  flex-shrink: 0;
}

.tag-news {
  background: #eff6ff;
  color: #3b82f6;
}

.tag-announcement {
  background: #fffbeb;
  color: #f59e0b;
}

.news-time {
  font-size: 11px;
  color: #94a3b8;
  flex-shrink: 0;
}

.news-source {
  font-size: 11px;
  color: #94a3b8;
}

@media (max-width: 1024px) {
  .bottom-grid {
    grid-template-columns: 1fr;
  }
}
</style>
