<template>
  <div class="license-settings-container">
    <!-- 当前学员状态 -->
    <el-card class="status-card">
      <template #header>
        <div class="card-header">
          <span>🎓 学员状态</span>
          <el-tag :type="statusTagType" size="large">{{ planLabel }}</el-tag>
        </div>
      </template>

      <el-descriptions :column="2" border>
        <el-descriptions-item label="学员等级">
          <el-tag :type="isPro ? 'success' : 'info'">
            {{ isPro ? '高级学员' : '初级学员' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="绑定邮箱">
          {{ licenseInfo?.email || '未绑定' }}
        </el-descriptions-item>
        <!-- 到期时间 -->
        <el-descriptions-item v-if="expireTimeLabel" label="有效期至">
          <el-tag :type="isExpiringSoon ? 'warning' : 'success'" size="small">
            {{ expireTimeLabel }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item v-else-if="licenseStore.plan !== 'free'" label="有效期至">
          <span class="text-muted">永久</span>
        </el-descriptions-item>
        <el-descriptions-item label="可用功能" :span="2">
          <div class="features-list">
            <el-tag
              v-for="feature in availableFeatures"
              :key="feature"
              size="small"
              style="margin-right: 8px; margin-bottom: 4px"
            >
              {{ featureLabels[feature] || feature }}
            </el-tag>
            <span v-if="!availableFeatures.length" class="text-muted">
              基础功能
            </span>
          </div>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- App Token 配置 -->
    <el-card style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>🔑 App Token 配置</span>
        </div>
      </template>

      <el-alert
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      >
        <template #title>
          App Token 用于验证您的专业版授权。请前往
          <el-link type="primary" href="https://www.tradingagentscn.com/" target="_blank">
            官网申请
          </el-link>
          获取您的 App Token。
        </template>
      </el-alert>

      <el-form label-width="120px">
        <el-form-item label="App Token">
          <el-input
            v-model="tokenInput"
            type="password"
            show-password
            placeholder="请输入您的 App Token"
            :disabled="saving"
            style="max-width: 500px"
          />
        </el-form-item>

        <el-form-item>
          <el-button 
            type="primary" 
            @click="saveToken"
            :loading="saving"
            :disabled="!tokenInput"
          >
            <el-icon><Key /></el-icon>
            验证并保存
          </el-button>
          <el-button 
            v-if="hasToken"
            type="danger" 
            @click="removeToken"
            :loading="removing"
          >
            <el-icon><Delete /></el-icon>
            删除 Token
          </el-button>
          <el-button @click="refreshStatus" :loading="loading">
            <el-icon><Refresh /></el-icon>
            刷新状态
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 高级学员功能说明 -->
    <el-card style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>⭐ 高级学员专属功能</span>
        </div>
      </template>

      <el-row :gutter="16">
        <el-col :span="8" v-for="feature in proFeatureList" :key="feature.key">
          <div class="feature-item" :class="{ enabled: hasFeature(feature.key) }">
            <el-icon :size="24" :color="hasFeature(feature.key) ? '#67c23a' : '#909399'">
              <component :is="feature.icon" />
            </el-icon>
            <div class="feature-info">
              <div class="feature-name">{{ feature.name }}</div>
              <div class="feature-desc">{{ feature.desc }}</div>
            </div>
            <el-tag
              :type="hasFeature(feature.key) ? 'success' : 'info'"
              size="small"
            >
              {{ hasFeature(feature.key) ? '已启用' : '未启用' }}
            </el-tag>
          </div>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Key, Delete, Refresh, Message, FolderOpened, Clock, PieChart, DocumentChecked } from '@element-plus/icons-vue'
import { useLicenseStore, type ProFeature } from '@/stores/license'
import request from '@/api/request'

const licenseStore = useLicenseStore()

// 状态
const tokenInput = ref('')
const loading = ref(false)
const saving = ref(false)
const removing = ref(false)

// 计算属性
const isPro = computed(() => licenseStore.isPro)
const licenseInfo = computed(() => licenseStore.licenseInfo)
// 检查是否有 token：从服务器返回的状态或本地存储
const hasToken = computed(() => {
  // 优先检查 licenseInfo 中的 email（有 email 表示已配置 token）
  if (licenseInfo.value?.email) return true
  // 其次检查本地存储的 token
  return !!licenseStore.appToken
})
const availableFeatures = computed(() => licenseInfo.value?.features || [])

const statusTagType = computed(() => {
  const plan = licenseStore.plan
  if (plan === 'enterprise') return 'danger'
  if (plan === 'pro') return 'warning'
  if (plan === 'trial') return 'success'
  return 'info'
})

const planLabel = computed(() => {
  const plan = licenseStore.plan
  if (plan === 'enterprise') return '终身高级学员'
  if (plan === 'pro') return '高级学员'
  if (plan === 'trial') return '体验高级学员'
  return '初级学员'
})

// 到期时间显示
const expireTimeLabel = computed(() => {
  const info = licenseStore.licenseInfo
  if (!info) return null

  // 试用版显示 trial_end_at
  if (info.plan === 'trial' && info.trial_end_at) {
    return formatExpireTime(info.trial_end_at)
  }

  // PRO版显示 pro_expire_at
  if (info.plan === 'pro' && info.pro_expire_at) {
    return formatExpireTime(info.pro_expire_at)
  }

  return null
})

// 是否即将到期（7天内）
const isExpiringSoon = computed(() => {
  const info = licenseStore.licenseInfo
  if (!info) return false

  let expireDate: Date | null = null
  if (info.plan === 'trial' && info.trial_end_at) {
    expireDate = new Date(info.trial_end_at)
  } else if (info.plan === 'pro' && info.pro_expire_at) {
    expireDate = new Date(info.pro_expire_at)
  }

  if (!expireDate) return false

  const daysUntilExpire = (expireDate.getTime() - Date.now()) / (1000 * 60 * 60 * 24)
  return daysUntilExpire <= 7
})

// 格式化到期时间
const formatExpireTime = (dateStr: string): string => {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = date.getTime() - now.getTime()
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays < 0) {
    return '已过期'
  } else if (diffDays === 0) {
    return '今天到期'
  } else if (diffDays === 1) {
    return '明天到期'
  } else if (diffDays <= 30) {
    return `${diffDays}天后到期`
  } else {
    return date.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })
  }
}

// 功能标签映射
const featureLabels: Record<string, string> = {
  email_notification: '邮件通知',
  watchlist_groups: '自选股分组',
  scheduled_analysis: '定时分析',
  portfolio_analysis: '持仓分析',
  trade_review: '操作复盘',
  advanced_screening: '高级选股',
  batch_analysis: '批量分析',
  export_reports: '导出报告',
}

// 高级学员专属功能列表
const proFeatureList = [
  { key: 'email_notification', name: '邮件通知', desc: '分析完成自动发送邮件', icon: Message },
  { key: 'watchlist_groups', name: '自选股分组', desc: '按策略分组管理自选股', icon: FolderOpened },
  { key: 'scheduled_analysis', name: '定时分析', desc: '多时段自动分析', icon: Clock },
  { key: 'portfolio_analysis', name: '持仓分析', desc: 'AI智能持仓诊断', icon: PieChart },
  { key: 'trade_review', name: '操作复盘', desc: '交易决策复盘分析', icon: DocumentChecked },
]

const hasFeature = (feature: string) => {
  return licenseStore.hasFeature(feature as ProFeature)
}

// Actions
const refreshStatus = async () => {
  loading.value = true
  try {
    await licenseStore.verifyLicense(true)
    ElMessage.success('状态已刷新')
  } catch (e: any) {
    ElMessage.error(e.message || '刷新失败')
  } finally {
    loading.value = false
  }
}

const saveToken = async () => {
  if (!tokenInput.value) {
    ElMessage.warning('请输入 App Token')
    return
  }

  saving.value = true
  try {
    const response = await request.post('/api/license/save-token', {
      token: tokenInput.value
    })

    if (response.success) {
      await licenseStore.setAppToken(tokenInput.value)
      ElMessage.success(`Token 保存成功，当前版本: ${response.data.plan}`)
      tokenInput.value = ''
    } else {
      ElMessage.error(response.message || 'Token 验证失败')
    }
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

const removeToken = async () => {
  try {
    await ElMessageBox.confirm(
      '删除 Token 后将降级为免费版，确定要继续吗？',
      '确认删除',
      { type: 'warning' }
    )

    removing.value = true
    const response = await request.delete('/api/license/token')

    if (response.success) {
      licenseStore.clearAppToken()
      ElMessage.success('Token 已删除')
    } else {
      ElMessage.error(response.message || '删除失败')
    }
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.message || '删除失败')
    }
  } finally {
    removing.value = false
  }
}

onMounted(() => {
  refreshStatus()
})
</script>

<style scoped lang="scss">
.license-settings-container {
  padding: 16px;
  max-width: 1200px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.features-list {
  display: flex;
  flex-wrap: wrap;
}

.text-muted {
  color: #909399;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  margin-bottom: 16px;
  transition: all 0.3s;

  &.enabled {
    border-color: #67c23a;
    background-color: #f0f9eb;
  }

  .feature-info {
    flex: 1;

    .feature-name {
      font-weight: 500;
      margin-bottom: 4px;
    }

    .feature-desc {
      font-size: 12px;
      color: #909399;
    }
  }
}
</style>

