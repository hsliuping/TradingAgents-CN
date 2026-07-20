<template>
  <div class="review-history-table">
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
      <el-table-column prop="realized_pnl" label="实现盈亏" width="120" align="right">
        <template #default="{ row }">
          <span :class="row.realized_pnl >= 0 ? 'positive' : 'negative'">
            {{ formatPnl(row.realized_pnl) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="getStatusType(row.status)" size="small">
            {{ getStatusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="复盘时间" width="160">
        <template #default="{ row }">
          {{ formatDateTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="230" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="$emit('view', row.review_id)">
            查看详情
          </el-button>
          <el-button 
            v-if="!row.is_case_study && row.status === 'completed'" 
            link type="success" size="small" 
            @click="$emit('save-case', row.review_id)"
          >
            加入案例库
          </el-button>
          <el-tag v-else-if="row.is_case_study" type="warning" size="small">已收藏</el-tag>
          <el-button 
            link type="danger" size="small" 
            @click="$emit('delete', row.review_id)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>
    
    <div class="pagination" v-if="total > 0">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="handlePageChange"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ReviewListItem, ReviewStatus } from '@/api/review'
import { formatDateTime } from '@/utils/datetime'

type TagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

const props = defineProps<{
  items: ReviewListItem[]
  loading: boolean
  total: number
  page: number
  pageSize: number
}>()

const emit = defineEmits<{
  (e: 'view', reviewId: string): void
  (e: 'save-case', reviewId: string): void
  (e: 'delete', reviewId: string): void
  (e: 'page-change', page: number): void
}>()

const currentPage = computed({
  get: () => props.page,
  set: (val) => emit('page-change', val)
})

const formatPnl = (value: number) => {
  if (value === undefined || value === null) return '-'
  const prefix = value >= 0 ? '+' : ''
  return prefix + value.toFixed(2)
}

const getStatusType = (status: ReviewStatus): TagType => {
  const map: Record<string, TagType> = {
    pending: 'info',
    processing: 'warning',
    completed: 'success',
    failed: 'danger'
  }
  return map[status] || 'info'
}

const getStatusLabel = (status: ReviewStatus) => {
  const map: Record<string, string> = {
    pending: '待处理',
    processing: '处理中',
    completed: '已完成',
    failed: '失败'
  }
  return map[status] || status
}

const handlePageChange = (page: number) => {
  emit('page-change', page)
}
</script>

<style scoped lang="scss">
.review-history-table {
  .stock-link {
    font-weight: 500;
    text-decoration: none;

    &:hover {
      text-decoration: underline;
    }
  }
  
  .positive { color: #f56c6c; }  // 中国习惯：红色表示盈利（正数）
  .negative { color: #67c23a; }  // 中国习惯：绿色表示亏损（负数）
  
  .pagination {
    margin-top: 16px;
    display: flex;
    justify-content: flex-end;
  }
}
</style>

