<template>
  <div class="sync-history">
    <el-card class="history-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <el-icon class="header-icon"><Clock /></el-icon>
          <span class="header-title">同步历史</span>
          <el-button
            type="primary"
            size="small"
            :loading="loading"
            @click="refreshHistory"
          >
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <div v-loading="loading" class="history-content">
        <div v-if="error" class="error-message">
          <el-alert
            :title="error"
            type="error"
            :closable="false"
            show-icon
          />
        </div>

        <div v-else-if="historyList.length > 0" class="history-list">
          <el-timeline>
            <el-timeline-item
              v-for="(item, index) in historyList"
              :key="index"
              :timestamp="formatTime(item.finished_at || item.started_at)"
              :type="getTimelineType(item.status)"
              :icon="getTimelineIcon(item.status)"
              placement="top"
            >
              <div class="history-item">
                <div class="item-header">
                  <el-tag 
                    :type="getStatusType(item.status)"
                    size="small"
                    class="status-tag"
                  >
                    {{ getStatusText(item.status) }}
                  </el-tag>
                  <span class="job-name">{{ item.job }}</span>
                </div>
                
                <div class="item-stats">
                  <div class="stats-row">
                    <span class="stat-item">总数: {{ item.total }}</span>
                    <span class="stat-item success">新增: {{ item.inserted }}</span>
                    <span class="stat-item primary">更新: {{ item.updated }}</span>
                    <span class="stat-item danger">错误: {{ item.errors }}</span>
                  </div>
                  
                  <div v-if="item.data_sources_used?.length" class="sources-row">
                    <span class="sources-label">数据源:</span>
                    <el-tag 
                      v-for="source in item.data_sources_used" 
                      :key="source"
                      size="small"
                      type="info"
                      class="source-tag"
                    >
                      {{ source }}
                    </el-tag>
                  </div>
                  
                  <div v-if="item.last_trade_date" class="trade-date-row">
                    <span class="trade-date-label">交易日期:</span>
                    <span class="trade-date-value">{{ item.last_trade_date }}</span>
                  </div>
                </div>
                
                <div v-if="item.message" class="item-message">
                  <el-alert
                    :title="item.message"
                    :type="item.status === 'failed' ? 'error' : 'warning'"
                    :closable="false"
                    size="small"
                  />
                </div>
                
                <div class="item-duration">
                  <span class="duration-text">
                    {{ getDuration(item.started_at, item.finished_at) }}
                  </span>
                </div>
              </div>
            </el-timeline-item>
          </el-timeline>
          
          <!-- 加载更多 -->
          <div v-if="hasMore" class="load-more">
            <el-button 
              type="primary" 
              link 
              :loading="loadingMore"
              @click="loadMore"
            >
              加载更多
            </el-button>
          </div>
        </div>

        <div v-else class="empty-state">
          <el-empty description="暂无同步历史" />
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Clock, Refresh, SuccessFilled, CircleCloseFilled, Warning } from '@element-plus/icons-vue'
import { getSyncHistory, type SyncStatus } from '@/api/sync'

// 响应式数据
const loading = ref(false)
const loadingMore = ref(false)
const error = ref('')
const historyList = ref<SyncStatus[]>([])
const hasMore = ref(false)
const currentPage = ref(1)
const pageSize = ref(10)

// 获取同步历史
const fetchHistory = async (page = 1) => {
  try {
    if (page === 1) {
      loading.value = true
      historyList.value = []
      currentPage.value = 1
    } else {
      loadingMore.value = true
    }

    error.value = ''

    console.log(`📚 获取同步历史，页码: ${page}`)

    // 调用真实的历史记录API
    const response = await getSyncHistory({
      page,
      page_size: pageSize.value
    })

    if (response.success) {
      const { records, total, has_more } = response.data

      console.log(`📊 获取到 ${records.length} 条历史记录，总数: ${total}`)

      if (page === 1) {
        historyList.value = records
      } else {
        historyList.value.push(...records)
      }

      hasMore.value = has_more

      // 如果没有历史记录，显示空状态
      if (records.length === 0 && page === 1) {
        console.log('📝 暂无同步历史记录')
      }
    } else {
      throw new Error(response.message || '获取历史记录失败')
    }
  } catch (err: any) {
    console.error('获取同步历史失败:', err)
    error.value = err.message || '网络请求失败'

    // 如果是第一页加载失败，显示错误信息
    if (page === 1) {
      ElMessage.error(`获取同步历史失败: ${err.message}`)
    }
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

// 加载更多
const loadMore = async () => {
  currentPage.value++
  await fetchHistory(currentPage.value)
}

// 刷新历史记录
const refreshHistory = async () => {
  console.log('🔄 手动刷新同步历史')
  await fetchHistory(1)
  ElMessage.success('同步历史已刷新')
}

// 获取状态类型
const getStatusType = (status: string) => {
  const typeMap: Record<string, string> = {
    idle: 'info',
    running: 'warning',
    success: 'success',
    success_with_errors: 'warning',
    failed: 'danger',
    never_run: 'info'
  }
  return typeMap[status] || 'info'
}

// 获取状态文本
const getStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    idle: '空闲',
    running: '运行中',
    success: '成功',
    success_with_errors: '部分成功',
    failed: '失败',
    never_run: '未运行'
  }
  return textMap[status] || '未知'
}

// 获取时间线类型
const getTimelineType = (status: string) => {
  const typeMap: Record<string, string> = {
    success: 'success',
    success_with_errors: 'warning',
    failed: 'danger',
    running: 'primary'
  }
  return typeMap[status] || 'info'
}

// 获取时间线图标
const getTimelineIcon = (status: string) => {
  const iconMap: Record<string, any> = {
    success: SuccessFilled,
    success_with_errors: Warning,
    failed: CircleCloseFilled,
    running: Clock
  }
  return iconMap[status] || Clock
}

// 格式化时间
const formatTime = (timeStr?: string) => {
  if (!timeStr) return ''
  
  const date = new Date(timeStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  
  // 如果是今天
  if (diff < 24 * 60 * 60 * 1000) {
    return date.toLocaleTimeString('zh-CN', { 
      hour: '2-digit', 
      minute: '2-digit',
      second: '2-digit'
    })
  }
  
  // 如果是昨天或更早
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 计算持续时间
const getDuration = (startTime?: string, endTime?: string) => {
  if (!startTime || !endTime) return ''
  
  const start = new Date(startTime)
  const end = new Date(endTime)
  const duration = end.getTime() - start.getTime()
  
  if (duration < 1000) {
    return `${duration}ms`
  } else if (duration < 60000) {
    return `${Math.round(duration / 1000)}s`
  } else {
    const minutes = Math.floor(duration / 60000)
    const seconds = Math.round((duration % 60000) / 1000)
    return `${minutes}m ${seconds}s`
  }
}

// 组件挂载时获取数据
onMounted(() => {
  fetchHistory()
})
</script>

<style scoped lang="scss">
.sync-history {
  .history-card {
    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      
      .header-icon {
        margin-right: 8px;
        color: var(--el-color-primary);
      }
      
      .header-title {
        font-weight: 600;
        flex: 1;
      }
    }
  }

  .history-content {
    min-height: 300px;
    max-height: 600px;
    overflow-y: auto;
  }

  .history-list {
    .history-item {
      .item-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;
        
        .job-name {
          font-weight: 500;
          color: var(--el-text-color-regular);
        }
      }
      
      .item-stats {
        margin-bottom: 8px;
        
        .stats-row {
          display: flex;
          gap: 16px;
          margin-bottom: 4px;
          
          .stat-item {
            font-size: 12px;
            
            &.success { color: var(--el-color-success); }
            &.primary { color: var(--el-color-primary); }
            &.danger { color: var(--el-color-danger); }
          }
        }
        
        .sources-row {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 4px;
          
          .sources-label {
            font-size: 12px;
            color: var(--el-text-color-secondary);
          }
          
          .source-tag {
            font-size: 10px;
          }
        }
        
        .trade-date-row {
          font-size: 12px;
          color: var(--el-text-color-secondary);
          
          .trade-date-label {
            margin-right: 4px;
          }
        }
      }
      
      .item-message {
        margin-bottom: 8px;
      }
      
      .item-duration {
        .duration-text {
          font-size: 12px;
          color: var(--el-text-color-secondary);
        }
      }
    }
    
    .load-more {
      text-align: center;
      padding: 16px 0;
    }
  }

  .error-message {
    margin-bottom: 16px;
  }

  .empty-state {
    text-align: center;
    padding: 40px 0;
  }
}

// 自定义时间线样式
:deep(.el-timeline-item__timestamp) {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

:deep(.el-timeline-item__wrapper) {
  padding-left: 28px;
}

:deep(.el-timeline-item__tail) {
  border-left: 2px solid var(--el-border-color-lighter);
}
</style>
