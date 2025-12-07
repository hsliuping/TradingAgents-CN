<template>
  <div class="scheduled-analysis-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>定时分析配置</span>
          <el-button type="primary" @click="showCreateDialog">
            <el-icon><Plus /></el-icon>
            创建配置
          </el-button>
        </div>
      </template>

      <el-table :data="configs" v-loading="loading">
        <el-table-column prop="name" label="配置名称" min-width="150" />
        <el-table-column prop="description" label="描述" min-width="200" />
        <el-table-column label="时间段" width="100" align="center">
          <template #default="{ row }">
            <el-tag>{{ row.time_slots?.length || 0 }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-switch
              v-model="row.enabled"
              @change="toggleEnabled(row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="最后运行" width="180">
          <template #default="{ row }">
            <span v-if="row.last_run_at">{{ formatTime(row.last_run_at) }}</span>
            <span v-else class="text-muted">未运行</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="editConfig(row)">
              <el-icon><Edit /></el-icon>
              编辑
            </el-button>
            <el-button link type="danger" @click="deleteConfig(row)">
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建/编辑配置对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? '创建配置' : '编辑配置'"
      width="900px"
      :close-on-click-modal="false"
    >
      <el-form :model="formData" :rules="formRules" ref="formRef" label-width="140px">
        <el-form-item label="配置名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入配置名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="formData.description"
            type="textarea"
            :rows="2"
            placeholder="请输入配置描述"
          />
        </el-form-item>

        <el-divider>默认分析参数</el-divider>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="默认分析深度">
              <el-select v-model="formData.default_analysis_depth" style="width: 100%">
                <el-option label="1级 - 快速" :value="1" />
                <el-option label="2级 - 基础" :value="2" />
                <el-option label="3级 - 标准" :value="3" />
                <el-option label="4级 - 深度" :value="4" />
                <el-option label="5级 - 全面" :value="5" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="发送邮件通知">
              <el-switch v-model="formData.send_email" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider>时间段配置</el-divider>
        <div class="time-slots">
          <div
            v-for="(slot, index) in formData.time_slots"
            :key="index"
            class="time-slot-item"
          >
            <el-card>
              <template #header>
                <div class="slot-header">
                  <span>时间段 {{ index + 1 }}</span>
                  <el-button
                    link
                    type="danger"
                    @click="removeTimeSlot(index)"
                  >
                    删除
                  </el-button>
                </div>
              </template>
              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item label="名称">
                    <el-input v-model="slot.name" placeholder="如：开盘前" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="CRON表达式">
                    <el-input v-model="slot.cron_expression" placeholder="如：0 9 * * 1-5" />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-form-item label="分析分组">
                <el-select
                  v-model="slot.group_ids"
                  multiple
                  placeholder="选择要分析的分组"
                  style="width: 100%"
                >
                  <el-option
                    v-for="group in groups"
                    :key="group.id"
                    :label="group.name"
                    :value="group.id"
                  />
                </el-select>
              </el-form-item>
              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item label="分析深度">
                    <el-select v-model="slot.analysis_depth" placeholder="使用默认值" clearable style="width: 100%">
                      <el-option label="1级 - 快速" :value="1" />
                      <el-option label="2级 - 基础" :value="2" />
                      <el-option label="3级 - 标准" :value="3" />
                      <el-option label="4级 - 深度" :value="4" />
                      <el-option label="5级 - 全面" :value="5" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="启用">
                    <el-switch v-model="slot.enabled" />
                  </el-form-item>
                </el-col>
              </el-row>
            </el-card>
          </div>
          <el-button @click="addTimeSlot" style="width: 100%; margin-top: 10px">
            <el-icon><Plus /></el-icon>
            添加时间段
          </el-button>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Edit, Delete } from '@element-plus/icons-vue'
import {
  getScheduledAnalysisConfigs,
  createScheduledAnalysisConfig,
  updateScheduledAnalysisConfig,
  deleteScheduledAnalysisConfig,
  enableScheduledAnalysisConfig,
  disableScheduledAnalysisConfig,
  type ScheduledAnalysisConfig,
  type ScheduledAnalysisConfigCreate,
  type ScheduledAnalysisConfigUpdate,
  type ScheduledAnalysisTimeSlot
} from '@/api/scheduled-analysis'
import { getWatchlistGroups, type WatchlistGroup } from '@/api/watchlist-groups'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import 'dayjs/locale/zh-cn'

dayjs.extend(relativeTime)
dayjs.locale('zh-cn')

const loading = ref(false)
const configs = ref<ScheduledAnalysisConfig[]>([])
const groups = ref<WatchlistGroup[]>([])

const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const submitting = ref(false)
const formRef = ref<FormInstance>()

const formData = ref<ScheduledAnalysisConfigCreate & { id?: string }>({
  name: '',
  description: '',
  enabled: true,
  time_slots: [],
  default_analysis_depth: 3,
  default_quick_analysis_model: 'qwen-plus',
  default_deep_analysis_model: 'qwen-max',
  notify_on_complete: true,
  notify_on_error: true,
  send_email: false
})

const formRules: FormRules = {
  name: [
    { required: true, message: '请输入配置名称', trigger: 'blur' }
  ]
}

// 格式化时间（相对时间格式）
const formatTime = (time: string) => {
  try {
    return dayjs(time).fromNow()
  } catch {
    return time
  }
}

// 加载配置列表
const loadConfigs = async () => {
  loading.value = true
  try {
    const res = await getScheduledAnalysisConfigs() as any
    if (res?.success) {
      configs.value = res.data.configs || []
    }
  } catch (error) {
    console.error('加载配置失败:', error)
    ElMessage.error('加载配置失败')
  } finally {
    loading.value = false
  }
}

// 加载分组列表
const loadGroups = async () => {
  try {
    const res = await getWatchlistGroups() as any
    if (res?.success) {
      groups.value = res.data.groups || []
    }
  } catch (error) {
    console.error('加载分组失败:', error)
  }
}

// 显示创建对话框
const showCreateDialog = () => {
  dialogMode.value = 'create'
  formData.value = {
    name: '',
    description: '',
    enabled: true,
    time_slots: [],
    default_analysis_depth: 3,
    default_quick_analysis_model: 'qwen-plus',
    default_deep_analysis_model: 'qwen-max',
    notify_on_complete: true,
    notify_on_error: true,
    send_email: false
  }
  dialogVisible.value = true
}

// 编辑配置
const editConfig = (config: ScheduledAnalysisConfig) => {
  dialogMode.value = 'edit'
  formData.value = {
    id: config.id,
    name: config.name,
    description: config.description,
    enabled: config.enabled,
    time_slots: JSON.parse(JSON.stringify(config.time_slots)),
    default_analysis_depth: config.default_analysis_depth,
    default_quick_analysis_model: config.default_quick_analysis_model,
    default_deep_analysis_model: config.default_deep_analysis_model,
    notify_on_complete: config.notify_on_complete,
    notify_on_error: config.notify_on_error,
    send_email: config.send_email
  }
  dialogVisible.value = true
}

// 添加时间段
const addTimeSlot = () => {
  if (!formData.value.time_slots) {
    formData.value.time_slots = []
  }
  formData.value.time_slots.push({
    name: '',
    cron_expression: '',
    enabled: true,
    group_ids: [],
    analysis_depth: undefined
  })
}

// 移除时间段
const removeTimeSlot = (index: number) => {
  formData.value.time_slots?.splice(index, 1)
}

// 提交表单
const submitForm = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    submitting.value = true
    try {
      if (dialogMode.value === 'create') {
        const res = await createScheduledAnalysisConfig(formData.value) as any
        if (res?.success) {
          ElMessage.success('创建成功')
          dialogVisible.value = false
          loadConfigs()
        } else {
          ElMessage.error(res?.message || '创建失败')
        }
      } else {
        const { id, ...updateData } = formData.value
        if (!id) return

        const res = await updateScheduledAnalysisConfig(id, updateData as ScheduledAnalysisConfigUpdate) as any
        if (res?.success) {
          ElMessage.success('更新成功')
          dialogVisible.value = false
          loadConfigs()
        } else {
          ElMessage.error(res?.message || '更新失败')
        }
      }
    } catch (error) {
      console.error('操作失败:', error)
      ElMessage.error('操作失败')
    } finally {
      submitting.value = false
    }
  })
}

// 切换启用状态
const toggleEnabled = async (config: ScheduledAnalysisConfig) => {
  try {
    const res = config.enabled
      ? await enableScheduledAnalysisConfig(config.id) as any
      : await disableScheduledAnalysisConfig(config.id) as any

    if (res?.success) {
      ElMessage.success(config.enabled ? '已启用' : '已禁用')
    } else {
      // 恢复状态
      config.enabled = !config.enabled
      ElMessage.error(res?.message || '操作失败')
    }
  } catch (error) {
    // 恢复状态
    config.enabled = !config.enabled
    console.error('切换状态失败:', error)
    ElMessage.error('操作失败')
  }
}

// 删除配置
const deleteConfig = async (config: ScheduledAnalysisConfig) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除配置"${config.name}"吗？`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    const res = await deleteScheduledAnalysisConfig(config.id) as any
    if (res?.success) {
      ElMessage.success('删除成功')
      loadConfigs()
    } else {
      ElMessage.error(res?.message || '删除失败')
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('删除失败:', error)
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  loadConfigs()
  loadGroups()
})
</script>

<style scoped lang="scss">
.scheduled-analysis-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.text-muted {
  color: #909399;
}

.time-slots {
  .time-slot-item {
    margin-bottom: 15px;
  }

  .slot-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
}
</style>

