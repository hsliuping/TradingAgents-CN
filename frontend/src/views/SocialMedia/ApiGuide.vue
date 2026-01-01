<template>
  <div class="api-guide-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>API接入指南</h2>
          <el-button type="primary" @click="downloadFile">
            <el-icon><Download /></el-icon>
            下载文件
          </el-button>
        </div>
      </template>

      <div v-loading="loading" class="markdown-content" v-html="renderedContent"></div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Download } from '@element-plus/icons-vue'
import { marked } from 'marked'

// 配置marked选项
marked.setOptions({ breaks: true, gfm: true })

const loading = ref(false)
const markdownContent = ref('')
const renderedContent = ref('')

// 加载Markdown内容
const loadContent = async () => {
  loading.value = true
  try {
    // 使用相对路径，通过Vite代理访问后端API
    const apiUrl = '/api/social-media/api-guide-content'
    
    const response = await fetch(apiUrl, {
      method: 'GET',
      headers: {
        'Accept': 'text/plain'
      }
    })
    
    if (!response.ok) {
      const errorText = await response.text().catch(() => '')
      throw new Error(`加载失败: ${response.status} ${response.statusText}${errorText ? ' - ' + errorText : ''}`)
    }
    
    markdownContent.value = await response.text()
    renderedContent.value = marked.parse(markdownContent.value) as string
  } catch (error: any) {
    console.error('加载API指南失败:', error)
    renderedContent.value = `<div style="color: var(--el-color-danger); padding: 20px;">
      <p><strong>加载失败</strong></p>
      <p>错误信息: ${error?.message || '未知错误'}</p>
      <p>请检查后端服务是否正常运行，或联系管理员。</p>
    </div>`
  } finally {
    loading.value = false
  }
}

// 下载文件
const downloadFile = () => {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || window.location.origin
  const url = `${baseUrl}/api/social-media/download-api-guide-file`
  const link = document.createElement('a')
  link.href = url
  link.target = '_blank'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

onMounted(() => {
  loadContent()
})
</script>

<style scoped lang="scss">
.api-guide-container {
  padding: 20px;

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    h2 {
      margin: 0;
    }
  }

  .markdown-content {
    padding: 20px;
    line-height: 1.6;
    color: var(--el-text-color-primary);

    :deep(h1) {
      font-size: 28px;
      margin: 24px 0 16px 0;
      color: var(--el-color-primary);
      border-bottom: 2px solid var(--el-color-primary);
      padding-bottom: 10px;
    }

    :deep(h2) {
      font-size: 22px;
      margin: 20px 0 12px 0;
      color: var(--el-text-color-primary);
      border-left: 4px solid var(--el-color-primary);
      padding-left: 12px;
    }

    :deep(h3) {
      font-size: 18px;
      margin: 16px 0 8px 0;
      color: var(--el-text-color-regular);
    }

    :deep(h4) {
      font-size: 16px;
      margin: 12px 0 6px 0;
      color: var(--el-text-color-regular);
    }

    :deep(p) {
      margin: 12px 0;
      line-height: 1.8;
    }

    :deep(ul), :deep(ol) {
      margin: 12px 0;
      padding-left: 24px;

      li {
        margin: 6px 0;
        line-height: 1.6;
      }
    }

    :deep(code) {
      background: var(--el-fill-color-light);
      padding: 2px 6px;
      border-radius: 4px;
      font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
      font-size: 13px;
      color: var(--el-color-danger);
    }

    :deep(pre) {
      background: var(--el-fill-color-light);
      color: var(--el-text-color-primary);
      padding: 16px;
      border-radius: 6px;
      overflow-x: auto;
      margin: 16px 0;
      font-size: 13px;
      border: 1px solid var(--el-border-color-light);

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
      background: var(--el-fill-color-lighter);
      border-radius: 4px;
    }

    :deep(strong) {
      font-weight: 600;
      color: var(--el-text-color-primary);
    }

    :deep(em) {
      font-style: italic;
      color: var(--el-text-color-regular);
    }

    :deep(table) {
      width: 100%;
      border-collapse: collapse;
      margin: 16px 0;

      th, td {
        border: 1px solid var(--el-border-color-light);
        padding: 10px;
        text-align: left;
      }

      th {
        background: var(--el-fill-color-light);
        font-weight: 600;
      }

      tr:nth-child(even) {
        background: var(--el-fill-color-lighter);
      }
    }

    :deep(a) {
      color: var(--el-color-primary);
      text-decoration: none;

      &:hover {
        text-decoration: underline;
      }
    }
  }
}
</style>

