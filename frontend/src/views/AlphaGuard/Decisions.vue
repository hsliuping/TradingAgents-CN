<template>
  <div v-loading="loading" class="page-grid">
    <section class="page-heading">
      <div><h2>决策中心</h2><p>从不可变证据到订单意图的真实到达路径。</p></div>
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </section>
    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="未调用、未到达和数据不足是独立状态；模型失败不会显示为 HOLD，前端也不会补出 PASS 或交易信号。"
    />

    <el-table :data="timelines" size="small" highlight-current-row @row-click="selectTimeline">
      <el-table-column prop="tradeDate" label="交易日" width="110" />
      <el-table-column prop="symbol" label="标的" width="90" />
      <el-table-column label="DataQuality" width="120"><template #default="{ row }"><el-tag :type="stageType(row.stages[0].status)">{{ row.stages[0].status }}</el-tag></template></el-table-column>
      <el-table-column label="Regime" width="165"><template #default="{ row }"><el-tag :type="stageType(row.regime.calculation_status)">{{ row.regime.calculation_status }}</el-tag></template></el-table-column>
      <el-table-column label="Proposal" min-width="230"><template #default="{ row }"><span v-for="item in row.proposalStatuses" :key="item.status" class="status-chip"><el-tag :type="stageType(item.status)" size="small">{{ item.status }} {{ item.count }}</el-tag></span></template></el-table-column>
      <el-table-column label="模型/风控" min-width="180"><template #default="{ row }">{{ row.modelReached ? '已到达' : '未到达' }}</template></el-table-column>
      <el-table-column label="OrderIntent" width="125"><template #default="{ row }">{{ row.intentReached ? '已创建' : '未创建' }}</template></el-table-column>
      <el-table-column prop="snapshot.snapshot_id" label="Snapshot ID" min-width="220" />
    </el-table>
    <el-empty v-if="!loading && !timelines.length" description="尚无真实决策链对象" />

    <section v-if="selected" class="timeline-section">
      <div class="section-header"><div><strong>{{ selected.symbol }} · {{ selected.tradeDate }}</strong><span>Snapshot {{ selected.snapshot.snapshot_id }}</span></div><el-tag>{{ selected.stages.length }} 个阶段</el-tag></div>
      <el-timeline>
        <el-timeline-item v-for="stage in selected.stages" :key="stage.key" :timestamp="stage.createdAt || '未创建'" :type="timelineType(stage.status)">
          <button class="stage-button" type="button" @click="inspectStage(stage)">
            <span class="stage-name">{{ stage.label }}</span>
            <el-tag :type="stageType(stage.status)" size="small">{{ stage.status }}</el-tag>
            <span class="stage-reason">{{ stage.reason }}</span>
          </button>
        </el-timeline-item>
      </el-timeline>
    </section>

    <el-drawer v-model="detailVisible" size="min(680px, 94vw)" :title="stageDetail?.label || '阶段详情'">
      <template v-if="stageDetail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="状态">{{ stageDetail.status }}</el-descriptions-item>
          <el-descriptions-item label="原因">{{ stageDetail.reason }}</el-descriptions-item>
          <el-descriptions-item label="对象 ID">{{ stageDetail.objectIds.join('、') || '未创建' }}</el-descriptions-item>
          <el-descriptions-item label="输入/对象 Hash">{{ stageDetail.hashes.join('、') || '—' }}</el-descriptions-item>
          <el-descriptions-item label="版本">{{ stageDetail.versions.join('、') || '—' }}</el-descriptions-item>
          <el-descriptions-item label="Trace">{{ stageDetail.traceIds.join('、') || '未记录' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ stageDetail.createdAt || '未创建' }}</el-descriptions-item>
          <el-descriptions-item label="证据引用">{{ stageDetail.evidenceCount }}</el-descriptions-item>
        </el-descriptions>
        <h4>原始只读对象</h4>
        <pre>{{ pretty(stageDetail.payload) }}</pre>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { alphaguardApi, type DecisionEvent, type EvidenceSnapshotSummary, type FactorResultSummary, type QuantProposalSummary, type RegimeResultSummary } from '@/api/alphaguard'

interface Stage { key: string; label: string; status: string; reason: string; objectIds: string[]; hashes: string[]; versions: string[]; traceIds: string[]; createdAt: string; evidenceCount: number; payload: unknown }
interface Timeline { symbol: string; tradeDate: string; snapshot: EvidenceSnapshotSummary; factors: FactorResultSummary[]; regime: RegimeResultSummary; proposals: QuantProposalSummary[]; proposalStatuses: Array<{status:string;count:number}>; stages: Stage[]; modelReached: boolean; intentReached: boolean }
const loading = ref(false)
const timelines = ref<Timeline[]>([])
const selected = ref<Timeline | null>(null)
const stageDetail = ref<Stage | null>(null)
const detailVisible = ref(false)
const pretty = (value: unknown) => JSON.stringify(value, null, 2)

function stage(key: string, label: string, status: string, reason: string, payload: unknown, options: Partial<Stage> = {}): Stage {
  return { key, label, status, reason, payload, objectIds: [], hashes: [], versions: [], traceIds: [], createdAt: '', evidenceCount: 0, ...options }
}
function countRefs(refs: Record<string, string[]> = {}) { return Object.values(refs).reduce((n, items) => n + items.length, 0) }
function benchmarkCount(snapshot: EvidenceSnapshotSummary) { return snapshot.actual_benchmark_count ?? snapshot.raw_refs.benchmark_prices?.length ?? 0 }
function evidenceContractStatus(snapshot: EvidenceSnapshotSummary) {
  if (snapshot.evidence_contract_status) return snapshot.evidence_contract_status
  return benchmarkCount(snapshot) < 61 ? 'LEGACY_EVIDENCE_INCOMPLETE' : 'LEGACY_CONTRACT_UNVERIFIED'
}
function proposalCounts(items: QuantProposalSummary[]) { const counts: Record<string, number> = {}; for (const item of items) counts[item.status] = (counts[item.status] || 0) + 1; return Object.entries(counts).map(([status,count]) => ({status,count})) }
function missingReason(proposals: QuantProposalSummary[]) { const reasons = [...new Set(proposals.flatMap(item => item.reason_codes || []))]; return reasons.join('；') || '没有可进入模型链的 Proposal' }
function eventOptions(event: DecisionEvent | undefined, objectId: string | null | undefined): Partial<Stage> {
  if (!event) return {}
  return {
    objectIds: objectId ? [objectId] : [],
    hashes: [event.input_hash, event.output_hash].filter((value): value is string => Boolean(value)),
    versions: event.component_version ? [event.component_version] : [],
    traceIds: event.trace_id ? [event.trace_id] : [],
    createdAt: event.created_at || '',
    evidenceCount: event.evidence_refs?.length || 0
  }
}

async function load() {
  loading.value = true
  try {
    const [candidateRes, proposalRes, eventRes] = await Promise.all([alphaguardApi.candidates({ limit: 500 }), alphaguardApi.quantProposals({ limit: 500 }), alphaguardApi.decisionEvents({ limit: 500 })])
    const groups = new Map<string, QuantProposalSummary[]>()
    for (const proposal of proposalRes.data.items) groups.set(proposal.snapshot_id, [...(groups.get(proposal.snapshot_id) || []), proposal])
    for (const candidate of candidateRes.data.items) if (candidate.latest_snapshot_id && !groups.has(candidate.latest_snapshot_id)) groups.set(candidate.latest_snapshot_id, [])
    timelines.value = await Promise.all([...groups.entries()].map(async ([snapshotId, proposals]) => {
      const [snapshotRes, factorRes, regimeRes] = await Promise.all([alphaguardApi.evidenceSnapshot(snapshotId), alphaguardApi.factorResults(snapshotId), alphaguardApi.regime(snapshotId)])
      return buildTimeline(snapshotRes.data, factorRes.data.items, regimeRes.data, proposals, eventRes.data.items.filter(item => item.snapshot_id === snapshotId))
    }))
    timelines.value.sort((a,b) => `${b.tradeDate}:${b.symbol}`.localeCompare(`${a.tradeDate}:${a.symbol}`))
    if (!selected.value && timelines.value.length) selected.value = timelines.value[0]
  } catch (error: any) { ElMessage.error(error?.message || '加载决策链失败') }
  finally { loading.value = false }
}

function buildTimeline(snapshot: EvidenceSnapshotSummary, factors: FactorResultSummary[], regime: RegimeResultSummary, proposals: QuantProposalSummary[], events: DecisionEvent[]): Timeline {
  const normalEvent = events.find(item => item.plan_id)
  const topEvent = events.find(item => item.review_id)
  const consensusEvent = events.find(item => item.consensus_id)
  const riskEvent = events.find(item => item.risk_decision_id)
  const intentEvent = events.find(item => item.intent_id)
  const proposalStatus = proposals.some(item => item.status === 'TRIGGERED') ? 'TRIGGERED' : proposals.some(item => item.status === 'INSUFFICIENT_DATA') ? 'INSUFFICIENT_DATA' : proposals[0]?.status || 'NOT_CREATED'
  const proposalReason = missingReason(proposals)
  const stages: Stage[] = [
    stage('quality','DataQuality',snapshot.data_quality.status,snapshot.data_quality.blocking_reasons.join('；') || '完整性、时效性与一致性检查通过',snapshot.data_quality,{objectIds:[],createdAt:snapshot.data_quality.checked_at}),
    stage('snapshot','EvidenceSnapshot','CREATED','使用持久化版本与正式引用创建',snapshot,{objectIds:[snapshot.snapshot_id],hashes:[snapshot.immutable_hash],versions:[snapshot.price_data_version,snapshot.financial_data_version,snapshot.news_data_version],createdAt:snapshot.created_at,evidenceCount:countRefs(snapshot.raw_refs)}),
    stage('evidence-contract','Evidence Contract',evidenceContractStatus(snapshot),`Snapshot ${snapshot.schema_version}；Benchmark Window ${benchmarkCount(snapshot)}/${snapshot.required_benchmark_count ?? 61}；MarketContext Window ${snapshot.market_context_window_manifest_id ? '121/121' : '未锁定'}`,{schema_version:snapshot.schema_version,benchmark_price_window_manifest_id:snapshot.benchmark_price_window_manifest_id,market_context_window_manifest_id:snapshot.market_context_window_manifest_id,evidence_contract_status:evidenceContractStatus(snapshot)},{objectIds:[snapshot.benchmark_price_window_manifest_id,snapshot.market_context_window_manifest_id].filter((value): value is string => Boolean(value)),hashes:[snapshot.benchmark_price_window_manifest_hash,snapshot.market_context_window_manifest_hash].filter((value): value is string => Boolean(value))}),
    stage('factor','Factor',factors.length ? 'CALCULATED' : 'NOT_REACHED',factors.length ? `${factors.length} 个版本锁定 FactorResult` : '没有 FactorResult',factors,{objectIds:factors.map(item => item.factor_result_id),hashes:factors.map(item => item.input_hash),versions:[...new Set(factors.map(item => `${item.factor_id}@${item.factor_version}`))],createdAt:factors[0]?.calculated_at || ''}),
    stage('context','MarketContext',snapshot.market_context_id ? 'REFERENCED' : 'NOT_REACHED',snapshot.market_context_id ? 'Snapshot 已锁定生产 MarketContext' : 'Snapshot 未引用 MarketContext',{market_context_id:snapshot.market_context_id},{objectIds:snapshot.market_context_id ? [snapshot.market_context_id] : []}),
    stage('regime','MarketRegime',regime.calculation_status,regime.evidence.join('；') || String(regime.regime || '没有可用 Regime'),regime,{objectIds:[regime.regime_result_id],hashes:[regime.input_hash],versions:[regime.regime_version],createdAt:regime.calculated_at}),
    stage('proposal','QuantProposal',proposalStatus,proposalReason,proposals,{objectIds:proposals.map(item => item.proposal_id),hashes:proposals.map(item => item.input_hash || '').filter(Boolean),versions:[...new Set(proposals.map(item => item.strategy_version))],createdAt:proposals[0]?.created_at || '',evidenceCount:proposals.reduce((n,item) => n + (item.evidence_refs?.length || 0),0)}),
    stage('normal','NormalTradePlan',normalEvent?.status || (normalEvent ? 'CREATED' : 'NOT_REACHED'),normalEvent?.reason || proposalReason,normalEvent || null,eventOptions(normalEvent, normalEvent?.plan_id)),
    stage('top','TopReviewDecision',topEvent?.status || (topEvent ? 'CREATED' : 'NOT_REACHED'),topEvent?.reason || 'NormalTradePlan 未形成，Top 未调用',topEvent || null,eventOptions(topEvent, topEvent?.review_id)),
    stage('consensus','ConsensusDecision',consensusEvent?.status || (consensusEvent ? 'CREATED' : 'NOT_REACHED'),consensusEvent?.reason || 'Normal/Top 未同时到达，Consensus 未调用',consensusEvent || null,eventOptions(consensusEvent, consensusEvent?.consensus_id)),
    stage('risk','HardRiskDecision',riskEvent?.status || (riskEvent ? 'CREATED' : 'NOT_REACHED'),riskEvent?.reason || 'Consensus 未通过，HardRisk 未调用',riskEvent || null,eventOptions(riskEvent, riskEvent?.risk_decision_id)),
    stage('intent','OrderIntent',intentEvent?.status || (intentEvent ? 'CREATED' : 'NOT_CREATED'),intentEvent?.reason || '没有完整通过量化、模型、一致性与硬风控的合法方案',intentEvent || null,eventOptions(intentEvent, intentEvent?.intent_id))
  ]
  return { symbol:snapshot.symbol, tradeDate:snapshot.trade_date.slice(0,10), snapshot, factors, regime, proposals, proposalStatuses:proposalCounts(proposals), stages, modelReached:Boolean(normalEvent), intentReached:Boolean(intentEvent) }
}
function selectTimeline(row: Timeline) { selected.value = row }
function inspectStage(value: Stage) { stageDetail.value = value; detailVisible.value = true }
function stageType(status: string) { if (['PASS','CREATED','CALCULATED','REFERENCED','TRIGGERED','COMPLETE'].includes(status)) return 'success'; if (['FAIL','REJECTED','MODEL_FAILED','HARD_RISK_REJECT'].includes(status)) return 'danger'; if (['INSUFFICIENT_DATA','LEGACY_EVIDENCE_INCOMPLETE','LEGACY_CONTRACT_UNVERIFIED'].includes(status)) return 'warning'; return 'info' }
function timelineType(status: string) { return stageType(status) === 'success' ? 'success' : stageType(status) === 'danger' ? 'danger' : stageType(status) === 'warning' ? 'warning' : 'info' }
onMounted(load)
</script>

<style scoped>
.page-grid { display: grid; gap: 16px; }
.page-heading, .section-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.page-heading h2 { margin: 0 0 4px; font-size: 22px; }.page-heading p { margin: 0; color: var(--el-text-color-secondary); }
.status-chip { margin-right: 6px; }.timeline-section { padding: 20px 0 0; border-top: 1px solid var(--el-border-color-light); }.section-header { margin-bottom: 18px; }.section-header div { display: grid; gap: 4px; }.section-header span { color: var(--el-text-color-secondary); font-size: 13px; }
.stage-button { width: 100%; display: grid; grid-template-columns: minmax(150px, 220px) auto 1fr; align-items: center; gap: 12px; border: 0; background: transparent; text-align: left; cursor: pointer; padding: 4px 0 12px; }.stage-name { font-weight: 600; }.stage-reason { color: var(--el-text-color-secondary); overflow-wrap: anywhere; }
pre { max-height: 520px; overflow: auto; padding: 12px; background: var(--el-fill-color-light); border-radius: 6px; white-space: pre-wrap; overflow-wrap: anywhere; }
@media (max-width: 700px) { .stage-button { grid-template-columns: 1fr auto; }.stage-reason { grid-column: 1 / -1; }.page-heading { flex-direction: column; } }
</style>
