<template>
  <div v-loading="loading" class="page-grid">
    <section class="page-heading">
      <div><h2>候选池</h2><p>用户明确选择或确认推荐的标的；任何推荐都不会自动加入。</p></div>
      <div><el-button :disabled="isDemo" @click="reconcile">安全核对</el-button><el-button type="primary" :disabled="isDemo" @click="dialogVisible = true">添加标的</el-button></div>
    </section>

    <el-alert type="info" :closable="false" show-icon title="移除只撤销当前可移除来源，不会删除推荐、Snapshot、决策、评价或仍受持仓/订单保护的候选。" />

    <el-table :data="rows" size="small" highlight-current-row @row-click="openDetail">
      <el-table-column prop="symbol" label="代码" width="90" />
      <el-table-column prop="name" label="名称" min-width="105" />
      <el-table-column prop="market" label="市场" width="70" />
      <el-table-column label="来源" min-width="160"><template #default="{ row }"><el-tag v-for="source in row.sources" :key="source" size="small">{{ sourceLabel(source) }}</el-tag></template></el-table-column>
      <el-table-column label="推荐" width="95"><template #default="{ row }">{{ row.recommendation_score != null ? Number(row.recommendation_score).toFixed(1) + ' 分' : '—' }}</template></el-table-column>
      <el-table-column prop="status" label="状态" width="105" />
      <el-table-column label="DataQuality" width="125"><template #default="{ row }"><el-tag :type="qualityType(row.dataQuality)">{{ row.dataQuality }}</el-tag></template></el-table-column>
      <el-table-column label="最新 Snapshot" min-width="145"><template #default="{ row }">{{ shortId(row.snapshot?.snapshot_id) }}</template></el-table-column>
      <el-table-column label="最新 Proposal" min-width="150"><template #default="{ row }"><span v-if="row.proposal"><el-tag :type="proposalType(row.proposal.status)" size="small">{{ row.proposal.status }}</el-tag> {{ row.proposal.strategy_id }}</span><span v-else>未生成</span></template></el-table-column>
      <el-table-column label="持仓" width="70"><template #default="{ row }">{{ row.held_account_ids.length ? '是' : '否' }}</template></el-table-column>
      <el-table-column label="冷却" width="105"><template #default="{ row }">{{ row.cooldown_until || '无' }}</template></el-table-column>
      <el-table-column prop="updated_at" label="候选更新时间" min-width="170" />
      <el-table-column label="操作" width="90" fixed="right"><template #default="{ row }"><el-button link type="danger" :disabled="isDemo" @click.stop="remove(row)">移除来源</el-button></template></el-table-column>
    </el-table>
    <el-empty v-if="!loading && !rows.length" description="候选池为空" />

    <el-drawer v-model="detailVisible" size="min(620px, 92vw)" title="候选详情">
      <template v-if="selected">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="标的">{{ selected.name }}（{{ selected.symbol }}）</el-descriptions-item>
          <el-descriptions-item label="状态">{{ selected.status }}</el-descriptions-item>
          <el-descriptions-item label="来源">{{ selected.sources.join('、') }}</el-descriptions-item>
          <el-descriptions-item label="DataQuality">{{ selected.dataQuality }}</el-descriptions-item>
          <el-descriptions-item label="持仓保护">{{ selected.held_account_ids.length ? selected.held_account_ids.length + ' 个账户' : '无' }}</el-descriptions-item>
          <el-descriptions-item label="冷却截止">{{ selected.cooldown_until || '无' }}</el-descriptions-item>
          <el-descriptions-item label="推荐来源" v-if="selected.recommendation_id">
            {{ selected.recommendation_trade_date }} · {{ selected.recommendation_score }} 分
            <router-link :to="`/alphaguard/recommendations?recommendation=${selected.recommendation_id}`">查看原推荐</router-link>
          </el-descriptions-item>
          <el-descriptions-item label="推荐理由" v-if="selected.recommendation_reason_summary">{{ selected.recommendation_reason_summary }}</el-descriptions-item>
        </el-descriptions>
        <h4>最新 EvidenceSnapshot</h4>
        <el-empty v-if="!selected.snapshot" description="尚无正式 Snapshot" />
        <el-descriptions v-else :column="1" border>
          <el-descriptions-item label="对象 ID">{{ selected.snapshot.snapshot_id }}</el-descriptions-item>
          <el-descriptions-item label="交易日">{{ dateOnly(selected.snapshot.trade_date) }}</el-descriptions-item>
          <el-descriptions-item label="Snapshot Schema">{{ selected.snapshot.schema_version }}</el-descriptions-item>
          <el-descriptions-item label="价格版本">{{ selected.snapshot.price_data_version }}</el-descriptions-item>
          <el-descriptions-item label="MarketContext">{{ selected.snapshot.market_context_id || '未引用' }}</el-descriptions-item>
          <el-descriptions-item label="Benchmark Window">{{ benchmarkWindow(selected.snapshot) }}</el-descriptions-item>
          <el-descriptions-item label="Benchmark Manifest">{{ selected.snapshot.benchmark_price_window_manifest_id || 'v1 未锁定' }}</el-descriptions-item>
          <el-descriptions-item label="MarketContext Window">{{ marketContextWindow(selected.snapshot) }}</el-descriptions-item>
          <el-descriptions-item label="MarketContext Manifest">{{ selected.snapshot.market_context_window_manifest_id || 'v1 未锁定' }}</el-descriptions-item>
          <el-descriptions-item label="Evidence Contract"><el-tag :type="evidenceContractStatus(selected.snapshot) === 'COMPLETE' ? 'success' : 'warning'">{{ evidenceContractStatus(selected.snapshot) }}</el-tag></el-descriptions-item>
          <el-descriptions-item label="Immutable Hash">{{ selected.snapshot.immutable_hash }}</el-descriptions-item>
          <el-descriptions-item label="证据引用">{{ evidenceCount(selected.snapshot.raw_refs) }} 条</el-descriptions-item>
        </el-descriptions>
        <h4>最新 QuantProposal</h4>
        <el-empty v-if="!selected.proposal" description="尚无 Proposal" />
        <el-descriptions v-else :column="1" border>
          <el-descriptions-item label="对象 ID">{{ selected.proposal.proposal_id }}</el-descriptions-item>
          <el-descriptions-item label="策略">{{ selected.proposal.strategy_id }} · {{ selected.proposal.strategy_version }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ selected.proposal.status }} / {{ selected.proposal.action_candidate }}</el-descriptions-item>
          <el-descriptions-item label="原因">{{ selected.proposal.reason_codes?.join('；') || selected.proposal.explanation || '—' }}</el-descriptions-item>
          <el-descriptions-item label="Input Hash">{{ selected.proposal.input_hash || '—' }}</el-descriptions-item>
        </el-descriptions>
      </template>
    </el-drawer>

    <el-dialog v-model="dialogVisible" title="添加用户选择候选" width="480px">
      <el-form label-width="90px">
        <el-form-item label="市场"><el-input model-value="CN" disabled /></el-form-item>
        <el-form-item label="股票代码"><el-input v-model.trim="form.symbol" placeholder="例如 600519 或 510300" /></el-form-item>
        <el-form-item label="名称"><el-input v-model.trim="form.name" placeholder="可选" /></el-form-item>
        <el-form-item label="优先级"><el-slider v-model="form.priority" :min="0" :max="100" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :disabled="!form.symbol" @click="add">确认添加</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { alphaguardApi, type CandidateEntry, type EvidenceSnapshotSummary, type QuantProposalSummary } from '@/api/alphaguard'

type CandidateRow = CandidateEntry & { proposal: QuantProposalSummary | null; snapshot: EvidenceSnapshotSummary | null; dataQuality: string }
const loading = ref(false)
const isDemo = import.meta.env.VITE_ALPHAGUARD_DEMO === 'true'
const dialogVisible = ref(false)
const detailVisible = ref(false)
const rows = ref<CandidateRow[]>([])
const selected = ref<CandidateRow | null>(null)
const form = reactive({ symbol: '', name: '', priority: 50 })

async function load() {
  loading.value = true
  try {
    const [candidateRes, proposalRes] = await Promise.all([
      alphaguardApi.candidates({ market: 'CN', limit: 500 }),
      alphaguardApi.quantProposals({ limit: 500 })
    ])
    const proposals = proposalRes.data.items
    const latestByCandidate = new Map<string, QuantProposalSummary>()
    for (const proposal of proposals) if (proposal.candidate_id && !latestByCandidate.has(proposal.candidate_id)) latestByCandidate.set(proposal.candidate_id, proposal)
    rows.value = await Promise.all(candidateRes.data.items.map(async candidate => {
      const proposal = latestByCandidate.get(candidate.candidate_id) || null
      const snapshotId = proposal?.snapshot_id || candidate.latest_snapshot_id
      const snapshot = snapshotId ? (await alphaguardApi.evidenceSnapshot(snapshotId)).data : null
      return { ...candidate, proposal, snapshot, dataQuality: snapshot?.data_quality.status || 'NOT_AVAILABLE' }
    }))
  } catch (error: any) { ElMessage.error(error?.message || '加载候选池失败') }
  finally { loading.value = false }
}
function openDetail(row: CandidateRow) { selected.value = row; detailVisible.value = true }
async function add() { await alphaguardApi.addCandidate({ symbol: form.symbol, name: form.name || undefined, priority: form.priority, market: 'CN' }); dialogVisible.value = false; form.symbol = ''; form.name = ''; ElMessage.success('USER_SELECTED 来源已合并'); await load() }
async function remove(row: Record<string, unknown>) { const candidate = row as unknown as CandidateRow; await ElMessageBox.confirm(`仅移除 ${candidate.symbol} 的 USER_SELECTED 来源？历史对象不会删除。`, '安全移除', { type: 'warning' }); const result = (await alphaguardApi.removeCandidate(candidate.candidate_id)).data; result.monitoring_retained ? ElMessage.warning(`候选继续保留：${result.retention_reasons.join('；')}`) : ElMessage.success('用户选择来源已移除'); await load() }
async function reconcile() { const result = await alphaguardApi.reconcileCandidates(); ElMessage.success(`核对完成：${JSON.stringify(result.data)}`); await load() }
function shortId(value?: string) { return value ? `${value.slice(0, 8)}…` : '未生成' }
function dateOnly(value?: string) { return value?.slice(0, 10) || '—' }
function evidenceCount(refs: Record<string, string[]>) { return Object.values(refs).reduce((total, items) => total + items.length, 0) }
function benchmarkCount(snapshot: EvidenceSnapshotSummary) { return snapshot.actual_benchmark_count ?? snapshot.raw_refs.benchmark_prices?.length ?? 0 }
function benchmarkWindow(snapshot: EvidenceSnapshotSummary) { return `${benchmarkCount(snapshot)}/${snapshot.required_benchmark_count ?? 61}` }
function marketContextWindow(snapshot: EvidenceSnapshotSummary) { return snapshot.market_context_window_manifest_id ? '121/121' : '未锁定' }
function evidenceContractStatus(snapshot: EvidenceSnapshotSummary) {
  if (snapshot.evidence_contract_status) return snapshot.evidence_contract_status
  return benchmarkCount(snapshot) < 61 ? 'LEGACY_EVIDENCE_INCOMPLETE' : 'LEGACY_CONTRACT_UNVERIFIED'
}
function qualityType(status: string) { return status === 'PASS' ? 'success' : status === 'FAIL' ? 'danger' : 'warning' }
function proposalType(status: string) { return status === 'TRIGGERED' ? 'success' : status === 'INSUFFICIENT_DATA' ? 'warning' : status === 'REJECTED' ? 'danger' : 'info' }
function sourceLabel(source: string) { return ({ USER_SELECTED: '用户手工添加', POSITION_REQUIRED: '持仓强制保留', SYSTEM_RECOMMENDED_CONFIRMED: '系统推荐后人工确认', SYSTEM_SCREENED: '系统筛选', EVENT_TRIGGERED: '事件触发', EXPERIMENT_ASSIGNED: '实验分配' } as Record<string, string>)[source] || source }
onMounted(load)
</script>

<style scoped>
.page-grid { display: grid; gap: 16px; }
.page-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.page-heading h2 { margin: 0 0 4px; font-size: 22px; }
.page-heading p { margin: 0; color: var(--el-text-color-secondary); }
h4 { margin: 22px 0 10px; }
@media (max-width: 700px) { .page-heading { flex-direction: column; } }
</style>
