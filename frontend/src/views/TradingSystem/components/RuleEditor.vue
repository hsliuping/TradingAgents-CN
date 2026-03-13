<template>
  <div class="rule-editor">
    <!-- 选股规则编辑 -->
    <template v-if="type === 'stock_selection'">
      <!-- 引导说明 -->
      <el-alert
        title="选股规则说明"
        type="info"
        :closable="false"
        class="guide-alert"
      >
        <p>定义您的选股标准，系统会在复盘时检查是否符合这些条件。</p>
        <div class="examples">
          <p><strong>示例：</strong></p>
          <ul>
            <li><strong>必须满足：</strong>市值 > 50亿、流通盘 > 10亿、近3日成交额 > 1亿</li>
            <li><strong>排除条件：</strong>ST股票、次新股（上市不足1年）、连续跌停</li>
          </ul>
        </div>
      </el-alert>

      <div class="rule-section">
        <div class="section-header">
          <h4>必须满足条件</h4>
          <el-button size="small" @click="addRule('must_have')">
            <el-icon><Plus /></el-icon> 添加
          </el-button>
        </div>
        <div v-for="(item, index) in modelValue.must_have" :key="index" class="rule-row">
          <el-input v-model="item.rule" placeholder="例如：市值 > 50亿" class="rule-input" />
          <el-input v-model="item.description" placeholder="说明为什么需要这个条件" class="desc-input" />
          <el-button type="danger" text @click="removeRule('must_have', index)">
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
      </div>
      <div class="rule-section">
        <div class="section-header">
          <h4>排除条件</h4>
          <el-button size="small" @click="addRule('exclude')">
            <el-icon><Plus /></el-icon> 添加
          </el-button>
        </div>
        <div v-for="(item, index) in modelValue.exclude" :key="index" class="rule-row">
          <el-input v-model="item.rule" placeholder="例如：ST股票、次新股" class="rule-input" />
          <el-input v-model="item.description" placeholder="说明为什么要排除" class="desc-input" />
          <el-button type="danger" text @click="removeRule('exclude', index)">
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
      </div>
      <div class="rule-section">
        <div class="section-header">
          <h4>加分条件</h4>
          <el-button size="small" @click="addRule('bonus')">
            <el-icon><Plus /></el-icon> 添加
          </el-button>
        </div>
        <div v-for="(item, index) in modelValue.bonus" :key="index" class="rule-row">
          <el-input v-model="item.rule" placeholder="例如：机构持续加仓、行业景气度上行" class="rule-input" />
          <el-input v-model="item.description" placeholder="说明为什么这是加分项" class="desc-input" />
          <el-button type="danger" text @click="removeRule('bonus', index)">
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
      </div>
    </template>

    <!-- 择时规则编辑 -->
    <template v-else-if="type === 'timing'">
      <!-- 引导说明 -->
      <el-alert
        title="择时规则说明"
        type="info"
        :closable="false"
        class="guide-alert"
      >
        <p>定义您的入场时机，明确什么情况下可以买入。</p>
        <div class="examples">
          <p><strong>示例：</strong></p>
          <ul>
            <li><strong>市场环境：</strong>大盘处于上升趋势（MA20 > MA60）</li>
            <li><strong>技术信号：</strong>股价突破前期高点、MACD金叉、成交量放大</li>
            <li><strong>确认条件：</strong>连续3日收阳、突破后回踩不破支撑</li>
          </ul>
        </div>
      </el-alert>

      <div class="rule-section">
        <div class="section-header">
          <h4>市场环境</h4>
        </div>
        <div class="rule-row timing-row">
          <el-input v-model="modelValue.market_condition.rule" placeholder="例如：市场环境" class="rule-input" />
          <el-input
            v-model="modelValue.market_condition.description"
            type="textarea"
            :rows="2"
            :autosize="{ minRows: 2, maxRows: 4 }"
            placeholder="例如：指数站上20日均线且成交额回升，涨跌家数明显改善"
            class="desc-input"
          />
          <div class="row-action-placeholder"></div>
        </div>
      </div>

      <div class="rule-section">
        <div class="section-header">
          <h4>入场信号</h4>
          <el-button size="small" @click="addRule('entry_signals')">
            <el-icon><Plus /></el-icon> 添加
          </el-button>
        </div>
        <div class="rule-row rule-row-header">
          <div class="rule-input">信号类型/条件名</div>
          <div class="desc-input">具体触发条件</div>
          <div class="row-action-placeholder"></div>
        </div>
        <div v-for="(item, index) in modelValue.entry_signals" :key="index" class="rule-row timing-row">
          <el-input v-model="item.signal" placeholder="例如：市场环境、技术位置、资金认可" class="rule-input" />
          <el-input
            v-model="item.condition"
            type="textarea"
            :rows="2"
            :autosize="{ minRows: 2, maxRows: 5 }"
            placeholder="例如：股价突破20日均线且成交量放大，回踩不破并出现放量阳线"
            class="desc-input"
          />
          <el-button type="danger" text @click="removeRule('entry_signals', index)">
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
      </div>

      <div class="rule-section">
        <div class="section-header">
          <h4>确认条件</h4>
          <el-button size="small" @click="addRule('confirmation')">
            <el-icon><Plus /></el-icon> 添加
          </el-button>
        </div>
        <div v-for="(item, index) in modelValue.confirmation" :key="index" class="rule-row timing-row">
          <el-input v-model="item.rule" placeholder="例如：放量确认、回踩不破" class="rule-input" />
          <el-input
            v-model="item.description"
            type="textarea"
            :rows="2"
            :autosize="{ minRows: 2, maxRows: 4 }"
            placeholder="例如：突破后1-2日内回踩关键位不破，且量能维持在均量以上"
            class="desc-input"
          />
          <el-button type="danger" text @click="removeRule('confirmation', index)">
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
      </div>
    </template>

    <!-- 风险管理规则编辑 -->
    <template v-else-if="type === 'risk_management'">
      <!-- 引导说明 -->
      <el-alert
        title="风险管理说明"
        type="warning"
        :closable="false"
        class="guide-alert"
      >
        <p>设置止损和止盈规则，保护您的资金安全。</p>
        <div class="examples">
          <p><strong>建议：</strong></p>
          <ul>
            <li><strong>止损：</strong>短线 5-8%，中线 10-15%，长线 20-25%</li>
            <li><strong>止盈：</strong>可以使用移动止盈（如跌破5日线）或分批止盈（涨20%卖1/3，涨40%卖1/3）</li>
            <li><strong>盈亏比：</strong>建议至少 1:2（止损10%，止盈至少20%）</li>
          </ul>
        </div>
      </el-alert>

      <el-form label-width="100px" label-position="top">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="止损类型">
              <el-select v-model="modelValue.stop_loss.type" placeholder="选择止损方式" @change="handleStopLossTypeChange">
                <el-option label="固定比例止损" value="percentage" />
                <el-option label="技术位止损" value="technical" />
                <el-option label="ATR止损" value="atr" />
              </el-select>
            </el-form-item>
            <el-form-item v-if="modelValue.stop_loss.type === 'percentage'" label="止损比例">
              <div class="slider-with-value">
                <el-slider v-model="stopLossPercent" :format-tooltip="(val: number) => `${val}%`" :max="30" />
                <span class="slider-value">{{ stopLossPercent }}%</span>
              </div>
            </el-form-item>
            <el-form-item v-if="modelValue.stop_loss.type === 'technical'" label="技术位说明">
              <el-input
                v-model="modelValue.stop_loss.description"
                type="textarea"
                :rows="2"
                placeholder="例如：跌破20日均线且收盘确认，次日开盘执行止损"
              />
            </el-form-item>
            <el-form-item v-if="modelValue.stop_loss.type === 'atr'" label="ATR倍数">
              <el-input-number v-model="modelValue.stop_loss.atr_multiplier" :min="0.5" :max="5" :step="0.1" :precision="1" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="止盈类型">
              <el-select v-model="modelValue.take_profit.type" placeholder="选择止盈方式" @change="handleTakeProfitTypeChange">
                <el-option label="固定比例止盈" value="percentage" />
                <el-option label="移动止盈" value="trailing" />
                <el-option label="分批止盈" value="scaled" />
              </el-select>
            </el-form-item>
            <el-form-item v-if="modelValue.take_profit.type === 'percentage'" label="止盈比例">
              <div class="slider-with-value">
                <el-slider v-model="takeProfitPercent" :format-tooltip="(val: number) => `${val}%`" :max="100" />
                <span class="slider-value">{{ takeProfitPercent }}%</span>
              </div>
            </el-form-item>
            <template v-if="modelValue.take_profit.type === 'trailing'">
              <el-form-item label="回撤触发比例">
                <div class="slider-with-value">
                  <el-slider v-model="trailingPullbackPercent" :format-tooltip="(val: number) => `${val}%`" :min="1" :max="20" />
                  <span class="slider-value">{{ trailingPullbackPercent }}%</span>
                </div>
              </el-form-item>
              <el-form-item label="激活条件（盈利达到）">
                <el-input-number v-model="trailingActivationPercent" :min="0" :max="80" :step="1" />
                <span class="inline-unit">%</span>
              </el-form-item>
              <el-form-item label="跟踪基准">
                <el-select v-model="modelValue.take_profit.reference" placeholder="选择跟踪基准">
                  <el-option label="最高价回撤" value="highest_price" />
                  <el-option label="5日均线" value="ma5" />
                  <el-option label="10日均线" value="ma10" />
                  <el-option label="ATR跟踪" value="atr" />
                </el-select>
              </el-form-item>
            </template>
            <template v-if="modelValue.take_profit.type === 'scaled'">
              <el-form-item label="分批止盈规则">
                <div class="dynamic-list">
                  <el-alert
                    :type="scaledSellRatioExceed ? 'error' : 'success'"
                    :closable="false"
                    class="ratio-alert"
                  >
                    总卖出比例：{{ (scaledSellRatioTotal * 100).toFixed(1) }}%
                    <span v-if="scaledSellRatioExceed">（请调整到100%以内）</span>
                  </el-alert>
                  <div v-for="(level, index) in modelValue.take_profit.levels" :key="index" class="dynamic-row">
                    <el-input-number
                      :model-value="toPercent(level.target_profit_pct)"
                      @update:model-value="(val) => updateScaledLevel(index, 'target_profit_pct', fromPercent(val))"
                      :min="1"
                      :max="300"
                      :step="1"
                    />
                    <span class="inline-unit">% 盈利时</span>
                    <el-input-number
                      :model-value="toPercent(level.sell_ratio)"
                      @update:model-value="(val) => updateScaledLevel(index, 'sell_ratio', fromPercent(val))"
                      :min="1"
                      :max="100"
                      :step="1"
                    />
                    <span class="inline-unit">% 仓位</span>
                    <el-button type="danger" text @click="removeScaledLevel(index)">
                      <el-icon><Delete /></el-icon>
                    </el-button>
                  </div>
                  <el-button size="small" @click="addScaledLevel">
                    <el-icon><Plus /></el-icon> 添加分段
                  </el-button>
                </div>
              </el-form-item>
            </template>
          </el-col>
        </el-row>
        <el-divider content-position="left">时间止损</el-divider>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="是否启用时间止损">
              <el-switch v-model="modelValue.time_stop.enabled" />
            </el-form-item>
          </el-col>
          <el-col :span="12" v-if="modelValue.time_stop.enabled">
            <el-form-item label="最大持有天数">
              <el-input-number v-model="modelValue.time_stop.max_holding_days" :min="1" :max="365" :step="1" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-divider content-position="left">逻辑止损</el-divider>
        <el-form-item label="逻辑止损条件">
          <div class="dynamic-list">
            <div v-for="(condition, index) in modelValue.logical_stop.conditions" :key="index" class="dynamic-row">
              <el-input
                :model-value="condition"
                @update:model-value="(val) => updateLogicalCondition(index, val)"
                placeholder="例如：业绩预告低于预期且跌破季线"
                class="desc-input"
              />
              <el-button type="danger" text @click="removeLogicalCondition(index)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
            <el-button size="small" @click="addLogicalCondition">
              <el-icon><Plus /></el-icon> 添加逻辑条件
            </el-button>
          </div>
        </el-form-item>
      </el-form>
    </template>

    <!-- 纪律规则编辑 -->
    <template v-else-if="type === 'discipline'">
      <!-- 引导说明 -->
      <el-alert
        title="交易纪律说明"
        type="error"
        :closable="false"
        class="guide-alert"
      >
        <p>明确您的交易纪律，这是交易计划的灵魂。</p>
        <div class="examples">
          <p><strong>示例：</strong></p>
          <ul>
            <li><strong>必须做到：</strong>严格执行止损、每次交易前检查选股条件、盈利后及时复盘总结</li>
            <li><strong>严禁操作：</strong>追涨杀跌、重仓单只股票、频繁交易、情绪化交易</li>
            <li><strong>违规处理：</strong>暂停交易1周、减少仓位、强制复盘</li>
          </ul>
        </div>
      </el-alert>

      <div class="rule-section">
        <div class="section-header success">
          <h4>✅ 必须做到</h4>
          <el-button size="small" @click="addRule('must_do')">
            <el-icon><Plus /></el-icon> 添加
          </el-button>
        </div>
        <div v-for="(item, index) in modelValue.must_do" :key="index" class="rule-row">
          <el-input v-model="item.rule" placeholder="例如：严格执行止损、每次交易前检查选股条件" class="rule-input" />
          <el-input v-model="item.description" placeholder="详细描述" class="desc-input" />
          <el-button type="danger" text @click="removeRule('must_do', index)">
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
      </div>
      <div class="rule-section">
        <div class="section-header danger">
          <h4>🚫 绝对禁止</h4>
          <el-button size="small" @click="addRule('must_not')">
            <el-icon><Plus /></el-icon> 添加
          </el-button>
        </div>
        <div v-for="(item, index) in modelValue.must_not" :key="index" class="rule-row">
          <el-input v-model="item.rule" placeholder="例如：追涨杀跌、重仓单只股票、频繁交易" class="rule-input" />
          <el-input v-model="item.description" placeholder="说明为什么禁止" class="desc-input" />
          <el-button type="danger" text @click="removeRule('must_not', index)">
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
      </div>
    </template>

    <!-- 默认：JSON编辑 -->
    <template v-else>
      <el-input
        type="textarea"
        :model-value="JSON.stringify(modelValue, null, 2)"
        @update:model-value="handleJsonChange"
        :rows="10"
        placeholder="请输入JSON格式的规则配置"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, watchEffect } from 'vue'
import { Plus, Delete } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  modelValue: any
  type: string
}>()

const emit = defineEmits(['update:modelValue'])

function isLikelyCategoryLabel(text: string): boolean {
  const value = String(text || '').trim()
  if (!value) return false
  if (value.length <= 10 && !/[，,。；;：:]/.test(value)) {
    return true
  }
  const commonLabels = ['市场环境', '技术位置', '技术信号', '动能转强', '催化剂', '资金认可', '确认条件']
  return commonLabels.some(label => value.includes(label))
}

function isLikelyDetailedCondition(text: string): boolean {
  const value = String(text || '').trim()
  if (!value) return false
  if (value.length >= 14) return true
  return /[，,。；;：:]|且|并|突破|回踩|放量|金叉|均线|收盘/.test(value)
}

watchEffect(() => {
  if (props.type === 'timing') {
    const source = props.modelValue || {}
    const entrySignals = Array.isArray(source.entry_signals) ? source.entry_signals : []
    const confirmations = Array.isArray(source.confirmation) ? source.confirmation : []
    const marketCondition = source.market_condition && typeof source.market_condition === 'object'
      ? { ...source.market_condition }
      : { rule: '市场环境', description: '' }
    if (!entrySignals.length) {
      if (!source.market_condition && !confirmations.length) {
        return
      }
    }

    let changed = false
    const nextEntrySignals = entrySignals.map((item: any) => {
      if (!item || typeof item !== 'object') {
        changed = true
        return { signal: '', condition: '' }
      }

      const normalized = { ...item }

      // 兼容旧字段：历史上可能混用 signal/rule/description/condition。
      const signal = String(normalized.signal || '').trim()
      const rule = String(normalized.rule || '').trim()
      const name = String(normalized.name || '').trim()
      const condition = String(normalized.condition || '').trim()
      const description = String(normalized.description || '').trim()

      if (!signal) {
        if (rule) {
          normalized.signal = rule
          changed = true
        } else if (name) {
          normalized.signal = name
          changed = true
        }
      }

      if (!normalized.condition && description) {
        // 第二列优先显示更详细描述，避免“有值但没显示”。
        normalized.condition = description
        changed = true
      }

      if (!normalized.signal && normalized.condition) {
        // 只有一列历史值时，先放第一列，便于用户看见并可继续补充第二列。
        normalized.signal = normalized.condition
        changed = true
      }

      // 兼容“前后列填反”的历史数据：第一列像详细条件、第二列像标签时自动交换。
      if (
        normalized.signal && normalized.condition
        && isLikelyDetailedCondition(normalized.signal)
        && isLikelyCategoryLabel(normalized.condition)
      ) {
        const temp = normalized.signal
        normalized.signal = normalized.condition
        normalized.condition = temp
        changed = true
      }

      if (!normalized.condition) {
        normalized.condition = condition
      }

      if (!('signal' in normalized)) {
        normalized.signal = ''
        changed = true
      }
      if (!('condition' in normalized)) {
        normalized.condition = ''
        changed = true
      }

      return normalized
    })

    const nextConfirmations = confirmations.map((item: any) => {
      if (!item || typeof item !== 'object') {
        changed = true
        return { rule: '', description: '' }
      }

      const normalized = { ...item }
      if (!('rule' in normalized)) {
        normalized.rule = ''
        changed = true
      }
      if (!('description' in normalized)) {
        normalized.description = ''
        changed = true
      }
      return normalized
    })

    if (!marketCondition.rule) {
      marketCondition.rule = '市场环境'
      changed = true
    }
    if (!('description' in marketCondition)) {
      marketCondition.description = ''
      changed = true
    }

    if (changed) {
      emit('update:modelValue', {
        ...source,
        market_condition: marketCondition,
        entry_signals: nextEntrySignals,
        confirmation: nextConfirmations
      })
    }
    return
  }

  if (props.type !== 'risk_management') {
    return
  }

  const source = props.modelValue || {}
  let changed = false
  const nextValue = { ...source }

  if (!nextValue.stop_loss) {
    nextValue.stop_loss = {}
    changed = true
  }
  if (!nextValue.take_profit) {
    nextValue.take_profit = {}
    changed = true
  }
  if (!nextValue.time_stop) {
    nextValue.time_stop = { enabled: false, max_holding_days: 30 }
    changed = true
  }
  if (!nextValue.logical_stop) {
    nextValue.logical_stop = { conditions: [] }
    changed = true
  }
  if (!Array.isArray(nextValue.logical_stop.conditions)) {
    nextValue.logical_stop.conditions = []
    changed = true
  }

  if (!nextValue.stop_loss.type) {
    nextValue.stop_loss = { ...nextValue.stop_loss, type: 'percentage', percentage: nextValue.stop_loss.percentage ?? 0.08 }
    changed = true
  }

  const normalizedStopLoss = sanitizeStopLoss(nextValue.stop_loss)
  if (JSON.stringify(normalizedStopLoss) !== JSON.stringify(nextValue.stop_loss)) {
    nextValue.stop_loss = normalizedStopLoss
    changed = true
  }

  if (!nextValue.take_profit.type) {
    nextValue.take_profit = { ...nextValue.take_profit, type: 'percentage', percentage: nextValue.take_profit.percentage ?? 0.2 }
    changed = true
  }

  const normalizedTakeProfit = sanitizeTakeProfit(nextValue.take_profit)
  if (JSON.stringify(normalizedTakeProfit) !== JSON.stringify(nextValue.take_profit)) {
    nextValue.take_profit = normalizedTakeProfit
    changed = true
  }

  if (changed) {
    emit('update:modelValue', nextValue)
  }
})

function sanitizeStopLoss(stopLoss: Record<string, any> | undefined) {
  const source = stopLoss || {}
  const type = source.type || 'percentage'

  if (type === 'technical') {
    return {
      type,
      description: source.description || ''
    }
  }

  if (type === 'atr') {
    return {
      type,
      atr_multiplier: source.atr_multiplier ?? 2.0
    }
  }

  return {
    type: 'percentage',
    percentage: source.percentage ?? 0.08
  }
}

function sanitizeTakeProfit(takeProfit: Record<string, any> | undefined) {
  const source = takeProfit || {}
  const type = source.type || 'percentage'

  if (type === 'trailing') {
    return {
      type,
      trailing_pullback_pct: source.trailing_pullback_pct ?? 0.08,
      activation_profit_pct: source.activation_profit_pct ?? 0.1,
      reference: source.reference || 'highest_price'
    }
  }

  if (type === 'scaled') {
    return {
      type,
      levels: (Array.isArray(source.levels) && source.levels.length > 0)
        ? source.levels
        : [
            { target_profit_pct: 0.2, sell_ratio: 0.3 },
            { target_profit_pct: 0.35, sell_ratio: 0.3 },
            { target_profit_pct: 0.5, sell_ratio: 0.4 }
          ]
    }
  }

  return {
    type: 'percentage',
    percentage: source.percentage ?? 0.2
  }
}

// 止损止盈百分比
const stopLossPercent = computed({
  get: () => Math.round((props.modelValue.stop_loss?.percentage || 0.08) * 100),
  set: (val: number) => {
    const newValue = { ...props.modelValue }
    newValue.stop_loss = { ...newValue.stop_loss, percentage: val / 100 }
    emit('update:modelValue', newValue)
  }
})

const takeProfitPercent = computed({
  get: () => Math.round((props.modelValue.take_profit?.percentage || 0.2) * 100),
  set: (val: number) => {
    const newValue = { ...props.modelValue }
    newValue.take_profit = { ...newValue.take_profit, percentage: val / 100 }
    emit('update:modelValue', newValue)
  }
})

const trailingPullbackPercent = computed({
  get: () => Math.round((props.modelValue.take_profit?.trailing_pullback_pct || 0.08) * 100),
  set: (val: number) => {
    const newValue = { ...props.modelValue }
    newValue.take_profit = { ...newValue.take_profit, trailing_pullback_pct: val / 100 }
    emit('update:modelValue', newValue)
  }
})

const trailingActivationPercent = computed({
  get: () => Math.round((props.modelValue.take_profit?.activation_profit_pct || 0.1) * 100),
  set: (val: number) => {
    const newValue = { ...props.modelValue }
    newValue.take_profit = { ...newValue.take_profit, activation_profit_pct: val / 100 }
    emit('update:modelValue', newValue)
  }
})

const scaledSellRatioTotal = computed(() => {
  const levels = props.modelValue?.take_profit?.levels
  if (!Array.isArray(levels)) {
    return 0
  }
  return levels.reduce((sum: number, item: any) => sum + Number(item?.sell_ratio || 0), 0)
})

const scaledSellRatioExceed = computed(() => scaledSellRatioTotal.value > 1.0001)

function handleStopLossTypeChange(type: string) {
  const newValue = { ...props.modelValue }
  newValue.stop_loss = sanitizeStopLoss({ ...newValue.stop_loss, type })
  emit('update:modelValue', newValue)
}

function handleTakeProfitTypeChange(type: string) {
  const newValue = { ...props.modelValue }
  newValue.take_profit = sanitizeTakeProfit({ ...newValue.take_profit, type })
  emit('update:modelValue', newValue)
}

function toPercent(value: number): number {
  return Math.round((value || 0) * 100)
}

function fromPercent(value: number | null | undefined): number {
  return Number((Number(value || 0) / 100).toFixed(4))
}

function addScaledLevel() {
  const newValue = { ...props.modelValue }
  const levels = Array.isArray(newValue.take_profit?.levels) ? [...newValue.take_profit.levels] : []
  levels.push({ target_profit_pct: 0.6, sell_ratio: 0.2 })
  newValue.take_profit = { ...newValue.take_profit, levels }
  emit('update:modelValue', newValue)
}

function removeScaledLevel(index: number) {
  const newValue = { ...props.modelValue }
  const levels = Array.isArray(newValue.take_profit?.levels) ? [...newValue.take_profit.levels] : []
  levels.splice(index, 1)
  newValue.take_profit = { ...newValue.take_profit, levels }
  emit('update:modelValue', newValue)
}

function updateScaledLevel(index: number, field: 'target_profit_pct' | 'sell_ratio', value: number) {
  const newValue = { ...props.modelValue }
  const levels = Array.isArray(newValue.take_profit?.levels) ? [...newValue.take_profit.levels] : []
  if (!levels[index]) {
    return
  }
  if (field === 'sell_ratio') {
    const otherTotal = levels.reduce((sum: number, item: any, i: number) => {
      if (i === index) {
        return sum
      }
      return sum + Number(item?.sell_ratio || 0)
    }, 0)
    const maxAllowed = Math.max(0, 1 - otherTotal)
    const safeValue = Math.min(Math.max(0, value), maxAllowed)
    if (safeValue < value) {
      ElMessage.warning('分批止盈总卖出比例不能超过100%，已自动调整')
    }
    levels[index] = { ...levels[index], [field]: safeValue }
  } else {
    levels[index] = { ...levels[index], [field]: value }
  }
  newValue.take_profit = { ...newValue.take_profit, levels }
  emit('update:modelValue', newValue)
}

function addLogicalCondition() {
  const newValue = { ...props.modelValue }
  const conditions = Array.isArray(newValue.logical_stop?.conditions) ? [...newValue.logical_stop.conditions] : []
  conditions.push('')
  newValue.logical_stop = { ...newValue.logical_stop, conditions }
  emit('update:modelValue', newValue)
}

function removeLogicalCondition(index: number) {
  const newValue = { ...props.modelValue }
  const conditions = Array.isArray(newValue.logical_stop?.conditions) ? [...newValue.logical_stop.conditions] : []
  conditions.splice(index, 1)
  newValue.logical_stop = { ...newValue.logical_stop, conditions }
  emit('update:modelValue', newValue)
}

function updateLogicalCondition(index: number, value: string) {
  const newValue = { ...props.modelValue }
  const conditions = Array.isArray(newValue.logical_stop?.conditions) ? [...newValue.logical_stop.conditions] : []
  if (index < 0 || index >= conditions.length) {
    return
  }
  conditions[index] = value
  newValue.logical_stop = { ...newValue.logical_stop, conditions }
  emit('update:modelValue', newValue)
}

// 添加规则
function addRule(field: string) {
  const newValue = { ...props.modelValue }
  if (!newValue[field]) {
    newValue[field] = []
  }
  if (field === 'entry_signals') {
    newValue[field].push({ signal: '', condition: '' })
  } else {
    newValue[field].push({ rule: '', description: '', condition: '' })
  }
  emit('update:modelValue', newValue)
}

// 删除规则
function removeRule(field: string, index: number) {
  const newValue = { ...props.modelValue }
  if (newValue[field]) {
    newValue[field].splice(index, 1)
    emit('update:modelValue', newValue)
  }
}

// JSON变更处理
function handleJsonChange(val: string) {
  try {
    const parsed = JSON.parse(val)
    emit('update:modelValue', parsed)
  } catch {
    // 忽略无效JSON
  }
}
</script>

<style scoped lang="scss">
.rule-editor {
  min-height: 200px;
}

.guide-alert {
  margin-bottom: 24px;

  p {
    margin: 0 0 12px 0;
    font-size: 14px;
  }

  .examples {
    margin-top: 12px;
    padding: 12px;
    background: rgba(255, 255, 255, 0.5);
    border-radius: 4px;

    p {
      margin: 0 0 8px 0;
      font-weight: 600;
    }

    ul {
      margin: 0;
      padding-left: 20px;

      li {
        margin-bottom: 6px;
        line-height: 1.6;

        &:last-child {
          margin-bottom: 0;
        }

        strong {
          color: var(--el-color-primary);
        }
      }
    }
  }
}

.rule-section {
  margin-bottom: 24px;

  &:last-child {
    margin-bottom: 0;
  }
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--el-border-color-lighter);

  h4 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
  }

  &.success h4 {
    color: var(--el-color-success);
  }

  &.danger h4 {
    color: var(--el-color-danger);
  }
}

.rule-row {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
  align-items: center;

  .rule-input {
    flex: 1;
    max-width: 200px;
  }

  .desc-input {
    flex: 2;
  }

  &:last-child {
    margin-bottom: 0;
  }
}

.timing-row {
  align-items: flex-start;

  :deep(.el-textarea) {
    width: 100%;
  }

  .el-button {
    margin-top: 4px;
  }
}

.rule-row-header {
  margin-bottom: 8px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-weight: 600;

  .rule-input,
  .desc-input {
    padding-left: 2px;
  }
}

.row-action-placeholder {
  width: 32px;
  flex-shrink: 0;
}

.dynamic-list {
  width: 100%;
}

.ratio-alert {
  margin-bottom: 8px;
}

.dynamic-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.inline-unit {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.slider-with-value {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  flex: 1;
  min-width: 0;

  :deep(.el-slider) {
    flex: 1;
    width: 100%;
    min-width: 0;
  }
}

.slider-value {
  min-width: 54px;
  text-align: right;
  font-size: 13px;
  font-weight: 600;
  color: var(--el-color-primary);
}
</style>

