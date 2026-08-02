<template>
  <div class="recommendation-page" v-loading="loading">
    <section class="page-heading">
      <div>
        <h2>股票推荐</h2>
        <p>从已持久化市场数据中筛选研究对象，由你确认后才进入候选池。</p>
      </div>
      <el-button
        v-if="authStore.isAdmin"
        type="primary"
        :loading="running"
        :disabled="isDemo"
        @click="runScan"
      >运行推荐扫描</el-button>
    </section>

    <el-alert
      type="warning"
      :closable="false"
      show-icon
      title="推荐仅用于筛选研究对象，不代表买入建议。加入候选池不会自动分析或下单。"
    />

    <section class="workflow" aria-label="推荐审核流程">
      <span>① 查看今日推荐</span>
      <span>② 阅读理由和风险</span>
      <span>③ 查看评分明细</span>
      <span>④ 人工处理</span>
      <span>⑤ 保留历史记录</span>
    </section>

    <section class="summary" aria-label="推荐摘要">
      <div><span>证券池</span><strong>{{ latestRun?.total_securities ?? 0 }}</strong></div>
      <div><span>符合资格</span><strong>{{ latestRun?.eligible_securities ?? 0 }}</strong></div>
      <div><span>本次推荐</span><strong>{{ latestRun?.recommended_securities ?? 0 }}</strong></div>
      <div><span>待审核</span><strong>{{ pendingCount }}</strong></div>
      <div><span>策略版本</span><strong>{{ latestRun?.policy_version || '尚未运行' }}</strong></div>
    </section>

    <section class="toolbar">
      <el-segmented v-model="activeStatus" :options="statusOptions" @change="load" />
      <div class="batch-actions">
        <span>已选 {{ selectedRows.length }} 项</span>
        <el-button :disabled="!selectedRows.length || isDemo" @click="batchReject">批量拒绝</el-button>
        <el-button type="primary" :disabled="!selectedRows.length || isDemo" @click="batchAccept">批量加入候选池</el-button>
      </div>
    </section>

    <el-table
      ref="tableRef"
      :data="rows"
      row-key="recommendation_id"
      size="small"
      @selection-change="selectedRows = $event"
      @row-click="openDetail"
    >
      <el-table-column type="selection" width="44" :selectable="selectable" />
      <el-table-column label="股票" min-width="150">
        <template #default="{ row }"><strong>{{ row.security_name }}</strong><small>{{ row.symbol }}</small></template>
      </el-table-column>
      <el-table-column label="推荐评分" width="100">
        <template #default="{ row }"><span class="score">{{ Number(row.recommendation_score).toFixed(1) }}</span></template>
      </el-table-column>
      <el-table-column label="主要理由" min-width="240">
        <template #default="{ row }">{{ row.recommendation_reasons.slice(0, 2).join('；') }}</template>
      </el-table-column>
      <el-table-column label="主要风险" min-width="190">
        <template #default="{ row }">{{ row.risk_reasons.slice(0, 2).join('；') || '未发现额外风险扣分' }}</template>
      </el-table-column>
      <el-table-column label="市场状态" width="120"><template #default="{ row }">{{ regimeLabel(row.regime_type) }}</template></el-table-column>
      <el-table-column label="策略信号" width="110"><template #default="{ row }">{{ signalLabel(row.strategy_signal_status) }}</template></el-table-column>
      <el-table-column label="数据质量" width="100"><template #default="{ row }"><el-tag :type="row.data_quality_status === 'PASS' ? 'success' : 'warning'">{{ row.data_quality_status === 'PASS' ? '通过' : '需复核' }}</el-tag></template></el-table-column>
      <el-table-column label="有效期" min-width="160"><template #default="{ row }">{{ displayTime(row.expires_at) }}</template></el-table-column>
      <el-table-column label="状态" width="110"><template #default="{ row }"><el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag></template></el-table-column>
      <el-table-column label="操作" width="240" fixed="right">
        <template #default="{ row }">
          <el-button link @click.stop="openDetail(row)">详情</el-button>
          <template v-if="row.status === 'PENDING_REVIEW'">
            <el-button link :disabled="isDemo" @click.stop="ignore(row)">暂不处理</el-button>
            <el-button link type="danger" :disabled="isDemo" @click.stop="reject(row)">拒绝</el-button>
            <el-button link type="primary" :disabled="isDemo" @click.stop="accept(row)">加入候选池</el-button>
          </template>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!loading && !rows.length" description="当前没有需要展示的推荐" />

    <el-drawer v-model="detailVisible" size="min(720px, 94vw)" title="推荐证据详情">
      <template v-if="selected">
        <section class="detail-heading">
          <div><h3>{{ selected.security_name }} <small>{{ selected.symbol }}</small></h3><p>{{ selected.recommendation_reasons.join('；') }}</p></div>
          <strong class="detail-score">{{ Number(selected.recommendation_score).toFixed(1) }}</strong>
        </section>
        <h4>评分构成</h4>
        <div class="metric-list">
          <div v-for="(value, key) in selected.score_components" :key="key"><span>{{ componentLabel(key) }}</span><strong>+{{ value }}</strong></div>
          <div v-for="(value, key) in selected.risk_penalties" :key="`risk-${key}`" class="risk"><span>{{ componentLabel(key) }}</span><strong>-{{ value }}</strong></div>
        </div>
        <h4>风险说明</h4>
        <el-empty v-if="!selected.risk_reasons.length" description="未发现额外风险扣分" :image-size="56" />
        <ul v-else><li v-for="item in selected.risk_reasons" :key="item">{{ item }}</li></ul>
        <h4>证据与版本</h4>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="证据日期">{{ selected.trade_date }}</el-descriptions-item>
          <el-descriptions-item label="数据质量">{{ selected.data_quality_status }}</el-descriptions-item>
          <el-descriptions-item label="推荐策略版本">{{ selected.policy_version }}</el-descriptions-item>
          <el-descriptions-item label="证据引用">{{ selected.evidence_refs.length }} 条</el-descriptions-item>
        </el-descriptions>
        <el-collapse class="advanced">
          <el-collapse-item title="高级信息" name="advanced">
            <p>推荐 ID：{{ selected.recommendation_id }}</p>
            <p>运行 ID：{{ selected.recommendation_run_id }}</p>
            <p>输入 Hash：{{ selected.input_hash }}</p>
            <p>输出 Hash：{{ selected.output_hash }}</p>
          </el-collapse-item>
        </el-collapse>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import type { TableInstance } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import {
  alphaguardRecommendationsApi,
  type CandidateRecommendation,
  type RecommendationRun,
  type RecommendationStatus
} from '@/api/alphaguardRecommendations'

const authStore = useAuthStore()
const route = useRoute()
const isDemo = import.meta.env.VITE_ALPHAGUARD_DEMO === 'true'
const loading = ref(false)
const running = ref(false)
const rows = ref<CandidateRecommendation[]>([])
const runs = ref<RecommendationRun[]>([])
const selectedRows = ref<CandidateRecommendation[]>([])
const selected = ref<CandidateRecommendation | null>(null)
const detailVisible = ref(false)
const activeStatus = ref<'ALL' | RecommendationStatus>('PENDING_REVIEW')
const tableRef = ref<TableInstance>()
const statusOptions = [
  { label: '待审核', value: 'PENDING_REVIEW' },
  { label: '全部记录', value: 'ALL' },
  { label: '已加入', value: 'ACCEPTED' },
  { label: '已拒绝', value: 'REJECTED' },
  { label: '暂不处理', value: 'IGNORED' }
]
const latestRun = computed(() => runs.value[0] || null)
const pendingCount = computed(() => rows.value.filter(row => row.status === 'PENDING_REVIEW').length)

async function load() {
  loading.value = true
  try {
    const [recommendationResponse, runResponse] = await Promise.all([
      alphaguardRecommendationsApi.list({
        status: activeStatus.value === 'ALL' ? undefined : activeStatus.value,
        limit: 500
      }),
      alphaguardRecommendationsApi.runs({ limit: 20 })
    ])
    rows.value = recommendationResponse.data.items
    runs.value = runResponse.data.items
    selectedRows.value = []
    tableRef.value?.clearSelection()
  } catch (error: any) {
    ElMessage.error(error?.message || '推荐记录加载失败，请稍后重试。')
  } finally {
    loading.value = false
  }
}

async function runScan() {
  running.value = true
  try {
    const response = await alphaguardRecommendationsApi.run()
    ElMessage.success(response.data.run_action === 'REUSED' ? '相同输入已复用，没有重复生成推荐。' : '推荐扫描完成。')
    await load()
  } catch (error: any) {
    ElMessage.error(error?.message || '扫描未启动：请先确认盘后行情和交易日历已经就绪。')
  } finally {
    running.value = false
  }
}

function recommendationRow(row: Record<string, unknown>) { return row as unknown as CandidateRecommendation }
function openDetail(row: Record<string, unknown>) { selected.value = recommendationRow(row); detailVisible.value = true }
function selectable(row: Record<string, unknown>) { return recommendationRow(row).status === 'PENDING_REVIEW' }

async function accept(raw: Record<string, unknown>) {
  const row = recommendationRow(raw)
  await ElMessageBox.confirm(`确认将 ${row.security_name}（${row.symbol}）加入候选池？此操作不会下单。`, '加入候选池', { type: 'warning' })
  await alphaguardRecommendationsApi.accept(row.recommendation_id)
  ElMessage.success('已加入候选池，推荐历史完整保留。')
  await load()
}

async function reject(raw: Record<string, unknown>) {
  const row = recommendationRow(raw)
  await ElMessageBox.confirm(`拒绝 ${row.security_name} 的本次推荐？`, '拒绝推荐', { type: 'warning' })
  await alphaguardRecommendationsApi.reject(row.recommendation_id)
  ElMessage.success('已拒绝，冷却期内不会重复提示相同证据。')
  await load()
}

async function ignore(raw: Record<string, unknown>) {
  const row = recommendationRow(raw)
  await alphaguardRecommendationsApi.ignore(row.recommendation_id)
  ElMessage.success('已暂不处理。')
  await load()
}

async function batchAccept() {
  await ElMessageBox.confirm(`确认将选中的 ${selectedRows.value.length} 只证券加入候选池？`, '批量加入候选池', { type: 'warning' })
  await alphaguardRecommendationsApi.batchAccept(selectedRows.value.map(row => row.recommendation_id))
  ElMessage.success('批量处理完成。')
  await load()
}

async function batchReject() {
  await ElMessageBox.confirm(`拒绝选中的 ${selectedRows.value.length} 条推荐？`, '批量拒绝', { type: 'warning' })
  await alphaguardRecommendationsApi.batchReject(selectedRows.value.map(row => row.recommendation_id))
  ElMessage.success('批量处理完成。')
  await load()
}

function displayTime(value: string) { return value.replace('T', ' ').slice(0, 19) }
function statusLabel(value: RecommendationStatus) { return ({ PENDING_REVIEW: '待审核', ACCEPTED: '已加入', REJECTED: '已拒绝', IGNORED: '暂不处理', EXPIRED: '已过期', SUPERSEDED: '已被替代' } as Record<string, string>)[value] || value }
function statusType(value: RecommendationStatus) { return value === 'ACCEPTED' ? 'success' : value === 'REJECTED' ? 'danger' : value === 'PENDING_REVIEW' ? 'warning' : 'info' }
function regimeLabel(value: string | null) { return ({ TREND_UP: '趋势向上', RANGE_STRONG: '强势震荡', RANGE_WEAK: '弱势震荡', TREND_DOWN: '趋势向下', EXTREME_RISK: '极端风险' } as Record<string, string>)[value || ''] || '暂无' }
function signalLabel(value: string | null) { return ({ TRIGGERED: '已触发', WATCH: '观察', REJECTED: '未通过', INSUFFICIENT_DATA: '证据不足' } as Record<string, string>)[value || ''] || '暂无' }
function componentLabel(value: string) { return ({ DATA_QUALITY: '数据完整度', LIQUIDITY: '成交活跃度', TREND: '趋势强度', MOMENTUM: '动量', RELATIVE_STRENGTH: '相对沪深300', MARKET_REGIME: '市场状态适配', STRATEGY_SIGNAL: '既有策略信号', VOLATILITY_RISK: '波动风险扣分', EVENT_RISK: '事件风险扣分', DRAWDOWN_RISK: '回撤风险扣分' } as Record<string, string>)[value] || value }

onMounted(async () => {
  await load()
  const recommendationId = typeof route.query.recommendation === 'string' ? route.query.recommendation : ''
  if (!recommendationId) return
  try {
    const response = await alphaguardRecommendationsApi.detail(recommendationId)
    selected.value = response.data as CandidateRecommendation
    detailVisible.value = true
  } catch {
    ElMessage.warning('原推荐记录不存在或不属于当前用户。')
  }
})
</script>

<style scoped>
.recommendation-page { display: grid; gap: 16px; }
.page-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.page-heading h2 { margin: 0 0 4px; font-size: 22px; }
.page-heading p, .detail-heading p { margin: 0; color: var(--el-text-color-secondary); }
.workflow { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); border: 1px solid var(--el-border-color-light); border-radius: 6px; overflow: hidden; }
.workflow span { padding: 12px; border-right: 1px solid var(--el-border-color-light); text-align: center; font-size: 13px; }
.workflow span:last-child { border-right: 0; }
.summary { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); border-block: 1px solid var(--el-border-color-light); }
.summary > div { padding: 12px 14px; display: grid; gap: 5px; border-right: 1px solid var(--el-border-color-light); }
.summary > div:last-child { border-right: 0; }
.summary span, small { color: var(--el-text-color-secondary); font-size: 12px; }
.summary strong { overflow-wrap: anywhere; }
.toolbar, .batch-actions, .detail-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.el-table small { display: block; margin-top: 2px; }
.score, .detail-score { font-variant-numeric: tabular-nums; color: var(--el-color-primary); font-weight: 700; }
.detail-score { font-size: 28px; }
h3 { margin: 0 0 5px; }
h4 { margin: 22px 0 10px; }
.metric-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); border: 1px solid var(--el-border-color-light); border-radius: 6px; overflow: hidden; }
.metric-list > div { display: flex; justify-content: space-between; gap: 12px; padding: 10px 12px; border-bottom: 1px solid var(--el-border-color-light); }
.metric-list .risk strong { color: var(--el-color-danger); }
.advanced { margin-top: 18px; }
.advanced p { overflow-wrap: anywhere; }
@media (max-width: 800px) {
  .page-heading { flex-direction: column; }
  .workflow, .summary { grid-template-columns: 1fr; }
  .workflow span, .summary > div { border-right: 0; border-bottom: 1px solid var(--el-border-color-light); text-align: left; }
  .metric-list { grid-template-columns: 1fr; }
}
</style>
