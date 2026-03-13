<template>
  <div class="rule-item" :class="typeClass">
    <div class="rule-icon">
      <el-icon v-if="type === 'must'" color="var(--el-color-success)"><CircleCheck /></el-icon>
      <el-icon v-else-if="type === 'exclude' || type === 'forbid'" color="var(--el-color-danger)"><CircleClose /></el-icon>
      <el-icon v-else-if="type === 'bonus'" color="var(--el-color-warning)"><Star /></el-icon>
      <el-icon v-else-if="type === 'signal'" color="var(--el-color-primary)"><Bell /></el-icon>
      <el-icon v-else-if="type === 'add'" color="var(--el-color-success)"><Plus /></el-icon>
      <el-icon v-else-if="type === 'reduce'" color="var(--el-color-warning)"><Minus /></el-icon>
      <el-icon v-else><InfoFilled /></el-icon>
    </div>
    <div class="rule-content">
      <div class="rule-main">
        {{ getMainContent() }}
      </div>
      <div v-if="getDescription()" class="rule-desc">
        {{ getDescription() }}
      </div>
      <div v-if="item.weight" class="rule-weight">
        权重：{{ item.weight }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  CircleCheck,
  CircleClose,
  Star,
  Bell,
  Plus,
  Minus,
  InfoFilled
} from '@element-plus/icons-vue'

const props = defineProps<{
  item: any
  type: 'must' | 'exclude' | 'bonus' | 'signal' | 'add' | 'reduce' | 'forbid' | string
}>()

const typeClass = computed(() => `type-${props.type}`)

function getMainContent(): string {
  const item = props.item
  if (!item) return ''
  
  // 对于signal类型，优先使用signal字段
  if (props.type === 'signal' && item.signal) {
    return String(item.signal)
  }
  
  // 其他类型，按优先级查找
  return item.rule || item.condition || item.name || item.signal || formatObject(item)
}

function getDescription(): string {
  const item = props.item
  if (!item) return ''

  // signal类型下，第二列语义是condition（具体触发条件）。
  if (props.type === 'signal' && item.condition) {
    return String(item.condition)
  }
  
  // 优先使用description字段
  if (item.description) {
    return String(item.description)
  }
  
  return ''
}

function formatObject(obj: any): string {
  if (typeof obj === 'string') return obj
  if (typeof obj === 'object') {
    // 尝试提取有意义的字段
    const keys = ['rule', 'condition', 'name', 'value', 'type', 'signal']
    for (const key of keys) {
      if (obj[key]) return String(obj[key])
    }
    // 如果都没有，尝试格式化显示（避免显示JSON）
    const entries = Object.entries(obj)
    if (entries.length > 0) {
      return entries.map(([k, v]) => `${k}: ${v}`).join(', ')
    }
    return JSON.stringify(obj)
  }
  return String(obj)
}
</script>

<style scoped lang="scss">
.rule-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
  margin-bottom: 8px;
  border-left: 3px solid var(--el-border-color);
  transition: all 0.2s;

  &:hover {
    background: var(--el-fill-color);
  }

  &:last-child {
    margin-bottom: 0;
  }

  &.type-must {
    border-left-color: var(--el-color-success);
  }

  &.type-exclude,
  &.type-forbid {
    border-left-color: var(--el-color-danger);
    background: var(--el-color-danger-light-9);
  }

  &.type-bonus {
    border-left-color: var(--el-color-warning);
  }

  &.type-signal {
    border-left-color: var(--el-color-primary);
  }

  &.type-add {
    border-left-color: var(--el-color-success);
  }

  &.type-reduce {
    border-left-color: var(--el-color-warning);
  }
}

.rule-icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  font-size: 18px;
}

.rule-content {
  flex: 1;
  min-width: 0;
}

.rule-main {
  font-size: 14px;
  color: var(--el-text-color-primary);
  line-height: 1.5;
}

.rule-desc {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
  line-height: 1.4;
}

.rule-weight {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  margin-top: 4px;
}
</style>

