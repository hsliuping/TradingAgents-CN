<template>
  <div class="multi-source-sync-card">
    <el-card class="sync-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-icon class="header-icon"><Connection /></el-icon>
            <span class="header-title">多数据源同步</span>
          </div>
          <div class="header-right">
            <el-button 
              type="primary" 
              size="small" 
              link
              @click="goToSyncPage"
            >
              管理
              <el-icon><ArrowRight /></el-icon>
            </el-button>
          </div>
        </div>
      </template>

      <div v-loading="loading" class="card-content">
        <!-- 同步状态 -->
        <div class="sync-status-section">
          <div class="status-display">
            <el-tag 
              :type="getStatusType(syncStatus?.status)"
              size="large"
              class="status-tag"
            >
              {{ getStatusText(syncStatus?.status) }}
            </el-tag>
            
            <div v-if="syncStatus?.status === 'running'" class="progress-display">
              <el-progress 
                :percentage="getProgress()"
                :status="syncStatus.errors > 0 ? 'warning' : 'success'"
                :stroke-width="6"
                :show-text="false"
              />
              <div class="progress-text">
                {{ syncStatus.total > 0 ? `${syncStatus.updated + syncStatus.inserted}/${syncStatus.total}` : '同步中...' }}
              </div>
            </div>
          </div>
        </div>

        <!-- 数据源状态 -->
        <div class="sources-status-section">
          <div class="sources-header">
            <span class="sources-title">数据源状态</span>
            <el-button 
              size="small" 
              type="primary" 
              link
              :loading="refreshing"
              @click="refreshStatus"
            >
              <el-icon><Refresh /></el-icon>
            </el-button>
          </div>
          
          <div class="sources-list">
            <div 
              v-for="source in dataSources" 
              :key="source.name"
              class="source-item"
              :class="{ 'available': source.available }"
            >
              <div class="source-info">
                <span class="source-name">{{ source.name.toUpperCase() }}</span>
                <el-icon 
                  :class="source.available ? 'status-success' : 'status-error'"
                >
                  <component :is="source.available ? 'SuccessFilled' : 'CircleCloseFilled'" />
                </el-icon>
              </div>
              <div class="source-priority">优先级: {{ source.priority }}</div>
            </div>
          </div>
        </div>

        <!-- 快速操作 -->
        <div class="quick-actions-section">
          <el-button
            type="primary"
            size="small"
            :loading="syncing"
            :disabled="syncStatus?.status === 'running'"
            @click="quickSync"
            style="width: 100%"
          >
            <el-icon><Refresh /></el-icon>
            {{ syncStatus?.status === 'running' ? '同步中...' : '快速同步' }}
          </el-button>
        </div>

        <!-- 最近同步信息 -->
        <div v-if="syncStatus && syncStatus.status !== 'never_run'" class="last-sync-section">
          <div class="last-sync-info">
            <div class="sync-stats">
              <span class="stat-item">总数: {{ syncStatus.total }}</span>
              <span class="stat-item success">更新: {{ syncStatus.updated }}</span>
              <span class="stat-item danger">错误: {{ syncStatus.errors }}</span>
            </div>
            <div v-if="syncStatus.finished_at" class="sync-time">
              {{ formatLastSyncTime(syncStatus.finished_at) }}
            </div>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { 
  Connection, 
  ArrowRight, 
  Refresh, 
  SuccessFilled, 
  CircleCloseFilled 
} from '@element-plus/icons-vue'
import { 
  getSyncStatus, 
  getDataSourcesStatus, 
  runStockBasicsSync,
  type SyncStatus, 
  type DataSourceStatus 
} from '@/api/sync'

// 路由
const router = useRouter()

// 响应式数据
const loading = ref(false)
const refreshing = ref(false)
const syncing = ref(false)
const syncStatus = ref<SyncStatus | null>(null)
const dataSources = ref<DataSourceStatus[]>([])
const refreshTimer = ref<NodeJS.Timeout | null>(null)

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
      dataSources.value = response.data
        .sort((a, b) => b.priority - a.priority) // 倒序：优先级高的在前
        .slice(0, 3) // 只显示前3个数据源
    }
  } catch (err: any) {
    console.error('获取数据源状态失败:', err)
  }
}

// 刷新状态
const refreshStatus = async () => {
  refreshing.value = true
  await Promise.all([
    fetchSyncStatus(),
    fetchDataSources()
  ])
  refreshing.value = false
}

// 快速同步
const quickSync = async () => {
  try {
    syncing.value = true
    
    const response = await runStockBasicsSync()
    if (response.success) {
      ElMessage.success('同步任务已启动')
      syncStatus.value = response.data
      startStatusPolling()
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

// 跳转到同步管理页面
const goToSyncPage = () => {
  router.push('/settings/sync')
}

// 开始状态轮询
const startStatusPolling = () => {
  if (refreshTimer.value) {
    clearInterval(refreshTimer.value)
  }
  
  refreshTimer.value = setInterval(async () => {
    await fetchSyncStatus()
    
    // 如果同步完成，停止轮询
    if (syncStatus.value?.status && !['running'].includes(syncStatus.value.status)) {
      stopStatusPolling()
    }
  }, 3000)
}

// 停止状态轮询
const stopStatusPolling = () => {
  if (refreshTimer.value) {
    clearInterval(refreshTimer.value)
    refreshTimer.value = null
  }
}

// 获取状态类型
const getStatusType = (status?: SyncStatus['status'] | string): 'success' | 'info' | 'warning' | 'danger' => {
  const typeMap: Record<string, 'success' | 'info' | 'warning' | 'danger'> = {
    idle: 'info',
    running: 'warning',
    success: 'success',
    success_with_errors: 'warning',
    failed: 'danger',
    never_run: 'info'
  }
  return typeMap[status ?? 'never_run'] ?? 'info'
}

// 获取状态文本
const getStatusText = (status?: SyncStatus['status'] | string) => {
  const textMap: Record<string, string> = {
    idle: '空闲',
    running: '运行中',
    success: '成功',
    success_with_errors: '部分成功',
    failed: '失败',
    never_run: '未运行'
  }
  return textMap[status ?? 'never_run'] ?? '未知'
}

// 获取进度百分比
const getProgress = () => {
  if (!syncStatus.value || syncStatus.value.total === 0) return 0
  return Math.round(((syncStatus.value.inserted + syncStatus.value.updated) / syncStatus.value.total) * 100)
}

// 格式化最后同步时间
const formatLastSyncTime = (timeStr: string) => {
  const date = new Date(timeStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  
  if (diff < 60000) {
    return '刚刚完成'
  } else if (diff < 3600000) {
    return `${Math.floor(diff / 60000)}分钟前`
  } else if (diff < 86400000) {
    return `${Math.floor(diff / 3600000)}小时前`
  } else {
    return date.toLocaleDateString('zh-CN')
  }
}

// 组件挂载
onMounted(async () => {
  loading.value = true
  await Promise.all([
    fetchSyncStatus(),
    fetchDataSources()
  ])
  loading.value = false
  
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
.multi-source-sync-card {
  .sync-card {
    height: 100%;
    
    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      
      .header-left {
        display: flex;
        align-items: center;
        
        .header-icon {
          margin-right: 8px;
          color: var(--el-color-primary);
        }
        
        .header-title {
          font-weight: 600;
          font-size: 16px;
        }
      }
    }
  }

  .card-content {
    .sync-status-section {
      margin-bottom: 16px;
      
      .status-display {
        .status-tag {
          margin-bottom: 8px;
        }
        
        .progress-display {
          .progress-text {
            margin-top: 4px;
            font-size: 12px;
            color: var(--el-text-color-secondary);
            text-align: center;
          }
        }
      }
    }

    .sources-status-section {
      margin-bottom: 16px;
      
      .sources-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 8px;
        
        .sources-title {
          font-size: 14px;
          font-weight: 500;
          color: var(--el-text-color-primary);
        }
      }
      
      .sources-list {
        .source-item {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 6px 8px;
          margin-bottom: 4px;
          border-radius: 4px;
          background-color: var(--el-fill-color-lighter);
          
          &.available {
            background-color: var(--el-color-success-light-9);
          }
          
          .source-info {
            display: flex;
            align-items: center;
            gap: 6px;
            
            .source-name {
              font-size: 12px;
              font-weight: 500;
            }
            
            .status-success {
              color: var(--el-color-success);
              font-size: 12px;
            }
            
            .status-error {
              color: var(--el-color-danger);
              font-size: 12px;
            }
          }
          
          .source-priority {
            font-size: 11px;
            color: var(--el-text-color-secondary);
          }
        }
      }
    }

    .quick-actions-section {
      margin-bottom: 16px;
    }

    .last-sync-section {
      .last-sync-info {
        .sync-stats {
          display: flex;
          justify-content: space-between;
          margin-bottom: 4px;
          
          .stat-item {
            font-size: 12px;
            
            &.success { color: var(--el-color-success); }
            &.danger { color: var(--el-color-danger); }
          }
        }
        
        .sync-time {
          font-size: 11px;
          color: var(--el-text-color-secondary);
          text-align: center;
        }
      }
    }
  }
}
</style>
