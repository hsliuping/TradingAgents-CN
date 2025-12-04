<template>
  <el-dialog
    :model-value="visible"
    :title="isEdit ? '编辑厂家信息' : '添加厂家'"
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
      <!-- 预设厂家选择 -->
      <el-form-item v-if="!isEdit" label="快速选择">
        <el-select
          v-model="selectedPreset"
          placeholder="选择预设厂家或手动填写"
          clearable
          @change="handlePresetChange"
        >
          <el-option
            v-for="preset in presetProviders"
            :key="preset.name"
            :label="preset.display_name"
            :value="preset.name"
          />
        </el-select>
      </el-form-item>

      <!-- 🆕 注册引导提示 -->
      <el-alert
        v-if="selectedPreset && currentPresetInfo?.register_url"
        :title="`📝 ${currentPresetInfo.display_name} 注册引导`"
        type="info"
        :closable="false"
        class="mb-4"
      >
        <template #default>
          <div class="register-guide">
            <p>{{ currentPresetInfo.register_guide || '如果您还没有账号，请先注册：' }}</p>
            <el-button
              type="primary"
              size="small"
              link
              @click="openRegisterUrl"
            >
              <el-icon><Link /></el-icon>
              前往注册 {{ currentPresetInfo.display_name }}
            </el-button>
          </div>
        </template>
      </el-alert>

      <el-form-item label="厂家ID" prop="name">
        <el-input 
          v-model="formData.name" 
          placeholder="如: openai, anthropic"
          :disabled="isEdit"
        />
        <div class="form-tip">厂家的唯一标识符，创建后不可修改</div>
      </el-form-item>

      <el-form-item label="显示名称" prop="display_name">
        <el-input 
          v-model="formData.display_name" 
          placeholder="如: OpenAI, Anthropic"
        />
      </el-form-item>

      <el-form-item label="描述" prop="description">
        <el-input 
          v-model="formData.description" 
          type="textarea"
          :rows="3"
          placeholder="厂家简介和特点"
        />
      </el-form-item>

      <el-form-item label="官网" prop="website">
        <el-input 
          v-model="formData.website" 
          placeholder="https://openai.com"
        />
      </el-form-item>

      <el-form-item label="API文档" prop="api_doc_url">
        <el-input 
          v-model="formData.api_doc_url" 
          placeholder="https://platform.openai.com/docs"
        />
      </el-form-item>

      <el-form-item label="默认API地址" prop="default_base_url">
        <el-input
          v-model="formData.default_base_url"
          placeholder="https://api.openai.com/v1"
        />
      </el-form-item>

      <el-alert
        title="🔒 安全提示"
        type="info"
        description="敏感密钥通过环境变量/运维配置注入，出于安全考虑，此处不存储或展示真实密钥。"
        show-icon
        :closable="false"
        class="mb-2"
      />
      <el-form-item label="密钥状态">
        <el-tag :type="(props.provider?.extra_config?.has_api_key ? 'success' : 'danger')" size="small">
          {{ props.provider?.extra_config?.has_api_key ? '已配置' : '未配置' }}
        </el-tag>
        <el-tag v-if="props.provider?.extra_config?.has_api_key" :type="props.provider?.extra_config?.source === 'environment' ? 'warning' : 'success'" size="small" class="ml-2">
          {{ props.provider?.extra_config?.source === 'environment' ? 'ENV' : '已配置' }}
        </el-tag>
      </el-form-item>

      <!-- 🔥 新增：API Key 输入框 -->
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

      <!-- 🔥 新增：API Secret 输入框（某些厂家需要） -->
      <el-form-item v-if="needsApiSecret" label="API Secret" prop="api_secret">
        <el-input
          v-model="formData.api_secret"
          type="password"
          placeholder="输入 API Secret（可选）"
          show-password
          clearable
        />
        <div class="form-tip">
          某些厂家（如百度千帆）需要额外的 Secret Key
        </div>
      </el-form-item>

      <el-form-item label="支持功能" prop="supported_features">
        <el-checkbox-group v-model="formData.supported_features">
          <el-checkbox label="chat">对话</el-checkbox>
          <el-checkbox label="completion">文本补全</el-checkbox>
          <el-checkbox label="embedding">向量化</el-checkbox>
          <el-checkbox label="image">图像生成</el-checkbox>
          <el-checkbox label="vision">图像理解</el-checkbox>
          <el-checkbox label="function_calling">函数调用</el-checkbox>
          <el-checkbox label="streaming">流式输出</el-checkbox>
        </el-checkbox-group>
      </el-form-item>

      <el-form-item label="状态">
        <el-switch 
          v-model="formData.is_active"
          active-text="启用"
          inactive-text="禁用"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleClose">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">
          {{ isEdit ? '更新' : '添加' }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Link } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { configApi, type LLMProvider } from '@/api/config'

// 表单数据类型（扩展 LLMProvider，添加临时字段）
interface ProviderFormData extends Partial<LLMProvider> {
  api_key?: string
  api_secret?: string
}

interface Props {
  visible: boolean
  provider?: Partial<LLMProvider>
}

const props = withDefaults(defineProps<Props>(), {
  provider: () => ({})
})

const emit = defineEmits<{
  'update:visible': [value: boolean]
  'success': []
}>()

// 表单引用
const formRef = ref<FormInstance>()
const submitting = ref(false)
const selectedPreset = ref('')

// 是否为编辑模式
const isEdit = computed(() => !!props.provider?.id)

// 是否需要API Secret（某些厂家需要）
const needsApiSecret = computed(() => {
  const providersNeedSecret = ['baidu', 'dashscope', 'qianfan']
  return providersNeedSecret.includes(formData.value.name || '')
})

// 当前选中的预设厂家信息
const currentPresetInfo = computed(() => {
  if (!selectedPreset.value) return null
  return presetProviders.find(p => p.name === selectedPreset.value)
})

// 打开注册链接
const openRegisterUrl = () => {
  if (currentPresetInfo.value?.register_url) {
    window.open(currentPresetInfo.value.register_url, '_blank')
  }
}

// 预设厂家数据
const presetProviders = [
  {
    name: 'dashscope',
    display_name: '阿里云百炼',
    description: '阿里云百炼大模型服务平台，提供通义千问等模型',
    website: 'https://bailian.console.aliyun.com',
    api_doc_url: 'https://help.aliyun.com/zh/dashscope/',
    default_base_url: 'https://dashscope.aliyuncs.com/api/v1',
    supported_features: ['chat', 'completion', 'embedding', 'function_calling', 'streaming'],
    register_url: 'https://account.aliyun.com/register/qr_register.htm',
    register_guide: '如果您还没有阿里云账号，请先注册并开通百炼服务：'
  },
  {
    name: '302ai',
    display_name: '302.AI',
    description: '302.AI是企业级AI聚合平台，提供多种主流大模型的统一接口',
    website: 'https://302.ai',
    api_doc_url: 'https://doc.302.ai',
    default_base_url: 'https://api.302.ai/v1',
    supported_features: ['chat', 'completion', 'embedding', 'image', 'vision', 'function_calling', 'streaming'],
    register_url: 'https://share.302.ai/DUjftK',
    register_guide: '如果您还没有 302.AI 账号，请先注册并获取 API Key：'
  },
    {
    name: 'deepseek',
    display_name: 'DeepSeek',
    description: 'DeepSeek提供高性能的AI推理服务',
    website: 'https://www.deepseek.com',
    api_doc_url: 'https://platform.deepseek.com/api-docs',
    default_base_url: 'https://api.deepseek.com',
    supported_features: ['chat', 'completion', 'function_calling', 'streaming'],
    register_url: 'https://platform.deepseek.com/sign_up',
    register_guide: '如果您还没有 DeepSeek 账号，请先注册并获取 API Key：'
  },
  {
    name: 'openai',
    display_name: 'OpenAI',
    description: 'OpenAI是人工智能领域的领先公司，提供GPT系列模型',
    website: 'https://openai.com',
    api_doc_url: 'https://platform.openai.com/docs',
    default_base_url: 'https://api.openai.com/v1',
    supported_features: ['chat', 'completion', 'embedding', 'image', 'vision', 'function_calling', 'streaming'],
    register_url: 'https://platform.openai.com/signup',
    register_guide: '如果您还没有 OpenAI 账号，请先注册并获取 API Key：'
  },
  {
    name: 'anthropic',
    display_name: 'Anthropic',
    description: 'Anthropic专注于AI安全研究，提供Claude系列模型',
    website: 'https://anthropic.com',
    api_doc_url: 'https://docs.anthropic.com',
    default_base_url: 'https://api.anthropic.com',
    supported_features: ['chat', 'completion', 'function_calling', 'streaming'],
    register_url: 'https://console.anthropic.com/signup',
    register_guide: '如果您还没有 Anthropic 账号，请先注册并获取 API Key：'
  },
  {
    name: 'google',
    display_name: 'Google AI',
    description: 'Google的人工智能平台，提供Gemini系列模型',
    website: 'https://ai.google.dev',
    api_doc_url: 'https://ai.google.dev/docs',
    default_base_url: 'https://generativelanguage.googleapis.com/v1',
    supported_features: ['chat', 'completion', 'embedding', 'vision', 'function_calling', 'streaming'],
    register_url: 'https://makersuite.google.com/app/apikey',
    register_guide: '如果您还没有 Google AI 账号，请先登录 Google 账号并获取 API Key：'
  },
  {
    name: 'azure',
    display_name: 'Azure OpenAI',
    description: 'Microsoft Azure平台上的OpenAI服务',
    website: 'https://azure.microsoft.com/en-us/products/ai-services/openai-service',
    api_doc_url: 'https://learn.microsoft.com/en-us/azure/ai-services/openai/',
    default_base_url: 'https://your-resource.openai.azure.com',
    supported_features: ['chat', 'completion', 'embedding', 'function_calling', 'streaming'],
    register_url: 'https://azure.microsoft.com/en-us/free/',
    register_guide: '如果您还没有 Azure 账号，请先注册并申请 Azure OpenAI 服务：'
  },
  {
    name: 'zhipu',
    display_name: '智谱AI',
    description: '智谱AI提供GLM系列中文大模型',
    website: 'https://zhipuai.cn',
    api_doc_url: 'https://open.bigmodel.cn/doc',
    default_base_url: 'https://open.bigmodel.cn/api/paas/v4',
    supported_features: ['chat', 'completion', 'embedding', 'function_calling', 'streaming'],
    register_url: 'https://open.bigmodel.cn/login',
    register_guide: '如果您还没有智谱AI账号，请先注册并获取 API Key：'
  },
  {
    name: 'baidu',
    display_name: '百度智能云',
    description: '百度提供的文心一言等AI服务',
    website: 'https://cloud.baidu.com',
    api_doc_url: 'https://cloud.baidu.com/doc/WENXINWORKSHOP/index.html',
    default_base_url: 'https://aip.baidubce.com',
    supported_features: ['chat', 'completion', 'embedding', 'streaming'],
    register_url: 'https://login.bce.baidu.com/new-reg',
    register_guide: '如果您还没有百度智能云账号，请先注册并开通文心一言服务：'
  }
]

// 表单数据
const formData = ref<ProviderFormData>({
  name: '',
  display_name: '',
  description: '',
  website: '',
  api_doc_url: '',
  default_base_url: '',
  api_key: '',
  api_secret: '',
  supported_features: [],
  is_active: true
})

// 表单验证规则
const rules: FormRules = {
  name: [
    { required: true, message: '请输入厂家ID', trigger: 'blur' },
    { pattern: /^[a-z0-9_-]+$/, message: '只能包含小写字母、数字、下划线和连字符', trigger: 'blur' }
  ],
  display_name: [
    { required: true, message: '请输入显示名称', trigger: 'blur' }
  ],
  supported_features: [
    { type: 'array', min: 1, message: '请至少选择一个支持的功能', trigger: 'change' }
  ]
}

// 重置表单
const resetForm = () => {
  formData.value = {
    name: '',
    display_name: '',
    description: '',
    website: '',
    api_doc_url: '',
    default_base_url: '',
    api_key: '',
    api_secret: '',
    supported_features: [],
    is_active: true
  }
  selectedPreset.value = ''
}

// 监听props变化，更新表单数据
watch(() => props.provider, (newProvider) => {
  if (newProvider && Object.keys(newProvider).length > 0) {
    formData.value = { ...newProvider }
  } else {
    resetForm()
  }
}, { immediate: true, deep: true })

// 处理预设选择
const handlePresetChange = (presetName: string) => {
  if (!presetName) return

  const preset = presetProviders.find(p => p.name === presetName)
  if (preset) {
    formData.value = {
      ...preset,
      is_active: true
    }
  }
}

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
  try {
    await formRef.value?.validate()
    submitting.value = true

    // 🔥 修改：处理 API Key 的提交逻辑
    const payload: any = { ...formData.value }

    // 处理 API Key
    if ('api_key' in payload) {
      const apiKey = payload.api_key || ''

      // 如果是截断的密钥（包含 "..."），表示用户没有修改，删除该字段（不更新）
      if (apiKey.includes('...')) {
        delete payload.api_key
      }
      // 如果是占位符，删除该字段（不更新）
      else if (apiKey.startsWith('your_') || apiKey.startsWith('your-')) {
        delete payload.api_key
      }
      // 如果是空字符串，保留（表示用户想清空密钥）
      // 如果是有效的完整密钥，保留（表示用户想更新密钥）
    }

    // 处理 API Secret（同样的逻辑）
    if ('api_secret' in payload) {
      const apiSecret = payload.api_secret || ''

      if (apiSecret.includes('...') || apiSecret.startsWith('your_') || apiSecret.startsWith('your-')) {
        delete payload.api_secret
      }
    }

    if (isEdit.value) {
      await configApi.updateLLMProvider(formData.value.id!, payload)
      ElMessage.success('厂家信息更新成功')
    } else {
      await configApi.addLLMProvider(payload)
      ElMessage.success('厂家添加成功')
    }

    emit('success')
    handleClose()
  } catch (error) {
    console.error('提交失败:', error)
    ElMessage.error(isEdit.value ? '更新失败' : '添加失败')
  } finally {
    submitting.value = false
  }
}
</script>

<style lang="scss" scoped>
.form-tip {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  margin-top: 4px;
}

.dialog-footer {
  text-align: right;
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
</style>
