<template>
  <section class="alphaguard-shell">
    <div v-if="isDemo" class="demo-banner">
      <strong>DEMO ENVIRONMENT</strong>
      <span>演示数据 · 不是正式模拟账户 · 不是实际投资结果</span>
    </div>
    <header class="product-header">
      <div>
        <h1>AlphaGuard</h1>
        <p>可追溯的多智能体研究、硬风控与自动模拟交易</p>
      </div>
      <div class="safety-badges">
        <el-tag :type="isDemo ? 'warning' : 'info'">{{ isDemo ? '隔离演示环境' : '真实本地环境' }}</el-tag>
        <el-tag type="success">SIM_AUTONOMOUS</el-tag>
        <el-tag type="danger">实盘永久关闭</el-tag>
      </div>
    </header>

    <el-alert
      type="warning"
      :closable="false"
      show-icon
      title="本系统当前只支持研究和自动模拟交易；Risk PASS 不等于订单，页面不提供实盘或绕过风控入口。"
    />

    <el-menu :default-active="route.path" mode="horizontal" router class="product-nav">
      <el-menu-item v-for="item in navItems" :key="item.path" :index="item.path">
        {{ item.label }}
      </el-menu-item>
    </el-menu>

    <router-view />
  </section>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()
const isDemo = import.meta.env.VITE_ALPHAGUARD_DEMO === 'true'
const navItems = [
  { path: '/alphaguard/overview', label: '总览' },
  { path: '/alphaguard/candidates', label: '候选池' },
  { path: '/alphaguard/decisions', label: '决策链' },
  { path: '/alphaguard/paper', label: '自动模拟' },
  { path: '/alphaguard/evaluations', label: '评价中心' },
  { path: '/alphaguard/experiments', label: '实验室' },
  { path: '/alphaguard/operations', label: '运维中心' }
]
</script>

<style scoped>
.alphaguard-shell { display: grid; gap: 16px; }
.demo-banner { position: sticky; top: 0; z-index: 20; display: flex; justify-content: center; gap: 12px; padding: 10px 16px; color: #3b2b00; background: #f7c948; border: 1px solid #d8a800; }
.product-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.product-header h1 { margin: 0 0 4px; }
.product-header p { margin: 0; color: var(--el-text-color-secondary); }
.safety-badges { display: flex; gap: 8px; flex-wrap: wrap; }
.product-nav { border: 1px solid var(--el-border-color-light); border-radius: 8px; padding: 0 8px; }
@media (max-width: 900px) {
  .product-header { align-items: flex-start; flex-direction: column; }
  .product-nav { overflow-x: auto; }
}
</style>
