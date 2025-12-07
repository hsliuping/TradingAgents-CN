<template>
  <div class="position-review-history-table">
    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="code" label="股票代码" width="100" />
      <el-table-column prop="name" label="股票名称" width="120" />
      <el-table-column prop="review_type" label="复盘类型" width="100">
        <template #default="{ row }">
          <el-tag size="small">{{ getReviewTypeLabel(row.review_type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="score" label="评分" width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="getScoreType(row.score)" size="small">
            {{ row.score || '-' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="summary" label="复盘摘要" min-width="200" show-overflow-tooltip />
      <el-table-column prop="created_at" label="复盘时间" width="160">
        <template #default="{ row }">
          {{ formatDateTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link size="small" @click="handleView(row.id)">
            查看详情
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
  review_type: string
  score: number
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
  (e: 'page-change', page: number): void
}>()

const getReviewTypeLabel = (type: string) => {
  const map: Record<string, string> = {
    current: '当前持仓',
    history: '历史持仓',
    complete: '完整交易'
  }
  return map[type] || type
}

const getScoreType = (score: number) => {
  if (score >= 80) return 'success'
  if (score >= 60) return 'warning'
  return 'danger'
}

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
}
</style>

