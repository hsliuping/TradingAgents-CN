<template>
  <div class="workflow-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <h1>
          <el-icon class="header-icon"><SetUp /></el-icon>
          分析流管理
        </h1>
        <span class="subtitle">设计和管理 AI 多智能体协作分析流程</span>
      </div>
      <div class="header-right">
        <el-button @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon>
          新建空白流程
        </el-button>
      </div>
    </div>

    <!-- 系统分析流模板 -->
    <div class="section">
      <div class="section-header">
        <h2>
          <el-icon><Promotion /></el-icon>
          系统分析流模板
        </h2>
        <span class="section-desc">基于 TradingAgents 论文设计的多智能体协作分析流程</span>
      </div>

      <el-row :gutter="20">
        <el-col v-for="template in sortedTemplates" :key="template.id" :xs="24" :md="12">
          <el-card class="template-card" shadow="hover">
            <div class="template-header">
              <div class="template-title">
                <el-icon class="template-icon" :style="{ color: getTemplateColor(template.id) }">
                  <component :is="getTemplateIcon(template.id)" />
                </el-icon>
                <div>
                  <h3>{{ template.name }}</h3>
                  <el-tag size="small" type="success">官方模板</el-tag>
                </div>
              </div>
              <div class="template-actions">
                <el-button type="primary" @click="useTemplate(template)">
                  <el-icon><DocumentCopy /></el-icon>
                  使用此模板
                </el-button>
                <el-button @click="openPreview(template)">
                  <el-icon><View /></el-icon>
                  预览
                </el-button>
              </div>
            </div>

            <p class="template-desc">{{ template.description }}</p>

            <!-- 流程预览图 -->
            <div class="flow-preview">
              <div class="flow-diagram">
                <!-- 并行分析层 -->
                <div class="flow-layer">
                  <span class="layer-label">并行分析</span>
                  <div class="flow-nodes parallel">
                    <div v-for="node in getAnalystNodes(template)" :key="node.id" class="flow-node analyst">
                      <el-tooltip :content="node.label">
                        <span>{{ getNodeIcon(node) }}</span>
                      </el-tooltip>
                    </div>
                  </div>
                </div>

                <!-- 辩论层 -->
                <div class="flow-layer" v-if="getResearcherNodes(template).length > 0">
                  <span class="layer-label">多空辩论</span>
                  <div class="flow-nodes debate">
                    <div class="flow-node researcher bull">
                      <el-tooltip content="看多研究员">
                        <span>🐂</span>
                      </el-tooltip>
                    </div>
                    <div class="debate-indicator">
                      <span class="debate-arrows">⚔️</span>
                      <span class="debate-rounds">{{ getDebateRounds(template, 'debate') }}</span>
                    </div>
                    <div class="flow-node researcher bear">
                      <el-tooltip content="看空研究员">
                        <span>🐻</span>
                      </el-tooltip>
                    </div>
                  </div>
                </div>

                <!-- 决策层 -->
                <div class="flow-layer">
                  <span class="layer-label">决策</span>
                  <div class="flow-nodes decision">
                    <div class="flow-node manager">
                      <el-tooltip content="研究经理">
                        <span>👔</span>
                      </el-tooltip>
                    </div>
                    <span class="flow-arrow">→</span>
                    <div class="flow-node trader">
                      <el-tooltip content="交易员">
                        <span>💰</span>
                      </el-tooltip>
                    </div>
                  </div>
                </div>

                <!-- 风险辩论层 -->
                <div class="flow-layer" v-if="template.nodes?.some(n => n.id === 'risk_debate')">
                  <span class="layer-label">风险辩论</span>
                  <div class="flow-nodes debate">
                    <div class="flow-node risk risky">
                      <el-tooltip content="激进分析师">
                        <span>🔥</span>
                      </el-tooltip>
                    </div>
                    <div class="debate-indicator">
                      <span class="debate-arrows">⚔️</span>
                      <span class="debate-rounds">{{ getDebateRounds(template, 'risk') }}</span>
                    </div>
                    <div class="flow-node risk safe">
                      <el-tooltip content="保守分析师">
                        <span>🛡️</span>
                      </el-tooltip>
                    </div>
                    <div class="debate-indicator">
                      <span class="debate-arrows">⚔️</span>
                    </div>
                    <div class="flow-node risk neutral">
                      <el-tooltip content="中性分析师">
                        <span>⚖️</span>
                      </el-tooltip>
                    </div>
                  </div>
                </div>

                <!-- 风险裁决 -->
                <div class="flow-layer">
                  <span class="layer-label">风险裁决</span>
                  <div class="flow-nodes decision">
                    <div class="flow-node manager">
                      <el-tooltip content="风险经理">
                        <span>👨‍⚖️</span>
                      </el-tooltip>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="template-stats">
              <div class="stat">
                <el-icon><User /></el-icon>
                <span>{{ template.nodes?.filter(n => n.type !== 'start' && n.type !== 'end' && n.type !== 'parallel' && n.type !== 'merge' && n.type !== 'debate').length || 0 }} 智能体</span>
              </div>
              <div class="stat">
                <el-icon><Connection /></el-icon>
                <span>{{ template.edges?.length || 0 }} 连接</span>
              </div>
              <div class="stat">
                <el-icon><Timer /></el-icon>
                <span>预计 5-8 分钟</span>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 我的分析流 -->
    <div class="section" v-if="userWorkflows.length > 0">
      <div class="section-header">
        <h2>
          <el-icon><Folder /></el-icon>
          我的分析流
        </h2>
        <span class="section-desc">您创建和自定义的分析流程</span>
      </div>

      <el-row :gutter="20">
        <el-col v-for="workflow in userWorkflows" :key="workflow.id" :xs="24" :sm="12" :md="8" :lg="6">
          <el-card class="workflow-card" shadow="hover">
            <template #header>
              <div class="card-header">
                <span class="workflow-name">{{ workflow.name }}</span>
                <el-dropdown trigger="click" @command="handleCommand($event, workflow.id)">
                  <el-button text size="small" @click.stop>
                    <el-icon><MoreFilled /></el-icon>
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="edit">
                        <el-icon><Edit /></el-icon> 编辑
                      </el-dropdown-item>
                      <el-dropdown-item command="execute">
                        <el-icon><VideoPlay /></el-icon> 执行
                      </el-dropdown-item>
                      <el-dropdown-item command="duplicate">
                        <el-icon><DocumentCopy /></el-icon> 复制
                      </el-dropdown-item>
                      <el-dropdown-item command="setDefault" divided>
                        <el-icon><Star /></el-icon> 设为默认
                      </el-dropdown-item>
                      <el-dropdown-item command="delete">
                        <el-icon><Delete /></el-icon> 删除
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
            </template>
            <p class="workflow-desc">{{ workflow.description || '暂无描述' }}</p>
            <div class="workflow-meta">
              <span class="version">v{{ workflow.version }}</span>
              <span class="date">{{ formatDate(workflow.updated_at) }}</span>
            </div>
            <div class="card-actions">
              <el-button size="small" type="primary" @click="openWorkflow(workflow.id)">
                编辑
              </el-button>
              <el-button size="small" @click="executeWorkflow(workflow.id)">
                执行
              </el-button>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 空状态 - 仅当没有用户工作流且模板加载完成时显示引导 -->
    <div class="empty-guide" v-if="!loading && userWorkflows.length === 0 && templates.length > 0">
      <el-divider>
        <el-icon><ArrowDown /></el-icon>
      </el-divider>
      <div class="guide-content">
        <el-icon class="guide-icon"><Pointer /></el-icon>
        <p>选择上方的系统模板开始创建您的第一个分析流</p>
      </div>
    </div>

    <!-- 创建空白工作流对话框 -->
    <el-dialog v-model="showCreateDialog" title="创建空白分析流" width="500px">
      <el-form :model="newWorkflow" label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="newWorkflow.name" placeholder="输入分析流名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="newWorkflow.description" type="textarea" :rows="3" placeholder="描述分析流的用途" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createWorkflow">创建</el-button>
      </template>
    </el-dialog>

    <!-- 模板预览对话框 -->
    <el-dialog v-model="showPreviewDialog" :title="currentPreviewTemplate?.name || '模板预览'" width="800px">
      <div class="preview-content" v-if="currentPreviewTemplate">
        <p class="preview-desc">{{ currentPreviewTemplate.description }}</p>

        <el-divider content-position="left">流程说明</el-divider>
        <div class="preview-flow">
          <div class="flow-step" v-for="(step, index) in getFlowSteps(currentPreviewTemplate)" :key="index">
            <div class="step-number">{{ index + 1 }}</div>
            <div class="step-content">
              <h4>{{ step.title }}</h4>
              <p>{{ step.desc }}</p>
              <div class="step-agents">
                <el-tag v-for="agent in step.agents" :key="agent" size="small" type="info">
                  {{ agent }}
                </el-tag>
              </div>
            </div>
          </div>
        </div>

        <el-divider content-position="left">节点详情</el-divider>
        <el-table :data="currentPreviewTemplate.nodes?.filter(n => n.type !== 'start' && n.type !== 'end')" size="small">
          <el-table-column prop="label" label="名称" />
          <el-table-column prop="type" label="类型">
            <template #default="{ row }">
              <el-tag :type="getNodeTypeTag(row.type)" size="small">{{ getNodeTypeName(row.type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="agent_id" label="智能体ID" />
        </el-table>
      </div>
      <template #footer>
        <el-button @click="showPreviewDialog = false">关闭</el-button>
        <el-button type="primary" @click="useTemplate(currentPreviewTemplate!)">使用此模板</el-button>
      </template>
    </el-dialog>

    <!-- 模板命名对话框 -->
    <el-dialog v-model="showNameDialog" title="命名您的分析流" width="400px">
      <el-form>
        <el-form-item label="名称" required>
          <el-input v-model="templateName" placeholder="输入分析流名称" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showNameDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmUseTemplate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Plus, SetUp, Promotion, Folder, User, Connection, Timer, View,
  DocumentCopy, Edit, Delete, VideoPlay, MoreFilled, ArrowDown, Pointer, Star
} from '@element-plus/icons-vue'
import { workflowApi, type WorkflowSummary, type WorkflowDefinition } from '@/api/workflow'
import dayjs from 'dayjs'

const router = useRouter()

// 状态
const loading = ref(false)
const workflows = ref<WorkflowSummary[]>([])
const templates = ref<WorkflowDefinition[]>([])
const sortedTemplates = computed(() => {
  // 🔥 只显示v2.0的流程，屏蔽非v2.0的流程
  const v2Templates = templates.value.filter((t: WorkflowDefinition) => {
    const name = (t.name || '').toLowerCase()
    const id = (t.id || '').toLowerCase()
    const tags = Array.isArray(t.tags) ? t.tags : []
    const version = String(t.version || '').toLowerCase()
    
    // 🔥 明确排除的旧版流程ID（即使名称可能包含v2，但ID明确不是v2）
    const excludedIds = [
      'default_analysis',      // TradingAgents 完整分析流（v1.0）
      'simple_analysis',       // 简单分析流（v1.0）
      'trade_review',          // 交易复盘（v1.0，非v2）
      'position_analysis'      // 持仓分析（v1.0，非v2）
    ]
    if (excludedIds.includes(id)) {
      return false
    }
    
    // 🔥 明确排除名称包含 "TradingAgents" 但不包含 "v2" 的流程
    if (name.includes('tradingagents') && !name.includes('v2')) {
      return false
    }
    
    // ✅ 1. ID 明确包含 _v2 或 v2_（最可靠的判断方式）
    if (id.includes('_v2') || id.startsWith('v2_')) {
      return true
    }
    
    // ✅ 2. ID 是 v2_stock_analysis（v2.0完整分析流）
    if (id === 'v2_stock_analysis') {
      return true
    }
    
    // ✅ 3. 名称明确包含 "v2.0"（不区分大小写）
    if (name.includes('v2.0')) {
      return true
    }
    
    // ✅ 4. tags 包含 v2 相关标签
    if (tags.some(tag => String(tag).toLowerCase().includes('v2'))) {
      return true
    }
    
    // ✅ 5. version 字段是 v2.0 相关（version 以 2. 开头）
    if (version.startsWith('2.')) {
      return true
    }
    
    // ❌ 默认：过滤掉非v2.0的流程
    return false
  })
  
  // 对v2.0流程进行排序
  const score = (t: WorkflowDefinition) => {
    const v = t.version
    let major = 0
    if (typeof v === 'string') {
      const m = parseInt(v.split('.')[0] || '0', 10)
      if (!Number.isNaN(m)) major = m
    } else if (typeof v === 'number') {
      major = v
    }
    const tags = Array.isArray(t.tags) ? t.tags : []
    const isV2Tag = tags.some(tag => String(tag).toLowerCase().includes('v2'))
    return (isV2Tag ? 1 : 0) * 100 + major
  }
  
  v2Templates.sort((a, b) => score(b) - score(a))
  return v2Templates
})
const showCreateDialog = ref(false)
const showPreviewDialog = ref(false)
const showNameDialog = ref(false)
const currentPreviewTemplate = ref<WorkflowDefinition | null>(null)
const selectedTemplateForUse = ref<WorkflowDefinition | null>(null)
const templateName = ref('')
const newWorkflow = ref({
  name: '',
  description: ''
})

// 计算属性：用户创建的工作流（非模板）
const userWorkflows = computed(() => workflows.value.filter(w => !w.is_template))

// 加载数据
const loadWorkflows = async () => {
  loading.value = true
  try {
    workflows.value = await workflowApi.listAll()
  } catch (error) {
    console.error('加载工作流失败:', error)
  } finally {
    loading.value = false
  }
}

const loadTemplates = async () => {
  try {
    templates.value = await workflowApi.getTemplates()
  } catch (error) {
    console.error('加载模板失败:', error)
  }
}

// 辅助方法：获取节点图标
const getTemplateIcon = (id: string) => {
  if (id === 'default_analysis') return 'Promotion'
  if (id === 'simple_analysis') return 'SetUp'
  if (id === 'trade_review') return 'DocumentCopy'
  if (id === 'trade_review_v2') return 'DocumentCopy'
  if (id === 'position_analysis') return 'SetUp'
  if (id === 'position_analysis_v2') return 'SetUp'
  if (id === 'v2_stock_analysis') return 'TrendCharts'
  return 'SetUp'
}

const getTemplateColor = (id: string) => {
  if (id === 'default_analysis') return '#409EFF'
  if (id === 'simple_analysis') return '#67C23A'
  if (id === 'trade_review') return '#E6A23C'
  if (id === 'trade_review_v2') return '#E6A23C'
  if (id === 'position_analysis') return '#409EFF'
  if (id === 'position_analysis_v2') return '#409EFF'
  if (id === 'v2_stock_analysis') return '#9C27B0'
  return '#409EFF'
}

const getNodeIcon = (node: any) => {
  const icons: Record<string, string> = {
    // v1.0 智能体
    market_analyst: '📈',
    fundamentals_analyst: '📊',
    news_analyst: '📰',
    social_analyst: '💬',
    bull_researcher: '🐂',
    bear_researcher: '🐻',
    research_manager: '👔',
    trader: '💼',
    risk_manager: '⚠️',
    index_analyst: '🌐',
    sector_analyst: '🏭',
    // 交易复盘相关智能体
    timing_analyst: '⏰',
    position_analyst: '📊',
    emotion_analyst: '😊',
    attribution_analyst: '🔍',
    review_manager: '📋',
    // v2.0 智能体（使用相同图标，但可以区分）
    market_analyst_v2: '📈',
    fundamentals_analyst_v2: '📊',
    news_analyst_v2: '📰',
    social_analyst_v2: '💬',
    bull_researcher_v2: '🐂',
    bear_researcher_v2: '🐻',
    research_manager_v2: '👔',
    trader_v2: '💼',
    risk_manager_v2: '⚠️',
    index_analyst_v2: '🌐',
    sector_analyst_v2: '🏭',
    // v2.0 风险分析师
    risky_analyst_v2: '🔥',
    safe_analyst_v2: '🛡️',
    neutral_analyst_v2: '⚖️',
    // v2.0 交易复盘智能体
    timing_analyst_v2: '⏰',
    position_analyst_v2: '📊',
    emotion_analyst_v2: '😊',
    attribution_analyst_v2: '🔍',
    review_manager_v2: '📋',
    // v2.0 持仓分析智能体
    pa_technical_v2: '📈',
    pa_fundamental_v2: '📊',
    pa_risk_v2: '⚠️',
    pa_advisor_v2: '📋'
  }
  return icons[node.agent_id] || '📦'
}

const getAnalystNodes = (template: WorkflowDefinition) =>
  template.nodes?.filter(n => n.type === 'analyst') || []

const getResearcherNodes = (template: WorkflowDefinition) =>
  template.nodes?.filter(n => n.type === 'researcher') || []

const getManagerNodes = (template: WorkflowDefinition) =>
  template.nodes?.filter(n => ['manager', 'trader', 'risk'].includes(n.type)) || []

// 根据分析深度获取辩论轮次（动态计算）
const getDebateRounds = (template: WorkflowDefinition, type: 'debate' | 'risk'): string => {
  const config = template.config || {}
  const depth = config.analysis_depth || 3
  const mapping = config.depth_rounds_mapping as Record<string, { debate: number; risk: number; name: string }> | undefined

  // 如果有映射配置，使用映射
  if (mapping && mapping[String(depth)]) {
    const rounds = type === 'debate' ? mapping[String(depth)].debate : mapping[String(depth)].risk
    const depthName = mapping[String(depth)].name
    return `${rounds}轮 (${depthName})`
  }

  // 默认映射
  const defaultMapping: Record<number, { debate: number; risk: number; name: string }> = {
    1: { debate: 1, risk: 1, name: '快速' },
    2: { debate: 1, risk: 1, name: '基础' },
    3: { debate: 1, risk: 2, name: '标准' },
    4: { debate: 2, risk: 2, name: '深度' },
    5: { debate: 3, risk: 3, name: '全面' },
  }

  const depthConfig = defaultMapping[depth] || defaultMapping[3]
  const rounds = type === 'debate' ? depthConfig.debate : depthConfig.risk
  return `${rounds}轮 (${depthConfig.name})`
}

// 计算辩论轮次
const calcDebateRounds = (depth: number, type: 'debate' | 'risk'): number => {
  const mapping: Record<number, { debate: number; risk: number }> = {
    1: { debate: 1, risk: 1 },
    2: { debate: 1, risk: 1 },
    3: { debate: 1, risk: 2 },
    4: { debate: 2, risk: 2 },
    5: { debate: 3, risk: 3 },
  }
  const config = mapping[depth] || mapping[3]
  return type === 'debate' ? config.debate : config.risk
}

const getFlowSteps = (template: WorkflowDefinition) => {
  const steps = []
  const analysts = getAnalystNodes(template)
  const researchers = getResearcherNodes(template)
  const managers = getManagerNodes(template)
  const hasDebate = template.nodes?.some(n => n.type === 'debate')
  const depth = template.config?.analysis_depth || 3
  const debateRounds = calcDebateRounds(depth, 'debate')
  const riskRounds = calcDebateRounds(depth, 'risk')

  if (analysts.length > 0) {
    steps.push({
      title: '📊 阶段一：多维度并行分析',
      desc: `${analysts.length}个专业分析师同时工作，分别从市场走势、基本面、新闻事件、社交媒体等维度进行独立分析`,
      agents: analysts.map(n => n.label)
    })
  }

  if (researchers.length > 0) {
    steps.push({
      title: hasDebate ? `⚔️ 阶段二：多空辩论（${debateRounds}轮）` : '📝 阶段二：研究分析',
      desc: hasDebate
        ? `看多研究员和看空研究员基于所有分析报告进行${debateRounds}轮辩论。每轮中双方针对对方观点进行反驳和论证，最终形成更全面的投资观点`
        : '研究员综合分析师报告形成投资观点',
      agents: researchers.map(n => n.label)
    })
  }

  // 决策层分开展示
  const researchManager = managers.find(n => n.agent_id === 'research_manager')
  const trader = managers.find(n => n.type === 'trader')
  const riskAnalysts = template.nodes?.filter(n =>
    n.type === 'risk' && ['risky_analyst', 'safe_analyst', 'neutral_analyst'].includes(n.agent_id || '')
  ) || []
  const riskManager = managers.find(n => n.agent_id === 'risk_manager')
  const hasRiskDebate = template.nodes?.some(n => n.id === 'risk_debate')

  if (researchManager) {
    steps.push({
      title: '👔 阶段三：综合评估',
      desc: '研究经理综合看多和看空双方的辩论结果，权衡各方观点，形成最终投资建议',
      agents: [researchManager.label]
    })
  }

  if (trader) {
    steps.push({
      title: '💰 阶段四：交易决策',
      desc: '交易员根据研究经理的建议，制定具体的交易策略，包括买入/卖出信号和目标仓位',
      agents: [trader.label]
    })
  }

  // 风险辩论阶段
  if (riskAnalysts.length > 0 || hasRiskDebate) {
    steps.push({
      title: hasRiskDebate ? `⚔️ 阶段五：风险辩论（${riskRounds}轮）` : '🛡️ 阶段五：风险评估',
      desc: hasRiskDebate
        ? `激进、保守、中性三个风险分析师从不同角度评估交易计划，进行${riskRounds}轮辩论讨论`
        : '风险分析师评估交易方案的风险敞口',
      agents: riskAnalysts.length > 0 ? riskAnalysts.map(n => n.label) : ['风险分析师']
    })
  }

  if (riskManager) {
    steps.push({
      title: '👨‍⚖️ 阶段六：风险裁决',
      desc: '风险经理综合三方风险分析师的辩论观点，做出最终风险调整决策，设置止损止盈',
      agents: [riskManager.label]
    })
  }

  return steps
}

const getNodeTypeName = (type: string) => {
  const names: Record<string, string> = {
    analyst: '分析师',
    researcher: '研究员',
    manager: '经理',
    trader: '交易员',
    risk: '风控',
    parallel: '并行',
    merge: '合并',
    debate: '辩论'
  }
  return names[type] || type
}

const getNodeTypeTag = (type: string): any => {
  const tags: Record<string, string> = {
    analyst: 'primary',
    researcher: 'success',
    manager: 'warning',
    trader: 'info',
    risk: 'danger',
    parallel: '',
    merge: '',
    debate: 'warning'
  }
  return (tags[type] || '') as any
}

// 操作方法
const openWorkflow = (id: string) => {
  router.push(`/workflow/editor/${id}`)
}

const createWorkflow = async () => {
  if (!newWorkflow.value.name) {
    ElMessage.warning('请输入分析流名称')
    return
  }

  try {
    const result = await workflowApi.create({
      name: newWorkflow.value.name,
      description: newWorkflow.value.description,
      tags: ['custom'],
      version: '1.0.0',
      nodes: [],
      edges: [],
      is_template: false
    })

    if (result.success && result.data) {
      ElMessage.success('创建成功')
      showCreateDialog.value = false
      newWorkflow.value = { name: '', description: '' }
      router.push(`/workflow/editor/${result.data.id}`)
    } else {
      ElMessage.error(result.message || '创建失败')
    }
  } catch (error) {
    console.error('创建失败:', error)
    ElMessage.error('创建失败')
  }
}

const openPreview = (template: WorkflowDefinition) => {
  currentPreviewTemplate.value = template
  showPreviewDialog.value = true
}

const useTemplate = (template: WorkflowDefinition) => {
  selectedTemplateForUse.value = template
  templateName.value = `${template.name} - 我的版本`
  showPreviewDialog.value = false
  showNameDialog.value = true
}

const confirmUseTemplate = async () => {
  if (!selectedTemplateForUse.value || !templateName.value) return

  try {
    const result = await workflowApi.createFromTemplate(
      selectedTemplateForUse.value.id,
      templateName.value
    )

    if (result.success && result.data) {
      ElMessage.success('创建成功')
      showNameDialog.value = false
      router.push(`/workflow/editor/${result.data.id}`)
    } else {
      ElMessage.error(result.message || '创建失败')
    }
  } catch (error) {
    console.error('创建失败:', error)
    ElMessage.error('创建失败')
  }
}

const executeWorkflow = (id: string) => {
  router.push(`/workflow/execute/${id}`)
}

const handleCommand = async (command: string, id: string) => {
  switch (command) {
    case 'edit':
      openWorkflow(id)
      break
    case 'execute':
      executeWorkflow(id)
      break
    case 'duplicate':
      await duplicateWorkflow(id)
      break
    case 'setDefault':
      await setAsDefault(id)
      break
    case 'delete':
      await deleteWorkflow(id)
      break
  }
}

const deleteWorkflow = async (id: string) => {
  try {
    const result = await workflowApi.delete(id)
    if (result.success) {
      ElMessage.success('删除成功')
      loadWorkflows()
    } else {
      ElMessage.error(result.error || '删除失败')
    }
  } catch (error) {
    console.error('删除失败:', error)
    ElMessage.error('删除失败')
  }
}

const duplicateWorkflow = async (id: string) => {
  try {
    const workflow = workflows.value.find(w => w.id === id)
    if (!workflow) return

    const result = await workflowApi.duplicate(id, `${workflow.name} - 副本`)
    if (result.success && result.data) {
      ElMessage.success('复制成功')
      loadWorkflows()
      // 可选：自动跳转到编辑页面
      router.push(`/workflow/editor/${result.data.id}`)
    } else {
      ElMessage.error(result.message || '复制失败')
    }
  } catch (error) {
    console.error('复制失败:', error)
    ElMessage.error('复制失败')
  }
}

const setAsDefault = async (id: string) => {
  try {
    const result = await workflowApi.setAsDefault(id)
    if (result.success) {
      ElMessage.success('已设为默认分析流，下次执行分析时将使用此流程')
      loadWorkflows()
    } else {
      ElMessage.error(result.message || '设置失败')
    }
  } catch (error) {
    console.error('设置默认失败:', error)
    ElMessage.error('设置默认失败')
  }
}

const formatDate = (date?: string) => {
  if (!date) return '-'
  return dayjs(date).format('YYYY-MM-DD HH:mm')
}

// 初始化
onMounted(() => {
  loadWorkflows()
  loadTemplates()
})
</script>

<style scoped lang="scss">
.workflow-page {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--el-border-color-lighter);

  .header-left {
    display: flex;
    align-items: baseline;
    gap: 12px;
  }

  h1 {
    margin: 0;
    font-size: 26px;
    display: flex;
    align-items: center;
    gap: 8px;

    .header-icon {
      color: var(--el-color-primary);
    }
  }

  .subtitle {
    color: var(--el-text-color-secondary);
    font-size: 14px;
  }
}

// 区块
.section {
  margin-bottom: 40px;

  .section-header {
    margin-bottom: 20px;

    h2 {
      margin: 0 0 4px;
      font-size: 18px;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .section-desc {
      color: var(--el-text-color-secondary);
      font-size: 14px;
    }
  }
}

// 模板卡片
.template-card {
  margin-bottom: 20px;
  transition: all 0.3s;

  &:hover {
    box-shadow: var(--el-box-shadow-light);
    transform: translateY(-2px);
  }

  .template-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 16px;

    .template-title {
      display: flex;
      align-items: center;
      gap: 12px;

      .template-icon {
        font-size: 32px;
      }

      h3 {
        margin: 0 0 4px;
        font-size: 18px;
      }
    }

    .template-actions {
      display: flex;
      gap: 8px;
    }
  }

  .template-desc {
    color: var(--el-text-color-secondary);
    font-size: 14px;
    margin: 0 0 16px;
    line-height: 1.6;
  }

  // 流程预览图
  .flow-preview {
    background: var(--el-fill-color-lighter);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 16px;

    .flow-diagram {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .flow-layer {
      display: flex;
      align-items: center;
      gap: 16px;

      .layer-label {
        width: 70px;
        font-size: 12px;
        color: var(--el-text-color-secondary);
        text-align: right;
        flex-shrink: 0;
      }

      .flow-nodes {
        display: flex;
        gap: 8px;
        flex: 1;
        align-items: center;

        &.parallel {
          position: relative;
          &::before {
            content: '';
            position: absolute;
            top: 50%;
            left: 0;
            right: 0;
            height: 2px;
            background: var(--el-border-color);
            z-index: 0;
          }
        }

        &.debate {
          justify-content: center;
        }

        &.decision {
          justify-content: center;
        }
      }

      .flow-node {
        width: 40px;
        height: 40px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 20px;
        cursor: default;
        position: relative;
        z-index: 1;

        &.analyst {
          background: var(--el-color-primary-light-8);
        }
        &.researcher {
          background: var(--el-color-success-light-8);
          &.bull {
            background: linear-gradient(135deg, #27ae60, #2ecc71);
          }
          &.bear {
            background: linear-gradient(135deg, #c0392b, #e74c3c);
          }
        }
        &.manager {
          background: var(--el-color-warning-light-8);
        }
        &.trader {
          background: linear-gradient(135deg, #f39c12, #f1c40f);
        }
        &.risk {
          &.risky {
            background: linear-gradient(135deg, #e74c3c, #c0392b);
          }
          &.safe {
            background: linear-gradient(135deg, #27ae60, #2ecc71);
          }
          &.neutral {
            background: linear-gradient(135deg, #3498db, #2980b9);
          }
        }
      }

      .flow-arrow {
        color: var(--el-text-color-secondary);
        font-size: 16px;
      }

      .debate-indicator {
        display: flex;
        flex-direction: column;
        align-items: center;
        margin: 0 12px;

        .debate-arrows {
          font-size: 24px;
          animation: pulse 1.5s infinite;
        }

        .debate-rounds {
          font-size: 10px;
          color: var(--el-text-color-secondary);
          background: var(--el-fill-color);
          padding: 2px 6px;
          border-radius: 10px;
          margin-top: 4px;
        }
      }
    }
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }

  .template-stats {
    display: flex;
    gap: 24px;

    .stat {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 13px;
      color: var(--el-text-color-secondary);
    }
  }
}

// 用户工作流卡片
.workflow-card {
  margin-bottom: 20px;
  transition: all 0.2s;

  &:hover {
    transform: translateY(-2px);
    box-shadow: var(--el-box-shadow-light);
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .workflow-name {
    font-weight: 600;
    font-size: 16px;
  }

  .workflow-desc {
    color: var(--el-text-color-secondary);
    font-size: 14px;
    margin: 8px 0;
    height: 40px;
    overflow: hidden;
    text-overflow: ellipsis;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
  }

  .workflow-meta {
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    color: var(--el-text-color-secondary);
    margin: 12px 0;
  }

  .card-actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
  }
}

// 空状态引导
.empty-guide {
  text-align: center;
  padding: 20px 0;

  .guide-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    color: var(--el-text-color-secondary);

    .guide-icon {
      font-size: 32px;
      animation: bounce 2s infinite;
    }
  }
}

@keyframes bounce {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-10px); }
}

// 预览对话框
.preview-content {
  .preview-desc {
    color: var(--el-text-color-secondary);
    margin-bottom: 16px;
    line-height: 1.6;
  }

  .preview-flow {
    .flow-step {
      display: flex;
      gap: 16px;
      margin-bottom: 20px;

      .step-number {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background: var(--el-color-primary);
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        flex-shrink: 0;
      }

      .step-content {
        flex: 1;

        h4 {
          margin: 0 0 4px;
          font-size: 15px;
        }

        p {
          margin: 0 0 8px;
          color: var(--el-text-color-secondary);
          font-size: 14px;
        }

        .step-agents {
          display: flex;
          gap: 6px;
          flex-wrap: wrap;
        }
      }
    }
  }
}
</style>
