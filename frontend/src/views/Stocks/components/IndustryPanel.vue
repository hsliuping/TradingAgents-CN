<template>
  <div class="industry-panel">
    <el-empty description="这个行业还没有系统级行业研究（行业世界模型为 Pro 版功能）">
      <template #image><el-icon :size="48" color="#C0C4CC"><DataAnalysis /></el-icon></template>
      <div class="ip-empty-sub">个股的全部研究功能不受影响。</div>
    </el-empty>
  </div>
</template>

<script setup lang="ts">
import { DataAnalysis } from '@element-plus/icons-vue'

defineProps<{ stockName: string }>()
</script>

<style scoped>
.industry-panel { min-height: 120px; }
.ip-empty-sub { margin-top: 10px; font-size: 12px; color: #c0c4cc; }
</style>
