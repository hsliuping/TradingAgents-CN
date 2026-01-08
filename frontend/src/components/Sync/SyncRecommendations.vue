<template>
  <div class="sync-recommendations">
    <el-card class="recommendations-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <el-icon class="header-icon"><Promotion /></el-icon>
          <span class="header-title">使用建议</span>
          <el-button 
            type="primary" 
            size="small" 
            :loading="loading"
            @click="fetchRecommendations"
          >
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <div v-loading="loading" class="recommendations-content">
        <div v-if="error" class="error-message">
          <el-alert
            :title="error"
            type="error"
            :closable="false"
            show-icon
          />
        </div>

        <div v-else-if="recommendations" class="recommendations-sections">
          <!-- 推荐主数据源 -->
          <div v-if="recommendations.primary_source" class="primary-source-section">
            <h4 class="section-title">
              <el-icon class="title-icon"><Star /></el-icon>
              推荐主数据源
            </h4>
            <div class="primary-source-card">
              <div class="source-info">
                <el-tag type="success" size="large" class="source-tag">
                  {{ recommendations.primary_source.name.toUpperCase() }}
                </el-tag>
                <div class="source-details">
                  <div class="priority">优先级: {{ recommendations.primary_source.priority }}</div>
                  <div class="reason">{{ recommendations.primary_source.reason }}</div>
                </div>
              </div>
            </div>
          </div>

          <!-- 备用数据源 -->
          <div v-if="recommendations.fallback_sources.length > 0" class="fallback-sources-section">
            <h4 class="section-title">
              <el-icon class="title-icon"><Connection /></el-icon>
              备用数据源
            </h4>
            <div class="fallback-sources-list">
              <div 
                v-for="source in recommendations.fallback_sources" 
                :key="source.name"
                class="fallback-source-item"
              >
                <el-tag type="info" size="default">
                  {{ source.name.toUpperCase() }}
                </el-tag>
                <span class="source-priority">优先级: {{ source.priority }}</span>
              </div>
            </div>
          </div>

          <!-- 建议列表 -->
          <div v-if="recommendations.suggestions.length > 0" class="suggestions-section">
            <h4 class="section-title">
              <el-icon class="title-icon"><Promotion /></el-icon>
              优化建议
            </h4>
            <div class="suggestions-list">
              <div 
                v-for="(suggestion, index) in recommendations.suggestions" 
                :key="index"
                class="suggestion-item"
              >
                <el-icon class="suggestion-icon"><Select /></el-icon>
                <span class="suggestion-text">{{ suggestion }}</span>
              </div>
            </div>
          </div>

          <!-- 警告信息 -->
          <div v-if="recommendations.warnings.length > 0" class="warnings-section">
            <h4 class="section-title">
              <el-icon class="title-icon"><Warning /></el-icon>
              注意事项
            </h4>
            <div class="warnings-list">
              <el-alert
                v-for="(warning, index) in recommendations.warnings"
                :key="index"
                :title="warning"
                type="warning"
                :closable="false"
                show-icon
                class="warning-item"
              />
            </div>
          </div>

          <!-- 配置示例 -->
          <div class="config-example-section">
            <h4 class="section-title">
              <el-icon class="title-icon"><Document /></el-icon>
              配置示例
            </h4>
            <div class="config-example">
              <el-collapse>
                <el-collapse-item title="环境变量配置" name="env">
                  <div class="code-block">
                    <pre><code># Tushare配置（推荐）
TUSHARE_ENABLED=true
TUSHARE_TOKEN=your_tushare_token_here

# AKShare配置
AKSHARE_ENABLED=true

# BaoStock配置
BAOSTOCK_ENABLED=true

# 默认数据源
DEFAULT_CHINA_DATA_SOURCE={{ recommendations.primary_source?.name || 'tushare' }}</code></pre>
                  </div>
                </el-collapse-item>
                
                <el-collapse-item title="API调用示例" name="api">
                  <div class="code-block">
                    <pre><code># 使用默认优先级同步
POST /api/sync/multi-source/stock_basics/run

# 指定优先数据源
POST /api/sync/multi-source/stock_basics/run?preferred_sources={{ getPreferredSourcesExample() }}

# 强制同步
POST /api/sync/multi-source/stock_basics/run?force=true</code></pre>
                  </div>
                </el-collapse-item>
              </el-collapse>
            </div>
          </div>
        </div>

        <div v-else class="empty-state">
          <el-empty description="暂无建议信息" />
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Promotion,
  Refresh,
  Star,
  Connection,
  Select,
  Warning,
  Document
} from '@element-plus/icons-vue'
import { getSyncRecommendations, type SyncRecommendations } from '@/api/sync'

// 响应式数据
const loading = ref(false)
const error = ref('')
const recommendations = ref<SyncRecommendations | null>(null)

// 获取同步建议
const fetchRecommendations = async () => {
  try {
    loading.value = true
    error.value = ''
    
    const response = await getSyncRecommendations()
    if (response.success) {
      recommendations.value = response.data
    } else {
      error.value = response.message || '获取建议失败'
    }
  } catch (err: any) {
    console.error('获取同步建议失败:', err)
    error.value = err.message || '网络请求失败'
  } finally {
    loading.value = false
  }
}

// 获取优先数据源示例
const getPreferredSourcesExample = (): string => {
  if (!recommendations.value) return 'tushare,akshare'
  
  const sources = []
  if (recommendations.value.primary_source) {
    sources.push(recommendations.value.primary_source.name)
  }
  if (recommendations.value.fallback_sources.length > 0) {
    sources.push(recommendations.value.fallback_sources[0].name)
  }
  
  return sources.join(',') || 'tushare,akshare'
}

// 组件挂载时获取数据
onMounted(() => {
  fetchRecommendations()
})
</script>

<style scoped lang="scss">
.sync-recommendations {
  .recommendations-card {
    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      
      .header-icon {
        margin-right: 8px;
        color: var(--el-color-warning);
      }
      
      .header-title {
        font-weight: 600;
        flex: 1;
      }
    }
  }

  .recommendations-content {
    min-height: 200px;
  }

  .recommendations-sections {
    .section-title {
      display: flex;
      align-items: center;
      margin: 0 0 16px 0;
      font-size: 16px;
      font-weight: 600;
      color: var(--el-text-color-primary);
      
      .title-icon {
        margin-right: 8px;
      }
    }

    .primary-source-section {
      margin-bottom: 24px;
      
      .primary-source-card {
        padding: 16px;
        border: 2px solid var(--el-color-success-light-7);
        border-radius: 8px;
        background-color: var(--el-color-success-light-9);
        
        .source-info {
          display: flex;
          align-items: center;
          gap: 16px;
          
          .source-details {
            .priority {
              font-size: 14px;
              color: var(--el-text-color-regular);
              margin-bottom: 4px;
            }
            
            .reason {
              font-size: 14px;
              color: var(--el-text-color-secondary);
            }
          }
        }
      }
    }

    .fallback-sources-section {
      margin-bottom: 24px;
      
      .fallback-sources-list {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        
        .fallback-source-item {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 8px 12px;
          border: 1px solid var(--el-border-color-light);
          border-radius: 6px;
          background-color: var(--el-fill-color-lighter);
          
          .source-priority {
            font-size: 12px;
            color: var(--el-text-color-secondary);
          }
        }
      }
    }

    .suggestions-section {
      margin-bottom: 24px;
      
      .suggestions-list {
        .suggestion-item {
          display: flex;
          align-items: flex-start;
          gap: 8px;
          margin-bottom: 12px;
          padding: 8px 0;
          
          .suggestion-icon {
            color: var(--el-color-success);
            margin-top: 2px;
            flex-shrink: 0;
          }
          
          .suggestion-text {
            line-height: 1.5;
            color: var(--el-text-color-regular);
          }
        }
      }
    }

    .warnings-section {
      margin-bottom: 24px;
      
      .warnings-list {
        .warning-item {
          margin-bottom: 8px;
          
          &:last-child {
            margin-bottom: 0;
          }
        }
      }
    }

    .config-example-section {
      .config-example {
        .code-block {
          background-color: var(--el-fill-color-lighter);
          border-radius: 6px;
          padding: 16px;
          
          pre {
            margin: 0;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            font-size: 13px;
            line-height: 1.5;
            color: var(--el-text-color-primary);
            white-space: pre-wrap;
            word-wrap: break-word;
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

@media (max-width: 768px) {
  .sync-recommendations {
    .recommendations-sections {
      .fallback-sources-section {
        .fallback-sources-list {
          .fallback-source-item {
            flex-direction: column;
            align-items: flex-start;
            gap: 4px;
          }
        }
      }
    }
  }
}
</style>
