<template>
  <div class="paper-trading">
    <div class="header">
      <div class="title">
        <el-icon style="margin-right:8px"><CreditCard /></el-icon>
        <span>模拟交易</span>
      </div>
      <div class="actions">
        <el-button :icon="Refresh" text size="small" @click="refreshAll">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="openOrderDialog">下市场单</el-button>
        <el-button type="success" plain :icon="Setting" @click="openInitializeDialog">初始化账户</el-button>
        <el-button type="danger" plain :icon="Delete" @click="confirmReset">重置账户</el-button>
      </div>
    </div>

    <!-- 风险提示横幅 -->
    <el-alert
      type="warning"
      :closable="false"
      show-icon
      style="margin-bottom: 16px;"
    >
      <template #title>
        <div style="font-weight: 600; font-size: 14px;">⚠️ 模拟交易风险提示</div>
      </template>
      <div style="font-size: 13px; line-height: 1.8;">
        <p style="margin: 0 0 8px 0;">
          <strong>1. 模拟性质：</strong>本功能为模拟交易工具，使用虚拟资金，不涉及真实资金交易，仅供学习和练习使用。
        </p>
        <p style="margin: 0 0 8px 0;">
          <strong>2. 数据延迟：</strong>模拟交易使用的行情数据可能存在延迟，与实际市场行情存在差异，成交价格和时机仅供参考。
        </p>
        <p style="margin: 0 0 8px 0;">
          <strong>3. 实盘差异：</strong>模拟交易环境与真实交易存在显著差异，包括但不限于：滑点、流动性、交易成本、心理压力等因素，模拟盈利不代表实盘能够盈利。
        </p>
        <p style="margin: 0;">
          <strong>4. 投资风险：</strong>股票投资存在市场风险，可能导致本金损失。请勿将模拟交易结果作为实盘投资决策依据，实盘交易前请充分评估自身风险承受能力并咨询专业投资顾问。
        </p>
      </div>
    </el-alert>

    <el-row :gutter="16" class="body">
      <el-col :span="8">
        <el-card shadow="hover" class="account-card">
          <template #header><div class="card-hd">账户信息</div></template>
          <div v-if="account">
            <el-tabs v-model="activeMarketTab" type="border-card">
              <!-- A股账户 -->
              <el-tab-pane label="🇨🇳 A股" name="CN">
                <el-descriptions :column="1" border>
                  <el-descriptions-item label="可用资金">¥{{ fmtAmount(account.cash?.CNY ?? (typeof account.cash === 'number' ? account.cash : 0)) }}</el-descriptions-item>
                  <el-descriptions-item label="持仓市值">¥{{ fmtAmount(account.positions_value?.CNY ?? (typeof account.positions_value === 'number' ? account.positions_value : 0)) }}</el-descriptions-item>
                  <el-descriptions-item label="总资产">¥{{ fmtAmount(account.equity?.CNY ?? (typeof account.equity === 'number' ? account.equity : 0)) }}</el-descriptions-item>
                  <el-descriptions-item label="已实现盈亏">
                    <span :style="{ color: (account.realized_pnl?.CNY ?? (typeof account.realized_pnl === 'number' ? account.realized_pnl : 0)) >= 0 ? '#67C23A' : '#F56C6C' }">
                      ¥{{ fmtAmount(account.realized_pnl?.CNY ?? (typeof account.realized_pnl === 'number' ? account.realized_pnl : 0)) }}
                    </span>
                  </el-descriptions-item>
                </el-descriptions>
              </el-tab-pane>

              <!-- 港股账户 -->
              <el-tab-pane label="🇭🇰 港股" name="HK">
                <el-descriptions :column="1" border>
                  <el-descriptions-item label="可用资金">HK${{ fmtAmount(account.cash?.HKD || 0) }}</el-descriptions-item>
                  <el-descriptions-item label="持仓市值">HK${{ fmtAmount(account.positions_value?.HKD || 0) }}</el-descriptions-item>
                  <el-descriptions-item label="总资产">HK${{ fmtAmount(account.equity?.HKD || 0) }}</el-descriptions-item>
                  <el-descriptions-item label="已实现盈亏">
                    <span :style="{ color: (account.realized_pnl?.HKD || 0) >= 0 ? '#67C23A' : '#F56C6C' }">
                      HK${{ fmtAmount(account.realized_pnl?.HKD || 0) }}
                    </span>
                  </el-descriptions-item>
                </el-descriptions>
              </el-tab-pane>

              <!-- 美股账户 -->
              <el-tab-pane label="🇺🇸 美股" name="US">
                <el-descriptions :column="1" border>
                  <el-descriptions-item label="可用资金">${{ fmtAmount(account.cash?.USD || 0) }}</el-descriptions-item>
                  <el-descriptions-item label="持仓市值">${{ fmtAmount(account.positions_value?.USD || 0) }}</el-descriptions-item>
                  <el-descriptions-item label="总资产">${{ fmtAmount(account.equity?.USD || 0) }}</el-descriptions-item>
                  <el-descriptions-item label="已实现盈亏">
                    <span :style="{ color: (account.realized_pnl?.USD || 0) >= 0 ? '#67C23A' : '#F56C6C' }">
                      ${{ fmtAmount(account.realized_pnl?.USD || 0) }}
                    </span>
                  </el-descriptions-item>
                </el-descriptions>
              </el-tab-pane>
            </el-tabs>

            <div style="margin-top: 12px; text-align: center; color: #909399; font-size: 12px">
              更新时间: {{ formatDateTime(account.updated_at) }}
            </div>
          </div>
          <el-empty v-else description="暂无账户数据" />
        </el-card>
      </el-col>

      <el-col :span="16">
        <el-card shadow="hover" class="positions-card">
          <template #header>
            <div class="card-hd">
              持仓
              <span style="margin-left: 8px; font-size: 12px; color: #909399; font-weight: normal">
                ({{ filteredPositions.length }} 个)
              </span>
            </div>
          </template>
          <el-table :data="filteredPositions" size="small" v-loading="loading.positions">
            <el-table-column label="代码" width="100">
              <template #default="{ row }">
                <el-link type="primary" @click="viewStockDetail(row.code)">{{ row.code }}</el-link>
              </template>
            </el-table-column>
            <el-table-column label="名称" width="100">
              <template #default="{ row }">{{ row.name || '-' }}</template>
            </el-table-column>
            <el-table-column label="市场" width="70">
              <template #default="{ row }">
                <el-tag v-if="row.market === 'CN'" type="success" size="small">🇨🇳 A股</el-tag>
                <el-tag v-else-if="row.market === 'HK'" type="warning" size="small">🇭🇰 港股</el-tag>
                <el-tag v-else-if="row.market === 'US'" type="info" size="small">🇺🇸 美股</el-tag>
                <el-tag v-else size="small">{{ row.market || 'CN' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="数量" width="80">
              <template #default="{ row }">
                {{ row.quantity }}
                <span v-if="row.available_qty !== undefined && row.available_qty < row.quantity" style="color: #909399; font-size: 11px">
                  (可用{{ row.available_qty }})
                </span>
              </template>
            </el-table-column>
            <el-table-column label="均价" width="100">
              <template #default="{ row }">{{ getCurrencySymbol(row.currency) }}{{ fmtPrice(row.avg_cost) }}</template>
            </el-table-column>
            <el-table-column label="最新价" width="100">
              <template #default="{ row }">{{ getCurrencySymbol(row.currency) }}{{ fmtPrice(row.last_price) }}</template>
            </el-table-column>
            <el-table-column label="浮盈" width="120">
              <template #default="{ row }">
                <span :style="{ color: (Number(row.last_price || 0) - Number(row.avg_cost || 0)) >= 0 ? '#67C23A' : '#F56C6C' }">
                  {{ getCurrencySymbol(row.currency) }}{{ fmtAmount((Number(row.last_price || 0) - Number(row.avg_cost || 0)) * Number(row.quantity || 0)) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200">
              <template #default="{ row }">
                <el-button size="small" type="primary" link @click="viewStockDetail(row.code)">详情</el-button>
                <el-button size="small" type="success" link @click="goAnalysisWithCode(row.code)">分析</el-button>
                <el-button size="small" type="danger" link @click="sellPosition(row)">卖出</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card shadow="hover" class="orders-card" style="margin-top:16px">
          <template #header>
            <div class="card-hd">
              订单记录
              <span style="margin-left: 8px; font-size: 12px; color: #909399; font-weight: normal">
                ({{ filteredOrders.length }} 条)
              </span>
            </div>
          </template>
          <el-table :data="filteredOrders" size="small" v-loading="loading.orders">
            <el-table-column label="时间" width="160">
              <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="方向" width="80">
              <template #default="{ row }">
                <el-tag :type="row.side === 'buy' ? 'success' : 'danger'" size="small">
                  {{ row.side === 'buy' ? '买入' : '卖出' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="代码" width="100">
              <template #default="{ row }">
                <el-link type="primary" @click="viewStockDetail(row.code)">{{ row.code }}</el-link>
              </template>
            </el-table-column>
            <el-table-column label="名称" width="100">
              <template #default="{ row }">{{ row.name || '-' }}</template>
            </el-table-column>
            <el-table-column prop="price" label="成交价" width="100">
              <template #default="{ row }">{{ fmtPrice(row.price) }}</template>
            </el-table-column>
            <el-table-column prop="quantity" label="数量" width="100" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.status === 'filled' ? 'success' : 'info'" size="small">
                  {{ row.status === 'filled' ? '已成交' : row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <!-- 关联分析报告 -->
            <el-table-column label="关联分析" width="120">
              <template #default="{ row }">
                <el-button v-if="row.analysis_id" size="small" type="primary" link @click="viewReport(row.analysis_id)">
                  查看报告
                </el-button>
                <span v-else style="color: #909399;">-</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="orderDialog" title="下市场单" width="480px">
      <!-- 分析上下文提示 -->
      <div v-if="(order as any).analysis_id" class="analysis-context" style="margin-bottom:12px">
        <el-alert :closable="false" type="info" show-icon>
          <template #title>
            来自分析报告：<span style="font-family:monospace">{{ (order as any).analysis_id }}</span>
            <el-button link size="small" type="primary" style="margin-left:8px" @click="viewReport((order as any).analysis_id)">查看报告</el-button>
          </template>
          <div v-if="analysisLoading" style="color:#666">正在加载分析摘要…</div>
          <div v-else-if="analysisContext">
            <div style="font-size:12px;color:#666">
              <span>标的：{{ analysisContext.stock_symbol || '-' }}</span>
              <span style="margin-left:8px">模型建议：{{ analysisContext.recommendation || '-' }}</span>
            </div>
          </div>
        </el-alert>
      </div>

      <el-form label-width="90px">
        <el-form-item label="方向">
          <el-radio-group v-model="order.side">
            <el-radio-button label="buy">买入</el-radio-button>
            <el-radio-button label="sell">卖出</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="代码">
          <el-input v-model="order.code" placeholder="A股: 600519 | 港股: 0700 | 美股: AAPL" @input="detectMarket" />
        </el-form-item>
        <el-form-item label="市场" v-if="detectedMarket">
          <el-tag v-if="detectedMarket === 'CN'" type="success">🇨🇳 A股市场 (CNY)</el-tag>
          <el-tag v-else-if="detectedMarket === 'HK'" type="warning">🇭🇰 港股市场 (HKD)</el-tag>
          <el-tag v-else-if="detectedMarket === 'US'" type="info">🇺🇸 美股市场 (USD)</el-tag>
          <div style="margin-top: 8px; font-size: 12px; color: #909399">
            <span v-if="detectedMarket === 'CN'">💡 A股T+1，今天买入明天可卖</span>
            <span v-else-if="detectedMarket === 'HK'">💡 港股T+0，买入后立即可卖</span>
            <span v-else-if="detectedMarket === 'US'">💡 美股T+0，买入后立即可卖 | 零佣金</span>
          </div>
        </el-form-item>
        <el-form-item label="数量">
          <el-input-number v-model="order.qty" :min="1" />
        </el-form-item>
        <el-form-item label="价格">
          <el-checkbox v-model="useCustomPrice" style="margin-right: 8px">指定价格</el-checkbox>
          <el-input-number
            v-if="useCustomPrice"
            v-model="order.price"
            :min="0.01"
            :precision="2"
            :step="0.01"
            style="width: 150px"
            placeholder="输入价格"
          />
          <span v-if="useCustomPrice && priceRange" style="margin-left: 8px; font-size: 12px; color: #909399">
            (当天区间: {{ priceRange.low?.toFixed(2) || '-' }} - {{ priceRange.high?.toFixed(2) || '-' }})
          </span>
          <span v-else-if="!useCustomPrice && currentPrice" style="margin-left: 8px; font-size: 12px; color: #909399">
            使用实时价格: {{ currentPrice.toFixed(2) }}
          </span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="orderDialog=false">取消</el-button>
        <el-button type="primary" @click="submitOrder">提交</el-button>
      </template>
    </el-dialog>

    <!-- 初始化账户对话框 -->
    <el-dialog v-model="initializeDialog" title="初始化账户" width="500px" :close-on-click-modal="false">
      <el-alert type="info" :closable="false" style="margin-bottom: 16px;">
        <template #title>
          <div style="font-size: 13px;">
            💡 提示：初始化账户将设置您的模拟交易初始资金。如果账户已存在，将清空所有持仓和订单，重置为指定金额。
          </div>
        </template>
      </el-alert>
      
      <el-form :model="initialCash" label-width="120px">
        <el-form-item label="🇨🇳 A股初始资金 (CNY)">
          <el-input-number
            v-model="initialCash.CNY"
            :min="0"
            :precision="2"
            :step="10000"
            style="width: 100%"
            placeholder="请输入A股初始资金"
          >
            <template #prefix>¥</template>
          </el-input-number>
          <div style="font-size: 12px; color: #909399; margin-top: 4px;">
            默认: ¥1,000,000.00
          </div>
        </el-form-item>
        
        <el-form-item label="🇭🇰 港股初始资金 (HKD)">
          <el-input-number
            v-model="initialCash.HKD"
            :min="0"
            :precision="2"
            :step="10000"
            style="width: 100%"
            placeholder="请输入港股初始资金"
          >
            <template #prefix>HK$</template>
          </el-input-number>
          <div style="font-size: 12px; color: #909399; margin-top: 4px;">
            默认: HK$1,000,000.00
          </div>
        </el-form-item>
        
        <el-form-item label="🇺🇸 美股初始资金 (USD)">
          <el-input-number
            v-model="initialCash.USD"
            :min="0"
            :precision="2"
            :step="1000"
            style="width: 100%"
            placeholder="请输入美股初始资金"
          >
            <template #prefix>$</template>
          </el-input-number>
          <div style="font-size: 12px; color: #909399; margin-top: 4px;">
            默认: $100,000.00
          </div>
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="initializeDialog = false">取消</el-button>
        <el-button type="primary" @click="handleInitialize" :loading="initializing">
          确认初始化
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CreditCard, Refresh, Plus, Delete, Setting } from '@element-plus/icons-vue'
import { paperApi } from '@/api/paper'
import { analysisApi } from '@/api/analysis'
import { stocksApi } from '@/api/stocks'
import { formatDateTime } from '@/utils/datetime'

// 路由与初始化
const route = useRoute()
const router = useRouter()

// 数据
const account = ref<any | null>(null)
const positions = ref<any[]>([])
const orders = ref<any[]>([])
const loading = ref({ account: false, positions: false, orders: false })

const orderDialog = ref(false)
const order = ref({ side: 'buy', code: '', qty: 100, price: undefined as number | undefined })
const detectedMarket = ref<string>('')

// 初始化账户对话框
const initializeDialog = ref(false)
const initializing = ref(false)
const initialCash = ref<{ CNY: number; HKD: number; USD: number }>({
  CNY: 1000000,
  HKD: 1000000,
  USD: 100000
})
const activeMarketTab = ref<string>('CN')
const useCustomPrice = ref(false)
const currentPrice = ref<number | null>(null)
const priceRange = ref<{ high: number; low: number } | null>(null)

// 计算属性：根据当前市场标签页过滤持仓
const filteredPositions = computed(() => {
  if (!positions.value || positions.value.length === 0) return []
  return positions.value.filter(pos => {
    const market = pos.market || 'CN'
    return market === activeMarketTab.value
  })
})

// 计算属性：根据当前市场标签页过滤订单
const filteredOrders = computed(() => {
  if (!orders.value || orders.value.length === 0) return []
  return orders.value.filter(ord => {
    const market = ord.market || 'CN'
    return market === activeMarketTab.value
  })
})

// 分析上下文
const analysisContext = ref<any | null>(null)
const analysisLoading = ref(false)

// 方法
function fmtPrice(n: number | null | undefined) {
  if (n == null || Number.isNaN(n as any)) return '-'
  return Number(n).toFixed(2)
}
function fmtAmount(n: number | null | undefined) {
  // 🔥 修复：处理 NaN 和非数字值
  if (n == null || Number.isNaN(n as any) || typeof n !== 'number') return '0.00'
  return Number(n).toFixed(2)
}

// 获取货币符号
function getCurrencySymbol(currency: string | undefined) {
  if (!currency) return '¥'
  if (currency === 'CNY') return '¥'
  if (currency === 'HKD') return 'HK$'
  if (currency === 'USD') return '$'
  return ''
}

// 获取价格信息（当前价格和价格区间）
async function fetchPriceInfo() {
  if (!order.value.code || !detectedMarket.value) {
    currentPrice.value = null
    priceRange.value = null
    return
  }

  try {
    const res = await paperApi.getQuote(order.value.code, detectedMarket.value)
    if (res.success && res.data) {
      currentPrice.value = res.data.current_price || null
      if (res.data.high && res.data.low) {
        priceRange.value = {
          high: res.data.high,
          low: res.data.low
        }
      } else {
        priceRange.value = null
      }
    }
  } catch (e: any) {
    console.warn('获取价格信息失败:', e)
    currentPrice.value = null
    priceRange.value = null
  }
}

// 检测市场类型
function detectMarket() {
  const code = order.value.code.trim().toUpperCase()
  if (!code) {
    detectedMarket.value = ''
    currentPrice.value = null
    priceRange.value = null
    return
  }

  // 美股：纯字母
  if (/^[A-Z]+$/.test(code)) {
    detectedMarket.value = 'US'
    fetchPriceInfo()
    return
  }

  // 港股：4-5位数字或.HK后缀
  if (/^\d{4,5}$/.test(code) || code.endsWith('.HK')) {
    detectedMarket.value = 'HK'
    fetchPriceInfo()
    return
  }

  // A股：6位数字
  if (/^\d{6}$/.test(code)) {
    detectedMarket.value = 'CN'
    fetchPriceInfo()
    return
  }

  // 默认A股
  detectedMarket.value = 'CN'
  fetchPriceInfo()
}

async function fetchAccount() {
  try {
    loading.value.account = true
    const res = await paperApi.getAccount()
    if (res.success) {
      account.value = res.data.account
      // 可选：也可从account接口带回的positions中填充
      // positions.value = res.data.positions || positions.value
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '获取账户失败')
  } finally {
    loading.value.account = false
  }
}

async function fetchPositions() {
  try {
    loading.value.positions = true
    const res = await paperApi.getPositions()
    if (res.success) {
      positions.value = res.data.items || []
      // 批量获取股票名称
      await fetchStockNames(positions.value)
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '获取持仓失败')
  } finally {
    loading.value.positions = false
  }
}

async function fetchOrders() {
  try {
    loading.value.orders = true
    const res = await paperApi.getOrders(50)
    if (res.success) {
      orders.value = res.data.items || []
      // 批量获取股票名称
      await fetchStockNames(orders.value)
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '获取订单失败')
  } finally {
    loading.value.orders = false
  }
}

// 批量获取股票名称
async function fetchStockNames(items: any[]) {
  if (!items || items.length === 0) return

  // 获取所有唯一的股票代码
  const codes = [...new Set(items.map(item => item.code).filter(Boolean))]

  // 并行获取所有股票的名称
  await Promise.all(
    codes.map(async (code) => {
      try {
        const res = await stocksApi.getQuote(code)
        if (res.success && res.data && res.data.name) {
          // 更新所有包含该代码的项目
          items.forEach(item => {
            if (item.code === code) {
              item.name = res.data.name
            }
          })
        }
      } catch (error) {
        console.warn(`获取股票 ${code} 名称失败:`, error)
      }
    })
  )
}

function openOrderDialog() {
  orderDialog.value = true
  // 重置价格相关状态
  useCustomPrice.value = false
  order.value.price = undefined
  currentPrice.value = null
  priceRange.value = null
  // 如果已有代码，获取价格信息
  if (order.value.code && detectedMarket.value) {
    fetchPriceInfo()
  }
}

async function submitOrder() {
  try {
    const payload: any = { 
      side: order.value.side as 'buy' | 'sell', 
      code: order.value.code, 
      quantity: Number(order.value.qty)
    }
    
    // 🔥 如果指定了价格，添加到 payload
    if (useCustomPrice.value && order.value.price !== undefined && order.value.price !== null) {
      payload.price = Number(order.value.price)
      console.log('[下单] 使用指定价格:', payload.price)
    } else {
      console.log('[下单] 使用实时价格（未指定价格）')
    }
    
    if ((order.value as any).analysis_id) payload.analysis_id = (order.value as any).analysis_id
    
    const res = await paperApi.placeOrder(payload)
    if (res.success) {
      ElMessage.success('下单成功')
      orderDialog.value = false
      // 重置订单表单
      order.value = { side: 'buy', code: '', qty: 100, price: undefined }
      useCustomPrice.value = false
      currentPrice.value = null
      priceRange.value = null
      await refreshAll()
    } else {
      ElMessage.error(res.message || '下单失败')
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '下单失败')
  }
}

// 打开初始化账户对话框
function openInitializeDialog(isReset: boolean = false) {
  // 如果账户已存在且不是重置操作，显示当前金额作为默认值
  if (account.value && !isReset) {
    const cash = account.value.cash
    if (typeof cash === 'object' && cash !== null) {
      initialCash.value = {
        CNY: cash.CNY || 1000000,
        HKD: cash.HKD || 1000000,
        USD: cash.USD || 100000
      }
    } else if (typeof cash === 'number') {
      // 兼容旧格式
      initialCash.value = {
        CNY: cash,
        HKD: 1000000,
        USD: 100000
      }
    }
  } else {
    // 重置操作或新账户，使用默认值
    initialCash.value = {
      CNY: 1000000,
      HKD: 1000000,
      USD: 100000
    }
  }
  initializeDialog.value = true
}

// 处理初始化账户
async function handleInitialize() {
  try {
    // 验证金额
    if (initialCash.value.CNY < 0 || initialCash.value.HKD < 0 || initialCash.value.USD < 0) {
      ElMessage.error('初始金额不能为负数')
      return
    }
    
    // 检查是否所有金额都为0
    if (initialCash.value.CNY === 0 && initialCash.value.HKD === 0 && initialCash.value.USD === 0) {
      ElMessage.warning('至少需要设置一个市场的初始金额')
      return
    }
    
    initializing.value = true
    const res = await paperApi.initializeAccount({
      initial_cash: {
        CNY: initialCash.value.CNY,
        HKD: initialCash.value.HKD,
        USD: initialCash.value.USD
      }
    })
    
    if (res.success) {
      ElMessage.success('账户已初始化')
      initializeDialog.value = false
      await refreshAll()
    } else {
      ElMessage.error(res.message || '初始化失败')
    }
  } catch (e: any) {
    ElMessage.error(e.message || '初始化账户失败')
  } finally {
    initializing.value = false
  }
}

async function confirmReset() {
  try {
    // 询问是否使用自定义金额
    await ElMessageBox.confirm(
      '重置账户将清空所有订单与持仓。\n\n是否使用自定义初始金额？',
      '重置账户',
      {
        confirmButtonText: '使用自定义金额',
        cancelButtonText: '使用默认金额',
        distinguishCancelAndClose: true,
        type: 'warning'
      }
    )
    // 用户选择了"使用自定义金额"，打开初始化对话框（重置模式）
    openInitializeDialog(true)
  } catch (e: any) {
    // 用户选择了"使用默认金额"或关闭对话框
    if (e === 'cancel') {
      // 用户选择了"使用默认金额"，继续重置流程
      try {
        await ElMessageBox.confirm('将清空所有订单与持仓，并重置账户为默认初始现金，确认重置？', '确认重置', { type: 'warning' })
        const res = await paperApi.resetAccount()
        if (res.success) {
          ElMessage.success('账户已重置')
          await refreshAll()
        }
      } catch (resetError: any) {
        if (resetError !== 'cancel') {
          ElMessage.error(resetError.message || '重置失败')
        }
      }
    }
    // 如果 e === 'close'，用户关闭了对话框，不做任何操作
  }
}

async function refreshAll() {
  await Promise.all([fetchAccount(), fetchPositions(), fetchOrders()])
}

// 查看报告详情（跳转到报告详情页）
function viewReport(analysisId: string) {
  if (!analysisId) return
  // 跳转到报告详情页
  router.push({ name: 'ReportDetail', params: { id: analysisId } })
}

// 跳转到分析页面（带股票代码和市场）
function goAnalysisWithCode(stockCode: string) {
  if (!stockCode) return
  // 根据股票代码判断市场
  const market = getMarketByCode(stockCode)
  router.push({ name: 'SingleAnalysis', query: { stock: stockCode, market } })
}

// 根据股票代码判断市场
function getMarketByCode(code: string): string {
  if (!code) return 'A股'

  // 6位数字 = A股
  if (/^\d{6}$/.test(code)) {
    return 'A股'
  }

  // 包含 .HK = 港股
  if (code.includes('.HK') || code.includes('.hk')) {
    return '港股'
  }

  // 其他 = 美股
  return '美股'
}

// 查看股票详情（跳转到股票详情页）
function viewStockDetail(stockCode: string) {
  if (!stockCode) return
  // 跳转到股票详情页
  router.push({ name: 'StockDetail', params: { code: stockCode } })
}

// 卖出持仓
async function sellPosition(position: any) {
  if (!position || !position.code) return

  try {
    // 确认卖出
    await ElMessageBox.confirm(
      `确认卖出 ${position.name || position.code}？\n\n当前持仓：${position.quantity} 股\n均价：${fmtPrice(position.avg_cost)}\n最新价：${fmtPrice(position.last_price)}`,
      '卖出确认',
      {
        confirmButtonText: '确认卖出',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    // 提交卖出订单
    const payload = {
      side: 'sell' as const,
      code: position.code,
      quantity: position.quantity
    }

    const res = await paperApi.placeOrder(payload)
    if (res.success) {
      ElMessage.success('卖出成功')
      await refreshAll()
    } else {
      ElMessage.error(res.message || '卖出失败')
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('卖出失败:', error)
      ElMessage.error(error?.message || '卖出失败')
    }
  }
}

async function fetchAnalysisContext(analysisId: string) {
  try {
    analysisLoading.value = true
    analysisContext.value = null
    const res = await analysisApi.getResult(analysisId)
    analysisContext.value = res as any
  } catch (e) {
    // 忽略错误，仅用于展示
  } finally {
    analysisLoading.value = false
  }
}

onMounted(() => {
  let hasPrefill = false
  const qCode = String(route.query.code || '').trim()
  if (qCode) {
    order.value.code = qCode
    hasPrefill = true
  }
  const qSide = String(route.query.side || '').trim().toLowerCase()
  if (qSide === 'buy' || qSide === 'sell') {
    order.value.side = qSide as 'buy' | 'sell'
    hasPrefill = true
  }
  const qQty = Number(route.query.qty || route.query.quantity || 0)
  if (!Number.isNaN(qQty) && qQty > 0) {
    order.value.qty = Math.round(qQty)
    hasPrefill = true
  }
  // 可选：后续用于下单时带上分析ID
  const qAnalysisId = String(route.query.analysis_id || '').trim()
  if (qAnalysisId) {
    // 暂存于本地，等待提交订单时附带
    ;(order as any).analysis_id = qAnalysisId
    fetchAnalysisContext(qAnalysisId)
    hasPrefill = true
  }
  if (hasPrefill) {
    orderDialog.value = true
  }
  refreshAll()
})
</script>

<style scoped>
.paper-trading { padding: 16px; }
.header { display:flex; align-items:center; justify-content:space-between; margin-bottom: 12px; }
.title { display:flex; align-items:center; font-weight: 600; font-size: 16px; }
.card-hd { font-weight: 600; }
</style>