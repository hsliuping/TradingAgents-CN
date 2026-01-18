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
          <!-- 执行配置 -->
          <el-card class="info-card" shadow="never" style="margin-bottom: 20px;">
            <template #header>
              <div class="card-header">
                <el-icon><Setting /></el-icon>
                <span>执行配置</span>
                <el-button 
                  v-if="!isEditingExecutionConfig" 
                  type="primary" 
                  link 
                  @click="startEditExecutionConfig"
                  style="margin-left: auto;"
                >
                  <el-icon><Edit /></el-icon> 编辑
                </el-button>
                <div v-else class="edit-actions" style="margin-left: auto;">
                  <el-button size="small" @click="cancelEditExecutionConfig">取消</el-button>
                  <el-button size="small" type="primary" :loading="savingExecutionConfig" @click="saveExecutionConfig">保存</el-button>
                </div>
              </div>
            </template>
            <div class="execution-config-content" v-loading="executionConfigLoading">
              <!-- 查看模式 -->
              <div v-if="!isEditingExecutionConfig">
                <div class="config-item">
                  <span class="label">温度参数:</span>
                  <span class="value">{{ executionConfig.temperature ?? '未设置（使用LLM默认值）' }}</span>
                  <el-tag v-if="executionConfig.temperature !== undefined" size="small" type="info" style="margin-left: 8px;">
                    {{ getTemperatureRecommendation(executionConfig.temperature) }}
                  </el-tag>
                </div>
                <div class="config-item">
                  <span class="label">最大迭代次数:</span>
                  <span class="value">{{ executionConfig.max_iterations ?? '未设置（使用默认值：3）' }}</span>
                </div>
                <div class="config-item">
                  <span class="label">超时时间（秒）:</span>
                  <span class="value">{{ executionConfig.timeout ?? '未设置（使用默认值：120）' }}</span>
                </div>
              </div>

              <!-- 编辑模式 -->
              <div v-else>
                <div class="edit-section">
                  <el-form :model="editingExecutionConfig" label-width="140px">
                    <el-form-item label="温度参数">
                      <el-input-number
                        v-model="editingExecutionConfig.temperature"
                        :min="0"
                        :max="2"
                        :step="0.1"
                        :precision="1"
                        placeholder="留空使用LLM默认值"
                        style="width: 100%"
                      />
                      <div class="form-help">
                        <el-text size="small" type="info">
                          推荐值：辩论Agent 0.6，数值计算Agent 0.1，其他Agent 0.2
                        </el-text>
                      </div>
                    </el-form-item>
                    <el-form-item label="最大迭代次数">
                      <el-input-number
                        v-model="editingExecutionConfig.max_iterations"
                        :min="1"
                        :max="10"
                        placeholder="留空使用默认值：3"
                        style="width: 100%"
                      />
                    </el-form-item>
                    <el-form-item label="超时时间（秒）">
                      <el-input-number
                        v-model="editingExecutionConfig.timeout"
                        :min="30"
                        :max="600"
                        placeholder="留空使用默认值：120"
                        style="width: 100%"
                      />
                    </el-form-item>
                  </el-form>
                </div>
              </div>
            </div>
          </el-card>

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

                      <!-- 工具 ID（用于提示词） -->
                      <div class="tool-id">
                        <span class="label">工具ID:</span>
                        <el-tag size="small" type="info" effect="plain">
                          <code>{{ tool.id }}</code>
                        </el-tag>
                        <el-button
                          size="small"
                          text
                          @click="copyToolId(tool.id)"
                          style="margin-left: 4px;"
                        >
                          <el-icon><CopyDocument /></el-icon>
                        </el-button>
                      </div>

                      <!-- 工具参数 -->
                      <div v-if="tool.parameters && tool.parameters.length > 0" class="tool-params">
                        <span class="label">参数:</span>
                        <div class="params-list">
                          <el-tag
                            v-for="param in tool.parameters"
                            :key="param.name"
                            size="small"
                            :type="param.required ? 'warning' : 'info'"
                            effect="plain"
                            style="margin: 2px;"
                          >
                            {{ param.name }}
                            <span v-if="param.required" style="color: #f56c6c;">*</span>
                            <span style="color: #909399;"> : {{ param.type }}</span>
                          </el-tag>
                        </div>
                      </div>
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
                      :label="`${tool.name} (${tool.id})`"
                      :value="tool.id"
                    >
                      <div class="tool-option">
                        <span class="tool-icon">{{ tool.icon }}</span>
                        <span class="tool-name">{{ tool.name }}</span>
                        <span class="tool-id">{{ tool.id }}</span>
                      </div>
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
                    v-if="promptTemplate && canDebugPrompt"
                    type="success"
                    link
                    @click="goToDebugPrompt"
                  >
                    <el-icon><Promotion /></el-icon> 调试
                  </el-button>
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
                  <el-button size="small" :loading="savingPrompt" @click="savePrompt('draft')">保存为草稿</el-button>
                  <el-button size="small" type="primary" :loading="savingPrompt" @click="savePrompt('active')">发布</el-button>
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
                      <!-- 发布按钮（仅草稿状态且非系统模板） -->
                      <el-button
                        v-if="promptTemplate.status === 'draft' && !promptTemplate.is_system"
                        size="small"
                        type="success"
                        @click="publishTemplate"
                        :loading="publishingTemplate"
                      >
                        <el-icon><Check /></el-icon> 发布
                      </el-button>
                    </div>

                    <!-- 可用变量提示 -->
                    <el-collapse style="margin-top: 12px;">
                      <el-collapse-item name="variables">
                        <template #title>
                          <div style="display: flex; align-items: center; gap: 6px; font-size: 13px;">
                            <el-icon><InfoFilled /></el-icon>
                            <span>可用变量说明</span>
                          </div>
                        </template>
                        <div style="padding: 8px; background: #f5f7fa; border-radius: 4px;">
                          <el-descriptions :column="2" border size="small">
                            <el-descriptions-item label="ticker" label-class-name="var-label">
                              股票代码（来自输入参数）
                            </el-descriptions-item>
                            <el-descriptions-item label="company_name" label-class-name="var-label">
                              公司名称（系统自动获取）
                            </el-descriptions-item>
                            <el-descriptions-item label="market_name" label-class-name="var-label">
                              市场名称（系统自动识别）
                            </el-descriptions-item>
                            <el-descriptions-item label="current_date" label-class-name="var-label">
                              当前分析日期
                            </el-descriptions-item>
                            <el-descriptions-item label="currency_name" label-class-name="var-label">
                              货币名称（如：人民币）
                            </el-descriptions-item>
                            <el-descriptions-item label="currency_symbol" label-class-name="var-label">
                              货币符号（如：¥）
                            </el-descriptions-item>
                            <el-descriptions-item label="tool_names" label-class-name="var-label">
                              可用工具列表
                            </el-descriptions-item>
                            <el-descriptions-item label="start_date" label-class-name="var-label">
                              开始日期（通常是1年前）
                            </el-descriptions-item>
                          </el-descriptions>
                          <div style="margin-top: 8px; padding: 8px; background: white; border-radius: 4px; font-size: 12px; color: #606266;">
                            <el-icon style="color: #409eff;"><InfoFilled /></el-icon>
                            这些变量会在运行时自动从工作流状态中提取和计算，无需用户手动提供
                          </div>
                        </div>
                      </el-collapse-item>
                    </el-collapse>

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
                      <el-tab-pane label="约束条件" name="constraints">
                        <div class="prompt-text">{{ promptTemplate.content?.constraints || '无' }}</div>
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

                <el-form label-position="top">
                  <el-form-item label="系统提示词">
                    <el-input
                      v-model="editingPrompt.system_prompt"
                      type="textarea"
                      :rows="6"
                      placeholder="请输入系统提示词，可使用上方的变量，如：你是{company_name}的分析师..."
                    />
                  </el-form-item>
                  <el-form-item label="用户提示词">
                    <el-input
                      v-model="editingPrompt.user_prompt"
                      type="textarea"
                      :rows="6"
                      placeholder="请输入用户提示词，可使用上方的变量"
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
                  <el-form-item label="约束条件">
                    <el-input
                      v-model="editingPrompt.constraints"
                      type="textarea"
                      :rows="4"
                      placeholder="请输入约束条件"
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
import { ArrowLeft, InfoFilled, Connection, Tools, Edit, Document, CopyDocument, Check, Promotion, Setting } from '@element-plus/icons-vue'
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

// 执行配置
const executionConfigLoading = ref(false)
const isEditingExecutionConfig = ref(false)
const executionConfig = ref<{ temperature?: number; max_iterations?: number; timeout?: number }>({})
const editingExecutionConfig = ref<{ temperature?: number; max_iterations?: number; timeout?: number }>({})
const savingExecutionConfig = ref(false)

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
  user_prompt: '',  // 🔥 新增：用户提示词
  tool_guidance: '',
  analysis_requirements: '',
  output_format: '',
  constraints: '',  // 🔥 新增：约束条件
  remark: ''
})

// 提示词模板列表和选择
const promptTemplates = ref<any[]>([]) // 所有可用的模板（3个系统模板）
const selectedTemplateId = ref<string>('') // 当前选中的模板 ID
const activeTemplateId = ref<string>('') // 用户设置的当前生效模板 ID
const publishingTemplate = ref(false) // 发布模板中

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

// 判断是否可以调试提示词（仅单股分析的六个分析师）
const canDebugPrompt = computed(() => {
  if (!agent.value?.id) return false

  // 单股分析的六个 v2.0 分析师
  const singleStockAnalysts = [
    'fundamentals_analyst_v2',  // 基本面分析师
    'market_analyst_v2',         // 市场分析师
    'news_analyst_v2',           // 新闻分析师
    'social_analyst_v2',         // 社交媒体分析师
    'sector_analyst_v2',         // 板块分析师
    'index_analyst_v2'           // 大盘分析师
  ]

  return singleStockAnalysts.includes(agent.value.id)
})

// 跳转到提示词调试页面
const goToDebugPrompt = () => {
  if (!agent.value?.id || !promptTemplate.value?.id) {
    ElMessage.warning('缺少必要信息')
    return
  }

  // 构建调试页面 URL
  // 格式: /settings/templates/debug?analyst_type=fundamentals_analyst_v2&template_id=xxx&symbol=&agent_type=analysts_v2
  const params = new URLSearchParams({
    analyst_type: agent.value.id,
    template_id: promptTemplate.value.id,
    symbol: '',
    agent_type: inferAgentType(agent.value.id)
  })

  const debugUrl = `/settings/templates/debug?${params.toString()}`
  router.push(debugUrl)
}

// 复制工具 ID
const copyToolId = async (toolId: string) => {
  try {
    await navigator.clipboard.writeText(toolId)
    ElMessage.success('工具 ID 已复制到剪贴板')
  } catch (error) {
    ElMessage.error('复制失败，请手动复制')
  }
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

    // 并行加载工具配置、执行配置和提示词模板
    await Promise.all([
      loadAgentTools(agentId),
      loadExecutionConfig(agentId),
      loadPromptTemplates(agentId)
    ])
  } catch (error: any) {
    console.error('加载 Agent 详情失败:', error)
    ElMessage.error(error.message || '加载失败')
  } finally {
    loading.value = false
  }
}

// 加载执行配置
const loadExecutionConfig = async (agentId: string) => {
  executionConfigLoading.value = true
  try {
    const config = await agentApi.getExecutionConfig(agentId)
    executionConfig.value = config || {}
  } catch (error: any) {
    console.error('加载执行配置失败:', error)
  } finally {
    executionConfigLoading.value = false
  }
}

// 开始编辑执行配置
const startEditExecutionConfig = () => {
  editingExecutionConfig.value = {
    temperature: executionConfig.value.temperature,
    max_iterations: executionConfig.value.max_iterations,
    timeout: executionConfig.value.timeout
  }
  isEditingExecutionConfig.value = true
}

// 取消编辑执行配置
const cancelEditExecutionConfig = () => {
  isEditingExecutionConfig.value = false
  editingExecutionConfig.value = {}
}

// 保存执行配置
const saveExecutionConfig = async () => {
  if (!agent.value) return

  savingExecutionConfig.value = true
  try {
    // 移除 undefined 值
    const configToSave: any = {}
    if (editingExecutionConfig.value.temperature !== undefined && editingExecutionConfig.value.temperature !== null) {
      configToSave.temperature = editingExecutionConfig.value.temperature
    }
    if (editingExecutionConfig.value.max_iterations !== undefined && editingExecutionConfig.value.max_iterations !== null) {
      configToSave.max_iterations = editingExecutionConfig.value.max_iterations
    }
    if (editingExecutionConfig.value.timeout !== undefined && editingExecutionConfig.value.timeout !== null) {
      configToSave.timeout = editingExecutionConfig.value.timeout
    }

    await agentApi.updateExecutionConfig(agent.value.id, configToSave)

    ElMessage.success('保存成功')
    isEditingExecutionConfig.value = false
    await loadExecutionConfig(agent.value.id)
  } catch (error: any) {
    console.error('保存执行配置失败:', error)
    ElMessage.error(error.message || '保存失败')
  } finally {
    savingExecutionConfig.value = false
  }
}

// 获取温度推荐说明
const getTemperatureRecommendation = (temperature: number): string => {
  if (temperature >= 0.5) return '辩论模式'
  if (temperature <= 0.15) return '高精度模式'
  return '标准模式'
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
    user_prompt: content.user_prompt || '',  // 🔥 新增：用户提示词
    tool_guidance: content.tool_guidance || '',
    analysis_requirements: content.analysis_requirements || '',
    output_format: content.output_format || '',
    constraints: content.constraints || '',  // 🔥 新增：约束条件
    remark: promptTemplate.value.remark || ''
  }
  isEditingPrompt.value = true
}

// 取消编辑提示词
const cancelEditPrompt = () => {
  isEditingPrompt.value = false
  editingPrompt.value = {
    system_prompt: '',
    user_prompt: '',  // 🔥 新增：用户提示词
    tool_guidance: '',
    analysis_requirements: '',
    output_format: '',
    constraints: '',  // 🔥 新增：约束条件
    remark: ''
  }
}

// 发布模板（从草稿变为已发布）
const publishTemplate = async () => {
  if (!promptTemplate.value || !agent.value) return

  publishingTemplate.value = true
  try {
    const { useAuthStore } = await import('@/stores/auth')
    const userId = useAuthStore().user?.id

    // 更新状态为 active
    const updateData = {
      status: 'active'
    }

    // 调用更新 API（传递 user_id）
    const updateResponse = await TemplatesApi.update(promptTemplate.value.id, updateData, userId)

    if (!updateResponse.success) {
      throw new Error(updateResponse.message || '发布失败')
    }

    ElMessage.success('发布成功')

    // 重新加载模板列表
    await loadPromptTemplates(agent.value.id)
  } catch (error: any) {
    console.error('发布模板失败:', error)
    ElMessage.error(error.message || '发布失败')
  } finally {
    publishingTemplate.value = false
  }
}

// 保存提示词
const savePrompt = async (status: 'draft' | 'active' = 'active') => {
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
        user_prompt: editingPrompt.value.user_prompt || '',  // 🔥 新增：用户提示词
        tool_guidance: editingPrompt.value.tool_guidance,
        analysis_requirements: editingPrompt.value.analysis_requirements,
        output_format: editingPrompt.value.output_format,
        constraints: editingPrompt.value.constraints || ''  // 🔥 新增：约束条件
      },
      remark: editingPrompt.value.remark,
      status: status  // 设置状态
    }

    // 调用更新 API（传递 user_id）
    const updateResponse = await TemplatesApi.update(templateId, updateData, userId)

    if (!updateResponse.success) {
      throw new Error(updateResponse.message || '更新失败')
    }

    const statusText = status === 'draft' ? '草稿已保存' : '发布成功'
    ElMessage.success(statusText)
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

            .tool-id {
              margin-top: 8px;
              display: flex;
              align-items: center;
              gap: 4px;
              font-size: 12px;

              .label {
                color: #909399;
                font-weight: 500;
              }

              code {
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                padding: 2px 6px;
                background: #f5f7fa;
                border-radius: 3px;
              }
            }

            .tool-params {
              margin-top: 8px;
              font-size: 12px;

              .label {
                color: #909399;
                font-weight: 500;
                display: block;
                margin-bottom: 4px;
              }

              .params-list {
                display: flex;
                flex-wrap: wrap;
                gap: 4px;
              }
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

      // 工具下拉选项样式
      .tool-option {
        display: flex;
        align-items: center;
        gap: 8px;
        width: 100%;

        .tool-icon {
          flex-shrink: 0;
          font-size: 14px;
        }

        .tool-name {
          flex-shrink: 0;
          color: #303133;
        }

        .tool-id {
          margin-left: auto;
          font-size: 12px;
          color: #909399;
          font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
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

            code {
              font-family: 'Consolas', 'Monaco', monospace;
              font-size: 12px;
              padding: 2px 6px;
              background: #e6f7ff;
              color: #1890ff;
              border-radius: 3px;
              font-weight: 500;
            }
          }

          // 变量标签样式
          :deep(.var-label) {
            font-family: 'Consolas', 'Monaco', monospace !important;
            font-size: 12px !important;
            color: #1890ff !important;
            font-weight: 500 !important;
            background: #e6f7ff !important;
            padding: 2px 6px !important;
            border-radius: 3px !important;
          }
        }
      }
    }
  }
}
</style>

