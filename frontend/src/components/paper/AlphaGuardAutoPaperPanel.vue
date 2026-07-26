<template>
  <div v-loading="loading" class="automatic-paper-panel">
    <el-alert type="info" :closable="false" show-icon class="paper-boundary">
      AlphaGuard 自动账户只使用虚拟资金；订单由内部决策与执行任务生成，始终禁止实盘，
      本页面不提供创建订单或修改成交价入口。
    </el-alert>

    <el-card shadow="never">
      <template #header>
        <div class="panel-header">
          <div>
            <span class="panel-title">自动模拟账户</span>
            <el-tag type="success" size="small">PAPER</el-tag>
            <el-tag type="danger" size="small">实盘禁用</el-tag>
          </div>
          <el-button :icon="Refresh" text @click="loadAll">刷新</el-button>
        </div>
      </template>
      <el-radio-group v-model="activeAccountId" @change="loadAccountDetails">
        <el-radio-button
          v-for="account in accounts"
          :key="account.account_id"
          :label="account.account_id"
        >
          {{ accountLabels[account.account_type] }}
        </el-radio-button>
      </el-radio-group>

      <el-empty v-if="!activeAccount" description="尚未初始化自动模拟账户" />
      <template v-else>
        <el-row :gutter="12" class="summary-row">
          <el-col :xs="12" :sm="6">
            <el-statistic title="可用现金" :value="numeric(activeAccount.cash_available)" :precision="2" prefix="¥" />
          </el-col>
          <el-col :xs="12" :sm="6">
            <el-statistic title="冻结现金" :value="numeric(activeAccount.cash_reserved)" :precision="2" prefix="¥" />
          </el-col>
          <el-col :xs="12" :sm="6">
            <el-statistic title="最近总资产" :value="numeric(latestSnapshot?.total_equity)" :precision="2" prefix="¥" />
          </el-col>
          <el-col :xs="12" :sm="6">
            <el-statistic title="累计费用" :value="numeric(activeAccount.total_fees)" :precision="2" prefix="¥" />
          </el-col>
        </el-row>
        <div class="account-meta">
          <el-tag :type="activeAccount.status === 'ACTIVE' ? 'success' : 'warning'">
            {{ activeAccount.status }}
          </el-tag>
          <span>{{ sourceDescription }}</span>
          <span v-if="latestSnapshot && !latestSnapshot.valuation_complete" class="warning">
            估值不完整：{{ latestSnapshot.missing_price_symbols.join(', ') || '缺少价格' }}
          </span>
        </div>
      </template>
    </el-card>

    <el-tabs v-if="activeAccount" v-model="activeTab" class="detail-tabs">
      <el-tab-pane label="持仓" name="positions">
        <el-table :data="positions" size="small">
          <el-table-column prop="symbol" label="代码" width="100" />
          <el-table-column prop="quantity" label="持仓" width="90" />
          <el-table-column prop="available_quantity" label="可卖" width="90" />
          <el-table-column prop="reserved_quantity" label="冻结" width="90" />
          <el-table-column label="平均成本" width="120">
            <template #default="{ row }">¥{{ money(row.average_cost) }}</template>
          </el-table-column>
          <el-table-column label="总成本">
            <template #default="{ row }">¥{{ money(row.total_cost) }}</template>
          </el-table-column>
          <el-table-column label="已实现盈亏">
            <template #default="{ row }">¥{{ money(row.realized_pnl) }}</template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="持仓批次 / T+1" name="lots">
        <el-table :data="lots" size="small">
          <el-table-column prop="symbol" label="代码" width="100" />
          <el-table-column prop="acquired_trade_date" label="买入日" width="120" />
          <el-table-column prop="available_from_date" label="可卖日" width="120" />
          <el-table-column prop="remaining_quantity" label="剩余" width="80" />
          <el-table-column prop="reserved_quantity" label="冻结" width="80" />
          <el-table-column label="单位成本" width="120">
            <template #default="{ row }">¥{{ money(row.unit_cost) }}</template>
          </el-table-column>
          <el-table-column prop="status" label="状态" />
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="订单" name="orders">
        <el-table :data="orders" size="small">
          <el-table-column prop="created_at" label="创建时间" width="165">
            <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column prop="symbol" label="代码" width="90" />
          <el-table-column prop="side" label="方向" width="70" />
          <el-table-column prop="source_type" label="来源" width="120" />
          <el-table-column label="成交进度" width="120">
            <template #default="{ row }">{{ row.filled_quantity }}/{{ row.requested_quantity }}</template>
          </el-table-column>
          <el-table-column label="状态" width="135">
            <template #default="{ row }">
              <el-tag :type="orderTagType(row.status)" size="small">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="决策关联" min-width="180">
            <template #default="{ row }">
              <span v-if="row.risk_decision_id">Risk {{ shortId(row.risk_decision_id) }}</span>
              <span v-else>{{ shortId(row.source_object_id) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80" fixed="right">
            <template #default="{ row }">
              <el-button
                v-if="cancellableStatuses.has(row.status)"
                type="danger"
                link
                @click="cancel(row)"
              >
                取消
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="成交与费用" name="fills">
        <el-table :data="fills" size="small">
          <el-table-column prop="trade_date" label="交易日" width="110" />
          <el-table-column prop="symbol" label="代码" width="90" />
          <el-table-column prop="side" label="方向" width="70" />
          <el-table-column prop="quantity" label="数量" width="80" />
          <el-table-column label="成交价" width="100">
            <template #default="{ row }">¥{{ money(row.price) }}</template>
          </el-table-column>
          <el-table-column label="成交额" width="120">
            <template #default="{ row }">¥{{ money(row.notional) }}</template>
          </el-table-column>
          <el-table-column label="费用" width="110">
            <template #default="{ row }">
              <el-tooltip
                :content="`佣金 ${money(row.fee_breakdown.commission)}；印花税 ${money(row.fee_breakdown.stamp_duty)}；过户费 ${money(row.fee_breakdown.transfer_fee)}`"
              >
                <span>¥{{ money(row.fee_breakdown.total_fee) }}</span>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column prop="matching_engine_version" label="撮合版本" />
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { formatDateTime } from '@/utils/datetime'
import {
  alphaguardPaperApi,
  type AutomaticAccountSnapshot,
  type AutomaticPaperAccount,
  type AutomaticPaperFill,
  type AutomaticPaperOrder,
  type AutomaticPaperPosition,
  type AutomaticPositionLot,
  type AutomaticAccountType
} from '@/api/alphaguardPaper'

const accounts = ref<AutomaticPaperAccount[]>([])
const positions = ref<AutomaticPaperPosition[]>([])
const lots = ref<AutomaticPositionLot[]>([])
const orders = ref<AutomaticPaperOrder[]>([])
const fills = ref<AutomaticPaperFill[]>([])
const snapshots = ref<AutomaticAccountSnapshot[]>([])
const activeAccountId = ref('')
const activeTab = ref('positions')
const loading = ref(false)

const accountLabels: Record<AutomaticAccountType, string> = {
  PAPER_QUANT: '量化基准',
  PAPER_NORMAL: '普通模型',
  PAPER_TOP_CONFIRMED: '双模型确认',
  PAPER_CHALLENGER: '挑战者（待启用）'
}
const accountSources: Record<AutomaticAccountType, string> = {
  PAPER_QUANT: '来源：QuantTradeProposal；基准账户，不代表通过双模型或硬风控',
  PAPER_NORMAL: '来源：普通模型第 0 轮 NormalTradePlan；基准账户',
  PAPER_TOP_CONFIRMED: '来源：Consensus PASS 且 HardRisk PASS/REDUCE',
  PAPER_CHALLENGER: 'PR-008 前只建立空账户，不会自动交易'
}
const cancellableStatuses = new Set([
  'CREATED',
  'RESERVED',
  'SUBMITTED',
  'PENDING',
  'PARTIALLY_FILLED'
])
const activeAccount = computed(
  () => accounts.value.find(item => item.account_id === activeAccountId.value) ?? null
)
const latestSnapshot = computed(() => snapshots.value[0] ?? null)
const sourceDescription = computed(
  () => activeAccount.value ? accountSources[activeAccount.value.account_type] : ''
)

function money(value: string | number | null | undefined) {
  const number = numeric(value)
  return number.toFixed(2)
}

function numeric(value: string | number | null | undefined) {
  const number = Number(value ?? 0)
  return Number.isFinite(number) ? number : 0
}

function shortId(value: string) {
  return value.length > 14 ? `${value.slice(0, 12)}…` : value
}

function orderTagType(status: string) {
  if (status === 'FILLED') return 'success'
  if (['REJECTED', 'EXPIRED', 'CANCELLED', 'SETTLEMENT_FAILED'].includes(status)) return 'danger'
  if (status === 'PARTIALLY_FILLED') return 'warning'
  return 'info'
}

async function loadAccountDetails() {
  if (!activeAccountId.value) return
  loading.value = true
  try {
    const accountId = activeAccountId.value
    const [positionsRes, lotsRes, ordersRes, fillsRes, snapshotsRes] = await Promise.all([
      alphaguardPaperApi.getPositions(accountId),
      alphaguardPaperApi.getPositionLots(accountId),
      alphaguardPaperApi.getOrders(accountId),
      alphaguardPaperApi.getFills(accountId),
      alphaguardPaperApi.getAccountSnapshots(accountId)
    ])
    positions.value = positionsRes.data.items
    lots.value = lotsRes.data.items
    orders.value = ordersRes.data.items
    fills.value = fillsRes.data.items
    snapshots.value = snapshotsRes.data.items
  } catch (error: any) {
    ElMessage.error(error?.message || '加载自动模拟账户失败')
  } finally {
    loading.value = false
  }
}

async function loadAll() {
  loading.value = true
  try {
    const response = await alphaguardPaperApi.getAccounts()
    accounts.value = response.data.items
    if (!accounts.value.some(item => item.account_id === activeAccountId.value)) {
      activeAccountId.value =
        accounts.value.find(item => item.account_type === 'PAPER_TOP_CONFIRMED')?.account_id
        ?? accounts.value[0]?.account_id
        ?? ''
    }
  } catch (error: any) {
    ElMessage.error(error?.message || '加载自动模拟账户失败')
  } finally {
    loading.value = false
  }
  await loadAccountDetails()
}

async function cancel(order: any) {
  try {
    await ElMessageBox.confirm(
      `取消 ${order.symbol} 未成交的 ${order.remaining_quantity} 股？已成交部分会保留。`,
      '取消自动模拟订单',
      { type: 'warning' }
    )
    await alphaguardPaperApi.cancelOrder(order.order_id)
    ElMessage.success('订单剩余部分已取消，相关预留已释放')
    await loadAccountDetails()
  } catch (error: any) {
    if (error !== 'cancel') ElMessage.error(error?.message || '取消订单失败')
  }
}

onMounted(loadAll)
</script>

<style scoped>
.automatic-paper-panel { display: grid; gap: 16px; }
.paper-boundary { margin-bottom: 0; }
.panel-header { display: flex; align-items: center; justify-content: space-between; }
.panel-title { margin-right: 10px; font-weight: 600; }
.panel-header .el-tag { margin-left: 6px; }
.summary-row { margin-top: 18px; }
.account-meta { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 18px; color: #606266; font-size: 13px; }
.warning { color: #e6a23c; }
.detail-tabs { padding: 0 4px; }
</style>
