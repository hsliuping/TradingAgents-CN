<template>
  <div class="position-review-history-table">
    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="code" label="股票代码" width="100">
        <template #default="{ row }">
          <el-link type="primary" :href="`/stocks/${row.code}`" class="stock-link">
            {{ row.code }}
          </el-link>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="股票名称" width="120">
        <template #default="{ row }">
          <el-link type="primary" :href="`/stocks/${row.code}`" class="stock-link">
            {{ row.name }}
          </el-link>
        </template>
      </el-table-column>
      <el-table-column prop="summary" label="复盘摘要" min-width="200" show-overflow-tooltip />
      <el-table-column prop="created_at" label="复盘时间" width="160">
        <template #default="{ row }">
          {{ formatDateTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link size="small" @click="handleView(row.id)">
            查看详情
          </el-button>
          <el-button type="danger" link size="small" @click="handleDelete(row.id)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>
    
    <el-empty v-if="!loading && items.length === 0" description="暂无复盘记录" />
    
    <el-pagination
      v-if="total > 0"
      class="pagination"
      :current-page="page"
      :page-size="pageSize"
      :total="total"
      layout="total, prev, pager, next"
      @current-change="handlePageChange"
    />
  </div>
</template>

<script setup lang="ts">
interface PositionReviewItem {
  id: string
  code: string
  name: string
  created_at: string
  summary: string
}

defineProps<{
  items: PositionReviewItem[]
  loading: boolean
  total: number
  page: number
  pageSize: number
}>()

const emit = defineEmits<{
  (e: 'view', reviewId: string): void
  (e: 'delete', reviewId: string): void
  (e: 'page-change', page: number): void
}>()

const formatDateTime = (dateStr?: string) => {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const handleView = (reviewId: string) => {
  emit('view', reviewId)
}

const handleDelete = (reviewId: string) => {
  emit('delete', reviewId)
}

const handlePageChange = (page: number) => {
  emit('page-change', page)
}
</script>

<style scoped lang="scss">
.position-review-history-table {
  .pagination {
    margin-top: 16px;
    justify-content: flex-end;
  }

  .stock-link {
    font-weight: 500;
    text-decoration: none;

    &:hover {
      text-decoration: underline;
    }
  }
}
</style>
