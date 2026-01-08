<template>
  <el-dialog
    :model-value="visible"
    :title="isEdit ? '编辑大模型配置' : '添加大模型配置'"
    width="600px"
    @update:model-value="handleVisibleChange"
    @close="handleClose"
  >
    <el-form
      ref="formRef"
      :model="formData"
      :rules="rules"
      label-width="120px"
    >
      <!-- 基础配置 -->
      <el-form-item label="供应商" prop="provider">
        <div style="display: flex; gap: 8px; align-items: flex-start; width: 100%;">
          <el-select
            v-model="formData.provider"
            placeholder="选择供应商"
            @change="handleProviderChange"
            :loading="providersLoading"
            style="flex: 1; min-width: 0;"
          >
            <el-option
              v-for="provider in availableProviders"
              :key="provider.name"
              :label="provider.display_name"
              :value="provider.name"
            />
          </el-select>
          <el-button
            :icon="Refresh"
            :loading="providersLoading"
            @click="() => loadProviders(true)"
            title="刷新供应商列表"
          />
        </div>
        <div class="form-tip">
          如果没有找到需要的供应商，请先在"厂家管理"中添加，然后点击刷新按钮
        </div>
      </el-form-item>

      <el-form-item label="选择模型" v-if="modelOptions.length > 0">
        <el-select
          v-model="selectedModelKey"
          placeholder="从列表中选择模型"
          filterable
          clearable
          @change="handleModelSelect"
        >
          <el-option
            v-for="model in modelOptions"
            :key="model.value"
            :label="model.label"
            :value="model.value"
          >
            <div style="display: flex; flex-direction: column;">
              <span>{{ model.label }}</span>
              <span style="font-size: 12px; color: #909399;">代码: {{ model.value }}</span>
            </div>
          </el-option>
        </el-select>
        <div class="form-tip">
          💡 从列表中选择模型，会自动填充下方的显示名称和模型代码
        </div>
      </el-form-item>

      <el-form-item label="模型显示名称" prop="model_display_name">
        <el-input
          v-model="formData.model_display_name"
          placeholder="输入模型的显示名称，如：Qwen3系列Flash模型 - 快速经济"
        />
        <div class="form-tip">
          💡 用于在界面上显示的友好名称
        </div>
      </el-form-item>

      <el-form-item label="模型代码" prop="model_name">
        <el-input
          v-model="formData.model_name"
          placeholder="输入模型的API调用代码，如：qwen-turbo"
        />
        <div class="form-tip">
          💡 实际调用API时使用的模型标识符
        </div>
      </el-form-item>

      <el-form-item label="API基础URL" prop="api_base">
        <el-input
          v-model="formData.api_base"
          placeholder="可选，自定义API端点（留空使用厂家默认地址）"
        />
        <div class="form-tip">
          💡 API密钥已在厂家配置中设置，此处只需配置模型参数
        </div>
      </el-form-item>

      <!-- 模型参数 -->
      <el-divider content-position="left">模型参数</el-divider>

      <el-form-item label="最大Token数" prop="max_tokens">
        <el-input-number
          v-model="formData.max_tokens"
          :min="100"
          :max="32000"
          :step="100"
        />
      </el-form-item>

      <el-form-item label="温度参数" prop="temperature">
        <el-input-number
          v-model="formData.temperature"
          :min="0"
          :max="2"
          :step="0.1"
          :precision="1"
        />
      </el-form-item>

      <el-form-item label="超时时间" prop="timeout">
        <el-input-number
          v-model="formData.timeout"
          :min="10"
          :max="300"
          :step="10"
        />
        <span class="ml-2 text-gray-500">秒</span>
      </el-form-item>

      <el-form-item label="重试次数" prop="retry_times">
        <el-input-number
          v-model="formData.retry_times"
          :min="0"
          :max="10"
        />
      </el-form-item>

      <!-- 定价配置 -->
      <el-divider content-position="left">定价配置</el-divider>

      <el-form-item label="输入价格" prop="input_price_per_1k">
        <el-input-number
          v-model="formData.input_price_per_1k"
          :min="0"
          :step="0.0001"
          :controls="false"
          placeholder="每1000个token的价格"
        />
        <span class="ml-2 text-gray-500">{{ formData.currency || 'CNY' }}/1K tokens</span>
      </el-form-item>

      <el-form-item label="输出价格" prop="output_price_per_1k">
        <el-input-number
          v-model="formData.output_price_per_1k"
          :min="0"
          :step="0.0001"
          :controls="false"
          placeholder="每1000个token的价格"
        />
        <span class="ml-2 text-gray-500">{{ formData.currency || 'CNY' }}/1K tokens</span>
      </el-form-item>

      <el-form-item label="货币单位" prop="currency">
        <el-select v-model="formData.currency" placeholder="选择货币单位">
          <el-option label="人民币 (CNY)" value="CNY" />
          <el-option label="美元 (USD)" value="USD" />
          <el-option label="欧元 (EUR)" value="EUR" />
        </el-select>
      </el-form-item>

      <!-- 高级设置 -->
      <el-divider content-position="left">高级设置</el-divider>

      <el-form-item label="启用模型">
        <el-switch v-model="formData.enabled" />
      </el-form-item>

      <el-form-item label="启用记忆功能">
        <el-switch v-model="formData.enable_memory" />
      </el-form-item>

      <el-form-item label="启用调试模式">
        <el-switch v-model="formData.enable_debug" />
      </el-form-item>

      <el-form-item label="优先级" prop="priority">
        <el-input-number
          v-model="formData.priority"
          :min="0"
          :max="100"
        />
        <span class="ml-2 text-gray-500">数值越大优先级越高</span>
      </el-form-item>

      <el-form-item label="模型类别" prop="model_category">
        <el-input
          v-model="formData.model_category"
          placeholder="可选，用于OpenRouter等分类"
        />
      </el-form-item>

      <el-form-item label="描述" prop="description">
        <el-input
          v-model="formData.description"
          type="textarea"
          :rows="3"
          placeholder="可选，配置描述"
        />
      </el-form-item>

      <!-- 🆕 模型能力配置 -->
      <el-divider content-position="left">模型能力配置</el-divider>

      <el-form-item label="能力等级" prop="capability_level">
        <el-select v-model="formData.capability_level" placeholder="选择模型能力等级">
          <el-option :value="1" label="1级 - 基础模型（快速分析）">
            <span>1级 - 基础模型</span>
            <span class="text-gray-400 text-xs ml-2">适合快速分析和简单任务</span>
          </el-option>
          <el-option :value="2" label="2级 - 标准模型（日常使用）">
            <span>2级 - 标准模型</span>
            <span class="text-gray-400 text-xs ml-2">适合日常分析和常规任务</span>
          </el-option>
          <el-option :value="3" label="3级 - 高级模型（深度分析）">
            <span>3级 - 高级模型</span>
            <span class="text-gray-400 text-xs ml-2">适合深度分析和复杂推理</span>
          </el-option>
          <el-option :value="4" label="4级 - 专业模型（专业分析）">
            <span>4级 - 专业模型</span>
            <span class="text-gray-400 text-xs ml-2">适合专业级分析和多轮辩论</span>
          </el-option>
          <el-option :value="5" label="5级 - 旗舰模型（全面分析）">
            <span>5级 - 旗舰模型</span>
            <span class="text-gray-400 text-xs ml-2">最强能力，适合全面分析</span>
          </el-option>
        </el-select>
        <div class="form-tip">
          💡 能力等级决定模型可以处理的分析深度上限
        </div>
      </el-form-item>

      <el-form-item label="适用角色" prop="suitable_roles">
        <el-select
          v-model="formData.suitable_roles"
          multiple
          placeholder="选择模型适用的角色"
          style="width: 100%"
        >
          <el-option value="quick_analysis" label="快速分析">
            <span>快速分析</span>
            <span class="text-gray-400 text-xs ml-2">数据收集、工具调用</span>
          </el-option>
          <el-option value="deep_analysis" label="深度分析">
            <span>深度分析</span>
            <span class="text-gray-400 text-xs ml-2">推理、决策</span>
          </el-option>
          <el-option value="both" label="两者都适合">
            <span>两者都适合</span>
            <span class="text-gray-400 text-xs ml-2">全能型模型</span>
          </el-option>
        </el-select>
        <div class="form-tip">
          💡 快速分析侧重数据收集，深度分析侧重推理决策
        </div>
      </el-form-item>

      <el-form-item label="推荐分析深度" prop="recommended_depths">
        <el-select
          v-model="formData.recommended_depths"
          multiple
          placeholder="选择推荐的分析深度级别"
          style="width: 100%"
        >
          <el-option value="快速" label="快速（1级）">
            <span>快速（1级）</span>
            <span class="text-gray-400 text-xs ml-2">任何模型都可以</span>
          </el-option>
          <el-option value="基础" label="基础（2级）">
            <span>基础（2级）</span>
            <span class="text-gray-400 text-xs ml-2">基础级以上</span>
          </el-option>
          <el-option value="标准" label="标准（3级）">
            <span>标准（3级）</span>
            <span class="text-gray-400 text-xs ml-2">标准级以上</span>
          </el-option>
          <el-option value="深度" label="深度（4级）">
            <span>深度（4级）</span>
            <span class="text-gray-400 text-xs ml-2">高级以上，需推理能力</span>
          </el-option>
          <el-option value="全面" label="全面（5级）">
            <span>全面（5级）</span>
            <span class="text-gray-400 text-xs ml-2">专业级以上，强推理能力</span>
          </el-option>
        </el-select>
        <div class="form-tip">
          💡 根据模型能力等级，系统会自动推荐合适的分析深度
        </div>
      </el-form-item>

      <el-form-item label="模型特性" prop="features">
        <el-select
          v-model="formData.features"
          multiple
          placeholder="选择模型支持的特性"
          style="width: 100%"
        >
          <el-option value="tool_calling" label="工具调用">
            <span>工具调用</span>
            <span class="text-gray-400 text-xs ml-2">必需特性</span>
          </el-option>
          <el-option value="long_context" label="长上下文">
            <span>长上下文</span>
            <span class="text-gray-400 text-xs ml-2">支持大量历史信息</span>
          </el-option>
          <el-option value="reasoning" label="强推理能力">
            <span>强推理能力</span>
            <span class="text-gray-400 text-xs ml-2">深度分析必需</span>
          </el-option>
          <el-option value="vision" label="视觉输入">
            <span>视觉输入</span>
            <span class="text-gray-400 text-xs ml-2">支持图表分析</span>
          </el-option>
          <el-option value="fast_response" label="快速响应">
            <span>快速响应</span>
            <span class="text-gray-400 text-xs ml-2">响应速度快</span>
          </el-option>
          <el-option value="cost_effective" label="成本效益高">
            <span>成本效益高</span>
            <span class="text-gray-400 text-xs ml-2">性价比高</span>
          </el-option>
        </el-select>
        <div class="form-tip">
          💡 工具调用是必需特性，推理能力对深度分析很重要
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleClose">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="loading">
          {{ isEdit ? '更新' : '添加' }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { configApi, type LLMProvider, type LLMConfig, validateLLMConfig } from '@/api/config'

// Props
interface Props {
  visible: boolean
  config?: LLMConfig | null
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
const providersLoading = ref(false)
const availableProviders = ref<LLMProvider[]>([])

// Computed
const isEdit = computed(() => !!props.config)

// 表单数据
const defaultFormData = {
  provider: '',
  model_name: '',
  model_display_name: '',  // 新增：模型显示名称
  api_base: '',
  max_tokens: 4000,
  temperature: 0.7,
  timeout: 180,  // 默认超时时间改为180秒
  retry_times: 3,
  enabled: true,
  enable_memory: false,
  enable_debug: false,
  priority: 0,
  model_category: '',
  description: '',
  input_price_per_1k: 0,
  output_price_per_1k: 0,
  currency: 'CNY',
  // 🆕 模型能力配置
  capability_level: 2,  // 默认标准级
  suitable_roles: ['both'],  // 默认两者都适合
  features: ['tool_calling'],  // 默认支持工具调用
  recommended_depths: ['快速', '基础', '标准'],  // 默认推荐1-3级分析
  performance_metrics: {
    speed: 3,
    cost: 3,
    quality: 3
  }
}

const formData = ref({ ...defaultFormData })

// 用于跟踪当前选择的模型（用于下拉列表）
const selectedModelKey = ref<string>('')

// 表单验证规则
const rules: FormRules = {
  provider: [{ required: true, message: '请选择供应商', trigger: 'change' }],
  model_name: [{ required: true, message: '请输入模型名称', trigger: 'blur' }],
  max_tokens: [{ required: true, message: '请输入最大Token数', trigger: 'blur' }],
  temperature: [{ required: true, message: '请输入温度参数', trigger: 'blur' }],
  timeout: [{ required: true, message: '请输入超时时间', trigger: 'blur' }],
  retry_times: [{ required: true, message: '请输入重试次数', trigger: 'blur' }],
  priority: [{ required: true, message: '请输入优先级', trigger: 'blur' }]
}

// 模型选项
const modelOptions = ref<Array<{ label: string; value: string }>>([])

// 从后端获取的模型目录（包含完整信息）
interface ModelInfo {
  name: string
  display_name: string
  description?: string
  context_length?: number
  max_tokens?: number
  input_price_per_1k?: number
  output_price_per_1k?: number
  currency?: string
  is_deprecated?: boolean
  release_date?: string
  capabilities?: string[]
}

const modelCatalog = ref<Record<string, Array<ModelInfo>>>({})

// 加载模型目录
const loadModelCatalog = async () => {
  try {
    const catalog = await configApi.getModelCatalog()
    // 转换为 provider -> models 的映射
    const catalogMap: Record<string, Array<ModelInfo>> = {}
    catalog.forEach(item => {
      catalogMap[item.provider] = item.models
    })
    modelCatalog.value = catalogMap
    console.log('✅ 模型目录加载成功:', Object.keys(catalogMap))
  } catch (error) {
    console.error('❌ 加载模型目录失败:', error)
    ElMessage.warning('加载模型列表失败，将使用默认列表')
    // 失败时使用空目录，允许用户手动输入
    modelCatalog.value = {}
  }
}

// 根据供应商获取模型选项
const getModelOptions = (provider: string) => {
  // 优先从后端获取的目录中查找
  const models = modelCatalog.value[provider]
  if (models && models.length > 0) {
    return models.map(m => ({
      label: m.display_name,
      value: m.name
    }))
  }

  // 如果后端没有数据，返回空数组（允许用户手动输入）
  return []
}

// 根据供应商和模型名称获取模型详细信息
const getModelInfo = (provider: string, modelName: string): ModelInfo | null => {
  const models = modelCatalog.value[provider]
  if (!models) return null

  return models.find(m => m.name === modelName) || null
}

// 处理供应商变更
const handleProviderChange = async (provider: string) => {
  // 先尝试从已加载的目录中获取
  modelOptions.value = getModelOptions(provider)

  // 如果没有找到模型，重新加载模型目录
  if (modelOptions.value.length === 0) {
    console.log(`⚠️ 供应商 ${provider} 没有模型数据，重新加载模型目录...`)
    await loadModelCatalog()
    // 重新获取模型选项
    modelOptions.value = getModelOptions(provider)

    if (modelOptions.value.length > 0) {
      ElMessage.success(`已加载 ${modelOptions.value.length} 个可用模型`)
    } else {
      ElMessage.warning('该供应商暂无可用模型，请在"模型目录管理"中添加')
    }
  }

  formData.value.model_name = ''
  // 清空价格信息
  formData.value.input_price_per_1k = 0
  formData.value.output_price_per_1k = 0
  formData.value.currency = 'CNY'
}

// 处理从下拉列表选择模型
const handleModelSelect = (modelCode: string) => {
  if (!modelCode) {
    // 清空选择
    selectedModelKey.value = ''
    return
  }

  // 查找选中的模型信息
  const selectedModel = modelOptions.value.find(m => m.value === modelCode)
  if (selectedModel) {
    // 自动填充模型代码和显示名称
    formData.value.model_name = selectedModel.value
    formData.value.model_display_name = selectedModel.label

    console.log('📋 选择模型:', {
      code: selectedModel.value,
      display_name: selectedModel.label
    })

    // 自动填充价格信息
    const modelInfo = getModelInfo(formData.value.provider, modelCode)
    if (modelInfo) {
      console.log('📋 自动填充模型信息:', modelInfo)

      if (modelInfo.input_price_per_1k !== undefined) {
        formData.value.input_price_per_1k = modelInfo.input_price_per_1k
      }
      if (modelInfo.output_price_per_1k !== undefined) {
        formData.value.output_price_per_1k = modelInfo.output_price_per_1k
      }
      if (modelInfo.currency) {
        formData.value.currency = modelInfo.currency
      }

      ElMessage.success('已自动填充模型信息和价格')
    } else {
      ElMessage.success('已填充模型名称')
    }
  }
}

// 监听配置变化
watch(
  () => props.config,
  (config) => {
    if (config) {
      // 编辑模式：先使用默认值，再用配置覆盖
      // 注意：对于数字类型的字段，即使是 0 也应该保留
      formData.value = {
        ...defaultFormData,
        ...config,
        // 确保价格字段正确加载，即使是 0 也要保留
        input_price_per_1k: config.input_price_per_1k ?? defaultFormData.input_price_per_1k,
        output_price_per_1k: config.output_price_per_1k ?? defaultFormData.output_price_per_1k,
        currency: config.currency || defaultFormData.currency,
        // 确保显示名称正确加载
        model_display_name: config.model_display_name || '',
        // 🆕 确保模型能力字段正确加载
        capability_level: config.capability_level ?? defaultFormData.capability_level,
        suitable_roles: config.suitable_roles || defaultFormData.suitable_roles,
        features: config.features || defaultFormData.features,
        recommended_depths: config.recommended_depths || defaultFormData.recommended_depths,
        performance_metrics: config.performance_metrics || defaultFormData.performance_metrics
      }
      modelOptions.value = getModelOptions(config.provider)

      // 如果有 model_name，尝试在下拉列表中选中它
      if (config.model_name) {
        selectedModelKey.value = config.model_name
      }

      console.log('📝 编辑模式加载配置:', formData.value)
    } else {
      formData.value = { ...defaultFormData }
      modelOptions.value = getModelOptions('dashscope')
      selectedModelKey.value = ''
    }
  },
  { immediate: true }
)

// 监听visible变化
watch(
  () => props.visible,
  async (visible) => {
    if (visible) {
      // 对话框打开时刷新供应商列表和模型目录，确保显示最新数据
      await Promise.all([
        loadProviders(),
        loadModelCatalog()
      ])

      if (props.config) {
        // 编辑模式：先使用默认值，再用配置覆盖
        formData.value = {
          ...defaultFormData,
          ...props.config,
          // 确保价格字段正确加载，即使是 0 也要保留
          input_price_per_1k: props.config.input_price_per_1k ?? defaultFormData.input_price_per_1k,
          output_price_per_1k: props.config.output_price_per_1k ?? defaultFormData.output_price_per_1k,
          currency: props.config.currency || defaultFormData.currency,
          // 确保显示名称正确加载
          model_display_name: props.config.model_display_name || '',
          // 🆕 确保模型能力字段正确加载
          capability_level: props.config.capability_level ?? defaultFormData.capability_level,
          suitable_roles: props.config.suitable_roles || defaultFormData.suitable_roles,
          features: props.config.features || defaultFormData.features,
          recommended_depths: props.config.recommended_depths || defaultFormData.recommended_depths,
          performance_metrics: props.config.performance_metrics || defaultFormData.performance_metrics
        }
        modelOptions.value = getModelOptions(props.config.provider)

        // 如果有 model_name，尝试在下拉列表中选中它
        if (props.config.model_name) {
          selectedModelKey.value = props.config.model_name
        }

        console.log('📝 对话框打开，加载配置:', formData.value)
      } else {
        // 新增模式：使用默认值
        formData.value = { ...defaultFormData }
        // 如果有供应商，加载其模型列表
        if (formData.value.provider) {
          modelOptions.value = getModelOptions(formData.value.provider)
        } else {
          modelOptions.value = []
        }
        selectedModelKey.value = ''
      }
    }
  }
)

// 处理可见性变化
const handleVisibleChange = (value: boolean) => {
  emit('update:visible', value)
}

// 处理关闭
const handleClose = () => {
  emit('update:visible', false)
  formRef.value?.resetFields()
}

// 处理提交
const handleSubmit = async () => {
  if (!formRef.value) return

  try {
    await formRef.value.validate()

    // 验证配置数据
    const errors = validateLLMConfig(formData.value)
    if (errors.length > 0) {
      ElMessage.error(`配置验证失败: ${errors.join(', ')}`)
      return
    }

    loading.value = true

    // 准备提交数据，移除api_key字段（由后端从厂家配置获取）
    const submitData = { ...formData.value }
    // 使用类型安全的方式移除api_key字段（如果存在的话）
    if ('api_key' in submitData) {
      delete (submitData as any).api_key  // 不发送api_key，让后端从厂家配置获取
    }

    console.log('🚀 提交大模型配置:', submitData)

    // 调用API
    await configApi.updateLLMConfig(submitData)

    ElMessage.success(isEdit.value ? '模型配置更新成功' : '模型配置添加成功')
    emit('success')
    handleClose()
  } catch (error) {
    console.error('❌ 提交大模型配置失败:', error)
    ElMessage.error(isEdit.value ? '模型配置更新失败' : '模型配置添加失败')
  } finally {
    loading.value = false
  }
}

// 加载可用的厂家列表
const loadProviders = async (showSuccessMessage = false) => {
  providersLoading.value = true
  try {
    const providers = await configApi.getLLMProviders()
    // 只显示启用的厂家
    availableProviders.value = providers.filter(p => p.is_active)
    console.log('✅ 加载厂家列表成功:', availableProviders.value.length)

    if (showSuccessMessage) {
      ElMessage.success(`已刷新供应商列表，共 ${availableProviders.value.length} 个启用的供应商`)
    }

    // 如果是新增模式且没有选择供应商，默认选择第一个
    if (!isEdit.value && !formData.value.provider && availableProviders.value.length > 0) {
      formData.value.provider = availableProviders.value[0].name
      await handleProviderChange(formData.value.provider)
    }
  } catch (error) {
    console.error('❌ 加载厂家列表失败:', error)
    ElMessage.error('加载厂家列表失败')
  } finally {
    providersLoading.value = false
  }
}

// 组件挂载时加载厂家数据和模型目录
onMounted(() => {
  loadProviders()
  loadModelCatalog()
})
</script>

<style lang="scss" scoped>
.dialog-footer {
  text-align: right;
}

.ml-2 {
  margin-left: 8px;
}

.text-gray-500 {
  color: #6b7280;
  font-size: 12px;
}

.text-gray-400 {
  color: #9ca3af;
}

.text-xs {
  font-size: 11px;
}

.form-tip {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  margin-top: 4px;
}

// 🆕 模型能力配置样式
:deep(.el-select-dropdown__item) {
  height: auto;
  line-height: 1.5;
  padding: 8px 20px;

  span {
    display: inline-block;
  }
}
</style>
