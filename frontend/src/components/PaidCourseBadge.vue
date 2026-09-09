<template>
  <!-- 付费课程引导 badge（v3.6.0 社区版开源分离：文案收敛于此组件，
       社区版发布时整文件替换为空壳，共享页面零改动） -->
  <el-tag type="warning" :size="size">{{ text }}</el-tag>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ size?: 'small' | 'default' | 'large'; text?: string }>(), {
  size: 'default',
  text: '完整版需加入知识星球'
})
</script>
