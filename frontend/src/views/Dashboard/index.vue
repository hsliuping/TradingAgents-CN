<template>
  <div class="dashboard">
    <!-- 欢迎区域 -->
    <div class="welcome-section">
      <div class="welcome-content">
        <h1 class="welcome-title">
          欢迎使用 TradingAgents-CN
          <span class="version-badge">{{ displayVersion }}{{ licenseStore.isPro ? ' Pro' : ' 社区版' }}</span>
        </h1>
        <p class="welcome-subtitle">
          AI辅助股票分析技术学习平台，通过全流程AI辅助，帮助您形成计划→执行→复盘→提升的循环提升方法
        </p>
      </div>
      <div class="welcome-actions">
        <el-button type="primary" size="large" @click="goToAssistant">
          <el-icon><ChatDotRound /></el-icon>
          智能助手
        </el-button>
        <el-button size="large" @click="quickAnalysis">
          <el-icon><TrendCharts /></el-icon>
          快速分析
        </el-button>
        <el-button size="large" @click="goToScreening">
          <el-icon><Search /></el-icon>
          股票筛选
        </el-button>
        <el-button size="large" @click="goToGuide">
          <el-icon><Document /></el-icon>
          使用指南
        </el-button>
      </div>
    </div>


    <!-- ════════ 增强版仪表盘内容（v3.0 统一布局） ════════ -->
    <div class="dashboard-enhanced-content">
      <!-- KPI 数据卡片行 -->
      <KpiCards
        :recent-tasks="recentAnalyses"
        @go-paper="goToPaperTrading"
      />

      <!-- 进行中任务 + 股票关注列表速览（左右布局） -->
      <el-row :gutter="24" class="jdyun-row">
        <el-col :xs="24" :lg="12">
          <RunningTasksCard
            @view-all="goToTasks"
            @view-task="viewTask"
            @start-analysis="quickAnalysis"
          />
        </el-col>
        <el-col :xs="24" :lg="12">
          <el-card class="favorite-stocks-card" shadow="never">
            <template #header>
              <div class="card-header">
                <span class="header-title">
                  <el-icon><Star /></el-icon>
                  股票关注列表速览
                </span>
                <el-button text size="small" @click="goToScreening">
                  添加 <el-icon><Plus /></el-icon>
                </el-button>
              </div>
            </template>
            <div v-if="favoriteStocks.length === 0" class="empty-state">
              <el-icon class="empty-icon"><Star /></el-icon>
              <p>还没有股票关注列表</p>
              <span class="empty-tip">添加关注的股票，追踪每日动态</span>
              <el-button type="primary" size="small" @click="goToScreening">
                添加股票关注列表
              </el-button>
            </div>
            <div v-else class="stock-list">
              <div
                v-for="stock in favoriteStocks.slice(0, 5)"
                :key="stock.code"
                class="stock-item"
                @click="goToStockAnalysis(stock.code)"
              >
                <div class="stock-info">
                  <div class="stock-code">{{ stock.code }}</div>
                  <div class="stock-name">{{ stock.name || stock.stock_name || '—' }}</div>
                </div>
                <div class="stock-price" v-if="stock.current_price">
                  ¥{{ stock.current_price }}
                </div>
                <el-icon class="stock-arrow"><ArrowRight /></el-icon>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 智能助手横幅（可关闭） -->
      <DismissableBanner
        title="试试 v3.0 智能助手"
        description="一句话描述需求，AI 自动完成股票研究、批量分析、复盘等任务"
        action-text="立即体验"
        :icon="ChatDotRound"
        variant="primary"
        storage-key="jdyun_dashboard_assistant_banner"
        @action="goToAssistant"
      />

      <!-- 学习中心横幅（可关闭） -->
      <DismissableBanner
        title="AI 股票分析学习中心"
        description="24 节系统课程，从入门到精通 AI 辅助投资分析"
        action-text="查看课程"
        :icon="Reading"
        variant="info"
        storage-key="jdyun_dashboard_learning_banner"
        @action="goToLearning"
      />

      <!-- 更多功能折叠区（v3.0 核心功能 + 流程配置） -->
      <CollapsibleSection
        title="更多功能"
        badge="展开查看"
        badge-type="info"
        storage-key="jdyun_dashboard_more_expanded"
      >
        <el-row :gutter="16">
          <el-col :xs="12" :sm="6" v-for="feature in jdyunMoreFeatures" :key="feature.path">
            <div class="feature-card" @click="router.push(feature.path)">
              <el-icon class="feature-icon"><component :is="feature.icon" /></el-icon>
              <div class="feature-info">
                <div class="feature-title">{{ feature.title }}</div>
                <div class="feature-desc">{{ feature.description }}</div>
              </div>
            </div>
          </el-col>
        </el-row>
      </CollapsibleSection>

      <!-- 最近分析（京东云版独立显示） -->
      <el-card class="recent-analyses-card jdyun-recent" header="最近分析" style="margin-top: 24px;">
        <el-table :data="recentAnalyses" style="width: 100%">
          <el-table-column prop="symbol" label="股票代码" width="120">
            <template #default="{ row }">
              {{ row.symbol || row.code || row.stock_code || '—' }}
            </template>
          </el-table-column>
          <el-table-column label="股票名称" width="150">
            <template #default="{ row }">
              {{ row.stock_name || row.symbol || row.code || '—' }}
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="getStatusType(row.status)">
                {{ getStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="180">
            <template #default="{ row }">
              {{ formatTime(row.started_at || row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作">
            <template #default="{ row }">
              <el-button type="text" size="small" @click="viewAnalysis(row)">
                查看
              </el-button>
              <el-button
                v-if="row.status === 'completed'"
                type="text"
                size="small"
                @click="downloadReport(row)"
              >
                下载
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="table-footer">
          <el-button type="text" @click="goToHistory">
            查看全部历史 <el-icon><ArrowRight /></el-icon>
          </el-button>
        </div>
      </el-card>

      <!-- 市场快讯（京东云版独立显示） -->
      <el-card class="market-news-card jdyun-news" style="margin-top: 24px;">
        <template #header>
          <span>市场快讯</span>
        </template>
        <div v-if="marketNews.length > 0" class="news-list">
          <div v-for="(news, index) in marketNews.slice(0, 5)" :key="index" class="news-item">
            <div class="news-title">{{ news.title }}</div>
            <div class="news-time">{{ formatTime(news.published_at || news.created_at) }}</div>
          </div>
        </div>
        <div v-else class="empty-state">
          <el-icon class="empty-icon"><InfoFilled /></el-icon>
          <p>暂无市场快讯</p>
        </div>
      </el-card>
    </div>
    <!-- ════════ 增强版仪表盘内容结束 ════════ -->


    <!-- 🔥 系统就绪度引导卡片（未就绪时显示，京东云版隐藏） -->
    <el-card
      v-if="!isJdyunMode && systemReadiness && !systemReadiness.overall_ready && systemReadiness.next_step !== 'error'"
      class="readiness-guide-card"
      shadow="hover"
    >
      <div class="readiness-guide">
        <div class="readiness-icon">
          <el-icon size="36" :color="systemReadiness.next_step === 'sync_data' ? '#E6A23C' : '#409EFF'">
            <SetUp />
          </el-icon>
        </div>
        <div class="readiness-content">
          <h3>{{ systemReadiness.next_step_message }}</h3>
          <div class="readiness-steps">
            <span :class="['step-item', systemReadiness.datasource_configured ? 'done' : (systemReadiness.next_step === 'configure_datasource' ? 'current' : '')]">
              <el-icon v-if="systemReadiness.datasource_configured"><DocumentChecked /></el-icon>
              <span v-else>1</span>
              配置数据源
            </span>
            <span :class="['step-item', systemReadiness.llm_configured ? 'done' : (systemReadiness.next_step === 'configure_llm' ? 'current' : '')]">
              <el-icon v-if="systemReadiness.llm_configured"><DocumentChecked /></el-icon>
              <span v-else>2</span>
              配置大模型
            </span>
            <span :class="['step-item', systemReadiness.basics_synced ? 'done' : (systemReadiness.next_step === 'sync_data' ? 'current' : '')]">
              <el-icon v-if="systemReadiness.basics_synced"><DocumentChecked /></el-icon>
              <span v-else>3</span>
              同步数据
            </span>
          </div>
        </div>
        <div class="readiness-action">
          <el-button type="primary" size="large" @click="goToNextStep">
            前往设置
            <el-icon class="el-icon--right"><ArrowRight /></el-icon>
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 首次登录引导弹窗 -->
    <GuideDialog
      v-model="showGuideDialog"
      :is-first-time="isFirstTimeUser"
      @confirm="handleGuideConfirm"
      @skip="handleGuideSkip"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, markRaw } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { useLicenseStore } from '@/stores/license'
import {
  TrendCharts,
  Search,
  Document,
  ArrowRight,
  InfoFilled,
  Reading,
  PieChart,
  DocumentChecked,
  SetUp,
  Tools,
  EditPen,
  ChatDotRound,
  Refresh,
  DataAnalysis
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { AnalysisTask, AnalysisStatus } from '@/types/analysis'
import KpiCards from '@/components/Dashboard/KpiCards.vue'
import RunningTasksCard from '@/components/Dashboard/RunningTasksCard.vue'
import DismissableBanner from '@/components/Dashboard/DismissableBanner.vue'
import CollapsibleSection from '@/components/Dashboard/CollapsibleSection.vue'
import GuideDialog from '@/components/GuideDialog.vue'
import { favoritesApi } from '@/api/favorites'
import { getTaskList as getUnifiedTaskList } from '@/api/unifiedTasks'
import { newsApi } from '@/api/news'
import { paperApi, type PaperAccountSummary } from '@/api/paper'
import { ensureReportExportAccess } from '@/utils/featureAccess'
import { request, ApiClient } from '@/api/request'
import { isJdyunMode as checkJdyunMode } from '@/utils/config'
import { Star, Plus } from '@element-plus/icons-vue'

const router = useRouter()
const appStore = useAppStore()
const licenseStore = useLicenseStore()
const displayVersion = computed(() => `v${appStore.version}`)
const isJdyunMode = checkJdyunMode()

// 京东云版"更多功能"折叠区配置
const jdyunMoreFeatures = ref([
  { path: '/assistant', title: '智能助手', description: '一句话描述需求，AI 自动完成', icon: markRaw(ChatDotRound) },
  { path: '/screening', title: '选股助手', description: '多维度筛选符合条件的股票', icon: markRaw(Search) },
  { path: '/workflow', title: '流程管理', description: '管理工作流和自定义流程', icon: markRaw(Tools) },
  { path: '/workflow/agent-workshop', title: 'Agent 工坊', description: '可视化构建专属 Agent', icon: markRaw(EditPen) },
  { path: '/review', title: '操作复盘', description: '对操作记录进行 AI 复盘分析', icon: markRaw(DataAnalysis) },
  { path: '/settings/sync', title: '数据同步', description: '同步股票基础和行情数据', icon: markRaw(Refresh) },
  { path: '/paper', title: '模拟交易', description: '使用虚拟资金练习模拟交易', icon: markRaw(PieChart) },
  { path: '/learning', title: '学习中心', description: '24 节 AI 股票分析系统课程', icon: markRaw(Reading) }
])

// 响应式数据
const userStats = ref({
  totalAnalyses: 0,
  successfulAnalyses: 0,
  dailyQuota: 1000,
  dailyUsed: 0,
  concurrentLimit: 3
})

const recentAnalyses = ref<AnalysisTask[]>([])

// 股票关注列表数据
const favoriteStocks = ref<any[]>([])

// 市场快讯数据
const marketNews = ref<any[]>([])
// 模拟交易账户数据
const paperAccount = ref<PaperAccountSummary | null>(null)

// 🔥 系统就绪度（首页引导卡片用）
const systemReadiness = ref<any>(null)

const loadSystemReadiness = async () => {
  try {
    const resp = await request.get('/api/system/readiness')
    systemReadiness.value = resp
  } catch (e) {
    console.warn('⚠️ 系统就绪度检查失败:', e)
  }
}

const goToNextStep = () => {
  if (!systemReadiness.value) return
  const redirect = systemReadiness.value.next_step_redirect || '/settings/config'
  const tab = systemReadiness.value.next_step_tab
  if (tab) {
    router.push(`${redirect}?tab=${tab}`)
  } else {
    router.push(redirect)
  }
}

// 首次登录引导弹窗
const showGuideDialog = ref(false)
const isFirstTimeUser = ref(false)



// 方法
const quickAnalysis = () => {
  router.push('/analysis/single')
}

const goToScreening = () => {
  router.push('/screening')
}

const goToHistory = () => {
    router.push('/tasks/unified')
}

// 京东云版专用方法
const goToTasks = () => {
  router.push('/tasks/unified')
}

const viewTask = (task: any) => {
  if (task?.task_id) {
    router.push(`/tasks/unified?task_id=${task.task_id}`)
  } else {
    router.push('/tasks/unified')
  }
}

const goToStockAnalysis = (code: string) => {
  if (!code) return
  router.push(`/stocks/${code}`)
}

const goToLearning = () => {
  router.push('/learning')
}

const goToGuide = () => {
  router.push('/guide')
}

const goToAssistant = () => {
  router.push('/assistant')
}

const viewAnalysis = (analysis: AnalysisTask) => {
  const status = (analysis as any)?.status
  if (status === 'completed') {
    router.push({ name: 'ReportDetail', params: { id: analysis.task_id } })
  } else {
    // 未完成任务跳转到任务中心的“进行中”标签页
    router.push('/tasks/unified')
  }
}

const downloadReport = async (analysis: AnalysisTask) => {
  if (!(await ensureReportExportAccess(router))) {
    return
  }

  try {
    const reportId = analysis.task_id
    const res: any = await ApiClient.get(`/api/reports/${reportId}/download`, { format: 'markdown' }, { responseType: 'blob' })
    // 响应拦截器直接返回 Blob（response.data）；兼容返回 { data: Blob } 的旧实现
    const blob = res instanceof Blob ? res : (res?.data instanceof Blob ? res.data : new Blob([res]))
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const code = (analysis as any).stock_code || (analysis as any).stock_symbol || 'stock'
    const dateStr = (analysis as any).analysis_date || (analysis as any).start_time || ''
    // 🔥 统一文件名格式：{code}_研究报告_{date}.md
    a.download = `${code}_研究报告_${String(dateStr).slice(0,10)}.md`
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
    ElMessage.success('报告已开始下载')
  } catch (err) {
    console.error('下载报告出错:', err)
    ElMessage.error('下载失败，请稍后重试')
  }
}

const getStatusType = (status: string | AnalysisStatus): 'success' | 'info' | 'warning' | 'danger' => {
  const statusMap: Record<string, 'success' | 'info' | 'warning' | 'danger'> = {
    pending: 'info',
    processing: 'warning',
    running: 'warning',
    completed: 'success',
    failed: 'danger',
    cancelled: 'info'
  }
  return statusMap[status] || 'info'
}

const getStatusText = (status: string | AnalysisStatus) => {
  const statusMap: Record<string, string> = {
    pending: '等待中',
    processing: '处理中',
    running: '处理中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消'
  }
  return statusMap[status] || String(status)
}

import { formatDateTime } from '@/utils/datetime'

const formatTime = (time: string) => {
  return formatDateTime(time)
}

// 剥除字符串中的 HTML 标签（如东方财富新闻标题中的 <em></em> 高亮标记）
// 安全策略：仅做纯文本提取，不渲染 HTML，避免 XSS 风险
const stripHtmlTags = (text: string): string => {
  if (!text) return ''
  // 先把常见 HTML 实体转义符解码（如 &lt; &gt; &amp;）
  return text
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
    .replace(/<[^>]+>/g, '') // 剥除所有 HTML 标签
    .trim()
}

const loadFavoriteStocks = async () => {
  try {
    const response = await favoritesApi.list()
    if (response.success && response.data) {
      favoriteStocks.value = response.data.map((item: any) => ({
        code: item.stock_code || item.code,
        name: item.stock_name || item.name,
        stock_code: item.stock_code,
        stock_name: item.stock_name,
        current_price: item.current_price || 0,
        change_percent: item.change_percent || 0
      }))
    }
  } catch (error) {
    console.error('加载股票关注列表失败:', error)
  }
}

const loadRecentAnalyses = async () => {
  try {
    // 使用新版统一任务中心接口（/api/v2/tasks/list），数据存储在 unified_analysis_tasks 集合
    // 旧版 analysisApi.getTaskList 读取 analysis_tasks 集合（已废弃，数据为空）
    const res = await getUnifiedTaskList({
      // 不传 limit，让后端返回所有记录（unified_tasks.py 中 limit 为 None 时返回全部）
      // 不传 status，展示所有状态的任务
    })

    // unifiedTasks API 返回结构：{ success, data: { tasks, total, limit, skip }, message }
    // 但 ApiClient.get 可能已解包，兼容多种返回结构
    const body: any = (res as any)?.data?.data || (res as any)?.data || res || {}
    const allTasks = body.tasks || []

    // 在前端取最近10条（接口已按 created_at 降序返回）
    const tasks = allTasks.slice(0, 10)

    recentAnalyses.value = tasks
    userStats.value.totalAnalyses = allTasks.length
    userStats.value.successfulAnalyses = allTasks.filter((item: any) => item.status === 'completed').length
  } catch (error) {
    console.error('加载最近研究失败:', error)
    recentAnalyses.value = []
  }
}

const loadMarketNews = async () => {
  try {
    // 先尝试获取最近 24 小时的新闻
    let response = await newsApi.getLatestNews(undefined, 10, 24)

    // 如果最近 24 小时没有新闻，则获取最新的 10 条（不限时间）
    if (response.success && response.data && response.data.news.length === 0) {
      console.log('最近 24 小时没有新闻，获取最新的 10 条新闻（不限时间）')
      response = await newsApi.getLatestNews(undefined, 10, 24 * 365) // 回溯 1 年
    }

    if (response.success && response.data) {
      marketNews.value = response.data.news.map((item: any) => ({
        id: item.id || item.title,
        // 兜底剥除标题中可能残留的 HTML 标签（如东方财富 <em> 高亮标记）
        title: stripHtmlTags(item.title || ''),
        time: item.publish_time,
        published_at: item.publish_time,
        created_at: item.created_at,
        url: item.url,
        source: item.source
      }))
    }
  } catch (error) {
    console.error('加载市场快讯失败:', error)
    // 如果加载失败，显示提示信息
    marketNews.value = []
  }
}

// 加载模拟交易账户信息
const loadPaperAccount = async () => {
  try {
    const response = await paperApi.getAccount()
    if (response.success && response.data) {
      paperAccount.value = response.data.account
    }
  } catch (error) {
    console.error('加载模拟交易账户失败:', error)
    paperAccount.value = null
  }
}

// 跳转到模拟交易页面
const goToPaperTrading = () => {
  router.push('/paper')
}

// 处理引导弹窗确认
const handleGuideConfirm = () => {
  // 弹窗已关闭，不需要额外操作
}

// 处理引导弹窗跳过
const handleGuideSkip = () => {
  // 弹窗已关闭，不需要额外操作
}

// 检查是否是首次登录用户
const checkFirstTimeUser = () => {
  // 检查localStorage中是否有标记
  const guideShown = localStorage.getItem('guide_dialog_shown')
  if (!guideShown) {
    // 首次登录，显示引导弹窗
    isFirstTimeUser.value = true
    showGuideDialog.value = true
  }
}

// 生命周期
onMounted(async () => {
  // 检查是否是首次登录用户
  checkFirstTimeUser()
  
  // 🔥 加载系统就绪度（引导卡片）
  await loadSystemReadiness()
  
  // 加载股票关注列表数据
  await loadFavoriteStocks()
  // 加载最近分析
  await loadRecentAnalyses()
  // 加载市场快讯
  await loadMarketNews()
  // 加载模拟交易账户
  await loadPaperAccount()
})
</script>

<style lang="scss" scoped>
.dashboard {
  .welcome-section {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 12px;
    padding: 40px;
    color: white;
    margin-bottom: 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;

    .welcome-content {
      .welcome-title {
        font-size: 32px;
        font-weight: 600;
        margin: 0 0 12px 0;
        display: flex;
        align-items: center;
        gap: 16px;

        .version-badge {
          background: rgba(255, 255, 255, 0.2);
          padding: 4px 12px;
          border-radius: 20px;
          font-size: 14px;
          font-weight: 400;
        }
      }

      .welcome-subtitle {
        font-size: 16px;
        opacity: 0.9;
        margin: 0;
      }
    }

    .welcome-actions {
      display: flex;
      gap: 16px;
    }
  }

  .readiness-guide-card {
    margin-bottom: 24px;
    border: 2px solid #409EFF;
    background: linear-gradient(135deg, #ecf5ff 0%, #f0f9ff 100%);

    .readiness-guide {
      display: flex;
      align-items: center;
      gap: 24px;
      padding: 8px 0;

      .readiness-icon {
        flex-shrink: 0;
      }

      .readiness-content {
        flex: 1;

        h3 {
          margin: 0 0 12px 0;
          font-size: 18px;
          color: #303133;
        }

        .readiness-steps {
          display: flex;
          gap: 20px;

          .step-item {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 14px;
            border-radius: 16px;
            font-size: 13px;
            background: #f5f7fa;
            color: #909399;

            &.done {
              background: #f0f9eb;
              color: #67c23a;
            }

            &.current {
              background: #ecf5ff;
              color: #409EFF;
              font-weight: 600;
              box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.2);
            }
          }
        }
      }

      .readiness-action {
        flex-shrink: 0;
      }
    }
  }

  .assistant-highlight-card {
    margin-bottom: 24px;
    border: 2px solid #10b981;
    box-shadow: 0 4px 12px rgba(16, 185, 129, 0.15);

    .assistant-icon {
      background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
    }

    .new-badge {
      display: inline-block;
      background: linear-gradient(135deg, #10b981 0%, #059669 100%);
      color: white;
      padding: 2px 10px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 500;
      vertical-align: middle;
      margin-left: 8px;
    }
  }

  .learning-highlight-card {
    margin-bottom: 24px;
    border: 2px solid var(--el-color-primary);
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);

    .learning-highlight {
      display: flex;
      align-items: center;
      gap: 24px;
      padding: 8px;

      .learning-icon {
        flex-shrink: 0;
        width: 80px;
        height: 80px;
        border-radius: 12px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
      }

      .learning-content {
        flex: 1;

        h2 {
          font-size: 20px;
          font-weight: 600;
          margin: 0 0 12px 0;
          color: var(--el-text-color-primary);
        }

        .learning-description {
          font-size: 14px;
          color: var(--el-text-color-regular);
          line-height: 1.8;
          margin: 0 0 16px 0;

          strong {
            color: var(--el-color-primary);
            font-weight: 600;
          }
        }

        .learning-features {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;

          .feature-tag {
            padding: 4px 12px;
            background: var(--el-color-primary-light-9);
            color: var(--el-color-primary);
            border-radius: 16px;
            font-size: 13px;
            font-weight: 500;

            &.highlight {
              background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
              color: white;
              font-weight: 600;
              box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
            }
          }
        }
      }

      .learning-action {
        flex-shrink: 0;
      }
    }
  }

  .quick-actions-card,
  .v2-features-card {
    .quick-actions {
      display: grid;
      gap: 16px;

      .action-item {
        display: flex;
        align-items: center;
        gap: 16px;
        padding: 20px;
        border: 1px solid var(--el-border-color-lighter);
        border-radius: 8px;
        cursor: pointer;
        transition: all 0.3s ease;

        &:hover {
          border-color: var(--el-color-primary);
          background-color: var(--el-color-primary-light-9);
        }

        .action-icon {
          width: 40px;
          height: 40px;
          border-radius: 8px;
          background: var(--el-color-primary-light-8);
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--el-color-primary);
          font-size: 20px;

          &.v3-icon {
            background: rgba(16, 185, 129, 0.1);
            color: #10b981;
          }
        }

        .action-content {
          flex: 1;

          h3 {
            display: flex;
            align-items: center;
            gap: 8px;
            margin: 0 0 4px 0;
            font-size: 16px;
            font-weight: 600;
            color: var(--el-text-color-primary);
          }

          .advanced-chip {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 2px 8px;
            border-radius: 999px;
            background: var(--el-color-success-light-8);
            color: var(--el-color-success-dark-2);
            font-size: 12px;
            font-weight: 600;
            line-height: 1;
          }

          p {
            margin: 0;
            font-size: 14px;
            color: var(--el-text-color-regular);
          }
        }

        .action-arrow {
          color: var(--el-text-color-placeholder);
          transition: transform 0.3s ease;
        }

        &:hover .action-arrow {
          transform: translateX(4px);
        }
      }
    }
  }

  .v3-features-card {
    border: 1px solid rgba(16, 185, 129, 0.3);

    .action-item:hover {
      border-color: #10b981 !important;
      background-color: rgba(16, 185, 129, 0.05) !important;
    }
  }

  .recent-analyses-card {
    .table-footer {
      text-align: center;
      margin-top: 16px;
    }
  }

  .system-status-card {
    .status-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 8px 0;

      &:not(:last-child) {
        border-bottom: 1px solid var(--el-border-color-lighter);
      }

      .status-label {
        color: var(--el-text-color-regular);
      }

      .status-value {
        font-weight: 600;
        color: var(--el-text-color-primary);
      }
    }
  }

  .market-news-card {
    .news-list {
      .news-item {
        padding: 12px 0;
        border-bottom: 1px solid var(--el-border-color-lighter);

        &:last-child {
          border-bottom: none;
        }

        &:hover {
          background-color: var(--el-fill-color-lighter);
          margin: 0 -16px;
          padding: 12px 16px;
          border-radius: 4px;
        }

        .news-title {
          display: block;
          font-size: 14px;
          color: var(--el-text-color-primary);
          margin-bottom: 4px;
          line-height: 1.4;
          word-break: break-all;
        }

        // 带链接的标题：显示为蓝色链接样式，hover 显示下划线
        .news-title-link {
          color: var(--el-color-primary);
          text-decoration: none;
          transition: color 0.2s ease;
          cursor: pointer;

          &:hover {
            color: var(--el-color-primary-light-3);
            text-decoration: underline;
          }

          &:visited {
            color: var(--el-color-primary);
          }
        }

        .news-time {
          font-size: 12px;
          color: var(--el-text-color-placeholder);
        }
      }
    }

    .news-footer {
      text-align: center;
      margin-top: 16px;
    }
  }

  .tips-card {
    .tip-item {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 0;
      font-size: 14px;
      color: var(--el-text-color-regular);

      .tip-icon {
        color: var(--el-color-primary);
      }
    }
  }

  .favorites-card {
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .empty-favorites {
      text-align: center;
      padding: 20px 0;
    }

    .favorites-list {
      .favorite-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 0;
        border-bottom: 1px solid var(--el-border-color-lighter);
        cursor: pointer;
        transition: background-color 0.3s ease;

        &:hover {
          background-color: var(--el-fill-color-lighter);
          margin: 0 -16px;
          padding: 12px 16px;
          border-radius: 6px;
        }

        &:last-child {
          border-bottom: none;
        }

        .stock-info {
          .stock-code {
            font-weight: 600;
            font-size: 14px;
            color: var(--el-text-color-primary);
          }

          .stock-name {
            font-size: 12px;
            color: var(--el-text-color-regular);
            margin-top: 2px;
          }
        }

        .stock-price {
          text-align: right;

          .current-price {
            font-weight: 600;
            font-size: 14px;
            color: var(--el-text-color-primary);
          }

          .change-percent {
            font-size: 12px;
            margin-top: 2px;

            &.price-up {
              color: #f56c6c;
            }

            &.price-down {
              color: #67c23a;
            }

            &.price-neutral {
              color: var(--el-text-color-regular);
            }
          }
        }
      }
    }

    .favorites-footer {
      text-align: center;
      padding-top: 12px;
      border-top: 1px solid var(--el-border-color-lighter);
      margin-top: 12px;
    }
  }

  .paper-trading-card {
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .paper-account-info {
      display: flex;
      flex-direction: column;
      gap: 16px;

      .account-section {
        border: 1px solid var(--el-border-color-lighter);
        border-radius: 8px;
        padding: 12px;
        background-color: var(--el-fill-color-blank);

        .account-section-title {
          font-size: 14px;
          font-weight: 600;
          color: var(--el-text-color-primary);
          margin-bottom: 12px;
          padding-bottom: 8px;
          border-bottom: 1px solid var(--el-border-color-lighter);
        }
      }

      .account-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 0;

        .account-label {
          font-size: 13px;
          color: var(--el-text-color-regular);
        }

        .account-value {
          font-size: 15px;
          font-weight: 600;
          color: var(--el-text-color-primary);

          &.primary {
            color: var(--el-color-primary);
            font-size: 16px;
          }

          &.price-up {
            color: #f56c6c;
          }

          &.price-down {
            color: #67c23a;
          }

          &.price-neutral {
            color: var(--el-text-color-regular);
          }
        }
      }
    }

    .empty-state {
      text-align: center;
      padding: 20px 0;

      .empty-icon {
        font-size: 48px;
        color: var(--el-text-color-placeholder);
        margin-bottom: 12px;
      }

      p {
        color: var(--el-text-color-secondary);
        margin-bottom: 16px;
      }
    }
  }
}

// 响应式设计
@media (max-width: 768px) {
  .dashboard {
    .welcome-section {
      flex-direction: column;
      text-align: center;
      gap: 24px;

      .welcome-actions {
        justify-content: center;
      }
    }

    .learning-highlight-card {
      .learning-highlight {
        flex-direction: column;
        text-align: center;

        .learning-content {
          .learning-features {
            justify-content: center;
          }
        }
      }
    }

    .main-content {
      .el-col {
        margin-bottom: 24px;
      }
    }
  }
}

// ════════ 京东云版专属样式 ════════
.jdyun-row {
  margin-bottom: 24px;
}

.jdyun-dashboard-content {
  margin-top: 24px;
}

.favorite-stocks-card {
  height: 100%;

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .header-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 16px;
      font-weight: 600;
      color: var(--el-text-color-primary);
    }
  }

  .empty-state {
    text-align: center;
    padding: 32px 0;

    .empty-icon {
      font-size: 36px;
      color: var(--el-color-warning);
      margin-bottom: 12px;
    }

    p {
      color: var(--el-text-color-primary);
      margin-bottom: 6px;
    }

    .empty-tip {
      font-size: 12px;
      color: var(--el-text-color-secondary);
      margin-bottom: 16px;
      display: block;
    }
  }

  .stock-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .stock-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 12px;
    border: 1px solid var(--el-border-color-lighter);
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;

    &:hover {
      border-color: var(--el-color-primary);
      background-color: var(--el-color-primary-light-9);
      box-shadow: 0 2px 8px rgba(64, 158, 255, 0.12);

      .stock-arrow {
        transform: translateX(4px);
        color: var(--el-color-primary);
      }

      .stock-code {
        color: var(--el-color-primary);
      }
    }
  }

  .stock-info {
    flex: 1;
    min-width: 0;
  }

  .stock-code {
    font-size: 14px;
    font-weight: 600;
    color: var(--el-text-color-primary);
    transition: color 0.2s ease;
  }

  .stock-name {
    font-size: 12px;
    color: var(--el-color-primary);
    margin-top: 2px;
    cursor: pointer;
    text-decoration: underline;
    text-decoration-style: dotted;
    text-underline-offset: 2px;

    &:hover {
      text-decoration-style: solid;
    }
  }

  .stock-price {
    font-size: 14px;
    font-weight: 500;
    color: var(--el-color-danger);
  }

  .stock-arrow {
    color: var(--el-color-primary);
    transition: all 0.2s ease;
  }
}

.feature-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
  height: 100%;
  background: var(--el-bg-color);

  &:hover {
    border-color: var(--el-color-primary);
    background-color: var(--el-color-primary-light-9);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(64, 158, 255, 0.1);
  }

  .feature-icon {
    font-size: 24px;
    color: var(--el-color-primary);
    background: var(--el-color-primary-light-9);
    padding: 8px;
    border-radius: 8px;
    flex-shrink: 0;
  }

  .feature-info {
    flex: 1;
    min-width: 0;
  }

  .feature-title {
    font-size: 16px;
    font-weight: 700;
    color: var(--el-color-primary);
    margin-bottom: 8px;
    letter-spacing: 0.3px;
    padding-bottom: 6px;
    border-bottom: 1px dashed var(--el-border-color);
    display: inline-block;
  }

  .feature-desc {
    font-size: 12px;
    color: var(--el-text-color-secondary);
    line-height: 1.5;
    opacity: 0.85;
  }
}

.jdyun-recent,
.jdyun-news {
  :deep(.el-card__body) {
    padding: 16px 20px;
  }
}
</style>
