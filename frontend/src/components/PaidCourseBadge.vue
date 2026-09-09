<template>
  <!-- 付费课程引导（v3.6.0 社区版开源分离：文案收敛于此组件内部，
       社区版发布时整文件替换为空壳，共享页面零改动、无文案泄露） -->
  <el-tag v-if="variant === 'tag'" type="warning" :size="size">完整版需加入知识星球</el-tag>
  <span v-else-if="variant === 'tag-short'" class="paid-badge-inline">
    <el-tag type="warning" :size="size">完整版·知识星球</el-tag>
  </span>
  <span v-else class="paid-text">完整版加入知识星球付费学习。</span>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ variant?: 'tag' | 'tag-short' | 'text'; size?: 'small' | 'default' | 'large' }>(), {
  variant: 'tag',
  size: 'default'
})
</script>

<style scoped>
.paid-badge-inline {
  margin-left: 8px;
}
.paid-text {
  color: var(--el-color-warning);
}
</style>
