<template>
  <div class="reviewable-trades-table">
    <el-empty 
      v-if="!loading && stocks.length === 0" 
      description="暂无可复盘的交易。请先在模拟交易中完成一笔完整的买卖操作。"
    >
      <el-button type="primary" @click="goToPaperTrading">前往模拟交易</el-button>
    </el-empty>
    
    <el-table v-else :data="stocks" v-loading="loading" stripe>
      <el-table-column prop="code" label="股票代码" width="120">
        <template #default="{ row }">
          <span class="code-text">{{ row.code }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="buy_count" label="买入次数" width="100" align="center" />
      <el-table-column prop="sell_count" label="卖出次数" width="100" align="center" />
      <el-table-column prop="total_pnl" label="累计盈亏" width="150" align="right">
        <template #default="{ row }">
          <span :class="row.total_pnl >= 0 ? 'positive' : 'negative'">
            {{ formatPnl(row.total_pnl) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <el-tag v-if="row.sell_count >= row.buy_count" type="success" size="small">
            已平仓
          </el-tag>
          <el-tag v-else type="warning" size="small">
            部分持仓
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150">
        <template #default="{ row }">
          <el-button type="primary" size="small" @click="$emit('start-review', row.code)">
            发起复盘
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="tips">
      <el-alert type="info" :closable="false" show-icon>
        <template #title>
          <span>复盘提示</span>
        </template>
        <template #default>
          <ul>
            <li>复盘可以帮助你分析买卖时机、发现操作中的问题</li>
            <li>建议对每笔完成的交易都进行复盘，持续改进交易策略</li>
            <li>优质的复盘可以保存到案例库，方便日后回顾学习</li>
          </ul>
        </template>
      </el-alert>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import type { ReviewableStock } from '@/api/review'

defineProps<{
  stocks: ReviewableStock[]
  loading: boolean
}>()

defineEmits<{
  (e: 'start-review', code: string): void
}>()

const router = useRouter()

const formatPnl = (value: number) => {
  if (value === undefined || value === null) return '-'
  const prefix = value >= 0 ? '+' : ''
  return prefix + value.toFixed(2)
}

const goToPaperTrading = () => {
  router.push('/paper')
}
</script>

<style scoped lang="scss">
.reviewable-trades-table {
  .code-text {
    font-weight: 500;
  }
  
  .positive { color: #67c23a; }
  .negative { color: #f56c6c; }
  
  .tips {
    margin-top: 20px;
    
    ul {
      margin: 8px 0 0 0;
      padding-left: 20px;
      li {
        margin-bottom: 4px;
        font-size: 13px;
      }
    }
  }
}
</style>

