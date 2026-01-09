<template>
  <div class="agent-detail-page">
    <!-- 顶部导航栏 -->
    <div class="page-header">
      <el-button @click="goBack" :icon="ArrowLeft" circle />
      <div class="header-title">
        <div class="icon-wrapper" :style="{ color: agent?.color, backgroundColor: agent?.color + '15' }">
          {{ agent?.icon }}
        </div>
        <div class="title-text">
          <h2>{{ agent?.name }}</h2>
          <span class="agent-id">{{ agent?.id }}</span>
        </div>
      </div>
      <div class="header-actions">
        <el-tag :type="agent?.license_tier === 'free' ? 'info' : 'success'">
          {{ agent?.license_tier }}
        </el-tag>
      </div>
    </div>

    <!-- 主内容区域 -->
    <div class="page-content" v-loading="loading">
      <el-row :gutter="20">
        <!-- 左侧：基本信息 + 输入输出 -->
        <el-col :span="12">
          <!-- 基本信息 -->
          <el-card class="info-card" shadow="never">
            <template #header>
              <div class="card-header">
                <el-icon><InfoFilled /></el-icon>
                <span>基本信息</span>
              </div>
            </template>
            <div class="info-content">
              <div class="info-item">
                <span class="label">描述</span>
                <p class="value">{{ agent?.description }}</p>
              </div>
              <div class="info-item">
                <span class="label">分类</span>
                <el-tag>{{ getCategoryName(agent?.category) }}</el-tag>
              </div>
              <div class="info-item">
                <span class="label">标签</span>
                <div class="tags">
                  <el-tag v-for="tag in agent?.tags" :key="tag" size="small" type="info">
                    {{ tag }}
                  </el-tag>
                  <span v-if="!agent?.tags?.length" class="empty-text">无标签</span>
                </div>
              </div>
            </div>
          </el-card>

          <!-- 输入输出 -->
          <el-card class="info-card" shadow="never">
            <template #header>
              <div class="card-header">
                <el-icon><Connection /></el-icon>
                <span>输入/输出</span>
              </div>
            </template>
            <div class="io-content">
              <div class="io-section">
                <h4>输入参数</h4>
                <div v-if="parsedInputs?.length" class="io-list">
                  <div v-for="input in parsedInputs" :key="input.name" class="io-param">
                    <div class="param-header">
                      <el-tag type="info" size="small">{{ input.name }}</el-tag>
                      <el-tag v-if="input.required" type="danger" size="small" effect="plain">必填</el-tag>
                      <el-tag v-else type="info" size="small" effect="plain">可选</el-tag>
                    </div>
                    <div class="param-desc">{{ input.description }}</div>
                    <div class="param-meta">
                      <span class="meta-item">类型: {{ input.type }}</span>
                    </div>
                  </div>
                </div>
                <span v-else class="empty-text">无特定输入</span>
              </div>
              <el-divider />
              <div class="io-section">
                <h4>输出结果</h4>
                <div v-if="parsedOutputs?.length" class="io-list">
                  <div v-for="output in parsedOutputs" :key="output.name" class="io-param">
                    <div class="param-header">
                      <el-tag type="success" size="small">{{ output.name }}</el-tag>
                    </div>
                    <div class="param-desc">{{ output.description }}</div>
                    <div class="param-meta">
                      <span class="meta-item">类型: {{ output.type }}</span>
                    </div>
                  </div>
                </div>
                <span v-else class="empty-text">无特定输出</span>
              </div>
            </div>
          </el-card>
        </el-col>

        <!-- 右侧：工具配置 + 提示词模板 -->
        <el-col :span="12">
          <!-- 工具配置 -->
          <el-card class="info-card" shadow="never">
            <template #header>
              <div class="card-header">
                <el-icon><Tools /></el-icon>
                <span>工具配置</span>
                <el-button 
                  v-if="!isEditingTools" 
                  type="primary" 
                  link 
                  @click="startEditTools"
                  style="margin-left: auto;"
                >
                  <el-icon><Edit /></el-icon> 编辑
                </el-button>
                <div v-else class="edit-actions" style="margin-left: auto;">
                  <el-button size="small" @click="cancelEditTools">取消</el-button>
                  <el-button size="small" type="primary" :loading="savingTools" @click="saveTools">保存</el-button>
                </div>
              </div>
            </template>
            <div class="tools-content" v-loading="toolsLoading">
              <!-- 查看模式 -->
              <div v-if="!isEditingTools">
                <div v-if="agentTools?.available_tools?.length" class="tools-grid">
                  <div v-for="tool in agentTools.available_tools" :key="tool.id" class="tool-card">
                    <div class="tool-icon" :style="{ color: tool.color }">{{ tool.icon }}</div>
                    <div class="tool-info">
                      <div class="tool-name">
                        {{ tool.name }}
                        <el-tag v-if="agentTools.default_tools.includes(tool.id)" size="small" type="success">默认</el-tag>
                      </div>
                      <div class="tool-desc">{{ tool.description }}</div>
                    </div>
                  </div>
                </div>
                <el-empty v-else description="暂无工具配置" :image-size="80" />
              </div>

              <!-- 编辑模式 -->
              <div v-else>
                <div class="edit-section">
                  <h4>可用工具</h4>
                  <el-select
                    v-model="editingTools"
                    multiple
                    filterable
                    placeholder="选择工具"
                    style="width: 100%"
                  >
                    <el-option
                      v-for="tool in allTools"
                      :key="tool.id"
                      :label="tool.name"
                      :value="tool.id"
                    >
                      <span>{{ tool.icon }} {{ tool.name }}</span>
                    </el-option>
                  </el-select>
                </div>
              </div>
            </div>
          </el-card>

          <!-- 提示词模板 -->
          <el-card class="info-card prompt-card" shadow="never">
            <template #header>
              <div class="card-header">
                <el-icon><Document /></el-icon>
                <span>提示词模板</span>
                <div v-if="!isEditingPrompt" class="header-actions">
                  <el-button
                    v-if="promptTemplate"
                    type="primary"
                    link
                    @click="startEditPrompt"
                  >
                    <el-icon><Edit /></el-icon> 编辑
                  </el-button>
                </div>
                <div v-else class="edit-actions">
                  <el-button size="small" @click="cancelEditPrompt">取消</el-button>
                  <el-button size="small" type="primary" :loading="savingPrompt" @click="savePrompt">保存</el-button>
                </div>
              </div>
            </template>
            <div class="prompt-content" v-loading="promptLoading">
              <!-- 查看模式 -->
              <div v-if="!isEditingPrompt">
                <div v-if="promptTemplates.length > 0">
                  <!-- 模板选择器 -->
                  <div class="template-selector">
                    <div class="selector-label">选择模板:</div>
                    <el-select
                      v-model="selectedTemplateId"
                      @change="handleTemplateChange"
                      style="flex: 1; max-width: 400px;"
                    >
                      <el-option
                        v-for="template in promptTemplates"
                        :key="template.id"
                        :label="`${template.template_name} (${template.preference_type || '默认'})`"
                        :value="template.id"
                      >
                        <div style="display: flex; align-items: center; justify-content: space-between;">
                          <span>{{ template.template_name }}</span>
                          <div style="display: flex; gap: 4px;">
                            <el-tag v-if="template.preference_type" size="small" type="info">
                              {{ template.preference_type }}
                            </el-tag>
                            <el-tag size="small" :type="template.is_system ? 'success' : 'warning'">
                              {{ template.is_system ? '系统' : '用户' }}
                            </el-tag>
                            <el-tag v-if="template.status === 'draft'" size="small" type="info">
                              草稿
                            </el-tag>
                            <el-tag v-if="template.id === activeTemplateId" size="small" type="primary">
                              当前生效
                            </el-tag>
                          </div>
                        </div>
                      </el-option>
                    </el-select>
                    <el-button
                      v-if="selectedTemplateId && selectedTemplateId !== activeTemplateId"
                      type="primary"
                      size="small"
                      @click="setAsActiveTemplate"
                    >
                      设为当前
                    </el-button>
                  </div>

                  <!-- 模板详情 -->
                  <div v-if="promptTemplate" class="template-detail">
                    <div class="prompt-meta">
                      <el-tag size="small">{{ promptTemplate.template_name }}</el-tag>
                      <el-tag size="small" type="info" v-if="promptTemplate.preference_type">
                        {{ promptTemplate.preference_type }}
                      </el-tag>
                      <el-tag size="small" :type="promptTemplate.is_system ? 'success' : 'warning'">
                        {{ promptTemplate.is_system ? '系统模板' : '用户模板' }}
                      </el-tag>
                      <el-tag v-if="promptTemplate.status === 'draft'" size="small" type="info">
                        草稿
                      </el-tag>
                      <el-tag v-if="promptTemplate.id === activeTemplateId" size="small" type="primary">
                        当前生效
                      </el-tag>
                    </div>

                    <el-tabs v-model="activePromptTab" class="prompt-tabs">
                      <el-tab-pane label="系统提示词" name="system">
                        <div class="prompt-text">{{ promptTemplate.content?.system_prompt || '无' }}</div>
                      </el-tab-pane>
                      <el-tab-pane label="用户提示词" name="user">
                        <div class="prompt-text">{{ promptTemplate.content?.user_prompt || '无' }}</div>
                      </el-tab-pane>
                      <el-tab-pane label="工具指导" name="tool">
                        <div class="prompt-text">{{ promptTemplate.content?.tool_guidance || '无' }}</div>
                      </el-tab-pane>
                      <el-tab-pane label="分析要求" name="analysis">
                        <div class="prompt-text">{{ promptTemplate.content?.analysis_requirements || '无' }}</div>
                      </el-tab-pane>
                      <el-tab-pane label="输出格式" name="output">
                        <div class="prompt-text">{{ promptTemplate.content?.output_format || '无' }}</div>
                      </el-tab-pane>
                    </el-tabs>

                    <div v-if="promptTemplate.remark" class="prompt-remark">
                      <el-divider />
                      <div class="remark-label">备注</div>
                      <div class="remark-text">{{ promptTemplate.remark }}</div>
                    </div>
                  </div>
                </div>
                <el-empty v-else description="暂无提示词模板" :image-size="80" />
              </div>

              <!-- 编辑模式 -->
              <div v-else class="edit-mode">
                <el-form label-position="top">
                  <el-form-item label="系统提示词">
                    <el-input
                      v-model="editingPrompt.system_prompt"
                      type="textarea"
                      :rows="6"
                      placeholder="请输入系统提示词"
                    />
                  </el-form-item>
                  <el-form-item label="工具指导">
                    <el-input
                      v-model="editingPrompt.tool_guidance"
                      type="textarea"
                      :rows="4"
                      placeholder="请输入工具使用指导"
                    />
                  </el-form-item>
                  <el-form-item label="分析要求">
                    <el-input
                      v-model="editingPrompt.analysis_requirements"
                      type="textarea"
                      :rows="4"
                      placeholder="请输入分析要求"
                    />
                  </el-form-item>
                  <el-form-item label="输出格式">
                    <el-input
                      v-model="editingPrompt.output_format"
                      type="textarea"
                      :rows="4"
                      placeholder="请输入输出格式要求"
                    />
                  </el-form-item>
                  <el-form-item label="备注">
                    <el-input
                      v-model="editingPrompt.remark"
                      type="textarea"
                      :rows="2"
                      placeholder="请输入备注信息"
                    />
                  </el-form-item>
                </el-form>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, InfoFilled, Connection, Tools, Edit, Document } from '@element-plus/icons-vue'
import { agentApi, type AgentMetadata, type AgentToolsConfig } from '@/api/agents'
import { toolsApi, type ToolMetadata } from '@/api/tools'
import { TemplatesApi } from '@/api/templates'
import { ApiClient } from '@/api/request'

const route = useRoute()
const router = useRouter()

// 数据
const loading = ref(false)
const agent = ref<AgentMetadata | null>(null)
const agentTools = ref<AgentToolsConfig | null>(null)
const allTools = ref<ToolMetadata[]>([])
const promptTemplate = ref<any>(null)

// 工具编辑
const toolsLoading = ref(false)
const isEditingTools = ref(false)
const editingTools = ref<string[]>([])
const editingDefaultTools = ref<string[]>([])
const savingTools = ref(false)

// 提示词
const promptLoading = ref(false)
const activePromptTab = ref('system')
const isEditingPrompt = ref(false)
const savingPrompt = ref(false)
const editingPrompt = ref({
  system_prompt: '',
  tool_guidance: '',
  analysis_requirements: '',
  output_format: '',
  remark: ''
})

// 提示词模板列表和选择
const promptTemplates = ref<any[]>([]) // 所有可用的模板（3个系统模板）
const selectedTemplateId = ref<string>('') // 当前选中的模板 ID
const activeTemplateId = ref<string>('') // 用户设置的当前生效模板 ID

// 分类映射
const categoryMap: Record<string, string> = {
  analyst: '分析师',
  researcher: '研究员',
  trader: '交易员',
  risk: '风控管理',
  manager: '管理者',
  post_processor: '后处理器'
}

const getCategoryName = (category?: string) => {
  return category ? categoryMap[category] || category : '未知'
}

// 解析输入输出参数
const parsedInputs = computed(() => {
  if (!agent.value?.inputs) return []

  // 如果是字符串数组，尝试解析为对象
  return agent.value.inputs.map((input: any) => {
    if (typeof input === 'string') {
      try {
        return JSON.parse(input)
      } catch {
        return { name: input, type: 'string', description: '', required: false }
      }
    }
    return input
  })
})

const parsedOutputs = computed(() => {
  if (!agent.value?.outputs) return []

  return agent.value.outputs.map((output: any) => {
    if (typeof output === 'string') {
      try {
        return JSON.parse(output)
      } catch {
        return { name: output, type: 'string', description: '' }
      }
    }
    return output
  })
})

// 返回
const goBack = () => {
  router.back()
}

// 加载 Agent 详情
const loadAgentDetail = async () => {
  const agentId = route.params.id as string
  if (!agentId) {
    ElMessage.error('Agent ID 不能为空')
    goBack()
    return
  }

  loading.value = true
  try {
    // 加载基本信息
    const agentData = await agentApi.get(agentId)
    if (agentData) {
      agent.value = agentData
    } else {
      throw new Error('Agent 不存在')
    }

    // 并行加载工具配置和提示词模板
    await Promise.all([
      loadAgentTools(agentId),
      loadPromptTemplates(agentId)
    ])
  } catch (error: any) {
    console.error('加载 Agent 详情失败:', error)
    ElMessage.error(error.message || '加载失败')
  } finally {
    loading.value = false
  }
}

// 加载工具配置
const loadAgentTools = async (agentId: string) => {
  toolsLoading.value = true
  try {
    const toolsData = await agentApi.getAgentTools(agentId)
    if (toolsData) {
      agentTools.value = toolsData
    }
  } catch (error: any) {
    console.error('加载工具配置失败:', error)
  } finally {
    toolsLoading.value = false
  }
}

// 加载提示词模板列表
const loadPromptTemplates = async (agentId: string) => {
  promptLoading.value = true
  try {
    if (!agent.value?.id) {
      console.warn('Agent ID not available')
      return
    }

    // 1. 获取所有可用的模板（包括系统模板和用户模板）
    // 注意：不过滤 status，以便显示用户的草稿模板
    const response = await TemplatesApi.list({
      agent_name: agent.value.id,
      skip: 0,
      limit: 20
    })

    const items = response.data?.items || []
    promptTemplates.value = items

    // 2. 获取用户当前生效的模板 ID
    await loadActiveTemplateId()

    // 3. 确定要显示的模板
    let templateIdToShow = ''

    if (activeTemplateId.value) {
      // 如果用户设置了当前模板，使用用户设置的
      templateIdToShow = activeTemplateId.value
    } else {
      // 否则使用系统默认的 neutral 模板
      const neutralTemplate = items.find((t: any) =>
        t.is_system && t.preference_type === 'neutral'
      )
      templateIdToShow = neutralTemplate?.id || items[0]?.id || ''
    }

    if (templateIdToShow) {
      selectedTemplateId.value = templateIdToShow
      await loadTemplateDetail(templateIdToShow)
    }
  } catch (error: any) {
    console.error('加载提示词模板失败:', error)
  } finally {
    promptLoading.value = false
  }
}

// 从 agent_name 推断 agent_type
const inferAgentType = (agentName: string): string => {
  // 例如: sector_analyst_v2 -> analysts_v2
  if (agentName.includes('_v2')) {
    if (agentName.includes('analyst')) return 'analysts_v2'
    if (agentName.includes('researcher')) return 'researchers_v2'
    if (agentName.includes('debator')) return 'debators_v2'
    if (agentName.includes('manager')) return 'managers_v2'
    if (agentName.includes('trader')) return 'trader_v2'
    if (agentName.includes('reviewer')) return 'reviewers_v2'
    if (agentName.includes('position')) return 'position_analysis_v2'
    return 'analysts_v2' // 默认值
  } else {
    // v1.x
    if (agentName.includes('analyst')) return 'analysts'
    if (agentName.includes('researcher')) return 'researchers'
    if (agentName.includes('debator')) return 'debators'
    if (agentName.includes('manager')) return 'managers'
    if (agentName.includes('trader')) return 'trader'
    if (agentName.includes('reviewer')) return 'reviewers'
    if (agentName.includes('position')) return 'position_analysis'
    return 'analysts' // 默认值
  }
}

// 加载用户当前生效的模板 ID
const loadActiveTemplateId = async () => {
  try {
    const { useAuthStore } = await import('@/stores/auth')
    const userId = useAuthStore().user?.id
    if (!userId || !agent.value?.id) return

    const agentType = inferAgentType(agent.value.id)

    const response = await ApiClient.get('/api/v1/user-template-configs/active', {
      user_id: userId,
      agent_name: agent.value.id,
      agent_type: agentType
    })

    if (response.success && response.data) {
      activeTemplateId.value = response.data.template_id
    }
  } catch (error: any) {
    console.warn('获取当前生效模板失败:', error)
  }
}

// 加载模板详情
const loadTemplateDetail = async (templateId: string) => {
  try {
    const detailResponse = await TemplatesApi.get(templateId)
    if (detailResponse.success && detailResponse.data) {
      promptTemplate.value = detailResponse.data
    }
  } catch (error: any) {
    console.error('加载模板详情失败:', error)
  }
}

// 切换模板
const handleTemplateChange = async (templateId: string) => {
  await loadTemplateDetail(templateId)
}

// 设置为当前模板
const setAsActiveTemplate = async () => {
  try {
    const { useAuthStore } = await import('@/stores/auth')
    const userId = useAuthStore().user?.id
    if (!userId || !promptTemplate.value || !agent.value) return

    // 使用模板中的 agent_type，如果没有则推断
    const agentType = promptTemplate.value.agent_type || inferAgentType(agent.value.id)

    const body = {
      agent_type: agentType,
      agent_name: promptTemplate.value.agent_name,
      template_id: selectedTemplateId.value
    }

    // 将 user_id 作为查询参数传递
    const url = `/api/v1/user-template-configs?user_id=${userId}`
    const response = await ApiClient.post(url, body)

    if (response.success) {
      ElMessage.success('已设为当前模板')
      activeTemplateId.value = selectedTemplateId.value
    } else {
      ElMessage.error(response.message || '设置失败')
    }
  } catch (error: any) {
    console.error('设置当前模板失败:', error)
    ElMessage.error(error.message || '设置失败')
  }
}

// 开始编辑提示词
const startEditPrompt = () => {
  if (!promptTemplate.value) return

  const content = promptTemplate.value.content || {}
  editingPrompt.value = {
    system_prompt: content.system_prompt || '',
    tool_guidance: content.tool_guidance || '',
    analysis_requirements: content.analysis_requirements || '',
    output_format: content.output_format || '',
    remark: promptTemplate.value.remark || ''
  }
  isEditingPrompt.value = true
}

// 取消编辑提示词
const cancelEditPrompt = () => {
  isEditingPrompt.value = false
  editingPrompt.value = {
    system_prompt: '',
    tool_guidance: '',
    analysis_requirements: '',
    output_format: '',
    remark: ''
  }
}

// 保存提示词
const savePrompt = async () => {
  if (!promptTemplate.value || !agent.value) return

  savingPrompt.value = true
  try {
    const { useAuthStore } = await import('@/stores/auth')
    const userId = useAuthStore().user?.id

    // 如果是系统模板，需要先克隆为用户模板
    let templateId = promptTemplate.value.id
    if (promptTemplate.value.is_system) {
      const cloneResponse = await TemplatesApi.clone(
        templateId,
        `${agent.value.id}_custom_${Date.now()}`,
        userId
      )

      if (!cloneResponse.success || !cloneResponse.data) {
        throw new Error('克隆模板失败')
      }

      templateId = cloneResponse.data.id
    }

    // 更新模板内容
    const updateData = {
      content: {
        system_prompt: editingPrompt.value.system_prompt,
        tool_guidance: editingPrompt.value.tool_guidance,
        analysis_requirements: editingPrompt.value.analysis_requirements,
        output_format: editingPrompt.value.output_format
      },
      remark: editingPrompt.value.remark
    }

    // 调用更新 API
    const updateResponse = await TemplatesApi.update(templateId, updateData)

    if (!updateResponse.success) {
      throw new Error(updateResponse.message || '更新失败')
    }

    ElMessage.success('保存成功')
    isEditingPrompt.value = false

    // 重新加载模板列表
    await loadPromptTemplates(agent.value.id)
  } catch (error: any) {
    console.error('保存提示词失败:', error)
    ElMessage.error(error.message || '保存失败')
  } finally {
    savingPrompt.value = false
  }
}

// 开始编辑工具
const startEditTools = async () => {
  // 加载所有工具
  try {
    const toolsList = await toolsApi.listTools()
    if (toolsList) {
      allTools.value = toolsList
    }
  } catch (error: any) {
    ElMessage.error('加载工具列表失败')
    return
  }

  editingTools.value = [...(agentTools.value?.tools || [])]
  editingDefaultTools.value = [...(agentTools.value?.default_tools || [])]
  isEditingTools.value = true
}

// 取消编辑
const cancelEditTools = () => {
  isEditingTools.value = false
  editingTools.value = []
  editingDefaultTools.value = []
}

// 保存工具配置
const saveTools = async () => {
  if (!agent.value) return

  savingTools.value = true
  try {
    await agentApi.updateAgentTools(agent.value.id, {
      tools: editingTools.value,
      default_tools: editingDefaultTools.value
    })

    ElMessage.success('保存成功')
    isEditingTools.value = false
    await loadAgentTools(agent.value.id)
  } catch (error: any) {
    console.error('保存工具配置失败:', error)
    ElMessage.error(error.message || '保存失败')
  } finally {
    savingTools.value = false
  }
}

onMounted(() => {
  loadAgentDetail()
})
</script>

<style scoped lang="scss">
.agent-detail-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;

  .page-header {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 20px 24px;
    background: white;
    border-bottom: 1px solid #e4e7ed;

    .header-title {
      display: flex;
      align-items: center;
      gap: 12px;
      flex: 1;

      .icon-wrapper {
        width: 48px;
        height: 48px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
      }

      .title-text {
        h2 {
          margin: 0;
          font-size: 20px;
          font-weight: 600;
          color: #303133;
        }

        .agent-id {
          font-size: 13px;
          color: #909399;
        }
      }
    }

    .header-actions {
      display: flex;
      gap: 12px;
    }
  }

  .page-content {
    flex: 1;
    padding: 20px 24px;
    overflow-y: auto;

    .info-card {
      margin-bottom: 20px;

      .card-header {
        display: flex;
        align-items: center;
        gap: 8px;
        font-weight: 600;
        color: #303133;

        .el-icon {
          font-size: 18px;
        }

        .header-actions {
          margin-left: auto;
          display: flex;
          gap: 8px;
        }

        .edit-actions {
          margin-left: auto;
          display: flex;
          gap: 8px;
        }
      }

      .info-content {
        .info-item {
          margin-bottom: 16px;

          &:last-child {
            margin-bottom: 0;
          }

          .label {
            display: block;
            font-size: 13px;
            color: #909399;
            margin-bottom: 8px;
          }

          .value {
            margin: 0;
            color: #303133;
            line-height: 1.6;
          }

          .tags {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
          }

          .empty-text {
            color: #c0c4cc;
            font-size: 13px;
          }
        }
      }

      .io-content {
        .io-section {
          h4 {
            margin: 0 0 12px 0;
            font-size: 14px;
            font-weight: 600;
            color: #606266;
          }

          .io-list {
            display: flex;
            flex-direction: column;
            gap: 12px;
          }

          .io-param {
            padding: 12px;
            background: #f5f7fa;
            border-radius: 8px;
            border-left: 3px solid #409eff;

            .param-header {
              display: flex;
              align-items: center;
              gap: 8px;
              margin-bottom: 8px;
            }

            .param-desc {
              font-size: 13px;
              color: #606266;
              margin-bottom: 6px;
              line-height: 1.5;
            }

            .param-meta {
              display: flex;
              gap: 12px;
              font-size: 12px;
              color: #909399;

              .meta-item {
                display: flex;
                align-items: center;
                gap: 4px;
              }
            }
          }

          .empty-text {
            color: #c0c4cc;
            font-size: 13px;
          }
        }
      }

      .tools-content {
        .tools-grid {
          display: grid;
          gap: 12px;
        }

        .tool-card {
          display: flex;
          gap: 12px;
          padding: 12px;
          background: #f5f7fa;
          border-radius: 8px;
          transition: all 0.3s;

          &:hover {
            background: #ecf5ff;
          }

          .tool-icon {
            font-size: 24px;
            width: 40px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 8px;
            background: white;
          }

          .tool-info {
            flex: 1;
            min-width: 0;

            .tool-name {
              display: flex;
              align-items: center;
              gap: 8px;
              font-weight: 600;
              color: #303133;
              margin-bottom: 4px;
            }

            .tool-desc {
              font-size: 13px;
              color: #909399;
              overflow: hidden;
              text-overflow: ellipsis;
              white-space: nowrap;
            }
          }
        }

        .edit-section {
          h4 {
            margin: 0 0 12px 0;
            font-size: 14px;
            font-weight: 600;
            color: #606266;
          }
        }
      }

      &.prompt-card {
        .prompt-content {
          .template-selector {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 20px;
            padding: 16px;
            background: #f5f7fa;
            border-radius: 8px;

            .selector-label {
              font-size: 14px;
              font-weight: 600;
              color: #606266;
              white-space: nowrap;
            }
          }

          .template-detail {
            margin-top: 16px;
          }

          .prompt-meta {
            display: flex;
            gap: 8px;
            margin-bottom: 16px;
            flex-wrap: wrap;
          }

          .prompt-tabs {
            :deep(.el-tabs__content) {
              padding: 16px 0;
            }
          }

          .prompt-text {
            background: #f5f7fa;
            padding: 16px;
            border-radius: 8px;
            white-space: pre-wrap;
            word-break: break-word;
            line-height: 1.8;
            color: #303133;
            font-size: 14px;
            max-height: 400px;
            overflow-y: auto;
          }

          .prompt-remark {
            .remark-label {
              font-size: 13px;
              color: #909399;
              margin-bottom: 8px;
            }

            .remark-text {
              color: #606266;
              line-height: 1.6;
            }
          }

          .edit-mode {
            :deep(.el-form-item) {
              margin-bottom: 20px;
            }

            :deep(.el-textarea__inner) {
              font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
              font-size: 13px;
              line-height: 1.6;
            }
          }
        }
      }
    }
  }
}
</style>

