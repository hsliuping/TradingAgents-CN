<template>
  <el-alert
    type="info"
    :closable="false"
    show-icon
    title="挑战者运行与当前 Champion 完全隔离；所有启用、暂停和退役操作均由管理员手工确认。"
    class="boundary"
  />
  <el-tabs v-model="activeView" class="experiment-views">
    <el-tab-pane label="挑战者" name="challenger"><AlphaGuardExperimentLab /></el-tab-pane>
    <el-tab-pane label="实验治理" name="governance" lazy><AlphaGuardExperimentGovernance /></el-tab-pane>
  </el-tabs>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import AlphaGuardExperimentLab from '@/components/paper/AlphaGuardExperimentLab.vue'
import AlphaGuardExperimentGovernance from '@/components/paper/AlphaGuardExperimentGovernance.vue'

const activeView = ref('challenger')
</script>
<style scoped>.boundary { margin-bottom: 16px; }.experiment-views { min-width: 0; }</style>
