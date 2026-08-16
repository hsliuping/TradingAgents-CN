<template>
  <div class="memory-page">
    <div class="page-header">
      <div class="header-left">
        <h1>
          <el-icon class="header-icon"><Coin /></el-icon>
          股票对象记忆
        </h1>
        <span class="subtitle">只展示带市场、标的、日期、结论的对象化长期记忆，原始自由文本已从用户视图隐藏。</span>
      </div>
      <div class="header-right">
        <el-button @click="fetchAll" :loading="loading || searching">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-popconfirm
          title="确定要清除全部股票对象记忆？此操作不可恢复。"
          confirm-button-text="确认清除"
          cancel-button-text="取消"
          @confirm="handleDeleteAllObjects"
        >
          <template #reference>
            <el-button type="danger" plain :disabled="objectMemoryTotal === 0">
              <el-icon><Delete /></el-icon>
              清除全部对象记忆
            </el-button>
          </template>
        </el-popconfirm>
      </div>
    </div>

    <el-alert
      v-if="!stats.enabled"
      title="记忆功能未启用"
      description="请在 .env 中设置 MEM0_ENABLED=true 并配置 LLM API Key 以启用对象化记忆。"
      type="warning"
      show-icon
      :closable="false"
      class="status-alert"
    />
    <el-alert
      v-else-if="stats.available === false"
      title="记忆服务不可用"
      :description="stats.message || 'mem0 初始化失败，请检查配置。'"
      type="error"
      show-icon
      :closable="false"
      class="status-alert"
    />

    <el-card shadow="never" class="overview-card">
      <div class="overview-item">
        <div class="overview-label">对象记忆总数</div>
        <div class="overview-value">{{ objectMemoryTotal }}</div>
      </div>
      <div class="overview-item">
        <div class="overview-label">当前结果</div>
        <div class="overview-value">{{ isSearchMode ? memories.length : totalMemories }}</div>
      </div>
      <div class="overview-item overview-note">
        <div class="overview-label">当前模式</div>
        <div class="overview-badges">
          <el-tag type="warning" effect="plain">analysis_insight</el-tag>
          <el-tag type="info" effect="plain">stock_analysis</el-tag>
          <el-tag effect="plain">stock</el-tag>
        </div>
      </div>
    </el-card>

    <el-card shadow="never" class="filter-card">
      <el-row :gutter="16" align="middle">
        <el-col :xs="24" :md="10">
          <el-input
            v-model="searchQuery"
            placeholder="搜索结论、建议或证据..."
            clearable
            @keyup.enter="handleSearch"
            @clear="handleClearSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
            <template #append>
              <el-button @click="handleSearch" :loading="searching">搜索</el-button>
            </template>
          </el-input>
        </el-col>
        <el-col :xs="12" :md="5">
          <el-input
            v-model="symbolFilter"
            placeholder="股票代码，如 000858"
            clearable
            @keyup.enter="handleFilterChange"
            @clear="handleFilterChange"
          />
        </el-col>
        <el-col :xs="12" :md="4">
          <el-select
            v-model="marketFilter"
            placeholder="全部市场"
            clearable
            @change="handleFilterChange"
            style="width: 100%"
          >
            <el-option
              v-for="option in marketOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-col>
        <el-col :xs="24" :md="5" class="filter-actions">
          <el-button @click="handleResetFilters">重置筛选</el-button>
          <el-button
            type="danger"
            plain
            :disabled="selectedIds.length === 0"
            @click="handleBatchDelete"
          >
            <el-icon><Delete /></el-icon>
            删除选中 ({{ selectedIds.length }})
          </el-button>
        </el-col>
      </el-row>
      <div class="filter-hint">
        <span v-if="isSearchMode">语义搜索结果：{{ memories.length }} 条</span>
        <span v-else>当前筛选命中：{{ totalMemories }} 条</span>
        <span v-if="hasActiveFilters">已启用对象筛选</span>
      </div>
    </el-card>

    <el-card shadow="never" class="list-card" v-loading="loading || searching">
      <div v-if="memoryCards.length" class="memory-grid">
        <el-row :gutter="16">
          <el-col
            v-for="item in memoryCards"
            :key="item.id"
            :xs="24"
            :sm="12"
            :xl="8"
          >
            <el-card shadow="hover" class="memory-object-card">
              <template #header>
                <div class="card-header">
                  <div class="card-title-row">
                    <el-checkbox
                      :model-value="isSelected(item.id)"
                      @change="toggleSelected(item.id, $event)"
                    />
                    <div class="identity-block">
                      <div class="identity-main">
                        <span class="symbol-text">{{ item.symbol }}</span>
                        <el-tag size="small">{{ item.marketLabel }}</el-tag>
                        <el-tag :type="getScopeColor(item.scope)" size="small" effect="plain">
                          {{ item.scopeLabel }}
                        </el-tag>
                      </div>
                      <div class="identity-sub">{{ item.objectKey }}</div>
                    </div>
                  </div>
                  <div class="card-actions">
                    <el-tag
                      v-if="isSearchMode"
                      :type="getScoreTagType(item.score)"
                      size="small"
                      effect="plain"
                    >
                      相关度 {{ formatScore(item.score) }}
                    </el-tag>
                    <el-popconfirm
                      title="确定删除这条对象记忆？"
                      @confirm="handleDeleteOne(item.id)"
                    >
                      <template #reference>
                        <el-button type="danger" text size="small">
                          <el-icon><Delete /></el-icon>
                        </el-button>
                      </template>
                    </el-popconfirm>
                  </div>
                </div>
              </template>

              <div class="card-meta">
                <span>分析日期：{{ item.analysisDate || '-' }}</span>
                <span>记录时间：{{ formatTime(item.timestamp) }}</span>
              </div>

              <div class="card-section">
                <div class="section-label">结论</div>
                <p class="section-text">{{ item.summary }}</p>
              </div>

              <div v-if="item.recommendation" class="card-section">
                <div class="section-label">建议</div>
                <p class="section-text accent-text">{{ item.recommendation }}</p>
              </div>

              <div v-if="item.nextChecks.length" class="card-section">
                <div class="section-label">后续检查</div>
                <div class="tag-list">
                  <el-tag
                    v-for="check in item.nextChecks"
                    :key="check"
                    class="detail-tag"
                    size="small"
                    type="warning"
                    effect="plain"
                  >
                    {{ check }}
                  </el-tag>
                </div>
              </div>

              <div v-if="item.evidence.length" class="card-section">
                <div class="section-label">证据</div>
                <div class="tag-list">
                  <el-tag
                    v-for="evidence in item.evidence"
                    :key="evidence"
                    class="detail-tag"
                    size="small"
                    type="info"
                    effect="plain"
                  >
                    {{ evidence }}
                  </el-tag>
                </div>
              </div>

              <div class="card-footer">
                <span>来源：{{ item.source }}</span>
                <span v-if="item.taskId">任务：{{ item.taskId }}</span>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>

      <el-empty v-else-if="!loading && !searching" :image-size="120">
        <template #description>
          <p v-if="isSearchMode">没有匹配到对象化记忆，换个关键词试试。</p>
          <p v-else-if="hasActiveFilters">当前筛选下没有对象化股票记忆。</p>
          <p v-else>暂无对象化股票记忆，新的分析完成后会在这里生成卡片。</p>
        </template>
      </el-empty>

      <div class="pagination-wrapper" v-if="!isSearchMode && totalMemories > pageSize">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[12, 24, 48]"
          :total="totalMemories"
          layout="total, sizes, prev, pager, next"
          @size-change="fetchList"
          @current-change="fetchList"
        />
      </div>
    </el-card>

    <!-- 偏好与纪律记忆（user_preference + trade_pattern）-->
    <el-card shadow="never" class="preference-card">
      <template #header>
        <div class="preference-header">
          <div class="preference-title">
            <el-icon><Memo /></el-icon>
            <span>我的偏好与纪律记忆</span>
            <el-tag size="small" effect="plain">user_preference</el-tag>
            <el-tag size="small" type="warning" effect="plain">trade_pattern</el-tag>
          </div>
          <div class="preference-actions">
            <el-button :loading="preferenceLoading" @click="fetchPreferenceList">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
        </div>
        <p class="preference-hint">
          这里展示助手通过 `remember_this` 工具登记的用户偏好，以及交易复盘和投资计划同步的纪律要点。
          可以在对话中直接说"请记住……"让助手主动记下偏好。
        </p>
      </template>

      <div v-loading="preferenceLoading">
        <el-empty v-if="!preferenceList.length" :image-size="100">
          <template #description>
            <p>暂无偏好/纪律记忆。试试在助手对话中说："请记住我偏好分红率高的蓝筹股"。</p>
          </template>
        </el-empty>

        <div v-else class="preference-list">
          <div
            v-for="item in preferenceList"
            :key="item.id"
            class="preference-item"
          >
            <div class="preference-item-header">
              <el-tag
                :type="item.scope === 'trade_pattern' ? 'warning' : 'primary'"
                size="small"
                effect="plain"
              >
                {{ item.scope === 'trade_pattern' ? '交易纪律' : '用户偏好' }}
              </el-tag>
              <span class="preference-item-time">{{ formatTime(item.created_at || item.updated_at || '') }}</span>
              <el-popconfirm
                title="确定删除这条记忆？"
                @confirm="handleDeletePreference(item.id)"
              >
                <template #reference>
                  <el-button type="danger" text size="small">
                    <el-icon><Delete /></el-icon>
                  </el-button>
                </template>
              </el-popconfirm>
            </div>
            <p class="preference-item-content">{{ item.memory }}</p>
            <div v-if="item.metadata && Object.keys(item.metadata).length" class="preference-item-meta">
              <el-tag
                v-for="(value, key) in normalizeMetadataTags(item.metadata)"
                :key="key"
                size="small"
                effect="plain"
                class="meta-tag"
              >
                {{ key }}: {{ value }}
              </el-tag>
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 智能助手事实记忆（assistant_memory_facts）-->
    <el-card shadow="never" class="fact-card">
      <template #header>
        <div class="fact-header">
          <div class="fact-title">
            <el-icon><Memo /></el-icon>
            <span>智能助手事实记忆</span>
            <el-tag size="small" effect="plain">assistant_memory_facts</el-tag>
          </div>
          <div class="fact-actions">
            <el-input
              v-model="factSearch"
              placeholder="搜索事实内容或主题..."
              clearable
              style="width: 280px"
              @keyup.enter="fetchFacts(1)"
              @clear="fetchFacts(1)"
            >
              <template #append>
                <el-button @click="fetchFacts(1)">
                  <el-icon><Search /></el-icon>
                </el-button>
              </template>
            </el-input>
            <el-button :loading="factLoading" @click="fetchFacts(currentFactPage)">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
            <el-button
              type="danger"
              plain
              :disabled="selectedFactIds.length === 0"
              @click="handleBatchDeleteFacts"
            >
              <el-icon><Delete /></el-icon>
              删除选中 ({{ selectedFactIds.length }})
            </el-button>
          </div>
        </div>
        <p class="fact-hint">
          这里展示智能助手通过联网工具提取并保存的事实（含数据采集时间与有效期），跨会话自动引用；引用时会标注数据采集日期。
          无需手动录入，助手在对话中获取到关键数据后会自动生成。
        </p>
      </template>

      <div v-loading="factLoading">
        <el-empty v-if="!factList.length" :image-size="100">
          <template #description>
            <p>暂无事实记忆。在助手对话中提问具体数据（如"赛力斯7月销量多少"）后，提取出的事实会自动保存在这里。</p>
          </template>
        </el-empty>

        <div v-else class="fact-list">
          <div v-for="item in factList" :key="item.id" class="fact-item">
            <div class="fact-item-header">
              <el-checkbox
                :model-value="selectedFactIds.includes(item.id)"
                @change="toggleFactSelected(item.id, $event)"
              />
              <el-tag size="small" effect="plain">{{ item.topic }}</el-tag>
              <el-tag
                :type="getFactCategoryType(item.category)"
                size="small"
                effect="plain"
              >
                {{ FACT_CATEGORY_LABELS[item.category || 'default'] }}
              </el-tag>
              <span v-if="item.symbol" class="fact-symbol">{{ item.symbol }}</span>
              <span class="fact-item-time">采集于 {{ formatTime(item.fetched_at) }}</span>
              <el-popconfirm
                title="确定删除这条事实记忆？"
                @confirm="handleDeleteFact(item.id)"
              >
                <template #reference>
                  <el-button type="danger" text size="small">
                    <el-icon><Delete /></el-icon>
                  </el-button>
                </template>
              </el-popconfirm>
            </div>
            <p class="fact-item-content">{{ item.content }}</p>
            <div class="fact-item-meta">
              <span>有效期至 {{ formatTime(item.valid_until) }}</span>
              <span v-if="item.tool_id">来源工具：{{ item.tool_id }}</span>
            </div>
          </div>
        </div>

        <div class="fact-pagination" v-if="factTotal > FACT_PAGE_SIZE">
          <el-pagination
            v-model:current-page="currentFactPage"
            :page-size="FACT_PAGE_SIZE"
            :total="factTotal"
            layout="total, prev, pager, next"
            @current-change="fetchFacts"
          />
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Coin, Delete, Refresh, Search, Memo } from '@element-plus/icons-vue'
import { memoryApi, SCOPE_COLORS, SCOPE_LABELS, FACT_CATEGORY_LABELS } from '@/api/memory'
import type { MemoryItem, MemoryQueryParams, AssistantFactItem } from '@/api/memory'

interface MemoryCardItem {
  id: string
  symbol: string
  market: string
  marketLabel: string
  objectKey: string
  summary: string
  recommendation: string
  analysisDate: string
  evidence: string[]
  nextChecks: string[]
  source: string
  taskId: string
  scope: string
  scopeLabel: string
  timestamp: string
  score: number
}

const OBJECT_MEMORY_SCOPE = 'analysis_insight'
const OBJECT_MEMORY_TYPE = 'stock'
const OBJECT_MEMORY_KIND = 'stock_analysis'
const DELETE_BATCH_SIZE = 50
const BULK_FETCH_SIZE = 100

const loading = ref(false)
const searching = ref(false)
const searchQuery = ref('')
const symbolFilter = ref('')
const marketFilter = ref('')
const currentPage = ref(1)
const pageSize = ref(12)
const memories = ref<MemoryItem[]>([])
const totalMemories = ref(0)
const objectMemoryTotal = ref(0)
const selectedIds = ref<string[]>([])
const isSearchMode = ref(false)

const stats = reactive<{
  enabled: boolean
  available?: boolean
  message?: string
}>({
  enabled: true,
  available: true,
})

const marketOptions = [
  { label: 'A股', value: 'cn' },
]

const normalizedSymbol = computed(() => symbolFilter.value.trim().toUpperCase())
const hasActiveFilters = computed(() => Boolean(normalizedSymbol.value || marketFilter.value.trim()))

const memoryCards = computed<MemoryCardItem[]>(() =>
  memories.value.map((item) => normalizeMemoryCard(item))
)

function buildObjectBaseParams(): MemoryQueryParams {
  return {
    scope: OBJECT_MEMORY_SCOPE,
    object_type: OBJECT_MEMORY_TYPE,
    memory_kind: OBJECT_MEMORY_KIND,
  }
}

function buildFilteredParams(overrides: MemoryQueryParams = {}): MemoryQueryParams {
  const params: MemoryQueryParams = {
    ...buildObjectBaseParams(),
  }
  if (normalizedSymbol.value) {
    params.symbol = normalizedSymbol.value
  }
  if (marketFilter.value) {
    params.market = marketFilter.value
  }
  return {
    ...params,
    ...overrides,
  }
}

function getScopeLabel(scope: string) {
  return SCOPE_LABELS[scope] || scope
}

type ElTagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

function getScopeColor(scope: string): ElTagType {
  return (SCOPE_COLORS[scope] || 'info') as ElTagType
}

function getMarketLabel(market: string) {
  const normalized = String(market || '').trim().toLowerCase()
  if (normalized === 'cn') return 'A股'
  return normalized || '-'
}

function getScoreTagType(score: number) {
  if (score >= 0.8) return 'success'
  if (score >= 0.5) return 'warning'
  return 'info'
}

function formatScore(score: number) {
  return `${Math.round((score || 0) * 100)}%`
}

function formatTime(t?: string | null) {
  if (!t) return '-'
  try {
    const d = new Date(t)
    if (Number.isNaN(d.getTime())) return t
    return d.toLocaleString('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return t
  }
}

function toTextArray(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .map(item => String(item || '').trim())
      .filter(Boolean)
  }
  const text = String(value || '').trim()
  return text ? [text] : []
}

function normalizeMemoryCard(item: MemoryItem): MemoryCardItem {
  const meta = item.metadata || {}
  const symbol = String(item.symbol || meta.symbol || '').trim().toUpperCase() || '未知标的'
  const market = String(item.market || meta.market || '').trim().toLowerCase() || 'cn'
  const objectKey = String(item.object_key || meta.object_key || `${market}:${symbol}`).trim()
  return {
    id: item.id,
    symbol,
    market,
    marketLabel: getMarketLabel(market),
    objectKey,
    summary: String(meta.summary || item.memory || '暂无结构化结论').trim(),
    recommendation: String(meta.recommendation || '').trim(),
    analysisDate: String(meta.analysis_date || '').trim(),
    evidence: toTextArray(meta.evidence),
    nextChecks: toTextArray(meta.next_checks),
    source: String(item.agent_id || meta.source_agent || '-').trim() || '-',
    taskId: String(meta.task_id || '').trim(),
    scope: String(item.scope || OBJECT_MEMORY_SCOPE),
    scopeLabel: getScopeLabel(String(item.scope || OBJECT_MEMORY_SCOPE)),
    timestamp: String(item.updated_at || item.created_at || '').trim(),
    score: Number(item.score || 0),
  }
}

function isSelected(id: string) {
  return selectedIds.value.includes(id)
}

function toggleSelected(id: string, checked: unknown) {
  const shouldSelect = Boolean(checked)
  if (shouldSelect) {
    if (!selectedIds.value.includes(id)) {
      selectedIds.value = [...selectedIds.value, id]
    }
    return
  }
  selectedIds.value = selectedIds.value.filter(itemId => itemId !== id)
}

async function fetchStats() {
  try {
    const data = await memoryApi.getStats()
    stats.enabled = data.enabled
    stats.available = data.available
    stats.message = data.message
  } catch {
    // ignore
  }
}

async function fetchObjectTotal() {
  try {
    const data = await memoryApi.getList({
      ...buildObjectBaseParams(),
      page: 1,
      page_size: 1,
    })
    objectMemoryTotal.value = data.total
  } catch {
    objectMemoryTotal.value = 0
  }
}

async function fetchList() {
  loading.value = true
  isSearchMode.value = false
  selectedIds.value = []
  try {
    const data = await memoryApi.getList({
      ...buildFilteredParams(),
      page: currentPage.value,
      page_size: pageSize.value,
    })
    memories.value = data.items
    totalMemories.value = data.total
  } catch (e: any) {
    ElMessage.error(e?.message || '加载对象记忆失败')
  } finally {
    loading.value = false
  }
}

async function handleSearch() {
  const q = searchQuery.value.trim()
  if (!q) {
    isSearchMode.value = false
    currentPage.value = 1
    await fetchList()
    return
  }
  searching.value = true
  isSearchMode.value = true
  selectedIds.value = []
  try {
    const data = await memoryApi.recall(q, buildFilteredParams(), 20)
    memories.value = data.items
    totalMemories.value = data.count
  } catch (e: any) {
    ElMessage.error(e?.message || '搜索失败')
  } finally {
    searching.value = false
  }
}

function handleClearSearch() {
  searchQuery.value = ''
  isSearchMode.value = false
  currentPage.value = 1
  fetchList()
}

function handleFilterChange() {
  currentPage.value = 1
  selectedIds.value = []
  if (searchQuery.value.trim()) {
    handleSearch()
  } else {
    fetchList()
  }
}

function handleResetFilters() {
  searchQuery.value = ''
  symbolFilter.value = ''
  marketFilter.value = ''
  currentPage.value = 1
  selectedIds.value = []
  fetchAll()
}

async function handleDeleteOne(id: string) {
  const ok = await memoryApi.deleteMemory(id)
  if (ok) {
    ElMessage.success('对象记忆已删除')
    await fetchAll()
  } else {
    ElMessage.error('删除失败')
  }
}

async function handleBatchDelete() {
  if (selectedIds.value.length === 0) return
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${selectedIds.value.length} 条对象记忆？`,
      '批量删除',
      { type: 'warning' },
    )
  } catch {
    return
  }

  let deleted = 0
  for (let index = 0; index < selectedIds.value.length; index += DELETE_BATCH_SIZE) {
    const batch = selectedIds.value.slice(index, index + DELETE_BATCH_SIZE)
    const result = await memoryApi.batchDelete(batch)
    deleted += result.deleted
  }

  ElMessage.success(`已删除 ${deleted} 条对象记忆`)
  selectedIds.value = []
  await fetchAll()
}

async function collectObjectMemoryIds() {
  const ids: string[] = []
  let page = 1
  let hasMore = true

  while (hasMore) {
    const data = await memoryApi.getList({
      ...buildObjectBaseParams(),
      page,
      page_size: BULK_FETCH_SIZE,
    })
    ids.push(...data.items.map(item => item.id))

    hasMore = Boolean(data.items.length && ids.length < data.total)
    page += 1
  }

  return ids
}

async function handleDeleteAllObjects() {
  loading.value = true
  try {
    const ids = await collectObjectMemoryIds()
    if (ids.length === 0) {
      ElMessage.info('暂无对象记忆可清理')
      return
    }

    let deleted = 0
    for (let index = 0; index < ids.length; index += DELETE_BATCH_SIZE) {
      const batch = ids.slice(index, index + DELETE_BATCH_SIZE)
      const result = await memoryApi.batchDelete(batch)
      deleted += result.deleted
    }

    ElMessage.success(`已清除 ${deleted} 条对象记忆`)
    selectedIds.value = []
    await fetchAll()
  } catch (e: any) {
    ElMessage.error(e?.message || '清除失败')
  } finally {
    loading.value = false
  }
}

async function fetchAll() {
  await Promise.all([fetchStats(), fetchObjectTotal()])
  if (searchQuery.value.trim()) {
    await handleSearch()
  } else {
    await fetchList()
  }
}

// ============================================================================
// 偏好与纪律记忆（user_preference + trade_pattern）
// 参考：docs/05-design/v3.0/unified-memory-layer-mem0.md §15.5 P0-3
// ============================================================================

const preferenceList = ref<MemoryItem[]>([])
const preferenceLoading = ref(false)

async function fetchPreferenceList() {
  preferenceLoading.value = true
  try {
    // 并行获取 user_preference + trade_pattern
    const [prefRes, patternRes] = await Promise.all([
      memoryApi.getList({ scope: 'user_preference', page: 1, page_size: 50 }),
      memoryApi.getList({ scope: 'trade_pattern', page: 1, page_size: 50 }),
    ])
    const items: MemoryItem[] = []
    if (prefRes?.items) {
      items.push(...prefRes.items)
    }
    if (patternRes?.items) {
      items.push(...patternRes.items)
    }
    // 按时间倒序
    items.sort((a, b) => {
      const ta = String(a.created_at || a.updated_at || '')
      const tb = String(b.created_at || b.updated_at || '')
      return tb.localeCompare(ta)
    })
    preferenceList.value = items
  } catch (e: any) {
    ElMessage.error(`加载偏好记忆失败：${e?.message || e}`)
  } finally {
    preferenceLoading.value = false
  }
}

async function handleDeletePreference(id: string) {
  try {
    const ok = await memoryApi.deleteMemory(id)
    if (ok) {
      ElMessage.success('已删除')
      await fetchPreferenceList()
    } else {
      ElMessage.error('删除失败')
    }
  } catch (e: any) {
    ElMessage.error(`删除失败：${e?.message || e}`)
  }
}

function normalizeMetadataTags(metadata: Record<string, any>): Record<string, string> {
  // 只展示用户关心的字段，过滤内部字段
  const KEEP_KEYS = ['category', 'source', 'symbol', 'name', 'review_id', 'system_id']
  const result: Record<string, string> = {}
  for (const key of KEEP_KEYS) {
    if (metadata[key]) {
      result[key] = String(metadata[key])
    }
  }
  return result
}

// ============================================================================
// 智能助手事实记忆（assistant_memory_facts）
// 参考：app/services/intelligent_assistant_service.py 事实记忆层
// ============================================================================

const FACT_PAGE_SIZE = 10
const factList = ref<AssistantFactItem[]>([])
const factTotal = ref(0)
const factLoading = ref(false)
const factSearch = ref('')
const currentFactPage = ref(1)
const selectedFactIds = ref<string[]>([])

function getFactCategoryType(category?: string): ElTagType {
  const map: Record<string, ElTagType> = {
    realtime_quote: 'danger',
    industry_metric: 'warning',
    company_financial: 'success',
    company_static: 'primary',
    default: 'info',
  }
  return map[category || 'default'] || 'info'
}

async function fetchFacts(page = 1) {
  factLoading.value = true
  try {
    const q = factSearch.value.trim()
    const data = await memoryApi.getAssistantFacts({
      q: q || undefined,
      page,
      page_size: FACT_PAGE_SIZE,
    })
    factList.value = data.items
    factTotal.value = data.total
    currentFactPage.value = data.page
    selectedFactIds.value = []
  } catch (e: any) {
    ElMessage.error(e?.message || '加载事实记忆失败')
  } finally {
    factLoading.value = false
  }
}

function toggleFactSelected(id: string, checked: unknown) {
  const shouldSelect = Boolean(checked)
  if (shouldSelect) {
    if (!selectedFactIds.value.includes(id)) {
      selectedFactIds.value.push(id)
    }
    return
  }
  selectedFactIds.value = selectedFactIds.value.filter(fid => fid !== id)
}

async function handleDeleteFact(id: string) {
  const ok = await memoryApi.deleteAssistantFact(id)
  if (ok) {
    ElMessage.success('事实记忆已删除')
    await fetchFacts(currentFactPage.value)
  } else {
    ElMessage.error('删除失败')
  }
}

async function handleBatchDeleteFacts() {
  if (selectedFactIds.value.length === 0) return
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${selectedFactIds.value.length} 条事实记忆？`,
      '批量删除',
      { type: 'warning' },
    )
  } catch {
    return
  }
  const result = await memoryApi.batchDeleteAssistantFacts(selectedFactIds.value)
  ElMessage.success(`已删除 ${result.deleted} 条事实记忆`)
  await fetchFacts(currentFactPage.value)
}

onMounted(() => {
  fetchAll()
  fetchPreferenceList()
  fetchFacts()
})
</script>

<style lang="scss" scoped>
.memory-page {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;

  .header-left {
    h1 {
      margin: 0 0 4px;
      font-size: 24px;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .header-icon {
      color: var(--el-color-primary);
    }

    .subtitle {
      display: block;
      max-width: 780px;
      color: var(--el-text-color-secondary);
      font-size: 13px;
      line-height: 1.6;
    }
  }

  .header-right {
    display: flex;
    gap: 8px;
    flex-shrink: 0;
  }
}

.status-alert,
.overview-card,
.filter-card {
  margin-bottom: 16px;
}

.overview-card {
  :deep(.el-card__body) {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 16px;
  }

  .overview-item {
    padding: 18px;
    border-radius: 14px;
    background: linear-gradient(140deg, #f8fafc, #eef4ff);
    border: 1px solid rgba(64, 158, 255, 0.12);
  }

  .overview-label {
    font-size: 12px;
    color: var(--el-text-color-secondary);
    margin-bottom: 8px;
  }

  .overview-value {
    font-size: 28px;
    font-weight: 700;
    color: var(--el-text-color-primary);
  }

  .overview-note {
    background: linear-gradient(135deg, #fff7ed, #fffaf0);
    border-color: rgba(230, 162, 60, 0.18);
  }

  .overview-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
}

.filter-card {
  .filter-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }

  .filter-hint {
    margin-top: 12px;
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    font-size: 13px;
    color: var(--el-text-color-secondary);
  }
}

.list-card {
  min-height: 240px;

  .memory-grid {
    min-height: 180px;
  }

  .memory-object-card {
    margin-bottom: 16px;
    border-radius: 16px;
    overflow: hidden;

    :deep(.el-card__header) {
      padding: 16px 18px;
      background: linear-gradient(135deg, rgba(64, 158, 255, 0.08), rgba(64, 158, 255, 0.02));
    }

    :deep(.el-card__body) {
      padding: 18px;
    }
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
  }

  .card-title-row {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    min-width: 0;
  }

  .identity-block {
    min-width: 0;
  }

  .identity-main {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
  }

  .symbol-text {
    font-size: 18px;
    font-weight: 700;
    color: var(--el-text-color-primary);
  }

  .identity-sub {
    font-size: 12px;
    color: var(--el-text-color-secondary);
    word-break: break-all;
  }

  .card-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }

  .card-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    margin-bottom: 16px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }

  .card-section {
    margin-bottom: 14px;
  }

  .section-label {
    margin-bottom: 6px;
    font-size: 12px;
    font-weight: 600;
    color: var(--el-text-color-secondary);
    letter-spacing: 0.02em;
  }

  .section-text {
    margin: 0;
    font-size: 14px;
    line-height: 1.7;
    color: var(--el-text-color-primary);
    word-break: break-word;
  }

  .accent-text {
    color: var(--el-color-warning-dark-2);
  }

  .tag-list {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .detail-tag {
    max-width: 100%;
    height: auto;
    padding: 6px 10px;
    align-items: flex-start;
    justify-content: flex-start;
    text-align: left;
    line-height: 1.6;
    white-space: normal;
  }

  .detail-tag :deep(.el-tag__content) {
    white-space: normal;
    word-break: break-word;
    overflow-wrap: anywhere;
  }

  .card-footer {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    padding-top: 10px;
    margin-top: 12px;
    border-top: 1px solid var(--el-border-color-lighter);
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }

  .pagination-wrapper {
    display: flex;
    justify-content: center;
    padding: 12px 0 4px;
  }
}

@media (max-width: 900px) {
  .page-header {
    flex-direction: column;
  }

  .overview-card {
    :deep(.el-card__body) {
      grid-template-columns: 1fr;
    }
  }

  .filter-card {
    .filter-actions {
      justify-content: flex-start;
      margin-top: 8px;
      flex-wrap: wrap;
    }
  }

  .list-card {
    .card-footer {
      flex-direction: column;
    }
  }
}

.preference-card {
  margin-top: 16px;

  .preference-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    flex-wrap: wrap;
  }

  .preference-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 600;
    font-size: 15px;
  }

  .preference-hint {
    margin: 8px 0 0;
    font-size: 12px;
    color: var(--el-text-color-secondary);
    line-height: 1.5;
  }

  .preference-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .preference-item {
    padding: 12px 14px;
    border: 1px solid var(--el-border-color-lighter);
    border-radius: 6px;
    background: var(--el-fill-color-blank);

    .preference-item-header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 6px;
    }

    .preference-item-time {
      flex: 1;
      font-size: 12px;
      color: var(--el-text-color-secondary);
    }

    .preference-item-content {
      margin: 0 0 8px;
      font-size: 14px;
      color: var(--el-text-color-primary);
      line-height: 1.6;
      white-space: pre-wrap;
      word-break: break-word;
    }

    .preference-item-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;

      .meta-tag {
        font-size: 11px;
      }
    }
  }
}

.fact-card {
  margin-top: 16px;

  .fact-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    flex-wrap: wrap;
  }

  .fact-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 600;
    font-size: 15px;
  }

  .fact-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .fact-hint {
    margin: 8px 0 0;
    font-size: 12px;
    color: var(--el-text-color-secondary);
    line-height: 1.5;
  }

  .fact-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .fact-item {
    padding: 12px 14px;
    border: 1px solid var(--el-border-color-lighter);
    border-radius: 6px;
    background: var(--el-fill-color-blank);

    .fact-item-header {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 6px;
    }

    .fact-symbol {
      font-weight: 600;
      color: var(--el-color-primary);
    }

    .fact-item-time {
      flex: 1;
      font-size: 12px;
      color: var(--el-text-color-secondary);
    }

    .fact-item-content {
      margin: 0 0 8px;
      font-size: 14px;
      color: var(--el-text-color-primary);
      line-height: 1.6;
      word-break: break-word;
    }

    .fact-item-meta {
      display: flex;
      gap: 16px;
      flex-wrap: wrap;
      font-size: 12px;
      color: var(--el-text-color-secondary);
    }
  }

  .fact-pagination {
    display: flex;
    justify-content: center;
    padding-top: 12px;
  }
}
</style>
