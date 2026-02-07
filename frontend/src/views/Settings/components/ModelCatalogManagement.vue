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

            <!-- 🔥 新增：导入模型目录（针对当前厂家） -->
            <el-button
              type="warning"
              size="small"
              @click="handleImportForProvider"
              :loading="importingForProvider"
            >
              <el-icon><Upload /></el-icon>
              导入模型目录
            </el-button>

            <!-- 🔥 新增：导出模型目录（针对当前厂家） -->
            <el-button
              type="success"
              size="small"
              @click="handleExportForProvider"
              :loading="exportingForProvider"
              :disabled="!formData.provider || formData.models.length === 0"
            >
              <el-icon><Download /></el-icon>
              导出模型目录
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
                type="info"
                size="small"
                @click="handleUsePresetModels"
              >
                <el-icon><Document /></el-icon>
                使用预设模板
              </el-button>
            </template>
          </div>

          <el-alert
            title="💡 重要提示"
            type="info"
            :closable="false"
            style="margin-bottom: 10px"
          >
            <div>
              <p style="margin: 0 0 8px 0;"><strong>模型目录更新说明：</strong></p>
              <ul style="margin: 0 0 8px 20px; padding: 0;">
                <li>模型目录仅用于在添加大模型配置时提供可选模型列表</li>
                <li>导入或更新模型目录<strong>不会影响</strong>已配置的大模型配置</li>
                <li>即使模型从目录中删除，已配置的大模型仍然可以正常使用</li>
                <li><strong>导出功能：</strong>可以将当前厂家的模型目录导出为 JSON 文件，分享给其他用户</li>
                <li><strong>导入功能：</strong>可以从 JSON 文件导入单个厂家的模型目录</li>
                <li><strong>导入模式说明：</strong>
                  <ul style="margin: 4px 0 0 20px; padding: 0;">
                    <li><strong>update（推荐）</strong>：更新现有模型，添加新模型，<strong>保留原有模型中不在新数据里的模型</strong>（不会删除）</li>
                    <li><strong>replace</strong>：替换整个目录（会删除原有模型中不在新数据里的模型）</li>
                    <li><strong>append</strong>：仅追加新模型（不更新现有模型）</li>
                  </ul>
                </li>
                <li>如需删除过时的模型，请使用 update 模式导入后，手动删除不需要的模型</li>
              </ul>
              <template v-if="isAggregatorProvider">
                <p style="margin: 8px 0 4px 0;"><strong>聚合平台特殊功能：</strong></p>
                <ul style="margin: 0 0 0 20px; padding: 0;">
                  <li>点击"从 API 获取模型列表"自动获取（需要配置 API Key）</li>
                  <li>点击"使用预设模板"快速导入常用模型</li>
                  <li>点击"手动添加模型"逐个添加</li>
                </ul>
              </template>
            </div>
          </el-alert>

          <el-table :data="formData.models" border max-height="400">
            <el-table-column label="模型名称" width="200">
              <template #default="{ row, $index }">
                <el-input
                  v-model="row.name"
                  placeholder="如: qwen-turbo"
                  size="small"
                />
              </template>
            </el-table-column>
            <el-table-column label="显示名称" width="280">
              <template #default="{ row, $index }">
                <el-input
                  v-model="row.display_name"
                  placeholder="如: Qwen Turbo - 快速经济"
                  size="small"
                />
              </template>
            </el-table-column>
            <el-table-column label="输入价格/1K" width="180">
              <template #default="{ row, $index }">
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
              <template #default="{ row, $index }">
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
              <template #default="{ row, $index }">
                <el-input
                  v-model.number="row.context_length"
                  placeholder="1000000"
                  size="small"
                  type="number"
                />
              </template>
            </el-table-column>
            <el-table-column label="货币单位" width="120">
              <template #default="{ row, $index }">
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
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Refresh, Document, Download, Upload } from '@element-plus/icons-vue'
import { configApi, type LLMProvider } from '@/api/config'

// 数据
const loading = ref(false)
const catalogs = ref<any[]>([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const saving = ref(false)
const formRef = ref<FormInstance>()
const availableProviders = ref<LLMProvider[]>([])
const providersLoading = ref(false)
const fetchingModels = ref(false)
const importingForProvider = ref(false)
const exportingForProvider = ref(false)

// 聚合平台列表
const aggregatorProviders = ['302ai', 'oneapi', 'newapi', 'openrouter', 'custom_aggregator']

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

const formData = ref({
  provider: '',
  provider_name: '',
  models: [] as ModelInfo[]
})

const rules: FormRules = {
  provider: [{ required: true, message: '请输入厂家标识', trigger: 'blur' }],
  provider_name: [{ required: true, message: '请输入厂家名称', trigger: 'blur' }]
}

// 方法
const loadCatalogs = async () => {
  loading.value = true
  try {
    const response = await configApi.getModelCatalog()
    catalogs.value = response
  } catch (error) {
    console.error('加载模型目录失败:', error)
    ElMessage.error('加载模型目录失败')
  } finally {
    loading.value = false
  }
}

// 加载可用的厂家列表
const loadProviders = async (showSuccessMessage = false) => {
  providersLoading.value = true
  try {
    const providers = await configApi.getLLMProviders()
    availableProviders.value = providers
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

    // 提示：某些聚合平台（如 OpenRouter）不需要 API Key
    if (!provider.extra_config?.has_api_key) {
      console.log('⚠️ 该厂家未配置 API Key，尝试无认证访问')
    }

    await ElMessageBox.confirm(
      '此操作将从 API 获取模型列表并覆盖当前的模型列表，是否继续？',
      '确认操作',
      { type: 'warning' }
    )

    fetchingModels.value = true

    // 构建 API URL
    let baseUrl = provider.default_base_url
    if (!baseUrl.endsWith('/v1')) {
      baseUrl = baseUrl.replace(/\/$/, '') + '/v1'
    }
    const apiUrl = `${baseUrl}/models`

    console.log('🔍 获取模型列表:', apiUrl)
    console.log('🔍 厂家信息:', provider)

    // 调用后端 API 来获取模型列表（避免 CORS 问题）
    // 注意：需要传递厂家的 ID，而不是 name
    const response = await configApi.fetchProviderModels(provider.id)

    console.log('📊 API 响应:', response)

    if (response.success && response.models && response.models.length > 0) {
      // 转换模型格式，包含价格信息
      formData.value.models = response.models.map((model: any) => ({
        name: model.id || model.name,
        display_name: model.name || model.id,
        // 使用 API 返回的价格信息（USD），如果没有则为 null
        input_price_per_1k: model.input_price_per_1k || null,
        output_price_per_1k: model.output_price_per_1k || null,
        context_length: model.context_length || null,
        // OpenRouter 的价格是 USD
        currency: 'USD'
      }))

      // 统计有价格信息的模型数量
      const modelsWithPricing = formData.value.models.filter(m => m.input_price_per_1k || m.output_price_per_1k).length

      ElMessage.success(`成功获取 ${formData.value.models.length} 个模型（${modelsWithPricing} 个包含价格信息）`)
    } else {
      // 显示详细的错误信息
      const errorMsg = response.message || '获取模型列表失败或列表为空'
      console.error('❌ 获取失败:', errorMsg)
      ElMessage.error(errorMsg)
    }
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

// 导入当前厂家的模型目录
const handleImportForProvider = () => {
  // 检查是否选择了厂家
  if (!formData.value.provider) {
    ElMessage.warning('请先选择厂家')
    return
  }

  // 创建文件输入元素
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.json'
  input.onchange = async (e: Event) => {
    const target = e.target as HTMLInputElement
    const file = target.files?.[0]
    if (!file) return

    try {
      importingForProvider.value = true
      
      // 读取文件内容
      const text = await file.text()
      let catalogsData: any[]
      
      try {
        catalogsData = JSON.parse(text)
      } catch (parseError) {
        ElMessage.error('JSON 文件格式错误，请检查文件内容')
        return
      }

      // 验证数据格式
      if (!Array.isArray(catalogsData)) {
        ElMessage.error('导入数据格式错误：应为数组格式')
        return
      }

      // 查找当前厂家的数据
      const currentProviderCatalog = catalogsData.find(
        (catalog: any) => catalog.provider === formData.value.provider
      )

      if (!currentProviderCatalog) {
        ElMessage.warning(
          `导入文件中未找到厂家 "${formData.value.provider}" 的模型目录。` +
          `文件中包含的厂家：${catalogsData.map((c: any) => c.provider).join(', ')}`
        )
        return
      }

      // 询问用户选择合并模式
      const { value: mergeMode } = await ElMessageBox.prompt(
        `将为厂家 "${formData.value.provider_name}" 导入 ${currentProviderCatalog.models?.length || 0} 个模型。\n\n` +
        '请选择导入模式：\n' +
        '• update: 更新现有模型，添加新模型，保留原有模型中不在新数据里的模型（推荐，安全）\n' +
        '• replace: 替换整个目录（会删除原有模型中不在新数据里的模型）\n' +
        '• append: 仅追加新模型（不更新现有模型）\n\n' +
        '⚠️ 注意：\n' +
        '1. 导入只会更新模型目录，不会影响已配置的大模型配置\n' +
        '2. update 模式会保留原有模型，如需删除过时模型请手动操作',
        '选择导入模式',
        {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          inputType: 'select',
          inputOptions: {
            update: 'update - 更新现有模型，添加新模型，保留原有模型（推荐，安全）',
            replace: 'replace - 替换整个目录（会删除原有模型）',
            append: 'append - 仅追加新模型（不更新现有模型）'
          },
          inputValue: 'update'
        }
      )

      // 调用导入接口（只导入当前厂家）
      const response = await configApi.importModelCatalog({
        catalogs: [currentProviderCatalog],
        merge_mode: mergeMode
      })

      if (response.success) {
        const successCount = response.data?.success_count || 0
        const failedCount = response.data?.failed_count || 0
        
        if (successCount > 0) {
          ElMessage.success(`导入成功！成功: ${successCount}，失败: ${failedCount}`)
          
          // 显示详细结果
          if (response.data?.errors && response.data.errors.length > 0) {
            console.warn('导入过程中的错误:', response.data.errors)
            ElMessage.warning(`部分导入失败，请查看控制台了解详情`)
          }
          
          // 重新加载当前编辑的目录数据
          if (isEdit.value) {
            // 如果是编辑模式，重新获取数据
            const updatedCatalog = await configApi.getProviderModelCatalog(formData.value.provider)
            if (updatedCatalog) {
              formData.value.models = updatedCatalog.models || []
              ElMessage.info('已刷新模型列表')
            }
          } else {
            // 如果是新增模式，直接使用导入的数据
            if (currentProviderCatalog.models) {
              formData.value.models = currentProviderCatalog.models.map((m: any) => ({
                name: m.name || '',
                display_name: m.display_name || m.name || '',
                input_price_per_1k: m.input_price_per_1k || null,
                output_price_per_1k: m.output_price_per_1k || null,
                context_length: m.context_length || null,
                max_tokens: m.max_tokens || null,
                currency: m.currency || 'CNY',
                description: m.description || '',
                is_deprecated: m.is_deprecated || false,
                release_date: m.release_date || '',
                capabilities: m.capabilities || []
              }))
              ElMessage.info('已加载导入的模型列表，请检查后保存')
            }
          }
        } else {
          ElMessage.error('导入失败，请检查文件格式和厂家标识是否正确')
        }
      } else {
        ElMessage.error(response.message || '导入失败')
      }
    } catch (error: any) {
      if (error !== 'cancel') {
        console.error('导入失败:', error)
        ElMessage.error(error.response?.data?.detail || error.message || '导入失败')
      }
    } finally {
      importingForProvider.value = false
    }
  }
  
  input.click()
}

// 导出当前厂家的模型目录
const handleExportForProvider = async () => {
  // 检查是否选择了厂家
  if (!formData.value.provider) {
    ElMessage.warning('请先选择厂家')
    return
  }

  // 检查是否有模型数据
  if (!formData.value.models || formData.value.models.length === 0) {
    ElMessage.warning('当前没有模型数据可导出')
    return
  }

  try {
    exportingForProvider.value = true

    // 构建导出数据（当前对话框中的数据）
    const catalogData = {
      provider: formData.value.provider,
      provider_name: formData.value.provider_name,
      models: formData.value.models.map((m: ModelInfo) => ({
        name: m.name,
        display_name: m.display_name,
        description: m.description || '',
        context_length: m.context_length || null,
        max_tokens: m.max_tokens || null,
        input_price_per_1k: m.input_price_per_1k || null,
        output_price_per_1k: m.output_price_per_1k || null,
        currency: m.currency || 'CNY',
        is_deprecated: m.is_deprecated || false,
        release_date: m.release_date || '',
        capabilities: m.capabilities || []
      }))
    }

    // 将数据转换为 JSON 格式并下载
    const jsonData = JSON.stringify([catalogData], null, 2)
    const blob = new Blob([jsonData], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    
    // 生成文件名：厂家名_日期.json
    const dateStr = new Date().toISOString().split('T')[0]
    const fileName = `model_catalog_${formData.value.provider}_${dateStr}.json`
    link.download = fileName
    
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)

    ElMessage.success(
      `成功导出 ${formData.value.provider_name} 的模型目录，` +
      `包含 ${formData.value.models.length} 个模型`
    )
  } catch (error: any) {
    console.error('导出失败:', error)
    ElMessage.error(error.message || '导出失败')
  } finally {
    exportingForProvider.value = false
  }
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

