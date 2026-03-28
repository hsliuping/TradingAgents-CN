<template>
  <div class="network-status" v-if="showStatus">
    <el-alert
      v-if="!appStore.isOnline"
      title="网络连接已断开"
      type="warning"
      :closable="false"
      show-icon
    >
      <template #default>
        <span>请检查您的网络连接</span>
      </template>
    </el-alert>
    
    <el-alert
      v-else-if="!appStore.apiConnected"
      title="后端服务连接失败"
      type="error"
      :closable="false"
      show-icon
    >
      <template #default>
        <div class="api-connection-message">
          <span>无法连接到后端服务，请检查服务是否正常运行</span>
          <span class="api-connection-tip">系统会自动重连，恢复后此提示会自动消失</span>
        </div>
      </template>
    </el-alert>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()

// 只在有网络问题时显示状态
const showStatus = computed(() => {
  return !appStore.isOnline || !appStore.apiConnected
})

// 定期检查API连接状态
let checkInterval: number | null = null

onMounted(() => {
  // 自动轮询重连；仅在网络在线且后端未连接时触发
  checkInterval = window.setInterval(() => {
    if (appStore.isOnline && !appStore.apiConnected) {
      appStore.checkApiConnection()
    }
  }, 15000)
})

onUnmounted(() => {
  if (checkInterval) {
    clearInterval(checkInterval)
  }
})
</script>

<style scoped>
.network-status {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 9999;
  max-width: 400px;
}

.network-status :deep(.el-alert) {
  margin-bottom: 10px;
}

.network-status :deep(.el-alert__content) {
  display: flex;
  align-items: center;
  justify-content: center;
}

.api-connection-message {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  text-align: center;
}

.api-connection-tip {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
