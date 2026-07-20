<template>
  <div class="collapsible-section">
    <div
      class="section-header"
      :class="{ 'is-expanded': isExpanded }"
      @click="toggleExpand"
    >
      <div class="header-left">
        <el-icon class="toggle-icon" :class="{ rotated: isExpanded }">
          <ArrowRight />
        </el-icon>
        <span class="section-title">{{ title }}</span>
        <el-tag v-if="badge" size="small" :type="badgeType" effect="light">{{ badge }}</el-tag>
      </div>
      <div class="header-right">
        <span class="expand-text">{{ isExpanded ? '收起' : '展开' }}</span>
      </div>
    </div>

    <transition name="section-expand">
      <div v-show="isExpanded" class="section-body">
        <slot />
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { ArrowRight } from '@element-plus/icons-vue'

interface Props {
  title: string
  badge?: string
  badgeType?: 'primary' | 'success' | 'info' | 'warning' | 'danger'
  storageKey?: string
  defaultExpanded?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  badgeType: 'info',
  defaultExpanded: false,
  storageKey: ''
})

const isExpanded = ref(props.defaultExpanded)

const toggleExpand = () => {
  isExpanded.value = !isExpanded.value
  if (props.storageKey) {
    try {
      localStorage.setItem(props.storageKey, String(isExpanded.value))
    } catch (e) {
      console.warn('localStorage 写入失败:', e)
    }
  }
}

watch(() => props.defaultExpanded, (val) => {
  isExpanded.value = val
})

onMounted(() => {
  if (props.storageKey) {
    try {
      const saved = localStorage.getItem(props.storageKey)
      if (saved !== null) {
        isExpanded.value = saved === 'true'
      }
    } catch (e) {
      console.warn('localStorage 读取失败:', e)
    }
  }
})
</script>

<style lang="scss" scoped>
.collapsible-section {
  margin-top: 24px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  overflow: hidden;
  background: var(--el-bg-color);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 20px;
  cursor: pointer;
  user-select: none;
  transition: background-color 0.2s;

  &:hover {
    background-color: var(--el-fill-color-light);
  }

  &.is-expanded {
    border-bottom: 1px solid var(--el-border-color-lighter);
  }
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toggle-icon {
  font-size: 14px;
  color: var(--el-text-color-secondary);
  transition: transform 0.3s ease;

  &.rotated {
    transform: rotate(90deg);
  }
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.header-right {
  .expand-text {
    font-size: 13px;
    color: var(--el-text-color-secondary);
  }
}

.section-body {
  padding: 20px;
}

.section-expand-enter-active,
.section-expand-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}

.section-expand-enter-from,
.section-expand-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}
</style>
