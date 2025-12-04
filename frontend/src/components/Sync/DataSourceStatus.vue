<template>
  <div class="data-source-status">
    <el-card class="status-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <el-icon class="header-icon"><Connection /></el-icon>
          <span class="header-title">数据源状态</span>
          <el-button 
            type="primary" 
            size="small" 
            :loading="refreshing"
            @click="refreshStatus"
          >
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <div v-loading="loading" class="status-content">
        <div v-if="error" class="error-message">
          <el-alert
            :title="error"
            type="error"
            :closable="false"
            show-icon
          />
        </div>

        <div v-else-if="dataSources.length > 0" class="sources-list">
          <div 
            v-for="source in dataSources" 
            :key="source.name"
            class="source-item"
            :class="{ 'available': source.available, 'unavailable': !source.available }"
          >
            <div class="source-header">
              <div class="source-info">
                <el-tag 
                  :type="source.available ? 'success' : 'danger'"
                  size="small"
                  class="status-tag"
                >
                  {{ source.available ? '可用' : '不可用' }}
                </el-tag>
                <span class="source-name">{{ source.name.toUpperCase() }}</span>
                <el-tag size="small" type="info" class="priority-tag">
                  优先级: {{ source.priority }}
                </el-tag>
              </div>
              <div class="source-actions">
                <el-button
                  size="small"
                  type="primary"
                  link
                  @click="testSingleSource(source.name)"
                  :loading="testingSource === source.name"
                >
                  <el-icon><Operation /></el-icon>
                  测试
                </el-button>
              </div>
            </div>
            <div class="source-description">
              {{ source.description }}
            </div>
            
            <!-- 测试结果展示 -->
            <div v-if="testResults[source.name]" class="test-results">
              <el-divider content-position="left">
                <span class="divider-text">最后测试结果</span>
              </el-divider>
              <div class="test-result-message">
                <el-alert
                  :title="testResults[source.name].message"
                  :type="testResults[source.name].available ? 'success' : 'error'"
                  :closable="false"
                  show-icon
                />
              </div>
            </div>
          </div>
        </div>

        <div v-else class="empty-state">
          <el-empty description="暂无数据源信息" />
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Connection, Refresh, Operation } from '@element-plus/icons-vue'
import { getDataSourcesStatus, testDataSources, type DataSourceStatus, type DataSourceTestResult } from '@/api/sync'
import { testApiConnection } from '@/api/request'

// 响应式数据
const loading = ref(false)
const refreshing = ref(false)
const error = ref('')
const dataSources = ref<DataSourceStatus[]>([])
const testResults = ref<Record<string, DataSourceTestResult>>({})
const testingSource = ref('')

// 获取数据源状态
const fetchDataSourcesStatus = async () => {
  try {
    console.log('🔍 [DataSourceStatus] 开始获取数据源状态')
    loading.value = true
    error.value = ''

    // 先测试API连接
    console.log('🔍 [DataSourceStatus] 先测试API连接')
    const connectionOk = await testApiConnection()
    console.log('🔍 [DataSourceStatus] API连接测试结果:', connectionOk)

    if (!connectionOk) {
      console.error('🔍 [DataSourceStatus] API连接测试失败，停止后续操作')
      error.value = '无法连接到后端服务，请确保后端服务正在 http://localhost:8000 运行'
      return
    }

    console.log('🔍 [DataSourceStatus] API连接测试成功，继续获取数据源状态')

    console.log('🔍 [DataSourceStatus] API连接正常，调用 getDataSourcesStatus')
    const response = await getDataSourcesStatus()
    console.log('🔍 [DataSourceStatus] API响应:', response)

    if (response.success) {
      console.log('🔍 [DataSourceStatus] API调用成功，数据源数量:', response.data?.length || 0)
      console.log('🔍 [DataSourceStatus] 数据源详情:', response.data)
      dataSources.value = response.data.sort((a, b) => b.priority - a.priority) // 倒序：优先级高的在前
      console.log('🔍 [DataSourceStatus] 排序后的数据源:', dataSources.value)
    } else {
      console.error('🔍 [DataSourceStatus] API调用失败')
      console.error('🔍 [DataSourceStatus] 完整响应对象:', response)
      console.error('🔍 [DataSourceStatus] 响应success字段:', response.success)
      console.error('🔍 [DataSourceStatus] 响应message字段:', response.message)
      console.error('🔍 [DataSourceStatus] 响应data字段:', response.data)
      console.error('🔍 [DataSourceStatus] 响应的所有属性:', Object.keys(response))
      error.value = response.message || '获取数据源状态失败'
    }
  } catch (err: any) {
    console.error('🔍 [DataSourceStatus] 捕获异常:', err)
    console.error('🔍 [DataSourceStatus] 异常类型:', err.constructor.name)
    console.error('🔍 [DataSourceStatus] 异常消息:', err.message)
    console.error('🔍 [DataSourceStatus] 异常堆栈:', err.stack)

    // 检查是否是网络错误
    if (err.message.includes('Failed to fetch') || err.message.includes('NetworkError')) {
      console.error('🔍 [DataSourceStatus] 这是一个网络连接错误')
      error.value = '网络连接失败，请检查服务器是否正常运行'
    } else if (err.message.includes('HTTP')) {
      console.error('🔍 [DataSourceStatus] 这是一个HTTP状态错误')
      error.value = `服务器错误: ${err.message}`
    } else {
      console.error('🔍 [DataSourceStatus] 这是一个其他类型的错误')
      error.value = err.message || '网络请求失败'
    }
  } finally {
    loading.value = false
    console.log('🔍 [DataSourceStatus] 获取数据源状态完成')
  }
}

// 刷新状态
const refreshStatus = async () => {
  refreshing.value = true
  await fetchDataSourcesStatus()
  refreshing.value = false
  ElMessage.success('数据源状态已刷新')
}

// 测试单个数据源
const testSingleSource = async (sourceName: string) => {
  try {
    testingSource.value = sourceName
    ElMessage.info(`正在测试 ${sourceName.toUpperCase()}，请稍候...`)

    // 传递数据源名称，只测试该数据源
    const response = await testDataSources(sourceName)
    if (response.success) {
      const results = response.data.test_results
      const sourceResult = results.find(r => r.name === sourceName)
      if (sourceResult) {
        testResults.value[sourceName] = sourceResult
        if (sourceResult.available) {
          ElMessage.success(`✅ ${sourceName.toUpperCase()} 连接成功`)
        } else {
          ElMessage.warning(`⚠️ ${sourceName.toUpperCase()} 连接失败: ${sourceResult.message}`)
        }
      }
    } else {
      ElMessage.error(`测试失败: ${response.message}`)
    }
  } catch (err: any) {
    console.error('测试数据源失败:', err)
    if (err.code === 'ECONNABORTED') {
      ElMessage.error(`测试超时: ${sourceName.toUpperCase()} 测试时间过长，请稍后重试`)
    } else {
      ElMessage.error(`测试失败: ${err.message}`)
    }
  } finally {
    testingSource.value = ''
  }
}

// 组件挂载时获取数据
onMounted(() => {
  fetchDataSourcesStatus()
})
</script>

<style scoped lang="scss">
.data-source-status {
  .status-card {
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

  .status-content {
    min-height: 200px;
  }

  .sources-list {
    .source-item {
      padding: 16px;
      border: 1px solid var(--el-border-color-light);
      border-radius: 8px;
      margin-bottom: 12px;
      transition: all 0.3s ease;

      &.available {
        border-color: var(--el-color-success-light-7);
        background-color: var(--el-color-success-light-9);
      }

      &.unavailable {
        border-color: var(--el-color-danger-light-7);
        background-color: var(--el-color-danger-light-9);
      }

      &:hover {
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
      }

      .source-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 8px;

        .source-info {
          display: flex;
          align-items: center;
          gap: 8px;

          .source-name {
            font-weight: 600;
            font-size: 16px;
          }
        }
      }

      .source-description {
        color: var(--el-text-color-regular);
        font-size: 14px;
        line-height: 1.5;
      }

      .test-results {
        margin-top: 16px;

        .divider-text {
          font-size: 12px;
          color: var(--el-text-color-secondary);
        }

        .test-items {
          .test-item {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
            font-size: 14px;

            .success-icon {
              color: var(--el-color-success);
            }

            .error-icon {
              color: var(--el-color-danger);
            }

            .test-name {
              font-weight: 500;
              min-width: 80px;
            }

            .test-message {
              color: var(--el-text-color-regular);
              flex: 1;
            }
          }
        }
      }
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
</style>
