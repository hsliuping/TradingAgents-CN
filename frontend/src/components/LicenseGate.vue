<template>
  <div class="license-gate">
    <!-- 已认证：显示正常内容 -->
    <slot v-if="isPro" />

    <!-- 未认证：显示锁定内容 -->
    <slot v-else name="locked">
      <div class="locked-content">
        <el-icon class="lock-icon"><Lock /></el-icon>
        <p class="lock-message">此功能需要高级学员权限</p>
      </div>
    </slot>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useLicenseStore } from '@/stores/license'
import { Lock } from '@element-plus/icons-vue'

const licenseStore = useLicenseStore()

// 检查是否是高级学员
const isPro = computed(() => licenseStore.isPro)
</script>

<style scoped lang="scss">
.license-gate {
  width: 100%;
}

.locked-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
  background: var(--el-fill-color-light);
  border-radius: 8px;
  border: 2px dashed var(--el-border-color);

  .lock-icon {
    font-size: 64px;
    color: var(--el-text-color-placeholder);
    margin-bottom: 16px;
  }

  .lock-message {
    font-size: 16px;
    color: var(--el-text-color-regular);
    margin: 0;
  }
}
</style>


