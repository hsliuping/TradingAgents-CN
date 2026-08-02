<template>
  <div class="research-flow" :class="{ stuck: isStuck }" ref="flowRef">
    <div class="section-header">
      <div class="section-title">
        研究路径
        <span class="badge">{{ steps.length }} 步</span>
      </div>
      <div class="progress-summary">
        已完成 <b>{{ doneCount }}</b> / {{ steps.length }}
      </div>
    </div>
    <div class="flow-steps">
      <template v-for="(step, idx) in steps" :key="step.key">
        <div
          class="flow-step"
          :class="[step.status, { active: idx === activeIndex }]"
          @click="$emit('stepClick', step.key)"
        >
          <div class="flow-step-header">
            <div class="flow-step-num">{{ idx + 1 }}</div>
            <span class="flow-step-status" :class="`status-${step.status}`">{{ statusLabel(step.status) }}</span>
          </div>
          <div class="flow-step-title">{{ step.title }}</div>
          <div class="flow-step-desc">{{ step.desc }}</div>
        </div>
        <div v-if="idx < steps.length - 1" class="flow-arrow">→</div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'

type StepStatus = 'done' | 'active' | 'pending'

interface FlowStep {
  key: string
  title: string
  desc: string
  status: StepStatus
}

const props = defineProps<{
  steps: FlowStep[]
  activeKey?: string
}>()

defineEmits<{
  (e: 'stepClick', key: string): void
}>()

const flowRef = ref<HTMLElement | null>(null)
const isStuck = ref(false)

const activeIndex = computed(() => {
  if (!props.activeKey) return -1
  return props.steps.findIndex(s => s.key === props.activeKey)
})

const doneCount = computed(() => props.steps.filter(s => s.status === 'done').length)

function statusLabel(status: StepStatus): string {
  if (status === 'done') return '已完成'
  if (status === 'active') return '进行中'
  return '待使用'
}

function handleScroll() {
  if (!flowRef.value) return
  const rect = flowRef.value.getBoundingClientRect()
  // 当卡片顶部贴近视口顶部时，认为已吸附
  isStuck.value = rect.top <= 0
}

onMounted(() => {
  window.addEventListener('scroll', handleScroll, { passive: true })
  handleScroll()
})

onUnmounted(() => {
  window.removeEventListener('scroll', handleScroll)
})
</script>

<style scoped>
.research-flow {
  background: var(--el-bg-color, #fff);
  border-radius: 12px;
  padding: 16px 20px;
  margin-bottom: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  border: 1px solid #f1f5f9;
  position: sticky;
  top: 0;
  z-index: 100;
  transition: box-shadow 0.3s, border-radius 0.3s;
}

.research-flow.stuck {
  border-radius: 0 0 12px 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.section-title {
  font-size: 15px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 8px;
  color: #1e293b;
}

.section-title .badge {
  padding: 2px 8px;
  background: #f5f3ff;
  color: #6b5ce7;
  border-radius: 4px;
  font-size: 11px;
}

.progress-summary {
  font-size: 12px;
  color: #64748b;
}

.progress-summary b {
  color: #6b5ce7;
  font-weight: 700;
}

.flow-steps {
  display: flex;
  align-items: stretch;
  gap: 0;
}

.flow-step {
  flex: 1;
  min-width: 120px;
  padding: 10px;
  border-radius: 8px;
  background: #f8fafc;
  border: 1px solid #f1f5f9;
  cursor: pointer;
  transition: all 0.2s;
}

.flow-step:hover {
  border-color: #6b5ce7;
  background: #f5f3ff;
}

.flow-step.active {
  border-color: #6b5ce7;
  background: #f5f3ff;
  box-shadow: 0 0 0 2px rgba(107, 92, 231, 0.1);
}

.flow-step-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.flow-step-num {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #e2e8f0;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.flow-step.active .flow-step-num {
  background: #6b5ce7;
}

.flow-step.done .flow-step-num {
  background: #3b82f6;
}

.flow-step-status {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  font-weight: 600;
}

.status-done {
  background: #dbeafe;
  color: #3b82f6;
}

.status-active {
  background: #f5f3ff;
  color: #6b5ce7;
}

.status-pending {
  background: #f1f5f9;
  color: #94a3b8;
}

.flow-step-title {
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 2px;
  color: #1e293b;
}

.flow-step-desc {
  font-size: 10px;
  color: #64748b;
}

.flow-arrow {
  flex-shrink: 0;
  width: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  font-size: 16px;
}

@media (max-width: 1024px) {
  .flow-steps {
    flex-direction: column;
    gap: 8px;
  }
  .flow-arrow {
    transform: rotate(90deg);
    width: 100%;
    height: 20px;
  }
}
</style>
