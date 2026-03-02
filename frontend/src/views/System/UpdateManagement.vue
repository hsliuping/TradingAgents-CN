<template>
  <div class="update-management">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1 class="page-title">
        <el-icon><Upload /></el-icon>
        系统更新
      </h1>
      <p class="page-description">
        检查并安装系统更新，保持系统为最新版本
      </p>
    </div>

    <!-- 当前版本信息 -->
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="card-header">
          <span>📋 当前版本信息</span>
          <el-button text type="primary" :icon="Refresh" @click="loadVersionInfo" :loading="loadingVersion">
            刷新
          </el-button>
        </div>
      </template>
      <el-descriptions :column="2" border v-if="versionInfo">
        <el-descriptions-item label="当前版本">
          <el-tag type="primary" size="large">v{{ versionInfo.current_version }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="构建类型">
          {{ versionInfo.build_info?.build_type || '未知' }}
        </el-descriptions-item>
        <el-descriptions-item label="构建时间 (UTC)">
          {{ formatBuildDateUtc(versionInfo.build_info?.build_date) }}
        </el-descriptions-item>
        <el-descriptions-item label="Git 提交">
          <code>{{ versionInfo.build_info?.git_commit || '未知' }}</code>
        </el-descriptions-item>
        <el-descriptions-item label="完整版本号" :span="2">
          {{ versionInfo.build_info?.full_version || '未知' }}
        </el-descriptions-item>
      </el-descriptions>
      <el-empty v-else description="加载中..." />
    </el-card>

    <!-- 检查更新 -->
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="card-header">
          <span>🔍 检查更新</span>
        </div>
      </template>

      <!-- Docker 部署：引导使用 docker pull 更新 -->
      <div v-if="versionInfo?.is_docker" class="docker-update-guide">
        <el-button type="primary" @click="doCheckUpdate" :loading="checking" :icon="Search" size="large" style="margin-bottom: 16px">
          检查更新
        </el-button>
        <el-alert v-if="checkDone && updateInfo?.has_update" type="warning" :closable="false" show-icon style="margin-bottom: 16px">
          <template #title>发现新版本 v{{ updateInfo?.latest_version }}</template>
          <template #default>
            <p>请使用以下方式更新 Docker 部署：</p>
            <ul style="margin: 8px 0; padding-left: 20px;">
              <li><strong>拉取最新镜像：</strong><code>docker pull &lt;镜像名&gt;:latest</code></li>
              <li><strong>使用 docker-compose：</strong><code>docker-compose pull &amp;&amp; docker-compose up -d</code></li>
            </ul>
          </template>
        </el-alert>
        <el-alert v-else-if="checkDone && updateInfo?.check_failed" type="error" :closable="false" show-icon style="margin-bottom: 16px">
          <template #title>检查更新失败</template>
          <template #default>{{ updateInfo?.error_message || '无法连接更新服务器，请检查网络或稍后重试' }}</template>
        </el-alert>
        <el-alert v-else-if="checkDone && !updateInfo?.has_update" title="当前已是最新版本" type="success" :closable="false" show-icon style="margin-bottom: 16px" />
        <el-alert type="info" :closable="false" show-icon>
          <template #title>Docker 更新说明</template>
          <template #default>
            <p>Docker 版本不支持应用内下载更新包，请使用以下方式获取最新版本：</p>
            <ul style="margin: 8px 0; padding-left: 20px;">
              <li><strong>拉取最新镜像：</strong><code>docker pull &lt;镜像名&gt;:latest</code></li>
              <li><strong>使用 docker-compose：</strong><code>docker-compose pull &amp;&amp; docker-compose up -d</code></li>
              <li>或访问官网下载最新安装包</li>
            </ul>
          </template>
        </el-alert>
      </div>

      <!-- Windows 便携版/安装版：应用内检查、下载、安装 -->
      <div v-else-if="versionInfo?.supports_in_app_update !== false" class="check-update-section">
        <el-button type="primary" @click="doCheckUpdate" :loading="checking" :icon="Search" size="large">
          检查更新
        </el-button>

        <!-- 检查失败（服务器连接不上等） -->
        <el-alert v-if="checkDone && updateInfo?.check_failed"
          type="error" :closable="false" show-icon style="margin-top: 16px">
          <template #title>检查更新失败</template>
          <template #default>{{ updateInfo?.error_message || '无法连接更新服务器，请检查网络或稍后重试' }}</template>
        </el-alert>
        <!-- 无更新 -->
        <el-alert v-else-if="checkDone && !updateInfo?.has_update"
          title="当前已是最新版本" type="success" :closable="false" show-icon
          style="margin-top: 16px" />

        <!-- 有更新 -->
        <div v-if="updateInfo?.has_update" class="update-available">
          <el-alert type="warning" :closable="false" show-icon style="margin-top: 16px">
            <template #title>
              发现新版本：<strong>v{{ updateInfo.latest_version }}</strong>
              <el-tag v-if="updateInfo.is_mandatory" type="danger" size="small" style="margin-left: 8px">强制更新</el-tag>
            </template>
          </el-alert>

          <el-descriptions :column="2" border style="margin-top: 16px">
            <el-descriptions-item label="最新版本">v{{ updateInfo.latest_version }}</el-descriptions-item>
            <el-descriptions-item label="发布日期">{{ updateInfo.release_date || '未知' }}</el-descriptions-item>
            <el-descriptions-item label="文件大小">{{ formatFileSize(updateInfo.file_size) }}</el-descriptions-item>
            <el-descriptions-item label="最低要求版本">v{{ updateInfo.min_version || '无' }}</el-descriptions-item>
          </el-descriptions>

          <!-- 更新说明 -->
          <div v-if="updateInfo.release_notes" class="release-notes">
            <h4>📝 更新说明</h4>
            <div class="release-notes-content" v-html="renderMarkdown(updateInfo.release_notes)"></div>
          </div>

          <!-- 下载和安装 -->
          <div class="update-actions">
            <el-button type="primary" @click="doDownload" :loading="downloading"
              :disabled="progress.status === 'completed'" size="large">
              {{ downloading ? '下载中...' : '下载更新包' }}
            </el-button>
            <el-button type="success" @click="doApply"
              :disabled="progress.status !== 'completed'" size="large">
              应用更新并重启
            </el-button>
          </div>

          <!-- 下载进度 -->
          <div v-if="progress.status !== 'idle'" class="download-progress">
            <el-progress :percentage="progress.percent || 0" :status="progressBarStatus" :stroke-width="20" />
            <p class="progress-text">
              <template v-if="progress.status === 'downloading'">
                正在下载... {{ formatFileSize(progress.downloaded || 0) }} / {{ formatFileSize(progress.total || 0) }}
              </template>
              <template v-else-if="progress.status === 'completed'">
                <el-icon style="color: var(--el-color-success)"><SuccessFilled /></el-icon>
                下载完成，可以应用更新
              </template>
              <template v-else-if="progress.status === 'failed'">
                <el-icon style="color: var(--el-color-danger)"><CircleCloseFilled /></el-icon>
                下载失败，请重试
              </template>
              <template v-else-if="progress.status === 'verify_failed'">
                <el-icon style="color: var(--el-color-danger)"><CircleCloseFilled /></el-icon>
                文件校验失败，请重新下载
              </template>
            </p>
          </div>

          <!-- 更新警告 -->
          <el-alert v-if="progress.status === 'completed'" type="warning" :closable="false" show-icon
            style="margin-top: 16px">
            <template #title>应用更新须知</template>
            <template #default>
              <ul style="margin: 8px 0; padding-left: 20px;">
                <li>更新过程中所有服务将<strong>自动停止并重启</strong></li>
                <li>系统会自动备份当前版本到 <code>backup/</code> 目录</li>
                <li>您的数据（数据库、配置文件）<strong>不会丢失</strong></li>
                <li>更新完成后请<strong>刷新浏览器页面</strong></li>
              </ul>
            </template>
          </el-alert>
        </div>
      </div>

      <!-- 未知构建类型 -->
      <el-alert v-else type="warning" :closable="false" show-icon>
        <template #title>当前部署方式暂不支持应用内更新</template>
        <template #default>
          请访问官网或联系管理员获取更新方式。
        </template>
      </el-alert>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, Refresh, Search, SuccessFilled, CircleCloseFilled } from '@element-plus/icons-vue'
import {
  getVersionInfo,
  checkUpdate,
  getDownloadProgress,
  downloadUpdate,
  applyUpdate,
  type VersionInfo,
  type UpdateInfo,
  type DownloadProgress
} from '@/api/update'

// ── 状态 ──────────────────────────────────────────────
const loadingVersion = ref(false)
const checking = ref(false)
const downloading = ref(false)
const checkDone = ref(false)

const versionInfo = ref<VersionInfo | null>(null)
const updateInfo = ref<UpdateInfo | null>(null)
const progress = ref<DownloadProgress>({ status: 'idle' })

let progressTimer: ReturnType<typeof setInterval> | null = null

// ── 计算属性 ──────────────────────────────────────────
const progressBarStatus = computed(() => {
  if (progress.value.status === 'completed') return 'success'
  if (progress.value.status === 'failed' || progress.value.status === 'verify_failed') return 'exception'
  return undefined
})

// ── 方法 ──────────────────────────────────────────────
const formatBuildDateUtc = (dateStr: string | undefined) => {
  if (!dateStr) return '未知'
  try {
    const date = new Date(dateStr)
    const y = date.getUTCFullYear()
    const m = String(date.getUTCMonth() + 1).padStart(2, '0')
    const d = String(date.getUTCDate()).padStart(2, '0')
    const h = String(date.getUTCHours()).padStart(2, '0')
    const min = String(date.getUTCMinutes()).padStart(2, '0')
    const s = String(date.getUTCSeconds()).padStart(2, '0')
    return `${y}-${m}-${d} ${h}:${min}:${s} UTC`
  } catch {
    return dateStr
  }
}

const loadVersionInfo = async () => {
  try {
    loadingVersion.value = true
    const res = await getVersionInfo()
    if (res.data) {
      versionInfo.value = res.data
    }
  } catch (e: any) {
    ElMessage.error('获取版本信息失败: ' + (e.message || '未知错误'))
  } finally {
    loadingVersion.value = false
  }
}

const doCheckUpdate = async () => {
  try {
    checking.value = true
    checkDone.value = false
    const res = await checkUpdate()
    if (res.data) {
      updateInfo.value = res.data
    }
    checkDone.value = true
  } catch (e: any) {
    ElMessage.error('检查更新失败: ' + (e.message || '网络错误'))
  } finally {
    checking.value = false
  }
}

const doDownload = async () => {
  try {
    downloading.value = true
    progress.value = { status: 'downloading', percent: 0 }
    await downloadUpdate()
    startPollingProgress()
  } catch (e: any) {
    ElMessage.error('启动下载失败: ' + (e.message || '未知错误'))
    downloading.value = false
  }
}

const startPollingProgress = () => {
  stopPollingProgress()
  progressTimer = setInterval(async () => {
    try {
      const res = await getDownloadProgress()
      if (res.data) {
        progress.value = res.data
        if (res.data.status === 'completed' || res.data.status === 'failed' || res.data.status === 'verify_failed') {
          stopPollingProgress()
          downloading.value = false
          if (res.data.status === 'completed') {
            ElMessage.success('更新包下载完成')
          } else {
            ElMessage.error('下载失败，请重试')
          }
        }
      }
    } catch {
      // 静默处理轮询错误
    }
  }, 2000)
}

const stopPollingProgress = () => {
  if (progressTimer) {
    clearInterval(progressTimer)
    progressTimer = null
  }
}

const doApply = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要应用更新吗？所有服务将自动停止并重启，更新过程中系统将暂时不可用。',
      '确认更新',
      { confirmButtonText: '确定更新', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return // 用户取消
  }

  try {
    const res = await applyUpdate()
    if (res.data?.success) {
      ElMessage.success('更新已启动，服务即将重启...')
      // 显示倒计时提示
      setTimeout(() => {
        ElMessageBox.alert(
          '更新正在进行中，服务将在 1-2 分钟后重新启动。请稍后刷新页面。',
          '更新进行中',
          { confirmButtonText: '知道了', type: 'info' }
        )
      }, 1000)
    } else {
      ElMessage.error('应用更新失败: ' + (res.data?.error || '未知错误'))
    }
  } catch (e: any) {
    // 如果后端已经退出，连接会断开，这是正常的
    if (e.message?.includes('Network Error') || e.code === 'ERR_NETWORK') {
      ElMessage.success('更新已启动，服务正在重启...')
      ElMessageBox.alert(
        '更新正在进行中，服务将在 1-2 分钟后重新启动。请稍后刷新页面。',
        '更新进行中',
        { confirmButtonText: '知道了', type: 'info' }
      )
    } else {
      ElMessage.error('应用更新失败: ' + (e.message || '未知错误'))
    }
  }
}

// ── 工具函数 ──────────────────────────────────────────
const formatFileSize = (bytes: number): string => {
  if (!bytes || bytes === 0) return '未知'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

const renderMarkdown = (text: string): string => {
  // 简单 Markdown 渲染：标题、列表、加粗、代码
  return text
    .replace(/^### (.+)$/gm, '<h5>$1</h5>')
    .replace(/^## (.+)$/gm, '<h4>$1</h4>')
    .replace(/^# (.+)$/gm, '<h3>$1</h3>')
    .replace(/^\- (.+)$/gm, '<li>$1</li>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>')
}

// ── 生命周期 ──────────────────────────────────────────
onMounted(() => {
  loadVersionInfo()
})

onBeforeUnmount(() => {
  stopPollingProgress()
})
</script>


<style lang="scss" scoped>
.update-management {
  .page-header {
    margin-bottom: 24px;

    .page-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 24px;
      font-weight: 600;
      color: var(--el-text-color-primary);
      margin: 0 0 8px 0;
    }

    .page-description {
      color: var(--el-text-color-regular);
      margin: 0;
    }
  }

  .section-card {
    margin-bottom: 24px;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: 600;
    font-size: 16px;
  }

  .check-update-section {
    .update-available {
      margin-top: 16px;
    }

    .update-actions {
      margin-top: 20px;
      display: flex;
      gap: 12px;
    }

    .download-progress {
      margin-top: 16px;

      .progress-text {
        margin-top: 8px;
        color: var(--el-text-color-regular);
        font-size: 14px;
        display: flex;
        align-items: center;
        gap: 6px;
      }
    }

    .release-notes {
      margin-top: 16px;
      padding: 16px;
      background: var(--el-fill-color-light);
      border-radius: 8px;

      h4 {
        margin: 0 0 12px 0;
        font-size: 15px;
      }

      .release-notes-content {
        font-size: 14px;
        line-height: 1.8;
        color: var(--el-text-color-regular);

        :deep(code) {
          background: var(--el-fill-color);
          padding: 2px 6px;
          border-radius: 4px;
          font-size: 13px;
        }

        :deep(li) {
          margin-left: 20px;
          list-style: disc;
        }
      }
    }
  }
}
</style>
