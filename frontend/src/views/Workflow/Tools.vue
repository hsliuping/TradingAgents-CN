<template>
  <div class="tools-config-page">
    <div class="page-header">
      <div class="header-left">
        <h1>
          <el-icon class="header-icon"><Tools /></el-icon>
          工具配置
        </h1>
        <span class="subtitle">查看和管理系统可用工具</span>
      </div>
      <div class="header-right">
        <el-button type="primary" @click="openCategoryManager">
          <el-icon><FolderOpened /></el-icon>
          分类管理
        </el-button>
        <el-button type="success" @click="openCreateTool">
          <el-icon><Plus /></el-icon>
          新增工具
        </el-button>
        <el-button @click="refreshTools">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <div class="filter-section">
      <el-radio-group v-model="currentCategory" @change="handleCategoryChange">
        <el-radio-button label="">全部</el-radio-button>
        <el-radio-button v-for="cat in categories" :key="cat.id" :label="cat.id">
          {{ getCategoryName(cat.id) }}
        </el-radio-button>
      </el-radio-group>
    </div>

    <el-table
      v-loading="loading"
      :data="filteredTools"
      style="width: 100%"
      border
      stripe
    >
      <el-table-column prop="name" label="工具名称" min-width="150">
        <template #default="{ row }">
          <div class="tool-name">
            <span class="tool-icon">{{ row.icon || '🔧' }}</span>
            <span class="name-text">{{ row.name }}</span>
            <el-tag v-if="!row.is_online" type="info" size="small" effect="plain" style="margin-left: 5px">离线</el-tag>
          </div>
        </template>
      </el-table-column>
      
      <el-table-column prop="description" label="描述" min-width="250" show-overflow-tooltip />
      
      <el-table-column prop="category" label="分类" width="120">
        <template #default="{ row }">
          <el-tag :type="getCategoryTagType(row.category) as any">{{ getCategoryName(row.category) }}</el-tag>
        </template>
      </el-table-column>
      
      <el-table-column prop="data_source" label="数据源" width="120" />
      
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link @click="showToolDetails(row)">
            详情
          </el-button>
          <template v-if="row.data_source === 'custom_http'">
            <el-button type="primary" link @click="openEditTool(row)">
              编辑
            </el-button>
            <el-button type="danger" link @click="handleDeleteTool(row)">
              删除
            </el-button>
          </template>
        </template>
      </el-table-column>
    </el-table>

    <!-- 工具详情弹窗 -->
    <el-dialog
      v-model="detailsVisible"
      :title="selectedTool?.name"
      width="600px"
      @close="cancelToolEdit"
    >
      <div v-if="selectedTool" class="tool-details">
        <!-- 详情展示模式 -->
        <template v-if="!isEditingTool">
          <div class="detail-item">
            <span class="label">ID:</span>
            <span class="value">{{ selectedTool.id }}</span>
          </div>
          <div class="detail-item">
            <span class="label">描述:</span>
            <span class="value">{{ selectedTool.description }}</span>
          </div>
          <div class="detail-item">
            <span class="label">分类:</span>
            <span class="value">{{ getCategoryName(selectedTool.category) }}</span>
          </div>
          <div class="detail-item">
            <span class="label">超时时间:</span>
            <span class="value">{{ selectedTool.timeout }}ms</span>
          </div>
          <div class="detail-item">
            <span class="label">状态:</span>
            <span class="value">
              <el-tag :type="selectedTool.is_online ? 'success' : 'info'">
                {{ selectedTool.is_online ? '在线' : '离线' }}
              </el-tag>
            </span>
          </div>
        </template>

        <!-- 编辑模式 -->
        <el-form v-else :model="editingToolForm" label-width="100px">
           <el-form-item label="描述">
             <el-input v-model="editingToolForm.description" type="textarea" :rows="3" />
           </el-form-item>
           <el-form-item label="分类">
             <el-select v-model="editingToolForm.category">
               <el-option 
                 v-for="cat in categories" 
                 :key="cat.id" 
                 :label="getCategoryName(cat.id)" 
                 :value="cat.id" 
               />
             </el-select>
           </el-form-item>
           <el-form-item label="超时时间(ms)">
             <el-input-number v-model="editingToolForm.timeout" :min="100" :step="1000" />
           </el-form-item>
           <el-form-item label="状态">
             <el-switch 
               v-model="editingToolForm.is_online" 
               active-text="在线" 
               inactive-text="离线" 
             />
           </el-form-item>
        </el-form>
        
        <div class="detail-section">
          <h3>参数列表</h3>
          <el-table :data="selectedTool.parameters" size="small" border>
            <el-table-column prop="name" label="参数名" width="120" />
            <el-table-column prop="type" label="类型" width="100" />
            <el-table-column prop="description" label="描述" />
            <el-table-column prop="required" label="必填" width="80">
              <template #default="{ row }">
                <el-tag :type="row.required ? 'danger' : 'info'" size="small">
                  {{ row.required ? '是' : '否' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <template v-if="!isEditingTool">
            <el-button @click="detailsVisible = false">关闭</el-button>
            <el-button type="primary" @click="toggleToolEdit">修改配置</el-button>
          </template>
          <template v-else>
            <el-button @click="cancelToolEdit">取消</el-button>
            <el-button type="primary" @click="saveToolConfig">保存</el-button>
          </template>
        </span>
      </template>
    </el-dialog>

    <!-- 分类管理弹窗 -->
    <el-dialog
      v-model="categoryManagerVisible"
      title="分类管理"
      width="600px"
    >
      <div style="margin-bottom: 15px;">
        <el-button type="primary" size="small" @click="openCreateCategory">
          <el-icon><Plus /></el-icon> 新增分类
        </el-button>
      </div>
      <el-table :data="categories" border stripe size="small">
        <el-table-column prop="id" label="ID" width="120" />
        <el-table-column prop="name" label="名称" />
        <el-table-column label="类型" width="100">
           <template #default="{ row }">
             <el-tag :type="row.is_builtin ? 'info' : 'success'" size="small">
               {{ row.is_builtin ? '内置' : '自定义' }}
             </el-tag>
           </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEditCategory(row)" :disabled="row.is_builtin">
              编辑
            </el-button>
            <el-button link type="danger" size="small" @click="handleDeleteCategory(row)" :disabled="row.is_builtin">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 新增/编辑分类弹窗 -->
    <el-dialog
      v-model="categoryFormVisible"
      :title="categoryForm.isEdit ? '编辑分类' : '新增分类'"
      width="400px"
    >
      <el-form :model="categoryForm" label-width="80px">
        <el-form-item label="ID">
          <el-input v-model="categoryForm.id" :disabled="categoryForm.isEdit" placeholder="英文ID，如 my_tools" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="categoryForm.name" placeholder="中文名称" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="categoryFormVisible = false">取消</el-button>
          <el-button type="primary" @click="submitCategoryForm">确定</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 自定义工具编辑弹窗 -->
    <el-dialog
      v-model="toolFormVisible"
      :title="toolForm.isEdit ? '编辑工具' : '新增工具'"
      width="800px"
      top="5vh"
    >
      <el-form :model="toolForm" label-width="100px">
        <el-tabs v-model="activeToolTab">
          <el-tab-pane label="基本信息" name="basic">
            <el-form-item label="ID" required>
              <el-input v-model="toolForm.id" :disabled="toolForm.isEdit" placeholder="唯一标识符，如 my_custom_tool" />
            </el-form-item>
            <el-form-item label="名称" required>
              <el-input v-model="toolForm.name" placeholder="显示名称" />
            </el-form-item>
            <el-form-item label="描述">
              <el-input
                v-model="toolForm.description"
                type="textarea"
                :rows="3"
              />
            </el-form-item>
            <el-form-item label="分类">
              <el-select v-model="toolForm.category">
                 <el-option v-for="cat in categories" :key="cat.id" :label="getCategoryName(cat.id)" :value="cat.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="超时(ms)">
              <el-input-number v-model="toolForm.timeout" :step="1000" />
            </el-form-item>
            <el-form-item label="状态">
              <el-switch v-model="toolForm.is_online" active-text="在线" inactive-text="离线" />
            </el-form-item>
          </el-tab-pane>
          
          <el-tab-pane label="实现配置" name="impl">
            <el-alert title="目前仅支持 HTTP 请求方式" type="info" show-icon :closable="false" style="margin-bottom: 15px" />
            <el-form-item label="URL" required>
              <el-input v-model="toolForm.implementation.url" placeholder="http://api.example.com/data?q={query}">
                 <template #append>
                   <el-select v-model="toolForm.implementation.method" style="width: 100px">
                     <el-option label="GET" value="GET" />
                     <el-option label="POST" value="POST" />
                     <el-option label="PUT" value="PUT" />
                     <el-option label="DELETE" value="DELETE" />
                   </el-select>
                 </template>
              </el-input>
              <div class="form-tip" style="font-size: 12px; color: #909399; margin-top: 5px">支持使用 {param_name} 作为参数占位符</div>
            </el-form-item>
            
            <div style="margin: 15px 0 10px 0; font-weight: bold">请求头 (Headers)</div>
            <div v-for="(header, index) in toolForm.implementation.headersList" :key="index" style="display: flex; margin-bottom: 10px; align-items: center">
              <el-input v-model="header.key" placeholder="Key" style="width: 40%; margin-right: 5px" />
              <span style="margin: 0 5px">:</span>
              <el-input v-model="header.value" placeholder="Value" style="width: 40%; margin-right: 10px" />
              <el-button type="danger" circle size="small" @click="removeHeader(index)"><el-icon><Delete /></el-icon></el-button>
            </div>
            <el-button type="primary" link @click="addHeader">+ 添加请求头</el-button>
          </el-tab-pane>
          
          <el-tab-pane label="参数定义" name="params">
            <el-table :data="toolForm.parameters" border size="small">
              <el-table-column label="参数名" width="150">
                <template #default="{ row }">
                  <el-input v-model="row.name" size="small" placeholder="参数名" />
                </template>
              </el-table-column>
              <el-table-column label="类型" width="120">
                <template #default="{ row }">
                  <el-select v-model="row.type" size="small">
                    <el-option label="string" value="string" />
                    <el-option label="number" value="number" />
                    <el-option label="boolean" value="boolean" />
                    <el-option label="integer" value="integer" />
                  </el-select>
                </template>
              </el-table-column>
              <el-table-column label="描述">
                <template #default="{ row }">
                  <el-input v-model="row.description" size="small" />
                </template>
              </el-table-column>
              <el-table-column label="必填" width="60" align="center">
                <template #default="{ row }">
                  <el-checkbox v-model="row.required" />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="60" align="center">
                <template #default="{ $index }">
                  <el-button type="danger" circle size="small" @click="removeParameter($index)"><el-icon><Delete /></el-icon></el-button>
                </template>
              </el-table-column>
            </el-table>
            <div style="margin-top: 10px">
              <el-button type="primary" link @click="addParameter">+ 添加参数</el-button>
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-form>
      <template #footer>
        <el-button @click="toolFormVisible = false">取消</el-button>
        <el-button type="primary" @click="submitToolForm">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Tools, Refresh, FolderOpened, Plus, Delete } from '@element-plus/icons-vue'
import { toolsApi, type ToolMetadata, type ToolCategory, type CustomToolDefinition } from '@/api/tools'

const loading = ref(false)
const tools = ref<ToolMetadata[]>([])
const categories = ref<ToolCategory[]>([])
const currentCategory = ref('')
const detailsVisible = ref(false)
const selectedTool = ref<ToolMetadata | null>(null)

// 分类管理状态
const categoryManagerVisible = ref(false)
const categoryFormVisible = ref(false)
const categoryForm = reactive({
  id: '',
  name: '',
  isEdit: false
})

// 工具编辑状态
const isEditingTool = ref(false)
const editingToolForm = reactive({
  description: '',
  category: '',
  timeout: 30000,
  is_online: true
})

// 内置的中文映射表（优先使用）
const categoryNameMap: Record<string, string> = {
  'trade_review': '复盘分析',
  'market': '市场数据',
  'fundamentals': '基本面数据',
  'news': '新闻数据',
  'social': '社交媒体',
  'technical': '技术分析',
  'china_market': '中国市场',
  'position_analysis': '持仓分析',
  'stock_analysis': '股票分析'
}

// 获取分类名称（优先使用内置映射，如果映射中没有则使用分类列表中的名称）
const getCategoryName = (categoryId: string) => {
  // 优先使用内置的中文映射
  if (categoryNameMap[categoryId]) {
    return categoryNameMap[categoryId]
  }
  
  // 如果映射中没有，尝试从分类列表中查找
  const category = categories.value.find(c => c.id === categoryId)
  if (category && category.name) {
    // 如果分类名称是中文，直接返回；如果是英文ID，尝试映射
    return categoryNameMap[category.name] || category.name
  }
  
  // 最后返回原始ID
  return categoryId
}

// 分类标签颜色
const getCategoryTagType = (categoryId: string) => {
  const map: Record<string, string> = {
    market: 'success',
    news: 'warning',
    fundamentals: 'primary',
    social: 'danger',
    technical: 'info'
  }
  return map[categoryId] || ''
}

// 过滤工具
const filteredTools = computed(() => {
  if (!currentCategory.value) {
    return tools.value
  }
  return tools.value.filter(t => t.category === currentCategory.value)
})

// 加载数据
const loadData = async () => {
  loading.value = true
  try {
    const [toolsData, categoriesData] = await Promise.all([
      toolsApi.listTools(),
      toolsApi.listCategories()
    ])
    tools.value = toolsData
    categories.value = categoriesData
  } catch (error) {
    console.error('加载工具失败:', error)
    ElMessage.error('加载工具列表失败')
  } finally {
    loading.value = false
  }
}

const refreshTools = () => {
  loadData()
}

const handleCategoryChange = () => {
  // 可以在这里添加额外逻辑
}

const showToolDetails = (tool: ToolMetadata) => {
  selectedTool.value = tool
  detailsVisible.value = true
  isEditingTool.value = false
}

// --- 分类管理逻辑 ---

const openCategoryManager = () => {
  categoryManagerVisible.value = true
}

const openCreateCategory = () => {
  categoryForm.id = ''
  categoryForm.name = ''
  categoryForm.isEdit = false
  categoryFormVisible.value = true
}

const openEditCategory = (cat: ToolCategory) => {
  categoryForm.id = cat.id
  categoryForm.name = cat.name
  categoryForm.isEdit = true
  categoryFormVisible.value = true
}

const handleDeleteCategory = async (cat: ToolCategory) => {
  try {
    await ElMessageBox.confirm(`确定要删除分类 "${cat.name}" 吗？`, '提示', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消'
    })
    
    await toolsApi.deleteCategory(cat.id)
    ElMessage.success('删除成功')
    loadData() // 刷新列表
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const submitCategoryForm = async () => {
  if (!categoryForm.id || !categoryForm.name) {
    ElMessage.warning('请填写完整信息')
    return
  }
  
  try {
    if (categoryForm.isEdit) {
      await toolsApi.updateCategory(categoryForm.id, { name: categoryForm.name })
      ElMessage.success('更新成功')
    } else {
      await toolsApi.createCategory({ id: categoryForm.id, name: categoryForm.name })
      ElMessage.success('创建成功')
    }
    categoryFormVisible.value = false
    loadData()
  } catch (e) {
    console.error(e)
    ElMessage.error(categoryForm.isEdit ? '更新失败' : '创建失败，可能ID已存在')
  }
}

// --- 工具配置编辑逻辑 ---

const toggleToolEdit = () => {
  if (!selectedTool.value) return
  
  editingToolForm.description = selectedTool.value.description
  editingToolForm.category = selectedTool.value.category
  editingToolForm.timeout = selectedTool.value.timeout
  editingToolForm.is_online = selectedTool.value.is_online
  
  isEditingTool.value = true
}

const cancelToolEdit = () => {
  isEditingTool.value = false
}

const saveToolConfig = async () => {
  if (!selectedTool.value) return
  
  try {
    await toolsApi.updateToolConfig(selectedTool.value.id, {
      description: editingToolForm.description,
      category: editingToolForm.category,
      timeout: editingToolForm.timeout,
      is_online: editingToolForm.is_online
    })
    
    ElMessage.success('配置已保存')
    isEditingTool.value = false
    detailsVisible.value = false
    loadData()
  } catch (e) {
    console.error(e)
    ElMessage.error('保存失败')
  }
}

// --- 自定义工具管理逻辑 ---

const toolFormVisible = ref(false)
const activeToolTab = ref('basic')
const toolForm = reactive({
  isEdit: false,
  id: '',
  name: '',
  description: '',
  category: '',
  timeout: 30000,
  is_online: true,
  parameters: [] as any[],
  implementation: {
    url: '',
    method: 'GET',
    headersList: [] as {key: string, value: string}[]
  }
})

const openCreateTool = () => {
  toolForm.isEdit = false
  toolForm.id = ''
  toolForm.name = ''
  toolForm.description = ''
  toolForm.category = categories.value.length > 0 ? categories.value[0].id : ''
  toolForm.timeout = 30000
  toolForm.is_online = true
  toolForm.parameters = []
  toolForm.implementation = {
    url: '',
    method: 'GET',
    headersList: []
  }
  activeToolTab.value = 'basic'
  toolFormVisible.value = true
}

const openEditTool = async (tool: ToolMetadata) => {
  try {
    loading.value = true
    const definition = await toolsApi.getCustomTool(tool.id)
    
    toolForm.isEdit = true
    toolForm.id = definition.id
    toolForm.name = definition.name
    toolForm.description = definition.description
    toolForm.category = definition.category
    toolForm.timeout = definition.timeout
    toolForm.is_online = definition.is_online
    toolForm.parameters = definition.parameters || []
    
    // 转换 headers 为 list
    const headersList = []
    if (definition.implementation && definition.implementation.headers) {
      for (const [key, value] of Object.entries(definition.implementation.headers)) {
        headersList.push({ key, value: definition.implementation.headers[key] })
      }
    }
    
    toolForm.implementation = {
      url: definition.implementation?.url || '',
      method: definition.implementation?.method || 'GET',
      headersList
    }
    
    activeToolTab.value = 'basic'
    toolFormVisible.value = true
  } catch (e) {
    console.error(e)
    ElMessage.error('获取工具详情失败')
  } finally {
    loading.value = false
  }
}

const handleDeleteTool = async (tool: ToolMetadata) => {
  try {
    await ElMessageBox.confirm(`确定要删除工具 "${tool.name}" 吗？`, '提示', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消'
    })
    
    await toolsApi.deleteCustomTool(tool.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const addHeader = () => {
  toolForm.implementation.headersList.push({ key: '', value: '' })
}

const removeHeader = (index: number) => {
  toolForm.implementation.headersList.splice(index, 1)
}

const addParameter = () => {
  toolForm.parameters.push({
    name: '',
    type: 'string',
    description: '',
    required: false
  })
}

const removeParameter = (index: number) => {
  toolForm.parameters.splice(index, 1)
}

const submitToolForm = async () => {
  if (!toolForm.id || !toolForm.name || !toolForm.implementation.url) {
    ElMessage.warning('请填写必要信息（ID、名称、URL）')
    return
  }
  
  // 转换 headers
  const headers: Record<string, string> = {}
  for (const h of toolForm.implementation.headersList) {
    if (h.key) {
      headers[h.key] = h.value
    }
  }
  
  const definition: CustomToolDefinition = {
    id: toolForm.id,
    name: toolForm.name,
    description: toolForm.description,
    category: toolForm.category,
    timeout: toolForm.timeout,
    is_online: toolForm.is_online,
    parameters: toolForm.parameters,
    implementation: {
      url: toolForm.implementation.url,
      method: toolForm.implementation.method,
      headers
    }
  }
  
  try {
    if (toolForm.isEdit) {
      await toolsApi.updateCustomTool(toolForm.id, definition)
      ElMessage.success('更新成功')
    } else {
      await toolsApi.createCustomTool(definition)
      ElMessage.success('创建成功')
    }
    toolFormVisible.value = false
    loadData()
  } catch (e) {
    console.error(e)
    ElMessage.error(toolForm.isEdit ? '更新失败' : '创建失败')
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped lang="scss">
.tools-config-page {
  padding: 20px;
  background-color: var(--el-bg-color);
  min-height: calc(100vh - 60px);

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;

    .header-left {
      h1 {
        display: flex;
        align-items: center;
        font-size: 24px;
        margin: 0 0 8px 0;
        
        .header-icon {
          margin-right: 12px;
          color: var(--el-color-primary);
        }
      }

      .subtitle {
        color: var(--el-text-color-secondary);
        font-size: 14px;
      }
    }
  }

  .filter-section {
    margin-bottom: 20px;
  }
  
  .tool-name {
    display: flex;
    align-items: center;
    
    .tool-icon {
      font-size: 18px;
      margin-right: 8px;
    }
    
    .name-text {
      font-weight: 500;
    }
  }
}

.tool-details {
  .detail-item {
    margin-bottom: 12px;
    display: flex;
    
    .label {
      font-weight: bold;
      width: 80px;
      color: var(--el-text-color-regular);
    }
    
    .value {
      color: var(--el-text-color-primary);
      flex: 1;
    }
  }
  
  .detail-section {
    margin-top: 24px;
    
    h3 {
      font-size: 16px;
      margin-bottom: 12px;
      border-left: 3px solid var(--el-color-primary);
      padding-left: 8px;
    }
  }
}
</style>
