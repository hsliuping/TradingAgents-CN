<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2 class="title">资讯头条</h2>
      </div>
      <div class="actions">
        <el-input v-model="keyword" placeholder="搜索标题/来源" clearable style="width: 260px" />
        <el-select
          v-model="selectedModel"
          placeholder="选择AI模型"
          size="small"
          filterable
          style="width: 220px"
        >
          <el-option
            v-for="model in availableModels"
            :key="model.model_name"
            :label="model.model_display_name || model.model_name"
            :value="model.model_name"
          />
        </el-select>
        <el-button @click="refresh">刷新</el-button>
      </div>
    </div>

    <el-card shadow="hover">
      <el-tabs v-model="activeTab" class="tabs">
        <el-tab-pane label="全部" name="all" />
        <el-tab-pane label="宏观" name="macro" />
        <el-tab-pane label="行业" name="industry" />
        <el-tab-pane label="公司" name="company" />
      </el-tabs>

      <el-empty v-if="!loading && filtered.length === 0" description="暂无匹配内容" />
      <div v-else class="list-wrapper" v-loading="loading">
        <div
          class="list-scroll"
          v-infinite-scroll="loadMore"
          :infinite-scroll-disabled="loading || loadingMore || !hasMore"
          :infinite-scroll-distance="80"
        >
          <div class="list">
            <div v-for="item in filtered" :key="item.id" class="row" @click="open(item)">
              <div class="left">
                <div class="headline">
                  <span class="dot" :class="item.level" />
                  <span class="title-text">{{ item.title }}</span>
                </div>
                <div class="meta">
                  <el-tag size="small" type="info">{{ tabLabel(item.category) }}</el-tag>
                  <el-tag
                    v-if="item.importance"
                    size="small"
                    :type="importanceTagType(item.importance)"
                  >
                    重要度{{ importanceLabel(item.importance) }}
                  </el-tag>
                  <span class="source">{{ item.source }}</span>
                  <span class="time">{{ formatTime(item.time) }}</span>
                </div>
              </div>
              <div class="right">
                <span v-if="item.importanceRank" class="rank">#{{ item.importanceRank }}</span>
                <el-button
                  type="primary"
                  text
                  size="small"
                  :loading="analyzing && selectedHeadline && selectedHeadline.id === item.id"
                  @click.stop="analyze(item)"
                >
                  AI解读
                </el-button>
                <el-button
                  v-if="item.url"
                  text
                  size="small"
                  @click.stop="open(item)"
                >
                  原文
                </el-button>
                <el-button
                  v-if="analysisCache[item.id]"
                  text
                  size="small"
                  @click.stop="showHistory(item)"
                >
                  历史解读
                </el-button>
                <el-tag v-if="item.hot" type="danger" size="small">热</el-tag>
                <el-icon class="arrow"><ArrowRight /></el-icon>
              </div>
            </div>
          </div>
          <div class="list-footer">
            <span v-if="loadingMore">加载中...</span>
            <el-button v-else-if="hasMore" text size="small" @click="loadMore">加载更多</el-button>
            <span v-else>没有更多了</span>
          </div>
        </div>
      </div>
    </el-card>
  </div>

  <el-dialog v-model="analysisDialogVisible" title="AI 新闻解读" width="820px" class="analysis-dialog">
    <el-scrollbar class="analysis-scroll" style="height: 460px;">
      <div class="analysis-card">
        <div v-if="selectedHeadline" class="analysis-header">
          <div class="analysis-title-row">
            <el-tag v-if="analysisModelName" size="small" effect="plain">{{ analysisModelName }}</el-tag>
          </div>
          <div class="analysis-subtitle">
            {{ selectedHeadline.source }} · {{ formatTime(selectedHeadline.time) }}
          </div>
          <div v-if="selectedHeadline.url" class="analysis-link">
            <el-button type="primary" text size="small" @click="openCurrent">查看原文</el-button>
          </div>
        </div>
        <div class="analysis-content-wrapper">
          <div class="analysis-section">
            <div class="analysis-content markdown-body" v-html="analysisHtml"></div>
          </div>
        </div>
      </div>
    </el-scrollbar>
    <template #footer>
      <el-button @click="analysisDialogVisible = false">关闭</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="fullTextDialogVisible" title="新闻全文" width="820px" class="analysis-dialog">
    <el-scrollbar class="analysis-scroll" style="height: 460px;">
      <div class="analysis-card">
        <div v-if="fullTextItem" class="analysis-header">
          <div class="analysis-title-row">
            <div class="analysis-title">{{ fullTextItem.title }}</div>
            <el-tag v-if="fullTextItem.source" size="small" effect="plain">{{ fullTextItem.source }}</el-tag>
          </div>
          <div class="analysis-subtitle">
            {{ formatTime(fullTextItem.time) }}
          </div>
          <div v-if="fullTextItem.url" class="analysis-link">
            <el-button type="primary" text size="small" @click="openCurrent">查看原文</el-button>
          </div>
        </div>
        <div class="analysis-content-wrapper">
          <div class="analysis-section">
            <div class="analysis-section-title">全文内容</div>
            <div class="analysis-content markdown-body" v-html="fullTextHtml"></div>
          </div>
        </div>
      </div>
    </el-scrollbar>
    <template #footer>
      <el-button @click="fullTextDialogVisible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { ArrowRight } from '@element-plus/icons-vue'
import { newsApi } from '@/api/news'
import { configApi } from '@/api/config'
import { marked } from 'marked'

type Category = 'macro' | 'industry' | 'company'
type Level = 'info' | 'warning' | 'danger'

type Headline = {
  id: string
  title: string
  source: string
  time: string
  category: Category
  level: Level
  hot?: boolean
  url?: string
  content?: string
  importance?: 'high' | 'medium' | 'low'
  importanceRank?: number
}

const activeTab = ref<'all' | Category>('all')
const keyword = ref('')
const lastUpdated = ref(new Date())
const items = ref<Headline[]>([])
const loading = ref(false)
const loadingMore = ref(false)
const hasMore = ref(true)
const pageSize = 20
const currentSkip = ref(0)
const analysisDialogVisible = ref(false)
const analyzing = ref(false)
const selectedHeadline = ref<Headline | null>(null)
const analysisMarkdown = ref('')
const analysisModelName = ref('')
const analysisModelProvider = ref('')
const availableModels = ref<any[]>([])
const selectedModel = ref<string>('')
const analysisCache = ref<Record<string, { analysis: string; model_name?: string; model_provider?: string }>>({})
const fullTextDialogVisible = ref(false)
const fullTextItem = ref<Headline | null>(null)

marked.setOptions({ breaks: true, gfm: true })
const analysisHtml = computed(() => {
  try {
    return marked.parse(analysisMarkdown.value || '') as string
  } catch {
    return `<pre>${analysisMarkdown.value}</pre>`
  }
})
const fullTextHtml = computed(() => {
  const content = fullTextItem.value?.content || ''
  try {
    return marked.parse(content) as string
  } catch {
    return `<pre>${content}</pre>`
  }
})

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  const list = items.value
    .filter((x) => activeTab.value === 'all' || x.category === activeTab.value)
    .filter((x) => {
      if (!kw) return true
      return x.title.toLowerCase().includes(kw) || x.source.toLowerCase().includes(kw)
    })
  const ranked = list.map((item) => ({ ...item }))
  ranked.sort((a, b) => {
    const scoreDiff = importanceScore(b.importance) - importanceScore(a.importance)
    if (scoreDiff !== 0) return scoreDiff
    return a.time < b.time ? 1 : -1
  })
  ranked.forEach((item, index) => {
    item.importanceRank = index + 1
  })
  return ranked
})

function categorizeByTitle(title: string): Category {
  const t = title.toLowerCase()
  const companyKeywords = ['公司', '公告', '业绩', '财报', '增持', '减持', '收购', '重组', 'ipo', '上市', '停牌', '复牌']
  const industryKeywords = ['行业', '板块', '赛道', '景气', '产业链', '板块轮动', '细分领域']
  const companyMatch = companyKeywords.some((k) => t.includes(k.toLowerCase()))
  if (companyMatch) return 'company'
  const industryMatch = industryKeywords.some((k) => t.includes(k.toLowerCase()))
  if (industryMatch) return 'industry'
  const codePattern = /\b\d{6}\b/
  if (codePattern.test(title)) return 'company'
  return 'macro'
}

function tabLabel(c: Category) {
  if (c === 'macro') return '宏观'
  if (c === 'industry') return '行业'
  return '公司'
}

function importanceLabel(level?: 'high' | 'medium' | 'low') {
  if (level === 'high') return '高'
  if (level === 'low') return '低'
  return '中'
}

function importanceTagType(level?: 'high' | 'medium' | 'low') {
  if (level === 'high') return 'danger'
  if (level === 'low') return 'info'
  return 'warning'
}

function importanceScore(level?: 'high' | 'medium' | 'low') {
  if (level === 'high') return 3
  if (level === 'low') return 1
  return 2
}

function inferImportance(title: string, content: string) {
  const text = `${title} ${content}`.toLowerCase()
  const highKeywords = ['重磅', '突发', '暴涨', '暴跌', '大涨', '大跌', '重大', '央行', '降息', '加息', '利好', '利空']
  const mediumKeywords = ['增长', '下滑', '发布', '回购', '中标', '减持', '增持', '财报', '业绩', '公告']
  if (highKeywords.some((k) => text.includes(k))) return 'high'
  if (mediumKeywords.some((k) => text.includes(k))) return 'medium'
  return 'low'
}

function formatTime(iso: string) {
  return dayjs(iso).format('MM-DD HH:mm')
}

function open(item: Headline) {
  if (item.url) {
    window.open(item.url, '_blank')
    return
  }
  fullTextItem.value = item
  fullTextDialogVisible.value = true
}

function openCurrent() {
  if (selectedHeadline.value) {
    open(selectedHeadline.value)
    return
  }
  if (fullTextItem.value) {
    open(fullTextItem.value)
  }
}

function refresh() {
  loadNews(true)
}

async function loadNews(reset: boolean = false) {
  try {
    if (loading.value || loadingMore.value) return
    if (reset) {
      items.value = []
      currentSkip.value = 0
      hasMore.value = true
    }
    if (!hasMore.value) return
    if (currentSkip.value === 0) {
      loading.value = true
    } else {
      loadingMore.value = true
    }
    const res = await newsApi.getLatestNews(undefined, pageSize, 24, currentSkip.value)
    if (res.success && res.data) {
      const nextItems = res.data.news.map((item: any) => ({
        id: item.id || item.title,
        title: item.title,
        source: item.source || '市场快讯',
        time: item.publish_time,
        category: categorizeByTitle(item.title || ''),
        level: 'info',
        url: item.url,
        content: item.content || '',
        importance: item.importance || inferImportance(item.title || '', item.content || '')
      }))
      const existing = new Set(items.value.map((item) => item.id))
      const merged = nextItems.filter((item: Headline) => !existing.has(item.id))
      items.value = currentSkip.value === 0 ? nextItems : [...items.value, ...merged]
      currentSkip.value += nextItems.length
      if (nextItems.length < pageSize) {
        hasMore.value = false
      }
      lastUpdated.value = new Date()
    }
  } catch (e) {
    ElMessage.error('加载新闻失败')
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

function loadMore() {
  if (!hasMore.value) return
  loadNews()
}

async function analyze(item: Headline) {
  try {
    analyzing.value = true
    selectedHeadline.value = item
    const payload: any = {
      title: item.title,
      content: item.content || ''
    }
    if (selectedModel.value) {
      payload.model_name = selectedModel.value
    }
    const res = await newsApi.analyzeNews(payload)
    if (res.success && res.data) {
      const content = res.data.analysis || ''
      analysisMarkdown.value = content
      analysisModelName.value = res.data.model_name || selectedModel.value || ''
      analysisModelProvider.value = res.data.model_provider || ''
      analysisCache.value[item.id] = {
        analysis: content,
        model_name: analysisModelName.value,
        model_provider: analysisModelProvider.value
      }
      analysisDialogVisible.value = true
    } else {
      ElMessage.error(res.message || '分析失败')
    }
  } catch (e) {
    ElMessage.error('分析失败')
  } finally {
    analyzing.value = false
  }
}

function showHistory(item: Headline) {
  const cache = analysisCache.value[item.id]
  if (!cache) {
    ElMessage.info('暂无历史解读')
    return
  }
  selectedHeadline.value = item
  analysisMarkdown.value = cache.analysis
  analysisModelName.value = cache.model_name || ''
  analysisModelProvider.value = cache.model_provider || ''
  analysisDialogVisible.value = true
}

async function initializeModelSettings() {
  try {
    const defaultModels = await configApi.getDefaultModels()
    selectedModel.value = defaultModels.quick_analysis_model || defaultModels.deep_analysis_model
    const llmConfigs = await configApi.getLLMConfigs()
    availableModels.value = llmConfigs.filter((config: any) => config.enabled)
  } catch (e) {
    selectedModel.value = 'deepseek-chat'
  }
}

onMounted(async () => {
  await initializeModelSettings()
  await loadNews(true)
})
</script>

<style lang="scss" scoped>
.page {
  .page-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 16px;
  }
  .title {
    margin: 0;
    font-size: 22px;
    font-weight: 700;
    color: var(--el-text-color-primary);
  }
  .subtitle {
    margin-top: 6px;
    font-size: 13px;
    color: var(--el-text-color-regular);
  }
  .actions {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .tabs {
    margin-bottom: 8px;
  }

  .list {
    display: flex;
    flex-direction: column;
  }
  .list-wrapper {
    position: relative;
  }
  .list-scroll {
    max-height: 520px;
    overflow-y: auto;
  }
  .row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
    padding: 12px 6px;
    border-bottom: 1px solid var(--el-border-color-lighter);
    cursor: pointer;
    transition: background-color 0.2s ease;
  }
  .row:hover {
    background: var(--el-fill-color-light);
    border-radius: 8px;
  }
  .row:last-child {
    border-bottom: none;
  }
  .left {
    min-width: 0;
    flex: 1;
  }
  .headline {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    line-height: 1.4;
  }
  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-top: 6px;
    flex-shrink: 0;
  }
  .dot.info {
    background: var(--el-color-info);
  }
  .dot.warning {
    background: var(--el-color-warning);
  }
  .dot.danger {
    background: var(--el-color-danger);
  }
  .title-text {
    font-size: 14px;
    font-weight: 600;
    color: var(--el-text-color-primary);
    word-break: break-word;
  }
  .meta {
    margin-top: 6px;
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }
  .source {
    white-space: nowrap;
  }
  .time {
    white-space: nowrap;
  }
  .right {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
    color: var(--el-text-color-placeholder);
  }
  .rank {
    font-size: 12px;
    font-weight: 600;
    color: var(--el-color-primary);
    background: var(--el-color-primary-light-9);
    padding: 2px 6px;
    border-radius: 999px;
  }
  .arrow {
    font-size: 16px;
  }
  .list-footer {
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 12px 0;
    color: var(--el-text-color-secondary);
    font-size: 12px;
  }
  .analysis-card {
    border: 1px solid var(--el-border-color-lighter);
    border-radius: 12px;
    background: var(--el-fill-color-light);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
    overflow: hidden;
  }
  .analysis-header {
    padding: 20px 24px;
    background: var(--el-bg-color);
    border-bottom: 1px solid var(--el-border-color-lighter);
  }
  .analysis-title-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
  }
  .analysis-title {
    font-size: 18px;
    font-weight: 600;
    color: var(--el-text-color-primary);
  }
  .analysis-subtitle {
    margin-top: 6px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }
  .analysis-link {
    margin-top: 12px;
  }
  .analysis-content-wrapper {
    padding: 24px;
    background: var(--el-bg-color);
  }
  .analysis-section {
    margin-bottom: 24px;
  }
  .analysis-section-title {
    font-size: 16px;
    font-weight: 600;
    color: var(--el-text-color-primary);
    margin-bottom: 12px;
    border-bottom: 2px solid var(--el-color-primary);
    padding-bottom: 4px;
  }
  .analysis-content {
    font-size: 14px;
    line-height: 1.8;
    color: var(--el-text-color-primary);
  }
  .analysis-scroll {
    padding: 8px;
  }
  .markdown-body p {
    margin: 0 0 12px;
  }
  .markdown-body ul,
  .markdown-body ol {
    padding-left: 22px;
    margin: 0 0 12px;
  }
  .markdown-body h1,
  .markdown-body h2,
  .markdown-body h3 {
    margin: 16px 0 10px;
    font-weight: 600;
  }
  .markdown-body code {
    padding: 2px 4px;
    border-radius: 3px;
    background: var(--el-fill-color-light);
  }
}
</style>
