<template>
  <div class="license-settings-container">
    <!-- 当前授权状态 -->
    <el-card class="status-card">
      <template #header>
        <div class="card-header">
          <span>🔐 授权状态</span>
          <el-tag :type="statusTagType" size="large">{{ planLabel }}</el-tag>
        </div>
      </template>

      <el-descriptions :column="2" border>
        <el-descriptions-item label="当前版本">
          <el-tag :type="isPro ? 'success' : 'info'">
            {{ isPro ? '专业版' : '免费版' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="授权邮箱">
          {{ licenseInfo?.email || '未授权' }}
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
              免费版功能
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
          App Token 用于验证您的专业版授权。请从
          <el-link type="primary" href="http://localhost:8081" target="_blank">
            TradingAgents Account Service
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

    <!-- PRO 功能说明 -->
    <el-card style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>⭐ 专业版功能</span>
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
import { Key, Delete, Refresh, Message, FolderOpened, Clock, PieChart, DocumentChecked, Filter, Files, Document } from '@element-plus/icons-vue'
import { useLicenseStore, PRO_FEATURES, type ProFeature } from '@/stores/license'
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
const hasToken = computed(() => !!licenseStore.appToken)
const availableFeatures = computed(() => licenseInfo.value?.features || [])

const statusTagType = computed(() => {
  const plan = licenseStore.plan
  if (plan === 'enterprise') return 'danger'
  if (plan === 'pro') return 'warning'
  return 'info'
})

const planLabel = computed(() => {
  const plan = licenseStore.plan
  if (plan === 'enterprise') return '企业版'
  if (plan === 'pro') return '专业版'
  return '免费版'
})

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

// PRO 功能列表
const proFeatureList = [
  { key: 'email_notification', name: '邮件通知', desc: '分析完成自动发送邮件', icon: Message },
  { key: 'watchlist_groups', name: '自选股分组', desc: '按策略分组管理自选股', icon: FolderOpened },
  { key: 'scheduled_analysis', name: '定时分析', desc: '多时段自动分析', icon: Clock },
  { key: 'portfolio_analysis', name: '持仓分析', desc: 'AI智能持仓诊断', icon: PieChart },
  { key: 'trade_review', name: '操作复盘', desc: '交易决策复盘分析', icon: DocumentChecked },
  { key: 'advanced_screening', name: '高级选股', desc: '复杂条件组合选股', icon: Filter },
  { key: 'batch_analysis', name: '批量分析', desc: '多股票并行分析', icon: Files },
  { key: 'export_reports', name: '导出报告', desc: '专业分析报告导出', icon: Document },
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

