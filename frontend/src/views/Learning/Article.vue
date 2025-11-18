<template>
  <div class="learning-article-wrapper">
    <!-- 页面头部 -->
    <el-page-header @back="goBack" :content="article.title">
      <template #extra>
        <el-button type="primary" :icon="Download" @click="downloadArticle">下载</el-button>
      </template>
    </el-page-header>

    <!-- 主容器：文章 + 侧边栏 -->
    <div class="learning-article">
      <div class="article-container">
        <div class="article-meta">
          <el-tag :type="article.categoryType" size="small">{{ article.category }}</el-tag>
          <span class="read-time">
            <el-icon><Clock /></el-icon>
            {{ article.readTime }}
          </span>
          <span class="views">
            <el-icon><View /></el-icon>
            {{ article.views }}
          </span>
          <span class="update-time">更新于 {{ article.updateTime }}</span>
        </div>

        <div class="article-content" v-html="article.content"></div>

        <div class="article-footer">
          <el-divider />
          <div class="navigation">
            <el-button v-if="prevArticle" @click="navigateToArticle(prevArticle.id)">
              <el-icon><ArrowLeft /></el-icon>
              上一篇：{{ prevArticle.title }}
            </el-button>
            <el-button v-if="nextArticle" @click="navigateToArticle(nextArticle.id)">
              下一篇：{{ nextArticle.title }}
              <el-icon><ArrowRight /></el-icon>
            </el-button>
          </div>
        </div>
      </div>

      <!-- 侧边栏目录 -->
      <div class="article-toc">
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
import { Download, Clock, View, ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'

const route = useRoute()
const router = useRouter()

const articleId = computed(() => route.params.id as string)

// 回退：不集成 Mermaid

// 文章注册表：支持本地 Markdown 或外链（externalUrl）
type ArticleInfo = {
  title: string
  category: string
  categoryType: any
  readTime: string
  loader?: () => Promise<any>
  externalUrl?: string
}

const registry: Record<string, ArticleInfo> = {
  'what-is-llm': { title: '什么是大语言模型（LLM）？', loader: () => import('../../../../docs/learning/01-ai-basics/what-is-llm.md?raw'), category: 'AI基础知识', categoryType: 'primary', readTime: '10分钟' },
  'prompt-basics': { title: '提示词基础', loader: () => import('../../../../docs/learning/02-prompt-engineering/prompt-basics.md?raw'), category: '提示词工程', categoryType: 'success', readTime: '10分钟' },
  'best-practices': { title: '提示词工程最佳实践', loader: () => import('../../../../docs/learning/02-prompt-engineering/best-practices.md?raw'), category: '提示词工程', categoryType: 'success', readTime: '12分钟' },
  'model-comparison': { title: '大语言模型对比与选择', loader: () => import('../../../../docs/learning/03-model-selection/model-comparison.md?raw'), category: '模型选择指南', categoryType: 'warning', readTime: '15分钟' },
  'multi-agent-system': { title: '多智能体系统详解', loader: () => import('../../../../docs/learning/04-analysis-principles/multi-agent-system.md?raw'), category: 'AI分析原理', categoryType: 'info', readTime: '15分钟' },
  'risk-warnings': { title: 'AI股票分析的风险与局限性', loader: () => import('../../../../docs/learning/05-risks-limitations/risk-warnings.md?raw'), category: '风险与局限性', categoryType: 'danger', readTime: '12分钟' },
  'tradingagents-intro': { title: 'TradingAgents项目介绍', loader: () => import('../../../../docs/learning/06-resources/tradingagents-intro.md?raw'), category: '源项目与论文', categoryType: 'primary', readTime: '15分钟' },
  'paper-guide': { title: 'TradingAgents论文解读', loader: () => import('../../../../docs/learning/06-resources/paper-guide.md?raw'), category: '源项目与论文', categoryType: 'primary', readTime: '20分钟' },
  'TradingAgents_论文中文版': { title: 'TradingAgents 论文中文版', loader: () => import('../../../../docs/paper/TradingAgents_论文中文版.md?raw'), category: '源项目与论文', categoryType: 'primary', readTime: '40分钟' },
  // 快速入门改为外链，点击后直接跳转到微信文章
  'getting-started': { title: '快速入门教程（外链）', externalUrl: 'https://mp.weixin.qq.com/s/uAk4RevdJHMuMvlqpdGUEw', category: '实战教程', categoryType: 'success', readTime: '10分钟' },
  // 使用指南（试用版）外链
  'usage-guide-preview': { title: '使用指南（试用版）', externalUrl: 'https://mp.weixin.qq.com/s/ppsYiBncynxlsfKFG8uEbw', category: '实战教程', categoryType: 'success', readTime: '15分钟' },
  'general-questions': { title: '常见问题解答', loader: () => import('../../../../docs/learning/08-faq/general-questions.md?raw'), category: '常见问题', categoryType: 'info', readTime: '15分钟' }
}

// 文章顺序用于上一页/下一页
const articleOrder = [
  'what-is-llm',
  'prompt-basics',
  'best-practices',
  'model-comparison',
  'multi-agent-system',
  'risk-warnings',
  'tradingagents-intro',
  'paper-guide',
  'TradingAgents_论文中文版',
  'getting-started',
  'usage-guide-preview',
  'general-questions'
]

// 当前文章数据
const article = ref({
  id: '',
  title: '',
  category: '',
  categoryType: 'primary' as any,
  readTime: '',
  views: 0,
  updateTime: '',
  content: ''
})

// 目录
const tableOfContents = ref<{ id: string; text: string; level: number }[]>([])

const prevArticle = ref<{ id: string; title: string } | null>(null)
const nextArticle = ref<{ id: string; title: string } | null>(null)

const goBack = () => {
  router.back()
}

const downloadArticle = async () => {
  if (!article.value.id) return
  const info = registry[article.value.id]
  if (!info) {
    ElMessage.warning('未找到文章资源')
    return
  }
  // 外链文章：下载按钮直接在新标签页打开
  if (info.externalUrl) {
    window.open(info.externalUrl, '_blank')
    return
  }
  try {
    const mod = info.loader ? await info.loader() : ''
    const md: string = typeof mod === 'string' ? mod : (mod.default || '')
    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${article.value.id}.md`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  } catch (e) {
    console.error(e)
    ElMessage.error('下载失败')
  }
}

const navigateToArticle = (id: string) => {
  router.push(`/learning/article/${id}`)
}

const scrollToHeading = (id: string) => {
  const element = document.getElementById(id)
  if (element) {
    element.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

// 将 markdown 中的本地链接转换为应用内路由链接
function convertLocalLinks(html: string): string {
  const div = document.createElement('div')
  div.innerHTML = html

  // 处理所有链接
  const links = div.querySelectorAll('a')
  for (const link of links) {
    const href = link.getAttribute('href')
    if (href && href.endsWith('.md')) {
      // 提取文件名（不含扩展名）
      const fileName = href.split('/').pop()?.replace('.md', '')
      if (fileName && registry[fileName]) {
        // 转换为应用内路由链接
        link.setAttribute('href', `/learning/article/${fileName}`)
        link.setAttribute('data-internal', 'true')
      }
    }
    // 将 PDF 链接重写为静态资源路径，并在新标签打开
    else if (href && href.endsWith('.pdf')) {
      const fileName = href.split('/').pop() || ''
      if (fileName) {
        // 如果原始链接在 docs 中指向 paper/，则优先映射到 /paper/
        const target = href.includes('/paper/') ? `/paper/${fileName}` : `/assets/${fileName}`
        link.setAttribute('href', target)
        link.setAttribute('target', '_blank')
        link.setAttribute('rel', 'noopener noreferrer')
      }
    }
  }

  return div.innerHTML
}

// 将 Markdown 中的图片路径重写为打包后的资源 URL（适配仓库根目录下的 assets/）
function rewriteImageSrc(html: string): string {
  const div = document.createElement('div')
  div.innerHTML = html

  const assetMap: Record<string, string> = {
    // 统一映射到前端 public 静态资源目录，避免 Vite 对跨根目录 new URL 的构建警告
    'assets/schema.png': '/assets/schema.png',
    'assets/analyst.png': '/assets/analyst.png',
    'assets/researcher.png': '/assets/researcher.png',
    'assets/trader.png': '/assets/trader.png',
    'assets/risk.png': '/assets/risk.png'
  }

  const imgs = div.querySelectorAll('img')
  for (const img of imgs) {
    const src = img.getAttribute('src') || ''
    // 对以 / 开头的绝对路径（如 /assets/...）不做改写，交给 public 静态资源处理
    if (src.startsWith('/')) continue
    for (const key in assetMap) {
      if (src.endsWith(key)) {
        img.setAttribute('src', assetMap[key])
        break
      }
    }
  }

  return div.innerHTML
}

// 回退：保留原始 markdown 代码块，不转换为 Mermaid 容器

// 已移除 Mermaid 渲染，保留普通代码块

// 从 markdown 加载文章
async function loadArticle(id: string) {
  const info = registry[id]
  if (!info) {
    ElMessage.error('未找到文章')
    return
  }
  // 外链文章：自动在新标签页打开，当前页保留在系统内
  if (info.externalUrl) {
    window.open(info.externalUrl, '_blank')
    article.value = {
      id,
      title: info.title,
      category: info.category,
      categoryType: info.categoryType,
      readTime: info.readTime,
      views: 0,
      updateTime: new Date().toISOString().slice(0, 10),
      content: ''
    }
    ElMessage.info('已在新标签页打开外部页面')
    return
  }
  article.value = {
    id,
    title: info.title,
    category: info.category,
    categoryType: info.categoryType,
    readTime: info.readTime,
    views: 0,
    updateTime: new Date().toISOString().slice(0, 10),
    content: ''
  }

  try {
    const mod = info.loader ? await info.loader() : ''
    const md: string = typeof mod === 'string' ? mod : (mod.default || '')
    // 解析 markdown -> html，并开启标题锚点（兼容中文）
    const renderer = new marked.Renderer()
    renderer.heading = function ({ tokens, depth, text }: any) {
      let htmlText = ''
      if (Array.isArray(tokens) && tokens.length) {
        htmlText = this.parser.parseInline(tokens)
      } else if (typeof text === 'string') {
        htmlText = marked.parseInline(text) as string
      }
      const plain = (htmlText || '').replace(/<[^>]+>/g, '')
      const id = plain
        .toLowerCase()
        .replace(/[^\w\u4e00-\u9fa5]+/g, '-')
        .replace(/^-+|-+$/g, '')
      return `<h${depth} class="article-heading" id="${id}">${htmlText}</h${depth}>`
    }
    marked.setOptions({ renderer })
    let html = marked.parse(md) as string
    // 转换本地文章链接
    html = convertLocalLinks(html)
    // 重写图片资源路径，确保从仓库根目录的 assets/ 正确加载
    html = rewriteImageSrc(html)
    article.value.content = html
    await nextTick()
    buildTOCFromHTML(html)
    buildPrevNext(id)
    // 在 DOM 更新后设置内部链接处理
    setupInternalLinks()
  } catch (e) {
    console.error(e)
    ElMessage.error('加载文章失败：无法访问文档资源')
  }
}

function buildTOCFromHTML(html: string) {
  const div = document.createElement('div')
  div.innerHTML = html
  const headings = Array.from(div.querySelectorAll('h2, h3, h4')) as HTMLHeadingElement[]
  tableOfContents.value = headings.map(h => ({
    id: h.id || h.textContent?.trim().toLowerCase().replace(/\s+/g, '-') || '',
    text: h.textContent || '',
    level: Number(h.tagName.substring(1))
  }))
}

// 在 DOM 更新后处理内部链接
function setupInternalLinks() {
  nextTick(() => {
    const container = document.querySelector('.article-content')
    if (!container) return

    const links = container.querySelectorAll('a[data-internal="true"]')
    for (const link of links) {
      link.addEventListener('click', (e) => {
        e.preventDefault()
        const href = link.getAttribute('href')
        if (href) {
          router.push(href)
        }
      })
    }
  })
}

function buildPrevNext(id: string) {
  const idx = articleOrder.indexOf(id)
  prevArticle.value = idx > 0 ? { id: articleOrder[idx - 1], title: registry[articleOrder[idx - 1]].title } : null
  nextArticle.value = idx >= 0 && idx < articleOrder.length - 1 ? { id: articleOrder[idx + 1], title: registry[articleOrder[idx + 1]].title } : null
}

onMounted(() => {
  loadArticle(articleId.value)
})

watch(articleId, (id) => {
  loadArticle(id)
})
</script>

<style scoped lang="scss">
.learning-article-wrapper {
  display: flex;
  flex-direction: column;
  min-height: 100vh;

  :deep(.el-page-header) {
    padding: 16px 24px;
    background: var(--el-fill-color-blank);
    border-bottom: 1px solid var(--el-border-color);
    flex-shrink: 0;
  }

  /* PageHeader 标题颜色提高对比度 */
  :deep(.el-page-header__content),
  :deep(.el-page-header__title) {
    color: var(--el-text-color-primary);
    font-weight: 600;
  }
}

  .learning-article {
    display: flex;
    padding: 24px;
    max-width: 1400px;
    margin: 0 auto;
    gap: 24px;
    flex: 1;
    width: 100%;

    .article-container {
      flex: 1;
      min-width: 0;
      background: var(--el-fill-color-blank);
      border-radius: 8px;
      padding: 32px;
      box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);

      .article-meta {
        display: flex;
        align-items: center;
        gap: 16px;
        margin-bottom: 32px;
        padding-bottom: 16px;
        border-bottom: 1px solid var(--el-border-color);

        span {
          display: flex;
          align-items: center;
          font-size: 14px;
          color: var(--el-text-color-regular);

          .el-icon {
            margin-right: 4px;
          }
        }
      }

      .article-content {
        font-size: 16px;
        line-height: 1.8;
        color: var(--el-text-color-primary);

        :deep(h1) {
          font-size: 28px;
          margin: 36px 0 18px;
          padding-bottom: 10px;
          border-bottom: 2px solid var(--el-border-color);
          color: var(--el-text-color-primary);
          font-weight: 700;
        }

        :deep(h2) {
          font-size: 24px;
          margin: 32px 0 16px;
          padding-bottom: 8px;
          border-bottom: 2px solid var(--el-border-color);
          color: var(--el-text-color-primary);
          font-weight: 600;
        }

        :deep(h3) {
          font-size: 20px;
          margin: 24px 0 12px;
          color: var(--el-text-color-regular);
          font-weight: 600;
        }

        :deep(h4) {
          font-size: 18px;
          margin: 20px 0 10px;
          color: var(--el-text-color-regular);
          font-weight: 600;
        }

        :deep(p) {
          margin: 16px 0;
          text-align: justify;
        }

        :deep(ul), :deep(ol) {
          margin: 16px 0;
          padding-left: 24px;

          li {
            margin: 8px 0;
          }
        }

        :deep(code) {
          background: var(--el-fill-color-light);
          padding: 2px 6px;
          border-radius: 4px;
          font-family: 'Consolas', 'Monaco', monospace;
          font-size: 14px;
          color: var(--el-text-color-primary);
        }

        :deep(pre) {
          background: var(--el-fill-color-light);
          color: var(--el-text-color-primary);
          padding: 16px;
          border-radius: 8px;
          overflow-x: auto;
          margin: 16px 0;

          code {
            background: none;
            padding: 0;
            color: inherit;
          }
        }


        :deep(blockquote) {
          border-left: 4px solid var(--el-color-primary);
          margin: 16px 0;
          padding: 12px 16px;
          color: var(--el-text-color-secondary);
          background: var(--el-fill-color-light);
          border-radius: 4px;
        }

        // 图片自适应容器宽度，避免过小或溢出
        :deep(img) {
          max-width: 100%;
          height: auto;
          display: block;
          margin: 12px auto;
        }
      }

    .article-footer {
      margin-top: 48px;

      .navigation {
        display: flex;
        justify-content: space-between;
        gap: 16px;

        .el-button {
          flex: 1;
          max-width: 400px;
        }
      }
    }
  }

  .article-toc {
    width: 240px;
    position: sticky;
    top: 80px;
    height: fit-content;
    background: var(--el-fill-color-blank);
    border-radius: 8px;
    padding: 20px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);

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

      .toc-item {
        padding: 8px 0;
        cursor: pointer;
        color: var(--el-text-color-regular);
        font-size: 14px;
        transition: all 0.3s;
        border-left: 2px solid transparent;
        padding-left: 12px;

        &:hover {
          color: var(--el-color-primary);
          border-left-color: var(--el-color-primary);
        }

        &.toc-level-3 {
          padding-left: 24px;
          font-size: 13px;
        }

        &.toc-level-4 {
          padding-left: 36px;
          font-size: 12px;
        }
      }
    }
  }
}

// 暗黑模式样式
:global(html.dark) {
  .learning-article-wrapper {
    background: #000000 !important;
    :deep(.el-page-header) {
      background: #000000 !important;
      border-bottom-color: var(--el-border-color-light);
    }
    :deep(.el-page-header__content),
    :deep(.el-page-header__title) {
      color: var(--el-text-color-primary) !important;
      opacity: 1;
    }
  }

  .learning-article {
    background: #000000 !important;
    .article-container {
      background: #000000 !important;
      box-shadow: 0 2px 12px rgba(0, 0, 0, 0.6);

      .article-meta {
        border-bottom-color: var(--el-border-color-light);

        span {
          color: var(--el-text-color-regular);
        }
      }

      .article-content {
        color: var(--el-text-color-primary) !important;

        :deep(.article-heading) {
          color: var(--el-text-color-primary) !important;
        }

        :deep(h1) {
          color: var(--el-text-color-primary) !important;
          border-bottom-color: var(--el-border-color) !important;
          font-weight: 800 !important;
        }

        :deep(h2) {
          color: var(--el-text-color-primary) !important;
          border-bottom-color: var(--el-border-color) !important;
          font-weight: 700 !important;
        }

        :deep(h3) {
          color: var(--el-text-color-primary) !important;
          font-weight: 700 !important;
        }

        :deep(h4) {
          color: var(--el-text-color-primary) !important;
          font-weight: 700 !important;
        }

        :deep(p) {
          color: var(--el-text-color-primary) !important;
        }

        :deep(li) {
          color: var(--el-text-color-primary) !important;
        }

        :deep(code) {
          background: var(--el-fill-color-light) !important;
          color: var(--el-text-color-primary) !important;
        }

        :deep(blockquote) {
          background: var(--el-fill-color-light) !important;
          color: var(--el-text-color-secondary) !important;
          border-left-color: var(--el-color-primary) !important;
        }
      }
    }

    .article-toc {
      background: #000000 !important;
      box-shadow: 0 2px 12px rgba(0, 0, 0, 0.6);

      .toc-title {
        color: var(--el-text-color-primary) !important;
      }

      .toc-list {
        .toc-item {
          color: var(--el-text-color-regular) !important;

          &:hover {
            color: var(--el-color-primary) !important;
            border-left-color: var(--el-color-primary) !important;
          }
        }
      }
    }
  }
}

@media (max-width: 1200px) {
  .learning-article {
    .article-toc {
      display: none;
    }
  }
}

@media (max-width: 768px) {
  .learning-article {
    padding: 16px;

    .article-container {
      padding: 20px;

      .article-content {
        font-size: 15px;

        :deep(h2) {
          font-size: 20px;
        }

        :deep(h3) {
          font-size: 18px;
        }
      }

      .article-footer {
        .navigation {
          flex-direction: column;

          .el-button {
            max-width: 100%;
          }
        }
      }
    }
  }
}
</style>

