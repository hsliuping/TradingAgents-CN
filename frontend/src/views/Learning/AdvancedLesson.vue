<template>
  <div class="advanced-lesson-wrapper">
    <!-- 页面头部 -->
    <el-page-header @back="goBack" :content="lessonTitle">
      <template #extra>
        <el-button type="primary" :icon="Download" @click="downloadLesson">下载</el-button>
      </template>
    </el-page-header>

    <!-- 主容器：课程内容 + 侧边栏 -->
    <div class="advanced-lesson">
      <div class="lesson-container">
        <div class="lesson-meta">
          <el-tag type="warning" size="small">高级课程</el-tag>
          <span class="category-name">{{ categoryName }}</span>
          <span class="lesson-order">第{{ lessonOrder }}课</span>
        </div>

        <div class="lesson-content" v-html="lessonContent"></div>

        <div class="lesson-footer">
          <el-divider />
          <div class="navigation">
            <el-button v-if="prevLesson" @click="navigateToLesson(prevLesson.category.id, prevLesson.lesson.id)">
              <el-icon><ArrowLeft /></el-icon>
              上一课：{{ prevLesson.lesson.title }}
            </el-button>
            <el-button v-if="nextLesson" @click="navigateToLesson(nextLesson.category.id, nextLesson.lesson.id)">
              下一课：{{ nextLesson.lesson.title }}
              <el-icon><ArrowRight /></el-icon>
            </el-button>
          </div>
        </div>
      </div>

      <!-- 侧边栏目录 -->
      <div class="lesson-toc">
        <div class="toc-title">目录</div>
        <ul class="toc-list">
          <li v-for="heading in tableOfContents" :key="heading.id"
              :class="['toc-item', `toc-level-${heading.level}`]"
              @click="scrollToHeading(heading.id)">
            {{ heading.text }}
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Download, ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import { 
  advancedCourseCategories, 
  getLesson, 
  getAdjacentLessons 
} from '@/config/advancedCourses'

const route = useRoute()
const router = useRouter()

const categoryId = computed(() => route.params.category as string)
const lessonId = computed(() => route.params.lesson as string)

// 获取课程信息
const lesson = computed(() => {
  return getLesson(categoryId.value, lessonId.value)
})

const category = computed(() => {
  return advancedCourseCategories.find(cat => cat.id === categoryId.value)
})

const categoryName = computed(() => category.value?.name || '')
const lessonTitle = computed(() => lesson.value?.title || '')
const lessonOrder = computed(() => lesson.value?.order || 0)

// 获取相邻课程
const { prev: prevLesson, next: nextLesson } = computed(() => {
  if (!categoryId.value || !lessonId.value) {
    return { prev: null, next: null }
  }
  return getAdjacentLessons(categoryId.value, lessonId.value)
})

// 课程内容
const lessonContent = ref('')
const loading = ref(false)

// 目录
const tableOfContents = ref<Array<{ id: string; text: string; level: number }>>([])

// 加载课程内容
const loadLesson = async () => {
  if (!lesson.value) {
    ElMessage.error('课程不存在')
    router.push('/learning/advanced')
    return
  }

  loading.value = true
  try {
    // 从静态导入映射中获取Markdown内容
    const { getCourseContent } = await import('@/config/advancedCourseContent')
    const markdown = await getCourseContent(lesson.value.file)
    
    if (!markdown) {
      throw new Error(`课程文件未找到: ${lesson.value.file}`)
    }

    // 转换为HTML
    const html = marked(markdown)
    lessonContent.value = html

    // 提取目录
    await nextTick()
    extractTableOfContents()
  } catch (error: any) {
    console.error('加载课程失败:', error)
    ElMessage.error('加载课程失败：' + (error.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

// 提取目录
const extractTableOfContents = () => {
  const contentDiv = document.querySelector('.lesson-content')
  if (!contentDiv) return

  const headings = contentDiv.querySelectorAll('h1, h2, h3, h4, h5, h6')
  tableOfContents.value = []

  headings.forEach((heading, index) => {
    const level = parseInt(heading.tagName.charAt(1))
    const text = heading.textContent || ''
    const id = `heading-${index}`

    // 设置ID以便跳转
    heading.id = id

    tableOfContents.value.push({
      id,
      text,
      level
    })
  })
}

// 滚动到指定标题
const scrollToHeading = (id: string) => {
  const element = document.getElementById(id)
  if (element) {
    element.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

// 下载课程
const downloadLesson = async () => {
  if (!lesson.value) return

  try {
    const { getCourseContent } = await import('@/config/advancedCourseContent')
    const markdown = await getCourseContent(lesson.value.file)
    
    if (!markdown) {
      ElMessage.error('课程内容未找到')
      return
    }

    const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = lesson.value.file
    a.click()
    URL.revokeObjectURL(url)
  } catch (error: any) {
    console.error('下载失败:', error)
    ElMessage.error('下载失败：' + (error.message || '未知错误'))
  }
}

// 导航到课程
const navigateToLesson = (catId: string, lesId: string) => {
  router.push(`/learning/advanced/${catId}/${lesId}`)
}

// 返回
const goBack = () => {
  router.push('/learning/advanced')
}

// 监听路由变化
watch([categoryId, lessonId], () => {
  loadLesson()
}, { immediate: true })

onMounted(() => {
  loadLesson()
})
</script>

<style scoped lang="scss">
.advanced-lesson-wrapper {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;

  :deep(.el-page-header) {
    margin-bottom: 32px;
    border-bottom: 1px solid var(--el-border-color);
    background: var(--el-fill-color-blank);
  }
}

.advanced-lesson {
  display: flex;
  gap: 24px;

  .lesson-container {
    flex: 1;
    background: var(--el-fill-color-blank);
    border-radius: 8px;
    padding: 32px;
    border: 1px solid var(--el-border-color);

    .lesson-meta {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--el-border-color);

      .category-name {
        font-size: 14px;
        color: var(--el-text-color-regular);
      }

      .lesson-order {
        font-size: 14px;
        color: var(--el-text-color-secondary);
        margin-left: auto;
      }
    }

    .lesson-content {
      font-size: 16px;
      line-height: 1.8;
      color: var(--el-text-color-primary);

      :deep(h1) {
        font-size: 32px;
        margin-top: 32px;
        margin-bottom: 16px;
        font-weight: 600;
        border-bottom: 2px solid var(--el-border-color);
        padding-bottom: 8px;
      }

      :deep(h2) {
        font-size: 24px;
        margin-top: 24px;
        margin-bottom: 12px;
        font-weight: 600;
      }

      :deep(h3) {
        font-size: 20px;
        margin-top: 20px;
        margin-bottom: 10px;
        font-weight: 600;
      }

      :deep(p) {
        margin-bottom: 16px;
      }

      :deep(ul), :deep(ol) {
        margin-bottom: 16px;
        padding-left: 24px;
      }

      :deep(li) {
        margin-bottom: 8px;
      }

      :deep(code) {
        background: var(--el-fill-color-light);
        padding: 2px 6px;
        border-radius: 4px;
        font-family: 'Courier New', monospace;
        font-size: 14px;
      }

      :deep(pre) {
        background: var(--el-fill-color-light);
        padding: 16px;
        border-radius: 8px;
        overflow-x: auto;
        margin-bottom: 16px;

        code {
          background: transparent;
          padding: 0;
        }
      }

      :deep(blockquote) {
        border-left: 4px solid var(--el-color-primary);
        padding-left: 16px;
        margin-left: 0;
        color: var(--el-text-color-regular);
        font-style: italic;
      }

      :deep(table) {
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 16px;

        th, td {
          border: 1px solid var(--el-border-color);
          padding: 8px 12px;
          text-align: left;
        }

        th {
          background: var(--el-fill-color-light);
          font-weight: 600;
        }
      }
    }

    .lesson-footer {
      margin-top: 48px;

      .navigation {
        display: flex;
        justify-content: space-between;
        gap: 16px;
      }
    }
  }

  .lesson-toc {
    width: 240px;
    position: sticky;
    top: 24px;
    height: fit-content;
    max-height: calc(100vh - 48px);
    overflow-y: auto;
    background: var(--el-fill-color-blank);
    border-radius: 8px;
    padding: 16px;
    border: 1px solid var(--el-border-color);

    .toc-title {
      font-size: 16px;
      font-weight: 600;
      margin-bottom: 12px;
      color: var(--el-text-color-primary);
    }

    .toc-list {
      list-style: none;
      padding: 0;
      margin: 0;

      .toc-item {
        padding: 6px 0;
        cursor: pointer;
        color: var(--el-text-color-regular);
        transition: color 0.2s;

        &:hover {
          color: var(--el-color-primary);
        }

        &.toc-level-1 {
          font-weight: 600;
          font-size: 14px;
        }

        &.toc-level-2 {
          padding-left: 16px;
          font-size: 13px;
        }

        &.toc-level-3 {
          padding-left: 32px;
          font-size: 12px;
        }
      }
    }
  }
}

// 暗黑模式适配
:global(html.dark) {
  .advanced-lesson-wrapper {
    background: #000000 !important;

    :deep(.el-page-header) {
      background: #000000 !important;
      border-bottom-color: var(--el-border-color);
    }
  }

  .advanced-lesson {
    .lesson-container,
    .lesson-toc {
      background: #000000 !important;
      border-color: var(--el-border-color) !important;
    }
  }
}

@media (max-width: 1024px) {
  .advanced-lesson {
    flex-direction: column;

    .lesson-toc {
      width: 100%;
      position: static;
      max-height: none;
    }
  }
}

@media (max-width: 768px) {
  .advanced-lesson-wrapper {
    padding: 16px;
  }

  .advanced-lesson .lesson-container {
    padding: 20px;
  }
}
</style>

