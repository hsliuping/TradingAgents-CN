<template>
  <div class="report-detail">
    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="10" animated />
    </div>

    <!-- 报告内容 -->
    <div v-else-if="report" class="report-content">
      <!-- 报告头部 -->
      <el-card class="report-header" shadow="never">
        <div class="header-content">
          <div class="title-section">
            <h1 class="report-title">
              <el-icon><Document /></el-icon>
              {{ report.stock_name || report.stock_symbol }} 研究报告
            </h1>
            <div class="report-meta">
              <el-tag type="primary">{{ report.stock_symbol }}</el-tag>
              <el-tag v-if="report.stock_name && report.stock_name !== report.stock_symbol" type="info">{{ report.stock_name }}</el-tag>
              <el-tag type="success">{{ getStatusText(report.status) }}</el-tag>
              <span class="meta-item">
                <el-icon><Calendar /></el-icon>
                {{ formatTime(report.created_at) }}
              </span>
              <span class="meta-item">
                <el-icon><User /></el-icon>
                {{ formatAnalysts(report.analysts) }}
              </span>
              <span v-if="report.model_info && report.model_info !== 'Unknown'" class="meta-item">
                <el-icon><Cpu /></el-icon>
                <el-tooltip :content="getModelDescription(report.model_info)" placement="top">
                  <el-tag type="info" style="cursor: help;">{{ report.model_info }}</el-tag>
                </el-tooltip>
              </span>
              <span v-if="report.research_depth" class="meta-item">
                <el-icon><DataAnalysis /></el-icon>
                <el-tooltip :content="getResearchDepthDescription(report.research_depth)" placement="top">
                  <el-tag type="warning" style="cursor: help;">深度: {{ report.research_depth }}</el-tag>
                </el-tooltip>
              </span>
            </div>
          </div>
          
          <div class="action-section">
            <el-dropdown trigger="click" @command="downloadReport">
              <el-button type="primary">
                <el-icon><Download /></el-icon>
                下载报告
                <el-icon class="el-icon--right"><arrow-down /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="markdown">
                    <el-icon><document /></el-icon> Markdown
                  </el-dropdown-item>
                  <el-dropdown-item command="docx">
                    <el-icon><document /></el-icon> Word 文档
                  </el-dropdown-item>
                  <el-dropdown-item command="pdf">
                    <el-icon><document /></el-icon> PDF
                  </el-dropdown-item>
                  <el-dropdown-item command="json" divided>
                    <el-icon><document /></el-icon> JSON (原始数据)
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-button @click="goBack">
              <el-icon><Back /></el-icon>
              返回
            </el-button>
          </div>
        </div>
      </el-card>

      <!-- 风险提示 -->
      <div class="risk-disclaimer">
        <el-alert
          type="warning"
          :closable="false"
          show-icon
        >
          <template #title>
            <div class="disclaimer-content">
              <el-icon class="disclaimer-icon"><WarningFilled /></el-icon>
              <div class="disclaimer-text">
                <p style="margin: 0 0 8px 0;"><strong>⚠️ 重要风险提示与免责声明</strong></p>
                <ul style="margin: 0; padding-left: 20px; line-height: 1.8;">
                  <li><strong>平台性质：</strong>本平台为AI辅助分析技术学习平台，专注于AI技术在证券与ETF分析领域的应用验证和技术学习。</li>
                  <li><strong>分析目的：</strong>所有分析结论仅用于学习和验证AI辅助分析技术，不作为真实交易操盘指导或投资依据。</li>
                  <li><strong>非投资建议：</strong>所有分析结果、评分、建议仅为技术验证参考，不构成任何买卖建议或投资决策依据。</li>
                  <li><strong>数据局限性：</strong>分析基于历史数据和公开信息，可能存在延迟、不完整或不准确的情况，无法预测未来市场走势。</li>
                  <li><strong>投资风险：</strong>股票与ETF投资均存在市场风险、流动性风险、政策风险等多种风险，可能导致本金损失。</li>
                  <li><strong>独立决策：</strong>投资者应基于自身风险承受能力、投资目标和财务状况独立做出投资决策。</li>
                  <li><strong>责任声明：</strong>使用本平台产生的任何投资决策及其后果由使用者自行承担，本平台不承担任何责任。</li>
                </ul>
              </div>
            </div>
          </template>
        </el-alert>
      </div>

      <!-- 研究简报 -->
      <el-card v-if="summaryDisplayContent" class="summary-card" shadow="never">
        <template #header>
          <div class="card-header">
            <el-icon><InfoFilled /></el-icon>
            <span>研究简报</span>
          </div>
        </template>
        <div class="summary-content markdown-content" v-html="renderMarkdown(summaryDisplayContent)"></div>
      </el-card>

      <TaskGrowthPanel
        v-if="growthTaskId"
        class="growth-card"
        :task-id="growthTaskId"
      />

      <!-- 报告模块 -->
      <el-card class="modules-card" shadow="never">
        <template #header>
          <div class="card-header">
            <el-icon><Files /></el-icon>
            <span>详细研究报告</span>
          </div>
        </template>
        
        <el-tabs v-model="activeModule" type="border-card">
          <el-tab-pane
            v-for="moduleName in detailedModuleNames"
            :key="moduleName"
            :label="getModuleDisplayName(moduleName)"
            :name="moduleName"
          >
            <div class="module-content">
              <div v-if="getModuleContent(report.reports[moduleName])" class="markdown-content">
                <div v-html="renderMarkdown(getModuleContent(report.reports[moduleName]) || '')"></div>
              </div>
              <div v-else class="json-content">
                <pre>{{ JSON.stringify(report.reports[moduleName], null, 2) }}</pre>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-card>
    </div>

    <!-- 错误状态 -->
    <div v-else class="error-container">
      <el-result
        icon="error"
        title="报告加载失败"
        sub-title="请检查报告ID是否正确或稍后重试"
      >
        <template #extra>
          <el-button type="primary" @click="goBack">返回列表</el-button>
        </template>
      </el-result>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { configApi, type LLMConfig } from '@/api/config'
import TaskGrowthPanel from '@/components/growth/TaskGrowthPanel.vue'
import {
  Document,
  Calendar,
  User,
  Download,
  Back,
  InfoFilled,
  Files,
  WarningFilled,
  DataAnalysis,
  Cpu,
  ArrowDown
} from '@element-plus/icons-vue'
import { ApiClient } from '@/api/request'
import { marked } from 'marked'

interface ReportDecision {
  action?: string
  analysis_view?: string
}

interface ReportDetailData {
  id: string | number
  analysis_id?: string | number
  task_id?: string
  stock_symbol: string
  stock_name?: string
  status: string
  created_at: string
  analysts: string[]
  model_info?: string
  research_depth?: number
  recommendation?: string
  reports: Record<string, any>
  confidence_score?: number
  risk_level?: string
  key_points?: string[]
  summary?: string
  task_type?: string
  decision?: ReportDecision
  report_manifest?: Array<{
    field: string
    display_name: string
    category?: string
    order: number
    is_primary?: boolean
  }>
}

// 路由和认证
const route = useRoute()
const router = useRouter()

// 配置 marked 以获得更完整的 Markdown 支持
marked.setOptions({ breaks: true, gfm: true })

// 响应式数据
const loading = ref(true)
const report = ref<ReportDetailData | null>(null)
const activeModule = ref('')
const llmConfigs = ref<LLMConfig[]>([]) // 存储所有模型配置
const growthTaskId = computed(() => report.value?.task_id || null)

const analystNameMap: Record<string, string> = {
  index_analyst: '大盘分析师',
  index_analyst_v2: '大盘分析师',
  sector_analyst: '板块分析师',
  sector_analyst_v2: '板块分析师',
  market_analyst: '市场分析师',
  market_analyst_v2: '市场分析师',
  fundamentals_analyst: '基本面分析师',
  fundamentals_analyst_v2: '基本面分析师',
  etf_analyst: 'ETF 分析师',
  etf_analyst_v2: 'ETF 分析师',
  news_analyst: '新闻分析师',
  news_analyst_v2: '新闻分析师',
  social_analyst: '社交媒体分析师',
  social_analyst_v2: '社交媒体分析师',
  sentiment_analyst: '社交媒体分析师',
  bull_researcher: '乐观情景研究员',
  bull_researcher_v2: '乐观情景研究员',
  bear_researcher: '审慎情景研究员',
  bear_researcher_v2: '审慎情景研究员',
  research_manager: '研究经理',
  research_manager_v2: '研究经理',
  trader: '研究整合员',
  trader_v2: '研究整合员',
  risky_analyst: '高弹性情景分析师',
  risky_analyst_v2: '高弹性情景分析师',
  safe_analyst: '防御情景分析师',
  safe_analyst_v2: '防御情景分析师',
  neutral_analyst: '基准情景分析师',
  neutral_analyst_v2: '基准情景分析师',
  risk_manager: '风险评估师',
  risk_manager_v2: '风险评估师',
  market: '市场分析师',
  fundamentals: '基本面分析师',
  etf: 'ETF 分析师',
  news: '新闻分析师',
  social: '社交媒体分析师',
  sentiment: '社交媒体分析师',
  technical: '市场分析师',
  '大盘指数分析师': '大盘分析师',
  '行业板块分析师': '板块分析师',
  '市场技术分析师': '市场分析师',
  '新闻事件分析师': '新闻分析师',
  '市场情绪分析师': '社交媒体分析师',
  '多头研究员': '乐观情景研究员',
  '空头研究员': '审慎情景研究员',
  '激进分析师': '高弹性情景分析师',
  '保守分析师': '防御情景分析师',
  '中性分析师': '基准情景分析师'
}

const moduleDisplayNameMap: Record<string, string> = {
  index_report: '📊 大盘分析师',
  sector_report: '🏭 板块分析师',
  market_report: '📈 市场分析师',
  sentiment_report: '💬 社交媒体分析师',
  news_report: '📰 新闻分析师',
  fundamentals_report: '💰 基本面分析师',
  bull_researcher: '🐂 积极证据研究员',
  bull_report: '🐂 积极证据研究',
  bear_researcher: '🐻 谨慎证据研究员',
  bear_report: '🐻 谨慎证据研究',
  research_team_decision: '🔬 研究整合员',
  trader_investment_plan: '🧩 研究整合员',
  risky_analyst: '⚡ 高弹性情景分析师',
  risky_opinion: '⚡ 高弹性情景研究观察',
  safe_analyst: '🛡️ 防御情景分析师',
  safe_opinion: '🛡️ 防御情景研究观察',
  neutral_analyst: '⚖️ 基准情景分析师',
  neutral_opinion: '⚖️ 基准情景研究观察',
  risk_management_decision: '👔 风险评估师',
  risk_assessment: '⚠️ 风险审阅',
  investment_plan: '🧾 研究简报',
  final_trade_decision: '🧾 综合研究结论',
  investment_debate_state: '🔬 研究团队分析（旧）',
  risk_debate_state: '⚖️ 风险团队分析（旧）',
  detailed_analysis: '📄 详细分析'
}

const manifestDisplayNameAliasMap: Record<string, string> = {
  '大盘分析 v2': '📊 大盘分析师',
  '大盘分析师 v2': '📊 大盘分析师',
  '板块分析 v2': '🏭 板块分析师',
  '板块分析师 v2': '🏭 板块分析师',
  '市场分析 v2': '📈 市场分析师',
  '市场分析师 v2': '📈 市场分析师',
  '市场技术分析': '📈 市场分析师',
  '基本面分析 v2': '💰 基本面分析师',
  '基本面分析师 v2': '💰 基本面分析师',
  '新闻分析 v2': '📰 新闻分析师',
  '新闻分析师 v2': '📰 新闻分析师',
  '新闻事件分析': '📰 新闻分析师',
  '舆情分析 v2': '💬 社交媒体分析师',
  '社交媒体分析师 v2': '💬 社交媒体分析师',
  '市场情绪分析': '💬 社交媒体分析师',
  '研究经理分析': '🔬 研究整合员',
  '研究经理 v2': '🔬 研究整合员',
  '研究经理': '🔬 研究整合员',
  '交易员计划': '🧩 研究整合员',
  '交易员 v2': '🧩 研究整合员',
  '交易员': '🧩 研究整合员',
  '研究整合员 v2': '🧩 研究整合员',
  '研究整合员': '🧩 研究整合员',
  '激进分析师': '⚡ 高弹性情景分析师',
  '激进分析师 v2': '⚡ 高弹性情景分析师',
  '保守分析师': '🛡️ 防御情景分析师',
  '保守分析师 v2': '🛡️ 防御情景分析师',
  '中性分析师': '⚖️ 基准情景分析师',
  '中性分析师 v2': '⚖️ 基准情景分析师',
  '风险管理者': '👔 风险评估师',
  '风险管理者 v2': '👔 风险评估师',
  '风险经理': '👔 风险评估师',
  '风险经理 v2': '👔 风险评估师',
  '风险评估': '⚠️ 风险审阅',
  '最终分析结果': '🧾 综合研究结论'
}

// 获取模型配置列表
const fetchLLMConfigs = async () => {
  try {
    const response = await configApi.getSystemConfig()
    llmConfigs.value = Array.isArray(response?.llm_configs) ? response.llm_configs : []
  } catch (error) {
    console.error('获取模型配置失败:', error)
  }
}

// 获取报告详情
const fetchReportDetail = async () => {
  loading.value = true
  try {
    const reportId = route.params.id as string

    const result = await ApiClient.get<any>(`/api/reports/${reportId}/detail`)

    if (result.success) {
      report.value = result.data

      // 设置默认激活的模块（跳过研究简报，优先定位到第一份详细研究报告）
      const reports = result.data.reports || {}
      const availableModules = Object.keys(reports)

      const manifest = Array.isArray(result.data.report_manifest) ? result.data.report_manifest : []
      const firstManifestModule = manifest.length > 0
        ? [...manifest]
            .sort((a, b) => a.order - b.order)
            .map(item => item.field)
            .find((field: string) => availableModules.includes(field))
        : undefined

      const orderedDetailedModules = moduleOrder.filter(name => {
        if (!availableModules.includes(name)) {
          return false
        }

        return name !== 'trader_investment_plan'
      })

      // 优先按照 report_manifest，再回退到详细模块顺序
      const firstModule = (firstManifestModule && firstManifestModule !== 'trader_investment_plan')
        ? firstManifestModule
        : orderedDetailedModules[0]
      if (firstModule) {
        activeModule.value = firstModule
      } else if (availableModules.length > 0) {
        const firstDetailedModule = availableModules.find(name => name !== 'trader_investment_plan')
        activeModule.value = firstDetailedModule || ''
      }
    } else {
      throw new Error(result.message || '获取报告详情失败')
    }
  } catch (error) {
    console.error('获取报告详情失败:', error)
    ElMessage.error('获取报告详情失败')
  } finally {
    loading.value = false
  }
}

// 下载报告
const downloadReport = async (format: string = 'markdown') => {
  if (!report.value) {
    ElMessage.warning('报告尚未加载完成')
    return
  }

  const currentReport = report.value
  try {
    // 显示加载提示
    const loadingMsg = ElMessage({
      message: `正在生成${getFormatName(format)}格式报告...`,
      type: 'info',
      duration: 0
    })

    const res: any = await ApiClient.get(`/api/reports/${currentReport.id}/download`, { format }, { responseType: 'blob', showLoading: false })

    loadingMsg.close()

    // 兼容：响应拦截器直接返回 Blob；兼容返回 { data: Blob } 的旧实现
    const blob = res instanceof Blob ? res : (res?.data instanceof Blob ? res.data : new Blob([res]))
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url

    // 根据格式设置文件扩展名
    const ext = getFileExtension(format)
    // 清理股票名称中的特殊字符（用于文件名）
    const cleanStockName = (currentReport.stock_name || '')
      .replace(/[/\\:*?"<>|]/g, '') // 移除文件名不允许的字符
      .replace(/\s+/g, '_') // 空格替换为下划线
      .trim()
    // 构建文件名：股票代码_股票名称_分析报告_日期
    const fileName = cleanStockName
      ? `${currentReport.stock_symbol}_${cleanStockName}_分析报告_${(currentReport as any).analysis_date}.${ext}`
      : `${currentReport.stock_symbol}_分析报告_${(currentReport as any).analysis_date}.${ext}`
    a.download = fileName

    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)

    ElMessage.success(`${getFormatName(format)}报告下载成功`)
  } catch (error: any) {
    console.error('下载报告失败:', error)

    // 显示详细错误信息
    if (error.message && error.message.includes('pandoc')) {
      ElMessage.error({
        message: 'Word 导出需要安装 pandoc 工具（PDF 导出不需要 pandoc）',
        duration: 5000
      })
    } else if (error.message && (error.message.includes('weasyprint') || error.message.includes('pdfkit'))) {
      ElMessage.error({
        message: 'PDF 导出需要安装 PDF 引擎：pip install weasyprint（推荐）',
        duration: 5000
      })
    } else {
      ElMessage.error(`下载报告失败: ${error.message || '未知错误'}`)
    }
  }
}

// 辅助函数：获取格式名称
const getFormatName = (format: string): string => {
  const names: Record<string, string> = {
    'markdown': 'Markdown',
    'docx': 'Word',
    'pdf': 'PDF',
    'json': 'JSON'
  }
  return names[format] || format
}

// 辅助函数：获取文件扩展名
const getFileExtension = (format: string): string => {
  const extensions: Record<string, string> = {
    'markdown': 'md',
    'docx': 'docx',
    'pdf': 'pdf',
    'json': 'json'
  }
  return extensions[format] || 'txt'
}

// 返回列表
const goBack = () => {
  router.push('/reports')
}

// 工具函数
const getStatusText = (status: string) => {
  const statusMap: Record<string, string> = {
    completed: '已完成',
    processing: '生成中',
    failed: '失败'
  }
  return statusMap[status] || status
}

const formatTime = (time: string) => {
  return new Date(time).toLocaleString('zh-CN')
}

const normalizeAnalystName = (analyst: string): string => {
  return analystNameMap[analyst] || analyst
}

// 将分析师英文名称转换为中文
const formatAnalysts = (analysts: string[] = []) => {
  return Array.from(new Set(analysts.map(normalizeAnalystName))).join('、')
}

// 获取模型的详细描述（从后端配置中获取）
const getModelDescription = (modelInfo: string) => {
  if (!modelInfo || modelInfo === 'Unknown') {
    return '未知模型'
  }

  // 1. 优先从后端配置中查找精确匹配
  const config = llmConfigs.value.find(c => c.model_name === modelInfo)
  if (config?.description) {
    return config.description
  }

  // 2. 尝试模糊匹配（处理版本号等变化）
  const fuzzyConfig = llmConfigs.value.find(c =>
    modelInfo.toLowerCase().includes(c.model_name.toLowerCase()) ||
    c.model_name.toLowerCase().includes(modelInfo.toLowerCase())
  )
  if (fuzzyConfig?.description) {
    return fuzzyConfig.description
  }

  // 3. 根据模型名称前缀提供通用描述
  const modelLower = modelInfo.toLowerCase()
  if (modelLower.includes('gpt')) {
    return `OpenAI ${modelInfo} - 强大的语言模型`
  } else if (modelLower.includes('claude')) {
    return `Anthropic ${modelInfo} - 高性能推理模型`
  } else if (modelLower.includes('qwen')) {
    return `阿里通义千问 ${modelInfo} - 中文优化模型`
  } else if (modelLower.includes('glm')) {
    return `智谱 ${modelInfo} - 综合性能优秀`
  } else if (modelLower.includes('deepseek')) {
    return `DeepSeek ${modelInfo} - 高性价比模型`
  } else if (modelLower.includes('ernie')) {
    return `百度文心 ${modelInfo} - 中文能力强`
  } else if (modelLower.includes('spark')) {
    return `讯飞星火 ${modelInfo} - 专业模型`
  } else if (modelLower.includes('moonshot')) {
    return `Moonshot ${modelInfo} - 长上下文模型`
  } else if (modelLower.includes('yi')) {
    return `零一万物 ${modelInfo} - 高性能模型`
  }

  // 4. 默认返回
  return `${modelInfo} - AI 大语言模型`
}

// 定义报告模块的展示顺序（按照分析流程顺序）
const moduleOrder = [
  // 第一阶段：宏观分析（2个）
  'index_report',
  'sector_report',

  // 第二阶段：分析师团队（4个）
  'market_report',
  'fundamentals_report',
  'sentiment_report',
  'news_report',

  // 第三阶段：研究团队（多情景研究 + 初步研究观察）
  'bull_researcher',
  'bull_report',
  'bear_researcher',
  'bear_report',
  'research_team_decision',
  // 'investment_plan',  // 🔑 已隐藏：与研究经理分析内容相同

  // 第四阶段：交易团队
  'trader_investment_plan',

  // 第五阶段：风险管理团队（风险辩论）
  'risky_analyst',
  'risky_opinion',
  'safe_analyst',
  'safe_opinion',
  'neutral_analyst',
  'neutral_opinion',
  'risk_management_decision',
  'risk_assessment',

  // 第六阶段：最终研究结论
  'final_trade_decision',  // 🔑 最终研究结论（风险管理后）

  // 兼容旧字段
  'investment_debate_state',
  'risk_debate_state',
  'detailed_analysis'
]

// 计算属性：按顺序返回存在的报告模块
const orderedModuleNames = computed(() => {
  if (!report.value?.reports) return []

  const availableModules = Object.keys(report.value.reports)

  // 动态模式：使用 report_manifest
  const manifest = report.value?.report_manifest as Array<{
    field: string; display_name: string; order: number
  }> | undefined
  if (manifest && manifest.length > 0) {
    const sorted = [...manifest].sort((a, b) => a.order - b.order)
    const manifestOrdered = sorted.map(m => m.field).filter(f => availableModules.includes(f))
    const remainingOrdered = moduleOrder.filter(name => {
      return availableModules.includes(name) && !manifestOrdered.includes(name)
    })
    const remaining = availableModules.filter(name => {
      return !manifestOrdered.includes(name) && !moduleOrder.includes(name)
    })

    return [...manifestOrdered, ...remainingOrdered, ...remaining]
  }

  // 旧逻辑：按 moduleOrder 排序
  const ordered = moduleOrder.filter(name => availableModules.includes(name))

  const remaining = availableModules.filter(name => !moduleOrder.includes(name))

  return [...ordered, ...remaining]
})

const isEtfReport = computed(() => {
  const analysts = report.value?.analysts || []
  return report.value?.task_type === 'etf_analysis' || analysts.includes('etf_analyst') || analysts.includes('etf_analyst_v2')
})

const normalizeModuleDisplayName = (displayName?: string, moduleName?: string) => {
  if (moduleName === 'fundamentals_report' && isEtfReport.value) {
    return '📊 ETF 分析师'
  }

  const normalized = (displayName || '').replace(/^【|】$/g, '').trim()
  if (normalized) {
    return manifestDisplayNameAliasMap[normalized] || normalized
  }

  if (moduleName) {
    return moduleDisplayNameMap[moduleName] || moduleName.replace(/_/g, ' ')
  }

  return ''
}

const getModuleDisplayName = (moduleName: string) => {
  // 动态模式：优先从 report_manifest 获取 display_name
  const manifest = report.value?.report_manifest as Array<{
    field: string; display_name: string
  }> | undefined
  if (manifest) {
    const item = manifest.find(m => m.field === moduleName)
    if (item?.display_name) return normalizeModuleDisplayName(item.display_name, moduleName)
  }

  return normalizeModuleDisplayName(undefined, moduleName)
}

/**
 * 将风险审阅 JSON 对象渲染为可读的 Markdown 文本。
 * 字段与后端 risk_assessment / risk_management_decision 结构保持一致。
 */
const formatRiskAssessment = (value: any): string | null => {
  if (!value || typeof value !== 'object') return null
  const riskLevel = value.risk_level || value.riskLevel
  const riskScore = value.risk_score ?? value.riskScore
  const reasoning = value.reasoning || value.conclusion || value.summary || value.assessment
  const keyRisks = value.key_risks || value.keyRisks || value.risks
  const riskControl = value.risk_control || value.riskControl || value.control || value.suggestions
  const investmentAdjustment = value.investment_adjustment || value.investmentAdjustment || value.adjustment

  if (riskLevel === undefined && riskScore === undefined && !reasoning && !riskControl && !investmentAdjustment) {
    return null
  }

  const parts: string[] = []
  if (riskLevel !== undefined) {
    parts.push(`**风险等级**：${riskLevel}`)
  }
  if (riskScore !== undefined) {
    const score = typeof riskScore === 'number' ? riskScore.toFixed(2) : riskScore
    parts.push(`**风险评分**：${score}`)
  }
  if (reasoning) {
    parts.push(`**评估结论**：${reasoning}`)
  }
  if (Array.isArray(keyRisks) && keyRisks.length > 0) {
    parts.push(`**核心风险**：`)
    keyRisks.forEach((risk: any) => {
      if (risk) parts.push(`- ${String(risk).trim()}`)
    })
  }
  if (riskControl) {
    parts.push(`**风控建议**：${riskControl}`)
  }
  if (investmentAdjustment) {
    parts.push(`**投资调整建议**：${investmentAdjustment}`)
  }

  return parts.join('\n\n')
}

const _stripJsonCodeFence = (text: string): string => {
  // 去除 ```json ... ``` 或 ``` ... ``` 代码块包裹
  let t = text.trim()
  const fenceMatch = t.match(/^```(?:json|JSON)?\s*\n([\s\S]*?)\n```\s*$/i)
  if (fenceMatch) {
    t = fenceMatch[1].trim()
  }
  return t
}

const _looksLikeRiskJson = (text: string): boolean => {
  const lowered = text.toLowerCase()
  return (
    text.startsWith('{') &&
    (lowered.includes('"risk_level"') ||
      lowered.includes('"risk_score"') ||
      lowered.includes('"reasoning"') ||
      lowered.includes('"key_risks"') ||
      lowered.includes('"risk_control"') ||
      lowered.includes('"investment_adjustment"'))
  )
}

const extractStructuredText = (value: any): string | null => {
  if (!value) return null

  if (typeof value === 'string') {
    // 先剥离 ```json 代码块，再判断是否为风险审阅 JSON
    const stripped = _stripJsonCodeFence(value.trim())
    if (!stripped) return null

    if (_looksLikeRiskJson(stripped)) {
      try {
        const parsed = JSON.parse(stripped)
        const riskText = formatRiskAssessment(parsed)
        if (riskText) return riskText
      } catch {
        // 不是合法 JSON，按普通文本返回
      }
    }
    // 如果原文是 ```json 代码块但不是风险 JSON，返回剥离后的内容
    return stripped !== value.trim() ? stripped : value.trim()
  }

  if (typeof value === 'object') {
    // 风险审阅结构化对象直接渲染为可读文本
    const riskText = formatRiskAssessment(value)
    if (riskText) return riskText

    // 对象里嵌套 content/text 字段时，递归尝试解析
    // 真实数据结构: { content: "```json\n{...}\n```", success: true }
    for (const key of ['content', 'markdown', 'text', 'message', 'report', 'judge_decision', 'risk_assessment', 'risk_management_decision']) {
      const item = value[key]
      if (item) {
        const nested = extractStructuredText(item)
        if (nested) return nested
      }
    }
  }

  return null
}

const normalizeDisplayedResearchText = (content: string) => {
  if (!content) return ''

  const replacements: Array<[RegExp, string]> = [
    [/交易分析计划/g, '研究整合意见'],
    [/交易员计划/g, '研究整合意见'],
    [/初步投资计划/g, '研究团队结论'],
    [/投资计划/g, '研究结论'],
    [/投资建议/g, '研究结论'],
    [/操作建议/g, '研究观点'],
    [/大盘指数分析/g, '大盘环境研究'],
    [/行业板块分析/g, '行业板块研究'],
    [/市场情绪分析/g, '情绪研究'],
    [/新闻事件分析/g, '新闻研究'],
    [/风险审阅摘要/g, '风险审阅结论'],
    [/综合研究简报/g, '综合研究结论'],
    [/风险管理决策/g, '风险审阅结论'],
    [/最终分析结果/g, '最终研究结论'],
    [/激进风险分析师/g, '高弹性情景分析师'],
    [/保守风险分析师/g, '防御情景分析师'],
    [/中性风险分析师/g, '基准情景分析师']
  ]

  return replacements.reduce((text, [pattern, replacement]) => text.replace(pattern, replacement), content)
}

const prepareMarkdownContent = (content: string) => {
  let preparedText = normalizeDisplayedResearchText(content || '').trim()

  if (!preparedText) {
    return ''
  }

  if (
    ((preparedText.startsWith('"') && preparedText.endsWith('"')) ||
      (preparedText.startsWith("'") && preparedText.endsWith("'"))) &&
    preparedText.length >= 2
  ) {
    preparedText = preparedText.slice(1, -1).trim()
  }

  const fencedMarkdownMatch = preparedText.match(/^```(?:markdown|md)?\s*\n([\s\S]*?)\n```\s*$/i)
  if (fencedMarkdownMatch) {
    preparedText = fencedMarkdownMatch[1].trim()
  }

  return preparedText
}

const renderMarkdown = (content: string) => {
  if (!content) return ''
  try {
    return marked.parse(prepareMarkdownContent(content)) as string
  } catch (e) {
    return `<pre style="white-space: pre-wrap; font-family: inherit;">${prepareMarkdownContent(content)}</pre>`
  }
}

// 🔥 提取模块内容（支持对象中的 content 字段）
const getModuleContent = (moduleData: any): string | null => {
  if (!moduleData) return null

  const extractedText = extractStructuredText(moduleData)
  if (extractedText) {
    return normalizeDisplayedResearchText(extractedText)
  }

  return null
}

// 获取分析深度描述
const getResearchDepthDescription = (depth: number) => {
  const descMap: Record<number, string> = {
    1: '快速分析 - 基础技术面和基本面分析',
    2: '标准分析 - 包含技术面、基本面和市场情绪分析',
    3: '深度分析 - 全面的多维度分析，包含详细的行业和竞争分析',
    4: '专家级分析 - 最全面的分析，包含所有维度和深度研究',
    5: '顶级分析 - 最高级别的分析深度，包含所有可能的分析维度'
  }
  return descMap[depth] || `分析深度: ${depth}`
}

const getResearchContentFingerprint = (moduleData: any) => {
  const prepared = prepareMarkdownContent(getModuleContent(moduleData) || '')
  if (!prepared) {
    return ''
  }

  const strippedTitleLines = prepared
    .split('\n')
    .map(line => line.trim())
    .filter(line => {
      const normalizedLine = line
        .replace(/^#{1,6}\s*/, '')
        .replace(/^[>*\-+\d.\s)]+/, '')
        .trim()

      return !['研究结论汇总', '研究经理简报', '研究团队结论', '研究结论', '研究简报'].includes(normalizedLine)
    })
    .join('\n')

  return strippedTitleLines
    .replace(/```[\s\S]*?```/g, '')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/^[-*+]\s+/gm, '')
    .replace(/^\d+[.)]\s+/gm, '')
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/__(.*?)__/g, '$1')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/\[(.*?)\]\([^)]*\)/g, '$1')
    .replace(/[>_*|~]/g, ' ')
    .replace(/[\s\u3000]+/g, '')
}

const userBriefContent = computed(() => {
  if (!report.value?.reports) return null
  return getModuleContent(report.value.reports.trader_investment_plan)
})

const summaryDisplayContent = computed(() => {
  return userBriefContent.value || getModuleContent(report.value?.summary) || ''
})

const detailedModuleNames = computed(() => {
  return orderedModuleNames.value.filter(name => {
    if (name === 'trader_investment_plan') {
      return false
    }

    if (name === 'investment_plan') {
      const reports = report.value?.reports || {}
      const researchDecision = getResearchContentFingerprint(reports.research_team_decision)
      const managerBrief = getResearchContentFingerprint(reports.investment_plan)
      if (researchDecision && researchDecision === managerBrief) {
        return false
      }
    }

    return true
  })
})

// 生命周期
onMounted(() => {
  fetchLLMConfigs() // 先加载模型配置
  fetchReportDetail() // 再加载报告详情
})
</script>

<style lang="scss" scoped>
.report-detail {
  .loading-container {
    padding: 24px;
  }

  .report-content {
    .report-header {
      margin-bottom: 24px;

      .header-content {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;

        .title-section {
          .report-title {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 24px;
            font-weight: 600;
            color: var(--el-text-color-primary);
            margin: 0 0 12px 0;
          }

          .report-meta {
            display: flex;
            align-items: center;
            gap: 16px;
            flex-wrap: wrap;

            .meta-item {
              display: flex;
              align-items: center;
              gap: 4px;
              color: var(--el-text-color-regular);
              font-size: 14px;
            }
          }
        }

        .action-section {
          display: flex;
          gap: 8px;
        }
      }
    }

    /* 风险提示样式 */
    .risk-disclaimer {
      margin-bottom: 24px;
      animation: fadeInDown 0.5s ease-out;
    }

    .risk-disclaimer :deep(.el-alert) {
      background: linear-gradient(135deg, #fff3cd 0%, #ffe69c 100%);
      border: 2px solid #ffc107;
      border-radius: 12px;
      padding: 16px 20px;
      box-shadow: 0 4px 12px rgba(255, 193, 7, 0.2);
    }

    .risk-disclaimer :deep(.el-alert__icon) {
      font-size: 24px;
      color: #ff6b00;
    }

    .disclaimer-content {
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 15px;
      line-height: 1.6;
    }

    .disclaimer-icon {
      font-size: 24px;
      color: #ff6b00;
      flex-shrink: 0;
      animation: pulse 2s ease-in-out infinite;
    }

    .disclaimer-text {
      color: #856404;
      flex: 1;
    }

    .disclaimer-text strong {
      color: #d63031;
      font-size: 16px;
      font-weight: 700;
    }

    @keyframes pulse {
      0%, 100% {
        transform: scale(1);
        opacity: 1;
      }
      50% {
        transform: scale(1.1);
        opacity: 0.8;
      }
    }

    @keyframes fadeInDown {
      from {
        opacity: 0;
        transform: translateY(-20px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    .summary-card,
    .metrics-card,
    .growth-card,
    .modules-card {
      margin-bottom: 24px;

      .card-header {
        display: flex;
        align-items: center;
        gap: 8px;
        font-weight: 600;
      }
    }

    .summary-content {
      line-height: 1.6;
      color: var(--el-text-color-primary);
    }

    .metrics-content {
      .metric-item {
        text-align: center;
        padding: 24px;
        border: 1px solid var(--el-border-color-light);
        border-radius: 12px;
        background: var(--el-fill-color-blank);
        transition: all 0.3s ease;

        &:hover {
          box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
          transform: translateY(-2px);
        }

        .metric-label {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
          font-size: 15px;
          font-weight: 500;
          color: var(--el-text-color-regular);
          margin-bottom: 16px;

          .el-icon {
            font-size: 18px;
          }
        }

        .metric-value {
          font-size: 18px;
          font-weight: 600;
          color: var(--el-color-primary);
        }

        .recommendation-value {
          font-size: 16px;
          line-height: 1.6;
          color: var(--el-text-color-primary);
          
          .core-conclusion {
            text-align: left;
            padding: 12px;
            background: var(--el-fill-color-light);
            border-radius: 8px;
            border-left: 3px solid var(--el-color-primary);
            
            strong {
              color: var(--el-color-primary);
              font-weight: 600;
            }
          }
        }
      }

      // 置信度评分样式
      .confidence-item {
        .confidence-display {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 8px;

          .confidence-value {
            display: flex;
            align-items: baseline;
            gap: 4px;
            margin-top: 8px;

            .confidence-number {
              font-size: 32px;
              font-weight: 700;
              color: var(--el-color-primary);
            }

            .confidence-unit {
              font-size: 16px;
              color: var(--el-text-color-regular);
            }
          }

          .confidence-label {
            font-size: 14px;
            font-weight: 500;
            color: var(--el-text-color-secondary);
          }
        }
      }

      // 风险等级样式
      .risk-item {
        .risk-display {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 12px;

          .risk-stars {
            display: flex;
            gap: 8px;
            font-size: 28px;

            .star-icon {
              color: #DCDFE6;
              transition: all 0.3s ease;

              &.active {
                color: #F7BA2A;
                animation: starPulse 0.6s ease-in-out;
              }
            }
          }

          .risk-label {
            font-size: 18px;
            font-weight: 700;
            margin-top: 4px;
          }

          .risk-description {
            font-size: 13px;
            color: var(--el-text-color-secondary);
            text-align: center;
            line-height: 1.4;
            max-width: 200px;
          }
        }
      }

      .key-points {
        margin-top: 32px;
        padding-top: 24px;
        border-top: 1px solid var(--el-border-color-lighter);

        h4 {
          display: flex;
          align-items: center;
          gap: 8px;
          margin: 0 0 16px 0;
          font-size: 16px;
          font-weight: 600;
          color: var(--el-text-color-primary);

          .el-icon {
            font-size: 18px;
            color: var(--el-color-primary);
          }
        }

        ul {
          margin: 0;
          padding: 0;
          list-style: none;

          li {
            display: flex;
            align-items: flex-start;
            gap: 8px;
            margin-bottom: 12px;
            padding: 12px;
            background: var(--el-fill-color-light);
            border-radius: 8px;
            line-height: 1.6;
            transition: all 0.2s ease;

            &:hover {
              background: var(--el-fill-color);
            }

            .point-icon {
              flex-shrink: 0;
              margin-top: 2px;
              font-size: 16px;
              color: var(--el-color-success);
            }
          }
        }
      }
    }

    // 星星脉冲动画
    @keyframes starPulse {
      0%, 100% {
        transform: scale(1);
      }
      50% {
        transform: scale(1.2);
      }
    }

    .module-content {
      .markdown-content {
        line-height: 1.6;
        
        :deep(h1), :deep(h2), :deep(h3) {
          margin: 16px 0 8px 0;
          color: var(--el-text-color-primary);
        }

        :deep(h1) { font-size: 24px; }
        :deep(h2) { font-size: 20px; }
        :deep(h3) { font-size: 16px; }
      }

      .json-content {
        pre {
          background: var(--el-fill-color-light);
          padding: 16px;
          border-radius: 8px;
          overflow-x: auto;
          font-size: 14px;
          line-height: 1.4;
        }
      }
    }
  }

  .error-container {
    padding: 48px 24px;
  }
}
</style>
