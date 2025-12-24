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
          <h4>入场信号</h4>
          <el-button size="small" @click="addRule('entry_signals')">
            <el-icon><Plus /></el-icon> 添加
          </el-button>
        </div>
        <div v-for="(item, index) in modelValue.entry_signals" :key="index" class="rule-row">
          <el-input v-model="item.condition" placeholder="例如：股价突破20日均线且成交量放大" class="rule-input" />
          <el-input v-model="item.description" placeholder="说明这个信号的意义" class="desc-input" />
          <el-button type="danger" text @click="removeRule('entry_signals', index)">
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
              <el-select v-model="modelValue.stop_loss.type" placeholder="选择止损方式">
                <el-option label="固定比例止损" value="percentage" />
                <el-option label="技术位止损" value="technical" />
                <el-option label="ATR止损" value="atr" />
              </el-select>
            </el-form-item>
            <el-form-item v-if="modelValue.stop_loss.type === 'percentage'" label="止损比例">
              <el-slider v-model="stopLossPercent" :format-tooltip="(val: number) => `${val}%`" :max="30" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="止盈类型">
              <el-select v-model="modelValue.take_profit.type" placeholder="选择止盈方式">
                <el-option label="固定比例止盈" value="percentage" />
                <el-option label="移动止盈" value="trailing" />
                <el-option label="分批止盈" value="scaled" />
              </el-select>
            </el-form-item>
            <el-form-item v-if="modelValue.take_profit.type === 'percentage'" label="止盈比例">
              <el-slider v-model="takeProfitPercent" :format-tooltip="(val: number) => `${val}%`" :max="100" />
            </el-form-item>
          </el-col>
        </el-row>
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
import { computed } from 'vue'
import { Plus, Delete } from '@element-plus/icons-vue'

const props = defineProps<{
  modelValue: any
  type: string
}>()

const emit = defineEmits(['update:modelValue'])

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

// 添加规则
function addRule(field: string) {
  const newValue = { ...props.modelValue }
  if (!newValue[field]) {
    newValue[field] = []
  }
  newValue[field].push({ rule: '', description: '', condition: '' })
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
</style>

