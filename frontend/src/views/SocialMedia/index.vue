<template>
  <div class="social-media-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>社媒消息管理</h2>
          <el-button type="primary" @click="showUploadDialog = true">
            <el-icon><Upload /></el-icon>
            上传社媒数据
          </el-button>
        </div>
      </template>

      <!-- 使用说明和模板下载 -->
      <el-alert
        type="info"
        :closable="false"
        show-icon
        class="help-alert"
      >
        <template #title>
          <div class="help-content">
            <div class="help-title">
              <el-icon><InfoFilled /></el-icon>
              <span>使用说明</span>
            </div>
            <div class="help-links">
              <div class="help-section">
                <strong>📄 模板文件：</strong>
                <el-link
                  type="primary"
                  @click="viewTemplate('json')"
                  :underline="false"
                  class="help-link"
                  style="cursor: pointer;"
                >
                  <el-icon><Document /></el-icon>
                  查看JSON模板
                </el-link>
                <el-link
                  type="primary"
                  @click="viewTemplate('csv')"
                  :underline="false"
                  class="help-link"
                  style="cursor: pointer;"
                >
                  <el-icon><Document /></el-icon>
                  查看CSV模板
                </el-link>
              </div>
              <div class="help-section">
                <strong>📚 API接入：</strong>
                <el-link
                  type="primary"
                  @click="viewApiGuide"
                  :underline="false"
                  class="help-link"
                  style="cursor: pointer;"
                >
                  <el-icon><Reading /></el-icon>
                  查看API指南
                </el-link>
                <el-link
                  type="primary"
                  @click="viewApiExample"
                  :underline="false"
                  class="help-link"
                  style="cursor: pointer;"
                >
                  <el-icon><Document /></el-icon>
                  查看示例代码
                </el-link>
              </div>
            </div>
            <div class="help-tip">
              💡 提示：下载模板文件后，按照格式填写数据，然后通过"上传社媒数据"按钮上传。也可以通过API接口批量上传数据。
            </div>
          </div>
        </template>
      </el-alert>

      <!-- 统计信息 -->
      <el-row :gutter="20" class="stats-row">
        <el-col :span="6">
          <el-statistic title="总消息数" :value="stats.total_count" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="正向情绪" :value="stats.positive_count">
            <template #suffix>
              <el-tag type="success" size="small">positive</el-tag>
            </template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <el-statistic title="负向情绪" :value="stats.negative_count">
            <template #suffix>
              <el-tag type="danger" size="small">negative</el-tag>
            </template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <el-statistic title="中性情绪" :value="stats.neutral_count">
            <template #suffix>
              <el-tag type="info" size="small">neutral</el-tag>
            </template>
          </el-statistic>
        </el-col>
      </el-row>

      <!-- 查询表单 -->
      <el-form :model="queryForm" inline class="query-form">
        <el-form-item label="股票代码">
          <el-input v-model="queryForm.symbol" placeholder="如：000001" clearable />
        </el-form-item>
        <el-form-item label="市场类型">
          <el-select v-model="queryForm.market" placeholder="选择市场" clearable style="width: 150px;">
            <el-option label="A股" value="A股" />
            <el-option label="港股" value="港股" />
            <el-option label="美股" value="美股" />
          </el-select>
        </el-form-item>
        <el-form-item label="平台">
          <el-select v-model="queryForm.platform" placeholder="选择平台" clearable style="width: 180px;">
            <el-option
              v-for="platform in platforms"
              :key="platform.code"
              :label="platform.name"
              :value="platform.code"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="情绪">
          <el-select v-model="queryForm.sentiment" placeholder="选择情绪" clearable style="width: 150px;">
            <el-option label="正向" value="positive" />
            <el-option label="负向" value="negative" />
            <el-option label="中性" value="neutral" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleQuery">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 消息列表 -->
      <el-table :data="messages" v-loading="loading" stripe>
        <el-table-column prop="symbol" label="股票代码" width="100" />
        <el-table-column prop="market" label="市场" width="80">
          <template #default="{ row }">
            <el-tag 
              :type="row.market === 'A股' ? 'success' : row.market === '港股' ? 'warning' : 'danger'"
              size="small"
            >
              {{ row.market || 'A股' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="platform" label="平台" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ getPlatformName(row.platform) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="content" label="内容" min-width="300" show-overflow-tooltip />
        <el-table-column prop="sentiment" label="情绪" width="100">
          <template #default="{ row }">
            <el-tag
              :type="row.sentiment === 'positive' ? 'success' : row.sentiment === 'negative' ? 'danger' : 'info'"
              size="small"
            >
              {{ row.sentiment || 'neutral' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="author.author_name" label="作者" width="120" />
        <el-table-column prop="publish_time" label="发布时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.publish_time) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="viewDetail(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleQuery"
        @current-change="handleQuery"
        class="pagination"
      />
    </el-card>

    <!-- 上传对话框 -->
    <el-dialog v-model="showUploadDialog" title="上传社媒数据" width="600px">
      <el-form :model="uploadForm" label-width="120px">
        <el-alert
          type="info"
          :closable="false"
          style="margin-bottom: 20px;"
        >
          <template #title>
            <div style="font-size: 14px;">
              <strong>提示：</strong>文件中的每条消息必须包含 <code>symbol</code>（股票代码）和 <code>platform</code>（平台）字段。
              <br />
              如果文件中缺少这些字段，上传将失败。
            </div>
          </template>
        </el-alert>
        <el-form-item label="文件编码">
          <el-select v-model="uploadForm.encoding">
            <el-option label="UTF-8" value="utf-8" />
            <el-option label="GBK" value="gbk" />
            <el-option label="GB2312" value="gb2312" />
          </el-select>
        </el-form-item>
        <el-form-item label="上传文件" required>
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
            accept=".json,.csv,.xlsx,.xls"
          >
            <el-button type="primary">选择文件</el-button>
            <template #tip>
              <div class="el-upload__tip">
                支持格式：JSON、CSV、Excel (.xlsx, .xls)
                <br />
                必需字段：message_id, platform, symbol, content, publish_time
              </div>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="uploadForm.overwrite">覆盖已存在的消息</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="handleUpload">
          上传
        </el-button>
      </template>
    </el-dialog>

    <!-- 详情对话框 -->
    <el-dialog v-model="showDetailDialog" title="消息详情" width="800px">
      <el-descriptions :column="2" border v-if="selectedMessage">
        <el-descriptions-item label="消息ID">{{ selectedMessage.message_id }}</el-descriptions-item>
        <el-descriptions-item label="股票代码">{{ selectedMessage.symbol }}</el-descriptions-item>
        <el-descriptions-item label="市场类型">
          <el-tag 
            :type="selectedMessage.market === 'A股' ? 'success' : selectedMessage.market === '港股' ? 'warning' : 'danger'"
            size="small"
          >
            {{ selectedMessage.market || 'A股' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="平台">{{ getPlatformName(selectedMessage.platform) }}</el-descriptions-item>
        <el-descriptions-item label="消息类型">{{ selectedMessage.message_type || 'post' }}</el-descriptions-item>
        <el-descriptions-item label="情绪">
          <el-tag
            :type="selectedMessage.sentiment === 'positive' ? 'success' : selectedMessage.sentiment === 'negative' ? 'danger' : 'info'"
            size="small"
          >
            {{ selectedMessage.sentiment || 'neutral' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="情绪评分">{{ selectedMessage.sentiment_score || 0 }}</el-descriptions-item>
        <el-descriptions-item label="作者">{{ selectedMessage.author?.author_name }}</el-descriptions-item>
        <el-descriptions-item label="认证">
          <el-tag v-if="selectedMessage.author?.verified" type="success" size="small">已认证</el-tag>
          <span v-else>未认证</span>
        </el-descriptions-item>
        <el-descriptions-item label="发布时间">{{ formatTime(selectedMessage.publish_time) }}</el-descriptions-item>
        <el-descriptions-item label="数据来源">{{ selectedMessage.data_source || 'manual' }}</el-descriptions-item>
        <el-descriptions-item label="内容" :span="2">
          <div class="message-content">{{ selectedMessage.content }}</div>
        </el-descriptions-item>
        <el-descriptions-item label="互动数据" :span="2">
          <el-row :gutter="20">
            <el-col :span="6">浏览量: {{ selectedMessage.engagement?.views || 0 }}</el-col>
            <el-col :span="6">点赞: {{ selectedMessage.engagement?.likes || 0 }}</el-col>
            <el-col :span="6">转发: {{ selectedMessage.engagement?.shares || 0 }}</el-col>
            <el-col :span="6">评论: {{ selectedMessage.engagement?.comments || 0 }}</el-col>
          </el-row>
        </el-descriptions-item>
        <el-descriptions-item label="话题标签" v-if="selectedMessage.hashtags?.length">
          <el-tag
            v-for="tag in selectedMessage.hashtags"
            :key="tag"
            size="small"
            style="margin-right: 8px"
          >
            {{ tag }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="关键词" v-if="selectedMessage.keywords?.length">
          <el-tag
            v-for="keyword in selectedMessage.keywords"
            :key="keyword"
            size="small"
            type="info"
            style="margin-right: 8px"
          >
            {{ keyword }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { Upload, InfoFilled, Document, Reading } from '@element-plus/icons-vue'
import { socialMediaApi, type SocialMediaMessage, type Platform } from '@/api/socialMedia'

const router = useRouter()

const loading = ref(false)
const uploading = ref(false)
const showUploadDialog = ref(false)
const showDetailDialog = ref(false)
const uploadRef = ref()
const selectedMessage = ref<SocialMediaMessage | null>(null)

const stats = ref({
  total_count: 0,
  positive_count: 0,
  negative_count: 0,
  neutral_count: 0
})

const platforms = ref<Platform[]>([])
const messages = ref<SocialMediaMessage[]>([])

const queryForm = ref({
  symbol: '',
  market: '',
  platform: '',
  sentiment: ''
})

const uploadForm = ref({
  encoding: 'utf-8',
  overwrite: false
})

const uploadFile = ref<File | null>(null)

const pagination = ref({
  page: 1,
  pageSize: 20,
  total: 0
})

// 加载平台列表
const loadPlatforms = async () => {
  try {
    const res = await socialMediaApi.getPlatforms()
    platforms.value = res.data?.platforms || []
  } catch (e: any) {
    console.error('加载平台列表失败:', e)
  }
}

// 加载统计信息
const loadStatistics = async () => {
  try {
    // 🔥 传递完整的查询条件给统计接口，确保统计和查询条件一致
    const res = await socialMediaApi.getStatistics({
      symbol: queryForm.value.symbol || undefined,
      market: queryForm.value.market || undefined,
      platform: queryForm.value.platform || undefined,
      sentiment: queryForm.value.sentiment || undefined
      // 不传 hoursBack，统计所有符合条件的数据
    })
    if (res.data?.statistics) {
      stats.value = {
        total_count: res.data.statistics.total_count || 0,
        positive_count: res.data.statistics.positive_count || 0,
        negative_count: res.data.statistics.negative_count || 0,
        neutral_count: res.data.statistics.neutral_count || 0
      }
    }
  } catch (e: any) {
    console.error('加载统计信息失败:', e)
  }
}

// 查询消息
const handleQuery = async () => {
  loading.value = true
  try {
    const res = await socialMediaApi.queryMessages({
      symbol: queryForm.value.symbol || undefined,
      market: queryForm.value.market || undefined,
      platform: queryForm.value.platform || undefined,
      sentiment: queryForm.value.sentiment || undefined,
      limit: pagination.value.pageSize,
      skip: (pagination.value.page - 1) * pagination.value.pageSize
    })
    messages.value = res.data?.messages || []
    pagination.value.total = res.data?.count || 0
    
    // 加载统计信息
    await loadStatistics()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '查询失败')
  } finally {
    loading.value = false
  }
}

// 重置查询
const handleReset = () => {
  queryForm.value = {
    symbol: '',
    market: '',
    platform: '',
    sentiment: ''
  }
  handleQuery()
}

// 文件选择
const handleFileChange = (file: any) => {
  uploadFile.value = file.raw
}

// 文件移除
const handleFileRemove = () => {
  uploadFile.value = null
}

// 上传文件
const handleUpload = async () => {
  if (!uploadFile.value) {
    ElMessage.warning('请选择要上传的文件')
    return
  }

  uploading.value = true
  try {
    // 🔥 不再传递symbol和platform，从文件中读取
    const res = await socialMediaApi.uploadFile(uploadFile.value, {
      encoding: uploadForm.value.encoding,
      overwrite: uploadForm.value.overwrite
    })

    ElMessage.success(`上传成功！保存了 ${res.data.saved} 条消息`)
    
    // 重置表单
    uploadForm.value = {
      encoding: 'utf-8',
      overwrite: false
    }
    uploadFile.value = null
    uploadRef.value?.clearFiles()
    showUploadDialog.value = false

    // 刷新列表
    await handleQuery()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = false
  }
}

// 查看详情
const viewDetail = (message: SocialMediaMessage) => {
  selectedMessage.value = message
  showDetailDialog.value = true
}

// 获取平台名称
const getPlatformName = (code: string) => {
  const platform = platforms.value.find(p => p.code === code)
  return platform?.name || code
}

// 格式化时间
const formatTime = (time: string | Date) => {
  if (!time) return '-'
  const date = typeof time === 'string' ? new Date(time) : time
  return date.toLocaleString('zh-CN')
}

// 获取模板文件下载URL
const getTemplateUrl = (type: 'json' | 'csv') => {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || window.location.origin
  return `${baseUrl}/api/social-media/download-template/${type}`
}

// 获取API指南下载URL
const getApiGuideUrl = () => {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || window.location.origin
  return `${baseUrl}/api/social-media/download-api-guide`
}

// 获取API示例代码下载URL
const getApiExampleUrl = () => {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || window.location.origin
  return `${baseUrl}/api/social-media/download-api-example`
}

// 查看API指南
const viewApiGuide = () => {
  router.push({ name: 'SocialMediaApiGuide' })
}

// 查看模板文件
const viewTemplate = (type: 'json' | 'csv') => {
  router.push({ name: 'SocialMediaTemplate', params: { type } })
}

// 查看API示例代码
const viewApiExample = () => {
  router.push({ name: 'SocialMediaApiExample' })
}

// 初始化
onMounted(async () => {
  await loadPlatforms()
  await handleQuery()
})
</script>

<style scoped lang="scss">
.social-media-container {
  padding: 20px;

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    h2 {
      margin: 0;
    }
  }

  .stats-row {
    margin-bottom: 20px;
  }

  .query-form {
    margin-bottom: 20px;
  }

  .pagination {
    margin-top: 20px;
    justify-content: flex-end;
  }

  .form-tip {
    font-size: 12px;
    color: var(--el-text-color-secondary);
    margin-top: 4px;
  }

  .message-content {
    max-height: 200px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-word;
  }

  .help-alert {
    margin-bottom: 20px;

    .help-content {
      .help-title {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 12px;
        font-weight: 600;
        font-size: 14px;
      }

      .help-links {
        display: flex;
        flex-direction: column;
        gap: 12px;
        margin-bottom: 12px;

        .help-section {
          display: flex;
          align-items: center;
          gap: 12px;
          flex-wrap: wrap;

          strong {
            color: var(--el-text-color-primary);
            font-weight: 600;
            min-width: 80px;
          }

          .help-link {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            margin-right: 16px;
            font-size: 13px;

            &:hover {
              color: var(--el-color-primary);
            }
          }
        }
      }

      .help-tip {
        margin-top: 8px;
        padding-top: 8px;
        border-top: 1px solid var(--el-border-color-lighter);
        font-size: 12px;
        color: var(--el-text-color-secondary);
        line-height: 1.6;
      }
    }
  }
}
</style>

