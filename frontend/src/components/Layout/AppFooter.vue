<template>
  <div class="app-footer">
    <div class="footer-content">
      <div class="copyright">
        <span>© 2025 TradingAgents-CN v1.0.1</span>
        <span class="rights">All rights reserved.</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// Footer组件逻辑
</script>

<style lang="scss" scoped>
.app-footer {
  .footer-content {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    gap: 6px;
    color: var(--el-text-color-regular);
    font-size: 14px;
    padding: 12px 16px;
    text-align: center;
  }

  .rights {
    margin-left: 4px;
  }
}
</style>

