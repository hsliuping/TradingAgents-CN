<template>
  <div class="assistant-hero">
    <div class="assistant-hero-left">
      <div class="assistant-hero-header">
        <div class="assistant-avatar">🤖</div>
        <div>
          <div class="assistant-hero-title">智能研究助手</div>
          <div class="assistant-hero-subtitle">
            正在解读：{{ code }} {{ stockName || '-' }} · {{ loadedText }}
          </div>
        </div>
      </div>
      <div class="assistant-hero-prompt">
        我已整合该股票的 <strong>单股分析</strong>、<strong>持仓分析</strong>、<strong>交易复盘</strong>、<strong>基本面</strong> 和 <strong>K线走势</strong>，可以为你全景解读。点击右侧任一问题开始研究：
      </div>
    </div>
    <div class="assistant-quick-grid">
      <button
        v-for="q in quickQuestions"
        :key="q.key"
        class="assistant-quick-btn"
        @click="$emit('ask', q.prompt)"
      >
        <span>{{ q.icon }}</span>
        <span>{{ q.label }}</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  code: string
  stockName: string
  hasAnalysis: boolean
  hasPosition: boolean
  hasReview: boolean
  hasFundamentals: boolean
  hasKline: boolean
}>()

defineEmits<{
  (e: 'ask', prompt: string): void
}>()

const loadedText = computed(() => {
  const loaded: string[] = []
  if (props.hasKline) loaded.push('K线')
  if (props.hasAnalysis) loaded.push('单股分析')
  if (props.hasPosition) loaded.push('持仓')
  if (props.hasReview) loaded.push('复盘')
  if (props.hasFundamentals) loaded.push('基本面')
  return loaded.length ? `已加载 ${loaded.join('·')}` : '正在加载数据'
})

const quickQuestions = [
  { key: 'overview', icon: '🔗', label: '全景解读', prompt: '帮我全景分析这只股票，从分析结果、持仓、复盘整体怎么看？' },
  { key: 'conclusion', icon: '📋', label: '分析结论', prompt: '最近一次单股分析的核心结论是什么？' },
  { key: 'position', icon: '💼', label: '持仓视角', prompt: '结合我的持仓和复盘，下一步重点跟踪什么？' },
  { key: 'risk', icon: '⚠️', label: '风险评估', prompt: '当前估值和基本面是否匹配？有哪些风险？' },
]
</script>

<style scoped>
.assistant-hero {
  background: linear-gradient(135deg, #6b5ce7 0%, #8b5cf6 50%, #a855f7 100%);
  border-radius: 12px;
  padding: 20px;
  color: #fff;
  position: relative;
  overflow: hidden;
  box-shadow: 0 8px 24px rgba(107, 92, 231, 0.25);
  margin-bottom: 16px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  align-items: center;
}

.assistant-hero::before {
  content: '';
  position: absolute;
  top: -50%;
  right: -10%;
  width: 50%;
  height: 200%;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.12) 0%, transparent 70%);
  pointer-events: none;
}

.assistant-hero-left {
  position: relative;
  z-index: 1;
}

.assistant-hero-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.assistant-avatar {
  width: 44px;
  height: 44px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  backdrop-filter: blur(10px);
}

.assistant-hero-title {
  font-size: 18px;
  font-weight: 700;
}

.assistant-hero-subtitle {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.85);
  margin-top: 2px;
}

.assistant-hero-prompt {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.95);
  line-height: 1.6;
}

.assistant-hero-prompt :deep(strong) {
  background: rgba(255, 255, 255, 0.2);
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 600;
}

.assistant-quick-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  position: relative;
  z-index: 1;
}

.assistant-quick-btn {
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  color: #fff;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;
  display: flex;
  align-items: center;
  gap: 8px;
  backdrop-filter: blur(10px);
  font-family: inherit;
}

.assistant-quick-btn:hover {
  background: rgba(255, 255, 255, 0.25);
  transform: translateY(-1px);
}

@media (max-width: 1024px) {
  .assistant-hero {
    grid-template-columns: 1fr;
  }
}
</style>
