<template>
  <div class="rule-display">
    <!-- 空状态 -->
    <el-empty v-if="!rule || isEmpty(rule)" description="暂未设置规则" :image-size="60" />

    <!-- 选股规则 -->
    <template v-else-if="type === 'stock_selection'">
      <div v-if="rule.must_have?.length" class="rule-group">
        <h4 class="rule-title">必须满足条件</h4>
        <RuleItem v-for="(item, index) in rule.must_have" :key="index" :item="item" type="must" />
      </div>
      <div v-if="rule.exclude?.length" class="rule-group">
        <h4 class="rule-title">排除条件</h4>
        <RuleItem v-for="(item, index) in rule.exclude" :key="index" :item="item" type="exclude" />
      </div>
      <div v-if="rule.bonus?.length" class="rule-group">
        <h4 class="rule-title">加分条件</h4>
        <RuleItem v-for="(item, index) in rule.bonus" :key="index" :item="item" type="bonus" />
      </div>
    </template>

    <!-- 择时规则 -->
    <template v-else-if="type === 'timing'">
      <div v-if="rule.market_condition" class="rule-group">
        <h4 class="rule-title">市场条件</h4>
        <ConditionDisplay :condition="rule.market_condition" />
      </div>
      <div v-if="rule.entry_signals?.length" class="rule-group">
        <h4 class="rule-title">入场信号</h4>
        <RuleItem v-for="(item, index) in rule.entry_signals" :key="index" :item="item" type="signal" />
      </div>
      <div v-if="rule.confirmation?.length" class="rule-group">
        <h4 class="rule-title">确认条件</h4>
        <RuleItem v-for="(item, index) in rule.confirmation" :key="index" :item="item" type="must" />
      </div>
    </template>

    <!-- 仓位规则 -->
    <template v-else-if="type === 'position'">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="单只仓位上限">
          {{ formatPercent(rule.max_per_stock) }}
        </el-descriptions-item>
        <el-descriptions-item label="最大持股数">
          {{ rule.max_holdings || '-' }} 只
        </el-descriptions-item>
        <el-descriptions-item label="最小持股数">
          {{ rule.min_holdings || '-' }} 只
        </el-descriptions-item>
      </el-descriptions>
      <div v-if="rule.total_position" class="rule-group mt-3">
        <h4 class="rule-title">总仓位配置</h4>
        <ConditionDisplay :condition="rule.total_position" />
      </div>
    </template>

    <!-- 持仓规则 -->
    <template v-else-if="type === 'holding'">
      <div v-if="rule.review_frequency" class="rule-group">
        <el-tag>检查频率：{{ getFrequencyLabel(rule.review_frequency) }}</el-tag>
      </div>
      <div v-if="rule.add_conditions?.length" class="rule-group">
        <h4 class="rule-title">加仓条件</h4>
        <RuleItem v-for="(item, index) in rule.add_conditions" :key="index" :item="item" type="add" />
      </div>
      <div v-if="rule.reduce_conditions?.length" class="rule-group">
        <h4 class="rule-title">减仓条件</h4>
        <RuleItem v-for="(item, index) in rule.reduce_conditions" :key="index" :item="item" type="reduce" />
      </div>
    </template>

    <!-- 风险管理规则 -->
    <template v-else-if="type === 'risk_management'">
      <div v-if="rule.stop_loss" class="rule-group">
        <h4 class="rule-title">止损设置</h4>
        <div class="risk-summary-card">
          <div class="risk-summary-row">
            <span class="risk-summary-label">类型：</span>
            <span class="risk-summary-value">{{ getStopLossTypeLabel(rule.stop_loss?.type) }}</span>
          </div>
          <div v-if="getStopLossSummary(rule.stop_loss)" class="risk-summary-row">
            <span class="risk-summary-label">条件：</span>
            <span class="risk-summary-value">{{ getStopLossSummary(rule.stop_loss) }}</span>
          </div>
        </div>
      </div>
      <div v-if="rule.take_profit" class="rule-group">
        <h4 class="rule-title">止盈设置</h4>
        <div class="risk-summary-card">
          <div class="risk-summary-row">
            <span class="risk-summary-label">类型：</span>
            <span class="risk-summary-value">{{ getTakeProfitTypeLabel(rule.take_profit?.type) }}</span>
          </div>
          <div v-if="getTakeProfitSummary(rule.take_profit)" class="risk-summary-row">
            <span class="risk-summary-label">规则：</span>
            <span class="risk-summary-value">{{ getTakeProfitSummary(rule.take_profit) }}</span>
          </div>
        </div>
      </div>
      <div v-if="rule.time_stop" class="rule-group">
        <h4 class="rule-title">时间止损</h4>
        <div class="risk-summary-card">
          <div class="risk-summary-row">
            <span class="risk-summary-label">启用：</span>
            <span class="risk-summary-value">{{ rule.time_stop?.enabled ? '是' : '否' }}</span>
          </div>
          <div v-if="rule.time_stop?.enabled" class="risk-summary-row">
            <span class="risk-summary-label">最大持有天数：</span>
            <span class="risk-summary-value">{{ rule.time_stop?.max_holding_days || '-' }} 天</span>
          </div>
        </div>
      </div>
    </template>

    <!-- 复盘规则 -->
    <template v-else-if="type === 'review'">
      <div v-if="rule.frequency" class="rule-group">
        <el-tag>复盘频率：{{ getFrequencyLabel(rule.frequency) }}</el-tag>
      </div>
      <div v-if="rule.checklist?.length" class="rule-group">
        <h4 class="rule-title">复盘检查项</h4>
        <ul class="checklist">
          <li v-for="(item, index) in rule.checklist" :key="index">
            <el-icon><Check /></el-icon>
            {{ item }}
          </li>
        </ul>
      </div>
    </template>

    <!-- 纪律规则 -->
    <template v-else-if="type === 'discipline'">
      <div v-if="rule.must_do?.length" class="rule-group">
        <h4 class="rule-title success">
          <el-icon><CircleCheck /></el-icon>
          必须做到
        </h4>
        <RuleItem v-for="(item, index) in rule.must_do" :key="index" :item="item" type="must" />
      </div>
      <div v-if="rule.must_not?.length" class="rule-group">
        <h4 class="rule-title danger">
          <el-icon><CircleClose /></el-icon>
          绝对禁止
        </h4>
        <RuleItem v-for="(item, index) in rule.must_not" :key="index" :item="item" type="forbid" />
      </div>
    </template>

    <!-- 通用显示 -->
    <template v-else>
      <pre class="json-display">{{ JSON.stringify(rule, null, 2) }}</pre>
    </template>
  </div>
</template>

<script setup lang="ts">
import { Check, CircleCheck, CircleClose } from '@element-plus/icons-vue'
import RuleItem from './RuleItem.vue'
import ConditionDisplay from './ConditionDisplay.vue'

defineProps<{
  rule: any
  type: string
}>()

function isEmpty(obj: any): boolean {
  if (!obj) return true
  if (typeof obj !== 'object') return false
  return Object.keys(obj).every(key => {
    const value = obj[key]
    if (Array.isArray(value)) return value.length === 0
    if (typeof value === 'object') return isEmpty(value)
    return !value
  })
}

function formatPercent(value: number | undefined): string {
  if (value === undefined || value === null) return '-'
  return `${(value * 100).toFixed(0)}%`
}

function getFrequencyLabel(frequency: string): string {
  const map: Record<string, string> = {
    'daily': '每日',
    'weekly': '每周',
    'monthly': '每月',
    'quarterly': '每季度',
    'yearly': '每年'
  }
  return map[frequency] || frequency
}

function toPercentText(value: number | undefined, digits = 1): string {
  if (value === undefined || value === null || Number.isNaN(Number(value))) return '-'
  return `${(Number(value) * 100).toFixed(digits)}%`
}

function getStopLossTypeLabel(type: string | undefined): string {
  const map: Record<string, string> = {
    percentage: '固定比例',
    technical: '技术位止损',
    atr: 'ATR 止损'
  }
  return map[type || ''] || (type || '-')
}

function getTakeProfitTypeLabel(type: string | undefined): string {
  const map: Record<string, string> = {
    percentage: '固定比例',
    trailing: '移动止盈',
    scaled: '分批止盈'
  }
  return map[type || ''] || (type || '-')
}

function getStopLossSummary(stopLoss: any): string {
  if (!stopLoss) return ''
  if (stopLoss.type === 'technical') {
    return stopLoss.description || '-'
  }
  if (stopLoss.type === 'atr') {
    return `跌破 ${stopLoss.atr_multiplier ?? 2.0} 倍 ATR 止损`
  }
  return `亏损达到 ${toPercentText(stopLoss.percentage)} 时止损`
}

function getTakeProfitSummary(takeProfit: any): string {
  if (!takeProfit) return ''
  if (takeProfit.type === 'trailing') {
    return `盈利达到 ${toPercentText(takeProfit.activation_profit_pct)} 后启动，较高点回撤 ${toPercentText(takeProfit.trailing_pullback_pct)} 止盈，参考 ${takeProfit.reference || 'highest_price'}`
  }
  if (takeProfit.type === 'scaled') {
    const levels = Array.isArray(takeProfit.levels) ? takeProfit.levels : []
    if (!levels.length) return '未设置分批止盈档位'
    return levels
      .map((item: any, index: number) => `第 ${index + 1} 档：盈利 ${toPercentText(item?.target_profit_pct)} 时卖出 ${toPercentText(item?.sell_ratio)}`)
      .join('；')
  }
  return `盈利达到 ${toPercentText(takeProfit.percentage)} 时止盈`
}
</script>

<style scoped lang="scss">
.rule-display {
  min-height: 100px;
}

.rule-group {
  margin-bottom: 16px;

  &:last-child {
    margin-bottom: 0;
  }
}

.rule-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 0 0 8px;
  display: flex;
  align-items: center;
  gap: 4px;

  &.success {
    color: var(--el-color-success);
  }

  &.danger {
    color: var(--el-color-danger);
  }
}

.mt-3 {
  margin-top: 12px;
}

.risk-summary-card {
  background: var(--el-fill-color-light);
  padding: 12px;
  border-radius: 6px;
}

.risk-summary-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px dashed var(--el-border-color-lighter);

  &:first-child {
    padding-top: 0;
  }

  &:last-child {
    padding-bottom: 0;
    border-bottom: none;
  }
}

.risk-summary-label {
  min-width: 72px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  flex-shrink: 0;
}

.risk-summary-value {
  color: var(--el-text-color-primary);
  font-size: 14px;
  line-height: 1.6;
}

.checklist {
  margin: 0;
  padding: 0;
  list-style: none;

  li {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background: var(--el-fill-color-light);
    border-radius: 4px;
    margin-bottom: 8px;
    font-size: 14px;

    .el-icon {
      color: var(--el-color-success);
    }
  }
}

.json-display {
  background: var(--el-fill-color-light);
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  overflow: auto;
  max-height: 300px;
}
</style>

