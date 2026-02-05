<template>
  <div class="market-news-container">
    <el-card>
      <el-tabs v-model="activeTab" type="card" @tab-change="handleTabChange">
        <!-- 智能聚合（默认） -->
        <el-tab-pane label="智能聚合" name="grouped-news">
          <!-- 切换按钮 -->
          <div class="view-switch-bar">
            <el-radio-group v-model="viewStrategy" size="small" @change="handleStrategyChange">
              <el-radio-button label="dynamic_hot">
                <el-icon><Star /></el-icon>
                热点优先
              </el-radio-button>
              <el-radio-button label="timeline">
                <el-icon><Clock /></el-icon>
                时间线
              </el-radio-button>
            </el-radio-group>
            <el-button type="primary" :icon="Refresh" @click="refreshGroupedNews" :loading="groupedLoading">
              刷新
            </el-button>
          </div>

          <!-- 分组新闻列表 -->
          <GroupedNewsList :grouped-data="groupedData" :loading="groupedLoading" />
        </el-tab-pane>

        <!-- 市场快讯 -->
        <el-tab-pane label="市场快讯" name="market-news">
          <!-- AI 总结按钮 -->
          <div class="ai-summary-btn">
            <el-button type="primary" :icon="ChatLineRound" @click="showAiSummary" :loading="aiLoading">
              AI 市场资讯总结
            </el-button>
          </div>

          <!-- 市场热词分析 -->
          <div class="market-analysis" v-if="showAnalysis">
            <el-card class="analysis-card">
              <template #header>
                <span>最近24小时市场热词</span>
              </template>
              <div class="wordcloud-container" ref="wordcloudRef" style="height: 300px;">
                <div class="wordcloud-wrapper" v-if="hotWords.length > 0">
                  <span
                    v-for="(word, index) in hotWords"
                    :key="index"
                    class="word-tag"
                    :style="getWordStyle(word)"
                  >
                    {{ word.word }}
                  </span>
                </div>
                <el-empty v-else description="暂无热词数据" :image-size="80" />
              </div>
            </el-card>
          </div>

          <!-- 新闻列表网格 - 平铺布局 -->
          <el-row :gutter="16" class="tiled-news-grid">
            <el-col :span="8" class="tiled-news-col">
              <NewsList
                :news-list="telegraphList"
                header-title="财联社电报"
                @refresh="refreshNews('财联社电报')"
              />
            </el-col>
            <el-col :span="8" class="tiled-news-col">
              <NewsList
                :news-list="sinaNewsList"
                header-title="新浪财经"
                @refresh="refreshNews('新浪财经')"
              />
            </el-col>
            <el-col :span="8" class="tiled-news-col">
              <NewsList
                :news-list="eastmoneyList"
                header-title="东方财富网"
                @refresh="refreshNews('东方财富网')"
              />
            </el-col>
          </el-row>
        </el-tab-pane>

        <!-- 全球股指 -->
        <el-tab-pane label="全球股指" name="global-indexes">
          <GlobalIndexGrid :data="globalStockIndexes" />
        </el-tab-pane>

        <!-- 行业排名 -->
        <el-tab-pane label="行业排名" name="industry-rank">
          <IndustryRankTable :data="industryRanks" @sort-change="handleIndustrySort" />
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- AI 总结对话框 -->
    <el-dialog
      v-model="aiSummaryVisible"
      title="AI 市场资讯总结"
      width="800px"
      :close-on-click-modal="false"
    >
      <el-scrollbar height="500px">
        <div class="ai-summary-content" v-loading="aiLoading">
          <div v-if="aiSummary" class="markdown-content" v-html="renderMarkdown(aiSummary)"></div>
          <el-empty v-else description="暂无AI总结" />
        </div>
      </el-scrollbar>
      <template #footer>
        <div class="dialog-footer">
          <el-text type="info" v-if="aiSummaryTime">
            <el-tag type="warning" v-if="modelName">{{ modelName }}</el-tag>
            {{ aiSummaryTime }}
          </el-text>
          <el-text type="danger">*AI分析结果仅供参考，请以实际行情为准。投资需谨慎，风险自担。</el-text>
        </div>
        <div class="dialog-actions">
          <el-input
            v-model="aiQuestion"
            type="textarea"
            :rows="3"
            placeholder="请输入您的问题，例如：总结和分析股票市场新闻中的投资机会"
          />
          <div class="action-buttons">
            <el-button type="primary" @click="generateAiSummary" :loading="aiLoading">生成总结</el-button>
            <el-button @click="copyAiSummary">复制</el-button>
            <el-button type="success" @click="saveAiSummary">保存</el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { ChatLineRound, Star, Clock, Refresh } from '@element-plus/icons-vue'
import NewsList from './components/NewsList.vue'
import GroupedNewsList from './components/GroupedNewsList.vue'
import GlobalIndexGrid from './components/GlobalIndexGrid.vue'
import IndustryRankTable from './components/IndustryRankTable.vue'
import { newsApi } from '@/api/news'

// 状态管理
const activeTab = ref('grouped-news')  // 默认显示智能聚合

// 新闻数据
const telegraphList = ref<any[]>([])
const sinaNewsList = ref<any[]>([])
const eastmoneyList = ref<any[]>([])
const globalStockIndexes = ref<any>(null)
const industryRanks = ref<any[]>([])

// AI 总结相关
const aiSummaryVisible = ref(false)
const aiLoading = ref(false)
const aiSummary = ref('')
const aiSummaryTime = ref('')
const modelName = ref('')
const aiQuestion = ref('总结和分析当前股票市场新闻中的投资机会和风险点')
const showAnalysis = ref(true)

// 智能聚合相关
const groupedData = ref<any>(null)
const groupedLoading = ref(false)
const viewStrategy = ref<'dynamic_hot' | 'timeline'>('dynamic_hot')

// 热词相关
const hotWords = ref<any[]>([])
const hotWordsLoading = ref(false)

// 加载热词数据
const loadHotWords = async () => {
  hotWordsLoading.value = true
  try {
    const res = await newsApi.getEnhancedWordcloud(24, 50)
    hotWords.value = res?.data?.words || []
  } catch (error) {
    console.error('加载热词失败:', error)
  } finally {
    hotWordsLoading.value = false
  }
}

// 计算词云样式
const getWordStyle = (word: any) => {
  const maxCount = Math.max(...hotWords.value.map(w => w.count))
  const minCount = Math.min(...hotWords.value.map(w => w.count))
  const range = maxCount - minCount || 1

  // 根据权重计算字体大小 (12px - 32px)
  const fontSize = 12 + ((word.count - minCount) / range) * 20

  // 随机位置偏移，实现自由分布效果
  const offsetX = Math.random() * 20 - 10
  const offsetY = Math.random() * 20 - 10

  // 随机旋转 (-5deg ~ 5deg)
  const rotation = Math.random() * 10 - 5

  // 颜色变体 - 从白色到浅色的变化
  const opacity = 0.7 + Math.random() * 0.3

  return {
    fontSize: `${fontSize}px`,
    transform: `translate(${offsetX}px, ${offsetY}px) rotate(${rotation}deg)`,
    opacity,
    margin: `${4 + Math.random() * 8}px`,
  }
}

// 加载智能聚合新闻
const loadGroupedNews = async (strategy: 'dynamic_hot' | 'timeline' = 'dynamic_hot') => {
  groupedLoading.value = true
  try {
    const res = await newsApi.getGroupedNews(null, strategy)
    groupedData.value = res?.data || null
  } catch (error) {
    console.error('加载智能聚合新闻失败:', error)
    ElMessage.error('加载智能聚合新闻失败')
  } finally {
    groupedLoading.value = false
  }
}

// 刷新智能聚合新闻
const refreshGroupedNews = async () => {
  await loadGroupedNews(viewStrategy.value)
  ElMessage.success('刷新成功')
}

// 切换排序策略
const handleStrategyChange = (strategy: 'dynamic_hot' | 'timeline') => {
  loadGroupedNews(strategy)
}

// 定时器
let newsRefreshTimer: ReturnType<typeof setInterval> | null = null
let indexRefreshTimer: ReturnType<typeof setInterval> | null = null

// 加载市场快讯
const loadMarketNews = async () => {
  try {
    const [telegraphRes, sinaRes, eastmoneyRes] = await Promise.all([
      newsApi.getTelegraphList('财联社电报'),
      newsApi.getTelegraphList('新浪财经'),
      newsApi.getTelegraphList('东方财富网').catch(() => ({ data: [] }))
    ])

    telegraphList.value = telegraphRes?.data || []
    sinaNewsList.value = sinaRes?.data || []
    eastmoneyList.value = eastmoneyRes?.data || []
  } catch (error) {
    console.error('加载市场快讯失败:', error)
  }
}

// 加载全球股指
const loadGlobalIndexes = async () => {
  try {
    const res = await newsApi.getGlobalStockIndexes()
    globalStockIndexes.value = res?.data || {}
  } catch (error) {
    console.error('加载全球股指失败:', error)
  }
}

// 加载行业排名
const loadIndustryRank = async (sort = '0') => {
  try {
    const res = await newsApi.getIndustryRank(sort, 150)
    industryRanks.value = res?.data || []
  } catch (error) {
    console.error('加载行业排名失败:', error)
  }
}

// 刷新指定来源的新闻
const refreshNews = async (source: string) => {
  try {
    const res = await newsApi.refreshTelegraphList(source)
    const data = res?.data || []
    if (source === '财联社电报') {
      telegraphList.value = data
    } else if (source === '新浪财经') {
      sinaNewsList.value = data
    } else if (source === '东方财富网') {
      eastmoneyList.value = data
    }
    ElMessage.success(`${source} 刷新成功`)
  } catch (error) {
    ElMessage.error(`${source} 刷新失败`)
  }
}

// 行业排序切换
const handleIndustrySort = (sort: string) => {
  loadIndustryRank(sort)
}

// 标签页切换
const handleTabChange = (tabName: string) => {
  console.log('切换到标签页:', tabName)
}

// AI 总结
const showAiSummary = () => {
  aiSummaryVisible.value = true
  if (!aiSummary.value) {
    generateAiSummary()
  }
}

const generateAiSummary = async () => {
  aiLoading.value = true
  try {
    const res = await newsApi.summaryMarketNews(aiQuestion.value)
    const result = res?.data || {}
    aiSummary.value = result.content || ''
    aiSummaryTime.value = result.time || new Date().toLocaleString()
    modelName.value = result.modelName || ''
  } catch (error) {
    ElMessage.error('AI总结生成失败')
  } finally {
    aiLoading.value = false
  }
}

const copyAiSummary = async () => {
  try {
    await navigator.clipboard.writeText(aiSummary.value)
    ElMessage.success('已复制到剪贴板')
  } catch (error) {
    ElMessage.error('复制失败')
  }
}

const saveAiSummary = () => {
  // 实现保存逻辑
  ElMessage.success('保存成功')
}

// 简单的 Markdown 渲染
const renderMarkdown = (content: string) => {
  return content
    .replace(/^### (.*$)/gm, '<h3>$1</h3>')
    .replace(/^## (.*$)/gm, '<h2>$1</h2>')
    .replace(/^# (.*$)/gm, '<h1>$1</h1>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/\n/g, '<br>')
}

// 初始化
onMounted(() => {
  loadMarketNews()
  loadGroupedNews()  // 加载智能聚合新闻
  loadHotWords()      // 加载热词数据
  loadGlobalIndexes()
  loadIndustryRank()

  // 设置定时刷新
  newsRefreshTimer = setInterval(() => {
    if (activeTab.value === 'market-news') {
      refreshNews('财联社电报')
      refreshNews('新浪财经')
      refreshNews('东方财富网')
    }
  }, 60000) // 每分钟刷新

  indexRefreshTimer = setInterval(() => {
    loadGlobalIndexes()
  }, 5000) // 每5秒刷新指数
})

onBeforeUnmount(() => {
  if (newsRefreshTimer) clearInterval(newsRefreshTimer)
  if (indexRefreshTimer) clearInterval(indexRefreshTimer)
})
</script>

<style scoped lang="scss">
.market-news-container {
  padding: 20px;

  .ai-summary-btn {
    margin-bottom: 20px;
    text-align: right;
  }

  .view-switch-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    padding: 12px 16px;
    background: var(--el-fill-color-light);
    border-radius: 8px;

    .el-radio-group {
      :deep(.el-radio-button__inner) {
        display: flex;
        align-items: center;
        gap: 4px;
      }
    }
  }

  .market-analysis {
    margin-bottom: 20px;

    .analysis-card {
      :deep(.el-card__header) {
        background: var(--el-fill-color-light);
        font-weight: bold;
      }
    }

    .wordcloud-container {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
      overflow: hidden;
      position: relative;

      .wordcloud-wrapper {
        display: flex;
        flex-wrap: wrap;
        justify-content: center;
        align-items: center;
        gap: 8px;
        max-width: 100%;
        max-height: 100%;
      }

      .word-tag {
        display: inline-block;
        color: #ffffff;
        font-weight: 500;
        white-space: nowrap;
        text-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
        cursor: pointer;
        transition: all 0.3s ease;
        user-select: none;
        padding: 4px 10px;
        border-radius: 4px;
        background: rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(4px);

        &:hover {
          transform: scale(1.15) !important;
          background: rgba(255, 255, 255, 0.25);
          text-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
          z-index: 10;
        }
      }

      :deep(.el-empty) {
        --el-empty-description-color: rgba(255, 255, 255, 0.7);
      }
    }
  }

  .news-grid {
    margin-top: 20px;
  }

  // 平铺新闻网格
  .tiled-news-grid {
    margin-top: 16px;

    :deep(.el-col) {
      display: flex;
      flex-direction: column;
    }

    :deep(.el-col > *) {
      flex: 1;
      display: flex;
      flex-direction: column;
    }
  }

  .tiled-news-col {
    :deep(.el-card) {
      height: 100%;
      display: flex;
      flex-direction: column;
    }

    :deep(.el-card__body) {
      flex: 1;
      overflow-y: auto;
      max-height: 600px;
    }
  }

  .ai-summary-content {
    .markdown-content {
      h1, h2, h3 {
        margin-top: 16px;
        margin-bottom: 8px;
        color: var(--el-text-color-primary);
      }

      h1 { font-size: 24px; }
      h2 { font-size: 20px; }
      h3 { font-size: 16px; }

      strong {
        color: var(--el-color-primary);
      }
    }
  }

  .dialog-footer {
    display: flex;
    justify-content: space-between;
    margin-bottom: 10px;
  }

  .dialog-actions {
    .action-buttons {
      margin-top: 10px;
      display: flex;
      justify-content: flex-end;
      gap: 10px;
    }
  }
}

:deep(.el-tabs__content) {
  padding-top: 20px;
}

:deep(.el-card__body) {
  padding: 20px;
}
</style>
