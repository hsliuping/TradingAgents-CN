<template>
  <div class="email-notification-page">
    <!-- PRO 功能标识 -->
    <el-alert
      type="warning"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
    >
      <template #title>
        <span style="display: flex; align-items: center; gap: 8px;">
          <el-tag type="warning" size="small" effect="dark">PRO</el-tag>
          <span>此功能为专业版功能，分析完成后自动发送邮件通知</span>
        </span>
      </template>
    </el-alert>

    <!-- SMTP 配置卡片 -->
    <el-card class="page-card">
      <template #header>
        <div class="card-header">
          <span>🔧 SMTP 服务器配置</span>
          <el-tag v-if="smtpEnabled" type="success" size="small">已配置</el-tag>
          <el-tag v-else type="warning" size="small">未配置</el-tag>
        </div>
      </template>

      <el-form :model="smtpConfig" label-width="140px" ref="smtpFormRef" :rules="smtpRules">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="SMTP服务器" prop="host">
              <el-input v-model="smtpConfig.host" placeholder="如: smtp.qq.com" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="端口" prop="port">
              <el-input-number v-model="smtpConfig.port" :min="1" :max="65535" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="用户名" prop="username">
              <el-input v-model="smtpConfig.username" placeholder="通常为邮箱地址" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="密码/授权码" prop="password">
              <el-input v-model="smtpConfig.password" type="password" show-password placeholder="QQ邮箱请使用授权码" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="发件人邮箱" prop="from_email">
              <el-input v-model="smtpConfig.from_email" placeholder="发送邮件时显示的邮箱" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="发件人名称">
              <el-input v-model="smtpConfig.from_name" placeholder="TradingAgents-CN" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="加密方式">
              <el-radio-group v-model="encryptionType" @change="onEncryptionChange">
                <el-radio value="tls">TLS (端口587)</el-radio>
                <el-radio value="ssl">SSL (端口465)</el-radio>
                <el-radio value="none">无</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item>
          <el-button type="primary" @click="saveSMTPConfig" :loading="savingSmtp">
            保存配置
          </el-button>
          <el-button @click="testSMTP" :loading="testingSmtp">
            测试连接
          </el-button>
          <span v-if="smtpSource" class="form-tip" style="margin-left: 15px">
            当前配置来源: {{ smtpSource === 'database' ? '数据库' : '环境变量' }}
          </span>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 通知设置卡片 -->
    <el-card class="page-card" style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>📧 邮件通知设置</span>
        </div>
      </template>

      <el-form :model="settings" label-width="140px" :disabled="!smtpEnabled">
        <!-- 基本设置 -->
        <el-divider content-position="left">基本设置</el-divider>

        <el-form-item label="启用邮件通知">
          <el-switch v-model="settings.enabled" />
        </el-form-item>

        <el-form-item label="接收邮箱">
          <el-input
            v-model="settings.email_address"
            placeholder="留空则使用注册邮箱"
            style="width: 300px"
          />
          <span class="form-tip">当前注册邮箱: {{ userEmail || '未设置' }}</span>
        </el-form-item>

        <!-- 通知类型 -->
        <el-divider content-position="left">通知类型</el-divider>

        <el-form-item label="单股分析结果">
          <el-switch v-model="settings.single_analysis" />
          <span class="form-tip">完成单只股票分析后发送邮件</span>
        </el-form-item>

        <el-form-item label="批量分析结果">
          <el-switch v-model="settings.batch_analysis" />
          <span class="form-tip">完成批量分析后发送汇总邮件</span>
        </el-form-item>

        <el-form-item label="定时分析报告">
          <el-switch v-model="settings.scheduled_analysis" />
          <span class="form-tip">定时任务执行完成后发送报告</span>
        </el-form-item>

        <el-form-item label="重要信号提醒">
          <el-switch v-model="settings.important_signals" />
          <span class="form-tip">发现重要买卖信号时发送提醒</span>
        </el-form-item>

        <el-form-item label="系统通知">
          <el-switch v-model="settings.system_notifications" />
          <span class="form-tip">系统维护、更新等通知</span>
        </el-form-item>

        <!-- 免打扰设置 -->
        <el-divider content-position="left">免打扰设置</el-divider>

        <el-form-item label="启用免打扰">
          <el-switch v-model="settings.quiet_hours_enabled" />
        </el-form-item>

        <el-form-item v-if="settings.quiet_hours_enabled" label="免打扰时段">
          <el-time-select
            v-model="settings.quiet_hours_start"
            :max-time="settings.quiet_hours_end"
            placeholder="开始时间"
            start="00:00"
            step="00:30"
            end="23:30"
            style="width: 120px"
          />
          <span style="margin: 0 10px">至</span>
          <el-time-select
            v-model="settings.quiet_hours_end"
            :min-time="settings.quiet_hours_start"
            placeholder="结束时间"
            start="00:00"
            step="00:30"
            end="23:30"
            style="width: 120px"
          />
        </el-form-item>

        <!-- 操作按钮 -->
        <el-form-item>
          <el-button type="primary" @click="saveSettings" :loading="saving">
            保存设置
          </el-button>
          <el-button @click="sendTest" :loading="testing" :disabled="!smtpEnabled || !settings.enabled">
            发送测试邮件
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 发送历史 -->
    <el-card class="page-card" style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>📋 发送历史</span>
          <el-button size="small" @click="loadHistory">刷新</el-button>
        </div>
      </template>

      <el-table :data="history" v-loading="loadingHistory" stripe>
        <el-table-column prop="subject" label="主题" min-width="200" />
        <el-table-column prop="to_email" label="收件人" width="200" />
        <el-table-column prop="email_type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag size="small">{{ getTypeLabel(row.email_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="发送时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.sent_at || row.created_at) }}
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="historyTotal > 0"
        style="margin-top: 15px; justify-content: flex-end"
        :current-page="historyPage"
        :page-size="historyPageSize"
        :total="historyTotal"
        layout="total, prev, pager, next"
        @current-change="handlePageChange"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import {
  getSMTPConfig,
  getEmailSettings,
  updateEmailSettings,
  sendTestEmail,
  getEmailHistory,
  updateSMTPConfig,
  testSMTPConnection,
  type EmailSettings,
  type SMTPConfig
} from '@/api/email'

const authStore = useAuthStore()

// SMTP 表单引用
const smtpFormRef = ref<FormInstance>()

// 状态
const smtpEnabled = ref(false)
const smtpSource = ref<string | null>(null)
const userEmail = ref('')
const saving = ref(false)
const savingSmtp = ref(false)
const testing = ref(false)
const testingSmtp = ref(false)
const loadingHistory = ref(false)
const encryptionType = ref<'tls' | 'ssl' | 'none'>('tls')

// SMTP 配置
const smtpConfig = reactive<SMTPConfig>({
  enabled: true,
  host: '',
  port: 587,
  username: '',
  password: '',
  from_email: '',
  from_name: 'TradingAgents-CN',
  use_tls: true,
  use_ssl: false
})

// SMTP 表单校验规则
const smtpRules = reactive<FormRules<SMTPConfig>>({
  host: [{ required: true, message: '请输入SMTP服务器地址', trigger: 'blur' }],
  port: [{ required: true, message: '请输入端口', trigger: 'blur' }],
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码或授权码', trigger: 'blur' }],
  from_email: [
    { required: true, message: '请输入发件人邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ]
})

// 设置
const settings = ref<EmailSettings>({
  enabled: false,
  email_address: '',
  single_analysis: true,
  batch_analysis: true,
  scheduled_analysis: true,
  important_signals: true,
  system_notifications: false,
  quiet_hours_enabled: false,
  quiet_hours_start: '22:00',
  quiet_hours_end: '08:00',
  format: 'html',
  language: 'zh'
})

// 历史记录
const history = ref<any[]>([])
const historyPage = ref(1)
const historyPageSize = ref(20)
const historyTotal = ref(0)

// 处理加密方式变更（el-radio-group change 事件兼容）
function onEncryptionChange(val: string | number | boolean | undefined) {
  handleEncryptionChange(val as 'tls' | 'ssl' | 'none')
}

function handleEncryptionChange(type: 'tls' | 'ssl' | 'none') {
  if (type === 'tls') {
    smtpConfig.use_tls = true
    smtpConfig.use_ssl = false
    smtpConfig.port = 587
  } else if (type === 'ssl') {
    smtpConfig.use_tls = false
    smtpConfig.use_ssl = true
    smtpConfig.port = 465
  } else {
    smtpConfig.use_tls = false
    smtpConfig.use_ssl = false
    smtpConfig.port = 25
  }
}

// 加载SMTP配置
async function loadSMTPConfig() {
  try {
    const res = await getSMTPConfig() as any
    if (res?.success) {
      const data = res.data
      smtpEnabled.value = data.configured
      smtpSource.value = data.source || null

      if (data.configured) {
        smtpConfig.host = data.host || ''
        smtpConfig.port = data.port || 587
        smtpConfig.username = data.username || ''
        smtpConfig.from_email = data.from_email || ''
        smtpConfig.from_name = data.from_name || 'TradingAgents-CN'
        smtpConfig.use_tls = data.use_tls ?? true
        smtpConfig.use_ssl = data.use_ssl ?? false

        // 设置加密方式
        if (data.use_ssl) {
          encryptionType.value = 'ssl'
        } else if (data.use_tls) {
          encryptionType.value = 'tls'
        } else {
          encryptionType.value = 'none'
        }
      }
    }
  } catch (e) {
    console.error('加载SMTP配置失败', e)
  }
}

// 保存 SMTP 配置
async function saveSMTPConfig() {
  if (!smtpFormRef.value) return

  await smtpFormRef.value.validate(async (valid) => {
    if (!valid) return

    savingSmtp.value = true
    try {
      const res = await updateSMTPConfig(smtpConfig) as any
      if (res?.success) {
        ElMessage.success(res.data?.message || 'SMTP配置已保存')
        smtpEnabled.value = true
        smtpSource.value = 'database'
      } else {
        ElMessage.error(res?.message || '保存失败')
      }
    } catch (e: any) {
      ElMessage.error(e?.message || '保存SMTP配置失败')
    } finally {
      savingSmtp.value = false
    }
  })
}

// 测试 SMTP 连接
async function testSMTP() {
  if (!smtpFormRef.value) return

  await smtpFormRef.value.validate(async (valid) => {
    if (!valid) return

    testingSmtp.value = true
    try {
      const res = await testSMTPConnection(smtpConfig) as any
      if (res?.success) {
        ElMessage.success(res.data?.message || 'SMTP连接测试成功')
      } else {
        ElMessage.error(res?.message || '连接测试失败')
      }
    } catch (e: any) {
      ElMessage.error(e?.message || 'SMTP连接测试失败')
    } finally {
      testingSmtp.value = false
    }
  })
}

// 加载用户设置
async function loadSettings() {
  const userId = authStore.user?.id
  if (!userId) return

  try {
    const res = await getEmailSettings(userId) as any
    if (res?.success) {
      const data = res.data
      settings.value = { ...settings.value, ...data.settings }
      userEmail.value = data.user_email || ''
    }
  } catch (e) {
    console.error('加载邮件设置失败', e)
  }
}

// 保存设置
async function saveSettings() {
  const userId = authStore.user?.id
  if (!userId) return

  saving.value = true
  try {
    const res = await updateEmailSettings(userId, settings.value) as any
    if (res?.success) {
      ElMessage.success('设置已保存')
    } else {
      ElMessage.error(res?.message || '保存失败')
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

// 发送测试邮件
async function sendTest() {
  const userId = authStore.user?.id
  if (!userId) return

  testing.value = true
  try {
    const res = await sendTestEmail(userId) as any
    if (res?.success) {
      ElMessage.success(res.data?.message || '测试邮件已发送')
      loadHistory()
    } else {
      ElMessage.error(res?.message || '发送失败')
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '发送失败')
  } finally {
    testing.value = false
  }
}

// 加载发送历史
async function loadHistory() {
  const userId = authStore.user?.id
  if (!userId) return

  loadingHistory.value = true
  try {
    const res = await getEmailHistory(userId, historyPage.value, historyPageSize.value) as any
    if (res?.success) {
      history.value = res.data?.items || []
      historyTotal.value = res.data?.total || 0
    }
  } catch (e) {
    console.error('加载发送历史失败', e)
  } finally {
    loadingHistory.value = false
  }
}

function handlePageChange(page: number) {
  historyPage.value = page
  loadHistory()
}

// 辅助函数
function getTypeLabel(type: string): string {
  const map: Record<string, string> = {
    single_analysis: '单股分析',
    batch_analysis: '批量分析',
    scheduled_analysis: '定时报告',
    important_signal: '信号提醒',
    system_notification: '系统通知',
    test_email: '测试邮件'
  }
  return map[type] || type
}

function getStatusType(status: string): 'success' | 'warning' | 'info' | 'danger' | 'primary' {
  const map: Record<string, 'success' | 'warning' | 'info' | 'danger' | 'primary'> = {
    sent: 'success',
    pending: 'warning',
    sending: 'info',
    failed: 'danger'
  }
  return map[status] || 'info'
}

function getStatusLabel(status: string): string {
  const map: Record<string, string> = {
    sent: '已发送',
    pending: '待发送',
    sending: '发送中',
    failed: '失败'
  }
  return map[status] || status
}

function formatTime(time: string): string {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

onMounted(() => {
  loadSMTPConfig()
  loadSettings()
  loadHistory()
})
</script>

<style scoped>
.email-notification-page {
  padding: 20px;
}

.page-card {
  max-width: 900px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.form-tip {
  margin-left: 10px;
  color: #909399;
  font-size: 12px;
}
</style>
