<template>
  <el-dialog
    v-model="visible"
    title="配置向导"
    width="800px"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    :show-close="currentStep > 0"
  >
    <div class="config-wizard">
      <!-- 步骤指示器 -->
      <el-steps :active="currentStep" align-center finish-status="success">
        <el-step title="欢迎" icon="el-icon-star-on" />
        <el-step title="数据库配置" icon="el-icon-coin" />
        <el-step title="大模型配置" icon="el-icon-cpu" />
        <el-step title="数据源配置" icon="el-icon-data-board" />
        <el-step title="完成" icon="el-icon-circle-check" />
      </el-steps>

      <!-- 步骤内容 -->
      <div class="wizard-content">
        <!-- 步骤 0: 欢迎 -->
        <div v-if="currentStep === 0" class="step-content welcome-step">
          <div class="welcome-icon">
            <el-icon :size="80" color="#409EFF"><Setting /></el-icon>
          </div>
          <h2>欢迎使用 TradingAgents-CN</h2>
          <p class="welcome-text">
            让我们通过几个简单的步骤来配置您的系统。
            这将帮助您快速开始使用股票分析功能。
          </p>
          <el-alert
            title="提示"
            type="info"
            :closable="false"
            show-icon
          >
            <template #default>
              <div>您可以随时在"配置管理"页面修改这些设置。</div>
              <div>如果您已经配置过系统，可以跳过此向导。</div>
            </template>
          </el-alert>
        </div>

        <!-- 步骤 1: 数据库配置 -->
        <div v-if="currentStep === 1" class="step-content">
          <h3>数据库配置</h3>
          <p class="step-description">
            系统需要连接到 MongoDB 和 Redis 数据库。
          </p>

          <el-form :model="wizardData" label-width="120px">
            <el-divider content-position="left">MongoDB 配置</el-divider>
            <el-form-item label="主机地址">
              <el-input
                v-model="wizardData.mongodb.host"
                placeholder="localhost"
              />
            </el-form-item>
            <el-form-item label="端口">
              <el-input
                v-model="wizardData.mongodb.port"
                placeholder="27017"
                type="number"
              />
            </el-form-item>
            <el-form-item label="数据库名">
              <el-input
                v-model="wizardData.mongodb.database"
                placeholder="tradingagents"
              />
            </el-form-item>

            <el-divider content-position="left">Redis 配置</el-divider>
            <el-form-item label="主机地址">
              <el-input
                v-model="wizardData.redis.host"
                placeholder="localhost"
              />
            </el-form-item>
            <el-form-item label="端口">
              <el-input
                v-model="wizardData.redis.port"
                placeholder="6379"
                type="number"
              />
            </el-form-item>
          </el-form>

          <el-alert
            title="注意"
            type="warning"
            :closable="false"
            show-icon
            description="数据库配置需要在 .env 文件中设置，此处仅用于验证连接。"
          />
        </div>

        <!-- 步骤 2: 大模型配置 -->
        <div v-if="currentStep === 2" class="step-content">
          <h3>大模型配置</h3>
          <p class="step-description">
            至少配置一个大模型 API 密钥，用于 AI 分析功能。
          </p>

          <el-form :model="wizardData" label-width="120px">
            <el-form-item label="选择大模型">
              <el-select
                v-model="wizardData.llm.provider"
                placeholder="请选择大模型提供商"
                @change="handleProviderChange"
              >
                <el-option label="DeepSeek（推荐，性价比高）" value="deepseek" />
                <el-option label="通义千问（推荐，国产稳定）" value="dashscope" />
                <el-option label="OpenAI" value="openai" />
                <el-option label="Google Gemini" value="google" />
              </el-select>
            </el-form-item>

            <el-form-item v-if="wizardData.llm.provider" label="API 密钥">
              <el-input
                v-model="wizardData.llm.apiKey"
                type="password"
                placeholder="请输入 API 密钥"
                show-password
              />
            </el-form-item>

            <el-form-item v-if="wizardData.llm.provider" label="模型名称">
              <el-select
                v-model="wizardData.llm.modelName"
                placeholder="请选择模型"
              >
                <template v-for="model in availableModels" :key="model.value">
                  <el-option
                    :label="model.label"
                    :value="model.value"
                  />
                </template>
              </el-select>
            </el-form-item>
          </el-form>

          <el-alert
            v-if="wizardData.llm.provider"
            :title="`如何获取 ${getProviderName(wizardData.llm.provider)} API 密钥？`"
            type="info"
            :closable="false"
            show-icon
          >
            <template #default>
              <div>
                <div style="margin-bottom: 8px;">{{ getProviderHelp(wizardData.llm.provider) }}</div>
                <div>
                  <el-link
                    :href="getProviderUrl(wizardData.llm.provider)"
                    type="primary"
                    target="_blank"
                  >
                    前往获取 →
                  </el-link>
                </div>
              </div>
            </template>
          </el-alert>
        </div>

        <!-- 步骤 3: 数据源配置 -->
        <div v-if="currentStep === 3" class="step-content">
          <h3>数据源配置</h3>
          <p class="step-description">
            选择股票数据源，用于获取行情数据和基本信息。
          </p>

          <el-form :model="wizardData" label-width="120px">
            <el-form-item label="默认数据源">
              <el-select
                v-model="datasourceType"
                placeholder="请选择数据源"
              >
                <el-option label="AKShare（推荐，免费无需密钥）" value="akshare" />
                <el-option label="Tushare（专业A股数据）" value="tushare" />
                <el-option label="FinnHub（美股数据）" value="finnhub" />
              </el-select>
            </el-form-item>

            <el-form-item
              v-if="datasourceType === 'tushare'"
              label="Tushare Token"
            >
              <el-input
                v-model="datasourceToken"
                placeholder="请输入 Tushare Token"
              />
            </el-form-item>

            <el-form-item
              v-if="datasourceType === 'finnhub'"
              label="FinnHub API Key"
            >
              <el-input
                v-model="datasourceApiKey"
                placeholder="请输入 FinnHub API Key"
              />
            </el-form-item>
          </el-form>

          <el-alert
            v-if="datasourceType === 'akshare'"
            title="AKShare 无需配置"
            type="success"
            :closable="false"
            show-icon
            description="AKShare 是免费的数据源，无需 API 密钥即可使用。"
          />

          <el-alert
            v-if="datasourceType === 'tushare'"
            title="如何获取 Tushare Token？"
            type="info"
            :closable="false"
            show-icon
          >
            <template #default>
              <div>
                <div>1. 访问 Tushare 官网注册账号</div>
                <div>2. 邮箱验证后登录</div>
                <div>3. 在个人中心获取 Token</div>
                <div style="margin-top: 8px;">
                  <el-link
                    href="https://tushare.pro/register?reg=tacn"
                    type="primary"
                    target="_blank"
                  >
                    前往注册 →
                  </el-link>
                </div>
              </div>
            </template>
          </el-alert>
        </div>

        <!-- 步骤 4: 完成 -->
        <div v-if="currentStep === 4" class="step-content complete-step">
          <div class="complete-icon">
            <el-icon :size="80" color="#67C23A"><CircleCheck /></el-icon>
          </div>
          <h2>配置完成！</h2>
          <p class="complete-text">
            恭喜！您已经完成了基本配置。现在可以开始使用系统了。
          </p>

          <div class="config-summary">
            <h4>配置摘要</h4>
            <el-descriptions :column="1" border>
              <el-descriptions-item label="数据库">
                MongoDB: {{ wizardData.mongodb.host }}:{{ wizardData.mongodb.port }}
              </el-descriptions-item>
              <el-descriptions-item label="大模型">
                {{ getProviderName(wizardData.llm.provider) }} - {{ wizardData.llm.modelName }}
              </el-descriptions-item>
              <el-descriptions-item label="数据源">
                {{ getDataSourceName(datasourceType) }}
              </el-descriptions-item>
            </el-descriptions>
          </div>

          <el-alert
            title="下一步"
            type="success"
            :closable="false"
            show-icon
          >
            <template #default>
              <div>
                <div>• 访问"仪表盘"查看系统概览</div>
                <div>• 访问"单股分析"开始分析股票</div>
                <div>• 访问"配置管理"调整详细设置</div>
              </div>
            </template>
          </el-alert>
        </div>
      </div>
    </div>

    <!-- 底部按钮（必须是 el-dialog 的直接子元素） -->
    <template #footer>
      <div class="wizard-footer">
        <el-button
          v-if="currentStep > 0 && currentStep < 4"
          @click="handlePrevious"
        >
          上一步
        </el-button>
        <el-button
          v-if="currentStep === 0"
          @click="handleSkip"
        >
          跳过向导
        </el-button>
        <el-button
          v-if="currentStep < 4"
          type="primary"
          @click="handleNext"
          :loading="saving"
        >
          {{ currentStep === 0 ? '开始配置' : '下一步' }}
        </el-button>
        <el-button
          v-if="currentStep === 4"
          type="primary"
          @click="handleComplete"
        >
          完成
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Setting, CircleCheck } from '@element-plus/icons-vue'

// 类型定义
interface DataSourceConfig {
  type: string
  token: string
  apiKey: string
}

interface WizardData {
  mongodb: {
    host: string
    port: number
    database: string
  }
  redis: {
    host: string
    port: number
  }
  llm: {
    provider: string
    apiKey: string
    modelName: string
  }
  datasource: DataSourceConfig
}

// Props
interface Props {
  modelValue: boolean
}

const props = defineProps<Props>()

// Emits
const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'complete', data: WizardData): void
}>()

// 响应式数据
const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const currentStep = ref(0)
const saving = ref(false)

const wizardData = ref<WizardData>({
  mongodb: {
    host: 'localhost',
    port: 27017,
    database: 'tradingagents'
  },
  redis: {
    host: 'localhost',
    port: 6379
  },
  llm: {
    provider: '',
    apiKey: '',
    modelName: ''
  },
  datasource: {
    type: 'akshare',
    token: '',
    apiKey: ''
  }
})

// 可用模型列表
const availableModels = computed(() => {
  const provider = wizardData.value.llm.provider
  const models: Record<string, Array<{ label: string; value: string }>> = {
    deepseek: [
      { label: 'deepseek-chat', value: 'deepseek-chat' },
      { label: 'deepseek-coder', value: 'deepseek-coder' }
    ],
    dashscope: [
      { label: 'qwen-turbo', value: 'qwen-turbo' },
      { label: 'qwen-plus', value: 'qwen-plus' },
      { label: 'qwen-max', value: 'qwen-max' }
    ],
    openai: [
      { label: 'gpt-3.5-turbo', value: 'gpt-3.5-turbo' },
      { label: 'gpt-4', value: 'gpt-4' },
      { label: 'gpt-4-turbo', value: 'gpt-4-turbo' }
    ],
    google: [
      { label: 'gemini-pro', value: 'gemini-pro' },
      { label: 'gemini-2.5-pro', value: 'gemini-2.5-pro' }
    ]
  }
  return models[provider] || []
})

// 数据源相关的计算属性，用于双向绑定
const datasourceType = computed({
  get: () => wizardData.value.datasource.type,
  set: (value: string) => {
    wizardData.value.datasource.type = value
  }
})

const datasourceToken = computed({
  get: () => wizardData.value.datasource.token,
  set: (value: string) => {
    wizardData.value.datasource.token = value
  }
})

const datasourceApiKey = computed({
  get: () => wizardData.value.datasource.apiKey,
  set: (value: string) => {
    wizardData.value.datasource.apiKey = value
  }
})

// 方法
const handleProviderChange = () => {
  wizardData.value.llm.modelName = ''
  if (availableModels.value.length > 0) {
    wizardData.value.llm.modelName = availableModels.value[0].value
  }
}

const getProviderName = (provider: string) => {
  const names: Record<string, string> = {
    deepseek: 'DeepSeek',
    dashscope: '通义千问',
    openai: 'OpenAI',
    google: 'Google Gemini'
  }
  return names[provider] || provider
}

const getProviderHelp = (provider: string) => {
  const helps: Record<string, string> = {
    deepseek: '注册 DeepSeek 账号，在控制台创建 API Key',
    dashscope: '注册阿里云账号，开通百炼服务，获取 API 密钥',
    openai: '注册 OpenAI 账号，在 API Keys 页面创建密钥',
    google: '注册 Google Cloud 账号，启用 Gemini API'
  }
  return helps[provider] || ''
}

const getProviderUrl = (provider: string) => {
  const urls: Record<string, string> = {
    deepseek: 'https://platform.deepseek.com/',
    dashscope: 'https://dashscope.aliyun.com/',
    openai: 'https://platform.openai.com/',
    google: 'https://ai.google.dev/'
  }
  return urls[provider] || ''
}

const getDataSourceName = (type: string) => {
  const names: Record<string, string> = {
    akshare: 'AKShare',
    tushare: 'Tushare',
    finnhub: 'FinnHub'
  }
  return names[type] || type
}

const handleNext = async () => {
  // 验证当前步骤
  if (currentStep.value === 2 && !wizardData.value.llm.provider) {
    ElMessage.warning('请选择大模型提供商')
    return
  }

  if (currentStep.value === 2 && !wizardData.value.llm.apiKey) {
    ElMessage.warning('请输入 API 密钥')
    return
  }

  currentStep.value++
}

const handlePrevious = () => {
  currentStep.value--
}

const handleSkip = () => {
  visible.value = false
}

const handleComplete = () => {
  emit('complete', wizardData.value)
  visible.value = false
  ElMessage.success('配置向导完成！')
}
</script>

<style scoped lang="scss">
.config-wizard {
  .wizard-content {
    margin: 30px 0;
    min-height: 400px;

    .step-content {
      h3 {
        margin: 0 0 8px 0;
        font-size: 18px;
        color: var(--el-text-color-primary);
      }

      .step-description {
        margin: 0 0 24px 0;
        color: var(--el-text-color-regular);
      }

      &.welcome-step {
        text-align: center;
        padding: 40px 20px;

        .welcome-icon {
          margin-bottom: 24px;
        }

        h2 {
          margin: 0 0 16px 0;
          font-size: 24px;
          color: var(--el-text-color-primary);
        }

        .welcome-text {
          margin: 0 0 32px 0;
          font-size: 16px;
          color: var(--el-text-color-regular);
          line-height: 1.6;
        }
      }

      &.complete-step {
        text-align: center;
        padding: 40px 20px;

        .complete-icon {
          margin-bottom: 24px;
        }

        h2 {
          margin: 0 0 16px 0;
          font-size: 24px;
          color: var(--el-text-color-primary);
        }

        .complete-text {
          margin: 0 0 32px 0;
          font-size: 16px;
          color: var(--el-text-color-regular);
        }

        .config-summary {
          margin-bottom: 24px;
          text-align: left;

          h4 {
            margin: 0 0 16px 0;
            font-size: 16px;
            color: var(--el-text-color-primary);
          }
        }
      }
    }
  }

  .wizard-footer {
    display: flex;
    justify-content: space-between;
  }
}
</style>