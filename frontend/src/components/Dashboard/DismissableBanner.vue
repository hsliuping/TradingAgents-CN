<template>
  <transition name="banner-slide">
    <div v-if="visible" class="dismissable-banner" :class="`banner-${variant}`">
      <div class="banner-icon">
        <el-icon size="22"><component :is="icon" /></el-icon>
      </div>
      <div class="banner-content">
        <div class="banner-title">{{ title }}</div>
        <div class="banner-description">{{ description }}</div>
      </div>
      <div class="banner-action" v-if="$slots.action || actionText">
        <slot name="action">
          <el-button type="primary" size="small" @click="$emit('action')">
            {{ actionText }}
          </el-button>
        </slot>
      </div>
      <el-icon class="banner-close" @click="handleDismiss"><Close /></el-icon>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Close } from '@element-plus/icons-vue'
import type { Component } from 'vue'

interface Props {
  title: string
  description?: string
  actionText?: string
  icon?: Component
  variant?: 'primary' | 'success' | 'info' | 'warning'
  storageKey?: string
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'primary',
  storageKey: ''
})

const emit = defineEmits<{
  (e: 'action'): void
  (e: 'dismiss'): void
}>()

const visible = ref(true)

const handleDismiss = () => {
  visible.value = false
  if (props.storageKey) {
    try {
      localStorage.setItem(props.storageKey, 'true')
    } catch (e) {
      console.warn('localStorage 写入失败:', e)
    }
  }
  emit('dismiss')
}

onMounted(() => {
  if (props.storageKey) {
    try {
      const dismissed = localStorage.getItem(props.storageKey) === 'true'
      if (dismissed) {
        visible.value = false
      }
    } catch (e) {
      console.warn('localStorage 读取失败:', e)
    }
  }
})
</script>

<style lang="scss" scoped>
.dismissable-banner {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 20px;
  border-radius: 10px;
  margin-bottom: 24px;
  position: relative;
  transition: all 0.3s ease;

  &.banner-primary {
    background: linear-gradient(135deg, rgba(64, 158, 255, 0.08) 0%, rgba(64, 158, 255, 0.02) 100%);
    border: 1px solid rgba(64, 158, 255, 0.2);

    .banner-icon { background: rgba(64, 158, 255, 0.15); color: #409eff; }
  }

  &.banner-success {
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.08) 0%, rgba(16, 185, 129, 0.02) 100%);
    border: 1px solid rgba(16, 185, 129, 0.2);

    .banner-icon { background: rgba(16, 185, 129, 0.15); color: #10b981; }
  }

  &.banner-info {
    background: linear-gradient(135deg, rgba(144, 147, 153, 0.08) 0%, rgba(144, 147, 153, 0.02) 100%);
    border: 1px solid rgba(144, 147, 153, 0.2);

    .banner-icon { background: rgba(144, 147, 153, 0.15); color: #909399; }
  }

  &.banner-warning {
    background: linear-gradient(135deg, rgba(230, 162, 60, 0.08) 0%, rgba(230, 162, 60, 0.02) 100%);
    border: 1px solid rgba(230, 162, 60, 0.2);

    .banner-icon { background: rgba(230, 162, 60, 0.15); color: #e6a23c; }
  }
}

.banner-icon {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.banner-content {
  flex: 1;
  min-width: 0;
}

.banner-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 4px;
}

.banner-description {
  font-size: 13px;
  color: var(--el-text-color-regular);
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.banner-action {
  flex-shrink: 0;
}

.banner-close {
  position: absolute;
  top: 10px;
  right: 12px;
  font-size: 14px;
  color: var(--el-text-color-placeholder);
  cursor: pointer;
  transition: color 0.2s;

  &:hover {
    color: var(--el-text-color-primary);
  }
}

.banner-slide-enter-active,
.banner-slide-leave-active {
  transition: all 0.4s ease;
}

.banner-slide-enter-from,
.banner-slide-leave-to {
  opacity: 0;
  transform: translateY(-10px);
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
  margin-bottom: 0;
}
</style>
