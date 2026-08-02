<template>
  <div class="challenger-page">
    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="挑战者仅进行模拟交易，不会连接券商或执行真实交易，也不会自动替换当前 Champion。"
    />

    <section class="status-band">
      <div><span>运行能力</span><strong>{{ challengerReady ? '已就绪' : '未就绪' }}</strong></div>
      <div><span>活动挑战者</span><strong>{{ activeChallenger ? '1' : '0' }}</strong></div>
      <div><span>挑战者总数</span><strong>{{ challengers.length }}</strong></div>
      <div><span>模拟账户</span><strong>{{ selected?.cash_available == null ? '未启用' : money(selected.cash_available) }}</strong></div>
    </section>

    <section class="workflow-band">
      <div class="section-title">
        <div>
          <h2>挑战者流程</h2>
          <p>{{ nextStepText }}</p>
        </div>
        <div class="header-actions">
          <el-button :loading="loading" :icon="Refresh" circle title="刷新" @click="refresh" />
          <el-button v-if="authStore.isAdmin" type="primary" :icon="Plus" @click="openCreate">新建挑战者</el-button>
        </div>
      </div>
      <el-steps :active="activeStep" finish-status="success" align-center>
        <el-step title="选择 Champion" />
        <el-step title="选择变量" />
        <el-step title="填写变更" />
        <el-step title="历史回放" />
        <el-step title="样本外验证" />
        <el-step title="Shadow 观察" />
        <el-step title="模拟挑战" />
        <el-step title="查看对比" />
        <el-step title="人工评审" />
      </el-steps>
    </section>

    <section class="content-grid">
      <aside class="challenger-list">
        <div class="list-heading">挑战者</div>
        <button
          v-for="item in challengers"
          :key="item.experiment_id"
          type="button"
          :class="['challenger-item', { selected: selected?.experiment_id === item.experiment_id }]"
          @click="select(item)"
        >
          <span class="item-main"><strong>{{ item.name }}</strong><small>{{ item.change_summary || item.primary_variable_path }}</small></span>
          <el-tag :type="statusType(item.status)" size="small">{{ statusText(item.status) }}</el-tag>
        </button>
        <el-empty v-if="!loading && challengers.length === 0" description="尚未创建挑战者" :image-size="72" />
      </aside>

      <main class="challenger-detail">
        <el-empty v-if="!selected" description="选择一个挑战者查看运行状态" />
        <template v-else>
          <div class="detail-heading">
            <div>
              <div class="title-line">
                <h2>{{ selected.name }}</h2>
                <el-tag :type="statusType(selected.status)">{{ statusText(selected.status) }}</el-tag>
              </div>
              <p>{{ selected.change_summary || '尚未填写变更摘要' }}</p>
            </div>
            <div v-if="authStore.isAdmin" class="header-actions">
              <el-button
                type="primary"
                :disabled="selected.status !== 'SHADOW' || !activationDate"
                :loading="submitting"
                @click="activate"
              >启用模拟挑战者</el-button>
              <el-button
                :disabled="selected.assignment_status !== 'ACTIVE'"
                :loading="submitting"
                @click="pause"
              >暂停</el-button>
              <el-button
                type="danger"
                plain
                :disabled="selected.status !== 'SUSPENDED'"
                :loading="submitting"
                @click="retire"
              >退役</el-button>
            </div>
          </div>

          <div class="metrics-grid">
            <div><span>可用现金</span><strong>{{ money(selected.cash_available) }}</strong></div>
            <div><span>持仓</span><strong>{{ selected.position_count }}</strong></div>
            <div><span>订单 / 成交</span><strong>{{ selected.order_count }} / {{ selected.fill_count }}</strong></div>
            <div><span>累计收益</span><strong>{{ percent(selected.net_return) }}</strong></div>
            <div><span>累计费用</span><strong>{{ money(selected.total_fees) }}</strong></div>
            <div><span>最近运行</span><strong>{{ selected.last_run_status ? runStatusText(selected.last_run_status) : '尚未运行' }}</strong></div>
          </div>

          <div class="action-strip">
            <div class="date-control">
              <span>启用日期</span>
              <el-date-picker v-model="activationDate" value-format="YYYY-MM-DD" placeholder="选择交易日" />
            </div>
            <el-button
              :disabled="!canBacktest"
              :loading="submitting"
              @click="backtest"
            >开始历史回放</el-button>
            <el-button
              :disabled="!canShadow"
              :loading="submitting"
              @click="startShadow"
            >开始 Shadow 观察</el-button>
            <el-button :disabled="!comparison" @click="activeTab = 'comparison'">查看 Champion 对比</el-button>
            <el-button
              v-if="authStore.isAdmin"
              type="primary"
              plain
              :disabled="!canSubmitReview"
              :loading="submitting"
              @click="submitReview"
            >提交人工评审</el-button>
          </div>
          <p v-if="actionBlockReason" class="action-reason">{{ actionBlockReason }}</p>

          <el-tabs v-model="activeTab" class="detail-tabs">
            <el-tab-pane label="运行记录" name="runs">
              <el-table :data="runs" size="small">
                <el-table-column prop="trading_date" label="运行日期" width="120" />
                <el-table-column prop="symbol" label="股票" width="100" />
                <el-table-column label="结果" width="130">
                  <template #default="{ row }">{{ runStatusText(String(row.status || '')) }}</template>
                </el-table-column>
                <el-table-column prop="terminal_stage" label="到达阶段" min-width="160" />
                <el-table-column prop="failure_code" label="异常" min-width="180" />
              </el-table>
              <el-empty v-if="runs.length === 0" description="尚无挑战者运行" />
            </el-tab-pane>
            <el-tab-pane label="决策链" name="decisions">
              <el-table :data="decisions" size="small">
                <el-table-column label="阶段" width="170">
                  <template #default="{ row }">{{ objectTypeText(String(row.object_type || '')) }}</template>
                </el-table-column>
                <el-table-column prop="created_at" label="时间" min-width="170" />
                <el-table-column label="状态" min-width="180">
                  <template #default="{ row }">{{ payloadStatus(row) }}</template>
                </el-table-column>
              </el-table>
              <el-empty v-if="decisions.length === 0" description="尚无决策对象" />
            </el-tab-pane>
            <el-tab-pane label="订单与成交" name="orders">
              <el-descriptions :column="3" border>
                <el-descriptions-item label="订单意图">{{ orders.intents.length }}</el-descriptions-item>
                <el-descriptions-item label="模拟订单">{{ orders.orders.length }}</el-descriptions-item>
                <el-descriptions-item label="模拟成交">{{ orders.fills.length }}</el-descriptions-item>
              </el-descriptions>
              <el-table :data="orders.orders" size="small" class="sub-table">
                <el-table-column prop="symbol" label="股票" width="100" />
                <el-table-column prop="side" label="方向" width="90" />
                <el-table-column prop="quantity" label="数量" width="100" />
                <el-table-column prop="status" label="状态" min-width="120" />
                <el-table-column prop="earliest_execute_at" label="最早执行" min-width="170" />
              </el-table>
            </el-tab-pane>
            <el-tab-pane label="评价" name="evaluation">
              <el-descriptions :column="3" border>
                <el-descriptions-item label="评价对象">{{ evaluationCount('subjects') }}</el-descriptions-item>
                <el-descriptions-item label="已成熟标签">{{ Number(evaluation.mature_label_count || 0) }}</el-descriptions-item>
                <el-descriptions-item label="待观察标签">{{ Number(evaluation.pending_label_count || 0) }}</el-descriptions-item>
              </el-descriptions>
            </el-tab-pane>
            <el-tab-pane label="与 Champion 对比" name="comparison">
              <el-descriptions v-if="comparison" :column="2" border>
                <el-descriptions-item label="挑战者收益">{{ percent(comparison.challenger_return) }}</el-descriptions-item>
                <el-descriptions-item label="Champion 收益">{{ percent(comparison.champion_return) }}</el-descriptions-item>
                <el-descriptions-item label="收益差">{{ percent(comparison.return_difference) }}</el-descriptions-item>
                <el-descriptions-item label="费用差">{{ money(comparison.cost_difference) }}</el-descriptions-item>
                <el-descriptions-item label="回撤差">{{ percent(comparison.drawdown_difference) }}</el-descriptions-item>
                <el-descriptions-item label="收益回撤比差">{{ decimalMetric(comparison.return_drawdown_ratio_difference) }}</el-descriptions-item>
                <el-descriptions-item label="交易次数差">{{ countDifference(comparison.trade_count_difference) }}</el-descriptions-item>
                <el-descriptions-item label="换手率差">{{ percent(comparison.turnover_difference) }}</el-descriptions-item>
                <el-descriptions-item label="不同市场状态表现">{{ regimeComparisonText(comparison.regime_difference) }}</el-descriptions-item>
                <el-descriptions-item label="极端交易依赖">{{ outlierDependencyText(comparison.extreme_trade_dependency) }}</el-descriptions-item>
              </el-descriptions>
              <el-empty v-else description="完成足够运行后生成对比" />
              <el-alert
                v-if="selected.validation_only"
                class="review-note"
                type="info"
                :closable="false"
                title="系统验证实验不可进入人工晋升评审。"
              />
              <el-alert
                v-else-if="comparison && !canSubmitReview"
                class="review-note"
                type="warning"
                :closable="false"
                :title="reviewBlockReason"
              />
            </el-tab-pane>
            <el-tab-pane label="高级信息" name="advanced">
              <el-descriptions :column="1" border>
                <el-descriptions-item label="实验 ID">{{ selected.experiment_id }}</el-descriptions-item>
                <el-descriptions-item label="挑战版本">{{ selected.challenger_version_id || '未登记' }}</el-descriptions-item>
                <el-descriptions-item label="Champion 版本">{{ selected.baseline_champion_version || '未登记' }}</el-descriptions-item>
                <el-descriptions-item label="配置 Hash">{{ selected.config_hash || '未登记' }}</el-descriptions-item>
                <el-descriptions-item label="账户 ID">{{ selected.account_id || '未启用' }}</el-descriptions-item>
                <el-descriptions-item label="最近失败代码">{{ selected.last_failure_code || '无' }}</el-descriptions-item>
              </el-descriptions>
            </el-tab-pane>
          </el-tabs>
        </template>
      </main>
    </section>

    <el-dialog v-model="createVisible" title="新建挑战者" width="680px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="挑战者名称"><el-input v-model="createForm.name" placeholder="例如：低波动因子权重验证" /></el-form-item>
        <el-form-item label="当前 Champion">
          <el-select v-model="createForm.champion_slot_id" filterable placeholder="选择对照 Champion" @change="syncChampion">
            <el-option
              v-for="item in options.champions"
              :key="item.champion_slot_id"
              :label="`${componentText(item.component_type)} · ${item.component_key}`"
              :value="item.champion_slot_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="挑战版本">
          <el-select v-model="createForm.challenger_version_ref" filterable placeholder="选择同一组件的实验版本">
            <el-option v-for="item in challengerVersions" :key="item.version_ref" :label="item.version_ref" :value="item.version_ref" />
          </el-select>
        </el-form-item>
        <el-form-item label="唯一变更字段"><el-input v-model="createForm.primary_variable_path" placeholder="例如 factor_weights.MOMENTUM_20D" /></el-form-item>
        <el-form-item label="变更说明"><el-input v-model="createForm.description" type="textarea" :rows="2" placeholder="说明只改变了什么" /></el-form-item>
        <el-form-item label="验证假设"><el-input v-model="createForm.hypothesis" type="textarea" :rows="2" placeholder="说明希望验证的结果和风险" /></el-form-item>
        <el-form-item label="仅用于系统验证"><el-switch v-model="createForm.validation_only" /><span class="field-note">启用后永远不能进入晋升流程</span></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!createReady" :loading="submitting" @click="create">创建草稿</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import {
  alphaguardExperimentApi,
  type ChallengerOptions,
  type ChallengerSummary
} from '@/api/alphaguardExperiments'
import { alphaguardOperationsApi } from '@/api/alphaguardOperations'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const loading = ref(false)
const submitting = ref(false)
const createVisible = ref(false)
const challengers = ref<ChallengerSummary[]>([])
const selected = ref<ChallengerSummary | null>(null)
const options = ref<ChallengerOptions>({ champions: [], component_versions: [], change_types: [] })
const runs = ref<Record<string, unknown>[]>([])
const decisions = ref<Record<string, unknown>[]>([])
const orders = ref<{ intents: Record<string, unknown>[]; orders: Record<string, unknown>[]; fills: Record<string, unknown>[] }>({ intents: [], orders: [], fills: [] })
const evaluation = ref<Record<string, any>>({})
const comparison = ref<Record<string, any> | null>(null)
const challengerReady = ref(false)
const activeChallenger = ref(false)
const activationDate = ref('')
const activeTab = ref('runs')
const detail = ref<Record<string, any> | null>(null)
const createForm = reactive({
  name: '', champion_slot_id: '', component_type: '', component_key: '',
  baseline_version_ref: '', challenger_version_ref: '', primary_variable_path: '',
  description: '', hypothesis: '', validation_only: false
})

const challengerVersions = computed(() => options.value.component_versions.filter(item =>
  item.component_type === createForm.component_type &&
  item.component_key === createForm.component_key &&
  item.version_ref !== createForm.baseline_version_ref &&
  item.execution_supported
))
const createReady = computed(() => Boolean(
  createForm.name && createForm.champion_slot_id && createForm.challenger_version_ref &&
  createForm.primary_variable_path && createForm.description && createForm.hypothesis
))
const latestManifestId = computed(() => String(detail.value?.dataset_manifests?.[0]?.dataset_manifest_id || ''))
const canBacktest = computed(() => Boolean(selected.value && latestManifestId.value && ['DRAFT', 'EXPERIMENT'].includes(selected.value.status)))
const canShadow = computed(() => Boolean(selected.value?.status === 'BACKTESTED' && latestManifestId.value))
const comparisonReportId = computed(() => String(comparison.value?.comparison_report_id || ''))
const riskReviews = computed(() => Array.isArray(detail.value?.risk_reviews) ? detail.value.risk_reviews : [])
const canSubmitReview = computed(() => Boolean(
  authStore.isAdmin && selected.value && !selected.value.validation_only &&
  comparisonReportId.value && comparison.value?.comparison_status === 'READY' &&
  riskReviews.value.length === 0
))
const reviewBlockReason = computed(() => {
  if (selected.value?.validation_only) return '系统验证实验不可进入人工晋升评审。'
  if (!comparisonReportId.value) return '需要先生成完整的 Champion 对比报告。'
  if (comparison.value?.comparison_status !== 'READY') return '对比证据尚未满足人工评审门槛。'
  if (riskReviews.value.length > 0) return '人工评审已提交，请在实验治理中查看审查状态。'
  return '仅管理员可以提交人工评审。'
})
const activeStep = computed(() => {
  const status = selected.value?.status
  if (!status) return 0
  if (status === 'DRAFT') return 3
  if (status === 'EXPERIMENT') return 3
  if (status === 'BACKTESTED') return 5
  if (status === 'SHADOW') return 6
  if (status === 'CHALLENGER') return 7
  if (status === 'SUSPENDED' || status === 'DEGRADED') return 7
  if (status === 'RETIRED') return 9
  return 3
})
const nextStepText = computed(() => {
  if (!selected.value) return challengers.value.length ? '选择一个挑战者继续' : '下一步：新建第一个挑战者'
  if (!latestManifestId.value && ['DRAFT', 'EXPERIMENT'].includes(selected.value.status)) return '当前缺少：历史验证数据集；请先在实验数据集中准备不可变样本'
  if (selected.value.status === 'DRAFT') return '下一步：验证实验定义并开始历史回放'
  if (selected.value.status === 'EXPERIMENT') return '下一步：开始历史回放'
  if (selected.value.status === 'BACKTESTED') return '下一步：开始 Shadow 观察'
  if (selected.value.status === 'SHADOW') return '下一步：选择交易日并启用模拟挑战者'
  if (selected.value.status === 'CHALLENGER') return '模拟挑战正在运行；可查看决策、订单和评价'
  if (selected.value.status === 'SUSPENDED') return '挑战者已暂停；不会产生新任务或新订单'
  return `当前状态：${statusText(selected.value.status)}`
})
const actionBlockReason = computed(() => {
  if (!selected.value) return ''
  if (!latestManifestId.value && ['DRAFT', 'EXPERIMENT', 'BACKTESTED'].includes(selected.value.status)) return '历史回放和 Shadow 需要先准备不可变数据集。'
  if (selected.value.status === 'SHADOW' && !activationDate.value) return '启用前请选择持久化交易日历中的交易日。'
  return ''
})

function statusText(value: string) {
  return ({ DRAFT: '草稿', EXPERIMENT: '实验中', BACKTESTED: '已回测', SHADOW: '影子观察', CHALLENGER: '模拟挑战中', DEGRADED: '运行异常', SUSPENDED: '已暂停', RETIRED: '已退役' } as Record<string, string>)[value] || value
}
function statusType(value: string) {
  if (value === 'CHALLENGER') return 'success'
  if (value === 'DEGRADED') return 'danger'
  if (value === 'SUSPENDED' || value === 'RETIRED') return 'info'
  return 'warning'
}
function runStatusText(value: string) { return ({ COMPLETED: '完成', BLOCKED: '安全停止', FAILED: '失败', RUNNING: '运行中', CREATED: '待运行' } as Record<string, string>)[value] || value }
function componentText(value: string) { return ({ FACTOR_WEIGHT: '因子权重', FACTOR_SET: '因子集合', REGIME_CONFIG: '市场状态', STRATEGY_CONFIG: '策略参数' } as Record<string, string>)[value] || value }
function objectTypeText(value: string) { return ({ QUANT_PROPOSAL: '量化提案', DECISION_CONTEXT: '决策上下文', RESEARCH_RESULT: 'TradingAgents 研究', NORMAL_PLAN: '普通模型方案', TOP_REVIEW: '终审模型复核', CONSENSUS_DECISION: '一致性决策', HARD_RISK_DECISION: '硬风险门禁' } as Record<string, string>)[value] || value }
function payloadStatus(row: Record<string, any>) { return String(row.payload?.status || row.payload?.decision_status || '已记录') }
function money(value: unknown) { if (value == null || value === '') return '暂无'; const parsed = Number(value); return Number.isFinite(parsed) ? `¥${parsed.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : String(value) }
function percent(value: unknown) { if (value == null || value === '') return '暂无'; const parsed = Number(value); return Number.isFinite(parsed) ? `${(parsed * 100).toFixed(2)}%` : String(value) }
function decimalMetric(value: unknown) { if (value == null || value === '') return '等待成熟数据'; const parsed = Number(value); return Number.isFinite(parsed) ? parsed.toFixed(3) : '等待成熟数据' }
function countDifference(value: unknown) { if (value == null || value === '') return '等待成熟数据'; const parsed = Number(value); return Number.isFinite(parsed) ? `${parsed > 0 ? '+' : ''}${parsed}` : '等待成熟数据' }
function regimeComparisonText(value: unknown) {
  if (!value || typeof value !== 'object') return '等待成熟数据'
  const segments = (value as Record<string, unknown>).available_segments
  return Array.isArray(segments) && segments.length ? `已覆盖 ${segments.join('、')}` : '等待成熟数据'
}
function outlierDependencyText(value: unknown) {
  if (!value || value === 'NOT_MATURE' || typeof value !== 'object') return '等待成熟数据'
  const data = value as Record<string, unknown>
  const top = data.top_trade_contribution_pct
  const topFive = data.top_five_trade_contribution_pct
  if (top == null && topFive == null) return '等待成熟数据'
  return `单笔 ${percent(top)}；前五笔 ${percent(topFive)}`
}
function evaluationCount(key: string) { return Array.isArray(evaluation.value[key]) ? evaluation.value[key].length : 0 }

async function refresh() {
  loading.value = true
  try {
    const [listResponse, optionsResponse, readinessResponse] = await Promise.all([
      alphaguardExperimentApi.challengers(), alphaguardExperimentApi.challengerOptions(), alphaguardOperationsApi.readiness()
    ])
    challengers.value = listResponse.data.items || []
    options.value = optionsResponse.data
    challengerReady.value = readinessResponse.data.challenger_ready
    activeChallenger.value = readinessResponse.data.active_challenger
    if (selected.value) {
      const latest = challengers.value.find(item => item.experiment_id === selected.value?.experiment_id)
      if (latest) await select(latest)
    }
  } finally { loading.value = false }
}

async function select(item: ChallengerSummary) {
  selected.value = item
  const [experimentResponse, runResponse, decisionResponse, orderResponse, evaluationResponse, comparisonResponse] = await Promise.all([
    alphaguardExperimentApi.experiment(item.experiment_id),
    alphaguardExperimentApi.challengerRuns(item.experiment_id),
    alphaguardExperimentApi.challengerDecisions(item.experiment_id),
    alphaguardExperimentApi.challengerOrders(item.experiment_id),
    alphaguardExperimentApi.challengerEvaluation(item.experiment_id),
    alphaguardExperimentApi.challengerComparison(item.experiment_id).catch(() => null)
  ])
  detail.value = experimentResponse.data
  runs.value = runResponse.data.items || []
  decisions.value = decisionResponse.data.items || []
  orders.value = orderResponse.data
  evaluation.value = evaluationResponse.data
  comparison.value = comparisonResponse?.data || null
}

function openCreate() {
  Object.assign(createForm, { name: '', champion_slot_id: '', component_type: '', component_key: '', baseline_version_ref: '', challenger_version_ref: '', primary_variable_path: '', description: '', hypothesis: '', validation_only: false })
  createVisible.value = true
}
function syncChampion(slotId: string) {
  const champion = options.value.champions.find(item => item.champion_slot_id === slotId)
  createForm.component_type = champion?.component_type || ''
  createForm.component_key = champion?.component_key || ''
  createForm.baseline_version_ref = champion?.current_version_ref || ''
  createForm.challenger_version_ref = ''
}
async function create() {
  if (!createReady.value) return
  submitting.value = true
  try {
    await alphaguardExperimentApi.createChallenger({
      name: createForm.name, description: createForm.description, hypothesis: createForm.hypothesis,
      component_type: createForm.component_type, component_key: createForm.component_key,
      baseline_version_ref: createForm.baseline_version_ref, challenger_version_ref: createForm.challenger_version_ref,
      primary_variable_path: createForm.primary_variable_path, validation_only: createForm.validation_only
    })
    createVisible.value = false
    ElMessage.success('挑战者草稿已创建')
    await refresh()
  } finally { submitting.value = false }
}
async function backtest() { if (!selected.value || !latestManifestId.value) return; submitting.value = true; try { await alphaguardExperimentApi.backtestChallenger(selected.value.experiment_id, latestManifestId.value); ElMessage.success('历史回放已进入队列') } finally { submitting.value = false } }
async function startShadow() { if (!selected.value || !latestManifestId.value) return; submitting.value = true; try { await alphaguardExperimentApi.shadowChallenger(selected.value.experiment_id, latestManifestId.value); ElMessage.success('Shadow 观察已启动'); await refresh() } finally { submitting.value = false } }
async function submitReview() {
  if (!selected.value || !comparisonReportId.value || !canSubmitReview.value) return
  await ElMessageBox.confirm('提交后只会进入受控风险审查和人工评审，不会自动替换 Champion。', '提交人工评审')
  submitting.value = true
  try {
    await alphaguardExperimentApi.requestRiskReview(selected.value.experiment_id, comparisonReportId.value)
    ElMessage.success('人工评审已提交；不会自动晋升 Champion')
    await select(selected.value)
  } finally { submitting.value = false }
}
async function activate() { if (!selected.value || !activationDate.value) return; await ElMessageBox.confirm('启用后仅使用 PAPER_CHALLENGER 模拟账户，不会连接券商。', '启用模拟挑战者'); submitting.value = true; try { await alphaguardExperimentApi.activateChallenger(selected.value.experiment_id, activationDate.value); ElMessage.success('模拟挑战者已启用'); await refresh() } finally { submitting.value = false } }
async function pause() { if (!selected.value) return; const { value } = await ElMessageBox.prompt('请输入暂停原因', '暂停模拟挑战者', { inputValidator: text => String(text || '').trim().length >= 3 || '至少输入3个字符' }); submitting.value = true; try { await alphaguardExperimentApi.pauseChallenger(selected.value.experiment_id, value); ElMessage.success('已暂停，不再产生新任务'); await refresh() } finally { submitting.value = false } }
async function retire() { if (!selected.value) return; const { value } = await ElMessageBox.prompt('请输入退役原因', '退役模拟挑战者', { inputValidator: text => String(text || '').trim().length >= 3 || '至少输入3个字符' }); submitting.value = true; try { await alphaguardExperimentApi.retireChallenger(selected.value.experiment_id, value); ElMessage.success('挑战者已退役，历史记录保留'); await refresh() } finally { submitting.value = false } }

onMounted(refresh)
</script>

<style scoped>
.challenger-page { display: grid; gap: 16px; }
.status-band { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border: 1px solid var(--el-border-color-light); border-radius: 6px; overflow: hidden; }
.status-band > div { min-height: 74px; padding: 12px 16px; border-right: 1px solid var(--el-border-color-light); display: grid; gap: 6px; }
.status-band > div:last-child { border-right: 0; }.status-band span,.metrics-grid span { color: var(--el-text-color-secondary); font-size: 13px; }.status-band strong { font-size: 20px; }
.workflow-band { padding: 16px 0 20px; border-bottom: 1px solid var(--el-border-color-light); }.section-title,.detail-heading,.title-line,.header-actions,.action-strip,.date-control { display: flex; align-items: center; }.section-title,.detail-heading { justify-content: space-between; gap: 16px; }.section-title h2,.detail-heading h2 { margin: 0; font-size: 20px; }.section-title p,.detail-heading p { margin: 5px 0 0; color: var(--el-text-color-secondary); }.header-actions,.title-line,.action-strip,.date-control { gap: 10px; }
.content-grid { display: grid; grid-template-columns: minmax(220px, 280px) minmax(0, 1fr); min-height: 520px; border: 1px solid var(--el-border-color-light); border-radius: 6px; overflow: hidden; }.challenger-list { border-right: 1px solid var(--el-border-color-light); background: var(--el-fill-color-lighter); }.list-heading { padding: 14px 16px; font-weight: 600; border-bottom: 1px solid var(--el-border-color-light); }.challenger-item { width: 100%; min-height: 68px; padding: 12px 14px; border: 0; border-bottom: 1px solid var(--el-border-color-light); background: transparent; color: inherit; display: flex; align-items: center; justify-content: space-between; gap: 8px; text-align: left; cursor: pointer; }.challenger-item:hover,.challenger-item.selected { background: var(--el-color-primary-light-9); }.challenger-item.selected { box-shadow: inset 3px 0 var(--el-color-primary); }.item-main { min-width: 0; display: grid; gap: 5px; }.item-main small { overflow: hidden; color: var(--el-text-color-secondary); text-overflow: ellipsis; white-space: nowrap; }
.challenger-detail { min-width: 0; padding: 18px; }.metrics-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); margin-top: 18px; border: 1px solid var(--el-border-color-light); border-radius: 6px; overflow: hidden; }.metrics-grid > div { min-height: 70px; padding: 12px 14px; border-right: 1px solid var(--el-border-color-light); border-bottom: 1px solid var(--el-border-color-light); display: grid; gap: 6px; }.metrics-grid > div:nth-child(3n) { border-right: 0; }.metrics-grid > div:nth-last-child(-n+3) { border-bottom: 0; }.metrics-grid strong { font-size: 17px; }.action-strip { flex-wrap: wrap; margin-top: 16px; }.date-control span { font-size: 13px; color: var(--el-text-color-secondary); }.action-reason { margin: 8px 0 0; color: var(--el-color-warning); font-size: 13px; }.detail-tabs { margin-top: 14px; }.sub-table { margin-top: 14px; }.field-note { margin-left: 10px; color: var(--el-text-color-secondary); font-size: 13px; }
.review-note { margin-top: 12px; }
@media (max-width: 980px) { .status-band { grid-template-columns: repeat(2, minmax(0, 1fr)); }.status-band > div:nth-child(2) { border-right: 0; }.content-grid { grid-template-columns: 1fr; }.challenger-list { max-height: 260px; overflow: auto; border-right: 0; border-bottom: 1px solid var(--el-border-color-light); }.metrics-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.metrics-grid > div { border-right: 1px solid var(--el-border-color-light) !important; border-bottom: 1px solid var(--el-border-color-light) !important; }.metrics-grid > div:nth-child(2n) { border-right: 0 !important; }.metrics-grid > div:nth-last-child(-n+2) { border-bottom: 0 !important; } }
@media (max-width: 640px) { .status-band,.metrics-grid { grid-template-columns: 1fr; }.status-band > div,.metrics-grid > div { border-right: 0 !important; border-bottom: 1px solid var(--el-border-color-light) !important; }.status-band > div:last-child,.metrics-grid > div:last-child { border-bottom: 0 !important; }.section-title,.detail-heading { align-items: flex-start; flex-direction: column; }.challenger-detail { padding: 14px; } }
</style>
