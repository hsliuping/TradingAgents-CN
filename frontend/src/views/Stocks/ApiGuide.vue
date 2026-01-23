<template>
  <div class="api-guide-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>📊 股票数据批量导入 API 指南</h2>
          <div class="header-actions">
            <el-tag v-if="!isPro" type="warning" effect="dark">
              <el-icon><Lock /></el-icon>
              高级功能
            </el-tag>
            <el-button type="primary" @click="downloadFile">
              <el-icon><Download /></el-icon>
              下载文档
            </el-button>
          </div>
        </div>
      </template>

      <!-- 高级学员权限提示 -->
      <el-alert
        v-if="!isPro"
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom: 20px;"
      >
        <template #title>
          <strong>此功能为高级学员专属</strong>
        </template>
        <p>批量导入功能需要高级学员权限。您可以在 <router-link to="/settings/license">许可证管理</router-link> 页面激活。</p>
      </el-alert>

      <div v-loading="loading" class="markdown-content" v-html="renderedContent"></div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { Download, Lock } from '@element-plus/icons-vue'
import { marked } from 'marked'
import { useLicenseStore } from '@/stores/license'

// 配置 marked 选项
marked.setOptions({ breaks: true, gfm: true })

const licenseStore = useLicenseStore()
const loading = ref(false)
const markdownContent = ref('')
const renderedContent = ref('')

// 检查是否为 PRO 用户
const isPro = computed(() => licenseStore.isPro)

// 加载 Markdown 内容
const loadContent = async () => {
  loading.value = true
  try {
    const apiUrl = '/api/stock-data/api-guide-content'
    
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
    console.error('加载 API 指南失败:', error)
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
  const url = `${baseUrl}/api/stock-data/download-api-guide-file`
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
      font-size: 20px;
    }

    .header-actions {
      display: flex;
      gap: 12px;
      align-items: center;
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

