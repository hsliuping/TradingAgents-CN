<template>
  <div class="stock-screening">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1 class="page-title">
        <el-icon><Search /></el-icon>
        股票筛选
      </h1>
      <p class="page-description">
        通过多维度筛选条件，快速找到符合投资策略的优质股票
      </p>
    </div>

    <!-- Tab 切换 -->
    <el-tabs v-model="activeTab" class="screening-tabs">
      <el-tab-pane label="传统筛选" name="traditional">

    <!-- 筛选条件面板 -->
    <el-card class="filter-panel" shadow="never">
      <template #header>
        <div class="card-header">
          <div style="display: flex; align-items: center; gap: 12px;">
            <span>筛选条件</span>
            <el-tag v-if="currentDataSource" type="info" size="small" effect="plain">
              <el-icon style="vertical-align: middle; margin-right: 4px;"><Connection /></el-icon>
              当前数据源: {{ currentDataSource.name }}
              <span v-if="currentDataSource.token_source_display" style="margin-left: 4px; opacity: 0.8;">
                ({{ currentDataSource.token_source_display }})
              </span>
            </el-tag>
            <el-tag v-else type="warning" size="small">
              <el-icon style="vertical-align: middle; margin-right: 4px;"><Warning /></el-icon>
              无可用数据源
            </el-tag>
          </div>
          <div class="header-actions">
            <el-button type="text" @click="resetFilters">
              <el-icon><Refresh /></el-icon>
              重置
            </el-button>
          </div>
        </div>
      </template>

      <el-form :model="filters" label-width="120px" class="filter-form">
        <el-row :gutter="24">
          <!-- 股票代码/名称 -->
          <el-col :span="8">
            <el-form-item label="股票代码/名称">
              <el-input
                v-model="filters.keyword"
                placeholder="请输入股票代码或名称"
                clearable
              />
            </el-form-item>
          </el-col>

          <el-col :span="8">
            <el-form-item label="行业分类">
              <el-select
                v-model="filters.industry"
                placeholder="选择行业"
                multiple
                collapse-tags
                collapse-tags-tooltip
              >
                <el-option
                  v-for="industry in industryOptions"
                  :key="industry.value"
                  :label="industry.label"
                  :value="industry.value"
                />
              </el-select>
            </el-form-item>
          </el-col>

          <!-- 基础信息 -->
          <el-col :span="8">
            <el-form-item label="市场类型">
              <el-select v-model="filters.market" placeholder="选择市场" disabled>
                <el-option label="A股" value="A股" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="24">
          <el-col :span="8">
            <el-form-item label="市值范围">
              <el-select v-model="filters.marketCapRange" placeholder="选择市值范围">
                <el-option label="小盘股 (< 100亿)" value="small" />
                <el-option label="中盘股 (100-500亿)" value="medium" />
                <el-option label="大盘股 (> 500亿)" value="large" />
              </el-select>
            </el-form-item>
          </el-col>

          <!-- 财务指标 -->
          <el-col :span="8">
            <el-form-item label="市盈率 (PE)">
              <el-input-number
                v-model="filters.peRatio.min"
                placeholder="最小值"
                :min="0"
                :precision="2"
                style="width: 45%"
              />
              <span style="margin: 0 8px">-</span>
              <el-input-number
                v-model="filters.peRatio.max"
                placeholder="最大值"
                :min="0"
                :precision="2"
                style="width: 45%"
              />
            </el-form-item>
          </el-col>

          <el-col :span="8">
            <el-form-item label="市净率 (PB)">
              <el-input-number
                v-model="filters.pbRatio.min"
                placeholder="最小值"
                :min="0"
                :precision="2"
                style="width: 45%"
              />
              <span style="margin: 0 8px">-</span>
              <el-input-number
                v-model="filters.pbRatio.max"
                placeholder="最大值"
                :min="0"
                :precision="2"
                style="width: 45%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="24">
          <el-col :span="8">
            <el-form-item label="ROE (%)">
              <el-input-number
                v-model="filters.roe.min"
                placeholder="最小值"
                :min="0"
                :max="100"
                :precision="2"
                style="width: 45%"
              />
              <span style="margin: 0 8px">-</span>
              <el-input-number
                v-model="filters.roe.max"
                placeholder="最大值"
                :min="0"
                :max="100"
                :precision="2"
                style="width: 45%"
              />
            </el-form-item>
          </el-col>

          <!-- 技术指标 -->
          <el-col :span="8">
            <el-form-item label="涨跌幅 (%)">
              <el-input-number
                v-model="filters.changePercent.min"
                placeholder="最小值"
                :precision="2"
                style="width: 45%"
              />
              <span style="margin: 0 8px">-</span>
              <el-input-number
                v-model="filters.changePercent.max"
                placeholder="最大值"
                :precision="2"
                style="width: 45%"
              />
            </el-form-item>
          </el-col>

          <el-col :span="8">
            <el-form-item label="成交量">
              <el-select v-model="filters.volumeLevel" placeholder="选择成交量水平">
                <el-option label="活跃 (高成交量)" value="high" />
                <el-option label="正常 (中等成交量)" value="medium" />
                <el-option label="清淡 (低成交量)" value="low" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 技术形态暂不实现，先隐藏 -->
        <el-row :gutter="24" v-if="false">
          <el-col :span="8">
            <el-form-item label="技术形态">
              <el-select
                v-model="filters.technicalPattern"
                placeholder="选择技术形态"
                multiple
                collapse-tags
              >
                <el-option label="突破上升趋势" value="breakout_up" />
                <el-option label="回调买入机会" value="pullback" />
                <el-option label="底部反转" value="bottom_reversal" />
                <el-option label="强势整理" value="consolidation" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 筛选按钮 -->
        <el-row>
          <el-col :span="24">
            <div class="filter-actions">
              <el-button
                type="primary"
                @click="performScreening"
                :loading="screeningLoading"
                size="large"
              >
                <el-icon><Search /></el-icon>
                开始筛选
              </el-button>
              <el-button @click="resetFilters" size="large">
                重置条件
              </el-button>
            </div>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <!-- 筛选结果 -->
    <el-card v-if="screeningResults.length > 0" class="results-panel" shadow="never">
      <template #header>
        <div class="card-header">
          <span>筛选结果 ({{ screeningResults.length }}只股票)</span>
          <div class="header-actions">
            <el-button
              type="primary"
              @click="batchAnalyze"
              :disabled="selectedStocks.length === 0"
            >
              <el-icon><TrendCharts /></el-icon>
              批量分析 ({{ selectedStocks.length }})
            </el-button>
            <el-button type="text" @click="exportResults">
              <el-icon><Download /></el-icon>
              导出结果
            </el-button>
          </div>
        </div>
      </template>

      <!-- 结果表格 -->
      <el-table
        :data="paginatedResults"
        @selection-change="handleSelectionChange"
        stripe
        style="width: 100%"
      >
        <el-table-column type="selection" width="55" />

        <el-table-column prop="code" label="股票代码" width="120">
          <template #default="{ row }">
            <el-link type="primary" @click="viewStockDetail(row)">
              {{ row.symbol }}
            </el-link>
          </template>
        </el-table-column>

        <el-table-column prop="name" label="股票名称" width="150" />

        <el-table-column prop="industry" label="行业" width="120" />

        <el-table-column prop="close" label="当前价格" width="100" align="right">
          <template #default="{ row }">
            <span v-if="row.close">¥{{ row.close?.toFixed(2) }}</span>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="pct_chg" label="涨跌幅" width="100" align="right">
          <template #default="{ row }">
            <span v-if="row.pct_chg !== null && row.pct_chg !== undefined" :class="getChangeClass(row.pct_chg)">
              {{ row.pct_chg > 0 ? '+' : '' }}{{ row.pct_chg?.toFixed(2) }}%
            </span>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="total_mv" label="市值" width="120" align="right">
          <template #default="{ row }">
            {{ formatMarketCap(row.total_mv) }}
          </template>
        </el-table-column>

        <el-table-column prop="pe" label="市盈率" width="130" align="right">
          <template #default="{ row }">
            <span v-if="row.pe">
              {{ row.pe?.toFixed(2) }}
              <el-tag v-if="row.pe_is_realtime" type="success" size="small" style="margin-left: 4px">实时</el-tag>
            </span>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="pb" label="市净率" width="130" align="right">
          <template #default="{ row }">
            <span v-if="row.pb">
              {{ row.pb?.toFixed(2) }}
              <el-tag v-if="row.pe_is_realtime" type="success" size="small" style="margin-left: 4px">实时</el-tag>
            </span>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="roe" label="ROE(%)" width="110" align="right">
          <template #default="{ row }">
            <span v-if="row.roe !== null && row.roe !== undefined">{{ row.roe?.toFixed(2) }}%</span>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="board" label="板块" width="100">
          <template #default="{ row }">
            {{ row.board || '-' }}
          </template>
        </el-table-column>

        <el-table-column prop="exchange" label="交易所" width="140">
          <template #default="{ row }">
            {{ row.exchange || '-' }}
          </template>
        </el-table-column>

        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button type="text" size="small" @click="analyzeSingle(row)">
              分析
            </el-button>
            <el-button type="text" size="small" @click="toggleFavorite(row)">
              <el-icon><Star /></el-icon>
              {{ isFavorited(row.symbol) ? '取消自选' : '股票关注列表' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[20, 50, 100]"
          :total="screeningResults.length"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <!-- 空状态 -->
    <el-empty
      v-else-if="!screeningLoading && hasSearched"
      description="未找到符合条件的股票"
      :image-size="200"
    >
      <el-button type="primary" @click="resetFilters">
        重新筛选
      </el-button>
    </el-empty>

      </el-tab-pane>

      <!-- 智能筛选 Tab -->
      <el-tab-pane label="智能筛选" name="intelligent">
        <div class="intelligent-screening">
          <div class="chat-body">
            <div ref="aiMessagesContainer" class="messages-container">
              <el-empty
                v-if="aiMessages.length === 0 && !aiLoading"
                description="输入选股需求开始对话，例如：帮我选几只低估值的银行股"
                :image-size="80"
              />
              <div v-else class="messages-list">
                <div v-if="aiLoading" class="message-item message-assistant thinking-bubble">
                  <div class="message-avatar"><el-icon><TrendCharts /></el-icon></div>
                  <div class="message-content thinking-content">
                    <span class="thinking-text">正在分析选股需求</span>
                    <span class="thinking-dots"><span class="dot">.</span><span class="dot">.</span><span class="dot">.</span></span>
                  </div>
                </div>
                <div v-for="(msg, idx) in aiMessages" :key="idx"
                  :class="['message-item', msg.role === 'user' ? 'message-user' : 'message-assistant']">
                  <template v-if="msg.role === 'user'">
                    <div class="message-content"><div class="message-text">{{ msg.content }}</div></div>
                    <div class="message-avatar"><el-icon><User /></el-icon></div>
                  </template>
                  <template v-else>
                    <div class="message-avatar"><el-icon><TrendCharts /></el-icon></div>
                    <div class="message-content">
                      <div class="message-text markdown-content" v-html="renderScreeningMarkdown(msg.content)"></div>
                      <div v-if="msg.tools_used?.length" class="message-tools">
                        <el-tag v-for="t in msg.tools_used" :key="t" size="small" type="info">{{ t }}</el-tag>
                      </div>
                      <div v-if="msg.phase === 'confirmation' && idx === aiMessages.length - 1 && !aiLoading" class="confirmation-actions">
                        <el-button type="primary" size="small" @click="sendAiMessage('按原需求筛选')">按原需求筛选</el-button>
                        <el-button type="success" size="small" @click="sendAiMessage('采纳建议后筛选')">采纳建议后筛选</el-button>
                      </div>
                      <div v-if="msg.phase === 'planning' && idx === aiMessages.length - 1 && !aiLoading" class="confirmation-actions">
                        <el-button type="primary" size="small" @click="sendAiMessage('执行筛选方案')">执行筛选方案</el-button>
                        <el-button type="default" size="small" @click="sendAiMessage('重新描述需求')">重新描述需求</el-button>
                      </div>
                      <div v-if="msg.stocks?.length" class="stock-cards">
                        <el-card v-for="s in msg.stocks" :key="s.code" class="stock-card" shadow="hover">
                          <div class="stock-card-header">
                            <span class="stock-name">{{ s.name }}</span>
                            <span class="stock-code">{{ s.code }}</span>
                            <el-tag size="small" type="info">{{ s.industry }}</el-tag>
                          </div>
                          <div class="stock-card-metrics">
                            <span v-if="s.price != null">价格: {{ s.price?.toFixed(2) }}</span>
                            <span v-if="s.pe != null">PE: {{ s.pe?.toFixed(1) }}</span>
                            <span v-if="s.pb != null">PB: {{ s.pb?.toFixed(2) }}</span>
                            <span v-if="s.pct_change != null" :class="(s.pct_change ?? 0) >= 0 ? 'text-red' : 'text-green'">
                              {{ (s.pct_change ?? 0) >= 0 ? '+' : '' }}{{ s.pct_change?.toFixed(2) }}%
                            </span>
                          </div>
                          <div class="stock-card-reason">{{ s.reason }}</div>
                        </el-card>
                      </div>
                    </div>
                  </template>
                </div>
              </div>
            </div>
            <div class="input-area">
              <div class="input-row">
                <el-input v-model="aiInput" type="textarea" :rows="2" :autosize="{ minRows: 2, maxRows: 5 }"
                  placeholder="输入选股需求，如：帮我选几只低估值的银行股、PE低于20的消费股"
                  :disabled="aiLoading" @keydown.enter.ctrl="handleAiSend" />
                <el-button type="primary" :loading="aiLoading" :disabled="!aiInput.trim()" class="send-btn" @click="handleAiSend">发送</el-button>
              </div>
              <div class="input-tip-row">
                <span class="input-tip">Ctrl+Enter 发送</span>
                <el-button v-if="aiMessages.length > 0 && !aiLoading" type="default" size="small" link @click="handleClearAi">清空对话</el-button>
              </div>
            </div>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Collection, TrendCharts, Download, Star, Setting, Connection, Warning, User } from '@element-plus/icons-vue'
import { marked } from 'marked'
import type { StockInfo } from '@/types/analysis'
import { screeningApi, type FieldConfigResponse, type FieldInfo, type ScreeningMessageItem, type StockRecommendation } from '@/api/screening'
import { favoritesApi } from '@/api/favorites'
import { getCurrentDataSource } from '@/api/sync'
import { normalizeMarketForAnalysis, exchangeCodeToMarket, getMarketByStockCode } from '@/utils/market'

// Markdown 渲染
marked.setOptions({ breaks: true, gfm: true })
const renderScreeningMarkdown = (content: string): string => {
  if (!content?.trim()) return ''
  try { return marked.parse(content) as string } catch { return content }
}

// Tab 状态
const activeTab = ref('traditional')

// ---- 智能筛选 ----
interface AiDisplayMessage {
  role: 'user' | 'assistant'
  content: string
  tools_used?: string[]
  stocks?: StockRecommendation[]
  phase?: 'confirmation' | 'planning' | 'result'
}
const aiMessages = ref<AiDisplayMessage[]>([])
const aiInput = ref('')
const aiLoading = ref(false)
const aiMessagesContainer = ref<HTMLElement | null>(null)

const scrollAiToBottom = () => {
  nextTick(() => {
    if (aiMessagesContainer.value) {
      aiMessagesContainer.value.scrollTop = aiMessagesContainer.value.scrollHeight
    }
  })
}

const loadAiConversation = async () => {
  try {
    const res = await screeningApi.getIntelligentConversation()
    const msgs = res.messages ?? (res as any)?.data?.messages ?? []
    if (msgs.length) {
      aiMessages.value = msgs.map((m: ScreeningMessageItem) => ({
        role: m.role,
        content: m.content,
        tools_used: m.tools_used,
        stocks: m.stocks,
        phase: m.phase,
      }))
      scrollAiToBottom()
    }
  } catch { /* 静默 */ }
}

const sendAiMessage = async (text: string) => {
  if (!text.trim() || aiLoading.value) return
  aiMessages.value.push({ role: 'user', content: text })
  aiInput.value = ''
  scrollAiToBottom()
  aiLoading.value = true
  try {
    const res = await screeningApi.intelligentChat(text)
    const data = (res as any)?.data ?? res
    aiMessages.value.push({
      role: 'assistant',
      content: data.reply,
      tools_used: data.tools_used?.length ? data.tools_used : undefined,
      stocks: data.stocks?.length ? data.stocks : undefined,
      phase: data.phase,
    })
    scrollAiToBottom()
  } catch (e: unknown) {
    const errMsg = e instanceof Error ? e.message : '请求失败，请稍后重试'
    ElMessage.error(errMsg)
    aiMessages.value.push({ role: 'assistant', content: `抱歉，处理您的请求时出错：${errMsg}` })
  } finally {
    aiLoading.value = false
  }
}

const handleAiSend = () => sendAiMessage(aiInput.value)

const handleClearAi = () => {
  ElMessageBox.confirm('确定清空智能筛选的对话记录吗？', '提示', {
    confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning'
  }).then(async () => {
    try {
      await screeningApi.clearIntelligentConversation()
      aiMessages.value = []
      ElMessage.success('已清空对话')
    } catch (e: unknown) {
      ElMessage.error(e instanceof Error ? e.message : '清空失败')
    }
  }).catch(() => {})
}

// ---- 传统筛选 ----
// 响应式数据
const screeningLoading = ref(false)
const hasSearched = ref(false)
const screeningResults = ref<StockInfo[]>([])
const selectedStocks = ref<StockInfo[]>([])
const currentPage = ref(1)
const pageSize = ref(20)

// 路由 & 自选集
const router = useRouter()
const favoriteSet = ref<Set<string>>(new Set())

// 当前数据源
const currentDataSource = ref<{
  name: string
  priority: number
  description: string
  token_source?: 'database' | 'env'
  token_source_display?: string
} | null>(null)

// 字段配置
const fieldConfig = ref<FieldConfigResponse | null>(null)
const fieldsLoading = ref(false)

// 筛选条件
const filters = reactive({
  keyword: '',
  market: 'A股',
  industry: [] as string[],
  marketCapRange: '',
  peRatio: { min: null, max: null },
  pbRatio: { min: null, max: null },
  roe: { min: null, max: null },
  changePercent: { min: null, max: null },
  volumeLevel: '',
  technicalPattern: [] as string[]
})

// 行业选项（动态加载）
const industryOptions = ref<Array<{label: string, value: string, count?: number}>>([])

// 计算属性
const paginatedResults = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return screeningResults.value.slice(start, end)
})

// 方法
const performScreening = async () => {
  screeningLoading.value = true
  hasSearched.value = true

  try {
    // 基于用户真实选择构建 conditions（只拼选中的项，不注入默认技术条件）
    const children: any[] = []

    // 股票代码/名称搜索
    if (filters.keyword) {
      // 使用后端支持的虚拟字段 keyword，后端会自动匹配 symbol 或 name
      children.push({ field: 'keyword', op: 'contains', value: filters.keyword })
    }

    // 市场类型（仅作为演示，实际后端暂用CN）
    if (filters.market) {
      // 可作为 universe 选择；当未实现时可忽略
    }

    // 行业分类（如果用户选择了行业）
    if (filters.industry && filters.industry.length > 0) {
      // 直接使用数据库中的行业名称，无需映射
      children.push({ field: 'industry', op: 'in', value: filters.industry })
    }

    // 市值范围映射为区间（单位：亿元 → 转换为万元以匹配后端 market_cap 单位）
    const capRangeMap: Record<string, [number, number] | null> = {
      small: [0, 100 * 10000], // <100亿 → < 100*1e4 万元
      medium: [100 * 10000, 500 * 10000],
      large: [500 * 10000, Number.MAX_SAFE_INTEGER],
    }
    const cap = filters.marketCapRange ? capRangeMap[filters.marketCapRange] : null
    if (cap) {
      children.push({ field: 'market_cap', op: 'between', value: cap })
    }
    // 市盈率/市净率/ROE 条件（仅当填写任一端时才拼接）
    if (filters.peRatio.min != null || filters.peRatio.max != null) {
      const lo = filters.peRatio.min ?? 0
      const hi = filters.peRatio.max ?? Number.MAX_SAFE_INTEGER
      children.push({ field: 'pe', op: 'between', value: [lo, hi] })
    }
    if (filters.pbRatio.min != null || filters.pbRatio.max != null) {
      const lo = filters.pbRatio.min ?? 0
      const hi = filters.pbRatio.max ?? Number.MAX_SAFE_INTEGER
      children.push({ field: 'pb', op: 'between', value: [lo, hi] })
    }
    if (filters.roe.min != null || filters.roe.max != null) {
      const lo = filters.roe.min ?? 0
      const hi = filters.roe.max ?? 100
      children.push({ field: 'roe', op: 'between', value: [lo, hi] })
    }

    // 涨跌幅条件
    if (filters.changePercent.min != null || filters.changePercent.max != null) {
      const lo = filters.changePercent.min ?? -100
      const hi = filters.changePercent.max ?? 100
      children.push({ field: 'pct_chg', op: 'between', value: [lo, hi] })
    }

    // 成交量条件（映射为成交额范围，单位：元）
    if (filters.volumeLevel) {
      const volumeRangeMap: Record<string, [number, number]> = {
        high: [1000000000, Number.MAX_SAFE_INTEGER],    // 高成交量：>10亿元
        medium: [300000000, 1000000000],                 // 中等成交量：3亿-10亿元
        low: [0, 300000000]                              // 低成交量：<3亿元
      }
      const volumeRange = volumeRangeMap[filters.volumeLevel]
      if (volumeRange) {
        children.push({ field: 'amount', op: 'between', value: volumeRange })
      }
    }

    // 明确指定：不加任何技术指标相关条件

    const payload = {
      market: 'CN' as const,
      date: undefined,
      adj: 'qfq' as const,
      conditions: { logic: 'AND', children },
      order_by: [{ field: 'market_cap', direction: 'desc' as const }],
      limit: 500,
      offset: 0,
    }

    // 调试日志：打印请求payload
    console.log('🔍 筛选请求 payload:', JSON.stringify(payload, null, 2))
    console.log('🔍 筛选条件 children:', children)

    const res = await screeningApi.run(payload, { timeout: 120000 })
    const data = (res as any)?.data || res // ApiClient封装会返回 {success,data} 格式
    const items = data?.items || []

    // 直接使用后端返回的数据，字段名已统一
    screeningResults.value = items.map((it: any) => ({
      symbol: it.symbol || it.code,  // 主字段
      code: it.symbol || it.code,    // 兼容字段
      name: it.name || it.symbol || it.code,  // 使用股票名称，如果没有则用代码
      market: it.market || 'A股',
      industry: it.industry,
      area: it.area,
      board: it.board,  // 板块（主板、创业板、科创板等）
      exchange: it.exchange,  // 交易所（上海证券交易所、深圳证券交易所等）

      // 市值信息
      total_mv: it.total_mv,
      circ_mv: it.circ_mv,

      // 财务指标
      pe: it.pe,
      pb: it.pb,
      pe_ttm: it.pe_ttm,
      pb_mrq: it.pb_mrq,
      roe: it.roe,

      // 交易数据
      close: it.close,
      pct_chg: it.pct_chg,
      amount: it.amount,
      turnover_rate: it.turnover_rate,
      volume_ratio: it.volume_ratio,

      // 技术指标
      ma20: it.ma20,
      rsi14: it.rsi14,
      kdj_k: it.kdj_k,
      kdj_d: it.kdj_d,
      kdj_j: it.kdj_j,
      dif: it.dif,
      dea: it.dea,
      macd_hist: it.macd_hist,
    }))

    ElMessage.success(`筛选完成，找到 ${screeningResults.value.length} 只股票`)
  } catch (error) {
    ElMessage.error('筛选失败，请重试')
  } finally {
    screeningLoading.value = false
  }
}

const generateMockResults = (): StockInfo[] => {
  const mockStocks = [
    { symbol: '000001', code: '000001', name: '平安银行', industry: '银行', close: 12.50, pct_chg: 2.1, total_mv: 2400, pe: 5.2, pb: 0.8 },
    { symbol: '000002', code: '000002', name: '万科A', industry: '房地产', close: 18.30, pct_chg: -1.5, total_mv: 2100, pe: 8.5, pb: 1.2 },
    { symbol: '000858', code: '000858', name: '五粮液', industry: '食品饮料', close: 168.50, pct_chg: 3.2, total_mv: 6500, pe: 25.3, pb: 4.5 }
  ]

  return mockStocks.map(stock => ({
    ...stock,
    market: filters.market
  }))
}

const resetFilters = () => {
  Object.assign(filters, {
    keyword: '',
    market: 'A股',
    industry: [],
    marketCapRange: '',
    peRatio: { min: null, max: null },
    pbRatio: { min: null, max: null },
    roe: { min: null, max: null },
    changePercent: { min: null, max: null },
    volumeLevel: '',
    technicalPattern: []
  })

  screeningResults.value = []
  selectedStocks.value = []
  hasSearched.value = false
  currentPage.value = 1
}

const handleSelectionChange = (selection: StockInfo[]) => {
  selectedStocks.value = selection
}

const batchAnalyze = async () => {
  if (selectedStocks.value.length === 0) {
    ElMessage.warning('请先选择要分析的股票')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要对选中的 ${selectedStocks.value.length} 只股票进行批量分析吗？`,
      '确认批量分析',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'info'
      }
    )

    // 跳转到批量分析页面（携带统一市场参数）
    router.push({
      name: 'BatchAnalysis',
      query: {
        stocks: selectedStocks.value.map(s => s.symbol).join(','),
        market: normalizeMarketForAnalysis(filters.market)
      }
    })
  } catch {
    // 用户取消
  }
}


const analyzeSingle = (stock: StockInfo) => {
  router.push({
    name: 'SingleAnalysis',
    query: {
      stock: stock.symbol,
      market: normalizeMarketForAnalysis((stock as any).market || filters.market)
    }
  })
}

const viewStockDetail = (stock: StockInfo) => {
  // 跳转到股票详情页面
  router.push({
    name: 'StockDetail',
    params: { code: stock.symbol }
  })
}

const isFavorited = (code: string) => favoriteSet.value.has(code)

const toggleFavorite = async (stock: StockInfo) => {
  try {
    const code = stock.symbol
    if (favoriteSet.value.has(code)) {
      // 取消自选
      const res = await favoritesApi.remove(code)
      if ((res as any)?.success === false) throw new Error((res as any)?.message || '取消失败')
      favoriteSet.value.delete(code)
      ElMessage.success(`已取消自选：${stock.name || code}`)
    } else {
      // 股票关注列表
      // 根据股票代码判断市场类型
      let marketType = 'A股'
      if ((stock as any).market) {
        // 如果有 market 字段，尝试转换（可能是交易所代码如 "sz", "sh"）
        marketType = exchangeCodeToMarket((stock as any).market)
      } else {
        // 否则根据股票代码判断
        marketType = getMarketByStockCode(code) || 'A股'
      }

      const payload = {
        symbol: code,
        stock_code: code,  // 兼容字段
        stock_name: stock.name || code,
        market: marketType
      }
      const res = await favoritesApi.add(payload)
      if ((res as any)?.success === false) throw new Error((res as any)?.message || '添加失败')
      favoriteSet.value.add(code)
      ElMessage.success(`已股票关注列表：${stock.name || code}`)
    }
  } catch (error: any) {
    ElMessage.error(error?.message || '自选操作失败')
  }
}

const exportResults = () => {
  // 导出筛选结果
  ElMessage.info('导出功能开发中...')
}

const getChangeClass = (changePercent: number) => {
  if (changePercent > 0) return 'text-red'
  if (changePercent < 0) return 'text-green'
  return ''
}

const formatMarketCap = (marketCap: number) => {
  if (marketCap >= 10000) {
    return `${(marketCap / 10000).toFixed(2)}万亿`
  } else {
    return `${marketCap.toFixed(2)}亿`
  }
}

const handleSizeChange = (size: number) => {
  pageSize.value = size
  currentPage.value = 1
}

const handleCurrentChange = (page: number) => {
  currentPage.value = page
}

// 获取字段配置
const loadFieldConfig = async () => {
  fieldsLoading.value = true
  try {
    const response = await screeningApi.getFields()
    fieldConfig.value = response.data || response
    console.log('字段配置加载成功:', fieldConfig.value)
  } catch (error) {
    console.error('加载字段配置失败:', error)
    ElMessage.error('加载字段配置失败')
  } finally {
    fieldsLoading.value = false
  }
}

// 加载行业列表
const loadIndustries = async () => {
  try {
    const response = await screeningApi.getIndustries()
    const data = response.data || response
    industryOptions.value = data.industries || []
    console.log('行业列表加载成功:', industryOptions.value.length, '个行业')
  } catch (error) {
    console.error('加载行业列表失败:', error)
    ElMessage.error('加载行业列表失败')
    // 如果加载失败，使用默认的行业列表
    industryOptions.value = [
      { label: '银行', value: '银行' },
      { label: '证券', value: '证券' },
      { label: '保险', value: '保险' },
      { label: '房地产', value: '房地产' },
      { label: '医药生物', value: '医药生物' }
    ]
  }
}

// 加载自选列表，初始化 favoriteSet
const loadFavorites = async () => {
  try {
    const resp = await favoritesApi.list()
    const list = (resp as any)?.data || resp
    const set = new Set<string>()
    ;(list || []).forEach((item: any) => {
      // 兼容新旧字段
      const code = item.symbol || item.stock_code || item.code
      if (code) set.add(code)
    })
    favoriteSet.value = set
  } catch (e) {
    console.warn('加载自选列表失败，可能未登录或接口不可用。', e)
  }
}

// 获取当前数据源
const loadCurrentDataSource = async () => {
  try {
    const response = await getCurrentDataSource()
    if (response.success && response.data) {
      currentDataSource.value = response.data
    }
  } catch (e) {
    console.warn('获取当前数据源失败', e)
  }
}

// 生命周期
onMounted(() => {
  // 加载字段配置和行业列表
  loadFieldConfig()
  loadIndustries()
  // 初始化自选状态
  loadFavorites()
  // 加载当前数据源
  loadCurrentDataSource()
  // 加载智能筛选对话历史
  loadAiConversation()
})
</script>

<style lang="scss" scoped>
.stock-screening {
  .page-header {
    margin-bottom: 24px;

    .page-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 24px;
      font-weight: 600;
      color: var(--el-text-color-primary);
      margin: 0 0 8px 0;
    }

    .page-description {
      color: var(--el-text-color-regular);
      margin: 0;
    }
  }

  .filter-panel {
    margin-bottom: 24px;

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;

      .header-actions {
        display: flex;
        gap: 8px;
      }
    }

    .filter-form {
      .filter-actions {
        display: flex;
        justify-content: center;
        gap: 16px;
        margin-top: 24px;
      }
    }
  }

  .results-panel {
    .pagination-wrapper {
      display: flex;
      justify-content: center;
      margin-top: 24px;
    }
  }

  .text-red {
    color: #f56c6c;
  }

  .text-green {
    color: #67c23a;
  }

  // ---- 智能筛选样式 ----
  .screening-tabs {
    :deep(.el-tabs__content) {
      overflow: visible;
    }
  }

  .intelligent-screening {
    .chat-body {
      display: flex;
      flex-direction: column;
      min-height: 0;
      height: calc(100vh - 220px);
      border: 1px solid var(--el-border-color-lighter);
      border-radius: 8px;
      background: var(--el-bg-color);
    }

    .messages-container {
      flex: 1;
      overflow-y: auto;
      padding: 20px 24px;
      min-height: 0;
    }

    .messages-list {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .message-item {
      display: flex;
      gap: 12px;
      align-items: flex-start;
      max-width: 92%;

      &.message-user {
        align-self: flex-end;
        flex-direction: row-reverse;

        .message-avatar {
          background: var(--el-color-primary-light-9);
          color: var(--el-color-primary);
        }
        .message-content {
          background: var(--el-color-primary);
          color: #fff;
          border-radius: 12px;
          padding: 10px 16px;
        }
        .message-text { color: inherit; }
      }

      &.message-assistant {
        align-self: flex-start;

        .message-avatar {
          background: var(--el-fill-color-light);
          color: var(--el-text-color-regular);
        }
        .message-content {
          background: var(--el-fill-color-lighter);
          border-radius: 12px;
          padding: 12px 20px;
        }
      }
    }

    .message-avatar {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      font-size: 16px;
    }

    .message-text {
      word-break: break-word;
      line-height: 1.7;
      font-size: 14px;

      &.markdown-content {
        :deep(h1), :deep(h2), :deep(h3), :deep(h4) { margin: 12px 0 8px; font-weight: 600; }
        :deep(h1:first-child), :deep(h2:first-child), :deep(h3:first-child) { margin-top: 0; }
        :deep(h1) { font-size: 18px; }
        :deep(h2) { font-size: 16px; }
        :deep(h3) { font-size: 15px; }
        :deep(p) { margin: 6px 0; }
        :deep(ul), :deep(ol) { margin: 6px 0; padding-left: 24px; }
        :deep(li) { margin: 3px 0; }
        :deep(strong) { font-weight: 600; }
        :deep(code) { background: var(--el-fill-color); padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }
        :deep(table) { border-collapse: collapse; margin: 8px 0; font-size: 13px; }
        :deep(th), :deep(td) { border: 1px solid var(--el-border-color-lighter); padding: 4px 10px; }
        :deep(th) { background: var(--el-fill-color-light); font-weight: 600; }
      }
    }

    .message-tools {
      margin-top: 8px;
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
    }

    .thinking-bubble { opacity: 0.95; }
    .thinking-content { display: flex; align-items: baseline; gap: 2px; }
    .thinking-text { color: var(--el-text-color-secondary); }
    .thinking-dots .dot {
      animation: screening-blink 1.4s infinite;
      display: inline-block;
      width: 0.5em;
    }
    .thinking-dots .dot:nth-child(1) { animation-delay: 0s; }
    .thinking-dots .dot:nth-child(2) { animation-delay: 0.2s; }
    .thinking-dots .dot:nth-child(3) { animation-delay: 0.4s; }

    .confirmation-actions {
      margin-top: 10px;
      display: flex;
      gap: 8px;
    }

    .stock-cards {
      margin-top: 12px;
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: 12px;
    }

    .stock-card {
      :deep(.el-card__body) { padding: 12px 16px; }

      .stock-card-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;

        .stock-name { font-weight: 600; font-size: 15px; }
        .stock-code { color: var(--el-text-color-secondary); font-size: 13px; }
      }

      .stock-card-metrics {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        font-size: 13px;
        color: var(--el-text-color-regular);
        margin-bottom: 8px;
      }

      .stock-card-reason {
        font-size: 13px;
        color: var(--el-text-color-secondary);
        line-height: 1.5;
      }
    }

    .input-area {
      flex-shrink: 0;
      padding: 12px 16px;
      border-top: 1px solid var(--el-border-color-lighter);

      .input-row {
        display: flex;
        gap: 12px;
        align-items: flex-end;
      }

      .send-btn {
        flex-shrink: 0;
        height: 56px;
        padding: 0 24px;
      }

      .input-tip-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-top: 4px;
      }

      .input-tip {
        font-size: 12px;
        color: var(--el-text-color-placeholder);
      }

      :deep(.el-textarea__inner) { resize: none; }
    }
  }
}

@keyframes screening-blink {
  0%, 60%, 100% { opacity: 0.2; }
  30% { opacity: 1; }
}
</style>


