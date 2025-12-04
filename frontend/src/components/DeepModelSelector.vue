<template>
  <el-select
    v-model="localValue"
    :style="{ width }"
    :size="size"
    filterable
    :placeholder="placeholder"
    @change="onChange"
  >
    <el-option
      v-for="model in availableModels"
      :key="model.model_name"
      :label="model.model_display_name || model.model_name"
      :value="model.model_name"
    >
      <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
        <span style="flex:1;">{{ model.model_display_name || model.model_name }}</span>
        <div style="display:flex;align-items:center;gap:4px;">
          <el-tag
            v-if="model.capability_level"
            :type="getCapabilityTagType(model.capability_level)"
            size="small"
            effect="plain"
          >
            {{ getCapabilityText(model.capability_level) }}
          </el-tag>
          <el-tag
            v-if="type === 'deep' ? isDeepAnalysisRole(model.suitable_roles) : isQuickAnalysisRole(model.suitable_roles)"
            :type="type === 'deep' ? 'warning' : 'success'"
            size="small"
            effect="plain"
          >
            {{ type === 'deep' ? '🧠深度' : '⚡快速' }}
          </el-tag>
          <span style="font-size:12px;color:#909399;">{{ model.provider }}</span>
        </div>
      </div>
    </el-option>
  </el-select>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

interface Props {
  modelValue: string
  availableModels: any[]
  placeholder?: string
  type?: 'quick' | 'deep'
  size?: 'large' | 'default' | 'small'
  width?: string
}

const props = withDefaults(defineProps<Props>(), {
  placeholder: '选择模型',
  type: 'deep',
  size: 'default',
  width: '100%'
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const localValue = ref(props.modelValue)

watch(() => props.modelValue, (val) => { localValue.value = val })

const onChange = (val: string) => {
  emit('update:modelValue', val)
}

const getCapabilityText = (level: number): string => {
  const texts: Record<number, string> = {
    1: '⚡基础',
    2: '📊标准',
    3: '🎯高级',
    4: '🔥专业',
    5: '👑旗舰'
  }
  return texts[level] || '📊标准'
}

const getCapabilityTagType = (level: number): 'success' | 'info' | 'warning' | 'danger' => {
  if (level >= 4) return 'danger'
  if (level >= 3) return 'warning'
  if (level >= 2) return 'success'
  return 'info'
}

const isQuickAnalysisRole = (roles: string[] | undefined): boolean => {
  if (!roles || !Array.isArray(roles)) return false
  return roles.includes('quick_analysis') || roles.includes('both')
}

const isDeepAnalysisRole = (roles: string[] | undefined): boolean => {
  if (!roles || !Array.isArray(roles)) return false
  return roles.includes('deep_analysis') || roles.includes('both')
}
</script>