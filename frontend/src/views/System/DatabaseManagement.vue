<template>
  <div class="database-management">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1 class="page-title">
        <el-icon><DataBoard /></el-icon>
        数据库管理
      </h1>
      <p class="page-description">
        MongoDB + Redis 数据库管理和监控
      </p>
    </div>

    <!-- 连接状态 -->
    <el-row :gutter="24">
      <el-col :span="12">
        <el-card class="connection-card" shadow="never">
          <template #header>
            <h3>🍃 MongoDB 连接状态</h3>
          </template>
          
          <div class="connection-status">
            <div class="status-indicator">
              <el-tag :type="mongoStatus.connected ? 'success' : 'danger'" size="large">
                {{ mongoStatus.connected ? '已连接' : '未连接' }}
              </el-tag>
            </div>
            
            <div v-if="mongoStatus.connected" class="connection-info">
              <p><strong>服务器:</strong> {{ mongoStatus.host }}:{{ mongoStatus.port }}</p>
              <p><strong>数据库:</strong> {{ mongoStatus.database }}</p>
              <p><strong>版本:</strong> {{ mongoStatus.version || 'Unknown' }}</p>
              <p v-if="mongoStatus.connected_at"><strong>连接时间:</strong> {{ formatDateTime(mongoStatus.connected_at) }}</p>
              <p v-if="mongoStatus.uptime"><strong>运行时间:</strong> {{ formatUptime(mongoStatus.uptime) }}</p>
            </div>
            
            <div class="connection-actions">
              <el-button @click="testConnections" :loading="testing">
                测试连接
              </el-button>
              <el-button @click="loadDatabaseStatus" :loading="loading" :icon="Refresh">
                刷新状态
              </el-button>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card class="connection-card" shadow="never">
          <template #header>
            <h3>🔴 Redis 连接状态</h3>
          </template>
          
          <div class="connection-status">
            <div class="status-indicator">
              <el-tag :type="redisStatus.connected ? 'success' : 'danger'" size="large">
                {{ redisStatus.connected ? '已连接' : '未连接' }}
              </el-tag>
            </div>
            
            <div v-if="redisStatus.connected" class="connection-info">
              <p><strong>服务器:</strong> {{ redisStatus.host }}:{{ redisStatus.port }}</p>
              <p><strong>数据库:</strong> {{ redisStatus.database }}</p>
              <p><strong>版本:</strong> {{ redisStatus.version || 'Unknown' }}</p>
              <p v-if="redisStatus.memory_used"><strong>内存使用:</strong> {{ formatBytes(redisStatus.memory_used) }}</p>
              <p v-if="redisStatus.connected_clients"><strong>连接数:</strong> {{ redisStatus.connected_clients }}</p>
            </div>
            
            <div class="connection-actions">
              <el-button @click="testConnections" :loading="testing">
                测试连接
              </el-button>
              <el-button @click="loadDatabaseStatus" :loading="loading" :icon="Refresh">
                刷新状态
              </el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 数据库统计 -->
    <el-row :gutter="24" style="margin-top: 24px">
      <el-col :span="8">
        <el-card class="stat-card" shadow="never">
          <div class="stat-content">
            <div class="stat-value">{{ dbStats.totalCollections }}</div>
            <div class="stat-label">MongoDB 集合数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="stat-card" shadow="never">
          <div class="stat-content">
            <div class="stat-value">{{ dbStats.totalDocuments }}</div>
            <div class="stat-label">总文档数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="stat-card" shadow="never">
          <div class="stat-content">
            <div class="stat-value">{{ formatBytes(dbStats.totalSize) }}</div>
            <div class="stat-label">数据库大小</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 数据管理操作 -->
    <el-card class="operations-card" shadow="never" style="margin-top: 24px">
      <template #header>
        <h3>🛠️ 数据管理操作</h3>
      </template>
      
      <el-row :gutter="24" justify="center">
        <!-- 数据导出 -->
        <el-col :span="10">
          <div class="operation-section">
            <h4>📤 数据导出</h4>
            <p>导出数据库数据到文件</p>
            
            <el-form-item label="导出格式">
              <el-select v-model="exportFormat" style="width: 100%">
                <el-option label="JSON" value="json" />
                <el-option label="CSV" value="csv" />
                <el-option label="Excel" value="xlsx" />
              </el-select>
            </el-form-item>
            
            <el-form-item label="数据集合">
              <el-select v-model="exportCollection" style="width: 100%">
                <el-option label="全部集合" value="all" />
                <el-option label="配置数据（用于演示系统）" value="config_only" />
                <el-option label="分析结果" value="analysis_results" />
                <el-option label="用户配置" value="user_configs" />
                <el-option label="操作日志" value="operation_logs" />
              </el-select>
            </el-form-item>
            
            <el-button @click="exportData" :loading="exporting">
              <el-icon><Download /></el-icon>
              导出数据
            </el-button>
          </div>
        </el-col>

        <!-- 数据备份 -->
        <el-col :span="10">
          <div class="operation-section">
            <h4>💾 数据备份</h4>
            <p>创建数据库完整备份</p>
            
            <el-form-item label="备份名称">
              <el-input v-model="backupName" placeholder="输入备份名称" />
            </el-form-item>
            
            <el-button @click="createBackup" :loading="backingUp">
              <el-icon><FolderAdd /></el-icon>
              创建备份
            </el-button>
            
            <el-button @click="loadBackups">
              <el-icon><Refresh /></el-icon>
              刷新列表
            </el-button>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 备份列表 -->
    <el-card class="backup-list" shadow="never" style="margin-top: 24px">
      <template #header>
        <h3>📋 备份列表</h3>
      </template>
      
      <el-table :data="backupList" v-loading="loadingBackups">
        <el-table-column prop="name" label="备份名称" />
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="size" label="文件大小" width="120">
          <template #default="{ row }">
            {{ formatBytes(row.size) }}
          </template>
        </el-table-column>
        <el-table-column label="集合数量" width="120">
          <template #default="{ row }">
            <el-tooltip
              v-if="Array.isArray(row.collections) && row.collections.length > 0"
              placement="top"
              :show-after="500"
            >
              <template #content>
                <div style="max-width: 300px;">
                  <div><strong>包含的集合 ({{ row.collections.length }}个):</strong></div>
                  <div style="margin-top: 8px;">
                    <el-tag
                      v-for="collection in row.collections"
                      :key="collection"
                      size="small"
                      style="margin: 2px;"
                    >
                      {{ collection }}
                    </el-tag>
                  </div>
                </div>
              </template>
              <el-tag size="small" type="info">
                {{ row.collections.length }} 个集合
              </el-tag>
            </el-tooltip>
            <span v-else>0 个集合</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button size="small" @click="restoreBackup(row)">
              恢复
            </el-button>
            <el-button size="small" @click="downloadBackup(row)">
              下载
            </el-button>
            <el-button size="small" type="danger" @click="deleteBackup(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>



    <!-- 数据清理 -->
    <el-card class="cleanup-card" shadow="never" style="margin-top: 24px">
      <template #header>
        <h3>🧹 数据清理</h3>
      </template>
      
      <el-alert
        title="危险操作"
        type="warning"
        description="以下操作将永久删除数据，请谨慎操作"
        :closable="false"
        style="margin-bottom: 16px"
      />
      
      <el-row :gutter="24">
        <el-col :span="12">
          <div class="cleanup-section">
            <h4>清理过期分析结果</h4>
            <p>删除指定天数之前的分析结果</p>
            <el-input-number v-model="cleanupDays" :min="1" :max="365" />
            <span style="margin-left: 8px">天前</span>
            <br><br>
            <el-button type="warning" @click="cleanupAnalysisResults" :loading="cleaning">
              清理分析结果
            </el-button>
          </div>
        </el-col>
        
        <el-col :span="12">
          <div class="cleanup-section">
            <h4>清理操作日志</h4>
            <p>删除指定天数之前的操作日志</p>
            <el-input-number v-model="logCleanupDays" :min="1" :max="365" />
            <span style="margin-left: 8px">天前</span>
            <br><br>
            <el-button type="warning" @click="cleanupOperationLogs" :loading="cleaning">
              清理操作日志
            </el-button>
          </div>
        </el-col>
        

      </el-row>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  DataBoard,
  Download,
  FolderAdd,
  Refresh
} from '@element-plus/icons-vue'

import {
  databaseApi,
  formatBytes,
  formatDateTime,
  formatUptime,
  type DatabaseStatus,
  type DatabaseStats,
  type BackupInfo,
  type ConnectionTestResult
} from '@/api/database'

// 响应式数据
const loading = ref(false)

const exporting = ref(false)
const backingUp = ref(false)
const loadingBackups = ref(false)
const testing = ref(false)
const cleaning = ref(false)

const exportFormat = ref('json')
const exportCollection = ref('all')
const backupName = ref('')
const cleanupDays = ref(30)
const logCleanupDays = ref(90)



// 数据状态
const databaseStatus = ref<DatabaseStatus | null>(null)
const databaseStats = ref<DatabaseStats | null>(null)
const backupList = ref<BackupInfo[]>([])

// 计算属性
const mongoStatus = computed(() => databaseStatus.value?.mongodb || {
  connected: false,
  host: 'localhost',
  port: 27017,
  database: 'tradingagents'
})

const redisStatus = computed(() => databaseStatus.value?.redis || {
  connected: false,
  host: 'localhost',
  port: 6379,
  database: 0
})

const dbStats = computed(() => ({
  totalCollections: databaseStats.value?.total_collections || 0,
  totalDocuments: databaseStats.value?.total_documents || 0,
  totalSize: databaseStats.value?.total_size || 0
}))

// 数据加载方法
const loadDatabaseStatus = async () => {
  try {
    loading.value = true
    const status = await databaseApi.getStatus()
    databaseStatus.value = status
    console.log('📊 数据库状态加载成功:', status)
  } catch (error) {
    console.error('❌ 加载数据库状态失败:', error)
    ElMessage.error('加载数据库状态失败')
  } finally {
    loading.value = false
  }
}

const loadDatabaseStats = async () => {
  try {
    const stats = await databaseApi.getStats()
    databaseStats.value = stats
    console.log('📈 数据库统计加载成功:', stats)
  } catch (error) {
    console.error('❌ 加载数据库统计失败:', error)
    ElMessage.error('加载数据库统计失败')
  }
}

const loadBackups = async () => {
  try {
    loadingBackups.value = true
    const response = await databaseApi.getBackups()
    backupList.value = response.data
    console.log('📋 备份列表加载成功:', response.data)
  } catch (error) {
    console.error('❌ 加载备份列表失败:', error)
    ElMessage.error('加载备份列表失败')
  } finally {
    loadingBackups.value = false
  }
}



const testConnections = async () => {
  try {
    testing.value = true
    const response = await databaseApi.testConnections()
    const results = response.data

    if (results.overall) {
      ElMessage.success('数据库连接测试成功')
    } else {
      ElMessage.warning('部分数据库连接测试失败')
    }

    // 显示详细结果
    const mongoMsg = `MongoDB: ${results.mongodb.message} (${results.mongodb.response_time_ms}ms)`
    const redisMsg = `Redis: ${results.redis.message} (${results.redis.response_time_ms}ms)`

    ElMessage({
      message: `${mongoMsg}\n${redisMsg}`,
      type: results.overall ? 'success' : 'warning',
      duration: 5000
    })

    // 测试成功后刷新状态显示
    await loadDatabaseStatus()

  } catch (error) {
    console.error('❌ 连接测试失败:', error)
    ElMessage.error('连接测试失败')
  } finally {
    testing.value = false
  }
}

// 数据管理方法

const exportData = async () => {
  exporting.value = true
  try {
    // 配置数据集合列表（用于演示系统）
    const configCollections = [
      'system_configs',      // 系统配置（包括 LLM 配置）
      'users',               // 用户数据（脱敏模式下只导出结构，不导出实际数据）
      'llm_providers',       // LLM 提供商
      'market_categories',   // 市场分类
      'user_tags',           // 用户标签
      'datasource_groupings',// 数据源分组
      'platform_configs',    // 平台配置
      'user_configs',        // 用户配置
      'model_catalog'        // 模型目录
      // 注意: 不包含 market_quotes 和 stock_basic_info（数据量大，不适合演示系统）
    ]

    let collections: string[] = []
    let sanitize = false  // 是否启用脱敏

    if (exportCollection.value === 'all') {
      collections = [] // 空数组表示导出所有集合
    } else if (exportCollection.value === 'config_only') {
      collections = configCollections // 仅导出配置数据
      sanitize = true  // 配置数据导出时自动启用脱敏（清空 API key 等敏感字段）
    } else {
      collections = [exportCollection.value] // 导出单个集合
    }

    const blob = await databaseApi.exportData({
      collections,
      format: exportFormat.value,
      sanitize  // 传递脱敏参数
    })

    // 创建下载链接
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    const suffix = exportCollection.value === 'config_only' ? '_config' : ''
    link.download = `database_export${suffix}_${new Date().toISOString().split('T')[0]}.${exportFormat.value}`
    link.click()
    URL.revokeObjectURL(url)

    if (exportCollection.value === 'config_only') {
      ElMessage.success('配置数据导出成功（已脱敏：API key 等敏感字段已清空，用户数据仅保留结构）')
    } else {
      ElMessage.success('数据导出成功')
    }

  } catch (error) {
    console.error('❌ 数据导出失败:', error)
    ElMessage.error('数据导出失败')
  } finally {
    exporting.value = false
  }
}

// 备份管理方法
const createBackup = async () => {
  if (!backupName.value.trim()) {
    ElMessage.warning('请输入备份名称')
    return
  }

  backingUp.value = true
  try {
    const response = await databaseApi.createBackup({
      name: backupName.value.trim(),
      collections: [] // 空数组表示备份所有集合
    })

    ElMessage.success('备份创建成功')
    backupName.value = ''

    // 重新加载备份列表
    await loadBackups()

  } catch (error) {
    console.error('❌ 备份创建失败:', error)
    ElMessage.error('备份创建失败')
  } finally {
    backingUp.value = false
  }
}

const restoreBackup = async (backup: BackupInfo) => {
  try {
    await ElMessageBox.confirm(
      `确定要恢复备份 "${backup.name}" 吗？这将覆盖当前数据！`,
      '确认恢复',
      { type: 'warning' }
    )

    ElMessage.info('备份恢复功能开发中...')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('备份恢复失败')
    }
  }
}

const downloadBackup = (backup: BackupInfo) => {
  ElMessage.info('备份下载功能开发中...')
}

const deleteBackup = async (backup: BackupInfo) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除备份 "${backup.name}" 吗？`,
      '确认删除',
      { type: 'warning' }
    )

    await databaseApi.deleteBackup(backup.id)
    ElMessage.success('备份删除成功')

    // 重新加载备份列表
    await loadBackups()

  } catch (error) {
    if (error !== 'cancel') {
      console.error('❌ 删除备份失败:', error)
      ElMessage.error('删除备份失败')
    }
  }
}

// 清理方法
const cleanupAnalysisResults = async () => {
  try {
    await ElMessageBox.confirm(
      `确定要清理 ${cleanupDays.value} 天前的分析结果吗？`,
      '确认清理',
      { type: 'warning' }
    )

    cleaning.value = true
    const response = await databaseApi.cleanupAnalysisResults(cleanupDays.value)

    ElMessage.success(`分析结果清理完成，删除了 ${response.data.deleted_count} 条记录`)

    // 重新加载统计信息
    await loadDatabaseStats()

  } catch (error) {
    if (error !== 'cancel') {
      console.error('❌ 清理分析结果失败:', error)
      ElMessage.error('清理分析结果失败')
    }
  } finally {
    cleaning.value = false
  }
}

const cleanupOperationLogs = async () => {
  try {
    await ElMessageBox.confirm(
      `确定要清理 ${logCleanupDays.value} 天前的操作日志吗？`,
      '确认清理',
      { type: 'warning' }
    )

    cleaning.value = true
    const response = await databaseApi.cleanupOperationLogs(logCleanupDays.value)

    ElMessage.success(`操作日志清理完成，删除了 ${response.data.deleted_count} 条记录`)

    // 重新加载统计信息
    await loadDatabaseStats()

  } catch (error) {
    if (error !== 'cancel') {
      console.error('❌ 清理操作日志失败:', error)
      ElMessage.error('清理操作日志失败')
    }
  } finally {
    cleaning.value = false
  }
}





// 生命周期
onMounted(async () => {
  console.log('🔄 数据库管理页面初始化')

  // 并行加载数据
  await Promise.all([
    loadDatabaseStatus(),
    loadDatabaseStats(),
    loadBackups()
  ])



  console.log('✅ 数据库管理页面初始化完成')
})
</script>

<style lang="scss" scoped>
.database-management {
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

  .connection-card {
    .connection-status {
      .status-indicator {
        text-align: center;
        margin-bottom: 16px;
      }
      
      .connection-info {
        margin-bottom: 16px;
        
        p {
          margin: 4px 0;
          font-size: 14px;
        }
      }
      
      .connection-actions {
        display: flex;
        gap: 8px;
        justify-content: center;
      }
    }
  }

  .stat-card {
    .stat-content {
      text-align: center;
      
      .stat-value {
        font-size: 24px;
        font-weight: 600;
        color: var(--el-color-primary);
        margin-bottom: 8px;
      }
      
      .stat-label {
        font-size: 14px;
        color: var(--el-text-color-regular);
      }
    }
  }

  .operations-card {
    .operation-section {
      h4 {
        margin: 0 0 8px 0;
        font-size: 16px;
      }
      
      p {
        margin: 0 0 16px 0;
        font-size: 14px;
        color: var(--el-text-color-regular);
      }
      
      .file-info {
        margin-top: 12px;
        
        p {
          margin: 0 0 8px 0;
          font-size: 14px;
        }
      }
    }
  }



  .cleanup-card {
    .cleanup-section {
      h4 {
        margin: 0 0 8px 0;
        font-size: 16px;
      }
      
      p {
        margin: 0 0 12px 0;
        font-size: 14px;
        color: var(--el-text-color-regular);
      }
    }
  }
}
</style>
