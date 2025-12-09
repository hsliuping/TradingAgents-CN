<template>
  <div class="agent-page">
    <el-card class="phase-card" shadow="never">
      <template #header>
        <div class="phase-header">
          <div class="phase-title-group">
            <h2 class="phase-title">阶段智能体配置（YAML）</h2>
            <el-tag size="small" type="info" effect="plain">phase{{ activePhase }}</el-tag>
            <span v-if="phaseConfigPath" class="phase-path">{{ phaseConfigPath }}</span>
          </div>
          <div class="phase-actions">
            <el-select v-model="activePhase" size="small" style="width: 200px" @change="fetchPhaseConfig">
              <el-option :value="1" label="第一阶段 (phase1)" />
              <el-option :value="2" label="第二阶段 (phase2)" />
              <el-option :value="3" label="第三阶段 (phase3)" />
              <el-option :value="4" label="第四阶段 (phase4)" />
            </el-select>
            <el-button size="small" @click="fetchPhaseConfig" :loading="phaseLoading">
              <el-icon><Refresh /></el-icon>刷新
            </el-button>
            <el-button size="small" type="primary" @click="addPhaseAgent">
              <el-icon><Plus /></el-icon>新增智能体
            </el-button>
            <el-button size="small" type="success" :loading="phaseSaving" @click="savePhaseConfig">
              保存配置
            </el-button>
          </div>
        </div>
      </template>

      <el-alert
        v-if="!phaseFileExists"
        type="warning"
        :closable="false"
        title="配置文件不存在"
        description="未找到对应 phase 的 YAML 文件，保存后将自动创建；如不需要可忽略。"
        style="margin-bottom: 12px;"
      />
      <el-alert
        v-else
        type="info"
        :closable="false"
        title="说明"
        description="slug / name / roleDefinition 为必填；groups、whenToUse 可留空；slug 需唯一。"
        style="margin-bottom: 12px;"
      />

      <el-skeleton v-if="phaseLoading" animated :rows="6" />
      <div v-else>
        <el-empty v-if="!phaseModes.length" description="暂无智能体，点击新增智能体" />
        <el-collapse v-else v-model="openedPanels">
          <el-collapse-item
            v-for="(mode, index) in phaseModes"
            :key="mode.slug || `agent-${index}`"
            :name="mode.slug || `agent-${index}`"
          >
            <template #title>
              <div class="collapse-title">
                <strong>{{ mode.name || '未命名智能体' }}</strong>
                <span class="collapse-sub">{{ mode.slug || '未设置 slug' }}</span>
              </div>
            </template>
            <el-form label-width="110px" class="mode-form">
              <el-row :gutter="16">
                <el-col :span="12">
                  <el-form-item label="slug" required>
                    <el-input v-model="mode.slug" placeholder="唯一标识，必填" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="名称" required>
                    <el-input v-model="mode.name" placeholder="显示名称，必填" />
                  </el-form-item>
                </el-col>
              </el-row>

              <el-row :gutter="16">
                <el-col :span="12">
                  <el-form-item label="description">
                    <el-input v-model="mode.description" placeholder="可选，不填将使用 slug" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="source">
                    <el-input v-model="mode.source" placeholder="默认 global，可留空" />
                  </el-form-item>
                </el-col>
              </el-row>

              <el-form-item label="groups">
                <el-select
                  v-model="mode.groups"
                  multiple
                  collapse-tags
                  filterable
                  allow-create
                  default-first-option
                  placeholder="可选，默认空"
                  style="width: 100%;"
                >
                  <el-option v-for="grp in groupOptions" :key="grp" :label="grp" :value="grp" />
                </el-select>
              </el-form-item>

              <el-form-item label="whenToUse">
                <el-input
                  v-model="mode.whenToUse"
                  type="textarea"
                  :rows="2"
                  placeholder="可选，使用场景说明"
                />
              </el-form-item>

              <el-form-item label="roleDefinition" required>
                <el-input
                  v-model="mode.roleDefinition"
                  type="textarea"
                  :rows="12"
                  class="prompt-editor"
                  placeholder="系统提示词，必填"
                />
              </el-form-item>

              <div class="mode-actions">
                <el-button type="primary" text @click.stop="savePhaseConfig" :loading="phaseSaving">保存</el-button>
                <el-button type="danger" text @click.stop="removePhaseAgent(index)">删除</el-button>
              </div>
            </el-form>
          </el-collapse-item>
        </el-collapse>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Refresh, Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { agentConfigApi, type PhaseAgentMode } from '@/api/agentConfigs'

// 阶段 YAML 配置
const activePhase = ref(1)
const phaseModes = ref<PhaseAgentMode[]>([])
const phaseLoading = ref(false)
const phaseSaving = ref(false)
const phaseFileExists = ref(true)
const phaseConfigPath = ref('')
const openedPanels = ref<string[]>([])
const groupOptions = ['read', 'edit', 'browser', 'command', 'mcp']

const normalizeMode = (mode?: PhaseAgentMode): PhaseAgentMode => ({
  slug: mode?.slug || '',
  name: mode?.name || '',
  roleDefinition: mode?.roleDefinition || '',
  description: mode?.description || mode?.slug || '',
  whenToUse: mode?.whenToUse || '',
  groups: mode?.groups ? [...mode.groups] : [],
  source: mode?.source || 'global'
})

const fetchPhaseConfig = async () => {
  phaseLoading.value = true
  try {
    const res = await agentConfigApi.getPhase(activePhase.value)
    const data = res.data
    phaseFileExists.value = data?.exists ?? false
    phaseConfigPath.value = data?.path || ''
    phaseModes.value = (data?.customModes || []).map((item) => normalizeMode(item))
    openedPanels.value = [] // 默认收起
    if (data && data.exists === false) {
      ElMessage.info(`phase${activePhase.value} 配置文件不存在，保存后将自动创建`)
    }
  } catch (error) {
    console.error('获取阶段配置失败', error)
    ElMessage.error('获取阶段配置失败')
  } finally {
    phaseLoading.value = false
  }
}

const addPhaseAgent = () => {
  const item = normalizeMode()
  item.source = 'global'
  phaseModes.value.push(item)
  openedPanels.value = [item.slug || `agent-${Date.now()}`]
}

const removePhaseAgent = (index: number) => {
  phaseModes.value.splice(index, 1)
}

const validatePhaseModes = () => {
  const slugSet = new Set<string>()
  for (let i = 0; i < phaseModes.value.length; i++) {
    const mode = phaseModes.value[i]
    const slug = mode.slug?.trim()
    const name = mode.name?.trim()
    const prompt = mode.roleDefinition?.trim()

    if (!slug) {
      ElMessage.error(`第 ${i + 1} 个智能体缺少 slug`)
      return false
    }
    if (slugSet.has(slug)) {
      ElMessage.error(`slug "${slug}" 重复，请保持唯一`)
      return false
    }
    slugSet.add(slug)
    if (!name) {
      ElMessage.error(`slug "${slug}" 缺少名称`)
      return false
    }
    if (!prompt) {
      ElMessage.error(`slug "${slug}" 缺少 roleDefinition`)
      return false
    }
  }
  return true
}

const savePhaseConfig = async () => {
  if (!validatePhaseModes()) return
  phaseSaving.value = true
  try {
    const payload = {
      customModes: phaseModes.value.map((mode) => ({
        slug: mode.slug.trim(),
        name: mode.name.trim(),
        roleDefinition: mode.roleDefinition,
        description: mode.description?.trim() || mode.slug.trim(),
        whenToUse: mode.whenToUse?.trim() || undefined,
        groups: mode.groups?.filter(Boolean) || [],
        source: mode.source?.trim() || 'global'
      }))
    }
    await agentConfigApi.savePhase(activePhase.value, payload)
    ElMessage.success('阶段配置已保存')
    await fetchPhaseConfig()
  } catch (error) {
    console.error('保存阶段配置失败', error)
    ElMessage.error('保存阶段配置失败')
  } finally {
    phaseSaving.value = false
  }
}

onMounted(() => {
  fetchPhaseConfig()
})
</script>

<style scoped>
.agent-page {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.phase-card {
  margin-bottom: 20px;
}

.phase-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.phase-title-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.phase-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.phase-path {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.phase-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.collapse-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.collapse-sub {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.mode-form {
  padding: 4px 0 8px;
}

.mode-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

:deep(.prompt-editor .el-textarea__inner) {
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  background-color: var(--el-fill-color-darker);
  line-height: 1.6;
}
</style>
