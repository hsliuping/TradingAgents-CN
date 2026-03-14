<template>
  <div class="skill-generation-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <h1>
          <el-icon class="header-icon"><MagicStick /></el-icon>
          AI Skill 工坊
        </h1>
        <span class="subtitle">用自然语言描述需求，AI 自动生成并验证工具</span>
      </div>
      <div class="header-right">
        <el-button type="primary" @click="() => goToCreate()">
          <el-icon><Plus /></el-icon>
          创建新 Skill
        </el-button>
        <el-button @click="loadSkills">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 未完成的草稿 -->
    <div v-if="draftSessions.length > 0" class="draft-section">
      <div class="section-header">
        <h2>📝 未完成的草稿</h2>
        <el-button text size="small" @click="loadDrafts">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
      <div class="draft-cards">
        <div v-for="draft in draftSessions" :key="draft.session_id" class="draft-card">
          <div class="draft-card-header">
            <el-tag :type="draft.status === 'gathering' ? 'warning' : 'info'" size="small">
              {{ draft.status === 'gathering' ? '需求沟通中' : draft.status === 'confirmed' ? '已确认待生成' : draft.status }}
            </el-tag>
            <span class="draft-time">{{ formatTime(draft.updated_at) }}</span>
          </div>
          <div class="draft-card-body">
            <p class="draft-preview">{{ getDraftPreview(draft) }}</p>
            <div class="draft-meta">
              <span>已对话 {{ draft.rounds?.length || 0 }} 轮</span>
              <span v-if="draft.clarity_level">· 清晰度: {{ draft.clarity_level }}</span>
            </div>
          </div>
          <div class="draft-card-footer">
            <el-button type="primary" size="small" @click="() => goToCreate(draft.session_id)">
              继续完善
            </el-button>
            <el-button type="danger" size="small" text @click="handleDeleteDraft(draft)">
              删除
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- Skill 列表 -->
    <div class="skill-list-section">
      <div class="section-header">
        <h2>已生成的 Skill</h2>
        <el-radio-group v-model="filterStatus" size="small" @change="loadSkills">
          <el-radio-button label="">全部</el-radio-button>
          <el-radio-button label="active">已启用</el-radio-button>
          <el-radio-button label="disabled">已禁用</el-radio-button>
        </el-radio-group>
      </div>

      <el-table v-loading="listLoading" :data="skills" style="width: 100%" border stripe empty-text="还没有生成任何 Skill，点击上方按钮创建">
        <el-table-column prop="display_name" label="名称" min-width="160">
          <template #default="{ row }">
            <span class="skill-name-cell">
              <strong>{{ row.display_name || row.tool_id }}</strong>
              <el-tag size="small" type="info" style="margin-left: 6px">{{ row.category }}</el-tag>
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="240" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : row.status === 'disabled' ? 'info' : 'warning'" size="small">
              {{ row.status === 'active' ? '启用' : row.status === 'disabled' ? '禁用' : row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="final_score" label="评分" width="80" align="center">
          <template #default="{ row }">
            <span v-if="row.final_score != null">{{ row.final_score }}/10</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="generation_rounds" label="轮次" width="70" align="center" />
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="340" fixed="right">
          <template #default="{ row }">
            <el-button type="info" link size="small" @click="showHistoryDialog(row)">沟通记录</el-button>
            <el-button type="primary" link size="small" @click="showCodeDialog(row)">代码</el-button>
            <el-button type="primary" link size="small" @click="handleTest(row)">测试</el-button>
            <el-button type="warning" link size="small" @click="showOptimizeDialog(row)">优化</el-button>
            <el-button v-if="row.status === 'active'" type="warning" link size="small" @click="handleStatusToggle(row, 'disabled')">禁用</el-button>
            <el-button v-else type="success" link size="small" @click="handleStatusToggle(row, 'active')">启用</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 代码查看对话框 -->
    <el-dialog v-model="codeDialogVisible" :title="'源代码: ' + codeDialogTitle" width="750px" destroy-on-close>
      <div class="code-viewer-header">
        <el-button size="small" @click="copyCode" :disabled="!codeContent">
          <el-icon><DocumentCopy /></el-icon>
          复制代码
        </el-button>
      </div>
      <pre class="code-viewer"><code v-html="highlightedCode"></code></pre>
    </el-dialog>

    <!-- 测试对话框：参数输入 + 结果 -->
    <el-dialog v-model="testDialogVisible" :title="'🧪 测试: ' + (testSkillRow?.display_name || testSkillRow?.tool_id || '')" width="640px" destroy-on-close>
      <!-- 参数输入区 -->
      <div v-if="testSkillRow" class="test-params-section">
        <div class="test-params-header">输入测试参数</div>
        <el-form v-if="testParamsList.length > 0" label-width="120px" size="default">
          <el-form-item v-for="p in testParamsList" :key="p.name" :label="p.name" :required="p.required">
            <el-input
              v-if="p.type === 'string' || !p.type"
              v-model="testArgs[p.name]"
              :placeholder="p.description || `请输入 ${p.name}`"
              clearable
            />
            <el-input-number
              v-else-if="p.type === 'integer' || p.type === 'int'"
              v-model="testArgs[p.name]"
              :placeholder="p.description"
              controls-position="right"
              style="width: 100%"
            />
            <el-input-number
              v-else-if="p.type === 'float' || p.type === 'number'"
              v-model="testArgs[p.name]"
              :placeholder="p.description"
              :precision="2"
              controls-position="right"
              style="width: 100%"
            />
            <el-switch v-else-if="p.type === 'boolean' || p.type === 'bool'" v-model="testArgs[p.name]" />
            <el-input
              v-else
              v-model="testArgs[p.name]"
              :placeholder="p.description || `请输入 ${p.name}`"
              clearable
            />
          </el-form-item>
        </el-form>
        <p v-else class="test-params-empty">该 Skill 无参数，将使用默认测试输入</p>
        <div class="test-actions">
          <el-button type="primary" @click="runTest" :loading="testLoading">
            执行测试
          </el-button>
        </div>
      </div>
      <!-- 测试结果区 -->
      <div class="test-result-section">
        <div v-if="testResult" class="test-result-content">
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="执行结果">
              <el-tag :type="testResult.success ? 'success' : 'danger'">{{ testResult.success ? '成功' : '失败' }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="耗时">{{ testResult.execution_time }}s</el-descriptions-item>
            <el-descriptions-item v-if="testResult.error" label="错误">
              <span style="color: var(--el-color-danger)">{{ testResult.error }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="输出">
              <pre style="max-height: 280px; overflow: auto; white-space: pre-wrap; font-size: 12px;">{{ JSON.stringify(testResult.output, null, 2) }}</pre>
            </el-descriptions-item>
          </el-descriptions>
        </div>
        <div v-else-if="testLoading" style="text-align: center; padding: 24px">
          <el-icon class="is-loading" :size="24"><Loading /></el-icon>
          <p>测试执行中...</p>
        </div>
        <div v-else-if="testSkillRow && !testResult" style="text-align: center; padding: 24px; color: var(--el-text-color-placeholder); font-size: 13px">
          填写参数后点击「执行测试」
        </div>
      </div>
    </el-dialog>

    <!-- 沟通记录对话框 -->
    <el-dialog v-model="historyDialogVisible" :title="'💬 沟通记录: ' + historyDialogTitle" width="700px" destroy-on-close top="5vh">
      <div v-if="historyLoading" style="text-align: center; padding: 40px">
        <el-icon class="is-loading" :size="24"><Loading /></el-icon>
        <p>加载中...</p>
      </div>
      <div v-else-if="historySections.length === 0" style="text-align: center; padding: 40px; color: var(--el-text-color-secondary);">
        暂无沟通记录
      </div>
      <div v-else class="history-chat-messages">
        <div v-for="(section, sIdx) in historySections" :key="sIdx" class="history-section">
          <!-- 分段标题 -->
          <div class="history-section-header">
            <el-tag :type="section.type === 'creation' ? 'primary' : 'warning'" size="small">{{ section.label }}</el-tag>
            <span class="history-section-time" v-if="section.created_at">{{ section.created_at.replace('T', ' ').slice(0, 19) }}</span>
          </div>
          <div v-if="section.feedback" class="history-section-feedback">
            <strong>优化需求：</strong>{{ section.feedback }}
          </div>
          <!-- 各轮对话 -->
          <div v-for="(r, idx) in section.rounds" :key="idx" class="history-round">
            <!-- 用户消息 -->
            <div class="chat-msg chat-user">
              <div class="msg-avatar"><el-icon><User /></el-icon></div>
              <div class="msg-bubble">
                <div class="msg-meta">用户 · 第{{ r.round_number }}轮</div>
                <div class="msg-text" v-html="renderMarkdown(r.user_message)"></div>
              </div>
            </div>
            <!-- AI 回复 -->
            <div class="chat-msg chat-ai">
              <div class="msg-avatar"><el-icon><MagicStick /></el-icon></div>
              <div class="msg-bubble">
                <div class="msg-meta">AI · 第{{ r.round_number }}轮</div>
                <div class="msg-text" v-html="renderMarkdown(r.ai_message)"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- 优化对话框 -->
    <el-dialog v-model="optimizeDialogVisible" :title="'🔧 优化 Skill: ' + optimizeSkillName" width="640px" :close-on-click-modal="false" destroy-on-close>
      <div v-if="optimizeStep === 'input'">
        <el-alert type="info" :closable="false" style="margin-bottom: 16px">
          <template #title>描述你希望改进的地方，AI 将基于原始需求和当前代码重新生成</template>
        </el-alert>
        <el-input
          v-model="optimizeFeedback"
          type="textarea"
          :rows="5"
          placeholder="例如：增加错误重试机制、返回数据增加时间戳字段、优化数据解析逻辑..."
        />
        <div style="text-align: right; margin-top: 12px">
          <el-button @click="optimizeDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleOptimize" :disabled="!optimizeFeedback.trim()">
            🚀 开始优化
          </el-button>
        </div>
      </div>
      <div v-else-if="optimizeStep === 'running'" style="text-align: center; padding: 30px 0">
        <el-icon class="gen-spinner" :size="32"><Loading /></el-icon>
        <h3 style="margin: 12px 0 4px">正在优化 Skill...</h3>
        <p style="color: var(--el-text-color-secondary); font-size: 13px">AI 正在重新生成代码并验证</p>
        <el-progress :percentage="Math.round(optimizeProgress * 100) / 100" :stroke-width="12" style="margin: 20px 40px" />
      </div>
      <div v-else-if="optimizeStep === 'done'">
        <el-result
          :icon="optimizeResult?.success ? 'success' : 'error'"
          :title="optimizeResult?.success ? '✅ 优化成功！' : '❌ 优化失败'"
          :sub-title="optimizeResult?.success
            ? `版本: v${optimizeResult.version} · 耗时 ${optimizeResult.total_time}s · 评分 ${optimizeResult.final_score ?? '-'}/10`
            : optimizeResult?.error || '请修改反馈后重试'"
        >
          <template #extra>
            <el-button v-if="optimizeResult?.success" type="primary" @click="optimizeDialogVisible = false; loadSkills()">
              完成
            </el-button>
            <el-button v-if="!optimizeResult?.success" @click="optimizeStep = 'input'">返回修改</el-button>
            <el-button @click="optimizeDialogVisible = false">关闭</el-button>
          </template>
        </el-result>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onActivated } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, Refresh, User, MagicStick, Loading, DocumentCopy } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'
import hljs from 'highlight.js/lib/core'
import python from 'highlight.js/lib/languages/python'
import 'highlight.js/styles/github.min.css'
import { skillGenerationApi } from '@/api/skillGeneration'

hljs.registerLanguage('python', python)
import type { ExternalSkill, TestResult, OptimizeResult, SessionDetail, HistorySection } from '@/api/skillGeneration'

marked.setOptions({ breaks: true, gfm: true })

const renderMarkdown = (content: string): string => {
  if (!content?.trim()) return ''
  try { return marked.parse(content) as string } catch { return content }
}

const formatTime = (t: string): string => {
  if (!t) return '-'
  try { return new Date(t).toLocaleString('zh-CN') } catch { return t }
}

const router = useRouter()

// ==================== 状态 ====================

// Skill 列表
const skills = ref<ExternalSkill[]>([])
const listLoading = ref(false)
const filterStatus = ref('')

// 代码查看
const codeDialogVisible = ref(false)
const codeDialogTitle = ref('')
const codeContent = ref('')
const highlightedCode = computed(() => {
  const code = codeContent.value
  if (!code?.trim()) return ''
  try {
    return hljs.highlight(code, { language: 'python' }).value
  } catch {
    return code.replace(/</g, '&lt;').replace(/>/g, '&gt;')
  }
})

// 测试
const testDialogVisible = ref(false)
const testSkillRow = ref<ExternalSkill | null>(null)
const testArgs = ref<Record<string, any>>({})
const testResult = ref<TestResult | null>(null)
const testLoading = ref(false)
const testParamsList = computed(() => {
  const row = testSkillRow.value
  if (!row) return []
  const params = row.parameters || []
  return Array.isArray(params) ? params : []
})

// 沟通记录
const historyDialogVisible = ref(false)
const historyDialogTitle = ref('')
const historyLoading = ref(false)
const historySections = ref<HistorySection[]>([])

// 优化
const optimizeDialogVisible = ref(false)
const optimizeSkillName = ref('')
const optimizeSkillId = ref('')
const optimizeFeedback = ref('')
const optimizeStep = ref<'input' | 'running' | 'done'>('input')
const optimizeProgress = ref(0)
const optimizeResult = ref<OptimizeResult | null>(null)

// 草稿
const draftSessions = ref<SessionDetail[]>([])

// ==================== 方法 ====================

/** 跳转到创建页（新建或恢复草稿） */
const goToCreate = (sessionId?: string) => {
  if (sessionId) {
    router.push({ path: '/workflow/skill-generation/create', query: { sessionId } })
  } else {
    router.push('/workflow/skill-generation/create')
  }
}

/** 加载 Skill 列表 */
const loadSkills = async () => {
  listLoading.value = true
  try {
    const res = await skillGenerationApi.listSkills({
      status: filterStatus.value || undefined,
      page: 1,
      page_size: 100,
    })
    skills.value = res.items || []
  } catch (e: any) {
    ElMessage.error('加载列表失败')
  } finally {
    listLoading.value = false
  }
}

/** 查看代码 */
const showCodeDialog = async (row: ExternalSkill) => {
  try {
    const res = await skillGenerationApi.getSkillCode(row.tool_id)
    codeContent.value = res.code
    codeDialogTitle.value = row.display_name || row.tool_id
    codeDialogVisible.value = true
  } catch {
    ElMessage.error('获取代码失败')
  }
}

/** 复制代码 */
const copyCode = async () => {
  if (!codeContent.value) return
  try {
    await navigator.clipboard.writeText(codeContent.value)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败')
  }
}

/** 打开测试对话框 */
const handleTest = (row: ExternalSkill) => {
  testSkillRow.value = row
  testResult.value = null
  testLoading.value = false
  // 初始化参数：从 test_input 或 parameters 的 default
  const params = row.parameters || []
  const defaults = (row as any).test_input || {}
  const init: Record<string, any> = {}
  for (const p of Array.isArray(params) ? params : []) {
    init[p.name] = defaults[p.name] ?? p.default ?? (p.type === 'boolean' || p.type === 'bool' ? false : '')
  }
  testArgs.value = init
  testDialogVisible.value = true
}

/** 执行测试 */
const runTest = async () => {
  if (!testSkillRow.value) return
  testLoading.value = true
  testResult.value = null
  try {
    // 转换类型：number/boolean
    const params = testParamsList.value
    const args: Record<string, any> = {}
    for (const p of params) {
      let v = testArgs.value[p.name]
      if (v === '' || v === undefined) v = p.default
      if (p.type === 'integer' || p.type === 'int') args[p.name] = v != null ? Number(v) : undefined
      else if (p.type === 'float' || p.type === 'number') args[p.name] = v != null ? Number(v) : undefined
      else if (p.type === 'boolean' || p.type === 'bool') args[p.name] = !!v
      else args[p.name] = v
    }
    testResult.value = await skillGenerationApi.testSkill(testSkillRow.value.tool_id, args)
  } catch (e: any) {
    testResult.value = {
      success: false, output: null, stdout: '', stderr: '',
      execution_time: 0, error: e?.message || '测试请求失败',
    }
  } finally {
    testLoading.value = false
  }
}

/** 切换状态 */
const handleStatusToggle = async (row: ExternalSkill, newStatus: string) => {
  try {
    await skillGenerationApi.updateSkillStatus(row.tool_id, newStatus)
    ElMessage.success(`已${newStatus === 'active' ? '启用' : '禁用'}`)
    loadSkills()
  } catch {
    ElMessage.error('操作失败')
  }
}

/** 删除 Skill */
const handleDelete = (row: ExternalSkill) => {
  ElMessageBox.confirm(`确定删除 Skill「${row.display_name || row.tool_id}」吗？此操作不可恢复。`, '确认删除', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    try {
      await skillGenerationApi.deleteSkill(row.tool_id)
      ElMessage.success('已删除')
      loadSkills()
    } catch {
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

/** 查看沟通记录 */
const showHistoryDialog = async (row: ExternalSkill) => {
  historyDialogTitle.value = row.display_name || row.tool_id
  historySections.value = []
  historyLoading.value = true
  historyDialogVisible.value = true
  try {
    const history = await skillGenerationApi.getSkillHistory(row.tool_id)
    historySections.value = history.sections || []
  } catch {
    ElMessage.error('获取沟通记录失败')
  } finally {
    historyLoading.value = false
  }
}

/** 打开优化对话框 */
const showOptimizeDialog = (row: ExternalSkill) => {
  optimizeSkillId.value = row.tool_id
  optimizeSkillName.value = row.display_name || row.tool_id
  optimizeFeedback.value = ''
  optimizeStep.value = 'input'
  optimizeProgress.value = 0
  optimizeResult.value = null
  optimizeDialogVisible.value = true
}

/** 执行优化 */
const handleOptimize = async () => {
  if (!optimizeFeedback.value.trim()) return
  optimizeStep.value = 'running'
  optimizeProgress.value = 0

  const progressTimer = setInterval(() => {
    if (optimizeProgress.value < 90) {
      optimizeProgress.value = Math.round((optimizeProgress.value + Math.random() * 12) * 100) / 100
    }
  }, 800)

  try {
    const res = await skillGenerationApi.optimizeSkill(optimizeSkillId.value, optimizeFeedback.value)
    clearInterval(progressTimer)
    optimizeProgress.value = 100
    optimizeResult.value = res
    optimizeStep.value = 'done'
  } catch (e: any) {
    clearInterval(progressTimer)
    optimizeResult.value = {
      status: 'failed', skill_id: optimizeSkillId.value,
      optimize_session_id: '', success: false, version: 0,
      total_rounds: 0, total_time: 0, final_score: null,
      error: e?.message || '优化失败',
    }
    optimizeStep.value = 'done'
  }
}

// ==================== 草稿管理 ====================

/** 加载草稿会话 */
const loadDrafts = async () => {
  try {
    const res = await skillGenerationApi.listSessions({ status: 'gathering,confirmed', page_size: 50 })
    draftSessions.value = res.items || []
  } catch {
    // 静默失败，不影响主流程
    draftSessions.value = []
  }
}

/** 获取草稿预览文字 */
const getDraftPreview = (draft: SessionDetail): string => {
  if (draft.rounds && draft.rounds.length > 0) {
    const firstMsg = draft.rounds[0].user_message
    return firstMsg.length > 80 ? firstMsg.slice(0, 80) + '...' : firstMsg
  }
  return '(无内容)'
}

/** 删除草稿 */
const handleDeleteDraft = (draft: SessionDetail) => {
  ElMessageBox.confirm(
    `确定删除这个草稿吗？删除后无法恢复。`,
    '确认删除',
    { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
  ).then(async () => {
    try {
      await skillGenerationApi.deleteSession(draft.session_id)
      ElMessage.success('草稿已删除')
      loadDrafts()
    } catch {
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

onMounted(() => { loadSkills(); loadDrafts() })
onActivated(() => { loadSkills(); loadDrafts() })
</script>


<style lang="scss" scoped>
.skill-generation-page {
  padding: 16px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 12px;

  h1 {
    font-size: 20px;
    margin: 0;
    display: flex;
    align-items: center;
    gap: 6px;
    .header-icon { font-size: 24px; }
  }
  .subtitle { color: var(--el-text-color-secondary); font-size: 13px; margin-left: 8px; }
  .header-left { display: flex; align-items: center; }
  .header-right { display: flex; gap: 8px; }
}

/* ========== 草稿区域 ========== */
.draft-section {
  margin-bottom: 24px;

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
    h2 { font-size: 16px; margin: 0; }
  }
}

.draft-cards {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.draft-card {
  width: 280px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 12px;
  background: var(--el-bg-color);
  transition: box-shadow 0.2s;
  &:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
}

.draft-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  .draft-time { font-size: 11px; color: var(--el-text-color-placeholder); }
}

.draft-card-body {
  margin-bottom: 10px;
  .draft-preview {
    font-size: 13px;
    color: var(--el-text-color-regular);
    margin: 0 0 6px;
    line-height: 1.5;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .draft-meta {
    font-size: 11px;
    color: var(--el-text-color-placeholder);
    span + span { margin-left: 4px; }
  }
}

.draft-card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* ========== Skill 列表 ========== */
.skill-list-section {
  margin-top: 20px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;

  h2 { font-size: 16px; margin: 0; }
}

.skill-name-cell {
  display: flex;
  align-items: center;
}

/* ========== 沟通记录（复用 chat-msg 样式） ========== */
.chat-msg {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
  &.chat-user { flex-direction: row-reverse; }
  .msg-avatar {
    width: 32px; height: 32px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center; flex-shrink: 0;
    background: var(--el-color-primary-light-8); color: var(--el-color-primary); font-size: 16px;
  }
  &.chat-user .msg-avatar {
    background: var(--el-color-success-light-8); color: var(--el-color-success);
  }
  .msg-bubble {
    max-width: 80%; padding: 10px 14px; border-radius: 12px;
    background: var(--el-bg-color); border: 1px solid var(--el-border-color-lighter); line-height: 1.6;
  }
  &.chat-user .msg-bubble {
    background: var(--el-color-primary-light-9); border-color: var(--el-color-primary-light-7);
  }
}
.msg-text { :deep(p) { margin: 0 0 4px; } :deep(ul), :deep(ol) { margin: 4px 0; padding-left: 20px; } }

.history-chat-messages {
  max-height: 60vh;
  overflow-y: auto;
  padding: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
}

.history-section {
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 2px solid var(--el-border-color);
  &:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
}

.history-section-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.history-section-time {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}

.history-section-feedback {
  background: var(--el-color-warning-light-9);
  border-left: 3px solid var(--el-color-warning);
  padding: 8px 12px;
  margin-bottom: 12px;
  border-radius: 4px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.history-round {
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px dashed var(--el-border-color-lighter);
  &:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
}

.msg-meta {
  font-size: 11px;
  color: var(--el-text-color-placeholder);
  margin-bottom: 4px;
}

/* ========== 测试对话框 ========== */
.test-params-section {
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.test-params-header {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 12px;
  color: var(--el-text-color-regular);
}
.test-params-empty {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin: 0 0 12px;
}
.test-actions {
  margin-top: 12px;
}
.test-result-section {
  min-height: 80px;
}
.test-result-content {
  padding: 8px 0;
}

/* ========== 代码查看 ========== */
.code-viewer-header {
  margin-bottom: 8px;
}
.code-viewer {
  margin: 0;
  padding: 12px 16px;
  background: #f6f8fa;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.5;
  overflow: auto;
  max-height: 60vh;
  white-space: pre;
}
.code-viewer code {
  padding: 0;
  background: none;
}
</style>