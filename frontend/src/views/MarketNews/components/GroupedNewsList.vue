<template>
  <div class="grouped-news-container">
    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="5" animated />
    </div>

    <!-- 空状态 -->
    <el-empty v-else-if="isEmpty" description="暂无新闻数据" />

    <!-- 分组新闻内容 -->
    <div v-else class="grouped-content">
      <!-- 1. 市场大盘与指标 -->
      <section v-if="groupedData.market_overview?.length > 0" class="news-section market-overview">
        <div class="section-header">
          <el-icon class="section-icon" :color="'#409eff'"><TrendCharts /></el-icon>
          <h3 class="section-title">市场大盘与指标</h3>
          <el-tag size="small" type="primary">{{ groupedData.market_overview.length }}</el-tag>
        </div>
        <div class="section-content">
          <NewsCard
            v-for="news in groupedData.market_overview"
            :key="news.id || news.title"
            :news="news"
            :show-tag="false"
          />
        </div>
      </section>

      <!-- 2. 热点概念/题材集群 -->
      <section v-if="groupedData.hot_concepts?.length > 0" class="news-section hot-concepts">
        <div class="section-header">
          <el-icon class="section-icon" :color="'#f56c6c'"><Star /></el-icon>
          <h3 class="section-title">热点概念/题材集群</h3>
          <el-tag size="small" type="danger">{{ groupedData.hot_concepts.length }}</el-tag>
        </div>
        <div class="section-content">
          <ConceptCard
            v-for="concept in groupedData.hot_concepts"
            :key="concept.concept_name"
            :concept="concept"
          />
        </div>
      </section>

      <!-- 3. 涨停与资金动向 -->
      <section v-if="groupedData.limit_up?.length > 0" class="news-section limit-up">
        <div class="section-header">
          <el-icon class="section-icon" :color="'#e6a23c'"><Trophy /></el-icon>
          <h3 class="section-title">涨停与资金动向</h3>
          <el-tag size="small" type="warning">{{ groupedData.limit_up.length }}</el-tag>
        </div>
        <div class="section-content">
          <NewsCard
            v-for="news in groupedData.limit_up"
            :key="news.id || news.title"
            :news="news"
            :show-tag="true"
            tag-type="warning"
            tag-text="涨停"
          />
        </div>
      </section>

      <!-- 4. 个股重要公告与异动 -->
      <section v-if="groupedData.stock_alerts?.length > 0" class="news-section stock-alerts">
        <div class="section-header">
          <el-icon class="section-icon" :color="'#67c23a'"><Warning /></el-icon>
          <h3 class="section-title">个股重要公告与异动</h3>
          <el-tag size="small" type="success">{{ groupedData.stock_alerts.length }}</el-tag>
        </div>
        <div class="section-content">
          <NewsCard
            v-for="news in groupedData.stock_alerts"
            :key="news.id || news.title"
            :news="news"
            :show-tag="true"
            tag-type="success"
            tag-text="个股"
          />
        </div>
      </section>

      <!-- 5. 资金动向汇总 -->
      <section v-if="groupedData.fund_movements?.length > 0" class="news-section fund-movements">
        <div class="section-header">
          <el-icon class="section-icon" :color="'#909399'"><Coin /></el-icon>
          <h3 class="section-title">资金动向汇总</h3>
          <el-tag size="small" type="info">{{ groupedData.fund_movements.length }}</el-tag>
        </div>
        <div class="section-content">
          <NewsCard
            v-for="news in groupedData.fund_movements"
            :key="news.id || news.title"
            :news="news"
            :show-tag="true"
            tag-type="info"
            tag-text="资金"
          />
        </div>
      </section>

      <!-- 统计摘要 -->
      <div v-if="groupedData.summary" class="summary-bar">
        <span class="summary-item">
          <el-tag size="small" type="info">总计</el-tag>
          <span class="summary-value">{{ groupedData.summary.total_news }} 条</span>
        </span>
        <span class="summary-divider"></span>
        <span class="summary-item">
          <span class="summary-label">热点概念:</span>
          <span class="summary-value">{{ groupedData.summary.hot_concept_count }}</span>
        </span>
        <span class="summary-item">
          <span class="summary-label">个股异动:</span>
          <span class="summary-value">{{ groupedData.summary.stock_alert_count }}</span>
        </span>
        <span class="summary-item">
          <span class="summary-label">涨停相关:</span>
          <span class="summary-value">{{ groupedData.summary.limit_up_count }}</span>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { TrendCharts, Star, Trophy, Warning, Coin } from '@element-plus/icons-vue'
import NewsCard from './NewsCard.vue'
import ConceptCard from './ConceptCard.vue'

interface NewsItem {
  id: string | number
  title: string
  content: string
  time: string
  dataTime: string
  url?: string
  source: string
  isRed?: boolean
  subjects?: string[]
  _entities?: any
  _type?: string
  _hotness_score?: number
}

interface ConceptGroup {
  concept_name: string
  news: NewsItem[]
  stats: {
    count: number
    total_score: number
    avg_score: number
  }
}

interface GroupedData {
  market_overview: NewsItem[]
  hot_concepts: ConceptGroup[]
  stock_alerts: NewsItem[]
  fund_movements: NewsItem[]
  limit_up: NewsItem[]
  summary: {
    total_news: number
    market_overview_count: number
    hot_concept_count: number
    stock_alert_count: number
    fund_movement_count: number
    limit_up_count: number
  }
}

const props = defineProps<{
  groupedData?: GroupedData
  loading?: boolean
}>()

const isEmpty = computed(() => {
  if (!props.groupedData) return true
  const g = props.groupedData
  return (
    g.market_overview?.length === 0 &&
    g.hot_concepts?.length === 0 &&
    g.stock_alerts?.length === 0 &&
    g.fund_movements?.length === 0 &&
    g.limit_up?.length === 0
  )
})
</script>

<style scoped lang="scss">
.grouped-news-container {
  .loading-container {
    padding: 20px;
  }

  .grouped-content {
    .news-section {
      margin-bottom: 30px;

      .section-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 2px solid var(--el-border-color-lighter);

        .section-icon {
          font-size: 20px;
        }

        .section-title {
          margin: 0;
          font-size: 18px;
          font-weight: 600;
          color: var(--el-text-color-primary);
          flex: 1;
        }
      }

      .section-content {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
    }

    .summary-bar {
      position: sticky;
      bottom: 0;
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 12px 16px;
      margin-top: 24px;
      background: var(--el-fill-color-light);
      border-radius: 8px;
      backdrop-filter: blur(10px);
      z-index: 10;

      .summary-item {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 14px;

        .summary-label {
          color: var(--el-text-color-secondary);
        }

        .summary-value {
          font-weight: 600;
          color: var(--el-text-color-primary);
        }
      }

      .summary-divider {
        width: 1px;
        height: 16px;
        background: var(--el-border-color);
      }
    }
  }
}

@media (max-width: 768px) {
  .grouped-news-container {
    .grouped-content {
      .news-section {
        margin-bottom: 20px;

        .section-header {
          .section-title {
            font-size: 16px;
          }
        }
      }

      .summary-bar {
        flex-wrap: wrap;
        gap: 8px;

        .summary-divider {
          display: none;
        }
      }
    }
  }
}
</style>
