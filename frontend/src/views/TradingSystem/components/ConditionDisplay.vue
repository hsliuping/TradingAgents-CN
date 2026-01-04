<template>
  <div class="condition-display">
    <template v-if="isObject(condition)">
      <div v-for="(value, key) in condition" :key="key" class="condition-item">
        <span class="condition-key">{{ formatKey(key as string) }}：</span>
        <span class="condition-value">{{ formatValue(value, key as string) }}</span>
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
    target: '目标',
    // 市场状态
    bull: '牛市',
    range: '震荡市',
    bear: '熊市',
    // 其他常见字段
    signal: '信号',
    threshold: '阈值',
    period: '周期',
    method: '方法',
    rule: '规则',
    action: '操作',
    reason: '原因'
  }
  return keyMap[key] || key
}

function formatValue(value: any, key?: string): string {
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
  
  // 字符串值的映射（特别是type字段）
  const valueStr = String(value).toLowerCase()
  const valueMap: Record<string, string> = {
    // 止损/止盈类型
    'percentage': '固定比例',
    'scaled': '分批止盈',
    'trailing': '移动止盈',
    'fixed': '固定',
    'dynamic': '动态',
    // 市场状态
    'bull': '牛市',
    'bear': '熊市',
    'range': '震荡市',
    'bullish': '看多',
    'bearish': '看空',
    'neutral': '中性',
    // 其他常见值
    'daily': '每日',
    'weekly': '每周',
    'monthly': '每月',
    'quarterly': '每季度',
    'yearly': '每年',
    'enabled': '启用',
    'disabled': '禁用',
    'true': '是',
    'false': '否',
    'yes': '是',
    'no': '否'
  }
  
  // 如果key是'type'，优先使用值映射
  if (key === 'type' && valueMap[valueStr]) {
    return valueMap[valueStr]
  }
  
  // 其他情况也尝试映射
  if (valueMap[valueStr]) {
    return valueMap[valueStr]
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

