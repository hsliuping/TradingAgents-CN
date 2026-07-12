<template>
  <div class="dashboard">
    <!-- 欢迎区域 -->
    <div class="welcome-section">
      <div class="welcome-content">
        <h1 class="welcome-title">
          欢迎使用 TradingAgents-CN
          <span class="version-badge">{{ displayVersion }} Pro</span>
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


    <!-- 🔥 系统就绪度引导卡片（未就绪时显示） -->
    <el-card
      v-if="systemReadiness && !systemReadiness.overall_ready && systemReadiness.next_step !== 'error'"
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

    <!-- v3.0 智能助手推荐卡片 -->
    <el-card class="assistant-highlight-card">
      <div class="learning-highlight">
        <div class="learning-icon assistant-icon">
          <el-icon size="48"><ChatDotRound /></el-icon>
        </div>
        <div class="learning-content">
          <h2>🤖 智能助手 <span class="new-badge">v3.0 NEW</span></h2>
          <p class="learning-description">
            <strong>🎯 AI 对话式股票分析助手</strong> — 通过自然语言对话，智能调用多种分析工具，为您提供个性化的投资研究支持。支持 QQ 频道接入、MCP 工具扩展、自动 Skill 生成等 v3.0 全新能力。
          </p>
          <div class="learning-features">
            <span class="feature-tag highlight">💬 对话式分析</span>
            <span class="feature-tag">🔧 MCP 工具扩展</span>
            <span class="feature-tag">🏭 Agent 工坊</span>
            <span class="feature-tag">📱 QQ 频道接入</span>
            <span class="feature-tag">⚡ Skill 自动生成</span>
            <span class="feature-tag">🔍 智能选股</span>
          </div>
        </div>
        <div class="learning-action">
          <el-button type="primary" size="large" @click="goToAssistant">
            <el-icon><ChatDotRound /></el-icon>
            开始对话
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 学习中心推荐卡片 -->
    <el-card class="learning-highlight-card">
      <div class="learning-highlight">
        <div class="learning-icon">
          <el-icon size="48"><Reading /></el-icon>
        </div>
        <div class="learning-content">
          <h2>📚 AI股票分析学习中心</h2>
          <p class="learning-description">
            <strong>🎯 24小时全流程AI辅助学习课程</strong> - 通过计划→执行→复盘→提升的完整循环，帮助您形成全流程使用AI辅助的炒股方法提升思路。从入门到提高，系统学习AI辅助股票分析技术。
          </p>
          <div class="learning-features">
            <span class="feature-tag highlight">⏰ 24小时全流程课程</span>
            <span class="feature-tag">📋 计划制定</span>
            <span class="feature-tag">⚡ 执行跟踪</span>
            <span class="feature-tag">📊 复盘分析</span>
            <span class="feature-tag">📈 持续提升</span>
            <span class="feature-tag">🎓 方法构建</span>
          </div>
        </div>
        <div class="learning-action">
          <el-button type="primary" size="large" @click="goToLearning">
            <el-icon><Reading /></el-icon>
            开始学习
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 主要功能区域 -->
    <el-row :gutter="24" class="main-content">
      <!-- 左侧：快速操作 -->
      <el-col :span="16">
        <el-card class="quick-actions-card" header="快速操作">
          <div class="quick-actions">
            <div class="action-item" @click="goToSingleAnalysis">
              <div class="action-icon">
                <el-icon><Document /></el-icon>
              </div>
              <div class="action-content">
                <h3>单股研究</h3>
                <p>深度整理单只股票的研究线索、证据与风险</p>
              </div>
              <el-icon class="action-arrow"><ArrowRight /></el-icon>
            </div>

            <div class="action-item" @click="goToBatchAnalysis">
              <div class="action-icon">
                <el-icon><Files /></el-icon>
              </div>
              <div class="action-content">
                <h3>批量分析 <span class="advanced-chip">高级</span></h3>
                <p>同时分析多只股票，提高效率</p>
              </div>
              <el-icon class="action-arrow"><ArrowRight /></el-icon>
            </div>

            <div class="action-item" @click="goToScreening">
              <div class="action-icon">
                <el-icon><Search /></el-icon>
              </div>
              <div class="action-content">
                <h3>股票筛选</h3>
                <p>通过多维度条件筛选优质股票</p>
              </div>
              <el-icon class="action-arrow"><ArrowRight /></el-icon>
            </div>

            <div class="action-item" @click="goToQueue">
              <div class="action-icon">
                <el-icon><List /></el-icon>
              </div>
              <div class="action-content">
                <h3>任务中心</h3>
                <p>查看和管理分析任务列表</p>
              </div>
              <el-icon class="action-arrow"><ArrowRight /></el-icon>
            </div>

            <div class="action-item" @click="goToPortfolio">
              <div class="action-icon">
                <el-icon><PieChart /></el-icon>
              </div>
              <div class="action-content">
                <h3>持仓研究</h3>
                <p>分析当前持仓的研究状态与风险变化</p>
              </div>
              <el-icon class="action-arrow"><ArrowRight /></el-icon>
            </div>

            <div class="action-item" @click="goToReview">
              <div class="action-icon">
                <el-icon><DocumentChecked /></el-icon>
              </div>
              <div class="action-content">
                <h3>复盘分析</h3>
                <p>回顾和总结交易操作</p>
              </div>
              <el-icon class="action-arrow"><ArrowRight /></el-icon>
            </div>

            <div class="action-item" @click="goToTradingSystem">
              <div class="action-icon">
                <el-icon><Tickets /></el-icon>
              </div>
              <div class="action-content">
                <h3>交易计划</h3>
                <p>制定和管理个人交易规则</p>
              </div>
              <el-icon class="action-arrow"><ArrowRight /></el-icon>
            </div>
          </div>
        </el-card>

        <!-- v3.0 核心功能 -->
        <el-card class="v2-features-card v3-features-card" style="margin-top: 24px;">
          <template #header>
            <span>v3.0 核心功能 <el-tag size="small" type="success" effect="dark" style="margin-left: 8px;">NEW</el-tag></span>
          </template>
          <div class="quick-actions">
            <div class="action-item" @click="goToAssistant">
              <div class="action-icon v3-icon">
                <el-icon><ChatDotRound /></el-icon>
              </div>
              <div class="action-content">
                <h3>智能助手 <el-tag size="small" type="success">v3.0</el-tag></h3>
                <p>AI 对话式分析助手，自然语言驱动的投资研究</p>
              </div>
              <el-icon class="action-arrow"><ArrowRight /></el-icon>
            </div>

            <div class="action-item" @click="goToScreening">
              <div class="action-icon v3-icon">
                <el-icon><Filter /></el-icon>
              </div>
              <div class="action-content">
                <h3>智能选股 <el-tag size="small" type="success">v3.0</el-tag></h3>
                <p>自然语言描述选股条件，AI 自动筛选</p>
              </div>
              <el-icon class="action-arrow"><ArrowRight /></el-icon>
            </div>

            <div class="action-item" @click="goToAgentWorkshop">
              <div class="action-icon v3-icon">
                <el-icon><MagicStick /></el-icon>
              </div>
              <div class="action-content">
                <h3>Agent 工坊 <el-tag size="small" type="success">v3.0</el-tag></h3>
                <p>可视化创建和管理自定义 AI 智能体</p>
              </div>
              <el-icon class="action-arrow"><ArrowRight /></el-icon>
            </div>

            <div class="action-item" @click="goToMcpServers">
              <div class="action-icon v3-icon">
                <el-icon><Connection /></el-icon>
              </div>
              <div class="action-content">
                <h3>MCP 服务器 <el-tag size="small" type="success">v3.0</el-tag></h3>
                <p>管理外部工具服务器，扩展 AI 能力边界</p>
              </div>
              <el-icon class="action-arrow"><ArrowRight /></el-icon>
            </div>
          </div>
        </el-card>

        <!-- 流程配置 -->
        <el-card class="v2-features-card" header="流程配置" style="margin-top: 24px;">
          <div class="quick-actions">
            <div class="action-item" @click="goToWorkflow">
              <div class="action-icon">
                <el-icon><SetUp /></el-icon>
              </div>
              <div class="action-content">
                <h3>流程管理 <span class="advanced-chip">高级</span></h3>
                <p>可视化工作流编辑器，配置分析流程</p>
              </div>
              <el-icon class="action-arrow"><ArrowRight /></el-icon>
            </div>

            <div class="action-item" @click="goToAgents">
              <div class="action-icon">
                <el-icon><UserFilled /></el-icon>
              </div>
              <div class="action-content">
                <h3>Agent配置 <span class="advanced-chip">高级</span></h3>
                <p>管理和配置AI分析智能体</p>
              </div>
              <el-icon class="action-arrow"><ArrowRight /></el-icon>
            </div>

            <div class="action-item" @click="goToTools">
              <div class="action-icon">
                <el-icon><Tools /></el-icon>
              </div>
              <div class="action-content">
                <h3>工具管理 <span class="advanced-chip">高级</span></h3>
                <p>配置和管理分析工具</p>
              </div>
              <el-icon class="action-arrow"><ArrowRight /></el-icon>
            </div>

            <div class="action-item" @click="goToPrompts">
              <div class="action-icon">
                <el-icon><EditPen /></el-icon>
              </div>
              <div class="action-content">
                <h3>提示词管理 <span class="advanced-chip">高级</span></h3>
                <p>管理和优化AI提示词模板</p>
              </div>
              <el-icon class="action-arrow"><ArrowRight /></el-icon>
            </div>
          </div>
        </el-card>

        <!-- 最近分析 -->
        <el-card class="recent-analyses-card" header="最近分析" style="margin-top: 24px;">
          <el-table :data="recentAnalyses" style="width: 100%">
            <el-table-column prop="stock_code" label="股票代码" width="120" />
            <el-table-column prop="stock_name" label="股票名称" width="150" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)">
                  {{ getStatusText(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="start_time" label="创建时间" width="180">
              <template #default="{ row }">
                {{ formatTime(row.start_time) }}
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

        <!-- 市场快讯 -->
        <el-card class="market-news-card" style="margin-top: 24px;">
          <template #header>
            <span>市场快讯</span>
          </template>
          <div v-if="marketNews.length > 0" class="news-list">
            <div
              v-for="news in marketNews"
              :key="news.id"
              class="news-item"
              @click="openNewsUrl(news.url)"
            >
              <div class="news-title">{{ news.title }}</div>
              <div class="news-time">{{ formatTime(news.time) }}</div>
            </div>
          </div>
          <div v-else class="empty-state">
            <el-icon class="empty-icon"><InfoFilled /></el-icon>
            <p>暂无市场快讯</p>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：自选股和快讯 -->
      <el-col :span="8">
        <!-- 股票关注列表 -->
        <el-card class="favorites-card">
          <template #header>
            <div class="card-header">
              <span>股票关注列表</span>
              <el-button type="text" size="small" @click="goToFavorites">
                查看全部 <el-icon><ArrowRight /></el-icon>
              </el-button>
            </div>
          </template>

          <div v-if="favoriteStocks.length === 0" class="empty-favorites">
            <el-empty description="暂无自选股" :image-size="60">
              <el-button type="primary" size="small" @click="goToFavorites">
                添加到研究列表
              </el-button>
            </el-empty>
          </div>

          <div v-else class="favorites-list">
            <div
              v-for="stock in favoriteStocks.slice(0, 5)"
              :key="stock.stock_code"
              class="favorite-item"
              @click="viewStockDetail(stock)"
            >
              <div class="stock-info">
                <div class="stock-code">{{ stock.stock_code }}</div>
                <div class="stock-name">{{ stock.stock_name }}</div>
              </div>
              <div class="stock-price">
                <div class="current-price">¥{{ stock.current_price }}</div>
                <div
                  class="change-percent"
                  :class="getPriceChangeClass(stock.change_percent)"
                >
                  {{ stock.change_percent > 0 ? '+' : '' }}{{ Number(stock.change_percent).toFixed(2) }}%
                </div>
              </div>
            </div>
          </div>

          <div v-if="favoriteStocks.length > 5" class="favorites-footer">
            <el-button type="text" size="small" @click="goToFavorites">
              查看全部 {{ favoriteStocks.length }} 只自选股
            </el-button>
          </div>
        </el-card>

        <!-- 模拟交易账户 -->
        <el-card class="paper-trading-card" style="margin-top: 24px;">
          <template #header>
            <div class="card-header">
              <span>模拟交易账户</span>
              <el-button type="text" size="small" @click="goToPaperTrading">
                查看详情 <el-icon><ArrowRight /></el-icon>
              </el-button>
            </div>
          </template>

          <div v-if="paperAccount" class="paper-account-info">
            <!-- A股账户 -->
            <div class="account-section">
              <div class="account-section-title">🇨🇳 A股账户</div>
              <div class="account-item">
                <div class="account-label">现金</div>
                <div class="account-value">¥{{ formatMoney(getCurrencyAmount(paperAccount.cash, 'CNY')) }}</div>
              </div>
              <div class="account-item">
                <div class="account-label">持仓市值</div>
                <div class="account-value">¥{{ formatMoney(getCurrencyAmount(paperAccount.positions_value, 'CNY')) }}</div>
              </div>
              <div class="account-item">
                <div class="account-label">总资产</div>
                <div class="account-value primary">¥{{ formatMoney(getCurrencyAmount(paperAccount.equity, 'CNY')) }}</div>
              </div>
            </div>


          </div>

          <div v-else class="empty-state">
            <el-icon class="empty-icon"><InfoFilled /></el-icon>
            <p>暂无账户信息</p>
            <el-button type="primary" size="small" @click="goToPaperTrading">
              查看模拟交易
            </el-button>
          </div>
        </el-card>

        <!-- 多数据源同步 -->
        <MultiSourceSyncCard style="margin-top: 24px;" />
      </el-col>
    </el-row>

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
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import {
  TrendCharts,
  Search,
  Document,
  Files,
  List,
  ArrowRight,
  InfoFilled,
  Reading,
  PieChart,
  DocumentChecked,
  Tickets,
  SetUp,
  UserFilled,
  Tools,
  EditPen,
  ChatDotRound,
  Filter,
  MagicStick,
  Connection
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { AnalysisTask, AnalysisStatus } from '@/types/analysis'
import MultiSourceSyncCard from '@/components/Dashboard/MultiSourceSyncCard.vue'
import GuideDialog from '@/components/GuideDialog.vue'
import { favoritesApi } from '@/api/favorites'
import { analysisApi } from '@/api/analysis'
import { newsApi } from '@/api/news'
import { paperApi, type PaperAccountSummary } from '@/api/paper'
import { ensureReportExportAccess } from '@/utils/featureAccess'
import { request } from '@/api/request'

const router = useRouter()
const authStore = useAuthStore()
const appStore = useAppStore()
const displayVersion = computed(() => `v${appStore.version}`)

// 响应式数据
const userStats = ref({
  totalAnalyses: 0,
  successfulAnalyses: 0,
  dailyQuota: 1000,
  dailyUsed: 0,
  concurrentLimit: 3
})

const recentAnalyses = ref<AnalysisTask[]>([])

// 自选股数据
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

const goToSingleAnalysis = () => {
  router.push('/analysis/single')
}

const goToBatchAnalysis = () => {
  router.push('/analysis/batch')
}

const goToScreening = () => {
  router.push('/screening')
}

const goToQueue = () => {
  router.push('/queue')
}

const goToHistory = () => {
    router.push('/tasks/unified')
}

const goToLearning = () => {
  router.push('/learning')
}

const goToGuide = () => {
  router.push('/guide')
}

const goToPortfolio = () => {
  router.push('/portfolio')
}

const goToReview = () => {
  router.push('/review')
}

const goToTradingSystem = () => {
  router.push('/trading-system')
}

const goToWorkflow = () => {
  router.push('/workflow')
}

const goToAgents = () => {
  router.push('/workflow/agents')
}

const goToTools = () => {
  router.push('/workflow/tools')
}

const goToPrompts = () => {
  router.push('/settings/templates')
}

const goToAssistant = () => {
  router.push('/assistant')
}

const goToAgentWorkshop = () => {
  router.push('/workflow/agent-workshop')
}

const goToMcpServers = () => {
  router.push('/workflow/mcp-servers')
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
    const res = await fetch(`/api/reports/${reportId}/download?format=markdown`, {
      headers: {
        'Authorization': `Bearer ${authStore.token}`
      }
    })
    if (!res.ok) {
      const msg = `下载失败：HTTP ${res.status}`
      console.error(msg)
      ElMessage.error('下载失败，报告可能尚未生成')
      return
    }
    const blob = await res.blob()
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

const openNewsUrl = (url?: string) => {
  if (url) {
    window.open(url, '_blank')
  } else {
    ElMessage.info('该新闻暂无详情链接')
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

// 自选股相关方法
const goToFavorites = () => {
  router.push('/favorites')
}

const viewStockDetail = (stock: any) => {
  // 可以跳转到股票详情页或分析页
  router.push(`/analysis/single?stock_code=${stock.stock_code}`)
}

const getPriceChangeClass = (changePercent: number) => {
  if (changePercent > 0) return 'price-up'
  if (changePercent < 0) return 'price-down'
  return 'price-neutral'
}

const loadFavoriteStocks = async () => {
  try {
    const response = await favoritesApi.list()
    if (response.success && response.data) {
      favoriteStocks.value = response.data.map((item: any) => ({
        stock_code: item.stock_code,
        stock_name: item.stock_name,
        current_price: item.current_price || 0,
        change_percent: item.change_percent || 0
      }))
    }
  } catch (error) {
    console.error('加载自选股失败:', error)
  }
}

const loadRecentAnalyses = async () => {
  try {
    // 使用任务中心的用户任务接口，不传 limit 让后端返回所有记录
    const res = await analysisApi.getTaskList({
      offset: 0,
      // 不限定状态，展示最近任务；如需仅展示已完成可设为 'completed'
      status: undefined
    })

    // 兼容不同返回结构（ApiResponse 或直接 data）
    const body: any = (res as any)?.data?.data || (res as any)?.data || res || {}
    const allTasks = body.tasks || []

    // 在前端取最近10条
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
        title: item.title,
        time: item.publish_time,
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

// 格式化金额
const formatMoney = (value: number | null | undefined) => {
  // 🔥 修复：处理 NaN 和非数字值
  if (value == null || Number.isNaN(value as any) || typeof value !== 'number') {
    return '0.00'
  }
  return value.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}

const getCurrencyAmount = (
  value: number | { CNY: number } | undefined,
  currency: 'CNY'
) => {
  if (typeof value === 'number') {
    return currency === 'CNY' ? value : 0
  }
  return value?.CNY ?? 0
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
  
  // 加载自选股数据
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
        cursor: pointer;
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
          font-size: 14px;
          color: var(--el-text-color-primary);
          margin-bottom: 4px;
          line-height: 1.4;
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
</style>
