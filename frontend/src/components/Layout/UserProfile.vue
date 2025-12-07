<template>
  <div class="user-profile" :class="{ collapsed: appStore.sidebarCollapsed }">
    <!-- 学员等级显示 -->
    <div v-if="!appStore.sidebarCollapsed" class="license-badge" @click="goToLicense">
      <el-tag
        :type="licenseTagType"
        size="small"
        effect="dark"
        class="license-tag"
      >
        <el-icon v-if="licenseStore.isPro" style="margin-right: 2px;"><Star /></el-icon>
        {{ licenseLabel }}
      </el-tag>
      <span v-if="licenseStore.daysRemaining !== null && licenseStore.daysRemaining > 0" class="expire-hint">
        {{ licenseStore.daysRemaining }}天后到期
      </span>
    </div>
    <div v-else class="license-badge-mini" @click="goToLicense">
      <el-tooltip :content="licenseLabel" placement="right">
        <el-icon :color="licenseIconColor" :size="18"><Star v-if="licenseStore.isPro" /><UserFilled v-else /></el-icon>
      </el-tooltip>
    </div>

    <!-- 用户信息 -->
    <el-dropdown trigger="click" @command="handleCommand">
      <div class="profile-info">
        <el-avatar :size="32" :src="userAvatar">
          <el-icon><User /></el-icon>
        </el-avatar>
        <div v-if="!appStore.sidebarCollapsed" class="user-info">
          <div class="username">{{ userDisplayName }}</div>
          <div class="user-role">{{ userRole }}</div>
        </div>
      </div>

      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item command="settings">
            <el-icon><Setting /></el-icon>
            设置
          </el-dropdown-item>
          <el-dropdown-item divided command="logout">
            <el-icon><SwitchButton /></el-icon>
            退出登录
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import { useLicenseStore } from '@/stores/license'
import { User, Setting, SwitchButton, Star, UserFilled } from '@element-plus/icons-vue'

const router = useRouter()
const appStore = useAppStore()
const authStore = useAuthStore()
const licenseStore = useLicenseStore()

// 用户头像：优先使用用户设置的头像，否则返回 undefined 使用 el-avatar 的默认图标
const userAvatar = computed(() => authStore.user?.avatar || undefined)
const userDisplayName = computed(() => authStore.user?.username || '未登录')
const userRole = computed(() => {
  if (!authStore.user) return '未登录'
  return '用户'
})

// 学员等级相关
const licenseLabel = computed(() => {
  const plan = licenseStore.plan
  if (plan === 'enterprise') return '终身高级学员'
  if (plan === 'pro') return '高级学员'
  if (plan === 'trial') return '体验高级学员'
  return '初级学员'
})

const licenseTagType = computed(() => {
  const plan = licenseStore.plan
  if (['enterprise', 'pro'].includes(plan)) return 'success'
  if (plan === 'trial') return 'warning'
  return 'info'
})

const licenseIconColor = computed(() => {
  const plan = licenseStore.plan
  if (['enterprise', 'pro'].includes(plan)) return '#67c23a'
  if (plan === 'trial') return '#e6a23c'
  return '#909399'
})

const goToLicense = () => {
  router.push('/settings/license')
}

const handleCommand = async (command: string) => {
  switch (command) {
    case 'settings':
      router.push('/settings')
      break
    case 'logout':
      await authStore.logout()
      ElMessage.success('已退出登录')
      router.push('/login')
      break
  }
}
</script>

<style lang="scss" scoped>
.user-profile {
  padding: 12px;

  &.collapsed {
    padding: 8px;
    text-align: center;
  }

  .license-badge {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px;
    margin-bottom: 8px;
    border-radius: 6px;
    background-color: var(--el-fill-color-lighter);
    cursor: pointer;
    transition: background-color 0.3s ease;

    &:hover {
      background-color: var(--el-fill-color-light);
    }

    .license-tag {
      font-size: 12px;
    }

    .expire-hint {
      font-size: 11px;
      color: var(--el-text-color-placeholder);
    }
  }

  .license-badge-mini {
    display: flex;
    justify-content: center;
    padding: 8px;
    margin-bottom: 8px;
    cursor: pointer;
    border-radius: 6px;
    transition: background-color 0.3s ease;

    &:hover {
      background-color: var(--el-fill-color-lighter);
    }
  }

  .profile-info {
    display: flex;
    align-items: center;
    gap: 12px;
    cursor: pointer;
    padding: 8px;
    border-radius: 6px;
    transition: background-color 0.3s ease;

    &:hover {
      background-color: var(--el-fill-color-lighter);
    }

    .user-info {
      flex: 1;
      min-width: 0;

      .username {
        font-size: 14px;
        font-weight: 500;
        color: var(--el-text-color-primary);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .user-role {
        font-size: 12px;
        color: var(--el-text-color-placeholder);
      }
    }
  }
}
</style>
