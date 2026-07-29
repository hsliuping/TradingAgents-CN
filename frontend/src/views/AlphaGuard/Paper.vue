<template>
  <div class="page-grid">
    <section class="account-boundary">
      <div><strong>AlphaGuard 自动模拟账户</strong><p>由结构化决策链驱动；不能手工改现金、持仓、订单或成交。</p></div>
      <el-button @click="router.push('/paper')">查看独立人工模拟账户</el-button>
    </section>
    <el-alert type="info" :closable="false" show-icon title="当前没有订单是因为没有完整通过策略、模型、一致性和硬风控的合法交易方案，并非系统没有运行。" />
    <AlphaGuardAutoPaperPanel />
  </div>
</template>
<script setup lang="ts">
import AlphaGuardAutoPaperPanel from '@/components/paper/AlphaGuardAutoPaperPanel.vue'
import { useRouter } from 'vue-router'
const router = useRouter()
</script>
<style scoped>
.page-grid { display: grid; gap: 16px; }
.account-boundary { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding-bottom: 16px; border-bottom: 1px solid var(--el-border-color-light); }
.account-boundary p { margin: 6px 0 0; color: var(--el-text-color-secondary); }
@media (max-width: 700px) { .account-boundary { flex-direction: column; } }
</style>
