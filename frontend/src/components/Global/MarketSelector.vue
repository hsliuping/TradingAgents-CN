<template>
  <el-select
    v-model="selectedMarket"
    :placeholder="placeholder"
    :size="size"
    :clearable="clearable"
    :disabled="disabled"
    @change="handleChange"
    class="market-selector"
  >
    <el-option
      v-for="market in markets"
      :key="market.code"
      :label="market.label"
      :value="market.code"
    >
      <span class="market-option">
        <span class="market-flag">{{ market.flag }}</span>
        <span class="market-name">{{ market.label }}</span>
      </span>
    </el-option>
  </el-select>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

interface Market {
  code: string
  label: string
  flag: string
}

interface Props {
  modelValue?: string
  placeholder?: string
  size?: 'large' | 'default' | 'small'
  clearable?: boolean
  disabled?: boolean
}

interface Emits {
  (e: 'update:modelValue', value: string): void
  (e: 'change', value: string): void
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: 'CN',
  placeholder: '选择市场',
  size: 'default',
  clearable: false,
  disabled: false
})

const emit = defineEmits<Emits>()

const markets: Market[] = [
  { code: 'CN', label: 'A股', flag: '🇨🇳' },
  { code: 'HK', label: '港股', flag: '🇭🇰' },
  { code: 'US', label: '美股', flag: '🇺🇸' }
]

const selectedMarket = ref(props.modelValue)

watch(() => props.modelValue, (newValue) => {
  selectedMarket.value = newValue
})

const handleChange = (value: string) => {
  emit('update:modelValue', value)
  emit('change', value)
}
</script>

<style scoped lang="scss">
.market-selector {
  min-width: 120px;
}

.market-option {
  display: flex;
  align-items: center;
  gap: 8px;
}

.market-flag {
  font-size: 18px;
}

.market-name {
  font-size: 14px;
}
</style>

