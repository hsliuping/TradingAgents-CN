<template>
  <el-alert
    type="warning"
    :closable="false"
    show-icon
    title="FULL_CHALLENGER_PIPELINE_NOT_READY：当前可做确定性重放和 Shadow，但真实 Challenger 下单保持 fail-closed。"
    class="boundary"
  />
  <AlphaGuardExperimentLab />
</template>
<script setup lang="ts">
import AlphaGuardExperimentLab from '@/components/paper/AlphaGuardExperimentLab.vue'
</script>
<style scoped>.boundary { margin-bottom: 16px; }</style>

