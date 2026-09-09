<template>
  <div class="prompt-preview-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <h1>
          <el-icon class="header-icon"><View /></el-icon>
          Prompt 实时预览
        </h1>
        <span class="subtitle">预览分层组装后的最终 Prompt，查看各段来源和能力缺口</span>
      </div>
    </div>

    <!-- 配置区域 -->
    <el-card class="config-card" shadow="never">
      <template #header>
        <span class="card-title">组装配置</span>
      </template>
      
      <el-form :model="form" label-width="100px" class="config-form">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="Agent 类型">
              <el-select
                v-model="form.agent_type"
                placeholder="选择 Agent 类型"
                @change="handleAgentTypeChange"
                style="width: 100%"
              >
                <el-option
                  v-for="type in agentTypes"
                  :key="type"
                  :label="labelAgentType(type)"
                  :value="type"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="Agent 名称">
              <el-select
                v-model="form.agent_name"
                placeholder="选择 Agent 名称"
                :disabled="!form.agent_type"
                style="width: 100%"
              >
                <el-option
                  v-for="agent in filteredAgents"
                  :key="agent.agent_name"
                  :label="labelAgentName(agent.agent_name)"
                  :value="agent.agent_name"
                >
                  <span>{{ labelAgentName(agent.agent_name) }}</span>
                  <span style="color: var(--el-text-color-secondary); font-size: 12px; margin-left: 8px">
                    ({{ agent.template_count }} 个模板)
                  </span>
                </el-option>
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="分析场景">
              <el-radio-group v-model="form.analysis_type">
                <el-radio-button value="general">通用</el-radio-button>
                <el-radio-button value="industry">行业</el-radio-button>
                <el-radio-button value="stock">个股</el-radio-button>
              </el-radio-group>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="行业" v-if="form.analysis_type !== 'general'">
              <el-select
                v-model="form.industry"
                placeholder="选择行业"
                filterable
                clearable
                style="width: 100%"
              >
                <el-option
                  v-for="ind in industries"
                  :key="ind.industry"
                  :label="ind.display_name"
                  :value="ind.industry"
                >
                  <span>{{ ind.display_name }}</span>
                  <span style="color: var(--el-text-color-secondary); font-size: 12px; margin-left: 8px">
                    {{ ind.analysis_focus }}
                  </span>
                </el-option>
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="股票代码" v-if="form.analysis_type === 'stock'">
              <el-input v-model="form.stock_symbol" placeholder="如：600519" clearable />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="16">
            <el-form-item label="任务描述">
              <el-input
                v-model="form.task_description"
                type="textarea"
                :rows="2"
                placeholder="输入当前分析任务描述（可选）"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="能力块">
              <el-switch v-model="form.include_capability" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item>
          <el-button type="primary" :loading="loading" @click="handlePreview">
            <el-icon><View /></el-icon>
            生成预览
          </el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 结果区域 -->
    <div v-if="result" class="result-area">
      <!-- 能力缺口提醒 -->
      <el-alert
        v-if="result.capability_gaps.length > 0"
        type="warning"
        :closable="false"
        class="gaps-alert"
      >
        <template #title>
          <span class="alert-title">能力缺口提醒</span>
        </template>
        <ul class="gaps-list">
          <li v-for="(gap, idx) in result.capability_gaps" :key="idx">{{ gap }}</li>
        </ul>
      </el-alert>

      <!-- 画像使用情况 -->
      <el-card v-if="result.profile_used" class="profile-card" shadow="never">
        <template #header>
          <span class="card-title">画像使用情况</span>
        </template>
        <el-descriptions :column="4" border size="small">
          <el-descriptions-item label="行业">
            {{ result.profile_used.industry || '-' }}
            <el-tag v-if="result.profile_used.industry_profile_found" type="success" size="small" style="margin-left: 4px">已找到</el-tag>
            <el-tag v-else-if="result.profile_used.industry" type="danger" size="small" style="margin-left: 4px">未找到</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="股票">
            {{ result.profile_used.stock_symbol || '-' }}
            <el-tag v-if="result.profile_used.stock_profile_found" type="success" size="small" style="margin-left: 4px">已找到</el-tag>
            <el-tag v-else-if="result.profile_used.stock_symbol" type="danger" size="small" style="margin-left: 4px">未找到</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="模板 ID">{{ result.template_id || '-' }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- Prompt 预览 -->
      <el-card class="prompt-card" shadow="never">
        <template #header>
          <div class="prompt-header">
            <span class="card-title">最终 Prompt ({{ result.final_prompt.length }} 字符)</span>
            <el-button type="primary" link @click="copyPrompt">
              <el-icon><CopyDocument /></el-icon>
              复制
            </el-button>
          </div>
        </template>
        <el-tabs v-model="activeTab">
          <el-tab-pane label="完整内容" name="full">
            <div class="prompt-content">
              <pre>{{ result.final_prompt }}</pre>
            </div>
          </el-tab-pane>
          <el-tab-pane label="分段查看" name="sections">
            <div class="sections-view">
              <div v-for="(content, key) in result.sections" :key="key" class="section-item">
                <div class="section-header">
                  <span class="section-name">{{ key }}</span>
                  <el-tag size="small" type="info">{{ result.sources[key] || '未知来源' }}</el-tag>
                </div>
                <div class="section-content">
                  <pre>{{ content || '(空)' }}</pre>
                </div>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { View, CopyDocument } from '@element-plus/icons-vue'
import { promptPreviewApi, type PromptPreviewResponse, type IndustryItem, type AgentItem } from '@/api/promptPreview'
import { labelAgentType, labelAgentName, filterV2AgentTypes } from '@/constants/agentLabels'

// 表单状态
const form = reactive({
  agent_type: '',
  agent_name: '',
  analysis_type: 'general' as 'general' | 'industry' | 'stock',
  industry: '',
  stock_symbol: '',
  task_description: '',
  include_capability: true,
})

// 数据状态
const loading = ref(false)
const industries = ref<IndustryItem[]>([])
const agents = ref<AgentItem[]>([])
const result = ref<PromptPreviewResponse | null>(null)
const activeTab = ref('full')

// 计算属性
const agentTypes = computed(() => {
  const types = new Set(agents.value.map((a) => a.agent_type))
  return filterV2AgentTypes(Array.from(types)).sort()
})

const filteredAgents = computed(() => {
  if (!form.agent_type) return []
  return agents.value.filter(a => a.agent_type === form.agent_type)
})

// 加载数据
const loadIndustries = async () => {
  try {
    const res = await promptPreviewApi.listIndustries()
    industries.value = res.industries || []
  } catch (e) {
    console.error('加载行业列表失败', e)
  }
}

const loadAgents = async () => {
  try {
    const res = await promptPreviewApi.listAgents()
    agents.value = res.agents || []
  } catch (e) {
    console.error('加载 Agent 列表失败', e)
  }
}

// 事件处理
const handleAgentTypeChange = () => {
  form.agent_name = ''
}

const handlePreview = async () => {
  if (!form.agent_type || !form.agent_name) {
    ElMessage.warning('请选择 Agent 类型和名称')
    return
  }

  if (form.analysis_type === 'industry' && !form.industry) {
    ElMessage.warning('请选择行业')
    return
  }

  if (form.analysis_type === 'stock' && !form.stock_symbol) {
    ElMessage.warning('请输入股票代码')
    return
  }

  loading.value = true
  try {
    result.value = await promptPreviewApi.assemble({
      agent_type: form.agent_type,
      agent_name: form.agent_name,
      analysis_type: form.analysis_type,
      industry: form.industry || undefined,
      stock_symbol: form.stock_symbol || undefined,
      task_description: form.task_description || undefined,
      include_capability: form.include_capability,
    })
    ElMessage.success('Prompt 组装完成')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '组装失败')
  } finally {
    loading.value = false
  }
}

const handleReset = () => {
  form.agent_type = ''
  form.agent_name = ''
  form.analysis_type = 'general'
  form.industry = ''
  form.stock_symbol = ''
  form.task_description = ''
  form.include_capability = true
  result.value = null
}

const copyPrompt = async () => {
  if (!result.value) return
  try {
    await navigator.clipboard.writeText(result.value.final_prompt)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败')
  }
}

// 初始化
onMounted(() => {
  loadIndustries()
  loadAgents()
})
</script>

<style scoped>
.prompt-preview-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
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

.config-card,
.profile-card,
.prompt-card {
  margin-bottom: 16px;
}

.card-title {
  font-weight: 500;
  font-size: 15px;
}

.config-form {
  margin-top: 12px;
}

.gaps-alert {
  margin-bottom: 16px;
}

.alert-title {
  font-weight: 500;
}

.gaps-list {
  margin: 8px 0 0 0;
  padding-left: 20px;
}

.gaps-list li {
  margin-bottom: 4px;
  font-size: 13px;
}

.prompt-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.prompt-content {
  background: var(--el-fill-color-light);
  border-radius: 4px;
  padding: 16px;
  max-height: 600px;
  overflow: auto;
}

.prompt-content pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 13px;
  line-height: 1.6;
}

.sections-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-item {
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  overflow: hidden;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: var(--el-fill-color-light);
  border-bottom: 1px solid var(--el-border-color);
}

.section-name {
  font-weight: 500;
  font-size: 14px;
}

.section-content {
  padding: 12px 16px;
  max-height: 300px;
  overflow: auto;
}

.section-content pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 12px;
  line-height: 1.5;
}
</style>