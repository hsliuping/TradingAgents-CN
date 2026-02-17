<template>
  <div class="concept-card">
    <!-- 概念标题栏 -->
    <div class="concept-header">
      <div class="concept-info">
        <h4 class="concept-name">{{ concept.concept_name }}</h4>
        <div class="concept-stats">
          <el-tag size="small" type="danger">{{ concept.stats.count }}条</el-tag>
          <el-tag size="small" type="warning">热度{{ Math.round(concept.stats.avg_score) }}</el-tag>
        </div>
      </div>
      <el-button
        text
        :icon="isExpanded ? ArrowUp : ArrowDown"
        @click="isExpanded = !isExpanded"
      >
        {{ isExpanded ? '收起' : '展开' }}
      </el-button>
    </div>

    <!-- 新闻列表 -->
    <transition name="el-fade-in-linear">
      <div v-show="isExpanded" class="concept-news">
        <NewsCard
          v-for="news in displayNews"
          :key="news.id || news.title"
          :news="news"
          :show-tag="false"
        />

        <!-- 展开/收起提示 -->
        <div
          v-if="concept.news.length > DISPLAY_LIMIT"
          class="expand-hint"
        >
          <el-button
            text
            type="primary"
            @click="isExpanded = !isExpanded"
          >
            还有 {{ concept.news.length - DISPLAY_LIMIT }} 条新闻，点击收起
          </el-button>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ArrowDown, ArrowUp } from '@element-plus/icons-vue'
import NewsCard from './NewsCard.vue'

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

const props = defineProps<{
  concept: ConceptGroup
}>()

const DISPLAY_LIMIT = 5
const isExpanded = ref(true)

const displayNews = computed(() => {
  if (props.concept.news.length <= DISPLAY_LIMIT) {
    return props.concept.news
  }
  return isExpanded.value ? props.concept.news : props.concept.news.slice(0, DISPLAY_LIMIT)
})
</script>

<style scoped lang="scss">
.concept-card {
  background: var(--el-fill-color-blank);
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  overflow: hidden;
  transition: all 0.3s ease;

  &:hover {
    border-color: var(--el-color-primary-light-5);
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  }

  .concept-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    background: linear-gradient(90deg, rgba(245, 108, 108, 0.05) 0%, transparent 100%);
    border-bottom: 1px solid var(--el-border-color-lighter);

    .concept-info {
      display: flex;
      align-items: center;
      gap: 12px;
      flex: 1;

      .concept-name {
        margin: 0;
        font-size: 16px;
        font-weight: 600;
        color: var(--el-text-color-primary);
      }

      .concept-stats {
        display: flex;
        gap: 6px;
      }
    }
  }

  .concept-news {
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    background: var(--el-fill-color-extra-light);

    .expand-hint {
      padding: 8px;
      text-align: center;
      background: var(--el-fill-color-blank);
      border-radius: 6px;
      margin-top: 4px;
    }
  }
}

@media (max-width: 768px) {
  .concept-card {
    .concept-header {
      flex-direction: column;
      align-items: flex-start;
      gap: 8px;

      .concept-info {
        width: 100%;

        .concept-name {
          font-size: 14px;
        }
      }
    }
  }
}
</style>
