<template>
  <div class="watchlist-groups-container">
    <!-- 高级学员功能标识 -->
    <el-alert
      type="success"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
    >
      <template #title>
        <span style="display: flex; align-items: center; gap: 8px;">
          <el-tag type="success" size="small" effect="dark">高级</el-tag>
          <span>高级学员专属功能，为定时分析创建股票分组，支持按策略分类管理</span>
        </span>
      </template>
    </el-alert>

    <el-card>
      <template #header>
        <div class="card-header">
          <span>定时分析分组管理</span>
          <el-button type="primary" @click="showCreateDialog">
            <el-icon><Plus /></el-icon>
            创建分组
          </el-button>
        </div>
      </template>

      <el-table :data="groups" v-loading="loading">
        <el-table-column label="分组名称" min-width="150">
          <template #default="{ row }">
            <div class="group-name">
              <el-icon :color="row.color" :size="18">
                <component :is="row.icon || 'Folder'" />
              </el-icon>
              <span>{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="200" />
        <el-table-column label="股票数量" width="100" align="center">
          <template #default="{ row }">
            <el-tag>{{ row.stock_codes?.length || 0 }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="分析深度" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.analysis_depth" type="info">{{ row.analysis_depth }}级</el-tag>
            <span v-else class="text-muted">默认</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="manageStocks(row)">
              <el-icon><List /></el-icon>
              管理股票
            </el-button>
            <el-button link type="primary" @click="editGroup(row)">
              <el-icon><Edit /></el-icon>
              编辑
            </el-button>
            <el-button link type="danger" @click="deleteGroup(row)">
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建/编辑分组对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? '创建分组' : '编辑分组'"
      width="600px"
    >
      <el-form :model="formData" :rules="formRules" ref="formRef" label-width="120px">
        <el-form-item label="分组名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入分组名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="formData.description"
            type="textarea"
            :rows="3"
            placeholder="请输入分组描述"
          />
        </el-form-item>
        <el-form-item label="颜色">
          <el-color-picker v-model="formData.color" />
        </el-form-item>
        <el-form-item label="图标">
          <el-select v-model="formData.icon" placeholder="选择图标">
            <el-option label="文件夹" value="Folder" />
            <el-option label="星标" value="Star" />
            <el-option label="火箭" value="Promotion" />
            <el-option label="趋势" value="TrendCharts" />
            <el-option label="钱袋" value="Money" />
            <el-option label="收藏" value="Collection" />
          </el-select>
        </el-form-item>
        <el-divider>分析参数（可选）</el-divider>
        <el-form-item label="分析深度">
          <el-select v-model="formData.analysis_depth" placeholder="使用默认值" clearable>
            <el-option label="1级 - 快速" :value="1" />
            <el-option label="2级 - 基础" :value="2" />
            <el-option label="3级 - 标准" :value="3" />
            <el-option label="4级 - 深度" :value="4" />
            <el-option label="5级 - 全面" :value="5" />
          </el-select>
        </el-form-item>

        <div>
          <el-divider>股票列表</el-divider>
          <el-form-item label="选择股票">
            <el-select
              v-model="formData.stock_codes"
              multiple
              filterable
              allow-create
              default-first-option
              :reserve-keyword="false"
              placeholder="请选择或直接输入股票代码"
              style="width: 100%"
            >
              <el-option
                v-for="stock in allFavorites"
                :key="stock.stock_code"
                :label="stock.stock_name + ' (' + stock.stock_code + ')'"
                :value="stock.stock_code"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="从标签导入">
            <div style="display: flex; gap: 10px; width: 100%;">
              <el-select
                v-model="selectedTag"
                placeholder="选择标签快速导入"
                style="flex: 1"
                clearable
              >
                <el-option
                  v-for="tag in userTags"
                  :key="tag.id"
                  :label="tag.name"
                  :value="tag.name"
                >
                  <span style="display: flex; align-items: center; gap: 6px;">
                    <span
                      :style="{
                        display: 'inline-block',
                        width: '12px',
                        height: '12px',
                        borderRadius: '2px',
                        background: tag.color
                      }"
                    ></span>
                    {{ tag.name }}
                  </span>
                </el-option>
              </el-select>
              <el-button @click="importFromTagToForm" type="primary" plain>
                <el-icon><Collection /></el-icon>
                导入
              </el-button>
            </div>
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- 管理股票对话框 -->
    <el-dialog
      v-model="stockDialogVisible"
      title="管理分组股票"
      width="800px"
    >
      <div v-if="currentGroup">
        <div class="stock-actions">
          <el-input
            v-model="newStockCode"
            placeholder="输入股票代码，多个用逗号分隔"
            style="width: 300px; margin-right: 10px"
          />
          <el-button type="primary" @click="addStocks">
            <el-icon><Plus /></el-icon>
            添加
          </el-button>
          <el-divider direction="vertical" />
          <el-select
            v-model="selectedTag"
            placeholder="从标签导入"
            style="width: 150px; margin-right: 10px"
            clearable
          >
            <el-option
              v-for="tag in userTags"
              :key="tag.id"
              :label="tag.name"
              :value="tag.name"
            >
              <span style="display: flex; align-items: center; gap: 6px;">
                <span
                  :style="{
                    display: 'inline-block',
                    width: '12px',
                    height: '12px',
                    borderRadius: '2px',
                    background: tag.color
                  }"
                ></span>
                {{ tag.name }}
              </span>
            </el-option>
          </el-select>
          <el-button @click="importFromTag" :loading="importingTag">
            <el-icon><Collection /></el-icon>
            导入
          </el-button>
          <el-divider direction="vertical" />
          <el-button @click="importAllFavorites" :loading="importingAll">
            <el-icon><Star /></el-icon>
            导入所有自选股
          </el-button>
        </div>
        <el-table :data="currentGroup.stock_codes" style="margin-top: 20px" max-height="400">
          <el-table-column label="股票代码" prop="code">
            <template #default="{ row }">
              {{ row }}
            </template>
          </el-table-column>
          <el-table-column label="股票名称" min-width="120">
            <template #default="{ row }">
              {{ getStockName(row) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button link type="danger" @click="removeStock(row)">
                移除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Edit, Delete, List, Folder, Star, Promotion, TrendCharts, Money, Collection } from '@element-plus/icons-vue'
import {
  getWatchlistGroups,
  createWatchlistGroup,
  updateWatchlistGroup,
  deleteWatchlistGroup,
  addStocksToGroup,
  removeStocksFromGroup,
  type WatchlistGroup,
  type WatchlistGroupCreate,
  type WatchlistGroupUpdate
} from '@/api/watchlist-groups'
import { tagsApi } from '@/api/tags'
import { favoritesApi } from '@/api/favorites'

const loading = ref(false)
const groups = ref<WatchlistGroup[]>([])

const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const submitting = ref(false)
const formRef = ref<FormInstance>()

const formData = ref<WatchlistGroupCreate & { id?: string }>({
  name: '',
  description: '',
  color: '#409EFF',
  icon: 'Folder',
  stock_codes: [],
  analysis_depth: undefined
})

const formRules: FormRules = {
  name: [
    { required: true, message: '请输入分组名称', trigger: 'blur' }
  ]
}

const stockDialogVisible = ref(false)
const currentGroup = ref<WatchlistGroup | null>(null)
const newStockCode = ref('')

// 标签导入相关
const userTags = ref<Array<{id: string, name: string, color: string}>>([])
const selectedTag = ref('')
const importingTag = ref(false)
const importingAll = ref(false)
const allFavorites = ref<Array<{stock_code: string, stock_name: string, tags: string[]}>>([])

// 加载用户标签
const loadUserTags = async () => {
  try {
    const res = await tagsApi.list() as any
    if (res?.data && Array.isArray(res.data)) {
      userTags.value = res.data.map((t: any) => ({
        id: t.id,
        name: t.name,
        color: t.color || '#409EFF'
      }))
    }
  } catch (error) {
    console.error('加载标签失败:', error)
  }
}

// 加载自选股列表
const loadFavorites = async () => {
  try {
    const res = await favoritesApi.list() as any
    if (res?.data && Array.isArray(res.data)) {
      allFavorites.value = res.data.map((f: any) => ({
        stock_code: f.stock_code || f.symbol,
        stock_name: f.stock_name || '',
        tags: f.tags || []
      }))
    }
  } catch (error) {
    console.error('加载自选股失败:', error)
  }
}

// 从标签导入股票
const importFromTag = async () => {
  if (!currentGroup.value || !selectedTag.value) {
    ElMessage.warning('请选择要导入的标签')
    return
  }

  importingTag.value = true
  try {
    // 从自选股中筛选包含该标签的股票
    const stockCodes = allFavorites.value
      .filter(f => f.tags.includes(selectedTag.value))
      .map(f => f.stock_code)

    if (stockCodes.length === 0) {
      ElMessage.warning(`标签"${selectedTag.value}"下没有股票`)
      return
    }

    // 添加到分组
    const res = await addStocksToGroup(currentGroup.value.id, stockCodes) as any
    if (res?.success) {
      ElMessage.success(`成功导入 ${stockCodes.length} 只股票`)
      selectedTag.value = ''
      await loadGroups()
      // 更新当前分组数据
      const updated = groups.value.find(g => g.id === currentGroup.value!.id)
      if (updated) {
        currentGroup.value = updated
      }
    } else {
      ElMessage.error(res?.message || '导入失败')
    }
  } catch (error) {
    console.error('导入失败:', error)
    ElMessage.error('导入失败')
  } finally {
    importingTag.value = false
  }
}

// 导入所有自选股
const importAllFavorites = async () => {
  if (!currentGroup.value) {
    ElMessage.warning('请先选择分组')
    return
  }

  if (allFavorites.value.length === 0) {
    ElMessage.warning('您还没有添加任何自选股')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要将所有 ${allFavorites.value.length} 只自选股导入到分组"${currentGroup.value.name}"吗？`,
      '确认导入',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'info'
      }
    )

    importingAll.value = true

    // 获取所有自选股的股票代码
    const stockCodes = allFavorites.value.map(f => f.stock_code)

    // 添加到分组
    const res = await addStocksToGroup(currentGroup.value.id, stockCodes) as any
    if (res?.success) {
      ElMessage.success(`成功导入 ${stockCodes.length} 只股票`)
      await loadGroups()
      // 更新当前分组数据
      const updated = groups.value.find(g => g.id === currentGroup.value!.id)
      if (updated) {
        currentGroup.value = updated
      }
    } else {
      ElMessage.error(res?.message || '导入失败')
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('导入所有自选股失败:', error)
      ElMessage.error('导入失败')
    }
  } finally {
    importingAll.value = false
  }
}

// 在创建模式下从标签导入到表单
const importFromTagToForm = () => {
  if (!selectedTag.value) {
    ElMessage.warning('请选择要导入的标签')
    return
  }

  const stockCodes = allFavorites.value
    .filter(f => f.tags.includes(selectedTag.value))
    .map(f => f.stock_code)

  if (stockCodes.length === 0) {
    ElMessage.warning(`标签"${selectedTag.value}"下没有股票`)
    return
  }
  
  // 合并并去重
  const current = formData.value.stock_codes || []
  const newSet = new Set([...current, ...stockCodes])
  formData.value.stock_codes = Array.from(newSet)
  
  ElMessage.success(`已添加 ${stockCodes.length} 只股票到列表`)
  selectedTag.value = ''
}

// 加载分组列表
const loadGroups = async () => {
  loading.value = true
  try {
    const res = await getWatchlistGroups() as any
    if (res?.success) {
      groups.value = res.data.groups || []
    }
  } catch (error) {
    console.error('加载分组失败:', error)
    ElMessage.error('加载分组失败')
  } finally {
    loading.value = false
  }
}

// 显示创建对话框
const showCreateDialog = () => {
  dialogMode.value = 'create'
  formData.value = {
    name: '',
    description: '',
    color: '#409EFF',
    icon: 'Folder',
    stock_codes: [],
    analysis_depth: undefined
  }
  dialogVisible.value = true
}

// 编辑分组
const editGroup = (group: WatchlistGroup) => {
  dialogMode.value = 'edit'
  formData.value = {
    id: group.id,
    name: group.name,
    description: group.description,
    color: group.color,
    icon: group.icon,
    analysis_depth: group.analysis_depth,
    stock_codes: group.stock_codes ? [...group.stock_codes] : []
  }
  dialogVisible.value = true
}

// 提交表单
const submitForm = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    submitting.value = true
    try {
      if (dialogMode.value === 'create') {
        // 显式构造 payload，确保 stock_codes 被正确传递
        const payload = {
          ...formData.value,
          stock_codes: formData.value.stock_codes ? [...formData.value.stock_codes] : []
        }
        console.log('创建分组 payload:', payload)
        
        const res = await createWatchlistGroup(payload) as any
        if (res?.success) {
          ElMessage.success('创建成功')
          dialogVisible.value = false
          loadGroups()
        } else {
          ElMessage.error(res?.message || '创建失败')
        }
      } else {
        const { id, ...updateData } = formData.value
        if (!id) return

        // 显式构造 payload，确保 stock_codes 被正确传递
        const payload = {
          ...updateData,
          stock_codes: formData.value.stock_codes ? [...formData.value.stock_codes] : []
        }
        
        const res = await updateWatchlistGroup(id, payload as WatchlistGroupUpdate) as any
        if (res?.success) {
          ElMessage.success('更新成功')
          dialogVisible.value = false
          loadGroups()
        } else {
          ElMessage.error(res?.message || '更新失败')
        }
      }
    } catch (error) {
      console.error('操作失败:', error)
      ElMessage.error('操作失败')
    } finally {
      submitting.value = false
    }
  })
}

// 删除分组
const deleteGroup = async (group: WatchlistGroup) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除分组"${group.name}"吗？`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    const res = await deleteWatchlistGroup(group.id) as any
    if (res?.success) {
      ElMessage.success('删除成功')
      loadGroups()
    } else {
      ElMessage.error(res?.message || '删除失败')
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('删除失败:', error)
      ElMessage.error('删除失败')
    }
  }
}

// 管理股票
const manageStocks = (group: WatchlistGroup) => {
  currentGroup.value = group
  newStockCode.value = ''
  stockDialogVisible.value = true
}

// 添加股票
const addStocks = async () => {
  if (!currentGroup.value || !newStockCode.value.trim()) {
    ElMessage.warning('请输入股票代码')
    return
  }

  const codes = newStockCode.value.split(',').map(c => c.trim()).filter(c => c)
  if (codes.length === 0) {
    ElMessage.warning('请输入有效的股票代码')
    return
  }

  try {
    const res = await addStocksToGroup(currentGroup.value.id, codes) as any
    if (res?.success) {
      ElMessage.success(res.data?.message || '添加成功')
      newStockCode.value = ''
      await loadGroups()
      // 更新当前分组数据
      const updated = groups.value.find(g => g.id === currentGroup.value!.id)
      if (updated) {
        currentGroup.value = updated
      }
    } else {
      ElMessage.error(res?.message || '添加失败')
    }
  } catch (error) {
    console.error('添加股票失败:', error)
    ElMessage.error('添加股票失败')
  }
}

// 移除股票
const removeStock = async (code: string) => {
  if (!currentGroup.value) return

  try {
    const res = await removeStocksFromGroup(currentGroup.value.id, [code]) as any
    if (res?.success) {
      ElMessage.success('移除成功')
      await loadGroups()
      // 更新当前分组数据
      const updated = groups.value.find(g => g.id === currentGroup.value!.id)
      if (updated) {
        currentGroup.value = updated
      }
    } else {
      ElMessage.error(res?.message || '移除失败')
    }
  } catch (error) {
    console.error('移除股票失败:', error)
    ElMessage.error('移除股票失败')
  }
}

const getStockName = (code: string) => {
  const stock = allFavorites.value.find(f => f.stock_code === code)
  return stock ? stock.stock_name : '-'
}

onMounted(() => {
  loadGroups()
  loadUserTags()
  loadFavorites()
})
</script>

<style scoped lang="scss">
.watchlist-groups-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.group-name {
  display: flex;
  align-items: center;
  gap: 8px;
}

.text-muted {
  color: #909399;
}

.stock-actions {
  display: flex;
  align-items: center;
}
</style>

