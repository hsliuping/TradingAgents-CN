<template>
  <div class="advanced-lesson-wrapper">
    <el-page-header @back="goBack" :content="sampleTitle">
      <template #extra>
        <el-button type="primary" :icon="Download" @click="downloadSample">下载</el-button>
      </template>
    </el-page-header>

    <div class="advanced-lesson">
      <div class="lesson-container">
        <div class="lesson-meta">
          <el-tag type="success" size="small">课程示例</el-tag>
          <span class="category-name">高级课程样本</span>
          <span class="lesson-order">{{ sampleSubtitle }}</span>
        </div>

        <p v-if="sampleDescription" class="sample-description">{{ sampleDescription }}</p>

        <div class="lesson-content" v-html="sampleContent"></div>
      </div>

      <div class="lesson-toc">
        <div class="toc-title">目录</div>
        <ul class="toc-list">
          <li
            v-for="heading in tableOfContents"
            :key="heading.id"
            :class="['toc-item', `toc-level-${heading.level}`]"
            @click="scrollToHeading(heading.id)"
          >
            {{ heading.text }}
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { renderMarkdown } from '@/utils/markdown'
import sample000001Content from '../../../../docs/07-courses/advanced/expanded/000001_研究报告_2026-04-30.md?raw'

type SampleDefinition = {
  title: string
  subtitle: string
  description: string
  fileName: string
  content: string
}

const sampleDefinitions: Record<string, SampleDefinition> = {
  '000001-research-report-2026-04-30': {
    title: '000001 研究报告示例',
    subtitle: '平安银行 2026-04-30 真实单股研究样本',
    description: '课程里多处引用这份样本来讲解单股研究、择时和风险边界。这里保留完整原文，方便对照阅读。',
    fileName: '000001_研究报告_2026-04-30.md',
    content: sample000001Content
  }
}

const route = useRoute()
const router = useRouter()

const sampleId = computed(() => route.params.sampleId as string)
const sample = computed(() => sampleDefinitions[sampleId.value] || null)

const sampleTitle = computed(() => sample.value?.title || '课程示例')
const sampleSubtitle = computed(() => sample.value?.subtitle || '')
const sampleDescription = computed(() => sample.value?.description || '')

const sampleContent = ref('')
const tableOfContents = ref<Array<{ id: string; text: string; level: number }>>([])

const stripLeadingHeading = (markdown: string) => {
  if (!markdown) {
    return ''
  }

  return markdown.replace(/^#\s+.+?(\r?\n){1,2}/, '')
}

const extractTableOfContents = () => {
  const contentDiv = document.querySelector('.lesson-content')
  if (!contentDiv) {
    return
  }

  const headings = contentDiv.querySelectorAll('h1, h2, h3, h4, h5, h6')
  tableOfContents.value = []

  headings.forEach((heading, index) => {
    const level = parseInt(heading.tagName.charAt(1), 10)
    const text = heading.textContent || ''
    const id = `sample-heading-${index}`

    heading.id = id
    tableOfContents.value.push({ id, text, level })
  })
}

const loadSample = async () => {
  if (!sample.value) {
    ElMessage.error('示例报告不存在')
    router.push('/learning/advanced')
    return
  }

  try {
    const markdown = sample.value.content
    const html = renderMarkdown(stripLeadingHeading(markdown))
    sampleContent.value = html as string

    await nextTick()
    extractTableOfContents()
  } catch (error: any) {
    console.error('加载课程示例失败:', error)
    ElMessage.error('加载课程示例失败：' + (error.message || '未知错误'))
  }
}

const scrollToHeading = (id: string) => {
  const element = document.getElementById(id)
  if (element) {
    element.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

const downloadSample = async () => {
  if (!sample.value) {
    return
  }

  try {
    const markdown = sample.value.content
    const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = sample.value.fileName
    link.click()
    URL.revokeObjectURL(url)
  } catch (error: any) {
    console.error('下载课程示例失败:', error)
    ElMessage.error('下载课程示例失败：' + (error.message || '未知错误'))
  }
}

const goBack = () => {
  router.push('/learning/advanced')
}

watch(sampleId, () => {
  loadSample()
}, { immediate: true })
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
      margin-bottom: 16px;
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

    .sample-description {
      margin: 0 0 24px;
      padding: 12px 16px;
      background: var(--el-fill-color-light);
      border-left: 4px solid var(--el-color-success);
      color: var(--el-text-color-regular);
      line-height: 1.7;
    }

    .lesson-content {
      line-height: 1.9;
      color: var(--el-text-color-primary);

      :deep(h1),
      :deep(h2),
      :deep(h3),
      :deep(h4),
      :deep(h5),
      :deep(h6) {
        scroll-margin-top: 100px;
      }
    }
  }

  .lesson-toc {
    width: 280px;
    flex-shrink: 0;
    position: sticky;
    top: 24px;
    align-self: flex-start;
    max-height: calc(100vh - 48px);
    overflow-y: auto;
    background: var(--el-fill-color-blank);
    border: 1px solid var(--el-border-color);
    border-radius: 8px;
    padding: 20px;

    .toc-title {
      font-size: 16px;
      font-weight: 600;
      margin-bottom: 16px;
      color: var(--el-text-color-primary);
    }

    .toc-list {
      list-style: none;
      padding: 0;
      margin: 0;
    }

    .toc-item {
      cursor: pointer;
      color: var(--el-text-color-regular);
      line-height: 1.6;
      margin-bottom: 10px;

      &:hover {
        color: var(--el-color-primary);
      }
    }

    .toc-level-1 {
      font-weight: 600;
    }

    .toc-level-2 {
      padding-left: 12px;
    }

    .toc-level-3,
    .toc-level-4,
    .toc-level-5,
    .toc-level-6 {
      padding-left: 24px;
      font-size: 13px;
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
</style>