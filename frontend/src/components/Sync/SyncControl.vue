<template>
  <div class="sync-control">
    <el-card class="control-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <el-icon class="header-icon"><Refresh /></el-icon>
          <span class="header-title">同步控制</span>
        </div>
      </template>

      <div class="control-content">
        <!-- 当前同步状态 -->
        <div class="sync-status-section">
          <h4 class="section-title">当前状态</h4>
          <div class="status-display">
            <el-tag 
              :type="getStatusType(syncStatus?.status)"
              size="large"
              class="status-tag"
            >
              {{ getStatusText(syncStatus?.status) }}
            </el-tag>
            <div v-if="syncStatus?.status === 'running'" class="progress-info">
              <el-progress 
                :percentage="getProgress()"
                :status="syncStatus.errors > 0 ? 'warning' : 'success'"
                :stroke-width="8"
              />
              <div class="progress-text">
                正在同步中... {{ syncStatus.total > 0 ? `${syncStatus.updated + syncStatus.inserted}/${syncStatus.total}` : '' }}
              </div>
            </div>
          </div>
        </div>

        <!-- 同步统计 -->
        <div v-if="syncStatus && syncStatus.status !== 'never_run'" class="sync-stats-section">
          <h4 class="section-title">同步统计</h4>
          <div class="stats-grid">
            <div class="stat-item">
              <div class="stat-value">{{ syncStatus.total }}</div>
              <div class="stat-label">总数</div>
            </div>
            <div class="stat-item">
              <div class="stat-value success">{{ syncStatus.inserted }}</div>
              <div class="stat-label">新增</div>
            </div>
            <div class="stat-item">
              <div class="stat-value primary">{{ syncStatus.updated }}</div>
              <div class="stat-label">更新</div>
            </div>
            <div class="stat-item">
              <div class="stat-value danger">{{ syncStatus.errors }}</div>
              <div class="stat-label">错误</div>
            </div>
          </div>
          
          <!-- 使用的数据源 -->
          <div v-if="syncStatus.data_sources_used?.length" class="sources-used">
            <div class="sources-label">使用的数据源:</div>
            <div class="sources-tags">
              <el-tag
                v-for="source in syncStatus.data_sources_used"
                :key="source"
                size="small"
                type="info"
              >
                {{ source }}
              </el-tag>
            </div>
          </div>

          <!-- 最后同步时间 -->
          <div v-if="syncStatus.finished_at" class="sync-time">
            <div class="time-label">完成时间:</div>
            <div class="time-value">{{ formatTime(syncStatus.finished_at) }}</div>
          </div>
        </div>

        <!-- 同步控制 -->
        <div class="sync-controls-section">
          <h4 class="section-title">同步操作</h4>
          
          <!-- 数据源选择 -->
          <div class="source-selection">
            <el-form :model="syncForm" label-width="120px" size="default">
              <el-form-item label="优先数据源:">
                <el-select
                  v-model="syncForm.preferred_sources"
                  multiple
                  placeholder="选择优先使用的数据源（可选）"
                  style="width: 100%"
                  clearable
                >
                  <el-option
                    v-for="source in availableSources"
                    :key="source.name"
                    :label="source.name.toUpperCase()"
                    :value="source.name"
                    :disabled="!source.available"
                  >
                    <span>{{ source.name.toUpperCase() }}</span>
                    <span style="float: right; color: var(--el-text-color-secondary);">
                      优先级: {{ source.priority }}
                    </span>
                  </el-option>
                </el-select>
              </el-form-item>
              
              <el-form-item label="强制同步:">
                <el-switch
                  v-model="syncForm.force"
                  active-text="是"
                  inactive-text="否"
                />
                <div class="form-help">
                  强制同步将忽略正在运行的同步任务
                </div>
              </el-form-item>
            </el-form>
          </div>

          <!-- 操作按钮 -->
          <div class="action-buttons">
            <el-button
              type="primary"
              size="large"
              :loading="syncing || syncStatus?.status === 'running'"
              :disabled="syncStatus?.status === 'running' && !syncForm.force"
              @click="startSync"
            >
              <el-icon><Refresh /></el-icon>
              {{ getSyncButtonText() }}
            </el-button>
            
            <el-button
              size="large"
              :loading="refreshing"
              @click="refreshStatus"
            >
              <el-icon><RefreshRight /></el-icon>
              刷新状态
            </el-button>
            
            <el-button
              size="large"
              type="warning"
              :loading="clearingCache"
              @click="clearCache"
            >
              <el-icon><Delete /></el-icon>
              清空缓存
            </el-button>

            <!-- 临时测试按钮 -->


            <el-button
              size="large"
              type="success"
              :loading="syncing"
              @click="forceSync"
            >
              🔄 强制重新同步
            </el-button>
          </div>
        </div>

        <!-- 错误信息 -->
        <div v-if="syncStatus?.message && syncStatus.status === 'failed'" class="error-section">
          <el-alert
            :title="syncStatus.message"
            type="error"
            :closable="false"
            show-icon
          />
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, RefreshRight, Delete } from '@element-plus/icons-vue'
import { 
  getSyncStatus, 
  runStockBasicsSync, 
  clearSyncCache,
  getDataSourcesStatus,
  type SyncStatus, 
  type DataSourceStatus 
} from '@/api/sync'

// Props
interface Props {
  autoRefresh?: boolean
  refreshInterval?: number
}

const props = withDefaults(defineProps<Props>(), {
  autoRefresh: true,
  refreshInterval: 5000
})

// Emits
const emit = defineEmits<{
  syncCompleted: [status: string]
}>()

// 响应式数据
const syncing = ref(false)
const refreshing = ref(false)
const clearingCache = ref(false)
const syncStatus = ref<SyncStatus | null>(null)
const availableSources = ref<DataSourceStatus[]>([])
const refreshTimer = ref<NodeJS.Timeout | null>(null)

// 表单数据
const syncForm = reactive({
  preferred_sources: [] as string[],
  force: false
})

// 获取同步状态
const fetchSyncStatus = async () => {
  try {
    const response = await getSyncStatus()
    if (response.success) {
      syncStatus.value = response.data
    }
  } catch (err: any) {
    console.error('获取同步状态失败:', err)
  }
}

// 获取数据源状态
const fetchDataSources = async () => {
  try {
    const response = await getDataSourcesStatus()
    if (response.success) {
      availableSources.value = response.data.sort((a, b) => b.priority - a.priority) // 倒序：优先级高的在前
    }
  } catch (err: any) {
    console.error('获取数据源状态失败:', err)
  }
}

// 开始同步
const startSync = async () => {
  try {
    syncing.value = true
    
    const params = {
      force: syncForm.force,
      preferred_sources: syncForm.preferred_sources.length > 0 
        ? syncForm.preferred_sources.join(',') 
        : undefined
    }
    
    const response = await runStockBasicsSync(params)
    if (response.success) {
      const responseStatus = response.data.status
      console.log('🚀 同步任务启动成功，当前状态:', responseStatus)

      syncStatus.value = response.data

      if (responseStatus === 'running') {
        ElMessage.success('同步任务已启动')
        // 开始轮询状态
        startStatusPolling()
        console.log('🔄 状态轮询已启动，间隔:', props.refreshInterval, 'ms')
      } else if (responseStatus === 'success' || responseStatus === 'success_with_errors' || responseStatus === 'failed') {
        // 同步已经完成，直接显示结果
        ElMessage.success('同步任务已完成')
        console.log('✅ 同步已完成，直接显示通知')
        showSyncCompletionNotification(responseStatus)
      } else {
        ElMessage.info(`同步状态: ${responseStatus}`)
      }
    } else {
      ElMessage.error(`同步启动失败: ${response.message}`)
    }
  } catch (err: any) {
    console.error('启动同步失败:', err)
    ElMessage.error(`同步启动失败: ${err.message}`)
  } finally {
    syncing.value = false
  }
}

// 刷新状态
const refreshStatus = async () => {
  refreshing.value = true
  await fetchSyncStatus()
  refreshing.value = false
  ElMessage.success('状态已刷新')
}

// 清空缓存
const clearCache = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要清空同步缓存吗？这将删除所有缓存的数据。',
      '确认清空缓存',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    clearingCache.value = true
    const response = await clearSyncCache()
    if (response.success) {
      ElMessage.success('缓存已清空')
    } else {
      ElMessage.error(`清空缓存失败: ${response.message}`)
    }
  } catch (err: any) {
    if (err !== 'cancel') {
      console.error('清空缓存失败:', err)
      ElMessage.error(`清空缓存失败: ${err.message}`)
    }
  } finally {
    clearingCache.value = false
  }
}

// 开始状态轮询
const startStatusPolling = () => {
  if (refreshTimer.value) {
    clearInterval(refreshTimer.value)
  }

  if (props.autoRefresh) {
    let previousStatus = syncStatus.value?.status
    let pollCount = 0
    const maxPolls = 60 // 最多轮询60次（5分钟）

    console.log('🔄 开始状态轮询，初始状态:', previousStatus)

    refreshTimer.value = setInterval(async () => {
      pollCount++
      await fetchSyncStatus()

      const currentStatus = syncStatus.value?.status
      console.log(`🔍 轮询 #${pollCount}: ${previousStatus} -> ${currentStatus}`)

      // 检查状态变化，提供用户反馈
      if (previousStatus === 'running' && currentStatus && currentStatus !== 'running') {
        // 同步完成，显示结果通知
        console.log('🎉 检测到同步完成，状态从', previousStatus, '变为', currentStatus)
        showSyncCompletionNotification(currentStatus)
        stopStatusPolling()
        return
      }

      // 更新前一个状态
      previousStatus = currentStatus

      // 如果同步完成但没有状态变化检测到，也停止轮询
      if (currentStatus && !['running'].includes(currentStatus)) {
        console.log('🛑 检测到非运行状态，停止轮询:', currentStatus)
        stopStatusPolling()
        return
      }

      // 防止无限轮询
      if (pollCount >= maxPolls) {
        console.log('⏰ 轮询次数达到上限，停止轮询')
        stopStatusPolling()
      }
    }, props.refreshInterval)
  }
}

// 停止状态轮询
const stopStatusPolling = () => {
  if (refreshTimer.value) {
    clearInterval(refreshTimer.value)
    refreshTimer.value = null
  }
}

// 显示同步完成通知
const showSyncCompletionNotification = (status: string) => {
  console.log('📢 显示同步完成通知，状态:', status)

  const stats = syncStatus.value
  if (!stats) {
    console.warn('⚠️ 无法获取同步统计信息')
    return
  }

  const total = stats.total || 0
  const inserted = stats.inserted || 0
  const updated = stats.updated || 0
  const errors = stats.errors || 0

  console.log('📊 同步统计:', { total, inserted, updated, errors })

  let title = ''
  let message = ''
  let type: 'success' | 'warning' | 'error' = 'success'

  if (status === 'success') {
    title = '🎉 同步完成！'
    message = `处理了 ${total} 条记录，新增 ${inserted} 条，更新 ${updated} 条`
    type = 'success'
  } else if (status === 'success_with_errors') {
    title = '⚠️ 同步完成但有错误！'
    message = `处理了 ${total} 条记录，新增 ${inserted} 条，更新 ${updated} 条，错误 ${errors} 条`
    type = 'warning'
  } else if (status === 'failed') {
    title = '❌ 同步失败！'
    message = stats.message || '未知错误'
    type = 'error'
  }

  // 显示页面通知
  ElMessage({
    message: `${title} ${message}`,
    type,
    duration: 8000,
    showClose: true
  })

  // 发射同步完成事件，通知父组件
  emit('syncCompleted', status)

  // 如果有使用的数据源信息，也显示出来
  if (stats.data_sources_used && stats.data_sources_used.length > 0) {
    setTimeout(() => {
      ElMessage({
        message: `📡 使用的数据源: ${stats.data_sources_used.join(', ')}`,
        type: 'info',
        duration: 6000,
        showClose: true
      })
    }, 1000)
  }
}

// 获取状态类型
const getStatusType = (status?: string) => {
  const typeMap: Record<string, string> = {
    idle: 'info',
    running: 'warning',
    success: 'success',
    success_with_errors: 'warning',
    failed: 'danger',
    never_run: 'info'
  }
  return typeMap[status || 'never_run'] || 'info'
}

// 获取状态文本
const getStatusText = (status?: string) => {
  const textMap: Record<string, string> = {
    idle: '空闲',
    running: '运行中',
    success: '成功',
    success_with_errors: '部分成功',
    failed: '失败',
    never_run: '未运行'
  }
  return textMap[status || 'never_run'] || '未知'
}

// 获取进度百分比
const getProgress = () => {
  if (!syncStatus.value || syncStatus.value.total === 0) return 0
  return Math.round(((syncStatus.value.inserted + syncStatus.value.updated) / syncStatus.value.total) * 100)
}

// 获取同步按钮文本
const getSyncButtonText = () => {
  if (syncing.value) return '启动中...'

  const status = syncStatus.value?.status
  if (status === 'running') {
    const progress = getProgress()
    if (progress > 0) {
      return `同步中 ${progress}%`
    }
    return '同步中...'
  }

  return '开始同步'
}

// 格式化时间
const formatTime = (isoString: string) => {
  try {
    const date = new Date(isoString)
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  } catch {
    return isoString
  }
}



// 强制重新同步
const forceSync = async () => {
  console.log('🔄 强制重新同步')

  // 先清空当前状态
  syncStatus.value = null

  // 设置强制同步标志
  const originalForce = syncForm.force
  syncForm.force = true

  try {
    await startSync()
  } finally {
    // 恢复原始设置
    syncForm.force = originalForce
  }
}

// 组件挂载
onMounted(async () => {
  await Promise.all([
    fetchSyncStatus(),
    fetchDataSources()
  ])
  
  // 如果正在同步，开始轮询
  if (syncStatus.value?.status === 'running') {
    startStatusPolling()
  }
})

// 组件卸载
onUnmounted(() => {
  stopStatusPolling()
})
</script>

<style scoped lang="scss">
.sync-control {
  .control-card {
    .card-header {
      display: flex;
      align-items: center;
      
      .header-icon {
        margin-right: 8px;
        color: var(--el-color-primary);
      }
      
      .header-title {
        font-weight: 600;
      }
    }
  }

  .control-content {
    .section-title {
      margin: 0 0 16px 0;
      font-size: 16px;
      font-weight: 600;
      color: var(--el-text-color-primary);
    }

    .sync-status-section {
      margin-bottom: 24px;
      
      .status-display {
        .status-tag {
          margin-bottom: 12px;
        }
        
        .progress-info {
          .progress-text {
            margin-top: 8px;
            font-size: 14px;
            color: var(--el-text-color-regular);
          }
        }
      }
    }

    .sync-stats-section {
      margin-bottom: 24px;
      
      .stats-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
        margin-bottom: 16px;
        
        .stat-item {
          text-align: center;
          padding: 16px;
          border: 1px solid var(--el-border-color-light);
          border-radius: 8px;
          
          .stat-value {
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 4px;
            
            &.success { color: var(--el-color-success); }
            &.primary { color: var(--el-color-primary); }
            &.danger { color: var(--el-color-danger); }
          }
          
          .stat-label {
            font-size: 14px;
            color: var(--el-text-color-secondary);
          }
        }
      }
      
      .sources-used {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
        margin-bottom: 12px;

        .sources-label {
          font-size: 14px;
          color: var(--el-text-color-regular);
        }
      }

      .sync-time {
        display: flex;
        align-items: center;
        gap: 8px;

        .time-label {
          font-size: 14px;
          color: var(--el-text-color-regular);
        }

        .time-value {
          font-size: 14px;
          color: var(--el-text-color-primary);
          font-weight: 500;
        }
      }
    }

    .sync-controls-section {
      margin-bottom: 24px;
      
      .source-selection {
        margin-bottom: 20px;
        
        .form-help {
          font-size: 12px;
          color: var(--el-text-color-secondary);
          margin-top: 4px;
        }
      }
      
      .action-buttons {
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
      }
    }

    .error-section {
      margin-top: 16px;
    }
  }
}

@media (max-width: 768px) {
  .sync-control {
    .control-content {
      .sync-stats-section {
        .stats-grid {
          grid-template-columns: repeat(2, 1fr);
        }
      }
      
      .sync-controls-section {
        .action-buttons {
          flex-direction: column;
          
          .el-button {
            width: 100%;
          }
        }
      }
    }
  }
}
</style>
