<template>
  <el-card class="news-list-card" shadow="hover">
    <template #header>
      <div class="card-header">
        <el-tag :type="tagType" size="large" :bordered="false">{{ headerTitle }}</el-tag>
        <!-- 财联社电报显示当前时间 -->
        <el-tag v-if="headerTitle === '财联社电报'" type="info" size="large" :bordered="false">
          {{ currentTime }}
        </el-tag>
        <el-button :icon="Refresh" circle size="small" @click="handleRefresh" :loading="refreshing" />
      </div>
    </template>

    <el-scrollbar height="550px">
      <div class="news-list">
        <div v-for="(item, idx) in newsList" :key="item.id || item.title" class="news-item">
          <!-- 日期分隔线 -->
          <el-divider v-if="showDateDivider(idx, item)" class="date-divider">
            {{ formatDate(item.dataTime) }}
          </el-divider>

          <!-- 有标题的新闻 -->
          <el-collapse v-if="item.title" v-model="activeNames" accordion>
            <el-collapse-item :name="item.id || item.title">
              <template #title>
                <div class="news-title">
                  <el-tag
                    :type="item.isRed ? 'danger' : 'warning'"
                    size="small"
                    :bordered="false"
                    class="time-tag"
                  >
                    {{ formatTime(item.time) }}
                  </el-tag>
                  <el-text :type="item.isRed ? 'danger' : 'primary'" truncated class="title-text">
                    {{ item.title }}
                  </el-text>
                </div>
              </template>

              <div class="news-content">
                <el-text :type="item.isRed ? 'danger' : 'info'" class="content-text">
                  {{ item.content }}
                </el-text>

                <!-- 主题标签 -->
                <div class="news-tags" v-if="item.subjects && item.subjects.length > 0">
                  <el-tag
                    v-for="subject in item.subjects"
                    :key="subject"
                    type="success"
                    size="small"
                    :bordered="false"
                  >
                    {{ subject }}
                  </el-tag>
                </div>

                <!-- 股票标签 -->
                <div class="news-tags" v-if="item.stocks && item.stocks.length > 0">
                  <el-tag
                    v-for="stock in item.stocks"
                    :key="stock"
                    type="warning"
                    size="small"
                    :bordered="false"
                  >
                    {{ stock }}
                  </el-tag>
                </div>

                <!-- 查看原文链接 -->
                <el-tag v-if="item.url" type="warning" size="small" :bordered="false" class="url-tag">
                  <a :href="item.url" target="_blank">
                    <el-text type="warning">查看原文</el-text>
                  </a>
                </el-tag>

                <!-- 情感分析结果 -->
                <el-tag
                  v-if="item.sentimentResult"
                  :type="getSentimentType(item.sentimentResult)"
                  size="small"
                  :bordered="false"
                >
                  {{ item.sentimentResult }}
                </el-tag>
              </div>
            </el-collapse-item>
          </el-collapse>

          <!-- 无标题的新闻 -->
          <div v-else class="news-without-title">
            <el-tag :type="item.isRed ? 'danger' : 'warning'" size="small" :bordered="false">
              {{ formatTime(item.time) }}
            </el-tag>
            <el-text :type="item.isRed ? 'danger' : 'info'">
              {{ item.content }}
            </el-text>
          </div>
        </div>

        <el-empty v-if="!newsList || newsList.length === 0" description="暂无新闻" :image-size="80" />
      </div>
    </el-scrollbar>
  </el-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

interface NewsItem {
  id?: string | number
  title?: string
  content: string
  time: string
  dataTime?: string
  url?: string
  isRed?: boolean
  subjects?: string[]
  stocks?: string[]
  sentimentResult?: string
}

interface Props {
  newsList: NewsItem[]
  headerTitle: string
}

interface Emits {
  (e: 'refresh', source: string): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const activeNames = ref<string[]>([])
const refreshing = ref(false)
const currentTime = ref('')

// 更新当前时间
const updateCurrentTime = () => {
  const now = new Date()
  currentTime.value = now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

let timer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  if (props.headerTitle === '财联社电报') {
    updateCurrentTime()
    timer = setInterval(updateCurrentTime, 1000)
  }
})

onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
  }
})

// 根据来源确定标签类型
const tagType = computed(() => {
  const typeMap: Record<string, any> = {
    '财联社电报': 'success',
    '新浪财经': 'warning',
    '外媒': 'info'
  }
  return typeMap[props.headerTitle] || 'primary'
})

// 获取情感分析类型
const getSentimentType = (sentiment: string) => {
  if (sentiment === '看涨') return 'danger'
  if (sentiment === '看跌') return 'success'
  return 'info'
}

// 格式化时间
const formatTime = (time: string) => {
  if (!time) return ''
  // 如果已经是HH:MM:SS格式
  if (/^\d{2}:\d{2}/.test(time)) {
    return time.substring(0, 5)
  }
  // 如果是完整时间字符串
  try {
    const date = new Date(time)
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return time
  }
}

// 格式化日期
const formatDate = (dataTime?: string) => {
  if (!dataTime) return ''
  try {
    const date = new Date(dataTime)
    return date.toLocaleDateString('zh-CN')
  } catch {
    return dataTime.split(' ')[0] || dataTime
  }
}

// 是否显示日期分隔线
const showDateDivider = (idx: number, item: NewsItem) => {
  if (idx === 0) return false
  const prevItem = props.newsList[idx - 1]
  if (!prevItem || !item.dataTime || !prevItem.dataTime) return false

  const currentDate = item.dataTime.split(' ')[0]
  const prevDate = prevItem.dataTime.split(' ')[0]
  return currentDate !== prevDate
}

// 刷新新闻
const handleRefresh = () => {
  refreshing.value = true
  emit('refresh', props.headerTitle)
  setTimeout(() => {
    refreshing.value = false
  }, 1000)
}
</script>

<style scoped lang="scss">
.news-list-card {
  height: 100%;

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
  }

  .news-list {
    .news-item {
      margin-bottom: 8px;
    }

    .date-divider {
      margin: 16px 0;
      :deep(.el-divider__text) {
        font-size: 12px;
        color: var(--el-text-color-secondary);
      }
    }

    .news-title {
      display: flex;
      align-items: center;
      gap: 8px;
      width: 100%;

      .time-tag {
        flex-shrink: 0;
        font-weight: bold;
      }

      .title-text {
        flex: 1;
      }
    }

    .news-content {
      padding: 8px 0;
      line-height: 1.6;

      .content-text {
        display: block;
        margin-bottom: 8px;
      }

      .news-tags {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
        margin-top: 8px;
      }

      .url-tag {
        margin-top: 8px;
        a {
          text-decoration: none;
        }
      }
    }

    .news-without-title {
      display: flex;
      align-items: flex-start;
      gap: 8px;
      padding: 8px 0;
    }
  }

  :deep(.el-collapse-item__header) {
    height: auto;
    min-height: 40px;
    padding: 8px 12px;
  }

  :deep(.el-collapse-item__content) {
    padding: 0 12px 12px;
  }

  :deep(.el-empty) {
    padding: 40px 0;
  }
}
</style>
