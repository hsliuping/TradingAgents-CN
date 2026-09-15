<template>
  <div class="skill-generate">
    <!-- 创建任务列表（含进行中/失败/已完成） -->
    <el-card class="history-card session-card">
      <template #header>
        <div class="card-header">
          <span>创建任务</span>
          <div class="header-right">
            <el-select v-model="sessionStatusFilter" size="small" style="width: 120px" @change="loadSessions">
              <el-option label="全部" value="all" />
              <el-option label="进行中" value="in_progress" />
              <el-option label="仅失败" value="failed" />
              <el-option label="仅已完成" value="completed" />
            </el-select>
            <el-button text size="small" @click="loadSessions">刷新</el-button>
          </div>
        </div>
      </template>
      <el-table :data="sessions" v-if="sessions.length" size="small">
        <el-table-column label="需求描述" min-width="200">
          <template #default="scope">
            {{ scope.row.spec?.description || scope.row.rounds?.[0]?.user_message || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="scope">
            <el-tag :type="getSessionTagType(scope.row.status)" size="small">
              {{ getSessionStatusLabel(scope.row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="120">
          <template #default="scope">
            <el-progress
              v-if="scope.row.status === 'generating'"
              :percentage="Math.round((scope.row.pipeline_progress || 0) * 100)"
              :stroke-width="14"
              :text-inside="true"
              status="warning"
            />
            <span v-else-if="scope.row.pipeline_stage">—</span>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="170">
          <template #default="scope">
            {{ formatTime(scope.row.updated_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140">
          <template #default="scope">
            <el-button
              v-if="scope.row.status === 'failed'"
              size="small"
              type="warning"
              @click="resumeSession(scope.row.session_id)"
            >修复</el-button>
            <el-button
              v-if="scope.row.status === 'gathering' || scope.row.status === 'confirmed'"
              size="small"
              type="primary"
              @click="resumeSession(scope.row.session_id)"
            >继续</el-button>
            <el-button
              v-if="scope.row.status === 'generating'"
              size="small"
              disabled
            >生成中</el-button>
            <el-button
              v-if="scope.row.status === 'completed'"
              size="small"
              @click="viewSessionSkill(scope.row)"
            >查看</el-button>
            <el-button
              size="small"
              text
              type="danger"
              @click="deleteSession(scope.row.session_id)"
            >删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-else class="empty-hint">
        <el-empty description="暂无创建任务" :image-size="60" />
      </div>
    </el-card>

    <!-- 已完成的 Skill 列表 -->
    <el-card class="history-card">
      <template #header>
        <span>AI 生成的 Skill</span>
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
        <el-table-column prop="created_at" label="生成时间" width="170" />
        <el-table-column label="操作" width="300">
          <template #default="scope">
            <div class="row-actions">
              <el-button size="small" type="primary" @click="openTestDialog(scope.row)">测试</el-button>
              <el-button size="small" @click="openEditDialog(scope.row)">编辑说明</el-button>
              <el-button size="small" @click="viewSkill(scope.row)">查看</el-button>
              <el-button size="small" @click="iterateSkill(scope.row)">迭代优化</el-button>
              <el-button size="small" text type="danger" @click="deleteSkill(scope.row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
      <div v-else class="empty-hint">
        <el-empty description="暂无生成记录" />
      </div>
    </el-card>

    <el-dialog
      v-model="detailVisible"
      :title="`Skill 详情：${detailSkill?.display_name || ''}`"
      width="900px"
      destroy-on-close
      class="skill-detail-dialog"
    >
      <div v-if="detailSkill" class="skill-detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="名称">{{ detailSkill.display_name }}</el-descriptions-item>
          <el-descriptions-item label="Tool ID">{{ detailSkill.tool_id }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusTagType(detailSkill.status)" size="small">
              {{ getStatusLabel(detailSkill.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="分类">{{ detailSkill.category || '-' }}</el-descriptions-item>
          <el-descriptions-item label="描述" :span="2">{{ detailSkill.description || '-' }}</el-descriptions-item>
          <el-descriptions-item label="生成轮次">{{ detailSkill.generation_rounds || '-' }}</el-descriptions-item>
          <el-descriptions-item label="生成耗时">
            {{ detailSkill.generation_time ? detailSkill.generation_time + 's' : '-' }}
          </el-descriptions-item>
        </el-descriptions>

        <div v-if="detailSkill.parameters?.length" class="detail-section">
          <div class="section-title">参数列表</div>
          <el-table :data="detailSkill.parameters" size="small" border>
            <el-table-column prop="name" label="参数名" width="140" />
            <el-table-column prop="type" label="类型" width="100" />
            <el-table-column prop="description" label="说明" />
            <el-table-column prop="required" label="必填" width="60">
              <template #default="scope">
                {{ scope.row.required ? '是' : '否' }}
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="detail-section">
          <div class="section-title">源代码</div>
          <div v-loading="codeLoading" class="code-container">
            <pre v-if="skillCode"><code>{{ skillCode }}</code></pre>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button type="primary" @click="detailSkill && openTestDialog(detailSkill)">测试</el-button>
        <el-button @click="detailSkill && openEditDialog(detailSkill)">编辑说明</el-button>
        <el-button type="primary" plain @click="iterateSkill(detailSkill)">迭代优化</el-button>
      </template>
    </el-dialog>

    <!-- 在线测试对话框 -->
    <el-dialog
      v-model="testVisible"
      :title="`测试 Skill：${testSkill?.display_name || ''}`"
      width="760px"
      destroy-on-close
      class="skill-test-dialog"
    >
      <div v-if="testSkill" class="test-dialog-body">
        <el-alert
          type="info"
          :closable="false"
          show-icon
          title="在沙箱中真实运行该 Skill，可直接修改参数后反复测试"
          style="margin-bottom: 12px;"
        />
        <el-form label-position="top" size="small" class="test-form">
          <el-form-item
            v-for="param in testParamDefs"
            :key="param.name"
            :label="`${param.name}${param.required ? ' *' : ''}（${param.type || 'string'}）${param.description ? ' — ' + param.description : ''}`"
          >
            <el-switch
              v-if="param.type === 'boolean'"
              v-model="testArgs[param.name]"
            />
            <el-input-number
              v-else-if="param.type === 'integer' || param.type === 'float'"
              v-model="testArgs[param.name]"
              :controls="false"
              style="width: 100%"
              :placeholder="param.default !== undefined && param.default !== null ? String(param.default) : '未填写则使用函数默认值'"
            />
            <el-input
              v-else
              v-model="testArgs[param.name]"
              :placeholder="param.default !== undefined && param.default !== null ? String(param.default) : '未填写则使用函数默认值'"
            />
          </el-form-item>
          <el-form-item v-if="!testParamDefs.length" label="参数">
            <span class="form-hint">该 Skill 没有定义参数，可直接运行。</span>
          </el-form-item>
        </el-form>

        <div v-if="testResult" class="test-result">
          <el-alert
            :type="testResult.success ? 'success' : 'error'"
            :closable="false"
            show-icon
            :title="testResult.success
              ? `执行成功（耗时 ${(testResult.execution_time || 0).toFixed(2)}s）`
              : `执行失败（耗时 ${(testResult.execution_time || 0).toFixed(2)}s）`"
            :description="testResult.error || ''"
            style="margin-bottom: 8px;"
          />
          <div class="result-section-title">执行输出</div>
          <pre class="result-json">{{ formatJson(testResult.output) }}</pre>
          <el-collapse v-if="testResult.stderr" class="stderr-collapse">
            <el-collapse-item title="错误日志（stderr）" name="stderr">
              <pre class="result-stderr">{{ testResult.stderr }}</pre>
            </el-collapse-item>
          </el-collapse>
        </div>
      </div>
      <template #footer>
        <el-button
          v-if="testSkill?.test_input && Object.keys(testSkill.test_input).length"
          @click="fillExampleArgs"
        >填入示例参数</el-button>
        <el-button @click="testVisible = false">关闭</el-button>
        <el-button type="primary" :loading="testLoading" @click="runTest">运行测试</el-button>
      </template>
    </el-dialog>

    <!-- 编辑说明对话框 -->
    <el-dialog
      v-model="editVisible"
      title="编辑 Skill 说明"
      width="560px"
      destroy-on-close
    >
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="这里修改的是展示名称和功能说明；参数、代码与接口契约如需变更，请使用「迭代优化」生成新版本。"
        style="margin-bottom: 14px;"
      />
      <el-form label-position="top">
        <el-form-item label="名称" required>
          <el-input v-model="editForm.display_name" maxlength="100" show-word-limit />
        </el-form-item>
        <el-form-item label="功能说明">
          <el-input
            v-model="editForm.description"
            type="textarea"
            :rows="5"
            maxlength="2000"
            show-word-limit
            placeholder="说明这个 Skill 的用途、输入和返回内容"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSaving" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { skillGenerationApi } from '@/api/skillGeneration'

const router = useRouter()
const recentSkills = ref<any[]>([])
const sessions = ref<any[]>([])
const sessionStatusFilter = ref('in_progress')
const detailVisible = ref(false)
const detailSkill = ref<any>(null)
const skillCode = ref('')
const codeLoading = ref(false)

// 在线测试
const testVisible = ref(false)
const testLoading = ref(false)
const testSkill = ref<any>(null)
const testArgs = ref<Record<string, any>>({})
const testResult = ref<any>(null)

// 编辑说明
const editVisible = ref(false)
const editSaving = ref(false)
const editForm = ref<{ tool_id: string; display_name: string; description: string }>({
  tool_id: '',
  display_name: '',
  description: '',
})

// 测试表单只展示 Skill 已定义的参数
const testParamDefs = computed(() => {
  const params = testSkill.value?.parameters
  return Array.isArray(params) ? params : []
})

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

function getSessionStatusLabel(status: string) {
  const labels: Record<string, string> = {
    gathering: '需求沟通中',
    confirmed: '已确认规格',
    generating: '生成中',
    completed: '已完成',
    failed: '失败'
  }
  return labels[status] || status
}

function getSessionTagType(status: string): ElTagType {
  const types: Record<string, ElTagType> = {
    gathering: 'primary',
    confirmed: 'info',
    generating: 'warning',
    completed: 'success',
    failed: 'danger'
  }
  return types[status] || 'info'
}

function formatTime(t: string) {
  if (!t) return '-'
  return t.replace('T', ' ').slice(0, 19)
}

async function viewSkill(skill: any) {
  detailSkill.value = skill
  detailVisible.value = true
  skillCode.value = ''
  try {
    codeLoading.value = true
    const result = await skillGenerationApi.getSkillCode(skill.tool_id)
    skillCode.value = result.code || ''
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '加载代码失败')
  } finally {
    codeLoading.value = false
  }
}

function viewSessionSkill(session: any) {
  const toolId = session.pipeline_result?.tool_id
  if (toolId) {
    const skill = recentSkills.value.find(s => s.tool_id === toolId)
    if (skill) {
      viewSkill(skill)
      return
    }
  }
  router.push('/skills/generation/create?sessionId=' + session.session_id)
}

function resumeSession(sessionId: string) {
  router.push('/skills/generation/create?sessionId=' + sessionId)
}

function iterateSkill(skill: any) {
  // 跳转到 Skill 生成页面，并带上现有 Skill 的信息用于迭代优化
  const params = new URLSearchParams()
  params.set('toolId', skill.tool_id)
  params.set('displayName', skill.display_name || '')
  params.set('description', skill.description || '')
  params.set('category', skill.category || '')
  params.set('mode', 'iterate')
  detailVisible.value = false
  router.push('/skills/generation/create?' + params.toString())
}

async function deleteSession(sessionId: string) {
  try {
    await ElMessageBox.confirm('确认删除该创建任务？', '提示', { type: 'warning' })
    await skillGenerationApi.deleteSession(sessionId)
    ElMessage.success('已删除')
    await loadSessions()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error?.response?.data?.detail || '删除失败')
    }
  }
}

async function deleteSkill(skill: any) {
  try {
    await ElMessageBox.confirm(`确认删除 Skill「${skill.display_name}」？删除后无法恢复。`, '提示', { type: 'warning' })
    await skillGenerationApi.deleteSkill(skill.tool_id)
    ElMessage.success('已删除')
    await loadRecentSkills()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error?.response?.data?.detail || '删除失败')
    }
  }
}

// ==================== 在线测试 ====================

function buildInitialTestArgs(skill: any): Record<string, any> {
  const args: Record<string, any> = {}
  const example = skill.test_input || {}
  for (const param of skill.parameters || []) {
    const name = param.name
    const exampleVal = example[name]
    if (exampleVal !== undefined && exampleVal !== null && exampleVal !== '') {
      args[name] = exampleVal
    } else if (param.default !== undefined && param.default !== null) {
      args[name] = param.default
    } else if (param.type === 'boolean') {
      args[name] = false
    } else {
      // 键先置空，输入框显示 placeholder（未填写则使用函数默认值）
      args[name] = undefined
    }
  }
  return args
}

function openTestDialog(skill: any) {
  testSkill.value = skill
  testArgs.value = buildInitialTestArgs(skill)
  testResult.value = null
  detailVisible.value = false
  testVisible.value = true
}

function fillExampleArgs() {
  if (testSkill.value) {
    testArgs.value = buildInitialTestArgs(testSkill.value)
  }
}

async function runTest() {
  if (!testSkill.value) return
  // 只提交已填写的参数；0/false 是合法入参，必须保留
  const args: Record<string, any> = {}
  for (const [key, value] of Object.entries(testArgs.value)) {
    if (value !== null && value !== undefined && value !== '') {
      args[key] = value
    }
  }
  testLoading.value = true
  testResult.value = null
  try {
    testResult.value = await skillGenerationApi.testSkill(testSkill.value.tool_id, args)
  } catch (error: any) {
    testResult.value = {
      success: false,
      output: null,
      stderr: '',
      execution_time: 0,
      error: error?.response?.data?.detail || error?.message || '测试请求失败',
    }
  } finally {
    testLoading.value = false
  }
}

function formatJson(value: any): string {
  if (value === null || value === undefined) return '（无输出）'
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

// ==================== 编辑说明 ====================

function openEditDialog(skill: any) {
  editForm.value = {
    tool_id: skill.tool_id,
    display_name: skill.display_name || '',
    description: skill.description || '',
  }
  detailVisible.value = false
  editVisible.value = true
}

async function saveEdit() {
  const displayName = editForm.value.display_name.trim()
  if (!displayName) {
    ElMessage.warning('名称不能为空')
    return
  }
  editSaving.value = true
  try {
    await skillGenerationApi.updateSkillInfo(
      editForm.value.tool_id,
      displayName,
      editForm.value.description.trim(),
    )
    ElMessage.success('说明已更新')
    editVisible.value = false
    // 同步本地列表与详情缓存，避免重新拉取前展示旧名称
    const target = recentSkills.value.find(s => s.tool_id === editForm.value.tool_id)
    if (target) {
      target.display_name = displayName
      target.description = editForm.value.description.trim()
    }
    if (detailSkill.value?.tool_id === editForm.value.tool_id) {
      detailSkill.value.display_name = displayName
      detailSkill.value.description = editForm.value.description.trim()
    }
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '保存失败')
  } finally {
    editSaving.value = false
  }
}

async function loadRecentSkills() {
  try {
    const result = await skillGenerationApi.listSkills({ page: 1, page_size: 10 })
    recentSkills.value = result.items || []
  } catch (error) {
    console.error('Load recent skills failed:', error)
  }
}

async function loadSessions() {
  try {
    const result = await skillGenerationApi.listSessions({ page: 1, page_size: 20 })
    let items = result.items || []
    const filter = sessionStatusFilter.value
    if (filter === 'in_progress') {
      items = items.filter(s => ['gathering', 'confirmed', 'generating'].includes(s.status))
    } else if (filter === 'failed') {
      items = items.filter(s => s.status === 'failed')
    } else if (filter === 'completed') {
      items = items.filter(s => s.status === 'completed')
    }
    sessions.value = items
  } catch (error) {
    console.error('Load sessions failed:', error)
  }
}

onMounted(() => {
  loadRecentSkills()
  loadSessions()
})
</script>

<style scoped>
.skill-generate {
  padding: 20px;
}

.history-card {
  max-width: 800px;
  margin-bottom: 16px;
}

.session-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;

  .header-right {
    display: flex;
    gap: 8px;
    align-items: center;
  }
}

.empty-hint {
  padding: 40px;
  text-align: center;
}

.row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 6px;
  align-items: center;
}

.form-hint {
  color: #909399;
  font-size: 13px;
}

.test-dialog-body {
  .test-result {
    margin-top: 14px;
  }

  .result-section-title {
    font-size: 13px;
    font-weight: 600;
    color: #303133;
    margin: 8px 0 6px;
  }

  .result-json,
  .result-stderr {
    margin: 0;
    padding: 10px;
    background: #f5f7fa;
    border-radius: 4px;
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 12px;
    line-height: 1.6;
    color: #303133;
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 320px;
    overflow: auto;
  }

  .result-stderr {
    background: #fef0f0;
    color: #f56c6c;
  }

  .stderr-collapse {
    margin-top: 8px;
  }
}

.skill-detail {
  .detail-section {
    margin-top: 16px;

    .section-title {
      font-size: 14px;
      font-weight: 600;
      color: #303133;
      margin-bottom: 8px;
    }
  }

  .code-container {
    max-height: 400px;
    overflow: auto;
    background: #f5f7fa;
    border-radius: 4px;
    padding: 12px;

    pre {
      margin: 0;
      font-family: 'Consolas', 'Monaco', monospace;
      font-size: 12px;
      line-height: 1.6;
      color: #303133;
      white-space: pre-wrap;
      word-break: break-all;
    }
  }
}
</style>
