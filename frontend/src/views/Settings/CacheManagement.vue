<template>
  <div class="cache-management">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1 class="page-title">
        <el-icon><Coin /></el-icon>
        缓存管理
      </h1>
      <p class="page-description">
        管理股票数据缓存，优化系统性能
      </p>
    </div>

    <el-row :gutter="24">
      <!-- 左侧：缓存统计 -->
      <el-col :span="12">
        <el-card class="stats-card" shadow="never">
          <template #header>
            <h3>📊 缓存统计</h3>
          </template>
          
          <div v-loading="statsLoading" class="stats-content">
            <el-row :gutter="16">
              <el-col :span="12">
                <div class="stat-item">
                  <div class="stat-value">{{ cacheStats.totalFiles }}</div>
                  <div class="stat-label">总文件数</div>
                </div>
              </el-col>
              <el-col :span="12">
                <div class="stat-item">
                  <div class="stat-value">{{ formatSize(cacheStats.totalSize) }}</div>
                  <div class="stat-label">总大小</div>
                </div>
              </el-col>
            </el-row>
            
            <el-row :gutter="16" style="margin-top: 16px">
              <el-col :span="12">
                <div class="stat-item">
                  <div class="stat-value">{{ cacheStats.stockDataCount }}</div>
                  <div class="stat-label">股票数据</div>
                </div>
              </el-col>
              <el-col :span="12">
                <div class="stat-item">
                  <div class="stat-value">{{ cacheStats.newsDataCount }}</div>
                  <div class="stat-label">新闻数据</div>
                </div>
              </el-col>
            </el-row>
            
            <el-divider />
            
            <div class="cache-usage">
              <h4>缓存使用情况</h4>
              <el-progress
                :percentage="cacheUsagePercentage"
                :color="getProgressColor(cacheUsagePercentage)"
                :stroke-width="12"
              />
              <p class="usage-text">
                已使用 {{ formatSize(cacheStats.totalSize) }} / {{ formatSize(cacheStats.maxSize) }}
              </p>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：缓存操作 -->
      <el-col :span="12">
        <el-card class="operations-card" shadow="never">
          <template #header>
            <h3>🛠️ 缓存操作</h3>
          </template>
          
          <div class="operations-content">
            <!-- 刷新统计 -->
            <div class="operation-item">
              <h4>🔄 刷新统计</h4>
              <p>重新获取最新的缓存统计信息</p>
              <el-button type="primary" @click="refreshStats" :loading="statsLoading">
                刷新统计
              </el-button>
            </div>
            
            <el-divider />
            
            <!-- 清理过期缓存 -->
            <div class="operation-item">
              <h4>🧹 清理过期缓存</h4>
              <p>删除指定天数之前的缓存文件</p>
              
              <el-form-item label="清理天数">
                <el-slider
                  v-model="cleanupDays"
                  :min="1"
                  :max="30"
                  :marks="cleanupMarks"
                  show-stops
                />
                <span class="cleanup-description">
                  将清理 {{ cleanupDays }} 天前的缓存文件
                </span>
              </el-form-item>
              
              <el-button 
                type="warning" 
                @click="cleanupOldCache" 
                :loading="cleanupLoading"
              >
                <el-icon><Delete /></el-icon>
                清理过期缓存
              </el-button>
            </div>
            
            <el-divider />
            
            <!-- 清空所有缓存 -->
            <div class="operation-item">
              <h4>🗑️ 清空所有缓存</h4>
              <p class="warning-text">⚠️ 此操作将删除所有缓存文件，无法恢复</p>
              
              <el-button 
                type="danger" 
                @click="clearAllCache" 
                :loading="clearAllLoading"
              >
                <el-icon><Delete /></el-icon>
                清空所有缓存
              </el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 缓存详情 -->
    <el-card class="details-card" shadow="never" style="margin-top: 24px">
      <template #header>
        <div class="card-header">
          <h3>📋 缓存详情</h3>
          <el-button size="small" @click="loadCacheDetails">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>
      
      <div v-loading="detailsLoading">
        <el-table :data="cacheDetails" style="width: 100%">
          <el-table-column prop="type" label="类型" width="120">
            <template #default="{ row }">
              <el-tag :type="getCacheTypeTag(row.type)">{{ row.type }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="symbol" label="股票代码" width="120" />
          <el-table-column prop="size" label="大小" width="100">
            <template #default="{ row }">
              {{ formatSize(row.size) }}
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="180">
            <template #default="{ row }">
              {{ formatDate(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column prop="last_accessed" label="最后访问" width="180">
            <template #default="{ row }">
              {{ formatDate(row.last_accessed) }}
            </template>
          </el-table-column>
          <el-table-column prop="hit_count" label="命中次数" width="100" />
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button 
                size="small" 
                type="danger" 
                @click="deleteCacheItem(row)"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        
        <!-- 分页 -->
        <el-pagination
          v-if="cacheDetails.length > 0"
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="totalItems"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          style="margin-top: 16px; text-align: right"
          @size-change="loadCacheDetails"
          @current-change="loadCacheDetails"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Coin,
  Delete,
  Refresh
} from '@element-plus/icons-vue'
import * as cacheApi from '@/api/cache'

// 响应式数据
const statsLoading = ref(false)
const cleanupLoading = ref(false)
const clearAllLoading = ref(false)
const detailsLoading = ref(false)

const cleanupDays = ref(7)
const currentPage = ref(1)
const pageSize = ref(20)
const totalItems = ref(0)

// 缓存统计数据
const cacheStats = ref({
  totalFiles: 0,
  totalSize: 0,
  maxSize: 1024 * 1024 * 1024, // 1GB
  stockDataCount: 0,
  newsDataCount: 0,
  analysisDataCount: 0
})

// 缓存详情数据
const cacheDetails = ref([])

// 清理天数标记
const cleanupMarks = {
  1: '1天',
  7: '1周',
  14: '2周',
  30: '1月'
}

// 计算属性
const cacheUsagePercentage = computed(() => {
  if (cacheStats.value.maxSize === 0) return 0
  return Math.round((cacheStats.value.totalSize / cacheStats.value.maxSize) * 100)
})

// 方法
const formatSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const formatDate = (dateString: string): string => {
  return new Date(dateString).toLocaleString('zh-CN')
}

const getProgressColor = (percentage: number): string => {
  if (percentage < 50) return '#67c23a'
  if (percentage < 80) return '#e6a23c'
  return '#f56c6c'
}

const getCacheTypeTag = (type: string): string => {
  const typeMap = {
    'stock': 'primary',
    'news': 'success',
    'analysis': 'warning'
  }
  return typeMap[type] || 'info'
}

const refreshStats = async () => {
  statsLoading.value = true
  try {
    const response = await cacheApi.getCacheStats()
    // 从 ApiResponse 中提取 data 字段
    cacheStats.value = response.data || response
    ElMessage.success('缓存统计已刷新')
  } catch (error: any) {
    console.error('刷新缓存统计失败:', error)
    ElMessage.error(error.message || '刷新缓存统计失败')
  } finally {
    statsLoading.value = false
  }
}

const cleanupOldCache = async () => {
  try {
    await ElMessageBox.confirm(
      `确定要清理 ${cleanupDays.value} 天前的缓存文件吗？`,
      '确认清理',
      { type: 'warning' }
    )

    cleanupLoading.value = true

    await cacheApi.cleanupOldCache(cleanupDays.value)

    ElMessage.success(`已清理 ${cleanupDays.value} 天前的缓存文件`)
    await refreshStats()
    await loadCacheDetails()

  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('清理缓存失败:', error)
      ElMessage.error(error.message || '清理缓存失败')
    }
  } finally {
    cleanupLoading.value = false
  }
}

const clearAllCache = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要清空所有缓存文件吗？此操作无法恢复！',
      '确认清空',
      {
        type: 'error',
        confirmButtonText: '确定清空',
        cancelButtonText: '取消'
      }
    )

    clearAllLoading.value = true

    await cacheApi.clearAllCache()

    ElMessage.success('所有缓存已清空')
    await refreshStats()
    await loadCacheDetails()

  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('清空缓存失败:', error)
      ElMessage.error(error.message || '清空缓存失败')
    }
  } finally {
    clearAllLoading.value = false
  }
}

const loadCacheDetails = async () => {
  detailsLoading.value = true
  try {
    const response = await cacheApi.getCacheDetails(currentPage.value, pageSize.value)
    // 从 ApiResponse 中提取 data 字段
    const data = response.data || response
    cacheDetails.value = data.items || []
    totalItems.value = data.total || 0
  } catch (error: any) {
    console.error('加载缓存详情失败:', error)
    ElMessage.error(error.message || '加载缓存详情失败')
  } finally {
    detailsLoading.value = false
  }
}

const deleteCacheItem = async (item: any) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除 ${item.symbol} 的${item.type}缓存吗？`,
      '确认删除',
      { type: 'warning' }
    )
    
    // 模拟API调用
    await new Promise(resolve => setTimeout(resolve, 500))
    
    ElMessage.success('缓存项已删除')
    await loadCacheDetails()
    await refreshStats()
    
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除缓存项失败')
    }
  }
}

// 生命周期
onMounted(() => {
  refreshStats()
  loadCacheDetails()
})
</script>

<style lang="scss" scoped>
.cache-management {
  .page-header {
    margin-bottom: 24px;

    .page-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 24px;
      font-weight: 600;
      color: var(--el-text-color-primary);
      margin: 0 0 8px 0;
    }

    .page-description {
      color: var(--el-text-color-regular);
      margin: 0;
    }
  }

  .stats-card {
    .stats-content {
      .stat-item {
        text-align: center;
        
        .stat-value {
          font-size: 24px;
          font-weight: 600;
          color: var(--el-color-primary);
          margin-bottom: 4px;
        }
        
        .stat-label {
          font-size: 14px;
          color: var(--el-text-color-regular);
        }
      }
      
      .cache-usage {
        h4 {
          margin: 0 0 12px 0;
          font-size: 16px;
        }
        
        .usage-text {
          margin: 8px 0 0 0;
          font-size: 14px;
          color: var(--el-text-color-regular);
          text-align: center;
        }
      }
    }
  }

  .operations-card {
    .operations-content {
      .operation-item {
        h4 {
          margin: 0 0 8px 0;
          font-size: 16px;
        }
        
        p {
          margin: 0 0 16px 0;
          font-size: 14px;
          color: var(--el-text-color-regular);
          
          &.warning-text {
            color: var(--el-color-warning);
          }
        }
        
        .cleanup-description {
          font-size: 12px;
          color: var(--el-text-color-placeholder);
          margin-left: 12px;
        }
      }
    }
  }

  .details-card {
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      
      h3 {
        margin: 0;
      }
    }
  }
}
</style>
