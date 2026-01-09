<template>
  <div class="license-debug">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>许可证调试信息</span>
          <el-button type="primary" @click="refresh">刷新</el-button>
        </div>
      </template>

      <el-descriptions :column="2" border>
        <el-descriptions-item label="App Token">
          {{ licenseStore.appToken || '未设置' }}
        </el-descriptions-item>
        <el-descriptions-item label="计划">
          <el-tag :type="getPlanType(licenseStore.plan)">
            {{ getPlanLabel(licenseStore.plan) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="是否 PRO">
          <el-tag :type="licenseStore.isPro ? 'success' : 'info'">
            {{ licenseStore.isPro ? '是' : '否' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="是否有效">
          <el-tag :type="licenseStore.licenseInfo?.is_valid ? 'success' : 'danger'">
            {{ licenseStore.licenseInfo?.is_valid ? '有效' : '无效' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="邮箱">
          {{ licenseStore.licenseInfo?.email || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="离线模式">
          <el-tag :type="licenseStore.isOffline ? 'warning' : 'success'">
            {{ licenseStore.isOffline ? '是' : '否' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="剩余天数">
          {{ licenseStore.daysRemaining !== null ? `${licenseStore.daysRemaining} 天` : '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="错误信息">
          {{ licenseStore.error || '-' }}
        </el-descriptions-item>
      </el-descriptions>

      <el-divider>原始数据</el-divider>
      <pre>{{ JSON.stringify(licenseStore.licenseInfo, null, 2) }}</pre>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { useLicenseStore } from '@/stores/license'
import { ElMessage } from 'element-plus'

const licenseStore = useLicenseStore()

const getPlanType = (plan: string) => {
  const types: Record<string, any> = {
    free: 'info',
    trial: 'warning',
    pro: 'success',
    enterprise: 'danger'
  }
  return types[plan] || 'info'
}

const getPlanLabel = (plan: string) => {
  const labels: Record<string, string> = {
    free: '免费版',
    trial: '体验版',
    pro: '高级学员',
    enterprise: '企业版'
  }
  return labels[plan] || plan
}

const refresh = async () => {
  console.log('🔄 手动刷新许可证状态...')
  await licenseStore.verifyLicense(true)
  ElMessage.success('刷新成功')
}
</script>

<style scoped lang="scss">
.license-debug {
  padding: 20px;

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  pre {
    background: var(--el-fill-color-light);
    padding: 12px;
    border-radius: 4px;
    overflow-x: auto;
  }
}
</style>

