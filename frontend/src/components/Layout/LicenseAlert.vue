<template>
  <!-- 授权状态提醒条 -->
  <div v-if="showAlert" class="license-alert" :class="alertType">
    <el-icon class="alert-icon">
      <WarningFilled v-if="alertType === 'warning'" />
      <CircleCloseFilled v-else-if="alertType === 'error'" />
      <InfoFilled v-else />
    </el-icon>
    <span class="alert-message">{{ alertMessage }}</span>
    <el-button 
      v-if="showAction" 
      size="small" 
      :type="alertType === 'error' ? 'danger' : 'warning'"
      @click="handleAction"
    >
      {{ actionText }}
    </el-button>
    <el-button 
      v-if="dismissible" 
      size="small" 
      text 
      @click="dismiss"
      class="dismiss-btn"
    >
      <el-icon><Close /></el-icon>
    </el-button>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useLicenseStore } from '@/stores/license'
import { WarningFilled, CircleCloseFilled, InfoFilled, Close } from '@element-plus/icons-vue'

const router = useRouter()
const licenseStore = useLicenseStore()

// 用户是否已关闭提醒（本次会话）
const dismissed = ref(false)
// 上次关闭时间（用于防止频繁显示）
const lastDismissedKey = 'license_alert_dismissed_at'

// 检查是否在今天已经关闭过
const isDismissedToday = () => {
  const lastDismissed = localStorage.getItem(lastDismissedKey)
  if (!lastDismissed) return false
  const dismissedDate = new Date(lastDismissed)
  const today = new Date()
  return dismissedDate.toDateString() === today.toDateString()
}

// 提醒类型
const alertType = computed(() => {
  if (licenseStore.isOffline) return 'info'
  if (licenseStore.isExpired) return 'error'
  if (licenseStore.isExpiringSoon) return 'warning'
  return 'info'
})

// 是否显示提醒
const showAlert = computed(() => {
  if (dismissed.value || isDismissedToday()) return false
  // 离线状态
  if (licenseStore.isOffline) return true
  // 已过期
  if (licenseStore.isExpired && licenseStore.isPro) return true
  // 即将到期（7天内）
  if (licenseStore.isExpiringSoon) return true
  return false
})

// 提醒消息
const alertMessage = computed(() => {
  if (licenseStore.isOffline) {
    return '⚠️ 无法连接授权服务器，当前使用离线模式，部分功能可能受限'
  }
  if (licenseStore.isExpired) {
    return '❌ 您的高级学员资格已过期，请及时续费以继续使用高级功能'
  }
  if (licenseStore.isExpiringSoon) {
    const days = licenseStore.daysRemaining
    const planLabel = licenseStore.isTrial ? '体验资格' : '高级学员资格'
    if (days === 1) {
      return `⏰ 您的${planLabel}将于明天到期，请及时续费`
    }
    return `⏰ 您的${planLabel}将在 ${days} 天后到期，请及时续费`
  }
  return ''
})

// 是否显示操作按钮
const showAction = computed(() => {
  return !licenseStore.isOffline
})

// 操作按钮文案
const actionText = computed(() => {
  if (licenseStore.isExpired) return '立即续费'
  if (licenseStore.isExpiringSoon) return '前往续费'
  return '了解详情'
})

// 是否可关闭
const dismissible = computed(() => {
  // 已过期不可关闭，必须处理
  return !licenseStore.isExpired
})

// 关闭提醒
const dismiss = () => {
  dismissed.value = true
  localStorage.setItem(lastDismissedKey, new Date().toISOString())
}

// 处理操作按钮点击
const handleAction = () => {
  router.push('/settings/license')
}

// 监听授权状态变化，重置关闭状态
watch(() => licenseStore.plan, () => {
  dismissed.value = false
})
</script>

<style lang="scss" scoped>
.license-alert {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 20px;
  font-size: 14px;
  position: sticky;
  top: 0;
  z-index: 1001;
  
  &.warning {
    background: linear-gradient(90deg, #fdf6ec 0%, #fef0e6 100%);
    border-bottom: 1px solid #f5dab1;
    color: #e6a23c;
  }
  
  &.error {
    background: linear-gradient(90deg, #fef0f0 0%, #fde2e2 100%);
    border-bottom: 1px solid #fab6b6;
    color: #f56c6c;
  }
  
  &.info {
    background: linear-gradient(90deg, #f4f4f5 0%, #ebeef5 100%);
    border-bottom: 1px solid #d3d4d6;
    color: #909399;
  }
  
  .alert-icon {
    font-size: 18px;
  }
  
  .alert-message {
    flex: 1;
  }
  
  .dismiss-btn {
    padding: 4px;
    min-height: auto;
  }
}
</style>

