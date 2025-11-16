<template>
  <div class="ta-template-management">
    <el-card class="ta-filter-card">
      <el-form :inline="true" :model="filters">
        <el-form-item v-if="!hasAgentTypeParam" label="Agent类型">
          <el-select v-model="filters.agent_type" placeholder="全部" style="width: 180px">
            <el-option label="analysts" value="analysts" />
            <el-option label="researchers" value="researchers" />
            <el-option label="debators" value="debators" />
            <el-option label="managers" value="managers" />
            <el-option label="trader" value="trader" />
          </el-select>
        </el-form-item>
        <el-form-item label="Agent名称">
          <el-input v-model="filters.agent_name" placeholder="例如 market_analyst" style="width: 220px" />
        </el-form-item>
        <el-form-item label="偏好">
          <el-select v-model="filters.preference_type" placeholder="全部" style="width: 160px">
            <el-option label="aggressive" value="aggressive" />
            <el-option label="neutral" value="neutral" />
            <el-option label="conservative" value="conservative" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源">
          <el-select v-model="filters.is_system" placeholder="全部" style="width: 140px">
            <el-option label="全部" :value="undefined" />
            <el-option label="系统" :value="true" />
            <el-option label="用户" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" style="width: 140px">
            <el-option label="全部" value="" />
            <el-option label="active" value="active" />
            <el-option label="draft" value="draft" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadTemplates">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="ta-table-card">
      <el-table :data="itemsSorted" style="width: 100%" v-loading="loading" :row-class-name="rowClassName">
        <el-table-column prop="template_name" label="模板名称" min-width="240" />
        <el-table-column v-if="!hasAgentTypeParam" label="Agent类型" width="140">
          <template #default="scope">
            <span>{{ labelAgentType(scope.row.agent_type) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="Agent名称" width="200">
          <template #default="scope">
            <span>{{ labelAgentName(scope.row.agent_name) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="偏好" width="140">
          <template #default="scope">
            <span>{{ labelPreference(scope.row.preference_type) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="160">
          <template #default="scope">
            <el-tag v-if="activeTemplateMap[scope.row.agent_name] === scope.row.id" type="primary">当前生效</el-tag>
            <el-tag v-else-if="scope.row.status === 'draft'" type="warning">草稿</el-tag>
            <el-tag v-else>可用</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="version" label="版本" width="100" />
        <el-table-column label="来源" width="120">
          <template #default="scope">
            <el-tag type="info" v-if="scope.row.is_system">系统</el-tag>
            <el-tag type="success" v-else>用户</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="200">
          <template #default="scope">
            <span>{{ formatDate(scope.row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="200">
          <template #default="scope">
            <span>{{ formatDate(scope.row.updated_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="360" fixed="right">
          <template #default="scope">
            <el-button size="small" @click="viewDetail(scope.row.id)">查看</el-button>
            <el-button size="small" type="warning" @click="cloneTemplate(scope.row.id)">克隆</el-button>
            <el-button v-if="!scope.row.is_system" size="small" type="success" @click="openEdit(scope.row.id)">编辑</el-button>
            <el-button v-if="!scope.row.is_system" size="small" type="danger" @click="deleteTemplate(scope.row.id)">删除</el-button>
            <el-button v-if="!scope.row.is_system && activeTemplateMap[scope.row.agent_name] !== scope.row.id" size="small" type="info" @click="activateTemplate(scope.row)">设为当前</el-button>
            <el-tag v-else-if="!scope.row.is_system && activeTemplateMap[scope.row.agent_name] === scope.row.id" type="primary">已当前</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="detailVisible" title="模板详情" width="700px">
      <div v-if="detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="模板名称">{{ detail.template_name }}</el-descriptions-item>
          <el-descriptions-item label="Agent">{{ labelAgentType(detail.agent_type) }} / {{ labelAgentName(detail.agent_name) }}</el-descriptions-item>
          <el-descriptions-item label="偏好">{{ labelPreference(detail.preference_type) }}</el-descriptions-item>
          <el-descriptions-item label="备注">{{ detail.remark || '-' }}</el-descriptions-item>
          <el-descriptions-item label="版本">{{ detail.version }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ labelStatus(detail.status) }}</el-descriptions-item>
        </el-descriptions>
        <el-divider />
        <el-tabs>
          <el-tab-pane label="系统提示词">
            <pre class="ta-pre">{{ detail.content?.system_prompt }}</pre>
          </el-tab-pane>
          <el-tab-pane label="工具指导">
            <pre class="ta-pre">{{ detail.content?.tool_guidance }}</pre>
          </el-tab-pane>
          <el-tab-pane label="分析要求">
            <pre class="ta-pre">{{ detail.content?.analysis_requirements }}</pre>
          </el-tab-pane>
          <el-tab-pane label="输出格式">
            <pre class="ta-pre">{{ detail.content?.output_format }}</pre>
          </el-tab-pane>
          <el-tab-pane label="约束条件">
            <pre class="ta-pre">{{ detail.content?.constraints }}</pre>
          </el-tab-pane>
        </el-tabs>
      </div>
      <template #footer>
        <el-button @click="detailVisible=false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editVisible" title="编辑模板" width="800px">
      <el-form :model="editForm" label-width="100px">
        <el-form-item label="模板名称">
          <el-input v-model="editForm.template_name" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.remark" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="editForm.status" style="width: 160px">
            <el-option label="可用" value="active" />
            <el-option label="草稿" value="draft" />
          </el-select>
        </el-form-item>
        <el-form-item label="系统提示词">
          <el-input v-model="editForm.content.system_prompt" type="textarea" :autosize="{ minRows: 10, maxRows: 24 }" />
        </el-form-item>
        <el-form-item label="工具指导">
          <el-input v-model="editForm.content.tool_guidance" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="分析要求">
          <el-input v-model="editForm.content.analysis_requirements" type="textarea" :autosize="{ minRows: 8, maxRows: 20 }" />
        </el-form-item>
        <el-form-item label="输出格式">
          <el-input v-model="editForm.content.output_format" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="约束条件">
          <el-input v-model="editForm.content.constraints" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="设为当前">
          <el-checkbox v-model="editSetActive">保存后设为当前模板</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible=false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { TemplatesApi, type TemplateItem } from '@/api/templates'
import { ApiClient } from '@/api/request'
import { ElMessage } from 'element-plus'

const route = useRoute()
const filters = reactive<{ agent_type?: string; agent_name?: string; preference_type?: string; is_system?: boolean; status?: string }>({})
const hasAgentTypeParam = computed(() => typeof route.query.agent_type === 'string')
const items = ref<TemplateItem[]>([])
const itemsSorted = computed(() => {
  const arr = [...items.value]
  arr.sort((a, b) => Number(a.is_system) - Number(b.is_system))
  return arr
})
const loading = ref(false)
const detailVisible = ref(false)
const detail = ref<any>(null)
const editVisible = ref(false)
const editId = ref<string>('')
const editForm = ref<any>({ template_name: '', remark: '', status: 'draft', content: { system_prompt: '', tool_guidance: '', analysis_requirements: '', output_format: '', constraints: '' } })
const editSetActive = ref(false)
const editAgentMeta = ref<{ agent_type?: string; agent_name?: string }>({})

const agentTypeMap: Record<string, string> = {
  analysts: '分析师',
  researchers: '研究员',
  debators: '辩手',
  managers: '管理者',
  trader: '交易员'
}

const agentNameMap: Record<string, string> = {
  market_analyst: '市场分析师',
  fundamentals_analyst: '基本面分析师',
  news_analyst: '新闻分析师',
  social_media_analyst: '社媒分析师',
  china_market_analyst: '中国市场分析师',
  bull_researcher: '看涨研究员',
  bear_researcher: '看跌研究员',
  aggressive_debator: '激进辩手',
  conservative_debator: '保守辩手',
  neutral_debator: '中性辩手',
  research_manager: '研究管理者',
  risk_manager: '风险管理者',
  trader: '交易员'
}

const agentNameReverseMap: Record<string, string> = Object.fromEntries(
  Object.entries(agentNameMap).map(([code, cn]) => [cn, code])
)

const labelAgentType = (v?: string) => (v && agentTypeMap[v]) || v || '-'
const labelAgentName = (v?: string) => (v && agentNameMap[v]) || v || '-'
const labelPreference = (v?: string) => {
  if (!v) return '通用'
  if (v === 'aggressive') return '激进型'
  if (v === 'neutral') return '中性型'
  if (v === 'conservative') return '保守型'
  return v
}
const labelStatus = (v?: string) => {
  if (v === 'active') return '已启用'
  if (v === 'draft') return '草稿'
  return v || '-'
}

const formatDate = (v?: string) => {
  if (!v) return '-'
  try { return new Date(v).toLocaleString() } catch { return v }
}

const resetFilters = () => {
  filters.agent_type = undefined
  filters.agent_name = ''
  filters.preference_type = undefined
  filters.is_system = undefined
  filters.status = ''
}

const loadTemplates = async () => {
  loading.value = true
  try {
    const res = await TemplatesApi.list({
      agent_type: filters.agent_type,
      agent_name: (filters.agent_name && agentNameReverseMap[filters.agent_name]) ? agentNameReverseMap[filters.agent_name] : filters.agent_name,
      preference_type: filters.preference_type,
      is_system: filters.is_system,
      status: filters.status || undefined
    })
    items.value = (res.data && (res.data as any).items) ? (res.data as any).items : (Array.isArray(res.data) ? res.data : [])
    await loadActiveId()
  } catch (e: any) {
    ElMessage.error(e?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

const viewDetail = async (id: string) => {
  try {
    const res = await TemplatesApi.get(id)
    detail.value = res.data
    detailVisible.value = true
  } catch (e: any) {
    ElMessage.error(e?.message || '获取详情失败')
  }
}


const openEdit = async (id: string) => {
  const res = await TemplatesApi.get(id)
  editId.value = id
  editAgentMeta.value = { agent_type: res.data?.agent_type, agent_name: res.data?.agent_name }
  editForm.value = {
    template_name: res.data?.template_name || '',
    remark: res.data?.remark || '',
    status: res.data?.status || 'draft',
    content: {
      system_prompt: res.data?.content?.system_prompt || '',
      tool_guidance: res.data?.content?.tool_guidance || '',
      analysis_requirements: res.data?.content?.analysis_requirements || '',
      output_format: res.data?.content?.output_format || '',
      constraints: res.data?.content?.constraints || ''
    }
  }
  editSetActive.value = false
  editVisible.value = true
}

const saveEdit = async () => {
  try {
    const { useAuthStore } = await import('@/stores/auth')
    const userId = useAuthStore().user?.id
    await ApiClient.put(`/api/v1/templates/${editId.value}`, {
      template_name: editForm.value.template_name,
      remark: editForm.value.remark,
      status: editForm.value.status,
      content: editForm.value.content
    }, { params: { user_id: userId } })
    ElMessage.success('保存成功')
    editVisible.value = false
    loadTemplates()
    if (editSetActive.value) {
      await activateTemplate({
        agent_type: editAgentMeta.value.agent_type,
        agent_name: editAgentMeta.value.agent_name,
        id: editId.value,
        is_system: false
      })
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  }
}

const cloneTemplate = async (id: string) => {
  try {
    const res = await TemplatesApi.get(id)
    const source = res.data
    const nameSuffix = new Date().toLocaleString()
    const { useAuthStore } = await import('@/stores/auth')
    const userId = useAuthStore().user?.id
    const payload = {
      agent_type: source.agent_type,
      agent_name: source.agent_name,
      template_name: `${source.template_name}（副本 ${nameSuffix}）`,
      preference_type: source.preference_type,
      content: source.content,
      status: 'draft',
      remark: source.remark || ''
    }
    const created = await ApiClient.post(`/api/v1/templates`, payload, { params: { user_id: userId, base_template_id: source.id } })
    if (created.success) {
      ElMessage.success('克隆成功')
      loadTemplates()
    } else {
      ElMessage.error(created.message || '克隆失败')
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '克隆失败')
  }
}

const activateTemplate = async (row: any) => {
  try {
    const { useAuthStore } = await import('@/stores/auth')
    const userId = useAuthStore().user?.id
    const body = {
      agent_type: row.agent_type,
      agent_name: row.agent_name,
      template_id: row.id,
      preference_id: undefined
    }
    const resp = await ApiClient.post(`/api/v1/user-template-configs`, body, { params: { user_id: userId } })
    if (resp.success) {
      ElMessage.success('已设为当前模板')
      await loadActiveId()
    } else {
      ElMessage.error(resp.message || '设置失败')
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '设置失败')
  }
}

const deleteTemplate = async (id: string) => {
  try {
    const { useAuthStore } = await import('@/stores/auth')
    const userId = useAuthStore().user?.id
    const resp = await ApiClient.delete(`/api/v1/templates/${id}`, { params: { user_id: userId } })
    if ((resp as any).success) {
      ElMessage.success('已删除')
      loadTemplates()
    } else {
      ElMessage.error((resp as any).message || '删除失败')
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '删除失败')
  }
}

const activeTemplateMap = ref<Record<string, string>>({})
const loadActiveId = async () => {
  try {
    if (!filters.agent_type) return
    const { useAuthStore } = await import('@/stores/auth')
    const userId = useAuthStore().user?.id
    const resp = await ApiClient.get(`/api/v1/user-template-configs/user/${userId}`)
    if ((resp as any).success) {
      const list = resp.data?.configs || []
      const map: Record<string, string> = {}
      for (const c of list) {
        if (c.agent_type === filters.agent_type && c.is_active) {
          map[c.agent_name] = c.template_id
        }
      }
      activeTemplateMap.value = map
    } else {
      activeTemplateMap.value = {}
    }
  } catch {
    activeTemplateMap.value = {}
  }
}

const rowClassName = ({ row }: any) => {
  const r = row
  const classes: string[] = []
  if (r.is_system) classes.push('ta-row-system')
  else classes.push('ta-row-user')
  if (activeTemplateMap.value[r.agent_name] && r.id === activeTemplateMap.value[r.agent_name]) classes.push('ta-row-active')
  return classes.join(' ')
}

onMounted(() => {
  const qp: any = route.query || {}
  if (typeof qp.agent_type === 'string') filters.agent_type = qp.agent_type
  if (typeof qp.is_system === 'string') {
    if (qp.is_system === 'true') filters.is_system = true
    else if (qp.is_system === 'false') filters.is_system = false
  }
  loadTemplates()
})
</script>

<style scoped>
.ta-template-management { padding: 16px }
.ta-filter-card { margin-bottom: 12px }
.ta-pre { white-space: pre-wrap; background: var(--el-fill-color); color: var(--el-text-color-primary); padding: 12px; border-radius: 6px; border: 1px solid var(--el-border-color-lighter) }
:deep(.ta-row-system) { background: var(--el-fill-color-lighter) }
:deep(.ta-row-user) { background: var(--el-color-success-light-9) }
:deep(.ta-row-active) { background: var(--el-color-primary-light-8); border-left: 4px solid var(--el-color-primary) }
</style>