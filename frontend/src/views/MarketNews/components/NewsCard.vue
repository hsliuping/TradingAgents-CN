<template>
  <div class="news-card" :class="{ 'is-red': news.isRed }">
    <!-- 标签 -->
    <div v-if="showTag" class="news-tag">
      <el-tag :type="tagType" size="small">{{ tagText }}</el-tag>
    </div>

    <!-- 时间 -->
    <div class="news-time">{{ news.time }}</div>

    <!-- 标题和内容 -->
    <div class="news-content">
      <a
        v-if="news.url"
        :href="news.url"
        target="_blank"
        class="news-title"
        :class="{ 'has-content': !!news.content && news.content !== news.title }"
        @click.prevent="handleOpen"
      >
        {{ news.title }}
      </a>
      <div
        v-else
        class="news-title"
        :class="{ 'has-content': !!news.content && news.content !== news.title }"
      >
        {{ news.title }}
      </div>

      <!-- 内容（如果有且不同于标题） -->
      <div
        v-if="news.content && news.content !== news.title"
        class="news-text"
        @click="handleContentClick"
      >
        {{ displayContent }}
        <span
          v-if="isContentTruncated"
          class="expand-btn"
          @click.stop="isExpanded = !isExpanded"
        >
          {{ isExpanded ? '收起' : '展开' }}
        </span>
      </div>

      <!-- 来源 -->
      <div class="news-source">{{ news.source }}</div>
    </div>

    <!-- 主题标签 -->
    <div v-if="news.subjects && news.subjects.length > 0" class="news-subjects">
      <el-tag
        v-for="(subject, idx) in news.subjects.slice(0, 3)"
        :key="idx"
        size="small"
        type="info"
        effect="plain"
      >
        {{ subject }}
      </el-tag>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

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

const props = defineProps<{
  news: NewsItem
  showTag?: boolean
  tagType?: 'primary' | 'success' | 'warning' | 'danger' | 'info'
  tagText?: string
}>()

const emit = defineEmits<{
  click: [news: NewsItem]
}>()

const MAX_CONTENT_LENGTH = 80
const isExpanded = ref(false)
const isContentTruncated = computed(() => {
  return props.news.content && props.news.content.length > MAX_CONTENT_LENGTH
})

const displayContent = computed(() => {
  if (!props.news.content) return ''
  if (isExpanded.value) return props.news.content
  return props.news.content.slice(0, MAX_CONTENT_LENGTH)
})

const handleOpen = () => {
  emit('click', props.news)
}

const handleContentClick = () => {
  // 如果内容被截断，点击可以展开
  if (isContentTruncated.value && !isExpanded.value) {
    isExpanded.value = true
  }
}
</script>

<style scoped lang="scss">
.news-card {
  position: relative;
  display: grid;
  grid-template-columns: 50px 1fr;
  gap: 8px 12px;
  padding: 12px;
  background: var(--el-fill-color-blank);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  transition: all 0.3s ease;

  &:hover {
    border-color: var(--el-color-primary-light-5);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  }

  &.is-red {
    background: linear-gradient(90deg, rgba(245, 108, 108, 0.05) 0%, transparent 100%);
    border-left: 3px solid var(--el-color-danger);
  }

  .news-tag {
    grid-column: 1 / -1;
    margin-bottom: 4px;
  }

  .news-time {
    grid-column: 1;
    grid-row: 2;
    font-size: 12px;
    color: var(--el-text-color-secondary);
    text-align: center;
    padding-top: 2px;
  }

  .news-content {
    grid-column: 2;
    display: flex;
    flex-direction: column;
    gap: 6px;

    .news-title {
      font-size: 14px;
      font-weight: 500;
      color: var(--el-text-color-primary);
      line-height: 1.5;
      cursor: pointer;
      transition: color 0.2s;

      &:hover {
        color: var(--el-color-primary);
      }

      &.has-content {
        font-weight: 600;
        margin-bottom: 2px;
      }

      &::-webkit-scrollbar {
        display: none;
      }
    }

    .news-text {
      font-size: 13px;
      color: var(--el-text-color-regular);
      line-height: 1.6;
      word-break: break-all;

      .expand-btn {
        color: var(--el-color-primary);
        cursor: pointer;
        margin-left: 4px;
        white-space: nowrap;

        &:hover {
          text-decoration: underline;
        }
      }
    }

    .news-source {
      font-size: 11px;
      color: var(--el-text-color-placeholder);
    }
  }

  .news-subjects {
    grid-column: 2;
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-top: 4px;
  }
}

@media (max-width: 768px) {
  .news-card {
    grid-template-columns: 45px 1fr;
    padding: 10px;

    .news-content {
      .news-title {
        font-size: 13px;
      }

      .news-text {
        font-size: 12px;
      }
    }
  }
}
</style>
