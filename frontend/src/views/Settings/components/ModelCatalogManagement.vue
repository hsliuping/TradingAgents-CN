<template>
  <div class="model-catalog-management">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>模型目录管理</span>
          <el-button type="primary" @click="handleAdd">
            <el-icon><Plus /></el-icon>
            添加厂家模型目录
          </el-button>
        </div>
      </template>

      <el-alert
        title="说明"
        type="info"
        :closable="false"
        style="margin-bottom: 20px"
      >
        模型目录用于在添加大模型配置时提供可选的模型列表。您可以在这里管理各个厂家支持的模型。
      </el-alert>

      <el-table
        :data="catalogs"
        v-loading="loading"
        border
        style="width: 100%"
      >
        <el-table-column prop="provider" label="厂家标识" width="150" />
        <el-table-column prop="provider_name" label="厂家名称" width="150" />
        <el-table-column label="模型数量" width="120">
          <template #default="{ row }">
            <el-tag>{{ row.models.length }} 个模型</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="模型列表">
          <template #default="{ row }">
            <el-tag
              v-for="model in row.models.slice(0, 3)"
              :key="model.name"
              size="small"
              style="margin-right: 5px"
            >
              {{ model.display_name }}
            </el-tag>
            <span v-if="row.models.length > 3">
              ... 还有 {{ row.models.length - 3 }} 个
            </span>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.updated_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button
              type="primary"
              size="small"
              @click="handleEdit(row)"
            >
              编辑
            </el-button>
            <el-button
              type="danger"
              size="small"
              @click="handleDelete(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑模型目录' : '添加模型目录'"
      width="1200px"
    >
      <el-form
        ref="formRef"
        :model="formData"
        :rules="rules"
        label-width="120px"
      >
        <el-form-item label="厂家标识" prop="provider">
          <div style="display: flex; gap: 8px; align-items: flex-start;">
            <el-select
              v-model="formData.provider"
              placeholder="请选择厂家"
              :disabled="isEdit"
              filterable
              @change="handleProviderChange"
              style="flex: 1"
            >
              <el-option
                v-for="provider in availableProviders"
                :key="provider.name"
                :label="`${provider.display_name} (${provider.name})`"
                :value="provider.name"
              />
            </el-select>
            <el-button
              :icon="Refresh"
              :loading="providersLoading"
              @click="() => loadProviders(true)"
              title="刷新厂家列表"
            />
          </div>
          <div class="form-tip">
            选择已配置的厂家，如果没有找到需要的厂家，请先在"厂家管理"中添加，然后点击刷新按钮
          </div>
        </el-form-item>
        <el-form-item label="厂家名称" prop="provider_name">
          <el-input
            v-model="formData.provider_name"
            placeholder="如: 通义千问"
            :disabled="true"
          />
          <div class="form-tip">
            自动从选择的厂家中获取
          </div>
        </el-form-item>
        <el-form-item label="模型列表">
          <div style="margin-bottom: 10px; display: flex; gap: 10px; flex-wrap: wrap;">
            <el-button
              type="primary"
              size="small"
              @click="handleAddModel"
            >
              <el-icon><Plus /></el-icon>
              手动添加模型
            </el-button>

            <!-- 聚合平台特殊功能 -->
            <template v-if="isAggregatorProvider">
              <el-button
                type="success"
                size="small"
                @click="handleFetchModelsFromAPI"
                :loading="fetchingModels"
              >
                <el-icon><Refresh /></el-icon>
                从 API 获取模型列表
              </el-button>
              <el-button
                type="warning"
                size="small"
                @click="handleUsePresetModels"
              >
                <el-icon><Document /></el-icon>
                使用预设模板
              </el-button>
            </template>
          </div>

          <el-alert
            v-if="isAggregatorProvider"
            title="💡 提示"
            type="info"
            :closable="false"
            style="margin-bottom: 10px"
          >
            聚合平台支持多个厂家的模型。您可以：
            <ul style="margin: 5px 0 0 20px; padding: 0;">
              <li>点击"从 API 获取模型列表"自动获取（需要配置 API Key）</li>
              <li>点击"使用预设模板"快速导入常用模型</li>
              <li>点击"手动添加模型"逐个添加</li>
            </ul>
          </el-alert>

          <el-table :data="formData.models" border max-height="400">
            <el-table-column label="模型名称" width="200">
              <template #default="{ row }">
                <el-input
                  v-model="row.name"
                  placeholder="如: qwen-turbo"
                  size="small"
                />
              </template>
            </el-table-column>
            <el-table-column label="显示名称" width="280">
              <template #default="{ row }">
                <el-input
                  v-model="row.display_name"
                  placeholder="如: Qwen Turbo - 快速经济"
                  size="small"
                />
              </template>
            </el-table-column>
            <el-table-column label="输入价格/1K" width="180">
              <template #default="{ row }">
                <div style="display: flex; align-items: center; gap: 4px;">
                  <el-input-number
                    v-model="row.input_price_per_1k"
                    :min="0"
                    :step="0.0001"
                    size="small"
                    :controls="false"
                    style="width: 110px;"
                  />
                  <span style="color: #909399; font-size: 12px; white-space: nowrap;">{{ row.currency || 'CNY' }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="输出价格/1K" width="180">
              <template #default="{ row }">
                <div style="display: flex; align-items: center; gap: 4px;">
                  <el-input-number
                    v-model="row.output_price_per_1k"
                    :min="0"
                    :step="0.0001"
                    size="small"
                    :controls="false"
                    style="width: 110px;"
                  />
                  <span style="color: #909399; font-size: 12px; white-space: nowrap;">{{ row.currency || 'CNY' }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="上下文长度" width="150">
              <template #default="{ row }">
                <el-input
                  v-model.number="row.context_length"
                  placeholder="1000000"
                  size="small"
                  type="number"
                />
              </template>
            </el-table-column>
            <el-table-column label="货币单位" width="120">
              <template #default="{ row }">
                <el-select
                  v-model="row.currency"
                  size="small"
                  placeholder="选择货币"
                >
                  <el-option label="CNY" value="CNY" />
                  <el-option label="USD" value="USD" />
                  <el-option label="EUR" value="EUR" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ $index }">
                <el-button
                  type="danger"
                  size="small"
                  @click="handleRemoveModel($index)"
                >
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">
          保存
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="fetchDialogVisible"
      title="从 API 获取模型列表"
      width="1200px"
      append-to-body
    >
      <el-form :model="fetchForm" label-width="110px">
        <el-form-item
          v-if="fetchingProvider?.name === 'aihubmix'"
          label="模型厂家"
        >
          <el-select
            v-model="fetchForm.provider_names"
            multiple
            collapse-tags
            collapse-tags-tooltip
            filterable
            placeholder="请选择要保留的模型厂家"
            style="width: 100%"
          >
            <el-option
              v-for="option in aihubmixProviderOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
          <div class="form-tip">可多选，例如同时保留 `OpenAI`、`DeepSeek`、`Qwen`。</div>
        </el-form-item>

        <el-form-item label="模型关键词">
          <el-input
            v-model="fetchForm.model_keyword"
            placeholder="可选，按模型名称模糊筛选"
            clearable
          />
        </el-form-item>

        <el-form-item label="返回数量">
          <el-input-number
            v-model="fetchForm.limit"
            :min="1"
            :max="200"
          />
        </el-form-item>

        <el-form-item label="附加筛选">
          <div style="display: flex; gap: 16px; flex-wrap: wrap;">
            <el-checkbox v-model="fetchForm.tools_only">仅工具调用</el-checkbox>
            <el-checkbox v-model="fetchForm.exclude_preview">排除预览/测试模型</el-checkbox>
            <el-checkbox v-model="fetchForm.recommended_only">仅推荐主流模型</el-checkbox>
          </div>
        </el-form-item>
      </el-form>

      <div style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
        <div class="form-tip">
          已返回 {{ fetchedModels.length }} 个模型，已选 {{ selectedFetchedModels.length }} 个
        </div>
        <div style="display: flex; gap: 8px;">
          <el-button size="small" @click="handleSelectAllFetchedModels" :disabled="fetchedModels.length === 0">全选</el-button>
          <el-button size="small" @click="handleClearFetchedModelsSelection" :disabled="selectedFetchedModels.length === 0">清空选择</el-button>
          <el-button type="primary" size="small" @click="handleRunFetchModels" :loading="fetchingModels">拉取模型</el-button>
        </div>
      </div>

      <el-table
        ref="fetchedModelsTableRef"
        :data="fetchedModels"
        border
        max-height="420"
        @selection-change="handleFetchedModelsSelectionChange"
      >
        <el-table-column type="selection" width="48" />
        <el-table-column prop="name" label="模型名称" min-width="220" />
        <el-table-column prop="provider_vendor" label="模型厂家" width="120">
          <template #default="{ row }">
            <el-tag size="small">{{ providerVendorLabelMap[row.provider_vendor] || row.provider_vendor || '其他' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="context_length" label="上下文" width="120" />
        <el-table-column prop="input_price_per_1k" label="输入/1K" width="110" />
        <el-table-column prop="output_price_per_1k" label="输出/1K" width="110" />
        <el-table-column label="能力" min-width="180">
          <template #default="{ row }">
            <el-tag
              v-for="cap in (row.capabilities || []).slice(0, 3)"
              :key="cap"
              size="small"
              style="margin-right: 4px;"
            >
              {{ cap }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>

      <template #footer>
        <el-button @click="fetchDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          @click="handleImportFetchedModels"
          :disabled="selectedFetchedModels.length === 0"
        >
          导入选中模型
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Refresh, Document } from '@element-plus/icons-vue'
import { configApi, type FetchProviderModelsRequest, type LLMProvider } from '@/api/config'

// 数据
const loading = ref(false)
const catalogs = ref<any[]>([])
const dialogVisible = ref(false)
const fetchDialogVisible = ref(false)
const isEdit = ref(false)
const saving = ref(false)
const formRef = ref<FormInstance>()
const availableProviders = ref<LLMProvider[]>([])
const providersLoading = ref(false)
const fetchingModels = ref(false)
const fetchingProvider = ref<LLMProvider | null>(null)
const fetchedModels = ref<any[]>([])
const selectedFetchedModels = ref<any[]>([])
const fetchedModelsTableRef = ref()

// 聚合平台列表
const aggregatorProviders = ['302ai', 'oneapi', 'newapi', 'openrouter', 'aihubmix', 'custom_aggregator']

// 计算属性：判断当前选择的是否为聚合平台
const isAggregatorProvider = computed(() => {
  return aggregatorProviders.includes(formData.value.provider)
})

interface ModelInfo {
  name: string
  display_name: string
  input_price_per_1k?: number | null
  output_price_per_1k?: number | null
  context_length?: number | null
  max_tokens?: number | null
  currency?: string
  description?: string
  is_deprecated?: boolean
  release_date?: string
  capabilities?: string[]
}

interface FetchDialogForm extends FetchProviderModelsRequest {
  provider_names: string[]
}

const formData = ref({
  provider: '',
  provider_name: '',
  models: [] as ModelInfo[]
})

const fetchForm = ref<FetchDialogForm>({
  type: 'llm',
  modalities: 'text',
  features: [],
  provider_names: [],
  model_keyword: '',
  sort_by: 'order',
  sort_order: 'asc',
  limit: 40,
  recommended_only: false,
  tools_only: false,
  exclude_preview: false
})

const aihubmixProviderOptions = [
  { label: 'OpenAI', value: 'openai' },
  { label: 'Anthropic', value: 'anthropic' },
  { label: 'Google', value: 'google' },
  { label: 'DeepSeek', value: 'deepseek' },
  { label: 'Qwen', value: 'qwen' },
  { label: 'GLM', value: 'glm' },
  { label: 'Kimi', value: 'kimi' },
  { label: '豆包', value: 'doubao' },
  { label: 'MiniMax', value: 'minimax' },
  { label: 'Mistral', value: 'mistral' },
  { label: 'Meta', value: 'meta' },
  { label: 'Jina', value: 'jina' }
]

const providerVendorLabelMap: Record<string, string> = Object.fromEntries(
  aihubmixProviderOptions.map(option => [option.value, option.label])
)

const rules: FormRules = {
  provider: [{ required: true, message: '请输入厂家标识', trigger: 'blur' }],
  provider_name: [{ required: true, message: '请输入厂家名称', trigger: 'blur' }]
}

// 方法
const loadCatalogs = async () => {
  loading.value = true
  try {
    const response = await configApi.getModelCatalog()
    catalogs.value = sortCatalogsByNewest(response)
  } catch (error) {
    console.error('加载模型目录失败:', error)
    ElMessage.error('加载模型目录失败')
  } finally {
    loading.value = false
  }
}

const sortCatalogsByNewest = (catalogList: any[]) => {
  const getTimestamp = (catalog: any) => {
    const timeValue = catalog.created_at || catalog.updated_at
    const timestamp = timeValue ? new Date(timeValue).getTime() : 0
    return Number.isNaN(timestamp) ? 0 : timestamp
  }

  return [...catalogList].sort((a, b) => getTimestamp(b) - getTimestamp(a))
}

// 加载可用的厂家列表
const loadProviders = async (showSuccessMessage = false) => {
  providersLoading.value = true
  try {
    const providers = await configApi.getLLMProviders()
    availableProviders.value = sortProvidersByNewest(providers)
    console.log('✅ 加载厂家列表成功:', availableProviders.value.length)
    if (showSuccessMessage) {
      ElMessage.success(`已刷新厂家列表，共 ${providers.length} 个厂家`)
    }
  } catch (error) {
    console.error('❌ 加载厂家列表失败:', error)
    ElMessage.error('加载厂家列表失败')
  } finally {
    providersLoading.value = false
  }
}

const sortProvidersByNewest = (providers: LLMProvider[]) => {
  const getTimestamp = (provider: LLMProvider) => {
    const timeValue = provider.created_at || provider.updated_at
    const timestamp = timeValue ? new Date(timeValue).getTime() : 0
    return Number.isNaN(timestamp) ? 0 : timestamp
  }

  return [...providers].sort((a, b) => getTimestamp(b) - getTimestamp(a))
}

// 处理厂家选择
const handleProviderChange = (providerName: string) => {
  const provider = availableProviders.value.find(p => p.name === providerName)
  if (provider) {
    formData.value.provider_name = provider.display_name
  }
}

const handleAdd = async () => {
  isEdit.value = false
  formData.value = {
    provider: '',
    provider_name: '',
    models: []
  }
  // 打开对话框前刷新厂家列表，确保显示最新添加的厂家
  await loadProviders()
  dialogVisible.value = true
}

const handleEdit = async (row: any) => {
  isEdit.value = true
  formData.value = {
    provider: row.provider,
    provider_name: row.provider_name,
    models: JSON.parse(JSON.stringify(row.models))
  }
  // 打开对话框前刷新厂家列表
  await loadProviders()
  dialogVisible.value = true
}

const handleDelete = async (row: any) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除厂家 ${row.provider_name} 的模型目录吗？`,
      '确认删除',
      {
        type: 'warning'
      }
    )
    
    await configApi.deleteModelCatalog(row.provider)
    ElMessage.success('删除成功')
    await loadCatalogs()
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('删除失败:', error)
      ElMessage.error('删除失败')
    }
  }
}

const handleAddModel = () => {
  formData.value.models.push({
    name: '',
    display_name: '',
    input_price_per_1k: null,
    output_price_per_1k: null,
    context_length: null,
    currency: 'CNY'
  })
}

const handleRemoveModel = (index: number) => {
  formData.value.models.splice(index, 1)
}

// 从 API 获取模型列表
const handleFetchModelsFromAPI = async () => {
  try {
    // 检查是否选择了厂家
    if (!formData.value.provider) {
      ElMessage.warning('请先选择厂家')
      return
    }

    // 获取厂家信息
    const provider = availableProviders.value.find(p => p.name === formData.value.provider)
    if (!provider) {
      ElMessage.error('未找到厂家信息')
      return
    }

    // 检查是否配置了 base_url
    if (!provider.default_base_url) {
      ElMessage.warning('该厂家未配置 API 基础地址')
      return
    }

    fetchingProvider.value = provider
    fetchForm.value = buildFetchModelFilters(provider.name)
    fetchedModels.value = []
    selectedFetchedModels.value = []
    fetchDialogVisible.value = true
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('获取模型列表失败:', error)
      const errorMsg = error.response?.data?.detail || error.message || '获取模型列表失败'
      ElMessage.error(errorMsg)
    }
  } finally {
    fetchingModels.value = false
  }
}

const buildFetchModelFilters = (providerName: string): FetchDialogForm => {
  if (providerName === 'aihubmix') {
    return {
      type: 'llm',
      modalities: 'text',
      features: [],
      provider_names: ['openai', 'deepseek'],
      sort_by: 'order',
      sort_order: 'asc',
      limit: 40,
      recommended_only: false,
      tools_only: false,
      exclude_preview: false
    }
  }

  return {
    type: 'llm',
    modalities: 'text',
    features: [],
    provider_names: [],
    model_keyword: '',
    sort_by: 'order',
    sort_order: 'asc',
    limit: 40,
    recommended_only: false,
    tools_only: false,
    exclude_preview: false
  }
}

const handleRunFetchModels = async () => {
  if (!fetchingProvider.value) return

  try {
    fetchingModels.value = true
    const requestPayload = {
      ...fetchForm.value,
      features: fetchForm.value.tools_only ? ['tools', 'function_calling'] : fetchForm.value.features
    }
    console.log('🔍 [fetch-models] provider=', fetchingProvider.value)
    console.log('🔍 [fetch-models] payload=', requestPayload)
    const response = await configApi.fetchProviderModels(fetchingProvider.value.id, requestPayload)
    console.log('📦 [fetch-models] response=', response)

    if (response.success && response.models && response.models.length > 0) {
      const mappedModels = response.models.map((model: any) => ({
        name: model.id || model.name,
        display_name: model.name || model.id,
        provider_vendor: normalizeFetchedModelVendor(model.provider_vendor || inferProviderVendor(model.id || model.name)),
        input_price_per_1k: model.input_price_per_1k || null,
        output_price_per_1k: model.output_price_per_1k || null,
        context_length: model.context_length || null,
        max_tokens: model.max_tokens || null,
        description: model.description || '',
        capabilities: model.capabilities || [],
        currency: model.currency || 'USD'
      }))

      const selectedProviders = new Set((fetchForm.value.provider_names || []).map(item => normalizeFetchedModelVendor(item)))
      fetchedModels.value = selectedProviders.size > 0
        ? mappedModels.filter(model => selectedProviders.has(normalizeFetchedModelVendor(model.provider_vendor)))
        : mappedModels

      selectedFetchedModels.value = []
      if (fetchedModels.value.length === 0) {
        ElMessage.warning('已拉取到模型，但按当前厂家筛选后没有匹配结果，请调整筛选条件')
        return
      }
      ElMessage.success(`成功拉取 ${fetchedModels.value.length} 个模型，请勾选后导入`)
    } else {
      fetchedModels.value = []
      selectedFetchedModels.value = []
      ElMessage.error(response.message || '获取模型列表失败或列表为空')
    }
  } catch (error: any) {
    console.error('获取模型列表失败:', error)
    const errorMsg = error.response?.data?.detail || error.message || '获取模型列表失败'
    ElMessage.error(errorMsg)
  } finally {
    fetchingModels.value = false
  }
}

const handleFetchedModelsSelectionChange = (rows: any[]) => {
  selectedFetchedModels.value = rows
}

const handleSelectAllFetchedModels = () => {
  fetchedModelsTableRef.value?.toggleAllSelection?.()
}

const handleClearFetchedModelsSelection = () => {
  fetchedModelsTableRef.value?.clearSelection?.()
  selectedFetchedModels.value = []
}

const handleImportFetchedModels = async () => {
  if (selectedFetchedModels.value.length === 0) {
    ElMessage.warning('请至少勾选一个模型')
    return
  }

  const importedModels = selectedFetchedModels.value.map((model: any) => ({
    name: model.name,
    display_name: model.display_name,
    input_price_per_1k: model.input_price_per_1k,
    output_price_per_1k: model.output_price_per_1k,
    context_length: model.context_length,
    max_tokens: model.max_tokens,
    description: model.description,
    capabilities: model.capabilities,
    currency: model.currency || 'USD'
  }))

  const mergedModels = [...formData.value.models]
  const indexByName = new Map(
    mergedModels.map((model, index) => [String(model.name || '').trim().toLowerCase(), index])
  )

  for (const importedModel of importedModels) {
    const modelKey = String(importedModel.name || '').trim().toLowerCase()
    if (!modelKey) continue

    const existingIndex = indexByName.get(modelKey)
    if (existingIndex !== undefined) {
      mergedModels[existingIndex] = {
        ...mergedModels[existingIndex],
        ...importedModel
      }
    } else {
      indexByName.set(modelKey, mergedModels.length)
      mergedModels.push(importedModel)
    }
  }

  formData.value.models = mergedModels

  fetchDialogVisible.value = false
  ElMessage.success(`已导入 ${importedModels.length} 个选中模型，当前共 ${formData.value.models.length} 个模型`)
}

const normalizeFetchedModelVendor = (vendor: string) => {
  return String(vendor || '').trim().toLowerCase()
}

const inferProviderVendor = (modelName: string) => {
  const name = String(modelName || '').toLowerCase()
  if (name.startsWith('gpt-') || name.startsWith('o1') || name.startsWith('o3') || name.startsWith('o4') || name.startsWith('chatgpt-')) return 'openai'
  if (name.startsWith('claude-')) return 'anthropic'
  if (name.startsWith('gemini')) return 'google'
  if (name.startsWith('deepseek')) return 'deepseek'
  if (name.startsWith('qwen')) return 'qwen'
  if (name.startsWith('glm') || name.startsWith('chatglm') || name.startsWith('zhipu')) return 'glm'
  if (name.startsWith('kimi') || name.startsWith('moonshot')) return 'kimi'
  if (name.startsWith('doubao')) return 'doubao'
  if (name.startsWith('minimax') || name.startsWith('mimo-') || name.startsWith('abab')) return 'minimax'
  if (name.startsWith('mistral')) return 'mistral'
  if (name.startsWith('meta/') || name.startsWith('meta-') || name.startsWith('llama-')) return 'meta'
  if (name.startsWith('jina')) return 'jina'
  return 'other'
}

// 使用预设模板
const handleUsePresetModels = async () => {
  try {
    if (!formData.value.provider) {
      ElMessage.warning('请先选择厂家')
      return
    }

    await ElMessageBox.confirm(
      '此操作将使用预设模板并覆盖当前的模型列表，是否继续？',
      '确认操作',
      { type: 'warning' }
    )

    // 根据不同的聚合平台提供不同的预设模板
    const presetModels = getPresetModels(formData.value.provider)

    if (presetModels.length > 0) {
      formData.value.models = presetModels
      ElMessage.success(`已导入 ${presetModels.length} 个预设模型`)
    } else {
      ElMessage.warning('该厂家暂无预设模板')
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('导入预设模板失败:', error)
    }
  }
}

// 获取预设模型列表
const getPresetModels = (providerName: string): ModelInfo[] => {
  const presets: Record<string, ModelInfo[]> = {
    '302ai': [
      // OpenAI 模型
      { name: 'gpt-4o', display_name: 'GPT-4o', input_price_per_1k: 0.005, output_price_per_1k: 0.015, context_length: 128000, currency: 'USD' },
      { name: 'gpt-4o-mini', display_name: 'GPT-4o Mini', input_price_per_1k: 0.00015, output_price_per_1k: 0.0006, context_length: 128000, currency: 'USD' },
      { name: 'gpt-4-turbo', display_name: 'GPT-4 Turbo', input_price_per_1k: 0.01, output_price_per_1k: 0.03, context_length: 128000, currency: 'USD' },
      { name: 'gpt-3.5-turbo', display_name: 'GPT-3.5 Turbo', input_price_per_1k: 0.0005, output_price_per_1k: 0.0015, context_length: 16385, currency: 'USD' },

      // Anthropic 模型
      { name: 'claude-3-5-sonnet-20241022', display_name: 'Claude 3.5 Sonnet', input_price_per_1k: 0.003, output_price_per_1k: 0.015, context_length: 200000, currency: 'USD' },
      { name: 'claude-3-5-haiku-20241022', display_name: 'Claude 3.5 Haiku', input_price_per_1k: 0.001, output_price_per_1k: 0.005, context_length: 200000, currency: 'USD' },
      { name: 'claude-3-opus-20240229', display_name: 'Claude 3 Opus', input_price_per_1k: 0.015, output_price_per_1k: 0.075, context_length: 200000, currency: 'USD' },

      // Google 模型
      { name: 'gemini-2.0-flash-exp', display_name: 'Gemini 2.0 Flash', input_price_per_1k: 0, output_price_per_1k: 0, context_length: 1000000, currency: 'USD' },
      { name: 'gemini-1.5-pro', display_name: 'Gemini 1.5 Pro', input_price_per_1k: 0.00125, output_price_per_1k: 0.005, context_length: 2000000, currency: 'USD' },
      { name: 'gemini-1.5-flash', display_name: 'Gemini 1.5 Flash', input_price_per_1k: 0.000075, output_price_per_1k: 0.0003, context_length: 1000000, currency: 'USD' },
    ],
    'openrouter': [
      // OpenAI 模型
      { name: 'openai/gpt-4o', display_name: 'GPT-4o', input_price_per_1k: 0.005, output_price_per_1k: 0.015, context_length: 128000, currency: 'USD' },
      { name: 'openai/gpt-4o-mini', display_name: 'GPT-4o Mini', input_price_per_1k: 0.00015, output_price_per_1k: 0.0006, context_length: 128000, currency: 'USD' },
      { name: 'openai/gpt-3.5-turbo', display_name: 'GPT-3.5 Turbo', input_price_per_1k: 0.0005, output_price_per_1k: 0.0015, context_length: 16385, currency: 'USD' },

      // Anthropic 模型
      { name: 'anthropic/claude-3.5-sonnet', display_name: 'Claude 3.5 Sonnet', input_price_per_1k: 0.003, output_price_per_1k: 0.015, context_length: 200000, currency: 'USD' },
      { name: 'anthropic/claude-3-opus', display_name: 'Claude 3 Opus', input_price_per_1k: 0.015, output_price_per_1k: 0.075, context_length: 200000, currency: 'USD' },

      // Google 模型
      { name: 'google/gemini-2.0-flash-exp', display_name: 'Gemini 2.0 Flash', input_price_per_1k: 0, output_price_per_1k: 0, context_length: 1000000, currency: 'USD' },
      { name: 'google/gemini-pro-1.5', display_name: 'Gemini 1.5 Pro', input_price_per_1k: 0.00125, output_price_per_1k: 0.005, context_length: 2000000, currency: 'USD' },
    ]
  }

  return presets[providerName] || []
}

const handleSave = async () => {
  if (!formRef.value) return
  
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    
    if (formData.value.models.length === 0) {
      ElMessage.warning('请至少添加一个模型')
      return
    }
    
    saving.value = true
    try {
      await configApi.saveModelCatalog(formData.value)
      ElMessage.success('保存成功')
      dialogVisible.value = false
      await loadCatalogs()
    } catch (error) {
      console.error('保存失败:', error)
      ElMessage.error('保存失败')
    } finally {
      saving.value = false
    }
  })
}

const formatDate = (date: string) => {
  if (!date) return '-'
  return new Date(date).toLocaleString('zh-CN')
}

onMounted(() => {
  loadCatalogs()
  loadProviders()
})
</script>

<style lang="scss" scoped>
.model-catalog-management {
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .form-tip {
    font-size: 12px;
    color: var(--el-text-color-placeholder);
    margin-top: 4px;
  }
}
</style>

