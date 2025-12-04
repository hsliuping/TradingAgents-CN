<template>
  <div class="case-library-table">
    <el-empty v-if="!loading && items.length === 0" description="暂无案例，将复盘结果加入案例库以便日后回顾" />
    
    <el-table v-else :data="items" v-loading="loading" stripe>
      <el-table-column prop="code" label="股票代码" width="100">
        <template #default="{ row }">
          <span class="code-link" @click="$emit('view', row.review_id)">{{ row.code }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="名称" width="120" />
      <el-table-column prop="realized_pnl" label="实现盈亏" width="120" align="right">
        <template #default="{ row }">
          <span :class="row.realized_pnl >= 0 ? 'positive' : 'negative'">
            {{ formatPnl(row.realized_pnl) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="overall_score" label="评分" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="getScoreType(row.overall_score)" size="small">
            {{ row.overall_score }}分
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="tags" label="标签" min-width="150">
        <template #default="{ row }">
          <el-tag 
            v-for="tag in (row.tags || [])" 
            :key="tag" 
            size="small" 
            type="info"
            style="margin-right: 4px"
          >
            {{ tag }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="160">
        <template #default="{ row }">
          {{ formatDateTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="$emit('view', row.review_id)">
            查看详情
          </el-button>
          <el-popconfirm title="确定从案例库移除？" @confirm="$emit('delete', row.review_id)">
            <template #reference>
              <el-button link type="danger" size="small">移除</el-button>
            </template>
          </el-popconfirm>
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
import type { ReviewListItem } from '@/api/review'
import { formatDateTime } from '@/utils/datetime'

const props = defineProps<{
  items: ReviewListItem[]
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

const currentPage = computed({
  get: () => props.page,
  set: (val) => emit('page-change', val)
})

const formatPnl = (value: number) => {
  if (value === undefined || value === null) return '-'
  const prefix = value >= 0 ? '+' : ''
  return prefix + value.toFixed(2)
}

const getScoreType = (score: number) => {
  if (score >= 80) return 'success'
  if (score >= 60) return 'warning'
  return 'danger'
}

const handlePageChange = (page: number) => {
  emit('page-change', page)
}
</script>

<style scoped lang="scss">
.case-library-table {
  .code-link {
    color: var(--el-color-primary);
    cursor: pointer;
    &:hover { text-decoration: underline; }
  }
  
  .positive { color: #67c23a; }
  .negative { color: #f56c6c; }
  
  .pagination {
    margin-top: 16px;
    display: flex;
    justify-content: flex-end;
  }
}
</style>

