<template>
  <div class="prompt-policy-manager">
    <div class="page-header">
      <div class="header-left">
        <h1>
          <el-icon class="header-icon"><Setting /></el-icon>
          注入策略管理
        </h1>
        <span class="subtitle">按 Agent + 场景控制上下文注入规则（行业/个股画像、能力块等）</span>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="handleCreate">
          <el-icon><Plus /></el-icon>
          新建策略
        </el-button>
        <el-button @click="handleRefresh">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button @click="goToPreview">
          <el-icon><View /></el-icon>
          Prompt 预览
        </el-button>
      </div>
    </div>

    <el-alert type="info" :closable="false" show-icon class="page-alert">
      无策略时使用默认行为（summary 模式 + 继承行业画像）。修改策略后可到
      <router-link to="/settings/prompt-preview">Prompt 预览</router-link>
      查看效果。
    </el-alert>

    <el-card class="policy-card" shadow="never">
      <template #header>
        <span class="card-title">策略列表</span>
        <el-select
          v-model="filterAgentType"
          placeholder="按 Agent 类型过滤"
          clearable
          style="width: 180px; margin-left: 12px"
          @change="loadPolicies"
        >
          <el-option v-for="t in agentTypes" :key="t" :label="labelAgentType(t)" :value="t" />
        </el-select>
      </template>

      <el-table
        v-loading="loading"
        :data="groupedPolicies"
        row-key="key"
        stripe
        style="width: 100%"
      >
        <el-table-column prop="agent_type" label="Agent 类型" width="140">
          <template #default="{ row }">{{ labelAgentType(row.agent_type) }}</template>
        </el-table-column>
        <el-table-column prop="agent_name" label="Agent 名称" width="180">
          <template #default="{ row }">{{ labelAgentName(row.agent_name) }}</template>
        </el-table-column>
        <el-table-column prop="scope" label="场景" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="scopeTagType(row.scope)">
              {{ scopeLabel(row.scope) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="enabled" label="启用" width="70" align="center">
          <template #default="{ row }">
            <el-switch
              v-model="row.enabled"
              size="small"
              @change="handleToggleEnabled(row)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="injection_mode" label="注入模式" width="100">
          <template #default="{ row }">
            {{ injectionModeLabel(row.injection_mode) }}
          </template>
        </el-table-column>
        <el-table-column label="继承行业" width="90" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.inherit_industry_for_stock" type="success" size="small">是</el-tag>
            <el-tag v-else type="info" size="small">否</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="能力块" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.include_capability_block" type="success" size="small">开</el-tag>
            <el-tag v-else type="info" size="small">关</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="handleEdit(row)">
              编辑
            </el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && groupedPolicies.length === 0" description="暂无策略，请先运行初始化脚本或手动创建" />
    </el-card>

    <!-- 编辑弹窗 -->
    <el-dialog
      v-model="editVisible"
      :title="editingPolicy?.id ? '编辑策略' : '新建策略'"
      width="520px"
      destroy-on-close
      @close="resetEditForm"
    >
      <el-form
        ref="editFormRef"
        :model="editForm"
        label-width="140px"
        :disabled="!!editingPolicy?.id"
      >
        <el-form-item v-if="!editingPolicy?.id" label="Agent 类型" required>
          <el-select v-model="editForm.agent_type" placeholder="选择 Agent 类型" style="width: 100%">
            <el-option v-for="type in agentTypes" :key="type" :label="labelAgentType(type)" :value="type" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="!editingPolicy?.id" label="Agent 名称" required>
          <el-select v-model="editForm.agent_name" placeholder="选择 Agent 名称" style="width: 100%" :disabled="!editForm.agent_type">
            <el-option v-for="name in agentNames" :key="name.value" :label="name.label" :value="name.value" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="!editingPolicy?.id" label="场景" required>
          <el-select v-model="editForm.scope" placeholder="选择场景" style="width: 100%">
            <el-option label="通用" value="general" />
            <el-option label="行业分析" value="industry" />
            <el-option label="个股分析" value="stock" />
          </el-select>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="editForm.enabled" />
        </el-form-item>
        <el-form-item label="注入模式">
          <el-select v-model="editForm.injection_mode" style="width: 100%">
            <el-option label="不注入" value="none" />
            <el-option label="摘要" value="summary" />
            <el-option label="完整" value="full" />
          </el-select>
        </el-form-item>
        <el-form-item label="个股继承行业画像">
          <el-switch v-model="editForm.inherit_industry_for_stock" />
        </el-form-item>
        <el-form-item label="包含能力块">
          <el-switch v-model="editForm.include_capability_block" />
        </el-form-item>
        <el-form-item label="包含外部缺口提醒">
          <el-switch v-model="editForm.include_external_gap_notice" />
        </el-form-item>
        <el-form-item label="包含可比公司">
          <el-switch v-model="editForm.include_comparable_companies" />
        </el-form-item>
        <el-form-item label="注入位置">
          <el-select v-model="editForm.inject_position" style="width: 100%">
            <el-option label="系统提示词" value="system_prompt" />
            <el-option label="分析要求" value="analysis_requirements" />
            <el-option label="约束条件" value="constraints" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">
          {{ editingPolicy?.id ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Setting, Refresh, View, Plus } from '@element-plus/icons-vue'
import { promptPoliciesApi, type PromptInjectionPolicy } from '@/api/promptPolicies'
import { promptPreviewApi, type AgentItem } from '@/api/promptPreview'
import { labelAgentType, labelAgentName, filterV2AgentTypes } from '@/constants/agentLabels'

const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const policies = ref<PromptInjectionPolicy[]>([])
const agents = ref<AgentItem[]>([])
const filterAgentType = ref('')
const editVisible = ref(false)
const editFormRef = ref()
const editingPolicy = ref<PromptInjectionPolicy | null>(null)

const editForm = ref({
  agent_type: '',
  agent_name: '',
  scope: 'general' as 'general' | 'industry' | 'stock',
  enabled: true,
  injection_mode: 'summary' as 'none' | 'summary' | 'full',
  inherit_industry_for_stock: true,
  include_capability_block: true,
  include_external_gap_notice: true,
  include_comparable_companies: true,
  inject_position: 'analysis_requirements' as 'system_prompt' | 'analysis_requirements' | 'constraints',
})

const agentTypes = computed(() => {
  const types = new Set(agents.value.map((a) => a.agent_type))
  return filterV2AgentTypes(Array.from(types)).sort()
})

const agentNames = computed(() => {
  if (!editForm.value.agent_type) return []
  return agents.value
    .filter((a) => a.agent_type === editForm.value.agent_type)
    .map((a) => ({ value: a.agent_name, label: labelAgentName(a.agent_name) }))
})

const groupedPolicies = computed(() => {
  let list = policies.value
  if (filterAgentType.value) {
    list = list.filter(p => p.agent_type === filterAgentType.value)
  }
  return list
})

type TagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

function scopeLabel(s: string) {
  const m: Record<string, string> = { general: '通用', industry: '行业', stock: '个股' }
  return m[s] || s
}

function scopeTagType(s: string): TagType {
  const m: Record<string, TagType> = { general: 'info', industry: 'warning', stock: 'success' }
  return m[s] || 'info'
}

function injectionModeLabel(m: string) {
  const map: Record<string, string> = { none: '不注入', summary: '摘要', full: '完整' }
  return map[m] || m
}

async function loadPolicies() {
  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (filterAgentType.value) params.agent_type = filterAgentType.value
    const res = await promptPoliciesApi.list(params)
    policies.value = res.policies || []
  } catch (e) {
    ElMessage.error('加载策略失败')
    policies.value = []
  } finally {
    loading.value = false
  }
}

async function loadAgents() {
  try {
    const res = await promptPreviewApi.listAgents()
    agents.value = res.agents || []
  } catch {
    agents.value = []
  }
}

function handleRefresh() {
  loadPolicies()
  loadAgents()
}

function goToPreview() {
  router.push('/settings/prompt-preview')
}

function resetEditForm() {
  editingPolicy.value = null
  editForm.value = {
    agent_type: '',
    agent_name: '',
    scope: 'general',
    enabled: true,
    injection_mode: 'summary',
    inherit_industry_for_stock: true,
    include_capability_block: true,
    include_external_gap_notice: true,
    include_comparable_companies: true,
    inject_position: 'analysis_requirements',
  }
}

function handleCreate() {
  editingPolicy.value = null
  resetEditForm()
  editVisible.value = true
}

function handleEdit(row: PromptInjectionPolicy) {
  editingPolicy.value = row
  editForm.value = {
    agent_type: row.agent_type,
    agent_name: row.agent_name,
    scope: row.scope as 'general' | 'industry' | 'stock',
    enabled: row.enabled,
    injection_mode: row.injection_mode,
    inherit_industry_for_stock: row.inherit_industry_for_stock,
    include_capability_block: row.include_capability_block,
    include_external_gap_notice: row.include_external_gap_notice,
    include_comparable_companies: row.include_comparable_companies,
    inject_position: row.inject_position as 'system_prompt' | 'analysis_requirements' | 'constraints',
  }
  editVisible.value = true
}

function handleSave() {
  if (!editForm.value.agent_type || !editForm.value.agent_name) {
    ElMessage.warning('请填写 Agent 类型和名称')
    return
  }

  saving.value = true
  const id = editingPolicy.value?.id
  const isUpdate = !!id
  const payload = {
    enabled: editForm.value.enabled,
    injection_mode: editForm.value.injection_mode,
    inherit_industry_for_stock: editForm.value.inherit_industry_for_stock,
    include_capability_block: editForm.value.include_capability_block,
    include_external_gap_notice: editForm.value.include_external_gap_notice,
    include_comparable_companies: editForm.value.include_comparable_companies,
    inject_position: editForm.value.inject_position,
  }

  const fn = isUpdate
    ? () => promptPoliciesApi.update(id!, payload)
    : () => promptPoliciesApi.create({
        agent_type: editForm.value.agent_type,
        agent_name: editForm.value.agent_name,
        scope: editForm.value.scope,
        ...payload,
      })

  fn()
    .then(() => {
      ElMessage.success(isUpdate ? '保存成功' : '创建成功')
      editVisible.value = false
      loadPolicies()
    })
    .catch((e: any) => {
      ElMessage.error(e?.response?.data?.detail || '操作失败')
    })
    .finally(() => {
      saving.value = false
    })
}

async function handleToggleEnabled(row: PromptInjectionPolicy) {
  if (!row.id) return
  try {
    await promptPoliciesApi.update(row.id, { enabled: row.enabled })
    ElMessage.success('已更新')
  } catch {
    row.enabled = !row.enabled
    ElMessage.error('更新失败')
  }
}

async function handleDelete(row: PromptInjectionPolicy) {
  if (!row.id) return
  try {
    await ElMessageBox.confirm(
      `确定删除 ${row.agent_type}/${row.agent_name} 的 ${scopeLabel(row.scope)} 策略？`,
      '确认删除',
      { type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await promptPoliciesApi.delete(row.id)
    ElMessage.success('已删除')
    loadPolicies()
  } catch {
    ElMessage.error('删除失败')
  }
}

onMounted(() => {
  loadPolicies()
  loadAgents()
})
</script>

<style scoped>
.prompt-policy-manager {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.header-left h1 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 4px 0;
  font-size: 22px;
  font-weight: 600;
}

.header-icon {
  color: var(--el-color-primary);
}

.subtitle {
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

.page-alert {
  margin-bottom: 16px;
}

.page-alert a {
  color: var(--el-color-primary);
}

.policy-card {
  margin-bottom: 16px;
}

.card-title {
  font-weight: 600;
}
</style>
