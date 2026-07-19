<template>
  <div class="kpi-cards">
    <el-card class="kpi-card" shadow="hover">
      <div class="kpi-content">
        <div class="kpi-icon today">
          <el-icon><Calendar /></el-icon>
        </div>
        <div class="kpi-info">
          <div class="kpi-label">今日任务</div>
          <div class="kpi-value">{{ todayStats.completed }}<span class="kpi-divider">/{{ todayStats.total }}</span></div>
          <div class="kpi-sub" v-if="todayStats.running > 0">
            <el-icon class="running-icon"><Loading /></el-icon>
            {{ todayStats.running }} 个进行中
          </div>
          <div class="kpi-sub" v-else>暂无进行中任务</div>
        </div>
      </div>
    </el-card>

    <el-card class="kpi-card" shadow="hover">
      <div class="kpi-content">
        <div class="kpi-icon week">
          <el-icon><DataAnalysis /></el-icon>
        </div>
        <div class="kpi-info">
          <div class="kpi-label">本周分析</div>
          <div class="kpi-value">{{ weekStats.total }}<span class="kpi-unit">次</span></div>
          <div class="kpi-sub">成功率 {{ weekStats.successRate }}%</div>
        </div>
      </div>
    </el-card>

    <el-card class="kpi-card kpi-card-clickable" shadow="hover" @click="$emit('go-paper')">
      <div class="kpi-content">
        <div class="kpi-icon profit">
          <el-icon><Wallet /></el-icon>
        </div>
        <div class="kpi-info">
          <div class="kpi-label">模拟交易总资产</div>
          <div class="kpi-value" v-if="paperAccount">¥{{ formatMoney(getAmount(paperAccount.equity)) }}</div>
          <div class="kpi-value kpi-placeholder" v-else>—</div>
          <div class="kpi-sub" v-if="paperAccount && hasPnl">
            持仓市值 ¥{{ formatMoney(getAmount(paperAccount.positions_value)) }}
          </div>
          <div class="kpi-sub kpi-action" v-else-if="paperAccount">查看账户详情 →</div>
          <div class="kpi-sub kpi-action" v-else>前往开通 →</div>
        </div>
        <el-icon class="kpi-card-arrow"><ArrowRight /></el-icon>
      </div>
    </el-card>

    <el-card class="kpi-card" shadow="hover">
      <div class="kpi-content">
        <div class="kpi-icon tokens">
          <el-icon><Coin /></el-icon>
        </div>
        <div class="kpi-info">
          <div class="kpi-label">本周 Token 用量</div>
          <div class="kpi-value" v-if="tokenStats.total > 0">{{ formatToken(tokenStats.total) }}</div>
          <div class="kpi-value kpi-placeholder" v-else>—</div>
          <div class="kpi-sub">{{ tokenStats.requests }} 次调用</div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Calendar, DataAnalysis, Wallet, Coin, Loading, ArrowRight } from '@element-plus/icons-vue'
import { paperApi, type PaperAccountSummary } from '@/api/paper'
import { getUsageStatistics } from '@/api/usage'

interface Props {
  recentTasks?: any[]
}

const props = withDefaults(defineProps<Props>(), {
  recentTasks: () => []
})

defineEmits<{
  (e: 'go-paper'): void
}>()

const paperAccount = ref<PaperAccountSummary | null>(null)
const tokenStats = ref({ total: 0, requests: 0 })

// 今日任务统计（基于传入的任务列表）
const todayStats = computed(() => {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const todayStart = today.getTime()

  const todayTasks = props.recentTasks.filter((t: any) => {
    // unifiedTasks 返回 started_at/created_at（字符串，含时区），兼容旧版 start_time
    const ts = new Date(t.started_at || t.start_time || t.created_at || '').getTime()
    return ts >= todayStart
  })

  return {
    total: todayTasks.length,
    completed: todayTasks.filter((t: any) => t.status === 'completed').length,
    running: todayTasks.filter((t: any) =>
      ['running', 'processing', 'pending'].includes(t.status)
    ).length
  }
})

// 本周分析统计
const weekStats = computed(() => {
  const now = new Date()
  const weekStart = new Date(now)
  weekStart.setDate(now.getDate() - 6) // 含今天共 7 天
  weekStart.setHours(0, 0, 0, 0)
  const weekStartTs = weekStart.getTime()

  const weekTasks = props.recentTasks.filter((t: any) => {
    const ts = new Date(t.started_at || t.start_time || t.created_at || '').getTime()
    return ts >= weekStartTs
  })

  const total = weekTasks.length
  const success = weekTasks.filter((t: any) => t.status === 'completed').length
  const successRate = total > 0 ? Math.round((success / total) * 100) : 0

  return { total, successRate }
})

const hasPnl = computed(() => {
  if (!paperAccount.value) return false
  const posValue = getAmount(paperAccount.value.positions_value)
  return posValue > 0
})

const getAmount = (value: number | { CNY: number } | undefined): number => {
  if (typeof value === 'number') return value
  return value?.CNY ?? 0
}

const formatMoney = (value: number) => {
  if (!value || Number.isNaN(value)) return '0.00'
  return value.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}

const formatToken = (value: number) => {
  if (value >= 1000000) return (value / 1000000).toFixed(1) + 'M'
  if (value >= 1000) return (value / 1000).toFixed(1) + 'K'
  return String(value)
}

const loadPaperAccount = async () => {
  try {
    const response = await paperApi.getAccount()
    if (response.success && response.data) {
      paperAccount.value = response.data.account
    }
  } catch (error) {
    console.error('加载模拟交易账户失败:', error)
  }
}

const loadTokenStats = async () => {
  try {
    const resp = await getUsageStatistics({ days: 7 })
    // 兼容不同返回结构
    const data: any = (resp as any)?.data?.data || (resp as any)?.data || resp || {}
    tokenStats.value = {
      total: (data.total_input_tokens || 0) + (data.total_output_tokens || 0),
      requests: data.total_requests || 0
    }
  } catch (error) {
    console.error('加载 Token 用量失败:', error)
    tokenStats.value = { total: 0, requests: 0 }
  }
}

onMounted(() => {
  loadPaperAccount()
  loadTokenStats()
})
</script>

<style lang="scss" scoped>
.kpi-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.kpi-card {
  :deep(.el-card__body) {
    padding: 18px 20px;
  }
}

// 可点击的 KPI 卡片（如"模拟交易总资产"，整卡跳转）
.kpi-card-clickable {
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08);

    :deep(.el-card__body) {
      background-color: var(--el-color-primary-light-9);
    }

    .kpi-icon.profit {
      background-color: rgba(230, 162, 60, 0.18);
    }

    .kpi-card-arrow {
      transform: translateX(4px);
      color: var(--el-color-primary);
      opacity: 1;
    }
  }
}

// 卡片右下角箭头（hover 时显示）
.kpi-card-arrow {
  position: absolute;
  right: 16px;
  bottom: 14px;
  font-size: 14px;
  color: var(--el-text-color-placeholder);
  opacity: 0.6;
  transition: all 0.2s ease;
}

.kpi-content {
  display: flex;
  align-items: center;
  gap: 14px;
}

.kpi-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  flex-shrink: 0;

  &.today {
    background: rgba(64, 158, 255, 0.1);
    color: #409eff;
  }

  &.week {
    background: rgba(103, 194, 58, 0.1);
    color: #67c23a;
  }

  &.profit {
    background: rgba(230, 162, 60, 0.1);
    color: #e6a23c;
  }

  &.tokens {
    background: rgba(144, 147, 153, 0.1);
    color: #909399;
  }
}

.kpi-info {
  flex: 1;
  min-width: 0;
}

.kpi-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
}

.kpi-value {
  font-size: 22px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  line-height: 1.2;

  &.kpi-placeholder {
    color: var(--el-text-color-placeholder);
  }

  .kpi-divider {
    font-size: 14px;
    color: var(--el-text-color-secondary);
    font-weight: 400;
    margin-left: 2px;
  }

  .kpi-unit {
    font-size: 13px;
    color: var(--el-text-color-secondary);
    font-weight: 400;
    margin-left: 4px;
  }
}

.kpi-sub {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
  display: flex;
  align-items: center;
  gap: 4px;

  .running-icon {
    animation: rotating 1.5s linear infinite;
  }

  &.kpi-action {
    color: var(--el-color-primary);
    cursor: pointer;

    &:hover {
      text-decoration: underline;
    }
  }
}

@keyframes rotating {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@media (max-width: 1200px) {
  .kpi-cards {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 640px) {
  .kpi-cards {
    grid-template-columns: 1fr;
  }
}
</style>
