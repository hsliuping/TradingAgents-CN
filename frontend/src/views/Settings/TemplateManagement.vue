<template>
  <div class="ta-template-management">
    <el-card class="ta-filter-card">
      <el-form :inline="true" :model="filters">
        <el-form-item label="Agent类型">
          <el-select v-model="filters.agent_type" placeholder="全部" style="width: 180px">
            <el-option label="analysts" value="analysts" />
            <el-option label="researchers" value="researchers" />
            <el-option label="debators" value="debators" />
            <el-option label="managers" value="managers" />
            <el-option label="trader" value="trader" />
          </el-select>
        </el-form-item>
        <el-form-item label="Agent名称">
          <el-input v-model="filters.agent_name" placeholder="例如 market_analyst" style="width: 220px" />
        </el-form-item>
        <el-form-item label="偏好">
          <el-select v-model="filters.preference_type" placeholder="全部" style="width: 160px">
            <el-option label="aggressive" value="aggressive" />
            <el-option label="neutral" value="neutral" />
            <el-option label="conservative" value="conservative" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源">
          <el-select v-model="filters.is_system" placeholder="全部" style="width: 140px">
            <el-option label="全部" :value="undefined" />
            <el-option label="系统" :value="true" />
            <el-option label="用户" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" style="width: 140px">
            <el-option label="全部" value="" />
            <el-option label="active" value="active" />
            <el-option label="draft" value="draft" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadTemplates">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="ta-table-card">
      <el-table :data="items" style="width: 100%" v-loading="loading">
        <el-table-column prop="agent_type" label="Agent类型" width="140" />
        <el-table-column prop="agent_name" label="Agent名称" width="200" />
        <el-table-column prop="template_name" label="模板名称" min-width="220" />
        <el-table-column prop="preference_type" label="偏好" width="140" />
        <el-table-column prop="status" label="状态" width="120" />
        <el-table-column prop="version" label="版本" width="100" />
        <el-table-column label="来源" width="120">
          <template #default="scope">
            <el-tag type="info" v-if="scope.row.is_system">系统</el-tag>
            <el-tag type="success" v-else>用户</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="200">
          <template #default="scope">
            <span>{{ formatDate(scope.row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="200">
          <template #default="scope">
            <span>{{ formatDate(scope.row.updated_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="scope">
            <el-button size="small" @click="viewDetail(scope.row.id)">查看</el-button>
            <el-button size="small" type="primary" @click="previewTemplate(scope.row.id)">预览</el-button>
            <el-button size="small" type="success" @click="openEdit(scope.row.id)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="detailVisible" title="模板详情" width="700px">
      <div v-if="detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="模板名称">{{ detail.template_name }}</el-descriptions-item>
          <el-descriptions-item label="Agent">{{ detail.agent_type }} / {{ detail.agent_name }}</el-descriptions-item>
          <el-descriptions-item label="偏好">{{ detail.preference_type || '通用' }}</el-descriptions-item>
          <el-descriptions-item label="版本">{{ detail.version }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ detail.status }}</el-descriptions-item>
        </el-descriptions>
        <el-divider />
        <el-tabs>
          <el-tab-pane label="系统提示词">
            <pre class="ta-pre">{{ detail.content?.system_prompt }}</pre>
          </el-tab-pane>
          <el-tab-pane label="工具指导">
            <pre class="ta-pre">{{ detail.content?.tool_guidance }}</pre>
          </el-tab-pane>
          <el-tab-pane label="分析要求">
            <pre class="ta-pre">{{ detail.content?.analysis_requirements }}</pre>
          </el-tab-pane>
          <el-tab-pane label="输出格式">
            <pre class="ta-pre">{{ detail.content?.output_format }}</pre>
          </el-tab-pane>
          <el-tab-pane label="约束条件">
            <pre class="ta-pre">{{ detail.content?.constraints }}</pre>
          </el-tab-pane>
        </el-tabs>
      </div>
      <template #footer>
        <el-button @click="detailVisible=false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editVisible" title="编辑模板" width="800px">
      <el-form :model="editForm" label-width="100px">
        <el-form-item label="模板名称">
          <el-input v-model="editForm.template_name" />
        </el-form-item>
        <el-form-item label="系统提示词">
          <el-input v-model="editForm.content.system_prompt" type="textarea" :rows="6" />
        </el-form-item>
        <el-form-item label="工具指导">
          <el-input v-model="editForm.content.tool_guidance" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="分析要求">
          <el-input v-model="editForm.content.analysis_requirements" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="输出格式">
          <el-input v-model="editForm.content.output_format" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="约束条件">
          <el-input v-model="editForm.content.constraints" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible=false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { TemplatesApi, type TemplateItem } from '@/api/templates'
import { ApiClient } from '@/api/request'
import { ElMessage } from 'element-plus'

const filters = reactive<{ agent_type?: string; agent_name?: string; preference_type?: string; is_system?: boolean; status?: string }>({})
const items = ref<TemplateItem[]>([])
const loading = ref(false)
const detailVisible = ref(false)
const detail = ref<any>(null)
const editVisible = ref(false)
const editId = ref<string>('')
const editForm = ref<any>({ template_name: '', content: { system_prompt: '', tool_guidance: '', analysis_requirements: '', output_format: '', constraints: '' } })

const formatDate = (v?: string) => {
  if (!v) return '-'
  try { return new Date(v).toLocaleString() } catch { return v }
}

const resetFilters = () => {
  filters.agent_type = undefined
  filters.agent_name = ''
  filters.preference_type = undefined
  filters.is_system = undefined
  filters.status = ''
}

const loadTemplates = async () => {
  loading.value = true
  try {
    const res = await TemplatesApi.list({
      agent_type: filters.agent_type,
      agent_name: filters.agent_name,
      preference_type: filters.preference_type,
      is_system: filters.is_system,
      status: filters.status || undefined
    })
    items.value = Array.isArray(res.data) ? res.data : []
  } catch (e: any) {
    ElMessage.error(e?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

const viewDetail = async (id: string) => {
  try {
    const res = await TemplatesApi.get(id)
    detail.value = res.data
    detailVisible.value = true
  } catch (e: any) {
    ElMessage.error(e?.message || '获取详情失败')
  }
}

const previewTemplate = async (id: string) => {
  await viewDetail(id)
}

const openEdit = async (id: string) => {
  const res = await TemplatesApi.get(id)
  editId.value = id
  editForm.value = {
    template_name: res.data?.template_name || '',
    content: {
      system_prompt: res.data?.content?.system_prompt || '',
      tool_guidance: res.data?.content?.tool_guidance || '',
      analysis_requirements: res.data?.content?.analysis_requirements || '',
      output_format: res.data?.content?.output_format || '',
      constraints: res.data?.content?.constraints || ''
    }
  }
  editVisible.value = true
}

const saveEdit = async () => {
  try {
    await ApiClient.put(`/api/v1/templates/${editId.value}`, {
      template_name: editForm.value.template_name,
      content: editForm.value.content
    })
    ElMessage.success('保存成功')
    editVisible.value = false
    loadTemplates()
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  }
}

onMounted(() => {
  loadTemplates()
})
</script>

<style scoped>
.ta-template-management { padding: 16px }
.ta-filter-card { margin-bottom: 12px }
.ta-pre { white-space: pre-wrap; background: #f5f7fa; padding: 12px; border-radius: 4px }
</style>