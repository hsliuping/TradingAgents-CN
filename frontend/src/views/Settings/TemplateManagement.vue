<template>
  <div class="ta-template-management">
    <el-card class="ta-filter-card">
      <el-form :inline="true" :model="filters">
        <el-form-item v-if="!hasAgentTypeParam" label="Agent类型">
          <el-select v-model="filters.agent_type" placeholder="全部" style="width: 220px">
            <el-option-group label="v2.0 Agents">
              <el-option label="分析师 v2.0" value="analysts_v2" />
              <el-option label="研究员 v2.0" value="researchers_v2" />
              <el-option label="辩手 v2.0" value="debators_v2" />
              <el-option label="管理者 v2.0" value="managers_v2" />
              <el-option label="交易员 v2.0" value="trader_v2" />
              <el-option label="复盘分析师 v2.0" value="reviewers_v2" />
              <el-option label="仓位分析 v2.0" value="position_analysis_v2" />
            </el-option-group>
          </el-select>
        </el-form-item>
        <el-form-item label="Agent名称">
          <el-select v-model="filters.agent_name" placeholder="请选择" style="width: 220px" filterable>
            <el-option v-for="opt in agentOptions" :key="opt.code" :label="opt.cn" :value="opt.code" />
          </el-select>
        </el-form-item>
        <el-form-item label="模板名称">
          <el-input v-model="filters.q" placeholder="输入模板名称进行搜索" style="width: 220px" @keyup.enter="loadTemplates" />
        </el-form-item>
        <el-form-item label="偏好">
          <el-select v-model="filters.preference_type" placeholder="全部" style="width: 160px">
            <el-option label="aggressive" value="aggressive" />
            <el-option label="neutral" value="neutral" />
            <el-option label="conservative" value="conservative" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源">
          <el-select v-model="filters.is_system_str" placeholder="全部" style="width: 140px">
            <el-option label="全部" value="" />
            <el-option label="系统" value="true" />
            <el-option label="用户" value="false" />
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
            <el-tag v-if="activeTemplateMap[scope.row.agent_name] === scope.row.id" type="primary">当前生效 · {{ labelPreference(scope.row.preference_type) }}</el-tag>
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
            <!-- 🔥 只有 analysts 和 analysts_v2 类型的 Agent 才显示调试按钮 -->
            <el-button v-if="!scope.row.is_system && canDebug(scope.row)" size="small" type="primary" @click="openDebug(scope.row)">调试</el-button>
            <el-tag v-if="!scope.row.is_system && activeTemplateMap[scope.row.agent_name] === scope.row.id" type="primary">已当前</el-tag>
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
          <el-tab-pane label="用户提示词">
            <pre class="ta-pre">{{ detail.content?.user_prompt }}</pre>
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

    <el-dialog v-model="editVisible" title="编辑模板" width="900px">
      <!-- 可用变量说明 -->
      <el-alert
        type="info"
        :closable="false"
        style="margin-bottom: 16px;"
      >
        <template #title>
          <div style="display: flex; align-items: center; gap: 8px;">
            <el-icon><InfoFilled /></el-icon>
            <span>可用变量说明</span>
          </div>
        </template>
        <div style="line-height: 1.8; font-size: 13px;">
          <p style="margin: 0 0 8px 0;">提示词中可以使用以下变量（系统会自动填充）：</p>
          <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px;">
            <div><code>{ticker}</code> - 股票代码</div>
            <div><code>{company_name}</code> - 公司名称（自动获取）</div>
            <div><code>{market_name}</code> - 市场名称（自动识别）</div>
            <div><code>{current_date}</code> - 当前日期</div>
            <div><code>{currency_name}</code> - 货币名称</div>
            <div><code>{currency_symbol}</code> - 货币符号</div>
            <div><code>{tool_names}</code> - 可用工具列表</div>
            <div><code>{start_date}</code> - 开始日期（1年前）</div>
          </div>
          <p style="margin: 8px 0 0 0; color: #909399; font-size: 12px;">
            💡 这些变量会在运行时自动从工作流状态中提取，无需用户手动提供
          </p>
        </div>
      </el-alert>

      <el-form :model="editForm" label-width="100px">
        <el-form-item label="模板名称">
          <el-input v-model="editForm.template_name" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.remark" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="偏好">
          <el-select v-model="editForm.preference_type" style="width: 160px" placeholder="请选择">
            <el-option label="激进型" value="aggressive" />
            <el-option label="中性型" value="neutral" />
            <el-option label="保守型" value="conservative" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="editForm.status" style="width: 160px">
            <el-option label="可用" value="active" />
            <el-option label="草稿" value="draft" />
          </el-select>
        </el-form-item>
        <el-form-item label="系统提示词">
          <el-input
            v-model="editForm.content.system_prompt"
            type="textarea"
            :autosize="{ minRows: 10, maxRows: 24 }"
            placeholder="请输入系统提示词，可使用上方的变量，如：你是{company_name}的分析师..."
          />
        </el-form-item>
        <el-form-item label="用户提示词">
          <el-input
            v-model="editForm.content.user_prompt"
            type="textarea"
            :autosize="{ minRows: 10, maxRows: 24 }"
            placeholder="请输入用户提示词，可使用上方的变量"
          />
        </el-form-item>
        <el-form-item label="工具指导">
          <el-input
            v-model="editForm.content.tool_guidance"
            type="textarea"
            :rows="4"
            placeholder="请输入工具使用指导"
          />
        </el-form-item>
        <el-form-item label="分析要求">
          <el-input
            v-model="editForm.content.analysis_requirements"
            type="textarea"
            :autosize="{ minRows: 8, maxRows: 20 }"
            placeholder="请输入分析要求"
          />
        </el-form-item>
        <el-form-item label="输出格式">
          <el-input
            v-model="editForm.content.output_format"
            type="textarea"
            :rows="4"
            placeholder="请输入输出格式要求"
          />
        </el-form-item>
        <el-form-item label="约束条件">
          <el-input
            v-model="editForm.content.constraints"
            type="textarea"
            :rows="3"
            placeholder="请输入约束条件"
          />
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
import { useRoute, useRouter } from 'vue-router'
import { TemplatesApi, type TemplateItem } from '@/api/templates'
import { ApiClient } from '@/api/request'
import { ElMessage } from 'element-plus'
import { InfoFilled } from '@element-plus/icons-vue'

const route = useRoute()
const filters = reactive<{ agent_type?: string; agent_name?: string; preference_type?: string; is_system?: boolean; is_system_str: string; status?: string; q?: string }>({ is_system_str: '' })
const hasAgentTypeParam = computed(() => typeof route.query.agent_type === 'string')
const items = ref<TemplateItem[]>([])
const itemsSorted = computed(() => {
  const arr = [...items.value]
  arr.sort((a, b) => {
    const sysDiff = Number(a.is_system) - Number(b.is_system)
    if (sysDiff !== 0) return sysDiff
    const ta = a.updated_at || a.created_at || ''
    const tb = b.updated_at || b.created_at || ''
    const taNum = ta ? new Date(ta).getTime() : 0
    const tbNum = tb ? new Date(tb).getTime() : 0
    return tbNum - taNum
  })
  return arr
})
const loading = ref(false)
const detailVisible = ref(false)
const detail = ref<any>(null)
const editVisible = ref(false)
const editId = ref<string>('')
const editForm = ref<any>({ template_name: '', remark: '', preference_type: '', status: 'draft', content: { system_prompt: '', user_prompt: '', tool_guidance: '', analysis_requirements: '', output_format: '', constraints: '' } })
const editSetActive = ref(false)
const editAgentMeta = ref<{ agent_type?: string; agent_name?: string }>({})

const agentTypeMap: Record<string, string> = {
  // v1.0
  //analysts: '分析师 v1.0',
  //researchers: '研究员 v1.0',
  //debators: '辩手 v1.0',
  //managers: '管理者 v1.0',
  //trader: '交易员 v1.0',
  //reviewers: '复盘分析师 v1.0',
  //position_analysis: '仓位分析 v1.0',
  // v2.0
  analysts_v2: '独立分析师 v2.0',
  researchers_v2: '看涨看跌研究员 v2.0',
  debators_v2: '风险分析 v2.0',
  managers_v2: '研究/风险管理者 v2.0',
  trader_v2: '交易员 v2.0',
  reviewers_v2: '复盘分析 v2.0',
  position_analysis_v2: '仓位分析 v2.0'
}

const agentNameMap: Record<string, string> = {
  // v1.0 agents
  //market_analyst: '市场分析师',
  //fundamentals_analyst: '基本面分析师',
  //news_analyst: '新闻分析师',
  //social_media_analyst: '社媒分析师',
  //china_market_analyst: '中国市场分析师',
  //index_analyst: '大盘/指数分析师',
  //sector_analyst: '行业/板块分析师',
  //bull_researcher: '看涨研究员',
  //bear_researcher: '看跌研究员',
  //aggressive_debator: '激进辩手',
  //conservative_debator: '保守辩手',
  //neutral_debator: '中性辩手',
  //research_manager: '研究管理者',
  // v2.0 agents
  fundamentals_analyst_v2: '基本面分析师 v2.0',
  market_analyst_v2: '市场分析师 v2.0',
  news_analyst_v2: '新闻分析师 v2.0',
  social_analyst_v2: '社交媒体分析师 v2.0',
  sector_analyst_v2: '板块分析师 v2.0',
  index_analyst_v2: '大盘分析师 v2.0',
  bull_researcher_v2: '看涨研究员 v2.0',
  bear_researcher_v2: '看跌研究员 v2.0',
  research_manager_v2: '研究经理 v2.0',
  risk_manager_v2: '风险管理者 v2.0',
  trader_v2: '交易员 v2.0',
  risky_analyst_v2: '激进风险分析师 v2.0',
  safe_analyst_v2: '保守风险分析师 v2.0',
  neutral_analyst_v2: '中性风险分析师 v2.0',
  timing_analyst_v2: '时机分析师 v2.0',
  position_analyst_v2: '仓位分析师 v2.0',
  emotion_analyst_v2: '情绪分析师 v2.0',
  attribution_analyst_v2: '归因分析师 v2.0',
  review_manager_v2: '复盘总结师 v2.0',
  pa_technical_v2: '技术面分析师 v2.0',
  pa_fundamental_v2: '基本面分析师 v2.0',
  pa_risk_v2: '风险评估师 v2.0',
  pa_advisor_v2: '操作建议师 v2.0'
}

const agentNameReverseMap: Record<string, string> = Object.fromEntries(
  Object.entries(agentNameMap).map(([code, cn]) => [cn, code])
)
const agentTypeMapList: Record<string, string[]> = {
  // v1.0
  analysts: ['market_analyst','fundamentals_analyst','news_analyst','social_media_analyst','index_analyst','sector_analyst'],
  researchers: ['bull_researcher','bear_researcher'],
  debators: ['aggressive_debator','conservative_debator','neutral_debator'],
  managers: ['research_manager','risk_manager'],
  trader: ['trader', 'position_advisor'],
  reviewers: ['timing_analyst','position_analyst','emotion_analyst','attribution_analyst','review_manager'],
  position_analysis: ['pa_technical','pa_fundamental','pa_risk','pa_advisor'],
  // v2.0
  analysts_v2: ['fundamentals_analyst_v2','market_analyst_v2','news_analyst_v2','social_analyst_v2','sector_analyst_v2','index_analyst_v2'],
  researchers_v2: ['bull_researcher_v2','bear_researcher_v2'],
  debators_v2: ['risky_analyst_v2','safe_analyst_v2','neutral_analyst_v2'],
  managers_v2: ['research_manager_v2','risk_manager_v2'],
  trader_v2: ['trader_v2'],
  reviewers_v2: ['timing_analyst_v2','position_analyst_v2','emotion_analyst_v2','attribution_analyst_v2','review_manager_v2'],
  position_analysis_v2: ['pa_technical_v2','pa_fundamental_v2','pa_risk_v2','pa_advisor_v2']
}
const availableAgentCodes = ref<string[]>([])
const agentOptions = computed(() => {
  const currentType = filters.agent_type || (typeof route.query.agent_type === 'string' ? (route.query.agent_type as string) : undefined)
  const baseCodes = currentType ? (agentTypeMapList[currentType] || []) : Object.keys(agentNameMap)
  const codes = availableAgentCodes.value.length ? baseCodes.filter(c => availableAgentCodes.value.includes(c)) : baseCodes
  return codes.map((code) => ({ code, cn: agentNameMap[code] })).sort((a, b) => a.cn.localeCompare(b.cn))
})

const loadAvailableAgents = async () => {
  try {
    if (!filters.agent_type && typeof route.query.agent_type !== 'string') {
      availableAgentCodes.value = []
      return
    }
    const currentType = filters.agent_type || (route.query.agent_type as string)
    const res = await TemplatesApi.list({ agent_type: currentType, limit: 200 })
    const items = (res.data && (res.data as any).items) ? (res.data as any).items : []
    const codes = Array.from(new Set(items.map((it: any) => it.agent_name).filter(Boolean)))
    availableAgentCodes.value = codes as string[]
    // 选中值无效时清空
    if (filters.agent_name && !codes.includes(filters.agent_name)) {
      filters.agent_name = undefined
    }
  } catch {
    availableAgentCodes.value = []
  }
}

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
  filters.is_system_str = ''
  filters.status = ''
}

// 将字符串的 is_system_str 转换为 boolean 类型
const getIsSystemValue = (): boolean | undefined => {
  if (filters.is_system_str === 'true') return true
  if (filters.is_system_str === 'false') return false
  return undefined
}

const loadTemplates = async () => {
  loading.value = true
  try {
    const res = await TemplatesApi.list({
      agent_type: filters.agent_type,
      agent_name: (filters.agent_name && agentNameReverseMap[filters.agent_name]) ? agentNameReverseMap[filters.agent_name] : filters.agent_name,
      preference_type: filters.preference_type,
      is_system: getIsSystemValue(),
      status: filters.status || undefined,
      q: filters.q || undefined,
      skip: 0,
      limit: 200
    })
    let allItems = (res.data && (res.data as any).items) ? (res.data as any).items : (Array.isArray(res.data) ? res.data : [])
    
    // 🔥 过滤掉v1.0版本的模板，只保留v2.0版本
    const v1AgentTypes = ['analysts', 'researchers', 'debators', 'managers', 'trader', 'reviewers', 'position_analysis']
    items.value = allItems.filter((item: any) => {
      // 如果指定了agent_type，且是v1.0类型，则过滤掉
      if (item.agent_type && v1AgentTypes.includes(item.agent_type)) {
        return false
      }
      // 如果没有指定agent_type，也过滤掉v1.0类型
      if (!filters.agent_type && item.agent_type && v1AgentTypes.includes(item.agent_type)) {
        return false
      }
      return true
    })
    
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
    preference_type: res.data?.preference_type || '',
    status: res.data?.status || 'draft',
    content: {
      system_prompt: res.data?.content?.system_prompt || '',
      user_prompt: res.data?.content?.user_prompt || '',
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
      preference_type: editForm.value.preference_type || undefined,
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
    const { useAuthStore } = await import('@/stores/auth')
    const userId = useAuthStore().user?.id
    const created = await TemplatesApi.clone(id, undefined, userId)
    if ((created as any).success) {
      ElMessage.success('克隆成功')
      loadTemplates()
    } else {
      ElMessage.error((created as any).message || '克隆失败')
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

/**
 * 判断模板是否可以调试
 * 只有 analysts 和 analysts_v2 类型的 Agent 才支持调试
 * 因为调试需要数据准备，目前只有这两种类型实现了数据准备逻辑
 */
const canDebug = (row: any) => {
  const agentType = row.agent_type
  return agentType === 'analysts' || agentType === 'analysts_v2'
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
  // 🔥 如果URL参数中是v1.0的agent_type，忽略它（只显示v2.0）
  const v1AgentTypes = ['analysts', 'researchers', 'debators', 'managers', 'trader', 'reviewers', 'position_analysis']
  if (typeof qp.agent_type === 'string' && !v1AgentTypes.includes(qp.agent_type)) {
    filters.agent_type = qp.agent_type
  }
  if (typeof qp.agent_name === 'string') filters.agent_name = qp.agent_name
  if (typeof qp.is_system === 'string') {
    // 同步设置 is_system 和 is_system_str
    if (qp.is_system === 'true') {
      filters.is_system = true
      filters.is_system_str = 'true'
    } else if (qp.is_system === 'false') {
      filters.is_system = false
      filters.is_system_str = 'false'
    }
  }
  // 如果当前选择的 agent_name 不在可选项中，重置为空，避免无效查询
  const validCodes = agentOptions.value.map(o => o.code)
  if (filters.agent_name && !validCodes.includes(filters.agent_name)) {
    filters.agent_name = undefined
  }
  loadAvailableAgents()
  loadTemplates()
})

watch(() => filters.agent_type, () => {
  loadAvailableAgents()
})
const router = useRouter()
const openDebug = (row: any) => {
  if (row?.is_system) {
    ElMessage.warning('系统模板不支持调试')
    return
  }
  const resolveAgentTypeByName = (agentName: string) => {
    for (const [type, list] of Object.entries(agentTypeMapList)) {
      if (list.includes(agentName)) return type
    }
    const qpType = typeof route.query.agent_type === 'string' ? (route.query.agent_type as string) : undefined
    return row?.agent_type || filters.agent_type || qpType || 'analysts'
  }
  const currentAgentType = resolveAgentTypeByName(row.agent_name)

  const query: any = {
    analyst_type: mapAnalystType(row.agent_name),
    template_id: row.id,
    symbol: '',
    agent_type: currentAgentType // 添加agent_type参数用于区分版本
  }

  console.log('🔍 [模板管理] 调试按钮跳转参数:', query)
  router.push({ name: 'TemplateDebug', query })
}

const mapAnalystType = (agentName: string) => {
  if (/_v2$/.test(agentName)) return agentName
  if (agentName === 'fundamentals_analyst' || agentName === '基本面分析师') return 'fundamentals'
  if (agentName === 'market_analyst' || agentName === '市场分析师') return 'market'
  if (agentName === 'china_market_analyst' || agentName === '中国市场分析师') return 'market'
  if (agentName === 'news_analyst' || agentName === '新闻分析师') return 'news'
  if (agentName === 'social_media_analyst' || agentName === '社媒分析师') return 'social'
  if (agentName === 'index_analyst' || agentName === '大盘/指数分析师') return 'index_analyst'
  if (agentName === 'sector_analyst' || agentName === '行业/板块分析师') return 'sector_analyst'
  return 'fundamentals'
}

</script>

<style scoped>
.ta-template-management { padding: 16px }
.ta-filter-card { margin-bottom: 12px }
.ta-pre { white-space: pre-wrap; background: var(--el-fill-color); color: var(--el-text-color-primary); padding: 12px; border-radius: 6px; border: 1px solid var(--el-border-color-lighter) }
:deep(.ta-row-system) { background: var(--el-fill-color-lighter) }
:deep(.ta-row-user) { background: var(--el-color-success-light-9) }
:deep(.ta-row-active) { background: var(--el-color-primary-light-8); border-left: 4px solid var(--el-color-primary) }
</style>
