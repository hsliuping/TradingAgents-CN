<template>
  <div class="market-category-management">
    <div class="header">
      <h3>市场分类管理</h3>
      <el-button type="primary" icon="Plus" @click="showAddDialog">
        添加分类
      </el-button>
    </div>

    <el-table
      v-loading="loading"
      :data="categories"
      style="width: 100%"
      row-key="id"
    >
      <el-table-column prop="sort_order" label="排序" width="80" sortable />
      
      <el-table-column prop="id" label="分类ID" width="120" />
      
      <el-table-column prop="display_name" label="显示名称" width="120" />
      
      <el-table-column prop="description" label="描述" min-width="200" />
      
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.enabled ? 'success' : 'danger'" size="small">
            {{ row.enabled ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column label="数据源数量" width="120">
        <template #default="{ row }">
          <el-tag type="info" size="small">
            {{ getDataSourceCount(row.id) }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column label="创建时间" width="180">
        <template #default="{ row }">
          {{ formatDate(row.created_at) }}
        </template>
      </el-table-column>

      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button
            size="small"
            @click="editCategory(row)"
          >
            编辑
          </el-button>
          <el-button
            size="small"
            :type="row.enabled ? 'warning' : 'success'"
            @click="toggleCategory(row)"
          >
            {{ row.enabled ? '禁用' : '启用' }}
          </el-button>
          <el-button
            size="small"
            type="danger"
            @click="deleteCategory(row)"
            :disabled="getDataSourceCount(row.id) > 0"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分类对话框 -->
    <MarketCategoryDialog
      v-model:visible="dialogVisible"
      :category="currentCategory"
      @success="handleSuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { configApi, type MarketCategory, type DataSourceGrouping } from '@/api/config'
import MarketCategoryDialog from './MarketCategoryDialog.vue'

// Refs
const loading = ref(false)
const categories = ref<MarketCategory[]>([])
const groupings = ref<DataSourceGrouping[]>([])
const dialogVisible = ref(false)
const currentCategory = ref<MarketCategory | null>(null)

// Computed
const getDataSourceCount = computed(() => {
  return (categoryId: string) => {
    return groupings.value.filter(g => g.market_category_id === categoryId && g.enabled).length
  }
})

// 格式化日期
const formatDate = (dateStr?: string) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

// 加载数据
const loadCategories = async () => {
  loading.value = true
  try {
    categories.value = await configApi.getMarketCategories()
    // 按排序顺序排列
    categories.value.sort((a, b) => a.sort_order - b.sort_order)
  } catch (error) {
    console.error('加载市场分类失败:', error)
    ElMessage.error('加载市场分类失败')
  } finally {
    loading.value = false
  }
}

const loadGroupings = async () => {
  try {
    groupings.value = await configApi.getDataSourceGroupings()
  } catch (error) {
    console.error('加载分组关系失败:', error)
  }
}

// 显示添加对话框
const showAddDialog = () => {
  currentCategory.value = null
  dialogVisible.value = true
}

// 编辑分类
const editCategory = (category: MarketCategory) => {
  currentCategory.value = category
  dialogVisible.value = true
}

// 切换分类状态
const toggleCategory = async (category: MarketCategory) => {
  try {
    await configApi.updateMarketCategory(category.id, {
      enabled: !category.enabled
    })
    
    category.enabled = !category.enabled
    ElMessage.success(`分类已${category.enabled ? '启用' : '禁用'}`)
  } catch (error) {
    console.error('切换分类状态失败:', error)
    ElMessage.error('切换分类状态失败')
  }
}

// 删除分类
const deleteCategory = async (category: MarketCategory) => {
  const dataSourceCount = getDataSourceCount.value(category.id)
  
  if (dataSourceCount > 0) {
    ElMessage.warning('该分类下还有数据源，无法删除')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要删除市场分类 "${category.display_name}" 吗？`,
      '确认删除',
      { type: 'warning' }
    )

    await configApi.deleteMarketCategory(category.id)
    await loadCategories()
    ElMessage.success('市场分类删除成功')
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除市场分类失败:', error)
      ElMessage.error('删除市场分类失败')
    }
  }
}

// 处理成功
const handleSuccess = () => {
  loadCategories()
}

// 生命周期
onMounted(() => {
  loadCategories()
  loadGroupings()
})
</script>

<style lang="scss" scoped>
.market-category-management {
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;

    h3 {
      margin: 0;
      color: #303133;
    }
  }
}
</style>
