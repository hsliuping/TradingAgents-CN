<template>
  <div class="governance-page">
    <el-alert
      type="warning"
      :closable="false"
      show-icon
      title="实验不会自动晋升或回退；所有 Champion 变更都需要管理员明确确认。"
    />

    <section class="summary-band">
      <div><span>Champion</span><strong>{{ champions.length }}</strong></div>
      <div><span>实验</span><strong>{{ experiments.length }}</strong></div>
      <div><span>待人工审批</span><strong>{{ pendingPromotions.length }}</strong></div>
      <div><span>晋升策略</span><strong>{{ policy ? '已配置' : '未配置' }}</strong></div>
    </section>

    <section class="governance-section">
      <div class="section-heading">
        <div><h2>Champion 总览</h2><p>回退只影响生效日后的新任务，不迁移既有持仓。</p></div>
        <el-button :icon="Refresh" circle title="刷新" :loading="loading" @click="refresh" />
      </div>
      <el-table :data="champions" size="small">
        <el-table-column prop="component_type" label="组件类型" min-width="140" />
        <el-table-column prop="component_key" label="组件名称" min-width="160" />
        <el-table-column prop="current_version_ref" label="当前版本" min-width="210" />
        <el-table-column prop="previous_version_ref" label="前一版本" min-width="180" />
        <el-table-column prop="effective_from_trade_date" label="生效日" width="115" />
        <el-table-column prop="status" label="状态" width="90" />
        <el-table-column v-if="authStore.isAdmin" label="操作" width="90">
          <template #default="{ row }">
            <el-button link type="danger" :disabled="!row.previous_version_ref" @click="invokeTableRowAction(champions, row, openRollback)">回退</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && champions.length === 0" description="尚未导入 Champion 指针" />
    </section>

    <section class="governance-section">
      <div class="section-heading"><div><h2>实验治理与人工评审</h2><p>选择实验查看证据、审查记录和待处理申请。</p></div></div>
      <el-table :data="experiments" size="small" highlight-current-row @row-click="selectExperiment">
        <el-table-column prop="name" label="实验名称" min-width="160" />
        <el-table-column prop="primary_variable_path" label="唯一变量" min-width="210" />
        <el-table-column prop="baseline_version_ref" label="基线版本" min-width="180" />
        <el-table-column prop="challenger_version_ref" label="挑战版本" min-width="180" />
        <el-table-column prop="status" label="状态" width="110" />
        <el-table-column label="可晋升" width="90">
          <template #default="{ row }"><el-tag :type="row.promotion_eligible ? 'success' : 'info'">{{ row.promotion_eligible ? '是' : '否' }}</el-tag></template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && experiments.length === 0" description="暂无实验" />
    </section>

    <section v-if="detail" class="governance-section">
      <div class="section-heading"><div><h2>{{ detail.definition.name }}</h2><p>{{ detail.definition.hypothesis }}</p></div></div>
      <el-tabs>
        <el-tab-pane label="数据与运行">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="数据集 Manifest">{{ detail.dataset_manifests.length }}</el-descriptions-item>
            <el-descriptions-item label="历史运行">{{ detail.runs.length }}</el-descriptions-item>
            <el-descriptions-item label="Shadow 运行">{{ detail.shadow_runs.length }}</el-descriptions-item>
            <el-descriptions-item label="挑战者分配">{{ detail.challenger_assignments.length }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>
        <el-tab-pane label="对比与风险">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="对比报告">{{ detail.comparison_reports.length }}</el-descriptions-item>
            <el-descriptions-item label="风险审查">{{ detail.risk_reviews.length }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>
        <el-tab-pane label="人工审批">
          <el-alert type="info" :closable="false" title="审批不会自动执行；后端仍会校验报告、风险审查、Hash、生效日和回退条件。" />
          <el-table :data="pendingPromotions" size="small" class="review-table">
            <el-table-column prop="promotion_request_id" label="申请" min-width="180" />
            <el-table-column prop="effective_from_trade_date" label="生效日" width="115" />
            <el-table-column prop="required_confirmation_text" label="确认文本" min-width="220" />
            <el-table-column v-if="authStore.isAdmin" label="操作" width="150">
              <template #default="{ row }">
                <el-button link type="primary" @click="openApproval(row)">审阅批准</el-button>
                <el-button link type="danger" @click="reject(row)">拒绝</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="pendingPromotions.length === 0" description="当前实验没有待人工审批申请" />
        </el-tab-pane>
        <el-tab-pane label="审计时间线">
          <el-timeline>
            <el-timeline-item v-for="event in detail.events" :key="String(event.event_id)" :timestamp="String(event.created_at || '')">
              {{ event.event_type }} · {{ event.reason }}
            </el-timeline-item>
          </el-timeline>
        </el-tab-pane>
      </el-tabs>
    </section>

    <el-dialog v-model="approvalVisible" title="人工晋升确认" width="min(650px, 92vw)">
      <el-form label-position="top">
        <el-form-item label="批准理由"><el-input v-model="approvalReason" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="确认文本"><el-input v-model="approvalConfirmation" :placeholder="String(approvalTarget?.required_confirmation_text || '')" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="approvalVisible = false">取消</el-button><el-button type="danger" :loading="submitting" @click="approve">明确批准</el-button></template>
    </el-dialog>

    <el-dialog v-model="rollbackVisible" title="受控 Champion 回退" width="min(620px, 92vw)">
      <el-form label-position="top">
        <el-form-item label="回退原因"><el-input v-model="rollbackReason" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="生效日"><el-date-picker v-model="rollbackDate" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="确认文本"><el-input v-model="rollbackConfirmation" :placeholder="rollbackPrompt" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="rollbackVisible = false">取消</el-button><el-button type="danger" :loading="submitting" @click="rollback">确认回退</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { invokeTableRowAction } from '@/utils/tableRows'
import {
  alphaguardExperimentApi,
  type ChampionAssignment,
  type ExperimentDefinition,
  type ExperimentDetail,
  type PromotionPolicy
} from '@/api/alphaguardExperiments'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const loading = ref(false)
const submitting = ref(false)
const champions = ref<ChampionAssignment[]>([])
const experiments = ref<ExperimentDefinition[]>([])
const policy = ref<PromotionPolicy | null>(null)
const detail = ref<ExperimentDetail | null>(null)
const approvalVisible = ref(false)
const approvalTarget = ref<Record<string, any> | null>(null)
const approvalReason = ref('')
const approvalConfirmation = ref('')
const rollbackVisible = ref(false)
const rollbackTarget = ref<ChampionAssignment | null>(null)
const rollbackReason = ref('')
const rollbackDate = ref('')
const rollbackConfirmation = ref('')

const pendingPromotions = computed(() =>
  (detail.value?.promotion_requests || []).filter(item => item.status === 'PENDING_APPROVAL')
)
const rollbackPrompt = computed(() => rollbackTarget.value ? `ROLLBACK ${rollbackTarget.value.champion_slot_id}` : '')

async function refresh() {
  loading.value = true
  try {
    const [championResponse, experimentResponse, policyResponse] = await Promise.all([
      alphaguardExperimentApi.champions(),
      alphaguardExperimentApi.experiments(),
      alphaguardExperimentApi.promotionPolicy()
    ])
    champions.value = championResponse.data.items || []
    experiments.value = experimentResponse.data.items || []
    policy.value = policyResponse.data.policy
    if (detail.value) {
      const current = experiments.value.find(item => item.experiment_id === detail.value?.definition.experiment_id)
      if (current) await selectExperiment(current)
    }
  } finally { loading.value = false }
}

async function selectExperiment(row: ExperimentDefinition) {
  const response = await alphaguardExperimentApi.experiment(row.experiment_id)
  detail.value = response.data
}

function openApproval(row: Record<string, any>) {
  approvalTarget.value = row
  approvalReason.value = ''
  approvalConfirmation.value = ''
  approvalVisible.value = true
}

async function approve() {
  if (!approvalTarget.value) return
  submitting.value = true
  try {
    await alphaguardExperimentApi.approvePromotion(String(approvalTarget.value.promotion_request_id), {
      decision_reason: approvalReason.value,
      confirmation_text: approvalConfirmation.value,
      current_champion_hash: String(approvalTarget.value.current_champion_hash),
      proposed_champion_hash: String(approvalTarget.value.proposed_champion_hash)
    })
    approvalVisible.value = false
    ElMessage.success('人工审批已提交，受控 Saga 将再次校验全部门禁')
    await refresh()
  } finally { submitting.value = false }
}

async function reject(row: Record<string, any>) {
  const { value } = await ElMessageBox.prompt('请输入拒绝原因', '拒绝晋升申请', {
    inputValidator: text => String(text || '').trim().length >= 3 || '至少输入3个字符'
  })
  await alphaguardExperimentApi.rejectPromotion(String(row.promotion_request_id), value)
  ElMessage.success('晋升申请已拒绝')
  await refresh()
}

function openRollback(row: ChampionAssignment) {
  rollbackTarget.value = row
  rollbackReason.value = ''
  rollbackDate.value = ''
  rollbackConfirmation.value = ''
  rollbackVisible.value = true
}

async function rollback() {
  if (!rollbackTarget.value) return
  submitting.value = true
  try {
    await alphaguardExperimentApi.rollbackChampion(rollbackTarget.value.champion_slot_id, {
      reason: rollbackReason.value,
      confirmation_text: rollbackConfirmation.value,
      current_champion_hash: rollbackTarget.value.assignment_hash,
      effective_from_trade_date: rollbackDate.value
    })
    rollbackVisible.value = false
    ElMessage.success('回退 Saga 已提交；既有持仓不会迁移')
    await refresh()
  } finally { submitting.value = false }
}

onMounted(refresh)
</script>

<style scoped>
.governance-page { display: grid; gap: 16px; }
.summary-band { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border: 1px solid var(--el-border-color-light); border-radius: 6px; overflow: hidden; }
.summary-band > div { min-height: 72px; padding: 12px 16px; border-right: 1px solid var(--el-border-color-light); display: grid; gap: 6px; }
.summary-band > div:last-child { border-right: 0; }
.summary-band span,.section-heading p { color: var(--el-text-color-secondary); }
.summary-band strong { font-size: 20px; }
.governance-section { padding: 18px 0; border-top: 1px solid var(--el-border-color-light); }
.section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 14px; }
.section-heading h2,.section-heading p { margin: 0; }
.section-heading h2 { font-size: 18px; }
.section-heading p { margin-top: 5px; font-size: 13px; }
.review-table { margin-top: 12px; }
@media (max-width: 760px) { .summary-band { grid-template-columns: repeat(2, minmax(0, 1fr)); }.summary-band > div:nth-child(2) { border-right: 0; } }
@media (max-width: 480px) { .summary-band { grid-template-columns: 1fr; }.summary-band > div { border-right: 0; border-bottom: 1px solid var(--el-border-color-light); }.summary-band > div:last-child { border-bottom: 0; } }
</style>
