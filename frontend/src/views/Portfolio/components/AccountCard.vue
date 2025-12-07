<template>
  <el-card class="account-card" v-loading="loading">
    <template #header>
      <div class="card-header">
        <span>资金账户</span>
        <div class="actions">
          <el-button type="primary" size="small" @click="openDepositDialog()">
            <el-icon><Plus /></el-icon> 入金
          </el-button>
          <el-button size="small" @click="openWithdrawDialog()">
            <el-icon><Minus /></el-icon> 出金
          </el-button>
          <el-button size="small" @click="showSettingsDialog = true">
            <el-icon><Setting /></el-icon>
          </el-button>
        </div>
      </div>
    </template>

    <!-- 未初始化状态 -->
    <div v-if="!hasInitialized" class="init-prompt">
      <el-empty description="还未设置初始资金">
        <el-button type="primary" @click="showInitDialog = true">设置初始资金</el-button>
      </el-empty>
    </div>

    <!-- 账户摘要 - 按币种分 Tab 展示 -->
    <div v-else class="summary-content">
      <el-tabs v-model="activeCurrency" type="border-card" class="currency-tabs">
        <!-- A股 (CNY) -->
        <el-tab-pane label="🇨🇳 A股 (CNY)" name="CNY">
          <CurrencyAccount
            :summary="summary"
            currency="CNY"
            symbol="¥"
            @deposit="() => openDepositDialog('CNY')"
            @withdraw="() => openWithdrawDialog('CNY')"
          />
        </el-tab-pane>

        <!-- 港股 (HKD) -->
        <el-tab-pane label="🇭🇰 港股 (HKD)" name="HKD">
          <CurrencyAccount
            :summary="summary"
            currency="HKD"
            symbol="HK$"
            @deposit="() => openDepositDialog('HKD')"
            @withdraw="() => openWithdrawDialog('HKD')"
          />
        </el-tab-pane>

        <!-- 美股 (USD) -->
        <el-tab-pane label="🇺🇸 美股 (USD)" name="USD">
          <CurrencyAccount
            :summary="summary"
            currency="USD"
            symbol="$"
            @deposit="() => openDepositDialog('USD')"
            @withdraw="() => openWithdrawDialog('USD')"
          />
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 初始化对话框 -->
    <el-dialog v-model="showInitDialog" title="设置初始资金" width="500px">
      <el-form :model="initForm" label-width="120px">
        <el-form-item label="A股 (CNY)">
          <el-input-number v-model="initForm.CNY" :min="0" :max="100000000" :step="10000" :precision="0" style="width: 100%" placeholder="可选" />
        </el-form-item>
        <el-form-item label="港股 (HKD)">
          <el-input-number v-model="initForm.HKD" :min="0" :max="100000000" :step="10000" :precision="0" style="width: 100%" placeholder="可选" />
        </el-form-item>
        <el-form-item label="美股 (USD)">
          <el-input-number v-model="initForm.USD" :min="0" :max="100000000" :step="10000" :precision="0" style="width: 100%" placeholder="可选" />
        </el-form-item>
        <el-alert type="info" :closable="false" style="margin-bottom: 16px">
          <template #default>
            可以同时设置多个币种的初始资金，至少需要设置一个币种
          </template>
        </el-alert>
      </el-form>
      <template #footer>
        <el-button @click="showInitDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleInitialize">确定</el-button>
      </template>
    </el-dialog>

    <!-- 入金对话框 -->
    <el-dialog v-model="showDepositDialog" :title="`入金 - ${getCurrencyLabel(transactionForm.currency)}`" width="400px">
      <el-form :model="transactionForm" label-width="80px">
        <el-form-item label="市场">
          <el-radio-group v-model="transactionForm.currency">
            <el-radio-button value="CNY">🇨🇳 A股</el-radio-button>
            <el-radio-button value="HKD">🇭🇰 港股</el-radio-button>
            <el-radio-button value="USD">🇺🇸 美股</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="金额">
          <el-input-number v-model="transactionForm.amount" :min="100" :max="100000000" :step="1000" :precision="2" style="width: 100%" />
          <span class="currency-hint">{{ getCurrencySymbol(transactionForm.currency) }}</span>
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="transactionForm.description" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDepositDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleDeposit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 出金对话框 -->
    <el-dialog v-model="showWithdrawDialog" :title="`出金 - ${getCurrencyLabel(transactionForm.currency)}`" width="400px">
      <el-form :model="transactionForm" label-width="80px">
        <el-form-item label="市场">
          <el-radio-group v-model="transactionForm.currency">
            <el-radio-button value="CNY">🇨🇳 A股</el-radio-button>
            <el-radio-button value="HKD">🇭🇰 港股</el-radio-button>
            <el-radio-button value="USD">🇺🇸 美股</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="金额">
          <el-input-number
            v-model="transactionForm.amount"
            :min="100"
            :max="getMaxWithdraw(transactionForm.currency)"
            :step="1000"
            :precision="2"
            style="width: 100%"
          />
          <span class="currency-hint">{{ getCurrencySymbol(transactionForm.currency) }}</span>
        </el-form-item>
        <el-form-item label="可用">
          <span class="available-cash">{{ getCurrencySymbol(transactionForm.currency) }}{{ formatMoney(summary?.cash?.[transactionForm.currency] || 0) }}</span>
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="transactionForm.description" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showWithdrawDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleWithdraw">确定</el-button>
      </template>
    </el-dialog>

    <!-- 设置对话框 -->
    <el-dialog v-model="showSettingsDialog" title="账户设置" width="450px">
      <el-form :model="settingsForm" label-width="140px">
        <el-form-item label="单股最大仓位">
          <el-input-number v-model="settingsForm.max_position_pct" :min="5" :max="100" :step="5" />
          <span class="unit">%</span>
        </el-form-item>
        <el-form-item label="最大亏损容忍">
          <el-input-number v-model="settingsForm.max_loss_pct" :min="1" :max="50" :step="1" />
          <span class="unit">%</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showSettingsDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleUpdateSettings">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Plus, Minus, Setting } from '@element-plus/icons-vue'
import { portfolioApi, type AccountSummary } from '@/api/portfolio'
import { ElMessage } from 'element-plus'
import CurrencyAccount from './CurrencyAccount.vue'

const emit = defineEmits<{
  (e: 'updated'): void
}>()

const loading = ref(false)
const submitting = ref(false)
const summary = ref<AccountSummary | null>(null)
const activeCurrency = ref<'CNY' | 'HKD' | 'USD'>('CNY')

// 对话框状态
const showInitDialog = ref(false)
const showDepositDialog = ref(false)
const showWithdrawDialog = ref(false)
const showSettingsDialog = ref(false)

// 表单数据
const initForm = ref({ CNY: 0, HKD: 0, USD: 0 })
const transactionForm = ref({ amount: 10000, currency: 'CNY' as string, description: '' })
const settingsForm = ref({ max_position_pct: 30, max_loss_pct: 10 })

// 是否已初始化 (任意一个币种有资金就算已初始化)
const hasInitialized = computed(() => {
  const cny = (summary.value?.initial_capital?.CNY || 0) + (summary.value?.total_deposit?.CNY || 0)
  const hkd = (summary.value?.initial_capital?.HKD || 0) + (summary.value?.total_deposit?.HKD || 0)
  const usd = (summary.value?.initial_capital?.USD || 0) + (summary.value?.total_deposit?.USD || 0)
  return cny > 0 || hkd > 0 || usd > 0
})

// 格式化金额
const formatMoney = (val: number) => {
  return val.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// 货币相关方法
const getCurrencySymbol = (currency: string) => {
  const map: Record<string, string> = { CNY: '¥', HKD: 'HK$', USD: '$' }
  return map[currency] || '¥'
}

const getCurrencyLabel = (currency: string) => {
  const map: Record<string, string> = { CNY: 'A股 (CNY)', HKD: '港股 (HKD)', USD: '美股 (USD)' }
  return map[currency] || currency
}

const getMaxWithdraw = (currency: string) => {
  return summary.value?.cash?.[currency as keyof typeof summary.value.cash] || 0
}

// 打开入金对话框
const openDepositDialog = (currency?: string) => {
  transactionForm.value = { amount: 10000, currency: currency || activeCurrency.value || 'CNY', description: '' }
  showDepositDialog.value = true
}

// 打开出金对话框
const openWithdrawDialog = (currency?: string) => {
  transactionForm.value = { amount: 10000, currency: currency || activeCurrency.value || 'CNY', description: '' }
  showWithdrawDialog.value = true
}

// 加载数据
const loadData = async () => {
  loading.value = true
  try {
    const res = await portfolioApi.getAccountSummary()
    if (res.success && res.data) {
      summary.value = res.data
      // 更新设置表单
      settingsForm.value = {
        max_position_pct: res.data.settings?.max_position_pct || 30,
        max_loss_pct: res.data.settings?.max_loss_pct || 10
      }
    }
  } catch (e) {
    console.error('加载账户摘要失败', e)
  } finally {
    loading.value = false
  }
}

// 初始化账户
const handleInitialize = async () => {
  // 验证至少有一个币种的初始资金
  const hasAny = initForm.value.CNY > 0 || initForm.value.HKD > 0 || initForm.value.USD > 0
  if (!hasAny) {
    ElMessage.warning('请至少设置一个币种的初始资金')
    return
  }

  submitting.value = true
  try {
    // 逐个初始化各币种
    const currencies = ['CNY', 'HKD', 'USD'] as const
    for (const currency of currencies) {
      const amount = initForm.value[currency]
      if (amount > 0) {
        const res = await portfolioApi.initializeAccount(amount, currency)
        if (!res.success) {
          ElMessage.error(`${currency} 初始资金设置失败: ${res.message}`)
          return
        }
      }
    }

    ElMessage.success('初始资金设置成功')
    showInitDialog.value = false
    initForm.value = { CNY: 0, HKD: 0, USD: 0 }
    await loadData()
    emit('updated')
  } catch (e: any) {
    ElMessage.error(e.message || '设置失败')
  } finally {
    submitting.value = false
  }
}

// 入金
const handleDeposit = async () => {
  submitting.value = true
  try {
    const res = await portfolioApi.deposit(transactionForm.value.amount, transactionForm.value.currency, transactionForm.value.description)
    if (res.success) {
      ElMessage.success(res.message || '入金成功')
      showDepositDialog.value = false
      transactionForm.value = { amount: 10000, currency: 'CNY', description: '' }
      await loadData()
      emit('updated')
    } else {
      ElMessage.error(res.message || '入金失败')
    }
  } catch (e: any) {
    ElMessage.error(e.message || '入金失败')
  } finally {
    submitting.value = false
  }
}

// 出金
const handleWithdraw = async () => {
  submitting.value = true
  try {
    const res = await portfolioApi.withdraw(transactionForm.value.amount, transactionForm.value.currency, transactionForm.value.description)
    if (res.success) {
      ElMessage.success(res.message || '出金成功')
      showWithdrawDialog.value = false
      transactionForm.value = { amount: 10000, currency: 'CNY', description: '' }
      await loadData()
      emit('updated')
    } else {
      ElMessage.error(res.message || '出金失败')
    }
  } catch (e: any) {
    ElMessage.error(e.message || '出金失败')
  } finally {
    submitting.value = false
  }
}

// 更新设置
const handleUpdateSettings = async () => {
  submitting.value = true
  try {
    const res = await portfolioApi.updateAccountSettings(settingsForm.value)
    if (res.success) {
      ElMessage.success('设置已保存')
      showSettingsDialog.value = false
      await loadData()
    } else {
      ElMessage.error(res.message || '保存失败')
    }
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    submitting.value = false
  }
}

// 暴露方法给父组件
defineExpose({ loadData })

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.account-card {
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.actions {
  display: flex;
  gap: 8px;
}

.init-prompt {
  padding: 20px 0;
}

.summary-content {
  padding: 8px 0;
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

.unit {
  margin-left: 8px;
  color: #909399;
}

.currency-tabs {
  margin-top: 8px;
}

.currency-tabs :deep(.el-tabs__header) {
  margin-bottom: 0;
}

.currency-hint {
  margin-left: 8px;
  color: #909399;
  font-weight: bold;
}

.available-cash {
  color: #67c23a;
  font-weight: bold;
}
</style>
