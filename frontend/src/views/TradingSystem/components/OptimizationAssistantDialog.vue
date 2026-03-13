<template>
  <el-dialog
    v-model="dialogVisible"
    title="AI优化助手"
    width="920px"
    :close-on-click-modal="false"
  >
    <div class="optimization-layout">
      <el-card shadow="never" class="optimization-panel">
        <template #header>
          <div class="panel-header">
            <span>讨论目标</span>
          </div>
        </template>

        <el-alert
          type="info"
          :closable="false"
          title="先问清楚，再选择性应用"
        >
          <p>你可以追问某条建议到底会提升哪些维度，AI 会返回说明和可勾选的结构化修改。</p>
        </el-alert>

        <el-form label-position="top" class="optimization-form">
          <el-form-item label="本轮重点建议">
            <el-checkbox-group v-model="selectedSuggestions" class="suggestion-checklist">
              <el-checkbox
                v-for="(suggestion, index) in availableSuggestions"
                :key="`${index}-${suggestion}`"
                :value="suggestion"
                class="suggestion-checkbox"
              >
                {{ suggestion }}
              </el-checkbox>
            </el-checkbox-group>
            <div v-if="!availableSuggestions.length" class="empty-tip">当前评估暂无明确建议，可直接输入追问。</div>
          </el-form-item>

          <el-form-item label="想和 AI 讨论什么？">
            <el-input
              v-model="userQuestion"
              type="textarea"
              :rows="4"
              placeholder="例如：如果补充移动止盈和排除条件，分别会提升哪些维度？请给我偏稳健的可执行方案。"
            />
          </el-form-item>
        </el-form>
      </el-card>

      <el-card shadow="never" class="optimization-panel">
        <template #header>
          <div class="panel-header">
            <span>讨论结果</span>
          </div>
        </template>

        <div class="message-list">
          <div
            v-for="(message, index) in messages"
            :key="`${message.role}-${index}`"
            class="message-item"
            :class="message.role"
          >
            <div class="message-role">{{ message.role === 'user' ? '你' : 'AI' }}</div>
            <div class="message-content">{{ message.content }}</div>
          </div>
          <div v-if="!messages.length" class="empty-tip">你可以先讨论，也可以直接应用已勾选建议。</div>
        </div>

        <div v-if="discussionResult?.updates?.length" class="candidate-section">
          <div class="candidate-header">可选择应用的修改</div>
          <el-checkbox-group v-model="selectedUpdateIds" class="candidate-list">
            <el-card
              v-for="item in discussionResult.updates"
              :key="item.id"
              shadow="hover"
              class="candidate-card"
            >
              <div class="candidate-top">
                <el-checkbox :value="item.id">{{ item.title }}</el-checkbox>
                <el-tag size="small">{{ moduleLabelMap[item.module] || item.module }}</el-tag>
              </div>
              <div class="candidate-summary">{{ item.summary }}</div>
              <div v-if="item.reason" class="candidate-reason">{{ item.reason }}</div>
              <div v-if="item.expected_improvements.length" class="candidate-tags">
                <el-tag v-for="label in item.expected_improvements" :key="label" size="small" type="success" effect="plain">
                  {{ label }}
                </el-tag>
              </div>
            </el-card>
          </el-checkbox-group>
        </div>
      </el-card>
    </div>

    <template #footer>
      <el-button @click="dialogVisible = false">关闭</el-button>
      <el-button type="primary" plain :loading="discussing" @click="handleDiscuss">
        继续讨论
      </el-button>
      <el-button
        type="primary"
        :disabled="!canApplyDirectly"
        :loading="applying || generatingUpdates"
        @click="handleApply"
      >
        {{ selectedUpdates.length ? '应用所选修改' : '直接应用建议' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  discussTradingPlanOptimization,
  type OptimizationChatMessage,
  type OptimizationDiscussionResult,
  type OptimizationSuggestionUpdate,
  type TradingPlanEvaluation
} from '@/api/tradingSystem'

const props = defineProps<{
  modelValue: boolean
  planData: Record<string, any>
  evaluationResult: TradingPlanEvaluation | null
  applying?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'apply', updates: OptimizationSuggestionUpdate[]): void
}>()

const moduleLabelMap: Record<string, string> = {
  stock_selection: '选股规则',
  timing: '择时规则',
  position: '仓位规则',
  holding: '持仓规则',
  risk_management: '风险管理',
  review: '复盘规则',
  discipline: '纪律规则'
}

const discussing = ref(false)
const generatingUpdates = ref(false)
const userQuestion = ref('')
const selectedSuggestions = ref<string[]>([])
const selectedUpdateIds = ref<string[]>([])
const discussionResult = ref<OptimizationDiscussionResult | null>(null)
const messages = ref<OptimizationChatMessage[]>([])

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value)
})

const availableSuggestions = computed(() => props.evaluationResult?.suggestions || [])
const applying = computed(() => Boolean(props.applying))
const canApplyDirectly = computed(() => selectedUpdates.value.length > 0 || selectedSuggestions.value.length > 0)
const selectedUpdates = computed(() => {
  const items = discussionResult.value?.updates || []
  return items.filter(item => selectedUpdateIds.value.includes(item.id))
})

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) {
      return
    }

    selectedSuggestions.value = [...availableSuggestions.value]
    selectedUpdateIds.value = []
    discussionResult.value = null
    userQuestion.value = ''
    messages.value = props.evaluationResult
      ? [{ role: 'assistant', content: `我已经读取这份评估结果。你可以继续追问某条建议会提升哪些维度，我会给出可直接应用的修改候选。当前等级：${props.evaluationResult.grade}` }]
      : [{ role: 'assistant', content: '你可以直接描述想优化的方向，我会拆解影响点并生成可选修改。' }]
  }
)

async function handleDiscuss() {
  if (!userQuestion.value.trim() && selectedSuggestions.value.length === 0) {
    ElMessage.warning('请至少输入一个问题或勾选一条建议')
    return
  }

  const question = userQuestion.value.trim()
  if (question) {
    messages.value.push({ role: 'user', content: question })
  }

  discussing.value = true
  try {
    const discussion = await requestDiscussion(question, messages.value)
    if (discussion) {
      discussionResult.value = discussion
      messages.value.push({ role: 'assistant', content: discussion.reply })
      selectedUpdateIds.value = (discussion.updates || []).map(item => item.id)
      userQuestion.value = ''
    }
  } catch (error: any) {
    console.error('优化讨论失败:', error)
    ElMessage.error(error.response?.data?.message || error.message || '讨论失败，请稍后重试')
  } finally {
    discussing.value = false
  }
}

async function handleApply() {
  if (selectedUpdates.value.length) {
    emit('apply', selectedUpdates.value)
    return
  }

  if (!selectedSuggestions.value.length) {
    ElMessage.warning('请先勾选至少一条建议')
    return
  }

  generatingUpdates.value = true
  try {
    const discussion = await requestDiscussion(
      '请不要展开讨论，直接基于我勾选的建议生成可应用的结构化修改候选，并尽量覆盖最值得优先落地的改动。',
      messages.value
    )

    if (!discussion) {
      return
    }

    discussionResult.value = discussion
    messages.value.push({ role: 'assistant', content: discussion.reply })
    selectedUpdateIds.value = (discussion.updates || []).map(item => item.id)

    if (!discussion.updates?.length) {
      ElMessage.warning('当前建议暂未生成可直接应用的修改，请先继续讨论细化')
      return
    }

    emit('apply', discussion.updates)
  } catch (error: any) {
    console.error('直接应用建议失败:', error)
    ElMessage.error(error.response?.data?.message || error.message || '直接应用失败，请稍后重试')
  } finally {
    generatingUpdates.value = false
  }
}

async function requestDiscussion(question: string, history: OptimizationChatMessage[]) {
  const res = await discussTradingPlanOptimization({
    trading_plan_data: props.planData,
    evaluation_result: props.evaluationResult,
    user_question: question,
    selected_suggestions: selectedSuggestions.value,
    conversation_history: history
  })

  if (res.success && res.data?.discussion) {
    return res.data.discussion
  }

  ElMessage.error(res.message || '生成修改建议失败')
  return null
}
</script>

<style scoped lang="scss">
.optimization-layout {
  display: grid;
  grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
  gap: 16px;
}

.optimization-panel {
  min-height: 520px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
}

.optimization-form {
  margin-top: 16px;
}

.suggestion-checklist {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.suggestion-checkbox {
  margin-right: 0;
  white-space: normal;
  line-height: 1.6;
}

.message-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 260px;
  overflow: auto;
  padding-right: 4px;
}

.message-item {
  padding: 12px 14px;
  border-radius: 12px;
  background: #f5f7fa;
}

.message-item.user {
  background: #ecf5ff;
}

.message-role {
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
}

.message-content {
  white-space: pre-wrap;
  line-height: 1.7;
  color: #303133;
}

.candidate-section {
  margin-top: 20px;
  border-top: 1px solid #ebeef5;
  padding-top: 16px;
}

.candidate-header {
  font-weight: 600;
  margin-bottom: 12px;
}

.candidate-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.candidate-card {
  border-color: #e4e7ed;
}

.candidate-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.candidate-summary {
  margin-top: 10px;
  line-height: 1.6;
  color: #303133;
}

.candidate-reason {
  margin-top: 8px;
  color: #606266;
  line-height: 1.6;
}

.candidate-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.empty-tip {
  color: #909399;
  font-size: 13px;
  line-height: 1.6;
}

@media (max-width: 900px) {
  .optimization-layout {
    grid-template-columns: 1fr;
  }

  .optimization-panel {
    min-height: auto;
  }
}
</style>