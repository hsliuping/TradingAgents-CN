<template>
  <div class="condition-display">
    <template v-if="isObject(condition)">
      <div v-for="(value, key) in condition" :key="key" class="condition-item">
        <span class="condition-key">{{ formatKey(key as string) }}：</span>
        <span class="condition-value">{{ formatValue(value) }}</span>
      </div>
    </template>
    <template v-else>
      <span class="condition-value">{{ formatValue(condition) }}</span>
    </template>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  condition: any
}>()

function isObject(value: any): boolean {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function formatKey(key: string): string {
  const keyMap: Record<string, string> = {
    type: '类型',
    percentage: '比例',
    value: '数值',
    condition: '条件',
    description: '说明',
    min: '最小值',
    max: '最大值',
    default: '默认值',
    bullish: '看多',
    bearish: '看空',
    neutral: '中性',
    days: '天数',
    target: '目标'
  }
  return keyMap[key] || key
}

function formatValue(value: any): string {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'number') {
    // 如果是小于1的数字，可能是百分比
    if (value > 0 && value < 1) {
      return `${(value * 100).toFixed(1)}%`
    }
    return String(value)
  }
  if (Array.isArray(value)) {
    return value.join('、')
  }
  if (typeof value === 'object') {
    return JSON.stringify(value)
  }
  return String(value)
}
</script>

<style scoped lang="scss">
.condition-display {
  background: var(--el-fill-color-light);
  padding: 12px;
  border-radius: 6px;
}

.condition-item {
  display: flex;
  align-items: baseline;
  padding: 6px 0;
  border-bottom: 1px dashed var(--el-border-color-lighter);

  &:last-child {
    border-bottom: none;
    padding-bottom: 0;
  }

  &:first-child {
    padding-top: 0;
  }
}

.condition-key {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  flex-shrink: 0;
  min-width: 80px;
}

.condition-value {
  color: var(--el-text-color-primary);
  font-size: 14px;
  word-break: break-all;
}
</style>

