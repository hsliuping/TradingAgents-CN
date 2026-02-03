<template>
  <div class="reviewable-trades-table">
    <el-empty
      v-if="!loading && stocks.length === 0"
      description="暂无可复盘的交易。请先在模拟交易中进行买卖操作。"
    >
      <el-button type="primary" @click="goToPaperTrading">前往模拟交易</el-button>
    </el-empty>

    <el-table v-else :data="stocks" v-loading="loading" stripe>
      <el-table-column prop="code" label="股票代码" width="110">
        <template #default="{ row }">
          <span class="code-text">{{ row.code }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="股票名称" width="100" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.name || '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="market" label="市场" width="70" align="center">
        <template #default="{ row }">
          <el-tag size="small" :type="getMarketType(row.market) as 'primary' | 'success' | 'warning' | 'info' | 'danger'">{{ row.market || 'CN' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="buy_count" label="买入" width="70" align="center" />
      <el-table-column prop="sell_count" label="卖出" width="70" align="center" />
      <el-table-column prop="total_pnl" label="累计盈亏" width="120" align="right">
        <template #default="{ row }">
          <span :class="(row.total_pnl || 0) >= 0 ? 'positive' : 'negative'">
            {{ formatPnl(row.total_pnl) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.status === 'completed' || row.sell_count >= row.buy_count" type="success" size="small">
            已平仓
          </el-tag>
          <el-tag v-else-if="row.sell_count > 0" type="warning" size="small">
            部分持仓
          </el-tag>
          <el-tag v-else type="primary" size="small">
            持仓中
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button 
            type="primary" 
            link
            size="small" 
            :disabled="!hasProPermission"
            @click="handleStartReview(row.code)"
          >
            发起复盘
          </el-button>
          <el-button 
            type="success" 
            link
            size="small" 
            @click="handleViewReport(row)"
          >
            查看报告
          </el-button>
          <el-button 
            type="info" 
            link
            size="small" 
            @click="handleViewHistory(row)"
          >
            复盘历史
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
            <li>持仓中的股票也可以复盘，分析买入时机是否合适</li>
          </ul>
        </template>
      </el-alert>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { computed } from 'vue'
import { useLicenseStore } from '@/stores/license'
import { ElMessage } from 'element-plus'
import type { ReviewableStock } from '@/api/review'

defineProps<{
  stocks: ReviewableStock[]
  loading: boolean
}>()

const emit = defineEmits<{
  (e: 'start-review', code: string): void
  (e: 'view-report', stock: ReviewableStock): void
  (e: 'view-history', stock: ReviewableStock): void
}>()

const router = useRouter()
const licenseStore = useLicenseStore()

// 检查是否有 PRO 权限
const hasProPermission = computed(() => {
  const hasFeature = licenseStore.hasFeature('trade_review')
  // 调试信息
  if (!hasFeature) {
    console.warn('[权限检查] 模拟交易复盘权限检查失败', {
      isPro: licenseStore.isPro,
      plan: licenseStore.plan,
      is_valid: licenseStore.licenseInfo?.is_valid,
      licenseInfo: licenseStore.licenseInfo
    })
  }
  return hasFeature
})

// 处理发起复盘按钮点击
const handleStartReview = (code: string) => {
  if (!hasProPermission.value) {
    const plan = licenseStore.plan
    const isPro = licenseStore.isPro
    const is_valid = licenseStore.licenseInfo?.is_valid
    console.error('[权限检查] 发起复盘被阻止', { plan, isPro, is_valid, licenseInfo: licenseStore.licenseInfo })
    ElMessage.warning('操作复盘功能需要 PRO 版本授权，请前往设置页面配置授权')
    return
  }
  emit('start-review', code)
}

const handleViewReport = (stock: ReviewableStock) => {
  emit('view-report', stock)
}

const handleViewHistory = (stock: ReviewableStock) => {
  emit('view-history', stock)
}

const formatPnl = (value?: number) => {
  if (value === undefined || value === null) return '-'
  const prefix = value >= 0 ? '+' : ''
  return prefix + value.toFixed(2)
}

const getMarketType = (market?: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' => {
  const map: Record<string, 'primary' | 'success' | 'warning' | 'info' | 'danger'> = {
    CN: 'danger',
    HK: 'warning',
    US: 'primary'
  }
  return map[market || 'CN'] || 'info'
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

