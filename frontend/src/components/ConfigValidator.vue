<template>
  <div class="config-validator">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <h3>
            <el-icon><CircleCheck /></el-icon>
            配置验证
          </h3>
          <el-button
            type="primary"
            size="small"
            @click="handleValidate"
            :loading="validating"
          >
            <el-icon><Refresh /></el-icon>
            重新验证
          </el-button>
        </div>
      </template>

      <div v-loading="validating" class="validator-content">
        <!-- 验证结果摘要 -->
        <div v-if="validationResult" class="validation-summary">
          <!-- 必需配置错误（红色） -->
          <el-alert
            v-if="!validationResult.success"
            title="配置验证失败"
            type="error"
            :closable="false"
            show-icon
          >
            <p v-if="envValidation?.missing_required?.length">
              缺少 {{ envValidation.missing_required.length }} 个必需配置
            </p>
            <p v-if="envValidation?.invalid_configs?.length">
              {{ envValidation.invalid_configs.length }} 个配置无效
            </p>
          </el-alert>

          <!-- 推荐配置警告（黄色） -->
          <el-alert
            v-else-if="hasRecommendedWarnings"
            title="配置验证通过（有推荐配置未设置）"
            type="warning"
            :closable="false"
            show-icon
          >
            <p v-if="envValidation?.missing_recommended?.length">
              缺少 {{ envValidation.missing_recommended.length }} 个推荐配置
            </p>
            <p v-if="mongodbValidation?.warnings?.length">
              {{ mongodbValidation.warnings.length }} 个 MongoDB 配置警告
            </p>
          </el-alert>

          <!-- 所有配置正常（绿色） -->
          <el-alert
            v-else
            title="配置验证通过"
            type="success"
            :closable="false"
            show-icon
          >
            <p>所有配置已正确设置</p>
          </el-alert>
        </div>

        <!-- 必需配置 -->
        <div class="config-section">
          <h4>
            <el-icon><Star /></el-icon>
            必需配置
          </h4>
          <div class="config-items">
            <div
              v-for="item in requiredConfigs"
              :key="item.key"
              class="config-item"
              :class="{ 'is-valid': item.valid, 'is-invalid': !item.valid }"
            >
              <div class="item-icon">
                <el-icon v-if="item.valid" color="#67C23A"><CircleCheck /></el-icon>
                <el-icon v-else color="#F56C6C"><CircleClose /></el-icon>
              </div>
              <div class="item-content">
                <div class="item-name">{{ item.name }}</div>
                <div class="item-description">{{ item.description }}</div>
                <div v-if="!item.valid && item.error" class="item-error">
                  {{ item.error }}
                </div>
              </div>
              <div class="item-status">
                <el-tag :type="item.valid ? 'success' : 'danger'" size="small">
                  {{ item.valid ? '已配置' : '未配置' }}
                </el-tag>
              </div>
            </div>
          </div>
        </div>

        <!-- 推荐配置 -->
        <div class="config-section">
          <h4>
            <el-icon><Warning /></el-icon>
            推荐配置
          </h4>
          <div class="config-items">
            <div
              v-for="item in recommendedConfigs"
              :key="item.key"
              class="config-item"
              :class="{ 'is-valid': item.valid, 'is-warning': !item.valid }"
            >
              <div class="item-icon">
                <el-icon v-if="item.valid" color="#67C23A"><CircleCheck /></el-icon>
                <el-icon v-else color="#E6A23C"><Warning /></el-icon>
              </div>
              <div class="item-content">
                <div class="item-name">{{ item.name }}</div>
                <div class="item-description">{{ item.description }}</div>
                <div v-if="!item.valid && item.help" class="item-help">
                  {{ item.help }}
                </div>
              </div>
              <div class="item-status">
                <el-tag :type="item.valid ? 'success' : 'warning'" size="small">
                  {{ item.valid ? '已配置' : '未配置' }}
                </el-tag>
              </div>
            </div>
          </div>
        </div>

        <!-- MongoDB 配置验证 -->
        <div v-if="mongodbValidation" class="config-section">
          <h4>
            <el-icon><Coin /></el-icon>
            MongoDB 配置验证
          </h4>

          <!-- 大模型厂家配置 -->
          <div v-if="mongodbValidation.llm_providers?.length" class="mongodb-subsection">
            <h5>大模型厂家</h5>
            <div class="config-items">
              <div
                v-for="(item, index) in mongodbValidation.llm_providers"
                :key="index"
                class="config-item"
                :class="{
                  'is-valid': item.status === '已配置',
                  'is-warning': item.status === '未配置或占位符'
                }"
              >
                <div class="item-icon">
                  <el-icon v-if="item.status === '已配置'" color="#67C23A"><CircleCheck /></el-icon>
                  <el-icon v-else color="#E6A23C"><Warning /></el-icon>
                </div>
                <div class="item-content">
                  <div class="item-name">{{ item.display_name }}</div>
                  <div class="item-description">{{ item.name }}</div>
                </div>
                <div class="item-status">
                  <el-tag
                    :type="item.status === '已配置' ? 'success' : item.enabled ? 'warning' : 'info'"
                    size="small"
                  >
                    {{ item.status }}
                  </el-tag>
                </div>
              </div>
            </div>
          </div>

          <!-- 数据源配置 -->
          <div v-if="mongodbValidation.data_source_configs?.length" class="mongodb-subsection">
            <h5>数据源配置</h5>
            <div class="config-items">
              <div
                v-for="(item, index) in mongodbValidation.data_source_configs"
                :key="index"
                class="config-item"
                :class="{
                  'is-valid': item.status === '已配置' || item.status === '已配置（无需密钥）',
                  'is-warning': item.status === '未配置或占位符' && item.enabled,
                  'is-disabled': !item.enabled
                }"
              >
                <div class="item-icon">
                  <el-icon v-if="item.status.includes('已配置')" color="#67C23A"><CircleCheck /></el-icon>
                  <el-icon v-else-if="item.enabled" color="#E6A23C"><Warning /></el-icon>
                  <el-icon v-else color="#909399"><CircleClose /></el-icon>
                </div>
                <div class="item-content">
                  <div class="item-name">{{ item.name }}</div>
                  <div class="item-description">{{ item.type }}</div>
                </div>
                <div class="item-status">
                  <el-tag
                    :type="item.status.includes('已配置') ? 'success' : item.enabled ? 'warning' : 'info'"
                    size="small"
                  >
                    {{ item.status }}
                  </el-tag>
                </div>
              </div>
            </div>
          </div>

          <!-- MongoDB 配置警告 -->
          <div v-if="mongodbValidation.warnings?.length" class="mongodb-warnings">
            <el-alert
              v-for="(warning, index) in mongodbValidation.warnings"
              :key="index"
              :title="warning"
              type="warning"
              :closable="false"
              show-icon
              class="warning-item"
            />
          </div>
        </div>

        <!-- 环境变量警告信息 -->
        <div v-if="envValidation?.warnings?.length" class="warnings-section">
          <h4>
            <el-icon><InfoFilled /></el-icon>
            环境变量警告
          </h4>
          <el-alert
            v-for="(warning, index) in envValidation.warnings"
            :key="index"
            :title="warning"
            type="warning"
            :closable="false"
            show-icon
            class="warning-item"
          />
        </div>

        <!-- 帮助信息 -->
        <div class="help-section">
          <el-collapse>
            <el-collapse-item title="如何修复配置问题？" name="1">
              <div class="help-content">
                <h5>必需配置</h5>
                <p>必需配置需要在 <code>.env</code> 文件中设置：</p>
                <ol>
                  <li>在项目根目录找到 <code>.env</code> 文件（如果没有，复制 <code>.env.example</code>）</li>
                  <li>按照提示填写缺少的配置项</li>
                  <li>保存文件并重启后端服务</li>
                </ol>

                <h5>推荐配置</h5>
                <p>推荐配置可以通过以下方式设置：</p>
                <ul>
                  <li>在 <code>.env</code> 文件中设置（推荐）</li>
                  <li>在"配置管理"页面的"大模型配置"或"数据源配置"中设置</li>
                </ul>

                <h5>常见问题</h5>
                <p><strong>Q: 为什么修改后还是显示未配置？</strong></p>
                <p>A: 环境变量需要重启后端服务才能生效。</p>

                <p><strong>Q: 如何获取 API 密钥？</strong></p>
                <p>A: 请访问对应服务商的官网注册并获取密钥。详见"配置管理"页面的帮助信息。</p>
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  CircleCheck,
  CircleClose,
  Refresh,
  Star,
  Warning,
  InfoFilled,
  Coin
} from '@element-plus/icons-vue'
import axios from 'axios'

// 类型定义
interface ConfigItem {
  key: string
  name: string
  description: string
  valid: boolean
  error?: string
  help?: string
}

interface EnvValidationResult {
  success: boolean
  missing_required?: Array<{ key: string; description: string }>
  missing_recommended?: Array<{ key: string; description: string }>
  invalid_configs?: Array<{ key: string; error: string }>
  warnings?: string[]
}

interface MongoDBValidationResult {
  llm_providers?: Array<{
    name: string
    display_name: string
    is_active: boolean
    has_api_key: boolean
    status: string
  }>
  data_source_configs?: Array<{
    name: string
    type: string
    enabled: boolean
    has_api_key: boolean
    status: string
  }>
  warnings?: string[]
}

interface ValidationResult {
  success: boolean
  env_validation?: EnvValidationResult
  mongodb_validation?: MongoDBValidationResult
}

// 响应式数据
const validating = ref(false)
const validationResult = ref<ValidationResult | null>(null)
const envValidation = ref<EnvValidationResult | null>(null)
const mongodbValidation = ref<MongoDBValidationResult | null>(null)
const requiredConfigs = ref<ConfigItem[]>([])
const recommendedConfigs = ref<ConfigItem[]>([])

// 计算属性：是否有推荐配置警告
const hasRecommendedWarnings = computed(() => {
  const hasMissingRecommended = (envValidation.value?.missing_recommended?.length ?? 0) > 0
  const hasMongodbWarnings = (mongodbValidation.value?.warnings?.length ?? 0) > 0
  return hasMissingRecommended || hasMongodbWarnings
})

// 方法
const handleValidate = async () => {
  validating.value = true
  try {
    const response = await axios.get('/api/system/config/validate')

    console.log('🔍 配置验证响应:', response.data)

    if (response.data.success) {
      validationResult.value = response.data.data

      // 提取环境变量验证结果和 MongoDB 验证结果
      envValidation.value = response.data.data.env_validation || null
      mongodbValidation.value = response.data.data.mongodb_validation || null

      console.log('🔍 环境变量验证:', envValidation.value)
      console.log('🔍 MongoDB 验证:', mongodbValidation.value)

      updateConfigItems()

      if (validationResult.value?.success) {
        ElMessage.success('配置验证通过')
      } else {
        ElMessage.warning('配置验证失败，请检查缺少的配置项')
      }
    } else {
      ElMessage.error(response.data.message || '验证失败')
    }
  } catch (error: any) {
    console.error('配置验证失败:', error)
    ElMessage.error(error.response?.data?.message || '验证失败')
  } finally {
    validating.value = false
  }
}

const updateConfigItems = () => {
  if (!envValidation.value) return

  // 更新必需配置
  const requiredKeys = [
    { key: 'MONGODB_HOST', name: 'MongoDB 主机', description: 'MongoDB 数据库主机地址' },
    { key: 'MONGODB_PORT', name: 'MongoDB 端口', description: 'MongoDB 数据库端口' },
    { key: 'MONGODB_DATABASE', name: 'MongoDB 数据库', description: 'MongoDB 数据库名称' },
    { key: 'REDIS_HOST', name: 'Redis 主机', description: 'Redis 缓存主机地址' },
    { key: 'REDIS_PORT', name: 'Redis 端口', description: 'Redis 缓存端口' },
    { key: 'JWT_SECRET', name: 'JWT 密钥', description: 'JWT 认证密钥' }
  ]

  requiredConfigs.value = requiredKeys.map(item => {
    const missing = envValidation.value?.missing_required?.find(m => m.key === item.key)
    const invalid = envValidation.value?.invalid_configs?.find(i => i.key === item.key)

    return {
      ...item,
      valid: !missing && !invalid,
      error: invalid?.error || (missing ? '未配置' : undefined)
    }
  })

  // 更新推荐配置
  const recommendedKeys = [
    { key: 'DEEPSEEK_API_KEY', name: 'DeepSeek API', description: 'DeepSeek 大模型 API 密钥', help: '用于 AI 分析功能' },
    { key: 'DASHSCOPE_API_KEY', name: '通义千问 API', description: '阿里云通义千问 API 密钥', help: '用于 AI 分析功能' },
    { key: 'TUSHARE_TOKEN', name: 'Tushare Token', description: 'Tushare 数据源 Token', help: '用于获取专业A股数据' }
  ]

  recommendedConfigs.value = recommendedKeys.map(item => {
    const missing = envValidation.value?.missing_recommended?.find(m => m.key === item.key)

    return {
      ...item,
      valid: !missing
    }
  })
}

// 生命周期
onMounted(() => {
  handleValidate()
})
</script>

<style scoped lang="scss">
.config-validator {
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    h3 {
      margin: 0;
      font-size: 16px;
      color: var(--el-text-color-primary);
      display: flex;
      align-items: center;
      gap: 8px;
    }
  }

  .validator-content {
    .validation-summary {
      margin-bottom: 24px;
    }

    .config-section {
      margin-bottom: 24px;

      h4 {
        margin: 0 0 16px 0;
        font-size: 14px;
        font-weight: 600;
        color: var(--el-text-color-primary);
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .config-items {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }

      .config-item {
        display: flex;
        align-items: flex-start;
        gap: 12px;
        padding: 16px;
        border-radius: 8px;
        border: 1px solid var(--el-border-color-light);
        background: var(--el-fill-color-blank);
        transition: all 0.3s;

        &.is-valid {
          border-color: var(--el-color-success-light-5);
          background: var(--el-color-success-light-9);
        }

        &.is-invalid {
          border-color: var(--el-color-danger-light-5);
          background: var(--el-color-danger-light-9);
        }

        &.is-warning {
          border-color: var(--el-color-warning-light-5);
          background: var(--el-color-warning-light-9);
        }

        &.is-disabled {
          border-color: var(--el-border-color-lighter);
          background: var(--el-fill-color-lighter);
          opacity: 0.7;
        }

        .item-icon {
          flex-shrink: 0;
          font-size: 20px;
        }

        .item-content {
          flex: 1;

          .item-name {
            font-size: 14px;
            font-weight: 600;
            color: var(--el-text-color-primary);
            margin-bottom: 4px;
          }

          .item-description {
            font-size: 13px;
            color: var(--el-text-color-regular);
            margin-bottom: 4px;
          }

          .item-error {
            font-size: 12px;
            color: var(--el-color-danger);
            margin-top: 4px;
          }

          .item-help {
            font-size: 12px;
            color: var(--el-color-warning);
            margin-top: 4px;
          }
        }

        .item-status {
          flex-shrink: 0;
        }
      }
    }

    .mongodb-subsection {
      margin-bottom: 20px;

      h5 {
        margin: 0 0 12px 0;
        font-size: 13px;
        font-weight: 600;
        color: var(--el-text-color-secondary);
        padding-left: 8px;
        border-left: 3px solid var(--el-color-primary);
      }

      &:last-child {
        margin-bottom: 0;
      }
    }

    .mongodb-warnings {
      margin-top: 16px;

      .warning-item {
        margin-bottom: 8px;

        &:last-child {
          margin-bottom: 0;
        }
      }
    }

    .warnings-section {
      margin-bottom: 24px;

      h4 {
        margin: 0 0 16px 0;
        font-size: 14px;
        font-weight: 600;
        color: var(--el-text-color-primary);
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .warning-item {
        margin-bottom: 8px;

        &:last-child {
          margin-bottom: 0;
        }
      }
    }

    .help-section {
      .help-content {
        h5 {
          margin: 16px 0 8px 0;
          font-size: 14px;
          color: var(--el-text-color-primary);

          &:first-child {
            margin-top: 0;
          }
        }

        p {
          margin: 8px 0;
          font-size: 13px;
          color: var(--el-text-color-regular);
          line-height: 1.6;
        }

        code {
          padding: 2px 6px;
          background: var(--el-fill-color-light);
          border-radius: 4px;
          font-family: 'Courier New', monospace;
          font-size: 12px;
        }

        ol, ul {
          margin: 8px 0;
          padding-left: 24px;

          li {
            margin: 4px 0;
            font-size: 13px;
            color: var(--el-text-color-regular);
            line-height: 1.6;
          }
        }
      }
    }
  }
}
</style>

