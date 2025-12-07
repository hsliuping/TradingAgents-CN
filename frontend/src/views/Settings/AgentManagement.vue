<template>
  <div class="agent-page">
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">智能体管理</h1>
        <el-tag type="info" size="small" effect="plain" class="count-tag">{{ totalAgents }} 个智能体</el-tag>
      </div>
      <div class="header-right">
        <el-button class="icon-btn" @click="fetchAgents" :loading="loading">
          <el-icon><Refresh /></el-icon>
        </el-button>
        <el-button type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon> 新增智能体
        </el-button>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="stage-tabs" type="card">
      <el-tab-pane label="分析阶段 (Analysis)" name="analysis">
        <div class="agents-grid">
          <AgentCard 
            v-for="agent in getAgentsByStage('analysis')" 
            :key="agent.id" 
            :agent="agent"
            @edit="openEdit"
            @delete="handleDelete"
          />
        </div>
      </el-tab-pane>
      <el-tab-pane label="研究阶段 (Research)" name="research">
        <div class="agents-grid">
          <AgentCard 
            v-for="agent in getAgentsByStage('research')" 
            :key="agent.id" 
            :agent="agent"
            @edit="openEdit"
            @delete="handleDelete"
          />
        </div>
      </el-tab-pane>
      <el-tab-pane label="风控阶段 (Risk)" name="risk">
        <div class="agents-grid">
          <AgentCard 
            v-for="agent in getAgentsByStage('risk')" 
            :key="agent.id" 
            :agent="agent"
            @edit="openEdit"
            @delete="handleDelete"
          />
        </div>
      </el-tab-pane>
      <el-tab-pane label="交易阶段 (Trading)" name="trading">
        <div class="agents-grid">
          <AgentCard 
            v-for="agent in getAgentsByStage('trading')" 
            :key="agent.id" 
            :agent="agent"
            @edit="openEdit"
            @delete="handleDelete"
          />
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 编辑/创建 Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingAgent?.id ? '编辑智能体' : '新增智能体'"
      width="680px"
      destroy-on-close
    >
      <el-form :model="form" label-width="100px" ref="formRef" :rules="rules">
        <el-form-item label="ID" prop="id">
          <el-input v-model="form.id" :disabled="!!editingAgent?.id" placeholder="唯一标识符，如 market_analyst" />
        </el-form-item>
        
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="显示名称" />
        </el-form-item>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="阶段" prop="stage">
              <el-select v-model="form.stage" placeholder="选择所属阶段" style="width: 100%">
                <el-option label="分析阶段" value="analysis" />
                <el-option label="研究阶段" value="research" />
                <el-option label="风控阶段" value="risk" />
                <el-option label="交易阶段" value="trading" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
             <el-form-item label="类型" prop="type">
              <el-input v-model="form.type" placeholder="如 market, custom" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>

        <el-form-item label="System Prompt" prop="prompt">
          <el-input 
            v-model="form.prompt" 
            type="textarea" 
            :rows="8" 
            class="prompt-editor"
            placeholder="在此定义智能体的角色设定和指令..." 
          />
        </el-form-item>
        
        <el-form-item label="启用状态">
          <el-switch v-model="form.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitForm" :loading="saving">保存</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { Refresh, Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import { agentsApi, type AgentConfig } from '@/api/agents'
import AgentCard from './components/AgentCard.vue'

const loading = ref(false)
const saving = ref(false)
const agents = ref<AgentConfig[]>([])
const activeTab = ref('analysis')
const dialogVisible = ref(false)
const editingAgent = ref<AgentConfig | null>(null)
const formRef = ref<FormInstance>()

const form = reactive<AgentConfig>({
  id: '',
  name: '',
  stage: 'analysis',
  type: 'custom',
  description: '',
  prompt: '',
  enabled: true,
  is_system: false
})

const rules = {
  id: [{ required: true, message: '请输入ID', trigger: 'blur' }],
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  stage: [{ required: true, message: '请选择阶段', trigger: 'change' }]
}

const totalAgents = computed(() => agents.value.length)

const fetchAgents = async () => {
  loading.value = true
  try {
    const res = await agentsApi.list()
    agents.value = res.data || []
  } catch (error) {
    ElMessage.error('获取智能体列表失败')
  } finally {
    loading.value = false
  }
}

const getAgentsByStage = (stage: string) => {
  return agents.value.filter(a => a.stage === stage)
}

const openCreate = () => {
  editingAgent.value = null
  Object.assign(form, {
    id: '',
    name: '',
    stage: activeTab.value,
    type: 'custom',
    description: '',
    prompt: '',
    enabled: true,
    is_system: false
  })
  dialogVisible.value = true
}

const openEdit = (agent: AgentConfig) => {
  editingAgent.value = agent
  Object.assign(form, JSON.parse(JSON.stringify(agent)))
  dialogVisible.value = true
}

const submitForm = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (valid) {
      saving.value = true
      try {
        await agentsApi.save(form)
        ElMessage.success('保存成功')
        dialogVisible.value = false
        fetchAgents()
      } catch (error) {
        ElMessage.error('保存失败')
      } finally {
        saving.value = false
      }
    }
  })
}

const handleDelete = async (agent: AgentConfig) => {
  const actionText = agent.is_system ? '重置为默认配置' : '删除该智能体'
  ElMessageBox.confirm(`确定要${actionText} "${agent.name}" 吗？`, '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      await agentsApi.delete(agent.id)
      ElMessage.success(agent.is_system ? '已重置' : '已删除')
      fetchAgents()
    } catch (error) {
      ElMessage.error('操作失败')
    }
  })
}

onMounted(() => {
  fetchAgents()
})
</script>

<style scoped>
.agent-page {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0;
  color: var(--el-text-color-primary);
}

.count-tag {
  font-weight: normal;
}

.header-right {
  display: flex;
  gap: 12px;
}

.stage-tabs {
  background-color: var(--el-bg-color);
  padding: 20px;
  border-radius: 8px;
  border: 1px solid var(--el-border-color-light);
}

.agents-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
  padding-top: 20px;
}

:deep(.prompt-editor .el-textarea__inner) {
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  background-color: var(--el-fill-color-darker);
  line-height: 1.6;
}
</style>
