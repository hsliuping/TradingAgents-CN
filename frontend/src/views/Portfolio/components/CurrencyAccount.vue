<template>
  <div class="currency-account">
    <el-row :gutter="16">
      <el-col :span="6">
        <div class="stat-item">
          <div class="label">总资产</div>
          <div class="value">{{ symbol }}{{ formatMoney(summary?.total_assets?.[currency] || 0) }}</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-item">
          <div class="label">可用资金</div>
          <div class="value">{{ symbol }}{{ formatMoney(summary?.cash?.[currency] || 0) }}</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-item">
          <div class="label">持仓市值</div>
          <div class="value">{{ symbol }}{{ formatMoney(summary?.positions_value?.[currency] || 0) }}</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-item">
          <div class="label">累计收益</div>
          <div class="value" :class="profitClass">
            {{ profitPrefix }}{{ symbol }}{{ formatMoney(Math.abs(profit)) }}
            <span class="pct">({{ profitPctPrefix }}{{ profitPct.toFixed(2) }}%)</span>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-divider />

    <el-row :gutter="16" class="detail-row">
      <el-col :span="6">
        <span class="detail-label">初始资金:</span>
        <span class="detail-value">{{ symbol }}{{ formatMoney(summary?.initial_capital?.[currency] || 0) }}</span>
      </el-col>
      <el-col :span="6">
        <span class="detail-label">累计入金:</span>
        <span class="detail-value">{{ symbol }}{{ formatMoney(summary?.total_deposit?.[currency] || 0) }}</span>
      </el-col>
      <el-col :span="6">
        <span class="detail-label">累计出金:</span>
        <span class="detail-value">{{ symbol }}{{ formatMoney(summary?.total_withdraw?.[currency] || 0) }}</span>
      </el-col>
      <el-col :span="6">
        <span class="detail-label">净入金:</span>
        <span class="detail-value">{{ symbol }}{{ formatMoney(summary?.net_capital?.[currency] || 0) }}</span>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AccountSummary } from '@/api/portfolio'

const props = defineProps<{
  summary: AccountSummary | null
  currency: 'CNY' | 'HKD' | 'USD'
  symbol: string
}>()

const emit = defineEmits<{
  (e: 'deposit'): void
  (e: 'withdraw'): void
}>()

const formatMoney = (val: number) => {
  return val.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const profit = computed(() => props.summary?.profit?.[props.currency] || 0)
const profitPct = computed(() => props.summary?.profit_pct?.[props.currency] || 0)
const profitClass = computed(() => profit.value >= 0 ? 'profit' : 'loss')
const profitPrefix = computed(() => profit.value >= 0 ? '+' : '-')
const profitPctPrefix = computed(() => profitPct.value >= 0 ? '+' : '')
</script>

<style scoped>
.currency-account {
  padding: 12px 0;
}

.stat-item {
  text-align: center;
}

.stat-item .label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.stat-item .value {
  font-size: 18px;
  font-weight: bold;
  color: #303133;
}

.stat-item .value.profit {
  color: #f56c6c; /* 红色表示盈利（中国股市规范） */
}

.stat-item .value.loss {
  color: #67c23a; /* 绿色表示亏损（中国股市规范） */
}

.stat-item .pct {
  font-size: 12px;
  font-weight: normal;
}

.detail-row {
  font-size: 13px;
}

.detail-label {
  color: #909399;
}

.detail-value {
  color: #606266;
  margin-left: 4px;
}
</style>

