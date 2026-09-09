<template>
  <div class="channel-configs-page">
    <el-alert type="success" :closable="false" show-icon style="margin-bottom: 16px">
      <template #title>
        <span style="display: flex; align-items: center; gap: 8px;">
          <el-tag type="success" size="small" effect="dark">高级</el-tag>
          <span>渠道推送：分析完成/预警时自动推送到飞书、钉钉、企业微信或邮件</span>
        </span>
      </template>
    </el-alert>

    <el-card class="page-card">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span>📣 推送渠道配置</span>
          <el-button type="primary" @click="showAddDialog">
            <el-icon><Plus /></el-icon> 添加渠道
          </el-button>
        </div>
      </template>

      <el-empty v-if="channels.length === 0" description="暂未配置推送渠道，点击右上角添加" />

      <el-table v-else :data="channels" style="width: 100%">
        <el-table-column label="渠道名称" prop="name" min-width="140" />
        <el-table-column label="类型" width="120">
          <template #default="{ row }">
            <el-tag :type="typeTagColor(row.type)" size="small">{{ typeLabel(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="订阅事件" min-width="200">
          <template #default="{ row }">
            <el-tag
              v-for="evt in row.events"
              :key="evt"
              size="small"
              style="margin-right: 4px; margin-bottom: 2px;"
            >{{ eventLabel(evt) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-switch
              v-model="row.enabled"
              @change="toggleChannel(row)"
              size="small"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleTest(row)" :loading="testing[row.channel_id]">测试</el-button>
            <el-button size="small" @click="showEditDialog(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 添加/编辑 Dialog -->
    <el-dialog v-model="dialogVisible" :title="editingChannel ? '编辑渠道' : '添加渠道'" width="560px">
      <el-form :model="form" label-width="110px" ref="formRef">
        <el-form-item label="渠道类型" prop="type" :rules="[{ required: true }]">
          <el-select v-model="form.type" :disabled="!!editingChannel" style="width: 100%">
            <el-option v-for="t in channelTypes" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="渠道名称" prop="name" :rules="[{ required: true, message: '请输入名称' }]">
          <el-input v-model="form.name" placeholder="如：飞书研究群" />
        </el-form-item>
        <el-form-item v-if="form.type !== 'email'" label="Webhook URL" prop="webhook_url"
          :rules="[{ required: true, message: '请输入 Webhook URL' }]">
          <el-input v-model="form.webhook_url" placeholder="https://open.feishu.cn/open-apis/bot/..." />
          <div class="form-tip">{{ webhookTip(form.type) }}</div>
        </el-form-item>
        <el-form-item v-if="form.type === 'email'" label="接收邮箱" prop="email_address"
          :rules="[{ required: true, message: '请输入接收邮箱' }]">
          <el-input v-model="form.email_address" placeholder="your@email.com" />
        </el-form-item>
        <el-form-item label="订阅事件">
          <el-checkbox-group v-model="form.events">
            <el-checkbox v-for="evt in eventTypes" :key="evt.value" :value="evt.value">
              {{ evt.label }}
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="立即启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
  getChannels, createChannel, updateChannel, deleteChannel, testChannel,
  type ChannelConfig, type ChannelConfigCreate
} from '@/api/channelConfigs'

const channels = ref<ChannelConfig[]>([])
const dialogVisible = ref(false)
const saving = ref(false)
const testing = reactive<Record<string, boolean>>({})
const editingChannel = ref<ChannelConfig | null>(null)
const formRef = ref()

const form = reactive<ChannelConfigCreate & { events: string[] }>({
  type: 'feishu',
  name: '',
  enabled: true,
  webhook_url: '',
  email_address: '',
  events: ['analysis_complete', 'alert'],
})

const channelTypes = [
  { value: 'feishu', label: '飞书' },
  { value: 'dingtalk', label: '钉钉' },
  { value: 'wechatwork', label: '企业微信' },
  { value: 'email', label: '邮件' },
]

const eventTypes = [
  { value: 'analysis_complete', label: '分析完成' },
  { value: 'alert', label: '预警通知' },
  { value: 'skill_gap', label: '工具缺口' },
  { value: 'system', label: '系统通知' },
]

type TagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

const typeLabel = (type: string) =>
  ({ feishu: '飞书', dingtalk: '钉钉', wechatwork: '企业微信', email: '邮件' }[type] || type)

const typeTagColor = (type: string): TagType => {
  const tagMap: Record<string, TagType> = {
    feishu: 'primary',
    dingtalk: 'warning',
    wechatwork: 'success',
    email: 'info'
  }
  return tagMap[type] || 'info'
}

const eventLabel = (evt: string) =>
  ({ analysis_complete: '分析完成', alert: '预警', skill_gap: '工具缺口', system: '系统' }[evt] || evt)

const webhookTip = (type: string) => ({
  feishu: '飞书开放平台 → 群组 → 机器人 → 自定义机器人 → 复制 Webhook 地址',
  dingtalk: '钉钉 → 群设置 → 机器人 → 自定义 → 复制 Webhook 地址',
  wechatwork: '企业微信 → 群聊 → 添加群机器人 → 复制 Webhook 地址',
}[type] || '')

const loadChannels = async () => {
  const res = await getChannels()
  channels.value = (res as any).channels || []
}

const resetForm = () => {
  Object.assign(form, {
    type: 'feishu', name: '', enabled: true,
    webhook_url: '', email_address: '', events: ['analysis_complete', 'alert']
  })
  editingChannel.value = null
}

const showAddDialog = () => { resetForm(); dialogVisible.value = true }

const showEditDialog = (row: ChannelConfig) => {
  editingChannel.value = row
  Object.assign(form, { ...row })
  dialogVisible.value = true
}

const handleSave = async () => {
  await formRef.value?.validate()
  saving.value = true
  try {
    if (editingChannel.value) {
      await updateChannel(editingChannel.value.channel_id, form)
      ElMessage.success('渠道更新成功')
    } else {
      await createChannel(form)
      ElMessage.success('渠道添加成功')
    }
    dialogVisible.value = false
    await loadChannels()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '操作失败')
  } finally {
    saving.value = false
  }
}

const toggleChannel = async (row: ChannelConfig) => {
  try {
    await updateChannel(row.channel_id, { enabled: row.enabled })
    ElMessage.success(row.enabled ? '已启用' : '已禁用')
  } catch {
    row.enabled = !row.enabled
    ElMessage.error('更新失败')
  }
}

const handleTest = async (row: ChannelConfig) => {
  testing[row.channel_id] = true
  try {
    const res = await testChannel(row.channel_id) as any
    ElMessage.success(res.message || '测试消息已发送')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '测试失败')
  } finally {
    testing[row.channel_id] = false
  }
}

const handleDelete = async (row: ChannelConfig) => {
  await ElMessageBox.confirm(`确认删除渠道「${row.name}」？`, '确认删除', { type: 'warning' })
  await deleteChannel(row.channel_id)
  ElMessage.success('已删除')
  await loadChannels()
}

onMounted(loadChannels)
</script>

<style scoped>
.channel-configs-page { max-width: 900px; margin: 0 auto; padding: 16px; }
.page-card { margin-bottom: 16px; }
.form-tip { font-size: 12px; color: #909399; margin-top: 4px; line-height: 1.4; }
</style>
