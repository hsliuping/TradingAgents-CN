<template>
  <div class="skill-review-card">
    <div class="skill-review-header">
      <div class="header-title">
        <el-icon><MagicStick /></el-icon>
        <span>Skill 待审核</span>
        <el-tag v-if="pendingCount > 0" size="small" type="warning" effect="dark" round>
          {{ pendingCount }}
        </el-tag>
      </div>
      <div class="header-actions">
        <el-button
          link
          type="primary"
          size="small"
          :loading="loading"
          @click="loadReviews"
        >
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <div v-if="loading && !reviews.length" class="review-empty">
      <el-icon class="is-loading"><Loading /></el-icon>
      正在加载...
    </div>

    <div v-else-if="!reviews.length" class="review-empty">
      <el-icon><Box /></el-icon>
      <span>暂无待审核的 Skill</span>
    </div>

    <div v-else class="review-list">
      <div
        v-for="item in reviews"
        :key="item.review_id"
        class="review-item"
        :class="{ 'is-pending': item.status === 'pending_review', 'is-confirmed': item.status === 'confirmed_bound', 'is-rejected': item.status === 'rejected_unbound' }"
      >
        <div class="review-item-header">
          <div class="review-item-title">
            <strong>{{ item.display_name || item.tool_id }}</strong>
            <el-tag size="small" :type="getStatusTagType(item.status)" effect="plain">
              {{ getStatusLabel(item.status) }}
            </el-tag>
          </div>
          <div class="review-item-meta">
            <span v-if="item.source_label || item.source_path" class="meta-item">
              <el-icon><Position /></el-icon>
              {{ item.source_label || getSourceLabel(item.source_path) }}
            </span>
            <span v-if="item.target_agent_name || item.target_agent_id" class="meta-item">
              <el-icon><User /></el-icon>
              目标 Agent: {{ item.target_agent_name || item.target_agent_id }}
            </span>
            <span v-if="item.created_at" class="meta-item">
              <el-icon><Clock /></el-icon>
              {{ formatTime(item.created_at) }}
            </span>
          </div>
        </div>

        <div v-if="item.description" class="review-item-desc">
          {{ item.description }}
        </div>

        <div v-if="item.test_summary" class="review-item-test">
          <el-tag
            size="small"
            :type="item.test_summary.passed ? 'success' : 'danger'"
            effect="plain"
          >
            {{ item.test_summary.passed ? '测试通过' : '测试失败' }}
          </el-tag>
          <span v-if="item.test_summary.score !== undefined" class="test-score">
            得分: {{ item.test_summary.score.toFixed(1) }}
          </span>
          <span v-if="item.test_summary.error" class="test-error">
            {{ item.test_summary.error }}
          </span>
        </div>

        <div v-if="item.code_snippet" class="review-item-code">
          <div class="code-header">
            <span>代码预览</span>
            <el-button link size="small" type="primary" @click="viewFullCode(item)">
              <el-icon><View /></el-icon>
              查看完整代码
            </el-button>
          </div>
          <pre class="code-preview">{{ truncateCode(item.code_snippet, 300) }}</pre>
        </div>

        <div v-if="item.status === 'pending_review'" class="review-item-actions">
          <el-tooltip
            v-if="item.is_expired"
            content="审核请求已超过 24 小时，请重新生成后再审核"
            placement="top"
          >
            <el-button
              type="success"
              size="small"
              disabled
            >
              <el-icon><Check /></el-icon>
              确认绑定
            </el-button>
          </el-tooltip>
          <el-button
            v-else
            type="success"
            size="small"
            :loading="acting === item.review_id"
            @click="handleConfirm(item)"
          >
            <el-icon><Check /></el-icon>
            确认绑定
          </el-button>
          <el-button
            type="danger"
            size="small"
            plain
            :loading="acting === item.review_id"
            @click="handleReject(item)"
          >
            <el-icon><Close /></el-icon>
            拒绝
          </el-button>
        </div>

        <div v-if="item.status === 'pending_review' && item.is_expired" class="review-item-expired">
          <el-alert type="warning" :closable="false" show-icon>
            该 Skill 审核请求已过期（超过 24 小时），请重新生成后再审核。
          </el-alert>
        </div>

        <div v-if="item.status !== 'pending_review'" class="review-item-result">
          <div v-if="item.status === 'confirmed_bound'" class="result-success">
            <el-icon><CircleCheckFilled /></el-icon>
            <span>已确认绑定</span>
            <span v-if="item.review_note" class="result-note">{{ item.review_note }}</span>
          </div>
          <div v-else-if="item.status === 'rejected_unbound'" class="result-rejected">
            <el-icon><CircleCloseFilled /></el-icon>
            <span>已拒绝，Skill 留在工坊</span>
            <span v-if="item.review_note" class="result-note">{{ item.review_note }}</span>
          </div>
          <div v-if="item.binding_error" class="result-error">
            <el-alert type="error" :closable="false" show-icon>
              {{ item.binding_error }}
            </el-alert>
          </div>
        </div>
      </div>
    </div>

    <!-- 完整代码查看对话框 -->
    <el-dialog
      v-model="codeDialogVisible"
      :title="`Skill 代码：${currentCodeItem?.tool_id || ''}`"
      width="80%"
      top="5vh"
      destroy-on-close
    >
      <div v-if="currentCodeItem" class="full-code-body">
        <div class="full-code-meta">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="Skill ID">{{ currentCodeItem.tool_id }}</el-descriptions-item>
            <el-descriptions-item label="名称">{{ currentCodeItem.display_name }}</el-descriptions-item>
            <el-descriptions-item label="来源">{{ currentCodeItem.source_label || currentCodeItem.source_path }}</el-descriptions-item>
            <el-descriptions-item label="状态">{{ getStatusLabel(currentCodeItem.status) }}</el-descriptions-item>
          </el-descriptions>
        </div>
        <pre class="full-code-content">{{ currentCodeItem.code_snippet }}</pre>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Check,
  Clock,
  Close,
  Box,
  Loading,
  MagicStick,
  Position,
  Refresh,
  User,
  View,
  CircleCheckFilled,
  CircleCloseFilled,
} from '@element-plus/icons-vue'
import agentWorkshopApi, {
  type SkillReviewItem,
} from '@/api/agentWorkshop'

const props = defineProps<{
  /** 会话 ID（Agent 工坊会话或 AI 工作流会话） */
  sessionId: string
  /** 来源筛选：agent_workshop / ai_workflow，留空返回全部 */
  sourcePath?: string
  /** 是否自动加载（默认 true） */
  autoLoad?: boolean
}>()

const emit = defineEmits<{
  (e: 'confirmed', item: SkillReviewItem): void
  (e: 'rejected', item: SkillReviewItem): void
  (e: 'updated'): void
}>()

const loading = ref(false)
const acting = ref<string>('')
const reviews = ref<SkillReviewItem[]>([])
const codeDialogVisible = ref(false)
const currentCodeItem = ref<SkillReviewItem | null>(null)

const pendingCount = computed(() =>
  reviews.value.filter(r => r.status === 'pending_review').length
)

const loadReviews = async () => {
  if (!props.sessionId) {
    reviews.value = []
    return
  }
  loading.value = true
  try {
    const result = await agentWorkshopApi.listSkillReviews(
      props.sessionId,
      props.sourcePath,
    )
    reviews.value = result.items || []
  } catch (err: any) {
    ElMessage.error(err?.message || '加载 Skill 待审核列表失败')
    reviews.value = []
  } finally {
    loading.value = false
  }
}

const handleConfirm = async (item: SkillReviewItem) => {
  try {
    await ElMessageBox.confirm(
      `确认将 Skill "${item.display_name || item.tool_id}" 绑定到 Agent？\n\n绑定后该 Skill 将成为 Agent 的内置工具。`,
      '确认绑定 Skill',
      {
        confirmButtonText: '确认绑定',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }

  acting.value = item.review_id
  try {
    const result = await agentWorkshopApi.confirmSkillReview(
      props.sessionId,
      item.tool_id,
      { note: '前端确认绑定' },
    )
    if (result.status === 'confirmed_bound') {
      ElMessage.success(`Skill "${item.display_name}" 已成功绑定到 Agent`)
      // 更新本地状态
      const idx = reviews.value.findIndex(r => r.review_id === item.review_id)
      if (idx >= 0) {
        reviews.value[idx] = { ...reviews.value[idx], status: 'confirmed_bound', binding_error: undefined }
      }
      emit('confirmed', item)
      emit('updated')
    } else if (result.status === 'expired') {
      ElMessage.warning(result.message || '该 Skill 审核请求已过期，请重新生成后再审核')
      const idx = reviews.value.findIndex(r => r.review_id === item.review_id)
      if (idx >= 0) {
        reviews.value[idx] = { ...reviews.value[idx], is_expired: true }
      }
    } else if (result.status === 'binding_failed' || result.binding_result?.error) {
      const errorMsg = result.binding_result?.error || result.error || '未知错误'
      ElMessage.error(`绑定失败：${errorMsg}`)
      const idx = reviews.value.findIndex(r => r.review_id === item.review_id)
      if (idx >= 0) {
        reviews.value[idx] = { ...reviews.value[idx], binding_error: errorMsg }
      }
    } else {
      ElMessage.warning(result.message || '绑定状态未知，请刷新查看')
      await loadReviews()
    }
  } catch (err: any) {
    ElMessage.error(err?.message || '确认绑定失败')
    // 刷新以获取最新状态
    await loadReviews()
  } finally {
    acting.value = ''
  }
}

const handleReject = async (item: SkillReviewItem) => {
  let note = ''
  try {
    const { value } = await ElMessageBox.prompt(
      `拒绝绑定 Skill "${item.display_name || item.tool_id}"？\n\n拒绝后该 Skill 将留在 Skill 工坊（状态: unbound），不绑定到 Agent。`,
      '拒绝绑定 Skill',
      {
        confirmButtonText: '确认拒绝',
        cancelButtonText: '取消',
        type: 'warning',
        inputPlaceholder: '请输入拒绝原因（可选）',
        inputType: 'textarea',
      },
    )
    note = value || ''
  } catch {
    return
  }

  acting.value = item.review_id
  try {
    const result = await agentWorkshopApi.rejectSkillReview(
      props.sessionId,
      item.tool_id,
      { note: note || '前端拒绝绑定' },
    )
    if (result.status === 'rejected_unbound') {
      ElMessage.success(`Skill "${item.display_name}" 已拒绝，留在工坊`)
      const idx = reviews.value.findIndex(r => r.review_id === item.review_id)
      if (idx >= 0) {
        reviews.value[idx] = { ...reviews.value[idx], status: 'rejected_unbound', review_note: note }
      }
      emit('rejected', item)
      emit('updated')
    } else {
      ElMessage.warning(result.message || '拒绝状态未知，请刷新查看')
      await loadReviews()
    }
  } catch (err: any) {
    ElMessage.error(err?.message || '拒绝绑定失败')
    await loadReviews()
  } finally {
    acting.value = ''
  }
}

const viewFullCode = (item: SkillReviewItem) => {
  currentCodeItem.value = item
  codeDialogVisible.value = true
}

const truncateCode = (code: string, max: number) => {
  if (!code) return ''
  if (code.length <= max) return code
  return code.slice(0, max) + '\n... (完整代码请点击"查看完整代码")'
}

const formatTime = (iso: string) => {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  } catch {
    return iso
  }
}

const getStatusLabel = (status: string) => {
  const map: Record<string, string> = {
    pending_review: '待审核',
    confirmed_bound: '已绑定',
    rejected_unbound: '已拒绝',
  }
  return map[status] || status
}

const getSourceLabel = (sourcePath?: string) => {
  const map: Record<string, string> = {
    agent_workshop: 'Agent 工坊自动补齐',
    ai_workflow: 'AI 工作流批量生成',
  }
  return map[sourcePath || ''] || sourcePath || '未知来源'
}

const getStatusTagType = (status: string): 'warning' | 'success' | 'info' | 'danger' => {
  const map: Record<string, 'warning' | 'success' | 'info' | 'danger'> = {
    pending_review: 'warning',
    confirmed_bound: 'success',
    rejected_unbound: 'info',
  }
  return map[status] || 'info'
}

watch(() => props.sessionId, (newId) => {
  if (newId && props.autoLoad !== false) {
    loadReviews()
  } else {
    reviews.value = []
  }
})

watch(() => props.sourcePath, () => {
  if (props.sessionId && props.autoLoad !== false) {
    loadReviews()
  }
})

onMounted(() => {
  if (props.autoLoad !== false) {
    loadReviews()
  }
})

defineExpose({
  loadReviews,
})
</script>

<style scoped lang="scss">
.skill-review-card {
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  padding: 12px;
  background: var(--el-bg-color);
}

.skill-review-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;

  .header-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    font-weight: 600;
    color: var(--el-text-color-primary);

    .el-icon {
      color: var(--el-color-primary);
    }
  }
}

.review-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 24px;
  color: var(--el-text-color-secondary);
  font-size: 13px;

  .el-icon {
    font-size: 16px;
  }
}

.review-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.review-item {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  padding: 10px 12px;
  background: var(--el-fill-color-blank);
  transition: all 0.2s;

  &:hover {
    border-color: var(--el-border-color);
  }

  &.is-pending {
    border-left: 3px solid var(--el-color-warning);
  }

  &.is-confirmed {
    border-left: 3px solid var(--el-color-success);
    opacity: 0.85;
  }

  &.is-rejected {
    border-left: 3px solid var(--el-color-info);
    opacity: 0.7;
  }
}

.review-item-header {
  margin-bottom: 6px;

  .review-item-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;

    strong {
      color: var(--el-text-color-primary);
    }
  }

  .review-item-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    margin-top: 4px;
    font-size: 12px;
    color: var(--el-text-color-secondary);

    .meta-item {
      display: flex;
      align-items: center;
      gap: 3px;
    }
  }
}

.review-item-desc {
  font-size: 12px;
  color: var(--el-text-color-regular);
  margin: 4px 0 6px;
  line-height: 1.5;
}

.review-item-test {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 6px 0;
  font-size: 12px;

  .test-score {
    color: var(--el-color-primary);
  }

  .test-error {
    color: var(--el-color-danger);
  }
}

.review-item-code {
  margin: 8px 0;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 4px;
  overflow: hidden;

  .code-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 4px 8px;
    background: var(--el-fill-color-light);
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }

  .code-preview {
    padding: 8px;
    margin: 0;
    font-family: 'Cascadia Code', 'Fira Code', Consolas, monospace;
    font-size: 11px;
    line-height: 1.5;
    color: var(--el-text-color-regular);
    background: var(--el-fill-color-blank);
    max-height: 180px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-all;
  }
}

.review-item-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.review-item-expired {
  margin-top: 8px;
}

.review-item-result {
  margin-top: 8px;
  font-size: 12px;

  .result-success,
  .result-rejected {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 0;
  }

  .result-success {
    color: var(--el-color-success);
  }

  .result-rejected {
    color: var(--el-text-color-secondary);
  }

  .result-note {
    color: var(--el-text-color-secondary);
    font-size: 11px;
    margin-left: 8px;
  }

  .result-error {
    margin-top: 6px;
  }
}

.full-code-body {
  .full-code-meta {
    margin-bottom: 12px;
  }

  .full-code-content {
    padding: 12px;
    margin: 0;
    font-family: 'Cascadia Code', 'Fira Code', Consolas, monospace;
    font-size: 12px;
    line-height: 1.5;
    color: var(--el-text-color-regular);
    background: var(--el-fill-color-light);
    border-radius: 4px;
    max-height: 60vh;
    overflow: auto;
    white-space: pre-wrap;
    word-break: break-all;
  }
}
</style>
