<template>
  <div class="skill-generate">
    <el-card class="generate-card">
      <template #header>
        <span>AI 生成 Skill</span>
      </template>

      <el-form :model="generateForm" label-width="120px">
        <el-form-item label="Skill 名称">
          <el-input
            v-model="generateForm.name"
            placeholder="输入 Skill 名称"
          />
        </el-form-item>

        <el-form-item label="需求描述">
          <el-input
            v-model="generateForm.description"
            type="textarea"
            :rows="6"
            placeholder="描述您希望 Skill 实现的功能..."
          />
        </el-form-item>

        <el-form-item label="标签">
          <el-input
            v-model="generateForm.tags"
            placeholder="用逗号分隔多个标签"
          />
        </el-form-item>

        <el-form-item label="数据源">
          <el-select v-model="generateForm.dataSource" placeholder="选择数据源">
            <el-option label="股票数据" value="stock" />
            <el-option label="外部API" value="external" />
            <el-option label="知识库" value="knowledge" />
          </el-select>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleGenerate" :loading="generating">
            <template #icon><MagicStick /></template>
            生成 Skill
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="history-card" style="margin-top: 20px;">
      <template #header>
        <span>最近生成</span>
      </template>
      <el-table :data="recentSkills" v-if="recentSkills.length">
        <el-table-column prop="display_name" label="名称" />
        <el-table-column prop="status" label="状态">
          <template #default="scope">
            <el-tag :type="getStatusTagType(scope.row.status)">
              {{ getStatusLabel(scope.row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="生成时间" />
        <el-table-column label="操作">
          <template #default="scope">
            <el-button size="small" @click="viewSkill(scope.row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-else class="empty-hint">
        <el-empty description="暂无生成记录" />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { MagicStick } from '@element-plus/icons-vue'
import { skillGenerationApi } from '@/api/skillGeneration'

const generateForm = ref({
  name: '',
  description: '',
  tags: '',
  dataSource: 'stock'
})

const generating = ref(false)
const recentSkills = ref<any[]>([])

function getStatusLabel(status: string) {
  const labels: Record<string, string> = {
    active: '已启用',
    disabled: '已禁用',
    draft: '草稿',
    testing: '测试中',
    archived: '已归档',
    failed: '失败'
  }
  return labels[status] || status
}

type ElTagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

function getStatusTagType(status: string): ElTagType {
  const types: Record<string, ElTagType> = {
    active: 'success',
    disabled: 'warning',
    draft: 'info',
    testing: 'primary',
    archived: 'info',
    failed: 'danger'
  }
  return types[status] || 'info'
}

async function handleGenerate() {
  if (!generateForm.value.description.trim()) {
    return
  }
  generating.value = true
  try {
    const result = await skillGenerationApi.startSession({
      description: generateForm.value.description,
      provider: 'openai'
    })
    console.log('Session started:', result)
    window.location.href = `/workflow/skill-generation/create?session=${result.session_id}`
  } catch (error) {
    console.error('Generate failed:', error)
  } finally {
    generating.value = false
  }
}

function viewSkill(skill: any) {
  window.location.href = `/workflow/skill-generation/create?skill=${skill.skill_id}`
}

async function loadRecentSkills() {
  try {
    const result = await skillGenerationApi.listSkills({ page: 1, page_size: 10 })
    recentSkills.value = result.items || []
  } catch (error) {
    console.error('Load recent skills failed:', error)
  }
}

onMounted(() => {
  loadRecentSkills()
})
</script>

<style scoped>
.skill-generate {
  padding: 20px;
}

.generate-card {
  max-width: 600px;
}

.history-card {
  max-width: 800px;
}

.empty-hint {
  padding: 40px;
  text-align: center;
}
</style>
