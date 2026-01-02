<template>
  <div class="agents-config-page">
    <div class="page-header">
      <div class="header-left">
        <h1>
          <el-icon class="header-icon"><UserFilled /></el-icon>
          Agent配置
        </h1>
        <span class="subtitle">查看和管理智能体配置</span>
      </div>
      <div class="header-right">
        <el-button @click="refreshAgents">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <div class="filter-section">
      <el-radio-group v-model="currentCategory" @change="handleCategoryChange">
        <el-radio-button label="">全部</el-radio-button>
        <el-radio-button v-for="cat in categories" :key="cat.id" :label="cat.id">
          {{ cat.name }} ({{ getCategoryCount(cat.id) }})
        </el-radio-button>
      </el-radio-group>
    </div>

    <el-row :gutter="20">
      <el-col v-for="agent in filteredAgents" :key="agent.id" :xs="24" :sm="12" :md="8" :lg="6">
        <el-card class="agent-card" shadow="hover" :body-style="{ padding: '0px' }">
          <div class="agent-header" :style="{ backgroundColor: agent.color + '15' }">
            <div class="agent-icon" :style="{ color: agent.color }">
              {{ agent.icon || '🤖' }}
            </div>
            <div class="agent-title">
              <h3>{{ agent.name }}</h3>
<el-tag size="small" :type="getLicenseType(agent.license_tier) || undefined">{{ agent.license_tier }}</el-tag>
            </div>
          </div>
          
          <div class="agent-body">
            <p class="description">{{ agent.description }}</p>
            
            <div class="tags">
              <el-tag v-for="tag in agent.tags" :key="tag" size="small" effect="plain" class="tag-item">
                {{ tag }}
              </el-tag>
            </div>

            <div class="status-bar">
              <span v-if="agent.is_available" class="status available">
                <el-icon><CircleCheckFilled /></el-icon> 可用
              </span>
              <span v-else class="status locked">
                <el-icon><Lock /></el-icon> {{ agent.locked_reason || '不可用' }}
              </span>
            </div>
          </div>
          
          <div class="agent-footer">
            <el-button text class="action-btn" @click="showAgentDetails(agent)">
              查看详情
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Agent详情弹窗 -->
    <el-dialog
      v-model="detailsVisible"
      :title="selectedAgent?.name"
      width="700px"
    >
      <div v-if="selectedAgent" class="agent-details">
        <div class="header-info">
          <div class="icon-wrapper" :style="{ color: selectedAgent.color, backgroundColor: selectedAgent.color + '15' }">
            {{ selectedAgent.icon }}
          </div>
          <div class="basic-info">
            <div class="id-row">ID: {{ selectedAgent.id }}</div>
            <div class="desc">{{ selectedAgent.description }}</div>
          </div>
        </div>

        <el-divider />

        <div class="detail-grid">
          <div class="grid-item">
            <span class="label">分类</span>
            <span class="value">{{ getCategoryName(selectedAgent.category) }}</span>
          </div>
          <div class="grid-item">
            <span class="label">权限等级</span>
            <el-tag size="small">{{ selectedAgent.license_tier }}</el-tag>
          </div>
        </div>

        <div class="detail-section">
          <h3>输入/输出</h3>
          <div class="io-container">
            <div class="io-box">
              <span class="io-label">输入</span>
              <div class="io-tags">
                <el-tag v-for="in_item in selectedAgent.inputs" :key="in_item" type="info" size="small">
                  {{ in_item }}
                </el-tag>
                <span v-if="!selectedAgent.inputs.length" class="empty-text">无特定输入</span>
              </div>
            </div>
            <div class="io-arrow">→</div>
            <div class="io-box">
              <span class="io-label">输出</span>
              <div class="io-tags">
                <el-tag v-for="out_item in selectedAgent.outputs" :key="out_item" type="success" size="small">
                  {{ out_item }}
                </el-tag>
                <span v-if="!selectedAgent.outputs.length" class="empty-text">无特定输出</span>
              </div>
            </div>
          </div>
        </div>
        
        <div class="detail-section" v-loading="toolsLoading">
          <div class="section-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
            <h3 style="margin: 0;">工具配置</h3>
            <el-button v-if="!isEditingTools" type="primary" link @click="startEditTools">
              <el-icon><Edit /></el-icon> 编辑
            </el-button>
            <div v-else class="edit-actions">
              <el-button size="small" @click="cancelEditTools">取消</el-button>
              <el-button size="small" type="primary" :loading="savingTools" @click="saveTools">保存</el-button>
            </div>
          </div>

          <!-- View Mode -->
          <div v-if="!isEditingTools">
            <div v-if="agentTools && agentTools.available_tools && agentTools.available_tools.length > 0">
              <div class="tools-grid">
                <div v-for="tool in agentTools.available_tools" :key="tool.id" class="tool-item">
                  <div class="tool-icon" :style="{ color: tool.color }">{{ tool.icon }}</div>
                  <div class="tool-info">
                    <div class="tool-name">
                      {{ tool.name }}
                      <el-tag v-if="agentTools.default_tools.includes(tool.id)" size="small" type="success" effect="plain">默认</el-tag>
                    </div>
                    <div class="tool-desc" :title="tool.description">{{ tool.description }}</div>
                  </div>
                </div>
              </div>
            </div>
            <div v-else-if="!toolsLoading" class="empty-state">
              暂无工具配置
            </div>
          </div>

          <!-- Edit Mode -->
          <div v-else class="edit-mode-container">
            <el-form label-position="top">
              <el-form-item label="最大调用次数">
                <el-input-number v-model="editingConfig.max_tool_calls" :min="1" :max="50" />
              </el-form-item>
              
              <el-form-item label="绑定工具">
                <el-input
                  v-model="toolSearchQuery"
                  placeholder="搜索工具（名称、描述、分类）"
                  prefix-icon="Search"
                  clearable
                  style="margin-bottom: 12px;"
                />
                <div class="tools-selection-list">
                  <div 
                    v-for="tool in filteredTools" 
                    :key="tool.id" 
                    class="tool-selection-item"
                    :class="{ selected: editingConfig.tools.includes(tool.id) }"
                  >
                    <div class="tool-checkbox">
                      <el-checkbox 
                        :model-value="editingConfig.tools.includes(tool.id)"
                        @change="toggleTool(tool.id)"
                      />
                    </div>
                    <div class="tool-content">
                      <div class="tool-main-info">
                        <span class="tool-icon" :style="{ color: tool.color }">{{ tool.icon }}</span>
                        <span class="tool-name">{{ tool.name }}</span>
                        <el-tag size="small" type="info">{{ tool.category }}</el-tag>
                      </div>
                      <div class="tool-desc">{{ tool.description }}</div>
                    </div>
                    <div class="tool-actions">
                       <el-checkbox 
                        v-if="editingConfig.tools.includes(tool.id)"
                        :model-value="editingConfig.default_tools.includes(tool.id)"
                        @change="toggleDefaultTool(tool.id)"
                        label="设为默认"
                      />
                    </div>
                  </div>
                </div>
              </el-form-item>
            </el-form>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { agentApi, type AgentMetadata, type AgentCategory, type AgentToolsConfig, type AgentToolsUpdate } from '@/api/agents'
import { toolsApi, type ToolMetadata } from '@/api/tools'

const loading = ref(false)
const agents = ref<AgentMetadata[]>([])
const categories = ref<AgentCategory[]>([])
const currentCategory = ref('')
const detailsVisible = ref(false)
const selectedAgent = ref<AgentMetadata | null>(null)
const agentTools = ref<AgentToolsConfig | null>(null)
const toolsLoading = ref(false)

// 编辑相关状态
const allTools = ref<ToolMetadata[]>([])
const isEditingTools = ref(false)
const toolSearchQuery = ref('')
const editingConfig = ref({
  tools: [] as string[],
  default_tools: [] as string[],
  max_tool_calls: 10
})
const savingTools = ref(false)

const getCategoryName = (categoryId: string) => {
  const category = categories.value.find(c => c.id === categoryId)
  return category ? category.name : categoryId
}

// 获取分类的 v2.0 agent 数量
const getCategoryCount = (categoryId: string) => {
  const v2Agents = agents.value.filter(isV2Agent)
  if (!categoryId) {
    return v2Agents.length
  }
  return v2Agents.filter(a => a.category === categoryId).length
}

const getLicenseType = (tier: string) => {
  switch (tier) {
    case 'free': return 'info'
    case 'basic': return 'success'
    case 'pro': return 'warning'
    case 'enterprise': return 'danger'
    default: return ''
  }
}

// 判断是否为 v2.0 agent
const isV2Agent = (agent: AgentMetadata): boolean => {
  const id = (agent.id || '').toLowerCase()
  const name = (agent.name || '').toLowerCase()
  const tags = Array.isArray(agent.tags) ? agent.tags : []
  
  // 1. ID 明确包含 _v2 或 v2_（最可靠的判断方式）
  if (id.includes('_v2') || id.startsWith('v2_')) {
    return true
  }
  
  // 2. 名称包含 v2.0 或 v2
  if (name.includes('v2.0') || name.includes(' v2')) {
    return true
  }
  
  // 3. tags 包含 v2 相关标签
  if (tags.some(tag => String(tag).toLowerCase().includes('v2'))) {
    return true
  }
  
  // 默认：过滤掉非v2.0的agent
  return false
}

const filteredAgents = computed(() => {
  // 🔥 只显示v2.0的agent，屏蔽非v2.0的agent
  const v2Agents = agents.value.filter(isV2Agent)
  
  // 再根据分类过滤
  if (!currentCategory.value) {
    return v2Agents
  }
  return v2Agents.filter(a => a.category === currentCategory.value)
})

const filteredTools = computed(() => {
  if (!toolSearchQuery.value) {
    return allTools.value
  }
  const query = toolSearchQuery.value.toLowerCase()
  return allTools.value.filter(tool => 
    tool.name.toLowerCase().includes(query) || 
    tool.description.toLowerCase().includes(query) ||
    tool.category.toLowerCase().includes(query)
  )
})

const loadData = async () => {
  loading.value = true
  try {
    const [agentsData, categoriesData] = await Promise.all([
      agentApi.listAvailable(), // 使用 listAvailable 以获取 availability info
      agentApi.getCategories()
    ])
    agents.value = agentsData
    categories.value = categoriesData
  } catch (error) {
    console.error('加载Agent失败:', error)
    ElMessage.error('加载Agent列表失败')
  } finally {
    loading.value = false
  }
}

const refreshAgents = () => {
  loadData()
}

const handleCategoryChange = () => {
  // logic if needed
}

const showAgentDetails = async (agent: AgentMetadata) => {
  selectedAgent.value = agent
  detailsVisible.value = true
  agentTools.value = null
  
  if (agent.id) {
    toolsLoading.value = true
    try {
      // 尝试获取工具配置，如果API不支持或出错，不影响显示其他信息
      const tools = await agentApi.getAgentTools(agent.id)
      agentTools.value = tools
    } catch (e) {
      console.warn('Failed to load agent tools:', e)
    } finally {
      toolsLoading.value = false
    }
  }
}

const startEditTools = async () => {
  if (!agentTools.value) return
  
  isEditingTools.value = true
  toolSearchQuery.value = ''
  // Initialize editing config
  editingConfig.value = {
    tools: [...agentTools.value.tools],
    default_tools: [...agentTools.value.default_tools],
    max_tool_calls: agentTools.value.max_tool_calls
  }
  
  // Load all tools if not loaded
  if (allTools.value.length === 0) {
    try {
      allTools.value = await toolsApi.listTools()
    } catch (e) {
      ElMessage.error('获取工具列表失败')
    }
  }
}

const cancelEditTools = () => {
  isEditingTools.value = false
}

const saveTools = async () => {
  if (!selectedAgent.value?.id) return
  
  savingTools.value = true
  try {
    await agentApi.updateAgentTools(selectedAgent.value.id, editingConfig.value)
    ElMessage.success('工具配置已更新')
    isEditingTools.value = false
    // Refresh agent tools
    const tools = await agentApi.getAgentTools(selectedAgent.value.id)
    agentTools.value = tools
  } catch (e) {
    ElMessage.error('更新失败')
  } finally {
    savingTools.value = false
  }
}

const toggleTool = (toolId: string) => {
  const index = editingConfig.value.tools.indexOf(toolId)
  if (index > -1) {
    // Remove tool
    editingConfig.value.tools.splice(index, 1)
    // Also remove from default tools if present
    const defaultIndex = editingConfig.value.default_tools.indexOf(toolId)
    if (defaultIndex > -1) {
      editingConfig.value.default_tools.splice(defaultIndex, 1)
    }
  } else {
    // Add tool
    editingConfig.value.tools.push(toolId)
  }
}

const toggleDefaultTool = (toolId: string) => {
  const index = editingConfig.value.default_tools.indexOf(toolId)
  if (index > -1) {
    editingConfig.value.default_tools.splice(index, 1)
  } else {
    editingConfig.value.default_tools.push(toolId)
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped lang="scss">
.agents-config-page {
  padding: 20px;
  background-color: var(--el-bg-color);
  min-height: calc(100vh - 60px);

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;

    .header-left {
      h1 {
        display: flex;
        align-items: center;
        font-size: 24px;
        margin: 0 0 8px 0;
        
        .header-icon {
          margin-right: 12px;
          color: var(--el-color-primary);
        }
      }

      .subtitle {
        color: var(--el-text-color-secondary);
        font-size: 14px;
      }
    }
  }

  .filter-section {
    margin-bottom: 24px;
  }
}

.agent-card {
  margin-bottom: 20px;
  transition: all 0.3s;
  border: 1px solid var(--el-border-color-lighter);
  
  &:hover {
    transform: translateY(-5px);
    box-shadow: 0 8px 16px rgba(0,0,0,0.1);
  }
  
  .agent-header {
    padding: 20px;
    display: flex;
    align-items: flex-start;
    
    .agent-icon {
      font-size: 32px;
      margin-right: 16px;
      background: #fff;
      width: 48px;
      height: 48px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    
    .agent-title {
      flex: 1;
      
      h3 {
        margin: 0 0 8px 0;
        font-size: 16px;
        line-height: 1.4;
      }
    }
  }
  
  .agent-body {
    padding: 20px;
    
    .description {
      color: var(--el-text-color-secondary);
      font-size: 13px;
      line-height: 1.6;
      height: 42px;
      overflow: hidden;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      margin-bottom: 16px;
    }
    
    .tags {
      margin-bottom: 16px;
      height: 24px;
      overflow: hidden;
      
      .tag-item {
        margin-right: 6px;
      }
    }
    
    .status-bar {
      font-size: 12px;
      
      .status {
        display: flex;
        align-items: center;
        gap: 4px;
        
        &.available {
          color: var(--el-color-success);
        }
        &.locked {
          color: var(--el-text-color-placeholder);
        }
      }
    }
  }
  
  .agent-footer {
    padding: 10px 20px;
    border-top: 1px solid var(--el-border-color-lighter);
    text-align: right;
    
    .action-btn {
      padding: 0;
    }
  }
}

.agent-details {
  .header-info {
    display: flex;
    align-items: flex-start;
    margin-bottom: 20px;
    
    .icon-wrapper {
      width: 64px;
      height: 64px;
      border-radius: 16px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 32px;
      margin-right: 20px;
    }
    
    .basic-info {
      .id-row {
        color: var(--el-text-color-secondary);
        font-size: 13px;
        margin-bottom: 8px;
      }
      
      .desc {
        font-size: 15px;
        line-height: 1.6;
      }
    }
  }
  
  .detail-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 20px;
    margin: 20px 0;
    
    .grid-item {
      display: flex;
      align-items: center;
      
      .label {
        color: var(--el-text-color-secondary);
        width: 80px;
      }
      
      .value {
        font-weight: 500;
      }
    }
  }
  
  .io-container {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: var(--el-fill-color-light);
    padding: 20px;
    border-radius: 8px;
    
    .io-box {
      flex: 1;
      display: flex;
      flex-direction: column;
      
      .io-label {
        font-size: 12px;
        color: var(--el-text-color-secondary);
        margin-bottom: 8px;
        text-transform: uppercase;
      }
      
      .io-tags {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        
        .empty-text {
          font-size: 12px;
          color: var(--el-text-color-placeholder);
          font-style: italic;
        }
      }
    }
    
    .io-arrow {
      margin: 0 20px;
      color: var(--el-text-color-placeholder);
      font-size: 20px;
    }
  }

  .tools-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;

    .tool-item {
      display: flex;
      align-items: flex-start;
      padding: 10px;
      background: var(--el-fill-color-light);
      border-radius: 8px;
      border: 1px solid transparent;

      &:hover {
        border-color: var(--el-border-color);
        background: var(--el-fill-color);
      }

      .tool-icon {
        font-size: 20px;
        margin-right: 12px;
        margin-top: 2px;
      }

      .tool-info {
        flex: 1;
        overflow: hidden;

        .tool-name {
          font-weight: 500;
          font-size: 14px;
          margin-bottom: 4px;
          display: flex;
          align-items: center;
          gap: 6px;
        }

        .tool-desc {
          font-size: 12px;
          color: var(--el-text-color-secondary);
          line-height: 1.4;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
      }
    }
  }
  
  .empty-state {
    color: var(--el-text-color-placeholder);
    font-size: 13px;
    text-align: center;
    padding: 20px 0;
    background: var(--el-fill-color-lighter);
    border-radius: 8px;
  }

  .tools-selection-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-height: 400px;
    overflow-y: auto;
    border: 1px solid var(--el-border-color-lighter);
    border-radius: 4px;
    padding: 8px;

    .tool-selection-item {
      display: flex;
      align-items: flex-start;
      padding: 8px;
      border-radius: 4px;
      background-color: var(--el-fill-color-light);
      transition: all 0.2s;
      
      &.selected {
        background-color: var(--el-color-primary-light-9);
        border: 1px solid var(--el-color-primary-light-5);
      }

      &:hover {
        background-color: var(--el-fill-color);
      }

      .tool-checkbox {
        margin-right: 12px;
        margin-top: 2px;
      }

      .tool-content {
        flex: 1;
        
        .tool-main-info {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 4px;

          .tool-icon {
            font-size: 16px;
          }

          .tool-name {
            font-weight: 500;
            font-size: 14px;
          }
        }

        .tool-desc {
          font-size: 12px;
          color: var(--el-text-color-secondary);
          line-height: 1.4;
        }
      }

      .tool-actions {
        margin-left: 12px;
        display: flex;
        align-items: center;
      }
    }
  }
}
</style>
