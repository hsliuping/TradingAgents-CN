<template>
  <el-card shadow="never" class="growth-panel">
    <template #header>
      <div class="card-header">
        <div class="header-main">
          <el-icon><Collection /></el-icon>
          <span>{{ title }}</span>
        </div>
        <el-button v-if="taskId" size="small" @click="refreshGrowthContext" :loading="growthLoading">
          刷新成长项
        </el-button>
      </div>
    </template>

    <div class="growth-summary-bar">
      <el-tag type="info">候选记忆 {{ growthSummary.memory_items_count }}</el-tag>
      <el-tag type="warning">成长建议 {{ growthSummary.suggestions_count }}</el-tag>
    </div>

    <el-skeleton :loading="growthLoading" animated :rows="4">
      <template #default>
        <template v-if="taskId">
          <el-tabs class="growth-tabs">
            <el-tab-pane :label="`成长记忆 (${growthMemories.length})`" name="memories">
              <div v-if="growthMemories.length" class="growth-list">
                <div v-for="item in growthMemories" :key="item.memory_id" class="growth-item">
                  <div class="growth-item-header">
                    <div class="growth-item-title-row">
                      <h4>{{ item.title }}</h4>
                      <div class="growth-item-tags">
                        <el-tag size="small" :type="memoryStatusTagType(item.status)">
                          {{ GrowthMemoryStatusNames[item.status] || item.status }}
                        </el-tag>
                        <el-tag size="small" effect="plain">
                          {{ GrowthMemoryScopeNames[item.scope] || item.scope }}
                        </el-tag>
                        <el-tag size="small" effect="plain">置信度 {{ formatConfidence(item.confidence) }}</el-tag>
                      </div>
                    </div>
                    <div v-if="item.status === GrowthMemoryStatus.PENDING" class="growth-actions">
                      <el-button size="small" type="primary" @click="handleApproveMemory(item.memory_id)">批准</el-button>
                      <el-button size="small" @click="handleRejectMemory(item.memory_id)">拒绝</el-button>
                    </div>
                  </div>
                  <p v-if="item.summary" class="growth-summary-text">{{ item.summary }}</p>
                  <el-collapse>
                    <el-collapse-item title="查看完整内容" :name="item.memory_id">
                      <div class="growth-content">{{ item.content }}</div>
                    </el-collapse-item>
                  </el-collapse>
                  <div v-if="item.evidence_refs?.length" class="growth-evidence">
                    <span class="growth-meta-label">证据来源：</span>
                    <el-tag v-for="ref in item.evidence_refs" :key="`${ref.type}-${ref.id}`" size="small" effect="plain">
                      {{ ref.label || ref.type }}: {{ ref.id }}
                    </el-tag>
                  </div>
                </div>
              </div>
              <el-empty v-else description="当前任务还没有成长记忆" />
            </el-tab-pane>

            <el-tab-pane :label="`成长建议 (${growthSuggestions.length})`" name="suggestions">
              <div v-if="growthSuggestions.length" class="growth-list">
                <div v-for="item in growthSuggestions" :key="item.suggestion_id" class="growth-item suggestion-item">
                  <div class="growth-item-header">
                    <div class="growth-item-title-row">
                      <h4>{{ item.title }}</h4>
                      <div class="growth-item-tags">
                        <el-tag size="small" :type="suggestionStatusTagType(item.status)">
                          {{ GrowthSuggestionStatusNames[item.status] || item.status }}
                        </el-tag>
                        <el-tag size="small" effect="plain">{{ item.suggestion_type }}</el-tag>
                        <el-tag size="small" effect="plain">置信度 {{ formatConfidence(item.confidence) }}</el-tag>
                      </div>
                    </div>
                    <div v-if="item.status === GrowthSuggestionStatus.PENDING" class="growth-actions">
                      <el-button size="small" type="primary" @click="handleAcceptSuggestion(item.suggestion_id)">接受</el-button>
                      <el-button size="small" @click="handleDismissSuggestion(item.suggestion_id)">忽略</el-button>
                    </div>
                    <div v-else-if="item.activation_result?.session_id" class="growth-actions">
                      <el-button size="small" type="success" plain @click="openWorkflowOptimization(item)">
                        打开优化会话
                      </el-button>
                    </div>
                  </div>
                  <p class="growth-summary-text">{{ item.summary }}</p>
                  <el-collapse v-if="item.suggested_action">
                    <el-collapse-item title="查看建议动作" :name="item.suggestion_id">
                      <pre class="json-content">{{ JSON.stringify(item.suggested_action, null, 2) }}</pre>
                    </el-collapse-item>
                  </el-collapse>
                  <div v-if="item.source_refs?.length" class="growth-evidence">
                    <span class="growth-meta-label">来源：</span>
                    <el-tag v-for="ref in item.source_refs" :key="`${ref.type}-${ref.id}`" size="small" effect="plain">
                      {{ ref.label || ref.type }}: {{ ref.id }}
                    </el-tag>
                  </div>
                </div>
              </div>
              <el-empty v-else description="当前任务还没有成长建议" />
            </el-tab-pane>
          </el-tabs>
        </template>
        <el-empty v-else description="当前页面没有关联任务，无法加载成长上下文" />
      </template>
    </el-skeleton>
  </el-card>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Collection } from '@element-plus/icons-vue'
import {
  getTaskGrowthContext,
  approveGrowthMemory,
  rejectGrowthMemory,
  acceptGrowthSuggestion,
  dismissGrowthSuggestion,
  GrowthMemoryStatus,
  GrowthSuggestionStatus,
  GrowthMemoryStatusNames,
  GrowthSuggestionStatusNames,
  GrowthMemoryScopeNames,
  type TaskGrowthContextPayload,
  type GrowthMemoryItem,
  type GrowthSuggestion
} from '@/api/workflowGrowth'

const props = withDefaults(defineProps<{
  taskId?: string | null
  title?: string
  initialContext?: TaskGrowthContextPayload | null
  closeOnNavigate?: boolean
}>(), {
  title: '受控成长',
  initialContext: null,
  closeOnNavigate: false
})

const emit = defineEmits<{
  (e: 'navigated'): void
  (e: 'updated', context: TaskGrowthContextPayload | null): void
}>()

const router = useRouter()
const growthLoading = ref(false)
const growthContext = ref<TaskGrowthContextPayload | null>(props.initialContext)

const growthMemories = computed<GrowthMemoryItem[]>(() => growthContext.value?.memory_items || [])
const growthSuggestions = computed<GrowthSuggestion[]>(() => growthContext.value?.suggestions || [])
const growthSummary = computed(() => ({
  memory_items_count: growthContext.value?.summary?.memory_items_count || 0,
  suggestions_count: growthContext.value?.summary?.suggestions_count || 0
}))

const refreshGrowthContext = async () => {
  if (!props.taskId) {
    growthContext.value = props.initialContext
    return
  }

  growthLoading.value = true
  try {
    const res = await getTaskGrowthContext(props.taskId)
    growthContext.value = (res as any)?.data?.data || (res as any)?.data || null
    emit('updated', growthContext.value)
  } catch (error: any) {
    if ((error?.message || '').includes('404')) {
      growthContext.value = props.initialContext
      emit('updated', growthContext.value)
      return
    }
    console.error('[TaskGrowthPanel] 获取成长上下文失败:', error)
    ElMessage.error(error?.message || '获取成长上下文失败')
  } finally {
    growthLoading.value = false
  }
}

const handleApproveMemory = async (memoryId: string) => {
  try {
    await approveGrowthMemory(memoryId)
    ElMessage.success('已批准成长记忆')
    await refreshGrowthContext()
  } catch (error: any) {
    ElMessage.error(error?.message || '批准成长记忆失败')
  }
}

const handleRejectMemory = async (memoryId: string) => {
  try {
    await rejectGrowthMemory(memoryId)
    ElMessage.success('已拒绝成长记忆')
    await refreshGrowthContext()
  } catch (error: any) {
    ElMessage.error(error?.message || '拒绝成长记忆失败')
  }
}

const handleAcceptSuggestion = async (suggestionId: string) => {
  try {
    const res = await acceptGrowthSuggestion(suggestionId)
    const acceptedSuggestion = (res as any)?.data?.data || (res as any)?.data || null
    ElMessage.success('已接受成长建议')
    await refreshGrowthContext()

    if (acceptedSuggestion?.activation_result?.session_id) {
      openWorkflowOptimization(acceptedSuggestion)
    }
  } catch (error: any) {
    ElMessage.error(error?.message || '接受成长建议失败')
  }
}

const handleDismissSuggestion = async (suggestionId: string) => {
  try {
    await dismissGrowthSuggestion(suggestionId)
    ElMessage.success('已忽略成长建议')
    await refreshGrowthContext()
  } catch (error: any) {
    ElMessage.error(error?.message || '忽略成长建议失败')
  }
}

const formatConfidence = (value?: number) => {
  if (value === undefined || value === null || Number.isNaN(Number(value))) return '-'
  return `${Math.round(Number(value) * 100)}%`
}

const memoryStatusTagType = (status: string) => {
  if (status === GrowthMemoryStatus.APPROVED) return 'success'
  if (status === GrowthMemoryStatus.REJECTED) return 'danger'
  if (status === GrowthMemoryStatus.PENDING) return 'warning'
  return 'info'
}

const suggestionStatusTagType = (status: string) => {
  if (status === GrowthSuggestionStatus.ACCEPTED) return 'success'
  if (status === GrowthSuggestionStatus.DISMISSED) return 'info'
  if (status === GrowthSuggestionStatus.PENDING) return 'warning'
  return 'info'
}

const openWorkflowOptimization = (suggestion: GrowthSuggestion) => {
  const sessionId = suggestion.activation_result?.session_id
  if (!sessionId) {
    ElMessage.warning('当前建议还没有可打开的优化会话')
    return
  }

  router.push({
    name: 'WorkflowGenerationCreate',
    query: { session_id: sessionId }
  })

  if (props.closeOnNavigate) {
    emit('navigated')
  }
}

watch(
  () => props.initialContext,
  (value) => {
    if (value) {
      growthContext.value = value
    }
  },
  { immediate: true }
)

watch(
  () => props.taskId,
  () => {
    void refreshGrowthContext()
  },
  { immediate: true }
)
</script>

<style scoped lang="scss">
.growth-panel {
  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    font-weight: 600;
    font-size: 16px;
    width: 100%;
  }

  .header-main {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .growth-summary-bar {
    display: flex;
    gap: 8px;
    margin-bottom: 16px;
  }

  .growth-tabs {
    :deep(.el-tabs__content) {
      overflow: visible;
    }
  }

  .growth-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .growth-item {
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 14px 16px;
    background: linear-gradient(180deg, #ffffff 0%, #fafafa 100%);
  }

  .growth-item-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 8px;
  }

  .growth-item-title-row {
    display: flex;
    flex-direction: column;
    gap: 8px;

    h4 {
      margin: 0;
      font-size: 15px;
      font-weight: 600;
      color: #1f2937;
    }
  }

  .growth-item-tags,
  .growth-actions,
  .growth-evidence {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .growth-summary-text {
    margin: 0 0 10px;
    color: #4b5563;
    line-height: 1.7;
  }

  .growth-content {
    white-space: pre-wrap;
    line-height: 1.7;
    color: #374151;
  }

  .growth-meta-label {
    color: #6b7280;
    font-size: 13px;
    line-height: 24px;
  }

  .json-content {
    background-color: #f5f7fa;
    padding: 12px;
    border-radius: 4px;
    font-size: 12px;
    line-height: 1.6;
    overflow-x: auto;
    max-height: 320px;
    overflow-y: auto;
    margin: 0;
  }
}
</style>