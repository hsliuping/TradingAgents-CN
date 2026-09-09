<template>
  <div class="agent-workshop-manager-page">
    <div class="page-header">
      <div class="header-left">
        <h1>Agent 工坊</h1>
        <span class="subtitle">管理工坊 Agent 和已发布 Agent，支持讨论、生成、评估和发布。</span>
      </div>
      <div class="header-right">
        <el-button plain @click="goToLanding()">
          返回总览
        </el-button>
        <el-button type="primary" @click="router.push({ path: '/workflow/agent-studio', query: { mode: 'new' } })">
          新建 Agent
        </el-button>
        <el-button @click="refreshAll" :loading="draftLoading || listLoading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <el-tabs v-model="activeTab" type="card" class="workshop-tabs">
      <el-tab-pane label="工坊 Agent" name="workshop">
    <div class="summary-grid">
      <el-card shadow="never" class="summary-card">
        <div class="summary-label">草稿会话</div>
        <div class="summary-value">{{ draftSessions.length }}</div>
        <div class="summary-note">还在讨论或待继续的 Agent</div>
      </el-card>
      <el-card shadow="never" class="summary-card">
        <div class="summary-label">Agent 规格</div>
        <div class="summary-value">{{ specs.length }}</div>
        <div class="summary-note">已经沉淀下来的 Agent 草案</div>
      </el-card>
      <el-card shadow="never" class="summary-card">
        <div class="summary-label">测试中</div>
        <div class="summary-value">{{ testingCount }}</div>
        <div class="summary-note">已经生成版本，正在验证效果</div>
      </el-card>
    </div>

    <div class="draft-section">
      <div class="section-header">
        <h2>进行中的工坊会话</h2>
        <el-button text size="small" @click="loadDrafts">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>

      <div v-if="draftLoading" class="card-grid loading-grid">
        <el-skeleton v-for="idx in 3" :key="idx" animated>
          <template #template>
            <el-card shadow="never" class="draft-card skeleton-card">
              <el-skeleton-item variant="h3" style="width: 60%" />
              <el-skeleton-item variant="text" style="margin-top: 12px" />
              <el-skeleton-item variant="text" style="width: 80%" />
            </el-card>
          </template>
        </el-skeleton>
      </div>

      <div v-else-if="draftSessions.length" class="card-grid">
        <el-card v-for="draft in draftSessions" :key="draft.session_id" shadow="never" class="draft-card">
          <div class="draft-head">
            <el-tag size="small" :type="stageTagType(draft.stage)">{{ stageText(draft.stage) }}</el-tag>
            <span class="draft-time">{{ formatTime(draft.updated_at) }}</span>
          </div>
          <div class="draft-title">{{ draft.current_spec_snapshot?.name || '未命名 Agent' }}</div>
          <div class="draft-preview">{{ getDraftPreview(draft) }}</div>
          <div class="draft-meta">
            <span>轮次 {{ draft.current_round }}</span>
            <span>齐备度 {{ Math.round((draft.completeness_score || 0) * 100) }}%</span>
            <span>{{ statusText(draft.feasibility_status) }}</span>
          </div>
          <div class="draft-actions">
            <el-button type="primary" size="small" @click="goToWorkshop(draft.session_id)">继续讨论</el-button>
            <el-button size="small" @click="goToWorkshop(draft.session_id)">进入工作页</el-button>
            <el-button type="danger" size="small" plain @click="handleDeleteDraftSession(draft)">删除</el-button>
          </div>
        </el-card>
      </div>

      <el-empty v-else description="当前没有进行中的 Agent 会话" />
    </div>

    <div class="spec-section">
      <div class="section-header">
        <h2>Agent 管理</h2>
        <div class="section-tools">
          <el-input
            v-model="searchKeyword"
            clearable
            placeholder="搜索 Agent 名称、领域或版本"
            class="search-input"
          />
          <el-radio-group v-model="filterStatus" size="small">
            <el-radio-button label="">全部</el-radio-button>
            <el-radio-button label="draft">草案</el-radio-button>
            <el-radio-button label="testing">测试中</el-radio-button>
            <el-radio-button label="active">已启用</el-radio-button>
            <el-radio-button label="archived">已归档</el-radio-button>
          </el-radio-group>
        </div>
      </div>

      <div v-loading="listLoading" class="group-list">
        <template v-if="filteredSpecs.length">
          <section v-for="group in specGroups" :key="group.status" v-show="group.items.length" class="group-section">
            <div class="group-header">
              <div class="group-title-row">
                <h3>{{ group.title }}</h3>
                <el-tag effect="plain">{{ group.items.length }}</el-tag>
              </div>
              <p>{{ group.description }}</p>
            </div>

            <div class="spec-card-grid">
              <el-card v-for="spec in group.items" :key="spec.spec_id" shadow="never" class="spec-card">
                <div class="spec-card-head">
                  <div class="spec-card-title">{{ spec.name }}</div>
                  <el-tag size="small" :type="specStatusTagType(spec.status)">{{ specStatusText(spec.status) }}</el-tag>
                </div>
                <div class="spec-card-goal" v-if="spec.primary_goal">
                  <el-tooltip placement="top" :show-after="400" :content="spec.primary_goal" effect="light" popper-class="long-text-tooltip">
                    <span class="text-ellipsis-2" @click.stop>{{ spec.primary_goal }}</span>
                  </el-tooltip>
                </div>
                <div class="spec-card-goal placeholder" v-else>还没有填写主要目标</div>
                <div class="spec-card-meta">
                  <span>{{ spec.domain || '未分类' }}</span>
                  <span>{{ getLatestSpecVersion(spec)?.version_id || spec.current_version_id || '无版本' }}</span>
                  <span>{{ formatTime(spec.updated_at) }}</span>
                </div>
                <div v-if="getLatestSpecVersion(spec)" class="spec-card-version-summary">
                  <div class="spec-card-version-head">
                    <strong>v{{ getLatestSpecVersion(spec)?.version }}</strong>
                    <el-tag size="small" effect="plain" :type="getVersionStatusTagType(getLatestSpecVersion(spec)?.status)">
                      {{ getVersionStatusText(getLatestSpecVersion(spec)?.status) }}
                    </el-tag>
                    <el-tag
                      v-if="getLatestSpecVersion(spec)?.last_evaluation_summary"
                      size="small"
                      effect="plain"
                      :type="getEvaluationDecisionTagType(getLatestSpecVersion(spec)?.last_evaluation_summary?.decision)"
                    >
                      {{ getEvaluationDecisionText(getLatestSpecVersion(spec)?.last_evaluation_summary?.decision) }}
                    </el-tag>
                  </div>
                  <div v-if="getLatestSpecVersion(spec)?.prompt_template_project_memory_binding_summary" class="spec-card-summary-text">
                    <el-popover
                      placement="top"
                      :width="360"
                      trigger="click"
                      :content="getLatestSpecVersion(spec)?.prompt_template_project_memory_binding_summary?.summary"
                    >
                      <template #reference>
                        <span class="text-ellipsis-3 clickable">{{ getLatestSpecVersion(spec)?.prompt_template_project_memory_binding_summary?.summary }}</span>
                      </template>
                    </el-popover>
                  </div>
                  <div v-if="getLatestSpecVersion(spec)?.prompt_template_project_memory_binding_summary || getLatestSpecVersion(spec)?.last_evaluation_summary?.project_memory_binding" class="spec-card-summary-meta">
                    <el-tag
                      v-if="getLatestSpecVersion(spec)?.last_evaluation_summary?.project_memory_binding"
                      size="small"
                      effect="plain"
                      :type="getProjectMemorySummaryTagType(getLatestSpecVersion(spec)?.last_evaluation_summary?.project_memory_binding?.review_status)"
                    >
                      {{ getProjectMemorySummaryText(getLatestSpecVersion(spec)?.last_evaluation_summary?.project_memory_binding?.review_status) }}
                    </el-tag>
                    <span v-if="typeof getLatestSpecVersion(spec)?.last_evaluation_summary?.overall_score === 'number'">
                      综合分 {{ getLatestSpecVersion(spec)?.last_evaluation_summary?.overall_score }}
                    </span>
                  </div>
                </div>
                <div class="spec-card-tags" v-if="spec.outputs?.length">
                  <el-tooltip
                    v-for="(item, idx) in getSpecOutputTags(spec).slice(0, 4)"
                    :key="idx"
                    placement="top"
                    trigger="click"
                    :content="item"
                    effect="light"
                    popper-class="long-text-tooltip"
                  >
                    <div class="spec-output-item text-ellipsis-1 clickable">{{ item }}</div>
                  </el-tooltip>
                </div>
                <div class="spec-card-actions">
                  <el-button type="primary" size="small" @click="openAgentStudio(spec)">Agent 工作室</el-button>
                  <el-button size="small" @click="openSpec(spec)">查看规格</el-button>
                  <el-button type="danger" size="small" plain @click="handleDeleteSpec(spec)">删除</el-button>
                </div>
              </el-card>
            </div>
          </section>
        </template>

        <el-empty v-else description="没有匹配的 Agent，可以清空搜索或新建一个 Agent。" />
      </div>
    </div>
      </el-tab-pane>

      <el-tab-pane label="已发布 Agent" name="published">
        <PublishedAgents />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, onActivated, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import PublishedAgents from './Agents.vue'
import agentWorkshopApi, { type AgentSpec, type AgentSpecIOItem, type AgentVersion, type AgentWorkshopSessionDetail } from '@/api/agentWorkshop'

const router = useRouter()

const activeTab = ref('workshop')
const draftLoading = ref(false)
const listLoading = ref(false)
const filterStatus = ref('')
const searchKeyword = ref('')

const draftSessions = ref<AgentWorkshopSessionDetail[]>([])
const specs = ref<AgentSpec[]>([])
const latestVersionBySpec = ref<Record<string, AgentVersion>>({})

const getSpecIoText = (item?: AgentSpecIOItem | null) => {
  if (!item) return ''
  if (typeof item === 'string') return item.trim()
  const name = String(item.name || '').trim()
  const description = String(item.description || '').trim()
  if (name && description && description !== name) {
    return `${name}：${description}`
  }
  return name || description
}

const getSpecOutputTags = (spec: AgentSpec) => (spec.outputs || []).map(item => getSpecIoText(item)).filter(Boolean)

const testingCount = computed(() => specs.value.filter(item => item.status === 'testing').length)
const normalizedSearch = computed(() => searchKeyword.value.trim().toLowerCase())
const filteredSpecs = computed(() => {
  return specs.value.filter(item => {
    if (filterStatus.value && item.status !== filterStatus.value) {
      return false
    }

    if (!normalizedSearch.value) {
      return true
    }

    const haystack = [
      item.name,
      item.domain,
      item.primary_goal,
      item.current_version_id,
      ...getSpecOutputTags(item),
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()

    return haystack.includes(normalizedSearch.value)
  })
})
const specGroups = computed(() => {
  const groups = [
    {
      status: 'draft',
      title: '草案中',
      description: '需求和规格已经有轮廓，但还在继续打磨。',
    },
    {
      status: 'testing',
      title: '测试中',
      description: '已经生成版本，正在看表现和评估结果。',
    },
    {
      status: 'active',
      title: '已启用',
      description: '已经进入可用状态，可以继续做迭代优化。',
    },
    {
      status: 'archived',
      title: '已归档',
      description: '不再继续推进，但保留历史记录。',
    },
  ]

  return groups.map(group => ({
    ...group,
    items: filteredSpecs.value.filter(item => item.status === group.status),
  }))
})

const formatTime = (value?: string) => {
  if (!value) return '-'
  return value.replace('T', ' ').slice(0, 19)
}

const stageText = (stage?: string) => {
  if (stage === 'gathering') return '需求沟通中'
  if (stage === 'planning') return '规格整理中'
  if (stage === 'gap-analysis') return '缺口分析中'
  if (stage === 'building') return '版本生成中'
  if (stage === 'evaluating') return '评估中'
  return stage || '处理中'
}

const stageTagType = (stage?: string) => {
  if (stage === 'gathering') return 'warning'
  if (stage === 'planning' || stage === 'gap-analysis') return 'primary'
  if (stage === 'building' || stage === 'evaluating') return 'success'
  return 'info'
}

const statusText = (status?: string) => {
  if (status === 'feasible') return '可继续'
  if (status === 'not-feasible') return '做不到'
  return '待澄清'
}

const specStatusText = (status?: string) => {
  if (status === 'draft') return '草案'
  if (status === 'testing') return '测试中'
  if (status === 'active') return '已启用'
  if (status === 'archived') return '已归档'
  return status || '-'
}

const specStatusTagType = (status?: string) => {
  if (status === 'active') return 'success'
  if (status === 'testing') return 'warning'
  if (status === 'archived') return 'info'
  return 'primary'
}

const getLatestSpecVersion = (spec: AgentSpec) => latestVersionBySpec.value[spec.spec_id] || null

const getVersionStatusText = (status?: string) => {
  if (status === 'active') return '已发布'
  if (status === 'testing') return '测试中'
  if (status === 'archived') return '已归档'
  if (status === 'draft') return '草稿'
  return status || '未知'
}

const getVersionStatusTagType = (status?: string): 'success' | 'warning' | 'info' | 'primary' => {
  if (status === 'active') return 'success'
  if (status === 'testing') return 'warning'
  if (status === 'archived') return 'info'
  return 'primary'
}

const getEvaluationDecisionText = (decision?: string) => {
  if (decision === 'pass') return '通过'
  if (decision === 'reject') return '拒绝'
  if (decision === 'revise') return '需修订'
  return decision || '未评估'
}

const getEvaluationDecisionTagType = (decision?: string): 'success' | 'warning' | 'danger' | 'info' => {
  if (decision === 'pass') return 'success'
  if (decision === 'reject') return 'danger'
  if (decision === 'revise') return 'warning'
  return 'info'
}

const getProjectMemorySummaryTagType = (status?: string): 'success' | 'warning' | 'danger' | 'info' => {
  if (status === 'pass') return 'success'
  if (status === 'evidence_incomplete') return 'warning'
  if (status === 'failed') return 'danger'
  return 'info'
}

const getProjectMemorySummaryText = (status?: string) => {
  if (status === 'pass') return 'L4 已绑定'
  if (status === 'failed') return 'L4 缺失'
  if (status === 'evidence_incomplete') return 'L4 证据不足'
  if (status === 'not_enabled') return 'L4 未启用'
  return status || 'L4 未知'
}

const getDraftPreview = (draft: AgentWorkshopSessionDetail) => {
  const lastAssistant = [...(draft.messages || [])].reverse().find(item => item.role === 'assistant')
  const lastUser = [...(draft.messages || [])].reverse().find(item => item.role === 'user')
  const preview = lastAssistant?.content || lastUser?.content || ''
  return preview.length > 96 ? `${preview.slice(0, 96)}...` : preview || '还没有可预览的内容'
}

const goToWorkshop = (sessionId?: string) => {
  if (sessionId) {
    router.push({ path: '/workflow/agent-workshop/create', query: { sessionId } })
    return
  }
  router.push('/workflow/agent-workshop/create')
}

const goToLanding = () => {
  router.push('/workflow/agent-workshop')
}

const openAgentStudio = (spec: AgentSpec) => {
  router.push({ path: '/workflow/agent-studio', query: { agent_id: spec.spec_id } })
}

const openSpec = (spec: AgentSpec) => {
  if (spec.latest_session_id) {
    goToWorkshop(spec.latest_session_id)
    return
  }
  router.push({ path: '/workflow/agent-workshop/create', query: { specId: spec.spec_id } })
}

const loadDrafts = async () => {
  draftLoading.value = true
  try {
    const result = await agentWorkshopApi.listSessions({ page: 1, page_size: 30 })
    draftSessions.value = (result.items || []).filter(item => item.stage !== 'completed')
  } catch (error: any) {
    draftSessions.value = []
    ElMessage.error(error?.message || '加载工坊会话失败')
  } finally {
    draftLoading.value = false
  }
}

const loadSpecs = async () => {
  listLoading.value = true
  try {
    const specResult = await agentWorkshopApi.listSpecs({ page: 1, page_size: 50 })
    const specItems = specResult.items || []
    specs.value = specItems

    const versionPairs = await Promise.all(
      specItems.map(async spec => {
        try {
          if (spec.current_version_id) {
            const version = await agentWorkshopApi.getVersion(spec.current_version_id)
            return [spec.spec_id, version] as const
          }

          const result = await agentWorkshopApi.listVersions({ spec_id: spec.spec_id, page: 1, page_size: 1 })
          const version = result.items?.[0]
          return version ? ([spec.spec_id, version] as const) : null
        } catch {
          return null
        }
      })
    )

    latestVersionBySpec.value = Object.fromEntries(
      versionPairs.filter((entry): entry is readonly [string, AgentVersion] => Array.isArray(entry) && !!entry[0] && !!entry[1])
    )
  } catch (error: any) {
    specs.value = []
    latestVersionBySpec.value = {}
    ElMessage.error(error?.message || '加载 Agent 列表失败')
  } finally {
    listLoading.value = false
  }
}

const refreshAll = async () => {
  await Promise.all([loadDrafts(), loadSpecs()])
}

const handleDeleteDraftSession = async (draft: AgentWorkshopSessionDetail) => {
  const agentName = draft.current_spec_snapshot?.name || '未命名 Agent'
  try {
    await ElMessageBox.confirm(
      `确定删除“${agentName}”这条进行中的工坊会话吗？这只会删除当前会话记录，不会删除已沉淀的 Agent 规格。`,
      '删除工坊会话',
      {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        confirmButtonClass: 'el-button--danger',
      }
    )

    await agentWorkshopApi.deleteSession(draft.session_id)
    ElMessage.success('工坊会话已删除')
    await loadDrafts()
  } catch (error: any) {
    if (error === 'cancel' || error?.message === 'cancel') {
      return
    }
    ElMessage.error(error?.message || '删除工坊会话失败')
  }
}

const handleDeleteSpec = async (spec: AgentSpec) => {
  try {
    await ElMessageBox.confirm(
      `确定删除"${spec.name}"吗？这会同时删除它的会话、版本、评估记录、运行时配置和提示词模板。`,
      '删除 Agent',
      {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        confirmButtonClass: 'el-button--danger',
      }
    )
  } catch (error: any) {
    if (error === 'cancel' || error?.message === 'cancel') {
      return
    }
  }

  try {
    // 第一次尝试删除
    const result = await agentWorkshopApi.deleteSpec(spec.spec_id, false)
    if (result.deleted) {
      ElMessage.success('Agent 已删除')
      await refreshAll()
      return
    }
  } catch (error: any) {
    // 如果是被工作流引用阻止（409），弹出二次确认
    const errData = error?.response?.data || error?.data
    if (errData?.data?.blocked_by_workflows && errData?.data?.workflow_references?.length) {
      const refs = errData.data.workflow_references
      const refHtml = refs.map((ref: any) =>
        `<li style="margin-bottom:6px;">
          <span style="font-weight:500;">${ref.workflow_name}</span>
          <span style="color:#909399;margin-left:8px;font-size:12px;">
            （引用：${ref.referenced_agents.join(', ')}）
          </span>
        </li>`
      ).join('')

      try {
        await ElMessageBox.confirm(
          `<p style="margin:0 0 12px;color:#e6a23c;">
            ⚠️ 该 Agent 被 <strong>${refs.length}</strong> 个工作流引用，删除后这些工作流将无法正常运行：
           </p>
           <ul style="margin:0;padding-left:20px;color:#606266;font-size:13px;line-height:1.6;">
             ${refHtml}
           </ul>
           <p style="margin:12px 0 0;color:#909399;font-size:12px;">
             建议先从上述工作流中移除该 Agent，再执行删除。
           </p>`,
          '存在工作流引用，确认强制删除？',
          {
            type: 'error',
            confirmButtonText: '强制删除',
            cancelButtonText: '取消',
            confirmButtonClass: 'el-button--danger',
            dangerouslyUseHTMLString: true,
          }
        )

        // 用户确认强制删除
        const forceResult = await agentWorkshopApi.deleteSpec(spec.spec_id, true)
        if (forceResult.deleted) {
          ElMessage.success('Agent 已强制删除')
          await refreshAll()
        } else {
          ElMessage.error(forceResult.message || '删除失败')
        }
      } catch (cancelErr: any) {
        if (cancelErr === 'cancel' || cancelErr?.message === 'cancel') {
          return
        }
        ElMessage.error(cancelErr?.message || '删除失败')
      }
      return
    }

    ElMessage.error(error?.message || '删除失败')
  }
}

onMounted(refreshAll)
onActivated(refreshAll)
</script>

<style scoped lang="scss">
.agent-workshop-manager-page {
  padding: 16px;
}

.page-header,
.section-header,
.section-tools,
.header-right,
.header-left,
.draft-head,
.draft-meta,
.draft-actions,
.group-title-row,
.spec-card-head,
.spec-card-meta,
.spec-card-actions,
.spec-card-tags {
  display: flex;
  align-items: center;
}

.page-header,
.section-header {
  justify-content: space-between;
  gap: 12px;
}

.page-header {
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.header-left {
  gap: 10px;
  flex-wrap: wrap;

  h1 {
    margin: 0;
    font-size: 22px;
    color: #123f39;
  }
}

.header-right,
.draft-actions {
  gap: 8px;
}

.section-tools,
.spec-card-tags,
.spec-card-actions,
.spec-card-meta {
  gap: 8px;
}

.subtitle {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.summary-card {
  border-radius: 14px;
}

.summary-label {
  color: #70837d;
  font-size: 13px;
}

.summary-value {
  margin-top: 8px;
  font-size: 32px;
  font-weight: 700;
  color: #123f39;
}

.summary-note {
  margin-top: 8px;
  color: #70837d;
  font-size: 13px;
  line-height: 1.6;
}

.draft-section,
.spec-section {
  margin-bottom: 24px;
}

.section-header {
  margin-bottom: 12px;
  flex-wrap: wrap;

  h2 {
    margin: 0;
    font-size: 17px;
  }
}

.section-tools {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.search-input {
  width: 300px;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.draft-card {
  border-radius: 16px;
}

.draft-head {
  justify-content: space-between;
  gap: 10px;
}

.draft-time {
  color: #8a9a95;
  font-size: 12px;
}

.draft-title {
  margin-top: 12px;
  font-size: 17px;
  font-weight: 700;
  color: #123f39;
}

.draft-preview {
  margin-top: 10px;
  min-height: 44px;
  color: #4e5b57;
  line-height: 1.65;
}

.draft-meta {
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 10px;
  color: #70837d;
  font-size: 12px;
}

.draft-actions {
  margin-top: 14px;
  justify-content: flex-end;
  flex-wrap: wrap;
}

.group-list {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.group-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.group-header {
  display: flex;
  flex-direction: column;
  gap: 6px;

  h3 {
    margin: 0;
    font-size: 16px;
    color: #123f39;
  }

  p {
    margin: 0;
    color: #70837d;
    font-size: 13px;
  }
}

.spec-card-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.spec-card {
  border-radius: 16px;
}

.spec-card-head {
  justify-content: space-between;
  gap: 10px;
}

.spec-card-title {
  font-size: 16px;
  font-weight: 700;
  color: #123f39;
}

.spec-card-goal {
  margin-top: 10px;
  min-height: 22px;
  line-height: 1.65;
  color: #4e5b57;
}

.spec-card-goal.placeholder {
  color: #9aada6;
  font-style: italic;
}

.spec-card-meta {
  margin-top: 10px;
  flex-wrap: wrap;
  color: #70837d;
  font-size: 12px;
}

.spec-card-version-summary {
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(18, 63, 57, 0.08);
  background: linear-gradient(180deg, rgba(251, 254, 253, 0.94) 0%, rgba(244, 250, 247, 0.98) 100%);
}

.spec-card-version-head,
.spec-card-summary-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.spec-card-version-head strong {
  color: #123f39;
  font-size: 13px;
}

.spec-card-summary-text {
  margin-top: 8px;
  color: #4e5b57;
  font-size: 12px;
  line-height: 1.6;
}

/* 多行省略号通用类 */
.text-ellipsis-1 {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.text-ellipsis-2 {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  text-overflow: ellipsis;
}

.text-ellipsis-3 {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  overflow: hidden;
  text-overflow: ellipsis;
}

.clickable {
  cursor: pointer;
  transition: color 0.2s;
}

.clickable:hover {
  color: #123f39;
}

/* 长文本提示框 */
:deep(.long-text-tooltip) {
  max-width: 420px;
  word-break: break-word;
  white-space: pre-wrap;
  font-size: 13px;
  line-height: 1.7;
}

.spec-card-summary-meta {
  margin-top: 8px;
  color: #70837d;
  font-size: 12px;
}

.spec-card-tags {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: stretch;
}

.spec-output-item {
  font-size: 12px;
  color: #4e5b57;
  padding: 4px 10px;
  border-radius: 8px;
  background: rgba(18, 63, 57, 0.04);
  border: 1px solid rgba(18, 63, 57, 0.06);
}

.spec-card-actions {
  margin-top: 14px;
  justify-content: flex-end;
  flex-wrap: wrap;
}

.loading-grid :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

@media (max-width: 1100px) {
  .summary-grid,
  .card-grid,
  .spec-card-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .search-input {
    width: 100%;
  }

  .section-tools {
    width: 100%;
    justify-content: stretch;
  }
}
</style>