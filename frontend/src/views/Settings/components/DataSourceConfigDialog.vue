<template>
  <el-dialog
    :model-value="visible"
    :title="isEdit ? '编辑数据源' : '添加数据源'"
    width="600px"
    @update:model-value="$emit('update:visible', $event)"
    @close="handleClose"
  >
    <el-form
      ref="formRef"
      :model="formData"
      :rules="rules"
      label-width="120px"
      label-position="left"
    >
      <!-- 基本信息 -->
      <el-form-item label="数据源类型" prop="type">
        <el-select
          v-model="formData.type"
          placeholder="请选择数据源类型"
          style="width: 100%"
          :disabled="isEdit"
          @change="handleTypeChange"
        >
          <el-option
            v-for="option in dataSourceTypes"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <div class="form-tip">
          ⚠️ 数据源类型一旦选择后不可修改，请谨慎选择
        </div>
      </el-form-item>

      <el-form-item label="数据源名称" prop="name">
        <el-input
          v-model="formData.name"
          placeholder="自动生成（基于数据源类型）"
          disabled
        />
        <div class="form-tip">
          📌 数据源名称由系统自动生成，用于后端识别，不可修改
        </div>
      </el-form-item>

      <el-form-item label="显示名称" prop="display_name">
        <el-input
          v-model="formData.display_name"
          placeholder="请输入显示名称（用于界面展示）"
        />
        <div class="form-tip">
          💡 显示名称可以自定义，用于在界面上展示，例如："Alpha Vantage - 美股数据"
        </div>
      </el-form-item>

      <!-- 🆕 注册引导提示 -->
      <el-alert
        v-if="formData.type && currentDataSourceInfo?.register_url"
        :title="`📝 ${currentDataSourceInfo.label} 注册引导`"
        type="info"
        :closable="false"
        class="mb-4"
      >
        <template #default>
          <div class="register-guide">
            <p>{{ currentDataSourceInfo.register_guide || '如果您还没有账号，请先注册：' }}</p>
            <el-button
              type="primary"
              size="small"
              link
              @click="openRegisterUrl"
            >
              <el-icon><Link /></el-icon>
              前往注册 {{ currentDataSourceInfo.label }}
            </el-button>
          </div>
        </template>
      </el-alert>

      <el-form-item label="数据提供商" prop="provider">
        <el-input
          v-model="formData.provider"
          placeholder="请输入数据提供商"
        />
      </el-form-item>

      <!-- 连接配置 -->
      <el-divider content-position="left">连接配置</el-divider>

      <el-form-item label="API端点" prop="endpoint">
        <el-input
          v-model="formData.endpoint"
          placeholder="请输入API端点URL"
        />
      </el-form-item>

      <!-- API Key 输入框 -->
      <el-form-item label="API Key" prop="api_key">
        <el-input
          v-model="formData.api_key"
          type="password"
          placeholder="输入 API Key（可选，留空则使用环境变量）"
          show-password
          clearable
        />
        <div class="form-tip">
          优先级：数据库配置 > 环境变量。留空则使用 .env 文件中的配置
        </div>
      </el-form-item>

      <!-- API Secret 输入框（某些数据源需要） -->
      <el-form-item v-if="needsApiSecret" label="API Secret" prop="api_secret">
        <el-input
          v-model="formData.api_secret"
          type="password"
          placeholder="输入 API Secret（可选）"
          show-password
          clearable
        />
        <div class="form-tip">
          某些数据源（如 Alpha Vantage）需要额外的 Secret Key
        </div>
      </el-form-item>

      <!-- 性能配置 -->
      <el-divider content-position="left">性能配置</el-divider>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="超时时间" prop="timeout">
            <el-input-number
              v-model="formData.timeout"
              :min="1"
              :max="300"
              controls-position="right"
              style="width: 100%"
            />
            <span class="form-help">秒</span>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="速率限制" prop="rate_limit">
            <el-input-number
              v-model="formData.rate_limit"
              :min="1"
              :max="10000"
              controls-position="right"
              style="width: 100%"
            />
            <span class="form-help">请求/分钟</span>
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="优先级" prop="priority">
        <el-input-number
          v-model="formData.priority"
          :min="0"
          :max="100"
          controls-position="right"
          style="width: 200px"
        />
        <span class="form-help">数值越大优先级越高</span>
      </el-form-item>

      <!-- 市场分类 -->
      <el-divider content-position="left">市场分类</el-divider>

      <el-form-item label="所属市场" prop="market_categories">
        <el-checkbox-group v-model="formData.market_categories">
          <el-checkbox
            v-for="category in marketCategories"
            :key="category.id"
            :label="category.id"
            :disabled="!category.enabled"
          >
            {{ category.display_name }}
          </el-checkbox>
        </el-checkbox-group>
      </el-form-item>

      <!-- 高级设置 -->
      <el-divider content-position="left">高级设置</el-divider>

      <el-form-item label="启用状态">
        <el-switch v-model="formData.enabled" />
      </el-form-item>

      <el-form-item label="描述" prop="description">
        <el-input
          v-model="formData.description"
          type="textarea"
          :rows="3"
          placeholder="请输入数据源描述"
        />
      </el-form-item>

      <!-- 自定义参数 -->
      <el-form-item label="自定义参数">
        <div class="config-params">
          <div
            v-for="(value, key, index) in formData.config_params"
            :key="index"
            class="param-item"
          >
            <el-input
              v-model="paramKeys[index]"
              placeholder="参数名"
              style="width: 40%"
              @blur="updateParamKey(index, paramKeys[index])"
            />
            <el-input
              v-model="formData.config_params[key]"
              placeholder="参数值"
              style="width: 40%; margin-left: 8px"
            />
            <el-button
              type="danger"
              size="small"
              icon="Delete"
              style="margin-left: 8px"
              @click="removeParam(key)"
            />
          </div>
          <el-button
            type="primary"
            size="small"
            icon="Plus"
            @click="addParam"
          >
            添加参数
          </el-button>
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleClose">取消</el-button>
        <el-button type="primary" :loading="loading" @click="handleSubmit">
          {{ isEdit ? '更新' : '创建' }}
        </el-button>
        <el-button
          v-if="formData.name"
          type="success"
          :loading="testing"
          @click="handleTest"
        >
          测试连接
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Link } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import {
  configApi,
  type DataSourceConfig,
  type MarketCategory
} from '@/api/config'

// Props
interface Props {
  visible: boolean
  config?: DataSourceConfig | null
}

const props = withDefaults(defineProps<Props>(), {
  config: null
})

// Emits
const emit = defineEmits<{
  'update:visible': [value: boolean]
  'success': []
}>()

// Refs
const formRef = ref<FormInstance>()
const loading = ref(false)
const testing = ref(false)
const marketCategories = ref<MarketCategory[]>([])

// Computed
const isEdit = computed(() => !!props.config)

// 判断是否需要显示 API Secret 字段
const needsApiSecret = computed(() => {
  const type = formData.value.type?.toLowerCase() || ''
  // 某些数据源类型需要 API Secret
  return ['alpha_vantage', 'wind', 'choice'].includes(type)
})

// 当前选中的数据源信息
const currentDataSourceInfo = computed(() => {
  if (!formData.value.type) return null
  return dataSourceTypes.find(ds => ds.value === formData.value.type)
})

// 打开注册链接
const openRegisterUrl = () => {
  if (currentDataSourceInfo.value?.register_url) {
    window.open(currentDataSourceInfo.value.register_url, '_blank')
  }
}

// 处理数据源类型变化
const handleTypeChange = () => {
  const selectedType = formData.value.type
  console.log('数据源类型已变更:', selectedType)

  // 🔥 自动填充数据源名称（使用数据源类型的值）
  if (selectedType) {
    formData.value.name = selectedType

    // 如果显示名称为空，也自动填充
    if (!formData.value.display_name) {
      const sourceInfo = dataSourceTypes.find(ds => ds.value === selectedType)
      if (sourceInfo) {
        formData.value.display_name = sourceInfo.label
      }
    }
  }
}

// 表单数据
const defaultFormData = {
  name: '',
  display_name: '',
  type: '',
  provider: '',
  api_key: '',
  api_secret: '',
  endpoint: '',
  timeout: 30,
  rate_limit: 100,
  enabled: true,
  priority: 0,
  config_params: {} as Record<string, any>,
  description: '',
  market_categories: [] as string[]
}

const formData = ref({ ...defaultFormData })
const paramKeys = ref<string[]>([])

/**
 * 数据源类型选项
 *
 * 注意：这些选项与后端 DataSourceType 枚举保持同步
 * 添加新数据源时，请先在后端 tradingagents/constants/data_sources.py 中注册
 */
const dataSourceTypes = [
  // 中国市场数据源
  {
    label: 'Tushare',
    value: 'tushare',
    register_url: 'https://tushare.pro/register?reg=tacn',
    register_guide: '如果您还没有 Tushare 账号，请先注册并获取 Token：'
  },
  {
    label: 'AKShare',
    value: 'akshare',
    register_url: 'https://akshare.akfamily.xyz/',
    register_guide: 'AKShare 是开源免费的金融数据接口库，无需注册即可使用。访问官网了解更多：'
  },
  {
    label: 'BaoStock',
    value: 'baostock',
    register_url: 'http://baostock.com/',
    register_guide: 'BaoStock 是开源免费的证券数据平台，无需注册即可使用。访问官网了解更多：'
  },

  // 美股数据源
  {
    label: 'Finnhub',
    value: 'finnhub',
    register_url: 'https://finnhub.io/register',
    register_guide: '如果您还没有 Finnhub 账号，请先注册并获取 API Key：'
  },
  {
    label: 'Yahoo Finance',
    value: 'yahoo_finance',
    register_url: 'https://finance.yahoo.com/',
    register_guide: 'Yahoo Finance 提供免费的金融数据，部分功能无需注册。访问官网了解更多：'
  },
  {
    label: 'Alpha Vantage',
    value: 'alpha_vantage',
    register_url: 'https://www.alphavantage.co/support/#api-key',
    register_guide: '如果您还没有 Alpha Vantage 账号，请先注册并获取免费 API Key：'
  },
  {
    label: 'IEX Cloud',
    value: 'iex_cloud',
    register_url: 'https://iexcloud.io/cloud-login#/register',
    register_guide: '如果您还没有 IEX Cloud 账号，请先注册并获取 API Token：'
  },

  // 专业数据源
  {
    label: 'Wind 万得',
    value: 'wind',
    register_url: 'https://www.wind.com.cn/',
    register_guide: 'Wind 是专业的金融数据服务商，需要购买商业授权。访问官网了解更多：'
  },
  {
    label: '东方财富 Choice',
    value: 'choice',
    register_url: 'https://choice.eastmoney.com/',
    register_guide: 'Choice 是专业的金融数据终端，需要购买商业授权。访问官网了解更多：'
  },

  // 其他数据源
  {
    label: 'Quandl',
    value: 'quandl',
    register_url: 'https://www.quandl.com/sign-up',
    register_guide: '如果您还没有 Quandl 账号，请先注册并获取 API Key：'
  },
  { label: '本地文件', value: 'local_file' },
  { label: '自定义', value: 'custom' }
]

// 表单验证规则
const rules: FormRules = {
  type: [{ required: true, message: '请选择数据源类型', trigger: 'change' }],
  name: [{ required: true, message: '数据源名称不能为空（自动生成）', trigger: 'blur' }],
  display_name: [{ required: true, message: '请输入显示名称', trigger: 'blur' }],
  timeout: [{ required: true, message: '请输入超时时间', trigger: 'blur' }],
  rate_limit: [{ required: true, message: '请输入速率限制', trigger: 'blur' }],
  priority: [{ required: true, message: '请输入优先级', trigger: 'blur' }],
  // API Key 验证规则
  api_key: [
    {
      validator: (rule: any, value: string, callback: any) => {
        // 如果为空，允许（表示使用环境变量）
        if (!value || value.trim() === '') {
          callback()
          return
        }

        const trimmedValue = value.trim()

        // 如果是截断的密钥（包含 "..."），允许（表示未修改）
        if (trimmedValue.includes('...')) {
          callback()
          return
        }

        // 如果是占位符，允许（表示未修改）
        if (trimmedValue.startsWith('your_') || trimmedValue.startsWith('your-')) {
          callback()
          return
        }

        // 如果是新输入的密钥，必须长度 > 10
        if (trimmedValue.length <= 10) {
          callback(new Error('API Key 长度必须大于 10 个字符'))
          return
        }

        callback()
      },
      trigger: 'blur'
    }
  ]
}

// 自定义参数管理
const addParam = () => {
  const newKey = `param_${Object.keys(formData.value.config_params).length + 1}`
  formData.value.config_params[newKey] = ''
  paramKeys.value.push(newKey)
}

const removeParam = (key: string) => {
  delete formData.value.config_params[key]
  const index = paramKeys.value.indexOf(key)
  if (index > -1) {
    paramKeys.value.splice(index, 1)
  }
}

const updateParamKey = (index: number, newKey: string) => {
  const oldKey = paramKeys.value[index]
  if (oldKey !== newKey && newKey.trim()) {
    const value = formData.value.config_params[oldKey]
    delete formData.value.config_params[oldKey]
    formData.value.config_params[newKey] = value
    paramKeys.value[index] = newKey
  }
}

// 加载市场分类
const loadMarketCategories = async () => {
  try {
    marketCategories.value = await configApi.getMarketCategories()
  } catch (error) {
    console.error('加载市场分类失败:', error)
    ElMessage.error('加载市场分类失败')
  }
}

// 监听配置变化
watch(
  () => props.config,
  (config) => {
    if (config) {
      // 编辑模式：合并默认值和传入的配置
      formData.value = {
        ...defaultFormData,
        ...config,
        market_categories: config.market_categories || []
      }
      // 初始化参数键列表
      paramKeys.value = Object.keys(config.config_params || {})
    } else {
      // 新增模式：使用默认值
      formData.value = { ...defaultFormData }
      paramKeys.value = []
    }
  },
  { immediate: true }
)

// 监听visible变化
watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      loadMarketCategories()
      if (props.config) {
        // 编辑模式
        formData.value = {
          ...defaultFormData,
          ...props.config,
          market_categories: props.config.market_categories || []
        }
        paramKeys.value = Object.keys(props.config.config_params || {})
      } else {
        // 新增模式
        formData.value = { ...defaultFormData }
        paramKeys.value = []
      }
    }
  }
)

// 处理关闭
const handleClose = () => {
  emit('update:visible', false)
}

// 处理提交
const handleSubmit = async () => {
  if (!formRef.value) return

  try {
    await formRef.value.validate()
    loading.value = true

    // 🔥 修复：直接发送截断的 API Key 给后端
    // 后端会判断截断值是否与数据库中的原值匹配
    const payload: any = { ...formData.value }

    // 添加日志，显示发送的 API Key
    if (payload.api_key) {
      console.log('🔍 [保存] 发送 API Key:', payload.api_key, '(长度:', payload.api_key.length, ')')
    } else {
      console.log('🔍 [保存] API Key 为空')
    }

    if (payload.api_secret) {
      console.log('🔍 [保存] 发送 API Secret:', payload.api_secret, '(长度:', payload.api_secret.length, ')')
    } else {
      console.log('🔍 [保存] API Secret 为空')
    }

    // 处理占位符（your_xxx 或 your-xxx）
    if ('api_key' in payload) {
      const apiKey = payload.api_key || ''
      // 如果是占位符，删除该字段（不更新）
      if (apiKey.startsWith('your_') || apiKey.startsWith('your-')) {
        console.log('🔍 [保存] API Key 是占位符，删除字段')
        delete payload.api_key
      }
    }

    if ('api_secret' in payload) {
      const apiSecret = payload.api_secret || ''
      // 如果是占位符，删除该字段（不更新）
      if (apiSecret.startsWith('your_') || apiSecret.startsWith('your-')) {
        console.log('🔍 [保存] API Secret 是占位符，删除字段')
        delete payload.api_secret
      }
    }

    if (isEdit.value) {
      // 更新数据源
      await configApi.updateDataSourceConfig(formData.value.name, payload)
      ElMessage.success('数据源更新成功')
    } else {
      // 创建数据源
      await configApi.addDataSourceConfig(payload)
      ElMessage.success('数据源创建成功')
    }

    emit('success')
    handleClose()
  } catch (error: any) {
    console.error('保存数据源失败:', error)

    // 提取详细的错误信息
    let errorMessage = '保存数据源失败'

    // 尝试从不同的错误结构中提取消息
    if (error?.response?.data?.detail) {
      // FastAPI HTTPException 的错误格式
      errorMessage = error.response.data.detail
    } else if (error?.response?.data?.message) {
      // 自定义错误格式
      errorMessage = error.response.data.message
    } else if (error?.message) {
      // 标准 Error 对象
      errorMessage = error.message
    }

    ElMessage.error(errorMessage)
  } finally {
    loading.value = false
  }
}

// 处理测试连接
const handleTest = async () => {
  if (!formRef.value) return

  try {
    await formRef.value.validate()
    testing.value = true

    // 🔥 修复：直接发送截断的 API Key 给后端
    // 后端会判断截断值是否与数据库中的原值匹配
    const testPayload: any = { ...formData.value }

    // 添加日志，显示发送的 API Key
    if (testPayload.api_key) {
      console.log('🔍 [测试连接] 发送 API Key:', testPayload.api_key, '(长度:', testPayload.api_key.length, ')')
    } else {
      console.log('🔍 [测试连接] API Key 为空')
    }

    if (testPayload.api_secret) {
      console.log('🔍 [测试连接] 发送 API Secret:', testPayload.api_secret, '(长度:', testPayload.api_secret.length, ')')
    } else {
      console.log('🔍 [测试连接] API Secret 为空')
    }

    const result = await configApi.testConfig({
      config_type: 'datasource',
      config_data: testPayload
    })

    if (result.success) {
      ElMessage.success(`连接测试成功: ${result.message}`)
    } else {
      ElMessage.error(`连接测试失败: ${result.message}`)
    }
  } catch (error) {
    console.error('测试连接失败:', error)
    ElMessage.error('测试连接失败')
  } finally {
    testing.value = false
  }
}

// 生命周期
onMounted(() => {
  loadMarketCategories()
})
</script>

<style lang="scss" scoped>
.form-help {
  color: #909399;
  font-size: 12px;
  margin-left: 8px;
}

.form-tip {
  color: #909399;
  font-size: 12px;
  margin-top: 4px;
  line-height: 1.5;
}

.mb-4 {
  margin-bottom: 16px;
}

.register-guide {
  p {
    margin: 0 0 12px 0;
    font-size: 15px;
    line-height: 1.6;
    color: var(--el-text-color-regular);
  }

  :deep(.el-button) {
    font-size: 15px;
    padding: 8px 16px;
  }
}

.config-params {
  .param-item {
    display: flex;
    align-items: center;
    margin-bottom: 8px;
  }
}

.dialog-footer {
  text-align: right;
}
</style>
