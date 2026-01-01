<template>
  <div class="template-viewer-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>{{ title }}</h2>
          <el-button type="primary" @click="downloadFile">
            <el-icon><Download /></el-icon>
            下载文件
          </el-button>
        </div>
      </template>

      <div v-loading="loading" class="content-display">
        <pre v-if="fileType === 'json'" class="json-content"><code>{{ content }}</code></pre>
        <div v-else-if="fileType === 'csv'" class="csv-content" v-html="renderedCsv"></div>
        <pre v-else class="code-content"><code>{{ content }}</code></pre>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { Download } from '@element-plus/icons-vue'

const route = useRoute()
const loading = ref(false)
const content = ref('')
const fileType = ref<'json' | 'csv' | 'python'>('json')

const title = computed(() => {
  if (fileType.value === 'json') return 'JSON模板文件'
  if (fileType.value === 'csv') return 'CSV模板文件'
  return 'Python API示例代码'
})

const downloadUrl = computed(() => {
  const routeName = route.name as string
  if (routeName === 'SocialMediaApiExample') {
    return '/api/social-media/download-api-example-file'
  }
  const type = route.params.type as string
  if (type === 'json') return '/api/social-media/download-template-file/json'
  if (type === 'csv') return '/api/social-media/download-template-file/csv'
  return ''
})

const renderedCsv = computed(() => {
  if (fileType.value !== 'csv' || !content.value) return ''
  
  const lines = content.value.trim().split('\n')
  if (lines.length === 0) return ''
  
  const headers = lines[0].split(',')
  const rows = lines.slice(1).filter(line => line.trim())
  
  const tableRows = rows.map(row => {
    const cells = row.split(',')
    return `<tr>${cells.map(cell => `<td>${cell}</td>`).join('')}</tr>`
  }).join('')
  
  return `
    <table class="csv-table">
      <thead>
        <tr>${headers.map(header => `<th>${header}</th>`).join('')}</tr>
      </thead>
      <tbody>
        ${tableRows}
      </tbody>
    </table>
  `
})

// 加载文件内容
const loadContent = async () => {
  loading.value = true
  try {
    // 判断是模板还是示例代码
    const routeName = route.name as string
    let apiUrl = ''
    
    if (routeName === 'SocialMediaApiExample') {
      // API示例代码
      fileType.value = 'python'
      apiUrl = '/api/social-media/api-example-content'
    } else {
      // 模板文件
      const type = route.params.type as string
      if (type === 'json') {
        fileType.value = 'json'
        apiUrl = '/api/social-media/template-content/json'
      } else if (type === 'csv') {
        fileType.value = 'csv'
        apiUrl = '/api/social-media/template-content/csv'
      } else {
        throw new Error('不支持的文件类型')
      }
    }
    
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
    
    content.value = await response.text()
  } catch (error: any) {
    console.error('加载文件失败:', error)
    content.value = `加载失败: ${error?.message || '未知错误'}`
  } finally {
    loading.value = false
  }
}

// 下载文件
const downloadFile = () => {
  const url = downloadUrl.value
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
.template-viewer-container {
  padding: 20px;

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    h2 {
      margin: 0;
    }
  }

  .content-display {
    padding: 20px;
    
    pre {
      background: var(--el-fill-color-light);
      padding: 20px;
      border-radius: 6px;
      overflow-x: auto;
      margin: 0;
      border: 1px solid var(--el-border-color-light);
      
      code {
        font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
        font-size: 14px;
        line-height: 1.6;
        color: var(--el-text-color-primary);
      }
    }

    .json-content {
      background: #282c34;
      color: #abb2bf;
      
      code {
        color: #abb2bf;
      }
    }

    .code-content {
      background: #282c34;
      color: #abb2bf;
      
      code {
        color: #abb2bf;
      }
    }

    .csv-content {
      :deep(.csv-table) {
        width: 100%;
        border-collapse: collapse;
        margin: 0;

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
    }
  }
}
</style>

