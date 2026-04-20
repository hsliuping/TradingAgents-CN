<template>
  <div class="usage-guide">
    <el-page-header @back="goBack" content="使用文档" />
    <div class="content" v-html="html"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { marked } from 'marked'

const router = useRouter()
const html = ref('')

const goBack = () => router.back()

onMounted(async () => {
  const mod = await import('../../../../docs/learning/07-tutorials/usage-guide.md?raw')
  const md: string = typeof mod === 'string' ? mod : (mod.default || '')

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
    return `<h${depth} id="${id}">${htmlText}</h${depth}>`
  }

  marked.setOptions({ renderer })
  html.value = marked.parse(md) as string
})
</script>

<style scoped lang="scss">
.usage-guide {
  display: flex;
  flex-direction: column;
  min-height: 100vh;

  :deep(.el-page-header) {
    padding: 16px 24px;
    background: var(--el-fill-color-blank);
    border-bottom: 1px solid var(--el-border-color);
    flex-shrink: 0;
  }

  .content {
    max-width: 1000px;
    margin: 0 auto;
    padding: 24px;
    width: 100%;
    font-size: 16px;
    line-height: 1.8;
    color: var(--el-text-color-primary);

    :deep(h1) {
      font-size: 28px;
      margin: 24px 0 16px;
      padding-bottom: 8px;
      border-bottom: 1px solid var(--el-border-color);
    }

    :deep(h2) {
      font-size: 22px;
      margin: 22px 0 14px;
      padding-bottom: 6px;
      border-bottom: 1px solid var(--el-border-color);
    }

    :deep(h3) {
      font-size: 18px;
      margin: 18px 0 12px;
    }

    :deep(a) {
      color: var(--el-color-primary);
      text-decoration: none;
    }

    :deep(a:hover) {
      text-decoration: underline;
    }

    :deep(code) {
      background: var(--el-fill-color-light);
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 0.95em;
    }

    :deep(pre) {
      background: var(--el-fill-color-light);
      padding: 14px 16px;
      border-radius: 8px;
      overflow: auto;
    }
  }
}
</style>

