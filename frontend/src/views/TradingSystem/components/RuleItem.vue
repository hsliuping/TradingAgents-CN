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
        {{ item.rule || item.condition || item.name || formatObject(item) }}
      </div>
      <div v-if="item.description" class="rule-desc">
        {{ item.description }}
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

function formatObject(obj: any): string {
  if (typeof obj === 'string') return obj
  if (typeof obj === 'object') {
    // 尝试提取有意义的字段
    const keys = ['rule', 'condition', 'name', 'value', 'type']
    for (const key of keys) {
      if (obj[key]) return String(obj[key])
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

