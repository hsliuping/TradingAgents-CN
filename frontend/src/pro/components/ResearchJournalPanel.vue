<template>
  <div class="research-journal-panel community-empty">
    <el-empty description="研究日志是 Pro 版功能（社区版不提供）" :image-size="72" />
  </div>
</template>

<script setup lang="ts">
defineProps<{
  stockCode: string
  stockName?: string
}>()

defineEmits<{
  (e: 'review-summary', payload: { openCount: number; openItems: any[] }): void
}>()
</script>

<style scoped>
.research-journal-panel { min-height: 80px; }
</style>
