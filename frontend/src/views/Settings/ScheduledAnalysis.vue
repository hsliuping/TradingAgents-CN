<template>
  <div class="scheduled-analysis-container">
    <!-- 高级学员功能标识 -->
    <el-alert
      type="success"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
    >
      <template #title>
        <span style="display: flex; align-items: center; gap: 8px;">
          <el-tag type="success" size="small" effect="dark">高级</el-tag>
          <span>高级学员专属功能，支持多时段定时分析，可为不同时段配置不同的分组和分析参数</span>
        </span>
      </template>
    </el-alert>

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
        <el-table-column label="操作" width="320" fixed="right">
          <template #default="{ row }">
            <el-button link type="success" @click="testConfig(row)" :loading="testingConfigId === row.id">
              <el-icon><Promotion /></el-icon>
              测试执行
            </el-button>
            <el-button link type="primary" @click="showHistory(row)">
              <el-icon><Timer /></el-icon>
              历史
            </el-button>
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

    <!-- 历史记录抽屉 -->
    <el-drawer
      v-model="historyDrawerVisible"
      :title="`执行历史 - ${currentConfigName}`"
      size="600px"
    >
      <el-table :data="historyList" v-loading="historyLoading" stripe>
        <el-table-column label="执行时间" width="160">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
            <div style="font-size: 12px; color: #909399;">
              {{ new Date(row.created_at).toLocaleString() }}
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="time_slot_name" label="时间段" width="100" />
        <el-table-column label="结果" min-width="120">
          <template #default="{ row }">
            <div style="display: flex; gap: 8px; flex-wrap: wrap;">
              <el-tag type="success" size="small">成功 {{ row.success_count }}</el-tag>
              <el-tag type="danger" size="small" v-if="row.failed_count > 0">失败 {{ row.failed_count }}</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'success' ? 'success' : (row.status === 'failed' ? 'danger' : 'warning')">
              {{ row.status === 'success' ? '成功' : (row.status === 'failed' ? '失败' : '部分') }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>

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
        <el-form-item label="默认分析分组">
          <div style="display: flex; gap: 10px; width: 100%; align-items: center;">
            <el-select
              v-model="formData.default_group_ids"
              multiple
              placeholder="选择默认要分析的分组（如果时间段未指定分组，将使用此设置）"
              style="flex: 1"
            >
              <el-option
                v-for="group in groups"
                :key="group.id"
                :label="group.name"
                :value="group.id"
              />
            </el-select>
            <el-tooltip content="前往分组管理创建或编辑分组" placement="top">
              <el-button type="primary" link @click="goToGroupManagement">
                <el-icon><Setting /></el-icon>
                配置
              </el-button>
            </el-tooltip>
          </div>
        </el-form-item>
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
                  <el-form-item label="时间设置">
                    <div class="cron-container">
                      <el-tabs v-model="(slot as any)._mode" type="border-card" class="cron-tabs">
                        <el-tab-pane label="简单模式" name="simple">
                          <div class="simple-mode-content">
                            <div class="presets-row">
                              <span class="presets-label">快速设置：</span>
                              <el-button-group size="small">
                                <el-button @click="applyPreset(slot, 'pre-market')">盘前 9:15</el-button>
                                <el-button @click="applyPreset(slot, 'market-open')">开盘 9:30</el-button>
                                <el-button @click="applyPreset(slot, 'market-close')">收盘 15:00</el-button>
                              </el-button-group>
                            </div>

                            <el-time-picker
                              v-model="(slot as any)._time"
                              format="HH:mm"
                              placeholder="选择时间"
                              style="width: 100%"
                              @change="updateCronFromUi(slot)"
                            />
                            
                            <div class="days-selector">
                              <el-checkbox-group 
                                v-model="(slot as any)._days" 
                                size="small"
                                @change="updateCronFromUi(slot)"
                              >
                                <el-checkbox-button 
                                  v-for="day in daysOptions" 
                                  :key="day.value" 
                                  :label="day.value"
                                >
                                  {{ day.label }}
                                </el-checkbox-button>
                              </el-checkbox-group>
                            </div>
                          </div>
                        </el-tab-pane>
                        
                        <el-tab-pane label="高级模式" name="advanced">
                          <div class="advanced-mode-content">
                            <el-input 
                              v-model="slot.cron_expression" 
                              placeholder="如：0 9 * * 1-5"
                              @input="debouncedFetchNextRuns(slot)"
                            >
                              <template #append>
                                <el-tooltip content="分 时 日 月 周 (0-6)" placement="top">
                                  <el-icon><QuestionFilled /></el-icon>
                                </el-tooltip>
                              </template>
                            </el-input>
                            <div class="cron-hint">
                              格式：分钟 小时 日期 月份 星期(0-6)
                            </div>
                          </div>
                        </el-tab-pane>
                      </el-tabs>

                      <!-- 执行预览 -->
                      <div class="cron-preview" v-if="(slot as any)._nextRuns && (slot as any)._nextRuns.length > 0">
                        <div class="preview-title">
                          <el-icon><Calendar /></el-icon> 接下来 5 次执行时间：
                        </div>
                        <div class="preview-list">
                          <div v-for="run in (slot as any)._nextRuns" :key="run" class="preview-item">
                            <span class="run-time">{{ run }}</span>
                            <span class="run-relative">{{ formatTime(run) }}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </el-form-item>
                </el-col>
              </el-row>
              <el-form-item label="分析分组">
                <div style="display: flex; gap: 10px; width: 100%; align-items: center;">
                  <el-select
                    v-model="slot.group_ids"
                    multiple
                    placeholder="选择要分析的分组"
                    style="flex: 1"
                  >
                    <el-option
                      v-for="group in groups"
                      :key="group.id"
                      :label="group.name"
                      :value="group.id"
                    />
                  </el-select>
                  <el-tooltip content="前往分组管理创建或编辑分组" placement="top">
                    <el-button type="primary" link @click="goToGroupManagement">
                      <el-icon><Setting /></el-icon>
                      配置
                    </el-button>
                  </el-tooltip>
                </div>
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
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { debounce } from 'lodash-es'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Edit, Delete, Setting, QuestionFilled, Timer, Calendar, Promotion } from '@element-plus/icons-vue'
import {
  getScheduledAnalysisConfigs,
  createScheduledAnalysisConfig,
  updateScheduledAnalysisConfig,
  deleteScheduledAnalysisConfig,
  enableScheduledAnalysisConfig,
  disableScheduledAnalysisConfig,
  testScheduledAnalysisConfig,
  previewCron,
  getScheduledAnalysisHistory,
  type ScheduledAnalysisConfig,
  type ScheduledAnalysisConfigCreate,
  type ScheduledAnalysisConfigUpdate,
  type ScheduledAnalysisTimeSlot,
  type ScheduledAnalysisHistory
} from '@/api/scheduled-analysis'
import { getWatchlistGroups, type WatchlistGroup } from '@/api/watchlist-groups'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import 'dayjs/locale/zh-cn'

dayjs.extend(relativeTime)
dayjs.locale('zh-cn')

const daysOptions = [
  { label: '周一', value: 1 },
  { label: '周二', value: 2 },
  { label: '周三', value: 3 },
  { label: '周四', value: 4 },
  { label: '周五', value: 5 },
  { label: '周六', value: 6 },
  { label: '周日', value: 0 },
]

// 解析 Cron 表达式到 UI 状态
const parseCronToUi = (cron: string) => {
  // 默认值：每天 09:00
  const defaultState = { 
    mode: 'simple', 
    time: new Date(new Date().setHours(9, 0, 0, 0)), 
    days: [1, 2, 3, 4, 5] // 默认周一到周五
  }
  
  if (!cron) return defaultState
  
  try {
    const parts = cron.split(' ')
    // 简单检查：必须是5段，且中间两段（日期、月份）必须是 *
    if (parts.length !== 5 || parts[2] !== '*' || parts[3] !== '*') {
      return { ...defaultState, mode: 'advanced' }
    }
    
    const minute = parseInt(parts[0])
    const hour = parseInt(parts[1])
    if (isNaN(minute) || isNaN(hour)) return { ...defaultState, mode: 'advanced' }
    
    const time = new Date()
    time.setHours(hour)
    time.setMinutes(minute)
    time.setSeconds(0)
    
    const dow = parts[4]
    let days: number[] = []
    
    if (dow === '*') {
      days = [1, 2, 3, 4, 5, 6, 0]
    } else if (dow.includes('-')) {
      const [start, end] = dow.split('-').map(Number)
      if (!isNaN(start) && !isNaN(end)) {
        // 处理跨周的情况比较复杂，这里只处理简单的递增
        if (start <= end) {
          for (let i = start; i <= end; i++) days.push(i)
        } else {
           // 比如 5-1 (周五到周一)，暂不支持解析为简单模式
           return { ...defaultState, mode: 'advanced' }
        }
      }
    } else {
      days = dow.split(',').map(Number).filter(n => !isNaN(n))
    }
    
    return { mode: 'simple', time, days }
  } catch (e) {
    return { ...defaultState, mode: 'advanced', nextRuns: [] }
  }
}

// 获取下几次执行时间
const fetchNextRuns = async (slot: any) => {
  if (!slot.cron_expression) return
  
  try {
    const res = await previewCron(slot.cron_expression) as any
    if (res?.success) {
      slot._nextRuns = res.data.next_runs
    }
  } catch (error) {
    console.error('预览 CRON 失败:', error)
  }
}

const debouncedFetchNextRuns = debounce(fetchNextRuns, 500)

// 从 UI 状态更新 Cron 表达式
const updateCronFromUi = (slot: any) => {
  if (slot._mode !== 'simple') return
  
  const time = slot._time as Date
  if (!time) return
  
  const minute = time.getMinutes()
  const hour = time.getHours()
  
  const days = (slot._days as number[] || []).sort((a, b) => a - b)
  
  let daysStr = '*'
  if (days.length === 0) {
    //如果不选天数，默认为 * (每天)
    daysStr = '*' 
  } else if (days.length < 7) {
    // 检查是否连续
    let isConsecutive = true
    for (let i = 0; i < days.length - 1; i++) {
      if (days[i+1] !== days[i] + 1) {
        isConsecutive = false
        break
      }
    }
    
    if (isConsecutive && days.length > 1) {
      daysStr = `${days[0]}-${days[days.length-1]}`
    } else {
      daysStr = days.join(',')
    }
  }
  
  slot.cron_expression = `${minute} ${hour} * * ${daysStr}`
  debouncedFetchNextRuns(slot)
}

// 快速预设
const applyPreset = (slot: any, type: string) => {
  const now = new Date()
  let hour = 9
  let minute = 0
  let days = [1, 2, 3, 4, 5] // 工作日

  switch (type) {
    case 'pre-market': // 盘前 09:15
      hour = 9
      minute = 15
      break
    case 'market-open': // 开盘 09:30
      hour = 9
      minute = 30
      break
    case 'market-close': // 收盘 15:00
      hour = 15
      minute = 0
      break
    case 'everyday-9am':
      hour = 9
      minute = 0
      days = [0, 1, 2, 3, 4, 5, 6]
      break
  }

  const time = new Date()
  time.setHours(hour, minute, 0, 0)
  
  slot._time = time
  slot._days = days
  slot._mode = 'simple'
  updateCronFromUi(slot)
}

const router = useRouter()
const loading = ref(false)
const configs = ref<ScheduledAnalysisConfig[]>([])
const groups = ref<WatchlistGroup[]>([])

const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const submitting = ref(false)
const formRef = ref<FormInstance>()

// 测试执行相关
const testingConfigId = ref<string | null>(null)

// 历史记录相关
const historyDrawerVisible = ref(false)
const historyLoading = ref(false)
const historyList = ref<ScheduledAnalysisHistory[]>([])
const currentConfigName = ref('')

const formData = ref<ScheduledAnalysisConfigCreate & { id?: string }>({
  name: '',
  description: '',
  enabled: true,
  time_slots: [],
  default_group_ids: [],
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

// 跳转到分组管理
const goToGroupManagement = () => {
  const routeData = router.resolve({ name: 'WatchlistGroups' })
  window.open(routeData.href, '_blank')
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
    default_group_ids: [],
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
  const timeSlots = JSON.parse(JSON.stringify(config.time_slots)).map((slot: any) => {
    const uiState = parseCronToUi(slot.cron_expression)
    const newSlot = {
      ...slot,
      _mode: uiState.mode,
      _time: uiState.time,
      _days: uiState.days,
      _nextRuns: []
    }
    // 立即获取一次预览
    fetchNextRuns(newSlot)
    return newSlot
  })
  
  formData.value = {
    id: config.id,
    name: config.name,
    description: config.description,
    enabled: config.enabled,
    time_slots: timeSlots,
    default_group_ids: config.default_group_ids || [],
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
  
  const defaultState = parseCronToUi('')
  const slot: any = {
    name: '',
    cron_expression: '0 9 * * 1-5', // 默认值
    enabled: true,
    group_ids: [],
    analysis_depth: undefined,
    _mode: defaultState.mode,
    _time: defaultState.time,
    _days: defaultState.days,
    _nextRuns: []
  }
  
  formData.value.time_slots.push(slot)
  // 立即获取一次预览
  fetchNextRuns(slot)
}

// 移除时间段
const removeTimeSlot = (index: number) => {
  formData.value.time_slots?.splice(index, 1)
}

// 查看历史记录
const showHistory = async (config: ScheduledAnalysisConfig) => {
  currentConfigName.value = config.name
  historyDrawerVisible.value = true
  historyLoading.value = true
  historyList.value = []
  
  try {
    const res = await getScheduledAnalysisHistory(config.id) as any
    if (res?.success) {
      historyList.value = res.data.history || []
    }
  } catch (error) {
    console.error('加载历史记录失败:', error)
    ElMessage.error('加载历史记录失败')
  } finally {
    historyLoading.value = false
  }
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

// 测试执行配置
const testConfig = async (config: ScheduledAnalysisConfig) => {
  try {
    // 检查是否有启用的时间段
    const enabledSlots = config.time_slots?.filter(slot => slot.enabled) || []
    if (enabledSlots.length === 0) {
      ElMessage.warning('该配置没有启用的时间段，无法测试')
      return
    }

    // 检查是否有选择分组
    const firstSlot = enabledSlots[0]
    if (!firstSlot.group_ids || firstSlot.group_ids.length === 0) {
      ElMessage.warning(`时间段"${firstSlot.name}"未配置分组，无法测试`)
      return
    }

    await ElMessageBox.confirm(
      `将立即执行时间段"${firstSlot.name}"的分析任务，确定继续吗？`,
      '测试执行',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'info'
      }
    )

    testingConfigId.value = config.id
    const res = await testScheduledAnalysisConfig(config.id) as any

    if (res?.success) {
      ElMessage.success({
        message: res.data?.message || '测试任务已启动，请稍后查看执行历史',
        duration: 5000
      })
      // 3秒后刷新配置列表（更新最后运行时间）
      setTimeout(() => {
        loadConfigs()
      }, 3000)
    } else {
      ElMessage.error(res?.message || '测试执行失败')
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('测试执行失败:', error)
      ElMessage.error('测试执行失败')
    }
  } finally {
    testingConfigId.value = null
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

.cron-container {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cron-tabs :deep(.el-tabs__content) {
  padding: 15px;
}

.simple-mode-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.presets-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.presets-label {
  font-size: 12px;
  color: #909399;
}

.days-selector {
  margin-top: 4px;
}

.advanced-mode-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cron-hint {
  font-size: 12px;
  color: #909399;
  padding-left: 4px;
}

.cron-preview {
  background-color: var(--el-fill-color-light);
  border-radius: 4px;
  padding: 12px;
  border: 1px solid var(--el-border-color-lighter);
}

.preview-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-primary);
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.preview-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.preview-item {
  font-size: 12px;
  color: var(--el-text-color-regular);
  display: flex;
  justify-content: space-between;
  padding: 2px 0;
}

.run-time {
  font-family: monospace;
}

.run-relative {
  color: #909399;
}
</style>

