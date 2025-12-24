<template>
  <div class="trading-system-create">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <el-button text @click="goBack">
          <el-icon><ArrowLeft /></el-icon>
          返回列表
        </el-button>
        <h1>{{ isEdit ? '编辑交易计划' : '创建交易计划' }}</h1>
      </div>
    </div>

    <!-- 步骤条 -->
    <el-steps :active="currentStep" finish-status="success" align-center class="steps-container">
      <el-step title="基本信息" description="设置系统名称和风格" />
      <el-step title="选股规则" description="定义选股条件" />
      <el-step title="择时规则" description="设置入场时机" />
      <el-step title="仓位规则" description="配置仓位管理" />
      <el-step title="风险管理" description="设置止盈止损" />
      <el-step title="纪律规则" description="明确交易纪律" />
      <el-step title="完成" description="确认并保存" />
    </el-steps>

    <!-- 步骤内容 -->
    <div class="step-content">
      <!-- Step 0: 基本信息 -->
      <el-card v-show="currentStep === 0">
        <template #header>
          <span>基本信息</span>
        </template>

        <!-- 引导说明 -->
        <el-alert
          title="欢迎创建您的交易计划"
          type="info"
          :closable="false"
          class="guide-alert"
        >
          <p>交易计划是您交易决策的核心框架，帮助您保持纪律性和一致性。</p>
          <div class="examples">
            <p><strong>交易风格说明：</strong></p>
            <ul>
              <li><strong>短线：</strong>持仓1-5天，关注技术面和市场情绪，适合有时间盯盘的投资者</li>
              <li><strong>中线：</strong>持仓1-3个月，结合技术面和基本面，适合上班族</li>
              <li><strong>长线：</strong>持仓3个月以上，重点关注基本面，适合价值投资者</li>
            </ul>
          </div>
        </el-alert>

        <!-- 模板选择 -->
        <el-card class="template-selector" shadow="never">
          <template #header>
            <div class="template-header">
              <el-icon><MagicStick /></el-icon>
              <span>快速开始：选择模板</span>
            </div>
          </template>
          <div class="template-list">
            <div
              v-for="template in templates"
              :key="template.id"
              class="template-item"
              :class="{ active: selectedTemplate === template.id }"
              @click="selectTemplate(template)"
            >
              <div class="template-name">{{ template.name }}</div>
              <div class="template-desc">{{ template.description }}</div>
              <div class="template-tags">
                <el-tag size="small" type="info">{{ getStyleLabel(template.style) }}</el-tag>
                <el-tag size="small" :type="getRiskType(template.risk_profile)">
                  {{ getRiskLabel(template.risk_profile) }}
                </el-tag>
              </div>
            </div>
          </div>
          <div class="template-tip">
            <el-icon><InfoFilled /></el-icon>
            <span>选择模板后，您可以在后续步骤中根据自己的需求进行调整</span>
          </div>
        </el-card>

        <el-form :model="formData" label-width="120px" label-position="top">
          <el-form-item label="系统名称" required>
            <el-input v-model="formData.name" placeholder="例如：趋势追踪系统" maxlength="50" show-word-limit />
          </el-form-item>
          <el-form-item label="系统描述">
            <el-input v-model="formData.description" type="textarea" :rows="3" placeholder="描述您的交易计划理念和特点" maxlength="500" show-word-limit />
          </el-form-item>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="交易风格">
                <el-radio-group v-model="formData.style">
                  <el-radio-button value="short_term">短线</el-radio-button>
                  <el-radio-button value="medium_term">中线</el-radio-button>
                  <el-radio-button value="long_term">长线</el-radio-button>
                </el-radio-group>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="风险偏好">
                <el-radio-group v-model="formData.risk_profile">
                  <el-radio-button value="conservative">保守</el-radio-button>
                  <el-radio-button value="balanced">中性</el-radio-button>
                  <el-radio-button value="aggressive">激进</el-radio-button>
                </el-radio-group>
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
      </el-card>

      <!-- Step 1: 选股规则 -->
      <el-card v-show="currentStep === 1">
        <template #header>
          <span>选股规则</span>
        </template>
        <RuleEditor v-model="formData.stock_selection" type="stock_selection" />
      </el-card>

      <!-- Step 2: 择时规则 -->
      <el-card v-show="currentStep === 2">
        <template #header>
          <span>择时规则</span>
        </template>
        <RuleEditor v-model="formData.timing" type="timing" />
      </el-card>

      <!-- Step 3: 仓位规则 -->
      <el-card v-show="currentStep === 3">
        <template #header>
          <span>仓位规则</span>
        </template>

        <!-- 引导说明 -->
        <el-alert
          title="仓位管理说明"
          type="success"
          :closable="false"
          class="guide-alert"
        >
          <p>合理的仓位管理是风险控制的关键。</p>
          <div class="examples">
            <p><strong>建议：</strong></p>
            <ul>
              <li><strong>单只股票仓位：</strong>短线 10-15%，中线 15-20%，长线 20-30%</li>
              <li><strong>持股数量：</strong>短线 5-10只，中线 3-8只，长线 2-5只</li>
              <li><strong>分散原则：</strong>不同行业、不同板块，避免集中风险</li>
            </ul>
          </div>
        </el-alert>

        <el-form :model="formData.position" label-width="120px" label-position="top">
          <el-row :gutter="20">
            <el-col :span="8">
              <el-form-item label="单只股票仓位上限">
                <el-slider v-model="positionMaxPerStock" :format-tooltip="(val: number) => `${val}%`" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="最大持股数">
                <el-input-number v-model="formData.position.max_holdings" :min="1" :max="50" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="最小持股数">
                <el-input-number v-model="formData.position.min_holdings" :min="1" :max="20" />
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
      </el-card>

      <!-- Step 4: 风险管理 -->
      <el-card v-show="currentStep === 4">
        <template #header>
          <span>风险管理规则</span>
        </template>
        <RuleEditor v-model="formData.risk_management" type="risk_management" />
      </el-card>

      <!-- Step 5: 纪律规则 -->
      <el-card v-show="currentStep === 5">
        <template #header>
          <span>纪律规则</span>
        </template>
        <RuleEditor v-model="formData.discipline" type="discipline" />
      </el-card>

      <!-- Step 6: 完成确认 -->
      <el-card v-show="currentStep === 6">
        <template #header>
          <span>确认信息</span>
        </template>

        <!-- 引导说明 -->
        <el-alert
          title="恭喜！您即将完成交易计划的创建"
          type="success"
          :closable="false"
          class="guide-alert"
        >
          <p>请仔细检查以下信息，确保您的交易计划符合预期。</p>
          <div class="examples">
            <p><strong>下一步建议：</strong></p>
            <ul>
              <li><strong>开始复盘：</strong>使用您的交易计划对历史行情进行复盘，验证系统的有效性</li>
              <li><strong>持续优化：</strong>根据复盘结果不断调整和完善您的交易规则</li>
              <li><strong>严格执行：</strong>在实际交易中严格遵守系统规则，保持纪律性</li>
            </ul>
          </div>
        </el-alert>

        <el-descriptions :column="2" border>
          <el-descriptions-item label="系统名称">{{ formData.name }}</el-descriptions-item>
          <el-descriptions-item label="交易风格">{{ getStyleLabel(formData.style) }}</el-descriptions-item>
          <el-descriptions-item label="风险偏好">{{ getRiskLabel(formData.risk_profile) }}</el-descriptions-item>
          <el-descriptions-item label="单只仓位上限">{{ positionMaxPerStock }}%</el-descriptions-item>
        </el-descriptions>
        <div class="confirm-tip">
          <el-alert title="确认创建后，您可以随时在详情页修改交易计划的规则。" type="info" show-icon :closable="false" />
        </div>
      </el-card>
    </div>

    <!-- 底部按钮 -->
    <div class="step-actions">
      <el-button v-if="currentStep > 0" @click="prevStep">上一步</el-button>
      <el-button v-if="currentStep < 6" type="primary" @click="nextStep" :disabled="!canNext">下一步</el-button>
      <el-button v-if="currentStep === 6" type="success" @click="handleSubmit" :loading="store.loading">
        {{ isEdit ? '保存修改' : '创建系统' }}
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, MagicStick, InfoFilled } from '@element-plus/icons-vue'
import { useTradingSystemStore } from '@/stores/tradingSystem'
import RuleEditor from './components/RuleEditor.vue'
import type { TradingSystemCreatePayload } from '@/api/tradingSystem'
import { tradingSystemTemplates, type TradingSystemTemplate } from '@/config/tradingSystemTemplates'

const route = useRoute()
const router = useRouter()
const store = useTradingSystemStore()

// 模板相关
const templates = tradingSystemTemplates
const selectedTemplate = ref<string | null>(null)

// 是否为编辑模式
const isEdit = computed(() => !!route.params.id)
const systemId = computed(() => route.params.id as string)

// 当前步骤
const currentStep = ref(0)

// 表单数据
const formData = ref<TradingSystemCreatePayload>({
  name: '',
  description: '',
  style: 'medium_term',
  risk_profile: 'balanced',
  stock_selection: { must_have: [], exclude: [], bonus: [] },
  timing: { entry_signals: [] },
  position: { max_per_stock: 0.2, max_holdings: 10, min_holdings: 3 },
  holding: { add_conditions: [], reduce_conditions: [] },
  risk_management: { stop_loss: {}, take_profit: {} },
  review: { checklist: [] },
  discipline: { must_do: [], must_not: [] }
})

// 仓位百分比（用于滑块）
const positionMaxPerStock = computed({
  get: () => Math.round((formData.value.position?.max_per_stock || 0.2) * 100),
  set: (val: number) => {
    if (formData.value.position) {
      formData.value.position.max_per_stock = val / 100
    }
  }
})

// 是否可以下一步
const canNext = computed(() => {
  if (currentStep.value === 0) {
    return formData.value.name?.trim().length > 0
  }
  return true
})

// 生命周期
onMounted(async () => {
  if (isEdit.value && systemId.value) {
    const system = await store.fetchSystem(systemId.value)
    if (system) {
      formData.value = {
        name: system.name,
        description: system.description || '',
        style: system.style,
        risk_profile: system.risk_profile,
        stock_selection: system.stock_selection || { must_have: [], exclude: [], bonus: [] },
        timing: system.timing || { entry_signals: [] },
        position: system.position || { max_per_stock: 0.2, max_holdings: 10, min_holdings: 3 },
        holding: system.holding || { add_conditions: [], reduce_conditions: [] },
        risk_management: system.risk_management || { stop_loss: {}, take_profit: {} },
        review: system.review || { checklist: [] },
        discipline: system.discipline || { must_do: [], must_not: [] }
      }
    }
  }
})

// 方法
function goBack() {
  router.push('/trading-system')
}

function prevStep() {
  if (currentStep.value > 0) currentStep.value--
}

function nextStep() {
  if (currentStep.value < 6) currentStep.value++
}

async function handleSubmit() {
  if (isEdit.value && systemId.value) {
    const result = await store.updateSystem(systemId.value, formData.value)
    if (result) {
      router.push(`/trading-system/${systemId.value}`)
    }
  } else {
    const result = await store.createSystem(formData.value)
    if (result) {
      router.push('/trading-system')
    }
  }
}

// 模板选择
function selectTemplate(template: TradingSystemTemplate) {
  selectedTemplate.value = template.id

  // 应用模板数据
  formData.value.name = template.name
  formData.value.description = template.description
  formData.value.style = template.style
  formData.value.risk_profile = template.risk_profile
  formData.value.stock_selection = JSON.parse(JSON.stringify(template.data.stock_selection))
  formData.value.timing = JSON.parse(JSON.stringify(template.data.timing))
  formData.value.position = JSON.parse(JSON.stringify(template.data.position))
  formData.value.holding = JSON.parse(JSON.stringify(template.data.holding))
  formData.value.risk_management = JSON.parse(JSON.stringify(template.data.risk_management))
  formData.value.review = JSON.parse(JSON.stringify(template.data.review))
  formData.value.discipline = JSON.parse(JSON.stringify(template.data.discipline))
}

// 工具函数
function getStyleLabel(style: string) {
  const map: Record<string, string> = {
    short_term: '短线',
    medium_term: '中线',
    long_term: '长线'
  }
  return map[style] || style
}

function getRiskLabel(risk: string) {
  const map: Record<string, string> = {
    conservative: '保守',
    balanced: '中性',
    aggressive: '激进'
  }
  return map[risk] || risk
}

function getRiskType(risk: string) {
  const map: Record<string, string> = {
    conservative: 'success',
    balanced: 'warning',
    aggressive: 'danger'
  }
  return map[risk] || 'info'
}
</script>

<style scoped lang="scss">
.trading-system-create {
  padding: 20px;
  max-width: 900px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 24px;

  .header-left {
    display: flex;
    align-items: center;
    gap: 16px;

    h1 {
      margin: 0;
      font-size: 20px;
      font-weight: 600;
    }
  }
}

.steps-container {
  margin-bottom: 32px;
}

.step-content {
  margin-bottom: 24px;

  .el-card {
    min-height: 300px;
  }
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

.step-actions {
  display: flex;
  justify-content: center;
  gap: 16px;
  padding: 20px;
  background: var(--el-bg-color);
  border-radius: 8px;
}

.confirm-tip {
  margin-top: 20px;
}

.template-selector {
  margin-bottom: 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;

  :deep(.el-card__header) {
    background: transparent;
    border-bottom: 1px solid rgba(255, 255, 255, 0.2);
    padding: 16px 20px;
  }

  :deep(.el-card__body) {
    padding: 20px;
  }

  .template-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 16px;
    font-weight: 600;
    color: white;
  }

  .template-list {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;
    margin-bottom: 16px;
  }

  .template-item {
    background: rgba(255, 255, 255, 0.95);
    border-radius: 8px;
    padding: 16px;
    cursor: pointer;
    transition: all 0.3s;
    border: 2px solid transparent;

    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }

    &.active {
      border-color: #67c23a;
      box-shadow: 0 0 0 3px rgba(103, 194, 58, 0.2);
    }

    .template-name {
      font-size: 16px;
      font-weight: 600;
      color: #303133;
      margin-bottom: 8px;
    }

    .template-desc {
      font-size: 13px;
      color: #606266;
      line-height: 1.5;
      margin-bottom: 12px;
    }

    .template-tags {
      display: flex;
      gap: 8px;
    }
  }

  .template-tip {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 4px;
    font-size: 13px;
    color: rgba(255, 255, 255, 0.9);
  }
}
</style>

