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
      
      <!-- 第一行：数据导入和导出 -->
      <el-row :gutter="24">
        <!-- 数据导出 -->
        <el-col :span="12">
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
                <el-option label="配置和报告（用于迁移）" value="config_and_reports" />
                <el-option label="配置数据（用于演示系统，已脱敏）" value="config_only" />
                <el-option label="分析报告" value="analysis_reports" />
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

        <!-- 数据导入 -->
        <el-col :span="12">
          <div class="operation-section">
            <h4>📥 数据导入</h4>
            <p>从导出文件导入数据</p>

            <el-form-item label="选择文件">
              <el-upload
                ref="uploadRef"
                :auto-upload="false"
                :limit="1"
                :on-change="handleFileChange"
                :on-remove="handleFileRemove"
                accept=".json"
                drag
              >
                <el-icon class="el-icon--upload"><Upload /></el-icon>
                <div class="el-upload__text">
                  拖拽文件到此处或<em>点击上传</em>
                </div>
                <template #tip>
                  <div class="el-upload__tip">
                    仅支持 JSON 格式的导出文件
                  </div>
                </template>
              </el-upload>
            </el-form-item>

            <el-form-item label="导入选项">
              <el-checkbox v-model="importOverwrite">
                覆盖现有数据
              </el-checkbox>
              <div style="font-size: 12px; color: #909399; margin-top: 4px;">
                ⚠️ 勾选后将删除现有数据再导入
              </div>
            </el-form-item>

            <el-button
              type="primary"
              @click="importData"
              :loading="importing"
              :disabled="!importFile"
            >
              <el-icon><Upload /></el-icon>
              导入数据
            </el-button>
          </div>
        </el-col>
      </el-row>

      <!-- 第二行：数据备份和还原说明 -->
      <el-row :gutter="24" style="margin-top: 24px">
        <el-col :span="24">
          <div class="operation-section">
            <h4>💾 数据备份与还原</h4>
            <el-alert
              title="请使用命令行工具进行备份和还原"
              type="info"
              :closable="false"
            >
              <template #default>
                <div style="line-height: 1.8;">
                  <p style="margin: 8px 0;">由于数据量较大，Web 界面备份体验较差，建议使用 MongoDB 原生工具：</p>
                  <div style="background: #f5f7fa; padding: 12px; border-radius: 4px; margin: 8px 0;">
                    <p style="margin: 4px 0; font-weight: bold;">📦 备份命令：</p>
                    <code style="display: block; margin: 4px 0; color: #409eff;">
                      mongodump --uri="mongodb://localhost:27017" --db=tradingagents --out=./backup --gzip
                    </code>
                    <p style="margin: 12px 0 4px 0; font-weight: bold;">🔄 还原命令：</p>
                    <code style="display: block; margin: 4px 0; color: #409eff;">
                      mongorestore --uri="mongodb://localhost:27017" --db=tradingagents --gzip ./backup/tradingagents
                    </code>
                  </div>
                  <p style="margin: 8px 0; font-size: 12px; color: #909399;">
                    💡 提示：请根据实际的 MongoDB 连接信息修改命令中的 URI
                  </p>
                </div>
              </template>
            </el-alert>
          </div>
        </el-col>
      </el-row>
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
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  DataBoard,
  Download,
  Upload
} from '@element-plus/icons-vue'

import {
  databaseApi,
  formatBytes,
  formatDateTime,
  formatUptime,
  type DatabaseStatus,
  type DatabaseStats
} from '@/api/database'

// 响应式数据
const loading = ref(false)

const exporting = ref(false)
const importing = ref(false)
const testing = ref(false)
const cleaning = ref(false)

const exportFormat = ref('json')
const exportCollection = ref('config_and_reports')  // 默认选择"配置和报告"
const importFile = ref<File | null>(null)
const importOverwrite = ref(false)
const uploadRef = ref()
const cleanupDays = ref(30)
const logCleanupDays = ref(90)

// 数据状态
const databaseStatus = ref<DatabaseStatus | null>(null)
const databaseStats = ref<DatabaseStats | null>(null)

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
      // v2.0 核心配置
      'workflow_definitions',      // 工作流定义
      'workflows',                 // 工作流实例
      'agent_configs',             // Agent 配置
      'tool_configs',              // 工具配置
      'tool_agent_bindings',       // 工具-Agent 绑定
      'agent_workflow_bindings',   // Agent-工作流 绑定
      'agent_io_definitions',      // Agent IO 定义

      // 系统配置
      'system_configs',            // 系统配置（包括 LLM 配置）
      'llm_providers',             // LLM 提供商
      'model_catalog',             // 模型目录
      'platform_configs',          // 平台配置
      'datasource_groupings',      // 数据源分组
      'market_categories',         // 市场分类
      'smtp_config',               // SMTP 配置
      'sync_status',               // 同步状态

      // 用户相关
      'users',                     // 用户数据（脱敏模式下只导出结构）
      'user_tags',                 // 用户标签
      'user_favorites',            // 用户收藏

      // 交易系统
      'trading_systems',           // 个人交易计划
      'paper_accounts',            // 模拟账户
      'paper_market_rules',        // 模拟市场规则
      'real_accounts',             // 实盘账户

      // 提示词
      'prompt_templates',          // 提示词模板
      'user_template_configs',     // 用户模板配置

      // 调度任务
      'scheduled_analysis_configs', // 定时分析配置
      'scheduler_metadata',         // 调度器元数据

      // 其他配置
      'watchlist_groups'            // 自选股分组

      // 注意: 不包含 market_quotes 和 stock_basic_info（数据量大，不适合演示系统）
    ]

    // 分析报告集合列表
    const reportCollections = [
      'unified_analysis_tasks',    // 统一分析任务（v2.0）
      'analysis_tasks',            // 分析任务（v1.x）
      'analysis_reports',          // 分析报告
      'position_analysis_reports', // 持仓分析报告
      'portfolio_analysis_reports' // 组合分析报告
    ]

    // 历史记录集合列表（可选，用于完整迁移）
    const historyCollections = [
      'workflow_history',          // 工作流历史
      'template_history',          // 模板历史
      'scheduled_analysis_history', // 定时分析历史
      'notifications',             // 通知
      'email_records'              // 邮件记录
    ]

    // 交易记录集合列表（可选，用于完整迁移）
    const tradingCollections = [
      'paper_positions',           // 模拟持仓
      'paper_orders',              // 模拟订单
      'paper_trades',              // 模拟交易
      'real_positions',            // 实盘持仓
      'capital_transactions',      // 资金交易
      'position_changes',          // 持仓变化
      'trade_reviews',             // 交易复盘
      'trading_system_evaluations' // 交易系统评估
    ]

    // 配置和报告集合列表（用于迁移）
    const configAndReportsCollections = [
      ...configCollections,
      ...reportCollections,
      ...historyCollections,
      ...tradingCollections
    ]

    let collections: string[] = []
    let sanitize = false  // 是否启用脱敏
    let exportType = ''   // 导出类型（用于文件名）

    if (exportCollection.value === 'config_only') {
      collections = configCollections // 仅导出配置数据
      sanitize = true  // 配置数据导出时自动启用脱敏（清空 API key 等敏感字段）- 用于演示系统
      exportType = '_config'
    } else if (exportCollection.value === 'config_and_reports') {
      collections = configAndReportsCollections // 导出配置和报告
      sanitize = false  // 不脱敏 - 用于迁移，需要保留完整数据
      exportType = '_config_reports'
    } else {
      collections = [exportCollection.value] // 导出单个集合
      exportType = `_${exportCollection.value}`
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
    link.download = `database_export${exportType}_${new Date().toISOString().split('T')[0]}.${exportFormat.value}`
    link.click()
    URL.revokeObjectURL(url)

    // 根据导出类型显示不同的成功消息
    if (exportCollection.value === 'config_only') {
      ElMessage.success('配置数据导出成功（已脱敏：API key 等敏感字段已清空，用户数据仅保留结构）')
    } else if (exportCollection.value === 'config_and_reports') {
      ElMessage.success('配置和报告数据导出成功（包含完整数据，可用于迁移）')
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

// 文件上传处理
const handleFileChange = (file: any) => {
  importFile.value = file.raw
  console.log('📁 选择文件:', file.name)
}

const handleFileRemove = () => {
  importFile.value = null
  console.log('🗑️ 移除文件')
}

// 数据导入
const importData = async () => {
  if (!importFile.value) {
    ElMessage.warning('请先选择要导入的文件')
    return
  }

  try {
    // 确认导入
    const confirmMessage = importOverwrite.value
      ? '确定要导入数据吗？这将覆盖现有数据！'
      : '确定要导入数据吗？'

    await ElMessageBox.confirm(
      confirmMessage,
      '确认导入',
      {
        type: 'warning',
        confirmButtonText: '确定导入',
        cancelButtonText: '取消'
      }
    )

    importing.value = true

    const result = await databaseApi.importData(importFile.value, {
      collection: 'imported_data',  // 后端会自动检测多集合模式
      format: 'json',
      overwrite: importOverwrite.value
    })

    console.log('✅ 导入结果:', result)

    // 根据导入模式显示不同的成功消息
    if (result.data.mode === 'multi_collection') {
      ElMessage.success(
        `数据导入成功！共导入 ${result.data.total_collections} 个集合，` +
        `${result.data.total_inserted} 条文档`
      )
    } else {
      ElMessage.success(
        `数据导入成功！导入 ${result.data.inserted_count} 条文档到集合 ${result.data.collection}`
      )
    }

    // 清空文件选择
    importFile.value = null
    uploadRef.value?.clearFiles()

    // 刷新数据库统计
    await loadDatabaseStats()

  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('❌ 数据导入失败:', error)
      ElMessage.error(error.response?.data?.detail || '数据导入失败')
    }
  } finally {
    importing.value = false
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
    loadDatabaseStats()
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
