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
        <el-button type="primary" @click="startNewCreation" :disabled="creating">
          <el-icon><Plus /></el-icon>
          创建新 Skill
        </el-button>
        <el-button @click="loadSkills">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 创建向导对话框 -->
    <el-dialog
      v-model="wizardVisible"
      title="🛠️ 创建新 Skill"
      width="720px"
      :close-on-click-modal="false"
      destroy-on-close
      top="5vh"
      @closed="loadDrafts"
    >
      <!-- 步骤条 -->
      <el-steps :active="wizardStep" finish-status="success" simple style="margin-bottom: 20px">
        <el-step title="需求沟通" />
        <el-step title="规格确认" />
        <el-step title="代码生成" />
        <el-step title="完成" />
      </el-steps>

      <!-- 步骤 1: 需求沟通（对话式） -->
      <div v-if="wizardStep === 0" class="wizard-chat">
        <!-- 对话消息区 -->
        <div ref="chatContainer" class="chat-messages">
          <el-empty v-if="chatMessages.length === 0 && !chatLoading" description="描述你需要的工具，AI 会引导你完善需求" :image-size="60" />
          <div v-for="(msg, idx) in chatMessages" :key="idx"
               :class="['chat-msg', msg.role === 'user' ? 'chat-user' : 'chat-ai']">
            <div class="msg-avatar">
              <el-icon v-if="msg.role === 'user'"><User /></el-icon>
              <el-icon v-else><MagicStick /></el-icon>
            </div>
            <div class="msg-bubble">
              <div class="msg-text" v-html="renderMarkdown(msg.content)"></div>
            </div>
          </div>
          <!-- 思考中指示器 -->
          <div v-if="chatLoading" class="chat-msg chat-ai">
            <div class="msg-avatar"><el-icon><MagicStick /></el-icon></div>
            <div class="msg-bubble thinking">
              <span class="dot-animation">AI 正在分析<span>.</span><span>.</span><span>.</span></span>
            </div>
          </div>
        </div>

        <!-- 边界警告 -->
        <el-alert v-if="boundaryWarning" type="warning" :closable="false" style="margin-bottom: 10px">
          <template #title>⚠️ 复杂度提醒 ({{ boundaryCheck?.complexity_score }}/5)</template>
          <div v-for="c in boundaryCheck?.concerns" :key="c">• {{ c }}</div>
          <div v-if="boundaryCheck?.decomposition_suggestions?.length" style="margin-top: 6px">
            <strong>建议拆分为：</strong>
            <div v-for="s in boundaryCheck?.decomposition_suggestions" :key="s">→ {{ s }}</div>
          </div>
        </el-alert>

        <!-- 输入区 -->
        <div class="chat-input">
          <el-input
            v-model="userInput"
            type="textarea"
            :rows="2"
            :autosize="{ minRows: 2, maxRows: 4 }"
            :placeholder="chatMessages.length === 0 ? '描述你需要的工具，例如：我需要获取东方财富个股新闻...' : '回复 AI 的问题...'"
            :disabled="chatLoading"
            @keydown.enter.ctrl="handleChatSend"
          />
          <div class="chat-actions">
            <span class="tip">Ctrl+Enter 发送 · 第 {{ currentRound }}/{{ expectedRounds }} 轮</span>
            <div>
              <el-button v-if="canConfirm" type="success" @click="handleConfirmSpec" :loading="chatLoading">
                ✅ 确认需求，开始生成
              </el-button>
              <el-button type="primary" @click="handleChatSend" :loading="chatLoading" :disabled="!userInput.trim()">
                发送
              </el-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 步骤 2: 规格确认（自动跳过，合并到步骤 1 的确认按钮） -->

      <!-- 步骤 2-3: 生成进度 -->
      <div v-if="wizardStep === 2" class="wizard-generating">
        <div class="gen-status">
          <el-icon class="gen-spinner" :size="32"><Loading /></el-icon>
          <h3>正在生成 Skill...</h3>
          <p class="gen-desc">AI 正在生成代码、验证语法、沙箱执行和质量评估</p>
        </div>
        <el-progress :percentage="genProgress" :stroke-width="12" style="margin: 20px 0" />
        <div class="gen-steps">
          <div v-for="(s, i) in genSteps" :key="i" :class="['gen-step', s.status]">
            <el-icon v-if="s.status === 'done'"><CircleCheck /></el-icon>
            <el-icon v-else-if="s.status === 'running'" class="is-loading"><Loading /></el-icon>
            <el-icon v-else><MoreFilled /></el-icon>
            <span>{{ s.label }}</span>
          </div>
        </div>
      </div>

      <!-- 步骤 3: 完成 -->
      <div v-if="wizardStep === 3" class="wizard-done">
        <el-result
          :icon="genResult?.success ? 'success' : 'error'"
          :title="genResult?.success ? '🎉 Skill 创建成功！' : '❌ 生成失败'"
          :sub-title="genResult?.success
            ? `工具 ID: ${genResult.skill_id} · 耗时 ${genResult.total_time}s · 评分 ${genResult.final_score ?? '-'}/10`
            : genResult?.error || '请重试或修改需求'"
        >
          <template #extra>
            <el-button v-if="genResult?.success" type="primary" @click="wizardVisible = false; loadSkills()">
              查看 Skill 列表
            </el-button>
            <el-button v-else @click="wizardStep = 0">返回修改需求</el-button>
            <el-button @click="wizardVisible = false">关闭</el-button>
          </template>
        </el-result>
      </div>
    </el-dialog>

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
            <el-button type="primary" size="small" @click="resumeSession(draft)">
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
    <el-dialog v-model="codeDialogVisible" :title="'源代码: ' + codeDialogTitle" width="700px" destroy-on-close>
      <el-input type="textarea" :model-value="codeContent" :rows="20" readonly style="font-family: monospace;" />
    </el-dialog>

    <!-- 测试结果对话框 -->
    <el-dialog v-model="testDialogVisible" title="🧪 测试结果" width="600px" destroy-on-close>
      <el-descriptions v-if="testResult" :column="1" border>
        <el-descriptions-item label="执行结果">
          <el-tag :type="testResult.success ? 'success' : 'danger'">{{ testResult.success ? '成功' : '失败' }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="耗时">{{ testResult.execution_time }}s</el-descriptions-item>
        <el-descriptions-item v-if="testResult.error" label="错误">
          <span style="color: var(--el-color-danger)">{{ testResult.error }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="输出">
          <pre style="max-height: 300px; overflow: auto; white-space: pre-wrap;">{{ JSON.stringify(testResult.output, null, 2) }}</pre>
        </el-descriptions-item>
      </el-descriptions>
      <div v-else style="text-align: center; padding: 40px">
        <el-icon class="is-loading" :size="24"><Loading /></el-icon>
        <p>测试执行中...</p>
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
        <el-progress :percentage="optimizeProgress" :stroke-width="12" style="margin: 20px 40px" />
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
import { ref, nextTick, onMounted, computed } from 'vue'
import { Plus, Refresh, User, MagicStick, Loading, CircleCheck, MoreFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'
import { skillGenerationApi } from '@/api/skillGeneration'
import type { ExternalSkill, BoundaryCheck, ConfirmResult, TestResult, ConversationRound, OptimizeResult, SessionDetail, HistorySection } from '@/api/skillGeneration'

marked.setOptions({ breaks: true, gfm: true })

const renderMarkdown = (content: string): string => {
  if (!content?.trim()) return ''
  try { return marked.parse(content) as string } catch { return content }
}

const formatTime = (t: string): string => {
  if (!t) return '-'
  try { return new Date(t).toLocaleString('zh-CN') } catch { return t }
}

// ==================== 状态 ====================

// 向导
const wizardVisible = ref(false)
const wizardStep = ref(0)
const creating = ref(false)

// 对话
interface ChatMsg { role: 'user' | 'ai'; content: string }
const chatMessages = ref<ChatMsg[]>([])
const chatLoading = ref(false)
const userInput = ref('')
const chatContainer = ref<HTMLElement | null>(null)
const sessionId = ref('')
const currentRound = ref(0)
const expectedRounds = ref(3)
const boundaryCheck = ref<BoundaryCheck | null>(null)
const boundaryWarning = computed(() => boundaryCheck.value && !boundaryCheck.value.within_boundary)
const canConfirm = computed(() => chatMessages.value.length >= 2)

// 生成进度
const genProgress = ref(0)
const genSteps = ref([
  { label: '生成代码', status: 'pending' },
  { label: '语法检查', status: 'pending' },
  { label: '安全扫描', status: 'pending' },
  { label: '沙箱执行', status: 'pending' },
  { label: '质量评估', status: 'pending' },
])
const genResult = ref<ConfirmResult | null>(null)

// Skill 列表
const skills = ref<ExternalSkill[]>([])
const listLoading = ref(false)
const filterStatus = ref('')

// 代码查看
const codeDialogVisible = ref(false)
const codeDialogTitle = ref('')
const codeContent = ref('')

// 测试
const testDialogVisible = ref(false)
const testResult = ref<TestResult | null>(null)

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

const scrollChat = () => {
  nextTick(() => {
    if (chatContainer.value) chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  })
}

/** 开始新创建 */
const startNewCreation = () => {
  wizardStep.value = 0
  chatMessages.value = []
  userInput.value = ''
  sessionId.value = ''
  currentRound.value = 0
  expectedRounds.value = 3
  boundaryCheck.value = null
  genResult.value = null
  genProgress.value = 0
  genSteps.value.forEach(s => s.status = 'pending')
  wizardVisible.value = true
}

/** 发送对话 */
const handleChatSend = async () => {
  const text = userInput.value?.trim()
  if (!text || chatLoading.value) return

  chatMessages.value.push({ role: 'user', content: text })
  userInput.value = ''
  scrollChat()
  chatLoading.value = true

  try {
    if (!sessionId.value) {
      const res = await skillGenerationApi.startSession({ description: text })
      sessionId.value = res.session_id
      currentRound.value = res.current_round
      expectedRounds.value = res.expected_rounds
      boundaryCheck.value = res.boundary_check
      chatMessages.value.push({ role: 'ai', content: res.ai_message })
    } else {
      const res = await skillGenerationApi.respondToSession(sessionId.value, text)
      currentRound.value = res.current_round
      expectedRounds.value = res.expected_rounds
      chatMessages.value.push({ role: 'ai', content: res.ai_message })
    }
    scrollChat()
  } catch (e: any) {
    const msg = e?.message || e?.response?.data?.message || '请求失败'
    ElMessage.error(msg)
    chatMessages.value.push({ role: 'ai', content: `❌ 出错了：${msg}` })
    scrollChat()
  } finally {
    chatLoading.value = false
  }
}

/** 确认规格并开始生成 */
const handleConfirmSpec = async () => {
  if (!sessionId.value) return
  chatLoading.value = true
  wizardStep.value = 2
  creating.value = true

  genSteps.value.forEach(s => s.status = 'pending')
  genProgress.value = 0
  const progressTimer = setInterval(() => {
    if (genProgress.value < 90) {
      genProgress.value += Math.random() * 15
      const thresholds = [10, 25, 45, 65, 80]
      thresholds.forEach((t, i) => {
        if (genProgress.value >= t && genSteps.value[i].status === 'pending') {
          genSteps.value[i].status = 'running'
        }
        if (i > 0 && genSteps.value[i].status === 'running') {
          genSteps.value[i - 1].status = 'done'
        }
      })
    }
  }, 800)

  try {
    const res = await skillGenerationApi.confirmSpec(sessionId.value)
    clearInterval(progressTimer)
    genProgress.value = 100
    genSteps.value.forEach(s => s.status = 'done')
    genResult.value = res
    wizardStep.value = 3
  } catch (e: any) {
    clearInterval(progressTimer)
    genResult.value = {
      status: 'failed', session_id: sessionId.value, skill_id: null,
      spec: null, success: false, total_rounds: 0, total_time: 0,
      final_score: null, error: e?.message || '生成失败'
    }
    wizardStep.value = 3
  } finally {
    chatLoading.value = false
    creating.value = false
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

/** 测试 Skill */
const handleTest = async (row: ExternalSkill) => {
  testResult.value = null
  testDialogVisible.value = true
  try {
    testResult.value = await skillGenerationApi.testSkill(row.tool_id)
  } catch (e: any) {
    testResult.value = {
      success: false, output: null, stdout: '', stderr: '',
      execution_time: 0, error: e?.message || '测试请求失败',
    }
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
      optimizeProgress.value += Math.random() * 12
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

/** 恢复草稿会话 */
const resumeSession = async (draft: SessionDetail) => {
  try {
    // 加载完整会话
    const session = await skillGenerationApi.getSession(draft.session_id)

    // 恢复向导状态
    sessionId.value = session.session_id
    currentRound.value = session.current_round
    expectedRounds.value = Math.max(3, session.rounds?.length || 0)
    boundaryCheck.value = session.boundary_check || null

    // 从 rounds 恢复聊天消息
    chatMessages.value = []
    for (const round of (session.rounds || [])) {
      chatMessages.value.push({ role: 'user', content: round.user_message })
      chatMessages.value.push({ role: 'ai', content: round.ai_message })
    }

    // 重置生成状态
    genResult.value = null
    genProgress.value = 0
    genSteps.value.forEach(s => s.status = 'pending')
    userInput.value = ''

    // 根据会话状态决定打开到哪一步
    if (session.status === 'confirmed') {
      wizardStep.value = 1  // 已确认，可直接查看规格或触发生成
    } else {
      wizardStep.value = 0  // 需求沟通中
    }

    wizardVisible.value = true
    scrollChat()
    ElMessage.success('已恢复草稿，可以继续完善需求')
  } catch (e: any) {
    ElMessage.error('恢复草稿失败: ' + (e?.message || ''))
  }
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

/* ========== 向导对话 ========== */
.wizard-chat {
  display: flex;
  flex-direction: column;
  height: 55vh;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
  margin-bottom: 12px;
}

.chat-msg {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;

  &.chat-user { flex-direction: row-reverse; }

  .msg-avatar {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    background: var(--el-color-primary-light-8);
    color: var(--el-color-primary);
    font-size: 16px;
  }

  &.chat-user .msg-avatar {
    background: var(--el-color-success-light-8);
    color: var(--el-color-success);
  }

  .msg-bubble {
    max-width: 80%;
    padding: 10px 14px;
    border-radius: 12px;
    background: var(--el-bg-color);
    border: 1px solid var(--el-border-color-lighter);
    line-height: 1.6;

    &.thinking {
      color: var(--el-text-color-secondary);
      font-style: italic;
    }
  }

  &.chat-user .msg-bubble {
    background: var(--el-color-primary-light-9);
    border-color: var(--el-color-primary-light-7);
  }
}

.msg-text {
  :deep(p) { margin: 0 0 4px; }
  :deep(ul), :deep(ol) { margin: 4px 0; padding-left: 20px; }
}

.dot-animation span {
  animation: blink 1.4s infinite both;
  &:nth-child(2) { animation-delay: 0.2s; }
  &:nth-child(3) { animation-delay: 0.4s; }
}
@keyframes blink { 0%, 80%, 100% { opacity: 0; } 40% { opacity: 1; } }

.chat-input {
  flex-shrink: 0;
}

.chat-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;

  .tip { color: var(--el-text-color-placeholder); font-size: 12px; }
}

/* ========== 生成进度 ========== */
.wizard-generating {
  text-align: center;
  padding: 20px 0;

  .gen-status h3 { margin: 12px 0 4px; }
  .gen-desc { color: var(--el-text-color-secondary); font-size: 13px; }
}

.gen-spinner { animation: spin 1.5s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.gen-steps {
  display: flex;
  justify-content: center;
  gap: 20px;
  margin-top: 16px;
}

.gen-step {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: var(--el-text-color-secondary);

  &.done { color: var(--el-color-success); }
  &.running { color: var(--el-color-primary); font-weight: 500; }
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

/* ========== 沟通记录 ========== */
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
</style>