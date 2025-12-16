<template>
  <div class="workflow-editor">
    <!-- 顶部工具栏 -->
    <div class="editor-toolbar">
      <div class="toolbar-left">
        <el-button text @click="goBack">
          <el-icon><ArrowLeft /></el-icon>
          返回
        </el-button>
        <el-divider direction="vertical" />
        <span class="workflow-title">{{ workflow?.name || '加载中...' }}</span>
        <el-tag v-if="hasUnsavedChanges" type="warning" size="small">未保存</el-tag>
      </div>
      <div class="toolbar-center">
        <el-button-group>
          <el-button :type="isEditMode ? 'primary' : 'default'" @click="isEditMode = true">编辑</el-button>
          <el-button :type="!isEditMode ? 'primary' : 'default'" @click="isEditMode = false">预览</el-button>
        </el-button-group>
      </div>
      <div class="toolbar-right">
        <el-button @click="validateWorkflow">
          <el-icon><Check /></el-icon>
          验证
        </el-button>
        <el-button type="primary" @click="saveWorkflow" :loading="saving">
          <el-icon><DocumentChecked /></el-icon>
          保存
        </el-button>
        <el-button @click="setAsDefault">
          <el-icon><Star /></el-icon>
          设为默认
        </el-button>
        <el-button type="success" @click="executeWorkflow">
          <el-icon><VideoPlay /></el-icon>
          执行
        </el-button>
      </div>
    </div>

    <div class="editor-main">
      <!-- 左侧节点面板 -->
      <div class="node-panel" :class="{ collapsed: !nodePanelExpanded }" v-if="isEditMode">
        <!-- 面板头部 -->
        <div class="panel-header">
          <span v-if="nodePanelExpanded">节点</span>
          <el-button class="toggle-btn" text circle size="small" @click="nodePanelExpanded = !nodePanelExpanded">
            <el-icon><ArrowLeft v-if="nodePanelExpanded" /><ArrowRight v-else /></el-icon>
          </el-button>
        </div>

        <!-- 面板内容（展开时显示） -->
        <div class="panel-content" v-show="nodePanelExpanded">
          <h3>智能体节点</h3>

          <!-- 按类别分组 -->
          <el-collapse v-model="activeCategories">
            <el-collapse-item v-for="category in categories" :key="category.id" :name="category.id">
              <template #title>
                <span class="category-title">
                  {{ category.name }}
                  <el-tag size="small" round>{{ getCategoryCount(category.id) }}</el-tag>
                </span>
              </template>
              <div class="node-list">
                <div v-for="agent in getAgentsByCategory(category.id)" :key="agent.id"
                     class="draggable-node" :class="{ locked: !isAgentAvailable(agent) }"
                     :style="{ '--node-color': agent.color }"
                     draggable="true"
                     @dragstart="onDragStart($event, agent)">
                  <span class="node-icon">{{ agent.icon }}</span>
                  <span class="node-name">{{ agent.name }}</span>
                  <el-icon v-if="!isAgentAvailable(agent)" class="lock-icon"><Lock /></el-icon>
                </div>
              </div>
            </el-collapse-item>
          </el-collapse>

          <!-- 控制节点 -->
          <h3>控制节点</h3>
          <div class="node-list">
            <div class="draggable-node control-node" draggable="true" @dragstart="onDragStart($event, { id: 'start', type: 'start', name: '开始', icon: '▶️' })">
              <span class="node-icon">▶️</span>
              <span class="node-name">开始</span>
            </div>
            <div class="draggable-node control-node" draggable="true" @dragstart="onDragStart($event, { id: 'end', type: 'end', name: '结束', icon: '⏹️' })">
              <span class="node-icon">⏹️</span>
              <span class="node-name">结束</span>
            </div>
            <div class="draggable-node control-node" draggable="true" @dragstart="onDragStart($event, { id: 'condition', type: 'condition', name: '条件分支', icon: '🔀' })">
              <span class="node-icon">🔀</span>
              <span class="node-name">条件分支</span>
            </div>
            <div class="draggable-node control-node" draggable="true" @dragstart="onDragStart($event, { id: 'parallel', type: 'parallel', name: '并行开始', icon: '⚡' })">
              <span class="node-icon">⚡</span>
              <span class="node-name">并行开始</span>
            </div>
            <div class="draggable-node control-node" draggable="true" @dragstart="onDragStart($event, { id: 'merge', type: 'merge', name: '并行合并', icon: '🔗' })">
              <span class="node-icon">🔗</span>
              <span class="node-name">并行合并</span>
            </div>
            <div class="draggable-node control-node debate-node" draggable="true" @dragstart="onDragStart($event, { id: 'debate', type: 'debate', name: '辩论', icon: '⚔️' })">
              <span class="node-icon">⚔️</span>
              <span class="node-name">辩论节点</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 中间画布 -->
      <div class="canvas-container" ref="canvasRef"
           @drop="onDrop"
           @dragover.prevent>
        <WorkflowCanvas 
          :nodes="nodes" 
          :edges="edges"
          :readonly="!isEditMode"
          @nodes-change="onNodesChange"
          @edges-change="onEdgesChange"
          @node-click="onNodeClick"
        />
      </div>

      <!-- 右侧属性面板 -->
      <div class="property-panel" v-if="selectedNode && isEditMode">
        <h3>节点属性</h3>
        <el-form label-position="top">
          <el-form-item label="节点ID">
            <el-input v-model="selectedNode.id" disabled />
          </el-form-item>
          <el-form-item label="显示名称">
            <el-input v-model="selectedNode.label" @change="updateNode" />
          </el-form-item>
          <el-form-item label="节点类型">
            <el-tag>{{ getNodeTypeName(selectedNode.type) }}</el-tag>
          </el-form-item>
          <el-form-item v-if="selectedNode.agent_id" label="智能体">
            <el-tag type="success">{{ selectedNode.agent_id }}</el-tag>
          </el-form-item>

          <!-- 辩论节点配置 -->
          <template v-if="selectedNode.type === 'debate'">
            <el-divider>辩论配置</el-divider>
            <el-form-item label="辩论轮次">
              <el-select v-model="nodeConfig.rounds" @change="updateNodeConfig">
                <el-option label="自动（根据分析深度）" value="auto" />
                <el-option label="1轮" :value="1" />
                <el-option label="2轮" :value="2" />
                <el-option label="3轮" :value="3" />
                <el-option label="4轮" :value="4" />
                <el-option label="5轮" :value="5" />
              </el-select>
            </el-form-item>
            <el-form-item label="描述">
              <el-input v-model="nodeConfig.description" type="textarea" :rows="2" @change="updateNodeConfig" />
            </el-form-item>
            <el-form-item label="参与者">
              <div class="participants-list">
                <el-tag v-for="p in (nodeConfig.participants || [])" :key="p" closable @close="removeParticipant(p)">
                  {{ p }}
                </el-tag>
              </div>
              <el-select v-model="newParticipant" placeholder="添加参与者" filterable @change="addParticipant">
                <el-option v-for="agent in availableParticipants" :key="agent.id" :label="agent.name" :value="agent.id" />
              </el-select>
            </el-form-item>
          </template>

          <!-- 条件节点配置 -->
          <template v-if="selectedNode.type === 'condition'">
            <el-divider>条件配置</el-divider>
            <el-form-item label="条件表达式">
              <el-input v-model="nodeConfig.expression" type="textarea" :rows="2" placeholder="例如: confidence > 0.7" @change="updateNodeConfig" />
            </el-form-item>
            <el-form-item label="真分支标签">
              <el-input v-model="nodeConfig.true_label" placeholder="满足条件" @change="updateNodeConfig" />
            </el-form-item>
            <el-form-item label="假分支标签">
              <el-input v-model="nodeConfig.false_label" placeholder="不满足条件" @change="updateNodeConfig" />
            </el-form-item>
          </template>

          <!-- 并行节点配置 -->
          <template v-if="selectedNode.type === 'parallel'">
            <el-divider>并行配置</el-divider>
            <el-form-item label="超时时间（秒）">
              <el-input-number v-model="nodeConfig.timeout" :min="30" :max="600" :step="30" @change="updateNodeConfig" />
            </el-form-item>
            <el-form-item label="描述">
              <el-input v-model="nodeConfig.description" type="textarea" :rows="2" @change="updateNodeConfig" />
            </el-form-item>
          </template>

          <!-- 合并节点配置 -->
          <template v-if="selectedNode.type === 'merge'">
            <el-divider>合并配置</el-divider>
            <el-form-item label="合并策略">
              <el-select v-model="nodeConfig.strategy" @change="updateNodeConfig">
                <el-option label="等待全部完成" value="wait_all" />
                <el-option label="任一完成即可" value="any" />
                <el-option label="多数完成" value="majority" />
              </el-select>
            </el-form-item>
          </template>

          <!-- 工具配置（仅 Agent 节点） -->
          <template v-if="selectedNode.agent_id && agentToolsConfig">
            <el-divider>🔧 工具配置</el-divider>
            <div v-loading="loadingTools" class="tools-section">
              <div v-if="agentToolsConfig.available_tools.length === 0" class="no-tools">
                <el-text type="info">该智能体不使用工具</el-text>
              </div>
              <div v-else>
                <el-form-item label="最大调用次数">
                  <el-input-number
                    v-model="nodeConfig.max_tool_calls"
                    :min="0"
                    :max="10"
                    :placeholder="String(agentToolsConfig.max_tool_calls)"
                    @change="updateNodeConfig"
                  />
                </el-form-item>
                <div class="tools-list">
                  <div
                    v-for="tool in agentToolsConfig.available_tools"
                    :key="tool.id"
                    class="tool-item"
                    :class="{ 'is-default': agentToolsConfig.default_tools.includes(tool.id) }"
                  >
                    <el-checkbox
                      :model-value="isToolEnabled(tool.id)"
                      @change="(val: boolean) => toggleTool(tool.id, val)"
                    >
                      <span class="tool-icon">{{ tool.icon }}</span>
                      <span class="tool-name">{{ tool.name }}</span>
                    </el-checkbox>
                    <el-tooltip :content="tool.description" placement="left">
                      <el-tag size="small" :type="tool.is_online ? 'success' : 'info'">
                        {{ tool.is_online ? '在线' : '离线' }}
                      </el-tag>
                    </el-tooltip>
                  </div>
                </div>
                <el-text type="info" size="small">
                  数据源: {{ getToolDataSources() }}
                </el-text>
              </div>
            </div>
          </template>

          <!-- 提示词模板配置（仅 Agent 节点） -->
          <template v-if="selectedNode.agent_id">
            <el-divider>📝 提示词模板</el-divider>
            <div v-loading="loadingTemplates" class="template-section">
              <el-form-item label="选择模板">
                <el-select
                  v-model="nodeConfig.template_id"
                  placeholder="使用默认模板"
                  clearable
                  @change="onTemplateChange"
                >
                  <el-option
                    v-for="tpl in agentTemplates"
                    :key="tpl.id"
                    :label="`${tpl.template_name}${tpl.preference_type ? ` (${getPreferenceLabel(tpl.preference_type)})` : ''}${tpl.is_system ? ' [系统]' : ' [自定义]'}`"
                    :value="tpl.id"
                  >
                    <div class="template-option">
                      <span>{{ tpl.template_name }}</span>
                      <el-tag v-if="tpl.preference_type" size="small" :type="getPreferenceType(tpl.preference_type)">
                        {{ getPreferenceLabel(tpl.preference_type) }}
                      </el-tag>
                      <el-tag size="small" :type="tpl.is_system ? 'info' : 'success'">
                        {{ tpl.is_system ? '系统' : '自定义' }}
                      </el-tag>
                    </div>
                  </el-option>
                </el-select>
              </el-form-item>
              <div class="template-actions">
                <el-button size="small" @click="previewTemplate" :disabled="!nodeConfig.template_id">
                  预览模板
                </el-button>
                <el-button size="small" type="primary" text @click="goToTemplateEditor">
                  管理模板 →
                </el-button>
              </div>
              <div v-if="agentTemplates.length === 0 && !loadingTemplates" class="no-templates">
                <el-text type="info">暂无可用模板，将使用系统默认配置</el-text>
              </div>
            </div>
          </template>

          <el-form-item label="位置">
            <div class="position-inputs">
              <el-input-number v-model="selectedNode.position.x" :step="10" @change="updateNode" />
              <el-input-number v-model="selectedNode.position.y" :step="10" @change="updateNode" />
            </div>
          </el-form-item>
          <el-form-item>
            <el-button type="danger" @click="deleteSelectedNode">删除节点</el-button>
          </el-form-item>
        </el-form>

        <!-- 连接管理 -->
        <el-divider>节点连接</el-divider>
        <div class="connections-section">
          <h4>输入连接</h4>
          <div v-if="getIncomingEdges().length === 0" class="no-connections">无</div>
          <div v-for="edge in getIncomingEdges()" :key="edge.id" class="connection-item">
            <span>← {{ getNodeLabel(edge.source) }}</span>
            <el-button type="danger" size="small" text @click="deleteEdge(edge.id)">删除</el-button>
          </div>

          <h4>输出连接</h4>
          <div v-if="getOutgoingEdges().length === 0" class="no-connections">无</div>
          <div v-for="edge in getOutgoingEdges()" :key="edge.id" class="connection-item">
            <span>→ {{ getNodeLabel(edge.target) }}</span>
            <el-input v-if="selectedNode?.type === 'condition'" v-model="edge.label" size="small" placeholder="条件标签" style="width: 80px; margin: 0 8px" @change="updateEdgeLabel(edge)" />
            <el-button type="danger" size="small" text @click="deleteEdge(edge.id)">删除</el-button>
          </div>

          <!-- 添加连接 -->
          <div class="add-connection">
            <el-select v-model="newConnectionTarget" placeholder="连接到..." size="small" style="flex: 1">
              <el-option v-for="node in availableTargets" :key="node.id" :label="node.label" :value="node.id" />
            </el-select>
            <el-button type="primary" size="small" @click="addConnection" :disabled="!newConnectionTarget">添加</el-button>
          </div>
        </div>
      </div>

      <!-- 空状态提示 -->
      <div class="property-panel" v-else-if="isEditMode">
        <div class="empty-panel">
          <el-icon :size="48" color="var(--el-text-color-placeholder)"><InfoFilled /></el-icon>
          <p>选择节点查看属性</p>
          <el-divider />
          <h4>操作提示</h4>
          <ul class="tips-list">
            <li>从左侧拖拽节点到画布添加</li>
            <li>从节点右侧圆点拖动连线</li>
            <li>点击连线可删除</li>
            <li>点击节点可编辑属性</li>
          </ul>
        </div>
      </div>
    </div>

    <!-- 验证结果对话框 -->
    <el-dialog v-model="showValidation" title="验证结果" width="500px">
      <div v-if="validationResult">
        <el-result v-if="validationResult.is_valid" icon="success" title="验证通过" sub-title="工作流定义有效" />
        <div v-else>
          <el-alert v-for="(error, i) in validationResult.errors" :key="i" type="error" :title="error" show-icon :closable="false" style="margin-bottom: 8px" />
        </div>
        <div v-if="validationResult.warnings?.length">
          <el-divider>警告</el-divider>
          <el-alert v-for="(warning, i) in validationResult.warnings" :key="i" type="warning" :title="warning" show-icon :closable="false" style="margin-bottom: 8px" />
        </div>
      </div>
    </el-dialog>

    <!-- 模板预览对话框 -->
    <el-dialog v-model="showTemplatePreview" title="提示词模板预览" width="700px">
      <div v-if="templatePreviewContent" class="template-preview">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="模板名称">{{ templatePreviewContent.template_name }}</el-descriptions-item>
          <el-descriptions-item label="偏好类型">
            <el-tag v-if="templatePreviewContent.preference_type" :type="getPreferenceType(templatePreviewContent.preference_type)">
              {{ getPreferenceLabel(templatePreviewContent.preference_type) }}
            </el-tag>
            <span v-else>通用</span>
          </el-descriptions-item>
          <el-descriptions-item label="版本">v{{ templatePreviewContent.version }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="templatePreviewContent.status === 'active' ? 'success' : 'info'">
              {{ templatePreviewContent.status === 'active' ? '已启用' : '草稿' }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>

        <el-divider>系统提示词</el-divider>
        <el-input
          type="textarea"
          :model-value="templatePreviewContent.content?.system_prompt || ''"
          :rows="4"
          readonly
        />

        <el-divider>工具使用指导</el-divider>
        <el-input
          type="textarea"
          :model-value="templatePreviewContent.content?.tool_guidance || ''"
          :rows="3"
          readonly
        />

        <el-divider>分析要求</el-divider>
        <el-input
          type="textarea"
          :model-value="templatePreviewContent.content?.analysis_requirements || ''"
          :rows="3"
          readonly
        />
      </div>
      <template #footer>
        <el-button @click="showTemplatePreview = false">关闭</el-button>
        <el-button type="primary" @click="goToTemplateEditor">编辑模板</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, ArrowRight, Check, DocumentChecked, VideoPlay, Lock, InfoFilled, Star } from '@element-plus/icons-vue'
import { workflowApi, type WorkflowDefinition, type NodeDefinition, type EdgeDefinition, type ValidationResult } from '@/api/workflow'
import { agentApi, type AgentMetadata, type AgentCategory } from '@/api/agents'
import { toolsApi, type AgentToolsConfig, type ToolMetadata } from '@/api/tools'
import { TemplatesApi, type TemplateItem } from '@/api/templates'
import { useAuthStore } from '@/stores/auth'
import { useLicenseStore } from '@/stores/license'
import WorkflowCanvas from './components/WorkflowCanvas.vue'

const authStore = useAuthStore()
const licenseStore = useLicenseStore()

const route = useRoute()
const router = useRouter()

// 状态
const workflow = ref<WorkflowDefinition | null>(null)
const nodes = ref<NodeDefinition[]>([])
const edges = ref<EdgeDefinition[]>([])
const agents = ref<AgentMetadata[]>([])
const allTools = ref<ToolMetadata[]>([])
const categories = ref<AgentCategory[]>([])
const selectedNode = ref<NodeDefinition | null>(null)
const isEditMode = ref(true)
const saving = ref(false)
const hasUnsavedChanges = ref(false)
const showValidation = ref(false)
const validationResult = ref<ValidationResult | null>(null)
const activeCategories = ref<string[]>(['analyst', 'researcher'])
const canvasRef = ref<HTMLElement | null>(null)
const nodePanelExpanded = ref(true)  // 左侧面板展开状态

// 工具配置
const agentToolsConfig = ref<AgentToolsConfig | null>(null)
const loadingTools = ref(false)

// 提示词模板配置
const agentTemplates = ref<TemplateItem[]>([])
const loadingTemplates = ref(false)
const showTemplatePreview = ref(false)
const templatePreviewContent = ref<any>(null)

// 节点配置
const nodeConfig = ref<Record<string, any>>({})
const newParticipant = ref('')
const newConnectionTarget = ref('')

// 计算属性
const workflowId = computed(() => route.params.id as string)

const getAgentsByCategory = (categoryId: string) => {
  // 根据工作流类型过滤智能体
  const workflowType = workflow.value?.config?.workflow_type || workflow.value?.id

  // 定义每种工作流类型对应的智能体
  const workflowAgents: Record<string, string[]> = {
    // 交易复盘工作流
    'trade_review': ['timing_analyst', 'position_analyst', 'emotion_analyst', 'attribution_analyst', 'review_manager'],
    // 持仓分析工作流
    'position_analysis': ['pa_technical', 'pa_fundamental', 'pa_risk', 'pa_advisor'],
    // 默认完整分析工作流 - 显示所有智能体
    'default': [], // 空数组表示显示所有
    'simple': [], // 简单工作流也显示所有
  }

  const allowedAgents = workflowAgents[workflowType] || []

  // 如果是空数组（默认工作流），显示所有该分类的智能体
  if (allowedAgents.length === 0) {
    return agents.value.filter(a => a.category === categoryId)
  }

  // 否则只显示当前工作流相关的智能体
  return agents.value.filter(a =>
    a.category === categoryId && allowedAgents.includes(a.id)
  )
}

const getCategoryCount = (categoryId: string) => {
  return getAgentsByCategory(categoryId).length
}

// 节点类型名称
const getNodeTypeName = (type: string) => {
  const names: Record<string, string> = {
    start: '开始',
    end: '结束',
    analyst: '分析师',
    researcher: '研究员',
    trader: '交易员',
    risk: '风险分析',
    manager: '经理',
    condition: '条件分支',
    parallel: '并行执行',
    merge: '合并',
    debate: '辩论'
  }
  return names[type] || type
}

// 可用的辩论参与者
const availableParticipants = computed(() => {
  const currentParticipants = nodeConfig.value.participants || []
  return agents.value.filter(a =>
    ['researcher', 'risk'].includes(a.category) &&
    !currentParticipants.includes(a.id)
  )
})

// 可用的连接目标
const availableTargets = computed(() => {
  if (!selectedNode.value) return []
  const currentTargets = edges.value
    .filter(e => e.source === selectedNode.value!.id)
    .map(e => e.target)
  return nodes.value.filter(n =>
    n.id !== selectedNode.value!.id &&
    n.type !== 'start' &&
    !currentTargets.includes(n.id)
  )
})

// 加载数据
const loadWorkflow = async () => {
  if (!workflowId.value) return

  try {
    workflow.value = await workflowApi.get(workflowId.value)
    nodes.value = workflow.value.nodes || []
    edges.value = workflow.value.edges || []
  } catch (error) {
    ElMessage.error('加载工作流失败')
    console.error(error)
  }
}

const loadAgents = async () => {
  try {
    // 获取所有智能体（包括不可用的），让前端自己判断权限
    agents.value = await agentApi.listAll()
    categories.value = await agentApi.getCategories()
  } catch (error) {
    console.error('加载智能体失败:', error)
  }
}

// 检查智能体是否可用（基于前端权限检查）
const isAgentAvailable = (agent: any) => {
  // 如果没有 license_tier 信息，默认可用
  if (!agent.license_tier) return true

  // 根据 license_tier 检查权限
  const tier = agent.license_tier.toLowerCase()
  if (tier === 'free') return true
  if (tier === 'basic') return true
  if (['pro', 'enterprise'].includes(tier)) {
    return licenseStore.isPro
  }

  return true
}

// 获取智能体锁定原因
const getAgentLockedReason = (agent: any) => {
  if (isAgentAvailable(agent)) return null

  const tier = agent.license_tier?.toLowerCase()
  if (['pro', 'enterprise'].includes(tier)) {
    return '需要高级学员权限'
  }

  return '此智能体需要更高级别许可证'
}

// 操作方法
const goBack = () => {
  if (hasUnsavedChanges.value) {
    ElMessageBox.confirm('有未保存的更改，确定离开吗？', '提示', {
      confirmButtonText: '离开',
      cancelButtonText: '取消',
      type: 'warning'
    }).then(() => router.push('/workflow'))
  } else {
    router.push('/workflow')
  }
}

const saveWorkflow = async () => {
  if (!workflow.value) return

  saving.value = true
  try {
    const result = await workflowApi.update(workflowId.value, {
      ...workflow.value,
      nodes: nodes.value,
      edges: edges.value
    })

    if (result.success) {
      ElMessage.success('保存成功')
      hasUnsavedChanges.value = false
    } else {
      ElMessage.error(result.message || '保存失败')
    }
  } catch (error) {
    ElMessage.error('保存失败')
    console.error(error)
  } finally {
    saving.value = false
  }
}

const validateWorkflow = async () => {
  try {
    const response = await workflowApi.validate({
      id: workflowId.value,
      name: workflow.value?.name || '',
      description: workflow.value?.description || '',
      version: workflow.value?.version || '1.0.0',
      nodes: nodes.value,
      edges: edges.value,
      tags: workflow.value?.tags || [],
      config: workflow.value?.config || {}
    })
    // API 返回格式为 { success: true, data: { is_valid, errors, warnings } }
    validationResult.value = response.data || response
    showValidation.value = true
  } catch (error) {
    ElMessage.error('验证失败')
    console.error(error)
  }
}

const setAsDefault = async () => {
  try {
    const result = await workflowApi.setAsDefault(workflowId.value)
    if (result.success) {
      ElMessage.success('已设为默认分析流')
    } else {
      ElMessage.error(result.message || '设置失败')
    }
  } catch (error) {
    console.error('设置默认失败:', error)
    ElMessage.error('设置默认失败')
  }
}

const executeWorkflow = () => {
  router.push(`/workflow/execute/${workflowId.value}`)
}

// 拖拽处理
const onDragStart = (event: DragEvent, agent: any) => {
  if (!isAgentAvailable(agent)) {
    event.preventDefault()
    ElMessage.warning(getAgentLockedReason(agent) || '此智能体需要更高级别许可证')
    return
  }
  event.dataTransfer?.setData('application/json', JSON.stringify(agent))
}

const onDrop = (event: DragEvent) => {
  const data = event.dataTransfer?.getData('application/json')
  if (!data) return

  const agent = JSON.parse(data)
  const rect = canvasRef.value?.getBoundingClientRect()
  if (!rect) return

  const position = {
    x: event.clientX - rect.left,
    y: event.clientY - rect.top
  }

  addNode(agent, position)
}

const addNode = (agent: any, position: { x: number; y: number }) => {
  const nodeId = `${agent.type || agent.category}_${Date.now()}`

  const newNode: NodeDefinition = {
    id: nodeId,
    type: agent.type || agent.category,
    agent_id: agent.id !== agent.type ? agent.id : undefined,
    label: agent.name,
    position
  }

  nodes.value.push(newNode)
  hasUnsavedChanges.value = true
}

// 节点事件
const onNodesChange = (newNodes: NodeDefinition[]) => {
  nodes.value = newNodes
  hasUnsavedChanges.value = true
}

const onEdgesChange = (newEdges: EdgeDefinition[]) => {
  edges.value = newEdges
  hasUnsavedChanges.value = true
}

const onNodeClick = async (node: NodeDefinition) => {
  console.log('Editor onNodeClick received:', node.id, node.label)
  selectedNode.value = { ...node }
  // 加载节点配置
  nodeConfig.value = { ...(node.config || {}) }
  console.log('selectedNode set to:', selectedNode.value)

  // 如果是 Agent 节点，加载工具配置和模板列表
  if (node.agent_id) {
    await Promise.all([
      loadAgentTools(node.agent_id),
      loadAgentTemplates(node.agent_id)
    ])
  } else {
    agentToolsConfig.value = null
    agentTemplates.value = []
  }
}

// 加载 Agent 工具配置
const loadAgentTools = async (agentId: string) => {
  console.log('loadAgentTools called with agentId:', agentId)
  loadingTools.value = true
  try {
    const result = await toolsApi.getAgentTools(agentId)
    console.log('loadAgentTools result:', result)
    agentToolsConfig.value = result
  } catch (error) {
    console.error('加载工具配置失败:', error)
    agentToolsConfig.value = null
  } finally {
    loadingTools.value = false
    console.log('agentToolsConfig.value:', agentToolsConfig.value)
  }
}

// 工具配置辅助函数
const isToolEnabled = (toolId: string): boolean => {
  // 如果节点配置了 enabled_tools，使用它；否则使用默认工具
  if (nodeConfig.value.enabled_tools) {
    return nodeConfig.value.enabled_tools.includes(toolId)
  }
  return agentToolsConfig.value?.default_tools.includes(toolId) ?? false
}

const toggleTool = (toolId: string, enabled: boolean) => {
  if (!nodeConfig.value.enabled_tools) {
    // 初始化为默认工具列表
    nodeConfig.value.enabled_tools = [...(agentToolsConfig.value?.default_tools || [])]
  }

  if (enabled) {
    if (!nodeConfig.value.enabled_tools.includes(toolId)) {
      nodeConfig.value.enabled_tools.push(toolId)
    }
  } else {
    nodeConfig.value.enabled_tools = nodeConfig.value.enabled_tools.filter((id: string) => id !== toolId)
  }
  updateNodeConfig()
}

const getToolDataSources = (): string => {
  if (!agentToolsConfig.value) return ''
  const sources = new Set(agentToolsConfig.value.available_tools.map(t => t.data_source))
  return Array.from(sources).filter(Boolean).join(', ')
}

// 提示词模板相关函数
// agentId -> { type, name } 映射 (匹配数据库中的模板配置)
const agentTemplateMapping: Record<string, { type: string; name: string }> = {
  // v1.0 agents
  market_analyst: { type: 'analysts', name: 'market_analyst' },
  fundamentals_analyst: { type: 'analysts', name: 'fundamentals_analyst' },
  news_analyst: { type: 'analysts', name: 'news_analyst' },
  social_analyst: { type: 'analysts', name: 'social_media_analyst' },  // 数据库中是 social_media_analyst
  sector_analyst: { type: 'analysts', name: 'sector_analyst' },
  index_analyst: { type: 'analysts', name: 'index_analyst' },
  bull_researcher: { type: 'researchers', name: 'bull_researcher' },
  bear_researcher: { type: 'researchers', name: 'bear_researcher' },
  risky_analyst: { type: 'debators', name: 'aggressive_debator' },  // 数据库中是 aggressive_debator
  safe_analyst: { type: 'debators', name: 'conservative_debator' },  // 数据库中是 conservative_debator
  neutral_analyst: { type: 'debators', name: 'neutral_debator' },  // 数据库中是 neutral_debator
  research_manager: { type: 'managers', name: 'research_manager' },
  risk_manager: { type: 'managers', name: 'risk_manager' },
  trader: { type: 'trader', name: 'trader' },
  // 持仓分析师
  position_advisor: { type: 'trader', name: 'position_advisor' },
  // 复盘分析师
  timing_analyst: { type: 'reviewers', name: 'timing_analyst' },
  position_analyst: { type: 'reviewers', name: 'position_analyst' },
  emotion_analyst: { type: 'reviewers', name: 'emotion_analyst' },
  attribution_analyst: { type: 'reviewers', name: 'attribution_analyst' },
  review_manager: { type: 'reviewers', name: 'review_manager' },
  // 持仓分析智能体
  pa_technical: { type: 'position_analysis', name: 'pa_technical' },
  pa_fundamental: { type: 'position_analysis', name: 'pa_fundamental' },
  pa_risk: { type: 'position_analysis', name: 'pa_risk' },
  pa_advisor: { type: 'position_analysis', name: 'pa_advisor' },

  // v2.0 agents
  fundamentals_analyst_v2: { type: 'analysts_v2', name: 'fundamentals_analyst_v2' },
  market_analyst_v2: { type: 'analysts_v2', name: 'market_analyst_v2' },
  news_analyst_v2: { type: 'analysts_v2', name: 'news_analyst_v2' },
  social_analyst_v2: { type: 'analysts_v2', name: 'social_analyst_v2' },
  sector_analyst_v2: { type: 'analysts_v2', name: 'sector_analyst_v2' },
  index_analyst_v2: { type: 'analysts_v2', name: 'index_analyst_v2' },
  bull_researcher_v2: { type: 'researchers_v2', name: 'bull_researcher_v2' },
  bear_researcher_v2: { type: 'researchers_v2', name: 'bear_researcher_v2' },
  research_manager_v2: { type: 'managers_v2', name: 'research_manager_v2' },
  risk_manager_v2: { type: 'managers_v2', name: 'risk_manager_v2' },
  trader_v2: { type: 'trader_v2', name: 'trader_v2' },
  risky_analyst_v2: { type: 'debators_v2', name: 'risky_analyst_v2' },
  safe_analyst_v2: { type: 'debators_v2', name: 'safe_analyst_v2' },
  neutral_analyst_v2: { type: 'debators_v2', name: 'neutral_analyst_v2' },
  timing_analyst_v2: { type: 'reviewers_v2', name: 'timing_analyst_v2' },
  position_analyst_v2: { type: 'reviewers_v2', name: 'position_analyst_v2' },
  emotion_analyst_v2: { type: 'reviewers_v2', name: 'emotion_analyst_v2' },
  attribution_analyst_v2: { type: 'reviewers_v2', name: 'attribution_analyst_v2' },
  review_manager_v2: { type: 'reviewers_v2', name: 'review_manager_v2' },
  pa_technical_v2: { type: 'position_analysis_v2', name: 'pa_technical_v2' },
  pa_fundamental_v2: { type: 'position_analysis_v2', name: 'pa_fundamental_v2' },
  pa_risk_v2: { type: 'position_analysis_v2', name: 'pa_risk_v2' },
  pa_advisor_v2: { type: 'position_analysis_v2', name: 'pa_advisor_v2' },
}

const loadAgentTemplates = async (agentId: string) => {
  loadingTemplates.value = true
  try {
    // 使用映射获取正确的 agent_type 和 agent_name
    const mapping = agentTemplateMapping[agentId] || { type: 'analysts', name: agentId }
    // 传入当前用户 ID，获取系统模板 + 用户模板
    const userId = authStore.user?.id
    console.log('loadAgentTemplates:', { agentId, mappedType: mapping.type, mappedName: mapping.name, userId })
    const res = await TemplatesApi.listByAgent(mapping.type, mapping.name, undefined, userId)
    agentTemplates.value = res.data?.templates || []
    console.log('loadAgentTemplates result:', agentTemplates.value.length, '个模板')
  } catch (error) {
    console.error('加载模板列表失败:', error)
    agentTemplates.value = []
  } finally {
    loadingTemplates.value = false
  }
}

const onTemplateChange = (templateId: string | null) => {
  nodeConfig.value.template_id = templateId
  updateNodeConfig()
}

const previewTemplate = async () => {
  if (!nodeConfig.value.template_id) return
  try {
    const res = await TemplatesApi.get(nodeConfig.value.template_id)
    templatePreviewContent.value = res.data
    showTemplatePreview.value = true
  } catch (error) {
    ElMessage.error('加载模板预览失败')
  }
}

const goToTemplateEditor = () => {
  // 跳转到模板管理页面
  const agentId = selectedNode.value?.agent_id
  if (agentId) {
    const mapping = agentTemplateMapping[agentId] || { type: 'analysts', name: agentId }
    router.push({
      path: '/settings/templates/manage',
      query: {
        agent_type: mapping.type,
        agent_name: mapping.name
      }
    })
  } else {
    router.push('/settings/templates/manage')
  }
}

const getPreferenceLabel = (type: string): string => {
  const labels: Record<string, string> = {
    aggressive: '激进',
    neutral: '中性',
    conservative: '保守',
  }
  return labels[type] || type
}

const getPreferenceType = (type: string): '' | 'success' | 'warning' | 'danger' | 'info' => {
  const types: Record<string, '' | 'success' | 'warning' | 'danger' | 'info'> = {
    aggressive: 'danger',
    neutral: '',
    conservative: 'success',
  }
  return types[type] || 'info'
}

const updateNode = () => {
  if (!selectedNode.value) return

  const index = nodes.value.findIndex(n => n.id === selectedNode.value!.id)
  if (index >= 0) {
    nodes.value[index] = { ...selectedNode.value }
    hasUnsavedChanges.value = true
  }
}

const updateNodeConfig = () => {
  if (!selectedNode.value) return

  selectedNode.value.config = { ...nodeConfig.value }
  updateNode()
}

const deleteSelectedNode = () => {
  if (!selectedNode.value) return

  nodes.value = nodes.value.filter(n => n.id !== selectedNode.value!.id)
  edges.value = edges.value.filter(e => e.source !== selectedNode.value!.id && e.target !== selectedNode.value!.id)
  selectedNode.value = null
  hasUnsavedChanges.value = true
}

// 辩论参与者管理
const addParticipant = (participantId: string) => {
  if (!nodeConfig.value.participants) {
    nodeConfig.value.participants = []
  }
  nodeConfig.value.participants.push(participantId)
  newParticipant.value = ''
  updateNodeConfig()
}

const removeParticipant = (participantId: string) => {
  nodeConfig.value.participants = nodeConfig.value.participants.filter((p: string) => p !== participantId)
  updateNodeConfig()
}

// 连接管理
const getIncomingEdges = () => {
  if (!selectedNode.value) return []
  return edges.value.filter(e => e.target === selectedNode.value!.id)
}

const getOutgoingEdges = () => {
  if (!selectedNode.value) return []
  return edges.value.filter(e => e.source === selectedNode.value!.id)
}

const getNodeLabel = (nodeId: string) => {
  const node = nodes.value.find(n => n.id === nodeId)
  return node?.label || nodeId
}

const deleteEdge = (edgeId: string) => {
  edges.value = edges.value.filter(e => e.id !== edgeId)
  hasUnsavedChanges.value = true
}

const updateEdgeLabel = (edge: EdgeDefinition) => {
  const index = edges.value.findIndex(e => e.id === edge.id)
  if (index >= 0) {
    edges.value[index] = { ...edge }
    hasUnsavedChanges.value = true
  }
}

const addConnection = () => {
  if (!selectedNode.value || !newConnectionTarget.value) return

  const newEdge: EdgeDefinition = {
    id: `e_${selectedNode.value.id}_${newConnectionTarget.value}_${Date.now()}`,
    source: selectedNode.value.id,
    target: newConnectionTarget.value
  }

  edges.value.push(newEdge)
  newConnectionTarget.value = ''
  hasUnsavedChanges.value = true
}

// 监听变化
watch([nodes, edges], () => {
  hasUnsavedChanges.value = true
}, { deep: true })

// 初始化
onMounted(() => {
  loadWorkflow()
  loadAgents()
})
</script>

<style scoped lang="scss">
.workflow-editor {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--el-bg-color);
}

.editor-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  background: var(--el-bg-color-overlay);
  border-bottom: 1px solid var(--el-border-color-light);

  .toolbar-left {
    display: flex;
    align-items: center;
    gap: 12px;

    .workflow-title {
      font-size: 16px;
      font-weight: 600;
    }
  }

  .toolbar-right {
    display: flex;
    gap: 8px;
  }
}

.editor-main {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.node-panel {
  width: 260px;
  min-width: 260px;
  flex-shrink: 0;
  background: var(--el-bg-color-overlay);
  border-right: 1px solid var(--el-border-color-light);
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease, min-width 0.3s ease;

  &.collapsed {
    width: 48px;
    min-width: 48px;

    .panel-header {
      justify-content: center;
      padding: 12px 8px;
    }
  }

  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px;
    border-bottom: 1px solid var(--el-border-color-light);
    font-weight: 600;
    font-size: 14px;
    color: var(--el-text-color-primary);
    flex-shrink: 0;

    .toggle-btn {
      flex-shrink: 0;
    }
  }

  .panel-content {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
  }

  h3 {
    margin: 0 0 12px;
    font-size: 14px;
    color: var(--el-text-color-secondary);
  }

  .category-title {
    display: flex;
    align-items: center;
    gap: 8px;
  }
}

.node-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.draggable-node {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color);
  border-left: 3px solid var(--node-color, var(--el-color-primary));
  border-radius: 6px;
  cursor: grab;
  transition: all 0.2s;

  &:hover {
    background: var(--el-fill-color);
    border-color: var(--node-color, var(--el-color-primary));
  }

  &.locked {
    opacity: 0.6;
    cursor: not-allowed;
  }

  &.control-node {
    border-left-color: var(--el-color-info);
  }

  .node-icon {
    font-size: 18px;
  }

  .node-name {
    flex: 1;
    font-size: 13px;
  }

  .lock-icon {
    color: var(--el-text-color-placeholder);
  }
}

.canvas-container {
  flex: 1;
  min-width: 0;  /* 防止 flex item 溢出 */
  position: relative;
  overflow: hidden;  /* 确保内容不溢出 */
  background:
    linear-gradient(90deg, var(--el-border-color-extra-light) 1px, transparent 1px),
    linear-gradient(var(--el-border-color-extra-light) 1px, transparent 1px);
  background-size: 20px 20px;
}

.property-panel {
  width: 300px;
  min-width: 300px;
  flex-shrink: 0;
  background: var(--el-bg-color-overlay);
  border-left: 1px solid var(--el-border-color-light);
  padding: 16px;
  overflow-y: auto;

  h3 {
    margin: 0 0 16px;
    font-size: 14px;
    color: var(--el-text-color-secondary);
  }

  h4 {
    margin: 12px 0 8px;
    font-size: 13px;
    color: var(--el-text-color-regular);
  }

  .position-inputs {
    display: flex;
    gap: 8px;

    .el-input-number {
      flex: 1;
    }
  }

  .participants-list {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-bottom: 8px;
  }

  .connections-section {
    .no-connections {
      color: var(--el-text-color-placeholder);
      font-size: 12px;
      padding: 4px 0;
    }

    .connection-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 4px 0;
      font-size: 13px;
    }

    .add-connection {
      display: flex;
      gap: 8px;
      margin-top: 12px;
    }
  }

  .empty-panel {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 24px 0;

    p {
      color: var(--el-text-color-placeholder);
      margin: 12px 0;
    }

    .tips-list {
      list-style: none;
      padding: 0;
      margin: 0;
      text-align: left;
      width: 100%;

      li {
        padding: 6px 0;
        color: var(--el-text-color-secondary);
        font-size: 13px;

        &::before {
          content: '•';
          color: var(--el-color-primary);
          margin-right: 8px;
        }
      }
    }
  }

  // 工具配置样式
  .tools-section {
    .no-tools {
      text-align: center;
      padding: 12px 0;
    }

    .tools-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin: 12px 0;
    }

    .tool-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 8px 12px;
      background: var(--el-fill-color-light);
      border-radius: 6px;
      transition: all 0.2s;

      &:hover {
        background: var(--el-fill-color);
      }

      &.is-default {
        border-left: 3px solid var(--el-color-primary);
      }

      .tool-icon {
        margin-right: 6px;
      }

      .tool-name {
        font-size: 13px;
      }
    }
  }

  // 提示词模板样式
  .template-section {
    .template-actions {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: 8px;
    }

    .no-templates {
      text-align: center;
      padding: 12px 0;
    }

    .template-option {
      display: flex;
      align-items: center;
      gap: 8px;

      span:first-child {
        flex: 1;
      }
    }
  }
}

// 模板预览弹窗样式
.template-preview {
  .el-descriptions {
    margin-bottom: 16px;
  }

  .el-textarea {
    :deep(.el-textarea__inner) {
      font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
      font-size: 13px;
      background: var(--el-fill-color-light);
    }
  }
}
</style>

