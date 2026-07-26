<template>
  <div class="experiment-lab">
    <el-alert
      type="warning"
      :closable="false"
      show-icon
      title="实验不会自动晋升或回退；真实样本不足时晋升会被后端阻断。"
    />

    <el-card class="section">
      <template #header>
        <div class="header-row">
          <strong>Champion 总览</strong>
          <el-button text :loading="loading" @click="refresh">刷新</el-button>
        </div>
      </template>
      <el-table :data="champions" size="small">
        <el-table-column prop="component_type" label="组件类型" min-width="150" />
        <el-table-column prop="component_key" label="组件名称" min-width="170" />
        <el-table-column prop="market" label="市场" width="75" />
        <el-table-column prop="current_version_ref" label="当前 Champion" min-width="220" />
        <el-table-column prop="previous_version_ref" label="前一版本" min-width="180" />
        <el-table-column prop="effective_from_trade_date" label="生效日" width="115" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column prop="source_experiment_id" label="来源实验" min-width="170" />
        <el-table-column v-if="authStore.isAdmin" label="受控操作" width="90">
          <template #default="{ row }">
            <el-button
              link
              type="danger"
              :disabled="!row.previous_version_ref"
              @click="openRollback(row)"
            >
              回退
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && champions.length === 0" description="尚未导入 Champion 指针" />
    </el-card>

    <el-card class="section">
      <template #header><strong>实验列表</strong></template>
      <el-table :data="experiments" size="small" highlight-current-row @row-click="selectExperiment">
        <el-table-column prop="name" label="实验名称" min-width="160" />
        <el-table-column prop="primary_variable_path" label="唯一变量" min-width="210" />
        <el-table-column prop="baseline_version_ref" label="Baseline" min-width="180" />
        <el-table-column prop="challenger_version_ref" label="Challenger" min-width="180" />
        <el-table-column prop="experiment_mode" label="模式" width="115" />
        <el-table-column prop="status" label="状态" width="110" />
        <el-table-column label="可晋升" width="90">
          <template #default="{ row }">
            <el-tag :type="row.promotion_eligible ? 'success' : 'info'">
              {{ row.promotion_eligible ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && experiments.length === 0" description="暂无生产实验；测试 fixture 不会写入此处" />
    </el-card>

    <el-card v-if="detail" class="section">
      <template #header><strong>实验详情：{{ detail.definition.name }}</strong></template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="实验假设">{{ detail.definition.hypothesis }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ detail.definition.status }}</el-descriptions-item>
        <el-descriptions-item label="唯一变量">{{ detail.definition.primary_variable_path }}</el-descriptions-item>
        <el-descriptions-item label="实验模式">{{ detail.definition.experiment_mode }}</el-descriptions-item>
        <el-descriptions-item label="Baseline">{{ detail.definition.baseline_version_ref }}</el-descriptions-item>
        <el-descriptions-item label="Challenger">{{ detail.definition.challenger_version_ref }}</el-descriptions-item>
      </el-descriptions>

      <el-tabs class="detail-tabs">
        <el-tab-pane label="数据集/分割">
          <pre>{{ pretty(detail.dataset_manifests) }}</pre>
        </el-tab-pane>
        <el-tab-pane label="阶段结果">
          <pre>{{ pretty({ runs: detail.runs, shadow: detail.shadow_runs, challenger: detail.challenger_assignments }) }}</pre>
        </el-tab-pane>
        <el-tab-pane label="比较与负面指标">
          <pre>{{ pretty(detail.comparison_reports) }}</pre>
        </el-tab-pane>
        <el-tab-pane label="泄漏/风险审查">
          <pre>{{ pretty(detail.risk_reviews) }}</pre>
        </el-tab-pane>
        <el-tab-pane label="审计时间线">
          <el-timeline>
            <el-timeline-item
              v-for="event in detail.events"
              :key="String(event.event_id)"
              :timestamp="String(event.created_at || '')"
            >
              {{ event.event_type }} — {{ event.reason }}
            </el-timeline-item>
          </el-timeline>
        </el-tab-pane>
      </el-tabs>

      <div v-if="authStore.isAdmin" class="approval-panel">
        <h4>晋升审批（管理员）</h4>
        <el-alert
          type="info"
          :closable="false"
          title="必须核对当前/挑战版本 Hash、泄漏审计、风险审查、失败门槛、回退版本和生效交易日。"
        />
        <el-table :data="pendingPromotions" size="small">
          <el-table-column prop="promotion_request_id" label="申请" min-width="180" />
          <el-table-column prop="current_champion_hash" label="当前 Hash" min-width="170" />
          <el-table-column prop="proposed_champion_hash" label="Challenger Hash" min-width="170" />
          <el-table-column prop="effective_from_trade_date" label="生效日" width="110" />
          <el-table-column prop="required_confirmation_text" label="确认文本" min-width="220" />
          <el-table-column label="操作" width="150">
            <template #default="{ row }">
              <el-button link type="primary" @click="openApproval(row)">审阅批准</el-button>
              <el-button link type="danger" @click="reject(row)">拒绝</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <el-dialog v-model="approvalVisible" title="人工晋升确认" width="650px">
      <el-descriptions v-if="approvalTarget" :column="1" border>
        <el-descriptions-item label="当前 Champion Hash">{{ approvalTarget.current_champion_hash }}</el-descriptions-item>
        <el-descriptions-item label="Challenger Hash">{{ approvalTarget.proposed_champion_hash }}</el-descriptions-item>
        <el-descriptions-item label="回退版本">{{ selectedChampion?.previous_version_ref || '请核查 Champion 总览' }}</el-descriptions-item>
        <el-descriptions-item label="生效日">{{ approvalTarget.effective_from_trade_date }}</el-descriptions-item>
      </el-descriptions>
      <el-form label-width="110px" class="dialog-form">
        <el-form-item label="批准理由"><el-input v-model="approvalReason" type="textarea" /></el-form-item>
        <el-form-item label="确认文本">
          <el-input v-model="approvalConfirmation" :placeholder="String(approvalTarget?.required_confirmation_text || '')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="approvalVisible = false">取消</el-button>
        <el-button type="danger" :loading="submitting" @click="approve">明确批准并提交 Saga</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="rollbackVisible" title="受控 Champion 回退" width="620px">
      <el-descriptions v-if="rollbackTarget" :column="1" border>
        <el-descriptions-item label="当前版本">{{ rollbackTarget.current_version_ref }}</el-descriptions-item>
        <el-descriptions-item label="目标旧版本">{{ rollbackTarget.previous_version_ref }}</el-descriptions-item>
        <el-descriptions-item label="当前 Hash">{{ rollbackTarget.assignment_hash }}</el-descriptions-item>
      </el-descriptions>
      <el-form label-width="100px" class="dialog-form">
        <el-form-item label="回退原因"><el-input v-model="rollbackReason" type="textarea" /></el-form-item>
        <el-form-item label="生效日"><el-date-picker v-model="rollbackDate" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="确认文本"><el-input v-model="rollbackConfirmation" :placeholder="rollbackPrompt" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rollbackVisible = false">取消</el-button>
        <el-button type="danger" :loading="submitting" @click="rollback">确认回退</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  alphaguardExperimentApi,
  type ChampionAssignment,
  type ExperimentDefinition,
  type ExperimentDetail
} from '@/api/alphaguardExperiments'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const loading = ref(false)
const submitting = ref(false)
const champions = ref<ChampionAssignment[]>([])
const experiments = ref<ExperimentDefinition[]>([])
const detail = ref<ExperimentDetail | null>(null)
const selectedChampion = ref<ChampionAssignment | null>(null)
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
const rollbackPrompt = computed(() =>
  rollbackTarget.value ? `ROLLBACK ${rollbackTarget.value.champion_slot_id}` : ''
)

function pretty(value: unknown) {
  return JSON.stringify(value, null, 2)
}

async function refresh() {
  loading.value = true
  try {
    const [championResponse, experimentResponse] = await Promise.all([
      alphaguardExperimentApi.champions(),
      alphaguardExperimentApi.experiments()
    ])
    champions.value = championResponse.data.items || []
    experiments.value = experimentResponse.data.items || []
  } finally {
    loading.value = false
  }
}

async function selectExperiment(row: ExperimentDefinition) {
  const response = await alphaguardExperimentApi.experiment(row.experiment_id)
  detail.value = response.data
  selectedChampion.value = champions.value.find(
    item =>
      item.component_type === row.component_type &&
      item.component_key === row.component_key
  ) || null
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
    await alphaguardExperimentApi.approvePromotion(
      String(approvalTarget.value.promotion_request_id),
      {
        decision_reason: approvalReason.value,
        confirmation_text: approvalConfirmation.value,
        current_champion_hash: String(approvalTarget.value.current_champion_hash),
        proposed_champion_hash: String(approvalTarget.value.proposed_champion_hash)
      }
    )
    approvalVisible.value = false
    ElMessage.success('人工批准已提交并由 Saga 校验')
    await refresh()
    if (detail.value) await selectExperiment(detail.value.definition)
  } finally {
    submitting.value = false
  }
}

async function reject(row: Record<string, any>) {
  const { value } = await ElMessageBox.prompt('请输入拒绝原因', '拒绝晋升申请', {
    inputValidator: text => String(text || '').trim().length >= 3 || '至少输入3个字符'
  })
  await alphaguardExperimentApi.rejectPromotion(String(row.promotion_request_id), value)
  ElMessage.success('晋升申请已拒绝')
  if (detail.value) await selectExperiment(detail.value.definition)
}

function openRollback(row: Record<string, any>) {
  rollbackTarget.value = row as ChampionAssignment
  rollbackReason.value = ''
  rollbackDate.value = ''
  rollbackConfirmation.value = ''
  rollbackVisible.value = true
}

async function rollback() {
  if (!rollbackTarget.value) return
  submitting.value = true
  try {
    await alphaguardExperimentApi.rollbackChampion(
      rollbackTarget.value.champion_slot_id,
      {
        reason: rollbackReason.value,
        confirmation_text: rollbackConfirmation.value,
        current_champion_hash: rollbackTarget.value.assignment_hash,
        effective_from_trade_date: rollbackDate.value
      }
    )
    rollbackVisible.value = false
    ElMessage.success('回退 Saga 已提交；只影响生效日后的新任务')
    await refresh()
  } finally {
    submitting.value = false
  }
}

onMounted(refresh)
</script>

<style scoped>
.experiment-lab { display: grid; gap: 16px; }
.section { margin-top: 0; }
.header-row { display: flex; align-items: center; justify-content: space-between; }
.detail-tabs { margin-top: 16px; }
.detail-tabs pre {
  max-height: 360px;
  overflow: auto;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 6px;
  white-space: pre-wrap;
}
.approval-panel { margin-top: 18px; }
.dialog-form { margin-top: 16px; }
</style>
